"""Batería v0.25.2: la salvaguarda de "voz baja" ya no confunde una PAUSA
REAL (con una palabra de Whisper desviada dentro) con habla baja.

Diagnóstico sobre el audio REAL del usuario (profesional): las pausas de
25s, 32s, 47s, 62s se marcaban como "habla muy baja" porque UNA palabra de
Whisper caía dentro (deriva ±0.3s) — y v0.25.1 iba a AMPLIFICAR el ruido de
esas pausas. Ahora se exige que las palabras LLENEN el hueco (>55%) y sean
>=2 para marcarlo; y el realce nunca toca algo por debajo de -55 dB.

T1  Pausa real (silencio) con 1 palabra desviada dentro → NO se marca ni se
    comprime pisando habla; se comprime como pausa normal.
T2  Frase dicha en voz baja (palabras que LLENAN el hueco) → SÍ se marca y se
    realza (no se pierde la protección real).
T3  boost_quiet_spans NO amplifica un tramo que es silencio de verdad (<-55).
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
from ytstudio.utils.media import (boost_quiet_spans, detect_silences,
                                  probe_duration, _segment_mean_db)

TMP = Path(__file__).parent / "t252"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


CFG = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2, "cut_guard": 0.20,
                 "onset_guard": 0.45, "deep_silence_db": -55}}
TOTAL = 8.4

print("T1 pausa real con UNA palabra desviada dentro → NO es 'voz baja'")
# A fuerte [0.3-2.0] | PAUSA real [2.0-6.0] (silencio de verdad) | B [6.5-8.0]
loud = "0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,6.5\\,8.0))"
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={loud}:s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)
# Whisper deja UNA palabra desviada en mitad de la pausa (t=4.0), como en el
# audio real; las demás están en el habla.
segments = [
    {"start": 0.3, "end": 2.0, "text": "Frase inicial completa.",
     "words": [{"start": 0.4, "end": 0.9, "text": "Frase"},
               {"start": 1.0, "end": 1.5, "text": "inicial"},
               {"start": 1.55, "end": 1.98, "text": "completa."},
               {"start": 4.0, "end": 4.35, "text": "desviada"}]},  # ← en la pausa
    {"start": 6.5, "end": 8.0, "text": "Cierre final.",
     "words": [{"start": 6.6, "end": 7.0, "text": "Cierre"},
               {"start": 7.1, "end": 7.9, "text": "final."}]},
]
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 6.5,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 6.5, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
out, _, _, chk, vmap = _build_timeline(scenes, {"segments": segments}, dict(CFG),
                                       src, TMP, TOTAL, 24.0)
print(f"     quiet_spans={vmap['quiet_spans']}  comp={vmap['n_comp']}")
check("la pausa real NO se marca como voz baja (1 palabra desviada)",
      not vmap["quiet_spans"], str(vmap["quiet_spans"]))
check("la pausa real SÍ se comprime (como pausa normal)",
      vmap["n_comp"] >= 1, str(vmap))
# y la voz fuerte sigue intacta
tl = probe_duration(out)
sp_src = TOTAL - sum(e - s for s, e in detect_silences(src, -45, 0.2))
sp_out = tl - sum(e - s for s, e in detect_silences(out, -45, 0.2))
check("la voz fuerte se conserva exacta", abs(sp_out - sp_src) < 0.15,
      f"{sp_src:.2f} vs {sp_out:.2f}")

print("T2 frase en voz baja que LLENA el hueco → sí se marca (protección real)")
low = "0.004*sin(2*PI*180*t)*between(t\\,2.4\\,5.9)"  # ~-48 dB (bajo el umbral)
src2 = TMP / "narr2.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={loud}+{low}:s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src2)], check=True)
low_words = [{"start": round(2.45 + i * 0.43, 2), "end": round(2.45 + i * 0.43 + 0.4, 2),
              "text": f"baja{i}"} for i in range(8)]  # 8 palabras LLENANDO [2.45,5.85]
seg2 = [
    {"start": 0.3, "end": 2.0, "text": "Frase inicial completa.",
     "words": [{"start": 0.4, "end": 0.9, "text": "Frase"},
               {"start": 1.0, "end": 1.98, "text": "completa."}]},
    {"start": 2.5, "end": 5.9, "text": "seis palabras dichas muy bajito seguidas.",
     "words": low_words},
    {"start": 6.5, "end": 8.0, "text": "Cierre final.",
     "words": [{"start": 6.6, "end": 7.9, "text": "final."}]},
]
sc2 = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 2.5,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 2.5, "audio_end": 6.5,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 3, "narration": "c", "audio_start": 6.5, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
out2, _, _, _, vmap2 = _build_timeline(sc2, {"segments": seg2}, dict(CFG),
                                       src2, TMP, TOTAL, 24.0)
print(f"     quiet_spans={vmap2['quiet_spans']}")
check("la frase baja que llena el hueco SÍ se marca (se protege y realza)",
      len(vmap2["quiet_spans"]) >= 1, str(vmap2["quiet_spans"]))

print("T3 boost no amplifica silencio de verdad (< -55 dB)")
silsrc = TMP / "sil.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "3",
                "-c:a", "pcm_s16le", str(silsrc)], check=True)
before = _segment_mean_db(silsrc, 0.5, 2.5)
out3 = boost_quiet_spans(silsrc, [(0.5, 2.5)], TMP / "sil_out.wav")
after = _segment_mean_db(out3, 0.5, 2.5)
check("un silencio real no se amplifica (sigue en silencio)",
      (after is None) or (before is None) or abs(after - before) < 1.0,
      f"{before}→{after}")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
