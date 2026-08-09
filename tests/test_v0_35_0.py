"""Batería v0.35.0: motor de texto/hooks visuales + rupturas de patrón +
formatos Meta Ads (1:1 y 4:5).

Según lo decidido con el usuario: primero el motor de texto. Todo es ffmpeg
local — costo $0 por uso.

T1  Formatos nuevos: ad_square (1080x1080) y ad_45 (1080x1350) registrados
    con subtítulos quemados; is_short_form distingue 9:16/1:1/4:5 del 16:9.
T2  aspect_for pide al generador el aspecto REAL del proyecto (antes un
    proyecto 1:1 pedía imágenes 16:9): 1:1, 4:5, 9:16, 16:9; y respeta la
    lista de aspectos que el modelo soporta (Kling sin 4:5 → 1:1).
T3  Gancho visual (overlay 'hook') en un render ffmpeg REAL 9:16: el texto
    aparece desde el primer instante (frame temprano CON texto) y desaparece
    hacia el final de la escena (frame tardío Sin texto) — medido por
    píxeles, no supuesto.
T4  Escena 1 de un formato corto SIEMPRE abre con hook: el respaldo
    determinista lo pone si el modelo no lo puso; en 16:9 NO se inventa.
T5  Rupturas de patrón: zoom punch en cortes alternados, flash con sfx boom,
    nada en escena 1/fundidos/16:9; y el render REAL con zoom muestra el
    primer frame ampliado respecto al frame asentado.
T6  El pase de dirección de arte y los prompts de escenas incluyen las
    reglas de formato corto SOLO en formatos cortos.
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
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from PIL import Image

from ytstudio.catalog import FORMATS, aspect_for, is_short_form, is_vertical

TMP = Path(__file__).parent / "t350"
TMP.mkdir(exist_ok=True)

print("T1 formatos Meta Ads registrados y clasificación short-form")
check("ad_square y ad_45 existen en FORMATS",
      "ad_square" in FORMATS and "ad_45" in FORMATS)
sq = FORMATS["ad_square"]["overrides"]["video"]
f45 = FORMATS["ad_45"]["overrides"]["video"]
check("1:1 = 1080x1080 con subtítulos quemados",
      sq["width"] == 1080 and sq["height"] == 1080 and sq["burn_subtitles"])
check("4:5 = 1080x1350", f45["width"] == 1080 and f45["height"] == 1350)


def _cfg(w, h):
    return {"video": {"width": w, "height": h}}


check("short-form: 9:16, 1:1 y 4:5 sí; 16:9 no",
      is_short_form(_cfg(1080, 1920)) and is_short_form(_cfg(1080, 1080))
      and is_short_form(_cfg(1080, 1350)) and not is_short_form(_cfg(1920, 1080)))
check("is_vertical NO cambió (1:1 no es vertical)",
      not is_vertical(_cfg(1080, 1080)) and is_vertical(_cfg(1080, 1920)))

print("T2 aspect_for pide el aspecto real al generador")
check("16:9 largo", aspect_for(_cfg(1920, 1080)) == "16:9")
check("vertical", aspect_for(_cfg(1080, 1920)) == "9:16")
check("cuadrado (antes pedía 16:9 y salía recortado)",
      aspect_for(_cfg(1080, 1080)) == "1:1")
check("retrato de feed", aspect_for(_cfg(1080, 1350)) == "4:5")
check("con lista de soportados (Kling sin 4:5): elige 1:1, el más cercano",
      aspect_for(_cfg(1080, 1350), allowed=("16:9", "9:16", "1:1")) == "1:1")

print("T3 gancho visual en render ffmpeg REAL (9:16)")
from ytstudio.phases.assembly import (_auto_interrupt, _hook_filters,
                                      _interrupt_filter, _still_filter)

W, H, FPS = 1080, 1920, 24
cfg_v = {"video": {"width": W, "height": H, "fps": FPS, "overlays": True,
                   "overlay_accent": "E8C46B"}}
img = TMP / "bg.jpg"
Image.new("RGB", (W, H), (12, 40, 24)).save(img, quality=95)
scene = {"id": 1, "duration": 4.0, "animation": "static",
         "overlay": {"type": "hook", "text": "Esto cambia tu manera de ahorrar",
                     "kicker": "", "emphasis": "ahorrar"},
         "narration": "esto cambia tu manera de ahorrar"}
hook = _hook_filters(scene, scene["overlay"], 4.0, cfg_v, TMP, "0xE8C46B")
check("el gancho genera drawtext multi-línea", len(hook) >= 2, str(len(hook)))
dur, frames = 4.0, 96
chain = [f"[0:v]{_still_filter(img, 'static', frames, W, H, FPS)}[v0]"]
label = "v0"
for i, dt in enumerate(hook, start=1):
    chain.append(f"[{label}]{dt}[t{i}]")
    label = f"t{i}"
outv = TMP / "hook.mp4"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-i", str(img), "-t", str(dur),
                "-filter_complex", ";".join(chain), "-map", f"[{label}]",
                "-frames:v", str(frames), "-pix_fmt", "yuv420p", str(outv)],
               check=True)


def frame_at(video, idx, name):
    png = TMP / name
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-vf", f"select=eq(n\\,{idx})",
                    "-vframes", "1", str(png)], check=True)
    return Image.open(png).convert("RGB")


def bright_pixels(im, region=None):
    px = im.load()
    w, h = im.size
    x0, y0, x1, y1 = region or (0, 0, w, h)
    n = 0
    for y in range(y0, y1, 3):
        for x in range(x0, x1, 3):
            if sum(px[x, y]) > 380:  # blanco/acento sobre fondo oscuro
                n += 1
    return n


early = frame_at(outv, 12, "early.png")   # t=0.5s
late = frame_at(outv, 90, "late.png")     # t=3.75s (tras la salida)
top = (0, 0, W, int(H * 0.55))
check("a los 0.5s el texto del gancho ESTÁ en pantalla",
      bright_pixels(early, top) > 150, str(bright_pixels(early, top)))
check("al final de la escena el gancho YA se fue (no queda pegado)",
      bright_pixels(late, top) < 20, str(bright_pixels(late, top)))

print("T4 la escena 1 de un formato corto SIEMPRE abre con hook")
from ytstudio.phases.scenes import _normalize_creative

sc = [{"id": 1, "narration": "Nadie te contó esto sobre el dinero y los bancos",
       "broll_type": "image", "animation": "zoom_in"},
      {"id": 2, "narration": "Segunda escena", "broll_type": "image",
       "animation": "pan_left"}]
_normalize_creative(sc, short_form=True)
o = sc[0].get("overlay")
check("respaldo determinista: hook con las primeras palabras (≤8)",
      o and o["type"] == "hook" and 0 < len(o["text"].split()) <= 9, str(o))
sc16 = [{"id": 1, "narration": "Un documental largo no abre con texto gigante",
         "broll_type": "image", "animation": "zoom_in"}]
_normalize_creative(sc16, short_form=False)
check("en 16:9 NO se inventa hook", not sc16[0].get("overlay"))
sc_llm = [{"id": 1, "narration": "x", "broll_type": "image",
           "animation": "zoom_in", "overlay_type": "hook",
           "overlay_text": "El banco no quiere que sepas esto",
           "overlay_kicker": "", "overlay_emphasis": "banco"}]
_normalize_creative(sc_llm, short_form=True)
check("si el modelo ya puso el hook, se respeta su texto",
      sc_llm[0]["overlay"]["text"] == "El banco no quiere que sepas esto")

print("T5 rupturas de patrón")
cfg_h = {"video": {"width": 1920, "height": 1080, "fps": 24}}
check("escena 1: sin efecto (el gancho manda)",
      _auto_interrupt({"id": 1, "transition": "corte"}, cfg_v) == "")
check("sfx boom → flash",
      _auto_interrupt({"id": 3, "sfx": "boom"}, cfg_v) == "flash")
check("corte seco alternado → zoom",
      _auto_interrupt({"id": 4, "transition": "corte"}, cfg_v) == "zoom")
check("fundido → sin efecto (el fundido ya es la transición)",
      _auto_interrupt({"id": 4, "transition": "fundido"}, cfg_v) == "")
check("en 16:9 nunca hay ruptura",
      _auto_interrupt({"id": 4, "sfx": "boom"}, cfg_h) == "")
# render real del golpe de zoom: primer frame ampliado vs frame asentado.
# La línea de referencia va al 10% de la altura (y=192): con zoom 1.10x
# centrado se desplaza hacia el borde (~y=115) sin salirse del cuadro —
# medible; una línea EN el borde se recortaría y no habría qué medir.
zoom = _interrupt_filter("zoom", FPS, W, H)
mark = TMP / "mark.png"
im = Image.new("RGB", (W, H), (30, 30, 30))
px = im.load()
Y_REF = int(H * 0.10)
for x in range(0, W, 2):
    for dy in (0, 1, 2):
        px[x, Y_REF + dy] = (255, 255, 255)
im.save(mark)
outz = TMP / "zoom.mp4"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-i", str(mark), "-t", "1",
                "-filter_complex", f"[0:v]fps={FPS},{zoom}[v]", "-map", "[v]",
                "-frames:v", "24", "-pix_fmt", "yuv420p", str(outz)],
               check=True)


def line_y(im):
    px = im.load()
    w, h = im.size
    for y in range(0, h // 2):
        row = sum(1 for x in range(0, w, 8) if sum(px[x, y]) > 500)
        if row > w / 24:
            return y
    return None


y_first = line_y(frame_at(outz, 0, "z0.png"))
y_settled = line_y(frame_at(outz, 20, "z20.png"))
check(f"primer frame AMPLIADO: la línea sube hacia el borde "
      f"[y0={y_first} vs asentado y={y_settled}]",
      y_first is not None and y_settled is not None
      and y_first < y_settled - 40)
check("flash genera un fade desde blanco",
      "color=white" in _interrupt_filter("flash", FPS, W, H))

print("T6 reglas short-form solo en formatos cortos")
from ytstudio.phases.scenes import SHORT_FORM_RULES, _art_direction_pass


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def complete_json(self, system, prompt, schema=None, max_tokens=None,
                      purpose=None):
        self.prompts.append(prompt)
        return {"bible": {"era_setting": "", "palette": "", "lighting": "",
                          "camera_language": "", "texture_grade": "",
                          "motifs": []}, "scenes": []}


class _P:
    def get(self, k, d=None):
        return d

    def set(self, k, v):
        pass

    def add_warning(self, m):
        pass


concept = {"visual_style": {"prompt_prefix": "x"}}
base = {"id": 1, "narration": "n", "broll_prompt": "p", "broll_type": "image"}
llm = _FakeLLM()
_art_direction_pass(llm, _P(), [dict(base)], concept, "es", short_form=True)
_art_direction_pass(llm, _P(), [dict(base)], concept, "es", short_form=False)
check("pase de dirección corto: lleva las reglas de formato corto",
      "FORMATO CORTO DE REDES" in llm.prompts[0])
check("pase de dirección largo: NO las lleva",
      "FORMATO CORTO DE REDES" not in llm.prompts[1])
check("las reglas exigen hook en la escena 1",
      "overlay_type='hook'" in SHORT_FORM_RULES)

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
