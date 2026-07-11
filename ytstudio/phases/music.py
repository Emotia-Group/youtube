"""FASE 7 — Musicalización: obtiene la pista de fondo (biblioteca local,
MusicGen o mock) con la duración total del video."""
from __future__ import annotations

from ytstudio.providers import get_music


def run(project, cfg) -> None:
    music = get_music(cfg)
    concept = project.get("concept")
    total = project.get("total_duration")
    if not total:
        raise RuntimeError("Ejecuta primero la fase 'voiceover' (define la duración).")

    out = project.path("music", "musica.mp3")
    mood = concept["music_direction"]["mood"]
    music.generate(mood, total + 2.0, out)
    project.set("music_file", out.name)
