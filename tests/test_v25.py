"""Batería v25: la regresión de v24 reproducida y corregida.

Escenario real: los tiempos de Whisper DERIVAN +0.25s respecto a la onda, y
la frontera de escena cae A MITAD DE FRASE (microhueco de 60ms entre
palabras, sin silencio real). v24 metía ahí la pausa de frontera → corte
audible a mitad de frase (el bug de la transición escena 1→2). v25 exige
silencio MEDIDO: sin él, no hay pausa y la voz fluye.

También: -frames:v exacto en el render (el -t redondeado metía un cuadro de
más por escena de video → desfase progresivo), y flatten_words ya no descarta
palabras legítimas con timestamps solapados.
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



from ytstudio.phases.voiceover import _build_timeline, _safe_cuts
from ytstudio.utils.media import detect_silences, probe_duration
from ytstudio.utils.align import flatten_words

TMP = Path(__file__).parent / "t25"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# ---- Onda REAL: dos frases largas; entre ellas un silencio real 4.0-4.6.
# Dentro de la primera frase, las palabras encadenan casi sin aire.
REAL_BURSTS = [(0.30, 4.00), (4.60, 9.50)]
AUDIO_TOTAL = 10.0
FPS = 24.0
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in REAL_BURSTS)
src = TMP / "narr.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=0.4*sin(2*PI*200*t)*({expr}):s=44100:d={AUDIO_TOTAL}",
                "-c:a", "pcm_s16le", str(src)], check=True)

# ---- Whisper con DERIVA +0.25s y microhuecos inventados entre palabras.
# La palabra w5 termina (según Whisper) en 2.20 y w6 empieza en 2.26: hueco de
# 60ms A MITAD DE FRASE — en la onda real ahí hay VOZ continua. La frontera de
# la escena 2 cae justo ahí (2.23). El silencio real está en 4.0-4.6 (Whisper
# lo ve en 4.25-4.85).
D = 0.25  # deriva
words = [
    {"start": 0.30 + D, "end": 0.80 + D, "text": "Primera"},
    {"start": 0.80 + D, "end": 1.30 + D, "text": "parte"},
    {"start": 1.30 + D, "end": 1.75 + D, "text": "de"},
    {"start": 1.75 + D, "end": 2.20 - D, "text": "la"},        # fin 1.95
    {"start": 2.26 - D, "end": 2.70 + D, "text": "historia"},  # microhueco 2.01→1.95...
    {"start": 2.70 + D, "end": 3.30 + D, "text": "que"},
    {"start": 3.30 + D, "end": 4.00 + D, "text": "contamos."},
    {"start": 4.60 + D, "end": 5.30 + D, "text": "Segunda"},
    {"start": 5.30 + D, "end": 6.20 + D, "text": "frase"},
    {"start": 6.20 + D, "end": 9.50 + D, "text": "completa."},
]
# hueco Whisper mid-frase: entre words[3] (end 1.95) y words[4] (start 2.01)
segments = [{"start": words[0]["start"], "end": words[6]["end"],
             "text": "Primera parte de la historia que contamos.",
             "words": words[:7]},
            {"start": words[7]["start"], "end": words[9]["end"],
             "text": "Segunda frase completa.", "words": words[7:]}]
narration = {"segments": segments, "file": "narr.wav"}

print("T1 _safe_cuts: sin silencio medido NO hay corte utilizable")
sils = detect_silences(src, min_d=0.08)
cuts = _safe_cuts(words, sils)
midphrase = [c for c in cuts if 1.5 < c["mid"] < 2.5]
check("el microhueco a mitad de frase queda con wide=0 (solo coordenada)",
      all(c["wide"] == 0.0 for c in midphrase), str(midphrase))
realgap = [c for c in cuts if c["wide"] >= 0.15]
check("el silencio real 4.0-4.6 SÍ da un corte respaldado",
      any(4.0 < c["mid"] < 4.6 for c in realgap), str(realgap))

print("T2 frontera a MITAD de frase → sin pausa, voz fluye (bug v24)")
scenes = [
    {"id": 1, "narration": "a", "audio_start": 0.0, "audio_end": 2.23,
     "pause_after": 1.2, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 2, "narration": "b", "audio_start": 2.23, "audio_end": 6.0,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
    {"id": 3, "narration": "c", "audio_start": 6.0, "audio_end": AUDIO_TOTAL,
     "pause_after": 0.0, "pace": "normal", "duration": 0, "overlay": None},
]
cfg = {"audio": {"scene_breath": 0.3, "intro_seconds": 0.8, "outro_seconds": 2.0,
                 "sentence_breath": 0.18}}
out, n_breaths, n_sent, chk, vmap = _build_timeline(
    scenes, narration, cfg, src, TMP, AUDIO_TOTAL, FPS)
print(f"     inserciones: {vmap['insertions']}")
in_real_silence = all(any(a + 0.02 < p < b - 0.02 for a, b in sils)
                      for p, _ in vmap["insertions"])
check("TODA inserción cae en silencio real de la ONDA (pese a la deriva Whisper)",
      in_real_silence, str(vmap["insertions"]))
check("ninguna inserción en el microhueco 1.9-2.3 (mitad de frase)",
      not any(1.9 < p < 2.3 for p, _ in vmap["insertions"]), str(vmap["insertions"]))
# La frontera escena2→3 (6.0) tampoco tiene silencio real cerca → sin pausa.
# Solo la frontera 1→2 re-anclada... no: 2.23 sin silencio → sin pausa. El
# silencio real 4.0-4.6 queda DENTRO de la escena 2 → respiro de frase ahí
# (fin de "contamos." con deriva) si el corte respaldado coincide.
check("autocomprobación en verde", chk is None, str(chk))

# Nada de voz perdida
tl_sils = detect_silences(out, min_d=0.08)
speech_src = AUDIO_TOTAL - sum(b - a for a, b in sils)
speech_tl = probe_duration(out) - sum(b - a for a, b in tl_sils)
check("ni un milisegundo de voz perdido", abs(speech_tl - speech_src) < 0.2,
      f"{speech_tl:.3f} vs {speech_src:.3f}")
sum_durs = sum(s["duration"] for s in scenes)
check("WAV == suma de escenas", abs(probe_duration(out) - sum_durs) < 0.1,
      f"{probe_duration(out):.3f} vs {sum_durs:.3f}")

print("T3 render con cuadros EXACTOS (fix del desfase progresivo)")
# Escena con clip de video y duración 250/24 = 10.41666s (caso que metía
# un cuadro de más con -t 10.417). El mp4 debe tener EXACTAMENTE 250 cuadros.
from ytstudio.phases import assembly
clip = TMP / "clip.mp4"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=12",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], check=True)
vo = TMP / "vo.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "10.5",
                str(vo)], check=True)


class _P:
    def path(self, key, *parts):
        d = TMP / key
        d.mkdir(exist_ok=True)
        return d.joinpath(*parts) if parts else d


p = _P()
shutil.copy(clip, TMP / "broll" / "clip.mp4") if (TMP / "broll").exists() or (TMP / "broll").mkdir() or True else None
shutil.copy(vo, TMP / "voiceover" / "vo.wav") if (TMP / "voiceover").exists() or (TMP / "voiceover").mkdir() or True else None
scene = {"id": 1, "duration": round(250 / 24, 3), "vo_file": "vo.wav",
         "broll_video": "clip.mp4", "animation": "static", "overlay": None,
         "on_screen_text": ""}
rcfg = {"video": {"width": 320, "height": 180, "fps": 24, "overlays": False,
                  "overlay_accent": "E8C46B"}}
outmp4 = TMP / "scene_out.mp4"
assembly._render_scene(scene, p, rcfg, outmp4,
                       {"fin": None, "fin_d": 0, "fout": None, "fout_d": 0})
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                        "-count_frames", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", str(outmp4)],
                       capture_output=True, text=True)
frames = int(probe.stdout.strip())
check("escena de video con EXACTAMENTE los cuadros del mapa (250)",
      frames == 250, f"frames={frames}")

print("T4 flatten_words: solapes legítimos NO se pierden; duplicados sí")
legit = [{"words": [{"start": 1.00, "end": 1.42, "text": "hola"},
                    {"start": 1.38, "end": 1.80, "text": "mundo"}]}]  # solape 40ms real
flat = flatten_words(legit)
check("palabras con solape legítimo se conservan", len(flat) == 2,
      str([w["text"] for w in flat]))
dup = [{"words": [{"start": 1.0, "end": 1.4, "text": "hola"}]},
       {"words": [{"start": 1.0, "end": 1.4, "text": "hola"},
                  {"start": 1.4, "end": 1.8, "text": "mundo"}]}]
flat2 = flatten_words(dup)
check("duplicado exacto (mismo texto+instante) se descarta",
      [w["text"] for w in flat2] == ["hola", "mundo"], str([w["text"] for w in flat2]))

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
