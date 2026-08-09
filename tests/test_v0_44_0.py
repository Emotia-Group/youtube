"""Batería v0.44.0 — blindaje ANTICIPADO para videos largos (estabilidad,
rapidez y economía).

Cada frente ataca un fallo que AÚN no ha ocurrido en los logs del creador pero
que el patrón de los anteriores hace casi seguro en las próximas corridas
largas:

1. 429/529/5xx de ANTHROPIC: un video largo hace ~25 llamadas grandes seguidas
   (tandas de escenas, dirección de arte, visión…). El SDK solo reintenta 2
   veces con esperas cortas — el mismo agujero que el 429 de OpenAI que mató
   la fase de imágenes (log 36cc3989), pero en el otro proveedor.
2. Economía de tokens por PROPÓSITO: las tareas auxiliares razonan en 'medium'
   — y effort+format viajan JUNTOS en un solo output_config (separados,
   extra_body pisaría el kwarg tipado y borraría el JSON estructurado).
3. Whisper rechaza archivos de más de 25MB: una narración de ~25 min a 128kbps
   ya lo supera. Se transcribe una copia mono a 48kbps (mismos tiempos).
4. UNA tanda fallida del diseño de escenas ya no tumba el storyboard entero.
5. El control factual con visión corre en PARALELO (2 a la vez): 14 tandas en
   serie añadían 7-14 minutos a un video de 84 escenas.
6. El falso aviso de «deriva inesperada» del último log real (109 pausas ×
   ~60ms ≈ 6.44s de ruido sub-umbral): la tolerancia escala con las pausas.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import shutil
import subprocess
import tempfile
import threading
import time
import types

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0440_"))

# Las esperas reales harían la batería eterna: se sustituye time.sleep y se
# anota cuánto se habría esperado (que es justo lo que hay que verificar).
DORMIDO = []
_real_sleep = time.sleep
time.sleep = lambda s: DORMIDO.append(s)

from ytstudio import usage as usage_mod
from ytstudio.providers.llm import ClaudeLLM, _server_wait

# ---------------------------------------------------------------------------
# Errores con la MISMA superficie que los del SDK de Anthropic
# ---------------------------------------------------------------------------


def _api_error(status, retry_after=None, name="APIStatusError"):
    headers = {"retry-after": str(retry_after)} if retry_after else {}
    e = type(name, (Exception,), {})(f"error {status}")
    e.status_code = status
    e.response = types.SimpleNamespace(headers=headers)
    return e


# ---------------------------------------------------------------------------
# T1 — _server_wait: qué se reintenta y cuánto se espera
# ---------------------------------------------------------------------------
check("T1 429 sin retry-after → 20s·intento",
      _server_wait(_api_error(429), 1) == 20.0
      and _server_wait(_api_error(429), 3) == 60.0, "")
check("T1b 529 (sobrecarga) y 503 también son transitorios",
      _server_wait(_api_error(529), 1) is not None
      and _server_wait(_api_error(503), 1) is not None, "")
check("T1c el retry-after de la API manda cuando supera la rampa",
      _server_wait(_api_error(429, retry_after=45), 1) == 46.0,
      str(_server_wait(_api_error(429, retry_after=45), 1)))
check("T1d la espera nunca se dispara (tope 120s)",
      _server_wait(_api_error(429, retry_after=500), 1) == 120.0
      and _server_wait(_api_error(529), 99) == 120.0, "")
check("T1e 400/401/404 NO se reintentan (sería pagar el mismo fallo)",
      _server_wait(_api_error(400), 1) is None
      and _server_wait(_api_error(401), 1) is None
      and _server_wait(Exception("x"), 1) is None, "")
conn = type("APIConnectionError", (Exception,), {})("corte de red")
check("T1f un corte de conexión (sin status) sí se reintenta",
      _server_wait(conn, 2) == 40.0, str(_server_wait(conn, 2)))

# ---------------------------------------------------------------------------
# Doble del SDK de Anthropic (misma superficie que usa ytstudio)
# ---------------------------------------------------------------------------


def _msg(text='{"ok": true}', stop="end_turn"):
    block = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(
        stop_reason=stop, content=[block],
        usage=types.SimpleNamespace(input_tokens=100, output_tokens=50))


class FakeStream:
    def __init__(self, result):
        self.result = result

    def __enter__(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.result


class FakeMessages:
    """Devuelve (o lanza) los resultados del guion, en orden."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.kwargs_vistos = []

    def stream(self, **kwargs):
        self.kwargs_vistos.append(kwargs)
        return FakeStream(self.guion.pop(0) if self.guion else _msg())


def make_llm(guion):
    llm = ClaudeLLM.__new__(ClaudeLLM)
    llm.model = "claude-opus-4-8"
    api = FakeMessages(guion)
    llm.client = types.SimpleNamespace(messages=api)
    return llm, api


# ---------------------------------------------------------------------------
# T2 — _resilient: el 429 de Anthropic ya no mata la fase
# ---------------------------------------------------------------------------
usage_mod.reset()
DORMIDO.clear()
llm, api = make_llm([_api_error(429), _api_error(529), _msg("hola")])
out = llm.complete("sys", "prompt", purpose="script")
check("T2 dos errores transitorios seguidos → espera y la llamada sale",
      out == "hola", repr(out))
check("T2b esperó 20s y luego 40s (rampa por intento)",
      DORMIDO == [20.0, 40.0], str(DORMIDO))

DORMIDO.clear()
llm, api = make_llm([_api_error(401)])
try:
    llm.complete("sys", "prompt")
    check("T2c un 401 sube intacto", False, "no lanzó")
except Exception as e:
    check("T2c un 401 sube intacto y sin esperas",
          getattr(e, "status_code", None) == 401 and not DORMIDO,
          f"{e} {DORMIDO}")

DORMIDO.clear()
llm, api = make_llm([_api_error(529)] * 10)
try:
    llm.complete("sys", "prompt")
    check("T2d si el servidor nunca cede, el error termina subiendo", False,
          "no lanzó")
except Exception as e:
    check("T2d si el servidor nunca cede, el error termina subiendo",
          getattr(e, "status_code", None) == 529, str(e))
check("T2e se intentó el número previsto de veces (4) con 3 esperas",
      len(api.kwargs_vistos) == ClaudeLLM.SERVER_RETRIES
      and len(DORMIDO) == ClaudeLLM.SERVER_RETRIES - 1,
      f"{len(api.kwargs_vistos)} llamadas, esperas {DORMIDO}")

# el reintento por truncado (v0.42.2) sigue componiendo con esta capa
DORMIDO.clear()
llm, api = make_llm([_msg(stop="max_tokens"), _msg("completo")])
out = llm.complete("sys", "prompt", max_tokens=16000)
check("T2f una respuesta cortada se reintenta con más techo (sin esperas)",
      out == "completo" and not DORMIDO
      and api.kwargs_vistos[1]["max_tokens"] > 16000,
      f"{out} techo={api.kwargs_vistos[-1].get('max_tokens')}")

# ---------------------------------------------------------------------------
# T3 — economía por propósito: effort y format viajan JUNTOS
# ---------------------------------------------------------------------------
esquema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
           "required": ["ok"], "additionalProperties": False}

llm, api = make_llm([_msg()])
llm.complete_json("sys", "p", schema=esquema, purpose="broll_qa")
kw = api.kwargs_vistos[0]
oc = kw.get("extra_body", {}).get("output_config", {})
check("T3 propósito auxiliar (broll_qa): razonamiento 'medium' via extra_body",
      oc.get("effort") == "medium", str(kw.get("extra_body")))
check("T3b …y el schema JSON viaja en el MISMO output_config "
      "(extra_body pisa el kwarg tipado: separados se perdería el formato)",
      oc.get("format", {}).get("type") == "json_schema"
      and "output_config" not in kw, str(sorted(kw.keys())))

llm, api = make_llm([_msg()])
llm.complete_json("sys", "p", schema=esquema, purpose="concept")
kw = api.kwargs_vistos[0]
check("T3c tarea creativa (concept): effort default, schema por kwarg tipado",
      "extra_body" not in kw
      and kw.get("output_config", {}).get("format", {}).get("type")
      == "json_schema", str(sorted(kw.keys())))

llm, api = make_llm([_msg("texto")])
llm.complete("sys", "p", purpose="music_pick")
kw = api.kwargs_vistos[0]
check("T3d auxiliar sin schema: solo el effort, sin output_config tipado",
      kw.get("extra_body", {}).get("output_config", {}).get("effort")
      == "medium" and "output_config" not in kw, str(sorted(kw.keys())))

llm, api = make_llm([_msg("texto")])
llm.complete("sys", "p", purpose="script")
check("T3e tarea creativa sin schema: la llamada va limpia (API default)",
      "extra_body" not in api.kwargs_vistos[0]
      and "output_config" not in api.kwargs_vistos[0], "")
check("T3f las fases CREATIVAS no están rebajadas",
      all(p not in ClaudeLLM.EFFORT_BY_PURPOSE
          for p in ("concept", "script", "scenes_design", "broll_fixed",
                    "art_direction", "metadata")),
      str(sorted(ClaudeLLM.EFFORT_BY_PURPOSE)))

# ---------------------------------------------------------------------------
# T4 — Whisper >24MB: copia ligera mono 48kbps (mismos tiempos)
# ---------------------------------------------------------------------------
from ytstudio.providers.stt import OpenAISTT

wav = TMP / "narracion.wav"
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                "sine=frequency=300:duration=4", "-ac", "2",
                "-ar", "44100", str(wav)],
               check=True, capture_output=True)


class FakeTranscriptions:
    def __init__(self):
        self.recibido = None      # (nombre, bytes) del archivo subido
        self.kwargs = None

    def create(self, model, file, **kwargs):
        self.recibido = (Path(file.name).name, Path(file.name).stat().st_size)
        self.kwargs = kwargs
        return types.SimpleNamespace(text="transcrito", words=[], segments=[])


def make_stt():
    stt = OpenAISTT.__new__(OpenAISTT)
    stt.language = "es"
    api = FakeTranscriptions()
    stt.client = types.SimpleNamespace(
        audio=types.SimpleNamespace(transcriptions=api))
    return stt, api


usage_mod.reset()
stt, api = make_stt()
stt.transcribe(wav)
check("T4 un audio pequeño se sube tal cual",
      api.recibido[0] == "narracion.wav", str(api.recibido))

# se fuerza el umbral por DEBAJO del wav para disparar la copia ligera
stt, api = make_stt()
stt.MAX_UPLOAD_BYTES = 40 * 1024
stt.transcribe(wav, hint="macacos rhesus, Mansa Musa")
check("T4b por encima del límite se sube la copia ligera, no el original",
      api.recibido[0] == "narracion_stt48k.mp3"
      and api.recibido[1] <= 40 * 1024, str(api.recibido))
check("T4c la copia temporal se borra al terminar",
      not (TMP / "narracion_stt48k.mp3").exists(), "")
check("T4d el vocabulario del proyecto sesga a Whisper (prompt)",
      api.kwargs.get("prompt", "").startswith("macacos"), str(api.kwargs))
items = usage_mod.get_state()
check("T4e el costo se mide sobre la duración REAL de la narración",
      len(items) == 2 and all(abs(i["qty"] - 4 / 60) < 0.01
                              for i in items), str(items))

# la copia se comprueba de verdad: mono y ~48kbps
stt, api = make_stt()
stt.MAX_UPLOAD_BYTES = 40 * 1024
_borrar = []
_orig_unlink = Path.unlink
Path.unlink = lambda self, **kw: _borrar.append(self.name)
try:
    stt.transcribe(wav)
finally:
    Path.unlink = _orig_unlink
copia = TMP / "narracion_stt48k.mp3"
probe = json.loads(subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams",
     str(copia)], capture_output=True, text=True).stdout)
audio_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
check("T4f la copia ligera es MONO (misma duración → mismos timestamps)",
      int(audio_stream.get("channels", 0)) == 1, str(audio_stream))
copia.unlink(missing_ok=True)

# >69 minutos: ni comprimida cabe → error claro, no el 413 críptico
stt, api = make_stt()
stt.MAX_UPLOAD_BYTES = 1024   # ni la copia a 48kbps baja de 1KB
try:
    stt.transcribe_segments(wav)
    check("T4g una narración imposible da un error accionable", False,
          "no lanzó")
except RuntimeError as e:
    check("T4g una narración imposible da un error accionable",
          "Divide la grabación" in str(e), str(e))
check("T4h y la copia fallida no queda huérfana en el disco",
      not (TMP / "narracion_stt48k.mp3").exists(), "")

# ---------------------------------------------------------------------------
# T5 — UNA tanda fallida del diseño de escenas no tumba el storyboard
# ---------------------------------------------------------------------------
from ytstudio.phases.scenes import _SCENES_PER_CALL, _broll_for_fixed


class PStub:
    def __init__(self):
        self.data = {}
        self.avisos = []

    def get(self, k, default=None):
        return self.data.get(k, default)

    def add_warning(self, m):
        self.avisos.append(m)


class TandaLLM:
    """complete_json que FALLA en la 2ª tanda (429 agotado, red, lo que sea)."""

    is_mock = False

    def __init__(self):
        self.llamadas = 0

    def complete_json(self, system, prompt, *, schema, max_tokens=64000,
                      purpose="", images=None):
        self.llamadas += 1
        if self.llamadas == 2:
            raise RuntimeError("Error code: 529 - overloaded (agotado)")
        import re
        n = len(re.findall(r"^\[\d+\]", prompt.split("NARRACIÓN POR ESCENA:")
                           [-1], flags=re.M))
        return {"scenes": [{"broll_prompt": f"cinematic shot {i}",
                            "broll_type": "image", "animation": "zoom_in",
                            "section": "Historia"} for i in range(n)]}


n_escenas = _SCENES_PER_CALL + 5   # 2 tandas: 40 + 5
escenas = [{"id": i + 1, "narration": f"La escena narra el hecho {i + 1}.",
            "animation": "static"} for i in range(n_escenas)]
concepto = {"visual_style": {"prompt_prefix": "estilo documental oscuro"}}
proyecto = PStub()
_broll_for_fixed(TandaLLM(), concepto, escenas, "español", 0, project=proyecto)
check("T5 la fase sobrevive a la tanda fallida y TODAS las escenas quedan "
      "con prompt",
      all(s.get("broll_prompt") for s in escenas), "")
check("T5b la tanda buena conserva el diseño del director",
      escenas[0]["broll_prompt"] == "cinematic shot 0", escenas[0]["broll_prompt"])
caidas = escenas[_SCENES_PER_CALL:]
check("T5c las escenas de la tanda caída salen con prefijo + narración "
      "(la dirección de arte las refina después)",
      all(s["broll_prompt"].startswith("estilo documental oscuro")
          and "narra el hecho" in s["broll_prompt"] for s in caidas),
      str(caidas[0]["broll_prompt"]))
check("T5d el proyecto guarda el aviso con el rango exacto de escenas",
      len(proyecto.avisos) == 1 and "41" in proyecto.avisos[0]
      and "45" in proyecto.avisos[0], str(proyecto.avisos))

# ---------------------------------------------------------------------------
# T6 — control factual con visión en PARALELO (2 a la vez)
# ---------------------------------------------------------------------------
from ytstudio.phases.broll import _qa_batches

broll_dir = TMP / "broll"
broll_dir.mkdir()
from PIL import Image
n_qa = 18   # 3 tandas de 6
for i in range(1, n_qa + 1):
    Image.new("RGB", (16, 16), (i * 10 % 255, 80, 40)).save(
        broll_dir / f"scene_{i:03d}.jpg")
targets = [{"id": i, "narration": f"Se narran {i} elementos."}
           for i in range(1, n_qa + 1)]
cfg_qa = {"language": "es"}


class VisionLLM:
    """Cuenta la concurrencia REAL de las tandas de visión."""

    is_mock = False

    def __init__(self, fallar_si=None):
        self.lock = threading.Lock()
        self.activos = 0
        self.pico = 0
        self.fallar_si = fallar_si   # id de escena que hace fallar su tanda

    def complete_json(self, system, prompt, *, schema, images=None,
                      max_tokens=64000, purpose=""):
        import re
        ids = [int(m) for m in re.findall(r"escena (\d+):", prompt)]
        with self.lock:
            self.activos += 1
            self.pico = max(self.pico, self.activos)
        _real_sleep(0.15)
        with self.lock:
            self.activos -= 1
        if self.fallar_si in ids:
            raise RuntimeError("Error code: 400 - imagen corrupta")
        return {"reviews": [{"scene": i, "fiel": True, "problema": "",
                             "prompt_corregido": ""} for i in ids]}


vision = VisionLLM()
t0 = time.perf_counter()
verdicts = _qa_batches(vision, cfg_qa, targets, broll_dir, PStub())
elapsed = time.perf_counter() - t0
check("T6 las 3 tandas de visión devuelven veredicto para las 18 escenas",
      verdicts is not None and len(verdicts) == n_qa,
      str(len(verdicts or {})))
check("T6b corren DOS a la vez (ni en serie ni sin freno)",
      vision.pico == 2, f"pico={vision.pico}")
check("T6c el paralelismo se nota en el reloj (3 tandas ≈ 2 turnos, no 3)",
      elapsed < 0.15 * 3, f"{elapsed:.2f}s")

proyecto_qa = PStub()
vision_mala = VisionLLM(fallar_si=8)
verdicts = _qa_batches(vision_mala, cfg_qa, targets, broll_dir, proyecto_qa)
check("T6d si UNA tanda falla: None (sin veredictos completos no se afirma "
      "nada) y aviso honesto",
      verdicts is None and len(proyecto_qa.avisos) == 1
      and "no se pudo completar" in proyecto_qa.avisos[0],
      f"{verdicts} {proyecto_qa.avisos}")

# ---------------------------------------------------------------------------
# T7 — el falso aviso de «deriva inesperada» (caso real del último log)
# ---------------------------------------------------------------------------
import inspect

from ytstudio.phases.voiceover import _speech_tolerance

check("T7 sin pausas ajustadas, la tolerancia base se mantiene (1.2s)",
      _speech_tolerance(0) == 1.2, str(_speech_tolerance(0)))
check("T7b EL CASO DEL LOG: 109 pausas ≈ 6.44s de ruido sub-umbral ya no "
      "dispara la falsa alarma",
      _speech_tolerance(109) > 6.44, str(_speech_tolerance(109)))
src = inspect.getsource(sys.modules["ytstudio.phases.voiceover"])
check("T7c la señal DURA (duración total, 0.15s) sigue intacta",
      "> 0.15 or" in src and "_speech_tolerance(n_comp + n_ext)" in src, "")

# ---------------------------------------------------------------------------
time.sleep = _real_sleep
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.44.0 completa: Anthropic con red de seguridad, Whisper "
      "sin techo de 25MB, tandas y visión resilientes, tokens medidos por "
      "propósito.")
shutil.rmtree(TMP, ignore_errors=True)
