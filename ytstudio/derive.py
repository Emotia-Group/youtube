"""SACAR SHORTS DE UN VIDEO LARGO.

Un Short no es un video corto: es una pieza con una función. Este módulo lee
un video largo —uno de tus proyectos terminados o cualquier enlace de
YouTube—, busca dentro los momentos que aguantan solos, y de cada uno escribe
un Short completo listo para generar.

Las tres decisiones de fondo, y por qué:

1. EL PUENTE ES MANUAL. Las plataformas usan sistemas de recomendación
   SEPARADOS para video corto y largo: un Short viral no empuja tu video
   largo. Lo único que convierte una vista de Short en una visita al largo es
   el enlace a video relacionado + una llamada a la acción + que el destino
   continúe ESA idea concreta. Por eso cada Short que sale de aquí nace
   apuntando a su video de origen.

2. UNA SOLA IDEA POR PIEZA. El impulso de meter dos porque «ya que estamos»
   es lo que rompe la retención. Si hay dos ideas, son dos Shorts.

3. LOS GANCHOS SE ROTAN. Repetir la misma fórmula fatiga a la audiencia y,
   además, es exactamente el patrón que las políticas describen como
   producción en masa. La rotación no es estética: es la defensa.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# LAS SEIS ESTRUCTURAS DE GANCHO — se rotan, mínimo cuatro por tanda
# ---------------------------------------------------------------------------
# `plantilla` enlaza cada estructura con la plantilla de guion que ya existe
# en el catálogo, para que el Short derivado nazca con su receta puesta.

HOOK_STRUCTURES: dict = {
    "cifra_contradiccion": {
        "label": "Cifra + contradicción",
        "patron": "Un dato duro que choca con la intuición.",
        "ejemplo": "«El 73% lo hace mal. Y el motivo no es el que crees.»",
        "plantilla": "dato_impactante",
    },
    "error_costeado": {
        "label": "Error costeado",
        "patron": "Nombra el coste concreto de un error común.",
        "ejemplo": "«Este error te cuesta 1.200 euros al año.»",
        "plantilla": "dato_impactante",
    },
    "mito_desmontado": {
        "label": "Mito desmontado",
        "patron": "Niega de frente una creencia extendida.",
        "ejemplo": "«No, madrugar no te hace más productivo.»",
        "plantilla": "mito_realidad",
    },
    "micro_historia": {
        "label": "Micro-historia en mitad de la acción",
        "patron": "Entra sin preámbulo, con la escena ya empezada.",
        "ejemplo": "«El día que lo enterró, creyó que era prudente.»",
        "plantilla": "historia_giro",
    },
    "pregunta_personal": {
        "label": "Pregunta con relevancia personal",
        "patron": "Obliga al espectador a evaluarse a sí mismo.",
        "ejemplo": "«¿Sabes cuánto te están cobrando de más?»",
        "plantilla": "libre",
    },
    "contraste_visual": {
        "label": "Contraste visual",
        "patron": "La imagen del primer segundo hace la pregunta.",
        "ejemplo": "Antes/después, sin una palabra de introducción.",
        "plantilla": "antes_despues",
    },
}

MIN_ROTACION = 4     # estructuras distintas exigidas en una tanda

# ---------------------------------------------------------------------------
# CALENDARIO DE CAMPAÑA alrededor del video largo (D0 = día del largo)
# ---------------------------------------------------------------------------
# El orden no es decorativo: va de lo general a lo específico. Las piezas que
# exigen contexto van DESPUÉS del video largo, cuando el contexto ya existe
# para recibir el clic.

CAMPAIGN: list = [
    {"id": "posicionamiento", "dia": -4, "label": "Posicionamiento",
     "para": "La pieza que explica por qué existe tu canal o tu tesis."},
    {"id": "promesa", "dia": -2, "label": "Promesa",
     "para": "Una brecha de curiosidad que el video largo cerrará."},
    {"id": "activacion", "dia": 0, "label": "Activación",
     "para": "Pregunta directa a la audiencia: genera comentarios el día clave."},
    {"id": "profundizacion", "dia": 2, "label": "Profundización",
     "para": "El concepto central del video, desarrollado."},
    {"id": "emocion", "dia": 4, "label": "Emoción",
     "para": "La pieza con más carga narrativa."},
    {"id": "expansion", "dia": 7, "label": "Expansión",
     "para": "La que funciona FUERA de tu nicho: es la que trae público nuevo."},
    {"id": "puente", "dia": 9, "label": "Puente",
     "para": "Cierra el tema y enlaza con el siguiente video largo."},
]
CAMPAIGN_BY_ID = {c["id"]: c for c in CAMPAIGN}

# Duración por tipo de contenido. Un Short corto puntúa mecánicamente más
# alto en «% medio visto», que es señal de ranking: menos oportunidades de
# abandono y un denominador más pequeño.
DURACION_MIN, DURACION_MAX = 20, 60


# ---------------------------------------------------------------------------
# DE DÓNDE SALE EL MATERIAL
# ---------------------------------------------------------------------------

def _hhmmss(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def source_from_project(slug: str) -> dict:
    """Material de un proyecto LARGO ya generado en este programa.

    Es la fuente más rica y no cuesta nada: las escenas ya traen su duración,
    así que el minuto exacto de cada frase se sabe sin transcribir nada."""
    from ytstudio.project import DIRS, Project, read_json_tolerant

    if not Project.exists(slug):
        raise ValueError(f"No existe el proyecto «{slug}».")
    project = Project(slug)
    scenes_file = project.dir / DIRS["scenes"] / "scenes.json"
    if not scenes_file.exists():
        raise ValueError(
            f"El proyecto «{slug}» todavía no tiene escenas. Genérale al menos "
            "el guion gráfico antes de sacarle Shorts.")
    scenes = read_json_tolerant(scenes_file).get("scenes") or []

    marcas, t = [], 0.0
    for s in scenes:
        texto = (s.get("narration") or "").strip()
        if texto:
            marcas.append({"t": round(t, 1), "seccion": s.get("section") or "",
                           "texto": texto})
        t += float(s.get("duration") or 0)

    concept = project.get("concept") or {}
    meta = project.get("metadata") or {}
    yid = project.get("youtube_id")
    return {
        "origen": "proyecto",
        "slug": slug,
        "titulo": meta.get("title") or project.state.get("display_name") or slug,
        "duracion": round(t, 1),
        "angulo": concept.get("angle") or "",
        "tono": concept.get("tone") or "",
        "audiencia": concept.get("audience") or "",
        "marcas": marcas,
        "url": f"https://youtu.be/{yid}" if yid else "",
    }


def _parse_vtt_timed(path) -> list:
    """Transcripción CON tiempos de un .vtt/.srt.

    El lector que ya existe en el programa (`refvideo._parse_vtt`) tira los
    tiempos a propósito, porque para copiar un estilo no hacen falta. Aquí sí:
    sin el minuto no se puede señalar el momento del video largo del que sale
    cada Short."""
    from pathlib import Path

    out: list = []
    actual: float | None = None
    for raw in Path(path).read_text(encoding="utf-8",
                                    errors="replace").splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()
        m = re.match(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->", line)
        if m:
            h, mi, s, ms = (int(x) for x in m.groups())
            actual = h * 3600 + mi * 60 + s + ms / 1000
            continue
        if (not line or line == "WEBVTT" or re.fullmatch(r"\d+", line)
                or line.startswith(("Kind:", "Language:", "NOTE"))):
            continue
        if actual is None:
            continue
        # Los subtítulos automáticos repiten la línea anterior al desplazarse
        if out and out[-1]["texto"].endswith(line):
            continue
        out.append({"t": round(actual, 1), "seccion": "", "texto": line})
    return out


def _limpiar_error_ytdlp(e) -> str:
    """Mensaje legible a partir de un error de yt-dlp.

    Los errores de yt-dlp vienen con códigos de color de consola («[0;31m»)
    y jerga que no dice nada al creador. Aquí se traducen a lo que de verdad
    importa: qué pasó y qué hacer."""
    msg = re.sub(r"\x1b?\[[0-9;]*m", "", str(e))
    msg = re.sub(r"^\s*ERROR:\s*", "", msg).strip()
    bajo = msg.lower()
    if "429" in msg or "too many requests" in bajo:
        return ("YouTube está limitando las peticiones desde tu conexión "
                "(error 429: «demasiadas peticiones»). NO es un fallo del "
                "programa ni de tu video: pasa cuando se consultan varios "
                "videos seguidos. Espera unos minutos y vuelve a intentarlo. "
                "Mientras tanto, si el video largo es un proyecto de este "
                "programa, deja la casilla del enlace VACÍA: así el material "
                "se lee de tu propio proyecto, sin tocar YouTube.")
    if "private video" in bajo or "sign in" in bajo:
        return ("Ese video es privado o pide iniciar sesión, así que el "
                "programa no puede leerlo. Ponlo como «no listado» o público, "
                "o saca los Shorts desde el proyecto de este programa.")
    if "video unavailable" in bajo or "not available" in bajo:
        return ("Ese video no está disponible (puede estar borrado, ser "
                "privado o tener restricción por país). Comprueba el enlace.")
    if "unable to download" in bajo and "subtitle" in bajo:
        return ("No se pudieron descargar los subtítulos de ese video. "
                f"Detalle técnico: {msg[:200]}")
    return msg[:400]


def _elegir_idioma_subtitulos(info: dict, lang: str):
    """Qué ÚNICA pista de subtítulos pedir, entre las que el video tiene.

    Antes se pedían tres a la vez (el idioma del proyecto, su variante
    «-orig» e inglés) aunque solo se usara la primera: tres descargas
    seguidas contra YouTube por cada consulta, que es justo lo que dispara
    el error 429 de «demasiadas peticiones». Ahora se mira PRIMERO qué
    pistas existen (eso viene en los metadatos, sin descargar nada) y se
    pide exactamente una.

    Devuelve (código de idioma, es_automático) o (None, False)."""
    manuales = info.get("subtitles") or {}
    automaticos = info.get("automatic_captions") or {}
    # Las pistas «live_chat» no son subtítulos
    manuales = {k: v for k, v in manuales.items() if k != "live_chat"}

    preferidos = [lang, f"{lang}-orig"]
    idioma_video = info.get("language")
    if idioma_video:
        preferidos += [idioma_video, f"{idioma_video}-orig"]
    preferidos.append("en")

    for tabla, es_auto in ((manuales, False), (automaticos, True)):
        # Se recorre preferencia por preferencia, probando primero el código
        # exacto y luego sus variantes regionales («es-419», «es-ES»). Hacerlo
        # en dos pasadas separadas era un error: con «es-419» e «inglés»
        # disponibles, un proyecto en español acababa en inglés.
        for code in preferidos:
            if code in tabla:
                return code, es_auto
            raiz = code.split("-")[0]
            for disponible in sorted(tabla):
                if disponible.split("-")[0] == raiz:
                    return disponible, es_auto
    # Lo que haya: mejor unos subtítulos en otro idioma que ninguno
    for tabla, es_auto in ((manuales, False), (automaticos, True)):
        if tabla:
            return next(iter(tabla)), es_auto
    return None, False


def source_from_url(url: str, cfg: dict, work_dir=None) -> dict:
    """Material de CUALQUIER video de YouTube a partir de su enlace.

    Solo se descargan los subtítulos y los metadatos: no hace falta bajar el
    video (que puede ser de horas). Y se descarga UNA sola pista, elegida
    entre las que el video tiene de verdad — pedir varias a la vez es lo que
    dispara el bloqueo por «demasiadas peticiones» de YouTube."""
    import time
    from pathlib import Path
    import tempfile

    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError(
            "Para leer un video de YouTube hace falta yt-dlp. Instálalo con "
            "«pip install yt-dlp» (o con el archivo actualizar.bat).")

    work = Path(work_dir or tempfile.mkdtemp(prefix="derive_"))
    work.mkdir(parents=True, exist_ok=True)
    lang = cfg.get("language", "es")
    base = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": float((cfg.get("reference") or {}).get(
            "timeout_seconds", 45)),
        "retries": 3,
        "skip_download": True,          # los subtítulos bastan
    }
    from ytstudio.progress import notify

    def _con_reintentos(fn, que: str):
        """YouTube devuelve 429 en rachas: un par de esperas cortas suelen
        bastar. Si no, el error sale traducido a algo accionable."""
        esperas = [0, 4, 12]
        ultimo = None
        for i, espera in enumerate(esperas):
            if espera:
                notify(f"⏳ YouTube pidió esperar; reintentando {que} en "
                       f"{espera}s… ({i} de {len(esperas) - 1})")
                time.sleep(espera)
            try:
                return fn()
            except Exception as e:
                ultimo = e
                if "429" not in str(e) and "Too Many Requests" not in str(e):
                    break
        raise RuntimeError(_limpiar_error_ytdlp(ultimo))

    # 1) METADATOS, sin descargar nada: título, duración y QUÉ subtítulos hay
    notify(f"🔎 Leyendo el video largo… ({url})")

    def _meta():
        with yt_dlp.YoutubeDL(base) as ydl:
            return ydl.extract_info(url, download=False)

    info = _con_reintentos(_meta, "la consulta")

    code, es_auto = _elegir_idioma_subtitulos(info, lang)
    if not code:
        raise RuntimeError(
            "Ese video no tiene subtítulos disponibles, ni propios ni "
            "automáticos, así que no se puede leer lo que dice. Si es tuyo, "
            "actívalos en YouTube Studio; si no, saca los Shorts desde el "
            "proyecto de este programa (deja la casilla del enlace vacía).")

    # 2) UNA sola pista de subtítulos, la elegida
    notify(f"📥 Descargando los subtítulos en «{code}»"
           + (" (automáticos)" if es_auto else "") + "…")
    opts = {
        **base,
        "writesubtitles": not es_auto,
        "writeautomaticsub": es_auto,
        "subtitleslangs": [code],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": str(work / "src.%(ext)s"),
        # Si la pista falla, no se tira la operación entera: puede que otra
        # variante sí haya quedado en disco, y el aviso claro vale más que
        # una traza de error.
        "ignoreerrors": True,
    }

    def _bajar():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    _con_reintentos(_bajar, "la descarga de subtítulos")

    subs = sorted(work.glob("src*.vtt")) + sorted(work.glob("src*.srt"))
    marcas = _parse_vtt_timed(subs[0]) if subs else []
    if not marcas:
        raise RuntimeError(
            f"YouTube no entregó los subtítulos de ese video (pista «{code}»). "
            "Suele ser un bloqueo temporal por hacer varias consultas "
            "seguidas: espera unos minutos y reinténtalo. Si el video largo "
            "es un proyecto de este programa, deja la casilla del enlace "
            "vacía y el material se lee de tu propio proyecto, sin tocar "
            "YouTube.")
    notify(f"📝 Leídas {len(marcas)} líneas con su minuto.")
    return {
        "origen": "enlace",
        "slug": "",
        "titulo": info.get("title") or url,
        "duracion": float(info.get("duration") or 0),
        "angulo": "", "tono": "", "audiencia": "",
        "canal": info.get("uploader") or info.get("channel") or "",
        "marcas": marcas,
        "url": info.get("webpage_url") or url,
        "subtitulos": {"idioma": code, "automaticos": es_auto},
    }


def transcript_block(source: dict, max_chars: int = 24000) -> str:
    """La transcripción con su minuto delante, recortada para caber en el
    prompt sin perder el reparto a lo largo de TODO el video (si se recortara
    por el final, los Shorts saldrían todos del principio)."""
    marcas = source.get("marcas") or []
    if not marcas:
        return ""
    lineas = [f"[{_hhmmss(m['t'])}] {m['texto']}" for m in marcas]
    total = sum(len(x) + 1 for x in lineas)
    if total > max_chars:
        paso = max(1, round(total / max_chars))
        lineas = lineas[::paso]
    return "\n".join(lineas)[:max_chars]


# ---------------------------------------------------------------------------
# LA PROPUESTA
# ---------------------------------------------------------------------------

CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidatos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "idea": {"type": "string"},
                    "gancho_tipo": {"type": "string",
                                    "enum": list(HOOK_STRUCTURES)},
                    "texto_pantalla": {"type": "string"},
                    "guion": {"type": "string"},
                    "cta": {"type": "string"},
                    "funcion": {"type": "string",
                                "enum": [c["id"] for c in CAMPAIGN]},
                    "desde": {"type": "number"},
                    "hasta": {"type": "number"},
                    "duracion": {"type": "integer"},
                    "titulo_youtube": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["nombre", "idea", "gancho_tipo", "texto_pantalla",
                             "guion", "cta", "funcion", "desde", "hasta",
                             "duracion", "titulo_youtube", "descripcion",
                             "hashtags"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["candidatos"],
    "additionalProperties": False,
}


def _system_prompt(lang: str) -> str:
    return (
        f"Eres editor de contenido vertical corto y escribes en {lang}. Tu "
        "trabajo es leer un video largo y encontrar dentro los momentos que "
        "AGUANTAN SOLOS: los que alguien que no ha visto el video entiende y "
        "disfruta en menos de un minuto.\n\n"
        "Trabajas con el modelo de ADQUISICIÓN: cada Short existe para llevar "
        "gente al video largo. Eso manda sobre todo lo demás — el final queda "
        "ABIERTO (la resolución está en el largo), la llamada a la acción es "
        "el video largo y NUNCA la suscripción, y el destino tiene que "
        "continuar esa idea concreta, no ser «tu mejor video».\n\n"
        "Escribes SOLO el texto que dirá el narrador: sin acotaciones, sin "
        "marcas de tiempo, sin corchetes.")


def _prompt(source: dict, n: int, hooks: list) -> str:
    hook_list = "\n".join(
        f"- {k}: {v['patron']} Ejemplo: {v['ejemplo']}"
        for k, v in HOOK_STRUCTURES.items() if k in hooks)
    funciones = "\n".join(f"- {c['id']} ({c['label']}): {c['para']}"
                          for c in CAMPAIGN)
    ficha = [f"Título del video largo: {source['titulo']}"]
    if source.get("canal"):
        ficha.append(f"Canal: {source['canal']}")
    if source.get("duracion"):
        ficha.append(f"Duración: {_hhmmss(source['duracion'])}")
    for k, etiqueta in (("angulo", "Ángulo"), ("tono", "Tono"),
                        ("audiencia", "Audiencia")):
        if source.get(k):
            ficha.append(f"{etiqueta}: {source[k]}")

    return (
        "\n".join(ficha) + "\n\n"
        "TRANSCRIPCIÓN DEL VIDEO LARGO, con el minuto de cada línea:\n<<<\n"
        + transcript_block(source) + "\n>>>\n\n"
        f"Propón {n} Shorts. Uno por momento REALMENTE bueno: si el video solo "
        f"da para menos, devuelve menos — más vale tres piezas que aguantan "
        f"que {n} rellenadas.\n\n"
        "REGLAS QUE NO SE NEGOCIAN:\n\n"
        "1. UNA SOLA IDEA por Short. Si un momento tiene dos, son dos Shorts.\n"
        "2. La PRIMERA FRASE del guion es el gancho, y se dice antes del "
        "medio segundo: nada de saludos, presentaciones ni «en este video "
        "te voy a explicar».\n"
        "3. REGLA DE DOBLE PISTA: 'texto_pantalla' es el gancho escrito para "
        "que aparezca desde el primer fotograma. Tiene que transmitir la "
        "MISMA promesa que la locución, porque la mayoría verá el Short SIN "
        "SONIDO. Máximo 6 palabras.\n"
        "4. ESTRUCTURA del guion, en este orden y sin encabezados: gancho → "
        "promesa concreta de qué se lleva quien se quede → desarrollo de la "
        "idea → PAGO (se cumple explícitamente lo prometido: sin esto no hay "
        "«me gusta», porque el «me gusta» se decide justo ahí) → llamada a la "
        "acción → una última frase que ENLACE CON EL PRINCIPIO (los Shorts se "
        "repiten solos: un final que conecta con el primer fotograma hace que "
        "la gente lo vea dos veces).\n"
        "5. UNA SOLA llamada a la acción, al final, hacia el VIDEO LARGO. "
        "Con motivo, no como orden: «suscríbete» está prohibido.\n"
        f"6. DURACIÓN entre {DURACION_MIN} y {DURACION_MAX} segundos "
        f"({DURACION_MIN * 150 // 60}-{DURACION_MAX * 150 // 60} palabras "
        "aproximadamente). Nunca más de 60: por encima del minuto, una "
        "reclamación de copyright bloquea el video en todo el mundo.\n"
        "7. ROTA LAS ESTRUCTURAS DE GANCHO. Usa al menos "
        f"{min(MIN_ROTACION, n)} distintas y NUNCA dos seguidas iguales:\n"
        f"{hook_list}\n\n"
        "8. 'desde' y 'hasta' son los segundos del video largo de donde sale "
        "la idea (números, no texto). Sirven para volver a ese punto.\n"
        "9. 'funcion' coloca la pieza en la campaña alrededor del video "
        f"largo. Reparte, no repitas:\n{funciones}\n\n"
        "10. 'titulo_youtube': 40-70 caracteres, la palabra clave al "
        "principio, SIN el hashtag de Shorts (la clasificación es automática "
        "por proporción y duración: ese hashtag es un mito de 2021).\n"
        "11. 'descripcion': primera línea = el gancho reformulado (es lo "
        "único que se ve sin desplegar). 'hashtags': 2 o 3, temáticos.")


def propose(source: dict, cfg: dict, n: int = 5) -> list:
    """Pide al director los mejores momentos y devuelve los candidatos ya
    normalizados (una sola llamada al modelo para toda la tanda)."""
    from ytstudio.catalog import lang_name
    from ytstudio.providers import get_llm

    if not (source.get("marcas") or []):
        raise ValueError("El video largo no tiene texto que leer.")
    n = max(1, min(int(n), len(CAMPAIGN)))
    llm = get_llm(cfg)
    data = llm.complete_json(_system_prompt(lang_name(cfg)),
                             _prompt(source, n, list(HOOK_STRUCTURES)),
                             schema=CANDIDATE_SCHEMA, purpose="derive_shorts")
    return normalize(data.get("candidatos") or [], source, n)


def normalize(candidatos: list, source: dict, n: int) -> list:
    """Red de seguridad sobre lo que devuelve el modelo: recorta a lo pedido,
    descarta lo incompleto, y garantiza que ninguna pieza pase de 60 s ni
    repita función de campaña."""
    limpio, funciones_usadas = [], set()
    for c in candidatos:
        if not (c.get("guion") or "").strip():
            continue
        c["gancho_tipo"] = (c.get("gancho_tipo") if c.get("gancho_tipo")
                            in HOOK_STRUCTURES else "pregunta_personal")
        c["plantilla"] = HOOK_STRUCTURES[c["gancho_tipo"]]["plantilla"]
        # La duración manda sobre lo que diga el modelo: por encima de 60 s
        # una reclamación de copyright bloquea el video en todo el mundo.
        try:
            dur = int(c.get("duracion") or 0)
        except (TypeError, ValueError):
            dur = 0
        palabras = len((c.get("guion") or "").split())
        c["duracion"] = max(DURACION_MIN,
                            min(DURACION_MAX, dur or round(palabras / 2.5)))
        # Función de campaña: la primera libre si el modelo repite
        f = c.get("funcion")
        if f not in CAMPAIGN_BY_ID or f in funciones_usadas:
            f = next((x["id"] for x in CAMPAIGN
                      if x["id"] not in funciones_usadas), CAMPAIGN[-1]["id"])
        c["funcion"] = f
        funciones_usadas.add(f)
        c["dia"] = CAMPAIGN_BY_ID[f]["dia"]
        c["hashtags"] = [h if h.startswith("#") else f"#{h}"
                         for h in (c.get("hashtags") or [])][:3]
        c["origen_url"] = source.get("url", "")
        c["origen_titulo"] = source.get("titulo", "")
        c["origen_slug"] = source.get("slug", "")
        limpio.append(c)
        if len(limpio) >= n:
            break
    limpio.sort(key=lambda c: c["dia"])
    return limpio


def rotation_report(candidatos: list) -> dict:
    """¿La tanda rota bastante? Repetir la misma fórmula fatiga a la audiencia
    y es el patrón que las políticas describen como producción en masa: la
    rotación no es estética, es la defensa."""
    tipos = [c.get("gancho_tipo") for c in candidatos]
    distintas = len(set(tipos))
    seguidas = [(a, b) for a, b in zip(tipos, tipos[1:]) if a == b]
    minimo = min(MIN_ROTACION, len(candidatos))
    return {
        "estructuras": distintas,
        "minimo": minimo,
        "suficiente": distintas >= minimo and not seguidas,
        "repetidas_seguidas": len(seguidas),
    }


def campaign_label(dia: int) -> str:
    """«D-4», «D0», «D+7» — la etiqueta del día en la campaña."""
    return "D0" if dia == 0 else f"D{dia:+d}"


def calendar(candidatos: list, d0=None) -> list:
    """Fechas reales de publicación a partir del día del video largo."""
    base = d0 or date.today()
    if isinstance(base, str):
        base = date.fromisoformat(base)
    return [{
        "nombre": c.get("nombre", ""),
        "funcion": CAMPAIGN_BY_ID[c["funcion"]]["label"],
        "para": CAMPAIGN_BY_ID[c["funcion"]]["para"],
        "dia": c["dia"],
        "etiqueta": campaign_label(c["dia"]),
        "fecha": (base + timedelta(days=c["dia"])).isoformat(),
        "slug": c.get("slug", ""),
    } for c in candidatos]


# ---------------------------------------------------------------------------
# DE CANDIDATO A PROYECTO DE VERDAD
# ---------------------------------------------------------------------------

def script_markdown(c: dict) -> str:
    """El guion del Short tal como se guarda en el proyecto.

    Se entrega como GUION TERMINADO, no como idea: el programa lo respeta y
    solo le pule la fluidez, en vez de reescribirlo desde cero."""
    return (f"## {c.get('nombre') or 'Short'}\n\n"
            + (c.get("guion") or "").strip() + "\n")


def brief_markdown(c: dict) -> str:
    """Ficha de la pieza, para el creador y para la revisión de originalidad
    (las apelaciones se ganan con evidencia archivada, no con explicaciones)."""
    h = HOOK_STRUCTURES[c["gancho_tipo"]]
    camp = CAMPAIGN_BY_ID[c["funcion"]]
    origen = c.get("origen_titulo", "")
    if c.get("origen_url"):
        origen += f" ({c['origen_url']})"
    enlace = c.get("origen_url") or (
        "PENDIENTE — pega aquí el enlace del video largo")
    return "\n".join([
        f"# {c.get('nombre', 'Short')}",
        "",
        f"**Sale de:** {origen}",
        f"**Momento del video largo:** {_hhmmss(c.get('desde') or 0)} → "
        f"{_hhmmss(c.get('hasta') or 0)}",
        "",
        f"**La idea (una sola):** {c.get('idea', '')}",
        f"**Estructura de gancho:** {h['label']} — {h['patron']}",
        f"**Texto en pantalla desde el primer fotograma:** "
        f"{c.get('texto_pantalla', '')}",
        f"**Llamada a la acción:** {c.get('cta', '')}",
        f"**Duración objetivo:** {c.get('duracion')} s",
        "",
        f"**En la campaña:** {camp['label']} · {campaign_label(camp['dia'])}",
        f"  {camp['para']}",
        "",
        "## Para publicar",
        "",
        f"- **Título:** {c.get('titulo_youtube', '')}",
        f"- **Descripción:** {c.get('descripcion', '')}",
        f"- **Hashtags:** {' '.join(c.get('hashtags') or [])}",
        f"- **Enlace a video relacionado:** {enlace}",
        "",
        "> El enlace a video relacionado se pone A MANO en YouTube Studio "
        "(Contenido → el Short → Video relacionado). No hay forma de ponerlo "
        "desde fuera. Se puede añadir DESPUÉS de publicar, así que un Short "
        "antiguo se puede reapuntar a un video largo nuevo.",
    ])


def create_short_project(c: dict, cfg: dict, *, slug: str | None = None,
                         channel_id: str = "", style_id: str = "") -> str:
    """Crea un proyecto de Short ya rellenado a partir de un candidato.

    Nace con el guion puesto (como GUION, no como idea: el programa lo
    respeta), con su plantilla de estructura, en formato vertical y apuntando
    al video largo del que salió."""
    import yaml

    from ytstudio.catalog import FORMATS, SHORT_TEMPLATES
    from ytstudio.phases.ingest import add_asset
    from ytstudio.project import Project, slugify

    base = slugify(slug or c.get("nombre") or "short")
    final, i = base, 2
    while Project.exists(final):
        final, i = f"{base}-{i}", i + 1

    project = Project.create(final)
    guion = project.path("input") / "guion_short.md"
    guion.write_text(script_markdown(c), encoding="utf-8")
    add_asset(project, guion, "guion")
    (project.path("input") / "ficha_short.md").write_text(
        brief_markdown(c), encoding="utf-8")

    project.set("format", "short")
    plantilla = c.get("plantilla") or "libre"
    project.set("short_template",
                plantilla if plantilla in SHORT_TEMPLATES else "libre")
    if channel_id:
        project.set("channel_id", channel_id)
    if style_id:
        project.set("style_id", style_id)
    # DE DÓNDE SALIÓ Y ADÓNDE APUNTA: sin esto, el Short pierde el único
    # enlace que lo convierte en visitas al video largo.
    project.set("derived_from", {
        "titulo": c.get("origen_titulo", ""),
        "url": c.get("origen_url", ""),
        "slug": c.get("origen_slug", ""),
        "desde": c.get("desde"), "hasta": c.get("hasta"),
    })
    project.set("shorts_plan", {
        "idea": c.get("idea", ""), "gancho_tipo": c.get("gancho_tipo"),
        "texto_pantalla": c.get("texto_pantalla", ""), "cta": c.get("cta", ""),
        "funcion": c.get("funcion"), "dia": c.get("dia"),
        "titulo_youtube": c.get("titulo_youtube", ""),
        "descripcion": c.get("descripcion", ""),
        "hashtags": c.get("hashtags") or [],
        "duracion": c.get("duracion"),
    })
    if c.get("nombre"):
        project.state["display_name"] = c["nombre"]
        project.save()

    # Overrides por proyecto: vertical, duración objetivo y subtítulos grandes
    overrides = {k: dict(v) for k, v in FORMATS["short"]["overrides"].items()}
    segundos = int(c.get("duracion") or 45)
    overrides.setdefault("video", {})["target_minutes"] = round(
        segundos / 60, 2)
    (project.dir / "config.yaml").write_text(
        yaml.safe_dump(overrides, allow_unicode=True), encoding="utf-8")
    return final


def plan_path(source: dict):
    """Dónde se guarda el plan cuando el origen es un proyecto de la casa."""
    from ytstudio.project import Project
    if not source.get("slug") or not Project.exists(source["slug"]):
        return None
    return Project(source["slug"]).dir / "plan_shorts.json"


def save_plan(source: dict, candidatos: list, d0=None) -> dict:
    """Guarda el plan junto al video largo del que salió."""
    plan = {
        "origen": {k: source.get(k) for k in ("titulo", "url", "slug",
                                              "duracion", "origen")},
        "candidatos": candidatos,
        "rotacion": rotation_report(candidatos),
        "calendario": calendar(candidatos, d0),
    }
    p = plan_path(source)
    if p is not None:
        p.write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    return plan
