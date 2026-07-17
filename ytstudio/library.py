"""Biblioteca del creador: CANALES de YouTube y ESTILOS reutilizables.

Un estilo captura lo caro de recrear en cada proyecto: la dirección visual
(descripción, prefijo de prompts, paleta), el tono de narración, la dirección
musical, el ritmo visual y la fórmula narrativa aprendida de las referencias.
Se puede guardar desde un proyecto ya analizado (gratis: reutiliza lo que ya
se pagó) o crear desde cero. Cada canal agrupa sus estilos; al crear un
proyecto se elige canal + estilo y el concepto lo aplica SIN re-analizar
referencias — ahorro directo de tiempo y tokens.

Todo vive en data/ (fuera de git, como projects/): datos del usuario.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from ytstudio.config import ROOT

DATA_DIR = ROOT / "data"
CHANNELS_FILE = DATA_DIR / "channels.json"
STYLES_DIR = DATA_DIR / "styles"

# Campos editables de un estilo (creación desde cero y edición)
STYLE_FIELDS = ("name", "channel_id", "visual_description", "prompt_prefix",
                "palette", "tone", "music_mood", "music_description",
                "scene_seconds", "transition", "formula")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


# --- Canales ----------------------------------------------------------------

def list_channels() -> list[dict]:
    if not CHANNELS_FILE.exists():
        return []
    from ytstudio.project import read_json_tolerant
    return read_json_tolerant(CHANNELS_FILE).get("channels", [])


def _save_channels(channels: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHANNELS_FILE.write_text(
        json.dumps({"channels": channels}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def create_channel(name: str, description: str = "") -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El canal necesita un nombre.")
    channels = list_channels()
    if any(c["name"].lower() == name.lower() for c in channels):
        raise ValueError(f"Ya existe un canal llamado «{name}».")
    channel = {"id": _new_id("ch"), "name": name,
               "description": (description or "").strip(),
               "created_at": _now()}
    channels.append(channel)
    _save_channels(channels)
    return channel


def update_channel(channel_id: str, name: str = None,
                   description: str = None) -> dict:
    channels = list_channels()
    for c in channels:
        if c["id"] == channel_id:
            if name is not None and name.strip():
                c["name"] = name.strip()
            if description is not None:
                c["description"] = description.strip()
            _save_channels(channels)
            return c
    raise ValueError("Canal no encontrado.")


def delete_channel(channel_id: str) -> None:
    channels = [c for c in list_channels() if c["id"] != channel_id]
    _save_channels(channels)
    # Los estilos del canal no se borran: quedan "sin canal"
    for style in list_styles():
        if style.get("channel_id") == channel_id:
            style["channel_id"] = None
            _write_style(style)


# --- Estilos ----------------------------------------------------------------

def _style_dir(style_id: str) -> Path:
    return STYLES_DIR / style_id


def _write_style(style: dict) -> None:
    d = _style_dir(style["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "style.json").write_text(
        json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")


def list_styles() -> list[dict]:
    if not STYLES_DIR.exists():
        return []
    from ytstudio.project import read_json_tolerant
    styles = []
    for f in sorted(STYLES_DIR.glob("*/style.json")):
        try:
            styles.append(read_json_tolerant(f))
        except Exception:
            continue
    return styles


def load_style(style_id: str) -> dict | None:
    f = _style_dir(style_id) / "style.json"
    if not f.exists():
        return None
    from ytstudio.project import read_json_tolerant
    return read_json_tolerant(f)


def delete_style(style_id: str) -> None:
    shutil.rmtree(_style_dir(style_id), ignore_errors=True)


def _clean_palette(value) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[,\s]+", value)
    return [p.strip() for p in (value or []) if p and p.strip()][:6]


def create_style(fields: dict) -> dict:
    """Crea un estilo desde cero (formulario de la UI)."""
    name = (fields.get("name") or "").strip()
    if not name:
        raise ValueError("El estilo necesita un nombre.")
    style = {
        "id": _new_id("st"), "name": name,
        "channel_id": fields.get("channel_id") or None,
        "created_at": _now(), "source_project": None,
        "visual_description": (fields.get("visual_description") or "").strip(),
        "prompt_prefix": (fields.get("prompt_prefix") or "").strip(),
        "palette": _clean_palette(fields.get("palette")),
        "tone": (fields.get("tone") or "").strip(),
        "music_mood": (fields.get("music_mood") or "").strip(),
        "music_description": (fields.get("music_description") or "").strip(),
        "scene_seconds": float(fields["scene_seconds"])
            if fields.get("scene_seconds") else None,
        "transition": fields.get("transition") or None,
        "formula": (fields.get("formula") or "").strip(),
        "frames": [],
    }
    _write_style(style)
    return style


def update_style(style_id: str, fields: dict) -> dict:
    style = load_style(style_id)
    if style is None:
        raise ValueError("Estilo no encontrado.")
    for key in STYLE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "palette":
            style[key] = _clean_palette(value)
        elif key == "scene_seconds":
            style[key] = float(value) if value else None
        elif key == "name":
            if (value or "").strip():
                style[key] = value.strip()
        elif key in ("channel_id", "transition"):
            style[key] = value or None
        else:
            style[key] = (value or "").strip()
    _write_style(style)
    return style


def save_style_from_project(project, name: str,
                            channel_id: str | None = None) -> dict:
    """Captura el estilo YA ANALIZADO de un proyecto (concepto + referencias)
    como plantilla reutilizable — sin volver a pagar el análisis."""
    concept = project.get("concept")
    if not concept:
        raise ValueError("El proyecto aún no tiene concepto: genera al menos "
                         "hasta la fase «Concepto» antes de guardar su estilo.")
    brief = project.get("brief") or {}

    # Ritmo: el del video de referencia si se midió
    scene_seconds = None
    formula_parts: list[str] = []
    for link in brief.get("links", []):
        rhythm = (link or {}).get("rhythm") or {}
        if rhythm.get("avg_shot_seconds") and scene_seconds is None:
            scene_seconds = min(15.0, max(3.5, float(rhythm["avg_shot_seconds"])))
        if link.get("transcript_excerpt"):
            formula_parts.append(
                f"Referencia «{link.get('title', link.get('url', ''))}»: "
                f"{link['transcript_excerpt'][:400]}")
    if brief.get("summary"):
        formula_parts.insert(0, brief["summary"])
    if concept.get("structure"):
        formula_parts.append("Estructura que funciona: "
                             + " → ".join(concept["structure"][:8]))

    vs = concept.get("visual_style", {})
    md = concept.get("music_direction", {})
    style = {
        "id": _new_id("st"), "name": (name or "").strip() or project.slug,
        "channel_id": channel_id or None,
        "created_at": _now(), "source_project": project.slug,
        "visual_description": vs.get("description", ""),
        "prompt_prefix": vs.get("prompt_prefix", ""),
        "palette": _clean_palette(vs.get("palette")),
        "tone": concept.get("tone", ""),
        "music_mood": md.get("mood", ""),
        "music_description": md.get("description", ""),
        "scene_seconds": scene_seconds,
        "transition": None,
        "formula": "\n".join(formula_parts)[:3000],
        "frames": [],
    }
    # Copiar unos fotogramas de referencia (recuerdo visual del estilo)
    d = _style_dir(style["id"])
    (d / "frames").mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate((brief.get("reference_frames") or [])[:4]):
        src = Path(frame)
        if src.exists():
            dest = d / "frames" / f"frame_{i:02d}{src.suffix}"
            shutil.copy(src, dest)
            style["frames"].append(f"frames/{dest.name}")
    _write_style(style)
    return style


def style_prompt_block(style: dict) -> str:
    """Texto que el concepto inyecta al LLM: el estilo guardado es OBLIGATORIO
    (no se re-inventa), solo se adapta el contenido al tema nuevo."""
    lines = [f"ESTILO GUARDADO DEL CANAL — «{style['name']}» (OBLIGATORIO: "
             "úsalo tal cual; adapta el contenido al tema, no el estilo):"]
    if style.get("visual_description"):
        lines.append(f"- Dirección visual: {style['visual_description']}")
    if style.get("prompt_prefix"):
        lines.append(f"- Prefijo de prompts (EXACTO): {style['prompt_prefix']}")
    if style.get("palette"):
        lines.append(f"- Paleta: {', '.join(style['palette'])}")
    if style.get("tone"):
        lines.append(f"- Tono de narración: {style['tone']}")
    if style.get("music_mood") or style.get("music_description"):
        lines.append(f"- Música: {style.get('music_mood', '')} — "
                     f"{style.get('music_description', '')}")
    if style.get("formula"):
        lines.append(f"- Fórmula narrativa del canal (replícala adaptada al "
                     f"tema):\n{style['formula']}")
    return "\n".join(lines)


def apply_style_to_concept(style: dict, concept: dict) -> dict:
    """Garantiza que el concepto final use EXACTAMENTE el estilo guardado
    (el LLM propone contenido; el estilo no se negocia)."""
    vs = concept.setdefault("visual_style", {})
    if style.get("visual_description"):
        vs["description"] = style["visual_description"]
    if style.get("prompt_prefix"):
        vs["prompt_prefix"] = style["prompt_prefix"]
    if style.get("palette"):
        vs["palette"] = style["palette"]
    if style.get("tone"):
        concept["tone"] = style["tone"]
    md = concept.setdefault("music_direction", {})
    if style.get("music_mood"):
        md["mood"] = style["music_mood"]
    if style.get("music_description"):
        md["description"] = style["music_description"]
    return concept
