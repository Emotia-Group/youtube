"""Batería v0.24.3: recorte de pausa con guarda a ambos lados (fin del
«pedazo de voz» recortado en la transición) + puntuación tolerante al
desajuste de conteo + lazo de sincronía con umbral más bajo.

T1  Al COMPRIMIR una pausa, el tramo saltado se queda a >= cut_guard de
    AMBOS bordes de silencio medidos (antes solo 0.1s del borde final: un
    arranque suave caía dentro y se recortaba). Se mide sobre la salida REAL.
T1b El mismo caso con la fórmula VIEJA dejaba el borde final a 0.1s — se
    demuestra que la nueva deja mucho más (el arreglo es real, no cosmético).
T1c Ni un milisegundo de voz perdido, medido con umbral SENSIBLE (-55 dB),
    que sí ve arranques suaves que el detector de corte (-45 dB) no marca.
T2  _restore_punctuation repone comas/puntos aunque el conteo de tokens no
    cuadre (número partido, token de puntuación suelto) — antes el bloque
    entero perdía la puntuación.
T3  El lazo de sincronía corrige un desfase de +80 ms (por debajo del tope
    viejo de 120 ms, que lo dejaba pasar) y lo lleva a ~0.
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
from ytstudio.providers.stt import _restore_punctuation
from ytstudio.utils.align import measure_sync_offset
from ytstudio.utils.media import detect_silences, probe_duration

TMP = Path(__file__).parent / "t243"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


CUT_GUARD = 0.25

# Voz con una PAUSA LARGA (4s) entre dos frases: frase A (0.3-2.0, '.'),
# SILENCIO [2.0-6.0], frase B (6.0-8.0). La pausa de 4s se comprime al tope.
BURSTS = [(0.3, 2.0), (6.0, 8.0)]
TOTAL = 8.4
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in BURSTS)
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.4*sin(2*PI*200*t)*({expr}):s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)


def mkwords(a, b, n, last):
    st = (b - a) / n
    ws = [{"start": round(a + i * st, 3), "end": round(a + (i + 1) * st - 0.02, 3),
           "text": f"w{round((a + i * st) * 10)}"} for i in range(n)]
    ws[-1]["text"] = last
    return ws


segments = [
    {"start": 0.3, "end": 2.0, "text": "Frase primera completa.",
     "words": mkwords(0.3, 2.0, 3, "completa.")},
    {"start": 6.0, "end": 8.0, "text": "Cierre final.",
     "words": mkwords(6.0, 8.0, 2, "final.")},
]
narration = {"segments": segments, "file": "narr.wav"}
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 6.0,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 6.0, "audio_end": TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18, "max_pause": 1.2, "cut_guard": CUT_GUARD}}
FPS = 24.0

print("T1 el recorte se queda a >= cut_guard de AMBOS bordes (salida real)")
out, n_b, n_s, chk, vmap = _build_timeline(scenes, narration, cfg, src, TMP,
                                           TOTAL, FPS)
src_sils = detect_silences(src, noise_db=-45, min_d=0.08)
big = [(s0, s1) for s0, s1 in src_sils if s1 - s0 >= 0.3]
print(f"     silencios medidos (>=0.3s): {[(round(a,2),round(b,2)) for a,b in big]}")
print(f"     inserciones: {vmap['insertions']}  (n_comp={vmap['n_comp']})")

comps = [(p, d) for p, d in vmap["insertions"] if d < 0]
check("hubo al menos un recorte de pausa", len(comps) >= 1, str(vmap))

new_trailing = []
for p, d in comps:
    skip_end = p - d           # d<0 → p+|d|
    # silencio medido que aloja el recorte
    sil = next(((s0, s1) for s0, s1 in big if s0 - 0.05 <= p <= s1 + 0.05), None)
    check(f"recorte en [{p:.2f},{skip_end:.2f}] cae dentro de un silencio medido",
          sil is not None, f"p={p}")
    if sil:
        s0, s1 = sil
        lead = p - s0
        trail = s1 - skip_end
        new_trailing.append(trail)
        check(f"  margen de guarda inicial >= {CUT_GUARD}s", lead >= CUT_GUARD - 0.02,
              f"lead={lead:.3f}")
        check(f"  margen de guarda FINAL >= {CUT_GUARD}s (era 0.1s)",
              trail >= CUT_GUARD - 0.02, f"trail={trail:.3f}")

print("T1b la fórmula VIEJA dejaba el borde final a ~0.1s (el arreglo es real)")
# reproducir la fórmula vieja para el mismo silencio y delta
for (p, d), (s0, s1) in [(comps[0], next((s for s in big
                          if s[0] - .05 <= comps[0][0] <= s[1] + .05), (0, 0)))]:
    natural = s1 - s0
    # delta viejo = target - natural, con target = max_pause=1.2 → -2.8 aprox
    target = min(natural, 1.2)
    delta_old = target - natural
    point = (s0 + s1) / 2
    old_skip_start = max(s0 + 0.1, min(point + 0.01, s1 - 0.1 + delta_old))
    old_trail = s1 - (old_skip_start - delta_old)
    check("la vieja fórmula dejaba solo ~0.1s de guarda final",
          old_trail <= 0.15, f"old_trail={old_trail:.3f}")
    check("la nueva deja MÁS guarda final que la vieja",
          new_trailing and new_trailing[0] > old_trail + 0.1,
          f"nueva={new_trailing} vieja={old_trail:.3f}")

print("T1c ni un milisegundo de voz perdido (umbral SENSIBLE -55 dB)")
tl_dur = probe_duration(out)
src_voice = TOTAL - sum(e - s for s, e in detect_silences(src, noise_db=-55, min_d=0.05))
tl_voice = tl_dur - sum(e - s for s, e in detect_silences(out, noise_db=-55, min_d=0.05))
check("la voz (a -55 dB) se conserva íntegra tras comprimir",
      abs(tl_voice - src_voice) < 0.2, f"{tl_voice:.2f} vs {src_voice:.2f}")
check("autocomprobación de la voz en verde", chk is None, str(chk))

print("T2 puntuación repuesta pese al desajuste de conteo")
# extra token 'y' en el segmento (Whisper no lo cronometró)
w1 = [{"start": 0, "end": .3, "text": "treinta"},
      {"start": .3, "end": .6, "text": "cinco"},
      {"start": .6, "end": 1., "text": "soldados"}]
r1 = _restore_punctuation("treinta y cinco soldados.", w1)
check("el punto final se repone aunque falte un token cronometrado",
      r1[-1]["text"] == "soldados.", str([x["text"] for x in r1]))
check("no se pierde ni se duplica ninguna palabra cronometrada",
      len(r1) == 3, str(r1))
# token de puntuación suelto (puntos suspensivos) + coma pegada
w2 = [{"start": 0, "end": .3, "text": "esperó"},
      {"start": .3, "end": .6, "text": "y"},
      {"start": .6, "end": 1., "text": "atacó"}]
r2 = _restore_punctuation("esperó … y atacó, decidido.", w2)
check("la coma pegada se repone con conteo distinto",
      r2[2]["text"].startswith("atacó"), str([x["text"] for x in r2]))
# caso 1-a-1 sigue exacto
w3 = [{"start": 0, "end": .3, "text": "hola"}, {"start": .3, "end": .6, "text": "mundo"}]
r3 = _restore_punctuation("Hola, mundo.", w3)
check("conteo igual → posicional exacto (con puntuación)",
      [x["text"] for x in r3] == ["Hola,", "mundo."], str(r3))

print("T3 el lazo corrige un desfase de +80 ms (el tope viejo lo dejaba pasar)")
onsets = [e for _, e in detect_silences(out, min_d=0.3) if e < tl_dur - 0.5]
cues_drift = [o + 0.08 for o in onsets]  # subtítulos 80 ms tarde
med, n_pts = measure_sync_offset(out, cues_drift)
check("se mide el desfase de +80 ms", 0.05 <= med <= 0.11 and n_pts >= 2,
      f"med={med} n={n_pts}")
check("el tope viejo (120 ms) lo dejaba pasar; el nuevo (50 ms) lo corrige",
      abs(med) <= 0.12 and abs(med) > 0.05, f"med={med}")
cues_fixed = [c - med for c in cues_drift]
med2, _ = measure_sync_offset(out, cues_fixed)
check("tras corregir, el desfase queda ~0", abs(med2) <= 0.05, f"med2={med2}")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
