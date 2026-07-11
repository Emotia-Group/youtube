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


def run_pipeline(project, cfg, *, from_phase: str | None = None,
                 to_phase: str | None = None) -> None:
    if from_phase:
        project.reset_from(from_phase, PHASE_ORDER)

    for name, module, desc in PHASES:
        if project.phase_status(name) == "done":
            print(f"✔ {name:<10} {desc} (ya completada)")
            if name == to_phase:
                break
            continue

        print(f"▶ {name:<10} {desc}…")
        start = time.time()
        try:
            module.run(project, cfg)
        except Exception as e:
            project.mark_phase(name, "failed", error=str(e))
            raise RuntimeError(f"La fase '{name}' falló: {e}") from e
        project.mark_phase(name, "done", seconds=round(time.time() - start, 1))
        print(f"✔ {name:<10} completada en {time.time() - start:.1f}s")

        if name == to_phase:
            break
