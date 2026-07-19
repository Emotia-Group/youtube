"""FASE 5 — Voz en off: usa la narración grabada por el usuario (línea de
tiempo continua con respiros SOLO en sus pausas naturales) o, si no la hay,
sintetiza con TTS. Mide la duración real de cada clip: es la base de tiempos
para montaje y subtítulos."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_tts
from ytstudio.utils.media import (cut_segment, detect_silences, probe_duration,
                                  run_ffmpeg)


_PACE_FACTOR = {"ligado": 0.0, "normal": 1.0, "amplio": 1.7}


def _pace_factor(pace) -> float:
    return _PACE_FACTOR.get((pace or "normal"), 1.0)


def _ends_sentence(text: str) -> bool:
    return (text or "").rstrip("»\"')”…").endswith((".", "!", "?", "…")) \
        or (text or "").endswith("…")


def _safe_cuts(words: list[dict],
               silences: list[tuple[float, float]]) -> list[dict]:
    """Puntos de corte del hueco entre words[i] y words[i+1]: {i, mid, wide}.

    DOBLE verificación para poder insertar silencio: el punto debe estar entre
    dos palabras reconocidas por Whisper (una completa antes y otra después)
    Y dentro de un silencio MEDIDO en la onda que solape ese hueco (los
    tiempos de Whisper derivan ±0.2-0.4s del audio real: un hueco de Whisper
    sin silencio medido puede caer sobre una palabra de verdad). `wide` es la
    anchura de ese solape verificado; el corte va en su punto medio.

    Los huecos SIN silencio medido se devuelven con wide=0: sirven únicamente
    como coordenada de frontera (agrupar palabras por escena) — JAMÁS para
    insertar silencio en ellos."""
    cuts: list[dict] = []
    for i in range(len(words) - 1):
        g0, g1 = float(words[i]["end"]), float(words[i + 1]["start"])
        if g1 - g0 <= 0.02:
            continue  # palabras pegadas: no hay hueco donde cortar
        # Silencio real (silencedetect) que solape el hueco de Whisper
        best = None
        for s0, s1 in silences:
            lo, hi = max(g0, s0), min(g1, s1)
            if hi - lo > 0 and (best is None or hi - lo > best[1] - best[0]):
                best = (lo, hi)
        if best is not None:
            mid, wide = (best[0] + best[1]) / 2, best[1] - best[0]
        else:
            mid, wide = (g0 + g1) / 2, 0.0  # coordenada sin respaldo medido
        cuts.append({"i": i, "mid": mid, "wide": wide})
    return cuts


def _build_timeline(scenes: list[dict], narration: dict, cfg: dict,
                    narration_file, vo_dir, audio_total: float, fps: float):
    """Construye la línea de tiempo de la voz al estilo documental, con el
    RITMO que decide el director audiovisual.

    Principio inquebrantable: la voz NUNCA se corta a destiempo. Todo silencio
    insertado cae en un hueco ENTRE dos palabras reconocidas (en su punto de
    menor energía), así que es imposible partir una palabra — sin importar la
    imprecisión de los tiempos de Whisper.

    El RITMO no depende de un rango de tiempos fijo, sino del criterio del
    director:
    - Entre escenas/bloques: respiro base (scene_breath) + la pausa dramática
      que el director marcó para esa escena (pause_after).
    - Dentro de la escena: un respiro breve al final de cada frase, escalado
      por el ritmo que el director eligió para la escena (pace: ligado /
      normal / amplio) — así las frases dejan de sonar pegadas sin cortar la
      voz.
    Donde el narrador encadenó dos palabras sin ningún hueco, no se inserta
    nada (no hay dónde hacerlo sin cortar): la voz fluye, muy documental.

    El resultado se escribe como narration_timeline.wav (PCM, sin el padding
    que el codificador mp3 mete en cada corte). Devuelve además el mapa GLOBAL
    de tiempo (intro + inserciones) — única fuente de verdad para sincronizar
    subtítulos y rótulos."""
    from ytstudio.utils.align import flatten_words, video_time_fn

    audio_cfg = cfg.get("audio", {})
    breath = max(0.0, float(audio_cfg.get("scene_breath", 0.3)))
    intro = max(0.0, float(audio_cfg.get("intro_seconds", 0.8)))
    outro = max(1.0, float(audio_cfg.get("outro_seconds", 2.0)))
    sent_breath = max(0.0, float(audio_cfg.get("sentence_breath", 0.18)))

    words = flatten_words(narration.get("segments") or [])
    # Silencios finos (0.08s) solo para elegir el punto MÁS silencioso de cada
    # hueco entre palabras — no para decidir SI se corta (eso lo dan las
    # palabras).
    silences = detect_silences(narration_file, min_d=0.08)
    cuts = _safe_cuts(words, silences)
    cut_by_word = {c["i"]: c for c in cuts}

    user_scenes = [s for s in scenes if "audio_start" in s]
    n = len(user_scenes)

    def nearest_cut(t: float, window: float, low: float,
                    min_wide: float = 0.0):
        best = None
        for c in cuts:
            if c["mid"] <= low + 0.001 or c["wide"] < min_wide:
                continue
            d = abs(c["mid"] - t)
            if d <= window and (best is None or d < best[0]):
                best = (d, c)
        return best[1] if best else None

    # 1) Fronteras de escena. La pausa entre escenas exige un corte RESPALDADO
    #    por silencio medido (wide >= 0.15) cerca de la frontera — un fin de
    #    frase o pausa natural de verdad. Si la frontera cae a mitad de frase
    #    (sin silencio real cerca), NO se inserta pausa: la voz fluye a través
    #    del corte visual, muy documental. (La versión anterior aceptaba
    #    cualquier microhueco entre palabras y metía la pausa a mitad de
    #    frase — el «corte» que se oía en la transición de escenas.)
    bounds = [0.0]
    boundary_pause = [0.0] * n  # pausa DESPUÉS de la escena i
    for i in range(1, n):
        b = float(user_scenes[i]["audio_start"])
        c = nearest_cut(b, window=0.7, low=bounds[-1] + 0.4, min_wide=0.15)
        if c is not None:
            bounds.append(c["mid"])
            pa = min(1.6, float(user_scenes[i - 1].get("pause_after") or 0.0))
            boundary_pause[i - 1] = breath + pa
        else:
            # Sin pausa posible: re-anclar la frontera al hueco entre palabras
            # más cercano (solo coordenada, para agrupar bien las palabras).
            c2 = nearest_cut(b, window=0.45, low=bounds[-1] + 0.4)
            nb = c2["mid"] if c2 is not None else b
            bounds.append(min(max(nb, bounds[-1] + 0.4), audio_total - 0.1))
    bounds.append(audio_total)

    # 2) Inserciones de silencio (punto en el audio original → duración)
    insertions: list[tuple[float, float]] = []
    boundary_pts: set[float] = set()
    for i in range(n - 1):
        if boundary_pause[i] > 0.001:
            insertions.append((bounds[i + 1], boundary_pause[i]))
            boundary_pts.add(round(bounds[i + 1], 4))
    # 2b) Respiros intra-escena al final de cada frase (según el pace del
    #     director), SOLO en cortes respaldados por silencio medido.
    n_sentence_breaths = 0
    for i, s in enumerate(user_scenes):
        pace = _pace_factor(s.get("pace"))
        if pace <= 0 or sent_breath <= 0:
            continue
        a, b = bounds[i], bounds[i + 1]
        for wi, w in enumerate(words[:-1]):
            if not (a <= float(w["start"]) < b) or not _ends_sentence(w["text"]):
                continue
            c = cut_by_word.get(wi)
            if c is None or not (a < c["mid"] < b) or c["wide"] < 0.12:
                continue
            if round(c["mid"], 4) in boundary_pts:
                continue  # ya lleva la pausa de frontera: no duplicar
            insertions.append((c["mid"], sent_breath * pace))
            n_sentence_breaths += 1

    # Fija las fronteras fuente de cada escena (base para agrupar palabras)
    for i, s in enumerate(user_scenes):
        s["audio_start"] = round(bounds[i], 4)
        s["audio_end"] = round(bounds[i + 1], 4)
        s["vo_duration"] = round(bounds[i + 1] - bounds[i], 3)

    # 3) Mapa GLOBAL de tiempo y duraciones de escena (a cuadros enteros)
    V = video_time_fn(intro, insertions)
    boundary_video = [0.0] + [V(bounds[i + 1]) for i in range(n)]
    boundary_video[-1] += outro  # la última escena sostiene la cola de cierre
    vframes = [round(x * fps) for x in boundary_video]
    vframes[0] = 0
    for i in range(1, len(vframes)):
        if vframes[i] <= vframes[i - 1]:
            vframes[i] = vframes[i - 1] + 1
    durs = [(vframes[i + 1] - vframes[i]) / fps for i in range(n)]
    for i, s in enumerate(user_scenes):
        s["duration"] = round(durs[i], 3)
        s["vo_offset"] = round(intro, 3) if i == 0 else 0.0

    # 4) WAV: trozos de la fuente cortados SOLO en los puntos de inserción
    #    (huecos entre palabras) + los silencios insertados. No se descarta ni
    #    un milisegundo de voz: se recorre [0, audio_total] entero.
    ins_pts = sorted(insertions)
    pieces: list[tuple] = []
    if intro > 0.001:
        pieces.append(("sil", intro))
    cur = 0.0
    for p, dur in ins_pts:
        if p - cur > 0.001:
            pieces.append(("cut", cur, p))
            cur = p
        if dur > 0.001:
            pieces.append(("sil", dur))
    if audio_total - cur > 0.001:
        pieces.append(("cut", cur, audio_total))
    if outro > 0.001:
        pieces.append(("sil", outro))

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

    voice_map = {"intro": round(intro, 4), "outro": round(outro, 4),
                 "audio_total": round(audio_total, 4),
                 "insertions": [[round(p, 4), round(d, 4)] for p, d in ins_pts]}
    n_breaths = sum(1 for i in range(n - 1) if boundary_pause[i] > 0.001)

    # AUTOCOMPROBACIÓN: solo se AÑADE silencio, jamás se quita voz.
    check = None
    try:
        got = probe_duration(out)
        want = vframes[-1] / fps
        speech_src = audio_total - sum(
            min(e, audio_total) - max(s, 0.0)
            for s, e in silences if s < audio_total)
        speech_tl = got - sum(e - s for s, e in detect_silences(out))
        # Umbral de voz-hablada holgado (1.2s): silencedetect mide con ruido
        # en los bordes cuando los respiros insertados quedan pegados a
        # silencios reales — la señal DURA es la duración total (0.15s).
        if abs(got - want) > 0.15 or abs(speech_tl - speech_src) > 1.2:
            check = (f"Autocomprobación de la voz: la pista mide {got:.2f}s "
                     f"(esperados {want:.2f}s) con {speech_tl:.2f}s de voz "
                     f"({speech_src:.2f}s en tu grabación). Hay una deriva "
                     "inesperada — reporta este aviso y usa «Rehacer desde "
                     "Voz» tras actualizar.")
    except Exception:
        pass
    return out, n_breaths, n_sentence_breaths, check, voice_map


def run(project, cfg) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from ytstudio import usage as usage_mod
    from ytstudio.progress import notify

    usage_items = usage_mod.get_state()

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
        timeline, n_breaths, n_sent, check, voice_map = _build_timeline(
            scenes, narration, cfg, narration_file, vo_dir, audio_total, fps)
        project.set("voice_timeline", timeline.name)
        project.set("voice_map", voice_map)
        if check:
            project.add_warning(check)
        outro = voice_map["outro"]
        notify(f"🎙 Narración propia: voz continua de {audio_total:.1f}s. El "
               f"director puso {n_breaths} respiros entre escenas y {n_sent} "
               "entre frases, TODOS en huecos entre palabras (imposible cortar "
               f"la voz) + {outro:.1f}s de cola final.")

    def _is_user_voice(scene: dict) -> bool:
        return "audio_start" in scene and narration_file is not None

    # Generación EN PARALELO (cada clip es independiente); la medición de
    # duraciones y la suma total van después, en orden.
    def _make_vo(scene: dict) -> None:
        usage_mod.bind(usage_items)
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

    fps = float(cfg.get("video", {}).get("fps", 24))
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
            # dramática (la música sube en él con el ducking). La duración se
            # cuantiza a CUADROS ENTEROS: el video se renderiza en cuadros, y
            # una duración con fracción de cuadro desalinearía audio y video
            # medio milisegundo por escena (se acumula).
            scene_pad = padding + float(scene.get("pause_after") or 0.0)
            scene["vo_duration"] = round(probe_duration(out), 3)
            frames = max(1, round((scene["vo_duration"] + scene_pad) * fps))
            scene["duration"] = round(frames / fps, 5)
        total += scene["duration"]

    # Cola de cierre también en TTS: la última imagen y la música respiran y
    # el fundido final no pisa la voz.
    if not use_user_voice and scenes:
        outro = max(1.0, float(cfg.get("audio", {}).get("outro_seconds", 2.0)))
        frames = round((scenes[-1]["duration"] + outro) * fps)
        add = round(frames / fps, 5) - scenes[-1]["duration"]
        scenes[-1]["duration"] = round(frames / fps, 5)
        total += add

    if use_user_voice:
        _sync_overlays(scenes, narration.get("segments") or [], voice_map)
    else:
        # UNA SOLA PISTA continua también con voz TTS: cada clip se coloca en
        # el inicio EXACTO de su escena (la misma arquitectura que la
        # narración propia). Las escenas de video van SIN audio — el audio por
        # escena era la causa del desfase en las transiciones.
        timeline = _build_tts_timeline(scenes, vo_dir)
        project.set("voice_timeline", timeline.name)
        project.set("voice_map", None)

    save_scenes(project, scenes)
    project.set("total_duration", round(total, 2))


def _build_tts_timeline(scenes: list[dict], vo_dir):
    """Compila los clips TTS en una única pista continua exacta: cada clip
    arranca en el inicio de su escena y se rellena con silencio hasta la
    escena siguiente (pad→trim a la duración exacta de la escena)."""
    fmt = "aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo"
    args: list[str] = []
    graph: list[str] = []
    labels: list[str] = []
    for k, s in enumerate(scenes):
        args += ["-i", str(vo_dir / s["vo_file"])]
        graph.append(f"[{k}:a]{fmt},apad,atrim=0:{float(s['duration']):.5f},"
                     f"asetpts=PTS-STARTPTS[p{k}]")
        labels.append(f"[p{k}]")
    graph.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]")
    out = vo_dir / "narration_timeline.wav"
    script = vo_dir / "timeline.filters"
    script.write_text(";\n".join(graph), encoding="utf-8")
    run_ffmpeg([*args, "-filter_complex_script", str(script),
                "-map", "[out]", "-c:a", "pcm_s16le", str(out)],
               "línea de tiempo de la voz (TTS)")
    return out


def _sync_overlays(scenes: list[dict], segments: list[dict],
                   voice_map: dict) -> None:
    """Sincroniza cada rótulo con el momento EXACTO en que se pronuncia.

    Usa el mapa GLOBAL de tiempo (intro + inserciones): el instante del video
    de una palabra es video_time(tiempo_original), y overlay_at es ese instante
    menos el arranque de la escena en el video. Así el rótulo aparece cuando lo
    dices aunque haya respiros insertados dentro de la escena.

    Prioridad 1: timestamp REAL de la palabra (Whisper "word"). Prioridad 2
    (proyectos sin timestamps por palabra): interpolar dentro del segmento.
    Prioridad 3: proporción sobre la narración de la escena."""
    import unicodedata

    from ytstudio.utils.align import (assign_words, flatten_words, local_time,
                                      video_time_fn)

    def norm(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                       if unicodedata.category(c) != "Mn")

    V = video_time_fn(voice_map["intro"],
                      [(p, d) for p, d in voice_map["insertions"]])
    # arranque de cada escena en el VIDEO = suma de duraciones anteriores
    starts, acc = [], 0.0
    for s in scenes:
        starts.append(acc)
        acc += float(s.get("duration") or 0.0)

    all_words = flatten_words(segments)
    word_map = assign_words(scenes, all_words)
    seg_norm = [(float(g["start"]), float(g["end"]), norm(g.get("text", "")))
                for g in segments]

    for idx, s in enumerate(scenes):
        s["overlay_at"] = None
        ov = s.get("overlay") or {}
        text = norm(ov.get("text") or "")
        if "audio_start" not in s or not text:
            continue
        a, b = float(s["audio_start"]), float(s["audio_end"])
        key_words = [w for w in text.split() if len(w) >= 3] or text.split()
        hit = None

        # 1) Coincidencia por PALABRA con su tiempo real. La contención por
        #    substring (para variantes con puntuación/plural) exige longitud
        #    mínima en AMBOS lados — si no, palabras cortas como "la" o "el"
        #    caen falsamente dentro de "Gaugamela" o "Alejandro".
        sw = word_map.get(s["id"], [])
        for w in sw:
            wn = norm(w["text"])
            if not wn:
                continue
            if any(wn == kw or (len(wn) >= 4 and len(kw) >= 4
                                and (wn in kw or kw in wn)) for kw in key_words):
                hit = float(w["start"])
                break

        # 2) Respaldo: segmento que contiene el texto, interpolando su
        #    posición dentro de él (proyectos sin timestamps por palabra)
        if hit is None:
            for start, end, txt in seg_norm:
                if not (a - 0.05 <= start <= b + 0.05):
                    continue
                pos = txt.find(text)
                if pos < 0:
                    pos = next((txt.find(w) for w in key_words if txt.find(w) >= 0), -1)
                if pos >= 0:
                    frac = pos / max(1, len(txt))
                    hit = start + (end - start) * frac
                    break

        # 3) Último respaldo: proporción sobre toda la narración de la escena
        if hit is None:
            narr = norm(s.get("narration") or "")
            i2 = next((narr.find(w) for w in key_words if narr.find(w) >= 0), -1)
            if i2 >= 0 and narr:
                hit = a + (b - a) * i2 / len(narr)

        if hit is not None:
            local = V(hit) - starts[idx]  # instante del video, relativo a la escena
            local = max(0.0, min(local, float(s["duration"]) - 0.5))
            s["overlay_at"] = round(local, 3)
