"""RÓTULOS con diseño: placa, filete de acento y jerarquía tipográfica.

Hasta v0.46 los rótulos eran `drawtext` puro: texto encima del video, con
sombra. Se leía, pero no era DISEÑO — sobre un B-roll claro perdía contraste,
no había anclaje visual y la palabra clave no podía ir en otro color (drawtext
pinta la línea entera de un solo color).

Aquí se compone el rótulo como PNG con PIL, igual que las miniaturas y los
insertos de archivo:
  · PLACA de fondo (opacidad graduada) que garantiza el contraste sobre
    cualquier imagen,
  · FILETE de acento que ancla el bloque (la marca del canal),
  · JERARQUÍA: antetítulo en versalitas + texto principal + la palabra de
    ÉNFASIS en el color de acento, dentro de la misma línea,
  · tres VARIANTES de estilo por canal: documental (placa sobria), minimal
    (sin placa, solo filete) y bold (placa de color, texto oscuro).

El montaje anima el PNG (deslizamiento + fundido) en el instante en que la
narración dice esas palabras.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.utils.media import find_font

STYLES = ("documental", "minimal", "bold")

# Composición por tipo de rótulo: dónde vive y qué peso tiene.
#   anchor: (x, y) relativos al encuadre — y=0.66 es tercio inferior
#   size: cuerpo del texto principal, relativo a la altura
#   caps: versalitas con tracking (locator documental)
LAYOUTS = {
    "lugar":     {"anchor": (0.062, 0.082), "size": 0.042, "caps": True},
    "fecha":     {"anchor": (0.062, 0.082), "size": 0.042, "caps": True},
    "personaje": {"anchor": (0.062, 0.660), "size": 0.058, "caps": False},
    "dato":      {"anchor": (0.062, 0.145), "size": 0.066, "caps": False},
    "lista":     {"anchor": (0.062, 0.145), "size": 0.050, "caps": False},
}


def _rgb(hex_str: str) -> tuple[int, int, int]:
    s = str(hex_str).lstrip("#").lstrip("0x")[:6] or "E8C46B"
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (232, 196, 107)


def _tracked(text: str, spacing: str = " ") -> str:
    return spacing.join(text.upper())


def _font(path: str | None, size: int):
    from PIL import ImageFont
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _split_emphasis(text: str, emphasis: str) -> list[tuple[str, bool]]:
    """Parte el texto en tramos (fragmento, es_énfasis) para pintar la palabra
    clave en el color de acento DENTRO de la línea."""
    import unicodedata

    def norm(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")

    emph = norm(emphasis or "").strip()
    if not emph:
        return [(text, False)]
    parts: list[tuple[str, bool]] = []
    cur: list[str] = []
    for word in text.split(" "):
        if emph and (norm(word).strip(".,;:!?¿¡") == emph or norm(word) == emph):
            if cur:
                parts.append((" ".join(cur), False))
                cur = []
            parts.append((word, True))
        else:
            cur.append(word)
    if cur:
        parts.append((" ".join(cur), False))
    return parts or [(text, False)]


def render(text: str, kicker: str, emphasis: str, otype: str, out: Path, *,
           width: int, height: int, style: str = "documental",
           accent: str = "E8C46B", text_color: str = "FFFFFF",
           font_main: str | None = None, font_kicker: str | None = None,
           serif: bool = False) -> dict:
    """Compone el rótulo y lo guarda como PNG con transparencia.

    Devuelve {'file', 'x', 'y', 'w', 'h'}: la posición final en el encuadre la
    decide este módulo (conoce el tamaño real del bloque ya compuesto)."""
    from PIL import Image, ImageDraw

    lay = LAYOUTS.get(otype, LAYOUTS["dato"])
    style = style if style in STYLES else "documental"
    ac = _rgb(accent)
    tc = _rgb(text_color)

    body = (text or "").strip()
    if not body:
        raise ValueError("rótulo sin texto")
    if lay["caps"]:
        body = _tracked(body)
    kick = (kicker or "").strip()

    size = max(14, int(height * lay["size"]))
    # Cuerpo adaptado a la longitud: un texto largo baja de cuerpo para no
    # salirse del encuadre (misma regla que tenían los rótulos de siempre).
    size = max(int(size * 0.55), int(size * min(1.0, (20 / max(1, len(body))) ** 0.5)))
    k_size = max(11, int(height * 0.026))

    f_main = _font(font_main or find_font(bold=True, serif=serif), size)
    f_kick = _font(font_kicker or find_font(bold=True), k_size)

    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))

    def measure(txt, font):
        box = probe.textbbox((0, 0), txt, font=font)
        return box[2] - box[0], box[3] - box[1]

    tramos = _split_emphasis(body, emphasis)
    seg_w = [measure(t, f_main)[0] for t, _ in tramos]
    space_w = measure(" ", f_main)[0]
    text_w = sum(seg_w) + space_w * (len(tramos) - 1)
    text_h = int(size * 1.28)
    kick_txt = _tracked(kick, " ") if kick else ""
    kick_w, _ = measure(kick_txt, f_kick) if kick_txt else (0, 0)
    kick_h = int(k_size * 1.9) if kick_txt else 0

    # Geometría del bloque: filete + márgenes de placa
    rule_w = max(3, int(height * 0.006))       # filete vertical de acento
    pad_x = int(size * 0.62)
    pad_y = int(size * 0.42)
    inner_w = max(text_w, kick_w)
    block_w = rule_w + pad_x + inner_w + pad_x
    block_h = pad_y + kick_h + text_h + pad_y
    margin = int(size * 0.5)                    # aire para la sombra
    W, H = block_w + margin * 2, block_h + margin * 2

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    x0, y0 = margin, margin
    x1, y1 = x0 + block_w, y0 + block_h
    radius = max(4, int(size * 0.16))

    if style == "documental":
        # Sombra difusa + placa oscura translúcida: contraste garantizado
        # sobre cualquier B-roll, sin tapar la imagen.
        for i in range(10, 0, -2):
            d.rounded_rectangle([x0 - i // 2, y0 + i // 2, x1 + i // 2, y1 + i],
                                radius=radius + 2, fill=(0, 0, 0, int(16 * (1 - i / 12))))
        d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=(10, 11, 14, 196))
        d.rounded_rectangle([x0, y0, x0 + rule_w, y1], radius=0, fill=(*ac, 255))
        body_color, kick_color = tc, ac
    elif style == "bold":
        # Placa de COLOR con texto oscuro: máxima presencia (canales de
        # divulgación enérgica, cifras que golpean).
        d.rounded_rectangle([x0 + 3, y0 + 4, x1 + 3, y1 + 5], radius=radius,
                            fill=(0, 0, 0, 90))
        d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=(*ac, 240))
        body_color, kick_color = (16, 16, 18), (60, 50, 20)
    else:  # minimal — sin placa: solo el filete y la tipografía
        d.rectangle([x0, y0 + pad_y // 2, x0 + rule_w, y1 - pad_y // 2],
                    fill=(*ac, 255))
        body_color, kick_color = tc, ac

    tx = x0 + rule_w + pad_x
    ty = y0 + pad_y
    if kick_txt:
        if style == "minimal":
            d.text((tx + 1, ty + 1), kick_txt, font=f_kick, fill=(0, 0, 0, 150))
        d.text((tx, ty), kick_txt, font=f_kick, fill=(*kick_color, 255))
        ty += kick_h

    cx = tx
    for (frag, is_emph), fw in zip(tramos, seg_w):
        color = ac if is_emph else body_color
        if style == "minimal":   # sin placa, la sombra sostiene la lectura
            d.text((cx + 2, ty + 2), frag, font=f_main, fill=(0, 0, 0, 170))
        d.text((cx, ty), frag, font=f_main, fill=(*color, 255))
        cx += fw + space_w

    canvas.save(out)
    ax, ay = lay["anchor"]
    x = int(width * ax) - margin
    y = int(height * ay) - margin
    # Nunca fuera del encuadre ni sobre la zona de subtítulos (parte baja)
    x = max(0, min(x, width - W))
    y = max(0, min(y, int(height * 0.80) - H if otype == "personaje"
                   else height - H))
    return {"file": out, "x": x, "y": y, "w": W, "h": H}
