"""Motor de miniaturas PROFESIONALES (PIL puro — sin IA extra ni costo).

Tres diseños distintos por video, cada uno aplicando las reglas de las
miniaturas ganadoras de YouTube:
  · Texto de 2-4 palabras GIGANTE, legible en tamaño pequeño (≈70% del
    tráfico llega desde móvil, donde la miniatura mide ~160px).
  · Alto contraste texto/fondo: gradientes, viñetas y trazos medidos —
    nunca texto "flotando" sobre la imagen.
  · UNA palabra de acento en el color de marca del canal (overlay_accent):
    la misma identidad visual que los rótulos del video.
  · Punto focal despejado: el texto vive en su zona (banda, panel o
    centro con viñeta), no tapa el sujeto.
  · Imagen realzada (contraste/saturación/nitidez): compite en un feed
    lleno de miniaturas saturadas.
  · Kicker pequeño de contexto (serie/categoría) para marca de canal.

Diseños:
  1. "cine"    — letterbox cinematográfico, gradiente inferior, texto a la
                 izquierda con subrayado de acento. Elegante, editorial.
  2. "impacto" — viñeta radial, texto centrado enorme con trazo negro
                 grueso y kicker en píldora. Máxima agresividad de CTR.
  3. "panel"   — panel lateral oscuro con filo de acento y texto apilado;
                 la imagen respira al otro lado. Muy legible en pequeño.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from ytstudio.utils.media import find_font


def _hex_rgb(hexcolor: str) -> tuple[int, int, int]:
    h = (hexcolor or "E8C46B").lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (232, 196, 107)


def _cover(img: Image.Image, W: int, H: int, focus_x: float = 0.5) -> Image.Image:
    """Recorte tipo cover llenando W×H, con foco horizontal desplazable."""
    r = max(W / img.width, H / img.height)
    img = img.resize((max(W, round(img.width * r)), max(H, round(img.height * r))),
                     Image.LANCZOS)
    left = round((img.width - W) * min(max(focus_x, 0.0), 1.0))
    top = (img.height - H) // 2
    return img.crop((left, top, left + W, top + H))


def _enhance(img: Image.Image) -> Image.Image:
    """Realce editorial: contraste, color y nitidez sutiles (sin quemar)."""
    img = ImageEnhance.Contrast(img).enhance(1.10)
    img = ImageEnhance.Color(img).enhance(1.22)
    img = ImageEnhance.Sharpness(img).enhance(1.25)
    return ImageEnhance.Brightness(img).enhance(0.98)


def _vgrad(W: int, H: int, y0: float, y1: float, a0: int, a1: int) -> Image.Image:
    """Capa negra con gradiente vertical de alpha a0→a1 entre y0 e y1."""
    col = Image.new("L", (1, H), 0)
    px = col.load()
    for y in range(H):
        if y < y0:
            a = a0
        elif y > y1:
            a = a1
        else:
            t = (y - y0) / max(1, (y1 - y0))
            a = round(a0 + (a1 - a0) * t)
        px[0, y] = a
    mask = col.resize((W, H))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    layer.putalpha(mask)
    return layer


def _vignette(W: int, H: int, edge_alpha: int = 175) -> Image.Image:
    """Viñeta radial (centro limpio, bordes oscuros) para foco central."""
    small_w, small_h = 320, max(2, round(320 * H / W))
    m = Image.new("L", (small_w, small_h), 0)
    px = m.load()
    cx, cy = small_w / 2, small_h / 2
    max_d = (cx ** 2 + cy ** 2) ** 0.5
    for y in range(small_h):
        for x in range(small_w):
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / max_d
            px[x, y] = round(edge_alpha * max(0.0, d - 0.42) / 0.58)
    mask = m.resize((W, H), Image.LANCZOS)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    layer.putalpha(mask)
    return layer


def _font(size: int) -> ImageFont.FreeTypeFont:
    path = find_font(bold=True)
    return (ImageFont.truetype(path, size) if path
            else ImageFont.load_default(size=size))


def _split_balanced(words: list[str], draw: ImageDraw.ImageDraw,
                    font: ImageFont.FreeTypeFont) -> list[str]:
    """1 o 2 líneas balanceadas (la miniatura ganadora nunca pasa de 2)."""
    if len(words) <= 2:
        return [" ".join(words)]
    best, best_diff = None, 1e12
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(draw.textlength(l1, font=font) - draw.textlength(l2, font=font))
        if diff < best_diff:
            best, best_diff = [l1, l2], diff
    return best or [" ".join(words)]


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int,
         floor: int = 44) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Tamaño máximo (búsqueda descendente) con el que el texto cabe en
    max_w usando 1-2 líneas balanceadas."""
    words = text.upper().split()
    size = start
    while size > floor:
        font = _font(size)
        lines = _split_balanced(words, draw, font)
        if all(draw.textlength(ln, font=font) <= max_w for ln in lines):
            return font, lines
        size -= 6
    font = _font(floor)
    return font, _split_balanced(words, draw, font)


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").upper())


def _draw_line_accent(draw, x, y, line: str, font, accent_word: str,
                      accent: tuple, base=(255, 255, 255),
                      stroke: int = 0, shadow: bool = True) -> float:
    """Dibuja una línea palabra a palabra, coloreando la palabra de acento.
    Devuelve el ancho total dibujado."""
    acc = _norm(accent_word)
    cx = x
    space = draw.textlength(" ", font=font)
    for w in line.split():
        color = accent if acc and _norm(w) == acc else base
        if shadow:
            draw.text((cx + 3, y + 4), w, font=font, fill=(0, 0, 0, 210))
        draw.text((cx, y), w, font=font, fill=color,
                  stroke_width=stroke, stroke_fill=(8, 8, 10))
        cx += draw.textlength(w, font=font) + space
    return cx - space - x


def _draw_kicker(draw, x, y, text: str, size: int, color: tuple,
                 tracking: int = 5) -> float:
    """Kicker en mayúsculas con espaciado de letras (look editorial)."""
    font = _font(size)
    cx = x
    for ch in text.upper():
        draw.text((cx + 2, y + 2), ch, font=font, fill=(0, 0, 0, 200))
        draw.text((cx, y), ch, font=font, fill=color)
        cx += draw.textlength(ch, font=font) + tracking
    return cx - tracking - x


# ------------------------------------------------------------------ diseños

def _design_cine(bg, W, H, kicker, text, accent_word, accent) -> Image.Image:
    img = bg.convert("RGBA")
    img.alpha_composite(_vgrad(W, H, H * 0.45, H * 0.96, 0, 235))
    draw = ImageDraw.Draw(img, "RGBA")
    if W > H:  # letterbox solo en horizontal
        bar = round(H * 0.045)
        draw.rectangle([(0, 0), (W, bar)], fill=(6, 7, 9, 255))
        draw.rectangle([(0, H - bar), (W, H)], fill=(6, 7, 9, 255))
    margin = round(W * 0.055)
    font, lines = _fit(draw, text, round(W * 0.82), round(H * 0.20))
    line_h = round(font.size * 1.14)
    block_h = line_h * len(lines)
    y = H - round(H * 0.075) - block_h
    if kicker:
        ksize = max(24, round(font.size * 0.30))
        _draw_kicker(draw, margin + 2, y - ksize - round(H * 0.022),
                     kicker, ksize, accent)
    widths = []
    for ln in lines:
        widths.append(_draw_line_accent(draw, margin, y, ln, font,
                                        accent_word, accent, stroke=2))
        y += line_h
    # subrayado de acento bajo la última línea
    uw = min(max(widths), round(W * 0.5))
    draw.rectangle([(margin, y + 6), (margin + uw, y + 6 + max(5, H // 130))],
                   fill=accent)
    return img


def _design_impacto(bg, W, H, kicker, text, accent_word, accent) -> Image.Image:
    img = bg.convert("RGBA")
    img.alpha_composite(_vignette(W, H, 185))
    img.alpha_composite(_vgrad(W, H, H * 0.55, H, 0, 120))
    draw = ImageDraw.Draw(img, "RGBA")
    font, lines = _fit(draw, text, round(W * 0.86), round(H * 0.24))
    line_h = round(font.size * 1.08)
    block_h = line_h * len(lines)
    y = round(H * 0.56) - block_h // 2 if W > H else round(H * 0.64) - block_h // 2
    if kicker:
        ksize = max(26, round(font.size * 0.26))
        kfont = _font(ksize)
        kw = draw.textlength(kicker.upper(), font=kfont) + 8 * len(kicker)
        pad = round(ksize * 0.55)
        kx = (W - kw) / 2
        ky = y - ksize - pad * 2 - round(H * 0.03)
        draw.rounded_rectangle([(kx - pad, ky - pad // 2),
                                (kx + kw + pad, ky + ksize + pad)],
                               radius=8, fill=(*accent, 235))
        _draw_kicker(draw, kx, ky, kicker, ksize, (12, 12, 14), tracking=8)
    stroke = max(6, font.size // 11)
    for ln in lines:
        x = (W - _line_width(draw, ln, font)) / 2
        _draw_line_accent(draw, x, y, ln, font, accent_word, accent,
                          stroke=stroke, shadow=False)
        y += line_h
    return img


def _line_width(draw, line: str, font) -> float:
    space = draw.textlength(" ", font=font)
    return sum(draw.textlength(w, font=font) for w in line.split()) + \
        space * (len(line.split()) - 1)


def _design_panel(bg, W, H, kicker, text, accent_word, accent) -> Image.Image:
    horizontal = W > H
    img = Image.new("RGBA", (W, H), (13, 15, 19, 255))
    if horizontal:
        pw = round(W * 0.40)
        img.alpha_composite(_cover(bg, W - pw, H, focus_x=0.5).convert("RGBA"),
                            (pw, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        # sombra suave del panel sobre la imagen (profundidad) + filo acento
        for k in range(round(W * 0.03)):
            a = round(90 * (1 - k / (W * 0.03)))
            draw.line([(pw + k, 0), (pw + k, H)], fill=(0, 0, 0, a))
        draw.rectangle([(pw - max(6, W // 190), 0), (pw, H)], fill=accent)
        tx, tw = round(W * 0.05), pw - round(W * 0.09)
        ty = round(H * 0.30)
    else:
        ph = round(H * 0.36)
        img.alpha_composite(_cover(bg, W, H - ph).convert("RGBA"), (0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([(0, H - ph - max(6, H // 240)), (W, H - ph)], fill=accent)
        tx, tw = round(W * 0.07), W - round(W * 0.14)
        ty = H - ph + round(ph * 0.16)
    if kicker:
        ksize = max(24, round((H if horizontal else W) * 0.032))
        _draw_kicker(draw, tx + 2, ty, kicker, ksize, accent)
        ty += round(ksize * 1.9)
    font, lines = _fit(draw, text, tw, round((H if horizontal else W) * 0.16))
    line_h = round(font.size * 1.16)
    for ln in lines:
        _draw_line_accent(draw, tx, ty, ln, font, accent_word, accent,
                          stroke=0, shadow=False)
        ty += line_h
    draw.rectangle([(tx, ty + 8), (tx + round(tw * 0.28), ty + 8 + 5)],
                   fill=(255, 255, 255, 90))
    return img


_DESIGNS = [("cine", _design_cine), ("impacto", _design_impacto),
            ("panel", _design_panel)]


def pick_backgrounds(scenes: list[dict], wanted_ids: list[int], n: int = 3
                     ) -> list[dict]:
    """Escena de fondo para cada variante: primero las que sugirió el LLM
    (válidas y con imagen), luego las de mayor intensidad dramática — sin
    repetir mientras haya material distinto."""
    with_img = [s for s in scenes if s.get("broll_image")]
    if not with_img:
        return []
    by_id = {int(s["id"]): s for s in with_img}
    ranked = sorted(with_img, key=lambda s: float(s.get("music_intensity") or 0),
                    reverse=True)
    out, used = [], set()
    for sid in wanted_ids:
        s = by_id.get(int(sid or -1))
        if s and s["id"] not in used:
            out.append(s)
            used.add(s["id"])
    for s in ranked:
        if len(out) >= n:
            break
        if s["id"] not in used:
            out.append(s)
            used.add(s["id"])
    while len(out) < n:  # menos imágenes que variantes: se repite la mejor
        out.append(out[-1] if out else ranked[0])
    return out[:n]


def render_thumbnails(project, cfg, options: list[dict],
                      scenes: list[dict]) -> list[str]:
    """Genera miniatura_1..N.jpg (un diseño distinto por opción) y devuelve
    los nombres de archivo. Rápido (PIL local): no añade tiempo perceptible."""
    from ytstudio.catalog import is_vertical
    W, H = (1080, 1920) if is_vertical(cfg) else (1280, 720)
    accent = _hex_rgb(cfg.get("video", {}).get("overlay_accent", "E8C46B"))
    bgs = pick_backgrounds(scenes, [o.get("scene_id") for o in options],
                           n=len(options))
    names: list[str] = []
    for i, opt in enumerate(options):
        text = (opt.get("text") or "").strip() or "LA HISTORIA"
        kicker = (opt.get("kicker") or "").strip()
        accent_word = (opt.get("accent_word") or text.split()[-1]).strip()
        if bgs:
            src = project.path("broll", bgs[i % len(bgs)]["broll_image"])
            base = _enhance(_cover(Image.open(src).convert("RGB"), W, H))
        else:  # sin imágenes aún: fondo neutro de marca
            base = Image.new("RGB", (W, H), (19, 22, 28))
        _, fn = _DESIGNS[i % len(_DESIGNS)]
        img = fn(base, W, H, kicker, text, accent_word, accent)
        name = f"miniatura_{i + 1}.jpg"
        img.convert("RGB").save(project.path("final", name), quality=92)
        names.append(name)
    return names
