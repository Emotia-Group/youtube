"""Batería v0.23.0: fin del recorte destructivo + B-roll por número.

T1: la limpieza NUEVA conserva TODO el contenido interno (incluida una
    sílaba suave a -40dB junto a una pausa, que la limpieza vieja se comía) y
    solo recorta los bordes.
T2: los silencios de inserción a -45dB ya no confunden voz aireada con
    silencio.
T3: B-roll con número de archivo va a SU escena (determinista); el resto pasa
    al reparto; nombres sin número no rompen nada.
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



from ytstudio.utils.media import clean_narration, detect_silences, probe_duration

TMP = Path(tempfile.mkdtemp(prefix="ytstudio_v0230_"))
FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 la limpieza conserva TODO el contenido interno")
# Grabación sintética: 1.2s de silencio inicial + frase fuerte + PAUSA de 1.5s
# + SÍLABA SUAVE (-40dB, como una 'h' aspirada) + frase fuerte + 2s de
# silencio final. La limpieza vieja (silenceremove interno a -42dB RMS con
# stop_duration=0.4) se comía parte de la pausa Y podía morder la sílaba
# suave. La nueva solo puede tocar los bordes.
strong1 = "0.4*sin(2*PI*200*t)*between(t\\,1.2\\,4.0)"
soft = "0.01*sin(2*PI*300*t)*between(t\\,5.5\\,6.1)"     # ~-40dB: voz suave
strong2 = "0.4*sin(2*PI*200*t)*between(t\\,6.1\\,9.0)"
src = TMP / "raw.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"aevalsrc=({strong1})+({soft})+({strong2}):s=44100:d=11.0",
                "-c:a", "pcm_s16le", str(src)], check=True)

out = TMP / "clean.mp3"
clean_narration(src, out, trim_silence=True)
dur = probe_duration(out)
# original: 11.0s. bordes: 1.2s inicial (deja 0.25) y 2.0s final (deja 0.25)
# => esperado ≈ 11.0 - (1.2-0.25) - (2.0-0.25) = 8.3s. El contenido interno
# (4.0→5.5 pausa + sílaba suave + voz) INTACTO.
check(f"solo se recortan los bordes (dur={dur:.2f}s, esperado ≈8.3s)",
      7.9 <= dur <= 8.7, f"{dur}")
# la pausa interna de 1.5s sigue COMPLETA (la limpieza vieja la dejaba en 0.4)
sils = detect_silences(out, noise_db=-50, min_d=0.5)
inner = [s for s in sils if 0.5 < s[0] < dur - 0.5]
check("la pausa interna de 1.5s sigue completa (no se comprimió)",
      any(1.3 <= (b - a) <= 1.7 for a, b in inner),
      str([(round(a,2), round(b,2)) for a, b in inner]))
# la sílaba suave sobrevive: hay contenido no-silencioso entre la pausa y la
# frase 2 (medido a -50dB la sílaba de -40dB es "sonido")
check("la sílaba suave (-40dB) NO fue devorada",
      not any(a < 4.85 < b for a, b in
              detect_silences(out, noise_db=-50, min_d=0.1)
              if (b - a) > 2.0),
      "la región de la sílaba aparece como silencio largo")

print("T2 inserción: la voz aireada ya no es 'silencio'")
sils45 = detect_silences(out, noise_db=-45, min_d=0.08)
soft_region_silent = any(a <= 4.83 and b >= 5.35 for a, b in sils45)
# la sílaba suave está ~-40dB > -45dB → NO debe quedar dentro de un silencio
# medido a -45 (la pausa previa sí, pero debe TERMINAR antes de la sílaba)
sil_pausa = next((s for s in sils45 if s[0] > 2.5 and s[1] - s[0] > 0.8), None)
check("el silencio de la pausa termina donde empieza la sílaba suave",
      sil_pausa is not None and sil_pausa[1] <= 4.95,
      str(sil_pausa))

print("T3 B-roll por número de archivo")
from ytstudio.phases.broll import _numbered_map

scenes = [{"id": i} for i in range(1, 8)]
assets = [
    {"name": "scene_003.mp4", "file": "01_scene_003.mp4", "kind": "video"},
    {"name": "05_castillo.jpg", "file": "02_05_castillo.jpg", "kind": "image"},
    {"name": "(2) mapa.png", "file": "03_(2) mapa.png", "kind": "image"},
    {"name": "batalla final.jpg", "file": "04_batalla final.jpg", "kind": "image"},
    {"name": "escena 7.mp4", "file": "05_escena 7.mp4", "kind": "video"},
    {"name": "scene_099.jpg", "file": "06_scene_099.jpg", "kind": "image"},
]
m = _numbered_map(scenes, assets)
got = {scenes[i]["id"]: assets[a]["name"] for i, a in m.items()}
check("scene_003 → escena 3", got.get(3) == "scene_003.mp4", str(got))
check("05_castillo → escena 5", got.get(5) == "05_castillo.jpg", str(got))
check("(2) mapa → escena 2", got.get(2) == "(2) mapa.png", str(got))
check("escena 7 → escena 7", got.get(7) == "escena 7.mp4", str(got))
check("sin número (batalla final) NO se asigna por número",
      "batalla final.jpg" not in got.values(), str(got))
check("número sin escena (099) NO se asigna", "scene_099.jpg" not in got.values(),
      str(got))

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
