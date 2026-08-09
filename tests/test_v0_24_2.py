"""Batería v0.24.2: ETA/porcentaje acotado a las fases realmente solicitadas.

T1: estimate() devuelve phase_seconds con TODAS las fases que tienen costo,
    y cada una respeta el piso de 5s.
T2: pedir "hasta scenes" (to_phase temprano) da un estimado MUCHO menor que
    pedir "hasta publish" (video completo) — reproduce la captura del
    usuario (test-23-alejandro-magno: 1% pero "~22 min restantes").
T3: reanudar con ingest/concept/script ya "done" excluye esos segundos del
    total acotado (igual que run_pipeline salta las fases 'done').
T4: la fórmula de server.api_run (reimplementada aquí con la misma lógica)
    replica ambos casos con datos reales de estimate().
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import sys
from pathlib import Path



from ytstudio.config import load_config
from ytstudio.estimate import estimate
from ytstudio.pipeline import PHASE_ORDER
from ytstudio.project import Project

# Aislamiento: los proyectos de prueba NUNCA se crean en la carpeta real
# projects/ del creador (antes se creaba «__test_v0_24_2__» junto a sus
# proyectos y solo se borraba si el test terminaba bien).
import tempfile as _tf
import ytstudio.project as _prj
_prj.PROJECTS_DIR = Path(_tf.mkdtemp(prefix="ytstudio_t0242_")) / "projects"

TMP_SLUG = "__test_v0_24_2__"
proj_dir = Project(TMP_SLUG).dir
if proj_dir.exists():
    shutil.rmtree(proj_dir)

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def scoped_seconds(_est, _proj, from_phase, to_phase):
    """Misma lógica que server.api_run: suma phase_seconds SOLO entre
    from_phase..to_phase, saltando las fases ya 'done'."""
    phase_secs = _est.get("phase_seconds") or {}
    lo = PHASE_ORDER.index(from_phase) if from_phase in PHASE_ORDER else 0
    hi = (PHASE_ORDER.index(to_phase) if to_phase in PHASE_ORDER
          else len(PHASE_ORDER) - 1)
    return sum(float(phase_secs.get(name, 0.0))
               for name in PHASE_ORDER[lo:hi + 1]
               if _proj.phase_status(name) != "done")


print("T1 phase_seconds cubre todas las fases con costo, con piso de 5s")
proj = Project.create(TMP_SLUG) if hasattr(Project, "create") else Project(TMP_SLUG)
proj.set("total_duration", 120)  # 2 min de video -> escenas reales
proj.set("scene_count", 20)
cfg = load_config(proj.dir)
est = estimate(proj, cfg)
ps = est["phase_seconds"]
print(f"     phase_seconds = { {k: round(v,1) for k,v in ps.items()} }")
check("hay al menos las fases típicas (script, scenes, voiceover, broll, assembly)",
      {"script", "scenes", "voiceover", "broll", "assembly"} <= set(ps),
      str(ps.keys()))
check("cada fase con trabajo respeta el piso de 5s",
      all(v >= 5.0 - 0.01 for v in ps.values()), str(ps))

print("T2 'hasta scenes' << 'hasta publish' (reproduce la captura del usuario)")
sec_early = scoped_seconds(est, proj, None, "scenes")
sec_full = scoped_seconds(est, proj, None, "publish")
print(f"     hasta scenes: {sec_early:.1f}s  |  hasta publish: {sec_full:.1f}s")
check("el estimado acotado a una fase temprana es MENOR que el del video completo",
      sec_early < sec_full, f"{sec_early} vs {sec_full}")
check("la fase temprana no incluye tiempo de broll/voiceover/assembly (fases futuras)",
      sec_early < sec_full * 0.5, f"{sec_early} vs {sec_full}")

print("T3 reanudar con fases ya 'done' las excluye del total acotado")
proj.mark_phase("ingest", "done", seconds=1)
proj.mark_phase("concept", "done", seconds=1)
proj.mark_phase("script", "done", seconds=1)
sec_resume = scoped_seconds(est, proj, None, "publish")
check("el total tras reanudar es menor que el total completo original",
      sec_resume < sec_full, f"{sec_resume} vs {sec_full}")
expected_drop = ps.get("ingest", 0) + ps.get("concept", 0) + ps.get("script", 0) * 0.0
# script se reparte con _LLM_SPLIT pero el LLM ya se ejecutó como un bloque:
# igual se descuenta su fracción, que es lo correcto (no se re-cobra ni
# re-cuenta tiempo de una fase ya completada al reanudar).
check("las fases 'done' (ingest, concept, script) no aportan al total acotado",
      abs(sec_resume - (sec_full - ps.get("ingest", 0) - ps.get("concept", 0)
                        - ps.get("script", 0))) < 0.5,
      f"resume={sec_resume} full={sec_full} ps={ps}")

print("T4 from_phase explícito también acota correctamente (reanudar desde voiceover)")
sec_from_voice = scoped_seconds(est, proj, "voiceover", "publish")
check("acotar desde voiceover excluye ingest/concept/script/scenes",
      sec_from_voice < sec_full - ps.get("scenes", 0),
      f"{sec_from_voice} vs {sec_full}")

shutil.rmtree(proj_dir, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
