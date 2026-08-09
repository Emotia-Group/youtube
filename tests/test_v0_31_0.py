"""Batería v0.31.0: pase de DIRECCIÓN DE ARTE global + auditoría de
movimiento para escenas de video IA.

Pedido del usuario: la coherencia y el detalle no deben decidirse solo
escena a escena — un segundo pase lee el storyboard COMPLETO y unifica
biblia visual (época, paleta, luz, cámara, textura, motivos), prompts con
detalle profesional, rótulos/transiciones/sfx/música como SISTEMA, y audita
el riesgo de artefactos de movimiento en las escenas de video IA
(reescribiendo los prompts riesgosos hacia movimiento de cámara/atmósfera).

T1  DIRECTION_SCHEMA es compatible con la API de structured output
    (check_schema, la lección de v0.29.1).
T2  Con un LLM real (simulado con respuestas controladas): los prompts se
    reescriben casándolos POR ID (aunque vengan en otro orden), la biblia
    queda guardada en el proyecto, la escena no devuelta conserva su prompt,
    el id desconocido se ignora, el riesgo de movimiento queda por escena y
    la escena de VIDEO con riesgo alto se reporta; los campos creativos
    ajustados sobreviven a _normalize_creative.
T3  El prompt que se envía al modelo contiene el storyboard completo (todas
    las narraciones + prompts actuales), las reglas creativas y el prefijo
    de estilo — el análisis es de TODO el guion, no por escena.
T4  Si el modelo falla, la fase NO se rompe: se conservan las decisiones del
    primer pase y queda un aviso.
T5  Con el modelo simulado (mock, modo preview) el pase se omite (no hay
    criterio global que aplicar sin modelo real).
T6  El storyboard.md incluye la biblia visual y el riesgo de movimiento.
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


from ytstudio.phases.scenes import (
    DIRECTION_SCHEMA, _art_direction_pass, _normalize_creative,
)
from ytstudio.providers.llm import check_schema

print("T1 esquema del pase de dirección compatible con structured output")
try:
    check_schema(DIRECTION_SCHEMA)
    check("DIRECTION_SCHEMA pasa el validador de esquemas", True)
except ValueError as e:
    check("DIRECTION_SCHEMA pasa el validador de esquemas", False, str(e))


class _StubProject:
    def __init__(self):
        self.data = {}
        self.warnings = []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def add_warning(self, msg):
        self.warnings.append(msg)


def make_scenes():
    base = {"overlay_type": "ninguno", "overlay_text": "",
            "overlay_kicker": "", "overlay_emphasis": "",
            "music_intensity": 0.5, "pause_after": 0, "pace": "normal",
            "sfx": "ninguno", "transition": "corte"}
    return [
        {"id": 1, "section": "Gancho", "narration": "Nace un imperio.",
         "broll_prompt": "old prompt 1", "broll_type": "video",
         "animation": "zoom_in", **base},
        {"id": 2, "section": "Gancho", "narration": "El rey avanza.",
         "broll_prompt": "old prompt 2", "broll_type": "image",
         "animation": "pan_left", **base},
        {"id": 3, "section": "Auge", "narration": "La batalla decisiva.",
         "broll_prompt": "old prompt 3", "broll_type": "image",
         "animation": "zoom_out", **base},
    ]


BIBLE = {"era_setting": "Macedonia, siglo IV a. C.",
         "palette": "bronce, ocre y azul noche",
         "lighting": "sol bajo lateral, antorchas",
         "camera_language": "gran angular bajo, medios compresivos",
         "texture_grade": "grano fino 35mm, contraste cálido",
         "motifs": ["águila dorada", "polvo en contraluz"]}


def _dir_scene(sid, prompt, risk="baja", **over):
    d = {"id": sid, "broll_prompt": prompt, "motion_risk": risk,
         "overlay_type": "ninguno", "overlay_text": "", "overlay_kicker": "",
         "overlay_emphasis": "", "music_intensity": 0.6, "pause_after": 0,
         "pace": "normal", "sfx": "ninguno", "transition": "corte"}
    d.update(over)
    return d


class _FakeLLM:
    """LLM 'real' (is_mock ausente) con respuesta controlada: ejercita el
    código de aplicación del pase tal cual corre en producción."""

    def __init__(self, result=None, raise_exc=None):
        self.result = result
        self.raise_exc = raise_exc
        self.calls = []

    def complete_json(self, system, prompt, schema=None, max_tokens=None,
                      purpose=None):
        self.calls.append({"system": system, "prompt": prompt,
                           "schema": schema, "purpose": purpose})
        check_schema(schema)  # como hace el cliente real desde v0.29.1
        if self.raise_exc:
            raise self.raise_exc
        return self.result


print("T2 aplicación del pase: por id, con biblia, riesgo y conservación")
concept = {"visual_style": {"prompt_prefix": "cinematic documentary still"}}
scenes = make_scenes()
project = _StubProject()
llm = _FakeLLM(result={
    "bible": BIBLE,
    "scenes": [
        # desordenadas a propósito (el casado debe ser POR ID, no por índice)
        _dir_scene(3, "cinematic documentary still, new battle prompt",
                   risk="baja", overlay_type="dato", overlay_text="40 000",
                   overlay_kicker="EJÉRCITO", sfx="boom",
                   transition="fundido", music_intensity=0.9),
        _dir_scene(1, "cinematic documentary still, slow dolly through dust, "
                      "king motionless in heroic pose", risk="alta"),
        _dir_scene(99, "prompt de un id inexistente"),
        # la escena 2 NO se devuelve → debe conservar su prompt original
    ],
})
from ytstudio import progress
notices = []
progress.set_sink(notices.append)

_art_direction_pass(llm, project, scenes, concept, "español")
check("prompt de la escena 1 reescrito (casado por id, no por orden)",
      "slow dolly" in scenes[0]["broll_prompt"], scenes[0]["broll_prompt"])
check("prompt de la escena 3 reescrito",
      "new battle prompt" in scenes[2]["broll_prompt"])
check("la escena 2 (no devuelta) conserva el prompt del primer pase",
      scenes[1]["broll_prompt"] == "old prompt 2", scenes[1]["broll_prompt"])
check("la biblia visual queda guardada en el proyecto",
      project.get("art_direction") == BIBLE,
      str(project.get("art_direction")))
check("motion_risk queda por escena",
      scenes[0].get("motion_risk") == "alta"
      and scenes[2].get("motion_risk") == "baja")
check("aviso de auditoría: la escena 1 (video, riesgo alto) se reporta",
      any("riesgo alto" in n and "1" in n for n in notices),
      str(notices))
check("sin avisos de fallo", not project.warnings, str(project.warnings))

_normalize_creative(scenes)
check("los ajustes creativos sobreviven a la normalización "
      "(rótulo de dato + sfx boom + fundido en la escena 3)",
      scenes[2].get("overlay", {}) and scenes[2]["overlay"]["type"] == "dato"
      and scenes[2]["sfx"] == "boom" and scenes[2]["transition"] == "fundido",
      str({k: scenes[2].get(k) for k in ("overlay", "sfx", "transition")}))
check("music_intensity ajustada y acotada", scenes[2]["music_intensity"] == 0.9)

print("T3 el análisis es de TODO el guion (no escena a escena)")
sent = llm.calls[0]["prompt"]
check("el prompt enviado incluye TODAS las narraciones",
      all(s in sent for s in ("Nace un imperio.", "El rey avanza.",
                              "La batalla decisiva.")))
check("incluye los prompts actuales para revisarlos",
      "old prompt 1" in sent and "old prompt 3" in sent)
check("incluye las reglas creativas globales (rótulos/música/sfx/transición)",
      "RÓTULOS EN PANTALLA" in sent and "TRANSICIÓN" in sent)
check("exige el prefijo de estilo en los prompts",
      "cinematic documentary still" in sent)
check("marca cuáles escenas son VIDEO IA para la auditoría de movimiento",
      "VIDEO IA (con movimiento)" in sent)
check("propósito de gasto etiquetado como 'direction'",
      llm.calls[0]["purpose"] == "direction")

print("T4 si el modelo falla, la fase no se rompe")
scenes2 = make_scenes()
project2 = _StubProject()
bad = _FakeLLM(raise_exc=RuntimeError("timeout simulado"))
_art_direction_pass(bad, project2, scenes2, concept, "español")
check("los prompts del primer pase quedan intactos",
      [s["broll_prompt"] for s in scenes2] ==
      ["old prompt 1", "old prompt 2", "old prompt 3"])
check("queda un aviso claro del pase omitido",
      any("dirección de arte" in w for w in project2.warnings),
      str(project2.warnings))

print("T5 con el modelo simulado (preview) el pase se omite")


class _MockLLM:
    is_mock = True

    def complete_json(self, *a, **k):
        raise AssertionError("no debe llamarse en modo mock")


scenes3 = make_scenes()
_art_direction_pass(_MockLLM(), _StubProject(), scenes3, concept, "español")
check("sin llamadas ni cambios en modo preview",
      scenes3[0]["broll_prompt"] == "old prompt 1")

print("T6 storyboard.md incluye biblia visual y riesgo de movimiento")
import tempfile
from pathlib import Path

from ytstudio.phases.scenes import _write_outputs


class _FsProject(_StubProject):
    def __init__(self, root):
        super().__init__()
        self.root = Path(root)

    def path(self, *parts):
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


with tempfile.TemporaryDirectory() as td:
    fsp = _FsProject(td)
    fsp.set("art_direction", BIBLE)
    sc = make_scenes()
    sc[0]["motion_risk"] = "alta"
    _normalize_creative(sc)
    _write_outputs(fsp, sc)
    board = (Path(td) / "scenes" / "storyboard.md").read_text(encoding="utf-8")
    check("biblia visual en el storyboard",
          "Dirección de arte" in board and "águila dorada" in board)
    check("riesgo de movimiento visible por escena",
          "riesgo alta" in board)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
