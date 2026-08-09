"""Batería v0.25.1: (1) realzar habla dicha muy baja para que se OIGA +
(2) subtítulos globales sin huérfanas ni solapes de 3 líneas.

Diagnóstico (log eventos8): las compresiones sumaban ~2.3s (imposible borrar
una frase), la pista tenía la longitud completa → NADA se borraba. El
«recorte largo» era una frase CONSERVADA pero tan baja que no se oía (solo la
sílaba fuerte). Fix: realzar solo esos tramos (quiet_spans) a nivel audible.

Subtítulos (imágenes): «El» sola al inicio de escena y «Cuando» en una 3ª
línea fugaz — troceo POR ESCENA partía frases en la frontera + cues
solapados. Fix: troceo GLOBAL + sin solapes.

T1  boost_quiet_spans sube el tramo bajo a nivel audible sin tocar el resto.
T2  Tras realzar en _build_timeline, la frase baja se OYE (a -45 dB ya cuenta
    como voz) y no salta la autocomprobación.
T3  Subtítulos: troceo global, ninguna palabra huérfana en fronteras, sin
    solapes (ningún cue empieza antes de que acabe el anterior), <= 2 líneas.
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



from ytstudio.phases.subtitles import build_cues
from ytstudio.phases.voiceover import _build_timeline
from ytstudio.utils.media import (boost_quiet_spans, detect_silences,
                                  probe_duration, _segment_mean_db)

TMP = Path(__file__).parent / "t251"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# --- audio con un tramo hablado MUY BAJO (-48 dB) entre dos fuertes ---
TOTAL = 8.4
low = "0.004*sin(2*PI*180*t)*between(t\\,2.5\\,6.0)"      # ~-48 dB (habla baja)
loud = "0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,6.5\\,8.0))"
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={loud}+{low}:s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)

print("T1 boost_quiet_spans realza solo el tramo bajo")
mean_before = _segment_mean_db(src, 2.5, 6.0)
out_b = boost_quiet_spans(src, [(2.4, 6.1)], TMP / "boosted.wav")
mean_after = _segment_mean_db(out_b, 2.5, 6.0)
loud_before = _segment_mean_db(src, 0.3, 2.0)
loud_after = _segment_mean_db(out_b, 0.3, 2.0)
print(f"     tramo bajo: {mean_before:.1f} dB → {mean_after:.1f} dB | "
      f"fuerte: {loud_before:.1f} → {loud_after:.1f} dB")
check("el tramo bajo sube claramente (>= 10 dB)",
      mean_after - mean_before >= 10, f"Δ={mean_after - mean_before:.1f}")
check("el tramo fuerte NO se toca (±1 dB)", abs(loud_after - loud_before) < 1.0,
      f"{loud_before:.1f}→{loud_after:.1f}")
check("tras realzar, el tramo bajo pasa el umbral de -45 dB",
      mean_after > -45, f"{mean_after:.1f} dB")

print("T2 _build_timeline realza la frase baja y la deja audible")
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
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2, "cut_guard": 0.20,
                 "onset_guard": 0.45, "deep_silence_db": -55}}
out, _, _, chk, vmap = _build_timeline(scenes, {"segments": segments,
                                       "file": "narr.wav"}, dict(cfg), src,
                                       TMP, TOTAL, 24.0)
check("se detectó la frase baja (quiet_spans)", len(vmap["quiet_spans"]) >= 1,
      str(vmap["quiet_spans"]))
# en la SALIDA, el tramo de la frase baja ya NO es 'silencio' a -45 (se oye)
tl_sils = detect_silences(out, noise_db=-45, min_d=0.2)
# mapear el tramo original [2.6,6.0] al video: intro 0.8 (sin inserciones antes)
lo_v, hi_v = 0.8 + 2.6, 0.8 + 6.0
covered = any(s <= lo_v + 0.3 and e >= hi_v - 0.3 for s, e in tl_sils)
check("la frase baja YA NO es un hueco silencioso en la salida (se oye)",
      not covered, f"silencios salida={[(round(a,1),round(b,1)) for a,b in tl_sils]}")
check("autocomprobación en verde (realzar no dispara falsa deriva)",
      chk is None, str(chk))

print("T3 subtítulos globales: sin huérfanas ni solapes")
# Dos escenas cuya frontera parte una oración: '... no habla de' | 'Cuando ...'
# y '... misticismo.' | 'El propio Alejandro ...'
segs = [
    {"start": 0.0, "end": 3.0, "text": "La narrativa oficial no habla de esto.",
     "words": [{"start": 0.2 + i * 0.4, "end": 0.5 + i * 0.4, "text": w}
               for i, w in enumerate(["La", "narrativa", "oficial", "no", "habla", "de", "esto."])]},
    {"start": 3.0, "end": 6.5, "text": "Cuando cruza a Asia Menor, todo cambió.",
     "words": [{"start": 3.0 + i * 0.4, "end": 3.3 + i * 0.4, "text": w}
               for i, w in enumerate(["Cuando", "cruza", "a", "Asia", "Menor,", "todo", "cambió."])]},
    {"start": 6.5, "end": 9.0, "text": "El propio Alejandro alimentó el mito.",
     "words": [{"start": 6.5 + i * 0.4, "end": 6.8 + i * 0.4, "text": w}
               for i, w in enumerate(["El", "propio", "Alejandro", "alimentó", "el", "mito."])]},
]
sub_scenes = [
    {"id": 1, "audio_start": 0.0, "audio_end": 3.0, "duration": 3.5, "narration": "a"},
    {"id": 2, "audio_start": 3.0, "audio_end": 6.5, "duration": 4.0, "narration": "b"},
    {"id": 3, "audio_start": 6.5, "audio_end": 9.0, "duration": 3.0, "narration": "c"},
]
vmap_sub = {"intro": 0.5, "insertions": []}
cues = build_cues(sub_scenes, 32, 2, {"segments": segs}, vmap_sub)
print(f"     {len(cues)} cues:")
for c in cues:
    print(f"       [{c['start']:.2f}-{c['end']:.2f}] " + c["text"].replace("\n", " ⏎ "))
# ninguna palabra huérfana: 'El' y 'Cuando' no aparecen SOLAS en un cue
solo = [c["text"] for c in cues if c["text"].strip() in ("El", "Cuando")]
check("ninguna palabra huérfana ('El'/'Cuando' solas)", not solo, str(solo))
# sin solapes
overlaps = [(cues[i]["end"], cues[i + 1]["start"]) for i in range(len(cues) - 1)
            if cues[i]["end"] > cues[i + 1]["start"] + 1e-6]
check("ningún cue se solapa con el siguiente", not overlaps, str(overlaps))
# <= 2 líneas
maxl = max((c["text"].count("\n") + 1 for c in cues), default=0)
check("ningún cue supera 2 líneas", maxl <= 2, f"máx={maxl}")
# 'Cuando' arranca su propio cue (primera palabra de su frase)
cuando_ok = any(c["text"].startswith("Cuando") for c in cues)
check("'Cuando' arranca su cue (no colgada al final del anterior)", cuando_ok)
check("'El' arranca su cue con su frase", any(c["text"].startswith("El propio")
      for c in cues), str([c["text"][:12] for c in cues]))

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
