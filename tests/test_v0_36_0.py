"""Batería v0.36.0: REACCIONES (chroma / burbuja / personaje PiP) +
PANTALLA DIVIDIDA.

Todo composición ffmpeg local (costo $0). Fuentes de reacción (decisión del
usuario: ambas): su propio video grabado (pantalla verde auto-detectada →
chroma key; sin verde → burbuja circular) y el personaje IA con lipsync en
modo burbuja (character.pip).

T1  Detección de pantalla verde: un video con fondo verde da True; uno con
    fondo normal da False (muestreo real de bordes de un fotograma).
T2  PANTALLA DIVIDIDA en render REAL 9:16: mitad superior e inferior
    muestran CADA una su imagen (colores medidos por píxeles), con divisor.
    En horizontal 16:9 la división es izquierda/derecha.
T3  CHROMA KEY real: la persona sobre fondo verde queda compuesta sobre el
    contenido — el verde desaparece (el fondo del contenido se ve donde
    había verde) y la persona permanece.
T4  BURBUJA CIRCULAR real: el video de reacción sin pantalla verde aparece
    en un círculo (esquinas del cuadrado de la burbuja = fondo visible,
    centro = reacción) en la esquina inferior.
T5  El tramo de reacción va SINCRONIZADO: la escena que empieza en t=N
    muestra el momento t=N del video de reacción (video-reloj de colores).
T6  Escenas: layout dividida requiere prompt B y formato corto; en 16:9
    largo se fuerza 'completo'; el B-roll B se refleja en el storyboard.
T7  Personaje PiP (burbuja): las escenas personaje conservan su B-roll y
    llevan pip_video; si el lipsync falla no hay fallback de pantalla
    completa (solo aviso); sin pip el comportamiento clásico no cambia.
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

TMP = Path(__file__).parent / "t360"
TMP.mkdir(exist_ok=True)


def make_video(path, color, seconds=3, size="320x480", overlay_clock=False):
    """Video sintético de un color; con overlay_clock, el color CAMBIA por
    segundo (rojo→verde→azul) para poder verificar sincronía de tramos."""
    if overlay_clock:
        vf = ("color=red:s=%s:d=1[a];color=lime:s=%s:d=1[b];"
              "color=blue:s=%s:d=1[c];[a][b][c]concat=n=3:v=1" % (size, size, size))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-filter_complex", vf, "-pix_fmt", "yuv420p",
                        str(path)], check=True)
    else:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"color={color}:s={size}:d={seconds}",
                        "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def make_person_on_green(path, seconds=3, size=(320, 480)):
    """'Persona' sintética: rectángulo magenta centrado sobre fondo VERDE."""
    w, h = size
    img = Image.new("RGB", (w, h), (0, 177, 64))       # verde chroma
    for y in range(h // 4, h):
        for x in range(w // 3, 2 * w // 3):
            img.putpixel((x, y), (200, 40, 160))       # magenta = persona
    png = TMP / "person.png"
    img.save(png)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(png), "-t", str(seconds),
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


print("T1 detección de pantalla verde (muestreo real de bordes)")
from ytstudio.phases.broll import _detect_green_screen

greenv = make_person_on_green(TMP / "green.mp4")
normal = make_video(TMP / "normal.mp4", "gray")
check("video con fondo verde → chroma detectado",
      _detect_green_screen(greenv, TMP) is True)
check("video normal → sin chroma (irá en burbuja)",
      _detect_green_screen(normal, TMP) is False)

print("T2 pantalla dividida en render REAL")
from ytstudio.phases.assembly import _render_scene


class _Proj:
    def __init__(self, root, data=None):
        self.root = Path(root)
        self.data = data or {}

    def path(self, key, *parts):
        p = self.root / key
        p.mkdir(parents=True, exist_ok=True)
        return p.joinpath(*parts) if parts else p

    def get(self, k, d=None):
        return self.data.get(k, d)


W, H, FPS = 1080, 1920, 24
cfg_v = {"video": {"width": W, "height": H, "fps": FPS, "overlays": True,
                   "overlay_accent": "E8C46B"}}
proj = _Proj(TMP / "proj")
Image.new("RGB", (720, 720), (200, 30, 30)).save(proj.path("broll", "scene_001.jpg"))
Image.new("RGB", (720, 720), (30, 60, 200)).save(proj.path("broll", "scene_001_b.jpg"))
scene_split = {"id": 3, "duration": 2.0, "animation": "zoom_in",
               "layout": "dividida", "broll_image": "scene_001.jpg",
               "broll_image_b": "scene_001_b.jpg", "narration": "x"}
out_split = TMP / "split.mp4"
_render_scene(scene_split, proj, cfg_v, out_split, {"fin": False, "fout": False})


def frame_of(video, idx, name):
    png = TMP / name
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video), "-vf", f"select=eq(n\\,{idx})",
                    "-vframes", "1", str(png)], check=True)
    return Image.open(png).convert("RGB")


fr = frame_of(out_split, 12, "split.png")
top = fr.getpixel((W // 2, H // 4))
bot = fr.getpixel((W // 2, 3 * H // 4))
check("vertical: mitad superior = imagen A (roja)",
      top[0] > 130 and top[2] < 90, str(top))
check("vertical: mitad inferior = imagen B (azul)",
      bot[2] > 130 and bot[0] < 90, str(bot))
mid = fr.getpixel((W // 2, H // 2))
check("hay divisor oscuro entre mitades", sum(mid) < 180, str(mid))

cfg_h = {"video": {"width": 1920, "height": 1080, "fps": FPS,
                   "overlays": True, "overlay_accent": "E8C46B"}}
out_h = TMP / "splith.mp4"
scene_split_h = dict(scene_split, id=4)
_render_scene(scene_split_h, proj, cfg_h, out_h, {"fin": False, "fout": False})
frh = frame_of(out_h, 12, "splith.png")
left = frh.getpixel((1920 // 4, 540))
right = frh.getpixel((3 * 1920 // 4, 540))
check("horizontal: izquierda A (roja) / derecha B (azul)",
      left[0] > 130 and right[2] > 130, f"{left} {right}")

print("T3 chroma key real: el verde desaparece, la persona queda")
proj_react = _Proj(TMP / "proj2",
                   {"reaction": {"file": "01_react.mp4", "chroma": True}})
import shutil as _sh
_sh.copyfile(greenv, proj_react.path("input", "01_react.mp4"))
Image.new("RGB", (1080, 1920), (240, 210, 60)).save(
    proj_react.path("broll", "scene_002.jpg"))   # fondo AMARILLO
scene_r = {"id": 2, "duration": 2.0, "animation": "static",
           "broll_image": "scene_002.jpg", "narration": "x", "_start": 0.0}
out_r = TMP / "react.mp4"
_render_scene(scene_r, proj_react, cfg_v, out_r, {"fin": False, "fout": False})
fr2 = frame_of(out_r, 12, "react.png")
# franja inferior: donde el video de reacción tenía VERDE debe verse el
# fondo amarillo del contenido; donde estaba la "persona" (magenta), magenta.
band_y = H - int(H * 0.44) + 40           # dentro de la franja de reacción
edge = fr2.getpixel((80, band_y + 200))   # borde: era verde → ahora amarillo
center = fr2.getpixel((W // 2, H - 200))  # centro-bajo: la persona magenta
check("donde había VERDE se ve el contenido (amarillo)",
      edge[0] > 170 and edge[1] > 140 and edge[2] < 130, str(edge))
check("la persona (magenta) permanece compuesta",
      center[0] > 130 and center[2] > 100 and center[1] < 110, str(center))
green_left = sum(1 for y in range(band_y, H, 10) for x in range(0, W, 10)
                 if (lambda p: p[1] > 110 and p[1] > p[0] * 1.3
                     and p[1] > p[2] * 1.3)(fr2.getpixel((x, y))))
check("no queda verde chroma visible", green_left < 30, str(green_left))

print("T4 burbuja circular real (reacción sin pantalla verde)")
proj_bub = _Proj(TMP / "proj3",
                 {"reaction": {"file": "01_react.mp4", "chroma": False}})
make_video(proj_bub.path("input", "01_react.mp4"), "magenta", seconds=3)
Image.new("RGB", (1080, 1920), (240, 210, 60)).save(
    proj_bub.path("broll", "scene_002.jpg"))
out_b = TMP / "bubble.mp4"
_render_scene(dict(scene_r, id=2), proj_bub, cfg_v, out_b,
              {"fin": False, "fout": False})
fr3 = frame_of(out_b, 12, "bubble.png")
d = int(min(W, H) * 0.30)
margin = int(min(W, H) * 0.04)
cx = margin + d // 2
cy = H - (margin + int(H * 0.09)) - d // 2
inside = fr3.getpixel((cx, cy))                      # centro del círculo
corner = fr3.getpixel((margin + 6, cy - d // 2 + 6))  # esquina del cuadrado
check("el centro de la burbuja muestra la reacción (magenta)",
      inside[0] > 150 and inside[2] > 150 and inside[1] < 120, str(inside))
check("fuera del círculo (esquina del cuadrado) se ve el fondo — es circular",
      corner[0] > 170 and corner[1] > 140 and corner[2] < 130, str(corner))

print("T5 sincronía del tramo de reacción (video-reloj)")
proj_clk = _Proj(TMP / "proj4",
                 {"reaction": {"file": "01_clock.mp4", "chroma": False}})
make_video(proj_clk.path("input", "01_clock.mp4"), "", overlay_clock=True)
Image.new("RGB", (1080, 1920), (240, 210, 60)).save(
    proj_clk.path("broll", "scene_002.jpg"))
out_c = TMP / "clock.mp4"
# escena que empieza en t=1.2 del video: la burbuja debe mostrar el color
# del SEGUNDO tramo del reloj (verde), no el primero (rojo)
_render_scene(dict(scene_r, id=2, _start=1.2), proj_clk, cfg_v, out_c,
              {"fin": False, "fout": False})
fr4 = frame_of(out_c, 6, "clock.png")
clk = fr4.getpixel((cx, cy))
check("la escena que empieza en t=1.2 muestra el tramo VERDE del reloj "
      "(no el rojo del inicio)", clk[1] > 130 and clk[0] < 110, str(clk))

print("T6 escenas: normalización de la pantalla dividida")
from ytstudio.phases.scenes import _normalize_creative

sc = [{"id": 1, "narration": "antes y después", "broll_type": "image",
       "animation": "zoom_in", "layout": "dividida",
       "broll_prompt_b": "the after state, same style"}]
_normalize_creative(sc, short_form=True)
check("dividida válida en formato corto (con prompt B)",
      sc[0]["layout"] == "dividida" and sc[0].get("broll_prompt_b"))
sc2 = [{"id": 1, "narration": "x", "broll_type": "image",
        "animation": "zoom_in", "layout": "dividida", "broll_prompt_b": ""}]
_normalize_creative(sc2, short_form=True)
check("dividida sin prompt B → completo", sc2[0]["layout"] == "completo")
sc3 = [{"id": 1, "narration": "x", "broll_type": "image",
        "animation": "zoom_in", "layout": "dividida",
        "broll_prompt_b": "algo"}]
_normalize_creative(sc3, short_form=False)
check("en 16:9 largo se fuerza completo (v1)", sc3[0]["layout"] == "completo")

print("T7 personaje en burbuja (pip) vs modo clásico")
from ytstudio.phases import broll as broll_phase


class _PipProj(_Proj):
    def __init__(self, root, pip):
        super().__init__(root, {"character": {"presence": 0.3, "pip": pip},
                                "characters": [{"id": 1, "name": "Ana",
                                                "narrator": True,
                                                "asset_ids": [1]}],
                                "assets": [{"id": 1, "file": "01_ana.jpg",
                                            "name": "ana.jpg",
                                            "category": "personaje",
                                            "kind": "image"}]})
        self.warnings = []
        Image.new("RGB", (400, 600), (120, 90, 70)).save(
            self.path("input", "01_ana.jpg"))

    def add_warning(self, m):
        self.warnings.append(m)

    def set(self, k, v):
        self.data[k] = v


class _FakeLipsync:
    model = "cjwbw/sadtalker"

    def __init__(self, fail=False):
        self.fail = fail

    def generate(self, image, audio, out, seconds):
        if self.fail:
            raise RuntimeError("cuota agotada (simulado)")
        make_video(out, "white", seconds=1, size="320x320")
        return out


def run_char(pip, fail=False):
    p = _PipProj(TMP / f"pipproj_{pip}_{fail}", pip)
    vo = p.path("voiceover", "vo_001.mp3")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    str(vo)], check=True)
    scenes = [{"id": 1, "shot": "personaje", "duration": 2.0,
               "narration": "hola", "broll_prompt": "a road",
               "broll_type": "image", "animation": "zoom_in"}]
    orig = broll_phase.get_lipsync if hasattr(broll_phase, "get_lipsync") else None
    import ytstudio.providers as prov
    orig_get = prov.get_lipsync
    prov.get_lipsync = lambda cfg: _FakeLipsync(fail)
    try:
        ids = broll_phase._generate_character_scenes(
            p, scenes, p.path("broll"), {"providers": {"lipsync": {}},
                                         "performance": {}})
    finally:
        prov.get_lipsync = orig_get
    return p, scenes, ids


p_pip, sc_pip, ids_pip = run_char(pip=True)
check("pip: la escena lleva pip_video y NO broll_video de lipsync",
      sc_pip[0].get("pip_video") and not sc_pip[0].get("broll_video")
      and sc_pip[0].get("broll_source") != "lipsync",
      str({k: sc_pip[0].get(k) for k in ("pip_video", "broll_video",
                                         "broll_source")}))
check("pip: devuelve set() — la escena sigue generando su B-roll de fondo",
      ids_pip == set())
p_cls, sc_cls, ids_cls = run_char(pip=False)
check("clásico: sin cambios (broll_video lipsync + escena resuelta)",
      sc_cls[0].get("broll_video") and ids_cls == {1})
p_f, sc_f, _ = run_char(pip=True, fail=True)
check("pip con lipsync caído: sin burbuja, solo aviso (no pantalla completa)",
      not sc_f[0].get("pip_video") and sc_f[0].get("broll_source") != "lipsync"
      and any("burbuja" in w for w in p_f.warnings), str(p_f.warnings))

# render real del pip: burbuja blanca sobre B-roll amarillo
proj_pip = _Proj(TMP / "proj5")
Image.new("RGB", (1080, 1920), (240, 210, 60)).save(
    proj_pip.path("broll", "scene_002.jpg"))
make_video(proj_pip.path("broll", "lipsync_002.mp4"), "white", seconds=3,
           size="320x320")
out_p = TMP / "pip.mp4"
_render_scene({"id": 2, "duration": 2.0, "animation": "static",
               "broll_image": "scene_002.jpg", "pip_video": "lipsync_002.mp4",
               "narration": "x"}, proj_pip, cfg_v, out_p,
              {"fin": False, "fout": False})
fr5 = frame_of(out_p, 12, "pip.png")
d = int(min(W, H) * 0.34)
cx5 = int(min(W, H) * 0.04) + d // 2
cy5 = H - (int(min(W, H) * 0.04) + int(H * 0.09)) - d // 2
pipc = fr5.getpixel((cx5, cy5))
check("render pip: la burbuja del personaje (blanca) está compuesta",
      min(pipc) > 180, str(pipc))

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
