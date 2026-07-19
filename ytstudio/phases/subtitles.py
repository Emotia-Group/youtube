"""FASE 8 — Subtítulos: genera .srt (para subir a YouTube o pista soft) y
.ass estilizado (para quemar en el video).

En narración propia, los tiempos de cada bloque se anclan a los timestamps
REALES de tus palabras (Whisper) — el subtítulo cambia cuando tú lo dices,
no por proporción de caracteres dentro de la escena (eso ligaba el cambio
de texto al corte visual en vez de a tu voz). En TTS (sin timestamps por
palabra) se reparte proporcionalmente, como antes."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes
from ytstudio.utils.align import (assign_words, flatten_words, local_time,
                                  video_time_fn)


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
    """Como _chunks, pero conservando qué palabras (con sus tiempos reales)
    componen cada línea/bloque — para anclar el subtítulo a la voz real."""
    lines: list[list[dict]] = []
    current: list[dict] = []
    current_text = ""
    for w in words:
        candidate = f"{current_text} {w['text']}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current, current_text = [w], w["text"]
        else:
            current.append(w)
            current_text = candidate
    if current:
        lines.append(current)
    blocks = []
    for i in range(0, len(lines), max_lines):
        block_lines = lines[i:i + max_lines]
        text = "\n".join(" ".join(w["text"] for w in ln) for ln in block_lines)
        blocks.append((text, [w for ln in block_lines for w in ln]))
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
    word_map = assign_words(scenes, all_words) if all_words else {}
    # Con narración propia, el instante de cada palabra en el video sale del
    # mapa GLOBAL de tiempo (intro + inserciones) — la misma fuente de verdad
    # que usan los rótulos y el WAV de la voz. Sin él (TTS o proyecto antiguo)
    # se reparte proporcionalmente dentro de cada escena.
    V = None
    if voice_map:
        V = video_time_fn(voice_map["intro"],
                          [(p, d) for p, d in voice_map["insertions"]])
    cues = []
    t = 0.0
    for scene in scenes:
        sw = word_map.get(scene.get("id"), [])
        if sw and V is not None:
            # Timing REAL absoluto: cada bloque empieza/termina cuando tú dices
            # esas palabras (video_time), no por proporción ni por escena.
            for text, bwords in _chunks_words(sw, max_chars, max_lines):
                start = V(float(bwords[0]["start"]))
                end = max(start + 0.25, V(float(bwords[-1]["end"])))
                cues.append({"start": start, "end": end, "text": text})
        elif sw:
            # Palabras reales pero sin mapa (raro): tiempo local por escena.
            for text, bwords in _chunks_words(sw, max_chars, max_lines):
                start = local_time(scene, bwords[0]["start"])
                end = max(start + 0.25, local_time(scene, bwords[-1]["end"]))
                cues.append({"start": t + start, "end": t + end, "text": text})
        else:
            # Respaldo (TTS, o proyectos de versiones anteriores sin
            # timestamps por palabra): reparto proporcional por caracteres.
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
    # Los cues por video_time son absolutos y ya vienen ordenados por palabra;
    # garantizar orden por si el respaldo se mezcló con el modo real.
    cues.sort(key=lambda c: c["start"])
    return cues


def run(project, cfg) -> None:
    scenes = load_scenes(project)
    narration = project.get("narration")
    voice_map = project.get("voice_map")
    sub_cfg = cfg.get("subtitles", {})
    max_chars = sub_cfg.get("max_chars_per_line", 42)
    max_lines = sub_cfg.get("max_lines", 2)
    cues = build_cues(scenes, max_chars, max_lines, narration, voice_map)

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
