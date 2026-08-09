"""Batería v0.37.0: STICKERS animados de aspecto nativo (encuesta, pregunta,
cuenta regresiva) para formatos cortos.

Decisión acordada con el usuario: imitaciones VISUALES — un MP4 no puede ser
interactivo; estos stickers se renderizan con el look y la animación de los
nativos como recurso de retención (la respuesta va a comentarios). PIL +
ffmpeg local, costo $0.

T1  Renderizadores PIL: las tres tarjetas se generan con transparencia real
    en las esquinas (redondeadas), tamaño pedido y contenido pintado.
T2  Normalización: solo formatos cortos, exige texto, máximo UNO por video
    (gana el primero), tipos inválidos fuera.
T3  Render ffmpeg REAL de la encuesta: el sticker NO está al arrancar la
    escena, SÍ está durante el cuerpo (tarjeta blanca medida por píxeles en
    su posición), y YA NO está tras su salida.
T4  Countdown VIVO en render real: el número cambia entre segundos (los
    píxeles del área del número difieren entre t=1.5 y t=2.5) — es una
    cuenta real, no una imagen fija.
T5  El sticker afecta la firma de render (cambiarlo re-renderiza la escena).
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

from ytstudio.utils import stickers as stk

TMP = Path(__file__).parent / "t370"
TMP.mkdir(exist_ok=True)

print("T1 renderizadores PIL")
poll = stk.render_poll("¿Tú qué harías?", "Ahorrar", "Invertir", 600,
                       TMP / "poll.png")
q = stk.render_question("¿Cuál es tu mayor gasto hormiga?", 600,
                        TMP / "q.png")
cd, geom = stk.render_countdown("EL RESULTADO EN…", 600, TMP / "cd.png")
for name, p in (("encuesta", poll), ("pregunta", q), ("countdown", cd)):
    img = Image.open(p)
    check(f"{name}: PNG RGBA de {img.size[0]}px de ancho",
          img.mode == "RGBA" and img.size[0] == 600, f"{img.mode} {img.size}")
    corner = img.getpixel((2, 2))
    center = img.getpixel((300, img.size[1] // 3))
    check(f"{name}: esquina transparente (redondeada) y centro pintado",
          corner[3] < 40 and center[3] > 180, f"{corner} {center}")
check("countdown entrega la geometría del hueco del número",
      geom and geom.get("num_h", 0) > 0 and geom.get("size", 0) > 0, str(geom))

print("T2 normalización")
from ytstudio.phases.scenes import _normalize_creative


def base_scene(i, **over):
    d = {"id": i, "narration": f"escena {i}", "broll_type": "image",
         "animation": "zoom_in"}
    d.update(over)
    return d


sc = [base_scene(1, sticker_type="encuesta", sticker_text="¿Tú qué harías?",
                 sticker_a="Ahorrar", sticker_b="Invertir"),
      base_scene(2, sticker_type="pregunta", sticker_text="¿Y tú?"),
      base_scene(3, sticker_type="countdown", sticker_text="YA VIENE…")]
_normalize_creative(sc, short_form=True)
check("máximo UN sticker por video (gana el primero)",
      sc[0]["sticker"] and not sc[1]["sticker"] and not sc[2]["sticker"],
      str([bool(s.get('sticker')) for s in sc]))
check("el sticker conserva tipo, texto y opciones",
      sc[0]["sticker"]["type"] == "encuesta"
      and sc[0]["sticker"]["a"] == "Ahorrar")
sc2 = [base_scene(1, sticker_type="encuesta", sticker_text="")]
_normalize_creative(sc2, short_form=True)
check("sin texto → sin sticker", sc2[0]["sticker"] is None)
sc3 = [base_scene(1, sticker_type="encuesta", sticker_text="¿Va?")]
_normalize_creative(sc3, short_form=False)
check("en 16:9 largo → sin stickers", sc3[0]["sticker"] is None)
sc4 = [base_scene(1, sticker_type="raro", sticker_text="x")]
_normalize_creative(sc4, short_form=True)
check("tipo inválido → sin sticker", sc4[0]["sticker"] is None)

print("T3 render real: la encuesta entra, se sostiene y sale")
from ytstudio.phases.assembly import _render_scene


class _Proj:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, key, *parts):
        p = self.root / key
        p.mkdir(parents=True, exist_ok=True)
        return p.joinpath(*parts) if parts else p

    def get(self, k, d=None):
        return d


W, H, FPS = 1080, 1920, 24
cfg_v = {"video": {"width": W, "height": H, "fps": FPS, "overlays": True,
                   "overlay_accent": "E8C46B"}}
proj = _Proj(TMP / "proj")
Image.new("RGB", (1080, 1920), (40, 40, 60)).save(
    proj.path("broll", "scene_002.jpg"))
scene = {"id": 2, "duration": 4.0, "animation": "static",
         "broll_image": "scene_002.jpg", "narration": "x",
         "sticker": {"type": "encuesta", "text": "¿Tú qué harías?",
                     "a": "Ahorrar", "b": "Invertir"}}
out_v = TMP / "poll.mp4"
_render_scene(scene, proj, cfg_v, out_v, {"fin": False, "fout": False})


def frame_of(video, idx, name):
    png = TMP / name
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-vf", f"select=eq(n\\,{idx})",
                    "-vframes", "1", str(png)], check=True)
    return Image.open(png).convert("RGB")


card_w = int(min(W, H) * 0.56)
x_final = W - card_w - int(W * 0.05)
probe_x, probe_y = x_final + card_w // 2, int(H * 0.36) + 60


def whiteness(im):
    p = im.getpixel((probe_x, probe_y))
    return sum(p)


early = whiteness(frame_of(out_v, 2, "p_early.png"))    # t≈0.08 (antes de t0)
mid = whiteness(frame_of(out_v, 48, "p_mid.png"))       # t=2.0 (sostenido)
late = whiteness(frame_of(out_v, 94, "p_late.png"))     # t≈3.9 (tras salida)
check(f"al inicio NO está (fondo oscuro) [{early}]", early < 300)
check(f"en el cuerpo SÍ está (tarjeta blanca) [{mid}]", mid > 550)
check(f"tras su salida YA NO está [{late}]", late < 300)

print("T4 countdown vivo: el número cambia con los segundos")
scene_cd = {"id": 3, "duration": 5.0, "animation": "static",
            "broll_image": "scene_002.jpg", "narration": "x",
            "sticker": {"type": "countdown", "text": "EL RESULTADO EN…",
                        "a": "", "b": ""}}
out_cd = TMP / "cd.mp4"
_render_scene(scene_cd, proj, cfg_v, out_cd, {"fin": False, "fout": False})
f1 = frame_of(out_cd, 36, "cd1.png")   # t=1.5
f2 = frame_of(out_cd, 60, "cd2.png")   # t=2.5
_, geom = stk.render_countdown("EL RESULTADO EN…", card_w, TMP / "probe.png")
ny0 = int(H * 0.36) + geom["num_y"]
region = (x_final, ny0, x_final + card_w, ny0 + geom["num_h"])
diff = sum(1 for y in range(region[1], region[3], 4)
           for x in range(region[0], region[2], 4)
           if f1.getpixel((x, y)) != f2.getpixel((x, y)))
check(f"los píxeles del número difieren entre t=1.5 y t=2.5 [{diff}]",
      diff > 40)
num_white = sum(1 for y in range(region[1], region[3], 4)
                for x in range(region[0], region[2], 4)
                if sum(f1.getpixel((x, y))) > 600)
check("el número blanco es visible sobre la tarjeta oscura",
      num_white > 10, str(num_white))

print("T5 el sticker forma parte de la firma de render")
from ytstudio.phases.assembly import _render_signature

s_a = [dict(scene, sticker={"type": "encuesta", "text": "A", "a": "", "b": ""})]
s_b = [dict(scene, sticker=None)]
plans = [{"fin": False, "fin_d": 0, "fout": False, "fout_d": 0}]
sig_a = _render_signature(s_a, plans, cfg_v, proj)
sig_b = _render_signature(s_b, plans, cfg_v, proj)
check("firma distinta con/sin sticker (cambiarlo re-renderiza)",
      sig_a != sig_b)

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
