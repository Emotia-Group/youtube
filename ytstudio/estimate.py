"""Estimación de costo (USD) y tiempo ANTES de generar un video.

Los precios son aproximados (tarifas públicas de los proveedores, julio 2026)
y se muestran como rangos: el costo real depende del proveedor, la longitud
del guion y los reintentos. La intención es que el creador sepa el orden de
magnitud antes de gastar — no una factura exacta.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.pricing import (IMG_COST, IMG_SECONDS, MUSIC_COST,
                              STT_PER_MIN, TOKENS_PER_WORD, TTS_PER_M_CHARS,
                              VIDEO_COST_5S, VIDEO_SECONDS,
                              VISION_TOKENS_PER_IMAGE, WORDS_PER_MINUTE,
                              llm_price)


def _llm_price(cfg: dict) -> tuple[float, float]:
    model = cfg.get("providers", {}).get("llm", {}).get("model", "")
    return llm_price(model)


def _fmt_range(lo: float, hi: float) -> list[float]:
    return [round(lo, 2), round(hi, 2)]


_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
            "elevenlabs": "ELEVENLABS_API_KEY"}


def _has_key(name: str) -> bool:
    import os
    env = _KEY_ENV.get(name)
    return bool(os.environ.get(env)) if env else True


def estimate(project, cfg: dict) -> dict:
    prov = cfg.get("providers", {})

    missing_key = False

    def active(name: str) -> str:
        """Nombre del proveedor si tiene clave; 'mock' si falta (el programa
        degradará a vista previa, así que no habría costo)."""
        nonlocal missing_key
        if name in _KEY_ENV and not _has_key(name):
            missing_key = True
            return "mock"
        return name

    llm_name = active(prov.get("llm", {}).get("name", "mock"))
    img_name = active(prov.get("images", {}).get("name", "mock"))
    vid_name = active(prov.get("videogen", {}).get("name", "none"))
    tts_name = active(prov.get("tts", {}).get("name", "mock"))
    stt_name = active(prov.get("stt", {}).get("name", "mock"))
    music_name = active(prov.get("music", {}).get("name", "mock"))
    if vid_name == "mock":
        vid_name = "none"

    target_min = float(cfg.get("video", {}).get("target_minutes", 10))
    scene_secs = float(cfg.get("video", {}).get("scene_seconds", 6))

    # Si el proyecto ya tiene escenas/duración reales, usarlas
    total_dur_min = project.get("total_duration")
    if total_dur_min:
        video_minutes = float(total_dur_min) / 60.0
    else:
        video_minutes = target_min
    n_scenes = project.get("scene_count") or max(1, round(video_minutes * 60 / scene_secs))

    assets = project.get("assets") or []
    user_broll = sum(1 for a in assets
                     if a.get("category") == "broll" and a.get("kind") in ("image", "video"))
    voice_assets = [a for a in assets
                    if a.get("category") == "voz" and a.get("kind") == "audio"]
    links = project.get("links") or []
    n_video_scenes = (int(prov.get("videogen", {}).get("max_scenes", 0) or 0)
                      if vid_name != "none" else 0)
    n_ai_images = max(0, n_scenes - user_broll)

    items: list[dict] = []
    notes: list[str] = []
    # Segundos de cada fase del pipeline (PHASE_ORDER), para poder acotar el
    # tiempo estimado a SOLO las fases que en verdad van a ejecutarse cuando
    # se pide "hasta tal paso" o se reanuda a mitad de camino — antes el
    # panel de progreso mostraba el ETA del VIDEO COMPLETO aunque solo se
    # hubiera pedido, por ejemplo, hasta el guion.
    phase_seconds: dict[str, float] = {}

    def add_phase_seconds(min_lo, min_hi, weights: dict[str, float]) -> None:
        mid_sec = (min_lo + min_hi) / 2 * 60
        for phase, w in weights.items():
            phase_seconds[phase] = phase_seconds.get(phase, 0.0) + mid_sec * w

    def add(fase, detalle, cost_lo, cost_hi, min_lo, min_hi,
            phases: dict[str, float] | None = None):
        # 'fase_key' = la fase del pipeline que de verdad ejecuta (y paga)
        # esta partida: la de mayor peso. Permite saber qué parte del costo
        # sigue PENDIENTE al reanudar, para calcular el tope de presupuesto
        # sobre lo que falta en vez de sobre el video entero.
        fase_key = max(phases, key=phases.get) if phases else ""
        items.append({"fase": fase, "fase_key": fase_key, "detalle": detalle,
                      "costo": _fmt_range(cost_lo, cost_hi),
                      "minutos": [round(min_lo, 1), round(min_hi, 1)]})
        if phases:
            add_phase_seconds(min_lo, min_hi, phases)

    # Reparto aproximado del bloque de Inteligencia (una sola llamada
    # combinada en la estimación) entre las fases que de verdad la consumen.
    _LLM_SPLIT = {"ingest": 0.12, "concept": 0.10, "script": 0.28,
                 "scenes": 0.35, "metadata": 0.15}

    # --- LLM (concepto, guion, escenas, rótulos, metadatos, visión) ---------
    if llm_name != "mock":
        in_lo, out_lo = _llm_price(cfg)
        words = video_minutes * WORDS_PER_MINUTE
        script_tokens = words * TOKENS_PER_WORD
        # llamadas: análisis, concepto, guion, escenas, semántica broll,
        # música, metadatos (+ visión de b-roll y fotogramas de referencia)
        calls_in = (6000                     # análisis + contexto
                    + 8000                   # concepto (brief + preset)
                    + script_tokens * 3      # guion se relee en escenas/metadatos
                    + 4000)
        calls_out = (1500 + 1500 + script_tokens
                     + n_scenes * 230        # escenas con campos creativos
                     + 1200)
        vision_images = 0
        if user_broll:
            vision_images += sum(2 if a.get("kind") == "video" else 1
                                 for a in assets if a.get("category") == "broll")
            calls_out += user_broll * 70
        if links:
            vision_images += 6 * len(links)
        calls_in += vision_images * VISION_TOKENS_PER_IMAGE
        cost_lo = (calls_in * in_lo + calls_out * out_lo) / 1e6
        n_calls = 7 + (1 if user_broll else 0)
        # Rango angosto (±20%): la variación real entre proyectos similares es
        # de reintentos/longitud de guion, no de un orden de magnitud — un
        # rango de 0.8x-1.8x (el anterior) no decía nada útil.
        add("Inteligencia (Claude)",
            f"~{n_calls} llamadas · guion de ~{int(words)} palabras"
            + (f" · visión de {vision_images} imágenes" if vision_images else ""),
            cost_lo * 1.0, cost_lo * 1.2,
            n_calls * 15 / 60, n_calls * 50 / 60, phases=_LLM_SPLIT)
    else:
        add("Inteligencia (Claude)", "modo vista previa (sin API)", 0, 0, 0, 0.2,
            phases=_LLM_SPLIT)

    # --- Voz -----------------------------------------------------------------
    if voice_assets:
        # narración propia → Whisper (transcripción con tiempos)
        audio_min = video_minutes  # aproximación: dura ~ lo que el video
        stt_cost = STT_PER_MIN if stt_name == "openai" else 0.0
        add("Voz (tu narración + Whisper)",
            f"transcripción de ~{audio_min:.0f} min",
            audio_min * stt_cost * 0.8, audio_min * stt_cost * 1.5,
            0.5, 2, phases={"voiceover": 1.0})
    elif tts_name == "openai":
        chars = video_minutes * WORDS_PER_MINUTE * 6.2
        add("Voz en off (OpenAI TTS)", f"~{int(chars):,} caracteres".replace(",", " "),
            chars * TTS_PER_M_CHARS[0] / 1e6, chars * TTS_PER_M_CHARS[1] / 1e6,
            n_scenes * 3 / 60, n_scenes * 8 / 60, phases={"voiceover": 1.0})
    elif tts_name == "elevenlabs":
        add("Voz en off (ElevenLabs)", "se descuenta de tu plan", 0, 0,
            n_scenes * 3 / 60, n_scenes * 10 / 60, phases={"voiceover": 1.0})
        notes.append("ElevenLabs cobra por caracteres según tu suscripción "
                     "(no se estima aquí).")
    else:
        add("Voz en off", f"proveedor '{tts_name}' (sin costo por uso)", 0, 0,
            0.2, 1, phases={"voiceover": 1.0})

    # --- Imágenes ------------------------------------------------------------
    perf = cfg.get("performance", {})
    from ytstudio.pricing import effective_image_model
    # El modelo REAL (OpenAI ignora el 'model' del config y usa gpt-image-1):
    # así el precio, el tiempo y la etiqueta describen lo que va a pasar.
    img_model = effective_image_model(img_name,
                                      prov.get("images", {}).get("model", ""))
    if n_ai_images and img_name in IMG_COST:
        from ytstudio.pricing import img_cost_range, img_seconds_range
        c = img_cost_range(img_name, img_model)
        s = img_seconds_range(img_name, img_model)
        iw = max(1, int(perf.get("parallel_images", 4)))
        if img_name in ("replicate", "openai"):
            iw = min(iw, 2)  # ambos limitan las imágenes por minuto
        model_tag = img_model.split("/")[-1] if img_model else img_name
        add(f"Imágenes IA ({model_tag})",
            f"{n_ai_images} imágenes (de {n_scenes} escenas, "
            f"{user_broll} con tu material) · {iw} en paralelo",
            n_ai_images * c[0], n_ai_images * c[1],
            n_ai_images * s[0] / 60 / iw, n_ai_images * s[1] / 60 / iw,
            phases={"broll": 1.0})
        if img_name == "replicate":
            notes.append("Replicate con menos de $5 de crédito limita a 6 "
                         "imágenes/min: el tiempo puede alargarse.")
    elif n_ai_images:
        add("Imágenes", f"{n_ai_images} placeholders (modo vista previa)",
            0, 0, 0.2, 1, phases={"broll": 1.0})

    # --- Video generativo ----------------------------------------------------
    if n_video_scenes:
        from ytstudio.pricing import video_cost_range, video_seconds_range
        vid_model = prov.get("videogen", {}).get("model", "")
        vc = video_cost_range(vid_model)
        vs = video_seconds_range(vid_model)
        long_clips = 1 if scene_secs > 7.5 else 0
        cost_lo = n_video_scenes * vc[0] * (2 if long_clips else 1)
        cost_hi = n_video_scenes * vc[1] * 2
        vw = max(1, int(perf.get("parallel_video", 2)))
        vid_tag = vid_model.split("/")[-1] if vid_model else "Kling"
        add(f"Video IA ({vid_tag} vía Replicate)",
            f"{n_video_scenes} clips de {'10' if scene_secs > 7.5 else '5'} s "
            f"· {vw} en paralelo",
            cost_lo, cost_hi,
            n_video_scenes * vs[0] / 60 / vw,
            n_video_scenes * vs[1] / 60 / vw, phases={"broll": 1.0})

    # --- Personaje narrador con lipsync ---------------------------------------
    ch = project.get("character") or {}
    has_char = any(a.get("category") == "personaje" for a in assets)
    presence = ch.get("presence")
    presence = 0.3 if (has_char and presence is None) else float(presence or 0)
    if has_char and presence > 0:
        ls_name = active(prov.get("lipsync", {}).get("name", "replicate"))
        ls_model = prov.get("lipsync", {}).get("model", "")
        char_secs = presence * video_minutes * 60
        if ls_name == "replicate":
            from ytstudio.pricing import (LIPSYNC_COMPUTE_FACTOR,
                                          lipsync_cost_range)
            lc = lipsync_cost_range(ls_model)
            vw = max(1, int(perf.get("parallel_video", 2)))
            add(f"Personaje lipsync ({ls_model.split('/')[-1] or 'lipsync'})",
                f"~{char_secs:.0f}s de personaje en pantalla "
                f"({presence * 100:.0f}% del video) · {vw} en paralelo",
                char_secs * lc[0], char_secs * lc[1],
                char_secs * LIPSYNC_COMPUTE_FACTOR[0] / 60 / vw,
                char_secs * LIPSYNC_COMPUTE_FACTOR[1] / 60 / vw,
                phases={"broll": 1.0})
            notes.append("El lipsync se cobra por segundo de personaje en "
                         "pantalla: baja el % de presencia o usa un modelo "
                         "económico para reducirlo.")
        else:
            add("Personaje (imagen fija)",
                "sin clave de lipsync: el personaje aparece sin hablar",
                0, 0, 0, 0.2, phases={"broll": 1.0})

    # --- Música ---------------------------------------------------------------
    if music_name == "library":
        add("Música (tu biblioteca)", "selección con IA incluida arriba",
            0, 0, 0.1, 0.5, phases={"music": 1.0})
    elif music_name == "replicate":
        add("Música (MusicGen)", "1 pista generada", *MUSIC_COST, 1, 3,
            phases={"music": 1.0})
    else:
        add("Música", f"proveedor '{music_name}'", 0, 0, 0.1, 0.5,
            phases={"music": 1.0})

    # --- Enlaces de referencia -------------------------------------------------
    if links:
        ref_max = float((cfg.get("reference") or {}).get("max_minutes", 12))
        stt_hi = (len(links) * ref_max * STT_PER_MIN
                  if stt_name == "openai" else 0.0)
        add("Videos de referencia (enlaces)",
            f"{len(links)} enlace(s): descarga + análisis"
            f" (Whisper solo si no hay subtítulos)",
            0, stt_hi, len(links) * 1, len(links) * 5, phases={"ingest": 1.0})

    # --- Montaje (local, gratis) ------------------------------------------------
    rw = max(1, int(perf.get("parallel_render", 2)))
    render_speed = 1 + (rw - 1) * 0.6  # los ffmpeg en paralelo comparten CPU
    add("Montaje y subtítulos (tu PC)",
        f"{n_scenes} escenas · {video_minutes:.0f} min de video · "
        f"{rw} en paralelo",
        0, 0, video_minutes * 0.3 / render_speed,
        (video_minutes * 0.9 + 1) / render_speed + 0.5,
        phases={"assembly": 0.92, "subtitles": 0.08})

    if missing_key:
        notes.append("Algún proveedor configurado no tiene clave de API "
                     "activa: esa parte correrá en modo vista previa (sin "
                     "costo) hasta que añadas la clave en ⚙ Configuración.")
    total_cost = [round(sum(i["costo"][0] for i in items), 2),
                  round(sum(i["costo"][1] for i in items), 2)]
    total_min = [round(sum(i["minutos"][0] for i in items), 0),
                 round(sum(i["minutos"][1] for i in items), 0)]
    notes.append("Estimación aproximada con tarifas públicas de julio 2026; "
                 "reanudar un proyecto NO repite fases ya completadas (no se "
                 "vuelve a pagar lo ya generado).")
    # Piso de 5s por fase con algo de trabajo real: evita un ETA en 0 mientras
    # la fase sigue corriendo de verdad (metadata/subtitles/publish son casi
    # instantáneas pero no cero).
    for name in ("ingest", "concept", "script", "scenes", "voiceover",
                "broll", "music", "subtitles", "assembly", "metadata"):
        if phase_seconds.get(name, 0.0) > 0.001:
            phase_seconds[name] = max(phase_seconds[name], 5.0)
    return {"items": items, "total_costo": total_cost,
            "total_costo_medio": round((total_cost[0] + total_cost[1]) / 2, 2),
            "total_minutos": total_min,
            "total_min_medio": round((total_min[0] + total_min[1]) / 2, 1),
            "notas": notes, "phase_seconds": phase_seconds,
            "escenas": n_scenes, "duracion_min": round(video_minutes, 1)}
