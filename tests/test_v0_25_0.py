"""Batería v0.25.0: (1) NO borrar frases dichas en voz baja + (2) subtítulos
cortos estilo cine.

Diagnóstico real (imagen del usuario): se borró la frase ENTERA «Su padre,
Filipo II, había pasado años convirtiendo una provincia vulnerable y
periféri…» — un pasaje dicho más bajo cae por debajo de -45 dB, silencedetect
lo marca como SILENCIO y el compresor lo quitaba como aire muerto. Whisper SÍ
lo transcribió: la salvaguarda es no tocar ningún hueco con palabras dentro.

T1  Un pasaje HABLADO por debajo del umbral (-48 dB) con palabras de Whisper
    dentro NO se recorta: la frase sobrevive íntegra y se avisa (quiet_spans).
T2  Un silencio de verdad (sin palabras) SÍ se sigue comprimiendo.
T3  Subtítulos cortos: cada bloque es una frase/cláusula breve, <= max_lines
    líneas, y ninguno es un párrafo largo.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import subprocess
import sys
from pathlib import Path



from ytstudio.phases.voiceover import _build_timeline
from ytstudio.phases.subtitles import _chunks_words
from ytstudio.utils.media import detect_silences, probe_duration

TMP = Path(__file__).parent / "t250"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


FPS = 24.0
CFG = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2, "cut_guard": 0.20,
                 "onset_guard": 0.45, "deep_silence_db": -55}}

# ---- T1: pasaje hablado EN VOZ BAJA (-48 dB) entre dos frases fuertes ----
# A fuerte [0.3-2.0] | frase BAJA [2.5-6.0] a -48 dB (bajo el umbral -45, pero
# es VOZ: Whisper la transcribe) | B fuerte [6.5-8.0]. Sin salvaguarda, el
# "silencio" [~2.0-6.5] se comprimía y borraba la frase baja.
TOTAL = 8.4
low = "0.004*sin(2*PI*180*t)*between(t\\,2.5\\,6.0)"
loud = "0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,6.5\\,8.0))"
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={loud}+{low}:s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)

# Whisper SÍ oyó la frase baja: palabras cronometradas DENTRO de [2.5,6.0]
low_words = [{"start": round(t, 2), "end": round(t + 0.45, 2), "text": txt}
             for t, txt in [(2.6, "Su"), (3.2, "padre"), (3.8, "Filipo"),
                            (4.5, "convirtiendo"), (5.2, "provincia"),
                            (5.7, "periférica.")]]
segments = [
    {"start": 0.3, "end": 2.0, "text": "Frase inicial fuerte.",
     "words": [{"start": 0.4, "end": 0.9, "text": "Frase"},
               {"start": 1.0, "end": 1.5, "text": "inicial"},
               {"start": 1.55, "end": 1.98, "text": "fuerte."}]},
    {"start": 2.6, "end": 6.0, "text": "Su padre Filipo convirtiendo provincia periférica.",
     "words": low_words},
    {"start": 6.5, "end": 8.0, "text": "Cierre final fuerte.",
     "words": [{"start": 6.6, "end": 7.0, "text": "Cierre"},
               {"start": 7.1, "end": 7.5, "text": "final"},
               {"start": 7.55, "end": 7.98, "text": "fuerte."}]},
]
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 2.6,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 2.6, "audio_end": 6.5,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 3, "narration": "c", "audio_start": 6.5, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
print("T1 la frase dicha en voz baja NO se borra")
sils45 = detect_silences(src, noise_db=-45, min_d=0.08)
print(f"     silencios a -45: {[(round(a,2),round(b,2)) for a,b in sils45]}")
big = next(((a, b) for a, b in sils45 if a < 3.0 < b and b - a > 1.5), None)
check("el pasaje bajo se marca como 'silencio' a -45 dB (reproduce el fallo)",
      big is not None and big[0] < 2.6 and big[1] > 5.7, str(big))

out, _, _, chk, vmap = _build_timeline(scenes, {"segments": segments,
                                       "file": "narr.wav"}, dict(CFG), src,
                                       TMP, TOTAL, FPS)
print(f"     inserciones: {vmap['insertions']}  quiet_spans: {vmap['quiet_spans']}")
comps = [(p, d) for p, d in vmap["insertions"] if d < 0]
# ningún recorte dentro del pasaje hablado bajo
in_low = [(p, d) for p, d in comps if 2.3 <= p <= 6.2]
check("NINGÚN recorte cae en el pasaje hablado bajo (frase preservada)",
      not in_low, f"recortes en la zona: {in_low}")
check("se AVISA del habla baja (quiet_spans)", len(vmap["quiet_spans"]) >= 1,
      str(vmap["quiet_spans"]))
qs = vmap["quiet_spans"][0] if vmap["quiet_spans"] else (0, 0, 0)
check("el aviso cubre la zona de la frase baja",
      qs[0] <= 2.6 and qs[1] >= 5.7, str(qs))
# la voz baja (medida a -55) sigue presente en la salida
tl_dur = probe_duration(out)
src_low = sum(min(e, 6.0) - max(s, 2.5)
              for s, e in [(2.5, 6.0)])  # 3.5s de "voz" baja en la fuente
tl_v55 = tl_dur - sum(e - s for s, e in detect_silences(out, noise_db=-55, min_d=0.05))
src_v55 = TOTAL - sum(e - s for s, e in detect_silences(src, noise_db=-55, min_d=0.05))
check("el contenido bajo (a -55) se conserva íntegro en la salida",
      abs(tl_v55 - src_v55) < 0.3, f"{tl_v55:.2f} vs {src_v55:.2f}")
check("autocomprobación en verde", chk is None, str(chk))

# ---- T2: un silencio de VERDAD (sin palabras) sí se comprime ----
print("T2 un silencio real (sin palabras) sí se comprime")
loud2 = "0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,6.0\\,8.0))"
src2 = TMP / "narr2.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={loud2}:s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src2)], check=True)
seg2 = [
    {"start": 0.3, "end": 2.0, "text": "Frase inicial completa.",
     "words": [{"start": 0.4, "end": 0.9, "text": "Frase"},
               {"start": 1.0, "end": 1.5, "text": "inicial"},
               {"start": 1.55, "end": 1.98, "text": "completa."}]},
    {"start": 6.0, "end": 8.0, "text": "Cierre final.",
     "words": [{"start": 6.1, "end": 6.6, "text": "Cierre"},
               {"start": 6.7, "end": 7.9, "text": "final."}]},
]
sc2 = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 6.0,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 6.0, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
_, _, _, _, vmap2 = _build_timeline(sc2, {"segments": seg2, "file": "narr2.wav"},
                                    dict(CFG), src2, TMP, TOTAL, FPS)
comps2 = [(p, d) for p, d in vmap2["insertions"] if d < 0]
print(f"     inserciones: {vmap2['insertions']}  quiet_spans: {vmap2['quiet_spans']}")
check("el silencio real (sin palabras) SÍ se comprime", len(comps2) >= 1,
      str(vmap2))
check("sin falsos avisos de voz baja en un silencio real",
      not vmap2["quiet_spans"], str(vmap2["quiet_spans"]))

# ---- T3: subtítulos cortos estilo cine ----
print("T3 subtítulos cortos, una frase/cláusula por bloque")
txt = ("En el 336 antes de Cristo, Alejandro asume el control de Macedonia. "
       "No heredó un reino estable, sino una corona manchada de sangre. "
       "Su padre, Filipo II, había convertido una provincia periférica.")
words = []
t = 0.0
for tok in txt.split():
    words.append({"start": round(t, 2), "end": round(t + 0.3, 2), "text": tok})
    t += 0.35
MAXC, MAXL = 32, 2
blocks = _chunks_words(words, MAXC, MAXL)
print(f"     {len(blocks)} bloques:")
for tx, _bw in blocks:
    print("       | " + tx.replace("\n", " ⏎ "))
check("se generan varios bloques cortos (no un párrafo)", len(blocks) >= 5,
      f"{len(blocks)} bloques")
longest_line = max((len(ln) for tx, _ in blocks for ln in tx.split("\n")),
                   default=0)
check(f"ninguna LÍNEA supera max_chars+holgura ({MAXC}+6)",
      longest_line <= MAXC + 6, f"línea más larga={longest_line}")
max_block_lines = max((tx.count("\n") + 1 for tx, _ in blocks), default=0)
check(f"ningún bloque supera max_lines ({MAXL})", max_block_lines <= MAXL,
      f"máx líneas/bloque={max_block_lines}")
# la mayoría de los bloques cierran en puntuación (frase/cláusula)
def ends_punct(tx):
    return tx.rstrip().rstrip("»\"')”").endswith((".", ",", ";", ":", "!", "?", "…"))
ratio = sum(1 for tx, _ in blocks if ends_punct(tx)) / max(1, len(blocks))
check("la mayoría de bloques cierran en puntuación (corte por frase)",
      ratio >= 0.6, f"ratio={ratio:.2f}")
# no se pierde ninguna palabra
n_words_out = sum(len(bw) for _, bw in blocks)
check("no se pierde ninguna palabra al trocear", n_words_out == len(words),
      f"{n_words_out} vs {len(words)}")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
