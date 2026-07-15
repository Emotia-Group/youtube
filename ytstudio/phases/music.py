"""FASE 7 — Musicalización: obtiene la pista de fondo con la duración total
del video.

Con biblioteca local, la pista NO se elige al azar: la IA compara los títulos
y metadatos de las pistas con el concepto del video (mood, género, tema) y
elige la que mejor acompaña. Si ninguna encaja de verdad y hay Replicate
configurado, se GENERA una pista a medida (MusicGen); si no, se usa la más
cercana avisando. La música es opcional: ante cualquier fallo se degrada a un
pad ambiental en vez de detener el proyecto."""
from __future__ import annotations

import os

from ytstudio.providers import get_llm, get_music
from ytstudio.providers.music import LibraryMusic, MockMusic, ReplicateMusic


def _pick_track(llm, tracks: list[dict], concept: dict, topic: str,
                lang: str) -> tuple[str, bool, str]:
    """Devuelve (archivo elegido, encaja_de_verdad, motivo)."""
    md = concept.get("music_direction") or {}
    listing = "\n".join(
        f"- {t['file']}"
        + (f" · título: \"{t['title']}\"" if t.get("title") else "")
        + (f" · artista: {t['artist']}" if t.get("artist") else "")
        + (f" · {t['seconds']}s" if t.get("seconds") else "")
        for t in tracks)
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string",
                     "enum": [t["file"] for t in tracks]},
            "fits": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["file", "fits", "reason"],
        "additionalProperties": False,
    }
    result = llm.complete_json(
        f"Eres supervisor musical de documentales y videos de YouTube en {lang}. "
        "Eliges la música de fondo que mejor sirve a la historia.",
        f"TEMA DEL VIDEO: {topic}\n"
        f"DIRECCIÓN MUSICAL DEL CONCEPTO: {md}\n\n"
        f"PISTAS DISPONIBLES EN LA BIBLIOTECA:\n{listing}\n\n"
        "Elige la pista que mejor acompaña el tono y el tema (file = la mejor "
        "opción SIEMPRE, aunque no sea perfecta). fits = true solo si esa "
        "pista realmente funciona para este video; false si ninguna encaja y "
        "sería mejor generar música a medida. reason: una frase.",
        schema=schema, purpose="music_pick")
    return result["file"], bool(result["fits"]), result.get("reason", "")


def run(project, cfg) -> None:
    music = get_music(cfg)
    concept = project.get("concept")
    total = project.get("total_duration")
    if not total:
        raise RuntimeError("Ejecuta primero la fase 'voiceover' (define la duración).")

    out = project.path("music", "musica.mp3")
    mood = concept["music_direction"]["mood"]
    seconds = total + 2.0

    # Biblioteca local: elegir la pista con criterio de supervisor musical
    if isinstance(music, LibraryMusic):
        llm = get_llm(cfg)
        tracks = music.list_tracks()
        if tracks and not getattr(llm, "is_mock", False):
            try:
                fname, fits, reason = _pick_track(
                    llm, tracks, concept,
                    (project.get("brief") or {}).get("topic", ""),
                    cfg.get("language", "es"))
                chosen = next(t for t in tracks if t["file"] == fname)
                if not fits and os.environ.get("REPLICATE_API_TOKEN"):
                    # Ninguna pista sirve → generar música a medida
                    try:
                        ReplicateMusic(cfg).generate(mood, seconds, out)
                        project.set("music_file", out.name)
                        project.set("music_choice", {
                            "source": "generada", "reason": reason})
                        return
                    except Exception as e:
                        project.add_warning(
                            f"No se pudo generar música a medida ({e}) — se "
                            f"usa la pista más cercana: {fname}")
                elif not fits:
                    project.add_warning(
                        f"Ninguna pista de la biblioteca encaja del todo "
                        f"({reason}) — se usa la más cercana: {fname}. "
                        "Configura Replicate para generar música a medida.")
                music.generate_track(chosen["path"], seconds, out)
                project.set("music_file", out.name)
                project.set("music_choice", {
                    "source": "biblioteca", "file": fname, "reason": reason})
                return
            except Exception as e:
                project.add_warning(f"Selección musical con IA no disponible "
                                    f"(pista por mood/aleatoria): {e}")

    try:
        music.generate(mood, seconds, out)
    except Exception as e:
        if isinstance(music, MockMusic):
            raise  # el pad sintético no debería fallar; si lo hace, es real
        MockMusic(cfg).generate(mood, seconds, out)
        project.add_warning(
            f"Música IA no disponible — se usó música ambiental sencilla. {e}")
    project.set("music_file", out.name)
