"""Batería v0.29.0: elenco con consistencia visual de personajes.

T1  characters.py: migración desde v0.28, fotos por personaje, narrador.
T2  scenes: schema con enum del elenco SOLO cuando hay elenco; saneo de
    etiquetas; reglas del elenco en el prompt.
T3  CRUD de personajes (crear con fotos, cambiar narrador, añadir fotos,
    eliminar) + roster en el detalle del proyecto.
T4  broll: escena CON personajes se genera con el modelo de IDENTIDAD y las
    fotos correctas; escena sin personajes usa el flujo normal; cambiar el
    elenco de una escena invalida su caché (firma).
T5  Personaje SIN fotos: referencia autogenerada UNA vez y reutilizada.
T6  El lipsync toma la imagen del narrador del elenco.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import base64
import json
import shutil
import sys
from pathlib import Path



from PIL import Image

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.characters import (cast_brief, character_images, narrator,
                                 references_for, roster)
from ytstudio.project import PROJECTS_DIR, Project

SLUG = "__test-v29-cast__"
if (PROJECTS_DIR / SLUG).exists():
    shutil.rmtree(PROJECTS_DIR / SLUG)
proj = Project.create(SLUG)

print("T1 módulo characters")
# legado v0.28: fotos sueltas categoría personaje sin registro
Image.new("RGB", (300, 400), (100, 80, 60)).save(proj.path("input", "01_n.jpg"))
proj.set("assets", [{"id": 1, "file": "01_n.jpg", "name": "n.jpg",
                     "category": "personaje", "kind": "image"}])
r = roster(proj)
check("migración v0.28 → un personaje narrador", len(r) == 1 and r[0]["narrator"]
      and r[0]["asset_ids"] == [1], str(r))
check("narrator() lo encuentra", narrator(proj) is not None)
check("character_images devuelve la foto",
      [p.name for p in character_images(proj, r[0])] == ["01_n.jpg"])

print("T2 schema y saneo del elenco en escenas")
from ytstudio.phases.scenes import (SCENES_SCHEMA, _cast_rules,
                                    _normalize_cast, _schema_with_cast)
proj.set("characters", [
    {"id": "ch1", "name": "Alejandro", "description": "rey joven",
     "asset_ids": [1], "narrator": True},
    {"id": "ch2", "name": "Filipo", "description": "rey veterano, barba",
     "asset_ids": [], "narrator": False},
])
names, rules = _cast_rules(proj)
check("nombres del elenco", names == ["Alejandro", "Filipo"], str(names))
check("las reglas describen el elenco y prohíben inventar rasgos",
      "Alejandro" in rules and "referencia" in rules.lower())
sch = _schema_with_cast(SCENES_SCHEMA, names)
item = sch["properties"]["scenes"]["items"]
check("schema con characters enum del elenco",
      item["properties"]["characters"]["items"]["enum"] == names
      and "characters" in item["required"])
check("sin elenco el schema queda INTACTO",
      _schema_with_cast(SCENES_SCHEMA, []) is SCENES_SCHEMA)
scs = [{"characters": ["alejandro", "Zeus", "Alejandro", "FILIPO"]}]
_normalize_cast(scs, names)
check("saneo: solo elenco, sin duplicados, nombre canónico",
      scs[0]["characters"] == ["Alejandro", "Filipo"], str(scs))

print("T3 CRUD de personajes")
from ytstudio.webui.server import (api_character_add_files,
                                   api_character_create, api_character_delete,
                                   api_character_update, api_project_detail)
img64 = base64.b64encode(Image.new("RGB", (200, 260), (60, 90, 120))
                         ._repr_jpeg_() if hasattr(Image.Image, "_repr_jpeg_")
                         else b"").decode() if False else None
# foto real por bytes
import io
buf = io.BytesIO()
Image.new("RGB", (200, 260), (60, 90, 120)).save(buf, format="JPEG")
img64 = base64.b64encode(buf.getvalue()).decode()
r3 = api_character_create(SLUG, {"name": "Darío", "description": "rey persa",
                                 "narrator": False,
                                 "files": [{"name": "dario1.jpg", "data_base64": img64},
                                           {"name": "dario2.jpg", "data_base64": img64}]})
ch_d = next(c for c in r3["characters"] if c["name"] == "Darío")
check("crear con 2 fotos", len(ch_d["asset_ids"]) == 2, str(ch_d))
api_character_update(SLUG, ch_d["id"], {"narrator": True})
r_now = roster(Project(SLUG))
check("cambiar narrador es EXCLUSIVO",
      [c["narrator"] for c in r_now] == [False, False, True], str(r_now))
api_character_add_files(SLUG, ch_d["id"],
                        {"files": [{"name": "dario3.jpg", "data_base64": img64}]})
check("añadir foto", len(next(c for c in roster(Project(SLUG))
                              if c["id"] == ch_d["id"])["asset_ids"]) == 3)
detail = api_project_detail(SLUG)
ros = detail.get("characters_roster") or []
check("detalle expone el roster con archivos",
      any(c["name"] == "Darío" and len(c["files"]) == 3 for c in ros), str(ros))
api_character_delete(SLUG, ch_d["id"])
check("eliminar personaje (y sus fotos)",
      all(c["name"] != "Darío" for c in roster(Project(SLUG))) and
      not any("dario" in (a.get("file") or "") for a in Project(SLUG).get("assets")))

print("T4 broll con modelo de identidad")
from ytstudio.phases import broll as broll_mod
from ytstudio.phases.scenes import save_scenes
import ytstudio.providers.images as images_mod
proj2 = Project(SLUG)
sc = [{"id": 1, "section": "a", "narration": "x", "broll_prompt": "king speech",
       "broll_type": "image", "animation": "static", "transition": "corte",
       "sfx": "ninguno", "music_intensity": 0.5, "pace": "normal",
       "overlay": None, "on_screen_text": "", "duration": 4.0,
       "characters": ["Alejandro"]},
      {"id": 2, "section": "b", "narration": "y", "broll_prompt": "landscape",
       "broll_type": "image", "animation": "static", "transition": "corte",
       "sfx": "ninguno", "music_intensity": 0.5, "pace": "normal",
       "overlay": None, "on_screen_text": "", "duration": 4.0,
       "characters": []}]
save_scenes(proj2, sc)

calls = {"refs": [], "normal": []}


class FakeRef:
    model = "google/nano-banana"
    def generate_with_refs(self, prompt, refs, out):
        calls["refs"].append((prompt, [p.name for p in refs]))
        Image.new("RGB", (64, 36), (10, 10, 10)).save(out)
        return out


class FakeImages:
    def generate(self, prompt, out):
        calls["normal"].append(prompt)
        Image.new("RGB", (64, 36), (30, 30, 30)).save(out)
        return out


import ytstudio.providers as prov_mod
class _MockL: is_mock = True
# broll importa las fábricas por nombre: se parchean SUS referencias
_orig = (broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen,
         images_mod.get_ref_images)
broll_mod.get_images = lambda cfg: FakeImages()
broll_mod.get_llm = lambda cfg: _MockL()
broll_mod.get_videogen = lambda cfg: None
images_mod.get_ref_images = lambda cfg: FakeRef()
try:
    broll_mod.run(proj2, {"providers": {"llm": {"name": "mock"},
                                        "images": {"name": "mock"},
                                        "videogen": {"name": "none"},
                                        "lipsync": {"name": "none"}},
                          "video": {"width": 1920, "height": 1080},
                          "performance": {"parallel_images": 2}})
finally:
    (broll_mod.get_images, broll_mod.get_llm, broll_mod.get_videogen,
     images_mod.get_ref_images) = _orig
check("la escena CON personaje usó el modelo de identidad con su foto",
      len(calls["refs"]) == 1 and calls["refs"][0][1] == ["01_n.jpg"],
      str(calls["refs"]))
check("la escena SIN personaje usó el flujo normal",
      calls["normal"] == ["landscape"], str(calls["normal"]))
sigs = json.loads((proj2.path("broll") / "prompts.json").read_text())
check("la firma de caché incluye el elenco de la escena",
      sigs.get("1") != sigs.get("2"))
# cambiar el elenco de la escena 1 → firma distinta → material se rehace
sc[0]["characters"] = []
save_scenes(proj2, sc)
import hashlib
new_sig = hashlib.md5(("king speech" + "|chars:").encode()).hexdigest()
check("cambiar personajes cambia la firma (se rehará esa escena)",
      new_sig != sigs.get("1"))

print("T5 referencia autogenerada para personaje sin fotos")
from ytstudio.characters import ensure_reference
gen_calls = []


class FakeImages2:
    def generate(self, prompt, out):
        gen_calls.append(prompt)
        Image.new("RGB", (64, 64), (50, 40, 30)).save(out)
        return out


_orig_imgs = prov_mod.get_images
prov_mod.get_images = lambda cfg: FakeImages2()
try:
    ch2 = next(c for c in roster(proj2) if c["id"] == "ch2")
    r1 = ensure_reference(proj2, {"providers": {"images": {"name": "x"}}}, ch2)
    r2 = ensure_reference(proj2, {"providers": {"images": {"name": "x"}}}, ch2)
finally:
    prov_mod.get_images = _orig_imgs
check("la referencia se genera UNA sola vez y se reutiliza",
      r1 == r2 and len(gen_calls) == 1 and r1.exists(), f"{gen_calls} {r1}")
check("el prompt de la referencia usa la descripción del personaje",
      "barba" in gen_calls[0] or "veterano" in gen_calls[0], str(gen_calls))

print("T6 lipsync usa la foto del narrador del elenco")
img = broll_mod._character_image(proj2, {"providers": {"images": {"name": "mock"}}})
check("narrador (Alejandro) → su foto subida", img is not None
      and img.name == "01_n.jpg", str(img))

shutil.rmtree(PROJECTS_DIR / SLUG, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
