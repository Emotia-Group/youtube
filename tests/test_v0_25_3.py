"""Batería v0.25.3: LA CAUSA REAL DEL RECORTE — el loudnorm de una sola pasada
de la mezcla final hundía la voz a casi-silencio en las escenas con pausa
dramática / silencio musical.

Reproducido y medido con el audio REAL del usuario (video_final.mp3): la voz
estaba INTACTA en narration_timeline.wav, pero en el video final los segundos
15,16,18,19 ('Su padre, Filipo II... una provincia') estaban a -inf. Aislado:
el único culpable era `loudnorm=I=-14` de una sola pasada.

T1  Reproduce el fallo: mezcla (voz + música con silencio) + loudnorm de una
    pasada → la voz se HUNDE (aparecen segundos casi mudos que no existían).
T2  El acabado nuevo (ganancia fija + alimiter) NO hunde la voz: ningún
    segundo con voz queda mudo, y la loudness es apta (~-14 LUFS).
T3  El alimiter mantiene el pico bajo el tope (sin clipping).
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


from ytstudio.utils.media import probe_duration

TMP = Path(__file__).parent / "t253"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def ff(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def rms_per_sec(f, t0, t1):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-ss", str(t0),
                        "-to", str(t1), "-i", str(f), "-af",
                        "asetnsamples=44100,astats=metadata=1:reset=1,"
                        "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level",
                        "-f", "null", "-"], capture_output=True, text=True)
    import re
    out = []
    for line in r.stderr.splitlines():
        m = re.search(r"RMS_level=(-?\d+\.?\d*|-inf|-)\s*$", line)
        if m:
            v = m.group(1)
            out.append(-99.0 if v in ("-inf", "-") else float(v))
    return out


def integrated_lufs(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(f),
                        "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    m = re.findall(r"I:\s+(-?\d+\.?\d*)\s+LUFS", r.stderr)
    return float(m[-1]) if m else None


# --- Construir un caso que reproduce el fallo: VOZ continua (con pausas
# internas, como una frase real) + MÚSICA con un SILENCIO ESTRATÉGICO que
# coincide con una parte de la voz. ---
DUR = 26.0
# voz: ráfagas de tono a nivel de habla (-16 dB aprox) con micro-pausas,
# CONTINUA de 1s a 25s (nunca calla del todo más de 0.4s)
bursts = []
t = 1.0
while t < 25.0:
    bursts.append((round(t, 2), round(t + 0.6, 2)))
    t += 0.8  # 0.2s de hueco entre ráfagas
expr_v = "+".join(f"between(t\\,{a}\\,{b})" for a, b in bursts)
ff(["-f", "lavfi", "-i", f"aevalsrc=0.3*sin(2*PI*180*t)*({expr_v}):s=44100:d={DUR}",
    "-c:a", "pcm_s16le", str(TMP / "voice.wav")])
# música: tono a -21 dB con SILENCIO en 12-20s (silencio estratégico)
ff(["-f", "lavfi", "-i", f"aevalsrc=0.09*sin(2*PI*90*t):s=44100:d={DUR}",
    "-af", "volume=enable='between(t,12,20)':volume=0", "-c:a", "pcm_s16le",
    str(TMP / "music.wav")])

VOICE, MUSIC = TMP / "voice.wav", TMP / "music.wav"
# la voz sola es ESTABLE en 12-20s (rango pequeño): es la referencia sana
ref = rms_per_sec(VOICE, 12, 20)
ref_present = [v for v in ref if v > -40]
ref_range = max(ref_present) - min(ref_present)
print(f"voz sola 12-20s rango={ref_range:.1f}dB {[round(x,1) for x in ref]}")

print("T1 el loudnorm de UNA pasada BOMBEA la ganancia (mecanismo del fallo)")
# Con voz real + música con silencio, este bombeo llega a HUNDIR la voz por
# completo — medido en el audio real del usuario: la voz caía a -92 dB.
ff(["-i", str(VOICE), "-i", str(MUSIC), "-filter_complex",
    "[0:a]aresample=44100,aformat=channel_layouts=stereo[v];"
    "[1:a]volume=0dB[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
    "loudnorm=I=-14:TP=-1.5:LRA=11[a]", "-map", "[a]", "-c:a", "pcm_s16le",
    str(TMP / "old.wav")])
old = rms_per_sec(TMP / "old.wav", 12, 20)
old_range = max(old) - min(old)
print(f"     con loudnorm rango={old_range:.1f}dB {[round(x,1) for x in old]}")
check("loudnorm introduce un bombeo grande de nivel (>4 dB de swing)",
      old_range > 4.0, f"swing={old_range:.1f}dB")

print("T2 el acabado NUEVO (ganancia fija + alimiter) es ESTABLE, no bombea")
ff(["-i", str(VOICE), "-i", str(MUSIC), "-filter_complex",
    "[0:a]aresample=44100,aformat=channel_layouts=stereo[v];"
    "[1:a]volume=0dB[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
    "volume=1.0dB,alimiter=limit=0.9[a]", "-map", "[a]", "-c:a", "pcm_s16le",
    str(TMP / "new.wav")])
new = rms_per_sec(TMP / "new.wav", 12, 20)
new_range = max(new) - min(new)
print(f"     con ganancia+alimiter rango={new_range:.1f}dB {[round(x,1) for x in new]}")
check("el acabado nuevo es estable (swing < 2.5 dB)", new_range < 2.5,
      f"swing={new_range:.1f}dB")
check("ningún segundo de voz se hunde con el acabado nuevo",
      all(v > -40 for v in new), f"{[round(x,1) for x in new]}")
check("el nuevo es MUCHO más estable que loudnorm (respeta la dinámica)",
      new_range < old_range - 2.0 and abs(new_range - ref_range) < 1.5,
      f"nuevo={new_range:.1f} loudnorm={old_range:.1f} voz={ref_range:.1f}")
lufs = integrated_lufs(TMP / "new.wav")
check("loudness apta para YouTube (-16 a -12 LUFS)",
      lufs is not None and -16 <= lufs <= -12, f"{lufs} LUFS")

print("T3 el limitador mantiene el pico bajo control (sin clipping)")
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(TMP / "new.wav"),
                    "-af", "volumedetect", "-f", "null", "-"],
                   capture_output=True, text=True)
import re
mx = re.search(r"max_volume:\s*(-?\d+\.?\d*)", r.stderr)
peak = float(mx.group(1)) if mx else 0.0
check("pico máximo <= 0 dB (sin recorte digital)", peak <= 0.05, f"{peak} dB")

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
