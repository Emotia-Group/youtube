"""Vídeo vertical corto: ZONA SEGURA y AUDITORÍA TÉCNICA.

Aquí vive lo que el Framework Universal de Shorts exige y el montaje no
comprobaba: dónde puede ir el texto sin que la interfaz de la app lo tape, y
la medición real del archivo terminado (resolución, códecs, duración y
sonoridad) contra las especificaciones de publicación.

Dos ideas que conviene tener claras al leer esto:

1. LA FRANJA INFERIOR NO ES NUESTRA. En el feed de Shorts, la app dibuja
   encima del vídeo: arriba el título, a la derecha la columna de botones y
   ABAJO el handle del canal y el ENLACE A VÍDEO RELACIONADO — que es el
   único mecanismo por el que una vista de Short se convierte en un clic al
   vídeo largo. Quemar los subtítulos ahí es competir contra la propia
   herramienta de conversión.

2. LOS DECIBELIOS NO MIDEN VOLUMEN. Un dB es un pico instantáneo; el volumen
   percibido se mide en LUFS. Y la normalización de la plataforma es
   ASIMÉTRICA: BAJA lo que suena alto, pero NO SUBE lo que suena bajo. Un
   archivo a -22 LUFS suena a una fracción del anterior del feed y nadie lo
   compensa. Por eso el objetivo (-14 LUFS) se MIDE, no se estima.

Las cifras de la zona segura son la intersección conservadora de las fuentes
públicas: la plataforma no publica un mapa de píxeles oficial.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

# ---------------------------------------------------------------------------
# ZONA SEGURA (referida al lienzo canónico de 1080x1920)
# ---------------------------------------------------------------------------
# Rectángulo útil de 900x1100 px, centrado horizontalmente y ligeramente por
# encima del centro vertical. Todo el texto crítico vive dentro.
SAFE_BASE = (1080, 1920)
SAFE_ZONE = {
    "width": 900,      # ancho útil
    "height": 1100,    # alto útil
    "top": 390,        # título del Short y elementos de la interfaz
    "bottom": 430,     # handle del canal + ENLACE A VÍDEO RELACIONADO
    "side": 90,        # aire lateral (la columna de botones vive a la derecha)
}

# Por debajo de esta proporción alto/ancho el vídeo no va al feed de Shorts
# (4:5 y 1:1 son formatos de anuncio, con otra interfaz encima): la zona
# segura de Shorts no aplica y no se toca nada.
SHORTS_RATIO_MIN = 1.7


def frame_size(cfg: dict) -> tuple[int, int]:
    video = cfg.get("video") or {}
    return int(video.get("width") or 1920), int(video.get("height") or 1080)


def is_shorts_frame(cfg: dict) -> bool:
    """¿El encuadre de este proyecto es el del feed de Shorts (9:16)?"""
    w, h = frame_size(cfg)
    return bool(w and h and h > w and h / w >= SHORTS_RATIO_MIN)


def safe_margins(cfg: dict) -> dict | None:
    """Márgenes de la zona segura en píxeles REALES del proyecto, o None si el
    formato no es el del feed de Shorts.

    Se escalan desde el lienzo canónico: un 1080x1920 los usa tal cual, y un
    vertical de otra resolución (720x1280) recibe los mismos márgenes en
    proporción, no en píxeles fijos."""
    if not is_shorts_frame(cfg):
        return None
    w, h = frame_size(cfg)
    kx, ky = w / SAFE_BASE[0], h / SAFE_BASE[1]
    return {
        "top": round(SAFE_ZONE["top"] * ky),
        "bottom": round(SAFE_ZONE["bottom"] * ky),
        "side": round(SAFE_ZONE["side"] * kx),
        "width": round(SAFE_ZONE["width"] * kx),
        "height": round(SAFE_ZONE["height"] * ky),
    }


# ---------------------------------------------------------------------------
# MINIATURA VERTICAL (framework §4.1)
# ---------------------------------------------------------------------------
# La miniatura no aparece en el feed deslizable, y por eso se da por hecho que
# da igual. No da igual: es lo que decide el clic en la PESTAÑA DE SHORTS del
# canal, en la búsqueda, en la portada y en el feed de suscripciones. Y tiene
# su propia zona segura, distinta a la del video: la parrilla del canal
# recorta y superpone en otros sitios.
MINIATURA_ZONA = {"top": 390, "bottom": 390, "left": 90, "right": 120}
MINIATURA_MAX_BYTES = 2 * 1024 * 1024
# LA REGLA QUE DECIDE SI SIRVE: la miniatura no se ve nunca a 1080 px de
# ancho, se ve a unos 150 en la parrilla del canal. A ese tamaño el
# presupuesto real es una cara y tres o cuatro palabras: nada más entra.
MINIATURA_PRUEBA_PX = 150
MINIATURA_PALABRAS_MAX = 4


def miniatura_margins(w: int, h: int) -> dict:
    """Zona segura de la miniatura en píxeles reales, escalada desde el
    lienzo canónico de 1080x1920."""
    kx, ky = w / SAFE_BASE[0], h / SAFE_BASE[1]
    return {"top": round(MINIATURA_ZONA["top"] * ky),
            "bottom": round(MINIATURA_ZONA["bottom"] * ky),
            "left": round(MINIATURA_ZONA["left"] * kx),
            "right": round(MINIATURA_ZONA["right"] * kx)}


def subtitle_margins(cfg: dict) -> tuple[int, int, int]:
    """(MarginL, MarginR, MarginV) para el .ass de subtítulos quemados.

    En horizontal se mantiene el margen de siempre. En vertical 9:16 los
    subtítulos SUBEN por encima de la franja inferior reservada al enlace a
    vídeo relacionado — que es exactamente donde los pone por defecto casi
    cualquier editor, y donde estorban más.

    `subtitles.safe_zone: false` en la configuración desactiva la corrección
    (vuelve al comportamiento anterior a la v0.63.0)."""
    sub = cfg.get("subtitles") or {}
    base_side = int(sub.get("margin_side") or 80)
    base_v = int(sub.get("margin_v") or 60)
    margins = safe_margins(cfg)
    if not margins or sub.get("safe_zone") is False:
        return base_side, base_side, base_v
    return (max(base_side, margins["side"]), max(base_side, margins["side"]),
            max(base_v, margins["bottom"]))


# ---------------------------------------------------------------------------
# AUDITORÍA TÉCNICA del archivo terminado
# ---------------------------------------------------------------------------
SPEC = {
    "width": 1080,
    "height": 1920,
    "lufs_target": -14.0,
    "lufs_tolerance": 1.5,     # aviso fuera de -15,5 / -12,5
    "lufs_critical": 3.0,      # problema serio fuera de -17 / -11
    "tp_max": -1.0,
    "tp_tolerance": 0.5,
    "lra_max": 14.0,
    "vcodec_preferred": "h264",
    "acodec_preferred": "aac",
    "sample_rate": 48000,
    "duration_max": 180.0,     # 3 min: por encima deja de ser Short
    "duration_music_risk": 60.0,
    "duration_sweet_min": 20.0,
    "duration_sweet_max": 75.0,
    # Bitrate de publicación: 8-12 Mbps (objetivo 10). Por debajo de 6 la
    # plataforma recomprime una imagen que ya venía blanda y se nota.
    "bitrate_min": 8_000_000,
    "bitrate_max": 12_000_000,
    "bitrate_low": 6_000_000,
}

# BANDAS Y ZONA MUERTA (framework §3.1: la imagen ocupa los cuatro bordes).
# Cuánta superficie puede faltar antes de decir algo: por debajo del 2% es
# ruido de medición; a partir del 5% son bandas de verdad.
BANDA_AVISO = 0.02
BANDA_PROBLEMA = 0.05

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe(path) -> dict | None:
    """Duración, resolución, códecs, fps y muestreo de audio."""
    r = _run(["ffprobe", "-v", "error", "-print_format", "json",
              "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

    info = {"duration": None, "width": None, "height": None, "fps": None,
            "vcodec": None, "acodec": None, "sample_rate": None,
            "bitrate": None, "has_audio": False}
    try:
        info["duration"] = float(d.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        pass
    try:
        info["bitrate"] = int(d.get("format", {}).get("bit_rate"))
    except (TypeError, ValueError):
        pass

    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and info["vcodec"] is None:
            info["vcodec"] = s.get("codec_name")
            info["width"] = s.get("width")
            info["height"] = s.get("height")
            fr = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/0"
            try:
                num, den = fr.split("/")
                info["fps"] = (round(float(num) / float(den), 2)
                               if float(den) else None)
            except (ValueError, ZeroDivisionError):
                pass
        elif s.get("codec_type") == "audio" and info["acodec"] is None:
            info["acodec"] = s.get("codec_name")
            info["has_audio"] = True
            try:
                info["sample_rate"] = int(s.get("sample_rate"))
            except (TypeError, ValueError):
                pass
    return info


def loudness(path) -> dict | None:
    """Sonoridad integrada (LUFS), pico real (dBTP) y rango (LU) MEDIDOS."""
    r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn",
              "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    blob = r.stderr or ""
    out: dict = {}
    for key in ("input_i", "input_tp", "input_lra"):
        m = re.search(r'"%s"\s*:\s*"?(-?[\d.]+|-?inf)"?' % key, blob)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                out[key] = None
    return out or None


def _luma(rgb: tuple[int, int, int]) -> float:
    """Claridad percibida (0 negro, 1 blanco). El ojo ve el verde mucho más
    claro que el azul: por eso no es la media de los tres canales."""
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def accent_over_image(hex_color: str, min_luma: float = 0.62) -> str:
    """ACLARA el color de acento lo justo para que se lea SOBRE IMAGEN.

    Un color de marca calibrado sobre fondo negro casi siempre se queda sin
    contraste cuando el texto deja de ir sobre negro y pasa a ir sobre el
    vídeo (framework §3.1). Aquí se mezcla con blanco hasta alcanzar una
    claridad mínima —el tono se conserva, solo sube la luz— y el color
    original se reserva para los fondos planos."""
    h = (hex_color or "").strip().lstrip("#")
    if len(h) != 6:
        return (hex_color or "").strip() or "E8C46B"
    try:
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return h
    luz = _luma(rgb)  # type: ignore[arg-type]
    if luz >= min_luma:
        return h.upper()
    t = (min_luma - luz) / (1.0 - luz)
    claro = tuple(round(c + t * (255 - c)) for c in rgb)
    return "".join(f"{c:02X}" for c in claro)


def detect_bands(path, info: dict | None = None) -> dict | None:
    """¿La imagen llega a los cuatro bordes, o hay bandas y zona muerta?

    El framework (§3.1) no admite bandas: en vertical se ve a pantalla
    completa y cualquier píxel que no sea imagen se lee como «esto es el
    recorte de otra cosa» justo en el segundo en que el espectador decide si
    desliza.

    Se mide con `cropdetect` en TRES puntos del vídeo y se QUEDA CON EL
    RECORTE MÁS GRANDE de los tres, no con el más pequeño: un plano oscuro o
    un fundido a negro engañarían a una sola medición y harían saltar el
    aviso en un vídeo perfecto. Devuelve {'width', 'height', 'perdido'} —
    `perdido` es la fracción de superficie que no es imagen— o None si no se
    pudo medir."""
    info = info or probe(path)
    if not info or not info.get("width") or not info.get("height"):
        return None
    W, H = int(info["width"]), int(info["height"])
    dur = float(info.get("duration") or 0)
    puntos = [dur * f for f in (0.2, 0.5, 0.8)] if dur > 4 else [0.0]
    mejor_w = mejor_h = 0
    for t in puntos:
        r = _run(["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{t:.2f}",
                  "-t", "1.5", "-i", str(path), "-vf",
                  "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"])
        for m in re.finditer(r"crop=(\d+):(\d+):", r.stderr or ""):
            mejor_w = max(mejor_w, int(m.group(1)))
            mejor_h = max(mejor_h, int(m.group(2)))
    if not mejor_w or not mejor_h:
        return None
    mejor_w, mejor_h = min(mejor_w, W), min(mejor_h, H)
    return {"width": mejor_w, "height": mejor_h,
            "perdido": max(0.0, 1.0 - (mejor_w * mejor_h) / float(W * H))}


def evaluate(info: dict | None, loud: dict | None,
             bands: dict | None = None) -> tuple[list, list, list]:
    """Devuelve (problemas, avisos, correctos) en lenguaje llano."""
    bad: list[str] = []
    warn: list[str] = []
    ok: list[str] = []

    if info is None:
        return (["No se pudo leer el archivo (¿formato no soportado?)"], [], [])

    # --- Resolución y aspecto
    w, h = info.get("width"), info.get("height")
    if w and h:
        if (w, h) == (SPEC["width"], SPEC["height"]):
            ok.append(f"Resolución {w}x{h}")
        elif h > w:
            warn.append(f"Resolución {w}x{h} — vertical, pero no 1080x1920. "
                        "Reescalar evita que la plataforma lo recomprima")
        else:
            bad.append(f"Resolución {w}x{h} — NO es vertical: no se "
                       "clasificará como Short")

    # --- Duración
    dur = info.get("duration")
    if dur:
        if dur > SPEC["duration_max"]:
            bad.append(f"Duración {dur:.1f}s — supera los 3 min: no se "
                       "clasificará como Short")
        elif dur > SPEC["duration_music_risk"]:
            warn.append(f"Duración {dur:.1f}s — supera 60 s: una reclamación "
                        "de copyright BLOQUEA el vídeo en todo el mundo (no "
                        "lo desmoneta: lo bloquea). Solo audio propio o de la "
                        "biblioteca de la plataforma")
        elif SPEC["duration_sweet_min"] <= dur <= SPEC["duration_sweet_max"]:
            ok.append(f"Duración {dur:.1f}s")
        else:
            warn.append(f"Duración {dur:.1f}s — fuera de la banda habitual "
                        f"({SPEC['duration_sweet_min']:.0f}-"
                        f"{SPEC['duration_sweet_max']:.0f}s)")

    # --- Códecs
    vc = (info.get("vcodec") or "").lower()
    if vc == SPEC["vcodec_preferred"]:
        ok.append("Códec de vídeo H.264")
    elif vc:
        warn.append(f"Códec de vídeo '{vc}' — se acepta, pero H.264 es la "
                    "opción segura para compatibilidad universal")

    ac = (info.get("acodec") or "").lower()
    if ac and ac != SPEC["acodec_preferred"]:
        warn.append(f"Códec de audio '{ac}' — se recomienda AAC-LC")

    sr = info.get("sample_rate")
    if sr and sr != SPEC["sample_rate"]:
        warn.append(f"Muestreo de audio {sr} Hz — se recomienda 48000 Hz")

    br = info.get("bitrate")
    if br:
        if br < SPEC["bitrate_low"]:
            warn.append(f"Bitrate {br / 1e6:.1f} Mbps — bajo para publicar "
                        f"(objetivo {SPEC['bitrate_min'] / 1e6:.0f}-"
                        f"{SPEC['bitrate_max'] / 1e6:.0f} Mbps). La "
                        "plataforma recomprime encima: la imagen se ve "
                        "blanda justo en los planos con movimiento")
        elif br <= SPEC["bitrate_max"] * 1.6:
            ok.append(f"Bitrate {br / 1e6:.1f} Mbps")

    # --- Bandas y zona muerta: la imagen tiene que llegar a los bordes
    if bands and bands.get("perdido") is not None:
        perdido = float(bands["perdido"])
        if perdido >= BANDA_PROBLEMA:
            bad.append(
                f"Hay BANDAS: la imagen ocupa {bands['width']}x"
                f"{bands['height']} y deja fuera el {perdido * 100:.0f}% del "
                "cuadro. En vertical se ve a pantalla completa y una banda "
                "se lee como «esto es el recorte de otra cosa» en el mismo "
                "segundo en que se decide si deslizar. Reencuadrar a sangre")
        elif perdido >= BANDA_AVISO:
            warn.append(
                f"Puede haber bandas: la imagen ocupa {bands['width']}x"
                f"{bands['height']} ({perdido * 100:.0f}% del cuadro sin "
                "imagen). Míralo: en vertical no debería sobrar ni un píxel")
        else:
            ok.append("La imagen llega a los cuatro bordes")

    if not info.get("has_audio"):
        bad.append("El archivo NO tiene pista de audio")

    # --- Sonoridad: la comprobación más importante
    if loud:
        i = loud.get("input_i")
        tp = loud.get("input_tp")
        lra = loud.get("input_lra")

        if i is not None:
            delta = i - SPEC["lufs_target"]
            if abs(delta) <= SPEC["lufs_tolerance"]:
                ok.append(f"Sonoridad {i:.1f} LUFS")
            elif delta < -SPEC["lufs_critical"]:
                bad.append(
                    f"Sonoridad {i:.1f} LUFS — {abs(delta):.1f} dB POR DEBAJO "
                    "del objetivo (-14). La plataforma NO sube lo que suena "
                    "bajo: sonará a una fracción del volumen del vídeo "
                    "anterior del feed. Normalizar antes de publicar")
            elif delta > SPEC["lufs_critical"]:
                warn.append(
                    f"Sonoridad {i:.1f} LUFS — por encima del objetivo (-14). "
                    "La plataforma lo bajará: pierdes rango dinámico sin "
                    "ganar volumen")
            else:
                warn.append(f"Sonoridad {i:.1f} LUFS — ajustar a -14")

        if tp is not None:
            if tp > SPEC["tp_max"] + SPEC["tp_tolerance"]:
                bad.append(f"Pico real {tp:.1f} dBTP — por encima de -1,0: "
                           "riesgo de distorsión tras la compresión de la "
                           "plataforma")
            elif tp < -6.0:
                warn.append(f"Pico real {tp:.1f} dBTP — muy bajo; suele "
                            "acompañar a una señal poco procesada")
            else:
                ok.append(f"Pico real {tp:.1f} dBTP")

        if lra is not None and lra > SPEC["lra_max"]:
            warn.append(f"Rango de sonoridad {lra:.1f} LU — muy amplio: las "
                        "partes suaves se perderán en un móvil en la calle")
    else:
        warn.append("No se pudo medir la sonoridad")

    return bad, warn, ok


def audit_file(path) -> dict:
    """Audita UN archivo y devuelve su ficha con problemas y avisos."""
    info = probe(path)
    loud = loudness(path) if info and info.get("has_audio") else None
    bands = detect_bands(path, info) if info else None
    bad, warn, ok = evaluate(info, loud, bands)
    return {"archivo": os.path.basename(str(path)), "ruta": str(path),
            "info": info, "sonoridad": loud, "bandas": bands,
            "problemas": bad, "avisos": warn, "correcto": ok}


def gather(paths) -> list[str]:
    """Expande carpetas a los archivos de vídeo que contienen."""
    files: list[str] = []
    for a in paths:
        a = str(a)
        if os.path.isdir(a):
            for n in sorted(os.listdir(a)):
                if os.path.splitext(n)[1].lower() in VIDEO_EXT:
                    files.append(os.path.join(a, n))
        elif os.path.isfile(a):
            files.append(a)
    return files


def audit_paths(paths) -> list[dict]:
    return [audit_file(f) for f in gather(paths)]


def summary_line(result: dict) -> str:
    """Ficha técnica de una línea: duración, tamaño, fps, códec, sonoridad."""
    i = result.get("info") or {}
    s = result.get("sonoridad") or {}
    bits = []
    if i.get("duration"):
        bits.append(f"{i['duration']:.1f}s")
    if i.get("width"):
        bits.append(f"{i['width']}x{i['height']}")
    if i.get("fps"):
        bits.append(f"{i['fps']:g}fps")
    if i.get("vcodec"):
        bits.append(str(i["vcodec"]))
    if s.get("input_i") is not None:
        bits.append(f"{s['input_i']:.1f} LUFS")
    if s.get("input_tp") is not None:
        bits.append(f"{s['input_tp']:.1f} dBTP")
    return "  ·  ".join(bits)


def report_lines(results: list[dict]) -> list[str]:
    """Informe legible (el mismo texto en la consola y en la interfaz)."""
    n_bad = sum(1 for r in results if r["problemas"])
    out = ["=" * 74,
           f"AUDITORÍA DE VÍDEO VERTICAL — {len(results)} archivo(s)",
           "=" * 74]
    for r in results:
        out += ["", f"■ {r['archivo']}", "  " + summary_line(r)]
        out += [f"  [PROBLEMA] {m}" for m in r["problemas"]]
        out += [f"  [AVISO]    {m}" for m in r["avisos"]]
        if not r["problemas"] and not r["avisos"]:
            out.append("  [OK]       Cumple todas las especificaciones medibles")
    out += ["", "=" * 74,
            f"RESUMEN: {n_bad} de {len(results)} archivo(s) con problemas que "
            "conviene corregir antes de publicar.",
            "=" * 74, "",
            "Lo que una medición NO puede ver — míralo tú en el archivo:",
            "  · Texto en pantalla desde el fotograma 1 (regla de doble pista:",
            "    el gancho tiene que entenderse con el sonido apagado)",
            "  · Que los subtítulos no tapen la franja inferior",
            "  · Que haya UN cierre con llamada a la acción, no un corte seco",
            "  · Que el primer fotograma prometa algo",
            "  · Que la imagen llegue a los CUATRO BORDES: ni bandas, ni",
            "    barras, ni fondo desenfocado, ni un solo píxel muerto",
            "  · Que ningún empalme sea un corte a hueso: fundidos de",
            "    0,3-0,4 s entre planos y una cama musical continua debajo"]
    return out


# ---------------------------------------------------------------------------
# METADATOS DE SHORT y LISTA DE COMPROBACIÓN antes de publicar
# ---------------------------------------------------------------------------
# Las reglas vienen del framework y de la documentación de la plataforma:
#
# - Título de 40-70 caracteres con la palabra clave al principio. En el feed
#   casi no se lee (el video simplemente empieza), pero en BÚSQUEDA es lo que
#   rankea.
# - SIN el hashtag de Shorts: la clasificación es automática por proporción y
#   duración. Ese hashtag es un mito residual de 2021 que solo ocupa sitio.
# - 2-3 hashtags temáticos. La plataforma muestra hasta 3; pasarse de 60 hace
#   que se ignoren TODOS.
# - 3-5 tags, y solo para variantes ortográficas: la documentación oficial
#   dice literalmente que juegan un papel mínimo en el descubrimiento.
# - La primera línea de la descripción es lo único visible sin desplegar:
#   ahí va el gancho, y el enlace al video largo va en el cuerpo.

_RE_SHORTS_TAG = re.compile(r"#shorts?\b", re.IGNORECASE)

TITLE_MIN, TITLE_MAX = 40, 70
HASHTAGS_MAX = 3
TAGS_MAX_SHORT = 5


def strip_shorts_hashtag(text: str) -> str:
    """Quita #Shorts/#Short de un texto, sin dejar dobles espacios."""
    return re.sub(r"\s{2,}", " ", _RE_SHORTS_TAG.sub("", text or "")).strip()


def count_hashtags(text: str) -> int:
    return len(re.findall(r"#\w+", text or ""))


def short_metadata_fixups(meta: dict, related_url: str = "") -> list[str]:
    """Corrige EN SITIO lo corregible de los metadatos de un Short y devuelve
    la lista de avisos de lo que se tocó (para que el creador lo sepa).

    Se corrige solo lo mecánico e indiscutible: quitar el hashtag de Shorts,
    recortar el exceso de tags y asegurar que la descripción lleve el enlace
    al video largo. Lo opinable (largo del título, número de hashtags) se
    REPORTA en la lista de comprobación, no se reescribe a ciegas."""
    avisos: list[str] = []

    for o in meta.get("title_options") or []:
        limpio = strip_shorts_hashtag(o.get("title") or "")
        if limpio != (o.get("title") or "").strip():
            avisos.append("Se quitó el hashtag de Shorts de un título: la "
                          "clasificación es automática y ahí solo resta "
                          "caracteres útiles.")
        o["title"] = limpio
    if meta.get("title"):
        meta["title"] = strip_shorts_hashtag(meta["title"])

    # Un tag 'shorts' puede venir con o sin almohadilla: fuera igual.
    tags = [t for t in (meta.get("tags") or [])
            if not re.fullmatch(r"shorts?", (t or "").strip().lstrip("#"),
                                re.IGNORECASE)
            and not _RE_SHORTS_TAG.search(t or "")]
    if len(tags) != len(meta.get("tags") or []):
        avisos.append("Se quitó 'shorts' de los tags (no interviene en la "
                      "clasificación).")
    if len(tags) > TAGS_MAX_SHORT:
        tags = tags[:TAGS_MAX_SHORT]
        avisos.append(f"Tags recortados a {TAGS_MAX_SHORT}: la documentación "
                      "oficial dice que juegan un papel mínimo — solo valen "
                      "para variantes ortográficas.")
    meta["tags"] = tags

    if related_url:
        linea = f"▶ El video completo: {related_url}"
        for o in meta.get("description_options") or []:
            desc = o.get("description") or ""
            if related_url not in desc:
                # Tras el primer párrafo (la primera línea es el gancho y es
                # lo único visible sin desplegar: no se toca).
                partes = desc.split("\n\n", 1)
                o["description"] = (partes[0] + "\n\n" + linea
                                    + ("\n\n" + partes[1] if len(partes) > 1
                                       else ""))
                avisos.append("Se añadió el enlace al video largo en una "
                              "descripción (es el destino del CTA).")
        if meta.get("description") and related_url not in meta["description"]:
            partes = meta["description"].split("\n\n", 1)
            meta["description"] = (partes[0] + "\n\n" + linea
                                   + ("\n\n" + partes[1] if len(partes) > 1
                                      else ""))
    return avisos


def publish_checklist(project, cfg: dict) -> list[dict]:
    """Lista de comprobación ANTES de publicar un vertical.

    Cada punto: {ok: True/False/None, label, detail}. `ok=None` significa
    «esto no lo puede comprobar una máquina: míralo tú» — y esos puntos son
    exactamente los que más se olvidan."""
    from ytstudio.project import DIRS, read_json_tolerant

    items: list[dict] = []

    def punto(ok, label, detail=""):
        items.append({"ok": ok, "label": label, "detail": detail})

    # 1. La medición técnica del archivo (ya hecha por el montaje)
    audit = project.get("shorts_audit") or {}
    problemas = audit.get("problemas") or []
    if audit:
        punto(not problemas, "El archivo pasa la revisión técnica",
              "; ".join(problemas) if problemas else
              "resolución, duración, códecs y sonoridad medidos")
    else:
        punto(False, "El archivo pasa la revisión técnica",
              "todavía sin medir: genera el video o pulsa «Medir el archivo»")

    # 2. Metadatos elegidos
    meta_path = project.dir / DIRS["final"] / "metadata.json"
    meta = read_json_tolerant(meta_path) if meta_path.exists() else {}
    titulo = (meta.get("title") or "").strip()
    desc = meta.get("description") or ""
    if titulo:
        punto(TITLE_MIN <= len(titulo) <= TITLE_MAX,
              f"Título de {TITLE_MIN}-{TITLE_MAX} caracteres",
              f"tiene {len(titulo)}: «{titulo[:60]}»")
        punto(not _RE_SHORTS_TAG.search(titulo + " ".join(meta.get("tags") or [])),
              "Sin el hashtag de Shorts",
              "la clasificación es automática; ese hashtag es un mito de 2021")
        n_hash = count_hashtags(desc)
        punto(1 <= n_hash <= HASHTAGS_MAX,
              f"2-3 hashtags en la descripción (hay {n_hash})",
              "se muestran hasta 3; más solo hace ruido")
        punto(len(meta.get("tags") or []) <= TAGS_MAX_SHORT,
              f"Como mucho {TAGS_MAX_SHORT} tags",
              "solo valen para variantes ortográficas")
    else:
        punto(False, "Metadatos generados",
              "ejecuta hasta la fase de Metadatos")

    # 3. El puente al video largo
    derived = project.get("derived_from") or {}
    if derived.get("url"):
        punto(derived["url"] in desc,
              "La descripción enlaza al video largo",
              derived["url"])
    punto(None, "Enlace a VIDEO RELACIONADO puesto en Studio",
          "Studio → Contenido → el Short → Video relacionado. No se puede "
          "poner desde fuera, y sin él la vista se regala. Se puede añadir "
          "después de publicar")

    # 4. La miniatura: en este framework se produce SIEMPRE
    mini = project.dir / DIRS["final"] / "miniatura.jpg"
    if mini.exists():
        peso = mini.stat().st_size
        tam = None
        try:
            from PIL import Image
            with Image.open(mini) as im:
                tam = im.size
        except Exception:  # noqa: BLE001 — sin PIL, se comprueba solo el peso
            pass
        bien = peso <= MINIATURA_MAX_BYTES and (tam is None or tam[1] > tam[0])
        detalle = (f"{tam[0]}x{tam[1]} · " if tam else "") + \
            f"{peso / 1024:.0f} KB (límite {MINIATURA_MAX_BYTES // 1024} KB)"
        if tam and tam[1] <= tam[0]:
            detalle += " — es HORIZONTAL: en la parrilla de Shorts se recorta"
        punto(bien, "Miniatura vertical generada", detalle)
    else:
        punto(False, "Miniatura vertical generada",
              "no aparece en el feed deslizable, pero es lo que decide el "
              "clic en la pestaña de Shorts del canal, en la búsqueda y en "
              "el feed de suscripciones")
    pruebas = sorted((project.dir / DIRS["final"]).glob("*_prueba150px.png"))
    punto(None, "Miniatura mirada a 150 px",
          (f"abre {pruebas[0].name}: si a ese tamaño —el de la parrilla del "
           "canal— no lees el texto, la miniatura no sirve por bonita que "
           "sea a tamaño completo" if pruebas else
           "la prueba se genera con la miniatura; vuelve a ejecutar la fase "
           "de Metadatos"))

    # 5. Subtítulos aparte (accesibilidad + texto indexable para búsqueda)
    srt = project.dir / DIRS["subtitles"] / "subtitulos.srt"
    punto(srt.exists(), "Archivo de subtítulos (SRT) generado",
          "se sube aparte: accesibilidad y texto indexable para búsqueda")

    punto(None, "Los subtítulos NO viajan junto al MP4 con el mismo nombre",
          "el programa los deja en 08_subtitles y el video en 09_final, que "
          "es como tiene que ser: juntos y con el mismo nombre, VLC carga el "
          ".srt ENCIMA del que ya va quemado y todo el texto sale duplicado")

    # 6. Lo que solo puede mirar una persona
    punto(None, "El gancho se entiende CON EL SONIDO APAGADO",
          "texto en pantalla desde el primer fotograma — la mayoría lo verá "
          "sin sonido")
    punto(None, "Contenido sintético declarado si aplica",
          "Studio → Atributos → Contenido alterado o sintético. Declarar no "
          "reduce el alcance; no declarar sí es un riesgo")
    punto(None, "Revisado en un teléfono real",
          "la interfaz de la app cambia entre iPhone y Android: solo ahí se "
          "ve qué tapa qué")
    return items
