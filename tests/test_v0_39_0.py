"""Batería v0.39.0: rediseño de la UI — tarjetas de plataforma, preview con
aspecto real y pipeline compacto para cortos.

T1  El detalle del proyecto expone formato, plantilla y ASPECTO real
    (leído del config del proyecto, no supuesto 16:9): un proyecto Reel
    devuelve 1080x1920; uno sin formato devuelve long/1920x1080.
    (Se ejercita la función real api_project sobre proyectos reales en un
    directorio temporal.)
T2  El HTML de la UI trae las piezas del rediseño: tarjetas de plataforma
    como primera decisión (con select oculto sincronizado), helpers de
    aspecto (thumbStyle/aspectOf/fmtBadges), marco de teléfono para el video
    vertical, chips mini del pipeline compacto y su CSS.
T3  Humo de servidor REAL: se levanta el HTTP server en un puerto libre y
    /api/config responde con formats(+short), short_templates y phases; la
    portada sirve el HTML con las tarjetas.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


import ytstudio.project as project_mod

TMP = Path(tempfile.mkdtemp(prefix="t390_"))
project_mod.PROJECTS_DIR = TMP / "projects"

from ytstudio.project import Project
from ytstudio.webui import server as srv

print("T1 api_project expone formato/plantilla/aspecto reales")
import yaml

p1 = Project("reel-prueba")
p1.set("format", "reel")
p1.set("short_template", "top3")
(p1.dir / "config.yaml").write_text(yaml.safe_dump(
    {"video": {"width": 1080, "height": 1920}}), encoding="utf-8")
d1 = srv.api_project_detail("reel-prueba")
check("formato y plantilla presentes",
      d1["format"] == "reel" and d1["short_template"] == "top3")
check("aspecto real 1080x1920 (del config del proyecto)",
      d1["video_aspect"] == {"w": 1080, "h": 1920}, str(d1["video_aspect"]))

p2 = Project("largo-prueba")
p2.save()
d2 = srv.api_project_detail("largo-prueba")
check("proyecto clásico: long + 1920x1080 (sin romper proyectos viejos)",
      d2["format"] == "long" and d2["video_aspect"]["w"] == 1920,
      str((d2["format"], d2["video_aspect"])))

print("T2 piezas del rediseño en la UI")
html = (ROOT / "ytstudio/webui/static/index.html").read_text(
    encoding="utf-8")
checks = {
    "tarjetas de plataforma (fmtcard + pickFormat)":
        "fmtcard" in html and "pickFormat(" in html,
    "select oculto sincronizado (compatibilidad del POST)":
        'id="np-format" style="display:none"' in html,
    "helpers de aspecto (aspectOf/thumbStyle/fmtBadges)":
        all(f in html for f in ("function aspectOf", "function thumbStyle",
                                "function fmtBadges")),
    "miniaturas del storyboard con aspect-ratio real":
        "thumbStyle(p)" in html,
    "video final en marco de teléfono para vertical":
        "vframe" in html and "max-height:72vh" in html,
    "pipeline compacto (chips mini para fases ligeras en cortos)":
        "phase.mini" in html and "light.has(ph.name)" in html,
    "badges de formato+plantilla en el encabezado":
        "fmtBadges(p)" in html,
    "¿Para dónde es este video? es la primera decisión":
        "¿Para dónde es este video?" in html,
}
for name, ok in checks.items():
    check(name, ok)

print("T3 humo de servidor real")
httpd = srv.ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/config",
                                timeout=10) as r:
        cfg = json.loads(r.read())
    check("formats con marca short",
          cfg["formats"]["reel"]["short"] is True
          and cfg["formats"]["long"]["short"] is False)
    check("short_templates servidas con label/hint",
          "top3" in cfg["short_templates"]
          and cfg["short_templates"]["top3"]["hint"])
    check("phases servidas para los chips", len(cfg["phases"]) == 11)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
        page = r.read().decode("utf-8")
    check("la portada sirve la UI con las tarjetas de plataforma",
          "fmtcard" in page)
    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/projects/reel-prueba",
            timeout=10) as r:
        via_http = json.loads(r.read())
    check("el detalle por HTTP trae el aspecto real",
          via_http["video_aspect"]["h"] == 1920)
finally:
    httpd.shutdown()

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
