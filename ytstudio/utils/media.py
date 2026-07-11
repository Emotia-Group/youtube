"""Utilidades ffmpeg/ffprobe compartidas por varias fases."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise RuntimeError(
                f"No se encontró '{tool}'. Instálalo (ej. apt install ffmpeg)."
            )


def run_ffmpeg(args: list[str], desc: str = "") -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló{f' ({desc})' if desc else ''}:\n{result.stderr[-3000:]}"
        )


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def make_silence(path: Path, seconds: float, sample_rate: int = 44100) -> Path:
    run_ffmpeg(
        ["-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=stereo",
         "-t", f"{seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "4", str(path)],
        "silencio",
    )
    return path


def extract_audio(video: Path, out: Path) -> Path:
    run_ffmpeg(["-i", str(video), "-vn", "-c:a", "libmp3lame", "-q:a", "3", str(out)],
               "extraer audio")
    return out


def extract_frames(video: Path, out_dir: Path, count: int = 6) -> list[Path]:
    """Extrae `count` fotogramas repartidos a lo largo del video."""
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(video)
    frames = []
    for i in range(count):
        t = duration * (i + 0.5) / count
        frame = out_dir / f"frame_{i:02d}.jpg"
        run_ffmpeg(["-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                    "-q:v", "3", str(frame)], "extraer fotograma")
        frames.append(frame)
    return frames
