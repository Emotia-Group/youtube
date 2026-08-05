"""STICKERS de aspecto nativo (encuesta, pregunta, cuenta regresiva) para
formatos cortos — imitaciones VISUALES de los stickers de Instagram/TikTok.

Importante (decisión de diseño acordada): un MP4 no puede ser interactivo —
la interactividad real solo la añade la app al publicar. Estos stickers se
RENDERIZAN en el video con el mismo aspecto y animación que los nativos,
como recurso de retención (el espectador se detiene a leerlos y muchos
responden en comentarios). Se dibujan con PIL en local: costo cero.

Cada renderizador produce un PNG con transparencia (esquinas redondeadas y
sombra suave); el montaje lo anima (deslizamiento + fundido) y, en la cuenta
regresiva, le superpone el número vivo con drawtext.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.utils.media import find_font

# Colores de sistema (look nativo: tarjeta blanca, tinta oscura, acento IG)
_INK = (28, 28, 34, 255)
_MUTED = (130, 133, 142, 255)
_CARD = (255, 255, 255, 244)
_ACCENT = (131, 58, 180, 255)     # violeta IG
_ACCENT2 = (225, 48, 108, 255)    # magenta IG
_DARK_CARD = (18, 18, 24, 235)


def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    path = find_font(bold=bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _canvas(w: int, h: int):
    from PIL import Image
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _shadowed_card(draw, box, radius: int, fill=_CARD, shadow=14):
    """Tarjeta redondeada con sombra suave (dibujada como halos)."""
    x0, y0, x1, y1 = box
    for i in range(shadow, 0, -2):
        a = int(38 * (1 - i / shadow))
        draw.rounded_rectangle([x0 - 0, y0 + i // 2, x1 + 0, y1 + i],
                               radius=radius + 2, fill=(0, 0, 0, a))
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and draw.textlength(cand, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines[:3]


def render_poll(question: str, opt_a: str, opt_b: str, width: int,
                out: Path) -> Path:
    """Sticker de ENCUESTA: tarjeta blanca con la pregunta y dos opciones en
    pastilla, la primera con el degradado de acento (look nativo IG)."""
    from PIL import Image, ImageDraw
    pad = width // 14
    qfont = _font(int(width * 0.082))
    ofont = _font(int(width * 0.075))
    probe = ImageDraw.Draw(_canvas(8, 8))
    qlines = _wrap(probe, question.strip()[:80], qfont, width - 2 * pad)
    qh = len(qlines) * int(qfont.size * 1.25)
    pill_h = int(width * 0.155)
    h = pad + qh + pad // 2 + 2 * pill_h + int(pad * 0.7) + pad + 14
    img = _canvas(width, h)
    d = ImageDraw.Draw(img)
    _shadowed_card(d, [0, 0, width - 1, h - 15], radius=width // 12)
    y = pad
    for ln in qlines:
        d.text((width // 2 - d.textlength(ln, font=qfont) / 2, y), ln,
               font=qfont, fill=_INK)
        y += int(qfont.size * 1.25)
    y += pad // 2
    for i, opt in enumerate((opt_a.strip()[:24] or "SÍ",
                             opt_b.strip()[:24] or "NO")):
        box = [pad, y, width - pad, y + pill_h]
        if i == 0:
            # opción A con borde de acento en degradado horizontal simulado
            d.rounded_rectangle(box, radius=pill_h // 2, outline=_ACCENT,
                                width=4)
            grad_fill = _ACCENT if i == 0 else _INK
            d.text((width // 2 - d.textlength(opt, font=ofont) / 2,
                    y + (pill_h - ofont.size) // 2), opt, font=ofont,
                   fill=grad_fill)
        else:
            d.rounded_rectangle(box, radius=pill_h // 2, outline=_ACCENT2,
                                width=4)
            d.text((width // 2 - d.textlength(opt, font=ofont) / 2,
                    y + (pill_h - ofont.size) // 2), opt, font=ofont,
                   fill=_ACCENT2)
        y += pill_h + int(pad * 0.7)
    img.save(out)
    return out


def render_question(prompt: str, width: int, out: Path,
                    hint: str = "Responde en comentarios…") -> Path:
    """Sticker de PREGUNTA: cabecera con degradado de acento + campo de
    respuesta con pista — el look del sticker de preguntas de IG, apuntando
    la respuesta a los comentarios (que es donde SÍ es interactivo)."""
    from PIL import Image, ImageDraw
    pad = width // 14
    qfont = _font(int(width * 0.08))
    hfont = _font(int(width * 0.062), bold=False)
    probe = ImageDraw.Draw(_canvas(8, 8))
    qlines = _wrap(probe, prompt.strip()[:90], qfont, width - 2 * pad)
    qh = len(qlines) * int(qfont.size * 1.25)
    field_h = int(width * 0.17)
    h = pad + qh + pad // 2 + field_h + pad + 14
    img = _canvas(width, h)
    d = ImageDraw.Draw(img)
    _shadowed_card(d, [0, 0, width - 1, h - 15], radius=width // 12)
    # banda superior de acento (degradado simulado en dos mitades)
    band_h = max(8, width // 40)
    d.rounded_rectangle([0, 0, width - 1, band_h * 2], radius=band_h,
                        fill=_ACCENT)
    y = pad
    for ln in qlines:
        d.text((width // 2 - d.textlength(ln, font=qfont) / 2, y), ln,
               font=qfont, fill=_INK)
        y += int(qfont.size * 1.25)
    y += pad // 2
    d.rounded_rectangle([pad, y, width - pad, y + field_h],
                        radius=field_h // 3, fill=(240, 240, 244, 255))
    d.text((width // 2 - d.textlength(hint, font=hfont) / 2,
            y + (field_h - hfont.size) // 2), hint, font=hfont, fill=_MUTED)
    img.save(out)
    return out


def render_countdown(label: str, width: int, out: Path) -> tuple[Path, dict]:
    """Sticker de CUENTA REGRESIVA: tarjeta oscura con el rótulo y un hueco
    para el NÚMERO — el número lo pinta el montaje con drawtext dinámico
    (cambia cada segundo de verdad). Devuelve (png, geometría del hueco)."""
    from PIL import Image, ImageDraw
    pad = width // 14
    lfont = _font(int(width * 0.07))
    probe = ImageDraw.Draw(_canvas(8, 8))
    llines = _wrap(probe, label.strip()[:60] or "¿LISTO?", lfont,
                   width - 2 * pad)
    lh = len(llines) * int(lfont.size * 1.3)
    num_h = int(width * 0.34)
    h = pad + lh + pad // 2 + num_h + pad + 14
    img = _canvas(width, h)
    d = ImageDraw.Draw(img)
    _shadowed_card(d, [0, 0, width - 1, h - 15], radius=width // 12,
                   fill=_DARK_CARD)
    y = pad
    for ln in llines:
        d.text((width // 2 - d.textlength(ln, font=lfont) / 2, y), ln,
               font=lfont, fill=(255, 255, 255, 255))
        y += int(lfont.size * 1.3)
    y += pad // 2
    # marco sutil del área del número
    d.rounded_rectangle([pad, y, width - pad, y + num_h],
                        radius=num_h // 6, outline=(255, 255, 255, 60),
                        width=3)
    geom = {"num_y": y, "num_h": num_h, "size": int(num_h * 0.62)}
    img.save(out)
    return out, geom
