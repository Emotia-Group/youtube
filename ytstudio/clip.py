"""RECORTAR UN SHORT DEL VIDEO ORIGINAL.

El otro camino para hacer Shorts. Hay dos, y la diferencia importa:

  · RECORTE (este módulo) — se baja el tramo exacto del video largo y se
    reencuadra a vertical. Conserva TU voz, TU edición y TU imagen tal como
    se publicaron. No cuesta ni voz ni imágenes: solo el rato de descargar
    y montar. Es lo que casi siempre se quiere.

  · PIEZA NUEVA (`ytstudio/derive.py`) — se escribe un guion nuevo y se
    genera todo de cero. Cuesta dinero y tiempo, pero permite decir algo que
    en el video largo no está dicho de forma que aguante sola.

Las dos salen del mismo análisis del video largo: el director elige el
momento y, según el modo, o se recorta o se reescribe.

Tres decisiones de fondo:

1. NO SE PIERDE IMAGEN. Al pasar de 16:9 a 9:16 sobra casi el 70% del ancho.
   Recortar por el centro se come lo que haya a los lados —y el sujeto no
   siempre está centrado—, así que por defecto el fotograma entero se
   coloca sobre un fondo hecho con la propia imagen ampliada y desenfocada:
   la pantalla se llena, no se pierde nada, y se lee como algo hecho a
   propósito. Quien prefiera llenar el cuadro tiene el recorte centrado.

2. LOS SUBTÍTULOS SALEN DEL PROPIO VIDEO, con sus tiempos, y se colocan en
   la zona segura — por encima de la franja que la app reserva al enlace al
   video largo.

3. SE MIDE LA SONORIDAD, igual que en cualquier otro video del programa: un
   recorte hereda el volumen del original, que casi nunca está a -14 LUFS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Cómo pasar de horizontal a vertical
REENCUADRES = {
    "fondo_desenfocado": {
        "label": "Fondo desenfocado (no se pierde nada)",
        "hint": "El fotograma entero, centrado, sobre su propia imagen "
                "ampliada y desenfocada. Llena la pantalla sin recortar.",
    },
    "recorte_centrado": {
        "label": "Recorte centrado (llena el cuadro)",
        "hint": "Se queda con la franja central de la imagen. Llena todo, "
                "pero pierde los lados: úsalo si el sujeto va centrado.",
    },
}
REENCUADRE_POR_DEFECTO = "fondo_desenfocado"

# Margen que se descarga de más a cada lado del tramo, para que el corte no
# empiece a media palabra: los cortes por fotograma clave no caen donde uno
# quiere, y un poco de aire cuesta segundos de descarga, no dinero.
AIRE_SEGUNDOS = 1.0


def available() -> bool:
    """¿Se puede recortar? Hace falta yt-dlp para bajar el tramo."""
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# 1) BAJAR SOLO EL TRAMO
# ---------------------------------------------------------------------------

def download_segment(url: str, desde: float, hasta: float, work: Path,
                     cfg: dict) -> Path:
    """Descarga ÚNICAMENTE el tramo pedido del video, no el video entero.

    Un documental de media hora pesa cientos de megas; el tramo de 40
    segundos que se necesita, unos pocos. yt-dlp sabe pedirle al servidor
    solo ese rango."""
    import yt_dlp

    from ytstudio.progress import notify

    work.mkdir(parents=True, exist_ok=True)
    ini = max(0.0, float(desde) - AIRE_SEGUNDOS)
    fin = float(hasta) + AIRE_SEGUNDOS
    altura = int((cfg.get("shorts") or {}).get("clip_height", 1080))

    notify(f"⬇ Descargando el tramo {ini:.0f}s–{fin:.0f}s del video "
           f"original (no el video entero)…")
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": float((cfg.get("reference") or {}).get(
            "timeout_seconds", 45)),
        "retries": 3, "fragment_retries": 5,
        # Se pide la mejor calidad que no pase de la altura objetivo: bajar
        # 4K para recortar a 1080 de alto es tirar tiempo y disco.
        "format": f"bv*[height<={altura}]+ba/b[height<={altura}]/b",
        "outtmpl": str(work / "origen.%(ext)s"),
        "download_ranges": yt_dlp.utils.download_range_func(None, [(ini, fin)]),
        # Sin esto, el corte cae en el fotograma clave más cercano y puede
        # irse varios segundos.
        "force_keyframes_at_cuts": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:  # noqa: BLE001 — se traduce y se vuelve a lanzar
        # Los errores de yt-dlp («ERROR: Unsupported URL: …») no le dicen
        # nada al creador. Se traducen y se le dice la salida: el modo
        # «pieza nueva» no necesita descargar nada.
        from ytstudio.derive import _limpiar_error_ytdlp
        raise RuntimeError(
            f"No se pudo traer el tramo del video original. "
            f"{_limpiar_error_ytdlp(e)} "
            f"Si el video no se puede descargar, cambia este Short al modo "
            f"«pieza nueva» y el programa lo creará desde cero.") from e

    videos = [p for p in work.glob("origen.*")
              if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if not videos:
        raise RuntimeError(
            "No se pudo descargar el tramo del video. Si el video es privado "
            "o tiene restricciones, no hay forma de recortarlo: usa el modo "
            "«pieza nueva» para ese Short.")
    return videos[0]


# ---------------------------------------------------------------------------
# 2) DE HORIZONTAL A VERTICAL
# ---------------------------------------------------------------------------

def reframe_filter(modo: str, w: int, h: int) -> str:
    """Cadena de filtros de ffmpeg que convierte cualquier entrada en un
    cuadro vertical de w x h."""
    if modo == "recorte_centrado":
        # Se queda con la franja central del ancho necesario para llenar el
        # cuadro vertical, y escala.
        return (f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})',"
                f"scale={w}:{h},setsar=1")
    # Por defecto: fondo con la propia imagen, ampliada y desenfocada, y el
    # fotograma entero encima. No se pierde ni un píxel del original.
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},gblur=sigma=28,eq=brightness=-0.08[bgb];"
        f"[fg]scale={w}:-2:force_original_aspect_ratio=decrease[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )


# ---------------------------------------------------------------------------
# 3) LOS SUBTÍTULOS DEL PROPIO VIDEO
# ---------------------------------------------------------------------------

def segment_cues(marcas: list, desde: float, hasta: float) -> list:
    """Los subtítulos del video original que caen dentro del tramo, con sus
    tiempos trasladados al inicio del recorte.

    Si una línea no trae fin (los subtítulos automáticos a menudo no lo
    dan), se usa el inicio de la siguiente."""
    dentro = []
    for i, m in enumerate(marcas):
        t = float(m.get("t") or 0)
        if t < desde - 0.5 or t > hasta:
            continue
        fin = m.get("t_fin")
        if fin is None:
            siguiente = marcas[i + 1]["t"] if i + 1 < len(marcas) else t + 3.0
            fin = min(float(siguiente), t + 6.0)
        texto = (m.get("texto") or "").strip()
        if not texto:
            continue
        dentro.append({"start": max(0.0, t - desde),
                       "end": max(0.3, min(float(fin), hasta) - desde),
                       "text": texto})
    # Sin solapes: un subtítulo no puede seguir en pantalla cuando ya entró
    # el siguiente.
    for a, b in zip(dentro, dentro[1:]):
        a["end"] = min(a["end"], b["start"])
    return [c for c in dentro if c["end"] > c["start"] + 0.15]


def _ass_time(s: float) -> str:
    h, r = divmod(max(0.0, s), 3600)
    m, sec = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}"


def write_ass(cues: list, path: Path, cfg: dict, gancho: str = "") -> Path:
    """Subtítulos quemados, dentro de la zona segura.

    `gancho` es el texto que aparece DESDE EL PRIMER FOTOGRAMA: la mayoría
    verá el Short sin sonido, y sin texto el gancho no existe."""
    from ytstudio.shorts import safe_margins, subtitle_margins

    sub = cfg.get("subtitles") or {}
    w, h = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    font = sub.get("font", "Arial")
    size = int(sub.get("font_size", 80))
    ml, mr, mv = subtitle_margins(cfg)
    margenes = safe_margins(cfg) or {}
    # El gancho va arriba, dentro de la zona segura
    mv_gancho = margenes.get("top", 390) if margenes else 120

    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,2,{ml},{mr},{mv},1
Style: Gancho,{font},{round(size * 1.15)},&H00FFFFFF,&H00FFFFFF,&H00101010,&HC8000000,-1,0,0,0,100,100,0,0,1,4,2,8,{ml},{mr},{mv_gancho},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    if (gancho or "").strip():
        # Desde el fotograma 1 y durante los primeros segundos: la regla de
        # doble pista del framework.
        eventos.append(
            f"Dialogue: 1,{_ass_time(0)},{_ass_time(3.2)},Gancho,,0,0,0,,"
            + gancho.strip().upper().replace("\n", "\\N"))
    for c in cues:
        eventos.append(
            f"Dialogue: 0,{_ass_time(c['start'])},{_ass_time(c['end'])},"
            f"Default,,0,0,0,," + c["text"].replace("\n", "\\N"))
    path.write_text(cabecera + "\n".join(eventos) + "\n", encoding="utf-8")
    return path


def write_srt(cues: list, path: Path) -> Path:
    """El SRT que se sube aparte: accesibilidad y texto indexable."""
    def t(s: float) -> str:
        h, r = divmod(max(0.0, s), 3600)
        m, sec = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int((sec % 1) * 1000):03d}"

    partes = []
    for i, c in enumerate(cues, 1):
        partes += [str(i), f"{t(c['start'])} --> {t(c['end'])}", c["text"], ""]
    path.write_text("\n".join(partes), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 4) EL MONTAJE
# ---------------------------------------------------------------------------

def render(project, cfg: dict, *, log=print) -> Path:
    """Produce el Short recortando el video original. Devuelve el archivo.

    No usa voz ni imágenes generadas: el gasto es tiempo de descarga y de
    montaje, nada más."""
    from ytstudio import eventlog, shorts
    from ytstudio.progress import notify
    from ytstudio.utils.media import (filter_path, normalize_loudness,
                                      probe_duration, run_ffmpeg)

    origen = project.get("clip_source") or {}
    url = (origen.get("url") or "").strip()
    if not url:
        raise RuntimeError(
            "Este Short está en modo recorte pero no guarda el enlace del "
            "video original. Vuelve a proponerlo desde la pestaña Shorts.")
    desde = float(origen.get("desde") or 0)
    hasta = float(origen.get("hasta") or (desde + 40))
    if hasta <= desde:
        hasta = desde + 40.0

    slug = getattr(project, "slug", None)
    work = project.path("broll") / "clip"
    work.mkdir(parents=True, exist_ok=True)

    # a) el tramo, y solo el tramo
    fuente = download_segment(url, desde, hasta, work, cfg)

    # El aire que se pidió de más se recorta ahora, ya en local y exacto.
    ini_real = max(0.0, desde - AIRE_SEGUNDOS)
    recorte_desde = desde - ini_real
    dur = hasta - desde

    # b) subtítulos del propio video, dentro de la zona segura
    marcas = origen.get("marcas") or []
    cues = segment_cues(marcas, desde, hasta)
    ass = write_ass(cues, project.path("subtitles", "subtitulos.ass"), cfg,
                    gancho=origen.get("texto_pantalla", ""))
    write_srt(cues, project.path("subtitles", "subtitulos.srt"))
    project.set("subtitle_cues", len(cues))
    notify(f"📝 {len(cues)} subtítulo(s) del video original, colocados en la "
           "zona segura.")

    # c) reencuadre vertical + subtítulos quemados, en una sola pasada
    modo = ((cfg.get("shorts") or {}).get("reencuadre")
            or REENCUADRE_POR_DEFECTO)
    if modo not in REENCUADRES:
        modo = REENCUADRE_POR_DEFECTO
    w, h = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    salida = project.path("final") / "video_final.mp4"
    filtros = (reframe_filter(modo, w, h)
               + f",ass='{filter_path(ass)}'")
    notify(f"🎬 Reencuadrando a vertical ({REENCUADRES[modo]['label']}) y "
           "quemando los subtítulos…")
    run_ffmpeg([
        "-ss", f"{recorte_desde:.3f}", "-i", str(fuente),
        "-t", f"{dur:.3f}",
        "-filter_complex", filtros,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(cfg["video"].get("fps", 30)),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(salida)], "recorte vertical")

    # d) la sonoridad, medida — un recorte hereda el volumen del original
    try:
        res = normalize_loudness(
            salida,
            target_i=float((cfg.get("audio") or {}).get("target_lufs", -14.0)),
            target_tp=float((cfg.get("audio") or {}).get("target_tp", -1.0)))
        if res:
            despues = (res.get("after") or {}).get("input_i")
            project.set("loudness", {"lufs": despues,
                                     "tp": (res.get("after") or {}).get("input_tp"),
                                     "gain_db": res.get("gain_db")})
            if res.get("gain_db"):
                notify(f"🔊 Sonoridad corregida a {despues:.1f} LUFS "
                       f"({res['gain_db']:+.1f} dB).")
    except Exception as e:
        eventlog.log("warn", f"No se pudo normalizar la sonoridad: {e}",
                     project=slug, phase="assembly")

    # e) un fotograma de verdad para la miniatura
    try:
        frame = project.path("broll") / "clip_portada.jpg"
        run_ffmpeg(["-ss", f"{min(2.0, dur / 3):.2f}", "-i", str(salida),
                    "-frames:v", "1", "-q:v", "3", str(frame)], "portada")
        _sync_scene(project, dur, frame.name)
    except Exception:
        _sync_scene(project, dur, None)

    # f) la misma auditoría que cualquier otro vertical
    try:
        resultado = shorts.audit_file(salida)
        project.set("shorts_audit", resultado)
        for linea in shorts.report_lines([resultado]):
            eventlog.log("info", linea, project=slug, phase="assembly")
        for problema in resultado["problemas"]:
            project.add_warning(problema)
    except Exception:
        pass

    project.set("final_video", str(salida))
    log(f"✔ Short recortado del original: {probe_duration(salida):.1f}s")
    return salida


def _sync_scene(project, duracion: float, portada: str | None) -> None:
    """Ajusta la escena única del recorte con la duración real y el fotograma
    de portada, para que los metadatos y la miniatura tengan de dónde tirar."""
    from ytstudio.phases.scenes import load_scenes, save_scenes
    try:
        escenas = load_scenes(project)
    except Exception:
        return
    if not escenas:
        return
    escenas[0]["duration"] = round(float(duracion), 2)
    if portada:
        escenas[0]["broll_image"] = portada
    save_scenes(project, escenas)
    project.set("total_duration", round(float(duracion), 2))
    project.set("scene_count", len(escenas))


# ---------------------------------------------------------------------------
# 5) EL ANDAMIAJE MÍNIMO para que el proyecto se comporte como los demás
# ---------------------------------------------------------------------------
# Un recorte no tiene concepto, ni guion, ni escenas que generar: el video ya
# existe. Pero los metadatos y la miniatura sí se quieren, y esas fases
# esperan encontrar un concepto y una lista de escenas. Se les da lo mínimo
# verdadero — sin inventar nada — y las fases que no aplican se marcan como
# hechas para que el orquestador las salte.

FASES_QUE_NO_APLICAN = ("ingest", "concept", "script", "scenes",
                        "voiceover", "broll", "music", "subtitles")


def scaffold(project, candidato: dict, source: dict) -> None:
    """Deja el proyecto listo para que «Generar video» solo tenga que
    recortar, poner metadatos y publicar."""
    from ytstudio.phases.scenes import save_scenes

    desde = float(candidato.get("desde") or 0)
    hasta = float(candidato.get("hasta") or (desde + 40))
    dur = max(5.0, hasta - desde)

    project.set("clip_source", {
        "url": source.get("url", ""),
        "titulo": source.get("titulo", ""),
        "desde": desde, "hasta": hasta,
        "texto_pantalla": candidato.get("texto_pantalla", ""),
        # Los subtítulos del tramo salen de aquí: se guardan para no tener
        # que volver a pedirlos a YouTube al generar.
        "marcas": [m for m in (source.get("marcas") or [])
                   if desde - 2 <= float(m.get("t") or 0) <= hasta + 2],
    })

    project.set("concept", {
        "title_options": [candidato.get("titulo_youtube")
                          or candidato.get("nombre", "")],
        "angle": candidato.get("idea", ""),
        "audience": source.get("audiencia") or "",
        "tone": source.get("tono") or "",
        "structure": ["Recorte del video original"],
        "duration_minutes": round(dur / 60, 2),
    })
    save_scenes(project, [{
        "id": 1, "section": "Recorte", "duration": round(dur, 2),
        "narration": candidato.get("idea", ""),
        "broll_prompt": f"recorte del video original ({desde:.0f}s-{hasta:.0f}s)",
        "broll_type": "video", "animation": "none", "on_screen_text":
            candidato.get("texto_pantalla", ""),
    }])
    project.set("total_duration", round(dur, 2))
    project.set("scene_count", 1)

    # El texto pegado documenta de dónde sale la pieza (y evita que la
    # ingesta se queje de un proyecto sin material si algún día se re-ejecuta).
    (project.path("input") / "texto.txt").write_text(
        f"Recorte del video original {source.get('url', '')}\n"
        f"Tramo {desde:.0f}s - {hasta:.0f}s\n\n"
        f"{candidato.get('idea', '')}\n", encoding="utf-8")
    project.set("has_text_input", True)

    for fase in FASES_QUE_NO_APLICAN:
        project.mark_phase(fase, "done", skipped="recorte del video original")
