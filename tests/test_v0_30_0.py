"""Batería v0.30.0: debug de la corrida test-2-hetty (lipsync caído 12 min,
clips Kling con «'NoneType' object has no attribute 'read'», re-cobros) +
reencuadre inteligente del personaje.

Hallazgos del log real del usuario:
- v0.29.3 introdujo un bug: al REINTENTAR una llamada con archivos, los
  handles ya estaban leídos a EOF → el reintento subía archivos VACÍOS y el
  modelo fallaba en el servidor con errores crípticos (Kling: «'NoneType'
  object has no attribute 'read'»).
- Cada reintento RE-CREABA la predicción → re-cobra el modelo entero (omni-
  human) y multiplica el tiempo (12 min en el log).
- Los avisos de reintento de los hilos trabajadores no llegaban al log de la
  UI (canal thread-local): el usuario veía la fase «colgada» sin explicación.
- La imagen fija del personaje (fallback del lipsync) es un retrato: el
  recorte de cobertura centrado cortaba la cara (ojos fuera de cuadro).

T1  Reintento con archivos: el 2º intento sube el contenido COMPLETO (los
    handles se rebobinan), no archivos vacíos.
T2  Corte de red durante la espera: se REANUDA el sondeo de la MISMA
    predicción (predictions.get), sin re-crear (sin re-cobro).
T3  Si la reconexión se agota, NO se re-crea la predicción y el error final
    es claro y accionable.
T4  net_retries: lipsync y videogen caen rápido (3 intentos) porque tienen
    degradación por escena; imágenes insisten más (6) porque detienen la fase.
T5  Encuadre (ffmpeg REAL): un retrato 9:16 con el sujeto en el TERCIO
    SUPERIOR (donde el recorte centrado lo cortaba) se compone ENTERO sobre
    fondo desenfocado en la salida 16:9 — sujeto completo, redondo, y fondo
    lateral con contenido (no barras negras). Una fuente ya 16:9 o 4:3 sigue
    usando el recorte de cobertura de siempre.
T6  Reencuadre con IA del personaje: con modelo de identidad disponible se
    regenera la foto al formato del video (prompt de reencuadre + la foto
    como referencia); sin token devuelve None; con foto ya 16:9 ni lo intenta.
T7  Avisos de hilos trabajadores: get_sink + _bind_worker_logging llevan los
    mensajes de un worker real (threading) al log de la ejecución.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys
import threading
import time
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.providers.replicate_util import (
    replicate_call, set_progress, PersistentNetworkError,
)

notices = []
set_progress(lambda m: notices.append(m))

TMP = Path(__file__).parent / "t300"
TMP.mkdir(exist_ok=True)


class _NoVersion:
    """models.get falla → replicate_call usa client.run (camino sin versión)."""
    def get(self, model):
        raise Exception("sin versión")


print("T1 reintento con archivos: el 2º intento sube contenido COMPLETO")
imgf = TMP / "img.bin"
audf = TMP / "aud.bin"
imgf.write_bytes(b"I" * 5000)
audf.write_bytes(b"A" * 3000)


class _RewindClient:
    def __init__(self):
        self.calls = 0
        self.read_sizes = []
        self.models = _NoVersion()

    def run(self, model, input=None):
        self.calls += 1
        total = 0
        for v in input.values():
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if hasattr(x, "read"):
                    total += len(x.read())  # consume el handle (como el real)
        self.read_sizes.append(total)
        if self.calls == 1:
            raise ConnectionResetError(
                "[WinError 10054] Se ha forzado la interrupción de una "
                "conexión existente por el host remoto")
        return ["ok"]


with open(imgf, "rb") as fi, open(audf, "rb") as fa:
    client = _RewindClient()
    out = replicate_call(client, "owner/m", {"image": fi, "refs": [fa]},
                         net_retries=3)
check("el 1er intento leyó los 8000 bytes", client.read_sizes[0] == 8000,
      str(client.read_sizes))
check("el 2º intento (reintento) TAMBIÉN leyó 8000 (no 0: rebobinado)",
      len(client.read_sizes) > 1 and client.read_sizes[1] == 8000,
      str(client.read_sizes))
check("devolvió el resultado", out == ["ok"], str(out))

print("T2 corte durante la espera → reanuda la MISMA predicción (sin re-cobro)")


class _Pred:
    def __init__(self, fail_times):
        self.id = "pred-1"
        self.fail = fail_times
        self.status = "succeeded"
        self.output = ["https://resultado"]
        self.error = None

    def wait(self):
        if self.fail > 0:
            self.fail -= 1
            raise ConnectionResetError("[WinError 10054] corte a mitad de espera")


class _ResumeClient:
    def __init__(self, wait_fails):
        self.creates = 0
        self.gets = 0
        self.pred = _Pred(wait_fails)
        outer = self

        class _Preds:
            def create(inner, version=None, input=None):
                outer.creates += 1
                return outer.pred

            def get(inner, pid):
                outer.gets += 1
                assert pid == "pred-1"
                return outer.pred

        class _V:
            id = "v1"

        class _M:
            latest_version = _V()

        class _Models:
            def get(inner, model):
                return _M()

        self.predictions = _Preds()
        self.models = _Models()


t0 = time.time()
client2 = _ResumeClient(wait_fails=2)
out = replicate_call(client2, "owner/m", {}, net_retries=5)
check("devolvió el resultado tras reconectar", out == ["https://resultado"])
check("la predicción se creó UNA sola vez (sin re-cobro)",
      client2.creates == 1, f"creates={client2.creates}")
check("se re-consultó la misma predicción al reconectar",
      client2.gets == 2, f"gets={client2.gets}")
check("avisó que la generación sigue en el servidor sin re-cobrar",
      any("no se cobra de nuevo" in n for n in notices), str(notices[-3:]))

print("T3 reconexión agotada → NO re-crea la predicción, error claro")
notices.clear()
client3 = _ResumeClient(wait_fails=999)
try:
    replicate_call(client3, "owner/m", {}, net_retries=2)
    check("lanzó un error al agotar la reconexión", False)
except RuntimeError as e:
    check("lanzó un error al agotar la reconexión", True)
    check("es el error de red persistente (no un traceback críptico)",
          isinstance(e, PersistentNetworkError) and "otra red" in str(e),
          f"{type(e).__name__}: {e}")
check("NO se re-creó la predicción al agotar (creates sigue en 1)",
      client3.creates == 1, f"creates={client3.creates}")

print("T4 net_retries por proveedor: lipsync/videogen caen rápido, imágenes insisten")


class _AlwaysDown:
    def __init__(self):
        self.calls = 0
        self.models = _NoVersion()

    def run(self, model, input=None):
        self.calls += 1
        raise ConnectionResetError("[WinError 10054] red caída")


class _StubReplicate:
    pass


sys.modules.setdefault("replicate", _StubReplicate())

from ytstudio.providers.lipsync import ReplicateLipsync
from ytstudio.providers.videogen import ReplicateVideo
from ytstudio.providers.images import ReplicateImages

ls = ReplicateLipsync({"providers": {"lipsync": {}}})
ls.client = _AlwaysDown()
try:
    ls.generate(imgf, audf, TMP / "out.mp4", seconds=5)
except RuntimeError:
    pass
check("lipsync: 3 intentos (1 + 2 reintentos) y cae a imagen fija",
      ls.client.calls == 3, str(ls.client.calls))

vg = ReplicateVideo({"providers": {"videogen": {}}, "video": {}})
vg.client = _AlwaysDown()
try:
    vg.generate("prompt", TMP / "clip.mp4", image=imgf, seconds=5)
except RuntimeError:
    pass
check("videogen: 3 intentos y cae a imagen animada",
      vg.client.calls == 3, str(vg.client.calls))

im = ReplicateImages({"providers": {"images": {}}, "video": {}})
im.client = _AlwaysDown()
try:
    im.generate("prompt", TMP / "img.jpg")
except RuntimeError:
    pass
check("imágenes: 6 intentos (detienen la fase: vale insistir más)",
      im.client.calls == 6, str(im.client.calls))

print("T5 encuadre con ffmpeg REAL: retrato 9:16 entero sobre fondo desenfocado")
import subprocess

from PIL import Image, ImageDraw

from ytstudio.phases.assembly import _still_filter

W, H, FPS, FRAMES = 1920, 1080, 24, 24


def render_still(img_path, animation="zoom_in", frame_idx=12):
    filt = _still_filter(img_path, animation, FRAMES, W, H, FPS)
    outv = TMP / "out.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(img_path), "-t", "1",
                    "-filter_complex", f"[0:v]{filt}[v]", "-map", "[v]",
                    "-frames:v", str(FRAMES), "-pix_fmt", "yuv420p",
                    str(outv)], check=True)
    png = TMP / "frame.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(outv), "-vf", f"select=eq(n\\,{frame_idx})",
                    "-vframes", "1", str(png)], check=True)
    return png


# Retrato 9:16 con fondo VERDE y el "sujeto" (círculo rojo) en el TERCIO
# SUPERIOR: el recorte de cobertura centrado lo dejaba fuera de cuadro.
port = TMP / "portrait.jpg"
pw, ph = 900, 1600
img = Image.new("RGB", (pw, ph), (40, 150, 80))
d = ImageDraw.Draw(img)
r = round(pw * 0.15)
cx, cy = pw // 2, round(ph * 0.22)  # tercio superior (como una cara)
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(230, 60, 60))
img.save(port, quality=95)

filt = _still_filter(port, "zoom_in", FRAMES, W, H, FPS)
check("retrato 9:16 → composición con fondo desenfocado (overlay)",
      "overlay" in filt and "boxblur" in filt, filt)
png = render_still(port)
frame = Image.open(png).convert("RGB")
check("la salida mide exactamente 1920x1080", frame.size == (W, H),
      str(frame.size))
px = frame.load()
minx, miny, maxx, maxy = W, H, -1, -1
for y in range(0, H, 2):
    for x in range(0, W, 2):
        rr, gg, bb = px[x, y]
        if abs(rr - 230) < 50 and abs(gg - 60) < 50 and abs(bb - 60) < 50:
            minx, miny = min(minx, x), min(miny, y)
            maxx, maxy = max(maxx, x), max(maxy, y)
found = maxx > 0
check("el sujeto del tercio superior APARECE (antes el recorte lo cortaba)",
      found)
if found:
    bw, bh = maxx - minx, maxy - miny
    ratio = bw / bh if bh else 0
    check(f"el sujeto está ENTERO y redondo [{bw}x{bh}]",
          0.85 <= ratio <= 1.18 and miny > 2 and maxy < H - 3,
          f"ratio={ratio:.2f} bbox=({minx},{miny},{maxx},{maxy})")
side = px[40, H // 2]
check("los laterales tienen fondo desenfocado (no barras negras)",
      sum(side) > 90, str(side))

wide16 = TMP / "wide.jpg"
Image.new("RGB", (1920, 1080), (40, 150, 80)).save(wide16, quality=95)
f169 = _still_filter(wide16, "zoom_in", FRAMES, W, H, FPS)
check("fuente ya 16:9 → recorte de cobertura de siempre (sin overlay)",
      "overlay" not in f169 and "force_original_aspect_ratio=increase" in f169,
      f169)
img43 = TMP / "img43.jpg"
Image.new("RGB", (1200, 900), (40, 150, 80)).save(img43, quality=95)
f43 = _still_filter(img43, "zoom_in", FRAMES, W, H, FPS)
check("fuente 4:3 (desajuste leve) → también recorte, no composición",
      "overlay" not in f43, f43)

print("T6 reencuadre con IA de la foto del personaje")
import ytstudio.providers.images as images_mod
from ytstudio.phases.broll import _reframe_character_still

cfg = {"video": {"width": 1920, "height": 1080}, "providers": {"images": {}}}


class _FakeRefImages:
    def __init__(self):
        self.calls = []

    def generate_with_refs(self, prompt, refs, out):
        self.calls.append((prompt, list(refs)))
        Image.new("RGB", (1920, 1080), (90, 90, 120)).save(out, quality=95)
        return out


orig_get_ref = images_mod.get_ref_images
fake = _FakeRefImages()
try:
    images_mod.get_ref_images = lambda cfg: fake
    dest = _reframe_character_still(port, "the narrator speaks", TMP, cfg)
    check("con identidad disponible: regenera la foto al formato del video",
          dest is not None and dest.exists() and
          Image.open(dest).size == (1920, 1080),
          str(dest))
    check("usó la foto como referencia y un prompt de reencuadre",
          len(fake.calls) == 1 and fake.calls[0][1] == [port]
          and "Reframe" in fake.calls[0][0], str(fake.calls))
    (TMP / "personaje_wide.jpg").unlink(missing_ok=True)

    images_mod.get_ref_images = lambda cfg: None
    check("sin token de identidad: devuelve None (el montaje compone con "
          "fondo desenfocado)",
          _reframe_character_still(port, "x", TMP, cfg) is None)

    calls_before = len(fake.calls)
    images_mod.get_ref_images = lambda cfg: fake
    check("foto ya 16:9: ni intenta regenerar (no gasta)",
          _reframe_character_still(wide16, "x", TMP, cfg) is None
          and len(fake.calls) == calls_before)
finally:
    images_mod.get_ref_images = orig_get_ref

print("T7 avisos de hilos trabajadores llegan al log de la ejecución")
from ytstudio import progress
from ytstudio.phases.broll import _bind_worker_logging

log_msgs = []
progress.set_sink(log_msgs.append)
check("get_sink devuelve el sink del hilo actual",
      progress.get_sink() is not None)
captured = progress.get_sink()
worker_saw = {}


def _worker():
    worker_saw["before"] = progress.get_sink()  # None: no hereda
    _bind_worker_logging(captured)
    progress.notify("aviso desde el worker")
    from ytstudio.providers.replicate_util import _notify
    _notify("reintento desde el worker")


t = threading.Thread(target=_worker)
t.start()
t.join()
check("un hilo nuevo NO hereda el sink (por eso hay que vincularlo)",
      worker_saw["before"] is None, str(worker_saw))
check("tras vincular, el aviso del worker llegó al log",
      "aviso desde el worker" in log_msgs, str(log_msgs))
check("los avisos de reintento de Replicate del worker también llegan",
      "reintento desde el worker" in log_msgs, str(log_msgs))

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
