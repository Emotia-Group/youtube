"""LOCACIONES del proyecto: lugares con identidad visual CONSISTENTE.

El mismo principio que el elenco (ytstudio/characters.py), aplicado a los
LUGARES de una serie animada: cada locación tiene nombre, descripción y una o
varias imágenes de referencia. Las escenas que ocurren en ella se generan con
el modelo de identidad usando esas imágenes — la cocina de la abuela es LA
MISMA cocina en todos los episodios.

Una locación SIN imágenes recibe una referencia AUTOGENERADA una única vez
(coherente con el estilo del video), que queda guardada en
06_broll/locations/ y se reutiliza siempre.

Estructura en project.json → data.locations (la escribe
ytstudio.series.materialize_episode al crear el episodio):
  [{"id": "lc_x", "name": "La cocina", "description": "...",
    "ambience": "...", "ref_files": ["locations/lc_x_01.jpg"]}]
"""
from __future__ import annotations

from pathlib import Path


def roster(project) -> list[dict]:
    return project.get("locations") or []


def location_images(project, loc: dict) -> list[Path]:
    """Imágenes de referencia de la locación existentes en disco."""
    out = []
    for rel in loc.get("ref_files") or []:
        p = project.path("broll") / rel
        if p.exists():
            out.append(p)
    return out


def ensure_reference(project, cfg, loc: dict) -> Path | None:
    """Referencia visual de la locación: sus imágenes si las tiene; si no, se
    GENERA una única vez y se reutiliza — el lugar mantiene el mismo aspecto
    en todo el video (y en toda la serie, si se sube después a su ficha)."""
    imgs = location_images(project, loc)
    if imgs:
        return imgs[0]
    ref_dir = project.path("broll") / "locations"
    ref_dir.mkdir(exist_ok=True)
    ref = ref_dir / f"{loc['id']}_ref.jpg"
    if ref.exists():
        return ref
    from ytstudio.providers import get_images
    images = get_images(cfg)
    if images is None or \
            getattr(images, "__class__", None).__name__ == "MockImages":
        return None
    concept = project.get("concept") or {}
    prefix = (concept.get("visual_style") or {}).get("prompt_prefix", "")
    desc = (loc.get("description") or loc.get("name") or "place").strip()
    prompt = (f"{prefix}, establishing wide shot of {desc}, "
              "empty scene without people, consistent lighting, "
              "no text").strip(", ")
    images.generate(prompt, ref)
    from ytstudio.progress import notify
    notify(f"📍 Referencia generada para la locación «{loc.get('name')}» "
           "(se reutiliza en todas sus escenas).")
    return ref


def references_for(project, cfg, names: list[str], cap: int = 3) -> list[Path]:
    """Imágenes de referencia de las locaciones nombradas, listas para el
    modelo de identidad."""
    from ytstudio.series import norm_name
    by_name = {norm_name(l.get("name", "")): l for l in roster(project)}
    refs: list[Path] = []
    for n in names or []:
        loc = by_name.get(norm_name(n or ""))
        if not loc:
            continue
        imgs = location_images(project, loc)
        if not imgs:
            r = ensure_reference(project, cfg, loc)
            imgs = [r] if r else []
        for p in imgs:
            if p not in refs:
                refs.append(p)
    return refs[:cap]


def location_brief(project) -> str:
    """Descripción de las locaciones para los prompts del director."""
    lines = []
    for l in roster(project):
        d = (l.get("description") or "").strip()
        n_img = len(l.get("ref_files") or [])
        lines.append(f"- {l.get('name')}" + (f": {d}" if d else "")
                     + (f" ({n_img} imagen(es) de referencia)" if n_img
                        else " (referencia autogenerada)"))
    return "\n".join(lines)
