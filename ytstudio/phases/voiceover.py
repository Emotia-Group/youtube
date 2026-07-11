"""FASE 5 — Voz en off: sintetiza la narración de cada escena con TTS y mide
su duración exacta (base de tiempos para montaje y subtítulos)."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import probe_duration


def run(project, cfg) -> None:
    tts = get_tts(cfg)
    scenes = load_scenes(project)
    vo_dir = project.path("voiceover")
    padding = cfg["video"].get("scene_padding", 0.35)

    total = 0.0
    for scene in scenes:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        if not out.exists():  # reanudable: no re-sintetiza lo ya hecho
            tts.synthesize(scene["narration"], out)
        scene["vo_file"] = out.name
        scene["vo_duration"] = round(probe_duration(out), 3)
        scene["duration"] = round(scene["vo_duration"] + padding, 3)
        total += scene["duration"]

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))
