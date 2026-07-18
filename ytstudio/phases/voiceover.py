"""FASE 5 — Voz en off: usa la narración grabada por el usuario (línea de
tiempo continua con respiros SOLO en sus pausas naturales) o, si no la hay,
sintetiza con TTS. Mide la duración real de cada clip: es la base de tiempos
para montaje y subtítulos."""
from __future__ import annotations

import math

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import cut_segment, probe_duration, run_ffmpeg


def _build_timeline(scenes: list[dict], narration: dict, cfg: dict,
                    narration_file, vo_dir, audio_total: float, fps: float):
    """Construye la línea de tiempo de la voz al estilo documental.

    Principio: la narración del usuario NUNCA se corta a destiempo. La voz es
    continua, y los respiros (espacios en blanco) se insertan ÚNICAMENTE
    dentro de las pausas naturales de la grabación — los huecos entre
    segmentos de Whisper, donde hay silencio real. Ahí es imposible cortar
    una palabra.

    Composición:
    - intro: aire antes de la primera palabra (el video abre, entra la música
      y luego la voz).
    - respiro entre escenas (scene_breath) + pausa dramática (pause_after del
      director creativo) — solo en fronteras con pausa natural; donde la
      frontera cae a mitad de frase, la voz fluye a través del corte visual
      (muy documental) sin insertar nada.
    - outro: cola tras la última palabra — la imagen y la música respiran y
      el fundido final NUNCA toca la voz.

    Cada duración se cuantiza a cuadros ENTEROS con difusión de error, y los
    silencios reabsorben el error acumulado: sincronía exacta de principio a
    fin. El resultado se escribe como narration_timeline.wav (PCM, sin el
    padding que el codificador mp3 mete en cada corte)."""
    audio_cfg = cfg.get("audio", {})
    breath = max(0.0, float(audio_cfg.get("scene_breath", 0.3)))
    intro = max(0.0, float(audio_cfg.get("intro_seconds", 0.8)))
    outro = max(1.0, float(audio_cfg.get("outro_seconds", 3.5)))

    segs = narration.get("segments") or []
    seg_starts = [float(s["start"]) for s in segs]
    seg_ends = [float(s["end"]) for s in segs]

    user_scenes = [s for s in scenes if "audio_start" in s]
    n = len(user_scenes)

    # Fronteras fuente, re-ancladas al inicio de segmento más cercano (repara
    # también los valores cuantizados que dejó la versión anterior)
    bounds = [0.0]
    for s in user_scenes[1:]:
        b = float(s["audio_start"])
        if seg_starts:
            j = min(range(len(seg_starts)), key=lambda k: abs(seg_starts[k] - b))
            if abs(seg_starts[j] - b) <= 0.15:
                b = seg_starts[j]
        b = min(max(b, bounds[-1] + 0.2), max(audio_total - 0.2, 0.2))
        bounds.append(b)
    bounds.append(audio_total)

    def natural_gap(b: float) -> float:
        """Silencio real de la grabación justo antes de la frontera b."""
        near = min((abs(s - b) for s in seg_starts), default=99.0)
        if near > 0.15:
            return 0.0  # frontera a mitad de frase (átomo partido): no tocar
        prev = [e for e in seg_ends if e <= b + 0.02]
        return max(0.0, b - max(prev)) if prev else 0.0

    pause_ideal: list[float] = []
    for i in range(n):
        if i == n - 1:
            pause_ideal.append(outro)
        elif natural_gap(bounds[i + 1]) >= 0.12:
            extra = min(1.6, float(user_scenes[i].get("pause_after") or 0.0))
            pause_ideal.append(breath + extra)
        else:
            pause_ideal.append(0.0)

    # Duraciones a cuadros exactos; los silencios reabsorben el error
    durs: list[float] = []
    sils: list[float] = []
    err = 0.0
    cum_v = 0.0
    sil_sum = 0.0
    for i in range(n):
        span = bounds[i + 1] - bounds[i]
        extra = intro if i == 0 else 0.0
        ideal = span + extra + pause_ideal[i]
        if pause_ideal[i] > 0:
            frames = max(math.ceil((span + extra) * fps) + 2,
                         round((ideal + err) * fps))
        else:
            frames = max(1, round((ideal + err) * fps))
        dur = frames / fps
        err += ideal - dur
        cum_v += dur
        if pause_ideal[i] > 0:
            s_len = max(0.0, cum_v - (bounds[i + 1] + sil_sum + intro))
            sil_sum += s_len
            err = 0.0  # el silencio realinea audio y video con exactitud
        else:
            s_len = 0.0
        durs.append(dur)
        sils.append(s_len)

    for i, s in enumerate(user_scenes):
        s["audio_start"] = round(bounds[i], 4)
        s["audio_end"] = round(bounds[i + 1], 4)
        s["vo_duration"] = round(bounds[i + 1] - bounds[i], 3)
        s["duration"] = round(durs[i], 3)
        s["vo_offset"] = round(intro, 3) if i == 0 else 0.0

    # WAV de la línea de tiempo: trozos LARGOS de la fuente (cortados solo en
    # pausas reales) + silencios insertados
    pieces: list[tuple] = []
    if intro > 0.001:
        pieces.append(("sil", intro))
    cur = bounds[0]
    for i in range(n):
        if sils[i] > 0.001 or i == n - 1:
            pieces.append(("cut", cur, bounds[i + 1]))
            if sils[i] > 0.001:
                pieces.append(("sil", sils[i]))
            cur = bounds[i + 1]
    n_cuts = sum(1 for p in pieces if p[0] == "cut")
    fmt = "aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo"
    graph: list[str] = []
    if n_cuts == 1:
        graph.append(f"[0:a]{fmt}[c0]")
    else:
        outs = "".join(f"[c{k}]" for k in range(n_cuts))
        graph.append(f"[0:a]{fmt},asplit={n_cuts}{outs}")
    labels: list[str] = []
    ci = si = 0
    for p in pieces:
        if p[0] == "cut":
            graph.append(f"[c{ci}]atrim=start={p[1]:.4f}:end={p[2]:.4f},"
                         f"asetpts=PTS-STARTPTS[p{ci}]")
            labels.append(f"[p{ci}]")
            ci += 1
        else:
            graph.append(f"aevalsrc=0:s=44100:d={p[1]:.4f},"
                         f"aformat=sample_fmts=s16:channel_layouts=stereo[s{si}]")
            labels.append(f"[s{si}]")
            si += 1
    graph.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]")
    out = vo_dir / "narration_timeline.wav"
    script = vo_dir / "timeline.filters"
    script.write_text(";\n".join(graph), encoding="utf-8")
    run_ffmpeg(["-i", str(narration_file), "-filter_complex_script",
                str(script), "-map", "[out]", "-c:a", "pcm_s16le", str(out)],
               "línea de tiempo de la voz")
    n_breaths = sum(1 for x in sils[:-1] if x > 0.001)
    return out, n_breaths


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
        timeline, n_breaths = _build_timeline(
            scenes, narration, cfg, narration_file, vo_dir, audio_total, fps)
        project.set("voice_timeline", timeline.name)
        outro = cfg.get("audio", {}).get("outro_seconds", 3.5)
        notify(f"🎙 Narración propia: voz continua de {audio_total:.1f}s con "
               f"{n_breaths} respiros en tus pausas naturales y {outro:.1f}s "
               "de cola final (el fundido nunca toca la voz).")

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
            # duración/vo_duration ya fijadas por _build_timeline (tramo de
            # voz + respiros insertados solo en pausas naturales)
            pass
        else:
            # Voz sintética (TTS): se deja un respiro entre escenas y la pausa
            # dramática (la música sube en él con el ducking).
            scene_pad = padding + float(scene.get("pause_after") or 0.0)
            scene["vo_duration"] = round(probe_duration(out), 3)
            scene["duration"] = round(scene["vo_duration"] + scene_pad, 3)
        total += scene["duration"]

    # Cola de cierre también en TTS: la última imagen y la música respiran y
    # el fundido final no pisa la voz.
    if not use_user_voice and scenes:
        outro = max(1.0, float(cfg.get("audio", {}).get("outro_seconds", 3.5)))
        scenes[-1]["duration"] = round(scenes[-1]["duration"] + outro, 3)
        total += outro

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))
