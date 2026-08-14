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
                    {"id": "claude-opus-4-8",
                     "label": "Claude Opus 4.8 — ✚ máxima calidad narrativa y criterio de director · ✖ el más caro (~$5/$25 por MTok) y algo más lento"},
                    {"id": "claude-sonnet-5",
                     "label": "Claude Sonnet 5 — ✚ 40% más barato y más rápido, guiones muy sólidos · ✖ giros narrativos algo menos finos que Opus"},
                    {"id": "claude-haiku-4-5",
                     "label": "Claude Haiku 4.5 — ✚ 5x más barato y rapidísimo, ideal para PRUEBAS y borradores · ✖ guion más plano; revísalo antes de publicar"},
                ],
                "notes": "Escribe el guion, diseña el concepto, divide en escenas, "
                         "genera metadatos SEO y analiza imágenes/videos de referencia. "
                         "Consejo de ahorro: itera la estructura con Haiku/Sonnet y "
                         "genera la versión final con Opus.",
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
                    {"id": "es-MX-JorgeNeural", "label": "Jorge — masculina (Español, México)"},
                    {"id": "es-MX-DaliaNeural", "label": "Dalia — femenina (Español, México)"},
                    {"id": "es-ES-AlvaroNeural", "label": "Álvaro — masculina (Español, España)"},
                    {"id": "es-CO-GonzaloNeural", "label": "Gonzalo — masculina (Español, Colombia)"},
                    {"id": "en-US-GuyNeural", "label": "Guy — masculina (Inglés, EE.UU.)"},
                    {"id": "en-US-JennyNeural", "label": "Jenny — femenina (Inglés, EE.UU.)"},
                    {"id": "zh-CN-YunxiNeural", "label": "Yunxi — masculina (Chino mandarín)"},
                    {"id": "zh-CN-XiaoxiaoNeural", "label": "Xiaoxiao — femenina (Chino mandarín)"},
                    {"id": "hi-IN-MadhurNeural", "label": "Madhur — masculina (Hindi)"},
                    {"id": "hi-IN-SwaraNeural", "label": "Swara — femenina (Hindi)"},
                    {"id": "fr-FR-HenriNeural", "label": "Henri — masculina (Francés)"},
                    {"id": "fr-FR-DeniseNeural", "label": "Denise — femenina (Francés)"},
                    {"id": "ar-SA-HamedNeural", "label": "Hamed — masculina (Árabe)"},
                    {"id": "ar-SA-ZariyahNeural", "label": "Zariyah — femenina (Árabe)"},
                    {"id": "bn-BD-PradeepNeural", "label": "Pradeep — masculina (Bengalí)"},
                    {"id": "bn-BD-NabanitaNeural", "label": "Nabanita — femenina (Bengalí)"},
                    {"id": "pt-BR-AntonioNeural", "label": "Antonio — masculina (Portugués, Brasil)"},
                    {"id": "pt-BR-FranciscaNeural", "label": "Francisca — femenina (Portugués, Brasil)"},
                    {"id": "ru-RU-DmitryNeural", "label": "Dmitry — masculina (Ruso)"},
                    {"id": "ru-RU-SvetlanaNeural", "label": "Svetlana — femenina (Ruso)"},
                    {"id": "de-DE-ConradNeural", "label": "Conrad — masculina (Alemán)"},
                    {"id": "de-DE-KatjaNeural", "label": "Katja — femenina (Alemán)"},
                ],
                "notes": "Gratis y sorprendentemente natural. Requiere `pip install "
                         "edge-tts`. IMPORTANTE: elige una voz DEL IDIOMA del video "
                         "(la voz no traduce; lee el guion en su acento).",
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
                    {"id": "black-forest-labs/flux-1.1-pro",
                     "label": "FLUX 1.1 Pro (~$0.04/img) — ✚ el mejor fotorrealismo cinematográfico · ✖ el más caro y no el más rápido"},
                    {"id": "black-forest-labs/flux-dev",
                     "label": "FLUX dev (~$0.025/img) — ✚ calidad muy cercana al Pro por menos · ✖ algo menos fiable en manos/texto"},
                    {"id": "black-forest-labs/flux-schnell",
                     "label": "FLUX schnell (~$0.003/img) — ✚ 10x más barato y casi instantáneo, ideal para PRUEBAS · ✖ menos detalle fino y microtexturas"},
                    {"id": "bytedance/sdxl-lightning-4step",
                     "label": "SDXL Lightning (~$0.0015/img) — ✚ casi gratis, 1-2s por imagen · ✖ calidad claramente inferior; solo borradores"},
                    {"id": "google/imagen-4-fast",
                     "label": "Imagen 4 Fast (~$0.02/img) — ✚ rápido y muy bueno con TEXTO dentro de la imagen · ✖ look menos 'cine' que FLUX"},
                    {"id": "recraft-ai/recraft-v3",
                     "label": "Recraft v3 (~$0.04/img) — ✚ ilustración/diseño gráfico de primera · ✖ no busca fotorrealismo"},
                    {"id": "stability-ai/stable-diffusion-3.5-large",
                     "label": "SD 3.5 Large (~$0.065/img) — ✚ estética alternativa artística · ✖ más caro que FLUX Pro y menos consistente"},
                ],
                "notes": "FLUX 1.1 Pro es la referencia para el look documental. Estrategia "
                         "de AHORRO: prueba la estructura del video con schnell/Lightning "
                         "(centavos) y regenera solo la versión final con Pro. Replicate "
                         "regala corridas de PRUEBA limitadas en varios modelos "
                         "(colección «try for free») — sirven para probar, no para "
                         "producción continua: al agotarlas pide crédito.",
            },
            {
                "name": "openai",
                "label": "OpenAI gpt-image-1",
                "env": "OPENAI_API_KEY",
                "models": [{"id": "gpt-image-1",
                            "label": "gpt-image-1 (~$0.07-0.25/img) — ✚ el que mejor obedece prompts complejos · ✖ caro, lento y look menos fotográfico"}],
                "notes": "Excelente seguimiento del prompt; look menos fotográfico que FLUX.",
            },
            {"name": "mock", "label": "Mock (tarjetas placeholder)", "env": None,
             "models": [], "notes": "Degradados con el texto del prompt, para previews."},
        ],
        "extra_fields": [
            {"key": "ref_model", "type": "text",
             "label": "Modelo de IDENTIDAD para escenas con personajes del elenco",
             "hint": "Genera guiándose por las fotos de referencia del personaje "
                     "(misma cara en todo el video). Opciones: google/nano-banana "
                     "(~$0.04/img, multi-referencia, recomendado) · "
                     "bytedance/seedream-4 (multi-referencia, gran fidelidad) · "
                     "black-forest-labs/flux-kontext-pro (look FLUX, 1 sola "
                     "referencia). Requiere REPLICATE_API_TOKEN."},
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
                    {"id": "kwaivgi/kling-v2.1",
                     "label": "Kling v2.1 (~$0.25-0.50/clip 5s) — ✚ el look más cinematográfico · ✖ el más caro y tarda 3-6 min/clip"},
                    {"id": "kwaivgi/kling-v1.6-standard",
                     "label": "Kling v1.6 standard (~$0.13-0.35/clip) — ✚ buen balance costo/calidad · ✖ movimiento algo menos fluido que v2.1"},
                    {"id": "wan-video/wan-2.2-i2v-a14b",
                     "label": "Wan 2.2 i2v (~$0.15-0.30/clip) — ✚ movimiento natural, open source · ✖ a veces deriva del encuadre original"},
                    {"id": "minimax/hailuo-02",
                     "label": "Hailuo 02 (~$0.20-0.45/clip) — ✚ física realista (agua, tela, multitudes) · ✖ tiempos de cola variables"},
                    {"id": "bytedance/seedance-1-lite",
                     "label": "Seedance 1 Lite (~$0.06-0.15/clip) — ✚ MUY barato con calidad digna, ideal para probar · ✖ detalle menor en planos amplios"},
                    {"id": "lightricks/ltx-video",
                     "label": "LTX Video (~$0.04-0.10/clip) — ✚ el más rápido (~30s) y el más barato · ✖ calidad visiblemente menor; solo pruebas"},
                ],
                "notes": "Anima las escenas clave (gancho/clímax) partiendo de la imagen "
                         "de la escena. AHORRO: prueba con Seedance Lite/LTX y genera la "
                         "final con Kling; o usa Ken Burns (gratis) — para documental "
                         "largo casi no se nota. Controla cuántas escenas con max_scenes.",
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
    "lipsync": {
        "title": "Personaje narrador con lipsync (imagen + tu voz → habla en cámara)",
        "config_path": ["providers", "lipsync"],
        "options": [
            {
                "name": "replicate",
                "label": "Replicate — lipsync",
                "env": "REPLICATE_API_TOKEN",
                "models": [
                    {"id": "cjwbw/sadtalker",
                     "label": "SadTalker (~$0.005-0.02/seg) — ✚ casi gratis y muy fiable, ideal para ITERAR · ✖ cabeza casi estática, calidad básica"},
                    {"id": "bytedance/omni-human",
                     "label": "OmniHuman (~$0.10-0.16/seg) — ✚ calidad CINE: gestos, cuerpo y emoción, sirve hasta con dibujos · ✖ el más caro y tarda minutos por clip"},
                    {"id": "zsxkib/sonic",
                     "label": "Sonic (~$0.02-0.05/seg) — ✚ buen punto medio de calidad · ✖ modelo de un autor independiente: puede cambiar de nombre o desaparecer en Replicate sin aviso (si falla con «no encontrado», prueba SadTalker u OmniHuman)"},
                ],
                "notes": "Sube la IMAGEN del personaje (categoría 🧑 Personaje) y tu "
                         "voz: el personaje narra en cámara con lipsync y el director "
                         "lo intercala con B-roll según el % de presencia que elijas. "
                         "OJO AL COSTO: se cobra por SEGUNDO de personaje en pantalla "
                         "(un video de 2 min al 30% ≈ 36 s de lipsync). Estrategia: "
                         "itera con SadTalker y genera la versión final con OmniHuman. "
                         "Si un modelo falla con «no encontrado», Replicate puede "
                         "haberlo renombrado/retirado: prueba otro de la lista o "
                         "busca el nombre exacto en replicate.com/collections/lipsync.",
            },
            {"name": "none", "label": "Desactivado", "env": None, "models": [],
             "notes": "Las escenas de personaje usan su imagen fija con Ken Burns."},
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
# Idiomas soportados
# ---------------------------------------------------------------------------
# code → {label (para la interfaz), prompt (nombre que se le da al LLM para
# que escriba TODO en ese idioma), lang3 (metadato de subtítulos del mp4)}.
# Nota TTS: ElevenLabs (multilingual) y OpenAI TTS hablan todos estos idiomas
# con las mismas voces; en Edge TTS la voz elegida DEBE ser del idioma
# (ej. en-US-GuyNeural para inglés, hi-IN-MadhurNeural para hindi).

LANGUAGES: list[dict] = [
    {"code": "es", "label": "Español", "prompt": "español", "lang3": "spa"},
    {"code": "en", "label": "Inglés (English)", "prompt": "inglés (English)", "lang3": "eng"},
    {"code": "zh", "label": "Chino mandarín (中文)", "prompt": "chino mandarín simplificado (中文)", "lang3": "chi"},
    {"code": "hi", "label": "Hindi (हिन्दी)", "prompt": "hindi (हिन्दी)", "lang3": "hin"},
    {"code": "fr", "label": "Francés (Français)", "prompt": "francés (français)", "lang3": "fra"},
    {"code": "ar", "label": "Árabe (العربية)", "prompt": "árabe estándar moderno (العربية)", "lang3": "ara"},
    {"code": "bn", "label": "Bengalí (বাংলা)", "prompt": "bengalí (বাংলা)", "lang3": "ben"},
    {"code": "pt", "label": "Portugués (Português)", "prompt": "portugués (português)", "lang3": "por"},
    {"code": "ru", "label": "Ruso (Русский)", "prompt": "ruso (русский)", "lang3": "rus"},
    {"code": "de", "label": "Alemán (Deutsch)", "prompt": "alemán (Deutsch)", "lang3": "deu"},
]

_LANG_BY_CODE = {l["code"]: l for l in LANGUAGES}


def lang_name(cfg: dict) -> str:
    """Nombre completo del idioma configurado, para instruir al LLM
    («escribe en chino mandarín…») en vez de pasarle la sigla."""
    code = cfg.get("language", "es")
    return _LANG_BY_CODE.get(code, {}).get("prompt", code)


# ---------------------------------------------------------------------------
# Formatos de video (largo horizontal vs. corto vertical)
# ---------------------------------------------------------------------------
# El formato se elige POR PROYECTO al crearlo y se materializa como overrides
# en el config.yaml del proyecto (load_config ya hace el merge). Todos los
# verticales comparten 1080x1920; cambian la duración objetivo y la etiqueta.

FORMATS: dict = {
    "long": {
        "label": "🎬 YouTube — video largo (16:9)",
        "overrides": {},  # usa la configuración global tal cual
    },
    "short": {
        "label": "📱 YouTube Short — vertical ≤60 s",
        "target_minutes": 0.9,
        "overrides": {
            "video": {"width": 1080, "height": 1920, "scene_seconds": 3,
                      "target_minutes": 0.9, "burn_subtitles": True},
            "subtitles": {"font_size": 88, "max_chars_per_line": 20,
                          "max_lines": 2},
            "providers": {"images": {"size": "1024x1536"}},
        },
    },
    "reel": {
        "label": "📱 Instagram Reel — vertical ≤90 s",
        "target_minutes": 1.4,
        "overrides": {
            "video": {"width": 1080, "height": 1920, "scene_seconds": 3,
                      "target_minutes": 1.4, "burn_subtitles": True},
            "subtitles": {"font_size": 88, "max_chars_per_line": 20,
                          "max_lines": 2},
            "providers": {"images": {"size": "1024x1536"}},
        },
    },
    "tiktok": {
        "label": "📱 TikTok — vertical ~60 s",
        "target_minutes": 1.0,
        "overrides": {
            "video": {"width": 1080, "height": 1920, "scene_seconds": 3,
                      "target_minutes": 1.0, "burn_subtitles": True},
            "subtitles": {"font_size": 88, "max_chars_per_line": 20,
                          "max_lines": 2},
            "providers": {"images": {"size": "1024x1536"}},
        },
    },
    "ad_square": {
        "label": "🟦 Meta Ads — cuadrado 1:1 (feed) ≤60 s",
        "target_minutes": 0.7,
        "overrides": {
            "video": {"width": 1080, "height": 1080, "scene_seconds": 3,
                      "target_minutes": 0.7, "burn_subtitles": True},
            "subtitles": {"font_size": 64, "max_chars_per_line": 24,
                          "max_lines": 2},
            "providers": {"images": {"size": "1024x1024"}},
        },
    },
    "ad_45": {
        "label": "🟦 Meta Ads / Feed IG — retrato 4:5 ≤60 s",
        "target_minutes": 0.7,
        "overrides": {
            "video": {"width": 1080, "height": 1350, "scene_seconds": 3,
                      "target_minutes": 0.7, "burn_subtitles": True},
            "subtitles": {"font_size": 70, "max_chars_per_line": 22,
                          "max_lines": 2},
            "providers": {"images": {"size": "1024x1536"}},
        },
    },
}


# ---------------------------------------------------------------------------
# PLANTILLAS DE FORMATO para cortos (elegibles al crear el proyecto):
# empaquetan estructura de guion + tratamiento visual + rótulos + sticker +
# arco musical en una receta de un clic. `script_rules` se inyecta en la fase
# de guion; `scene_rules` en el storyboard y el pase de dirección de arte.
# ---------------------------------------------------------------------------

SHORT_TEMPLATES: dict = {
    "libre": {
        "label": "✨ Libre — el director decide la estructura",
        "hint": "Sin plantilla: gancho + desarrollo + cierre según el tema.",
        "script_rules": "", "scene_rules": "",
    },
    "top3": {
        "label": "🏆 Top 3 / Ranking",
        "hint": "Cuenta regresiva de 3 ítems, el mejor al final (clímax).",
        "script_rules": (
            "PLANTILLA TOP 3/RANKING: el gancho PROMETE el ranking («los 3 "
            "X que Y»). Luego los ítems en CUENTA REGRESIVA (3 → 2 → 1: el "
            "mejor SIEMPRE al final, es el clímax), 1-2 frases por ítem, "
            "concretas y con un porqué. Cierre de una línea que reta a "
            "comentar cuál elige el espectador."),
        "scene_rules": (
            "PLANTILLA TOP 3: cada ítem lleva overlay 'lista' (kicker «TOP "
            "3»/«TOP 2»/«TOP 1» + el nombre del ítem). La música SUBE ítem a "
            "ítem hasta el clímax en el TOP 1 (sfx riser antes, boom al "
            "llegar). Transiciones corte, pace ligado. Sticker 'encuesta' o "
            "'pregunta' en el cierre («¿cuál eliges?»)."),
    },
    "historia_giro": {
        "label": "🎭 Historia con giro",
        "hint": "Relato in media res con un giro inesperado al 70%.",
        "script_rules": (
            "PLANTILLA HISTORIA CON GIRO: arranca EN MEDIO de la acción (in "
            "media res, sin presentaciones), desarrolla en 3 actos "
            "comprimidos y suelta un GIRO inesperado hacia el 70% del guion. "
            "Remate final de UNA línea que recontextualiza todo. Primera o "
            "tercera persona, presente."),
        "scene_rules": (
            "PLANTILLA HISTORIA CON GIRO: pausa dramática (pause_after "
            "0.8-1.2) en la escena ANTERIOR al giro; el giro entra con sfx "
            "'boom' y transición 'corte'; tras el giro un 'fundido'. La "
            "música BAJA antes del giro y hace clímax después. Sin stickers "
            "salvo 'pregunta' final si pide opinión."),
    },
    "antes_despues": {
        "label": "🔁 Antes / Después",
        "hint": "Transformación con comparación en pantalla dividida.",
        "script_rules": (
            "PLANTILLA ANTES/DESPUÉS: estado inicial con el problema en "
            "carne viva (gancho), el proceso o decisión en 2-3 frases, y el "
            "DESPUÉS con el resultado medible. Compara explícitamente el "
            "antes y el después en una frase espejo («antes X, hoy Y»)."),
        "scene_rules": (
            "PLANTILLA ANTES/DESPUÉS: la escena de la comparación clave usa "
            "layout 'dividida' (broll_prompt = el ANTES, broll_prompt_b = el "
            "DESPUÉS, mismo encuadre y estilo para que el contraste cante). "
            "Overlays 'dato' para las cifras del cambio. Sticker 'encuesta' "
            "al cierre («¿lo probarías?»). Música de menos a más."),
    },
    "mito_realidad": {
        "label": "❌✅ Mito vs Realidad",
        "hint": "Enuncia el mito como cierto y desmóntalo con hechos.",
        "script_rules": (
            "PLANTILLA MITO VS REALIDAD: el gancho enuncia el MITO como si "
            "fuera verdad (que duela creerlo). Luego lo desmonta con 2-3 "
            "hechos verificables, del más débil al más demoledor. Cierre: la "
            "REALIDAD en una sola frase memorable."),
        "scene_rules": (
            "PLANTILLA MITO VS REALIDAD: overlay 'dato' con kicker «MITO» en "
            "el gancho y kicker «REALIDAD» en el remate. El primer hecho que "
            "desmonta entra con sfx 'boom'. Pace ligado; transiciones corte. "
            "Sticker 'pregunta' opcional («¿te lo creías?»)."),
    },
    "pasos": {
        "label": "⚡ Tutorial en pasos",
        "hint": "Resultado prometido + 3-5 pasos imperativos accionables.",
        "script_rules": (
            "PLANTILLA TUTORIAL EN PASOS: el gancho promete el RESULTADO "
            "(«así se logra X en Y»). Después 3-5 PASOS imperativos, uno por "
            "escena, ultra concretos (verbo + acción + detalle accionable). "
            "Cierre de una línea: «guárdalo para cuando lo necesites»."),
        "scene_rules": (
            "PLANTILLA TUTORIAL: cada paso lleva overlay 'lista' (kicker "
            "«PASO 1»…«PASO N» + el verbo del paso). Ritmo constante: pace "
            "ligado, cortes secos, música media sin clímax exagerado. "
            "Sticker 'countdown' opcional antes del resultado final."),
    },
    "dato_impactante": {
        "label": "🤯 Dato impactante",
        "hint": "Una cifra que rompe la cabeza, contexto y por qué importa.",
        "script_rules": (
            "PLANTILLA DATO IMPACTANTE: la CIFRA o dato chocante es la "
            "PRIMERA frase (sin preámbulo). Luego el contexto que lo hace "
            "creíble, por qué le importa al espectador, y un remate que "
            "conecta el dato con su vida."),
        "scene_rules": (
            "PLANTILLA DATO IMPACTANTE: overlay 'dato' GRANDE con la cifra "
            "en la escena 1 (además del hook). Música con arco corto: golpe "
            "inicial (sfx boom en la escena 2), desarrollo y cierre seco. "
            "Sticker 'pregunta' al final («¿lo sabías?»)."),
    },
}


def short_template(project, cfg: dict) -> dict | None:
    """Plantilla de formato del proyecto, o None (formato largo, plantilla
    'libre' o proyectos sin el campo)."""
    if not is_short_form(cfg):
        return None
    tid = project.get("short_template") if hasattr(project, "get") else None
    t = SHORT_TEMPLATES.get(tid or "")
    return t if t and tid != "libre" else None


# ---------------------------------------------------------------------------
# BRANDING DE RÓTULOS por canal/estilo (v0.41.0): tipografía y color de los
# rótulos en pantalla, configurables por estilo en vez de un único look
# global. Sin estilo, o con un estilo que no fije estos campos, el resultado
# es IDÉNTICO al de antes (sans + dorado E8C46B + texto blanco).
# ---------------------------------------------------------------------------

OVERLAY_FONT_FAMILIES: dict = {
    "moderna": {"label": "Moderna (sans neutra)",
               "hint": "Arial/Segoe/Liberation Sans — el look por defecto, "
                       "limpio y versátil para cualquier tema."},
    "editorial": {"label": "Editorial (serif)",
                 "hint": "Georgia/Times — aire de prensa/documental "
                         "histórico, elegante y con autoridad."},
    "impacto": {"label": "Impacto (display)",
               "hint": "Impact/Arial Black — títulos gruesos y directos, "
                       "estilo noticiero o contenido viral."},
    "mono": {"label": "Mono (datos)",
            "hint": "Monoespaciada — look técnico/de datos, cifras y "
                    "hechos con precisión de terminal."},
}

# Combos de un clic (familia + colores) — el creador puede partir de uno y
# ajustar accent/texto a mano después.
OVERLAY_BRANDING_PRESETS: dict = {
    "documental_clasico": {"label": "🎞 Documental clásico",
                           "overlay_font_family": "editorial",
                           "overlay_accent": "E8C46B",
                           "overlay_text_color": "FFFFFF",
                           "overlay_style": "documental"},
    "impacto_viral": {"label": "⚡ Impacto viral",
                      "overlay_font_family": "impacto",
                      "overlay_accent": "FF3B30",
                      "overlay_text_color": "FFFFFF",
                      "overlay_style": "bold"},
    "tech_datos": {"label": "🖥 Tech / datos",
                   "overlay_font_family": "mono",
                   "overlay_accent": "39FF14",
                   "overlay_text_color": "E6E6E6",
                   "overlay_style": "documental"},
    "minimalista": {"label": "◻ Minimalista",
                    "overlay_font_family": "moderna",
                    "overlay_accent": "FFFFFF",
                    "overlay_text_color": "FFFFFF",
                    "overlay_style": "minimal"},
}


def is_vertical(cfg: dict) -> bool:
    v = cfg.get("video", {})
    return int(v.get("height", 1080)) > int(v.get("width", 1920))


def is_short_form(cfg: dict) -> bool:
    """¿Es un formato de redes sociales de consumo rápido? Cubre vertical
    (9:16), cuadrado (1:1) y retrato de feed (4:5) — todos comparten el
    lenguaje: gancho visual de apertura, texto grande, ritmo alto, rupturas
    de patrón. El 16:9 largo NO lo es."""
    v = cfg.get("video", {})
    w, h = int(v.get("width", 1920)), int(v.get("height", 1080))
    return h >= w or (max(w, h) / max(1, min(w, h))) < 1.6


def aspect_for(cfg: dict, allowed: tuple[str, ...] | None = None) -> str:
    """Relación de aspecto para pedirle al generador (imágenes/video IA),
    según el formato del proyecto. Antes solo existían 16:9 y 9:16: un
    proyecto cuadrado (Meta Ads 1:1) pedía imágenes 16:9 y todo salía
    recortado. `allowed` restringe a lo que soporta el modelo (ej. Kling
    no genera 4:5) y se elige lo más cercano."""
    v = cfg.get("video", {})
    w, h = int(v.get("width", 1920)), int(v.get("height", 1080))
    ratio = w / max(1, h)
    table = [("9:16", 9 / 16), ("4:5", 4 / 5), ("1:1", 1.0),
             ("4:3", 4 / 3), ("16:9", 16 / 9)]
    if allowed:
        table = [t for t in table if t[0] in allowed] or table
    return min(table, key=lambda t: abs(t[1] - ratio))[0]


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
        "insert_sfx": "archivo",
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
        "insert_sfx": "epico",
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
        "insert_sfx": "sobrio",
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
        "insert_sfx": "archivo",
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
        "insert_sfx": "moderno",
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
