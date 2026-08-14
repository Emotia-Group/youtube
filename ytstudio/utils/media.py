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

# FAMILIAS DE RÓTULO para el branding por canal/estilo (v0.41.0): cada canal
# puede elegir el "look" tipográfico de sus rótulos en vez de la única sans
# por defecto. Cada familia es (negrita, regular); si ninguna candidata
# existe en el sistema, se cae a la familia 'moderna' (comportamiento
# idéntico al de antes de v0.41.0 para estilos sin branding configurado).
_DISPLAY_CANDIDATES = {
    "Windows": [
        (r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\impact.ttf"),
        (r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\ariblk.ttf"),
    ],
    "Darwin": [
        ("/System/Library/Fonts/Supplemental/Impact.ttf",
         "/System/Library/Fonts/Supplemental/Impact.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial Black.ttf",
         "/System/Library/Fonts/Supplemental/Arial Black.ttf"),
    ],
    "Linux": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ],
}
_MONO_CANDIDATES = {
    "Windows": [
        (r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\consola.ttf"),
        (r"C:\Windows\Fonts\couri.ttf", r"C:\Windows\Fonts\cour.ttf"),
    ],
    "Darwin": [
        ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
         "/System/Library/Fonts/Supplemental/Courier New.ttf"),
        ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"),
    ],
    "Linux": [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
    ],
}

FONT_FAMILIES = {
    "moderna": _FONT_CANDIDATES,     # sans neutra — comportamiento por defecto
    "editorial": None,               # serif — resuelto con _SERIF_CANDIDATES
    "impacto": _DISPLAY_CANDIDATES,  # display/condensada — rótulos punchy
    "mono": _MONO_CANDIDATES,        # monoespaciada — look "datos/técnico"
}

# Ubicaciones típicas de ffmpeg en Windows cuando no está en el PATH
_WIN_FFMPEG_DIRS = [
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
]


def _search_pairs(table: dict, bold: bool) -> str | None:
    for bold_path, regular_path in table.get(platform.system(), []):
        path = bold_path if bold else regular_path
        if Path(path).exists():
            return path
    for pairs in table.values():
        for bold_path, regular_path in pairs:
            path = bold_path if bold else regular_path
            if Path(path).exists():
                return path
    return None


def find_font(bold: bool = True, serif: bool = False,
             family: str | None = None) -> str | None:
    """Ruta de una fuente del sistema, o None.

    `family` (v0.41.0, branding por canal/estilo): 'moderna' (sans, por
    defecto) · 'editorial' (serif) · 'impacto' (display/condensada) ·
    'mono' (monoespaciada). Si la familia pedida no tiene ninguna candidata
    instalada en este sistema, cae a 'moderna' — nunca a None solo por
    faltar una familia exótica. `serif=True` sigue funcionando igual que
    antes (equivale a family='editorial') para no romper llamadas previas."""
    fam = family or ("editorial" if serif else "moderna")
    if fam == "editorial":
        found = _search_pairs({k: [(p, p) for p in v]
                               for k, v in _SERIF_CANDIDATES.items()}, True)
        if found:
            return found
    elif fam in FONT_FAMILIES and FONT_FAMILIES[fam]:
        found = _search_pairs(FONT_FAMILIES[fam], bold)
        if found:
            return found
    # sin la familia pedida en este sistema → sans neutra (comportamiento
    # de siempre), y como último recurso cualquier candidata de cualquiera.
    return _search_pairs(_FONT_CANDIDATES, bold)


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


def run_ffmpeg(args: list[str], desc: str = "",
               timeout: float | None = None) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-y", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ffmpeg tardó demasiado{f' ({desc})' if desc else ''} "
            f"(>{timeout:.0f}s) y se canceló para no bloquear el proyecto.")
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


def probe_video_size(path: Path) -> tuple[int, int] | None:
    """(ancho, alto) del primer flujo de video, o None si no se puede leer.
    Lo usa el montaje para decidir si un clip cabe en el cuadro recortando o
    hay que componerlo entero sobre fondo desenfocado."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=True)
        st = (json.loads(result.stdout).get("streams") or [{}])[0]
        w, h = int(st.get("width") or 0), int(st.get("height") or 0)
        return (w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


def _segment_mean_db(path: Path, s0: float, s1: float) -> float | None:
    """Volumen medio (dBFS) del tramo [s0, s1] con volumedetect. None si no
    se puede medir."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-ss", f"{s0:.3f}",
         "-to", f"{s1:.3f}", "-i", str(path), "-vn", "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in res.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0])
            except (ValueError, IndexError):
                return None
    return None


def boost_quiet_spans(src: Path, spans: list[tuple[float, float]], out: Path,
                      *, target_db: float = -18.0, max_gain_db: float = 20.0,
                      min_gain_db: float = 3.0, floor_db: float = -55.0) -> Path:
    """Sube el volumen SOLO de los tramos indicados (habla dicha muy baja que
    Whisper sí transcribió) para que se oigan, sin tocar el resto del audio ni
    el silencio real. Cada tramo se mide y se realza hacia `target_db` de
    media, con tope `max_gain_db`.

    Salvaguarda: si el tramo mide por DEBAJO de `floor_db` es silencio de
    verdad (no habla baja) — no se realza, para no amplificar el ruido de
    fondo de una pausa. Devuelve `out` (o copia intacta si no hay nada que
    realzar)."""
    import shutil
    filters: list[str] = []
    for s0, s1 in spans:
        if s1 - s0 < 0.1:
            continue
        mean = _segment_mean_db(src, s0, s1)
        if mean is None or mean < floor_db:
            continue  # silencio real: no amplificar ruido
        gain = min(max_gain_db, target_db - mean)
        if gain < min_gain_db:
            continue
        filters.append(
            f"volume=enable='between(t,{s0:.3f},{s1:.3f})':volume={gain:.1f}dB")
    if not filters:
        shutil.copyfile(src, out)
        return out
    run_ffmpeg(["-i", str(src), "-vn", "-af", ",".join(filters),
                "-c:a", "pcm_s16le", str(out)], "realzar habla baja")
    return out


def detect_silences(path: Path, noise_db: int = -38,
                    min_d: float = 0.15) -> list[tuple[float, float]]:
    """Silencios REALES medidos en la onda de audio con silencedetect.

    Devuelve [(inicio, fin)] en segundos. Es la fuente de verdad para saber
    dónde se puede cortar la narración sin partir una palabra: los tiempos de
    Whisper traen un sesgo de ±0.2–0.4s en los bordes de segmento, así que
    cortar ahí puede caer a mitad de palabra — medir el silencio en la onda
    no tiene ese problema."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn",
         "-af", f"silencedetect=noise={noise_db}dB:d={min_d}",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in result.stderr.splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].split()[0])
            except (ValueError, IndexError):
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].split()[0])
                if end > start:
                    silences.append((start, end))
            except (ValueError, IndexError):
                pass
            start = None
    if start is not None:  # silencio abierto hasta el final del archivo
        try:
            silences.append((start, probe_duration(path)))
        except Exception:
            pass
    return silences


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
        run_ffmpeg(["-i", str(paths[0]), "-vn", "-c:a", "libmp3lame", "-q:a", "3",
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
                    keep: float = 0.4, threshold_db: int = -45,
                    lufs: int = -16) -> Path:
    """Normaliza el volumen de una narración y (opcional) recorta el silencio
    de los BORDES (inicio y fin), dejando 0.25s de aire.

    Los silencios INTERNOS ya NO se tocan: recortar entre frases era la única
    operación destructiva que quedaba en todo el pipeline, y con voz suave o
    aireada el filtro confundía sílabas con silencio y SE COMÍA pedazos de
    palabra — siempre en el mismo punto (filtro determinista), justo en las
    pausas donde caen las fronteras de escena. El motor de pausas del
    director conserva y gestiona los silencios internos: nunca se pierde ni
    un milisegundo de la grabación."""
    # Bordes MEDIDOS (silencedetect) y recortados con -ss/-to calculados —
    # sin cadenas silenceremove/areverse, que pueden colgarse según el build
    # de ffmpeg. Determinista y verificable.
    seek: list[str] = []
    if trim_silence:
        try:
            dur = probe_duration(src)
            sils = detect_silences(src, noise_db=threshold_db, min_d=0.4)
            start, end = 0.0, dur
            if sils and sils[0][0] <= 0.1:      # silencio inicial
                start = max(0.0, sils[0][1] - 0.25)
            if sils and sils[-1][1] >= dur - 0.1:  # silencio final
                end = min(dur, sils[-1][0] + 0.25)
            if end - start >= 1.0 and (start > 0.01 or end < dur - 0.01):
                seek = ["-ss", f"{start:.3f}", "-to", f"{end:.3f}"]
        except Exception:
            pass  # sin recorte de bordes: mejor íntegro que arriesgar
    # -ss/-to DESPUÉS del input: corte preciso a la muestra (antes del input
    # el seek de mp3 cae en el frame más cercano, ±26 ms)
    run_ffmpeg(["-i", str(src), *seek, "-vn",
                "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
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
    run_ffmpeg(["-ss", f"{coarse:.3f}", "-i", str(src), "-vn",
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
