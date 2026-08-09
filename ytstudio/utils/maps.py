"""MAPAS de ubicación animados para los insertos documentales.

Cuando la narración sitúa la historia («cruzó el Sahara», «llegó a El Cairo»),
un mapa localizador con el pin cayendo sobre el punto exacto vale más que
cualquier ilustración: el espectador entiende DÓNDE en un segundo.

Dos caminos, con el mismo criterio de siempre:
1. MAPA REAL: teselas de maps.wikimedia.org (OpenStreetMap, licencia libre
   ODbL). Se descargan las que cubren el punto, se unen, se tiñen al lenguaje
   del documental y se marca la ubicación. La atribución a OpenStreetMap se
   añade sola a la descripción del video.
2. RESPALDO LOCAL (sin internet o si el servicio no responde): una ficha de
   coordenadas con retícula y pin en su posición relativa correcta. No es un
   mapa, pero es un localizador digno — y nunca falla.

En ambos casos el resultado es una SECUENCIA de PNG: el pin cae y un anillo
se expande, y el montaje la reproduce en el instante de la mención.
"""
from __future__ import annotations

import math
import urllib.request
from pathlib import Path

from ytstudio.utils.media import find_font

TILE_URL = "https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png"
TILE_PX = 256
OSM_CREDIT = ("Mapas: © colaboradores de OpenStreetMap (ODbL), "
              "vía Wikimedia Maps")
_HEADERS = {"User-Agent": "ytstudio/1.0 (documental; contacto: local)"}

FRAMES = 14           # cuadros de la animación (pin + anillo), a 12 fps


def tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    """Coordenadas de tesela (con decimales) del punto, en el esquema Web
    Mercator que usan todos los mapas de teselas."""
    lat = max(-85.05, min(85.05, float(lat)))
    n = 2.0 ** z
    x = (float(lon) + 180.0) / 360.0 * n
    rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(rad)) / math.pi) / 2.0 * n
    return x, y


def _fetch_tile(z: int, x: int, y: int, timeout: float = 12):
    from PIL import Image
    n = 2 ** z
    if not (0 <= y < n):
        return None
    url = TILE_URL.format(z=z, x=x % n, y=y)
    req = urllib.request.Request(url, headers=_HEADERS)
    import io
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return Image.open(io.BytesIO(r.read(4_000_000))).convert("RGB")


def fetch_map(lat: float, lon: float, z: int, width: int, height: int):
    """Trozo de mapa REAL centrado en el punto, o None si no se pudo.
    Devuelve una imagen PIL de (width × height)."""
    from PIL import Image
    fx, fy = tile_xy(lat, lon, z)
    cols = math.ceil(width / TILE_PX) + 2
    rows = math.ceil(height / TILE_PX) + 2
    x0, y0 = int(fx) - cols // 2, int(fy) - rows // 2
    canvas = Image.new("RGB", (cols * TILE_PX, rows * TILE_PX), (232, 230, 224))
    got = 0
    for i in range(cols):
        for j in range(rows):
            try:
                t = _fetch_tile(z, x0 + i, y0 + j)
            except Exception:
                t = None
            if t is not None:
                canvas.paste(t, (i * TILE_PX, j * TILE_PX))
                got += 1
    if got == 0:
        return None
    # recorte centrado EXACTAMENTE en el punto pedido
    px = (fx - x0) * TILE_PX
    py = (fy - y0) * TILE_PX
    left = int(px - width / 2)
    top = int(py - height / 2)
    left = max(0, min(left, canvas.width - width))
    top = max(0, min(top, canvas.height - height))
    return canvas.crop((left, top, left + width, top + height))


def _stylize(img, accent: tuple[int, int, int]):
    """Tiñe el mapa al lenguaje del documental: desaturado, oscurecido y con
    un velo del color de acento — así no parece una captura de Google Maps
    pegada encima del video."""
    from PIL import Image, ImageEnhance
    g = ImageEnhance.Color(img).enhance(0.25)
    g = ImageEnhance.Brightness(g).enhance(0.62)
    veil = Image.new("RGB", g.size, accent)
    return Image.blend(g, veil, 0.12)


def _grid_backdrop(size, lat: float, lon: float, accent):
    """Respaldo sin internet: retícula de meridianos y paralelos con el punto
    en su posición relativa correcta (proyección equirectangular)."""
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("RGB", size, (18, 20, 26))
    d = ImageDraw.Draw(img)
    for i in range(1, 8):          # meridianos
        x = w * i / 8
        d.line([(x, 0), (x, h)], fill=(44, 48, 58), width=1)
    for j in range(1, 5):          # paralelos
        y = h * j / 5
        d.line([(0, y), (w, y)], fill=(44, 48, 58), width=1)
    d.line([(0, h / 2), (w, h / 2)], fill=(70, 74, 86), width=2)  # ecuador
    return img


def _point_xy(size, lat: float, lon: float) -> tuple[int, int]:
    w, h = size
    return int(w * (float(lon) + 180.0) / 360.0), int(h * (90.0 - float(lat)) / 180.0)


def render_map_frames(place: str, lat: float, lon: float, out_dir: Path, *,
                      card_w: int, accent: str = "E8C46B", zoom: int = 5,
                      allow_web: bool = True) -> dict:
    """Secuencia animada del localizador. Devuelve
    {'files': [nombres], 'real': bool} — 'real' dice si el mapa es
    cartografía de verdad o el respaldo local."""
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    ac = tuple(int(str(accent).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    mw, mh = card_w, int(card_w * 0.62)

    base = None
    if allow_web:
        try:
            base = fetch_map(lat, lon, zoom, mw, mh)
        except Exception:
            base = None
    real = base is not None
    if real:
        base = _stylize(base, ac)
        px, py = mw // 2, mh // 2          # el mapa está centrado en el punto
    else:
        base = _grid_backdrop((mw, mh), lat, lon, ac)
        px, py = _point_xy((mw, mh), lat, lon)

    label = (place or "").strip()[:34]
    coords = (f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}  "
              f"{abs(lon):.1f}°{'E' if lon >= 0 else 'O'}")
    f_lab = _font_or_default(int(card_w * 0.062), True)
    f_coord = _font_or_default(int(card_w * 0.036), False)
    bar_h = int(card_w * 0.155)
    border = max(3, int(card_w * 0.012))
    W = mw + border * 2
    H = mh + bar_h + border * 2

    files: list[str] = []
    for i in range(FRAMES):
        t = i / (FRAMES - 1)
        canvas = Image.new("RGBA", (W + 16, H + 16), (0, 0, 0, 0))
        d0 = ImageDraw.Draw(canvas)
        d0.rounded_rectangle([8, 10, 8 + W, 10 + H], radius=10,
                             fill=(0, 0, 0, 90))
        d0.rounded_rectangle([8, 8, 8 + W, 8 + H], radius=10,
                             fill=(246, 244, 238, 250))
        canvas.paste(base, (8 + border, 8 + border))
        d = ImageDraw.Draw(canvas)
        ox, oy = 8 + border, 8 + border

        # ANILLO que se expande y se apaga (el «aquí»)
        if t > 0.35:
            k = (t - 0.35) / 0.65
            r = int(card_w * 0.03 + card_w * 0.16 * k)
            a = int(200 * (1 - k))
            d.ellipse([ox + px - r, oy + py - r, ox + px + r, oy + py + r],
                      outline=(*ac, a), width=max(2, int(card_w * 0.008)))
        # PIN que cae y se asienta (rebote suave)
        drop = int(card_w * 0.22 * max(0.0, 1 - t * 2.2) ** 2)
        pr = max(4, int(card_w * 0.022))
        cy = oy + py - drop
        d.line([(ox + px, cy), (ox + px, oy + py)], fill=(*ac, 160), width=2)
        d.ellipse([ox + px - pr, cy - pr, ox + px + pr, cy + pr],
                  fill=(*ac, 255), outline=(30, 28, 24, 255), width=2)

        # Pie: nombre del lugar + coordenadas
        ty = 8 + border + mh + int(bar_h * 0.16)
        d.text((ox, ty), label, font=f_lab, fill=(26, 25, 22, 255))
        d.text((ox, ty + int(card_w * 0.075)), coords, font=f_coord,
               fill=(110, 108, 102, 255))
        d.rectangle([ox, 8 + border + mh + 3, ox + int(card_w * 0.11),
                     8 + border + mh + 3 + max(3, int(card_w * 0.009))],
                    fill=(*ac, 255))
        p = out_dir / f"f_{i:02d}.png"
        canvas.save(p)
        files.append(p.name)
    return {"files": files, "real": real}


def _font_or_default(size: int, bold: bool):
    from PIL import ImageFont
    path = find_font(bold=bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)
