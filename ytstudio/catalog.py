"""Catálogo de integraciones y estilos.

Fuente única de verdad sobre qué proveedores/modelos soporta el sistema en
cada categoría (LLM, voz, transcripción, imágenes, video generativo, música),
qué clave de API necesita cada uno y qué opciones expone. La interfaz web y
el módulo de configuración se construyen a partir de este catálogo.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Proveedores por categoría
# ---------------------------------------------------------------------------
# Cada entrada: name (valor en config.yaml), label, env (clave requerida o
# None si es gratuito/local), models/voices (opciones), notes (guía de uso).

CATALOG: dict = {
    "llm": {
        "title": "Inteligencia (concepto, guion, escenas, metadatos)",
        "config_path": ["providers", "llm"],
        "options": [
            {
                "name": "anthropic",
                "label": "Claude (Anthropic)",
                "env": "ANTHROPIC_API_KEY",
                "models": [
                    {"id": "claude-opus-4-8", "label": "Claude Opus 4.8 — máxima calidad narrativa (recomendado)"},
                    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5 — rápido y económico"},
                    {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5 — borradores muy rápidos"},
                ],
                "notes": "Escribe el guion, diseña el concepto, divide en escenas, "
                         "genera metadatos SEO y analiza imágenes/videos de referencia.",
            },
            {"name": "mock", "label": "Mock (sin API, contenido de ejemplo)", "env": None,
             "models": [], "notes": "Para probar el pipeline sin gastar."},
        ],
    },
    "tts": {
        "title": "Voz en off (texto a voz)",
        "config_path": ["providers", "tts"],
        "options": [
            {
                "name": "elevenlabs",
                "label": "ElevenLabs — voces premium multilingües",
                "env": "ELEVENLABS_API_KEY",
                "voices": [
                    {"id": "onwK4e9ZLuTAKqWW03F9", "label": "Daniel — masculina profunda (documental)"},
                    {"id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah — femenina cálida"},
                    {"id": "pNInz6obpgDQGcFmaJgB", "label": "Adam — masculina versátil"},
                    {"id": "XB0fDUnXU5powFXDhCwa", "label": "Charlotte — femenina elegante"},
                ],
                "notes": "La mejor calidad para narración documental en español "
                         "(modelo eleven_multilingual_v2). Pega cualquier voice_id "
                         "de tu biblioteca de ElevenLabs.",
            },
            {
                "name": "openai",
                "label": "OpenAI TTS (gpt-4o-mini-tts)",
                "env": "OPENAI_API_KEY",
                "voices": [
                    {"id": "onyx", "label": "Onyx — masculina grave (documental)"},
                    {"id": "echo", "label": "Echo — masculina clara"},
                    {"id": "nova", "label": "Nova — femenina enérgica"},
                    {"id": "shimmer", "label": "Shimmer — femenina suave"},
                    {"id": "alloy", "label": "Alloy — neutra"},
                    {"id": "fable", "label": "Fable — narrativa expresiva"},
                ],
                "notes": "Buena calidad, muy económico (~$0.20 por video de 10 min).",
            },
            {
                "name": "edge",
                "label": "Edge TTS — gratuito (voces neuronales de Microsoft)",
                "env": None,
                "voices": [
                    {"id": "es-MX-JorgeNeural", "label": "Jorge — masculina (México)"},
                    {"id": "es-MX-DaliaNeural", "label": "Dalia — femenina (México)"},
                    {"id": "es-ES-AlvaroNeural", "label": "Álvaro — masculina (España)"},
                    {"id": "es-ES-ElviraNeural", "label": "Elvira — femenina (España)"},
                    {"id": "es-CO-GonzaloNeural", "label": "Gonzalo — masculina (Colombia)"},
                    {"id": "es-AR-TomasNeural", "label": "Tomás — masculina (Argentina)"},
                    {"id": "es-US-AlonsoNeural", "label": "Alonso — masculina (EE.UU.)"},
                ],
                "notes": "Gratis y sorprendentemente natural. Requiere `pip install edge-tts`.",
            },
            {"name": "mock", "label": "Mock (silencio con duración realista)", "env": None,
             "voices": [], "notes": "Para validar tiempos y montaje sin TTS real."},
        ],
    },
    "stt": {
        "title": "Transcripción (notas de voz / video de referencia)",
        "config_path": ["providers", "stt"],
        "options": [
            {"name": "openai", "label": "Whisper (OpenAI)", "env": "OPENAI_API_KEY",
             "notes": "Transcribe notas de voz y el audio de videos de referencia."},
            {"name": "mock", "label": "Mock", "env": None,
             "notes": "Transcripción de ejemplo."},
        ],
    },
    "images": {
        "title": "Imágenes IA (B-roll y miniatura)",
        "config_path": ["providers", "images"],
        "options": [
            {
                "name": "replicate",
                "label": "Replicate — FLUX y otros",
                "env": "REPLICATE_API_TOKEN",
                "models": [
                    {"id": "black-forest-labs/flux-1.1-pro", "label": "FLUX 1.1 Pro — fotorrealismo cinematográfico (recomendado para cine)"},
                    {"id": "black-forest-labs/flux-dev", "label": "FLUX dev — buena calidad, más barato"},
                    {"id": "black-forest-labs/flux-schnell", "label": "FLUX schnell — muy rápido y barato"},
                    {"id": "recraft-ai/recraft-v3", "label": "Recraft v3 — ilustración y diseño"},
                    {"id": "stability-ai/stable-diffusion-3.5-large", "label": "SD 3.5 Large — estilo alternativo"},
                ],
                "notes": "FLUX 1.1 Pro es la referencia para look cinematográfico/documental.",
            },
            {
                "name": "openai",
                "label": "OpenAI gpt-image-1",
                "env": "OPENAI_API_KEY",
                "models": [{"id": "gpt-image-1", "label": "gpt-image-1"}],
                "notes": "Excelente seguimiento del prompt; look menos fotográfico que FLUX.",
            },
            {"name": "mock", "label": "Mock (tarjetas placeholder)", "env": None,
             "models": [], "notes": "Degradados con el texto del prompt, para previews."},
        ],
    },
    "videogen": {
        "title": "Video generativo por escena (opcional)",
        "config_path": ["providers", "videogen"],
        "options": [
            {
                "name": "replicate",
                "label": "Replicate — Kling / Wan / Hailuo / LTX",
                "env": "REPLICATE_API_TOKEN",
                "models": [
                    {"id": "kwaivgi/kling-v2.1", "label": "Kling v2.1 — el look más cinematográfico (imagen→video)"},
                    {"id": "kwaivgi/kling-v1.6-standard", "label": "Kling v1.6 standard — buen balance costo/calidad"},
                    {"id": "wan-video/wan-2.2-i2v-a14b", "label": "Wan 2.2 i2v — movimiento natural, open source"},
                    {"id": "minimax/hailuo-02", "label": "Hailuo 02 (MiniMax) — física realista"},
                    {"id": "lightricks/ltx-video", "label": "LTX Video — el más rápido y barato"},
                ],
                "notes": "Anima las escenas clave (gancho/clímax) partiendo de la imagen "
                         "de la escena. Costo por clip de 5s: ~$0.10–0.50 según modelo. "
                         "Controla cuántas escenas con max_scenes.",
            },
            {"name": "none", "label": "Ninguno — Ken Burns sobre imágenes (recomendado para videos largos)",
             "env": None, "models": [],
             "notes": "Movimiento de cámara sobre las imágenes; gratis y muy cinematográfico "
                      "si las imágenes son buenas."},
        ],
        "extra_fields": [
            {"key": "max_scenes", "label": "Nº de escenas con video IA", "type": "number",
             "hint": "Solo las N escenas de mayor impacto se generan en video; el resto usa Ken Burns."},
        ],
    },
    "music": {
        "title": "Música de fondo",
        "config_path": ["providers", "music"],
        "options": [
            {
                "name": "replicate",
                "label": "MusicGen (Meta, vía Replicate)",
                "env": "REPLICATE_API_TOKEN",
                "models": [{"id": "meta/musicgen", "label": "MusicGen stereo-large"}],
                "notes": "Genera música original según el mood del concepto (sin copyright).",
            },
            {
                "name": "library",
                "label": "Biblioteca local (assets/music)",
                "env": None,
                "models": [],
                "notes": "Usa tus pistas libres de derechos. Nombra los archivos con el "
                         "mood (ej. cinematic-tension.mp3) para selección automática.",
            },
            {"name": "mock", "label": "Mock (pad sintético)", "env": None,
             "models": [], "notes": "Acorde ambiental generado con ffmpeg."},
        ],
    },
}

# ---------------------------------------------------------------------------
# Presets de estilo cinematográfico
# ---------------------------------------------------------------------------
# Cada preset guía a la fase de concepto (dirección visual/tono/música) y
# ajusta parámetros técnicos del render. El LLM adapta el preset al tema.

STYLE_PRESETS: dict = {
    "documental_cinematografico": {
        "label": "Documental cinematográfico",
        "description": "Estilo BBC/Netflix: fotografía realista de alto rango dinámico, "
                       "luz natural dramática, composición de cine.",
        "fps": 24,
        "visual_direction": (
            "Fotografía documental cinematográfica: aspecto de película, luz natural "
            "dramática, alto rango dinámico, paleta sobria y desaturada con acentos "
            "cálidos, composición con profundidad de campo, texturas reales. "
            "Prefijo sugerido: 'cinematic documentary photography, film still, natural "
            "dramatic lighting, shallow depth of field, muted color grade, 35mm'"),
        "tone": "Narrador documental sobrio y absorbente, ritmo pausado con tensión creciente",
        "music": "orchestral documentary, subtle tension, ambient strings",
    },
    "cine_epico": {
        "label": "Cine épico",
        "description": "Gran escala: paisajes monumentales, contraluces, orquesta épica.",
        "fps": 24,
        "visual_direction": (
            "Cine épico de gran presupuesto: planos amplios monumentales, contraluz y "
            "atmósfera volumétrica, paleta teal & orange, grano de película sutil. "
            "Prefijo sugerido: 'epic cinematic film still, anamorphic, volumetric light, "
            "teal and orange color grade, imax scale'"),
        "tone": "Narración solemne y poderosa, con momentos de silencio dramático",
        "music": "epic orchestral, cinematic percussion, emotional build",
    },
    "misterio_oscuro": {
        "label": "Misterio / true crime",
        "description": "Atmósfera noir: sombras profundas, luz puntual, tensión constante.",
        "fps": 24,
        "visual_direction": (
            "Estética noir de misterio: claroscuro, sombras profundas, fuentes de luz "
            "puntuales, paleta fría con acentos ámbar, niebla y atmósfera. "
            "Prefijo sugerido: 'dark moody cinematic still, chiaroscuro lighting, noir "
            "atmosphere, cold color grade, fog'"),
        "tone": "Narrador de suspenso, pausado, con preguntas que generan intriga",
        "music": "dark ambient tension, pulsing suspense, minimal piano",
    },
    "historia_vintage": {
        "label": "Histórico / vintage",
        "description": "Look de archivo: tonos sepia, grano, texturas de época.",
        "fps": 24,
        "visual_direction": (
            "Estética histórica: tonos sepia y dorados, grano de película visible, "
            "viñeteado sutil, iluminación de época, texturas envejecidas. "
            "Prefijo sugerido: 'vintage historical film still, sepia tones, film grain, "
            "period-accurate, aged photograph aesthetic'"),
        "tone": "Narrador clásico de documental histórico, evocador",
        "music": "nostalgic orchestral, period strings, melancholic piano",
    },
    "moderno_dinamico": {
        "label": "Moderno / divulgación",
        "description": "Estilo divulgación actual: limpio, colorido, ritmo ágil (30 fps).",
        "fps": 30,
        "visual_direction": (
            "Estilo de divulgación moderna: imágenes limpias y vibrantes, iluminación "
            "brillante, composiciones gráficas, colores saturados con intención. "
            "Prefijo sugerido: 'modern editorial photography, clean bright lighting, "
            "vibrant color palette, high detail'"),
        "tone": "Narrador cercano y enérgico, ritmo ágil",
        "music": "upbeat modern electronic, positive energy, driving rhythm",
    },
    "ninguno": {
        "label": "Automático (la IA decide según el tema)",
        "description": "El sistema define libremente el estilo a partir de tu idea.",
        "fps": None,
        "visual_direction": "",
        "tone": "",
        "music": "",
    },
}


def key_status() -> dict:
    """Qué claves de API están definidas en el entorno (para la UI)."""
    keys = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY",
            "REPLICATE_API_TOKEN"]
    return {k: bool(os.environ.get(k)) for k in keys}


def get_style_preset(cfg: dict) -> dict | None:
    """Preset activo según config (style.preset), o None."""
    name = (cfg.get("style") or {}).get("preset") or "ninguno"
    preset = STYLE_PRESETS.get(name)
    if not preset or name == "ninguno":
        return None
    return {"name": name, **preset}
