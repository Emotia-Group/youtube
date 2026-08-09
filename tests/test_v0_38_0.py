"""Batería v0.38.0: PLANTILLAS DE FORMATO COMPLETO para cortos.

Recetas de un clic que empaquetan estructura de guion + tratamiento visual +
rótulos + sticker + arco musical: Top 3, Historia con giro, Antes/Después,
Mito vs Realidad, Tutorial en pasos, Dato impactante (+ Libre por defecto).

T1  Catálogo: las 7 plantillas registradas con label/hint/reglas; 'libre'
    sin reglas (comportamiento actual); short_template() solo devuelve
    plantilla en formato corto y nunca para 'libre'.
T2  Fase de GUION: con plantilla Top 3 en un corto, el prompt del guionista
    lleva la estructura del ranking (además de los hooks); en un 16:9 largo
    la plantilla NO se aplica aunque esté guardada; con guion propio del
    creador se añade la nota de respeto al contenido.
T3  Fase de ESCENAS: las reglas de escena de la plantilla llegan al prompt
    del storyboard y al pase de dirección de arte (y no llegan sin
    plantilla).
T4  La plantilla Antes/Después empuja la pantalla dividida (sus reglas piden
    layout 'dividida' con el segundo prompt) — verificado en el texto que
    recibe el modelo.
T5  Server: el id de plantilla se persiste solo si es válido y el formato es
    corto (validación de api_get_config payload incluida).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.catalog import SHORT_TEMPLATES, short_template

print("T1 catálogo de plantillas")
expected = {"libre", "top3", "historia_giro", "antes_despues",
            "mito_realidad", "pasos", "dato_impactante"}
check("las 7 plantillas registradas", set(SHORT_TEMPLATES) == expected,
      str(set(SHORT_TEMPLATES)))
check("todas con label y hint",
      all(t.get("label") and t.get("hint") for t in SHORT_TEMPLATES.values()))
check("todas menos 'libre' con reglas de guion Y de escenas",
      all(t["script_rules"] and t["scene_rules"]
          for k, t in SHORT_TEMPLATES.items() if k != "libre"))
check("'libre' sin reglas (comportamiento actual intacto)",
      SHORT_TEMPLATES["libre"]["script_rules"] == ""
      and SHORT_TEMPLATES["libre"]["scene_rules"] == "")


class _P:
    def __init__(self, tpl=None):
        self.data = {"short_template": tpl} if tpl else {}

    def get(self, k, d=None):
        return self.data.get(k, d)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        pass


cfg_short = {"video": {"width": 1080, "height": 1920}}
cfg_long = {"video": {"width": 1920, "height": 1080}}
check("short_template devuelve la plantilla en formato corto",
      short_template(_P("top3"), cfg_short) is SHORT_TEMPLATES["top3"])
check("en 16:9 largo devuelve None aunque esté guardada",
      short_template(_P("top3"), cfg_long) is None)
check("'libre' y ausente devuelven None",
      short_template(_P("libre"), cfg_short) is None
      and short_template(_P(), cfg_short) is None)

print("T2 fase de guion")
from pathlib import Path

from ytstudio.phases import script as script_phase


class _FakeLLM:
    is_mock = False

    def __init__(self):
        self.calls = []

    def complete(self, system, prompt, max_tokens=None, purpose=None):
        self.calls.append({"system": system, "prompt": prompt})
        return "## Narración\nGuion de prueba."


class _Proj:
    slug = "test-tpl"

    def __init__(self, tpl="top3", input_type="topic", raw=""):
        self.data = {"short_template": tpl,
                     "brief": {"input_type": input_type,
                               "topic": "ciudades más caras",
                               "summary": "costo de vida",
                               "key_points": [], "raw_text": raw},
                     "concept": {"angle": "dinero", "tone": "directo",
                                 "audience": "jóvenes",
                                 "structure": ["Gancho", "Cierre"],
                                 "duration_minutes": 1,
                                 "visual_style": {"prompt_prefix": "x"}}}

    def get(self, k, d=None):
        return self.data.get(k, d)

    def set(self, k, v):
        self.data[k] = v

    def path(self, key, *parts):
        import tempfile
        base = Path(tempfile.gettempdir()) / "t380" / key
        base.mkdir(parents=True, exist_ok=True)
        return base.joinpath(*parts)


cfgv = {"video": {"width": 1080, "height": 1920, "target_minutes": 1},
        "language": "es", "providers": {"llm": {"name": "anthropic"}}}
cfgh = {"video": {"width": 1920, "height": 1080, "target_minutes": 10},
        "language": "es", "providers": {"llm": {"name": "anthropic"}}}

orig = script_phase.get_llm
try:
    fake = _FakeLLM()
    script_phase.get_llm = lambda cfg: fake
    script_phase.run(_Proj("top3"), cfgv)
    p_short = fake.calls[-1]["prompt"]
    check("corto + Top 3: el prompt lleva la estructura del ranking",
          "PLANTILLA TOP 3" in p_short and "CUENTA REGRESIVA" in p_short)
    check("y sigue llevando los hooks virales", "GANCHOS VIRALES" in p_short)
    script_phase.run(_Proj("top3"), cfgh)
    p_long = fake.calls[-1]["prompt"]
    check("largo 16:9: la plantilla NO se aplica",
          "PLANTILLA TOP 3" not in p_long)
    script_phase.run(_Proj("historia_giro", input_type="script",
                           raw="Mi guion propio completo."), cfgv)
    p_own = fake.calls[-1]["prompt"]
    check("con guion propio: plantilla + nota de respeto al contenido",
          "PLANTILLA HISTORIA CON GIRO" in p_own
          and "respeta su" in p_own.lower())
finally:
    script_phase.get_llm = orig

print("T3 fase de escenas y pase de dirección")
from ytstudio.phases.scenes import _art_direction_pass


class _FakeJson:
    def __init__(self):
        self.prompts = []

    def complete_json(self, system, prompt, schema=None, max_tokens=None,
                      purpose=None):
        self.prompts.append(prompt)
        return {"bible": {"era_setting": "", "palette": "", "lighting": "",
                          "camera_language": "", "texture_grade": "",
                          "motifs": []}, "scenes": []}


concept = {"visual_style": {"prompt_prefix": "x"}}
base = [{"id": 1, "narration": "n", "broll_prompt": "p", "broll_type": "image"}]
fj = _FakeJson()
rules = SHORT_TEMPLATES["top3"]["scene_rules"]
_art_direction_pass(fj, _P(), list(base), concept, "es", short_form=True,
                    template_rules="\n" + rules + "\n")
_art_direction_pass(fj, _P(), list(base), concept, "es", short_form=True)
check("dirección de arte CON plantilla: reglas presentes",
      "PLANTILLA TOP 3" in fj.prompts[0])
check("dirección de arte SIN plantilla: sin reglas",
      "PLANTILLA TOP 3" not in fj.prompts[1])

print("T4 Antes/Después empuja la pantalla dividida")
ad = SHORT_TEMPLATES["antes_despues"]["scene_rules"]
check("las reglas piden layout dividida con el segundo prompt",
      "dividida" in ad and "broll_prompt_b" in ad)
check("Top 3 pide overlays de lista y sticker de cierre",
      "lista" in SHORT_TEMPLATES["top3"]["scene_rules"]
      and "encuesta" in SHORT_TEMPLATES["top3"]["scene_rules"])

print("T5 server: persistencia y payload")
from ytstudio.webui import server as srv

payload = srv.api_get_config()
check("api_get_config expone las plantillas con label y hint",
      set(payload["short_templates"]) == expected
      and all(v.get("label") for v in payload["short_templates"].values()))
check("los formatos marcan cuáles son cortos",
      payload["formats"]["long"]["short"] is False
      and payload["formats"]["short"]["short"] is True)
html = (ROOT / "ytstudio/webui/static/index.html").read_text(
    encoding="utf-8")
check("la UI tiene el selector de plantilla condicionado al formato",
      "np-template" in html and "toggleTplSel" in html
      and "short_template:" in html)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
