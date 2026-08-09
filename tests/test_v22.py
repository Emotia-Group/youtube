"""Batería v22: auditoría de sincronización total.

T1  detect_silences mide los silencios reales de la onda.
T2  _build_timeline corta SOLO en silencios reales aunque Whisper traiga
    fronteras sesgadas (±0.35s): jamás parte una ráfaga de voz.
T2b Frontera "falsa" de Whisper (hueco inventado a mitad de voz continua):
    NO se inserta silencio (el código viejo cortaba ahí → voz picada).
T3  Invariante de sincronía: cada palabra suena en el video exactamente en la
    posición que los subtítulos/rótulos calculan (±1.5 cuadros).
T4  Subtítulos: monotonía, sin duplicados de frontera, dentro de su escena.
T5  Caché honesta de B-roll: prompt cambiado → regenera; legado → adopta;
    asignación user↔IA cambiada → limpia.
T6  Firma de render: material regenerado con el mismo nombre → re-render.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import math
import shutil
import subprocess
import sys
from pathlib import Path



from ytstudio.utils.media import detect_silences, probe_duration
from ytstudio.phases.voiceover import _build_timeline
from ytstudio.phases.subtitles import build_cues
from ytstudio.utils.align import assign_words, flatten_words, local_time

TMP = Path(__file__).parent / "t22"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# ---------- audio sintético: ráfagas de "voz" (seno 220Hz) con huecos ----
# habla: 0.2-3.0 | SIL 3.0-3.4 | habla 3.4-7.0 | SIL 7.0-7.8 |
# habla 7.8-18.0 (continua a través de 14.0) | SIL 18.0-20.0
BURSTS = [(0.2, 3.0), (3.4, 7.0), (7.8, 18.0)]
TOTAL = 20.0
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in BURSTS)
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.4*sin(2*PI*220*t)*({expr}):s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)

print("T1 detect_silences")
sils = detect_silences(src)
def in_sils(t):
    return any(s0 - 0.08 <= t <= s1 + 0.08 for s0, s1 in sils)
check("detecta el hueco 3.0-3.4", any(abs(s0 - 3.0) < 0.1 and abs(s1 - 3.4) < 0.1 for s0, s1 in sils), str(sils))
check("detecta el hueco 7.0-7.8", any(abs(s0 - 7.0) < 0.1 and abs(s1 - 7.8) < 0.1 for s0, s1 in sils), str(sils))
check("NO inventa silencio en 14.0", not in_sils(14.0), str(sils))

# ---------- transcripción Whisper SESGADA (peor caso real) ----------------
# seg2 arranca 0.35s TARDE (la voz real vuelve en 3.4, Whisper dice 3.75):
# el código v19-v21 cortaba en 3.75 → a mitad de palabra. seg4 inventa un
# hueco 13.8→14.0 dentro de voz continua: el código viejo insertaba respiro.
def mkwords(a, b, n):
    st = (b - a) / n
    return [{"start": round(a + i * st, 3), "end": round(a + (i + 1) * st - 0.02, 3),
             "text": f"w{round((a + i * st) * 100)}"} for i in range(n)]

segments = [
    {"start": 0.25, "end": 2.9, "text": "s1", "words": mkwords(0.25, 2.9, 6)},
    {"start": 3.75, "end": 6.9, "text": "s2", "words": mkwords(3.75, 6.9, 7)},
    {"start": 7.85, "end": 13.8, "text": "s3", "words": mkwords(7.85, 13.8, 12)},
    {"start": 14.0, "end": 17.9, "text": "s4", "words": mkwords(14.0, 17.9, 8)},
]
narration = {"segments": segments, "file": "narr.wav"}
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 3.75, "pause_after": 0.5},
    {"id": 2, "narration": "b", "audio_start": 3.75, "audio_end": 7.85, "pause_after": 0.0},
    {"id": 3, "narration": "c", "audio_start": 7.85, "audio_end": 14.0, "pause_after": 0.8},
    {"id": 4, "narration": "d", "audio_start": 14.0, "audio_end": TOTAL, "pause_after": 0.0},
]
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 3.5}}
FPS = 24.0

print("T2 _build_timeline: cortes solo en silencio real")
out, n_breaths, _n_sent, selfcheck, vmap = _build_timeline(
    scenes, narration, cfg, src, TMP, TOTAL, FPS)
b1, b2, b3 = (scenes[1]["audio_start"], scenes[2]["audio_start"], scenes[3]["audio_start"])
check("frontera 2 re-anclada DENTRO del silencio real (3.0-3.4)", 3.0 < b1 < 3.4, f"b1={b1}")
check("frontera 3 re-anclada DENTRO del silencio real (7.0-7.8)", 7.0 < b2 < 7.8, f"b2={b2}")
check("frontera 4 dentro del hueco inventado, sin tocar voz "
      "(v0.24.5: guarda de ataque)", 13.79 <= b3 <= 14.01, f"b3={b3}")
d3 = scenes[2]["duration"]
span3 = scenes[2]["vo_duration"]
check("T2b: SIN respiro en la frontera falsa (voz continua)",
      abs(d3 - round(span3 * FPS) / FPS) < 1.0 / FPS + 1e-6, f"dur={d3} span={span3}")
check("autocomprobación en verde", selfcheck is None, str(selfcheck))
tl_dur = probe_duration(out)
sum_durs = sum(s["duration"] for s in scenes)
check("WAV == suma de escenas", abs(tl_dur - sum_durs) < 0.06, f"{tl_dur} vs {sum_durs}")
tl_sils = detect_silences(out)
speech_src = TOTAL - sum(e - s for s, e in sils)
speech_tl = tl_dur - sum(e - s for s, e in tl_sils)
check("ni un segundo de voz perdido", abs(speech_tl - speech_src) < 0.35,
      f"{speech_tl} vs {speech_src}")

print("T3 invariante palabra↔video (subtítulos y rótulos)")
# posición de cada palabra en el AUDIO montado = intro + silencios insertados
# antes de ella + su tiempo fuente. Debe coincidir con la posición que los
# subtítulos calculan: inicio de su escena + local_time.
intro = cfg["audio"]["intro_seconds"]
bounds = [s["audio_start"] for s in scenes] + [scenes[-1]["audio_end"]]
# silencios insertados: duration - vo_duration (- intro en la 1a escena)
ins = [s["duration"] - s["vo_duration"] - (intro if i == 0 else 0.0)
       for i, s in enumerate(scenes)]
words = flatten_words(segments)
wmap = assign_words(scenes, words)
starts_v = []
acc = 0.0
for s in scenes:
    starts_v.append(acc)
    acc += s["duration"]
worst = 0.0
for i, s in enumerate(scenes):
    for w in wmap[s["id"]]:
        audio_pos = intro + w["start"] + sum(ins[j] for j in range(len(scenes))
                                             if bounds[j + 1] <= w["start"] + 1e-6 and ins[j] > 0.001)
        video_pos = starts_v[i] + local_time(s, w["start"])
        worst = max(worst, abs(audio_pos - video_pos))
check("cada palabra suena donde el subtítulo la pinta (±1.5 cuadros)",
      worst <= 1.5 / FPS, f"desvío máx {worst:.4f}s")

print("T4 subtítulos")
cues = build_cues(scenes, 42, 2, narration, voice_map=vmap)
ok_mono = all(cues[i]["start"] <= cues[i + 1]["start"] + 1e-6 for i in range(len(cues) - 1))
check("cues monótonos", ok_mono)
check("cues dentro del video", cues[0]["start"] >= intro - 1e-6 and cues[-1]["end"] <= sum_durs + 1e-6,
      f"{cues[0]['start']}..{cues[-1]['end']} vs {sum_durs}")
alltext = " ".join(c["text"].replace("\n", " ") for c in cues).split()
check("sin palabras duplicadas en fronteras", len(alltext) == len(set(alltext)) == len(words),
      f"{len(alltext)} vs {len(words)}")

# ---------- T5/T6: caché honesta de B-roll + firma de render --------------
print("T5 caché honesta de B-roll")
import json
import ytstudio.project as prj
prj.PROJECTS_DIR = TMP / "projects"
from ytstudio.project import Project
from ytstudio.phases import broll
from ytstudio.phases.scenes import save_scenes as _save
from ytstudio.phases import assembly

p = Project("t22")
bcfg = {"language": "es",
        "video": {"width": 640, "height": 360, "fps": 24},
        "providers": {"llm": {"name": "mock"}, "images": {"name": "mock"},
                      "videogen": {"name": "none"}},
        "performance": {"parallel_images": 2, "parallel_video": 1}}
bscenes = [{"id": 1, "section": "intro", "narration": "n1", "broll_prompt": "castillo medieval",
            "broll_type": "image", "animation": "static", "duration": 5},
           {"id": 2, "section": "nudo", "narration": "n2", "broll_prompt": "batalla antigua",
            "broll_type": "image", "animation": "static", "duration": 5}]
_save(p, bscenes)
broll.run(p, bcfg)
bdir = p.path("broll")
img2 = bdir / "scene_002.jpg"
sig_file = bdir / "prompts.json"
check("genera imágenes y firma", img2.exists() and sig_file.exists())
m0 = img2.stat().st_mtime_ns

# 5a: mismo prompt → caché intacta
broll.run(p, bcfg)
check("prompt igual → NO regenera", img2.stat().st_mtime_ns == m0)

# 5b: prompt cambiado → regenera esa escena (solo esa)
sc = json.loads(p.path("scenes", "scenes.json").read_text(encoding="utf-8"))["scenes"]
sc[1]["broll_prompt"] = "puerto fenicio al amanecer"
_save(p, sc)
img1 = bdir / "scene_001.jpg"
m1 = img1.stat().st_mtime_ns
broll.run(p, bcfg)
check("prompt cambiado → regenera escena 2", img2.stat().st_mtime_ns != m0)
check("escena 1 intacta", img1.stat().st_mtime_ns == m1)

# 5c: proyecto legado sin firma → adopta sin regenerar
sig_file.unlink()
m2 = img2.stat().st_mtime_ns
broll.run(p, bcfg)
check("legado sin firma → adopta sin regenerar", img2.stat().st_mtime_ns == m2 and sig_file.exists())

# 5d: la asignación cambió de user→IA (firma distinta) → limpia y regenera
sigs = json.loads(sig_file.read_text(encoding="utf-8"))
sigs["2"] = "user:viejo.jpg"
sig_file.write_text(json.dumps(sigs), encoding="utf-8")
broll.run(p, bcfg)
check("cambio user↔IA → regenera", img2.stat().st_mtime_ns != m2)

print("T6 firma de render sensible al contenido")
plans = [{"fin": "none", "fin_d": 0, "fout": "none", "fout_d": 0}] * 2
sc = json.loads(p.path("scenes", "scenes.json").read_text(encoding="utf-8"))["scenes"]
for s, name in zip(sc, ("scene_001.jpg", "scene_002.jpg")):
    s["broll_image"] = name
sig_a = assembly._render_signature(sc, plans, bcfg, p)
img2.write_bytes(img2.read_bytes() + b"\0")  # mismo nombre, contenido nuevo
sig_b = assembly._render_signature(sc, plans, bcfg, p)
check("regenerar con el MISMO nombre cambia la firma", sig_a != sig_b)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
