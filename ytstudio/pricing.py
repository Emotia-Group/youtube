"""Tarifas aproximadas de cada proveedor (USD, julio 2026).

Única fuente de verdad para dos cosas distintas que deben usar los MISMOS
números para no contradecirse entre sí: la estimación ANTES de generar
(estimate.py, con recuentos previstos) y el reporte de gasto REAL después de
generar (usage.py, con los recuentos que de verdad ocurrieron)."""
from __future__ import annotations

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
# Costo por MODELO concreto (si se conoce, prevalece sobre el del proveedor):
# así la estimación refleja el ahorro real al elegir un modelo económico.
IMG_MODEL_COST = {
    "black-forest-labs/flux-1.1-pro": (0.04, 0.05),
    "black-forest-labs/flux-dev": (0.024, 0.03),
    "black-forest-labs/flux-schnell": (0.003, 0.004),
    "bytedance/sdxl-lightning-4step": (0.0014, 0.002),
    "google/imagen-4-fast": (0.02, 0.03),
    "recraft-ai/recraft-v3": (0.04, 0.05),
    "stability-ai/stable-diffusion-3.5-large": (0.06, 0.07),
    "gpt-image-1": (0.07, 0.25),
}
IMG_MODEL_SECONDS = {
    "black-forest-labs/flux-schnell": (1, 4),
    "bytedance/sdxl-lightning-4step": (1, 3),
    "google/imagen-4-fast": (3, 8),
}
VIDEO_COST_5S = (0.13, 0.35)      # Kling estándar por clip de 5 s
VIDEO_SECONDS = (180, 420)        # por clip (generación + descarga)
VIDEO_MODEL_COST_5S = {
    "kwaivgi/kling-v2.1": (0.25, 0.50),
    "kwaivgi/kling-v1.6-standard": (0.13, 0.35),
    "wan-video/wan-2.2-i2v-a14b": (0.15, 0.30),
    "minimax/hailuo-02": (0.20, 0.45),
    "bytedance/seedance-1-lite": (0.06, 0.15),
    "lightricks/ltx-video": (0.04, 0.10),
}
VIDEO_MODEL_SECONDS = {
    "lightricks/ltx-video": (25, 90),
    "bytedance/seedance-1-lite": (60, 180),
}
MUSIC_COST = (0.05, 0.15)         # MusicGen por pista
# Lipsync (personaje narrador): USD por SEGUNDO de personaje en pantalla —
# es la generación más cara del pipeline; el % de presencia manda el costo.
LIPSYNC_PER_SEC = {
    "bytedance/omni-human": (0.10, 0.16),
    "zsxkib/sonic": (0.02, 0.05),
    "cjwbw/sadtalker": (0.005, 0.02),
}
LIPSYNC_DEFAULT_PER_SEC = (0.02, 0.06)
# segundos de CÓMPUTO por segundo de clip (para estimar el tiempo)
LIPSYNC_COMPUTE_FACTOR = (2.0, 6.0)
TTS_PER_M_CHARS = (12.0, 30.0)    # OpenAI tts-1 / tts-1-hd por millón de caracteres
STT_PER_MIN = 0.006               # Whisper por minuto de audio
VISION_TOKENS_PER_IMAGE = 1500    # tokens de entrada aproximados por imagen

WORDS_PER_MINUTE = 150            # ritmo de narración
TOKENS_PER_WORD = 1.6             # aproximación para español


def llm_price(model: str) -> tuple[float, float]:
    return LLM_PRICES.get(model, LLM_DEFAULT_PRICE)


def img_cost_range(provider: str, model: str = "") -> tuple[float, float]:
    """Rango de costo por imagen: por MODELO si se conoce; si no, por proveedor."""
    return IMG_MODEL_COST.get(model) or IMG_COST.get(provider, (0.0, 0.0))


def img_seconds_range(provider: str, model: str = "") -> tuple[float, float]:
    return IMG_MODEL_SECONDS.get(model) or IMG_SECONDS.get(provider, (8, 25))


def img_cost_mid(provider: str, model: str = "") -> float:
    lo, hi = img_cost_range(provider, model)
    return (lo + hi) / 2


def video_cost_range(model: str = "") -> tuple[float, float]:
    return VIDEO_MODEL_COST_5S.get(model, VIDEO_COST_5S)


def video_seconds_range(model: str = "") -> tuple[float, float]:
    return VIDEO_MODEL_SECONDS.get(model, VIDEO_SECONDS)


def video_cost_mid(seconds: float, model: str = "") -> float:
    lo, hi = video_cost_range(model)
    mult = 2 if seconds > 7.5 else 1
    return (lo + hi) / 2 * mult


def music_cost_mid() -> float:
    lo, hi = MUSIC_COST
    return (lo + hi) / 2


def lipsync_cost_range(model: str = "") -> tuple[float, float]:
    return LIPSYNC_PER_SEC.get(model, LIPSYNC_DEFAULT_PER_SEC)


def lipsync_cost_mid(seconds: float, model: str = "") -> float:
    lo, hi = lipsync_cost_range(model)
    return round(seconds * (lo + hi) / 2, 4)


def tts_cost(chars: int) -> float:
    lo, hi = TTS_PER_M_CHARS
    return chars * (lo + hi) / 2 / 1e6


def stt_cost(minutes: float) -> float:
    return minutes * STT_PER_MIN
