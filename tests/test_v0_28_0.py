"""Batería v0.28.0: personaje narrador con lipsync.

T1  Catálogo/pricing: sección lipsync con 3 modelos y costos por segundo.
T2  _assign_shots: reparto narrativo — gancho y cierre primero, respeta el %
    aproximado por PESO de escena; sin personaje no marca nada.
T3  Estimación: el costo de lipsync escala con la presencia y con el modelo
    (OmniHuman ≫ Sonic); sin clave cae a 'imagen fija' con costo 0.
T4  broll con proveedor FALSO: escenas personaje generan clip + fotograma,
    broll_type=video, broll_source=lipsync; el clip fallido degrada a imagen
    fija del personaje con aviso; el resto de escenas no se toca.
T5  Sin clave (get_lipsync None): degradación limpia a imagen fija + aviso.
T6  api_edit_scenes con 'shot': persiste el override y devuelve
    rerun_from='broll'.
T7  Creación de proyecto con personaje: guarda presence desde la UI.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import shutil
import subprocess
import sys
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 catálogo y pricing")
from ytstudio.catalog import CATALOG
from ytstudio.pricing import LIPSYNC_PER_SEC, lipsync_cost_range
ls_cat = CATALOG.get("lipsync")
check("sección lipsync en el catálogo", ls_cat is not None)
models = [m["id"] for o in ls_cat["options"] for m in o.get("models", [])]
check("3 modelos con OmniHuman y Sonic",
      "bytedance/omni-human" in models and "zsxkib/sonic" in models
      and len(models) >= 3, str(models))
check("todos los modelos con etiqueta ✚/✖ y precio",
      all(("✚" in m["label"] and "✖" in m["label"] and "$" in m["label"])
          for o in ls_cat["options"] for m in o.get("models", [])))
check("OmniHuman cuesta ≫ Sonic por segundo",
      lipsync_cost_range("bytedance/omni-human")[0]
      > lipsync_cost_range("zsxkib/sonic")[1])

print("T2 reparto narrativo de escenas de personaje")
from ytstudio.phases.scenes import _assign_shots
from ytstudio.project import PROJECTS_DIR, Project
SLUG = "__test-v28-char__"
if (PROJECTS_DIR / SLUG).exists():
    shutil.rmtree(PROJECTS_DIR / SLUG)
proj = Project.create(SLUG)
proj.set("assets", [{"id": 1, "file": "01_p.jpg", "name": "p.jpg",
                     "category": "personaje", "kind": "image"}])
proj.set("character", {"presence": 0.3})


def mkscenes(n=10):
    return [{"id": i + 1, "section": ["Gancho"] + ["Desarrollo"] * (n - 2) + ["Cierre"]
             and (["Gancho"] if i == 0 else ["Cierre"] if i == n - 1 else ["Desarrollo"])[0],
             "narration": "palabra " * 20,
             "music_intensity": [0.7, 0.4, 0.5, 0.9, 0.4, 0.5, 0.85, 0.4, 0.5, 0.6][i % 10],
             "duration": 6.0} for i in range(n)]


scenes = mkscenes()
_assign_shots(proj, scenes, {})
shots = [s["shot"] for s in scenes]
share = sum(1 for x in shots if x == "personaje") / len(shots)
print(f"     shots: {shots}  (share≈{share:.0%})")
check("gancho (escena 1) es personaje", shots[0] == "personaje")
check("el reparto ronda el 30% pedido (20-45%)", 0.2 <= share <= 0.45,
      f"{share:.0%}")
# con 30% caben ~3 escenas: gancho, cierre y EL PICO más alto (0.9); el
# 0.85 queda fuera por el tope de presencia — correcto, no un fallo
check("el pico dramático más alto (0.9) es personaje",
      shots[3] == "personaje", str(shots))
check("una escena plana (0.4) NO le gana al pico", shots[1] == "broll",
      str(shots))
proj.set("character", {"presence": 0.0})
scenes2 = mkscenes()
_assign_shots(proj, scenes2, {})
check("presencia 0 → sin escenas de personaje",
      all(s.get("shot") != "personaje" for s in scenes2))
proj.set("character", None)
proj.set("assets", [])
scenes3 = mkscenes()
_assign_shots(proj, scenes3, {})
check("sin imagen de personaje → sin campo shot",
      all("shot" not in s for s in scenes3))

print("T3 estimación por presencia y modelo")
import os
os.environ["REPLICATE_API_TOKEN"] = "test-token"
from ytstudio.estimate import estimate


class _P:
    slug = "_t"
    def __init__(self, presence):
        self._p = presence
    def get(self, k, d=None):
        return {"total_duration": 120, "scene_count": 20,
                "assets": [{"id": 1, "category": "personaje", "kind": "image"}],
                "character": {"presence": self._p}}.get(k, d)


def cfg_ls(model):
    return {"providers": {"llm": {"name": "mock"},
                          "images": {"name": "mock"},
                          "videogen": {"name": "none", "max_scenes": 0},
                          "tts": {"name": "mock"}, "stt": {"name": "mock"},
                          "music": {"name": "library"},
                          "lipsync": {"name": "replicate", "model": model}},
            "video": {"target_minutes": 2, "scene_seconds": 6},
            "performance": {}}


e15 = estimate(_P(0.15), cfg_ls("zsxkib/sonic"))
e45 = estimate(_P(0.45), cfg_ls("zsxkib/sonic"))
i15 = next(i for i in e15["items"] if "lipsync" in i["fase"].lower())
i45 = next(i for i in e45["items"] if "lipsync" in i["fase"].lower())
print(f"     sonic 15%: ${i15['costo']}  45%: ${i45['costo']}")
check("el costo escala ~3x con la presencia",
      2.5 <= i45["costo"][0] / max(0.01, i15["costo"][0]) <= 3.5)
e_omni = estimate(_P(0.3), cfg_ls("bytedance/omni-human"))
i_omni = next(i for i in e_omni["items"] if "lipsync" in i["fase"].lower())
e_sonic = estimate(_P(0.3), cfg_ls("zsxkib/sonic"))
i_sonic = next(i for i in e_sonic["items"] if "lipsync" in i["fase"].lower())
print(f"     30%: omni ${i_omni['costo']} vs sonic ${i_sonic['costo']}")
check("OmniHuman estima mucho más caro que Sonic",
      i_omni["costo"][0] > i_sonic["costo"][1])
del os.environ["REPLICATE_API_TOKEN"]
e_nokey = estimate(_P(0.3), cfg_ls("zsxkib/sonic"))
i_nokey = next((i for i in e_nokey["items"] if "Personaje" in i["fase"]), None)
check("sin clave → 'imagen fija' a costo 0",
      i_nokey is not None and i_nokey["costo"] == [0, 0], str(i_nokey))

print("T4 broll con proveedor FALSO (éxito + fallo por escena)")
from ytstudio.phases import broll as broll_mod
from ytstudio.phases.scenes import save_scenes
import ytstudio.providers as providers_mod
proj.set("assets", [{"id": 1, "file": "01_p.jpg", "name": "p.jpg",
                     "category": "personaje", "kind": "image"}])
proj.set("character", {"presence": 0.5})
from PIL import Image
Image.new("RGB", (640, 800), (120, 90, 70)).save(proj.path("input", "01_p.jpg"))
sc = [{"id": i, "section": "s", "narration": "x", "broll_prompt": "p",
       "broll_type": "image", "animation": "static", "transition": "corte",
       "sfx": "ninguno", "music_intensity": 0.5, "pace": "normal",
       "overlay": None, "on_screen_text": "", "duration": 4.0,
       "shot": ("personaje" if i in (1, 2) else "broll")} for i in (1, 2, 3)]
save_scenes(proj, sc)
vo = proj.path("voiceover")
for i in (1, 2, 3):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "aevalsrc=0.2*sin(2*PI*200*t):s=44100:d=4",
                    "-c:a", "libmp3lame", str(vo / f"vo_{i:03d}.mp3")], check=True)


class FakeLS:
    model = "fake/model"
    def generate(self, image, audio, out, seconds):
        if "002" in out.name:
            raise RuntimeError("cuota agotada (simulado)")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"color=c=blue:s=320x240:d={seconds}",
                        "-pix_fmt", "yuv420p", str(out)], check=True)
        return out


_orig = providers_mod.get_lipsync
providers_mod.get_lipsync = lambda cfg: FakeLS()
try:
    scenes_l = json.loads((proj.dir / "04_scenes" / "scenes.json")
                          .read_text(encoding="utf-8"))["scenes"]
    ids = broll_mod._generate_character_scenes(proj, scenes_l,
                                               proj.path("broll"), {})
finally:
    providers_mod.get_lipsync = _orig
s1, s2, s3 = scenes_l
check("escena 1: clip lipsync + fotograma + tipo video",
      s1.get("broll_video") == "lipsync_001.mp4"
      and s1.get("broll_image") == "lipsync_001.jpg"
      and s1.get("broll_type") == "video"
      and (proj.path("broll") / "lipsync_001.jpg").exists(), str(s1))
check("escena 2 (clip falló): degrada a imagen fija del personaje",
      s2.get("broll_type") == "image" and "personaje" in (s2.get("broll_image") or ""),
      str(s2))
check("aviso del fallo registrado",
      any("lipsync falló" in w.lower() or "falló en 1" in w
          for w in (proj.get("warnings") or [])),
      str(proj.get("warnings")))
check("escena 3 (broll) intacta", "broll_video" not in s3 and
      s3.get("broll_source") != "lipsync")
check("devuelve los ids de personaje", ids == {1, 2}, str(ids))

print("T5 sin clave → imagen fija para todas las de personaje")
for f in proj.path("broll").glob("lipsync_*"):
    f.unlink()
scenes_n = json.loads((proj.dir / "04_scenes" / "scenes.json")
                      .read_text(encoding="utf-8"))["scenes"]
os.environ.pop("REPLICATE_API_TOKEN", None)
ids2 = broll_mod._generate_character_scenes(
    proj, scenes_n, proj.path("broll"),
    {"providers": {"lipsync": {"name": "replicate"}}})
check("todas las de personaje quedan como imagen fija",
      all(s.get("broll_type") == "image" and "personaje" in (s.get("broll_image") or "")
          for s in scenes_n if s.get("shot") == "personaje"), str(scenes_n[:2]))
check("aviso claro de lipsync desactivado",
      any("REPLICATE_API_TOKEN" in w for w in (proj.get("warnings") or [])))

print("T6 override de shot desde el Editor")
from ytstudio.webui.server import api_edit_scenes
for ph in ("broll", "music", "subtitles", "assembly"):
    proj.mark_phase(ph, "done", seconds=1)
r = api_edit_scenes(SLUG, {"edits": [{"id": 3, "shot": "personaje"}]})
check("cambiar shot → rerun_from=broll", r["rerun_from"] == "broll", str(r))
check("el override queda persistido",
      (Project(SLUG).get("shot_overrides") or {}).get("3") == "personaje")
check("broll invalidada", Project(SLUG).phase_status("broll") == "pending")

print("T7 creación con personaje guarda la presencia")
from ytstudio.webui.server import api_create_project
import base64
SLUG2 = "__test-v28-create__"
if (PROJECTS_DIR / SLUG2).exists():
    shutil.rmtree(PROJECTS_DIR / SLUG2)
img_b = Path(proj.path("input", "01_p.jpg")).read_bytes()
api_create_project({"slug": SLUG2, "text": "idea",
                    "character_presence": 45,
                    "files": [{"name": "heroe.jpg", "category": "personaje",
                               "data_base64": base64.b64encode(img_b).decode()}]})
p2 = Project(SLUG2)
check("presence 45% guardada", abs((p2.get("character") or {}).get("presence", 0)
                                   - 0.45) < 0.001)
check("asset personaje registrado",
      any(a["category"] == "personaje" for a in p2.get("assets")))

shutil.rmtree(PROJECTS_DIR / SLUG, ignore_errors=True)
shutil.rmtree(PROJECTS_DIR / SLUG2, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
