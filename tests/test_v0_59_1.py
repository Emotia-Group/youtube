"""Batería v0.59.1 — el SONIDO NATIVO de los clips entra en la mezcla.

Veo 3.1 es el único modelo de video que devuelve el clip con su propio
ambiente, ya sincronizado con lo que se ve. Hasta ahora esa pista se extraía y
se guardaba junto al clip, pero NO llegaba al video final: se perdía.

Verifica:
1. La pista propia se localiza por convención (scene_007.mp4 →
   scene_007_amb.m4a) y solo en escenas que de verdad son video.
2. Cada escena entra con el retardo de SU posición en la línea de tiempo, y
   recortada a la duración de la escena (no la del clip).
3. El grafo que se genera es válido para ffmpeg DE VERDAD (se ejecuta).
4. El sonido suena en su escena y NO antes: se mide la energía del resultado
   en dos tramos.
5. Se puede apagar desde la configuración, y sin pistas no ensucia el grafo.
6. El interruptor está documentado en config.yaml.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def have_ffmpeg() -> bool:
    from shutil import which
    return bool(which("ffmpeg") and which("ffprobe"))


TMP = Path(tempfile.mkdtemp(prefix="v0591_"))
BROLL = TMP / "broll"
BROLL.mkdir(parents=True)


class ProjectStub:
    """Lo mínimo que usa el montaje: resolver rutas dentro del proyecto."""

    def path(self, *parts):
        return TMP.joinpath(*parts)


from ytstudio.phases.assembly import _native_audio_graph, native_audio_file

CFG = {"audio": {}}

# ---------------------------------------------------------------------------
print("T1 la pista propia se localiza por convención")
# escena 2: clip de video CON pista propia · escena 1 y 3: sin ella
(BROLL / "scene_002.mp4").write_bytes(b"x")
(BROLL / "scene_002_amb.m4a").write_bytes(b"x" * 100)
(BROLL / "scene_003.mp4").write_bytes(b"x")          # video, pero clip mudo

esc = [
    {"id": 1, "duration": 4.0, "broll_type": "image", "broll_image": "scene_001.jpg"},
    {"id": 2, "duration": 6.0, "broll_type": "video", "broll_video": "scene_002.mp4"},
    {"id": 3, "duration": 5.0, "broll_type": "video", "broll_video": "scene_003.mp4"},
]
p = ProjectStub()
check("T1a la escena con pista propia la encuentra",
      native_audio_file(p, esc[1]) is not None)
check("T1b una escena de IMAGEN nunca tiene pista propia (aunque hubiera archivo)",
      native_audio_file(p, esc[0]) is None)
check("T1c un clip mudo (Kling, Wan…) no inventa pista",
      native_audio_file(p, esc[2]) is None)

# ---------------------------------------------------------------------------
print("\nT2 el retardo y el recorte son los de la escena")
for s, t in zip(esc, (0.0, 4.0, 10.0)):
    s["_start"] = t
args, filters, label = _native_audio_graph(esc, p, CFG, 5)
check("T2a solo entra la escena que tiene pista", len(args) == 2, str(args))
check("T2b y su etiqueta se expone a la mezcla", label == "nat", str(label))
graf = ";".join(filters)
check("T2c se retrasa a los 4.000 s de la escena 2 (no a 0)",
      "adelay=4000|4000" in graf, graf)
check("T2d se recorta a los 6 s de LA ESCENA, no a la duración del clip",
      "atrim=0:6.000" in graf, graf)
check("T2e entra al volumen configurable, por debajo de la voz",
      "volume=-24dB" in graf, graf)
check("T2f con micro-fundidos que evitan el chasquido del corte",
      "afade=t=in" in graf and "afade=t=out" in graf, graf)

# ---------------------------------------------------------------------------
print("\nT3 se puede apagar, y sin pistas no ensucia el grafo")
off = _native_audio_graph(esc, p, {"audio": {"native_audio": False}}, 5)
check("T3a apagado desde la configuración, no aporta nada", off == ([], [], None))
solo_img = [{"id": 9, "duration": 3.0, "broll_type": "image", "_start": 0.0}]
check("T3b sin ninguna pista propia, tampoco",
      _native_audio_graph(solo_img, p, CFG, 5) == ([], [], None))

# ---------------------------------------------------------------------------
print("\nT4 el grafo es VÁLIDO para ffmpeg y suena donde debe")
if not have_ffmpeg():
    print("      (sin ffmpeg: se omite la comprobación con audio real)")
else:
    # Pista propia REAL: 6 s de tono. La escena 2 empieza en el segundo 4.
    real = BROLL / "scene_002_amb.m4a"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=6", "-c:a", "aac", str(real)],
                   capture_output=True, check=True)
    args, filters, label = _native_audio_graph(esc, p, CFG, 0)
    # Mezcla mínima: solo la pista nativa, para medirla aislada.
    graph = ";".join(filters) + f";[{label}]anull[aout]"
    out = TMP / "mezcla.wav"
    r = subprocess.run(["ffmpeg", "-y", *args, "-filter_complex", graph,
                        "-map", "[aout]", "-t", "12", str(out)],
                       capture_output=True, text=True)
    check("T4a ffmpeg acepta y ejecuta el grafo generado", r.returncode == 0,
          (r.stderr or "")[-400:])

    def energia(desde, hasta):
        """Volumen medio de un tramo, en dB (más alto = suena)."""
        rr = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", str(desde), "-t", str(hasta - desde),
             "-i", str(out), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        for linea in (rr.stderr or "").splitlines():
            if "mean_volume:" in linea:
                return float(linea.split("mean_volume:")[1].split("dB")[0])
        return -999.0

    if out.exists():
        antes = energia(0.5, 3.5)      # escena 1: debe estar en silencio
        durante = energia(5.0, 9.0)    # escena 2: aquí suena el clip
        despues = energia(10.5, 11.5)  # escena 3: ya terminó
        check("T4b NO suena antes de su escena", antes < durante - 20,
              f"antes {antes:.1f} dB · durante {durante:.1f} dB")
        check("T4c suena durante su escena", durante > -60.0, f"{durante:.1f} dB")
        check("T4d y se calla al terminarla", despues < durante - 20,
              f"después {despues:.1f} dB · durante {durante:.1f} dB")

# ---------------------------------------------------------------------------
print("\nT5 la reanudación no pierde el sonido del clip")
# Si la fase se cortó entre bajar el clip y extraerle el audio, al reanudar el
# clip ya existe y generate() no se llama: la pista se habría perdido en
# silencio. ensure_audio() la recupera sin volver a pagar el clip.
from ytstudio.providers.videogen import ReplicateVideo
v = ReplicateVideo.__new__(ReplicateVideo)
v.native_audio = True
huerfano = BROLL / "scene_004.mp4"
if have_ffmpeg():
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                    "-shortest", "-c:v", "libx264", "-c:a", "aac", str(huerfano)],
                   capture_output=True, check=True)
    rec = v.ensure_audio(huerfano)
    check("T5a un clip ya descargado sin pista la recupera al reanudar",
          rec is not None and rec.exists() and rec.stat().st_size > 0, str(rec))
    check("T5b y no la vuelve a extraer si ya estaba",
          v.ensure_audio(huerfano) == rec)
v.native_audio = False
check("T5c con un modelo mudo (Kling, Wan…) no intenta nada",
      v.ensure_audio(huerfano) is None)

print("\nT6 el interruptor está documentado")
conf = (ROOT / "config.yaml").read_text(encoding="utf-8")
check("T6a config.yaml explica native_audio",
      "native_audio:" in conf and "Veo 3.1" in conf)
check("T6b y su volumen", "native_audio_db:" in conf)

# ---------------------------------------------------------------------------
import shutil

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.59.1 completa: el sonido propio de los clips de Veo llega "
      "al video final, en su escena y a su volumen.")
