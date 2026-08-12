"""Batería v0.53.0 — los tres huecos declarados + el idioma del texto en pantalla.

En la v0.52.0 dije con claridad qué NO quedaba cubierto. Esto lo cierra:

1. El control con visión miraba la IMAGEN FIJA de cada escena, no el
   movimiento de los clips de video IA (un animal que la narración da por
   muerto puede acabar moviéndose al animarse).
2. Corregía UNA sola vez.
3. La auditoría gratuita comprobaba cantidad y estado sin vida, pero no la
   UBICACIÓN exacta («una herida en el cuello» dibujada en el costado).

Y añade lo que pidió el creador: cuando la escena muestra un texto real de
otra lengua (un papiro en arameo dentro de un documental en español), ese
texto debe verse EN SU LENGUA, no en la de la narración.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
import json
import shutil
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0530_"))

from PIL import Image

from ytstudio import prompt_safety as ps
from ytstudio.phases import broll as broll_phase
from ytstudio.phases import scenes as scenes_phase


class PStub:
    def __init__(self, name="proj"):
        self.data, self.avisos = {}, []
        self.dir = TMP / name

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.avisos.append(m)

    def path(self, kind, name=""):
        d = self.dir / kind
        d.mkdir(parents=True, exist_ok=True)
        return d / name if name else d


CFG = {"language": "es",
       "video": {"width": 640, "height": 360, "fps": 12, "elements": False},
       "providers": {"images": {"fact_check": True, "fact_check_retries": 2}},
       "audio": {}}

# ---------------------------------------------------------------------------
# HUECO 3 — la auditoría gratuita ya comprueba la UBICACIÓN
# ---------------------------------------------------------------------------
faltan = ps.auditar_fidelidad(
    "La herida estaba en el cuello del animal.",
    "a goat with a clinical mark on its side")
check("T1 caza la ubicación equivocada (cuello narrado, costado dibujado)",
      any("cuello" in f for f in faltan), str(faltan))
check("T1b un prompt con la ubicación correcta no se queja",
      ps.auditar_fidelidad("La herida estaba en el cuello del animal.",
                           "a goat with a puncture mark on the neck") == [],
      "")
check("T1c acepta el sinónimo en inglés (garganta → throat)",
      ps.auditar_fidelidad("una herida en la garganta",
                           "a wound on the throat") == [], "")
check("T1d NO exige ubicación si no se narra ninguna marca "
      "(«la cabeza del imperio» no es anatomía)",
      ps.auditar_fidelidad("Tombuctú era la cabeza del imperio",
                           "a golden city at dawn") == [], "")
check("T1e y sigue cazando cantidad y estado (no rompimos lo anterior)",
      len(ps.auditar_fidelidad("Tres cabras muertas con heridas en el cuello",
                               "a goat in a field")) == 3,
      str(ps.auditar_fidelidad("Tres cabras muertas con heridas en el cuello",
                               "a goat in a field")))

# ---------------------------------------------------------------------------
# HUECO 1 — el control con visión mira DENTRO del clip de video
# ---------------------------------------------------------------------------
proj = PStub()
broll_dir = proj.path("broll")
Image.new("RGB", (320, 180), (40, 60, 40)).save(broll_dir / "scene_001.jpg")
Image.new("RGB", (320, 180), (40, 60, 40)).save(broll_dir / "scene_002.jpg")
clip = broll_dir / "scene_002.mp4"
subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=size=320x180:rate=12:duration=3",
                "-pix_fmt", "yuv420p", str(clip)],
               check=True, capture_output=True)

sin_clip = broll_phase._qa_frame({"id": 1}, broll_dir)
check("T2 una escena de imagen se revisa por su propia imagen",
      sin_clip is not None and sin_clip.name == "scene_001.jpg", str(sin_clip))

con_clip = broll_phase._qa_frame({"id": 2, "broll_video": "scene_002.mp4"},
                                 broll_dir)
check("T2b una escena de CLIP se revisa por un fotograma de su INTERIOR",
      con_clip is not None and con_clip.name == "scene_002_mid.jpg"
      and con_clip.exists(), str(con_clip))
check("T2c el fotograma no es la imagen inicial (se extrajo del movimiento)",
      list(Image.open(con_clip).convert("RGB").getdata())
      != list(Image.open(broll_dir / "scene_002.jpg").convert("RGB").getdata()),
      "")
mtime = con_clip.stat().st_mtime_ns
broll_phase._qa_frame({"id": 2, "broll_video": "scene_002.mp4"}, broll_dir)
check("T2d al reanudar se reutiliza (no se re-extrae)",
      con_clip.stat().st_mtime_ns == mtime, "")
check("T2e si el clip no existe, cae a la imagen fija sin romperse",
      (broll_phase._qa_frame({"id": 1, "broll_video": "no_existe.mp4"},
                             broll_dir) or Path("x")).name == "scene_001.jpg",
      "")

src_qa = inspect.getsource(broll_phase._qa_batches)
check("T2f al revisor se le avisa de qué imágenes son fotogramas de un clip",
      "FOTOGRAMA INTERIOR" in src_qa, "")
check("T2g y se le pide comprobar que el MOVIMIENTO no contradiga lo narrado",
      "MOVIMIENTO no contradiga" in src_qa, "")

# ---------------------------------------------------------------------------
# HUECO 2 — varias rondas de corrección, y el clip infiel NO se re-paga
# ---------------------------------------------------------------------------
class VisionLLM:
    """Declara infieles las escenas indicadas, ronda por ronda."""

    is_mock = False

    def __init__(self, infieles_por_ronda):
        self.rondas = list(infieles_por_ronda)
        self.llamadas = 0

    def complete_json(self, system, prompt, *, schema, images=None,
                      max_tokens=64000, purpose=""):
        import re
        ids = [int(m) for m in re.findall(r"escena (\d+)", prompt)]
        infieles = self.rondas[min(self.llamadas, len(self.rondas) - 1)]
        self.llamadas += 1
        return {"reviews": [
            {"scene": i, "fiel": i not in infieles,
             "problema": "el animal aparece vivo" if i in infieles else "",
             "prompt_corregido": f"dead goat, corrected v{self.llamadas}"
             if i in infieles else ""} for i in ids]}


generadas: list[tuple[int, str]] = []


def gen_one(scene, prompt, img):
    generadas.append((scene["id"], prompt))
    Image.new("RGB", (320, 180), (90, 20, 20)).save(img)


# escena 1 = imagen (falla 2 rondas, se arregla a la 3ª mirada)
p1 = PStub("p1")
d1 = p1.path("broll")
Image.new("RGB", (320, 180), (10, 10, 10)).save(d1 / "scene_001.jpg")
esc1 = [{"id": 1, "narration": "La cabra estaba muerta.",
         "broll_prompt": "a goat"}]
llm1 = VisionLLM([{1}, {1}, set()])
generadas.clear()
broll_phase._verify_factual(p1, llm1, CFG, esc1, d1, gen_one, skip=set())
check("T3 con 2 rondas, una imagen tozuda se regenera DOS veces",
      len(generadas) == 2, str(generadas))
check("T3b y el prompt corregido de cada ronda es el que se usa",
      generadas[0][1].endswith("v1") and generadas[1][1].endswith("v2"),
      str([g[1][-3:] for g in generadas]))
check("T3c el aviso indica en qué ronda se corrigió",
      any("ronda 1" in a for a in p1.avisos)
      and any("ronda 2" in a for a in p1.avisos), str(p1.avisos[:2]))

# con 1 ronda (comportamiento anterior) solo se corrige una vez
p1b = PStub("p1b")
d1b = p1b.path("broll")
Image.new("RGB", (320, 180), (10, 10, 10)).save(d1b / "scene_001.jpg")
esc1b = [{"id": 1, "narration": "La cabra estaba muerta.",
          "broll_prompt": "a goat"}]
generadas.clear()
cfg1 = {**CFG, "providers": {"images": {"fact_check": True,
                                        "fact_check_retries": 1}}}
broll_phase._verify_factual(p1b, VisionLLM([{1}, {1}, {1}]), cfg1, esc1b, d1b,
                            gen_one, skip=set())
check("T3d con fact_check_retries=1 se corrige UNA vez (como antes)",
      len(generadas) == 1, str(generadas))
check("T3e y avisa de que puede seguir sin respetar lo narrado",
      any("pueden seguir" in a for a in p1b.avisos), str(p1b.avisos[-1:]))

# escena de CLIP infiel: baja a imagen fija y NO se paga nada
p2 = PStub("p2")
d2 = p2.path("broll")
Image.new("RGB", (320, 180), (10, 10, 10)).save(d2 / "scene_007.jpg")
subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=size=320x180:rate=12:duration=2",
                "-pix_fmt", "yuv420p", str(d2 / "scene_007.mp4")],
               check=True, capture_output=True)
esc2 = [{"id": 7, "narration": "El animal estaba muerto.",
         "broll_prompt": "a dead goat", "broll_video": "scene_007.mp4",
         "broll_type": "video"}]
generadas.clear()
broll_phase._verify_factual(p2, VisionLLM([{7}, set()]), CFG, esc2, d2,
                            gen_one, skip=set())
check("T4 un CLIP infiel NO se re-genera (cuesta 10 veces más que una imagen)",
      generadas == [], str(generadas))
check("T4b la escena baja a su imagen fija, ya verificada",
      "broll_video" not in esc2[0], str(esc2[0].get("broll_video")))
check("T4c y se explica sin cobrar de más",
      any("no se paga otro clip" in a for a in p2.avisos), str(p2.avisos))
check("T4d el fotograma de QA del clip caído se limpia",
      not (d2 / "qa" / "scene_007_mid.jpg").exists(), "")

# todo fiel a la primera: ni una regeneración
p3 = PStub("p3")
d3 = p3.path("broll")
Image.new("RGB", (320, 180), (10, 10, 10)).save(d3 / "scene_001.jpg")
generadas.clear()
broll_phase._verify_factual(p3, VisionLLM([set()]), CFG,
                            [{"id": 1, "narration": "x", "broll_prompt": "y"}],
                            d3, gen_one, skip=set())
check("T4e si todo respeta lo narrado, no se gasta nada",
      generadas == [] and not p3.avisos, str(p3.avisos))

# ---------------------------------------------------------------------------
# IDIOMA DEL TEXTO EN PANTALLA — lo manda la ESCENA, no la narración
# ---------------------------------------------------------------------------
src_sc = inspect.getsource(scenes_phase)
check("T5 el director dispone del campo image_text_lang",
      '"image_text_lang"' in src_sc, "")
check("T5b las reglas explican el caso del papiro en arameo",
      "arameo" in src_sc and "EL IDIOMA LO MANDA LA ESCENA" in src_sc, "")
check("T5c y le piden no inventar grafías que no conoce",
      "escritura ilegible que inventar" in src_sc, "")

escenas = [{"id": 1, "image_text": "PAPIRO", "image_text_lang": "Aramaic script",
            "overlay_type": "ninguno", "music_intensity": 0.5, "narration": "x"},
           {"id": 2, "image_text": "ÚLTIMA HORA", "image_text_lang": "",
            "overlay_type": "ninguno", "music_intensity": 0.5, "narration": "x"},
           {"id": 3, "image_text": "", "image_text_lang": "Latin",
            "overlay_type": "ninguno", "music_intensity": 0.5, "narration": "x"}]
scenes_phase._normalize_creative(escenas)
check("T5d el idioma propio se conserva",
      escenas[0].get("image_text_lang") == "Aramaic script", "")
check("T5e vacío = idioma del video (no se guarda basura)",
      "image_text_lang" not in escenas[1], "")
check("T5f sin texto no se guarda idioma huérfano",
      "image_text_lang" not in escenas[2], "")

src_br = inspect.getsource(broll_phase.run)
check("T6 el generador usa el idioma de la ESCENA cuando lo hay",
      'scene.get("image_text_lang")' in src_br, "")
check("T6b si es otra lengua, exige su grafía y prohíbe traducir",
      "NOT translated and NOT transliterated" in src_br
      and "historically accurate lettering" in src_br, "")
check("T6c y si no la hay, sigue mandando el idioma del video",
      'or lang' in src_br and 'written in {idioma}' in src_br, "")

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.53.0 completa: la visión mira dentro de los clips, corrige "
      "en rondas sin re-pagar video, la ubicación se audita gratis y el texto "
      "en pantalla respeta la lengua de la escena.")
