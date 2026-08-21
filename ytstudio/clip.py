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

1. LA IMAGEN VA A SANGRE, sin bandas. En vertical se ve a pantalla completa
   y cualquier píxel que no sea imagen —banda negra, barra, fondo
   desenfocado— se lee como «esto es el recorte de otra cosa» justo en el
   segundo en que el espectador decide si desliza. Al pasar de 16:9 a 9:16
   sobra casi el 70% del ancho: sí, se pierde imagen, y esa pérdida es el
   precio correcto. Lo que se elige entonces es DÓNDE se recorta —izquierda,
   centro o derecha— porque el sujeto no siempre está centrado y el recorte
   centrado por defecto decapita cualquier plano que no lo esté.

   El fondo desenfocado sigue disponible para quien lo prefiera, pero ya no
   es el de por defecto: el framework lo desaconseja expresamente.

1bis. NADA A HUESO. Cuando un Short se monta con VARIOS fragmentos del largo,
   cada empalme corta tres cosas a la vez: la imagen, la voz y la cama
   musical que ya venía dentro del máster. La imagen aguanta un corte seco;
   la voz y la música, no. Por eso: fundido corto entre planos, fundido y
   una brecha de aire en la voz, y una cama musical CONTINUA por debajo que
   enmascara las discontinuidades del lecho musical de cada fragmento.

2. LOS SUBTÍTULOS SALEN DEL PROPIO VIDEO, con sus tiempos, y se colocan en
   la zona segura — por encima de la franja que la app reserva al enlace al
   video largo.

3. SE MIDE LA SONORIDAD, igual que en cualquier otro video del programa: un
   recorte hereda el volumen del original, que casi nunca está a -14 LUFS.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# Cómo pasar de horizontal a vertical
REENCUADRES = {
    "a_sangre": {
        "label": "A sangre (recomendado)",
        "hint": "La imagen ocupa los cuatro bordes, sin bandas. Se pierde "
                "lo que queda fuera del recorte: elige abajo POR DÓNDE se "
                "recorta según dónde esté el sujeto.",
    },
    "fondo_desenfocado": {
        "label": "Fondo desenfocado (no recomendado)",
        "hint": "El fotograma entero sobre su propia imagen ampliada y "
                "desenfocada. No pierde nada, pero deja zona muerta arriba "
                "y abajo, y eso se lee como «esto es el recorte de otra "
                "cosa». El framework lo desaconseja.",
    },
}
# 'recorte_centrado' era el nombre viejo del recorte a sangre por el centro:
# se sigue aceptando para no romper los proyectos y las configuraciones que
# ya lo tenían escrito.
ALIAS_REENCUADRE = {"recorte_centrado": "a_sangre"}
REENCUADRE_POR_DEFECTO = "a_sangre"

# POR DÓNDE se recorta. El recorte centrado por defecto es exactamente lo que
# decapita los planos cuyo sujeto no está en el centro, así que esto se elige
# MIRANDO el plano, no de oficio.
PUNTOS_RECORTE = {
    "izquierda": {"label": "Por la izquierda", "valor": 0.0},
    "centro": {"label": "Por el centro", "valor": 0.5},
    "derecha": {"label": "Por la derecha", "valor": 1.0},
}
PUNTO_POR_DEFECTO = "centro"

# EMPALMES (framework §3.2). Valores por defecto, ajustables en config.yaml.
FUNDIDO_DEFECTO = 0.35    # imagen: fundido entre planos (segundos)
BRECHA_DEFECTO = 0.25     # voz: aire entre fragmentos (segundos)
VOZ_FUNDIDO = 0.18        # voz: entrada y salida de cada fragmento
CAMA_DB_DEFECTO = -20     # cama musical continua, por debajo de la voz

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

def normalizar_modo(modo) -> str:
    """El modo de reencuadre válido, aceptando el nombre viejo."""
    modo = ALIAS_REENCUADRE.get(str(modo or ""), str(modo or ""))
    return modo if modo in REENCUADRES else REENCUADRE_POR_DEFECTO


def punto_a_fraccion(valor) -> float:
    """De «izquierda / centro / derecha» (o de un 0-1) a la fracción del
    ancho sobrante que queda a la IZQUIERDA del recorte: 0 pega el recorte
    al borde izquierdo, 1 al derecho."""
    if isinstance(valor, (int, float)):
        return min(max(float(valor), 0.0), 1.0)
    p = PUNTOS_RECORTE.get(str(valor or "").strip().lower())
    if p:
        return float(p["valor"])
    try:
        return min(max(float(valor), 0.0), 1.0)
    except (TypeError, ValueError):
        return float(PUNTOS_RECORTE[PUNTO_POR_DEFECTO]["valor"])


def reframe_filter(modo: str, w: int, h: int, punto="centro") -> str:
    """Cadena de filtros de ffmpeg que convierte cualquier entrada en un
    cuadro vertical de w x h.

    `punto` solo cuenta en el recorte a sangre: es por dónde se recorta."""
    modo = normalizar_modo(modo)
    if modo == "a_sangre":
        # La franja del ancho justo para llenar el cuadro vertical, movida al
        # punto elegido, y escalada con lanczos (el remuestreo bueno: aquí se
        # amplía casi un 78%, y con el filtro por defecto se nota).
        f = punto_a_fraccion(punto)
        return (f"crop=w='min(iw,ih*{w}/{h})':h='min(ih,iw*{h}/{w})':"
                f"x='(iw-ow)*{f:.4f}':y='(ih-oh)/2',"
                f"scale={w}:{h}:flags=lanczos,setsar=1")
    # Por defecto: fondo con la propia imagen, ampliada y desenfocada, y el
    # fotograma entero encima. No se pierde ni un píxel del original.
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},gblur=sigma=28,eq=brightness=-0.08[bgb];"
        f"[fg]scale={w}:-2:force_original_aspect_ratio=decrease[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )



def velo_png(path: Path, w: int, h: int, alpha: int = 200) -> Path:
    """VELO DEGRADADO para que el texto se lea sobre la imagen.

    Cuando la imagen va a sangre, el texto deja de caer sobre negro y cae
    sobre el vídeo. La solución NO es una caja opaca detrás del texto: eso
    reintroduce por la puerta de atrás la banda que acabamos de quitar. Se
    pone un velo oscuro DEGRADADO —fuerte en los extremos, transparente en el
    centro—, que apaga el fondo sin tapar el plano.

    Se dibuja con PIL (milisegundos) en vez de con el generador de ffmpeg,
    que para esto tarda segundos por fotograma."""
    from PIL import Image

    y1 = round(h * 0.469)          # hasta dónde llega el velo de arriba
    y2 = round(h * 0.531)          # desde dónde empieza el de abajo
    velo = Image.new("RGBA", (1, h), (0, 0, 0, 0))
    px = velo.load()
    for y in range(h):
        if y < y1:
            a = alpha * ((y1 - y) / y1) ** 0.62
        elif y > y2:
            a = alpha * ((y - y2) / max(1, h - y2)) ** 0.75
        else:
            a = 0.0
        px[0, y] = (0, 0, 0, int(round(min(alpha, max(0.0, a)))))
    velo.resize((w, h)).save(path)
    return path


def _ass_color(hex_color: str) -> str:
    """De «RRGGBB» al color de un subtítulo .ass, que va al revés (BGR)."""
    h = (hex_color or "FFFFFF").lstrip("#")
    if len(h) != 6:
        return "&H00FFFFFF"
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def tramos_de(origen: dict) -> list[dict]:
    """Los FRAGMENTOS del video largo con los que se monta este Short.

    Un Short puede salir de un solo tramo continuo (lo habitual) o de varios
    fragmentos encadenados, porque el momento bueno casi nunca está entero y
    seguido: el gancho suele estar enterrado a mitad del bloque. Los
    proyectos antiguos guardaban un único «desde/hasta»: se leen igual."""
    salida = []
    for t in (origen.get("tramos") or []):
        try:
            d, h = float(t.get("desde")), float(t.get("hasta"))
        except (TypeError, ValueError):
            continue
        if h > d:
            salida.append({"desde": round(d, 2), "hasta": round(h, 2),
                           "punto": t.get("punto") or ""})
    if salida:
        return salida
    desde = float(origen.get("desde") or 0)
    hasta = float(origen.get("hasta") or (desde + 40))
    if hasta <= desde:
        hasta = desde + 40.0
    return [{"desde": desde, "hasta": hasta,
             "punto": origen.get("punto_recorte") or ""}]


# ---------------------------------------------------------------------------
# LA CAMA MUSICAL CONTINUA
# ---------------------------------------------------------------------------

def _lra(path: Path) -> float | None:
    """Rango de sonoridad (LU) de una pista: cuánto separa lo suave de lo
    fuerte. Se mide, no se juzga de oído."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostdin", "-ss", "20", "-t", "45",
             "-i", str(path), "-af", "ebur128=peak=none", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120)
    except (subprocess.SubprocessError, OSError):
        return None
    valores = re.findall(r"LRA:\s*(-?[\d.]+)\s*LU", r.stderr or "")
    try:
        return float(valores[-1]) if valores else None
    except ValueError:
        return None


AUDIO_EXT = (".mp3", ".wav", ".m4a", ".flac", ".ogg")


def _pistas_del_mundo_sonoro(project, cfg: dict) -> list[Path]:
    """Dónde buscar la cama: PRIMERO la música del propio video largo.

    Quien salte del Short al video largo tiene que encontrarse el mismo mundo
    sonoro; si se estrena una pista nueva, el salto suena a otro canal. Solo
    si el largo no es un proyecto de este programa se recurre a la
    biblioteca local."""
    from ytstudio.config import ROOT
    from ytstudio.project import Project

    slug = (project.get("derived_from") or {}).get("slug") or ""
    if slug and Project.exists(slug):
        try:
            carpeta = Project(slug).path("music")
            pistas = [f for f in sorted(carpeta.glob("*"))
                      if f.suffix.lower() in AUDIO_EXT]
            if pistas:
                return pistas
        except Exception:  # noqa: BLE001 — sin música del largo, se sigue
            pass
    lib = ((cfg.get("providers") or {}).get("music") or {}).get(
        "library_dir", "assets/music")
    carpeta = Path(lib)
    if not carpeta.is_absolute():
        carpeta = ROOT / lib
    return [f for f in sorted(carpeta.glob("*"))
            if f.suffix.lower() in AUDIO_EXT] if carpeta.exists() else []


def elegir_cama(project, cfg: dict) -> Path | None:
    """La pista MÁS PLANA de las disponibles, o None si no hay ninguna.

    Se elige por medición: la de MENOR rango de sonoridad (LRA) es la única
    que se puede tender bajo cuarenta segundos sin que se note dónde empieza
    ni dónde da la vuelta."""
    pistas = _pistas_del_mundo_sonoro(project, cfg)[:8]
    if not pistas:
        return None
    if len(pistas) == 1:
        return pistas[0]
    medidas = [(_lra(f), f) for f in pistas]
    con_dato = [(v, f) for v, f in medidas if v is not None]
    if not con_dato:
        return pistas[0]
    return min(con_dato, key=lambda x: x[0])[1]


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
    from ytstudio.shorts import (accent_over_image, safe_margins,
                                 subtitle_margins)

    sub = cfg.get("subtitles") or {}
    scfg = cfg.get("shorts") or {}
    w, h = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    font = sub.get("font", "Arial")
    size = int(sub.get("font_size", 80))
    ml, mr, mv = subtitle_margins(cfg)
    margenes = safe_margins(cfg) or {}
    # El gancho va arriba, dentro de la zona segura
    mv_gancho = margenes.get("top", 390) if margenes else 120
    # EL COLOR DE ACENTO, ACLARADO. Un color de marca calibrado sobre fondo
    # negro se queda sin contraste en cuanto el texto pasa a ir sobre la
    # imagen — que es justo lo que ocurre al recortar a sangre.
    acento = (cfg.get("video") or {}).get("overlay_accent") or ""
    color_gancho = ("&H00FFFFFF" if not acento
                    or scfg.get("gancho_acento") is False
                    else _ass_color(accent_over_image(acento)))

    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,2,{ml},{mr},{mv},1
Style: Gancho,{font},{round(size * 1.15)},{color_gancho},{color_gancho},&H00101010,&HC8000000,-1,0,0,0,100,100,0,0,1,4,2,8,{ml},{mr},{mv_gancho},1

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

def cues_de_tramos(marcas: list, tramos: list, brecha: float) -> list:
    """Los subtítulos de TODOS los fragmentos, con sus tiempos ya trasladados
    a la línea de tiempo del Short montado (contando el aire que se deja
    entre fragmento y fragmento)."""
    cues, reloj = [], 0.0
    for t in tramos:
        dur = float(t["hasta"]) - float(t["desde"])
        for c in segment_cues(marcas, float(t["desde"]), float(t["hasta"])):
            cues.append({"start": c["start"] + reloj, "end": c["end"] + reloj,
                         "text": c["text"]})
        reloj += dur + brecha
    return cues


def _encode_fragment(fuente: Path, salida: Path, *, desde_local: float,
                     dur: float, modo: str, punto, w: int, h: int, fps,
                     fundido: float, primero: bool, ultimo: bool) -> Path:
    """Un fragmento ya vertical, con sus fundidos de imagen y de voz.

    Los fundidos de imagen se ponen SOLO en los empalmes: un fundido de
    entrada en el primer fragmento se comería el gancho (que tiene que estar
    desde el fotograma 1), y uno de salida en el último rompería el cierre de
    bucle. Los de voz van en todos: son de dos décimas y lo que quitan es el
    chasquido del empalme."""
    from ytstudio.utils.media import run_ffmpeg

    fd = max(0.05, fundido / 2.0)
    v = [reframe_filter(modo, w, h, punto)]
    if not primero:
        v.append(f"fade=t=in:st=0:d={fd:.2f}")
    if not ultimo:
        v.append(f"fade=t=out:st={max(0.0, dur - fd):.2f}:d={fd:.2f}")
    # El paso alto limpia la locución Y rebaja el retumbe de la cama vieja que
    # viaja dentro del fragmento, dejando sitio a la cama nueva.
    a = ["highpass=f=90", f"afade=t=in:st=0:d={VOZ_FUNDIDO:.2f}",
         f"afade=t=out:st={max(0.0, dur - VOZ_FUNDIDO):.2f}:d={VOZ_FUNDIDO:.2f}"]
    run_ffmpeg([
        "-ss", f"{desde_local:.3f}", "-i", str(fuente), "-t", f"{dur:.3f}",
        "-vf", ",".join(v), "-af", ",".join(a),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", str(salida)], "fragmento vertical")
    return salida


def _encode_brecha(salida: Path, *, segundos: float, w: int, h: int,
                   fps) -> Path:
    """El aire entre fragmentos: negro y silencio, con los mismos ajustes que
    los fragmentos para que se puedan pegar sin recodificar."""
    from ytstudio.utils.media import run_ffmpeg

    run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", f"{segundos:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", str(salida)], "brecha entre fragmentos")
    return salida


def _concat(partes: list, salida: Path, work: Path) -> Path:
    """Pega los fragmentos SIN recodificar (todos salieron con los mismos
    ajustes, así que se pueden encadenar tal cual)."""
    from ytstudio.utils.media import run_ffmpeg

    lista = work / "lista.txt"
    lista.write_text("".join(
        "file '" + str(f.resolve()).replace("\\", "/").replace("'", "'\\''")
        + "'\n" for f in partes), encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lista),
                "-c", "copy", str(salida)], "unir los fragmentos")
    return salida


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

    scfg = cfg.get("shorts") or {}
    modo = normalizar_modo(scfg.get("reencuadre"))
    punto_global = (origen.get("punto_recorte")
                    or scfg.get("punto_recorte") or PUNTO_POR_DEFECTO)
    fundido = float(scfg.get("fundido", FUNDIDO_DEFECTO) or 0)
    brecha = float(scfg.get("brecha", BRECHA_DEFECTO) or 0)
    w, h = int(cfg["video"]["width"]), int(cfg["video"]["height"])
    fps = cfg["video"].get("fps", 30)

    slug = getattr(project, "slug", None)
    work = project.path("broll") / "clip"
    work.mkdir(parents=True, exist_ok=True)

    tramos = tramos_de(origen)
    if len(tramos) == 1:
        brecha = 0.0

    # a) los tramos, y solo los tramos
    partes: list[Path] = []
    for i, tr in enumerate(tramos):
        desde, hasta = float(tr["desde"]), float(tr["hasta"])
        dur = hasta - desde
        sub = work / f"t{i + 1}"
        sub.mkdir(parents=True, exist_ok=True)
        if len(tramos) > 1:
            notify(f"⬇ Fragmento {i + 1} de {len(tramos)} "
                   f"({desde:.0f}s-{hasta:.0f}s)…")
        fuente = download_segment(url, desde, hasta, sub, cfg)
        # El aire que se pidió de más se recorta ahora, ya en local y exacto.
        desde_local = desde - max(0.0, desde - AIRE_SEGUNDOS)
        if i:
            partes.append(_encode_brecha(work / f"aire{i}.mp4",
                                         segundos=brecha, w=w, h=h, fps=fps))
        partes.append(_encode_fragment(
            fuente, work / f"f{i + 1}.mp4", desde_local=desde_local, dur=dur,
            modo=modo, punto=(tr.get("punto") or punto_global), w=w, h=h,
            fps=fps, fundido=fundido, primero=(i == 0),
            ultimo=(i == len(tramos) - 1)))

    total = sum(float(t["hasta"]) - float(t["desde"]) for t in tramos) \
        + brecha * (len(tramos) - 1)

    # b) subtítulos del propio video, dentro de la zona segura
    marcas = origen.get("marcas") or []
    cues = cues_de_tramos(marcas, tramos, brecha)
    ass = write_ass(cues, project.path("subtitles", "subtitulos.ass"), cfg,
                    gancho=origen.get("texto_pantalla", ""))
    write_srt(cues, project.path("subtitles", "subtitulos.srt"))
    project.set("subtitle_cues", len(cues))
    notify(f"📝 {len(cues)} subtítulo(s) del video original, colocados en la "
           "zona segura.")

    # c) pegar los fragmentos (sin recodificar: ya salieron iguales)
    montaje = work / "montaje.mp4"
    if len(partes) == 1:
        montaje = partes[0]
    else:
        _concat(partes, montaje, work)
        notify(f"🎞 {len(tramos)} fragmentos unidos con fundidos de "
               f"{fundido:.2f}s y {brecha:.2f}s de aire entre ellos.")

    # d) velo, subtítulos quemados y cama musical continua, en una pasada
    salida = project.path("final") / "video_final.mp4"
    entradas = ["-i", str(montaje)]
    cadena_v = "[0:v]"
    if scfg.get("velo", True) and modo == "a_sangre":
        velo = velo_png(work / "velo.png", w, h)
        entradas += ["-i", str(velo)]
        cadena_v = "[0:v][1:v]overlay=0:0,"

    cama = None
    quiere_cama = str(scfg.get("cama_musical", "auto")).lower()
    if quiere_cama not in ("no", "false", "none") and (
            quiere_cama != "auto" or len(tramos) > 1):
        cama = elegir_cama(project, cfg)
        if cama is None and len(tramos) > 1:
            notify("🎵 Sin pista para la cama musical: los empalmes se oirán "
                   "más. Deja un MP3 en la carpeta de música del video largo "
                   "o en assets/music.")

    filtros = [f"{cadena_v}ass='{filter_path(ass)}'[vout]"]
    idx_cama = 2 if len(entradas) > 2 else 1
    if cama is not None:
        # La cama se repite en bucle hasta cubrir la pieza: una sola pista,
        # continua, sin un corte (y el corte del final lo da el fundido).
        entradas += ["-stream_loop", "-1", "-i", str(cama)]
        fade = min(1.5, max(0.4, total * 0.05))
        cama_db = float(scfg.get("cama_db", CAMA_DB_DEFECTO))
        filtros += [
            "[0:a]asplit=2[voz][sc]",
            f"[{idx_cama}:a]volume={cama_db:g}dB,"
            f"afade=t=in:st=0:d={fade:.2f},"
            f"afade=t=out:st={max(0.0, total - fade):.2f}:d={fade:.2f}[cama]",
            # Ducking: la cama se aparta debajo de la voz y vuelve en cuanto
            # hay hueco. Sin esto, o no se oye la cama o no se oye la voz.
            "[cama][sc]sidechaincompress=threshold=0.05:ratio=6:attack=25:"
            "release=320[camad]",
            "[voz][camad]amix=inputs=2:duration=first:dropout_transition=0"
            ":normalize=0[aout]",
        ]
        # Con la cama en bucle infinito hay que decirle dónde parar.
        mapa_a = ["-map", "[aout]", "-t", f"{total:.3f}"]
    else:
        mapa_a = ["-map", "0:a?"]

    notify(f"🎬 Montando el vertical ({REENCUADRES[modo]['label']}"
           + (f", recorte {punto_global}" if modo == "a_sangre" else "")
           + ") y quemando los subtítulos…")
    run_ffmpeg([
        *entradas,
        "-filter_complex", ";".join(filtros),
        "-map", "[vout]", *mapa_a,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(salida)], "montaje vertical")

    if cama is not None:
        project.set("cama_musical", cama.name)
        notify(f"🎵 Cama musical continua: {cama.name} (la pista más plana de "
               "las disponibles), por debajo de la voz y sin un solo corte.")
        if total > 60:
            project.add_warning(
                "El Short pasa de 60 segundos y lleva cama musical: por "
                "encima del minuto una reclamación de copyright NO desmoneta, "
                "BLOQUEA el video en todo el mundo. Usa solo música propia o "
                "de la biblioteca de YouTube, y archiva la licencia.")

    # e) la sonoridad, medida — un recorte hereda el volumen del original
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

    # f) un fotograma de verdad para la miniatura
    try:
        frame = project.path("broll") / "clip_portada.jpg"
        run_ffmpeg(["-ss", f"{min(2.0, total / 3):.2f}", "-i", str(salida),
                    "-frames:v", "1", "-q:v", "3", str(frame)], "portada")
        _sync_scene(project, total, frame.name)
    except Exception:
        _sync_scene(project, total, None)

    # g) la misma auditoría que cualquier otro vertical
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

    # Los FRAGMENTOS con los que se monta: uno solo (lo habitual) o varios
    # encadenados. De ellos salen la duración real de la pieza y los
    # subtítulos que hay que guardar.
    tramos = tramos_de({"tramos": candidato.get("tramos") or [],
                        "desde": candidato.get("desde"),
                        "hasta": candidato.get("hasta"),
                        "punto_recorte": candidato.get("punto_recorte") or ""})
    desde = min(t["desde"] for t in tramos)
    hasta = max(t["hasta"] for t in tramos)
    # La duración es la SUMA de los fragmentos más el aire entre ellos, no la
    # distancia entre el primer segundo y el último: con dos fragmentos
    # separados por diez minutos de video, esa distancia no significa nada.
    dur = max(5.0, sum(t["hasta"] - t["desde"] for t in tramos)
              + BRECHA_DEFECTO * (len(tramos) - 1))

    def _dentro(m) -> bool:
        t = float(m.get("t") or 0)
        return any(x["desde"] - 2 <= t <= x["hasta"] + 2 for x in tramos)

    project.set("clip_source", {
        "url": source.get("url", ""),
        "titulo": source.get("titulo", ""),
        "desde": desde, "hasta": hasta,
        "tramos": tramos,
        "punto_recorte": candidato.get("punto_recorte") or "",
        "texto_pantalla": candidato.get("texto_pantalla", ""),
        # Los subtítulos de los tramos salen de aquí: se guardan para no
        # tener que volver a pedirlos a YouTube al generar.
        "marcas": [m for m in (source.get("marcas") or []) if _dentro(m)],
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
        "broll_prompt": "recorte del video original ("
            + ", ".join(f"{t['desde']:.0f}s-{t['hasta']:.0f}s" for t in tramos)
            + ")",
        "broll_type": "video", "animation": "none", "on_screen_text":
            candidato.get("texto_pantalla", ""),
    }])
    project.set("total_duration", round(dur, 2))
    project.set("scene_count", 1)

    # El texto pegado documenta de dónde sale la pieza (y evita que la
    # ingesta se queje de un proyecto sin material si algún día se re-ejecuta).
    (project.path("input") / "texto.txt").write_text(
        f"Recorte del video original {source.get('url', '')}\n"
        + "".join(f"Tramo {t['desde']:.0f}s - {t['hasta']:.0f}s\n"
                  for t in tramos) + "\n"
        f"{candidato.get('idea', '')}\n", encoding="utf-8")
    project.set("has_text_input", True)

    for fase in FASES_QUE_NO_APLICAN:
        project.mark_phase(fase, "done", skipped="recorte del video original")
