"""Batería v0.65.0 — publicación de Shorts: metadatos con las reglas del
formato y LISTA DE COMPROBACIÓN antes de publicar.

Fase 4 (y última) de la integración del framework de Shorts:

1.  Los METADATOS de un vertical siguen las reglas del formato: título de
    40-70 caracteres, SIN el hashtag de Shorts (mito de 2021: la
    clasificación es automática), 2-3 hashtags, 3-5 tags, y el enlace al
    video largo dentro de la descripción — respetando la primera línea, que
    es lo único visible sin desplegar.
2.  Si el Short salió de un video largo, el título y la descripción que
    decidió el PLAN EDITORIAL se garantizan como primera opción.
3.  La LISTA DE COMPROBACIÓN antes de publicar: lo medible se mide (revisión
    técnica, título, hashtags, SRT, enlace) y lo que solo puede mirar una
    persona se marca con ☐ — que son justo los puntos que más se olvidan.
4.  La fase de publicación entiende los Shorts: limpia los metadatos justo
    antes de subir, sube el SRT como pista aparte (con aviso claro si falta
    el permiso), no tira la fase si la miniatura de Short aún no está
    disponible en el canal, y recuerda el ÚNICO paso que no se puede
    automatizar: el enlace a video relacionado se pone a mano en Studio.

Ninguna prueba usa claves ni internet.
"""

import io
import json
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


WORK = Path(tempfile.mkdtemp(prefix="v0650_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el  # noqa: E402
el.LOG_PATH = WORK / "data" / "events.log"

from ytstudio import derive, shorts  # noqa: E402
from ytstudio.project import DIRS, Project, read_json_tolerant  # noqa: E402

CFG_V = {"language": "es", "providers": {"llm": {"name": "mock"}},
         "video": {"width": 1080, "height": 1920}}

# ---------------------------------------------------------------------------
# T1 — las correcciones mecánicas de metadatos de Short
# ---------------------------------------------------------------------------
print("T1 correcciones de metadatos de Short")

m = {"title_options": [{"title": "Mi título #Shorts de prueba"}],
     "title": "Mi título #shorts de prueba",
     "tags": ["historia", "shorts", "#Shorts", "documental", "mitos",
              "leyendas", "datos"],
     "description_options": [
         {"description": "El gancho.\n\nEl cuerpo. #historia #datos"}],
     "description": "El gancho.\n\nEl cuerpo. #historia #datos"}
avisos = shorts.short_metadata_fixups(m, "https://youtu.be/XYZ")

check("T1a se quita el hashtag de Shorts del título",
      "#" not in m["title"] and "#" not in m["title_options"][0]["title"],
      m["title"])
check("T1b se quita 'shorts' de los tags",
      all("short" not in t.lower() for t in m["tags"]), str(m["tags"]))
check("T1c los tags se recortan a 5", len(m["tags"]) <= 5, str(m["tags"]))
check("T1d la descripción gana el enlace al video largo",
      "https://youtu.be/XYZ" in m["description"])
check("T1e sin pisar la primera línea (el gancho es lo único visible)",
      m["description"].startswith("El gancho."), m["description"][:40])
check("T1f y cada corrección se explica", len(avisos) >= 3, str(len(avisos)))
check("T1g volver a corregir no duplica el enlace",
      not shorts.short_metadata_fixups(m, "https://youtu.be/XYZ")
      or m["description"].count("https://youtu.be/XYZ") == 1,
      str(m["description"].count("https://youtu.be/XYZ")))
check("T1h contar hashtags funciona",
      shorts.count_hashtags("hola #uno #dos tres") == 2)

# ---------------------------------------------------------------------------
# T2 — la fase de metadatos aplica las reglas a los verticales
# ---------------------------------------------------------------------------
print("\nT2 la fase de metadatos, en vertical")

p = Project.create("largo")
p.set("metadata", {"title": "x"})
p.set("youtube_id", "ABC123XYZ")
(p.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": i, "section": "Desarrollo", "duration": 30.0,
     "narration": f"Frase {i}."} for i in range(1, 31)]}), encoding="utf-8")
cand = derive.propose(derive.source_from_project("largo"), CFG_V, n=3)[0]
slug = derive.create_short_project(cand, CFG_V)
q = Project(slug)
q.set("concept", {"angle": "a", "tone": "b", "audience": "c"})
(q.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": 1, "section": "Gancho", "duration": 10.0, "narration": "Hola.",
     "broll_prompt": "x"}]}), encoding="utf-8")

from ytstudio.phases import metadata as metadata_phase  # noqa: E402
metadata_phase.run(q, CFG_V)
meta = read_json_tolerant(q.dir / DIRS["final"] / "metadata.json")

check("T2a el título del plan editorial es la PRIMERA opción",
      meta["title_options"][0]["title"] == cand["titulo_youtube"],
      str(meta["title_options"][0]))
check("T2b la descripción del plan también, con sus hashtags",
      any(h in meta["description_options"][0]["description"]
          for h in cand["hashtags"]),
      meta["description_options"][0]["description"][:80])
check("T2c todas las descripciones enlazan al video largo",
      all("https://youtu.be/ABC123XYZ" in o["description"]
          for o in meta["description_options"]))
check("T2d ningún título lleva el hashtag de Shorts",
      all("#short" not in o["title"].lower() for o in meta["title_options"]))
check("T2e como mucho 5 tags y ninguno es 'shorts'",
      len(meta["tags"]) <= 5
      and all("short" not in t.lower() for t in meta["tags"]),
      str(meta["tags"]))

META_SRC = (ROOT / "ytstudio" / "phases" / "metadata.py").read_text(encoding="utf-8")
check("T2f las reglas de Short viajan en el prompt del estratega",
      "SHORT VERTICAL" in META_SRC and "PROHIBIDO el hashtag" in META_SRC)

# En horizontal, nada de esto se aplica (los capítulos y los 15-25 tags del
# video largo siguen siendo correctos ahí)
CFG_H = {"language": "es", "providers": {"llm": {"name": "mock"}},
         "video": {"width": 1920, "height": 1080}}
h = Project.create("horizontal")
h.set("concept", {"angle": "a", "tone": "b", "audience": "c"})
(h.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": 1, "section": "Gancho", "duration": 10.0, "narration": "Hola.",
     "broll_prompt": "x"}]}), encoding="utf-8")
metadata_phase.run(h, CFG_H)
mh = read_json_tolerant(h.dir / DIRS["final"] / "metadata.json")
check("T2g en horizontal los metadatos quedan como siempre",
      len(mh["tags"]) >= 3 and "title_options" in mh)

# ---------------------------------------------------------------------------
# T3 — la lista de comprobación
# ---------------------------------------------------------------------------
print("\nT3 la lista de comprobación antes de publicar")

# El proyecto q ya tiene metadatos; se le añade una auditoría limpia y el SRT
q.set("shorts_audit", {"problemas": [], "avisos": [], "correcto": ["ok"]})
(q.dir / DIRS["subtitles"] / "subtitulos.srt").write_text("1\n", encoding="utf-8")
items = shorts.publish_checklist(q, CFG_V)
por = {i["label"]: i for i in items}

check("T3a comprueba la revisión técnica",
      any("revisión técnica" in i["label"] for i in items))
check("T3b evalúa el largo del título contra 40-70",
      any("40-70" in i["label"] for i in items))
check("T3c comprueba que no haya hashtag de Shorts",
      por.get("Sin el hashtag de Shorts", {}).get("ok") is True)
check("T3d cuenta los hashtags de la descripción",
      any("hashtags en la descripción" in i["label"] for i in items))
check("T3e comprueba el enlace al video largo en la descripción",
      por.get("La descripción enlaza al video largo", {}).get("ok") is True)
check("T3f comprueba que el SRT exista",
      por.get("Archivo de subtítulos (SRT) generado", {}).get("ok") is True)

manuales = [i for i in items if i["ok"] is None]
check("T3g los pasos que solo puede mirar una persona van con ☐ (ok=None)",
      len(manuales) >= 3, str(len(manuales)))
check("T3h el video relacionado es uno de ellos, con la ruta exacta en Studio",
      any("VIDEO RELACIONADO" in i["label"] and "Studio" in i["detail"]
          for i in manuales))
check("T3i la regla de doble pista es otro",
      any("SONIDO APAGADO" in i["label"] for i in manuales))
check("T3j declarar contenido sintético es otro",
      any("sintético" in i["label"] for i in manuales))

# Sin metadatos ni auditoría, la lista lo dice en rojo — no finge verde
vacio = Project.create("vertical-vacio")
items2 = shorts.publish_checklist(vacio, CFG_V)
check("T3k sin auditoría ni metadatos, la lista queda en rojo (no finge)",
      any(i["ok"] is False for i in items2),
      str([(i["label"], i["ok"]) for i in items2[:3]]))

# ---------------------------------------------------------------------------
# T4 — la fase de publicación entiende los Shorts
# ---------------------------------------------------------------------------
print("\nT4 la fase de publicación")

q.set("final_video", str(q.dir / DIRS["final"] / "video_final.mp4"))
from ytstudio.phases import publish  # noqa: E402
buf = io.StringIO()
with redirect_stdout(buf):
    publish.run(q, {**CFG_V, "publish": {"enabled": False}})
salida = buf.getvalue()

check("T4a con la publicación apagada, imprime la lista de comprobación",
      "Lista de comprobación del Short" in salida, salida[:200])
check("T4b y recuerda el destino del video relacionado",
      "Video relacionado" in salida and "ABC123XYZ" in salida)
check("T4c la lista queda guardada para la interfaz",
      bool(q.get("publish_checklist")))

PUB = (ROOT / "ytstudio" / "phases" / "publish.py").read_text(encoding="utf-8")
check("T4d pide el permiso de subtítulos en la autorización",
      "youtube.force-ssl" in PUB)
check("T4e sube el SRT como pista aparte", "captions().insert" in PUB)
check("T4f si el SRT falla, explica cómo arreglarlo (token.json / a mano)",
      "token.json" in PUB and "a mano" in PUB)
check("T4g una miniatura rechazada NO tira la fase (despliegue gradual)",
      "no se pudo poner" in PUB and "miniaturas de Shorts" in PUB)
check("T4h limpia los metadatos elegidos justo antes de subir",
      "_prepare_short_body" in PUB and "short_metadata_fixups" in PUB)
check("T4i el aviso del enlace relacionado queda como warning del proyecto",
      "add_warning(aviso)" in PUB)

# En horizontal, la fase no imprime listas de Short
buf2 = io.StringIO()
h.set("final_video", str(h.dir / DIRS["final"] / "video_final.mp4"))
with redirect_stdout(buf2):
    publish.run(h, {**CFG_H, "publish": {"enabled": False}})
check("T4j en horizontal no hay lista de Short",
      "Lista de comprobación del Short" not in buf2.getvalue())

# ---------------------------------------------------------------------------
# T5 — enchufado a la interfaz
# ---------------------------------------------------------------------------
print("\nT5 enchufado a la interfaz")

from ytstudio.webui import server as srv  # noqa: E402
srv.Project = Project
(q.dir / DIRS["final"] / "video_final.mp4").write_bytes(b"x")
d = srv.api_project_detail(slug)
check("T5a el detalle sirve la lista calculada EN VIVO",
      bool(d.get("publish_checklist")))

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T5b la interfaz {nombre} pinta «Antes de publicar»",
          "Antes de publicar" in html)
    check(f"T5c la interfaz {nombre} distingue ✔ ✖ ☐",
          "✔" in html and "☐" in html)
    check(f"T5d la interfaz {nombre} explica los puntos ☐",
          "no los puede comprobar una máquina" in html)

# ---------------------------------------------------------------------------
# T6 — documentación
# ---------------------------------------------------------------------------
print("\nT6 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T6a el manual {nombre} explica la lista «Antes de publicar»",
          "Antes de publicar" in texto)
    check(f"T6b el manual {nombre} explica el permiso nuevo (token.json)",
          "token.json" in texto)
    check(f"T6c el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T6d el CHANGELOG cuenta lo que trajo la v0.65.0",
      "## v0.65.0" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.65.0: metadatos de Short y lista antes de publicar — correcto.")
