"""FASE 10 — Metadatos: título final, descripción con capítulos (timestamps
reales calculados de las escenas), tags y miniatura."""
from __future__ import annotations

import json

from ytstudio.phases.scenes import load_scenes
from ytstudio.providers import get_llm

METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string"},
    },
    "required": ["title", "description", "tags", "thumbnail_text"],
    "additionalProperties": False,
}


def _chapters(scenes: list[dict]) -> list[tuple[str, float]]:
    """Un capítulo por cambio de sección, con su timestamp de inicio."""
    chapters, t = [], 0.0
    last = None
    for s in scenes:
        if s["section"] != last:
            chapters.append((s["section"], t))
            last = s["section"]
        t += s["duration"]
    return chapters


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _make_thumbnail(project, cfg, text: str) -> str:
    """Miniatura 1280x720: imagen de la primera escena + texto grande."""
    from PIL import Image, ImageDraw, ImageFont

    scenes = load_scenes(project)
    base_path = project.path("broll", scenes[0]["broll_image"])
    img = Image.open(base_path).convert("RGB")
    img = img.resize((1280, int(1280 * img.height / img.width)))
    img = img.crop((0, max(0, (img.height - 720) // 2),
                    1280, max(0, (img.height - 720) // 2) + 720))
    if img.height < 720:
        img = img.resize((1280, 720))

    draw = ImageDraw.Draw(img, "RGBA")
    # Banda inferior oscura para legibilidad
    draw.rectangle([(0, 480), (1280, 720)], fill=(0, 0, 0, 150))
    from ytstudio.utils.media import find_font
    font_path = find_font(bold=True)
    font = (ImageFont.truetype(font_path, 84) if font_path
            else ImageFont.load_default(size=84))

    # Ajuste de texto a 2 líneas máximo
    words, lines, cur = text.upper().split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if draw.textlength(cand, font=font) > 1160 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    y = 700 - 96 * len(lines[:2])
    for line in lines[:2]:
        draw.text((62, y + 2), line, font=font, fill=(0, 0, 0, 220))
        draw.text((60, y), line, font=font, fill=(255, 214, 90, 255))
        y += 96

    out = project.path("final", "miniatura.jpg")
    img.save(out, quality=92)
    return str(out)


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    concept = project.get("concept")
    scenes = load_scenes(project)
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)  # nombre completo del idioma para el LLM
    chapters = _chapters(scenes)
    chapters_txt = "\n".join(f"{_ts(t)} {name}" for name, t in chapters)

    system = (f"Eres especialista en SEO de YouTube. Escribes metadatos en {lang} "
              "que maximizan CTR y descubrimiento sin clickbait engañoso.")
    prompt = (
        f"Concepto del video:\n{json.dumps(concept, ensure_ascii=False)[:4000]}\n\n"
        f"Capítulos reales del video (INCLÚYELOS tal cual en la descripción):\n"
        f"{chapters_txt}\n\n"
        "Devuelve:\n"
        "- title: el mejor título final (máx. 90 caracteres)\n"
        "- description: descripción completa (2-3 párrafos + sección 'Capítulos:' "
        "con los timestamps de arriba + 3-5 hashtags al final)\n"
        "- tags: 15-25 tags\n"
        "- thumbnail_text: texto de la miniatura (3-6 palabras, alto impacto)"
    )
    meta = llm.complete_json(system, prompt, schema=METADATA_SCHEMA,
                             purpose="metadata")
    meta["chapters"] = [{"time": _ts(t), "title": name} for name, t in chapters]
    meta["thumbnail"] = _make_thumbnail(project, cfg, meta["thumbnail_text"])

    project.path("final", "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    project.set("metadata", {k: meta[k] for k in ("title", "tags", "thumbnail")})
