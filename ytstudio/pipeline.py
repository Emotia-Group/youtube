"""Orquestador: ejecuta las fases en orden, con estado reanudable por fase."""
from __future__ import annotations

import time

from ytstudio.phases import (assembly, broll, concept, ingest, metadata, music,
                             publish, scenes, script, subtitles, voiceover)

PHASES: list[tuple[str, object, str]] = [
    ("ingest", ingest, "Ingesta y análisis del input"),
    ("concept", concept, "Concepto y estilo"),
    ("script", script, "Guion completo"),
    ("scenes", scenes, "Escenas / storyboard"),
    ("voiceover", voiceover, "Voz en off (TTS)"),
    ("broll", broll, "B-roll generado con IA"),
    ("music", music, "Musicalización"),
    ("subtitles", subtitles, "Subtítulos"),
    ("assembly", assembly, "Montaje y edición"),
    ("metadata", metadata, "Metadatos y miniatura"),
    ("publish", publish, "Publicación en YouTube"),
]

PHASE_ORDER = [name for name, _, _ in PHASES]

# Etiquetas cortas y humanas para la interfaz
PHASE_LABELS = {
    "ingest": "Análisis",
    "concept": "Concepto",
    "script": "Guion",
    "scenes": "Escenas",
    "voiceover": "Voz",
    "broll": "Imágenes",
    "music": "Música",
    "subtitles": "Subtítulos",
    "assembly": "Montaje",
    "metadata": "Metadatos",
    "publish": "Publicación",
}


def run_pipeline(project, cfg, *, from_phase: str | None = None,
                 to_phase: str | None = None, log=print) -> None:
    # Verificar ffmpeg desde el inicio (en Windows también lo busca en
    # C:\ffmpeg\bin y lo añade al PATH) — mejor un error claro ahora que
    # un fallo críptico en mitad del pipeline.
    from ytstudio.utils.media import require_ffmpeg
    require_ffmpeg()

    # Los avisos de espera por límite de velocidad de Replicate se muestran en
    # el registro de progreso (no solo en la consola).
    from ytstudio.providers import replicate_util
    replicate_util.set_progress(log)

    if from_phase:
        project.reset_from(from_phase, PHASE_ORDER)

    project.set("warnings", [])  # avisos frescos por ejecución

    for name, module, desc in PHASES:
        if project.phase_status(name) == "done":
            log(f"✔ {name:<10} {desc} (ya completada)")
            if name == to_phase:
                break
            continue

        log(f"▶ {name:<10} {desc}…")
        start = time.time()
        try:
            module.run(project, cfg)
        except Exception as e:
            project.mark_phase(name, "failed", error=str(e))
            raise RuntimeError(f"La fase '{name}' falló: {e}") from e
        project.mark_phase(name, "done", seconds=round(time.time() - start, 1))
        log(f"✔ {name:<10} completada en {time.time() - start:.1f}s")

        if name == to_phase:
            break
