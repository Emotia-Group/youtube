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

KINDS = ("whoosh", "riser", "boom", "pop", "papel", "latido",
         "clic", "aire", "cuerda", "sello")

# Duración de cada efecto sintetizado y cómo se alinea con el corte de escena:
# whoosh/riser terminan EN el corte (anticipan); boom/papel/latido suenan EN
# el corte; pop, clic, aire, cuerda y sello son los acentos de los INSERTOS
# documentales (suenan en la mención, no en el corte).
SFX_SPECS = {
    "whoosh": {"dur": 1.0, "before_cut": 0.85},
    "riser": {"dur": 2.4, "before_cut": 2.4},
    "boom": {"dur": 2.2, "before_cut": 0.0},
    "pop": {"dur": 0.4, "before_cut": 0.0},
    "papel": {"dur": 0.9, "before_cut": 0.15},
    "latido": {"dur": 1.6, "before_cut": 0.0},
    "clic": {"dur": 0.35, "before_cut": 0.0},
    "aire": {"dur": 1.4, "before_cut": 0.35},
    "cuerda": {"dur": 1.8, "before_cut": 0.3},
    "sello": {"dur": 0.8, "before_cut": 0.0},
}

# PALETAS del acento de los INSERTOS documentales (fotos de archivo, cifras,
# mapas). Antes TODOS sonaban con el mismo 'pop' — un acento de app que no
# pega con un documental histórico. Cada paleta da un sonido distinto según
# QUÉ entra en pantalla, así el video no repite el mismo golpe 20 veces.
INSERT_PALETTES: dict[str, dict[str, str]] = {
    "archivo": {"photo": "papel", "video": "papel", "stat": "clic",
                "map": "aire"},
    "sobrio": {"photo": "aire", "video": "aire", "stat": "clic",
               "map": "aire"},
    "epico": {"photo": "cuerda", "video": "cuerda", "stat": "cuerda",
              "map": "aire"},
    "oficina": {"photo": "sello", "video": "sello", "stat": "clic",
                "map": "clic"},
    "moderno": {"photo": "pop", "video": "pop", "stat": "pop", "map": "pop"},
    "ninguno": {},
}

PALETTE_LABELS = {
    "auto": "Automático — según el estilo del video",
    "archivo": "Archivo — roce de papel y tic de proyector (documental)",
    "sobrio": "Sobrio — un soplo de aire, casi imperceptible",
    "epico": "Épico — cuerdas breves que crecen",
    "oficina": "Registro — sello y clic de mecanismo",
    "moderno": "Moderno — 'pop' de app (el de siempre)",
    "ninguno": "Sin sonido — los insertos entran mudos",
}


def insert_kind(el: dict, palette: str) -> str | None:
    """Efecto que acompaña a UN inserto documental, según la paleta elegida.
    None = ese inserto entra mudo."""
    table = INSERT_PALETTES.get(palette or "archivo")
    if table is None:            # nombre de efecto suelto ('papel', 'boom'…)
        return palette if palette in SFX_SPECS else None
    if not table:
        return None
    tipo = (el.get("tipo") or "").lower()
    if tipo == "mapa":
        key = "map"
    elif tipo in ("cifra", "fecha"):
        key = "stat"
    elif el.get("mode") == "video":
        key = "video"
    else:
        key = "photo"
    return table.get(key)


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
    elif kind == "papel":
        # Roce de papel/archivo: dos ráfagas cortas de ruido agudo — el gesto
        # de pasar un documento, para los tramos de archivo y datos.
        expr = ("(random(0)-0.5)*1.4*exp(-13*t)"
                "+(random(0)-0.5)*1.1*exp(-16*max(0\\,t-0.28))")
        post = "highpass=f=1200,lowpass=f=7000"
    elif kind == "clic":
        # Tic de mecanismo (avance de proyector de diapositivas): un golpe
        # seco y corto de madera — el acento más discreto para una cifra.
        expr = ("0.8*sin(2*PI*1600*t)*exp(-90*t)"
                "+0.5*(random(0)-0.5)*exp(-70*t)")
        post = "highpass=f=600,lowpass=f=6000"
    elif kind == "aire":
        # Soplo de aire suave que entra y se va: presencia sin percusión,
        # para documentales sobrios donde un 'pop' suena a aplicación.
        expr = ("(random(0)-0.5)*1.2*exp(-3.0*pow(t-0.55\\,2)*6)")
        post = "highpass=f=280,lowpass=f=1800"
    elif kind == "cuerda":
        # Cuerdas breves que crecen y se apagan (quinta grave + octava):
        # el acento épico, sin percusión.
        expr = ("0.45*sin(2*PI*220*t)*(1-exp(-4*t))*exp(-1.6*t)"
                "+0.30*sin(2*PI*330*t)*(1-exp(-3*t))*exp(-1.8*t)"
                "+0.18*sin(2*PI*440*t)*(1-exp(-2.5*t))*exp(-2.2*t)")
        post = "highpass=f=120,lowpass=f=3000"
    elif kind == "sello":
        # Sello de caucho sobre un expediente: golpe apagado + roce corto.
        expr = ("0.85*sin(2*PI*120*t)*exp(-26*t)"
                "+0.45*(random(0)-0.5)*exp(-30*t)"
                "+0.25*(random(0)-0.5)*exp(-22*max(0\\,t-0.12))")
        post = "lowpass=f=3200"
    elif kind == "latido":
        # Latido (lub-dub): dos golpes graves con la separación real del
        # corazón — tensión sostenida sin música añadida.
        expr = ("0.9*sin(2*PI*46*t)*exp(-7*t)"
                "+0.7*sin(2*PI*42*max(0\\,t-0.34))*exp(-8*max(0\\,t-0.34))")
        post = "lowpass=f=180"
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
