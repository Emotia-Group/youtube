"""Proveedores de música de fondo."""
from __future__ import annotations

import random
from pathlib import Path

from ytstudio.config import ROOT
from ytstudio.utils.media import run_ffmpeg


class LibraryMusic:
    """Elige una pista de una carpeta local (assets/music). Si el nombre del
    archivo contiene el mood pedido, se prioriza."""

    def __init__(self, cfg: dict):
        self.dir = ROOT / cfg["providers"]["music"].get("library_dir", "assets/music")

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        tracks = [p for p in self.dir.glob("*")
                  if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg")]
        if not tracks:
            raise RuntimeError(
                f"No hay pistas en {self.dir}. Añade música libre de derechos "
                "o cambia providers.music.name en config.yaml.")
        preferred = [t for t in tracks if mood.lower() in t.stem.lower()]
        track = random.choice(preferred or tracks)
        # Loop hasta cubrir la duración total y recorte exacto. -vn es CRÍTICO:
        # los mp3 con carátula incrustada (Suno, iTunes…) traen un stream de
        # video (la imagen) que con -stream_loop -1 nunca alcanza la duración
        # de corte → ffmpeg se queda en bucle infinito. Timeout de respaldo.
        run_ffmpeg(["-stream_loop", "-1", "-i", str(track), "-vn",
                    "-t", f"{seconds:.2f}",
                    "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                   "música library", timeout=300)
        return out


class ReplicateMusic:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        # La versión se resuelve dinámicamente en replicate_call (evita el 404
        # por hashes caducados), así que basta el slug del modelo.
        self.model = cfg["providers"]["music"].get("model", "meta/musicgen")

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        import urllib.request
        from ytstudio.providers.replicate_util import replicate_call
        # MusicGen genera hasta ~30s; se generan y loopean
        raw = out.with_suffix(".raw.mp3")
        output = replicate_call(self.client, self.model, {
            "prompt": f"{mood} instrumental background music for a documentary video, "
                      "no vocals, seamless loop",
            "duration": 30, "output_format": "mp3",
            "model_version": "stereo-large",
        })
        url = output[0] if isinstance(output, list) else output
        urllib.request.urlretrieve(str(url), raw)
        run_ffmpeg(["-stream_loop", "-1", "-i", str(raw), "-vn",
                    "-t", f"{seconds:.2f}",
                    "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                   "loop música", timeout=300)
        raw.unlink(missing_ok=True)
        return out


class MockMusic:
    """Pad ambiental sintético (acorde con trémolo) generado con ffmpeg."""

    def __init__(self, cfg: dict):
        pass

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        run_ffmpeg([
            "-f", "lavfi", "-i", f"sine=frequency=110:duration={seconds:.2f}",
            "-f", "lavfi", "-i", f"sine=frequency=165:duration={seconds:.2f}",
            "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds:.2f}",
            "-filter_complex",
            "[0:a][1:a][2:a]amix=inputs=3:normalize=1,"
            "tremolo=f=0.25:d=0.6,volume=0.4,aformat=channel_layouts=stereo[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "4", str(out),
        ], "música mock")
        return out
