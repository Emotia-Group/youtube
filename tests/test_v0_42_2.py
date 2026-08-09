"""Batería v0.42.2 — el corte por max_tokens (fase Concepto) y el gasto invisible.

Reproduce con un cliente Anthropic FALSO (misma forma que el SDK real:
client.messages.stream(...) → context manager → get_final_message()) el
escenario exacto del log d1cbcffd:

  «Concepto y estilo: La respuesta del modelo se cortó por el límite de
   tokens (max_tokens=16000)»

Verifica:
1. Con thinking adaptativo, una respuesta cortada YA NO mata la fase: se
   reintenta una vez con el techo ampliado y el proyecto continúa.
2. El GASTO de la llamada cortada (y de una rechazada) se registra SIEMPRE —
   antes era invisible: se pagaba y no aparecía en el reporte.
3. Los techos por defecto suben a 64000 (max_tokens es un TOPE, no una
   reserva: solo se paga lo generado).
4. Si ni con el techo máximo cabe, el error es claro y accionable.
5. La fase de Concepto REAL (concept.run) sobrevive a un corte.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys
import types



FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


# ---------------------------------------------------------------------------
# Doble del SDK de Anthropic (misma superficie que usa ytstudio)
# ---------------------------------------------------------------------------

class FakeUsage:
    def __init__(self, i, o):
        self.input_tokens, self.output_tokens = i, o


class FakeMessage:
    def __init__(self, stop_reason, text, usage):
        self.stop_reason = stop_reason
        self.usage = usage
        self.content = ([types.SimpleNamespace(type="thinking", thinking="…")]
                        + ([types.SimpleNamespace(type="text", text=text)]
                           if text is not None else []))


class FakeStream:
    def __init__(self, message):
        self._m = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._m


class FakeMessages:
    """Devuelve respuestas programadas; registra los max_tokens recibidos."""

    def __init__(self, script):
        self.script = list(script)   # [(stop_reason, text, in_tok, out_tok)]
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        stop, text, i, o = self.script.pop(0)
        return FakeStream(FakeMessage(stop, text, FakeUsage(i, o)))


class FakeAnthropic:
    def __init__(self, script):
        self.messages = FakeMessages(script)


def make_llm(script, model="claude-opus-4-8"):
    from ytstudio.providers.llm import ClaudeLLM
    llm = ClaudeLLM.__new__(ClaudeLLM)   # sin __init__: no requiere clave real
    llm.client = FakeAnthropic(script)
    llm.model = model
    return llm


from ytstudio import usage as usage_mod
from ytstudio.providers.llm import ClaudeLLM, MockLLM

# ---------------------------------------------------------------------------
# T1 — EL CASO DEL LOG: respuesta cortada → reintento con techo ampliado
# ---------------------------------------------------------------------------
usage_mod.reset()
llm = make_llm([
    ("max_tokens", None, 30000, 16000),           # corte (como en el log)
    ("end_turn", '{"angle": "ok"}', 30000, 900),  # reintento: cabe
])
out = llm.complete_json("sys", "prompt",
                        schema={"type": "object",
                                "properties": {"angle": {"type": "string"}},
                                "required": ["angle"],
                                "additionalProperties": False},
                        purpose="concept")
check("T1 la fase sobrevive al corte (reintento automático)",
      out == {"angle": "ok"}, str(out))
calls = llm.client.messages.calls
check("T1b hubo exactamente 2 llamadas", len(calls) == 2, str(len(calls)))
check("T1c el reintento amplía el techo",
      calls[1]["max_tokens"] > calls[0]["max_tokens"],
      f"{calls[0]['max_tokens']} → {calls[1]['max_tokens']}")
check("T1d el reintento no supera el techo del modelo",
      calls[1]["max_tokens"] <= ClaudeLLM.MAX_OUTPUT,
      str(calls[1]["max_tokens"]))
check("T1e sigue usando pensamiento adaptativo",
      calls[0]["thinking"] == {"type": "adaptive"}, str(calls[0].get("thinking")))

# ---------------------------------------------------------------------------
# T2 — EL DINERO: el gasto de la llamada CORTADA se registra igual
# ---------------------------------------------------------------------------
items = usage_mod.get_state()
tokens = sum(i["qty"] for i in items if i["provider"] == "anthropic")
spent = sum(i["usd"] for i in items if i["provider"] == "anthropic")
# llamada 1: 30000 in + 16000 out · llamada 2: 30000 in + 900 out
esperado_tokens = (30000 + 16000) + (30000 + 900)
esperado_usd = ((30000 * 5.0 + 16000 * 25.0) + (30000 * 5.0 + 900 * 25.0)) / 1e6
check("T2 los tokens de AMBAS llamadas quedan registrados",
      tokens == esperado_tokens, f"{tokens} vs {esperado_tokens}")
check("T2b el costo incluye la llamada cortada (antes era invisible)",
      abs(spent - esperado_usd) < 1e-9, f"{spent:.4f} vs {esperado_usd:.4f}")
check("T2c la llamada cortada aporta gasto real > 0",
      esperado_usd > 0.5, f"{esperado_usd:.4f}")

# ---------------------------------------------------------------------------
# T3 — RECHAZO (refusal): también se paga y también se registra
# ---------------------------------------------------------------------------
usage_mod.reset()
llm = make_llm([("refusal", None, 12000, 300, )])
try:
    llm.complete("sys", "prompt", purpose="transcript_polish")
    check("T3 el rechazo se propaga como error", False, "no lanzó")
except RuntimeError as e:
    check("T3 el rechazo se propaga como error claro", "rechazó" in str(e), str(e))
items = usage_mod.get_state()
check("T3b el gasto del rechazo queda registrado (antes invisible)",
      any(i["provider"] == "anthropic" and i["qty"] == 12300 for i in items),
      str(items))

# ---------------------------------------------------------------------------
# T4 — techos por defecto amplios (max_tokens es tope, no reserva)
# ---------------------------------------------------------------------------
import inspect

sig = inspect.signature(ClaudeLLM.complete)
sig_j = inspect.signature(ClaudeLLM.complete_json)
check("T4 complete por defecto 64000",
      sig.parameters["max_tokens"].default == 64000,
      str(sig.parameters["max_tokens"].default))
check("T4b complete_json por defecto 64000",
      sig_j.parameters["max_tokens"].default == 64000,
      str(sig_j.parameters["max_tokens"].default))
check("T4c MockLLM mantiene la misma firma",
      inspect.signature(MockLLM.complete_json).parameters["max_tokens"].default
      == 64000, "")

usage_mod.reset()
llm = make_llm([("end_turn", "hola", 100, 10)])
llm.complete("sys", "prompt", purpose="x")
check("T4d una llamada sin max_tokens pide 64000",
      llm.client.messages.calls[0]["max_tokens"] == 64000,
      str(llm.client.messages.calls[0]["max_tokens"]))

# ---------------------------------------------------------------------------
# T5 — si NI con el techo máximo cabe: error claro y accionable
# ---------------------------------------------------------------------------
usage_mod.reset()
llm = make_llm([("max_tokens", None, 500, 64000),
                ("max_tokens", None, 500, 128000)])
try:
    llm.complete("sys", "prompt", purpose="scenes")
    check("T5 error tras dos cortes", False, "no lanzó")
except RuntimeError as e:
    check("T5 error claro tras dos cortes",
          "cortó dos veces" in str(e) and "tandas" in str(e), str(e))
check("T5b el gasto de los DOS intentos queda registrado",
      len([i for i in usage_mod.get_state()
           if i["provider"] == "anthropic"]) == 2,
      str(usage_mod.get_state()))

# techo ya en el máximo → no reintenta (no gasta de más)
usage_mod.reset()
llm = make_llm([("max_tokens", None, 500, ClaudeLLM.MAX_OUTPUT)])
try:
    llm.complete("sys", "prompt", max_tokens=ClaudeLLM.MAX_OUTPUT, purpose="x")
    check("T5c sin reintento inútil en el techo máximo", False, "no lanzó")
except RuntimeError as e:
    check("T5c sin reintento inútil en el techo máximo",
          len(llm.client.messages.calls) == 1 and "máximo" in str(e), str(e))

# respuesta sin bloque de texto (solo razonamiento) → se trata como corte
usage_mod.reset()
llm = make_llm([("end_turn", None, 200, 8000),
                ("end_turn", "recuperado", 200, 50)])
check("T5d respuesta sin texto se recupera con el reintento",
      llm.complete("s", "p", purpose="x") == "recuperado", "")

# ---------------------------------------------------------------------------
# T6 — LA FASE REAL: concept.run() sobrevive a un corte
# ---------------------------------------------------------------------------
import json
import tempfile
from pathlib import Path

from ytstudio.phases import concept as concept_phase
from ytstudio.project import DIRS


class PStub:
    def __init__(self, root):
        self.root = Path(root)
        self.slug = "test"
        self.data = {}
        self.warnings = []

    def path(self, key, *parts):
        p = self.root / DIRS[key]
        p.mkdir(parents=True, exist_ok=True)
        return p.joinpath(*parts) if parts else p

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.warnings.append(m)


CONCEPT_JSON = json.dumps({
    "title_options": ["A", "B", "C"], "angle": "ang", "audience": "aud",
    "tone": "tono", "structure": ["Gancho", "Cierre"],
    "visual_style": {"description": "d", "prompt_prefix": "pfx",
                     "palette": ["#111111"]},
    "music_direction": {"mood": "tense", "description": "d"},
    "duration_minutes": 15,
})

tmp = Path(tempfile.mkdtemp(prefix="v0422_"))
p = PStub(tmp / "proj")
# brief GRANDE, como el del log (video de referencia + narración de 20 min)
p.set("brief", {"topic": "Mansa Musa", "summary": "s" * 4000,
                "key_points": ["k"] * 10, "reference_frames": [],
                "links": [{"transcript_excerpt": "t" * 1200,
                           "rhythm": {"avg_shot_seconds": 6}}]})
usage_mod.reset()
llm = make_llm([("max_tokens", None, 40000, 16000),   # el corte del log
                ("end_turn", CONCEPT_JSON, 40000, 1200)])
old_get_llm = concept_phase.get_llm
concept_phase.get_llm = lambda cfg: llm
try:
    cfg = {"language": "es", "video": {"target_minutes": 15, "width": 1920,
                                       "height": 1080},
           "providers": {"llm": {"model": "claude-opus-4-8"}}}
    concept_phase.run(p, cfg)
finally:
    concept_phase.get_llm = old_get_llm
check("T6 la fase Concepto REAL se completa pese al corte",
      (p.get("concept") or {}).get("angle") == "ang", str(p.get("concept")))
check("T6b escribió concept.json",
      (p.path("concept") / "concept.json").exists(), "")
check("T6c el gasto de la llamada cortada quedó en el reporte",
      sum(i["qty"] for i in usage_mod.get_state()
          if i["provider"] == "anthropic") == (40000 + 16000) + (40000 + 1200),
      str(usage_mod.get_state()))

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.42.2 completa: corte por max_tokens recuperado y gasto "
      "siempre visible.")
import shutil
shutil.rmtree(tmp, ignore_errors=True)
