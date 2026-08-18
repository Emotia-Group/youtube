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
}

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


def evaluate(info: dict | None, loud: dict | None) -> tuple[list, list, list]:
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
    bad, warn, ok = evaluate(info, loud)
    return {"archivo": os.path.basename(str(path)), "ruta": str(path),
            "info": info, "sonoridad": loud, "problemas": bad,
            "avisos": warn, "correcto": ok}


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
            "  · Que el primer fotograma prometa algo"]
    return out
