"""Metadatos de enlaces web de referencia (YouTube, Vimeo, Wistia o cualquier
página). Se usa la API oEmbed pública del proveedor cuando existe y las
etiquetas Open Graph / title de la página como respaldo — sin dependencias y
sin descargar el video."""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ytstudio/1.0)"}


def _get(url: str, timeout: float = 15) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(1_500_000).decode("utf-8", errors="replace")


def _oembed_endpoint(url: str) -> str | None:
    u = url.lower()
    q = urllib.parse.quote(url, safe="")
    if "youtube.com" in u or "youtu.be" in u:
        return f"https://www.youtube.com/oembed?url={q}&format=json"
    if "vimeo.com" in u:
        return f"https://vimeo.com/api/oembed.json?url={q}"
    if "wistia.com" in u or "wi.st" in u:
        return f"https://fast.wistia.com/oembed?url={q}&format=json"
    return None


def _og(html_text: str, prop: str) -> str | None:
    # <meta property="og:x" content="..."> en cualquier orden de atributos
    pat1 = rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']*)'
    pat2 = rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']{re.escape(prop)}'
    m = re.search(pat1, html_text, re.I) or re.search(pat2, html_text, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def fetch_link_info(url: str) -> dict:
    """Título, autor, proveedor y descripción de un enlace. Nunca lanza:
    si algo falla devuelve el dict con la clave 'error'."""
    info: dict = {"url": url}
    try:
        endpoint = _oembed_endpoint(url)
        if endpoint:
            data = json.loads(_get(endpoint))
            for src, dst in (("title", "title"), ("author_name", "author"),
                             ("provider_name", "provider")):
                if data.get(src):
                    info[dst] = str(data[src])
        page = _get(url)
        info.setdefault("title", _og(page, "og:title") or None)
        desc = _og(page, "og:description")
        if not desc:
            m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content='
                          r'["\']([^"\']*)', page, re.I)
            desc = html.unescape(m.group(1)).strip() if m else None
        if desc:
            info["description"] = desc[:1500]
        if not info.get("title"):
            m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
            if m:
                info["title"] = html.unescape(m.group(1)).strip()[:200]
        if not info.get("title") and not info.get("description"):
            info["error"] = "la página no expone título ni descripción"
    except Exception as e:
        info["error"] = str(e)
    return info


def link_summary(info: dict) -> str:
    lines = [f"URL: {info['url']}"]
    for key, label in (("provider", "Plataforma"), ("title", "Título"),
                       ("author", "Canal/Autor"), ("description", "Descripción")):
        if info.get(key):
            lines.append(f"{label}: {info[key]}")
    return "\n".join(lines)
