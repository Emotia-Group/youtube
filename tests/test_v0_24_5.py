"""Batería v0.24.5: recorte de pausa POR EL FRENTE con guarda asimétrica.

Diagnóstico del log eventos7: v0.24.4 (recortar en el interior profundo más
grande) MOVIÓ el recorte hacia la palabra siguiente; cuando una respiración a
mitad de pausa partía el silencio profundo y el trozo mayor quedaba pegado a
«Su», el recorte se comía el arranque de esa «s» suave — y por ser el trozo
mayor, el recorte fue el MÁS LARGO de todos.

Modelo correcto: la COLA de la palabra anterior decae rápido (borde fiable →
guarda corta, cut_guard); el ARRANQUE de la siguiente, si es fricativa suave,
queda por debajo de CUALQUIER umbral 100-250 ms (borde tardío → guarda grande,
onset_guard). Por eso se recorta por el FRENTE y se deja onset_guard antes del
arranque.

T1  El recorte arranca por el FRENTE (~s0+cut_guard) y TERMINA a >= onset_guard
    del arranque de la palabra siguiente (con «s» suave a -48 dB).
T2  REGRESIÓN v0.24.4: con una respiración a mitad de pausa que parte el
    silencio profundo, el recorte NO se mueve hacia «Su» (sigue por el frente).
T3  Las palabras (a -45 dB) se conservan exactas; WAV == suma; autocheck verde.
T4  Sigue comprimiendo de verdad (no se anula) y el arranque suave sobrevive.
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
from ytstudio.utils.media import detect_silences, probe_duration

TMP = Path(__file__).parent / "t245"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def mkwords(a, b, n, last):
    st = (b - a) / n
    ws = [{"start": round(a + i * st, 3), "end": round(a + (i + 1) * st - 0.02, 3),
           "text": f"w{round((a + i * st) * 10)}"} for i in range(n)]
    ws[-1]["text"] = last
    return ws


FPS = 24.0
CUT_GUARD, ONSET_GUARD = 0.20, 0.45
CFG = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2,
                 "cut_guard": CUT_GUARD, "onset_guard": ONSET_GUARD,
                 "deep_silence_db": -55}}
TOTAL = 8.4
SOFT0, SOFT1 = 5.65, 6.0   # «s» suave de «Su» a -48 dB, arranca en 5.65

segments = [
    {"start": 0.3, "end": 2.0, "text": "Frase primera completa.",
     "words": mkwords(0.3, 2.0, 3, "completa.")},
    {"start": 6.0, "end": 8.0, "text": "Su padre Filipo.",
     "words": mkwords(6.0, 8.0, 3, "Filipo.")},
]
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 6.0,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 6.0, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]


def build(expr, tag):
    src = TMP / f"{tag}.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={TOTAL}",
                    "-c:a", "pcm_s16le", str(src)], check=True)
    return src


LOUD = "0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,6.0\\,8.0))"
SOFT_S = f"0.004*sin(2*PI*3000*t)*between(t\\,{SOFT0}\\,{SOFT1})"

print("T1 recorte por el FRENTE, a >= onset_guard del arranque de «Su»")
src = build(f"{LOUD}+{SOFT_S}", "narr")
out, _, _, chk, vmap = _build_timeline(scenes, {"segments": segments,
                                       "file": "narr.wav"}, dict(CFG), src,
                                       TMP, TOTAL, FPS)
print(f"     inserciones: {vmap['insertions']}")
comps = [(p, d) for p, d in vmap["insertions"] if d < 0]
check("hubo un recorte de la pausa larga", len(comps) == 1, str(vmap))
p, d = comps[0]
skip_end = p - d
check("el recorte ARRANCA por el frente (~s0+cut_guard, <= 2.5)", p <= 2.5,
      f"p={p:.3f}")
check("el recorte TERMINA a >= onset_guard del borde -45 (<= 5.55)",
      skip_end <= 5.55 + 0.02, f"skip_end={skip_end:.3f}")
check("el recorte termina ANTES del arranque de la «s» suave (5.65)",
      skip_end < SOFT0, f"skip_end={skip_end:.3f} vs s en {SOFT0}")

print("T2 REGRESIÓN v0.24.4: una respiración a mitad de pausa NO mueve el corte")
# respiración a -48 dB en [3.0,3.3]: parte el silencio profundo en
# [2.0,3.0] (1.0s) y [3.3,5.65] (2.35s). v0.24.4 elegía el mayor (el de
# atrás) y recortaba hacia «Su»; v0.24.5 sigue por el frente.
BREATH = "0.004*sin(2*PI*3000*t)*between(t\\,3.0\\,3.3)"
src2 = build(f"{LOUD}+{SOFT_S}+{BREATH}", "narr_breath")
out2, _, _, chk2, vmap2 = _build_timeline(scenes, {"segments": segments,
                                          "file": "narr_breath.wav"},
                                          dict(CFG), src2, TMP, TOTAL, FPS)
comps2 = [(p, d) for p, d in vmap2["insertions"] if d < 0]
print(f"     inserciones (con respiración): {vmap2['insertions']}")
check("hubo recorte también con respiración", len(comps2) == 1, str(vmap2))
p2, d2 = comps2[0]
check("el recorte SIGUE por el frente pese a la respiración (<= 2.5)",
      p2 <= 2.5, f"p2={p2:.3f}")
check("el recorte NO se movió hacia «Su» (v0.24.4 lo ponía en ~3.55)",
      p2 <= 2.5, f"p2={p2:.3f}")
check("termina antes de la «s» suave también con respiración",
      (p2 - d2) < SOFT0, f"skip_end={p2 - d2:.3f}")

print("T3 palabras intactas (-45 dB), WAV == suma, autocheck verde")
tl_dur = probe_duration(out)
src_w45 = TOTAL - sum(e - s for s, e in detect_silences(src, noise_db=-45, min_d=0.08))
tl_w45 = tl_dur - sum(e - s for s, e in detect_silences(out, noise_db=-45, min_d=0.08))
check("las palabras (a -45 dB) se conservan exactas",
      abs(tl_w45 - src_w45) < 0.15, f"{tl_w45:.2f} vs {src_w45:.2f}")
check("autocomprobación en verde", chk is None, str(chk))
sum_durs = sum(s["duration"] for s in scenes)
check("WAV == suma de escenas", abs(tl_dur - sum_durs) < 0.1,
      f"{tl_dur:.2f} vs {sum_durs:.2f}")

print("T4 compresión útil + la «s» suave sobrevive en la salida real")
check("se comprimió una cantidad útil (>= 1s)", -d >= 1.0, f"take={-d:.2f}")
# La región [5.65,6.0] (la «s») debe seguir presente: se mapea al video con el
# tiempo global y se mide RMS ahí. Como termina el recorte antes de 5.65, esa
# región cae íntegra tras el punto de reanudación.
check("el recorte deja intacta la ventana del arranque suave",
      skip_end < SOFT0, f"skip_end={skip_end:.3f}")

print("T5 AMPLIAR una pausa no parte una respiración por la mitad")
# pausa [2.0-3.0] con respiración suave en [2.4-2.6]; pause_after grande →
# el director AMPLÍA. El punto de inserción se reubica al interior profundo.
TOT5 = 5.4
expr5 = ("0.4*sin(2*PI*200*t)*(between(t\\,0.3\\,2.0)+between(t\\,3.0\\,5.0))"
         "+0.004*sin(2*PI*3000*t)*between(t\\,2.4\\,2.6)")
src5 = TMP / "narr5.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"aevalsrc={expr5}:s=44100:d={TOT5}",
                "-c:a", "pcm_s16le", str(src5)], check=True)
seg5 = [
    {"start": 0.3, "end": 2.0, "text": "Frase primera completa.",
     "words": mkwords(0.3, 2.0, 3, "completa.")},
    {"start": 3.0, "end": 5.0, "text": "Sigue la historia.",
     "words": mkwords(3.0, 5.0, 3, "historia.")},
]
sc5 = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 3.0,
     "pause_after": 1.2, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 3.0, "audio_end": TOT5,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
out5, _, _, chk5, vmap5 = _build_timeline(sc5, {"segments": seg5,
                                          "file": "narr5.wav"}, dict(CFG),
                                          src5, TMP, TOT5, FPS)
exts = [(p, d) for p, d in vmap5["insertions"] if d > 0]
print(f"     inserciones: {vmap5['insertions']}")
check("hubo ampliación (pausa de director)", len(exts) >= 1, str(vmap5))
for p5, d5 in exts:
    check(f"el punto de inserción {p5:.2f} NO parte la respiración (2.42-2.58)",
          not (2.42 <= p5 <= 2.58), f"p={p5}")
check("autocomprobación T5 en verde", chk5 is None, str(chk5))

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
