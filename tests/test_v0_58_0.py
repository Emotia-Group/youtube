"""Batería v0.58.0 — relevo de modelos apagados y nuevas rutas de ahorro.

Dos modelos que el programa usaba tienen fecha de apagado por sus proveedores:
imagen-4-fast (17/08/2026) y gpt-image-1 (23/10/2026). El segundo era grave: lo
usaban EN EXCLUSIVA las escenas con texto legible, que se habrían quedado sin
soporte. Además se incorporan las opciones que abaratan y aceleran.

Verifica:
1.  El modelo de OpenAI ya no está clavado: por defecto gpt-image-2, pero si
    pides uno de OpenAI concreto se respeta, y un slug de Replicate se ignora.
2.  El proveedor sigue construyéndose sin __init__ (lo hacen las baterías).
3.  Los modelos retirados están fichados con fecha y sustituto, y la fábrica
    AVISA antes de generar en vez de dejar que falle la API a mitad de fase.
4.  El escalado: elige el factor mínimo, se salta lo que ya da la talla (y por
    tanto no cobra), y si falla CONSERVA la imagen original.
5.  Cartesia y AssemblyAI: precios por proveedor, no el número único de antes.
6.  Veo 3.1: duraciones propias (4/6/8 frente a 5/10 de Kling), audio nativo
    declarado y costo proporcional a los segundos que se piden de verdad.
7.  Hedra queda entre Sonic y OmniHuman en precio.
8.  El catálogo de la interfaz ofrece todo lo nuevo y ya no ofrece lo apagado.
9.  La estimación previa cuenta el escalado (si no, el tope de gasto lo
    frenaría a mitad de camino).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0580_"))

# ---------------------------------------------------------------------------
# T1 — el modelo de OpenAI dejó de estar clavado
# ---------------------------------------------------------------------------
print("T1 relevo de gpt-image-1")
from ytstudio import pricing

check("T1a por defecto se usa gpt-image-2",
      pricing.effective_image_model("openai", "") == "gpt-image-2")
check("T1b un slug de Replicate NO falsea el modelo (ni el precio)",
      pricing.effective_image_model("openai", "black-forest-labs/flux-1.1-pro")
      == "gpt-image-2")
check("T1c si pides gpt-image-1 explícitamente, se respeta (hasta que muera)",
      pricing.effective_image_model("openai", "gpt-image-1") == "gpt-image-1")
check("T1d Replicate sigue respetando cualquier modelo suyo",
      pricing.effective_image_model("replicate", "black-forest-labs/flux-2-pro")
      == "black-forest-labs/flux-2-pro")

from ytstudio.providers.images import OpenAIImages
_p = OpenAIImages.__new__(OpenAIImages)      # sin __init__: no pide clave
check("T1e el proveedor es usable sin __init__ (model y quality por defecto)",
      _p.model == "gpt-image-2" and _p.quality == "medium",
      f"{getattr(_p, 'model', None)}/{getattr(_p, 'quality', None)}")

# ---------------------------------------------------------------------------
# T2 — modelos retirados: fichados y avisados ANTES de gastar
# ---------------------------------------------------------------------------
print("\nT2 modelos con fecha de apagado")
for muerto, relevo in (("google/imagen-4-fast", "google/nano-banana"),
                       ("gpt-image-1", "gpt-image-2")):
    info = pricing.retirement(muerto)
    check(f"T2 «{muerto}» está fichado con fecha y sustituto",
          bool(info) and info[1] == relevo, str(info))
check("T2c un modelo vivo no se marca como retirado",
      pricing.retirement("black-forest-labs/flux-1.1-pro") is None)

import io
from contextlib import redirect_stdout
from ytstudio.providers import _warn_retired
buf = io.StringIO()
with redirect_stdout(buf):
    _warn_retired({"providers": {"images": {"model": "google/imagen-4-fast"}}})
aviso = buf.getvalue()
check("T2d la fábrica AVISA del modelo retirado antes de generar",
      "imagen-4-fast" in aviso and "nano-banana" in aviso, repr(aviso[:120]))
buf = io.StringIO()
with redirect_stdout(buf):
    _warn_retired({"providers": {"images": {"model": "black-forest-labs/flux-1.1-pro"}}})
check("T2e y calla si el modelo está vivo", buf.getvalue() == "",
      repr(buf.getvalue()))

# La migración de una sola vez REPARA el config en vez de solo avisar: un
# modelo apagado no es una preferencia que respetar, es una avería en camino.
from ytstudio.webui.server import _apply_migrations
roto = {"providers": {"images": {"name": "replicate",
                                 "model": "google/imagen-4-fast",
                                 "ref_model": "google/nano-banana"}},
        "migrations": ["images_replicate_v0_45"]}
buf = io.StringIO()
with redirect_stdout(buf):
    arreglado = _apply_migrations(roto)
check("T2f la migración sustituye el modelo apagado por su relevo",
      arreglado["providers"]["images"]["model"] == "google/nano-banana",
      str(arreglado["providers"]["images"]))
check("T2g y avisa de lo que cambió", "imagen-4-fast" in buf.getvalue())
with redirect_stdout(io.StringIO()):
    _otra_vez = _apply_migrations(dict(arreglado))
check("T2h la migración es idempotente (no se repite al reiniciar)",
      _otra_vez == arreglado, str(_otra_vez))

elegido = {"providers": {"images": {"name": "replicate",
                                    "model": "black-forest-labs/flux-2-pro"}},
           "migrations": ["images_replicate_v0_45"]}
with redirect_stdout(io.StringIO()):
    intacto = _apply_migrations(elegido)
check("T2i y NO toca el modelo que el creador eligió a conciencia",
      intacto["providers"]["images"]["model"] == "black-forest-labs/flux-2-pro")

# ---------------------------------------------------------------------------
# T3 — ESCALADO: la palanca de ahorro, sin cobrar de más ni romper nada
# ---------------------------------------------------------------------------
print("\nT3 escalado (modo híbrido)")
from PIL import Image
from ytstudio.providers.images import ReplicateUpscale

up = ReplicateUpscale.__new__(ReplicateUpscale)
up.model = "nightmareai/real-esrgan"
up.target_w = 1920

chica = TMP / "chica.jpg"
Image.new("RGB", (512, 288), (10, 20, 30)).save(chica)
grande = TMP / "grande.jpg"
Image.new("RGB", (1920, 1080), (10, 20, 30)).save(grande)
media = TMP / "media.jpg"
Image.new("RGB", (1024, 576), (10, 20, 30)).save(media)

check("T3a una imagen de 512px pide x4 (512x4=2048 ≥ 1920)",
      up._scale_for(chica) == 4, str(up._scale_for(chica)))
check("T3b una de 1024px pide solo x2 (no se paga un x4 innecesario)",
      up._scale_for(media) == 2, str(up._scale_for(media)))
check("T3c una que YA da la talla no se escala (factor 0 = no se cobra)",
      up._scale_for(grande) == 0, str(up._scale_for(grande)))

antes = grande.read_bytes()
check("T3d y upscale() la devuelve intacta sin llamar a la API",
      up.upscale(grande) == grande and grande.read_bytes() == antes)


class _FallaSiempre:
    def __getattr__(self, _):
        raise RuntimeError("red caída")


up.client = _FallaSiempre()
orig = chica.read_bytes()
res = up.upscale(chica)
check("T3e si el escalado falla, se CONSERVA la imagen original",
      res == chica and chica.read_bytes() == orig and chica.exists())
check("T3f y no deja basura _up en el proyecto",
      not (TMP / "chica_up.jpg").exists())

# El escalado es una MEJORA opcional: ningún fallo suyo puede tumbar la fase
from ytstudio.config import load_config
from ytstudio.providers.images import get_upscaler
_cfg = load_config()
_cfg["providers"]["images"]["upscale"] = False
check("T3g1 apagado, no hay escalador (ni gasto)", get_upscaler(_cfg) is None)
_cfg["providers"]["images"]["upscale"] = True
import os as _os
_tok = _os.environ.pop("REPLICATE_API_TOKEN", None)
with redirect_stdout(io.StringIO()):
    _sin_token = get_upscaler(_cfg)
check("T3g2 activado pero sin token: avisa y sigue sin escalar (no revienta)",
      _sin_token is None)
_os.environ["REPLICATE_API_TOKEN"] = "test-token"
with redirect_stdout(io.StringIO()):
    _sin_paquete = get_upscaler(_cfg)      # aquí falta `pip install replicate`
check("T3g3 y si el proveedor no se puede preparar, degrada en vez de fallar",
      _sin_paquete is None or hasattr(_sin_paquete, "upscale"))
if _tok is None:
    _os.environ.pop("REPLICATE_API_TOKEN", None)
else:
    _os.environ["REPLICATE_API_TOKEN"] = _tok

check("T3g el escalado cuesta una fracción de generar caro",
      pricing.upscale_cost_mid("nightmareai/real-esrgan") < 0.01)
# La cuenta que justifica todo el modo híbrido
barato = pricing.img_cost_mid("replicate", "black-forest-labs/flux-schnell")
caro = pricing.img_cost_mid("replicate", "black-forest-labs/flux-1.1-pro")
hibrido = (barato + pricing.upscale_cost_mid("nightmareai/real-esrgan")) * 100
check("T3h 100 imágenes: híbrido bajo $1 contra ~$4.5 del modelo caro",
      hibrido < 1.0 and caro * 100 > 4.0,
      f"híbrido ${hibrido:.2f} · caro ${caro * 100:.2f}")

# ---------------------------------------------------------------------------
# T4 — voz y transcripción: precio POR PROVEEDOR
# ---------------------------------------------------------------------------
print("\nT4 voz y transcripción")
chars = 9000        # ~10 min de narración
check("T4a Cartesia es mucho más barato que OpenAI en el mismo texto",
      pricing.tts_cost(chars, "cartesia") < pricing.tts_cost(chars, "openai") / 1.5,
      f"cartesia ${pricing.tts_cost(chars, 'cartesia'):.3f} · "
      f"openai ${pricing.tts_cost(chars, 'openai'):.3f}")
check("T4b ElevenLabs sigue sin costo por uso (va contra el plan)",
      pricing.tts_cost(chars, "elevenlabs") == 0.0)
check("T4c AssemblyAI cuesta menos por minuto que Whisper",
      pricing.stt_cost(12, "assemblyai") < pricing.stt_cost(12, "openai"))
check("T4d sin proveedor, el precio histórico de Whisper no cambia",
      abs(pricing.stt_cost(10) - 0.06) < 1e-6)

from ytstudio.providers import _REQUIRED_KEYS
check("T4e las claves nuevas están registradas (degradan a mock sin ellas)",
      _REQUIRED_KEYS.get("cartesia") == "CARTESIA_API_KEY"
      and _REQUIRED_KEYS.get("assemblyai") == "ASSEMBLYAI_API_KEY")

from ytstudio.providers import tts as tts_mod, stt as stt_mod
check("T4f los proveedores nuevos existen y exponen su interfaz",
      hasattr(tts_mod.CartesiaTTS, "synthesize")
      and hasattr(stt_mod.AssemblyAISTT, "transcribe_segments")
      and hasattr(stt_mod.AssemblyAISTT, "transcribe"))

# ---------------------------------------------------------------------------
# T5 — Veo 3.1: duraciones propias, audio nativo y costo proporcional
# ---------------------------------------------------------------------------
print("\nT5 video con audio nativo")
from ytstudio.providers.videogen import clip_duration_for

check("T5a Kling sigue pidiendo 5 s para una escena corta",
      clip_duration_for("kwaivgi/kling-v1.6-standard", 6.0) == 10
      and clip_duration_for("kwaivgi/kling-v1.6-standard", 4.0) == 5)
check("T5b Veo usa SUS duraciones (4/6/8), no las de Kling",
      clip_duration_for("google/veo-3.1-fast", 5.0) == 6
      and clip_duration_for("google/veo-3.1-fast", 7.0) == 8
      and clip_duration_for("google/veo-3.1-fast", 3.0) == 4)
check("T5c Veo declara audio nativo y los demás no",
      pricing.has_native_audio("google/veo-3.1-fast")
      and not pricing.has_native_audio("kwaivgi/kling-v1.6-standard"))
# El costo escala con los segundos REALES: antes saltaba al doble pasando 7.5s
c5 = pricing.video_cost_mid(5, "kwaivgi/kling-v1.6-standard")
c10 = pricing.video_cost_mid(10, "kwaivgi/kling-v1.6-standard")
check("T5d Kling a 10 s sigue costando el doble que a 5 s (sin cambios)",
      abs(c10 - 2 * c5) < 1e-6, f"{c5} → {c10}")
c8 = pricing.video_cost_mid(8, "google/veo-3.1-fast")
check("T5e Veo a 8 s cuesta 8/5 de su tarifa, no el doble de golpe",
      abs(c8 - pricing.video_cost_mid(5, "google/veo-3.1-fast") * 1.6) < 1e-6,
      str(c8))

# ---------------------------------------------------------------------------
# T6 — Hedra en la escalera de lipsync
# ---------------------------------------------------------------------------
print("\nT6 lipsync")
sonic = pricing.lipsync_cost_range("zsxkib/sonic")
hedra = pricing.lipsync_cost_range("hedra/character-3")
omni = pricing.lipsync_cost_range("bytedance/omni-human")
check("T6a Hedra queda entre Sonic y OmniHuman en precio",
      sonic[1] <= hedra[0] and hedra[1] < omni[0],
      f"sonic {sonic} · hedra {hedra} · omni {omni}")
from ytstudio.providers.lipsync import _MODEL_INPUTS
check("T6b y sus inputs están mapeados (si no, fallaría al llamarlo)",
      "hedra/character-3" in _MODEL_INPUTS)

# ---------------------------------------------------------------------------
# T7 — el catálogo de la interfaz ofrece lo nuevo y retira lo apagado
# ---------------------------------------------------------------------------
print("\nT7 catálogo de la interfaz")
from ytstudio.catalog import CATALOG, key_status

img_ids = [m["id"] for o in CATALOG["images"]["options"]
           for m in o.get("models", [])]
check("T7a gpt-image-2 está ofrecido", "gpt-image-2" in img_ids)
check("T7b imagen-4-fast (apagado el 17/08/2026) ya NO se ofrece",
      "google/imagen-4-fast" not in img_ids, str(img_ids))
check("T7c FLUX 2 está disponible",
      "black-forest-labs/flux-2-pro" in img_ids
      and "black-forest-labs/flux-2-flash" in img_ids)

extra = {f["key"] for f in CATALOG["images"].get("extra_fields", [])}
check("T7d el modo híbrido es configurable desde la interfaz",
      {"upscale", "upscale_model", "quality"} <= extra, str(extra))
bool_fields = [f for f in CATALOG["images"]["extra_fields"]
               if f["key"] == "upscale"]
check("T7e y el interruptor es de tipo booleano (casilla, no texto)",
      bool_fields and bool_fields[0].get("type") == "bool")

vid_ids = [m["id"] for o in CATALOG["videogen"]["options"]
           for m in o.get("models", [])]
check("T7f Veo 3.1 está ofrecido", "google/veo-3.1-fast" in vid_ids)
tts_names = [o["name"] for o in CATALOG["tts"]["options"]]
stt_names = [o["name"] for o in CATALOG["stt"]["options"]]
mus_names = [o["name"] for o in CATALOG["music"]["options"]]
lip_ids = [m["id"] for o in CATALOG["lipsync"]["options"]
           for m in o.get("models", [])]
check("T7g Cartesia, AssemblyAI, ElevenLabs Music y Hedra están ofrecidos",
      "cartesia" in tts_names and "assemblyai" in stt_names
      and "elevenlabs" in mus_names and "hedra/character-3" in lip_ids,
      f"{tts_names} {stt_names} {mus_names}")
check("T7h las claves nuevas se muestran en el panel de claves",
      {"CARTESIA_API_KEY", "ASSEMBLYAI_API_KEY"} <= set(key_status()))

# El catálogo NO debe ofrecer nada que ya esté retirado
todos = img_ids + vid_ids + lip_ids
vivos = [m for m in todos if pricing.retirement(m)
         and m != "gpt-image-1"]   # gpt-image-1 se mantiene, etiquetado, hasta oct
check("T7i ningún otro modelo retirado sigue ofrecido", not vivos, str(vivos))

# ---------------------------------------------------------------------------
# T8 — la estimación cuenta el escalado (o el tope de gasto lo frenaría)
# ---------------------------------------------------------------------------
print("\nT8 estimación previa")
import copy
import os

import yaml
from ytstudio.estimate import estimate

# Sin token, la estimación asume vista previa (costo 0) y no habría nada que
# medir: se simula que Replicate está configurado.
_prev_tok = os.environ.get("REPLICATE_API_TOKEN")
os.environ["REPLICATE_API_TOKEN"] = "test-token"

cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
cfg["providers"]["images"]["name"] = "replicate"
cfg["providers"]["images"]["model"] = "black-forest-labs/flux-schnell"


class PStub:
    def __init__(self):
        self.data = {"assets": [], "scene_count": 100}

    def get(self, k, d=None):
        return self.data.get(k, d)


sin_up = copy.deepcopy(cfg)
sin_up["providers"]["images"]["upscale"] = False
con_up = copy.deepcopy(cfg)
con_up["providers"]["images"]["upscale"] = True

e_sin = estimate(PStub(), sin_up)
e_con = estimate(PStub(), con_up)
fases_con = [i["fase"] for i in e_con["items"]]
check("T8a con el escalado activo aparece su propia partida",
      any(f.startswith("Escalado") for f in fases_con), str(fases_con))
check("T8b y sin él no aparece",
      not any(f.startswith("Escalado") for f in
              [i["fase"] for i in e_sin["items"]]))


def _techo(e):
    return sum(i["costo"][1] for i in e["items"])


check("T8c el escalado sube el costo estimado (se paga aparte)",
      _techo(e_con) > _techo(e_sin),
      f"${_techo(e_sin):.2f} → ${_techo(e_con):.2f}")
# …y aun así el híbrido completo sigue MUY por debajo del modelo caro
caro_cfg = copy.deepcopy(sin_up)
caro_cfg["providers"]["images"]["model"] = "black-forest-labs/flux-1.1-pro"
check("T8d y el total híbrido sigue muy por debajo de FLUX 1.1 Pro",
      _techo(e_con) < _techo(estimate(PStub(), caro_cfg)),
      f"híbrido ${_techo(e_con):.2f} vs pro "
      f"${_techo(estimate(PStub(), caro_cfg)):.2f}")

if _prev_tok is None:
    os.environ.pop("REPLICATE_API_TOKEN", None)
else:
    os.environ["REPLICATE_API_TOKEN"] = _prev_tok

# ---------------------------------------------------------------------------
import shutil

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.58.0 completa: relevo de los modelos apagados, modo "
      "híbrido de ahorro, voz y transcripción más baratas, y video con "
      "audio nativo.")
