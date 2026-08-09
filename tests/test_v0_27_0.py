"""Batería v0.27.0: metadatos profesionales — 3 miniaturas con diseños
distintos + 3 títulos + 3 descripciones + selección persistente.

T1  La fase metadata (mock) produce 3 opciones de todo; las 3 miniaturas
    existen, miden 1280x720, son DISTINTAS entre sí, y miniatura.jpg = la
    elegida por defecto (la 1).
T2  Fondos: pick_backgrounds respeta las escenas sugeridas, no repite y
    completa por intensidad musical.
T3  Vertical: los proyectos 9:16 generan miniaturas 1080x1920.
T4  api_select_metadata: cambiar la miniatura copia la variante elegida a
    miniatura.jpg; cambiar el título actualiza metadata; índice fuera de
    rango falla limpio.
T5  _norm_meta rellena hasta 3 opciones con datos del concepto (proyectos
    antiguos / respuestas incompletas del LLM).
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
import sys
from pathlib import Path



from PIL import Image, ImageDraw

from ytstudio.phases import metadata as meta_phase
from ytstudio.phases.scenes import save_scenes
from ytstudio.project import PROJECTS_DIR, Project
from ytstudio.utils.thumbs import pick_backgrounds, render_thumbnails
from ytstudio.webui.server import api_select_metadata

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


SLUG = "__test-v27-meta__"
if (PROJECTS_DIR / SLUG).exists():
    shutil.rmtree(PROJECTS_DIR / SLUG)
proj = Project.create(SLUG)


def synth_scene_img(path, base_rgb, motif):
    """Fondo sintético con algo de estructura (gradiente + formas), para que
    los diseños tengan una 'foto' sobre la que trabajar."""
    img = Image.new("RGB", (1344, 768))
    d = ImageDraw.Draw(img)
    for y in range(768):
        t = y / 768
        d.line([(0, y), (1344, y)],
               fill=tuple(int(c * (0.35 + 0.65 * (1 - t))) for c in base_rgb))
    if motif == "sun":
        d.ellipse([900, 80, 1180, 360], fill=(235, 200, 130))
    elif motif == "tower":
        d.rectangle([560, 180, 780, 768], fill=(48, 42, 34))
        d.polygon([(560, 180), (670, 90), (780, 180)], fill=(60, 52, 40))
    else:
        for i in range(7):
            d.rectangle([80 + i * 180, 500, 150 + i * 180, 768], fill=(52, 46, 38))
    img.save(path, quality=90)


broll = proj.path("broll")
scenes = []
for i, (rgb, motif) in enumerate([((120, 90, 50), "sun"), ((70, 80, 110), "tower"),
                                  ((90, 60, 70), "cols"), ((60, 90, 60), "sun")],
                                 start=1):
    synth_scene_img(broll / f"scene_{i:03d}.jpg", rgb, motif)
    scenes.append({"id": i, "section": ["Gancho", "Desarrollo", "Desarrollo",
                                        "Cierre"][i - 1],
                   "narration": f"escena {i}", "broll_prompt": f"p{i}",
                   "broll_type": "image", "animation": "static",
                   "transition": "corte", "sfx": "ninguno",
                   "music_intensity": [0.4, 0.9, 0.6, 0.8][i - 1],
                   "pace": "normal", "overlay": None, "on_screen_text": "",
                   "duration": 40.0, "vo_duration": 38.0,
                   "broll_image": f"scene_{i:03d}.jpg"})
save_scenes(proj, scenes)
proj.set("concept", {"title_options": ["Título A del concepto",
                                       "Título B del concepto"]})

CFG = {"providers": {"llm": {"name": "mock"}},
       "video": {"width": 1920, "height": 1080, "overlay_accent": "E8C46B"},
       "language": "es"}

print("T1 fase metadata: 3 opciones de todo + miniaturas distintas")
meta_phase.run(proj, CFG)
meta = json.loads((proj.dir / "09_final" / "metadata.json").read_text(encoding="utf-8"))
check("3 títulos con estrategia", len(meta["title_options"]) == 3 and
      all(o.get("angle") for o in meta["title_options"]))
check("3 descripciones con enfoque", len(meta["description_options"]) == 3)
check("3 miniaturas registradas", len(meta["thumbnails"]) == 3)
final = proj.path("final")
sizes = []
datas = []
for f in meta["thumbnails"]:
    p = final / f
    check(f"{f} existe", p.exists())
    img = Image.open(p)
    sizes.append(img.size)
    datas.append(p.read_bytes())
check("las 3 miden 1280x720", all(s == (1280, 720) for s in sizes), str(sizes))
check("las 3 son DISTINTAS entre sí (diseños diferentes)",
      len({d[:8000] for d in datas}) == 3)
mini = (final / "miniatura.jpg").read_bytes()
check("miniatura.jpg = opción 1 por defecto", mini == datas[0])
check("title = primera opción", meta["title"] == meta["title_options"][0]["title"])
check("chosen inicial en 0", meta["chosen"] == {"title": 0, "description": 0,
                                                "thumbnail": 0})

print("T2 fondos elegidos con criterio")
bgs = pick_backgrounds(scenes, [2, 3, 1])
check("respeta las escenas sugeridas por el LLM",
      [b["id"] for b in bgs] == [2, 3, 1], str([b["id"] for b in bgs]))
bgs2 = pick_backgrounds(scenes, [2, 2, 2])  # sugerencias repetidas
ids2 = [b["id"] for b in bgs2]
check("sugerencias repetidas → completa con las de mayor intensidad sin repetir",
      len(set(ids2)) == 3 and ids2[0] == 2 and 4 in ids2, str(ids2))

print("T3 vertical 1080x1920")
CFGV = {"providers": {"llm": {"name": "mock"}},
        "video": {"width": 1080, "height": 1920, "overlay_accent": "E8C46B"}}
names_v = render_thumbnails(proj, CFGV,
                            [{"kicker": "SHORT", "text": "CAYÓ EL IMPERIO",
                              "accent_word": "CAYÓ", "scene_id": 2}] * 3, scenes)
sv = Image.open(final / names_v[0]).size
check("miniatura vertical 1080x1920", sv == (1080, 1920), str(sv))
# re-render horizontal para dejar el estado coherente para T4
meta_phase.run(proj, CFG)
meta = json.loads((proj.dir / "09_final" / "metadata.json").read_text(encoding="utf-8"))
datas = [(final / f).read_bytes() for f in meta["thumbnails"]]

print("T4 selección persistente")
r = api_select_metadata(SLUG, {"kind": "thumbnail", "index": 2})
check("elegir miniatura 3 → miniatura.jpg cambia a esa variante",
      (final / "miniatura.jpg").read_bytes() == datas[2] and
      r["chosen"]["thumbnail"] == 2)
api_select_metadata(SLUG, {"kind": "title", "index": 1})
meta2 = json.loads((proj.dir / "09_final" / "metadata.json").read_text(encoding="utf-8"))
check("elegir título 2 → title actualizado y persistido",
      meta2["title"] == meta2["title_options"][1]["title"] and
      meta2["chosen"]["title"] == 1)
check("la elección llega al resumen del proyecto (publicación)",
      Project(SLUG).get("metadata")["title"] == meta2["title"])
try:
    api_select_metadata(SLUG, {"kind": "thumbnail", "index": 9})
    check("índice fuera de rango falla limpio", False)
except Exception:
    check("índice fuera de rango falla limpio", True)

print("T5 _norm_meta rellena opciones que falten")
old = {"title": "Solo un título", "description": "Solo una descripción",
       "thumbnail_text": "IMPACTO TOTAL", "tags": ["a"]}
normed = meta_phase._norm_meta(dict(old), {"title_options": ["Alt B", "Alt C"]})
check("títulos completados a 3 (con los del concepto)",
      len(normed["title_options"]) == 3 and
      normed["title_options"][0]["title"] == "Alt B")
check("descripciones completadas a 3", len(normed["description_options"]) == 3)
check("miniaturas completadas a 3 desde thumbnail_text",
      len(normed["thumbnail_options"]) == 3 and
      "IMPACTO" in normed["thumbnail_options"][0]["text"])

# copia de las 3 miniaturas para revisión visual
demo = Path(__file__).parent / "thumbs_demo"
demo.mkdir(exist_ok=True)
for f in meta["thumbnails"]:
    shutil.copyfile(final / f, demo / f)

shutil.rmtree(PROJECTS_DIR / SLUG, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
