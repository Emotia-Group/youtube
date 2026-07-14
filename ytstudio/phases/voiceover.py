"""FASE 5 — Voz en off: usa la narración grabada por el usuario (cortada al
tramo exacto de cada escena) o, si no la hay, sintetiza con TTS. Mide la
duración real de cada clip: es la base de tiempos para montaje y subtítulos."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import cut_segment, probe_duration


def run(project, cfg) -> None:
    scenes = load_scenes(project)
    vo_dir = project.path("voiceover")
    padding = cfg["video"].get("scene_padding", 0.35)
    narration = project.get("narration")
    use_user_voice = bool(narration and any("audio_start" in s for s in scenes))

    tts = None if use_user_voice else get_tts(cfg)
    narration_file = (project.path("input", narration["file"])
                      if use_user_voice else None)

    total = 0.0
    for scene in scenes:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        if "audio_start" in scene and narration_file is not None:
            # Voz REAL del usuario: cortar su tramo del audio limpio
            if not out.exists():
                cut_segment(narration_file, scene["audio_start"],
                            scene["audio_end"], out)
        else:
            # Voz sintética (TTS) desde el texto de la escena
            if tts is None:
                tts = get_tts(cfg)
            if not out.exists():
                tts.synthesize(scene["narration"], out)
        # Respiro dramático: el silencio extra queda dentro de la escena; la
        # música sube sola en él (ducking) — recurso cinematográfico.
        scene_pad = padding + float(scene.get("pause_after") or 0.0)
        scene["vo_file"] = out.name
        scene["vo_duration"] = round(probe_duration(out), 3)
        scene["duration"] = round(scene["vo_duration"] + scene_pad, 3)
        total += scene["duration"]

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))
