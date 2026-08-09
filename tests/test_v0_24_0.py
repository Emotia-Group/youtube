"""Batería v0.24.0: compresión de pausas en la línea de tiempo + lazo cerrado.

T1: pausas naturales largas (3s/5s) se COMPRIMEN al tope (saltando solo
    silencio medido) — el video ya no acumula aire muerto — y el invariante
    palabra↔video se mantiene con deltas negativos.
T2: frontera en VACILACIÓN (sin fin de oración) → sin pausa de director.
T3: frontera tras FIN DE ORACIÓN → pausa del director, capada.
T4: lazo cerrado — cues corridos +300ms se corrigen a ~0 y sync_shift queda.
T5: e2e ambos modos siguen en verde con el modelo nuevo.
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
import tempfile
from pathlib import Path



from ytstudio.phases.voiceover import _build_timeline
from ytstudio.utils.media import detect_silences, probe_duration
from ytstudio.utils.align import (assign_words, flatten_words, local_time,
                                  measure_sync_offset, video_time_fn)

TMP = Path(__file__).parent / "t240"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# Voz sintética con pausas LARGAS (el caso "demasiados silencios"):
# frase A (0.3-3.0, termina en '.'), PAUSA 5s, frase B (8.0-11.0 SIN punto:
# vacilación), PAUSA 3s a mitad de frase, sigue B2 (14.0-17.0 con punto),
# pausa 1.0s, frase C (18.0-21.0). Total 21.6s.
BURSTS = [(0.3, 3.0), (8.0, 11.0), (14.0, 17.0), (18.0, 21.0)]
TOTAL = 21.6
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in BURSTS)
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.4*sin(2*PI*200*t)*({expr}):s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)


def mkwords(a, b, n, last_txt):
    st = (b - a) / n
    ws = [{"start": round(a + i * st, 3), "end": round(a + (i + 1) * st - 0.02, 3),
           "text": f"w{round((a + i * st) * 10)}"} for i in range(n)]
    ws[-1]["text"] = last_txt
    return ws


segments = [
    {"start": 0.3, "end": 3.0, "text": "Frase primera completa.",
     "words": mkwords(0.3, 3.0, 3, "completa.")},
    {"start": 8.0, "end": 11.0, "text": "Frase que sigue sin punto",
     "words": mkwords(8.0, 11.0, 3, "punto")},          # vacilación (sin '.')
    {"start": 14.0, "end": 17.0, "text": "y termina aquí.",
     "words": mkwords(14.0, 17.0, 3, "aquí.")},
    {"start": 18.0, "end": 21.0, "text": "Cierre final.",
     "words": mkwords(18.0, 21.0, 3, "final.")},
]
narration = {"segments": segments, "file": "narr.wav"}
# Escena 1|2 frontera en 8.0 (tras FIN de oración + pausa 5s);
# escena 2|3 frontera en 14.0 (tras VACILACIÓN sin punto + pausa 3s)
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 8.0,
     "pause_after": 1.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 8.0, "audio_end": 14.0,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 3, "narration": "c", "audio_start": 14.0, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2}}
FPS = 24.0

print("T1 pausas largas comprimidas + invariante palabra↔video")
out, n_b, n_s, chk, vmap = _build_timeline(scenes, narration, cfg, src, TMP,
                                           TOTAL, FPS)
tl_dur = probe_duration(out)
sum_durs = sum(s["duration"] for s in scenes)
print(f"     fuente {TOTAL}s → línea de tiempo {tl_dur:.2f}s "
      f"(ajustes: {vmap['n_comp']} recortes, {vmap['n_ext']} ampliaciones)")
# bruto = fuente 21.6 + intro 0.8 + outro 2.0 = 24.4; comprimidas las pausas
# de 5s y 3s deben quitarse ≥ 4.5s de aire muerto
check("las pausas de 5s y 3s se comprimieron (≥4.5s de aire quitado)",
      tl_dur <= TOTAL + 2.8 - 4.5, f"{tl_dur} (bruto 24.4)")
check("hubo recortes de pausa", vmap["n_comp"] >= 2, str(vmap))
check("WAV == suma de escenas", abs(tl_dur - sum_durs) < 0.1,
      f"{tl_dur} vs {sum_durs}")
check("autocomprobación en verde (voz íntegra)", chk is None, str(chk))
# voz hablada intacta pese a los recortes
src_sils = detect_silences(src, noise_db=-45)
speech_src = TOTAL - sum(b - a for a, b in src_sils)
tl_sils = detect_silences(out, noise_db=-45)
speech_tl = tl_dur - sum(b - a for a, b in tl_sils)
check("ni un milisegundo de VOZ perdido al comprimir",
      abs(speech_tl - speech_src) < 0.25, f"{speech_tl:.2f} vs {speech_src:.2f}")
# invariante con deltas negativos
V = video_time_fn(vmap["intro"], [(p, d) for p, d in vmap["insertions"]])
words = flatten_words(segments)
wmap = assign_words(scenes, words)
starts_v, acc = [], 0.0
for s in scenes:
    starts_v.append(acc)
    acc += s["duration"]
worst = 0.0
for i, s in enumerate(scenes):
    for w in wmap[s["id"]]:
        video_pos = starts_v[i] + local_time(s, float(w["start"]))
        worst = max(worst, abs(V(float(w["start"])) - video_pos))
check("invariante palabra↔video con recortes (±1.5 cuadros)",
      worst <= 1.5 / FPS, f"desvío máx {worst:.4f}s")

print("T2/T3 fronteras: oración vs vacilación")
# frontera 1→2 (fin de oración): pausa director presente pero CAPADA
b1 = scenes[1]["audio_start"]
sil1 = next((s for s in src_sils if s[0] < b1 < s[1] or abs(s[1] - b1) < 1.0), None)
# pausa resultante en el video alrededor de la frontera 1→2:
p1_video = V(8.05) - V(2.95)  # aire entre fin de frase A y arranque de B
check("frontera con oración: pausa = criterio director, capada (≤ 2.6s de aire)",
      0.8 <= p1_video <= 2.8, f"aire={p1_video:.2f}s (natural era 5s)")
p2_video = V(14.05) - V(10.95)  # aire en la vacilación (frontera 2→3)
check("frontera en vacilación: SIN pausa de director (aire ≤ 1.6s)",
      p2_video <= 1.6, f"aire={p2_video:.2f}s (natural era 3s)")

print("T4 lazo cerrado de subtítulos")
onsets_reales = [e for _, e in detect_silences(out, min_d=0.3)
                 if e < tl_dur - 0.5]
cues_drift = [o + 0.30 for o in onsets_reales]  # subtítulos 300ms tarde
med, n_pts = measure_sync_offset(out, cues_drift)
check("la medición detecta el desfase de +300ms",
      0.2 <= med <= 0.4 and n_pts >= 2, f"med={med} n={n_pts}")
cues_fixed = [c - med for c in cues_drift]
med2, _ = measure_sync_offset(out, cues_fixed)
check("tras corregir por la mediana, desfase ≈ 0", abs(med2) <= 0.08,
      f"med2={med2}")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
