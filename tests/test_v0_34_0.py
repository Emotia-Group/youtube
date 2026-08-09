"""Batería v0.34.0: biblioteca de 970 ganchos virales + integración en el
guion de videos verticales cortos.

Primer paso del giro a redes sociales: el PDF «1000 HOOKS VIRALES» del
creador se convirtió en una biblioteca estructurada (plantilla + ejemplo) y
el guionista de cortos recibe ~20 plantillas AFINES AL TEMA para abrir el
video adaptando la mejor — en vez de un «gancho demoledor» en abstracto.

T1  La biblioteca es válida: ≥900 ganchos, todos con plantilla, sin huecos
    [así] en los ejemplos (señal de mal parseo del PDF).
T2  pick_for: afinidad temática real (un tema de dinero recibe ganchos de
    dinero), variedad, determinismo por semilla y distinción entre semillas.
T3  prompt_block genera el bloque para el guionista; sin biblioteca devuelve
    vacío (la fase de guion no depende de que exista el archivo).
T4  Integración real en la fase de guion: en un proyecto VERTICAL el prompt
    lleva los ganchos; en uno HORIZONTAL (video largo) NO — cero cambios al
    flujo original.
T5  El guion con narración propia (transcripción) no pasa por el LLM ni por
    los ganchos (se respeta la voz grabada, como siempre).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


import re

from ytstudio import hooks

print("T1 biblioteca válida")
all_hooks = hooks.load()
check("hay al menos 900 ganchos", len(all_hooks) >= 900, str(len(all_hooks)))
check("todos tienen plantilla no vacía",
      all(h.get("plantilla") for h in all_hooks))
bad = [h for h in all_hooks if re.search(r"\[[^\]]+\]", h.get("ejemplo", ""))]
check("ningún ejemplo trae huecos [así] (señal de mal parseo)",
      not bad, str(bad[:2]))
with_ex = sum(1 for h in all_hooks if h.get("ejemplo"))
check("la gran mayoría trae ejemplo concreto", with_ex >= 900, str(with_ex))
check("ids únicos y consecutivos",
      [h["id"] for h in all_hooks] == list(range(1, len(all_hooks) + 1)))

print("T2 selección por afinidad + variedad determinista")
tema_dinero = ("cómo ahorrar dinero e invertir para lograr libertad "
               "financiera pagando tus deudas")
sel = hooks.pick_for(tema_dinero, n=20, seed="proyecto-1")
check("devuelve exactamente 20", len(sel) == 20, str(len(sel)))
money_words = ("dinero", "financier", "invertir", "deuda", "ahorr", "€", "$")
affine = sum(1 for h in sel
             if any(w in (h["plantilla"] + h["ejemplo"]).lower()
                    for w in money_words))
check("una parte sustancial es afín al tema (dinero)", affine >= 5,
      f"{affine}/20")
ids_a = [h["id"] for h in hooks.pick_for(tema_dinero, n=20, seed="proyecto-1")]
ids_b = [h["id"] for h in hooks.pick_for(tema_dinero, n=20, seed="proyecto-1")]
ids_c = [h["id"] for h in hooks.pick_for(tema_dinero, n=20, seed="proyecto-2")]
check("misma semilla → misma selección (reproducible)", ids_a == ids_b)
check("semilla distinta → selección distinta (variedad entre proyectos)",
      ids_a != ids_c)

print("T3 bloque de prompt y tolerancia a biblioteca ausente")
block = hooks.prompt_block(tema_dinero, seed="p1")
check("el bloque contiene plantillas y la instrucción de adaptar",
      "GANCHOS VIRALES" in block and "PRIMERA FRASE" in block
      and block.count("- ") >= 15, block[:120])
orig = hooks.HOOKS_PATH
try:
    hooks.HOOKS_PATH = Path("/no/existe.json")
    hooks.load.cache_clear()
    check("sin biblioteca: lista vacía y bloque vacío (no bloquea nada)",
          hooks.load() == [] and hooks.prompt_block("x") == "")
finally:
    hooks.HOOKS_PATH = orig
    hooks.load.cache_clear()

print("T4 integración en la fase de guion (vertical sí, largo no)")
from ytstudio.phases import script as script_phase


class _FakeLLM:
    is_mock = False

    def __init__(self):
        self.calls = []

    def complete(self, system, prompt, max_tokens=None, purpose=None):
        self.calls.append({"system": system, "prompt": prompt})
        return "## Narración\nGuion de prueba."


class _Proj:
    slug = "test-hooks"

    def __init__(self):
        self.data = {"brief": {"input_type": "topic", "topic": "ahorrar dinero",
                               "summary": "libertad financiera", "key_points": [],
                               "raw_text": ""},
                     "concept": {"angle": "finanzas personales", "tone": "directo",
                                 "audience": "jóvenes", "structure": ["Gancho", "Cierre"],
                                 "duration_minutes": 1,
                                 "visual_style": {"prompt_prefix": "x"}}}
        self.written = {}

    def get(self, k, d=None):
        return self.data.get(k, d)

    def set(self, k, v):
        self.data[k] = v

    def path(self, key, *parts):
        import tempfile
        base = Path(tempfile.gettempdir()) / "t340" / key
        base.mkdir(parents=True, exist_ok=True)
        return base.joinpath(*parts)


import ytstudio.providers as providers_mod

cfg_vert = {"video": {"width": 1080, "height": 1920, "target_minutes": 1},
            "language": "es", "providers": {"llm": {"name": "anthropic"}}}
cfg_horiz = {"video": {"width": 1920, "height": 1080, "target_minutes": 10},
             "language": "es", "providers": {"llm": {"name": "anthropic"}}}

orig_get_llm = script_phase.get_llm
try:
    fake = _FakeLLM()
    script_phase.get_llm = lambda cfg: fake
    script_phase.run(_Proj(), cfg_vert)
    vert_prompt = fake.calls[-1]["prompt"]
    check("proyecto VERTICAL: el prompt lleva la biblioteca de ganchos",
          "GANCHOS VIRALES" in vert_prompt)
    check("los ganchos elegidos son afines al tema del proyecto",
          any(w in vert_prompt.lower() for w in ("dinero", "financier")),
          vert_prompt[-300:])
    script_phase.run(_Proj(), cfg_horiz)
    long_prompt = fake.calls[-1]["prompt"]
    check("proyecto LARGO (16:9): el prompt NO cambia (sin ganchos)",
          "GANCHOS VIRALES" not in long_prompt)
finally:
    script_phase.get_llm = orig_get_llm

print("T5 narración propia: ni LLM ni ganchos (la voz grabada manda)")
try:
    fake2 = _FakeLLM()
    script_phase.get_llm = lambda cfg: fake2
    p = _Proj()
    p.data["narration"] = {"segments": [{"start": 0, "end": 1, "text": "hola"}]}
    p.data["brief"]["raw_text"] = "hola este es mi guion grabado"
    script_phase.run(p, cfg_vert)
    check("con narración propia no se llama al LLM", fake2.calls == [])
finally:
    script_phase.get_llm = orig_get_llm

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
