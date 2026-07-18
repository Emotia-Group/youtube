"""FASE 5 — Voz en off: usa la narración grabada por el usuario (cortada al
tramo exacto de cada escena) o, si no la hay, sintetiza con TTS. Mide la
duración real de cada clip: es la base de tiempos para montaje y subtítulos."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import cut_segment, probe_duration


def _continuous_grid(scenes: list[dict], audio_total: float, fps: float) -> None:
    """LA CLAVE del audio sin saltos en narración propia.

    Los timestamps de Whisper traen HUECOS entre segmentos (respiraciones,
    pausas): si cada escena durara solo su tramo [start, end], esos huecos se
    descartan de la línea de tiempo → el video queda más corto que la voz, el
    final se trunca y todo se desincroniza (los "saltos").

    Aquí las fronteras se convierten en PUNTOS DE CORTE sobre una línea de
    tiempo CONTINUA: la escena i va desde su inicio hasta el inicio de la
    i+1 (la primera arranca en 0, la última termina en el final real del
    audio). Cada duración se cuantiza a cuadros de video ENTEROS con difusión
    de error, así los cortes caen en cuadros exactos y la suma iguala la
    duración del audio sin deriva acumulada. Resultado: ni un milisegundo de
    narración perdido y sincronía exacta de escenas y subtítulos."""
    user_scenes = [s for s in scenes if "audio_start" in s]
    if not user_scenes:
        return
    starts = [0.0] + [float(s["audio_start"]) for s in user_scenes[1:]]
    t = 0.0
    err = 0.0
    for i, scene in enumerate(user_scenes):
        end = starts[i + 1] if i + 1 < len(user_scenes) else audio_total
        ideal = max(0.25, end - t)
        frames = max(6, round((ideal + err) * fps))
        dur = frames / fps
        err = (t + ideal) - (t + dur)
        scene["audio_start"] = round(t, 4)
        scene["audio_end"] = round(t + dur, 4)
        t += dur


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

    if use_user_voice:
        audio_total = probe_duration(narration_file)
        fps = float(cfg.get("video", {}).get("fps", 24))
        _continuous_grid(scenes, audio_total, fps)
        notify(f"🎙 Narración propia: línea de tiempo continua de "
               f"{audio_total:.1f}s (sin huecos ni recortes).")

    def _is_user_voice(scene: dict) -> bool:
        return "audio_start" in scene and narration_file is not None

    # Generación EN PARALELO (cada clip es independiente); la medición de
    # duraciones y la suma total van después, en orden.
    def _make_vo(scene: dict) -> None:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        if _is_user_voice(scene):
            span = float(scene["audio_end"]) - float(scene["audio_start"])
            if out.exists():
                # Caché obsoleta: si las fronteras cambiaron desde que se cortó
                # este clip (p.ej. proyectos de versiones anteriores), recortar.
                if abs(probe_duration(out) - span) <= 0.2:
                    return
                out.unlink()
            # Tramos CONTIGUOS exactos (lead=0): concatenados reproducen la
            # narración continua tal cual.
            cut_segment(narration_file, scene["audio_start"],
                        scene["audio_end"], out, lead=0.0)
        else:
            if out.exists():  # reanudable
                return
            # Voz sintética (TTS) desde el texto de la escena
            tts.synthesize(scene["narration"], out)

    workers = max(1, int(cfg.get("performance", {}).get("parallel_tts", 4)))
    notify(f"🎙 Generando la voz de las escenas ({workers} en paralelo)…")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(_make_vo, scenes):
            pass  # propaga el primer error (fase reanudable)

    total = 0.0
    for scene in scenes:
        out = vo_dir / f"vo_{scene['id']:03d}.mp3"
        scene["vo_file"] = out.name
        if _is_user_voice(scene):
            # Duración EXACTA del tramo en la rejilla continua (no la del mp3,
            # que añade ~38 ms de padding del codificador). Sin relleno ni
            # pausas añadidas: la grabación ya tiene su ritmo natural y el
            # montaje usa la narración CONTINUA como pista de voz.
            exact = float(scene["audio_end"]) - float(scene["audio_start"])
            scene["vo_duration"] = round(exact, 3)
            scene["duration"] = round(exact, 3)
        else:
            # Voz sintética (TTS): se deja un respiro entre escenas y la pausa
            # dramática (la música sube en él con el ducking).
            scene_pad = padding + float(scene.get("pause_after") or 0.0)
            scene["vo_duration"] = round(probe_duration(out), 3)
            scene["duration"] = round(scene["vo_duration"] + scene_pad, 3)
        total += scene["duration"]

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))
