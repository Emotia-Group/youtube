"""Batería: B-roll manual por escena (subida en Storyboard).

Cubre: validación de tipo (video solo en escena de video; imagen en escena de
video se degrada; video en escena de imagen se rechaza), colocación con
prioridad sobre IA, revisión del director (encaja/no + auto-reemplazo), y que
NADA de esto toca voz/tiempos."""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import base64
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_manual_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
from ytstudio.project import Project
from ytstudio.phases.scenes import save_scenes as _save
from ytstudio.phases import broll as broll_mod
from ytstudio.webui import server

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def png_b64():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (100, 60, 40)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def mp4_b64():
    f = WORK / "clip.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f",
                    "lavfi", "-i", "color=c=green:s=64x36:r=24:d=2", "-c:v",
                    "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    return base64.b64encode(f.read_bytes()).decode()


# Proyecto con 3 escenas: 1=video, 2=imagen, 3=imagen
p = Project.create("mb")
scenes = [
    {"id": 1, "section": "A", "narration": "Escena de video sobre batallas.",
     "broll_prompt": "battle", "broll_type": "video", "animation": "zoom_in",
     "duration": 5.0, "on_screen_text": ""},
    {"id": 2, "section": "B", "narration": "Escena de imagen sobre un mapa.",
     "broll_prompt": "map", "broll_type": "image", "animation": "pan_left",
     "duration": 4.0, "on_screen_text": ""},
    {"id": 3, "section": "C", "narration": "Otra escena de imagen.",
     "broll_prompt": "temple", "broll_type": "image", "animation": "zoom_out",
     "duration": 4.0, "on_screen_text": ""},
]
_save(p, scenes)
# Marca la fase scenes como hecha para que _scene_or_404 encuentre scenes.json
(p.dir / "04_scenes" / "scenes.json").exists()

print("T1 validación de tipo en la subida")
# video en escena de imagen -> rechazado
try:
    server.api_scene_broll_upload("mb", 2, {"file": {"name": "x.mp4", "data_base64": mp4_b64()}})
    check("rechaza video en escena de imagen", False, "no lanzó error")
except server.ApiError as e:
    check("rechaza video en escena de imagen", "imagen fija" in e.message or "no como video" in e.message, e.message)
# imagen en escena de imagen -> ok
r2 = server.api_scene_broll_upload("mb", 2, {"file": {"name": "m.png", "data_base64": png_b64()}})
check("acepta imagen en escena de imagen", r2["ok"] and r2["kind"] == "image")
# video en escena de video -> ok
r1 = server.api_scene_broll_upload("mb", 1, {"file": {"name": "b.mp4", "data_base64": mp4_b64()}})
check("acepta video en escena de video", r1["ok"] and r1["kind"] == "video")
# imagen en escena de video -> ok con downgrade
r1b = server.api_scene_broll_upload("mb", 1, {"file": {"name": "still.png", "data_base64": png_b64()}})
check("acepta imagen en escena de video (con downgrade)", r1b["ok"] and r1b["downgrade"])
# vuelve a poner video en escena 1
server.api_scene_broll_upload("mb", 1, {"file": {"name": "b.mp4", "data_base64": mp4_b64()}})

print("T2 subir resetea SOLO desde broll (no toca guion/voz/escenas)")
# scenes sigue disponible; manual_broll registrado
detail = server.api_project_detail("mb")
check("manual_broll expuesto en el detalle con 2 escenas",
      set(detail["manual_broll"].keys()) == {"1", "2"}, str(detail["manual_broll"]))

print("T3 colocación + prioridad sobre IA (mock LLM = revisión omitida)")
gen_calls = []


class _FakeImages:
    def __init__(self, cfg): pass
    def generate(self, prompt, out):
        from PIL import Image
        Image.new("RGB", (8, 8)).save(out)
        gen_calls.append(out.name)


class _MockLLM:
    is_mock = True


orig_gi, orig_gl, orig_gv = broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen
broll_mod.get_images = lambda cfg: _FakeImages(cfg)
broll_mod.get_llm = lambda cfg: _MockLLM()
broll_mod.get_videogen = lambda cfg: None
bcfg = {"language": "es", "video": {"width": 320, "height": 180, "fps": 24},
        "providers": {"llm": {"name": "mock"}, "images": {"name": "openai"},
                      "videogen": {"name": "none"}},
        "performance": {"parallel_images": 2, "parallel_video": 1}}
p = Project('mb')
try:
    broll_mod.run(p, bcfg)
finally:
    broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen = orig_gi, orig_gl, orig_gv

placed = broll_mod.load_scenes(p)
by_id = {s["id"]: s for s in placed}
check("escena 1 (video manual) usa tu material (broll_source=manual)",
      by_id[1].get("broll_source") == "manual" and by_id[1]["broll_video"].startswith("manual/"),
      str(by_id[1]))
check("escena 2 (imagen manual) usa tu material",
      by_id[2].get("broll_source") == "manual" and by_id[2]["broll_image"].startswith("manual/"),
      str(by_id[2]))
check("escena 3 (sin manual) se generó con IA",
      by_id[3].get("broll_source") != "manual" and "scene_003" in by_id[3]["broll_image"],
      str(by_id[3]))
check("SOLO se generó IA para la escena 3 (no para 1 ni 2)",
      gen_calls == ["scene_003.jpg"], str(gen_calls))
# los archivos manuales existen dentro de 06_broll/manual/
mandir = p.path("broll", "manual")
check("archivos manuales presentes", any(mandir.glob("scene_001.*")) and any(mandir.glob("scene_002.*")))
check("duraciones intactas (no se tocó la voz/tiempos)",
      by_id[1]["duration"] == 5.0 and by_id[2]["duration"] == 4.0)

print("T4 revisión del director: NO encaja + auto-reemplazo OFF -> se respeta y avisa")


class _FakeLLMReject:
    is_mock = False
    def __init__(self, fits): self.fits = fits
    def complete_json(self, system, prompt, *, schema, images=None, max_tokens=16000, purpose=""):
        # devuelve un veredicto por cada escena listada en el prompt
        import re
        sids = [int(x) for x in re.findall(r"escena (\d+):", prompt)]
        return {"reviews": [{"scene": s, "fits": self.fits,
                             "reason": "no coincide con la narración"} for s in sids]}


p2 = Project.create("mb2")
_save(p2, [dict(s) for s in scenes])
server.api_scene_broll_upload("mb2", 2, {"file": {"name": "m.png", "data_base64": png_b64()}})
server.api_set_broll_policy("mb2", {"auto_replace": False})
broll_mod.get_images = lambda cfg: _FakeImages(cfg)
broll_mod.get_llm = lambda cfg: _FakeLLMReject(False)
broll_mod.get_videogen = lambda cfg: None
p2 = Project('mb2')
try:
    broll_mod.run(p2, bcfg)
finally:
    broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen = orig_gi, orig_gl, orig_gv
d2 = {s["id"]: s for s in broll_mod.load_scenes(p2)}
check("auto-reemplazo OFF: se respeta tu B-roll aunque no encaje",
      d2[2].get("broll_source") == "manual", str(d2[2]))
warns = p2.get("warnings") or []
check("avisa que el director cree que no encaja",
      any("no ilustra" in w.lower() or "no encaja" in w.lower() for w in warns), str(warns))
mb2 = p2.get("manual_broll")
check("el veredicto queda guardado (fits=false)",
      mb2["2"]["review"]["fits"] is False, str(mb2["2"].get("review")))

print("T5 revisión del director: NO encaja + auto-reemplazo ON -> reemplaza por IA")
gen_calls.clear()
p3 = Project.create("mb3")
_save(p3, [dict(s) for s in scenes])
server.api_scene_broll_upload("mb3", 2, {"file": {"name": "m.png", "data_base64": png_b64()}})
server.api_set_broll_policy("mb3", {"auto_replace": True})
broll_mod.get_images = lambda cfg: _FakeImages(cfg)
broll_mod.get_llm = lambda cfg: _FakeLLMReject(False)
broll_mod.get_videogen = lambda cfg: None
p3 = Project('mb3')
try:
    broll_mod.run(p3, bcfg)
finally:
    broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen = orig_gi, orig_gl, orig_gv
d3 = {s["id"]: s for s in broll_mod.load_scenes(p3)}
check("auto-reemplazo ON: la escena 2 pasó a IA",
      d3[2].get("broll_source") != "manual" and "scene_002" in (d3[2].get("broll_image") or ""),
      str(d3[2]))
check("se generó IA para la escena 2 reemplazada", "scene_002.jpg" in gen_calls, str(gen_calls))
check("el manual de la escena 2 se quitó del registro",
      "2" not in (p3.get("manual_broll") or {}), str(p3.get("manual_broll")))

print("T6 revisión DESACTIVADA: no se llama al LLM (ahorro de tokens)")
review_calls = []


class _SpyLLM:
    is_mock = False
    def complete_json(self, system, prompt, *, schema, images=None, max_tokens=16000, purpose=""):
        review_calls.append(purpose)
        import re
        sids = [int(x) for x in re.findall(r"escena (\d+):", prompt)]
        return {"reviews": [{"scene": s, "fits": False, "reason": "x"} for s in sids]}


p4 = Project.create("mb4")
_save(p4, [dict(s) for s in scenes])
server.api_scene_broll_upload("mb4", 2, {"file": {"name": "m.png", "data_base64": png_b64()}})
pol = server.api_set_broll_policy("mb4", {"review": False})
check("la política refleja review=False", pol["broll_review"] is False, str(pol))
broll_mod.get_images = lambda cfg: _FakeImages(cfg)
broll_mod.get_llm = lambda cfg: _SpyLLM()
broll_mod.get_videogen = lambda cfg: None
p4 = Project('mb4')
try:
    broll_mod.run(p4, bcfg)
finally:
    broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen = orig_gi, orig_gl, orig_gv
check("con revisión OFF, el LLM de revisión NO se llamó",
      "broll_review" not in review_calls, str(review_calls))
d4 = {s["id"]: s for s in broll_mod.load_scenes(p4)}
check("con revisión OFF, tu B-roll se usa tal cual (sin veredicto)",
      d4[2].get("broll_source") == "manual"
      and "review" not in (p4.get("manual_broll") or {}).get("2", {}),
      str((p4.get("manual_broll") or {}).get("2")))

print("T7 quitar B-roll manual -> vuelve a IA")
server_del = server.api_scene_broll_delete("mb", 2)
check("delete ok", server_del["ok"])
check("escena 2 ya no está en manual_broll",
      "2" not in (Project("mb").get("manual_broll") or {}))

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
