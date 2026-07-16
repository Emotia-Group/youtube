"""FASE 4 — Escenas / storyboard: divide el guion en escenas de 10-25 s de
narración, cada una con su prompt de B-roll, tipo (imagen o video IA),
animación y texto en pantalla."""
from __future__ import annotations

import json

from ytstudio.phases.script import load_script
from ytstudio.providers import get_llm

# Campos creativos por escena (dirección de arte + banda sonora):
# - overlay_*: rótulo cinematográfico SOLO en momentos clave (tipado: el
#   montaje le da un diseño distinto a cada tipo).
# - music_intensity: arco dramático de la música (0 = mínima, 1 = clímax).
# - pause_after: respiro dramático tras la escena (la música sube en él).
# - sfx: efecto de sonido incidental en el corte de entrada de la escena.
_CREATIVE_PROPS = {
    "overlay_type": {"type": "string",
                     "enum": ["ninguno", "personaje", "lugar", "fecha",
                              "dato", "lista", "conclusion"]},
    "overlay_text": {"type": "string"},
    "overlay_kicker": {"type": "string"},
    "overlay_emphasis": {"type": "string"},
    "music_intensity": {"type": "number"},
    "pause_after": {"type": "number"},
    "sfx": {"type": "string", "enum": ["ninguno", "whoosh", "riser", "boom"]},
    "transition": {"type": "string", "enum": ["corte", "fundido"]},
}

SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "section": {"type": "string"},
                    "narration": {"type": "string"},
                    "broll_prompt": {"type": "string"},
                    "broll_type": {"type": "string", "enum": ["image", "video"]},
                    "animation": {"type": "string",
                                  "enum": ["zoom_in", "zoom_out", "pan_left",
                                           "pan_right", "static"]},
                    **_CREATIVE_PROPS,
                },
                "required": ["id", "section", "narration", "broll_prompt",
                             "broll_type", "animation", *_CREATIVE_PROPS],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenes"],
    "additionalProperties": False,
}

# Reglas de dirección creativa compartidas por los dos flujos con LLM
# (guion nuevo y narración propia). Criterio de documental/serie: los rótulos
# son un acento, no un hábito; la música cuenta el arco; el silencio es un
# recurso.
CREATIVE_RULES = """\
RÓTULOS EN PANTALLA (overlay_*): son acentos cinematográficos, NO subtítulos.
- Úsalos SOLO en momentos clave: como máximo en 1 de cada 3-4 escenas. En el
  resto: overlay_type='ninguno' y textos vacíos.
- Momentos que SÍ merecen rótulo: primera aparición de un personaje relevante;
  un lugar o una fecha que sitúan la acción; una cifra o dato crucial; los
  ítems de una enumeración ("Razón 1…"); la conclusión más importante de una
  sección o del video.
- overlay_text: el dato en sí, 1-5 palabras (ej. "Alejandro Magno", "331 a. C.",
  "40 000 soldados"). EXCEPCIÓN conclusion: puede ser una frase corta completa
  de hasta 8 palabras (ej. "El veredicto es tuyo") — se compone en pantalla
  como una declaración tipográfica grande.
- overlay_kicker: contexto en 1-3 palabras que se muestra pequeño encima
  (ej. kicker "REY DE MACEDONIA" + text "Alejandro Magno"; kicker "BATALLA DE
  GAUGAMELA" + text "331 a. C."; kicker "RAZÓN 2" + text "La logística").
  Puede ir vacío si el texto se explica solo.
- overlay_emphasis: LA palabra de overlay_text que carga el peso dramático
  (se destaca en negrita, ej. "veredicto"). Vacío si no aplica.
- overlay_type: personaje | lugar | fecha | dato | lista | conclusion — elige
  el que corresponda al contenido (cada tipo tiene un diseño distinto).
- IMPORTANTE: usa palabras que aparezcan en la narración de ESA escena (el
  rótulo se sincroniza con el momento en que el narrador las dice).

MÚSICA (music_intensity, 0.0-1.0): dibuja el arco dramático de la historia.
- Gancho inicial 0.65-0.8 · desarrollo/exposición 0.35-0.55 · tensión creciente
  0.6-0.75 · clímax 0.85-1.0 · cierre 0.45-0.6.
- Cambia de forma gradual (±0.15 entre escenas contiguas); reserva los saltos
  bruscos para golpes dramáticos reales.

RESPIROS (pause_after, segundos): silencio de la voz tras la escena, donde la
música respira y sube — recurso cinematográfico, úsalo con intención.
- 0 en la mayoría de escenas. 0.8-1.6 tras una revelación, una pregunta al
  espectador, o el final de una sección. Máximo en 1 de cada 6 escenas.

EFECTOS DE SONIDO (sfx): acento en el corte de ENTRADA de la escena.
- 'whoosh' al cambiar de sección/lugar/tiempo · 'riser' en la escena que
  desemboca en el clímax (crea anticipación) · 'boom' en una revelación
  impactante · 'ninguno' en el resto (máximo 1 de cada 4 escenas).

TRANSICIÓN (transition): cómo ENTRA la escena desde la anterior.
- 'corte': corte seco, sin transición (por defecto). Da ritmo y es lo más
  común en documentales; úsalo en la mayoría de escenas, sobre todo en
  secuencias rápidas, enumeraciones y acción encadenada.
- 'fundido': breve caída a negro compartida con la escena anterior. Resérvalo
  para los CAMBIOS de sección, saltos de tiempo/lugar y los momentos
  dramáticos (tras una revelación o un respiro). Que NO sean todas iguales:
  como mucho 1 de cada 3-4 escenas.
"""


WORDS_PER_SECOND = 2.5  # ritmo medio de narración (≈150 palabras/min)


def scene_seconds(cfg: dict, project=None) -> float:
    """Ritmo visual: cada cuántos segundos cambia la imagen. Si hay un video
    de referencia analizado (yt-dlp), se replica SU ritmo de plano medio;
    si no, el de la configuración."""
    if project is not None:
        for link in (project.get("brief") or {}).get("links", []):
            rhythm = (link or {}).get("rhythm") or {}
            avg = rhythm.get("avg_shot_seconds")
            if avg:
                target = min(15.0, max(3.5, float(avg)))
                project.add_warning(
                    f"ℹ Ritmo visual tomado del video de referencia: "
                    f"~{target:.0f} s por plano.")
                return target
    return float(cfg.get("video", {}).get("scene_seconds", 6))


def _assign_video_scenes(scenes: list[dict], cfg: dict) -> None:
    """Marca deterministamente N escenas como video (broll_type='video'),
    repartidas uniformemente, según providers.videogen.max_scenes. Así el
    usuario obtiene EXACTAMENTE el número de escenas de video que pidió, en
    vez de dejarlo al criterio del modelo. El resto quedan como imagen."""
    vg = cfg.get("providers", {}).get("videogen", {})
    n = vg.get("max_scenes", 0) if vg.get("name", "none") != "none" else 0
    n = min(int(n or 0), len(scenes))
    if n <= 0:
        for s in scenes:
            s["broll_type"] = "image"
        return
    if n >= len(scenes):
        idxs = set(range(len(scenes)))
    else:  # distribuidas uniformemente, incluyendo la primera (el gancho)
        idxs = {round(i * (len(scenes) - 1) / (n - 1)) if n > 1 else 0
                for i in range(n)}
    for i, s in enumerate(scenes):
        s["broll_type"] = "video" if i in idxs else "image"


def _default_intensity(i: int, n: int) -> float:
    """Arco musical por defecto (sin criterio del LLM): gancho fuerte, valle de
    desarrollo, clímax hacia el 85 % y cierre suave. Interpolación lineal."""
    keys = [(0.0, 0.7), (0.2, 0.45), (0.6, 0.55), (0.85, 0.9), (1.0, 0.5)]
    x = i / (n - 1) if n > 1 else 0.5
    for (x0, y0), (x1, y1) in zip(keys, keys[1:]):
        if x <= x1:
            return round(y0 + (y1 - y0) * (x - x0) / (x1 - x0), 2)
    return keys[-1][1]


_OVERLAY_TYPES = {"personaje", "lugar", "fecha", "dato", "lista", "conclusion"}


def _normalize_creative(scenes: list[dict]) -> None:
    """Valida y compacta los campos creativos: los flat overlay_* del esquema
    se convierten en un objeto `overlay` (o None), y los valores numéricos se
    acotan. `on_screen_text` se mantiene sincronizado para la interfaz y los
    proyectos antiguos."""
    n = len(scenes)
    for i, s in enumerate(scenes):
        o_type = s.pop("overlay_type", None) or "ninguno"
        max_len = 70 if o_type == "conclusion" else 48
        o_text = (s.pop("overlay_text", "") or "").strip()[:max_len]
        o_kicker = (s.pop("overlay_kicker", "") or "").strip()[:36]
        o_emph = (s.pop("overlay_emphasis", "") or "").strip()[:24]
        if o_type in _OVERLAY_TYPES and o_text:
            s["overlay"] = {"type": o_type, "text": o_text, "kicker": o_kicker,
                            "emphasis": o_emph}
        else:
            s["overlay"] = None
        s["on_screen_text"] = o_text if s["overlay"] else ""

        mi = s.get("music_intensity")
        if not isinstance(mi, (int, float)):
            mi = _default_intensity(i, n)
        s["music_intensity"] = round(min(1.0, max(0.0, float(mi))), 2)

        pa = s.get("pause_after")
        pa = float(pa) if isinstance(pa, (int, float)) else 0.0
        s["pause_after"] = round(min(2.0, max(0.0, pa)), 2)

        s["sfx"] = s.get("sfx") if s.get("sfx") in ("whoosh", "riser", "boom") \
            else None

        s["transition"] = s.get("transition") if s.get("transition") in \
            ("corte", "fundido") else None


def _split_sentences(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p for p in parts if p]


def _mechanical_scenes(script_md: str, prompt_prefix: str,
                       target_seconds: float = 6.0) -> list[dict]:
    """División del guion sin LLM (modo preview): agrupa frases en escenas del
    ritmo pedido respetando las secciones '## ' y rota las animaciones.
    Preserva el texto EXACTO del guion del usuario."""
    animations = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    max_words = max(6, round(target_seconds * WORDS_PER_SECOND))
    sections: list[tuple[str, list[str]]] = []
    current = ("Narración", [])
    for line in script_md.splitlines():
        if line.startswith("## "):
            if current[1]:
                sections.append(current)
            current = (line[3:].strip() or "Sección", [])
        elif line.strip():
            current[1].append(line.strip())
    if current[1]:
        sections.append(current)

    scenes: list[dict] = []
    for section, lines in sections:
        chunk: list[str] = []
        words = 0
        def flush():
            nonlocal chunk, words
            if chunk:
                scenes.append({
                    "id": len(scenes) + 1,
                    "section": section,
                    "narration": " ".join(chunk),
                    "broll_prompt": f"{prompt_prefix}, {section}".strip(", "),
                    "broll_type": "image",
                    "animation": animations[len(scenes) % len(animations)],
                    "on_screen_text": "",
                })
                chunk, words = [], 0
        for sentence in _split_sentences(" ".join(lines)):
            chunk.append(sentence)
            words += len(sentence.split())
            if words >= max_words:
                flush()
        flush()
    return scenes


def _atomize(segments: list[dict], target: float) -> list[dict]:
    """Convierte los segmentos del STT en 'átomos' de como mucho ~target
    segundos: los segmentos más largos que el ritmo se parten por tiempo,
    repartiendo su texto por palabras (para el subtítulo). Así la imagen puede
    cambiar dentro de una frase larga."""
    atoms: list[dict] = []
    for seg in segments:
        dur = seg["end"] - seg["start"]
        n = max(1, round(dur / target)) if dur > target * 1.4 else 1
        if n == 1:
            atoms.append(dict(seg))
            continue
        words = seg["text"].split()
        per = max(1, len(words) // n)
        for i in range(n):
            a = seg["start"] + dur * i / n
            b = seg["start"] + dur * (i + 1) / n
            chunk = words[i * per: (i + 1) * per] if i < n - 1 else words[i * per:]
            atoms.append({"start": a, "end": b, "text": " ".join(chunk)})
    return atoms


def _group_narration(segments: list[dict], target_seconds: float = 6.0) -> list[dict]:
    """Divide la narración transcrita (con tiempos del audio real) en escenas de
    ~target_seconds. Cada escena lleva su tramo exacto de audio
    [audio_start, audio_end]; la imagen cambia a ese ritmo."""
    atoms = _atomize(segments, target_seconds)
    scenes: list[dict] = []
    cur: list[dict] = []
    for a in atoms:
        cur.append(a)
        if cur[-1]["end"] - cur[0]["start"] >= target_seconds * 0.85:
            scenes.append(_scene_from_group(cur, len(scenes) + 1))
            cur = []
    if cur:
        # evita una última escena minúscula: fúndela con la anterior
        if scenes and cur[-1]["end"] - cur[0]["start"] < target_seconds * 0.4:
            prev = scenes[-1]
            prev["narration"] = (prev["narration"] + " "
                                 + " ".join(s["text"] for s in cur)).strip()
            prev["audio_end"] = round(cur[-1]["end"], 3)
        else:
            scenes.append(_scene_from_group(cur, len(scenes) + 1))
    return scenes


def _scene_from_group(group: list[dict], idx: int) -> dict:
    return {
        "id": idx,
        "section": "Narración",
        "narration": " ".join(s["text"] for s in group).strip(),
        "audio_start": round(group[0]["start"], 3),
        "audio_end": round(group[-1]["end"], 3),
        "broll_type": "image",
        "animation": ["zoom_in", "pan_right", "zoom_out", "pan_left"][(idx - 1) % 4],
        "on_screen_text": "",
    }


def _broll_for_fixed(llm, concept, scenes, lang, videogen_scenes) -> None:
    """Rellena broll_prompt / on_screen_text / section de escenas ya fijadas por
    el audio, para que el B-roll sea coherente con lo que se dice en cada tramo.
    Modifica `scenes` en el sitio."""
    prefix = concept["visual_style"]["prompt_prefix"]
    if getattr(llm, "is_mock", False):
        for s in scenes:
            s["broll_prompt"] = f"{prefix}, {s['narration'][:60]}".strip(", ")
        return

    schema = {
        "type": "object",
        "properties": {"scenes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "broll_prompt": {"type": "string"},
                "broll_type": {"type": "string", "enum": ["image", "video"]},
                "animation": {"type": "string", "enum": ["zoom_in", "zoom_out",
                              "pan_left", "pan_right", "static"]},
                "section": {"type": "string"},
                **_CREATIVE_PROPS,
            },
            "required": ["broll_prompt", "broll_type", "animation", "section",
                         *_CREATIVE_PROPS],
            "additionalProperties": False,
        }}},
        "required": ["scenes"], "additionalProperties": False,
    }
    narr = "\n".join(f"[{s['id']}] {s['narration']}" for s in scenes)
    system = (
        f"Eres a la vez director de fotografía, editor senior y director "
        f"creativo de documentales y videos largos de YouTube en {lang}. Las "
        "escenas y su narración YA están fijadas por el audio del narrador; tú "
        "diseñas el apoyo visual, los rótulos y la dirección de la banda "
        "sonora de cada una con criterio cinematográfico.")
    prompt = (
        f"Para cada una de estas {len(scenes)} escenas (en el mismo orden y "
        "cantidad), diseña el apoyo audiovisual de lo que se dice:\n"
        "- broll_prompt: prompt EN INGLÉS, detallado, que ilustre el contenido "
        f"de esa narración concreta, comenzando con el prefijo de estilo "
        f"\"{prefix}\". Sin texto ni letras en la imagen, sin personas reales.\n"
        + (f"- broll_type: 'video' solo en las {videogen_scenes} de mayor "
           "impacto, el resto 'image'.\n" if videogen_scenes else
           "- broll_type: siempre 'image'.\n")
        + "- animation: alterna zoom_in/zoom_out/pan_left/pan_right.\n"
        "- section: título temático corto del tramo (para los capítulos).\n\n"
        + CREATIVE_RULES
        + f"\nNARRACIÓN POR ESCENA:\n{narr}")
    result = llm.complete_json(system, prompt, schema=schema,
                               max_tokens=32000, purpose="broll_fixed")
    got = result["scenes"]
    for i, s in enumerate(scenes):
        b = got[i] if i < len(got) else {}
        s["broll_prompt"] = b.get("broll_prompt") or f"{prefix}, {s['narration'][:50]}"
        s["broll_type"] = b.get("broll_type", "image")
        s["animation"] = b.get("animation", s["animation"])
        if b.get("section"):
            s["section"] = b["section"]
        for key in _CREATIVE_PROPS:
            if key in b:
                s[key] = b[key]


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    concept = project.get("concept")
    script_md = load_script(project)
    lang = cfg.get("language", "es")
    videogen_scenes = cfg["providers"]["videogen"].get("max_scenes", 0)

    target = scene_seconds(cfg, project)

    # MODO NARRACIÓN PROPIA: escenas alineadas al audio real del usuario.
    narration = project.get("narration")
    if narration and narration.get("segments"):
        scenes = _group_narration(narration["segments"], target)
        _broll_for_fixed(llm, concept, scenes, lang, videogen_scenes)
        _assign_video_scenes(scenes, cfg)  # nº de escenas de video determinista
        _normalize_creative(scenes)
        _write_outputs(project, scenes)
        return

    # Sin LLM real (modo preview): dividir el guion real mecánicamente en vez
    # de sustituirlo por escenas de ejemplo.
    if getattr(llm, "is_mock", False):
        scenes = _mechanical_scenes(
            script_md, concept["visual_style"]["prompt_prefix"], target)
        if scenes:
            _assign_video_scenes(scenes, cfg)
            _normalize_creative(scenes)
            _write_outputs(project, scenes)
            return

    system = (
        f"Eres a la vez editor senior, director de fotografía y director "
        f"creativo de documentales, series y videos largos de YouTube en {lang}. "
        "Conviertes guiones en storyboards listos para producción con IA, con "
        "criterio cinematográfico: los rótulos son acentos puntuales, la música "
        "dibuja el arco dramático y el silencio es un recurso narrativo."
    )
    words = max(6, round(target * WORDS_PER_SECOND))
    lo, hi = max(4, words - 4), words + 6
    broll_type_rule = (
        f"- 'broll_type': usa 'video' solo en las {videogen_scenes} escenas de "
        "mayor impacto (gancho/clímax); el resto 'image'.\n" if videogen_scenes
        else "- 'broll_type': siempre 'image'.\n")
    prompt = (
        "Divide este guion en escenas para el montaje. Reglas:\n"
        f"- Cada escena cubre ~{target:.0f} segundos de narración "
        f"(aprox. {lo}-{hi} palabras) — la imagen cambia a ese ritmo. NO cambies "
        "ni recortes el texto del guion: el campo 'narration' debe contener el "
        "texto EXACTO, y la concatenación de todas las escenas debe reconstruir "
        "el guion completo.\n"
        "- 'section': encabezado del guion al que pertenece.\n"
        "- 'broll_prompt': prompt EN INGLÉS para generar la imagen/video IA de "
        f"fondo, coherente con lo que se dice en esa escena. Detallado y SIEMPRE "
        f"comenzando con el prefijo de estilo \"{concept['visual_style']['prompt_prefix']}\". "
        "Sin texto ni letras dentro de la imagen, sin personas famosas reales.\n"
        + broll_type_rule +
        "- 'animation': varía entre zoom_in, zoom_out, pan_left, pan_right "
        "(evita repetir la misma dos veces seguidas).\n\n"
        + CREATIVE_RULES
        + f"\nGUION:\n<<<\n{script_md}\n>>>"
    )

    result = llm.complete_json(system, prompt, schema=SCENES_SCHEMA,
                               max_tokens=64000, purpose="scenes")
    scenes = result["scenes"]
    for i, s in enumerate(scenes, start=1):
        s["id"] = i  # ids consecutivos garantizados
    _assign_video_scenes(scenes, cfg)  # nº de escenas de video determinista
    _normalize_creative(scenes)
    _write_outputs(project, scenes)


def _write_outputs(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Storyboard", ""]
    for s in scenes:
        md += [f"## Escena {s['id']} — {s['section']} ({s['animation']}, {s['broll_type']})",
               f"**Narración:** {s['narration']}",
               f"**B-roll:** {s['broll_prompt']}"]
        o = s.get("overlay")
        if o:
            kick = f" ({o['kicker']})" if o.get("kicker") else ""
            md.append(f"**Rótulo [{o['type']}]:** {o['text']}{kick}")
        extras = [f"música {s['music_intensity']:.2f}" if "music_intensity" in s else ""]
        if s.get("transition"):
            extras.append(f"entra: {s['transition']}")
        if s.get("pause_after"):
            extras.append(f"respiro {s['pause_after']:.1f}s")
        if s.get("sfx"):
            extras.append(f"sfx {s['sfx']}")
        md.append(f"*({', '.join(x for x in extras if x)})*")
        md.append("")
    project.path("scenes", "storyboard.md").write_text("\n".join(md), encoding="utf-8")
    project.set("scene_count", len(scenes))


def load_scenes(project) -> list[dict]:
    from ytstudio.project import read_json_tolerant
    return read_json_tolerant(project.path("scenes", "scenes.json"))["scenes"]


def save_scenes(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
