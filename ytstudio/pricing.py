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

IMG_COST = {"openai": (0.03, 0.21), "replicate": (0.03, 0.06)}   # por imagen
IMG_SECONDS = {"openai": (20, 60), "replicate": (8, 25)}
# Costo por MODELO concreto (si se conoce, prevalece sobre el del proveedor):
# así la estimación refleja el ahorro real al elegir un modelo económico.
IMG_MODEL_COST = {
    "black-forest-labs/flux-2-pro": (0.055, 0.075),
    "black-forest-labs/flux-2-flash": (0.015, 0.025),
    "black-forest-labs/flux-1.1-pro": (0.04, 0.05),
    "black-forest-labs/flux-dev": (0.024, 0.03),
    "black-forest-labs/flux-schnell": (0.003, 0.004),
    "bytedance/sdxl-lightning-4step": (0.0014, 0.002),
    "google/imagen-4-fast": (0.02, 0.03),           # RETIRADO 17 ago 2026
    "recraft-ai/recraft-v3": (0.04, 0.05),
    "ideogram-ai/ideogram-v3-turbo": (0.03, 0.04),
    "stability-ai/stable-diffusion-3.5-large": (0.06, 0.07),
    "gpt-image-1": (0.07, 0.25),                    # RETIRADO 23 oct 2026
    "gpt-image-2": (0.03, 0.21),
    # modelos de IDENTIDAD (escenas con personajes del elenco)
    "google/nano-banana": (0.035, 0.045),
    "google/nano-banana-pro": (0.13, 0.24),
    "bytedance/seedream-4": (0.03, 0.05),
    "black-forest-labs/flux-kontext-pro": (0.04, 0.05),
}
IMG_MODEL_SECONDS = {
    "black-forest-labs/flux-schnell": (1, 4),
    "black-forest-labs/flux-2-flash": (2, 6),
    "bytedance/sdxl-lightning-4step": (1, 3),
    "google/imagen-4-fast": (3, 8),
    "google/nano-banana-pro": (10, 30),
}

# ESCALADO (upscaling): recuperar resolución de una imagen ya generada. Es la
# pieza que hace viable el MODO HÍBRIDO — generar con un modelo barato y subir
# la resolución después sale mucho más barato que generar con un modelo caro.
UPSCALE_MODEL_COST = {
    "nightmareai/real-esrgan": (0.0015, 0.0030),
    "philz1337x/clarity-upscaler": (0.010, 0.020),
    "recraft-ai/recraft-crisp-upscale": (0.006, 0.010),
}
UPSCALE_DEFAULT_COST = (0.0015, 0.0030)
UPSCALE_MODEL_SECONDS = {
    "nightmareai/real-esrgan": (4, 12),
    "philz1337x/clarity-upscaler": (10, 30),
    "recraft-ai/recraft-crisp-upscale": (4, 10),
}
UPSCALE_DEFAULT_SECONDS = (4, 12)

# MODELOS RETIRADOS por su proveedor: fecha de apagado y sustituto sugerido.
# No basta con quitarlos del catálogo — un config.yaml antiguo puede seguir
# nombrándolos, y el fallo llegaría como un error críptico de la API a mitad de
# la fase de imágenes. Con esto el programa avisa ANTES y propone el relevo.
RETIRED_MODELS = {
    "google/imagen-4-fast": ("17 de agosto de 2026", "google/nano-banana"),
    "google/imagen-4": ("17 de agosto de 2026", "google/nano-banana"),
    "google/imagen-4-ultra": ("17 de agosto de 2026", "google/nano-banana-pro"),
    "gpt-image-1": ("23 de octubre de 2026", "gpt-image-2"),
    "openai/sora-2": ("24 de septiembre de 2026", "google/veo-3.1-fast"),
    "openai/sora-2-pro": ("24 de septiembre de 2026", "google/veo-3.1"),
}


def retirement(model: str) -> tuple[str, str] | None:
    """(fecha de apagado, sustituto) si el modelo está retirado, o None."""
    return RETIRED_MODELS.get(model)
VIDEO_COST_5S = (0.13, 0.35)      # Kling estándar por clip de 5 s
VIDEO_SECONDS = (180, 420)        # por clip (generación + descarga)
# Los modelos nuevos publican su tarifa POR SEGUNDO; aquí se guarda ya
# convertida a clip de 5 s, que es la unidad con la que trabaja el montaje.
VIDEO_MODEL_COST_5S = {
    "kwaivgi/kling-v2.1": (0.25, 0.50),
    "kwaivgi/kling-v1.6-standard": (0.13, 0.35),
    "kwaivgi/kling-v3.0": (0.45, 0.70),          # $0.09-0.14/s
    "wan-video/wan-2.2-i2v-a14b": (0.15, 0.30),
    "minimax/hailuo-02": (0.20, 0.45),
    "bytedance/seedance-1-lite": (0.06, 0.15),
    "lightricks/ltx-video": (0.04, 0.10),
    # VEO 3.1 — el único con AUDIO NATIVO sincronizado dentro del clip
    "google/veo-3.1-lite": (0.25, 0.35),         # $0.05/s, 1080p, sin audio
    "google/veo-3.1-fast": (0.70, 0.85),         # $0.15/s, CON audio
    "google/veo-3.1": (1.90, 2.20),              # $0.40/s, 4K + audio
}
VIDEO_MODEL_SECONDS = {
    "lightricks/ltx-video": (25, 90),
    "bytedance/seedance-1-lite": (60, 180),
    "google/veo-3.1-fast": (90, 240),
    "google/veo-3.1": (150, 360),
}
# Modelos de video que traen su PROPIO audio: el montaje conserva esa pista en
# lugar de sintetizar ambiente para esa escena.
VIDEO_NATIVE_AUDIO = {"google/veo-3.1-fast", "google/veo-3.1"}


def has_native_audio(model: str) -> bool:
    """True si el clip llega con su propia banda de sonido."""
    return model in VIDEO_NATIVE_AUDIO


MUSIC_COST = (0.05, 0.15)         # MusicGen por pista
# Música por proveedor y pista. ElevenLabs Music cuesta más que MusicGen pero
# viene con LICENCIA COMERCIAL cerrada — lo que importa en un canal que
# monetiza. Suno y Udio quedan fuera: no tienen API pública y su licencia
# estaba en litigio a mediados de 2026.
MUSIC_PROVIDER_COST = {
    "replicate": (0.05, 0.15),
    "elevenlabs": (0.08, 0.20),
    "library": (0.0, 0.0),
    "mock": (0.0, 0.0),
}
# Lipsync (personaje narrador): USD por SEGUNDO de personaje en pantalla —
# es la generación más cara del pipeline; el % de presencia manda el costo.
LIPSYNC_PER_SEC = {
    "bytedance/omni-human": (0.10, 0.16),
    "bytedance/omni-human-1.5": (0.13, 0.18),
    "hedra/character-3": (0.05, 0.09),
    "zsxkib/sonic": (0.02, 0.05),
    "cjwbw/sadtalker": (0.005, 0.02),
}
LIPSYNC_DEFAULT_PER_SEC = (0.02, 0.06)
# segundos de CÓMPUTO por segundo de clip (para estimar el tiempo)
LIPSYNC_COMPUTE_FACTOR = (2.0, 6.0)

# VOZ: USD por millón de caracteres, POR PROVEEDOR. Antes había un único número
# (el de OpenAI) aplicado a todos, así que elegir un proveedor barato no se
# notaba ni en la estimación ni en el gasto real.
TTS_PER_M_CHARS = (12.0, 30.0)    # OpenAI gpt-4o-mini-tts (compatibilidad)
TTS_PROVIDER_PER_M_CHARS = {
    "openai": (12.0, 30.0),
    "cartesia": (10.0, 12.0),     # Sonic — muy por debajo de ElevenLabs
    "elevenlabs": (0.0, 0.0),     # cobra por plan de suscripción, no por uso
    "edge": (0.0, 0.0),           # gratuito
    "mock": (0.0, 0.0),
}

# TRANSCRIPCIÓN: USD por minuto de audio, POR PROVEEDOR.
STT_PER_MIN = 0.006               # Whisper (compatibilidad)
STT_PROVIDER_PER_MIN = {
    "openai": 0.006,
    "assemblyai": 0.0025,         # tarifa por lotes: 2.4x más barato
    "mock": 0.0,
}
VISION_TOKENS_PER_IMAGE = 1500    # tokens de entrada aproximados por imagen

WORDS_PER_MINUTE = 150            # ritmo de narración
TOKENS_PER_WORD = 1.6             # aproximación para español


def llm_price(model: str) -> tuple[float, float]:
    return LLM_PRICES.get(model, LLM_DEFAULT_PRICE)


# Qué modelo usa DE VERDAD cada proveedor de imágenes. El campo
# providers.images.model del config solo lo respeta Replicate; OpenAI genera
# siempre con gpt-image-1. Sin esta distinción, un config con name=openai que
# conservaba el model de FLUX (caso real del creador) hacía que la estimación
# —y con ella el TOPE DE GASTO— usara el precio de FLUX ($0.04-0.05) para
# imágenes que costaban $0.07-0.25: 83 imágenes estimadas en $3.32-$4.15
# cuando de verdad valían $5.81-$20.75.
#
# OpenAI SÍ admite ya varios modelos de imagen, pero solo los suyos: un
# 'model' heredado de Replicate (FLUX) se ignora y se cae al de la casa.
OPENAI_IMAGE_MODELS = ("gpt-image-2", "gpt-image-1")
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
_DEFAULT_IMAGE_MODEL = {"replicate": "black-forest-labs/flux-1.1-pro",
                        "openai": DEFAULT_OPENAI_IMAGE_MODEL}


def effective_image_model(provider: str, configured: str = "") -> str:
    """El modelo de imágenes que realmente se usará con ese proveedor."""
    if provider == "openai":
        return (configured if configured in OPENAI_IMAGE_MODELS
                else DEFAULT_OPENAI_IMAGE_MODEL)
    return configured or _DEFAULT_IMAGE_MODEL.get(provider, "")


def img_cost_range(provider: str, model: str = "") -> tuple[float, float]:
    """Rango de costo por imagen: por MODELO si se conoce; si no, por proveedor.
    El modelo se normaliza al que el proveedor usa de verdad, para que un
    'model' heredado de otro proveedor no falsee el precio."""
    model = effective_image_model(provider, model)
    return IMG_MODEL_COST.get(model) or IMG_COST.get(provider, (0.0, 0.0))


def img_seconds_range(provider: str, model: str = "") -> tuple[float, float]:
    model = effective_image_model(provider, model)
    return IMG_MODEL_SECONDS.get(model) or IMG_SECONDS.get(provider, (8, 25))


def img_cost_mid(provider: str, model: str = "") -> float:
    lo, hi = img_cost_range(provider, model)
    return (lo + hi) / 2


def video_cost_range(model: str = "") -> tuple[float, float]:
    return VIDEO_MODEL_COST_5S.get(model, VIDEO_COST_5S)


def video_seconds_range(model: str = "") -> tuple[float, float]:
    return VIDEO_MODEL_SECONDS.get(model, VIDEO_SECONDS)


def video_cost_mid(seconds: float, model: str = "") -> float:
    """Costo de UN clip de `seconds` segundos. La tarifa se guarda por clip de
    5 s y aquí se escala en proporción: Kling a 10 s sigue costando el doble
    que a 5 s (como siempre), y los modelos con tarifa por segundo —Veo, que
    genera clips de 4, 6 u 8 s— quedan bien cobrados en vez de saltar de
    golpe al doble en cuanto pasan de 7.5 s."""
    lo, hi = video_cost_range(model)
    return (lo + hi) / 2 * max(1.0, seconds) / 5.0


def upscale_cost_range(model: str = "") -> tuple[float, float]:
    return UPSCALE_MODEL_COST.get(model, UPSCALE_DEFAULT_COST)


def upscale_seconds_range(model: str = "") -> tuple[float, float]:
    return UPSCALE_MODEL_SECONDS.get(model, UPSCALE_DEFAULT_SECONDS)


def upscale_cost_mid(model: str = "") -> float:
    lo, hi = upscale_cost_range(model)
    return (lo + hi) / 2


def music_cost_range(provider: str = "") -> tuple[float, float]:
    return MUSIC_PROVIDER_COST.get(provider, MUSIC_COST)


def music_cost_mid(provider: str = "") -> float:
    lo, hi = music_cost_range(provider)
    return (lo + hi) / 2


def lipsync_cost_range(model: str = "") -> tuple[float, float]:
    return LIPSYNC_PER_SEC.get(model, LIPSYNC_DEFAULT_PER_SEC)


def lipsync_cost_mid(seconds: float, model: str = "") -> float:
    lo, hi = lipsync_cost_range(model)
    return round(seconds * (lo + hi) / 2, 4)


def tts_cost_range(provider: str = "openai") -> tuple[float, float]:
    return TTS_PROVIDER_PER_M_CHARS.get(provider, TTS_PER_M_CHARS)


def tts_cost(chars: int, provider: str = "openai") -> float:
    lo, hi = tts_cost_range(provider)
    return chars * (lo + hi) / 2 / 1e6


def stt_per_min(provider: str = "openai") -> float:
    return STT_PROVIDER_PER_MIN.get(provider, STT_PER_MIN)


def stt_cost(minutes: float, provider: str = "openai") -> float:
    return minutes * stt_per_min(provider)
