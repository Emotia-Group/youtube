"""Batería v24: motor de pausas dirigido por el director sobre cortes en
huecos entre palabras.

INVARIANTE CENTRAL: todo silencio insertado cae ESTRICTAMENTE dentro de un
silencio real de la grabación (entre dos palabras) -> imposible partir voz.
Reproduce además el bug del "segundo 11": frontera de escena colocada a mitad
de palabra por el atomizador -> el respiro se re-ancla a un hueco seguro.
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



from ytstudio.phases.voiceover import _build_timeline, _sync_overlays
from ytstudio.phases.subtitles import build_cues
from ytstudio.utils.media import detect_silences, probe_duration
from ytstudio.utils.align import video_time_fn

TMP = Path(__file__).parent / "t24"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# --- Palabras sintéticas (3 frases). Contiguas dentro de la frase (sin hueco),
# con hueco REAL entre frases. Puntuación al final de cada frase. ------------
WORDS = [
    # Frase A: 0.30-1.60  "Hola mundo real."   hueco 1.60-2.00
    {"start": 0.30, "end": 0.70, "text": "Hola"},
    {"start": 0.70, "end": 1.10, "text": "mundo"},
    {"start": 1.10, "end": 1.60, "text": "real."},
    # Frase B: 2.00-2.90  "Segunda frase clave."  hueco 2.90-3.30
    {"start": 2.00, "end": 2.35, "text": "Segunda"},
    {"start": 2.35, "end": 2.65, "text": "frase"},
    {"start": 2.65, "end": 2.90, "text": "clave."},
    # Frase C: 3.30-4.80  "Tercera parte final."  (escena 2)
    {"start": 3.30, "end": 3.70, "text": "Tercera"},
    {"start": 3.70, "end": 4.20, "text": "parte"},
    {"start": 4.20, "end": 4.80, "text": "final."},
]
AUDIO_TOTAL = 5.0
FPS = 24.0

# Renderiza voz (seno) SOLO durante las palabras; los huecos son silencio real.
expr = "+".join(f"between(t\\,{w['start']}\\,{w['end']})" for w in WORDS)
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.4*sin(2*PI*200*t)*({expr}):s=44100:d={AUDIO_TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)

segments = [{"start": 0.30, "end": 2.90, "text": "Hola mundo real. Segunda frase clave.",
             "words": WORDS[:6]},
            {"start": 3.30, "end": 4.80, "text": "Tercera parte final.",
             "words": WORDS[6:]}]
narration = {"segments": segments, "file": "narr.wav"}

# Escena 2 con audio_start = 3.50 -> ¡A MITAD de la palabra "Tercera" (3.30-3.70)!
# Esto es EXACTAMENTE el bug del seg 11: el atomizador partió por tiempo. El
# motor debe re-anclar el respiro al hueco seguro 2.90-3.30, sin cortar voz.
scenes = [
    {"id": 1, "narration": "Hola mundo real. Segunda frase clave.",
     "audio_start": 0.0, "audio_end": 3.50, "pause_after": 1.0, "pace": "amplio",
     "duration": 0, "overlay": {"text": "mundo"}},
    {"id": 2, "narration": "Tercera parte final.",
     "audio_start": 3.50, "audio_end": AUDIO_TOTAL, "pause_after": 0.0,
     "pace": "ligado", "duration": 0, "overlay": {"text": "final"}},
]
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.2}}

print("T1 _build_timeline")
out, n_breaths, n_sent, check_msg, vmap = _build_timeline(
    scenes, narration, cfg, src, TMP, AUDIO_TOTAL, FPS)
src_sils = detect_silences(src, min_d=0.08)
print(f"     silencios fuente: {[(round(a,2),round(b,2)) for a,b in src_sils]}")
print(f"     inserciones: {vmap['insertions']}  respiros escena={n_breaths} frase={n_sent}")

# INVARIANTE: cada punto de inserción cae ESTRICTAMENTE dentro de un silencio
# real -> ninguna palabra se parte. (La causa del corte del seg 11.)
def strictly_silent(p):
    return any(a + 0.02 < p < b - 0.02 for a, b in src_sils)
all_safe = all(strictly_silent(p) for p, _ in vmap["insertions"])
check("todo silencio insertado cae en un hueco real (voz jamás cortada)", all_safe,
      str(vmap["insertions"]))

# El respiro entre escenas se re-ancló al hueco 2.90-3.30 (NO en 3.50 mid-palabra)
boundary_ins = [p for p, d in vmap["insertions"] if 2.85 < p < 3.35]
check("respiro entre escenas re-anclado al hueco seguro (no a mitad de «Tercera»)",
      len(boundary_ins) == 1, str(vmap["insertions"]))
check("director HONRADO: hay pausa entre escena 1 y 2 (pause_after=1.0)", n_breaths >= 1)
check("respiro intra-escena tras la 1ª frase (pace amplio)", n_sent >= 1, f"n_sent={n_sent}")
check("escena 2 (pace ligado) sin respiros intra-escena", n_sent == 1, f"n_sent={n_sent}")
check("autocomprobación en verde", check_msg is None, str(check_msg))

# Cobertura: se preserva TODA la voz (suma de trozos = audio_total)
tl_sils = detect_silences(out, min_d=0.08)
speech_src = AUDIO_TOTAL - sum(b - a for a, b in src_sils)
speech_tl = probe_duration(out) - sum(b - a for a, b in tl_sils)
check("ni un milisegundo de voz perdido", abs(speech_tl - speech_src) < 0.2,
      f"{speech_tl:.3f} vs {speech_src:.3f}")

# Duración total = suma de escenas
sum_durs = sum(s["duration"] for s in scenes)
check("WAV == suma de duraciones de escena", abs(probe_duration(out) - sum_durs) < 0.1,
      f"{probe_duration(out):.3f} vs {sum_durs:.3f}")

print("T2 sincronía global palabra ↔ video (subtítulos y rótulos)")
V = video_time_fn(vmap["intro"], [(p, d) for p, d in vmap["insertions"]])
# La posición REAL en el audio de la palabra en tiempo-fuente t es
# intro + t + (silencios insertados antes de t). Debe ser exactamente V(t).
def real_audio_pos(t):
    return vmap["intro"] + t + sum(d for p, d in vmap["insertions"] if p <= t)
worst = max(abs(V(w["start"]) - real_audio_pos(w["start"])) for w in WORDS)
check("V(t) coincide con la posición real de la voz", worst < 1e-6, f"{worst}")

# Subtítulos: monótonos, con puntuación, dentro del video
cues = build_cues(scenes, 42, 2, narration, vmap)
mono = all(cues[i]["start"] <= cues[i + 1]["start"] + 1e-6 for i in range(len(cues) - 1))
check("cues monótonos", mono)
joined = " ".join(c["text"] for c in cues)
check("subtítulos conservan puntuación", "." in joined, joined)
check("primer subtítulo tras el intro (no en 0)", cues[0]["start"] >= vmap["intro"] - 1e-6,
      f"{cues[0]['start']}")
# Cada cue empieza cuando su palabra suena de verdad
first_word_cue = cues[0]["start"]
check("primer subtítulo = video_time de la 1ª palabra", abs(first_word_cue - V(0.30)) < 0.05,
      f"{first_word_cue} vs {V(0.30)}")

# Rótulos: overlay_at cae dentro de su escena y en el instante de la palabra
_sync_overlays(scenes, segments, vmap)
starts, acc = [], 0.0
for s in scenes:
    starts.append(acc); acc += s["duration"]
# rótulo escena 1 = "mundo" (0.70-1.10) -> video_time(0.70) - inicio escena 1
ov1 = scenes[0]["overlay_at"]
check("rótulo escena 1 sincronizado con «mundo»", ov1 is not None and abs((starts[0] + ov1) - V(0.70)) < 0.06,
      f"ov_at={ov1} start={starts[0]} V=~{V(0.70):.2f}")
ov2 = scenes[1]["overlay_at"]
check("rótulo escena 2 sincronizado con «final»", ov2 is not None and abs((starts[1] + ov2) - V(4.20)) < 0.06,
      f"ov_at={ov2} start={starts[1]} V=~{V(4.20):.2f}")

print("T3 caso sin huecos (frases pegadas): la voz fluye, nada se rompe")
# Palabras 100% contiguas, sin ningún hueco -> no hay dónde insertar.
words_glued = [{"start": round(0.3 + i * 0.4, 3), "end": round(0.3 + (i + 1) * 0.4, 3),
                "text": f"w{i}."} for i in range(8)]
expr2 = f"between(t\\,0.3\\,{words_glued[-1]['end']})"
src2 = TMP / "glued.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", f"aevalsrc=0.4*sin(2*PI*200*t)*({expr2}):s=44100:d=4.0",
                "-c:a", "pcm_s16le", str(src2)], check=True)
seg2 = [{"start": 0.3, "end": words_glued[-1]["end"], "text": "x", "words": words_glued}]
sc2 = [{"id": 1, "narration": "x", "audio_start": 0.0, "audio_end": 4.0,
        "pause_after": 0.0, "pace": "amplio", "duration": 0, "overlay": {}}]
o2, nb2, ns2, chk2, vm2 = _build_timeline(sc2, {"segments": seg2, "file": "glued.wav"},
                                          cfg, src2, TMP, 4.0, FPS)
check("sin huecos → 0 inserciones (voz intacta)", len(vm2["insertions"]) == 0, str(vm2["insertions"]))
check("autocomprobación en verde (caso pegado)", chk2 is None, str(chk2))

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
