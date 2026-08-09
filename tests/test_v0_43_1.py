"""Batería v0.43.1 — el 429 de gpt-image-1 que mató la fase B-roll.

Reproduce el escenario del log 36cc3989 (proyecto 3-mansa-musa):

  «B-roll generado con IA: Error code: 429 - Rate limit reached for
   gpt-image-1 … on input-images per min: Limit 5, Used 5, Requested 1.
   Please try again in 12s.»

…tras 8 imágenes ya generadas (y pagadas), con 13 minutos de silencio antes
del error.

Verifica:
1. Un 429 transitorio ya NO mata la fase: se espera lo que la propia API pide
   y se reintenta.
2. La espera sale del mensaje («try again in 12s»), no de un número inventado.
3. Si el límite no cede nunca, el error es accionable y las imágenes ya
   generadas se conservan.
4. Un error que NO es de límite (auth) sigue subiendo intacto y sin esperas.
5. El paralelismo se reduce con OpenAI (4 hilos contra 5 img/min = 429 seguro).
6. La ESTIMACIÓN usa el modelo REAL: con name=openai y un 'model' heredado de
   FLUX, el precio ya no es el de FLUX (era el error de dinero del log).
7. El gasto se registra por imagen y el tope de presupuesto se respeta.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import base64
import io
import time
import types

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


# ---------------------------------------------------------------------------
# Doble del SDK de OpenAI (misma superficie que usa ytstudio)
# ---------------------------------------------------------------------------

def _png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 40, 120)).save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode()


class FakeRateLimit(Exception):
    """Igual que el 429 real de OpenAI: status_code + mensaje con la espera."""

    def __init__(self, msg="Error code: 429 - {'error': {'message': 'Rate "
                           "limit reached for gpt-image-1 (for limit "
                           "gpt-image) on input-images per min: Limit 5, "
                           "Used 5, Requested 1. Please try again in 12s.', "
                           "'code': 'rate_limit_exceeded'}}"):
        super().__init__(msg)
        self.status_code = 429


class FakeImagesAPI:
    def __init__(self, fallos_429=0, siempre_429=False, otro_error=None):
        self.restantes = fallos_429
        self.siempre = siempre_429
        self.otro = otro_error
        self.llamadas = 0

    def generate(self, **kwargs):
        self.llamadas += 1
        if self.otro is not None:
            raise self.otro
        if self.siempre or self.restantes > 0:
            self.restantes -= 1
            raise FakeRateLimit()
        return types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json=_png_b64())])


def make_provider(**kw):
    """OpenAIImages con el SDK sustituido (sin __init__: no pide clave)."""
    from ytstudio.providers.images import OpenAIImages
    p = OpenAIImages.__new__(OpenAIImages)
    p.size = "1536x1024"
    api = FakeImagesAPI(**kw)
    p.client = types.SimpleNamespace(images=api)
    return p, api


# Las esperas reales harían la batería eterna: se sustituye time.sleep y se
# anota cuánto se habría esperado (que es justo lo que hay que verificar).
DORMIDO = []
_real_sleep = time.sleep
time.sleep = lambda s: DORMIDO.append(s)

from ytstudio import usage as usage_mod
from ytstudio.providers.images import OpenAIImages, _rate_limit_wait

import tempfile
TMP = Path(tempfile.mkdtemp(prefix="v0431_"))

# ---------------------------------------------------------------------------
# T1 — EL CASO DEL LOG: 429 transitorio → espera y reintento, sin morir
# ---------------------------------------------------------------------------
usage_mod.reset()
DORMIDO.clear()
prov, api = make_provider(fallos_429=2)
out = prov.generate("un mercado de Tombuctú con un cartel legible", TMP / "a.jpg")
check("T1 la imagen se genera pese a dos 429 seguidos",
      out.exists() and out.stat().st_size > 0, str(out))
check("T1b hubo 3 intentos (2 rechazados + 1 bueno)", api.llamadas == 3,
      str(api.llamadas))
check("T1c esperó lo que pidió la API (12s + margen), no un número inventado",
      len(DORMIDO) == 2 and all(13.0 <= d <= 15.0 for d in DORMIDO),
      str(DORMIDO))

# ---------------------------------------------------------------------------
# T2 — la espera se lee del mensaje; sin dato, crece de forma acotada
# ---------------------------------------------------------------------------
check("T2 «try again in 12s» → ~14s", 13.0 <= _rate_limit_wait(FakeRateLimit(), 1) <= 15.0,
      str(_rate_limit_wait(FakeRateLimit(), 1)))
sin_dato = FakeRateLimit("Error code: 429 - rate_limit_exceeded")
w1, w3 = _rate_limit_wait(sin_dato, 1), _rate_limit_wait(sin_dato, 3)
check("T2b sin dato en el mensaje, la espera crece", w3 > w1, f"{w1} → {w3}")
check("T2c la espera nunca se dispara (≤90s)",
      _rate_limit_wait(sin_dato, 99) <= 90.0, str(_rate_limit_wait(sin_dato, 99)))
ms = FakeRateLimit("429 rate limit. Please try again in 800ms.")
check("T2d entiende milisegundos", 2.0 <= _rate_limit_wait(ms, 1) <= 3.0,
      str(_rate_limit_wait(ms, 1)))

# ---------------------------------------------------------------------------
# T3 — si el límite NO cede: error accionable (y lo generado se conserva)
# ---------------------------------------------------------------------------
usage_mod.reset()
DORMIDO.clear()
prov, api = make_provider(siempre_429=True)
try:
    prov.generate("otra imagen", TMP / "b.jpg")
    check("T3 error tras agotar los reintentos", False, "no lanzó")
except RuntimeError as e:
    msg = str(e)
    check("T3 error tras agotar los reintentos", True)
    check("T3b el mensaje dice cómo seguir (reanudar / paralelismo / límite)",
          "Rehacer desde Imágenes" in msg and "parallel_images" in msg
          and "openai.com" in msg, msg[:200])
check("T3c se intentó el número previsto de veces",
      api.llamadas == OpenAIImages.RATE_RETRIES, str(api.llamadas))
check("T3d no se cobró nada por una imagen que nunca llegó",
      not usage_mod.get_state(), str(usage_mod.get_state()))

# ---------------------------------------------------------------------------
# T4 — un error que NO es de límite sube intacto y SIN esperas
# ---------------------------------------------------------------------------
DORMIDO.clear()
auth = Exception("Error code: 401 - invalid api key")
prov, api = make_provider(otro_error=auth)
try:
    prov.generate("x", TMP / "c.jpg")
    check("T4 el error de auth se propaga", False, "no lanzó")
except Exception as e:
    check("T4 el error de auth se propaga intacto", "401" in str(e), str(e))
check("T4b sin reintentos ni esperas ante un error que no es de límite",
      api.llamadas == 1 and not DORMIDO, f"{api.llamadas} {DORMIDO}")

# ---------------------------------------------------------------------------
# T5 — el gasto se anota por imagen y el tope de presupuesto se respeta
# ---------------------------------------------------------------------------
usage_mod.reset()
prov, api = make_provider()
prov.generate("y", TMP / "d.jpg")
items = usage_mod.get_state()
check("T5 la imagen generada queda en el reporte de gasto",
      len(items) == 1 and items[0]["provider"] == "openai", str(items))
usage_mod.reset()
usage_mod.set_cap(0.05)   # tope por debajo del costo de una imagen
prov, api = make_provider()
try:
    prov.generate("z", TMP / "e.jpg")
    check("T5b el tope de gasto frena antes de pedir la imagen", False, "no frenó")
except usage_mod.BudgetExceeded:
    check("T5b el tope de gasto frena antes de pedir la imagen",
          api.llamadas == 0, str(api.llamadas))
usage_mod.set_cap(0)

# ---------------------------------------------------------------------------
# T6 — paralelismo: con OpenAI se baja (4 hilos contra 5 img/min = 429 seguro)
# ---------------------------------------------------------------------------
import inspect

from ytstudio.phases import broll as broll_phase

src = inspect.getsource(broll_phase.run)
check("T6 la fase limita los hilos también con OpenAI",
      '_img_name == "openai"' in src and "img_workers = min(img_workers, 2)" in src,
      "")

# ---------------------------------------------------------------------------
# T7 — LA ESTIMACIÓN usa el modelo REAL (el error de dinero del log)
# ---------------------------------------------------------------------------
from ytstudio.pricing import effective_image_model, img_cost_range

check("T7 con OpenAI el modelo efectivo es gpt-image-1, no el heredado",
      effective_image_model("openai", "black-forest-labs/flux-1.1-pro")
      == "gpt-image-1", "")
c_mal = (0.04, 0.05)                                   # lo que se usaba antes
c_bien = img_cost_range("openai", "black-forest-labs/flux-1.1-pro")
check("T7b el precio ya no es el de FLUX", c_bien != c_mal, str(c_bien))
check("T7c 83 imágenes se estiman en su costo real (~$5.8-$20.8)",
      abs(83 * c_bien[0] - 5.81) < 0.1 and abs(83 * c_bien[1] - 20.75) < 0.1,
      f"${83*c_bien[0]:.2f}-${83*c_bien[1]:.2f}")
check("T7d Replicate sigue respetando el modelo que elijas",
      img_cost_range("replicate", "black-forest-labs/flux-schnell") == (0.003, 0.004),
      str(img_cost_range("replicate", "black-forest-labs/flux-schnell")))

# la estimación completa etiqueta y pagina con el modelo real
from ytstudio.estimate import estimate


class PStub:
    def __init__(self):
        self.data = {"scene_count": 83, "total_duration": 1080}
        self.dir = TMP

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        pass


cfg = {
    "language": "es",
    "video": {"width": 1920, "height": 1080, "target_minutes": 18,
              "scene_seconds": 11},
    "providers": {
        "llm": {"name": "anthropic", "model": "claude-opus-4-8"},
        # el caso REAL del creador: proveedor OpenAI con el model de FLUX
        "images": {"name": "openai", "model": "black-forest-labs/flux-1.1-pro"},
        "videogen": {"name": "none"}, "tts": {"name": "mock"},
        "stt": {"name": "openai"}, "music": {"name": "mock"},
    },
    "performance": {"parallel_images": 4},
    "audio": {}, "subtitles": {}, "publish": {},
}
# La estimación degrada a «vista previa» si no hay clave (correcto): para
# medir el costo REAL se simula que la clave existe, como en la máquina del
# creador.
_prev_key = os.environ.get("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = "sk-de-prueba-no-se-usa"
try:
    est = estimate(PStub(), cfg)
finally:
    if _prev_key is None:
        os.environ.pop("OPENAI_API_KEY", None)
    else:
        os.environ["OPENAI_API_KEY"] = _prev_key
img_items = [i for i in est["items"] if i["fase"].startswith("Imágenes IA")]
check("T8 la estimación nombra el modelo REAL en la etiqueta",
      bool(img_items) and "gpt-image-1" in img_items[0]["fase"],
      str([i["fase"] for i in est["items"]]))
check("T8b y con paralelismo 2, no 4",
      bool(img_items) and "2 en paralelo" in img_items[0]["detalle"],
      str(img_items[0]["detalle"]) if img_items else "")
# 'costo' es el par [mínimo, máximo] en dólares
_costo = img_items[0]["costo"] if img_items else [0, 0]
check("T8c el costo estimado ya no es el de FLUX (era $3.32-$4.15)",
      _costo[1] > 15.0 and _costo[0] > 5.0, f"${_costo[0]}-${_costo[1]}")

# ---------------------------------------------------------------------------
time.sleep = _real_sleep
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.43.1 completa: el límite de OpenAI ya no mata la fase y "
      "la estimación dice la verdad.")
import shutil
shutil.rmtree(TMP, ignore_errors=True)
