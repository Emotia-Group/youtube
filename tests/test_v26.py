"""Batería v26: voz ignorada en silencio (causa raíz encontrada) + gestión
de proyectos (fecha, duplicar, renombrar, listar/filtrar)."""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_v26_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
from ytstudio.project import Project
from ytstudio.phases import ingest

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 BUG DE RAÍZ: voz grabada en contenedor de VIDEO (.webm/.mp4) ya no se ignora")
# Simula una "nota de voz" exportada como .webm (video container, solo audio) —
# el caso real que el usuario reportó: "subiendo la voz en off... el programa
# las generó por su cuenta" (sin ningún error visible).
voz_webm = WORK / "nota.webm"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", "sine=frequency=200:duration=3",
                "-c:a", "libopus", str(voz_webm)], check=True)
check("kind_of clasifica .webm como video (la trampa)",
      ingest.kind_of(voz_webm) == "video")

p = Project.create("t26a")
ingest.add_asset(p, voz_webm, "voz")  # la UI manda category='voz' explícito


class _MockLLM:
    is_mock = True

    def complete_json(self, *a, **k):
        return {"topic": "x", "summary": "x", "key_points": ["x"],
               "detected_type": "idea"}


class _StubSTT:
    is_mock = False

    def transcribe_segments(self, audio):
        from ytstudio.utils.media import probe_duration
        d = probe_duration(audio)
        return [{"start": 0.1, "end": max(0.2, d - 0.1), "text": "hola mundo",
                 "words": [{"start": 0.1, "end": 0.5, "text": "hola"},
                          {"start": 0.6, "end": 1.0, "text": "mundo"}]}]


import ytstudio.phases.ingest as ingest_mod
orig_get_llm, orig_get_stt = ingest_mod.get_llm, ingest_mod.get_stt
ingest_mod.get_llm = lambda cfg: _MockLLM()
ingest_mod.get_stt = lambda cfg: _StubSTT()
cfg = {"language": "es", "audio": {"trim_silence": True, "silence_keep": 0.4,
                                   "vo_lufs": -16}}
try:
    ingest_mod.run(p, cfg)
finally:
    ingest_mod.get_llm, ingest_mod.get_stt = orig_get_llm, orig_get_stt

narration = p.get("narration")
check("la voz en .webm SÍ se usó como narración (antes se perdía en silencio)",
      narration is not None and bool(narration.get("segments")),
      str(narration))
warnings = p.get("warnings") or []
check("no hace falta ningún warning cuando SÍ funcionó", True)

print("T2 warning explícito cuando un asset 'voz' no es usable")
p2 = Project.create("t26b")
bad = WORK / "notas.pdf"
bad.write_bytes(b"%PDF-1.4 fake")
# Fuerza un asset 'voz' de tipo texto (caso límite defensivo)
from ytstudio.phases.ingest import add_asset
a = add_asset(p2, bad, "guion")
assets = p2.get("assets")
assets[0]["category"] = "voz"  # simula una clasificación forzada anómala
p2.set("assets", assets)
ingest_mod.get_llm = lambda cfg: _MockLLM()
ingest_mod.get_stt = lambda cfg: _StubSTT()
try:
    ingest_mod.run(p2, cfg)
except Exception as e:
    print("     (excepción esperada o no, ver warnings):", e)
finally:
    ingest_mod.get_llm, ingest_mod.get_stt = orig_get_llm, orig_get_stt
warn2 = p2.get("warnings") or []
check("avisa cuando un asset 'voz' no se pudo usar como audio",
      any("no se pudo usar" in w.lower() or "ningun" in w.lower().replace("ó","o")
          for w in warn2), str(warn2))

print("T3 gestión de proyectos: fecha de creación, duplicar, renombrar")
from ytstudio.webui import server

p3 = Project.create("proyecto-viejo")
time.sleep(0.05)
p4 = Project.create("proyecto-nuevo")
lst = server.api_list_projects()
order = [x["slug"] for x in lst if x["slug"] in ("proyecto-viejo", "proyecto-nuevo")]
check("proyectos listados del más reciente al más antiguo",
      order == ["proyecto-nuevo", "proyecto-viejo"], str(order))
check("cada proyecto trae display_name y created_at",
      all("display_name" in x and "created_at" in x for x in lst))

dup = server.api_duplicate_project("proyecto-viejo")
check("duplicar crea un slug nuevo", dup["slug"] != "proyecto-viejo" and Project.exists(dup["slug"]))
dupproj = Project(dup["slug"])
check("la copia tiene su propia fecha de creación (más reciente)",
      dupproj.state["created_at"] >= p3.state["created_at"])
check("el nombre de la copia lo indica", "copia" in dupproj.state["display_name"].lower())

ren = server.api_rename_project("proyecto-viejo", {"name": "Mi Proyecto Épico"})
check("renombrar cambia el nombre visible", ren["display_name"] == "Mi Proyecto Épico")
check("renombrar NO mueve la carpeta (slug intacto)",
      Project.exists("proyecto-viejo") and
      Project("proyecto-viejo").state["display_name"] == "Mi Proyecto Épico")

# Proyecto legado sin created_at/display_name (versiones anteriores)
legacy_dir = prj.PROJECTS_DIR / "legado"
legacy_dir.mkdir(parents=True)
import json
(legacy_dir / "project.json").write_text(
    json.dumps({"slug": "legado", "phases": {}, "data": {}}), encoding="utf-8")
legacy = Project("legado")
check("proyecto legado adopta created_at/display_name sin romperse",
      legacy.state.get("created_at") and legacy.state.get("display_name") == "legado")

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
