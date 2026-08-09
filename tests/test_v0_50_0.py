"""Batería v0.50.0 — MAPAS localizadores animados (Fase 4 de las 4).

Cuando la narración sitúa la historia («cruzó el Sahara», «llegó a El Cairo»),
aparece un mapa con el pin cayendo sobre el punto exacto. La cartografía es de
OpenStreetMap (licencia libre, crédito automático) y, si no hay internet, una
ficha de coordenadas generada en local — que nunca falla.

Verifica:
1. La proyección Web Mercator es correcta (puntos de referencia conocidos).
2. Las teselas se unen y se recortan centradas en el punto; una tesela caída
   no rompe el mapa; si NINGUNA llega, se devuelve None (y entra el respaldo).
3. La animación: 14 cuadros, el pin cae y el anillo se expande.
4. El respaldo local pone el pin en su posición geográfica relativa correcta.
5. Integración: el tipo 'mapa' resuelve coordenadas, guarda la secuencia y
   añade el crédito de OpenStreetMap; tu archivo propio tiene prioridad; sin
   coordenadas, aviso honesto.
6. El montaje reproduce la secuencia (render REAL con ffmpeg).
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
import shutil
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0500_"))

from PIL import Image

from ytstudio.utils import maps

ACCENT = "E8C46B"
AC = (232, 196, 107)
CAIRO = (30.05, 31.25)

# ---------------------------------------------------------------------------
# T1 — la proyección Web Mercator (si esto falla, el pin miente)
# ---------------------------------------------------------------------------
check("T1 el punto (0,0) cae en el centro del mundo",
      maps.tile_xy(0, 0, 1) == (1.0, 1.0), str(maps.tile_xy(0, 0, 1)))
x, y = maps.tile_xy(51.5, -0.13, 0)      # Londres, mundo entero
check("T1b Londres cae al oeste del meridiano y en el hemisferio norte",
      0.49 < x < 0.51 and 0.32 < y < 0.35, f"{x:.3f},{y:.3f}")
xs, ys = maps.tile_xy(-33.45, -70.66, 0)  # Santiago de Chile
check("T1c Santiago cae al oeste y en el hemisferio sur",
      xs < 0.35 and ys > 0.55, f"{xs:.3f},{ys:.3f}")
check("T1d el zoom multiplica la rejilla (z=5 → 32 teselas por lado)",
      abs(maps.tile_xy(0, 180, 5)[0] - 32.0) < 0.01,
      str(maps.tile_xy(0, 180, 5)))
check("T1e las latitudes imposibles se acotan (no revienta en los polos)",
      0 <= maps.tile_xy(95, 0, 3)[1] <= 8
      and 0 <= maps.tile_xy(-95, 0, 3)[1] <= 8,
      f"{maps.tile_xy(95, 0, 3)} {maps.tile_xy(-95, 0, 3)}")

# ---------------------------------------------------------------------------
# T2 — unión de teselas (servidor simulado: aquí no hay internet)
# ---------------------------------------------------------------------------
PEDIDAS = []


def fake_tile(z, x, y, timeout=12):
    PEDIDAS.append((z, x, y))
    # cada tesela con un color propio, para ver que se pegan en su sitio
    return Image.new("RGB", (maps.TILE_PX, maps.TILE_PX),
                     ((x * 37) % 255, (y * 53) % 255, 120))


_real_fetch = maps._fetch_tile
maps._fetch_tile = fake_tile
PEDIDAS.clear()
img = maps.fetch_map(*CAIRO, 5, 420, 260)
check("T2 el mapa se arma con el tamaño exacto pedido",
      img is not None and img.size == (420, 260), str(img and img.size))
check("T2b se descargan solo las teselas necesarias (rejilla acotada)",
      4 <= len(PEDIDAS) <= 20, f"{len(PEDIDAS)} teselas")
check("T2c todas del nivel de zoom pedido",
      all(z == 5 for z, _, _ in PEDIDAS), "")


def flaky_tile(z, x, y, timeout=12):
    if (x + y) % 3 == 0:
        raise OSError("tesela caída")
    return fake_tile(z, x, y)


maps._fetch_tile = flaky_tile
img2 = maps.fetch_map(*CAIRO, 5, 420, 260)
check("T2d si algunas teselas fallan, el mapa se arma igual",
      img2 is not None and img2.size == (420, 260), str(img2 and img2.size))

maps._fetch_tile = lambda *a, **k: (_ for _ in ()).throw(OSError("sin red"))
check("T2e si NINGUNA tesela llega, se devuelve None (entra el respaldo)",
      maps.fetch_map(*CAIRO, 5, 420, 260) is None, "")

# ---------------------------------------------------------------------------
# T3 — la animación con mapa real (simulado)
# ---------------------------------------------------------------------------
maps._fetch_tile = fake_tile
res = maps.render_map_frames("El Cairo", *CAIRO, TMP / "cairo_web",
                             card_w=420, accent=ACCENT, zoom=5,
                             allow_web=True)
check("T3 con cartografía disponible, el localizador es REAL",
      res["real"] is True and len(res["files"]) == maps.FRAMES,
      f"real={res['real']} n={len(res['files'])}")
frames = [Image.open(TMP / "cairo_web" / f).convert("RGBA")
          for f in res["files"]]


def acento_px(im, solo_mapa=True):
    w, h = im.size
    lim = int(h * 0.62) if solo_mapa else h
    n = 0
    for yy in range(0, lim, 2):
        for xx in range(0, w, 2):
            p = im.getpixel((xx, yy))
            if p[3] > 120 and abs(p[0] - AC[0]) < 40 and \
                    abs(p[1] - AC[1]) < 40 and abs(p[2] - AC[2]) < 45:
                n += 1
    return n


check("T3b el pin del color de acento está dibujado en el mapa",
      acento_px(frames[-1]) > 20, str(acento_px(frames[-1])))
check("T3c la secuencia ANIMA (el primer cuadro difiere del último)",
      list(frames[0].getdata()) != list(frames[-1].getdata()), "")
serie = [acento_px(f) for f in frames]
check("T3d la cantidad de acento CAMBIA cuadro a cuadro (pin cayendo + "
      "anillo), no es una imagen fija repetida",
      max(serie) - min(serie) > 20, str(serie))
# lo que de verdad importa: el pin acaba CLAVADO en el punto (centro del mapa
# real, que se recortó centrado en las coordenadas pedidas)
ult = frames[-1]
wf, hf = ult.size
pts = [(xx, yy) for yy in range(0, int(hf * 0.62), 2)
       for xx in range(0, wf, 2)
       if (lambda p: p[3] > 120 and abs(p[0] - AC[0]) < 40
           and abs(p[1] - AC[1]) < 40 and abs(p[2] - AC[2]) < 45)(
               ult.getpixel((xx, yy)))]
cxr = sum(p[0] for p in pts) / len(pts) / wf if pts else -1
check("T3e y en el último cuadro el pin está sobre el punto (centro del "
      "recorte, ±8%)", 0.42 < cxr < 0.58, f"cx={cxr:.2f}")

# ---------------------------------------------------------------------------
# T4 — respaldo local: el pin en su posición geográfica relativa
# ---------------------------------------------------------------------------
loc = maps.render_map_frames("El Cairo", *CAIRO, TMP / "cairo_local",
                             card_w=420, accent=ACCENT, allow_web=False)
check("T4 sin internet hay localizador igualmente (y se declara no-real)",
      loc["real"] is False and len(loc["files"]) == maps.FRAMES, str(loc["real"]))
im = Image.open(TMP / "cairo_local" / loc["files"][-1]).convert("RGBA")
w, h = im.size
puntos = [(xx, yy) for yy in range(0, int(h * 0.62), 2)
          for xx in range(0, w, 2)
          if (lambda p: p[3] > 120 and abs(p[0] - AC[0]) < 40
              and abs(p[1] - AC[1]) < 40 and abs(p[2] - AC[2]) < 45)(
                  im.getpixel((xx, yy)))]
check("T4b el pin se dibuja", len(puntos) > 15, str(len(puntos)))
if puntos:
    cx = sum(p[0] for p in puntos) / len(puntos) / w
    cy = sum(p[1] for p in puntos) / len(puntos) / h
    # El Cairo: 31.25°E → x≈0.587 del ancho · 30.05°N → y≈0.333 de 180°
    check("T4c y cae en su longitud relativa correcta (≈0.59 del ancho)",
          0.52 < cx < 0.66, f"cx={cx:.2f}")
    check("T4d y en su latitud relativa correcta (hemisferio norte)",
          0.10 < cy < 0.45, f"cy={cy:.2f}")
santiago = maps.render_map_frames("Santiago", -33.45, -70.66,
                                  TMP / "scl", card_w=420, accent=ACCENT,
                                  allow_web=False)
im_s = Image.open(TMP / "scl" / santiago["files"][-1]).convert("RGBA")
pts_s = [(xx, yy) for yy in range(0, int(im_s.size[1] * 0.62), 2)
         for xx in range(0, im_s.size[0], 2)
         if (lambda p: p[3] > 120 and abs(p[0] - AC[0]) < 40
             and abs(p[1] - AC[1]) < 40 and abs(p[2] - AC[2]) < 45)(
                 im_s.getpixel((xx, yy)))]
if pts_s and puntos:
    cxs = sum(p[0] for p in pts_s) / len(pts_s) / im_s.size[0]
    check("T4e un lugar del hemisferio oeste cae a la IZQUIERDA de El Cairo",
          cxs < cx, f"{cxs:.2f} vs {cx:.2f}")

# ---------------------------------------------------------------------------
# T5 — integración en la fase B-roll
# ---------------------------------------------------------------------------
from ytstudio.phases import broll as broll_phase
from ytstudio.utils import elements as elib


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


cfg = {"language": "es",
       "video": {"width": 640, "height": 360, "fps": 12, "elements": True,
                 "elements_web": True, "elements_ai": False,
                 "elements_map_zoom": 5, "overlay_accent": ACCENT},
       "audio": {}}
_real_geo = elib.geo_lookup
elib.geo_lookup = lambda q, lang="es": CAIRO if "cairo" in q.lower() else None

_real_bank = elib.BANK_DIR
elib.BANK_DIR = TMP / "banco_vacio"


def escena_mapa(consulta="El Cairo"):
    return [{"id": 7, "duration": 8.0, "animation": "static",
             "narration": "El oro llegó a El Cairo.",
             "elements": [{"tipo": "mapa", "consulta": consulta,
                           "etiqueta": consulta, "momento": "El Cairo"}]}]


proj = PStub()
esc = escena_mapa()
broll_phase._resolve_elements(proj, cfg, esc, proj.path("broll"))
el = esc[0]["elements"][0]
check("T5 el tipo 'mapa' produce la secuencia animada del localizador",
      el.get("mode") == "stat" and len(el.get("files", [])) == maps.FRAMES,
      str(el.get("mode")) + " " + str(len(el.get("files", []))))
check("T5b los cuadros quedan en el proyecto",
      all((proj.path("broll", "elements") / f).exists() for f in el["files"]),
      "")
check("T5c y el crédito de OpenStreetMap se registra para la descripción",
      any("OpenStreetMap" in c for c in (proj.get("element_credits") or [])),
      str(proj.get("element_credits")))

# tu archivo propio manda sobre la cartografía
elib.BANK_DIR = TMP / "banco"
(elib.BANK_DIR / "mapas").mkdir(parents=True, exist_ok=True)
Image.new("RGB", (300, 200), (20, 90, 30)).save(
    elib.BANK_DIR / "mapas" / "El Cairo.png")
p2 = PStub("proj2")
esc2 = escena_mapa()
broll_phase._resolve_elements(p2, cfg, esc2, p2.path("broll"))
check("T5d un mapa propio del banco tiene prioridad sobre OpenStreetMap",
      esc2[0]["elements"][0].get("mode") == "photo",
      str(esc2[0]["elements"][0].get("mode")))
elib.BANK_DIR = TMP / "banco_vacio"

p3 = PStub("proj3")
esc3 = escena_mapa("Lugar Inexistente")
broll_phase._resolve_elements(p3, cfg, esc3, p3.path("broll"))
check("T5e sin coordenadas: sin inserto y aviso honesto (nada inventado)",
      not esc3[0].get("elements") and p3.avisos
      and "mapa" in p3.avisos[0], str(p3.avisos))

cfg_off = {**cfg, "video": {**cfg["video"], "elements_web": False}}
p4 = PStub("proj4")
esc4 = escena_mapa()
broll_phase._resolve_elements(p4, cfg_off, esc4, p4.path("broll"))
check("T5f con elements_web=false no se consulta la red para mapas",
      not esc4[0].get("elements"), str(esc4[0].get("elements")))

# ---------------------------------------------------------------------------
# T6 — el montaje reproduce la secuencia (render real)
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import _element_setup, _render_scene

el["at"] = 1.5
args, chain, pos = _element_setup(esc[0], 8.0, cfg, proj)
check("T6 el montaje reproduce la secuencia como animación",
      "-framerate" in args and "f_%02d.png" in " ".join(args)
      and "eof_action=repeat" in pos, f"{args} | {pos}")

Image.new("RGB", (640, 360), (128, 128, 128)).save(
    proj.path("broll", "scene_001.jpg"))
esc_r = {**esc[0], "broll_image": "scene_001.jpg", "duration": 5.0}
esc_r["elements"][0]["at"] = 1.5
out_mp4 = TMP / "mapa.mp4"
try:
    _render_scene(esc_r, proj, cfg, out_mp4, fade={})
    ok = out_mp4.exists() and out_mp4.stat().st_size > 0
except Exception as e:
    ok = False
    print("   render:", e)
check("T6b la escena con el mapa renderiza con ffmpeg", ok, "")
if ok:
    def colores(t):
        f = TMP / f"fr{t}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(out_mp4),
                        "-frames:v", "1", str(f)], capture_output=True)
        return len(set(Image.open(f).convert("RGB").getdata()))
    check("T6c el mapa SE VE tras la mención y no antes",
          colores(0.5) <= 2 and colores(3.5) > 20,
          f"antes={colores(0.5)} después={colores(3.5)}")

check("T6d el director tiene el tipo 'mapa' en su catálogo",
      "'mapa'" in inspect.getsource(
          __import__("ytstudio.phases.scenes", fromlist=["x"])), "")

maps._fetch_tile = _real_fetch
elib.geo_lookup = _real_geo
elib.BANK_DIR = _real_bank

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.50.0 completa: mapas localizadores con pin animado, "
      "cartografía libre con crédito y respaldo local que nunca falla.")
shutil.rmtree(TMP, ignore_errors=True)
