"""Efectos de sonido incidentales para las transiciones (whoosh, riser, boom).

Prioridad: si el usuario tiene archivos en assets/sfx/ cuyo nombre empieza por
el tipo (whoosh*.wav, riser*.mp3, boom*...), se usan esos. Si no, se sintetiza
un efecto sobrio con ffmpeg (aevalsrc): a volumen bajo funcionan como acento
cinematográfico sin sonar artificiales.
"""
from __future__ import annotations

import random
from pathlib import Path

from ytstudio.config import ROOT
from ytstudio.utils.media import run_ffmpeg

KINDS = ("whoosh", "riser", "boom", "pop")

# Duración de cada efecto sintetizado y cómo se alinea con el corte de escena:
# whoosh/riser terminan EN el corte (anticipan); boom suena EN el corte;
# pop es el acento sutil de los INSERTOS documentales (suena en la mención).
SFX_SPECS = {
    "whoosh": {"dur": 1.0, "before_cut": 0.85},
    "riser": {"dur": 2.4, "before_cut": 2.4},
    "boom": {"dur": 2.2, "before_cut": 0.0},
    "pop": {"dur": 0.4, "before_cut": 0.0},
}


def _library_track(kind: str) -> Path | None:
    lib = ROOT / "assets" / "sfx"
    if not lib.is_dir():
        return None
    hits = [p for p in lib.glob(f"{kind}*")
            if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg")]
    return random.choice(hits) if hits else None


def _synthesize(kind: str, out: Path) -> Path:
    d = SFX_SPECS[kind]["dur"]
    if kind == "whoosh":
        # Ráfaga de ruido con envolvente gaussiana + banda media: soplo de aire.
        expr = f"(random(0)-0.5)*1.6*exp(-10*pow(t-{d/2:.2f}\\,2))"
        post = "highpass=f=180,lowpass=f=2400"
    elif kind == "riser":
        # Ruido que crece de forma cuadrática hasta el corte: tensión en aumento.
        expr = f"(random(0)-0.5)*1.1*pow(t/{d:.2f}\\,2.4)"
        post = "highpass=f=300,lowpass=f=5000"
    elif kind == "pop":
        # Toque breve y suave (barrido corto descendente): acento de inserto.
        expr = "0.55*sin(2*PI*(820-600*t)*t)*exp(-16*t)"
        post = "highpass=f=200,lowpass=f=2600"
    else:  # boom
        # Sub-golpe (52 Hz con caída exponencial) + ataque breve de ruido.
        expr = (f"0.95*sin(2*PI*52*t)*exp(-3.2*t)"
                f"+0.25*(random(0)-0.5)*exp(-38*t)")
        post = "lowpass=f=150"
    run_ffmpeg([
        "-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={d:.2f}",
        "-af", f"{post},afade=t=out:st={max(0.0, d - 0.25):.2f}:d=0.25,"
               "aformat=sample_rates=44100:channel_layouts=stereo",
        "-c:a", "pcm_s16le", str(out),
    ], f"sfx {kind}")
    return out


def ensure_sfx(kind: str, work_dir: Path) -> Path:
    """Devuelve la ruta de un efecto listo para mezclar (biblioteca o síntesis).
    Cachea la síntesis en work_dir para no regenerarla por cada aparición."""
    lib = _library_track(kind)
    if lib is not None:
        return lib
    out = work_dir / f"sfx_{kind}.wav"
    if not out.exists():
        _synthesize(kind, out)
    return out
