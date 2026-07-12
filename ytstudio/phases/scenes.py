"""FASE 4 — Escenas / storyboard: divide el guion en escenas de 10-25 s de
narración, cada una con su prompt de B-roll, tipo (imagen o video IA),
animación y texto en pantalla."""
from __future__ import annotations

import json

from ytstudio.phases.script import load_script
from ytstudio.providers import get_llm

SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "section": {"type": "string"},
                    "narration": {"type": "string"},
                    "broll_prompt": {"type": "string"},
                    "broll_type": {"type": "string", "enum": ["image", "video"]},
                    "animation": {"type": "string",
                                  "enum": ["zoom_in", "zoom_out", "pan_left",
                                           "pan_right", "static"]},
                    "on_screen_text": {"type": "string"},
                },
                "required": ["id", "section", "narration", "broll_prompt",
                             "broll_type", "animation", "on_screen_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenes"],
    "additionalProperties": False,
}


def _split_sentences(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p for p in parts if p]


def _mechanical_scenes(script_md: str, prompt_prefix: str) -> list[dict]:
    """División del guion sin LLM (modo preview): agrupa frases en escenas de
    ~25-55 palabras respetando las secciones '## ' y rota las animaciones.
    Preserva el texto EXACTO del guion del usuario."""
    animations = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    sections: list[tuple[str, list[str]]] = []
    current = ("Narración", [])
    for line in script_md.splitlines():
        if line.startswith("## "):
            if current[1]:
                sections.append(current)
            current = (line[3:].strip() or "Sección", [])
        elif line.strip():
            current[1].append(line.strip())
    if current[1]:
        sections.append(current)

    scenes: list[dict] = []
    for section, lines in sections:
        chunk: list[str] = []
        words = 0
        def flush():
            nonlocal chunk, words
            if chunk:
                scenes.append({
                    "id": len(scenes) + 1,
                    "section": section,
                    "narration": " ".join(chunk),
                    "broll_prompt": f"{prompt_prefix}, {section}".strip(", "),
                    "broll_type": "image",
                    "animation": animations[len(scenes) % len(animations)],
                    "on_screen_text": "",
                })
                chunk, words = [], 0
        for sentence in _split_sentences(" ".join(lines)):
            chunk.append(sentence)
            words += len(sentence.split())
            if words >= 45:
                flush()
        flush()
    return scenes


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    concept = project.get("concept")
    script_md = load_script(project)
    lang = cfg.get("language", "es")
    videogen_scenes = cfg["providers"]["videogen"].get("max_scenes", 0)

    # Sin LLM real (modo preview): dividir el guion real mecánicamente en vez
    # de sustituirlo por escenas de ejemplo.
    if getattr(llm, "is_mock", False):
        scenes = _mechanical_scenes(
            script_md, concept["visual_style"]["prompt_prefix"])
        if scenes:
            _write_outputs(project, scenes)
            return

    system = (
        f"Eres editor y director de fotografía de videos de YouTube en {lang}. "
        "Conviertes guiones en storyboards de escenas listos para producción con IA."
    )
    prompt = (
        "Divide este guion en escenas para el montaje. Reglas:\n"
        "- Cada escena cubre entre 10 y 25 segundos de narración "
        "(aprox. 25-60 palabras). NO cambies ni recortes el texto del guion: "
        "el campo 'narration' debe contener el texto EXACTO, y la concatenación "
        "de todas las escenas debe reconstruir el guion completo.\n"
        "- 'section': encabezado del guion al que pertenece.\n"
        "- 'broll_prompt': prompt EN INGLÉS para generar la imagen/video IA de "
        f"fondo. Escríbelo detallado y SIEMPRE comenzando con este prefijo de "
        f"estilo: \"{concept['visual_style']['prompt_prefix']}\". Sin texto ni "
        "letras dentro de la imagen, sin personas famosas reales.\n"
        f"- 'broll_type': usa 'video' solo en las {videogen_scenes} escenas de "
        "mayor impacto (gancho/clímax); el resto 'image'.\n"
        if videogen_scenes
        else
        "Divide este guion en escenas para el montaje. Reglas:\n"
        "- Cada escena cubre entre 10 y 25 segundos de narración "
        "(aprox. 25-60 palabras). NO cambies ni recortes el texto del guion: "
        "el campo 'narration' debe contener el texto EXACTO, y la concatenación "
        "de todas las escenas debe reconstruir el guion completo.\n"
        "- 'section': encabezado del guion al que pertenece.\n"
        "- 'broll_prompt': prompt EN INGLÉS para generar la imagen IA de fondo. "
        f"Escríbelo detallado y SIEMPRE comenzando con este prefijo de estilo: "
        f"\"{concept['visual_style']['prompt_prefix']}\". Sin texto ni letras "
        "dentro de la imagen, sin personas famosas reales.\n"
        "- 'broll_type': siempre 'image'.\n"
    )
    prompt += (
        "- 'animation': varía entre zoom_in, zoom_out, pan_left, pan_right "
        "(evita repetir la misma dos veces seguidas).\n"
        "- 'on_screen_text': texto breve en pantalla (2-5 palabras) solo cuando "
        "refuerce un dato clave; cadena vacía en el resto.\n\n"
        f"GUION:\n<<<\n{script_md}\n>>>"
    )

    result = llm.complete_json(system, prompt, schema=SCENES_SCHEMA,
                               max_tokens=64000, purpose="scenes")
    scenes = result["scenes"]
    for i, s in enumerate(scenes, start=1):
        s["id"] = i  # ids consecutivos garantizados
    _write_outputs(project, scenes)


def _write_outputs(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Storyboard", ""]
    for s in scenes:
        md += [f"## Escena {s['id']} — {s['section']} ({s['animation']}, {s['broll_type']})",
               f"**Narración:** {s['narration']}",
               f"**B-roll:** {s['broll_prompt']}"]
        if s["on_screen_text"]:
            md.append(f"**Texto en pantalla:** {s['on_screen_text']}")
        md.append("")
    project.path("scenes", "storyboard.md").write_text("\n".join(md), encoding="utf-8")
    project.set("scene_count", len(scenes))


def load_scenes(project) -> list[dict]:
    return json.loads(project.path("scenes", "scenes.json").read_text(encoding="utf-8"))["scenes"]


def save_scenes(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
