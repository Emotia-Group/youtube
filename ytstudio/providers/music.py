"""Proveedores de música de fondo."""
from __future__ import annotations

import json
import random
from pathlib import Path

from ytstudio.config import ROOT
from ytstudio.utils.media import run_ffmpeg


class LibraryMusic:
    """Elige una pista de una carpeta local (assets/music). La fase de música
    puede elegir la pista con IA (por título/nombre frente al concepto del
    video) vía generate_track; generate() mantiene el criterio simple (mood en
    el nombre del archivo, o aleatoria)."""

    def __init__(self, cfg: dict):
        self.dir = ROOT / cfg["providers"]["music"].get("library_dir", "assets/music")

    def list_tracks(self) -> list[dict]:
        """Pistas disponibles con sus metadatos (título/artista del ID3)."""
        import subprocess
        tracks = []
        for p in sorted(self.dir.glob("*")):
            if p.suffix.lower() not in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
                continue
            info = {"file": p.name, "path": p}
            try:
                r = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format_tags=title,artist:format=duration", "-of", "json",
                     str(p)], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=30)
                fmt = json.loads(r.stdout).get("format", {})
                tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
                info["title"] = tags.get("title", "")
                info["artist"] = tags.get("artist", "")
                info["seconds"] = round(float(fmt.get("duration", 0)))
            except Exception:
                pass
            tracks.append(info)
        return tracks

    def generate_track(self, track: Path, seconds: float, out: Path) -> Path:
        """Loop de una pista CONCRETA hasta cubrir la duración pedida."""
        run_ffmpeg(["-stream_loop", "-1", "-i", str(track), "-vn",
                    "-t", f"{seconds:.2f}",
                    "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                   "música library", timeout=300)
        return out

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        tracks = [p for p in self.dir.glob("*")
                  if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg")]
        if not tracks:
            raise RuntimeError(
                f"No hay pistas en {self.dir}. Añade música libre de derechos "
                "o cambia providers.music.name en config.yaml.")
        preferred = [t for t in tracks if mood.lower() in t.stem.lower()]
        track = random.choice(preferred or tracks)
        return self.generate_track(track, seconds, out)


class ReplicateMusic:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        # La versión se resuelve dinámicamente en replicate_call (evita el 404
        # por hashes caducados), así que basta el slug del modelo.
        self.model = cfg["providers"]["music"].get("model", "meta/musicgen")

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        # MusicGen genera hasta ~30s; se generan y loopean
        raw = out.with_suffix(".raw.mp3")
        charge = {"provider": "replicate", "label": "pista de música",
                  "qty": 1, "unit": "pista",
                  "usd": pricing.music_cost_mid("replicate")}
        run_and_download(self.client, self.model, {
            "prompt": f"{mood} instrumental background music for a documentary video, "
                      "no vocals, seamless loop",
            "duration": 30, "output_format": "mp3",
            "model_version": "stereo-large",
        }, raw, charge=charge)
        run_ffmpeg(["-stream_loop", "-1", "-i", str(raw), "-vn",
                    "-t", f"{seconds:.2f}",
                    "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                   "loop música", timeout=300)
        raw.unlink(missing_ok=True)
        return out  # el gasto ya quedó anotado al terminar la predicción


class ElevenLabsMusic:
    """Música con LICENCIA COMERCIAL CERRADA.

    Para un canal que monetiza, la licencia pesa más que el último punto de
    calidad: Suno y Udio suenan mejor, pero a mediados de 2026 no tienen API
    pública y sus términos comerciales seguían en litigio por los datos de
    entrenamiento. ElevenLabs Music cerró la licencia antes de lanzar y sí
    expone API — es el único relevo defendible de MusicGen para este uso.

    Genera la pista de la duración pedida de una vez (sin el loop de 30 s que
    necesita MusicGen), así que la banda sonora no se repite."""

    MAX_SECONDS = 300     # tope por pista de la API; más allá se loopea

    def __init__(self, cfg: dict):
        import os
        self.api_key = os.environ["ELEVENLABS_API_KEY"]

    def generate(self, mood: str, seconds: float, out: Path) -> Path:
        import json
        import urllib.request

        from ytstudio import pricing, usage
        usd = pricing.music_cost_mid("elevenlabs")
        usage.check_budget(usd, "una pista de música de ElevenLabs")
        want = min(float(seconds), float(self.MAX_SECONDS))
        body = json.dumps({
            "prompt": f"{mood} instrumental background score for a "
                      "documentary film, no vocals, cinematic, subtle",
            "music_length_ms": int(want * 1000),
        }).encode()
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/music", data=body,
            headers={"xi-api-key": self.api_key,
                     "Content-Type": "application/json"})
        raw = out.with_suffix(".raw.mp3")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw.write_bytes(resp.read())
        except Exception as e:
            raw.unlink(missing_ok=True)
            raise RuntimeError(
                f"ElevenLabs Music no pudo generar la pista ({e}). Revisa "
                "ELEVENLABS_API_KEY y que tu plan incluya música.") from e
        usage.record("elevenlabs", "pista de música", 1, "pista", usd)
        usage.add_spend(usd)
        # Si el video es más largo que el tope de la API, se loopea el sobrante
        run_ffmpeg(["-stream_loop", "-1", "-i", str(raw), "-vn",
                    "-t", f"{seconds:.2f}",
                    "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                   "música ElevenLabs", timeout=300)
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
