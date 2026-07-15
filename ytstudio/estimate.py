"""Estimación de costo (USD) y tiempo ANTES de generar un video.

Los precios son aproximados (tarifas públicas de los proveedores, julio 2026)
y se muestran como rangos: el costo real depende del proveedor, la longitud
del guion y los reintentos. La intención es que el creador sepa el orden de
magnitud antes de gastar — no una factura exacta.
"""
from __future__ import annotations

from pathlib import Path

# --- Tarifas aproximadas ----------------------------------------------------

# LLM: USD por millón de tokens (entrada, salida)
LLM_PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
LLM_DEFAULT_PRICE = (5.0, 25.0)

IMG_COST = {"openai": (0.07, 0.25), "replicate": (0.03, 0.06)}   # por imagen
IMG_SECONDS = {"openai": (20, 60), "replicate": (8, 25)}
VIDEO_COST_5S = (0.13, 0.35)      # Kling estándar por clip de 5 s
VIDEO_SECONDS = (180, 420)        # por clip (generación + descarga)
MUSIC_COST = (0.05, 0.15)         # MusicGen por pista
TTS_PER_M_CHARS = (12.0, 30.0)    # OpenAI tts-1 / tts-1-hd por millón de caracteres
STT_PER_MIN = 0.006               # Whisper por minuto de audio
VISION_TOKENS_PER_IMAGE = 1500    # tokens de entrada aproximados por imagen

WORDS_PER_MINUTE = 150            # ritmo de narración
TOKENS_PER_WORD = 1.6             # aproximación para español


def _llm_price(cfg: dict) -> tuple[float, float]:
    model = cfg.get("providers", {}).get("llm", {}).get("model", "")
    return LLM_PRICES.get(model, LLM_DEFAULT_PRICE)


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

    def add(fase, detalle, cost_lo, cost_hi, min_lo, min_hi):
        items.append({"fase": fase, "detalle": detalle,
                      "costo": _fmt_range(cost_lo, cost_hi),
                      "minutos": [round(min_lo, 1), round(min_hi, 1)]})

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
        add("Inteligencia (Claude)",
            f"~{n_calls} llamadas · guion de ~{int(words)} palabras"
            + (f" · visión de {vision_images} imágenes" if vision_images else ""),
            cost_lo * 0.8, cost_lo * 1.8,
            n_calls * 15 / 60, n_calls * 50 / 60)
    else:
        add("Inteligencia (Claude)", "modo vista previa (sin API)", 0, 0, 0, 0.2)

    # --- Voz -----------------------------------------------------------------
    if voice_assets:
        # narración propia → Whisper (transcripción con tiempos)
        audio_min = video_minutes  # aproximación: dura ~ lo que el video
        stt_cost = STT_PER_MIN if stt_name == "openai" else 0.0
        add("Voz (tu narración + Whisper)",
            f"transcripción de ~{audio_min:.0f} min",
            audio_min * stt_cost * 0.8, audio_min * stt_cost * 1.5,
            0.5, 2)
    elif tts_name == "openai":
        chars = video_minutes * WORDS_PER_MINUTE * 6.2
        add("Voz en off (OpenAI TTS)", f"~{int(chars):,} caracteres".replace(",", " "),
            chars * TTS_PER_M_CHARS[0] / 1e6, chars * TTS_PER_M_CHARS[1] / 1e6,
            n_scenes * 3 / 60, n_scenes * 8 / 60)
    elif tts_name == "elevenlabs":
        add("Voz en off (ElevenLabs)", "se descuenta de tu plan", 0, 0,
            n_scenes * 3 / 60, n_scenes * 10 / 60)
        notes.append("ElevenLabs cobra por caracteres según tu suscripción "
                     "(no se estima aquí).")
    else:
        add("Voz en off", f"proveedor '{tts_name}' (sin costo por uso)", 0, 0,
            0.2, 1)

    # --- Imágenes ------------------------------------------------------------
    if n_ai_images and img_name in IMG_COST:
        c = IMG_COST[img_name]
        s = IMG_SECONDS[img_name]
        add(f"Imágenes IA ({img_name})",
            f"{n_ai_images} imágenes (de {n_scenes} escenas, "
            f"{user_broll} con tu material)",
            n_ai_images * c[0], n_ai_images * c[1],
            n_ai_images * s[0] / 60, n_ai_images * s[1] / 60)
        if img_name == "replicate":
            notes.append("Replicate con menos de $5 de crédito limita a 6 "
                         "imágenes/min: el tiempo puede alargarse.")
    elif n_ai_images:
        add("Imágenes", f"{n_ai_images} placeholders (modo vista previa)",
            0, 0, 0.2, 1)

    # --- Video generativo ----------------------------------------------------
    if n_video_scenes:
        long_clips = 1 if scene_secs > 7.5 else 0
        cost_lo = n_video_scenes * VIDEO_COST_5S[0] * (2 if long_clips else 1)
        cost_hi = n_video_scenes * VIDEO_COST_5S[1] * 2
        add("Video IA (Kling vía Replicate)",
            f"{n_video_scenes} clips de {'10' if scene_secs > 7.5 else '5'} s",
            cost_lo, cost_hi,
            n_video_scenes * VIDEO_SECONDS[0] / 60,
            n_video_scenes * VIDEO_SECONDS[1] / 60)

    # --- Música ---------------------------------------------------------------
    if music_name == "library":
        add("Música (tu biblioteca)", "selección con IA incluida arriba",
            0, 0, 0.1, 0.5)
    elif music_name == "replicate":
        add("Música (MusicGen)", "1 pista generada", *MUSIC_COST, 1, 3)
    else:
        add("Música", f"proveedor '{music_name}'", 0, 0, 0.1, 0.5)

    # --- Enlaces de referencia -------------------------------------------------
    if links:
        ref_max = float((cfg.get("reference") or {}).get("max_minutes", 12))
        stt_hi = (len(links) * ref_max * STT_PER_MIN
                  if stt_name == "openai" else 0.0)
        add("Videos de referencia (enlaces)",
            f"{len(links)} enlace(s): descarga + análisis"
            f" (Whisper solo si no hay subtítulos)",
            0, stt_hi, len(links) * 1, len(links) * 5)

    # --- Montaje (local, gratis) ------------------------------------------------
    add("Montaje y subtítulos (tu PC)",
        f"{n_scenes} escenas · {video_minutes:.0f} min de video",
        0, 0, video_minutes * 0.4, video_minutes * 1.2 + 1)

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
    return {"items": items, "total_costo": total_cost,
            "total_minutos": total_min, "notas": notes,
            "escenas": n_scenes, "duracion_min": round(video_minutes, 1)}
