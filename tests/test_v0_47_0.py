"""Batería v0.47.0 — RÓTULOS con diseño + estimación honesta de llamadas.

Fase 1 de las 4 acordadas para la calidad audiovisual. Hasta v0.46 el rótulo
era `drawtext` pelado: sin placa (se perdía sobre un B-roll claro), sin filete
de acento y sin poder pintar la palabra clave en otro color. Ahora se compone
como imagen (PIL) con placa, filete y jerarquía, en tres variantes por estilo
de canal.

Y la estimación decía «~7 llamadas» cuando un video de 84 escenas hace ~25
(tandas de escenas, dirección de arte, documentalista, control con visión):
el tope de presupuesto se calculaba sobre una base corta.

Verifica:
1. Las tres variantes (documental/minimal/bold) producen diseños REALMENTE
   distintos, medidos en píxeles.
2. El filete de acento y la palabra de énfasis se pintan con el color del
   canal (no toda la línea del mismo color, que era el límite de drawtext).
3. El bloque nunca se sale del encuadre y el de 'personaje' no invade la
   franja de subtítulos.
4. Gancho y conclusión conservan su lenguaje propio; con overlay_plate=false
   se vuelve al rótulo clásico (y no se pinta dos veces).
5. Montaje REAL con ffmpeg: el rótulo aparece tras su momento, no antes.
6. La firma de render cambia con el estilo de rótulo (reanudar re-renderiza).
7. La estimación cuenta las llamadas reales y su costo sube en consecuencia.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os
import shutil
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0470_"))

from PIL import Image

from ytstudio.utils import lower_thirds as lt

ACCENT = "E8C46B"
AC_RGB = (232, 196, 107)


def stats(png: Path) -> dict:
    """(opacos, acento, oscuros) del PNG compuesto."""
    im = Image.open(png).convert("RGBA")
    px = list(im.getdata())
    opacos = sum(1 for p in px if p[3] > 40)
    acento = sum(1 for p in px if p[3] > 120
                 and abs(p[0] - AC_RGB[0]) < 26 and abs(p[1] - AC_RGB[1]) < 26
                 and abs(p[2] - AC_RGB[2]) < 26)
    oscuros = sum(1 for p in px if p[3] > 120 and max(p[:3]) < 60)
    return {"total": len(px), "opacos": opacos, "acento": acento,
            "oscuros": oscuros}


# ---------------------------------------------------------------------------
# T1 — las tres variantes son diseños distintos (medido en píxeles)
# ---------------------------------------------------------------------------
res = {}
for st in lt.STYLES:
    p = lt.render("Mansa Musa", "El hombre más rico", "Musa", "personaje",
                  TMP / f"{st}.png", width=1920, height=1080, style=st,
                  accent=ACCENT)
    res[st] = {**stats(p["file"]), **p}

check("T1 'documental' pone una PLACA oscura tras el texto",
      res["documental"]["oscuros"] > 0.35 * res["documental"]["total"],
      f"{res['documental']['oscuros']}/{res['documental']['total']}")
check("T1b 'minimal' NO lleva placa (casi todo transparente)",
      res["minimal"]["opacos"] < 0.25 * res["minimal"]["total"],
      f"{res['minimal']['opacos']}/{res['minimal']['total']}")
check("T1c 'bold' llena la placa con el color de acento",
      res["bold"]["acento"] > 0.35 * res["bold"]["total"],
      f"{res['bold']['acento']}/{res['bold']['total']}")
check("T1d y las tres se distinguen entre sí",
      len({res[s]["oscuros"] // 500 for s in lt.STYLES}) == 3,
      str({s: res[s]["oscuros"] for s in lt.STYLES}))

# ---------------------------------------------------------------------------
# T2 — filete de acento y ÉNFASIS en color dentro de la misma línea
# ---------------------------------------------------------------------------
con = lt.render("El imperio más rico", "", "rico", "dato", TMP / "emph.png",
                width=1920, height=1080, style="documental", accent=ACCENT)
sin = lt.render("El imperio más rico", "", "", "dato", TMP / "noemph.png",
                width=1920, height=1080, style="documental", accent=ACCENT)
s_con, s_sin = stats(con["file"]), stats(sin["file"])
check("T2 el filete de acento existe siempre (aunque no haya énfasis)",
      s_sin["acento"] > 200, str(s_sin["acento"]))
check("T2b la palabra de ÉNFASIS añade acento dentro de la línea",
      s_con["acento"] > s_sin["acento"] * 1.15,
      f"con={s_con['acento']} sin={s_sin['acento']}")
part = lt._split_emphasis("El imperio más rico", "rico")
check("T2c el texto se parte en tramos y solo el énfasis va marcado",
      any(t[1] for t in part) and sum(1 for t in part if t[1]) == 1,
      str(part))
check("T2d sin énfasis, el texto va de una pieza",
      lt._split_emphasis("Solo texto", "") == [("Solo texto", False)],
      str(lt._split_emphasis("Solo texto", "")))

# ---------------------------------------------------------------------------
# T3 — el bloque cabe en el encuadre y respeta la franja de subtítulos
# ---------------------------------------------------------------------------
largo = lt.render("Una frase mucho más larga de lo habitual para un rótulo",
                  "Contexto largo también", "larga", "dato", TMP / "largo.png",
                  width=1920, height=1080, style="documental", accent=ACCENT)
check("T3 un texto largo sigue cabiendo en el encuadre",
      largo["x"] >= 0 and largo["y"] >= 0
      and largo["x"] + largo["w"] <= 1920
      and largo["y"] + largo["h"] <= 1080,
      f"{largo['x']},{largo['y']} {largo['w']}x{largo['h']}")
pers = res["documental"]
check("T3b el rótulo de personaje no invade la franja de subtítulos (<80%)",
      pers["y"] + pers["h"] <= 1080 * 0.80 + 2,
      f"y={pers['y']} h={pers['h']} límite={1080 * 0.80:.0f}")
vert = lt.render("El Cairo", "Egipto", "", "lugar", TMP / "vert.png",
                 width=1080, height=1920, style="documental", accent=ACCENT)
check("T3c en vertical (9:16) también cabe",
      vert["x"] + vert["w"] <= 1080 and vert["y"] + vert["h"] <= 1920,
      f"{vert['w']}x{vert['h']} en {vert['x']},{vert['y']}")

# ---------------------------------------------------------------------------
# T4 — qué lleva placa y qué no (sin pintar dos veces)
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import (_lower_third_plan, _lower_third_setup,
                                      _overlay_filters)

cfg = {"language": "es",
       "video": {"width": 640, "height": 360, "fps": 12, "overlays": True,
                 "overlay_accent": ACCENT, "overlay_plate": True,
                 "overlay_style": "documental", "elements": False},
       "audio": {}}
esc = {"id": 1, "duration": 8.0, "narration": "Mansa Musa cruzó el Sahara.",
       "overlay": {"type": "personaje", "text": "Mansa Musa",
                   "kicker": "Emperador de Malí", "emphasis": "Musa"}}
plan = _lower_third_plan(esc, cfg, TMP)
check("T4 un rótulo de personaje se compone con placa", plan is not None, "")
check("T4b y entonces NO se dibuja además con el método clásico",
      _overlay_filters(esc, 8.0, cfg, TMP) == [], "")

hook = {"id": 2, "duration": 6.0, "narration": "x",
        "overlay": {"type": "hook", "text": "Nadie lo sabía", "kicker": "",
                    "emphasis": "Nadie"}}
concl = {"id": 3, "duration": 6.0, "narration": "x",
         "overlay": {"type": "conclusion", "text": "Y así terminó todo",
                     "kicker": "", "emphasis": "terminó"}}
check("T4c gancho y conclusión conservan su lenguaje propio (sin placa)",
      _lower_third_plan(hook, cfg, TMP) is None
      and _lower_third_plan(concl, cfg, TMP) is None, "")
check("T4d …y siguen dibujándose (no se perdieron)",
      len(_overlay_filters(hook, 6.0, cfg, TMP)) > 0
      and len(_overlay_filters(concl, 6.0, cfg, TMP)) > 0, "")

cfg_off = {**cfg, "video": {**cfg["video"], "overlay_plate": False}}
check("T4e con overlay_plate=false se vuelve al rótulo clásico",
      _lower_third_plan(esc, cfg_off, TMP) is None
      and len(_overlay_filters(esc, 8.0, cfg_off, TMP)) > 0, "")
cfg_no = {**cfg, "video": {**cfg["video"], "overlays": False}}
check("T4f con overlays=false no hay rótulo de ningún tipo",
      _lower_third_plan(esc, cfg_no, TMP) is None
      and _overlay_filters(esc, 8.0, cfg_no, TMP) == [], "")

# proyectos antiguos (texto plano) siguen funcionando
viejo = {"id": 4, "duration": 8.0, "narration": "x",
         "on_screen_text": "1324 d.C."}
check("T4g un proyecto antiguo (on_screen_text) también recibe el diseño",
      _lower_third_plan(viejo, cfg, TMP) is not None, "")

# ---------------------------------------------------------------------------
# T5 — MONTAJE REAL con ffmpeg: el rótulo aparece cuando debe
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import _render_scene


class PStub:
    def __init__(self):
        self.data = {}

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        pass

    def path(self, kind, name=""):
        d = TMP / "proj" / kind
        d.mkdir(parents=True, exist_ok=True)
        return d / name if name else d


proj = PStub()
# Fondo GRIS MEDIO a propósito: sobre un fondo oscuro, una placa oscura casi
# no cambia el brillo — lo que se mide es la aparición del COLOR DE ACENTO
# (filete + énfasis), que no existe en el B-roll.
Image.new("RGB", (640, 360), (128, 128, 128)).save(
    proj.path("broll", "scene_001.jpg"))
esc_r = {**esc, "broll_image": "scene_001.jpg", "animation": "static",
         "duration": 5.0, "overlay_at": 2.0}
args, chain, pos = _lower_third_setup(esc_r, 5.0, cfg, TMP)
check("T5 el rótulo entra al grafo con su ventana de tiempo",
      args and "between(t," in pos and "fade=t=in" in chain, f"{pos}")
out_mp4 = TMP / "esc.mp4"
try:
    _render_scene(esc_r, proj, cfg, out_mp4, fade={})
    ok = out_mp4.exists() and out_mp4.stat().st_size > 0
except Exception as e:
    ok = False
    print("   render:", e)
check("T5b la escena con rótulo de placa RENDERIZA con ffmpeg", ok, "")
if ok:
    def acento_px(t):
        f = TMP / f"fr{t}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(out_mp4),
                        "-frames:v", "1", str(f)], capture_output=True)
        im = Image.open(f).convert("RGB")
        return sum(1 for p in im.getdata()
                   if abs(p[0] - AC_RGB[0]) < 40 and abs(p[1] - AC_RGB[1]) < 40
                   and abs(p[2] - AC_RGB[2]) < 40)
    antes, durante = acento_px(0.6), acento_px(3.0)
    check("T5c el rótulo es VISIBLE tras su momento y no antes "
          "(color de acento medido en el cuadro)",
          antes == 0 and durante > 150, f"antes={antes} durante={durante}")

# ---------------------------------------------------------------------------
# T6 — la firma de render reacciona al estilo de rótulo
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import _render_signature

escenas = [{"id": 1, "duration": 5, "broll_image": "scene_001.jpg",
            "overlay": esc["overlay"]}]
f_doc = _render_signature(escenas, [{}], cfg, proj)
cfg_bold = {**cfg, "video": {**cfg["video"], "overlay_style": "bold"}}
f_bold = _render_signature(escenas, [{}], cfg_bold, proj)
check("T6 cambiar el estilo del rótulo re-renderiza las escenas",
      f_doc != f_bold, "")

# ---------------------------------------------------------------------------
# T7 — la estimación cuenta las llamadas REALES
# ---------------------------------------------------------------------------
from ytstudio.estimate import estimate


class PEst:
    def __init__(self, n):
        self.data = {"scene_count": n, "total_duration": n * 13}
        self.dir = TMP

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        pass


cfg_est = {
    "language": "es",
    "video": {"width": 1920, "height": 1080, "target_minutes": 18,
              "scene_seconds": 13},
    "providers": {
        "llm": {"name": "anthropic", "model": "claude-opus-4-8"},
        "images": {"name": "replicate",
                   "model": "black-forest-labs/flux-1.1-pro",
                   "fact_check": True},
        "videogen": {"name": "none"}, "tts": {"name": "mock"},
        "stt": {"name": "openai"}, "music": {"name": "mock"},
    },
    "performance": {"parallel_images": 4},
    "audio": {}, "subtitles": {}, "publish": {},
}
# La estimación degrada a «vista previa» sin claves (correcto): para medir el
# costo REAL se simula que existen, como en la máquina del creador.
_prev = {k: os.environ.get(k)
         for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "REPLICATE_API_TOKEN")}
os.environ.update({k: "de-prueba-no-se-usa" for k in _prev})
try:
    est84 = estimate(PEst(84), cfg_est)
    est12 = estimate(PEst(12), cfg_est)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def llm_item(est):
    return next(i for i in est["items"] if i["fase"].startswith("Inteligencia"))


i84, i12 = llm_item(est84), llm_item(est12)
import re

n84 = int(re.search(r"~(\d+) llamadas", i84["detalle"]).group(1))
n12 = int(re.search(r"~(\d+) llamadas", i12["detalle"]).group(1))
check("T7 un video de 84 escenas ya no dice «7 llamadas» (tandas + visión)",
      n84 >= 20, f"{n84} llamadas")
check("T7b y un video corto sigue siendo barato en llamadas",
      n12 < n84 and n12 >= 7, f"{n12} vs {n84}")
check("T7c el costo de inteligencia crece con el tamaño del video",
      i84["costo"][0] > i12["costo"][0], f"{i84['costo']} vs {i12['costo']}")
check("T7d el control de calidad con visión entra en la cuenta",
      "visión" in i84["detalle"], i84["detalle"])

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.47.0 completa: rótulos con placa, filete y énfasis en "
      "color, en tres variantes por canal — y la estimación dice la verdad.")
shutil.rmtree(TMP, ignore_errors=True)
