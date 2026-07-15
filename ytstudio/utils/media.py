"""Utilidades ffmpeg/ffprobe compartidas por varias fases.

Compatibilidad multiplataforma: localización de fuentes tipográficas en
Windows/macOS/Linux, autodetección de ffmpeg en rutas comunes de Windows y
escapado de rutas para los filtros de ffmpeg (los ':' de 'C:\\' rompen el
grafo de filtros si no se escapan).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

# Candidatas por sistema: (negrita, regular)
_FONT_CANDIDATES = {
    "Windows": [
        (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"),
        (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\segoeui.ttf"),
        (r"C:\Windows\Fonts\calibrib.ttf", r"C:\Windows\Fonts\calibri.ttf"),
    ],
    "Darwin": [
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf"),
        ("/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial.ttf"),
        ("/System/Library/Fonts/Helvetica.ttc",
         "/System/Library/Fonts/Helvetica.ttc"),
    ],
    "Linux": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ],
}

# Fuentes serif (negrita) para rótulos cinematográficos: nombres de
# personajes y conclusiones. Si no hay ninguna, se degrada a la sans.
_SERIF_CANDIDATES = {
    "Windows": [
        r"C:\Windows\Fonts\georgiab.ttf",
        r"C:\Windows\Fonts\constanb.ttf",   # Constantia
        r"C:\Windows\Fonts\timesbd.ttf",
    ],
    "Darwin": [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    ],
    "Linux": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf",
    ],
}

# Ubicaciones típicas de ffmpeg en Windows cuando no está en el PATH
_WIN_FFMPEG_DIRS = [
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
]


def find_font(bold: bool = True, serif: bool = False) -> str | None:
    """Ruta de una fuente del sistema (negrita o regular; serif opcional para
    rótulos cinematográficos), o None."""
    if serif:
        for path in _SERIF_CANDIDATES.get(platform.system(), []):
            if Path(path).exists():
                return path
        for paths in _SERIF_CANDIDATES.values():
            for path in paths:
                if Path(path).exists():
                    return path
        # sin serif en el sistema → sans negrita
    for bold_path, regular_path in _FONT_CANDIDATES.get(platform.system(), []):
        path = bold_path if bold else regular_path
        if Path(path).exists():
            return path
    # Último recurso: cualquier candidata de cualquier sistema
    for pairs in _FONT_CANDIDATES.values():
        for bold_path, regular_path in pairs:
            path = bold_path if bold else regular_path
            if Path(path).exists():
                return path
    return None


def filter_path(p: Path | str) -> str:
    """Escapa una ruta para usarla como valor de opción en un filtro ffmpeg
    (drawtext fontfile=, ass=). Barras de Windows → '/', y se escapan los
    caracteres especiales del parser de filtros (: ' \\)."""
    s = str(Path(p).resolve()).replace("\\", "/")
    return s.replace(":", "\\:").replace("'", "\\'")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    # Windows: buscar en rutas comunes (incluye subcarpetas — el zip de gyan.dev
    # se extrae a menudo como C:\ffmpeg\ffmpeg-X.Y-essentials_build\bin) y
    # añadir al PATH del proceso.
    if platform.system() == "Windows":
        candidates = []
        for d in _WIN_FFMPEG_DIRS:
            base = Path(d)
            if (base / "ffmpeg.exe").exists():
                candidates.append(base)
        for root in (Path(r"C:\ffmpeg"), Path(r"C:\Program Files\ffmpeg")):
            if root.exists():
                candidates += [p.parent for p in root.rglob("ffmpeg.exe")]
        for d in candidates:
            os.environ["PATH"] += os.pathsep + str(d)
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                return
        raise RuntimeError(
            "No se encontró ffmpeg. Descarga 'ffmpeg-release-essentials.zip' de "
            "https://www.gyan.dev/ffmpeg/builds/ y descomprímelo en C:\\ffmpeg "
            "(debe existir C:\\ffmpeg\\bin\\ffmpeg.exe o similar).")
    raise RuntimeError(
        "No se encontró ffmpeg/ffprobe. Instálalo (ej. apt install ffmpeg / "
        "brew install ffmpeg).")


def run_ffmpeg(args: list[str], desc: str = "") -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falló{f' ({desc})' if desc else ''}:\n{result.stderr[-3000:]}"
        )


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True,
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


def concat_audios(paths: list[Path], out: Path) -> Path:
    """Une varios audios en uno solo (re-encodeados a un formato común)."""
    if len(paths) == 1:
        run_ffmpeg(["-i", str(paths[0]), "-c:a", "libmp3lame", "-q:a", "3",
                    str(out)], "normalizar audio")
        return out
    inputs = []
    for p in paths:
        inputs += ["-i", str(p)]
    n = len(paths)
    filt = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    run_ffmpeg([*inputs, "-filter_complex", filt, "-map", "[a]",
                "-c:a", "libmp3lame", "-q:a", "3", str(out)], "unir audios")
    return out


def clean_narration(src: Path, out: Path, *, trim_silence: bool = True,
                    keep: float = 0.4, threshold_db: int = -35,
                    lufs: int = -16) -> Path:
    """Normaliza el volumen de una narración y (opcional) recorta los silencios
    largos — al inicio, al final y entre frases — dejando pausas uniformes de
    `keep` segundos. Devuelve la ruta del audio limpio."""
    filters = []
    if trim_silence:
        filters.append(
            f"silenceremove=start_periods=1:start_duration=0:"
            f"start_threshold={threshold_db}dB:detection=peak:"
            f"stop_periods=-1:stop_duration={keep}:"
            f"stop_threshold={threshold_db}dB:detection=peak")
    filters.append(f"loudnorm=I={lufs}:TP=-1.5:LRA=11")
    run_ffmpeg(["-i", str(src), "-af", ",".join(filters),
                "-c:a", "libmp3lame", "-q:a", "2", str(out)], "limpiar narración")
    return out


def cut_segment(src: Path, start: float, end: float, out: Path,
                lead: float = 0.12) -> Path:
    """Extrae el tramo [start, end] (segundos) de un audio.

    Corte preciso en dos etapas: un seek rápido aproximado ANTES del input y el
    ajuste fino DESPUÉS (el seek de entrada solo, en mp3, cae en el frame
    anterior o siguiente y se comía el arranque de la primera palabra). Además
    se adelanta `lead` segundos — cabe en la pausa que deja clean_narration —
    para no cortar el ataque de la voz, con un microfundido anticlic."""
    start = max(0.0, start - lead)
    dur = max(0.1, end - start)
    coarse = max(0.0, start - 1.0)
    fine = start - coarse
    run_ffmpeg(["-ss", f"{coarse:.3f}", "-i", str(src),
                "-ss", f"{fine:.3f}", "-t", f"{dur:.3f}",
                "-af", "afade=t=in:st=0:d=0.02",
                "-c:a", "libmp3lame", "-q:a", "3", str(out)], "cortar segmento")
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
