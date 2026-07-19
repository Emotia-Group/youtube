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

    # Registro de eventos persistente (novedades, errores y tiempos): todo lo
    # que aparece en el progreso queda guardado para diagnóstico y para poder
    # compartirlo. El estado de la fase actual acompaña a cada evento.
    from ytstudio import eventlog
    slug = getattr(project, "slug", None)
    cur = {"phase": None}

    # Gasto REAL (tokens/imágenes/voz/video que de verdad se generaron en esta
    # ejecución) — se acumula al histórico del proyecto al terminar, para que
    # el reporte cubra TODO el proyecto aunque se haya generado en varias
    # sesiones (reanudar no cuenta de nuevo lo ya hecho, y aquí tampoco).
    from ytstudio import usage
    usage.reset()

    def emit(level: str, msg: str, **kw) -> None:
        eventlog.log(level, msg, project=slug, phase=cur["phase"], **kw)

    def sink(msg) -> None:
        log(msg)
        emit("info", str(msg))

    # Los avisos de espera por límite de velocidad de Replicate y el canal de
    # progreso general (descargas, análisis…) van al log de la UI y al de
    # eventos.
    from ytstudio.providers import replicate_util
    replicate_util.set_progress(sink)
    from ytstudio import progress
    progress.set_sink(sink)

    if from_phase:
        project.reset_from(from_phase, PHASE_ORDER)

    project.set("warnings", [])  # avisos frescos por ejecución
    emit("info", f"Generación iniciada (desde «{from_phase or 'inicio'}» "
                 f"hasta «{to_phase or 'fin'}»).")
    run_start = time.time()
    seen_warnings = 0

    try:
        for name, module, desc in PHASES:
            cur["phase"] = name
            if project.phase_status(name) == "done":
                log(f"✔ {name:<10} {desc} (ya completada)")
                if name == to_phase:
                    break
                continue

            sink(f"▶ {name:<10} {desc}…")
            start = time.time()
            try:
                module.run(project, cfg)
            except Exception as e:
                secs = round(time.time() - start, 1)
                project.mark_phase(name, "failed", error=str(e))
                emit("error", f"{desc}: {e}", seconds=secs)
                raise RuntimeError(f"La fase '{name}' falló: {e}") from e
            secs = round(time.time() - start, 1)
            project.mark_phase(name, "done", seconds=secs)
            # Avisos nuevos acumulados por esta fase (B-roll sin usar, NSFW, etc.)
            warnings = project.get("warnings") or []
            for w in warnings[seen_warnings:]:
                emit("warn", w)
            seen_warnings = len(warnings)
            emit("info", f"{desc}: completada", seconds=secs)
            log(f"✔ {name:<10} completada en {secs:.1f}s")

            if name == to_phase:
                break
    finally:
        # El gasto YA incurrido se guarda SIEMPRE, incluso si una fase falló a
        # mitad de camino — ese dinero/tiempo se gastó de verdad.
        _persist_usage(project, round(time.time() - run_start, 1))

    cur["phase"] = None
    emit("info", f"Generación finalizada en {time.time() - run_start:.1f}s.")


def _persist_usage(project, elapsed_seconds: float) -> None:
    from ytstudio import usage
    new_items = usage.get_state()
    if new_items:
        project.set("usage_items", (project.get("usage_items") or []) + new_items)
    time_report = project.get("time_report") or {"total_seconds": 0.0}
    time_report["last_run_seconds"] = elapsed_seconds
    time_report["total_seconds"] = round(
        time_report.get("total_seconds", 0.0) + elapsed_seconds, 1)
    project.set("time_report", time_report)
