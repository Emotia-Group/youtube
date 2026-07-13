"""FASE 3 — Guion: narración completa del video, sección por sección.
Si el input ya era un guion listo, se respeta y solo se adapta ligeramente.
El resultado (03_script/guion.md) es editable antes de continuar."""
from __future__ import annotations

from ytstudio.providers import get_llm

WORDS_PER_MINUTE = 150  # ritmo medio de narración en español


def _normalize_sections(text: str) -> str:
    """Garantiza que el guion tenga al menos una sección '## ' (las secciones
    se usan para el storyboard y los capítulos de YouTube)."""
    if any(line.startswith("## ") for line in text.splitlines()):
        return text
    return "## Narración\n" + text


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    brief = project.get("brief")
    concept = project.get("concept")
    lang = cfg.get("language", "es")
    minutes = concept.get("duration_minutes") or cfg["video"].get("target_minutes", 10)
    target_words = minutes * WORDS_PER_MINUTE
    is_script = brief["input_type"] == "script" or brief.get("detected_type") == "script"

    # Narración grabada por el usuario: el guion ES la transcripción exacta del
    # audio (no se reescribe, para que coincida con lo que se oye).
    if project.get("narration"):
        script_md = _normalize_sections(brief["raw_text"].strip())
        project.path("script", "guion.md").write_text(script_md, encoding="utf-8")
        project.set("script_words", len(script_md.split()))
        return

    # El guion del usuario NUNCA se descarta: sin LLM real (modo preview),
    # se usa tal cual en lugar de sustituirlo por contenido de ejemplo.
    if is_script and getattr(llm, "is_mock", False):
        script_md = _normalize_sections(brief["raw_text"].strip())
        project.path("script", "guion.md").write_text(script_md, encoding="utf-8")
        project.set("script_words", len(script_md.split()))
        return

    system = (
        f"Eres guionista senior de videos largos de YouTube en {lang}. Escribes "
        "narración hablada natural (para leerse en voz alta), con frases cortas, "
        "transiciones fluidas y técnicas de retención: gancho inmediato, bucles "
        "abiertos, preguntas retóricas y un cierre con llamada a la acción. "
        "SOLO escribes el texto que dirá el narrador — sin acotaciones de cámara, "
        "sin marcas de tiempo, sin indicaciones entre corchetes."
    )

    if is_script:
        prompt = (
            "El creador ya tiene un guion listo. Respétalo al máximo: solo pulir "
            "fluidez oral, dividirlo en secciones con encabezados '## ' según la "
            "estructura del concepto, y asegurar gancho y cierre.\n\n"
            f"GUION ORIGINAL:\n<<<\n{brief['raw_text']}\n>>>\n\n"
            f"Estructura de referencia: {concept['structure']}"
        )
    else:
        prompt = (
            f"Escribe el guion completo del video (~{target_words} palabras, "
            f"~{minutes} minutos de narración).\n\n"
            f"Tema: {brief['topic']}\n"
            f"Brief: {brief['summary']}\n"
            f"Puntos clave: {brief['key_points']}\n"
            f"Ángulo: {concept['angle']}\n"
            f"Tono: {concept['tone']}\n"
            f"Audiencia: {concept['audience']}\n\n"
            f"Estructura obligatoria (una sección '## ' por cada elemento):\n"
            + "\n".join(f"- {s}" for s in concept["structure"])
        )

    script_md = llm.complete(system, prompt, max_tokens=32000, purpose="script")
    project.path("script", "guion.md").write_text(script_md, encoding="utf-8")
    project.set("script_words", len(script_md.split()))


def load_script(project) -> str:
    """Lee el guion (posiblemente editado a mano por el usuario)."""
    return project.path("script", "guion.md").read_text(encoding="utf-8")
