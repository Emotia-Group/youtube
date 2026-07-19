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
VIDEO_COST_5S = (0.13, 0.35)      # Kling estándar por clip de 5 s
VIDEO_SECONDS = (180, 420)        # por clip (generación + descarga)
MUSIC_COST = (0.05, 0.15)         # MusicGen por pista
TTS_PER_M_CHARS = (12.0, 30.0)    # OpenAI tts-1 / tts-1-hd por millón de caracteres
STT_PER_MIN = 0.006               # Whisper por minuto de audio
VISION_TOKENS_PER_IMAGE = 1500    # tokens de entrada aproximados por imagen

WORDS_PER_MINUTE = 150            # ritmo de narración
TOKENS_PER_WORD = 1.6             # aproximación para español


def llm_price(model: str) -> tuple[float, float]:
    return LLM_PRICES.get(model, LLM_DEFAULT_PRICE)


def img_cost_mid(provider: str) -> float:
    lo, hi = IMG_COST.get(provider, (0.0, 0.0))
    return (lo + hi) / 2


def video_cost_mid(seconds: float) -> float:
    lo, hi = VIDEO_COST_5S
    mult = 2 if seconds > 7.5 else 1
    return (lo + hi) / 2 * mult


def music_cost_mid() -> float:
    lo, hi = MUSIC_COST
    return (lo + hi) / 2


def tts_cost(chars: int) -> float:
    lo, hi = TTS_PER_M_CHARS
    return chars * (lo + hi) / 2 / 1e6


def stt_cost(minutes: float) -> float:
    return minutes * STT_PER_MIN
