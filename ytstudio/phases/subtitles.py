"""FASE 8 — Subtítulos: genera .srt (para subir a YouTube o pista soft) y
.ass estilizado (para quemar en el video). Los tiempos se reparten dentro de
cada escena proporcionalmente al número de caracteres de cada bloque."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes


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


def _fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _fmt_ass(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_cues(scenes: list[dict], max_chars: int, max_lines: int) -> list[dict]:
    cues = []
    t = 0.0
    for scene in scenes:
        blocks = _chunks(scene["narration"], max_chars, max_lines)
        vo = scene["vo_duration"]
        total_chars = sum(len(b) for b in blocks) or 1
        offset = 0.0
        for block in blocks:
            dur = vo * len(block) / total_chars
            cues.append({"start": t + offset, "end": t + offset + dur, "text": block})
            offset += dur
        t += scene["duration"]
    return cues


def run(project, cfg) -> None:
    scenes = load_scenes(project)
    sub_cfg = cfg.get("subtitles", {})
    max_chars = sub_cfg.get("max_chars_per_line", 42)
    max_lines = sub_cfg.get("max_lines", 2)
    cues = build_cues(scenes, max_chars, max_lines)

    # SRT
    srt = []
    for i, c in enumerate(cues, 1):
        srt += [str(i), f"{_fmt_srt(c['start'])} --> {_fmt_srt(c['end'])}",
                c["text"], ""]
    project.path("subtitles", "subtitulos.srt").write_text("\n".join(srt))

    # ASS estilizado (para quemado)
    font = sub_cfg.get("font", "DejaVu Sans")
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
    project.path("subtitles", "subtitulos.ass").write_text(header + "\n".join(events) + "\n")
    project.set("subtitle_cues", len(cues))
