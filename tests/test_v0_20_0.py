"""Batería v0.20.0: gasto real (usage.py) propagado a hilos paralelos,
persistencia acumulada (pipeline._persist_usage), progreso %/ETA en vivo
(server._run_progress), rango de costo LLM angostado y campo display_name en
project_detail (fix del renombrado que no se veía en el panel principal)."""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import sys
import tempfile
import time
from pathlib import Path



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_v0200_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
from ytstudio.project import Project

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 usage.py: bind() propaga el acumulador a hilos de un pool")
from ytstudio import usage
from concurrent.futures import ThreadPoolExecutor

usage.reset()
shared = usage.get_state()
usage.record("anthropic", "llm", 100, "tokens", 0.01)


def worker(i):
    usage.bind(shared)  # como hacen broll.py/voiceover.py al entrar al hilo
    usage.record("openai", f"imagen{i}", 1, "img", 0.045)


with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(worker, range(10)))

s = usage.summary()
check("las 10 imágenes generadas EN OTROS HILOS se contabilizaron",
      sum(e["usd"] for e in s["by_provider"] if e["provider"] == "openai") > 0.44,
      str(s))
check("el registro del hilo principal también está", any(
    e["provider"] == "anthropic" for e in s["by_provider"]), str(s))
check("total correcto", abs(s["total_usd"] - (0.01 + 10 * 0.045)) < 0.001, str(s))

print("T2 broll.py: la generación en paralelo SÍ contabiliza el gasto real")
from ytstudio.phases import broll
from ytstudio.phases.scenes import save_scenes as _save


class _FakeImages:
    def __init__(self, cfg):
        pass

    def generate(self, prompt, out):
        from PIL import Image
        Image.new("RGB", (8, 8)).save(out)
        usage.record("openai", "imagen", 1, "img", 0.045)


import ytstudio.phases.broll as broll_mod
orig_get_images, orig_get_llm = broll_mod.get_images, broll_mod.get_llm


class _MockLLM:
    is_mock = True


broll_mod.get_images = lambda cfg: _FakeImages(cfg)
broll_mod.get_llm = lambda cfg: _MockLLM()

p = Project("t0200")
bcfg = {"language": "es", "video": {"width": 320, "height": 180, "fps": 24},
        "providers": {"llm": {"name": "mock"}, "images": {"name": "openai"},
                      "videogen": {"name": "none"}},
        "performance": {"parallel_images": 4, "parallel_video": 1}}
bscenes = [{"id": i, "section": "s", "narration": f"n{i}",
           "broll_prompt": f"p{i}", "broll_type": "image", "animation": "static",
           "duration": 3} for i in range(1, 9)]
_save(p, bscenes)
usage.reset()
broll_shared = usage.get_state()
try:
    broll.run(p, bcfg)
finally:
    broll_mod.get_images, broll_mod.get_llm = orig_get_images, orig_get_llm

check("8 imágenes generadas EN PARALELO se contabilizaron todas",
      len([x for x in broll_shared if x["provider"] == "openai"]) == 8,
      str(len(broll_shared)))

print("T3 pipeline._persist_usage: se acumula entre ejecuciones (reanudar)")
from ytstudio import pipeline

p2 = Project("t0200b")
usage.reset()
usage.record("anthropic", "guion", 5000, "tokens", 0.05)
pipeline._persist_usage(p2, 42.5)
tr1 = p2.get("time_report")
check("primera ejecución: total == última", tr1["total_seconds"] == 42.5 == tr1["last_run_seconds"])
ui1 = p2.get("usage_items")
check("primera ejecución: 1 registro guardado", len(ui1) == 1)

usage.reset()
usage.record("openai", "imagen", 1, "img", 0.05)
pipeline._persist_usage(p2, 30.0)
tr2 = p2.get("time_report")
check("segunda ejecución: el tiempo se SUMA (no se reemplaza)",
      abs(tr2["total_seconds"] - 72.5) < 0.01, str(tr2))
check("segunda ejecución: last_run_seconds es SOLO esta corrida",
      tr2["last_run_seconds"] == 30.0)
ui2 = p2.get("usage_items")
check("los registros de ambas ejecuciones conviven",
      len(ui2) == 2 and {x["provider"] for x in ui2} == {"anthropic", "openai"})

print("T4 server._run_progress: % y ETA en vivo, consistentes con el estimado")
from ytstudio.webui import server

server.RUNS["t0200c"] = {"running": True, "lines": [], "error": None,
                         "phase": "broll", "run_start": time.time() - 30,
                         "est_total_sec": 120.0}
prog = server._run_progress("t0200c")
check("percent ~25% a los 30s de 120s estimados",
      20 <= prog["percent"] <= 30, str(prog))
check("eta ~90s restantes", 80 <= prog["eta_seconds"] <= 95, str(prog))

server.RUNS["t0200d"] = {"running": False, "lines": [], "error": None, "phase": None}
prog2 = server._run_progress("t0200d")
check("sin ejecución en curso -> percent None", prog2["percent"] is None, str(prog2))

print("T5 rango de costo LLM angostado (antes 0.8x-1.8x = 2.25x de ancho)")
from ytstudio.estimate import estimate

p3 = Project("t0200e")
p3.set("scene_count", 20)
p3.set("total_duration", 600)
ecfg = {"providers": {"llm": {"name": "anthropic", "model": "claude-opus-4-8"},
                      "images": {"name": "mock"}, "videogen": {"name": "none"},
                      "tts": {"name": "mock"}, "stt": {"name": "mock"},
                      "music": {"name": "mock"}},
        "video": {"target_minutes": 10, "scene_seconds": 6},
        "performance": {}, "reference": {}}
import os
had_key = os.environ.get("ANTHROPIC_API_KEY")
os.environ["ANTHROPIC_API_KEY"] = "sk-test-fake"
try:
    e = estimate(p3, ecfg)
finally:
    if had_key is None:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    else:
        os.environ["ANTHROPIC_API_KEY"] = had_key
llm_item = next(i for i in e["items"] if "Inteligencia" in i["fase"])
lo, hi = llm_item["costo"]
check("rango LLM angosto (hi/lo <= 1.3, antes ~2.25)", lo > 0 and hi / lo <= 1.3,
      f"lo={lo} hi={hi} ratio={hi/lo if lo else None}")
check("total_costo_medio presente y entre el rango total",
      "total_costo_medio" in e and e["total_costo"][0] <= e["total_costo_medio"] <= e["total_costo"][1],
      str(e.get("total_costo_medio")))
check("total_min_medio presente", "total_min_medio" in e)

print("T6 renombrar: display_name viaja en project_detail (lo que faltaba en el panel)")
p4 = Project.create("t0200f")
server.api_rename_project("t0200f", {"name": "Mi Video Épico"})
detail = server.api_project_detail("t0200f")
check("api_project_detail trae el display_name actualizado",
      detail["display_name"] == "Mi Video Épico", str(detail.get("display_name")))

print("T7 pricing.py compartido: mismos números en estimate y usage real")
from ytstudio import pricing

check("llm_price conocido", pricing.llm_price("claude-opus-4-8") == (5.0, 25.0))
check("llm_price desconocido cae al default", pricing.llm_price("modelo-random") == pricing.LLM_DEFAULT_PRICE)
check("img_cost_mid coherente con IMG_COST", abs(pricing.img_cost_mid("openai") - 0.16) < 0.001)
check("stt_cost proporcional a minutos", abs(pricing.stt_cost(10) - 0.06) < 1e-6)

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
