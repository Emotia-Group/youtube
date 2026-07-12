"""FASE 2 — Concepto y estilo: ángulo, audiencia, tono, estructura de
retención, guía visual (para los prompts de B-roll) y dirección musical."""
from __future__ import annotations

import json

from ytstudio.providers import get_llm

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title_options": {"type": "array", "items": {"type": "string"}},
        "angle": {"type": "string"},
        "audience": {"type": "string"},
        "tone": {"type": "string"},
        "structure": {"type": "array", "items": {"type": "string"}},
        "visual_style": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "prompt_prefix": {"type": "string"},
                "palette": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["description", "prompt_prefix", "palette"],
            "additionalProperties": False,
        },
        "music_direction": {
            "type": "object",
            "properties": {
                "mood": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["mood", "description"],
            "additionalProperties": False,
        },
        "duration_minutes": {"type": "integer"},
    },
    "required": ["title_options", "angle", "audience", "tone", "structure",
                 "visual_style", "music_direction", "duration_minutes"],
    "additionalProperties": False,
}


def run(project, cfg) -> None:
    from ytstudio.catalog import get_style_preset

    llm = get_llm(cfg)
    brief = project.get("brief")
    lang = cfg.get("language", "es")
    target = cfg["video"].get("target_minutes", 10)
    preset = get_style_preset(cfg)

    from pathlib import Path
    frames = [Path(f) for f in brief.get("reference_frames", []) if Path(f).exists()]

    system = (
        f"Eres director creativo de un canal de YouTube de videos largos tipo "
        f"faceless/documental. Trabajas en {lang}. Diseñas conceptos con máxima "
        f"retención: gancho en los primeros 30 segundos, bucles abiertos, ritmo "
        f"variable y cierre con llamada a la acción."
    )
    prompt = (
        f"Brief del video:\n{json.dumps(brief, ensure_ascii=False, indent=2)[:8000]}\n\n"
        f"Duración objetivo: ~{target} minutos.\n\n"
        "Diseña el concepto completo del video:\n"
        "- title_options: 3-5 títulos con alto CTR (sin clickbait engañoso)\n"
        "- angle: el ángulo narrativo diferencial\n"
        "- audience: a quién le habla el video\n"
        "- tone: tono de la narración\n"
        "- structure: secciones del video en orden (pensadas para retención)\n"
        "- visual_style: description (estilo visual coherente para todo el video), "
        "prompt_prefix (prefijo EN INGLÉS que se antepondrá a cada prompt de imagen "
        "IA para mantener consistencia de estilo), palette (3-5 colores hex)\n"
        "- music_direction: mood (1-3 palabras en inglés, ej. 'cinematic tense') "
        "y description\n"
        f"- duration_minutes: duración final recomendada (cercana a {target})"
    )
    if preset:
        prompt += (
            f"\n\nEl creador eligió el preset de estilo «{preset['label']}». "
            "Adáptalo al tema del video (no lo copies literal):\n"
            f"- Dirección visual: {preset['visual_direction']}\n"
            f"- Tono de narración: {preset['tone']}\n"
            f"- Dirección musical: {preset['music']}"
        )
    if frames:
        prompt += ("\n\nHay imágenes de referencia adjuntas: el visual_style debe "
                   "ser coherente con ellas.")

    concept = llm.complete_json(system, prompt, schema=CONCEPT_SCHEMA,
                                images=frames or None, purpose="concept")
    project.path("concept", "concept.json").write_text(
        json.dumps(concept, ensure_ascii=False, indent=2))
    project.set("concept", concept)

    # Resumen legible para revisión humana
    md = [f"# Concepto — {project.slug}", "",
          "## Títulos propuestos"]
    md += [f"- {t}" for t in concept["title_options"]]
    md += ["", f"**Ángulo:** {concept['angle']}",
           f"**Audiencia:** {concept['audience']}",
           f"**Tono:** {concept['tone']}", "",
           "## Estructura"]
    md += [f"{i+1}. {s}" for i, s in enumerate(concept["structure"])]
    md += ["", "## Estilo visual", concept["visual_style"]["description"],
           f"Prefijo de prompts: `{concept['visual_style']['prompt_prefix']}`", "",
           "## Música", f"{concept['music_direction']['mood']} — "
           f"{concept['music_direction']['description']}"]
    project.path("concept", "concept.md").write_text("\n".join(md))
