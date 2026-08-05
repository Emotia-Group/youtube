"""Biblioteca de GANCHOS VIRALES para videos verticales cortos.

Fuente: assets/hooks/hooks_virales.json — 970 plantillas de gancho con su
ejemplo, extraídas del documento «1000 HOOKS VIRALES» del creador. Cada
plantilla tiene huecos ([resultado], [acción], (título)…) que el guionista
adapta al tema del video.

El guion de un corto vive o muere en la primera frase: en vez de pedirle al
modelo «un gancho demoledor» en abstracto, se le entrega una selección de
plantillas PROBADAS afín al tema, para que abra el video adaptando la que
mejor encaje. La selección mezcla afinidad temática (palabras compartidas
con el brief) con variedad aleatoria determinista (mismo proyecto → mismos
candidatos, proyectos distintos → selecciones distintas).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ytstudio.config import ROOT

HOOKS_PATH = ROOT / "assets" / "hooks" / "hooks_virales.json"

_WORD = re.compile(r"[a-záéíóúñü]{4,}")

# Palabras que aparecen en cientos de plantillas y no discriminan tema
_STOP = {"esto", "para", "como", "cómo", "aquí", "este", "esta", "cuando",
         "tienes", "quieres", "puedes", "cosas", "hacer", "video", "sobre",
         "todo", "nunca", "siempre", "después", "antes", "más", "menos"}


@lru_cache(maxsize=1)
def load() -> list[dict]:
    """Todos los ganchos, o lista vacía si la biblioteca no está (el guion
    funciona igual que antes: la biblioteca suma, nunca bloquea)."""
    try:
        data = json.loads(HOOKS_PATH.read_text(encoding="utf-8"))
        return list(data.get("hooks") or [])
    except Exception:
        return []


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower())} - _STOP


def pick_for(topic_text: str, n: int = 20, seed: str = "") -> list[dict]:
    """Selección de `n` ganchos para un tema: la mitad por AFINIDAD (comparten
    vocabulario con el tema — un video de finanzas recibe los de dinero) y la
    otra mitad al azar determinista (variedad: los mejores ganchos suelen ser
    transversales al tema). `seed` fija la mezcla por proyecto."""
    import random
    hooks = load()
    if not hooks:
        return []
    n = min(n, len(hooks))
    topic = _words(topic_text)
    scored = []
    for h in hooks:
        overlap = len(topic & _words(h["plantilla"] + " " + h["ejemplo"]))
        scored.append((overlap, h))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    half = n // 2
    affine = [h for s, h in scored[:half] if s > 0]
    rest = [h for _, h in scored[len(affine):]]
    rng = random.Random(seed or "ytstudio")
    varied = rng.sample(rest, min(n - len(affine), len(rest)))
    return affine + varied


def prompt_block(topic_text: str, seed: str = "", n: int = 20) -> str:
    """Bloque listo para inyectar en el prompt del guionista de cortos.
    Vacío si no hay biblioteca (el prompt queda como siempre)."""
    picked = pick_for(topic_text, n=n, seed=seed)
    if not picked:
        return ""
    lines = [f"- {h['plantilla']}" + (f" (ej.: {h['ejemplo']})"
                                      if h.get("ejemplo") else "")
             for h in picked]
    return (
        "\nGANCHOS VIRALES DE REFERENCIA (plantillas probadas — los huecos "
        "[así] o (así) se rellenan con el tema): elige LA plantilla que mejor "
        "encaje con el tema y ADÁPTALA como PRIMERA FRASE del guion (en el "
        "idioma del video, natural, sin corchetes). No la copies si no encaja: "
        "inspírate en su estructura. Ganchos disponibles:\n"
        + "\n".join(lines) + "\n")
