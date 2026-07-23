"""ELENCO del proyecto: personajes con identidad visual CONSISTENTE.

Cada personaje tiene nombre, descripción, una o varias FOTOS de referencia
(assets de categoría 'personaje') y opcionalmente el rol de NARRADOR (el que
hace lipsync). El director etiqueta en qué escenas aparece cada uno, y esas
escenas se generan con un modelo de referencia de identidad (Nano Banana /
Seedream 4 / FLUX Kontext) usando sus fotos — misma cara en todo el video.

Un personaje SIN fotos recibe una referencia AUTOGENERADA una única vez
(retrato coherente con el estilo del video) que se reutiliza en todas sus
escenas: consistencia también para personajes 100% IA.

Estructura en project.json → data.characters:
  [{"id": "ch1", "name": "Alejandro", "description": "...",
    "asset_ids": [3, 4], "narrator": true}]
Compatibilidad v0.28: fotos sueltas de categoría 'personaje' sin registro se
tratan como un único personaje narrador («Personaje 1»).
"""
from __future__ import annotations

from pathlib import Path


def roster(project) -> list[dict]:
    """Elenco del proyecto (con migración transparente desde v0.28)."""
    chars = project.get("characters")
    if chars:
        return chars
    legacy = [a for a in (project.get("assets") or [])
              if a.get("category") == "personaje" and a.get("kind") == "image"]
    if legacy:
        return [{"id": "ch1", "name": "Personaje 1", "description": "",
                 "asset_ids": [a["id"] for a in legacy], "narrator": True}]
    return []


def character_images(project, ch: dict) -> list[Path]:
    """Fotos de referencia SUBIDAS del personaje (existentes en disco)."""
    by_id = {a["id"]: a for a in (project.get("assets") or [])}
    out = []
    for aid in ch.get("asset_ids") or []:
        a = by_id.get(aid)
        if a and a.get("kind") == "image":
            p = project.path("input", a["file"])
            if p.exists():
                out.append(p)
    return out


def narrator(project) -> dict | None:
    """El personaje que narra en cámara (lipsync), si lo hay."""
    for ch in roster(project):
        if ch.get("narrator"):
            return ch
    r = roster(project)
    return r[0] if len(r) == 1 else None


def ensure_reference(project, cfg, ch: dict) -> Path | None:
    """Referencia visual del personaje: sus fotos si las subió; si no, se
    GENERA un retrato una única vez (06_broll/characters/) y se reutiliza —
    así el personaje IA también mantiene la misma cara en todo el video.
    Devuelve None si no hay fotos ni forma de generar."""
    imgs = character_images(project, ch)
    if imgs:
        return imgs[0]
    ref_dir = project.path("broll") / "characters"
    ref_dir.mkdir(exist_ok=True)
    ref = ref_dir / f"{ch['id']}_ref.jpg"
    if ref.exists():
        return ref
    from ytstudio.providers import get_images
    images = get_images(cfg)
    if getattr(images, "__class__", None).__name__ == "MockImages" or \
            images is None:
        return None
    concept = project.get("concept") or {}
    prefix = (concept.get("visual_style") or {}).get("prompt_prefix", "")
    desc = (ch.get("description") or ch.get("name") or "person").strip()
    prompt = (f"{prefix}, character reference portrait of {desc}, "
              "front-facing medium shot, neutral pose, clearly visible face, "
              "plain background, no text").strip(", ")
    images.generate(prompt, ref)
    from ytstudio.progress import notify
    notify(f"🧑 Referencia generada para el personaje «{ch.get('name')}» "
           "(se reutiliza en todas sus escenas).")
    return ref


def references_for(project, cfg, names: list[str], cap: int = 6) -> list[Path]:
    """Fotos de referencia (subidas o autogeneradas) de los personajes
    nombrados en una escena, listas para el modelo de identidad."""
    by_name = {c.get("name", "").strip().lower(): c for c in roster(project)}
    refs: list[Path] = []
    for n in names or []:
        ch = by_name.get((n or "").strip().lower())
        if not ch:
            continue
        imgs = character_images(project, ch)
        if not imgs:
            r = ensure_reference(project, cfg, ch)
            imgs = [r] if r else []
        for p in imgs:
            if p not in refs:
                refs.append(p)
    return refs[:cap]


def cast_brief(project) -> str:
    """Descripción del elenco para los prompts del director (vacío si no hay)."""
    lines = []
    for ch in roster(project):
        d = (ch.get("description") or "").strip()
        n_ph = len(ch.get("asset_ids") or [])
        lines.append(f"- {ch.get('name')}"
                     + (f": {d}" if d else "")
                     + (" [narrador en cámara]" if ch.get("narrator") else "")
                     + (f" ({n_ph} foto(s) de referencia)" if n_ph else
                        " (referencia autogenerada)"))
    return "\n".join(lines)
