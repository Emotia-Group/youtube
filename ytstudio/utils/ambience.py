"""AMBIENTES: la capa de sonido que sostiene el documental por debajo.

La música dibuja el arco dramático; el AMBIENTE da lugar. Un tramo que narra
el desierto suena distinto de uno que narra un mercado o una sala de archivo,
aunque la música sea la misma — es lo que separa un video con voz y música de
un documental.

Dos fuentes, como el resto del programa:
1. TU BIBLIOTECA: assets/sfx/ambientes/<tipo>*.wav|mp3 — manda siempre.
2. SÍNTESIS LOCAL con ffmpeg (costo cero): ruido coloreado y filtrado con
   modulación lenta. No imita una grabación de campo, pero da fondo y cuerpo
   al plano sin sonar artificial al volumen al que va (muy por debajo de la
   voz).

El ambiente se arma POR ACTOS (los mismos que ya usa la música) y se funde
entre tramos, para que el lugar cambie con la historia y no de golpe.
"""
from __future__ import annotations

import random
from pathlib import Path

from ytstudio.config import ROOT
from ytstudio.utils.media import run_ffmpeg

# Catálogo de ambientes. Cada receta es ruido coloreado + filtro + una
# modulación LENTA de volumen (la respiración del ambiente: sin ella el ruido
# suena a estática de televisor).
#   color: white | pink | brown  ·  filtro: cadena ffmpeg  ·  mod: expresión
KINDS: dict[str, dict] = {
    "ninguno": {},
    "sala": {          # room tone: el fondo de una sala, casi imperceptible
        "color": "brown", "filter": "lowpass=f=420,highpass=f=40",
        "mod": "0.85+0.15*sin(2*PI*t/17)", "label": "sala / interior"},
    "viento": {        # desierto, estepa, altura
        "color": "brown", "filter": "lowpass=f=900,highpass=f=90",
        "mod": "0.55+0.45*sin(2*PI*t/11)*sin(2*PI*t/5.3)",
        "label": "viento / desierto"},
    "multitud": {      # mercado, ciudad, gentío (murmullo de fondo)
        "color": "pink", "filter": "highpass=f=280,lowpass=f=2600",
        "mod": "0.6+0.4*sin(2*PI*t/7.3)*sin(2*PI*t/3.1)",
        "label": "multitud / mercado"},
    "lluvia": {
        "color": "white", "filter": "highpass=f=900,lowpass=f=7500",
        "mod": "0.8+0.2*sin(2*PI*t/13)", "label": "lluvia"},
    "mar": {           # oleaje: la modulación ES la ola
        "color": "brown", "filter": "lowpass=f=1400,highpass=f=60",
        "mod": "0.35+0.65*pow(max(0,sin(2*PI*t/8.5)),2)", "label": "mar / olas"},
    "fuego": {
        "color": "brown", "filter": "lowpass=f=2200,highpass=f=120",
        "mod": "0.7+0.3*sin(2*PI*t/2.7)*sin(2*PI*t/1.3)", "label": "fuego"},
    "tension": {       # dron grave: no es un lugar, es una emoción sostenida
        "color": "brown", "filter": "lowpass=f=180",
        "mod": "0.7+0.3*sin(2*PI*t/23)", "label": "tensión / dron grave"},
}

LIB_DIR = ROOT / "assets" / "sfx" / "ambientes"
_AUDIO_EXT = (".wav", ".mp3", ".m4a", ".flac", ".ogg")


def kind_names() -> list[str]:
    """Tipos elegibles por el director (sin 'ninguno', que es la ausencia)."""
    return [k for k in KINDS if k != "ninguno"]


def catalog_text() -> str:
    return "\n".join(f"- {k}: {v['label']}"
                     for k, v in KINDS.items() if k != "ninguno")


def _library_file(kind: str) -> Path | None:
    if not LIB_DIR.is_dir():
        return None
    hits = [p for p in LIB_DIR.glob(f"{kind}*") if p.suffix.lower() in _AUDIO_EXT]
    return random.choice(hits) if hits else None


def render_kind(kind: str, seconds: float, out: Path) -> Path:
    """Un tramo de ambiente de la duración pedida: de tu biblioteca (en bucle
    si hace falta) o sintetizado en local."""
    seconds = max(0.5, float(seconds))
    src = _library_file(kind)
    if src is not None:
        run_ffmpeg(["-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.3f}",
                    "-af", "aformat=sample_rates=44100:channel_layouts=stereo",
                    "-c:a", "pcm_s16le", str(out)], f"ambiente {kind}")
        return out
    spec = KINDS.get(kind) or KINDS["sala"]
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"anoisesrc=color={spec['color']}:r=44100:d={seconds:.3f}:a=0.7",
        "-af", (f"{spec['filter']},"
                f"volume='{spec['mod']}':eval=frame,"
                "aformat=sample_rates=44100:channel_layouts=stereo"),
        "-c:a", "pcm_s16le", str(out),
    ], f"ambiente {kind} (sintetizado)")
    return out


def build_bed(plan: list[tuple[str, float]], out: Path, *,
              xfade: float = 2.5, work_dir: Path | None = None) -> Path | None:
    """Construye la cama de ambiente del video completo desde el plan
    [(tipo, duración)] por acto, fundiendo un tramo con el siguiente.

    Los tramos 'ninguno' se sustituyen por silencio (el silencio también es
    diseño de sonido: un tramo sin ambiente destaca por contraste).
    Devuelve None si no hay nada que sonar."""
    plan = [(k, d) for k, d in plan if d > 0.2]
    if not plan or all(k == "ninguno" for k, _ in plan):
        return None
    work = work_dir or out.parent
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for i, (kind, dur) in enumerate(plan):
        part = work / f"amb_{i:02d}.wav"
        # cada juntura consume xfade s: cada tramo se genera un poco más largo
        extra = xfade if i < len(plan) - 1 else 0.5
        if kind == "ninguno":
            run_ffmpeg(["-f", "lavfi",
                        "-i", f"anullsrc=r=44100:cl=stereo:d={dur + extra:.3f}",
                        "-c:a", "pcm_s16le", str(part)], "ambiente (silencio)")
        else:
            render_kind(kind, dur + extra, part)
        parts.append(part)
    if len(parts) == 1:
        parts[0].replace(out)
        return out
    args: list[str] = []
    for p in parts:
        args += ["-i", str(p)]
    graph, cur = [], "[0:a]"
    for i in range(1, len(parts)):
        nxt = f"[x{i}]"
        graph.append(f"{cur}[{i}:a]acrossfade=d={xfade:.1f}:c1=tri:c2=tri{nxt}")
        cur = nxt
    run_ffmpeg(args + ["-filter_complex", ";".join(graph), "-map", cur,
                       "-c:a", "pcm_s16le", str(out)],
               "cama de ambiente", timeout=600)
    for p in parts:
        p.unlink(missing_ok=True)
    return out
