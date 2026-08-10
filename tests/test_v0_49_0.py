"""Batería v0.49.0 — BANCO DE ELEMENTOS gestionable, insertos en VIDEO e
ilustración IA de respaldo (Fase 3 de las 4).

Hasta v0.48 el banco existía pero solo se alimentaba copiando archivos a mano
en carpetas, aceptaba únicamente imágenes, y una entidad sin foto de licencia
libre se quedaba sin inserto.

Verifica:
1. API del banco: inventario, alta (con validación de formato) y baja, sin
   salirse nunca de assets/elements (ruta encerrada).
2. La búsqueda encuentra también CLIPS de video y respeta la prioridad del
   material propio.
3. Un clip del banco se copia al proyecto y el montaje lo compone enmarcado,
   en bucle y con fundidos (verificado con un render REAL de ffmpeg).
4. La ilustración IA es el ÚLTIMO recurso, viene APAGADA y respeta su tope.
5. El servidor sirve los archivos del banco para la vista previa y la
   interfaz tiene los controles.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import base64
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


TMP = Path(tempfile.mkdtemp(prefix="v0490_"))

from PIL import Image

from ytstudio.utils import elements as elib

# El banco se redirige a una carpeta temporal: la batería NUNCA toca el banco
# real del creador.
_real_bank = elib.BANK_DIR
elib.BANK_DIR = TMP / "banco"


def png_bytes(color=(120, 40, 40)) -> bytes:
    import io
    buf = io.BytesIO()
    Image.new("RGB", (240, 180), color).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# T1 — API del banco: inventario, alta y baja
# ---------------------------------------------------------------------------
inv = elib.bank_list()
check("T1 el inventario trae las 5 categorías, vacías al principio",
      set(inv) == set(elib.CATEGORIES) and all(not v for v in inv.values()),
      str({k: len(v) for k, v in inv.items()}))

it = elib.bank_add("personajes", "Elon Musk.png", png_bytes())
check("T1b se puede añadir un elemento y queda catalogado",
      it["etiqueta"] == "Elon Musk" and it["kind"] == "image"
      and (elib.BANK_DIR / "personajes" / "Elon Musk.png").exists(), str(it))
check("T1c el inventario lo refleja",
      len(elib.bank_list()["personajes"]) == 1, "")

for mal, motivo in [("virus.exe", "formato"), ("doc.pdf", "formato")]:
    try:
        elib.bank_add("personajes", mal, b"x")
        check(f"T1d se rechaza «{mal}»", False, "no lanzó")
    except ValueError as e:
        check(f"T1d se rechaza «{mal}» con un mensaje claro",
              "admitido" in str(e) or "Formato" in str(e), str(e))
try:
    elib.bank_add("inventada", "a.png", png_bytes())
    check("T1e se rechaza una categoría inexistente", False, "no lanzó")
except ValueError as e:
    check("T1e se rechaza una categoría inexistente", "Categoría" in str(e),
          str(e))
try:
    elib.bank_add("personajes", "vacio.png", b"")
    check("T1f se rechaza un archivo vacío", False, "no lanzó")
except ValueError as e:
    check("T1f se rechaza un archivo vacío", "vacío" in str(e), str(e))

check("T1g se puede quitar del banco",
      elib.bank_delete("personajes", "Elon Musk.png")
      and not elib.bank_list()["personajes"], "")
check("T1h quitar algo que no existe no revienta",
      elib.bank_delete("personajes", "fantasma.png") is False, "")
# intento de fuga de ruta
elib.bank_add("personajes", "Elon Musk.png", png_bytes())
check("T1i un nombre con ruta no escapa de la carpeta del banco",
      elib.bank_delete("personajes", "../../secreto.png") is False
      and (elib.BANK_DIR / "personajes" / "Elon Musk.png").exists(), "")

# ---------------------------------------------------------------------------
# T2 — búsqueda: clips de video y prioridad del material propio
# ---------------------------------------------------------------------------
clip = elib.BANK_DIR / "lugares" / "El Cairo.mp4"
clip.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=size=320x240:rate=12:duration=2",
                "-pix_fmt", "yuv420p", str(clip)],
               check=True, capture_output=True)
hit = elib.bank_lookup("El Cairo")
check("T2 la búsqueda encuentra CLIPS de video del banco",
      hit is not None and hit.suffix == ".mp4" and elib.is_video(hit), str(hit))
check("T2b y sigue encontrando imágenes con tildes/mayúsculas",
      (elib.bank_lookup("elon musk") or Path("x")).name == "Elon Musk.png", "")
check("T2c una entidad que no está devuelve None",
      elib.bank_lookup("Rockefeller") is None, "")

# ---------------------------------------------------------------------------
# T3 — el clip se copia al proyecto y el montaje lo compone
# ---------------------------------------------------------------------------
from ytstudio.phases import broll as broll_phase


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
                 "elements_web": False, "elements_ai": False,
                 "overlay_accent": "E8C46B"},
       "audio": {}}
escenas = [{"id": 1, "duration": 8.0, "animation": "static",
            "narration": "El oro llegó a El Cairo.",
            "elements": [{"tipo": "lugar", "consulta": "El Cairo",
                          "etiqueta": "El Cairo", "momento": "El Cairo"}]}]
proj = PStub()
broll_phase._resolve_elements(proj, cfg, escenas, proj.path("broll"))
el = escenas[0]["elements"][0]
check("T3 el clip del banco se copia al proyecto como inserto de video",
      el.get("mode") == "video"
      and (proj.path("broll", "elements") / el["files"][0]).exists(), str(el))

from ytstudio.phases.assembly import _element_setup, _render_scene

el["at"] = 2.0
args, chain, pos = _element_setup(escenas[0], 8.0, cfg, proj)
check("T3b el montaje lo pone en bucle, enmarcado y con fundidos",
      "-stream_loop" in args and "pad=" in chain and "fade=t=in" in chain
      and "between(t,2.00" in pos, f"{args} | {chain}")

Image.new("RGB", (640, 360), (128, 128, 128)).save(
    proj.path("broll", "scene_001.jpg"))
esc_r = {**escenas[0], "broll_image": "scene_001.jpg", "duration": 5.0}
esc_r["elements"][0]["at"] = 1.5
out_mp4 = TMP / "esc_video.mp4"
try:
    _render_scene(esc_r, proj, cfg, out_mp4, fade={})
    ok = out_mp4.exists() and out_mp4.stat().st_size > 0
except Exception as e:
    ok = False
    print("   render:", e)
check("T3c la escena con inserto de VIDEO renderiza con ffmpeg", ok, "")
if ok:
    def variedad(t):
        f = TMP / f"fr{t}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(out_mp4),
                        "-frames:v", "1", str(f)], capture_output=True)
        im = Image.open(f).convert("RGB")
        return len(set(im.getdata()))
    antes, durante = variedad(0.5), variedad(3.0)
    # Comparación RELATIVA: el fondo «plano» no da 1 color exacto — según la
    # versión de ffmpeg, la compresión deja un puñado de tonos casi idénticos
    # (4 en el equipo del creador, 1-2 en otros). Lo que demuestra el inserto
    # es el SALTO de variedad, no un umbral absoluto.
    check("T3d el inserto de video SE VE tras la mención (el cuadro deja de "
          "ser plano)", durante > max(20, antes * 5),
          f"colores antes={antes} durante={durante}")

# ---------------------------------------------------------------------------
# T4 — la ilustración IA: último recurso, apagada por defecto, con tope
# ---------------------------------------------------------------------------
class FakeImages:
    is_mock = False

    def __init__(self):
        self.n = 0

    def generate(self, prompt, out: Path):
        self.n += 1
        Image.new("RGB", (200, 200), (30, 60, 90)).save(out)
        return out


def escena_sin_fuente(n=1):
    return [{"id": i, "duration": 8.0,
             "narration": "Nadie sabe quién fue.",
             "elements": [{"tipo": "persona", "consulta": f"Desconocido {i}",
                           "etiqueta": f"Desconocido {i}",
                           "momento": "Nadie"}]} for i in range(1, n + 1)]


p_off = PStub("proj_off")
img_off = FakeImages()
esc_off = escena_sin_fuente()
broll_phase._resolve_elements(p_off, cfg, esc_off, p_off.path("broll"),
                              images=img_off)
check("T4 con elements_ai apagado NO se gasta en ilustrar",
      img_off.n == 0 and not esc_off[0].get("elements"), str(img_off.n))
check("T4b y el aviso explica cómo cubrirlo (banco o activar la IA)",
      p_off.avisos and "Banco de elementos" in p_off.avisos[0]
      and "elements_ai" in p_off.avisos[0], str(p_off.avisos))

cfg_ai = {**cfg, "video": {**cfg["video"], "elements_ai": True,
                           "elements_ai_max": 2}}
p_on = PStub("proj_on")
img_on = FakeImages()
esc_on = escena_sin_fuente(5)
broll_phase._resolve_elements(p_on, cfg_ai, esc_on, p_on.path("broll"),
                              images=img_on)
check("T4c encendida, ilustra solo hasta el tope (2 de 5)", img_on.n == 2,
      str(img_on.n))
con_inserto = [s for s in esc_on if s.get("elements")]
check("T4d las ilustradas quedan como tarjeta y el resto se descarta",
      len(con_inserto) == 2
      and all(e["mode"] == "photo" for s in con_inserto
              for e in s["elements"]), str(len(con_inserto)))
check("T4e el prompt de la ilustración prohíbe texto en la imagen",
      "no text" in inspect.getsource(broll_phase._resolve_elements), "")

p_mock = PStub("proj_mock")


class MockImgs:
    is_mock = True

    def generate(self, *a, **k):
        raise AssertionError("no debe llamarse en modo vista previa")


esc_mock = escena_sin_fuente()
broll_phase._resolve_elements(p_mock, cfg_ai, esc_mock, p_mock.path("broll"),
                              images=MockImgs())
check("T4f en modo vista previa nunca se ilustra (no hay gasto simulado)",
      not esc_mock[0].get("elements"), "")

# ---------------------------------------------------------------------------
# T5 — servidor e interfaz
# ---------------------------------------------------------------------------
from ytstudio.webui import server as srv

lst = srv.api_elements_list()
check("T5 el endpoint de inventario responde con categorías e ítems",
      set(lst["categories"]) == set(elib.CATEGORIES)
      and "personajes" in lst["items"], str(list(lst)))
added = srv.api_elements_add({"category": "entidades",
                              "file": {"name": "UNESCO.png",
                                       "data_base64": base64.b64encode(
                                           png_bytes()).decode()}})
check("T5b el endpoint de alta guarda el archivo",
      added["ok"] and (elib.BANK_DIR / "entidades" / "UNESCO.png").exists(), "")
check("T5c el de baja lo quita",
      srv.api_elements_delete("entidades", "UNESCO.png")["ok"], "")
try:
    srv.api_elements_add({"category": "entidades", "file": {}})
    check("T5d sin archivo, error claro (no 500)", False, "no lanzó")
except srv.ApiError as e:
    check("T5d sin archivo, error claro (no 500)", e.status == 400, str(e))

ssrc = inspect.getsource(srv)
check("T5e las rutas del banco están registradas (GET/POST/DELETE + archivos)",
      '"/api/elements"' in ssrc and "/elements/([\\w-]+)/(.+)" in ssrc
      and "_element_file" in ssrc, "")
check("T5f la vista previa encierra la ruta dentro del banco",
      "startswith(str(base))" in inspect.getsource(srv.Handler._element_file),
      "")

html = (ROOT / "ytstudio" / "webui" / "static" / "index.html").read_text(
    encoding="utf-8")
check("T5g la Biblioteca tiene el banco con subida, borrado y vista previa",
      "Banco de elementos" in html and "bankUpload" in html
      and "bankDelete" in html and "/elements/" in html, "")
check("T5h y los clips se previsualizan como video",
      "<video src=\"/elements/" in html, "")

elib.BANK_DIR = _real_bank

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.49.0 completa: banco gestionable desde la interfaz, "
      "insertos en video e ilustración IA acotada y opcional.")
shutil.rmtree(TMP, ignore_errors=True)
