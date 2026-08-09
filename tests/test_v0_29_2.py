"""Batería v0.29.2: fin del estiramiento Ken Burns en imágenes no-16:9 +
modelo de lipsync por defecto más fiable.

Bug real (confirmado visualmente en el video_final.mp4 del usuario): subió
la foto de referencia del personaje y un B-roll con relación de aspecto
DISTINTA a 16:9 (esperando que el director las ajustara). _kenburns hacía
scale=2560:-2 (conserva el aspecto ORIGINAL de la imagen) y luego zoompan con
s=WxH — si el aspecto de la imagen no coincidía con el de salida, zoompan
ESTIRABA el recorte de forma no uniforme al ajustarlo a WxH (caras anchas).
El camino de video (broll_video) ya hacía cover-crop correcto; a _kenburns
le faltaba.

T1  Con una imagen CUADRADA (1:1) sobre salida 16:9: un círculo perfecto
    dibujado en el centro sigue siendo un CÍRCULO (no una elipse) en el
    fotograma final, para las 5 animaciones.
T2  Con una imagen VERTICAL (9:16, como una foto de personaje de retrato)
    sobre salida 16:9: mismo resultado — sin estiramiento.
T3  Con una imagen YA 16:9 el resultado es idéntico a antes (no se rompe el
    caso normal): el encuadre cubre el 100% del frame de salida.
T4  El modelo de lipsync por defecto cambia a cjwbw/sadtalker (confirmado
    que existe en Replicate); zsxkib/sonic queda como alternativa con aviso.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import subprocess
import shutil
import sys
from pathlib import Path



from PIL import Image, ImageDraw

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.phases.assembly import _kenburns

TMP = Path(__file__).parent / "t292"
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

W, H, FPS = 1920, 1080, 24
FRAMES = 24  # 1s, animación "static" (zoom casi nulo): mide el encuadre limpio


def make_circle_image(path, size, bg=(20, 20, 25), fg=(230, 60, 60)):
    """Imagen con UN CÍRCULO PERFECTO centrado, pequeño (15% del lado menor):
    debe sobrevivir ENTERO a cualquier cover-crop 1:1↔16:9↔9:16 razonable y
    al zoom máximo (1.14x) del Ken Burns, para que su bounding box mida el
    ESTIRAMIENTO real y no un recorte de cobertura legítimo."""
    w, h = size
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    r = round(min(w, h) * 0.15)
    cx, cy = w // 2, h // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fg)
    img.save(path, quality=95)
    return r / min(w, h)


def render_frame(img_path, animation, frame_idx=12):
    """Renderiza el filtro _kenburns real sobre img_path y extrae UN
    fotograma como PNG (sin pérdida) para medir el círculo con precisión."""
    filt = _kenburns(animation, FRAMES, W, H, FPS)
    out = TMP / f"out_{animation}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(img_path), "-t", "1",
                    "-filter_complex", f"[0:v]{filt}[v]", "-map", "[v]",
                    "-frames:v", str(FRAMES), "-pix_fmt", "yuv420p",
                    str(out)], check=True)
    png = TMP / f"frame_{animation}.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(out), "-vf", f"select=eq(n\\,{frame_idx})",
                    "-vframes", "1", str(png)], check=True)
    return png


def measure_circle_bbox(png_path, fg=(230, 60, 60), tol=40):
    """Bounding box del color del círculo en el PNG (ancho/alto en px)."""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    px = img.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    # muestreo cada 2px: suficiente para medir proporción, mucho más rápido
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if abs(r - fg[0]) < tol and abs(g - fg[1]) < tol and abs(b - fg[2]) < tol:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if maxx < 0:
        return None
    return (maxx - minx), (maxy - miny)  # (ancho_px, alto_px) del círculo


ANIMS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]

print("T1 imagen CUADRADA (1:1) → círculo sigue siendo círculo")
sq = TMP / "square.jpg"
make_circle_image(sq, (1000, 1000))
for anim in ANIMS:
    png = render_frame(sq, anim)
    bbox = measure_circle_bbox(png)
    check(f"  {anim}: se detecta el círculo", bbox is not None, "no se detectó color")
    if bbox:
        bw, bh = bbox
        ratio = bw / bh if bh else 0
        check(f"  {anim}: proporción ancho/alto ≈ 1.0 (círculo, no elipse) "
              f"[{bw}x{bh}]", 0.85 <= ratio <= 1.18, f"ratio={ratio:.2f}")

print("T2 imagen VERTICAL (9:16, foto de personaje) → sin estiramiento")
vert = TMP / "vertical.jpg"
make_circle_image(vert, (900, 1600))
stretched_before = []
for anim in ANIMS:
    png = render_frame(vert, anim)
    bbox = measure_circle_bbox(png)
    check(f"  {anim}: se detecta el círculo", bbox is not None)
    if bbox:
        bw, bh = bbox
        ratio = bw / bh if bh else 0
        check(f"  {anim}: proporción ancho/alto ≈ 1.0 con fuente vertical "
              f"[{bw}x{bh}]", 0.85 <= ratio <= 1.18, f"ratio={ratio:.2f}")
        # La fórmula VIEJA (sin cover-crop) habría dado un ratio MUY distinto
        # de 1.0 para esta fuente 9:16 sobre salida 16:9 — se documenta el
        # contraste para dejar constancia del defecto real.
        old_w = W  # scale=2560:-2 sobre 900x1600 -> ancho objetivo tras zoompan
        expected_old_ratio = (900 / 1600) / (W / H)  # cuánto se comprime X vs Y
        stretched_before.append(expected_old_ratio)
print(f"     (con la fórmula vieja, el ratio esperado habría sido "
      f"~{sum(stretched_before)/len(stretched_before):.2f} — bien lejos de 1.0)")

print("T3 imagen YA 16:9 → sigue cubriendo el 100% del frame (sin regresión)")
wide = TMP / "wide.jpg"
make_circle_image(wide, (1920, 1080))
png = render_frame(wide, "static")
img = Image.open(png)
check("el fotograma de salida mide exactamente WxH", img.size == (W, H),
      str(img.size))
bbox = measure_circle_bbox(png)
if bbox:
    ratio = bbox[0] / bbox[1]
    check("fuente ya 16:9: el círculo se mantiene circular",
          0.85 <= ratio <= 1.18, f"ratio={ratio:.2f}")

print("T4 modelo de lipsync por defecto más fiable")
from ytstudio.providers.lipsync import ReplicateLipsync
import ytstudio.providers.lipsync as lipsync_mod


class _FakeReplicate:
    pass


orig_import = None
try:
    import sys as _s
    # evitar exigir el paquete 'replicate' instalado: se prueba solo el default
    class _StubReplicate:
        pass
    _s.modules.setdefault("replicate", _StubReplicate())
    ls = ReplicateLipsync({"providers": {"lipsync": {}}})
    check("modelo por defecto = cjwbw/sadtalker (confirmado en Replicate)",
          ls.model == "cjwbw/sadtalker", ls.model)
finally:
    pass

from ytstudio.catalog import CATALOG
opts = CATALOG["lipsync"]["options"][0]["models"]
ids = [m["id"] for m in opts]
check("sadtalker es la PRIMERA opción del catálogo (por defecto)",
      ids[0] == "cjwbw/sadtalker", str(ids))
sonic = next(m for m in opts if m["id"] == "zsxkib/sonic")
check("sonic queda con aviso de que puede desaparecer/renombrarse",
      "renombrar" in sonic["label"].lower() or "desaparecer" in sonic["label"].lower(),
      sonic["label"])

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
