"""Análisis PROFUNDO de un video de referencia a partir de su enlace
(YouTube, Vimeo, Wistia y ~1800 sitios soportados por yt-dlp).

Qué se extrae para poder replicar la fórmula del video:
- Metadatos: título, canal, duración, capítulos y descripción.
- El GUION completo: subtítulos oficiales o automáticos si existen; si no,
  se transcribe el audio con el STT configurado.
- El RITMO DE EDICIÓN: se descarga el video en baja resolución, se detectan
  los cortes de plano con ffmpeg y se calcula la duración media de plano
  (esto alimenta directamente el ritmo visual del nuevo proyecto).
- FOTOGRAMAS repartidos para que la visión IA analice estilo, paleta,
  rótulos y animaciones.

yt-dlp es opcional: si no está instalado, la ingesta usa solo los metadatos
públicos (oEmbed/Open Graph) y avisa cómo activar el análisis completo.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from ytstudio.utils.media import extract_audio, extract_frames, probe_duration


def available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


def _parse_vtt(path: Path) -> str:
    """Texto plano de un .vtt/.srt (sin tiempos, sin repeticiones seguidas)."""
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if (not line or "-->" in line or line == "WEBVTT"
                or re.fullmatch(r"\d+", line)
                or line.startswith(("Kind:", "Language:", "NOTE"))):
            continue
        if not lines or lines[-1] != line:
            lines.append(line)
    return " ".join(lines)


def detect_cut_rhythm(video: Path, threshold: float = 0.30,
                      max_seconds: float = 900) -> dict:
    """Cortes de plano y duración media de plano, con detección de escenas de
    ffmpeg sobre (como mucho) los primeros `max_seconds` del video."""
    dur = min(probe_duration(video), max_seconds)
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-t", f"{dur:.1f}",
         "-i", str(video), "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    cuts = len(re.findall(r"pts_time:([0-9.]+)", result.stderr))
    shots = cuts + 1
    return {"analyzed_seconds": round(dur, 1), "cuts": cuts,
            "avg_shot_seconds": round(dur / shots, 1),
            "cuts_per_minute": round(cuts / (dur / 60), 1) if dur else 0}


def analyze_reference_video(url: str, work_dir: Path, cfg: dict,
                            stt=None) -> dict:
    """Descarga (en baja resolución, acotado en minutos) y analiza el video.
    Lanza excepción si el enlace no es descargable — el llamador decide el
    fallback a metadatos simples."""
    import yt_dlp

    ref_cfg = cfg.get("reference") or {}
    from ytstudio.progress import notify

    max_min = float(ref_cfg.get("max_minutes", 12))
    height = int(ref_cfg.get("video_height", 480))
    # socket_timeout evita que una conexión atascada con YouTube cuelgue la
    # fase para siempre: si un fragmento no responde, falla y el llamador
    # degrada a los metadatos públicos.
    sock_timeout = float(ref_cfg.get("timeout_seconds", 45))
    lang = cfg.get("language", "es")
    work_dir.mkdir(parents=True, exist_ok=True)
    base_opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "socket_timeout": sock_timeout, "retries": 3, "fragment_retries": 3,
    }

    # Metadatos primero (sin descargar): duración real para decidir el recorte
    notify(f"🔎 Consultando el video de referencia… ({url})")
    with yt_dlp.YoutubeDL(base_opts) as ydl:
        meta = ydl.extract_info(url, download=False)
    duration = meta.get("duration") or 0
    title = meta.get("title") or url
    mins = f"{duration / 60:.0f} min" if duration else "duración desconocida"
    cap = f", se analizarán los primeros {max_min:.0f} min" if duration > max_min * 60 else ""
    notify(f"⬇ Descargando referencia «{title}» ({mins}{cap}) a {height}p… "
           "esto puede tardar varios minutos.")

    opts = {
        **base_opts,
        "format": f"bv*[height<={height}]+ba/b[height<={height}]/b",
        "outtmpl": str(work_dir / "ref.%(ext)s"),
        "writesubtitles": True, "writeautomaticsub": True,
        "subtitleslangs": [lang, f"{lang}-orig", "en"],
        "subtitlesformat": "vtt/srt/best",
    }
    if duration > max_min * 60:
        # Solo los primeros N minutos: suficiente para fórmula y ritmo,
        # sin descargar horas de video.
        opts["download_ranges"] = yt_dlp.utils.download_range_func(
            None, [(0, max_min * 60)])
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    analysis: dict = {
        "url": url,
        "title": info.get("title"),
        "author": info.get("uploader") or info.get("channel"),
        "duration_seconds": info.get("duration"),
        "description": (info.get("description") or "")[:2000],
        "chapters": [{"title": c.get("title"),
                      "start": round(c.get("start_time", 0))}
                     for c in (info.get("chapters") or [])][:40],
    }

    video = next((p for p in work_dir.glob("ref.*")
                  if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")), None)
    if video is not None:  # descartar descargas corruptas/vacías
        try:
            if probe_duration(video) < 1:
                video = None
        except Exception:
            video = None

    # Guion: subtítulos descargados o transcripción del audio
    transcript = ""
    subs = sorted(work_dir.glob("ref.*.vtt")) + sorted(work_dir.glob("ref.*.srt"))
    if subs:
        notify("📝 Leyendo los subtítulos del video de referencia…")
        transcript = _parse_vtt(subs[0])
    elif video is not None and stt is not None:
        notify("🎧 El video no trae subtítulos: transcribiendo su audio…")
        audio = extract_audio(video, work_dir / "ref_audio.mp3")
        transcript = stt.transcribe(audio)
    analysis["transcript"] = transcript[:20000]

    if video is not None:
        try:
            notify("🎬 Midiendo el ritmo de edición del video de referencia…")
            analysis["rhythm"] = detect_cut_rhythm(video)
        except Exception:
            pass
        analysis["frames"] = [str(f) for f in
                              extract_frames(video, work_dir / "frames", count=10)]
    (work_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return analysis


def analysis_summary(a: dict) -> str:
    """Resumen textual del análisis para el prompt de la ingesta/concepto."""
    lines = [f"URL: {a['url']}"]
    if a.get("title"):
        lines.append(f"Título: {a['title']}")
    if a.get("author"):
        lines.append(f"Canal: {a['author']}")
    if a.get("duration_seconds"):
        lines.append(f"Duración: {round(a['duration_seconds'] / 60, 1)} min")
    r = a.get("rhythm")
    if r:
        lines.append(
            f"Ritmo de edición: plano medio de {r['avg_shot_seconds']}s "
            f"({r['cuts_per_minute']} cortes/min en los primeros "
            f"{round(r['analyzed_seconds'] / 60, 1)} min)")
    if a.get("chapters"):
        caps = " · ".join(f"{c['title']}" for c in a["chapters"][:12])
        lines.append(f"Estructura por capítulos: {caps}")
    if a.get("description"):
        lines.append(f"Descripción: {a['description'][:600]}")
    if a.get("transcript"):
        lines.append("GUION/TRANSCRIPCIÓN (para analizar fórmula, gancho, "
                     f"estructura y tono):\n{a['transcript'][:7000]}")
    return "\n".join(lines)
