"""Batería v0.33.0: TOPE DE GASTO DINÁMICO + punto de control del storyboard.

Problema que resuelve (planteado por el usuario): un tope FIJO no puede
servir a dos propósitos opuestos. $8 es enorme para una prueba de 3 escenas
—donde un fallo en bucle se comió $11.85 sin que nada lo frenara— y demasiado
pequeño para un documental de 15 min con personaje narrador, que
legítimamente cuesta ~$40 y quedaría interrumpido sin motivo.

Solución: el tope se calcula de la estimación de lo que FALTA por generar,
por un margen, con piso mínimo y techo manual opcional; y se RECALCULA antes
de cada fase (tras «Escenas» la estimación ya es exacta).

T1  El tope escala con el tamaño real del proyecto: la prueba corta del
    usuario queda con un tope PEQUEÑO y el documental de 15 min con uno
    HOLGADO — con la misma configuración, sin tocar nada.
T2  Con los números REALES de la pérdida ($11.85 en 5 predicciones de una
    prueba de 3 escenas), el tope dinámico habría frenado el sangrado mucho
    antes; el tope fijo de $8 no.
T3  El documental de 15 min con lipsync NO se interrumpe (el caso que el
    usuario temía): el tope queda por encima de su costo estimado alto.
T4  Piso mínimo: un proyecto diminuto no queda con un tope hipersensible.
T5  Techo manual: manda solo si es MÁS restrictivo (candado, no permiso).
T6  El tope se calcula sobre lo PENDIENTE: las fases ya completadas no lo
    inflan (reanudar no vuelve a pagar lo hecho).
T7  Recalcular a mitad de corrida NO borra el gasto ya acumulado (si no, cada
    recálculo regalaría presupuesto nuevo y el freno no serviría).
T8  El punto de control tras «Escenas» sale en el registro con el desglose de
    lo que falta por pagar y dónde revisarlo.
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


import os

os.environ.setdefault("REPLICATE_API_TOKEN", "r8_prueba")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-prueba")

from ytstudio import budget, usage
from ytstudio.estimate import estimate


class _Proj:
    """Proyecto de prueba: solo lo que estimate()/compute_cap() consultan."""

    def __init__(self, data=None, done=()):
        self.data = data or {}
        self.done = set(done)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def phase_status(self, phase):
        return "done" if phase in self.done else "pending"


def cfg_base(**over):
    cfg = {
        "video": {"target_minutes": 10, "scene_seconds": 6,
                  "width": 1920, "height": 1080},
        "providers": {
            "llm": {"name": "anthropic", "model": "claude-opus-4-8"},
            "images": {"name": "replicate",
                       "model": "black-forest-labs/flux-1.1-pro"},
            "videogen": {"name": "none", "model": "kwaivgi/kling-v1.6-standard",
                         "max_scenes": 0},
            "tts": {"name": "mock"}, "stt": {"name": "mock"},
            "music": {"name": "mock"},
            "lipsync": {"name": "replicate", "model": "bytedance/omni-human"},
        },
        "performance": {"parallel_images": 4, "parallel_video": 2,
                        "parallel_render": 2},
        "budget": {"margin": 1.4, "min_usd": 1.5, "max_usd": 0},
    }
    for k, v in over.items():
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) else v
    return cfg


# --- Los dos proyectos reales de la conversación --------------------------
# A) La prueba del usuario: 51s de video, 3 escenas, 1 con personaje lipsync.
PRUEBA = _Proj({"scene_count": 3, "total_duration": 51,
                "character": {"presence": 0.33},
                "assets": [{"category": "personaje", "kind": "image"}]})
# B) Documental de 15 min, mismo montaje con personaje al 30%.
DOC = _Proj({"scene_count": 150, "total_duration": 900,
             "character": {"presence": 0.30},
             "assets": [{"category": "personaje", "kind": "image"}]})

print("T1 el tope escala con el tamaño real del proyecto")
cfg = cfg_base()
cap_prueba = budget.compute_cap(PRUEBA, cfg)
cap_doc = budget.compute_cap(DOC, cfg)
est_prueba = estimate(PRUEBA, cfg)
est_doc = estimate(DOC, cfg)
print(f"     prueba 51s/3 escenas → estimado {est_prueba['total_costo']} · "
      f"tope ${cap_prueba['cap']:.2f}")
print(f"     doc 15min/150 escenas → estimado {est_doc['total_costo']} · "
      f"tope ${cap_doc['cap']:.2f}")
check("la prueba corta queda con un tope pequeño (< $8, el fijo anterior)",
      cap_prueba["cap"] < 8, f"${cap_prueba['cap']:.2f}")
check("el documental queda con un tope holgado (> $8)",
      cap_doc["cap"] > 8, f"${cap_doc['cap']:.2f}")
check("el tope del documental es MUY superior al de la prueba (escala sola)",
      cap_doc["cap"] > cap_prueba["cap"] * 5,
      f"{cap_doc['cap']:.2f} vs {cap_prueba['cap']:.2f}")

print("T2 con los números REALES de la pérdida, el tope dinámico frena antes")
PERDIDA_USD = 11.85     # 5 predicciones de omni-human a $2.37
check("el tope de la prueba corta es MUY inferior a lo que se perdió",
      cap_prueba["cap"] < PERDIDA_USD,
      f"tope ${cap_prueba['cap']:.2f} vs pérdida ${PERDIDA_USD:.2f}")
# Simulación del sangrado real: cobros de $2.37 hasta que el freno actúe.
usage.set_cap(cap_prueba["cap"])
cobros = 0
try:
    for _ in range(10):
        usage.check_budget(2.37, "lipsync")
        usage.add_spend(2.37)
        cobros += 1
except usage.BudgetExceeded:
    pass
gastado = round(cobros * 2.37, 2)
print(f"     con tope dinámico se habrían permitido {cobros} cobros "
      f"(${gastado:.2f}) en vez de 5 (${PERDIDA_USD:.2f})")
check("el freno corta ANTES de llegar a la pérdida real",
      gastado < PERDIDA_USD, f"${gastado:.2f}")
# El tope fijo de $8 habría dejado pasar más
usage.set_cap(8.0)
cobros8 = 0
try:
    for _ in range(10):
        usage.check_budget(2.37, "lipsync")
        usage.add_spend(2.37)
        cobros8 += 1
except usage.BudgetExceeded:
    pass
check("el tope dinámico es más estricto que el fijo de $8 en esta prueba",
      cobros <= cobros8, f"dinámico={cobros} fijo8={cobros8}")

print("T3 el documental de 15 min NO se interrumpe (lo que el usuario temía)")
coste_alto_doc = est_doc["total_costo"][1]
check("el tope supera el costo ALTO estimado del documental completo",
      cap_doc["cap"] >= coste_alto_doc,
      f"tope ${cap_doc['cap']:.2f} < costo ${coste_alto_doc:.2f}")
usage.set_cap(cap_doc["cap"])
ok = True
try:
    # se gasta TODO lo estimado alto, escena a escena
    paso = coste_alto_doc / 150
    for _ in range(150):
        usage.check_budget(paso, "escena")
        usage.add_spend(paso)
except usage.BudgetExceeded:
    ok = False
check("gastar el estimado alto completo NO dispara el freno", ok)

print("T4 piso mínimo: un proyecto diminuto no queda hipersensible")
mini = _Proj({"scene_count": 1, "total_duration": 6})
cap_mini = budget.compute_cap(mini, cfg)
check("el tope nunca baja del piso configurado",
      cap_mini["cap"] >= cfg["budget"]["min_usd"],
      f"${cap_mini['cap']:.2f}")
check("y se explica que actuó el mínimo de seguridad",
      "mínimo de seguridad" in budget.explain(cap_mini)
      or cap_mini["cap"] > cfg["budget"]["min_usd"],
      budget.explain(cap_mini))

print("T5 techo manual: manda solo si es MÁS restrictivo")
cfg_techo = cfg_base(budget={"margin": 1.4, "min_usd": 1.5, "max_usd": 5.0})
cap_lim = budget.compute_cap(DOC, cfg_techo)
check("un techo manual bajo recorta el tope automático alto",
      cap_lim["cap"] == 5.0 and cap_lim["limited_by_manual"],
      str(cap_lim))
check("se explica que el recorte lo puso el techo manual",
      "techo manual" in budget.explain(cap_lim), budget.explain(cap_lim))
cfg_techo_alto = cfg_base(budget={"margin": 1.4, "min_usd": 1.5,
                                  "max_usd": 999.0})
cap_alto = budget.compute_cap(PRUEBA, cfg_techo_alto)
check("un techo manual ALTO no sirve para gastar más de lo automático",
      cap_alto["cap"] == cap_prueba["cap"] and not cap_alto["limited_by_manual"],
      f"{cap_alto['cap']} vs {cap_prueba['cap']}")

print("T6 el tope se calcula sobre lo PENDIENTE (reanudar no lo infla)")
doc_hecho = _Proj(DOC.data, done=("ingest", "concept", "script", "scenes",
                                  "voiceover", "broll"))
cap_resto = budget.compute_cap(doc_hecho, cfg)
check("con el B-roll ya generado el tope baja muchísimo",
      cap_resto["cap"] < cap_doc["cap"] / 5,
      f"${cap_resto['cap']:.2f} vs ${cap_doc['cap']:.2f}")
check("lo pendiente ya no incluye el costo del B-roll",
      cap_resto["pending_high"] < cap_doc["pending_high"] / 5,
      f"{cap_resto['pending_high']} vs {cap_doc['pending_high']}")

print("T7 recalcular a mitad de corrida NO borra el gasto acumulado")
usage.set_cap(10.0)
usage.add_spend(4.0)
usage.set_cap(12.0, reset=False)   # recálculo entre fases
check("el gasto sigue contando tras recalcular",
      abs(usage.spent() - 4.0) < 0.001, str(usage.spent()))
check("y el tope nuevo aplica sobre ese gasto",
      usage.cap() == 12.0, str(usage.cap()))
try:
    usage.check_budget(9.0, "algo caro")
    check("el freno usa gasto acumulado + tope nuevo", False)
except usage.BudgetExceeded:
    check("el freno usa gasto acumulado + tope nuevo", True)
usage.set_cap(10.0)   # reset por defecto sí limpia (corrida nueva)
check("una corrida NUEVA sí arranca el gasto en cero", usage.spent() == 0)

print("T8 punto de control del storyboard en el registro")
from ytstudio.pipeline import _storyboard_checkpoint

lines = []
_storyboard_checkpoint(DOC, cfg, lines.append)
txt = "\n".join(lines)
check("anuncia el punto de control con nº de escenas y duración",
      "PUNTO DE CONTROL" in txt and "150 escenas" in txt, txt[:200])
check("dice dónde revisarlo", "storyboard.md" in txt)
check("muestra lo que falta por pagar y el tope activo",
      "Falta por generar" in txt and "tope $" in txt, txt)
check("desglosa las partidas de pago (imágenes y lipsync)",
      "Imágenes IA" in txt and "lipsync" in txt.lower(), txt)
check("avisa de que corregir aquí es gratis",
      "no cuesta nada" in txt, txt)
lines2 = []
_storyboard_checkpoint(_Proj({"scene_count": 3, "total_duration": 51},
                             done=("broll",)), cfg_base(providers={
                                 "images": {"name": "mock"},
                                 "llm": {"name": "mock"}}), lines2.append)
check("no revienta cuando no queda nada de pago",
      any("PUNTO DE CONTROL" in l for l in lines2), str(lines2))

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
