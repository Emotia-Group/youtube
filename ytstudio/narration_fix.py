"""CORRECTOR DE ERRORES DE NARRACIÓN — quita del audio y del guion los
tropiezos evidentes de una grabación propia.

Hasta v0.39 la grabación era verdad absoluta: si el narrador arrancaba mal y
volvía a empezar, ese falso arranque terminaba en el video Y en los
subtítulos. Este módulo detecta los errores EVIDENTES, corta el audio real
(no solo el texto: si no, la voz seguiría diciéndolo) y avisa de cada
corrección.

Regla de oro: ante la duda, NO se corta. Un falso positivo destruye contenido
legítimo del creador; un falso negativo solo deja un tropiezo que ya estaba.
Por eso cada detector exige EVIDENCIA CONVERGENTE (varias señales a la vez),
no una sola pista.

Cinco detectores deterministas (sin costo, sin modelo):

1. FALSO ARRANQUE: el narrador empieza una frase, se corta y la reinicia.
   Evidencia: (a) el reintento REPITE las primeras palabras del intento,
   (b) hay una PAUSA real entre ambos, (c) el intento quedó TRUNCADO (corto
   y sin puntuación de cierre). Las tres juntas — una anáfora retórica
   («El registro dice esto. El registro dice aquello») no cumple (c).
2. FRASE REINICIADA: el intento terminó «bien» según Whisper (con
   puntuación), pero tras una pausa real el narrador lo vuelve a decir desde
   el principio — coincidencia larga (≥4 palabras) que el reintento continúa,
   o la frase completa repetida tras una pausa clara. Cubre el redo que el
   detector 1 no puede ver.
3. REPETICIÓN INMEDIATA de la misma palabra («el el registro»).
4. MULETILLA aislada («eh», «este») rodeada de pausas — NUNCA conectores
   discursivos («es decir», «o sea»): esos son contenido.
5. MARCADOR EXPLÍCITO de error («voy de nuevo», «corrijo», «otra vez»): se
   borra el marcador Y el intento anterior hasta el inicio de la frase.

Todos los cortes llevan GUARDAS DE EMPALME: el corte termina dentro de la
pausa, a 100-350 ms del inicio nominal de la palabra que se conserva (los
tiempos de Whisper traen ±100 ms de error; sin guarda, el empalme se comía
el ataque de la palabra siguiente y sonaba a tartamudeo).

Y una capa opcional con el MODELO (`review_with_llm`) que juzga los casos
ambiguos que la heurística no puede decidir sola — la inteligencia que
distingue un tropiezo de un recurso retórico.
"""
from __future__ import annotations

import re
import unicodedata

# --- normalización --------------------------------------------------------

_PUNCT_END = ".!?…"


def norm(text: str) -> str:
    """minúsculas, sin tildes y sin puntuación: «registró,» → «registro».
    Así un reintento que corrige la palabra sigue reconociéndose."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", t)


# Muletillas que SOLO se quitan si van aisladas entre pausas (nunca dentro de
# una frase fluida, donde pueden ser palabras legítimas: «este libro»).
# - VOCAL: sonidos sin contenido («eh», «mmm») — aislados, siempre tropiezo.
# - WORD: palabras reales usadas como relleno («este…», «bueno…») — además de
#   aisladas, NO pueden venir tras puntuación (ahí abren o retoman frase
#   legítimamente: «Bueno, sigamos»).
# Los CONECTORES DISCURSIVOS («es decir», «o sea», «en fin», «ahora bien») NO
# están y NUNCA deben estar aquí: enlazan ideas, y el narrador hace pausa
# natural alrededor («…térmica; es decir, el tejido…») — v0.40.0 los cortaba
# como "muletilla aislada" y destruía contenido legítimo (caso real del
# usuario). Si alguna vez son relleno de verdad, lo decide la revisión IA con
# contexto, nunca una lista.
VOCAL_FILLERS = {"eh", "ehh", "em", "emm", "mmm", "mm", "ah", "aah"}
WORD_FILLERS = {"este", "esto", "bueno", "digamos", "verdad"}
FILLERS = VOCAL_FILLERS | WORD_FILLERS  # compat: conjunto completo

# Marcadores donde el narrador DICE que se equivocó.
RESTART_MARKERS = [
    ("voy", "de", "nuevo"), ("otra", "vez"), ("corrijo"), ("repito"),
    ("perdon",), ("perdón",), ("me", "equivoque"), ("lo", "repito"),
    ("empiezo", "de", "nuevo"), ("desde", "el", "principio"),
    ("a", "ver", "otra", "vez"), ("nuevamente",),
]
_MARKERS = [tuple(m) if isinstance(m, tuple) else (m,) for m in RESTART_MARKERS]


def flatten(segments: list[dict]) -> list[dict]:
    """Todas las palabras del audio en una sola lista ordenada, con su
    segmento de origen (para poder reconstruir después)."""
    words: list[dict] = []
    for si, seg in enumerate(segments):
        for w in (seg.get("words") or []):
            if (w.get("text") or "").strip():
                words.append({"start": float(w["start"]), "end": float(w["end"]),
                              "text": w["text"].strip(), "seg": si})
    words.sort(key=lambda w: w["start"])
    return words


# --- detectores -----------------------------------------------------------

def _gap(words: list[dict], i: int) -> float:
    """Silencio entre la palabra i y la i+1."""
    if i + 1 >= len(words):
        return 0.0
    return max(0.0, words[i + 1]["start"] - words[i]["end"])


def _cut_end(words: list[dict], last_idx: int) -> float:
    """Fin SEGURO de un corte cuyo último tramo borrado es la palabra
    last_idx: dentro de la pausa que sigue, dejando un margen antes del
    inicio nominal de la palabra siguiente. Los tiempos de Whisper traen
    ±100 ms de error — cortar exactamente en el 'start' de la palabra que se
    conserva puede comerse su ataque real, y el empalme suena como un gageo
    («e-el tejido», caso real del usuario)."""
    if last_idx + 1 >= len(words):
        return words[last_idx]["end"]
    nxt = words[last_idx + 1]["start"]
    gap = max(0.0, nxt - words[last_idx]["end"])
    guard = min(0.35, max(0.10, gap * 0.5))
    return max(words[last_idx]["end"], nxt - guard)


def _cut_start(words: list[dict], idx: int) -> float:
    """Inicio seguro de un corte que empieza en la palabra idx: un pelo antes
    de su inicio nominal (dentro del silencio previo, si lo hay) para no dejar
    el arranque de la palabra borrada sonando en el empalme."""
    w = words[idx]
    if idx == 0:
        return w["start"]
    gap = max(0.0, w["start"] - words[idx - 1]["end"])
    return w["start"] - min(0.06, gap * 0.3)


def detect_false_starts(words: list[dict], min_pause: float = 0.30,
                        max_attempt_words: int = 9) -> list[dict]:
    """FALSO ARRANQUE (el caso real del usuario: «El registró veterinario»
    …2s… «El registro veterinario oficial es la evidencia…»).

    Se recorre cada PAUSA: se mira el arranque que viene después y se
    compara con las últimas palabras de antes. Si el reintento repite ese
    arranque y lo de antes quedó truncado, el intento fallido se corta."""
    cuts: list[dict] = []
    n = len(words)
    for i in range(n - 1):
        pause = _gap(words, i)
        if pause < min_pause:
            continue
        # Palabras del intento previo: desde el inicio de su frase hasta i.
        start_idx = _phrase_start(words, i)
        attempt = words[start_idx:i + 1]
        if not attempt or len(attempt) > max_attempt_words:
            continue
        # (c) TRUNCADO: no termina en puntuación de cierre. Una frase
        # terminada es contenido legítimo, no un tropiezo.
        if attempt[-1]["text"].rstrip()[-1:] in _PUNCT_END:
            continue
        # (a) el reintento repite el intento COMPLETO: todo lo que el
        # narrador alcanzó a decir se vuelve a decir. Una coincidencia
        # PARCIAL de arranque («ni en…», «tuvo la…», «luego las…») es el
        # patrón de las ENUMERACIONES y anáforas — caso real: en v0.42.0
        # este detector cortó «ni en América Latina,» y «ni en Europa,» de
        # una enumeración porque el siguiente ítem repetía «ni en». Un redo
        # de verdad re-dice el intento entero.
        k = _overlap_len(attempt, words[i + 1:], max_k=len(attempt))
        if k <= 0 or k < len(attempt):
            continue
        cuts.append({
            "kind": "falso_arranque",
            "start": _cut_start(words, start_idx), "end": _cut_end(words, i),
            "text": " ".join(w["text"] for w in attempt),
            "reason": (f"reinicio de frase: se repite «"
                       + " ".join(w["text"] for w in words[i + 1:i + 1 + k])
                       + f"» tras una pausa de {pause:.1f}s"),
            "confidence": "alta" if k >= 2 else "media",
        })
    return cuts


def _phrase_start(words: list[dict], i: int) -> int:
    """Índice donde empieza la frase que termina en i (tras puntuación fuerte
    o tras una pausa larga)."""
    j = i
    while j > 0:
        prev = words[j - 1]["text"].rstrip()
        if prev[-1:] in _PUNCT_END:
            break
        if _gap(words, j - 1) >= 0.6:
            break
        j -= 1
    return j


def _overlap_len(attempt: list[dict], rest: list[dict],
                 max_k: int = 6) -> int:
    """Cuántas palabras iniciales comparten el intento y el reintento. Exige
    2 palabras, o 1 si es larga (≥6 letras): con una palabra corta («el»,
    «y») la coincidencia sería casual."""
    best = 0
    limit = min(len(attempt), len(rest), max_k)
    for k in range(1, limit + 1):
        a = [norm(w["text"]) for w in attempt[:k]]
        b = [norm(w["text"]) for w in rest[:k]]
        if a == b and all(a):
            best = k
    if best == 1 and len(norm(attempt[0]["text"])) < 6:
        return 0
    return best


def detect_immediate_repeats(words: list[dict],
                             max_gap: float = 0.8) -> list[dict]:
    """La misma palabra dos veces seguidas («el el registro»). Se quita la
    PRIMERA (la segunda es la que enlaza con lo que sigue)."""
    cuts = []
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if not norm(a["text"]) or norm(a["text"]) != norm(b["text"]):
            continue
        if _gap(words, i) > max_gap:
            continue
        # números y palabras de una letra pueden repetirse legítimamente
        if len(norm(a["text"])) < 2 or norm(a["text"]).isdigit():
            continue
        cuts.append({"kind": "repeticion", "start": _cut_start(words, i),
                     "end": _cut_end(words, i), "text": a["text"],
                     "reason": f"palabra repetida: «{a['text']} {b['text']}»",
                     "confidence": "alta"})
    return cuts


def _prefix_overlap(attempt: list[dict], rest: list[dict]) -> int:
    """Cuántas palabras iniciales de `attempt` se repiten, en orden, al
    comienzo de `rest` (normalizadas: tildes y puntuación fuera)."""
    k = 0
    for a, b in zip(attempt, rest):
        if not norm(a["text"]) or norm(a["text"]) != norm(b["text"]):
            break
        k += 1
    return k


def detect_sentence_restarts(words: list[dict],
                             min_pause: float = 0.35,
                             max_attempt_words: int = 18) -> list[dict]:
    """REDO DE FRASE: el narrador termina (o casi) una frase, hace una pausa
    y la VUELVE A DECIR desde el principio. Es el caso que detect_false_starts
    no cubre: si Whisper le puso puntuación de cierre al intento («El registró
    veterinario.»), la condición de truncado lo protegía y el redo se quedaba
    ENTERO en el video (reportado por el usuario en v0.41.0).

    Evidencia convergente exigida (una anáfora retórica no la cumple):
    - el reintento repite el intento COMPLETO (≥3 palabras): todo lo que el
      narrador dijo se vuelve a decir. Una coincidencia PARCIAL de arranque
      («ni en…», «tuvo la…») es el patrón de las enumeraciones y anáforas
      (caso real que v0.42.0 cortó mal), nunca base suficiente para cortar.
    - pausa real proporcional a la ambigüedad: si el reintento CONTINÚA más
      allá del intento (lo corrige/completa) hace falta una pausa larga
      (≥1.2 s — el eco retórico de extensión «Nadie lo sabía. Nadie lo sabía
      hasta hoy.» se dice con pausa corta; un redo real viene tras un reset
      largo, como los 2 s del caso del usuario). Si es una repetición
      idéntica: ≥0.8 s (≥0.5 s con ≥5 palabras — cuanto más larga la
      coincidencia, menos probable el eco retórico).
    Se corta el PRIMER intento; el reintento (la versión buena) se conserva."""
    cuts: list[dict] = []
    n = len(words)
    for i in range(n - 1):
        pause = _gap(words, i)
        if pause < min_pause:
            continue
        start_idx = _phrase_start(words, i)
        attempt = words[start_idx:i + 1]
        if len(attempt) < 3 or len(attempt) > max_attempt_words:
            continue
        rest = words[i + 1:]
        k = _prefix_overlap(attempt, rest)
        if k < len(attempt):
            continue  # cobertura COMPLETA o nada (protege enumeraciones)
        # ¿El reintento SIGUE la frase más allá del intento (lo corrige o
        # completa), o fue una repetición idéntica que terminó ahí?
        j = i + k  # última palabra re-dicha, en índice global
        ended = (words[j]["text"].rstrip()[-1:] in _PUNCT_END
                 or j == n - 1 or _gap(words, j) >= 0.5)
        need = (0.5 if k >= 5 else 0.8) if ended else 1.2
        if pause < need:
            continue
        cuts.append({
            "kind": "falso_arranque",
            "start": _cut_start(words, start_idx), "end": _cut_end(words, i),
            "text": " ".join(w["text"] for w in attempt),
            "reason": (f"frase reiniciada: tras una pausa de {pause:.1f}s se "
                       "repite «"
                       + " ".join(w["text"] for w in rest[:k]) + "»"),
            "confidence": "alta" if k >= 4 else "media",
        })
    return cuts


def detect_fillers(words: list[dict], min_around: float = 0.25) -> list[dict]:
    """Muletillas AISLADAS: rodeadas de pausa a ambos lados. Dentro de una
    frase fluida no se tocan (pueden ser palabras reales). Ya NO se detectan
    frases conectoras («es decir», «o sea»): enlazan ideas y llevan pausa
    natural alrededor — cortarlas destruye contenido legítimo."""
    cuts = []
    for i, w in enumerate(words):
        token = norm(w["text"])
        if token not in FILLERS:
            continue
        prev_txt = words[i - 1]["text"].rstrip() if i > 0 else ""
        # Una palabra-relleno tras puntuación abre o retoma frase de forma
        # legítima («Bueno, sigamos» · «…terminó. Este fue el resultado»):
        # la pausa alrededor la explica la puntuación, no el tropiezo.
        if token in WORD_FILLERS and prev_txt[-1:] in ",.;:!?…":
            continue
        gap_before = (w["start"] - words[i - 1]["end"]) if i > 0 else 99
        gap_after = _gap(words, i) if i + 1 < len(words) else 99
        if gap_before >= min_around and gap_after >= min_around:
            cuts.append({"kind": "muletilla",
                         "start": _cut_start(words, i),
                         "end": _cut_end(words, i),
                         "text": w["text"],
                         "reason": f"muletilla aislada: «{w['text']}»",
                         "confidence": "media"})
    return cuts


def detect_explicit_restarts(words: list[dict]) -> list[dict]:
    """El narrador DICE que se equivocó («voy de nuevo», «corrijo»): se borra
    el marcador y el intento anterior hasta el inicio de su frase."""
    cuts = []
    n = len(words)
    for i in range(n):
        for m in _MARKERS:
            k = len(m)
            if i + k > n:
                continue
            if tuple(norm(w["text"]) for w in words[i:i + k]) != m:
                continue
            start_idx = _phrase_start(words, max(0, i - 1))
            end_idx = i + k - 1
            cuts.append({
                "kind": "correccion_explicita",
                "start": _cut_start(words, start_idx),
                "end": _cut_end(words, end_idx),
                "text": " ".join(w["text"] for w in words[start_idx:end_idx + 1]),
                "reason": f"el narrador anuncia la corrección: «{' '.join(m)}»",
                "confidence": "alta"})
            break
    return cuts


def detect_all(segments: list[dict]) -> list[dict]:
    """Todos los detectores deterministas, ya fusionados y ordenados."""
    words = flatten(segments)
    if len(words) < 3:
        return []
    cuts = (detect_explicit_restarts(words) + detect_false_starts(words)
            + detect_sentence_restarts(words)
            + detect_immediate_repeats(words) + detect_fillers(words))
    return merge_cuts(cuts)


def merge_cuts(cuts: list[dict]) -> list[dict]:
    """Ordena y funde los tramos que se solapan (un mismo tropiezo puede
    dispararse por dos detectores)."""
    if not cuts:
        return []
    cuts = sorted(cuts, key=lambda c: (c["start"], c["end"]))
    out = [dict(cuts[0])]
    for c in cuts[1:]:
        last = out[-1]
        if c["start"] <= last["end"] + 0.01:
            if c["end"] > last["end"]:
                last["end"] = c["end"]
                last["text"] = (last["text"] + " " + c["text"]).strip()
                last["reason"] = last["reason"] + " + " + c["reason"]
        else:
            out.append(dict(c))
    return out


# --- aplicación sobre texto y tiempos -------------------------------------

def apply_to_segments(segments: list[dict], cuts: list[dict]) -> list[dict]:
    """Quita las palabras cortadas y DESPLAZA los tiempos, para que el texto,
    los subtítulos y las escenas encajen con el audio ya recortado."""
    if not cuts:
        return segments

    def shift(t: float) -> float:
        """Tiempo en el audio nuevo: se resta todo lo cortado antes de t."""
        removed = 0.0
        for c in cuts:
            if c["end"] <= t:
                removed += c["end"] - c["start"]
            elif c["start"] < t < c["end"]:
                removed += t - c["start"]
        return round(max(0.0, t - removed), 3)

    def dropped(w: dict) -> bool:
        mid = (float(w["start"]) + float(w["end"])) / 2
        return any(c["start"] <= mid < c["end"] for c in cuts)

    out = []
    for seg in segments:
        words = [w for w in (seg.get("words") or []) if not dropped(w)]
        if not words:
            continue
        new_words = [{"start": shift(float(w["start"])),
                      "end": shift(float(w["end"])),
                      "text": w["text"]} for w in words]
        text = " ".join(w["text"] for w in new_words).strip()
        text = re.sub(r"\s+([,.;:!?…])", r"\1", text)
        out.append({"start": new_words[0]["start"], "end": new_words[-1]["end"],
                    "text": text, "words": new_words})
    return out


def apply_to_audio(src, dest, cuts: list[dict], fade: float = 0.012) -> bool:
    """Corta de verdad los tramos del audio y devuelve True si se escribió.
    Cada juntura lleva un fundido de ~12 ms: sin él, el empalme hace 'clic'."""
    from ytstudio.utils.media import probe_duration, run_ffmpeg
    if not cuts:
        return False
    total = probe_duration(src)
    keeps: list[tuple[float, float]] = []
    cursor = 0.0
    for c in sorted(cuts, key=lambda x: x["start"]):
        if c["start"] > cursor + 0.02:
            keeps.append((cursor, c["start"]))
        cursor = max(cursor, c["end"])
    if cursor < total - 0.02:
        keeps.append((cursor, total))
    if not keeps:
        return False
    parts, labels = [], []
    for i, (a, b) in enumerate(keeps):
        d = b - a
        f = min(fade, max(0.0, d / 3))
        parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:st=0:d={f:.3f},"
                     f"afade=t=out:st={max(0.0, d - f):.3f}:d={f:.3f}[k{i}]")
        labels.append(f"[k{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + \
        f"concat=n={len(keeps)}:v=0:a=1[out]"
    run_ffmpeg(["-i", str(src), "-filter_complex", graph, "-map", "[out]",
                "-c:a", "libmp3lame", "-q:a", "2", str(dest)],
               "recorte de errores de narración")
    return True


# --- capa con modelo (los casos que la heurística no puede decidir) -------

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "errores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "inicio_palabra": {"type": "integer"},
                    "fin_palabra": {"type": "integer"},
                    "tipo": {"type": "string",
                             "enum": ["falso_arranque", "repeticion",
                                      "muletilla", "correccion_explicita"]},
                    "motivo": {"type": "string"},
                    "seguridad": {"type": "string",
                                  "enum": ["alta", "media", "baja"]},
                },
                "required": ["inicio_palabra", "fin_palabra", "tipo",
                             "motivo", "seguridad"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["errores"],
    "additionalProperties": False,
}


def review_with_llm(llm, segments: list[dict], lang: str = "español",
                    known: list[dict] | None = None) -> list[dict]:
    """Segunda opinión del modelo sobre la transcripción con tiempos: caza
    los tropiezos que la heurística no ve (una reformulación con otras
    palabras, un dato dicho a medias) y SOLO esos — no toca el contenido.
    Nunca rompe la fase: si falla, se queda con lo determinista."""
    words = flatten(segments)
    if not words or getattr(llm, "is_mock", False):
        return []
    listado = "\n".join(
        f"[{i}] {w['text']}"
        + (f"  ⏸{_gap(words, i):.1f}s" if _gap(words, i) >= 0.3 else "")
        for i, w in enumerate(words))
    ya = ""
    if known:
        ya = ("\nYa se van a cortar estos tramos (NO los repitas):\n"
              + "\n".join(f"- «{c['text']}» ({c['kind']})" for c in known))
    system = (
        f"Eres editor de audio de documentales en {lang}. Recibes la "
        "transcripción PALABRA A PALABRA de una grabación real, con las "
        "pausas marcadas, y detectas ÚNICAMENTE los tropiezos EVIDENTES de "
        "grabación. Eres extremadamente conservador: ante la duda, NO marcas "
        "nada. Borrar contenido legítimo del narrador es mucho peor que "
        "dejar pasar un tropiezo.")
    prompt = (
        "Marca los tramos que son claramente un ERROR DE GRABACIÓN:\n"
        "- falso_arranque: empieza una frase, se corta y la reinicia (con "
        "las mismas palabras o reformulada) INMEDIATAMENTE después.\n"
        "- repeticion: repite palabras o una frase entera sin intención, "
        "SEGUIDAS (el reintento viene justo después del tropiezo).\n"
        "- muletilla: relleno vocal aislado sin contenido ('eh', 'mmm'…).\n"
        "- correccion_explicita: dice que se equivocó ('voy de nuevo', "
        "'corrijo', 'perdón').\n\n"
        "NO marques JAMÁS:\n"
        "- conectores discursivos («es decir», «o sea», «en fin», «ahora "
        "bien», «dicho esto»): enlazan ideas y son contenido, aunque lleven "
        "pausas alrededor.\n"
        "- una frase o idea que se retoma MÁS TARDE en la narración (a "
        "muchas palabras de distancia): reformular o recapitular es un "
        "recurso del narrador, no un tropiezo. Un error de grabación y su "
        "reintento son SIEMPRE contiguos.\n"
        "- repeticiones RETÓRICAS con intención (anáforas, énfasis), "
        "enumeraciones, muletillas integradas en una frase fluida, ni nada "
        "que forme parte del contenido. Si dudas, no lo marques.\n"
        "Indica el rango por ÍNDICE de palabra (inicio_palabra y "
        "fin_palabra, ambos incluidos) y usa seguridad='alta' solo cuando "
        "sea indiscutible — SOLO los 'alta' se cortan.\n"
        + ya +
        f"\n\nTRANSCRIPCIÓN CON PAUSAS:\n{listado}")
    try:
        res = llm.complete_json(system, prompt, schema=REVIEW_SCHEMA,
                                max_tokens=8000, purpose="narration_fix")
    except Exception:
        return []
    out = []
    for e in (res.get("errores") or []):
        try:
            i0, i1 = int(e["inicio_palabra"]), int(e["fin_palabra"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (0 <= i0 <= i1 < len(words)):
            continue
        if e.get("seguridad") != "alta":
            continue  # la IA solo corta con evidencia INDISCUTIBLE: un corte
            # 'media' equivocado destruye contenido (caso «monos masivos»,
            # una recapitulación a 70 s del original cortada como repetición)
        out.append({"kind": e.get("tipo", "falso_arranque"),
                    "start": _cut_start(words, i0), "end": _cut_end(words, i1),
                    "text": " ".join(w["text"] for w in words[i0:i1 + 1]),
                    "reason": str(e.get("motivo", ""))[:160] + " (revisión IA)",
                    "confidence": e.get("seguridad", "media")})
    return out
