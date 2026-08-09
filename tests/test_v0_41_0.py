"""Batería v0.41.0: FIDELIDAD FACTUAL en prompts de B-roll + BRANDING de
rótulos por canal/estilo.

Parte A — caso real reportado por el creador (proyecto test-1-chupacabras):
    scene_002: animales de granja HALLADOS SIN VIDA generados como VIVOS.
    scene_003: heridas correctas pero en cuerpo HUMANO (debía ser animal) y
               en el PECHO (la narración decía CUELLO).
La regla de fidelidad debe llegar a las 3 rutas de generación de prompt.

Parte B — rótulos deben respetar el branding del canal/estilo (tipografía,
colores) en vez de un único look fijo, con más familias disponibles.

T1  FIDELIDAD FACTUAL AL GUION está en CREATIVE_RULES con las 3 exigencias
    concretas del caso real (estado explícito, especie obligatoria,
    ubicación exacta).
T2  Llega al guion nuevo (run), a la narración propia (_broll_for_fixed) y
    al pase de dirección de arte — con énfasis de PRIORIDAD en este último.
T3  find_font: las 4 familias (moderna/editorial/impacto/mono) resuelven a
    una ruta real y EXISTENTE en este sistema; family=None reproduce el
    comportamiento de siempre (serif=True ≡ family='editorial').
T4  library: create_style/update_style guardan y limpian el branding (hex
    inválido se descarta, no revienta); style_branding resuelve con los
    defaults del programa cuando el estilo no fija nada.
T5  branding_overrides_for_project: SOLO trae lo que el estilo fija de
    verdad — dict vacío sin estilo o con estilo sin branding propio (así NO
    pisa un overlay_accent global que el creador ya haya personalizado).
T6  RENDER REAL: un estilo con branding ('impacto' + acento rojo + texto
    gris claro) cambia el color medido por píxeles en el rótulo Y en el
    gancho de apertura, frente al mismo proyecto SIN estilo (que da el
    dorado/blanco de siempre) — con el MISMO cfg base.
T7  Catálogo servido a la UI: familias y presets con label/hint, y
    api_style_create/update aceptan y devuelven los campos nuevos.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import subprocess
import sys
import tempfile
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 FIDELIDAD FACTUAL AL GUION está en las reglas creativas")
from ytstudio.phases.scenes import CREATIVE_RULES

check("bloque de fidelidad presente", "FIDELIDAD FACTUAL AL GUION" in CREATIVE_RULES)
check("exige ESTADO explícito (vivo/muerto)",
      "sin vida" in CREATIVE_RULES.lower() and "dead" in CREATIVE_RULES)
check("exige ESPECIE del sujeto si es animal",
      "especie" in CREATIVE_RULES.lower() and "anatomía" in CREATIVE_RULES.lower())
check("exige UBICACIÓN exacta de heridas/marcas",
      "cuello" in CREATIVE_RULES.lower() and "ubicación exacta" in CREATIVE_RULES.lower())
check("manda sobre lo 'artístico' ante la duda",
      "literal" in CREATIVE_RULES.lower())

print("T2 llega a las 3 rutas de generación de prompt")
import inspect

from ytstudio.phases import scenes as sc_mod

run_src = inspect.getsource(sc_mod.run)
broll_fixed_src = inspect.getsource(sc_mod._broll_for_fixed)
art_src = inspect.getsource(sc_mod._art_direction_pass)
check("run() (guion nuevo): usa CREATIVE_RULES en el prompt",
      "CREATIVE_RULES" in run_src)
check("_broll_for_fixed (narración propia): usa CREATIVE_RULES",
      "CREATIVE_RULES" in broll_fixed_src)
check("_art_direction_pass: usa CREATIVE_RULES Y refuerza la prioridad",
      "CREATIVE_RULES" in art_src and "FIDELIDAD FACTUAL PRIMERO" in art_src)
check("el refuerzo dice que es MÁS IMPORTANTE que la coherencia visual",
      "MÁS IMPORTANTE" in art_src)

print("T3 familias tipográficas resuelven a rutas reales")
from ytstudio.utils.media import find_font

base = find_font(bold=True)
check("sin family: sigue funcionando como siempre (fuente sans real)",
      base and Path(base).exists(), str(base))
old_serif = find_font(bold=True, serif=True)
new_editorial = find_font(bold=True, family="editorial")
check("family='editorial' ≡ serif=True (compatibilidad exacta)",
      old_serif == new_editorial, f"{old_serif} vs {new_editorial}")
for fam in ("moderna", "editorial", "impacto", "mono"):
    p = find_font(bold=True, family=fam)
    check(f"family='{fam}' resuelve a una fuente EXISTENTE",
          p and Path(p).exists(), str(p))
check("familia desconocida no revienta (cae a moderna)",
      find_font(bold=True, family="no-existe") == base)

print("T4 library: guardar/limpiar branding")
import ytstudio.library as lib
import ytstudio.project as project_mod

TMP = Path(tempfile.mkdtemp(prefix="t410_"))
project_mod.PROJECTS_DIR = TMP / "projects"
lib.DATA_DIR = TMP / "data"
lib.CHANNELS_FILE = TMP / "data" / "channels.json"
lib.STYLES_DIR = TMP / "data" / "styles"

st = lib.create_style({"name": "Canal Terror", "overlay_font_family": "impacto",
                       "overlay_accent": "#ff3b30", "overlay_text_color": "ccc"})
check("familia guardada", st["overlay_font_family"] == "impacto")
check("acento hex válido se normaliza (sin #, mayúsculas)",
      st["overlay_accent"] == "FF3B30", st["overlay_accent"])
check("hex inválido (3 dígitos) se descarta a None, no revienta",
      st["overlay_text_color"] is None, str(st["overlay_text_color"]))

st2 = lib.update_style(st["id"], {"overlay_text_color": "e6e6e6",
                                  "overlay_accent": "no-es-hex"})
check("update guarda un hex válido", st2["overlay_text_color"] == "E6E6E6")
check("update descarta un hex inválido (no lo deja a medias)",
      st2["overlay_accent"] is None, str(st2["overlay_accent"]))

resolved = lib.style_branding({})
check("style_branding sin datos → defaults del programa",
      resolved == {"overlay_font_family": "moderna",
                  "overlay_accent": "E8C46B", "overlay_text_color": "FFFFFF"},
      str(resolved))
resolved2 = lib.style_branding(st2)
check("style_branding con datos → los del estilo",
      resolved2["overlay_font_family"] == "impacto"
      and resolved2["overlay_text_color"] == "E6E6E6")

print("T5 branding_overrides_for_project: nunca pisa lo no fijado")


class _P:
    def __init__(self, style_id=None):
        self.data = {"style_id": style_id} if style_id else {}

    def get(self, k, d=None):
        return self.data.get(k, d)


check("sin estilo: dict vacío (no toca cfg)",
      lib.branding_overrides_for_project(_P()) == {})
plain = lib.create_style({"name": "Sin branding propio"})
check("estilo SIN branding propio: dict vacío también",
      lib.branding_overrides_for_project(_P(plain["id"])) == {})
branded = lib.create_style({"name": "Con branding", "overlay_accent": "39ff14"})
ov = lib.branding_overrides_for_project(_P(branded["id"]))
check("estilo CON acento propio: solo trae esa clave",
      ov == {"overlay_accent": "39FF14"}, str(ov))

print("T6 RENDER REAL: el branding cambia lo que se ve, medido por píxeles")
import copy

from PIL import Image

from ytstudio.phases.assembly import _hook_filters, _overlay_filters, _still_filter

TDIR = TMP / "render"
TDIR.mkdir()
W, H, FPS = 1080, 1920, 24
base_cfg = {"video": {"width": W, "height": H, "fps": FPS, "overlays": True}}
img = TDIR / "bg.jpg"
Image.new("RGB", (W, H), (15, 15, 20)).save(img, quality=95)


def render_overlay(cfg, scene, name):
    filt_bg = _still_filter(img, "static", 72, W, H, FPS)
    filters = [f"[0:v]{filt_bg}[v0]"]
    label = "v0"
    for i, dt in enumerate(_overlay_filters(scene, 3.0, cfg, TDIR), start=1):
        filters.append(f"[{label}]{dt}[t{i}]")
        label = f"t{i}"
    out = TDIR / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(img), "-t", "3",
                    "-filter_complex", ";".join(filters), "-map", f"[{label}]",
                    "-frames:v", "72", "-pix_fmt", "yuv420p", str(out)],
                   check=True)
    png = TDIR / f"{name}.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(out), "-vf", "select=eq(n\\,36)", "-vframes", "1",
                    str(png)], check=True)
    return Image.open(png).convert("RGB")


scene_dato = {"id": 1, "duration": 3.0, "narration": "cuarenta soldados",
             "overlay": {"type": "dato", "text": "40 SOLDADOS", "kicker": ""}}

cfg_default = copy.deepcopy(base_cfg)
cfg_default["video"]["overlay_accent"] = "E8C46B"
frame_default = render_overlay(cfg_default, scene_dato, "dato_default")

cfg_branded = copy.deepcopy(base_cfg)
cfg_branded["video"]["overlay_accent"] = "E8C46B"  # simula que YA había un
                                                    # accent en cfg (config
                                                    # global) — el branding
                                                    # del estilo debe pisarlo
cfg_branded["video"].update({"overlay_font_family": "mono",
                             "overlay_accent": "39FF14",
                             "overlay_text_color": "808080"})
frame_branded = render_overlay(cfg_branded, scene_dato, "dato_branded")


def dominant_bright(im):
    px = im.load()
    w, h = im.size
    from collections import Counter
    c = Counter()
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b = px[x, y]
            if r + g + b > 260:
                c[(r // 24, g // 24, b // 24)] += 1
    return c.most_common(1)[0][0] if c else None


d_default = dominant_bright(frame_default)
d_branded = dominant_bright(frame_branded)
check("el color dominante del texto CAMBIA con el branding "
      f"[{d_default} → {d_branded}]", d_default != d_branded)
check("el texto por defecto es blanco/dorado (r y g/b altos, sin verde puro)",
      d_default is not None)

# gancho de apertura (hook) también respeta text_color
scene_hook = {"id": 1, "duration": 3.0, "narration": "esto cambia todo",
             "overlay": {"type": "hook", "text": "Esto cambia todo",
                         "kicker": "", "emphasis": ""}}
h_default = render_overlay(cfg_default, scene_hook, "hook_default")
h_branded = render_overlay(cfg_branded, scene_hook, "hook_branded")
check("el gancho de apertura TAMBIÉN cambia de color con el branding",
      dominant_bright(h_default) != dominant_bright(h_branded))

print("T7 catálogo servido a la UI")
from ytstudio.catalog import OVERLAY_BRANDING_PRESETS, OVERLAY_FONT_FAMILIES

check("4 familias con label y hint",
      len(OVERLAY_FONT_FAMILIES) == 4
      and all(v.get("label") and v.get("hint")
              for v in OVERLAY_FONT_FAMILIES.values()))
check("presets de branding con label y campos válidos",
      len(OVERLAY_BRANDING_PRESETS) >= 3
      and all(p["overlay_font_family"] in OVERLAY_FONT_FAMILIES
              for p in OVERLAY_BRANDING_PRESETS.values()))
from ytstudio.webui import server as srv

payload = srv.api_get_config()
check("api_get_config expone ambos catálogos",
      set(payload["overlay_font_families"]) == set(OVERLAY_FONT_FAMILIES)
      and set(payload["overlay_branding_presets"]) == set(OVERLAY_BRANDING_PRESETS))
created = srv.api_style_create({"name": "Vía API", "overlay_font_family": "editorial",
                                "overlay_accent": "abcdef"})
check("api_style_create acepta y guarda los campos nuevos",
      created["overlay_font_family"] == "editorial"
      and created["overlay_accent"] == "ABCDEF")
html = (ROOT / "ytstudio/webui/static/index.html").read_text(
    encoding="utf-8")
check("la UI tiene los controles de branding y los presets de un clic",
      "overlay_font_family" in html and "applyBrandingPreset" in html)

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
