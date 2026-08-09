"""ELEMENTOS documentales de superposición: el material de archivo que
acompaña a las menciones de la narración (personajes, lugares, entidades,
cifras, fechas) como tarjetas sobre el B-roll.

Tres fuentes, en orden de prioridad:
1. El BANCO LOCAL del creador (assets/elements/<categoría>/): archivos de uso
   libre que él mismo coloca. Manda siempre que haya coincidencia.
2. WIKIMEDIA/WIKIPEDIA (solo licencias libres): la foto principal del artículo
   de la entidad. La atribución se guarda y se añade sola a la descripción
   del video en la fase de Metadatos.
3. GENERADO EN LOCAL (costo cero, PIL): cifras con cuenta ascendente y fechas
   en tarjeta — el recurso que más se nota y el más barato.

Las tarjetas son PNG con transparencia (como los stickers): el montaje las
anima (deslizamiento + fundido) en el instante exacto de la mención.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from ytstudio.config import ROOT
from ytstudio.utils.media import find_font

BANK_DIR = ROOT / "assets" / "elements"
CATEGORIES = ("personajes", "lugares", "entidades", "mapas", "stickers")

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v")
BANK_EXT = IMAGE_EXT + VIDEO_EXT

# Licencias admitidas de Wikimedia (prefijo del LicenseShortName, minúsculas):
# solo material libre — con atribución automática en la descripción.
_FREE_LICENSES = ("cc0", "cc by", "cc-by", "public domain", "pd", "no restrictions")

_HEADERS = {"User-Agent": "ytstudio/1.0 (documental; contacto: local)"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# --- fuente 1: banco local -------------------------------------------------

def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXT


def bank_lookup(query: str, categories: tuple = CATEGORIES) -> Path | None:
    """Busca en assets/elements/ un archivo cuyo nombre coincida con la
    consulta (sin tildes ni signos): 'elon-musk.jpg' encaja con «Elon Musk».
    El material del creador SIEMPRE tiene prioridad sobre internet, y puede
    ser imagen O CLIP DE VIDEO."""
    qn = _norm(query)
    if not qn or not BANK_DIR.is_dir():
        return None
    best: tuple[int, Path] | None = None
    for cat in categories:
        d = BANK_DIR / cat
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in BANK_EXT:
                continue
            fn = _norm(p.stem)
            if fn == qn:
                return p
            if fn and (fn in qn or qn in fn):
                score = len(fn)
                if best is None or score > best[0]:
                    best = (score, p)
    return best[1] if best else None


# --- gestión del banco desde la interfaz ----------------------------------

def bank_list() -> dict[str, list[dict]]:
    """Inventario del banco por categoría, para la pestaña Biblioteca."""
    out: dict[str, list[dict]] = {}
    for cat in CATEGORIES:
        d = BANK_DIR / cat
        items: list[dict] = []
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.suffix.lower() not in BANK_EXT:
                    continue
                items.append({"file": p.name, "etiqueta": p.stem,
                              "kind": "video" if is_video(p) else "image",
                              "size": p.stat().st_size})
        out[cat] = items
    return out


def bank_add(category: str, filename: str, data: bytes) -> dict:
    """Guarda un elemento en el banco. El NOMBRE es la clave de búsqueda: se
    conserva tal cual lo escribe el creador (así «El Cairo.jpg» encuentra la
    mención «El Cairo»)."""
    if category not in CATEGORIES:
        raise ValueError(f"Categoría desconocida: {category}")
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext not in BANK_EXT:
        raise ValueError(
            f"Formato no admitido: {ext or 'sin extensión'}. Usa imágenes "
            "(jpg, png, webp) o clips (mp4, webm, mov).")
    if not data:
        raise ValueError("El archivo está vacío.")
    d = BANK_DIR / category
    d.mkdir(parents=True, exist_ok=True)
    dest = d / name
    dest.write_bytes(data)
    return {"file": dest.name, "etiqueta": dest.stem,
            "kind": "video" if is_video(dest) else "image",
            "size": len(data)}


def bank_delete(category: str, filename: str) -> bool:
    if category not in CATEGORIES:
        raise ValueError(f"Categoría desconocida: {category}")
    p = (BANK_DIR / category / Path(filename).name)
    if not p.exists() or p.suffix.lower() not in BANK_EXT:
        return False
    p.unlink()
    return True


# --- fuente 2: Wikipedia/Wikimedia (licencias libres) ----------------------

def _api_json(url: str, timeout: float = 12) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(2_000_000).decode("utf-8", errors="replace"))


def _page_image(query: str, lang: str) -> tuple[str, str] | None:
    """(url_original, nombre_de_archivo) de la imagen principal del artículo
    de Wikipedia sobre la entidad — mucho más certera que una búsqueda libre
    (la foto canónica de «Elon Musk», no cualquier resultado)."""
    for wiki in (lang, "en"):
        u = (f"https://{wiki}.wikipedia.org/w/api.php?action=query&format=json"
             f"&redirects=1&prop=pageimages&piprop=original|name"
             f"&titles={urllib.parse.quote(query)}")
        try:
            pages = (_api_json(u).get("query") or {}).get("pages") or {}
        except Exception:
            continue
        for p in pages.values():
            orig = (p.get("original") or {}).get("source")
            name = p.get("pageimage")
            if orig and name:
                return orig, name
    return None


def geo_lookup(query: str, lang: str = "es") -> tuple[float, float] | None:
    """Coordenadas (lat, lon) del lugar según Wikipedia, o None. Es lo que
    permite poner el pin del mapa en el sitio EXACTO que se narra."""
    for wiki in (lang, "en"):
        u = (f"https://{wiki}.wikipedia.org/w/api.php?action=query&format=json"
             f"&redirects=1&prop=coordinates"
             f"&titles={urllib.parse.quote(query)}")
        try:
            pages = (_api_json(u).get("query") or {}).get("pages") or {}
        except Exception:
            continue
        for p in pages.values():
            for c in (p.get("coordinates") or []):
                try:
                    return float(c["lat"]), float(c["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
    return None


def _commons_license(file_name: str) -> tuple[str, str] | None:
    """(licencia, autor) del archivo en Commons, o None si no es libre."""
    u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
         "&prop=imageinfo&iiprop=extmetadata"
         f"&titles=File:{urllib.parse.quote(file_name)}")
    try:
        pages = (_api_json(u).get("query") or {}).get("pages") or {}
    except Exception:
        return None
    for p in pages.values():
        meta = ((p.get("imageinfo") or [{}])[0]).get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {})
                        .get("value", "")).strip()
        if lic and any(lic.lower().startswith(f) for f in _FREE_LICENSES):
            return lic, (artist or "autor no indicado")
    return None


def wiki_photo(query: str, lang: str, out_dir: Path) -> dict | None:
    """Foto LIBRE de la entidad: {'file': Path, 'credit': str} o None.
    Solo licencias libres verificadas; la atribución exacta viaja con el
    resultado para añadirla a la descripción del video."""
    hit = _page_image(query, lang)
    if not hit:
        return None
    url, name = hit
    lic = _commons_license(name)
    if lic is None:
        return None   # sin licencia libre verificada, no se usa
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        return None   # svg u otros: fuera del alcance del compositor
    out = out_dir / (re.sub(r"[^a-z0-9]+", "_", _norm(query)) + ext)
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            out.write_bytes(r.read(15_000_000))
    except Exception:
        return None
    license_name, artist = lic
    return {"file": out,
            "credit": f"{query}: {artist} ({license_name}), Wikimedia Commons"}


# --- fuente 3 y composición: tarjetas PIL (costo cero) ---------------------

def _font(size: int, bold: bool = True):
    from PIL import ImageFont
    path = find_font(bold=bold)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _shadow_card(draw, box, radius: int, fill, shadow: int = 12) -> None:
    x0, y0, x1, y1 = box
    for i in range(shadow, 0, -2):
        a = int(40 * (1 - i / shadow))
        draw.rounded_rectangle([x0, y0 + i // 2, x1, y1 + i],
                               radius=radius + 2, fill=(0, 0, 0, a))
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def render_photo_card(photo: Path, label: str, out: Path, card_w: int,
                      accent: str = "E8C46B") -> Path:
    """Tarjeta de ARCHIVO: la foto con marco blanco tipo copia impresa,
    etiqueta debajo y sombra suave — sobria, estilo documental."""
    from PIL import Image, ImageDraw
    img = Image.open(photo).convert("RGB")
    inner_w = card_w - 28 * 2
    ratio = min(1.5, max(0.6, img.height / img.width))
    inner_h = int(inner_w * ratio)
    scale = max(inner_w / img.width, inner_h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)))
    x = (img.width - inner_w) // 2
    y = (img.height - inner_h) // 2
    img = img.crop((x, y, x + inner_w, y + inner_h))

    lab_h = 64 if label else 20
    W, H = card_w + 24, 28 + inner_h + lab_h + 28 + 18
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    _shadow_card(d, (12, 8, 12 + card_w, 8 + 28 + inner_h + lab_h + 20),
                 radius=10, fill=(248, 246, 240, 250))
    canvas.paste(img, (12 + 28, 8 + 28))
    if label:
        f = _font(30, bold=True)
        ac = tuple(int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        ty = 8 + 28 + inner_h + 14
        d.text((12 + 28, ty), label[:40], font=f, fill=(30, 28, 24, 255))
        d.rectangle([12 + 28, ty + 38, 12 + 28 + 46, ty + 42],
                    fill=(*ac, 255))
    canvas.save(out)
    return out


_NUM_RE = re.compile(r"^(.*?)([\d][\d\.\,]*)(.*)$", re.S)


def render_stat_frames(text: str, kicker: str, out_dir: Path, card_w: int,
                       accent: str = "E8C46B", frames: int = 14) -> list[Path]:
    """Tarjeta de CIFRA/FECHA. Si el texto arranca con un número, la cifra
    SUBE en cuenta ascendente hasta el valor real (una secuencia de PNG que
    el montaje reproduce); si no hay número, una sola tarjeta estática.
    Conserva el formato original (separador de miles incluido)."""
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    m = _NUM_RE.match(text.strip())
    prefix, num_txt, suffix = (m.groups() if m else ("", "", text.strip()))
    sep = "." if "." in num_txt else ("," if "," in num_txt else "")
    try:
        value = int(re.sub(r"[\.,]", "", num_txt)) if num_txt else None
    except ValueError:
        value = None

    def fmt(v: int) -> str:
        s = f"{v:,}".replace(",", "\x00").replace(".", ",")
        return s.replace("\x00", sep or "")

    ac = tuple(int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    f_big = _font(int(card_w * 0.175), bold=True)
    f_kick = _font(int(card_w * 0.075), bold=False)
    H = int(card_w * 0.44) + (34 if kicker else 0)

    steps = ([round(value * (i / (frames - 1)) ** 2.2) for i in range(frames - 1)]
             + [value]) if value is not None and value > 1 else [None]
    paths: list[Path] = []
    for i, v in enumerate(steps):
        canvas = Image.new("RGBA", (card_w + 24, H + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        _shadow_card(d, (12, 6, 12 + card_w, 6 + H), radius=12,
                     fill=(16, 15, 20, 225))
        y = 6 + 22
        if kicker:
            d.text((12 + 30, y), kicker[:36].upper(), font=f_kick,
                   fill=(215, 214, 210, 255))
            y += 40
        shown = (f"{prefix}{fmt(v)}{suffix}" if v is not None
                 else f"{prefix}{num_txt}{suffix}")
        d.text((12 + 30, y), shown[:26], font=f_big, fill=(*ac, 255))
        p = out_dir / f"f_{i:02d}.png"
        canvas.save(p)
        paths.append(p)
    return paths
