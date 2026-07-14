"""FASE 7 — Musicalización: obtiene la pista de fondo (biblioteca local,
MusicGen o mock) con la duración total del video. La música es opcional: si el
proveedor falla, se degrada a una pista ambiental sencilla en vez de detener
el proyecto."""
from __future__ import annotations

from ytstudio.providers import get_music
from ytstudio.providers.music import MockMusic


def run(project, cfg) -> None:
    music = get_music(cfg)
    concept = project.get("concept")
    total = project.get("total_duration")
    if not total:
        raise RuntimeError("Ejecuta primero la fase 'voiceover' (define la duración).")

    out = project.path("music", "musica.mp3")
    mood = concept["music_direction"]["mood"]
    try:
        music.generate(mood, total + 2.0, out)
    except Exception as e:
        if isinstance(music, MockMusic):
            raise  # el pad sintético no debería fallar; si lo hace, es real
        MockMusic(cfg).generate(mood, total + 2.0, out)
        project.add_warning(
            f"Música IA no disponible — se usó música ambiental sencilla. {e}")
    project.set("music_file", out.name)
