"""FASE 5 — Voz en off: usa la narración grabada por el usuario (cortada al
tramo exacto de cada escena) o, si no la hay, sintetiza con TTS. Mide la
duración real de cada clip: es la base de tiempos para montaje y subtítulos."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import cut_segment, probe_duration


def run(project, cfg) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from ytstudio.progress import notify

    scenes = load_scenes(project)
    vo_dir = project.path("voiceover")
    padding = cfg["video"].get("scene_padding", 0.35)
    narration = project.get("narration")
    use_user_voice = bool(narration and any("audio_start" in s for s in scenes))

    needs_tts = any("audio_start" not in s for s in scenes) or not use_user_voice
    tts = get_tts(cfg) if needs_tts else None
    narration_file = (project.path("input", narration["file"])
                      if use_user_voice else None)

    # Generación EN PARALELO (cada clip es independiente); la medición de
    # duraciones y la suma total van después, en orden.
    def _make_vo(scene: dict) -> None:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        if out.exists():  # reanudable
            return
        if "audio_start" in scene and narration_file is not None:
            # Voz REAL del usuario: cortar su tramo del audio limpio
            cut_segment(narration_file, scene["audio_start"],
                        scene["audio_end"], out)
        else:
            # Voz sintética (TTS) desde el texto de la escena
            tts.synthesize(scene["narration"], out)

    todo = [s for s in scenes
            if not (vo_dir / f"vo_{s['id']:03d}.mp3").exists()]
    workers = max(1, int(cfg.get("performance", {}).get("parallel_tts", 4)))
    if todo:
        notify(f"🎙 Generando la voz de {len(todo)} escenas "
               f"({workers} en paralelo)…")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in pool.map(_make_vo, todo):
                pass  # propaga el primer error (fase reanudable)

    total = 0.0
    for scene in scenes:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        # Respiro dramático: el silencio extra queda dentro de la escena; la
        # música sube sola en él (ducking) — recurso cinematográfico.
        scene_pad = padding + float(scene.get("pause_after") or 0.0)
        scene["vo_file"] = out.name
        scene["vo_duration"] = round(probe_duration(out), 3)
        scene["duration"] = round(scene["vo_duration"] + scene_pad, 3)
        total += scene["duration"]

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))
