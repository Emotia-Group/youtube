"""FASE 8 — Subtítulos: genera .srt (para subir a YouTube o pista soft) y
.ass estilizado (para quemar en el video).

En narración propia, los tiempos de cada bloque se anclan a los timestamps
REALES de tus palabras (Whisper) — el subtítulo cambia cuando tú lo dices,
no por proporción de caracteres dentro de la escena (eso ligaba el cambio
de texto al corte visual en vez de a tu voz). En TTS (sin timestamps por
palabra) se reparte proporcionalmente, como antes."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes
from ytstudio.utils.align import flatten_words, video_time_fn
from ytstudio.utils.text import strip_bullets


def _chunks(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Divide la narración en bloques de subtítulo de hasta max_lines líneas."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = w
        else:
            current = candidate
    if current:
        lines.append(current)
    return ["\n".join(lines[i:i + max_lines])
            for i in range(0, len(lines), max_lines)]


def _chunks_words(words: list[dict], max_chars: int, max_lines: int):
    """Divide las palabras (con sus tiempos reales) en subtítulos CORTOS,
    estilo cinematográfico: cada bloque es una frase o cláusula breve, nunca
    dos oraciones juntas ni un párrafo largo.

    Dos reglas de corte: (1) al superar max_chars por línea se pasa de línea,
    y si ya hay max_lines se cierra el bloque; (2) al cerrar una oración
    (. ! ? …) SIEMPRE se cierra el bloque; una coma/;/: cierra el bloque solo
    si la línea ya tiene cuerpo (para no dejar retazos de una o dos palabras).
    Así el texto en pantalla cambia al ritmo de lo que se dice."""
    blocks: list[tuple[str, list[dict]]] = []
    cur_lines: list[list[dict]] = [[]]     # palabras por línea del bloque actual
    cur_texts: list[str] = [""]

    def flush() -> None:
        words_flat = [w for ln in cur_lines for w in ln]
        if words_flat:
            text = "\n".join(" ".join(w["text"] for w in ln)
                             for ln in cur_lines if ln)
            blocks.append((text, words_flat))
        cur_lines.clear(); cur_lines.append([])
        cur_texts.clear(); cur_texts.append("")

    for w in words:
        cand = f"{cur_texts[-1]} {w['text']}".strip()
        if len(cand) > max_chars and cur_lines[-1]:
            if len(cur_lines) >= max_lines:      # no cabe otra línea → nuevo bloque
                flush()
            else:
                cur_lines.append([]); cur_texts.append("")
        cur_lines[-1].append(w)
        cur_texts[-1] = f"{cur_texts[-1]} {w['text']}".strip()
        t = w["text"]
        line_len = len(cur_texts[-1])
        strong = t.rstrip("»\"')”").endswith((".", "!", "?", "…"))
        soft = t.rstrip("»\"')”").endswith((",", ";", ":"))
        if strong or (soft and line_len >= max(12, max_chars // 2)):
            flush()
    flush()
    return blocks


def _fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _fmt_ass(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_cues(scenes: list[dict], max_chars: int, max_lines: int,
               narration: dict | None = None,
               voice_map: dict | None = None) -> list[dict]:
    all_words = flatten_words((narration or {}).get("segments") or [])
    # Con narración propia, el instante de cada palabra en el video sale del
    # mapa GLOBAL de tiempo (intro + inserciones) — la misma fuente de verdad
    # que usan los rótulos y el WAV de la voz. Sin él (TTS o proyecto antiguo)
    # se reparte proporcionalmente dentro de cada escena.
    V = None
    if voice_map:
        V = video_time_fn(voice_map["intro"],
                          [(p, d) for p, d in voice_map["insertions"]])
    cues = []
    if all_words and V is not None:
        # SUBTÍTULOS GLOBALES: se trocean TODAS las palabras juntas y se
        # cronometran con el mapa de tiempo. Antes se troceaban POR ESCENA, y
        # una frase que cruzaba la frontera de escena quedaba partida:
        # dejaba palabras huérfanas («El» sola al empezar la escena, «Cuando»
        # sola al final). Ahora la frase fluye a través de las escenas.
        for text, bwords in _chunks_words(all_words, max_chars, max_lines):
            start = V(float(bwords[0]["start"]))
            end = max(start + 0.4, V(float(bwords[-1]["end"])))
            cues.append({"start": start, "end": end, "text": text})
    else:
        # Respaldo (TTS o proyectos sin timestamps por palabra): reparto
        # proporcional por caracteres, escena a escena.
        t = 0.0
        for scene in scenes:
            blocks = _chunks(scene["narration"], max_chars, max_lines)
            vo = scene["vo_duration"]
            total_chars = sum(len(b) for b in blocks) or 1
            offset = float(scene.get("vo_offset") or 0.0)
            for block in blocks:
                dur = vo * len(block) / total_chars
                cues.append({"start": t + offset, "end": t + offset + dur,
                            "text": block})
                offset += dur
            t += scene["duration"]
    # Ninguna viñeta llega a pantalla: si la transcripción de un proyecto
    # anterior arrastra el «• » con que Whisper copiaba el formato del guion,
    # el subtítulo sale limpio igual (los tiempos no se tocan).
    for c in cues:
        c["text"] = "\n".join(strip_bullets(ln) for ln in c["text"].split("\n"))
    cues = [c for c in cues if c["text"].strip()]
    cues.sort(key=lambda c: c["start"])
    # SIN SOLAPES: cada subtítulo termina antes de que empiece el siguiente.
    # Si dos cues se solapaban, ambos se dibujaban a la vez y aparecía una
    # TERCERA línea fugaz (la primera palabra del siguiente subtítulo colada
    # bajo el actual). Recortar el fin al inicio del siguiente lo evita.
    for i in range(len(cues) - 1):
        cues[i]["end"] = min(cues[i]["end"], cues[i + 1]["start"] - 0.03)
    # DEFENSA: ningún subtítulo puede pasar del final del video (la suma de
    # duraciones de escena). Un cue colgando más allá estira la pista de
    # subtítulos del mp4 y desincroniza la duración del contenedor.
    limit = sum(float(s["duration"]) for s in scenes)
    if limit > 0:
        cues = [c for c in cues if c["start"] < limit - 0.05]
        for c in cues:
            c["end"] = min(c["end"], limit)
    # Descarta cues degenerados (fin <= inicio) que el de-solape pudiera crear.
    cues = [c for c in cues if c["end"] > c["start"] + 0.05]
    return cues


def run(project, cfg) -> None:
    scenes = load_scenes(project)
    narration = project.get("narration")
    voice_map = project.get("voice_map")
    sub_cfg = cfg.get("subtitles", {})
    max_chars = sub_cfg.get("max_chars_per_line", 42)
    max_lines = sub_cfg.get("max_lines", 2)
    cues = build_cues(scenes, max_chars, max_lines, narration, voice_map)

    # LAZO CERRADO de sincronía: se mide el desfase de los cues contra la
    # pista de voz REAL (narration_timeline.wav) y, si es significativo, se
    # corrigen TODOS por la mediana medida — y se re-mide para confirmar.
    # Los rótulos usan la misma corrección (project.sync_shift) al montar.
    project.set("sync_shift", 0.0)
    tl = project.get("voice_timeline")
    tl_path = project.path("voiceover", tl) if tl else None
    if cues and tl_path and tl_path.exists():
        from ytstudio import eventlog
        from ytstudio.utils.align import measure_sync_offset
        try:
            med, n_pts = measure_sync_offset(tl_path,
                                             [c["start"] for c in cues])
            # Umbral BAJO (50 ms): con la mediana de ~15 arranques la medición
            # es estable, así que corregir hasta ~0 no arriesga sobrecorregir.
            # Antes el tope era 120 ms y dejaba pasar desfases de ~111 ms que
            # sí se notaban (los subtítulos «un pelo tarde» que reportaste).
            if abs(med) > 0.05 and n_pts >= 4:
                limit = sum(float(s["duration"]) for s in scenes)
                for c in cues:
                    c["start"] = min(max(0.0, c["start"] - med), limit - 0.3)
                    c["end"] = min(max(c["start"] + 0.25, c["end"] - med), limit)
                project.set("sync_shift", round(-med, 3))
                med2, _ = measure_sync_offset(tl_path,
                                             [c["start"] for c in cues])
                eventlog.log("info",
                             f"🔁 Lazo de sincronía: subtítulos corregidos "
                             f"{-med * 1000:+.0f} ms (desfase medido "
                             f"{med * 1000:+.0f} ms en {n_pts} arranques; tras "
                             f"corregir: {med2 * 1000:+.0f} ms).",
                             project=getattr(project, "slug", None),
                             phase="subtitles")
        except Exception:
            pass

    # SRT
    srt = []
    for i, c in enumerate(cues, 1):
        srt += [str(i), f"{_fmt_srt(c['start'])} --> {_fmt_srt(c['end'])}",
                c["text"], ""]
    project.path("subtitles", "subtitulos.srt").write_text("\n".join(srt), encoding="utf-8")

    # ASS estilizado (para quemado)
    font = sub_cfg.get("font", "Arial")
    size = sub_cfg.get("font_size", 54)
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = [
        f"Dialogue: 0,{_fmt_ass(c['start'])},{_fmt_ass(c['end'])},Default,,0,0,0,,"
        + c["text"].replace("\n", "\\N")
        for c in cues
    ]
    project.path("subtitles", "subtitulos.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    project.set("subtitle_cues", len(cues))
