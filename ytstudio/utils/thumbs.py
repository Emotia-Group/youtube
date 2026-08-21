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

from ytstudio.shorts import (MINIATURA_MAX_BYTES, MINIATURA_PALABRAS_MAX,
                             MINIATURA_PRUEBA_PX, accent_over_image,
                             miniatura_margins)
from ytstudio.utils.media import find_font


def _ancho_util(W: int, x: int, ancho: int, safe: dict | None) -> tuple[int, int]:
    """(x, ancho) del texto, metidos en la zona segura de la miniatura.

    Los laterales importan tanto como el alto: en la parrilla del canal la
    miniatura se recorta también por los lados, y una palabra cortada por la
    derecha se lee como un error, no como diseño."""
    if not safe:
        return x, ancho
    izq = max(x, safe["left"])
    return izq, max(80, min(ancho, W - safe["right"] - izq))


def _dentro(y: float, block_h: float, safe: dict | None, H: int) -> int:
    """Sube o baja un bloque de texto hasta que quepa en la ZONA SEGURA.

    En vertical la parrilla del canal recorta arriba y abajo: el texto que se
    sale de esa ventana simplemente no está ahí para quien mira la pestaña de
    Shorts del canal."""
    if not safe:
        return round(y)
    tope = safe["top"]
    suelo = H - safe["bottom"] - block_h
    if suelo < tope:            # bloque más alto que la ventana: se centra
        return round((H - block_h) / 2)
    return round(min(max(y, tope), suelo))


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

def _design_cine(bg, W, H, kicker, text, accent_word, accent,
                 safe=None) -> Image.Image:
    img = bg.convert("RGBA")
    img.alpha_composite(_vgrad(W, H, H * 0.45, H * 0.96, 0, 235))
    draw = ImageDraw.Draw(img, "RGBA")
    if W > H:  # letterbox solo en horizontal
        bar = round(H * 0.045)
        draw.rectangle([(0, 0), (W, bar)], fill=(6, 7, 9, 255))
        draw.rectangle([(0, H - bar), (W, H)], fill=(6, 7, 9, 255))
    margin, ancho = _ancho_util(W, round(W * 0.055), round(W * 0.82), safe)
    font, lines = _fit(draw, text, ancho, round(H * 0.20))
    line_h = round(font.size * 1.14)
    block_h = line_h * len(lines)
    ksize = max(24, round(font.size * 0.30)) if kicker else 0
    alto_kicker = (ksize + round(H * 0.022)) if kicker else 0
    subrayado = 12 + max(5, H // 130)
    y = _dentro(H - round(H * 0.075) - block_h,
                block_h + subrayado, safe, H)
    if safe and kicker:         # el kicker vive por encima del texto
        y = max(y, safe["top"] + alto_kicker)
    if kicker:
        _draw_kicker(draw, margin + 2, y - alto_kicker,
                     kicker, ksize, accent)
    widths = []
    for ln in lines:
        widths.append(_draw_line_accent(draw, margin, y, ln, font,
                                        accent_word, accent, stroke=2))
        y += line_h
    # subrayado de acento bajo la última línea
    uw = min(max(widths), round(ancho * 0.6))
    draw.rectangle([(margin, y + 6), (margin + uw, y + 6 + max(5, H // 130))],
                   fill=accent)
    return img


def _design_impacto(bg, W, H, kicker, text, accent_word, accent,
                    safe=None) -> Image.Image:
    img = bg.convert("RGBA")
    img.alpha_composite(_vignette(W, H, 185))
    img.alpha_composite(_vgrad(W, H, H * 0.55, H, 0, 120))
    draw = ImageDraw.Draw(img, "RGBA")
    izq, ancho = _ancho_util(W, round(W * 0.07), round(W * 0.86), safe)
    centro = izq + ancho / 2
    font, lines = _fit(draw, text, ancho, round(H * 0.24))
    line_h = round(font.size * 1.08)
    block_h = line_h * len(lines)
    y = round(H * 0.56) - block_h // 2 if W > H else round(H * 0.64) - block_h // 2
    ksize0 = max(26, round(font.size * 0.26)) if kicker else 0
    alto_kicker = (ksize0 + round(ksize0 * 1.1) + round(H * 0.03)) if kicker else 0
    y = _dentro(y, block_h, safe, H)
    if safe and kicker:
        y = max(y, safe["top"] + alto_kicker)
    if kicker:
        ksize = max(26, round(font.size * 0.26))
        kfont = _font(ksize)
        kw = draw.textlength(kicker.upper(), font=kfont) + 8 * len(kicker)
        pad = round(ksize * 0.55)
        kx = centro - kw / 2
        ky = y - ksize - pad * 2 - round(H * 0.03)
        draw.rounded_rectangle([(kx - pad, ky - pad // 2),
                                (kx + kw + pad, ky + ksize + pad)],
                               radius=8, fill=(*accent, 235))
        _draw_kicker(draw, kx, ky, kicker, ksize, (12, 12, 14), tracking=8)
    stroke = max(6, font.size // 11)
    for ln in lines:
        x = centro - _line_width(draw, ln, font) / 2
        _draw_line_accent(draw, x, y, ln, font, accent_word, accent,
                          stroke=stroke, shadow=False)
        y += line_h
    return img


def _line_width(draw, line: str, font) -> float:
    space = draw.textlength(" ", font=font)
    return sum(draw.textlength(w, font=font) for w in line.split()) + \
        space * (len(line.split()) - 1)


def _design_panel(bg, W, H, kicker, text, accent_word, accent,
                  safe=None) -> Image.Image:
    """Panel oscuro con filo de acento y texto apilado; la imagen respira al
    otro lado. En vertical el panel se dimensiona DESPUÉS de medir el texto,
    para que ni una línea caiga en la franja que recorta la parrilla."""
    horizontal = W > H
    img = Image.new("RGBA", (W, H), (13, 15, 19, 255))
    medidor = ImageDraw.Draw(img, "RGBA")
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
        ksize = max(24, round(H * 0.032)) if kicker else 0
        font, lines = _fit(medidor, text, tw, round(H * 0.16))
    else:
        tx, tw = _ancho_util(W, round(W * 0.07), W - round(W * 0.14), safe)
        ksize = max(24, round(W * 0.032)) if kicker else 0
        font, lines = _fit(medidor, text, tw, round(W * 0.16))
        alto_kicker = round(ksize * 1.9) if kicker else 0
        bloque = alto_kicker + round(font.size * 1.16) * len(lines) + 13
        pad = round(H * 0.03)
        ph = round(H * 0.36)
        if safe:   # el panel crece lo justo para que el texto quede dentro
            ph = min(round(H * 0.62), max(ph, safe["bottom"] + bloque + pad * 2))
        img.alpha_composite(_cover(bg, W, H - ph).convert("RGBA"), (0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([(0, H - ph - max(6, H // 240)), (W, H - ph)],
                       fill=accent)
        ty = H - ph + pad
    if kicker:
        _draw_kicker(draw, tx + 2, ty, kicker, ksize, accent)
        ty += round(ksize * 1.9)
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


def _guardar(img: Image.Image, dest: Path) -> int:
    """Guarda la miniatura por debajo del límite de peso de la plataforma
    (2 MB). Devuelve el tamaño final en bytes."""
    calidad = 92
    while True:
        img.convert("RGB").save(dest, quality=calidad, optimize=True)
        peso = dest.stat().st_size
        if peso <= MINIATURA_MAX_BYTES or calidad <= 60:
            return peso
        calidad -= 8


def prueba_150px(dest: Path) -> Path:
    """LA PRUEBA QUE DECIDE SI LA MINIATURA SIRVE.

    La miniatura no se ve nunca a 1080 px de ancho: se ve a unos 150 en la
    parrilla del canal. Se guarda esa versión reducida al lado, sobre un
    fondo neutro, para poder mirarla al tamaño de verdad. Si ahí no se lee el
    texto, la miniatura no sirve — por bonita que sea a tamaño completo."""
    img = Image.open(dest)
    alto = round(img.height * MINIATURA_PRUEBA_PX / img.width)
    pequena = img.convert("RGB").resize((MINIATURA_PRUEBA_PX, alto),
                                        Image.LANCZOS)
    lienzo = Image.new("RGB", (MINIATURA_PRUEBA_PX + 40, alto + 40), (32, 34, 38))
    lienzo.paste(pequena, (20, 20))
    salida = dest.with_name(dest.stem + "_prueba150px.png")
    lienzo.save(salida)
    return salida


def render_thumbnails(project, cfg, options: list[dict],
                      scenes: list[dict]) -> list[str]:
    """Genera miniatura_1..N.jpg (un diseño distinto por opción) y devuelve
    los nombres de archivo. Rápido (PIL local): no añade tiempo perceptible.

    En vertical (Shorts) manda el framework §4.1: lienzo 9:16 de 1080x1920,
    texto dentro de la zona segura de la parrilla, color de acento aclarado
    para que se lea sobre la imagen, menos de 2 MB, y su prueba a 150 px al
    lado."""
    from ytstudio.catalog import is_vertical
    vertical = is_vertical(cfg)
    W, H = (1080, 1920) if vertical else (1280, 720)
    safe = miniatura_margins(W, H) if vertical else None
    acento_hex = cfg.get("video", {}).get("overlay_accent", "E8C46B")
    # Sobre imagen, el color de marca calibrado para fondo negro se queda sin
    # contraste: en vertical se usa la variante aclarada.
    accent = _hex_rgb(accent_over_image(acento_hex) if vertical else acento_hex)
    bgs = pick_backgrounds(scenes, [o.get("scene_id") for o in options],
                           n=len(options))
    names: list[str] = []
    largas: list[str] = []
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
        img = fn(base, W, H, kicker, text, accent_word, accent, safe)
        name = f"miniatura_{i + 1}.jpg"
        dest = project.path("final", name)
        _guardar(img, dest)
        if vertical:
            prueba_150px(dest)
            if len(text.split()) > MINIATURA_PALABRAS_MAX:
                largas.append(text)
        names.append(name)
    if largas:
        project.add_warning(
            f"{len(largas)} miniatura(s) con más de {MINIATURA_PALABRAS_MAX} "
            "palabras. A 150 px —el tamaño al que se ve de verdad en la "
            "parrilla del canal— solo entran una cara y tres o cuatro "
            "palabras: mira las pruebas «_prueba150px.png» antes de elegir.")
    return names
