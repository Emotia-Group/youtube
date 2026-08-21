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
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)  # nombre completo del idioma para el LLM
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

    from ytstudio.catalog import is_vertical, short_template
    vertical = is_vertical(cfg)
    hooks_block = ""
    if vertical:
        # Biblioteca de ganchos probados: al guionista se le entregan ~20
        # plantillas afines al tema para que ABRA el video adaptando la mejor
        # (v0.34.0). Sin biblioteca, el prompt queda como siempre.
        from ytstudio import hooks as hooks_lib
        topic = " ".join(str(x) for x in (
            brief.get("topic", ""), brief.get("summary", ""),
            concept.get("angle", "")))
        hooks_block = hooks_lib.prompt_block(topic, seed=project.slug)
    # Plantilla de formato elegida al crear el proyecto (Top 3, historia con
    # giro, antes/después…): su estructura manda sobre la genérica. Si el
    # creador trajo SU guion, la plantilla solo ordena, no reescribe.
    tpl = short_template(project, cfg)
    if tpl and tpl.get("script_rules"):
        hooks_block += ("\n" + tpl["script_rules"]
                        + ("\n(El creador trajo su guion: respeta su "
                           "contenido y aplícale SOLO la estructura de la "
                           "plantilla.)" if is_script else "") + "\n")
    # EPISODIO DE SERIE ANIMADA: la biblia de la serie (elenco, locaciones,
    # escenas recurrentes) y el formato de diálogo etiquetado mandan.
    from ytstudio.series import series_script_block
    serie_block = series_script_block(project)
    if serie_block:
        hooks_block += "\n" + serie_block + "\n"
    if vertical:
        system = (
            f"Eres guionista senior de videos VERTICALES CORTOS (Shorts/Reels/"
            f"TikTok) en {lang}. Escribes narración hablada de ~{int(minutes * 60)} "
            "segundos: gancho demoledor en la PRIMERA frase (sin saludos ni "
            "introducciones), una sola idea, frases cortísimas, cero relleno, "
            "y un cierre con giro o llamada a la acción de una línea. "
            "SOLO escribes el texto que dirá el narrador — sin acotaciones, "
            "sin marcas de tiempo, sin indicaciones entre corchetes."
        )
    else:
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
            + hooks_block
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
            + hooks_block
        )

    script_md = llm.complete(system, prompt, max_tokens=64000, purpose="script")
    project.path("script", "guion.md").write_text(script_md, encoding="utf-8")
    project.set("script_words", len(script_md.split()))


def load_script(project) -> str:
    """Lee el guion (posiblemente editado a mano por el usuario)."""
    return project.path("script", "guion.md").read_text(encoding="utf-8")
