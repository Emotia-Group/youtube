"""Limpieza de TEXTO que viene de fuera (guion escrito, transcripción).

Viñetas y marcas de lista: Whisper IMITA el formato del texto que se le pasa
como contexto de vocabulario. Con un guion escrito en viñetas, empezaba CADA
frase transcrita con «• » — y esa viñeta terminaba impresa en los subtítulos
del video (caso real del creador). Aquí se limpian las dos puntas: el contexto
que se le manda a Whisper y el texto que devuelve.
"""
from __future__ import annotations

import re

BULLET_CHARS = "•·▪◦●○∙‣⁃"

_BULLET_RE = re.compile(rf"^[\s ]*(?:[{BULLET_CHARS}]|\*+)[\s ]*")
_ANY_BULLET_RE = re.compile(rf"[{BULLET_CHARS}]")
_LIST_LINE_RE = re.compile(
    rf"^[\s >]*(?:[{BULLET_CHARS}]|[-*+]|\d{{1,2}}[.)])[\s ]+", re.M)


def strip_bullets(text: str) -> str:
    """Quita la viñeta inicial de un texto (y las que quedaran sueltas
    dentro). Nunca toca guiones ni rayas: en español abren diálogo."""
    if not text:
        return text
    out = _ANY_BULLET_RE.sub("", _BULLET_RE.sub("", text))
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def strip_bullets_segments(segments: list[dict]) -> list[dict]:
    """Quita las viñetas de los segmentos de transcripción Y de cada palabra
    con sus tiempos (de ahí salen los subtítulos). Una palabra que era SOLO la
    viñeta se descarta; el resto conserva intactos sus tiempos."""
    out = []
    for seg in segments or []:
        s = {**seg, "text": strip_bullets(seg.get("text", ""))}
        if seg.get("words") is not None:
            s["words"] = [{**w, "text": strip_bullets(w.get("text", ""))}
                          for w in seg["words"]
                          if strip_bullets(w.get("text", ""))]
        out.append(s)
    return out


def clean_vocab_hint(text: str) -> str:
    """Extracto de guion listo para sesgar el vocabulario de Whisper: SOLO
    palabras. Se le quitan viñetas, numeraciones, encabezados y marcas de
    formato, para que aprenda los nombres propios y NO copie el formato."""
    if not text:
        return ""
    t = _LIST_LINE_RE.sub("", text)
    t = re.sub(r"^[\s ]*#{1,6}[\s ]*", "", t, flags=re.M)
    t = re.sub(rf"[{BULLET_CHARS}]|[*_`>|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()
