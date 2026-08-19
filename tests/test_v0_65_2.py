"""Batería v0.65.2 — los proyectos con tilde daban «No encontrado».

Caso real del creador: los Shorts se crearon bien, pero al abrir dos de ellos
—«conservó-la-fortuna-mentira»— la interfaz respondía «El servidor respondió
con error · No encontrado», y el registro de eventos seguía sin enterarse.

La causa, y es de manual: el navegador CODIFICA los acentos al pedir una
dirección. «conservó» viaja como «conserv%C3%B3». El servidor comparaba sus
rutas contra el texto SIN descodificar, y el símbolo «%» no encaja en ninguna,
así que ningún proyecto con tilde o eñe se encontraba jamás. Los que no tenían
acentos funcionaban, que es justo por qué no se había visto antes.

Tres arreglos:

1.  La ruta se DESCODIFICA una vez, antes de compararla. Con eso, los
    proyectos que ya existen con acentos vuelven a abrirse.
2.  Los nombres NUEVOS se fabrican sin acentos (el nombre bonito se guarda
    aparte y es el que se ve), para que el problema no vuelva por otra vía:
    carpetas en Windows, Git, codificaciones.
3.  Un 404 ya no es mudo. No es una excepción, así que no pasaba por el
    manejador de errores y no llegaba al registro — justo el aviso que habría
    señalado esto a la primera.

La prueba levanta el SERVIDOR DE VERDAD y le pide las direcciones tal como
las pide el navegador. Sin claves ni internet.
"""

import json
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


WORK = Path(tempfile.mkdtemp(prefix="v0652_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as elog  # noqa: E402
elog.LOG_PATH = WORK / "data" / "events.log"

from ytstudio.project import DIRS, Project, slugify  # noqa: E402
from ytstudio.webui import server as srv  # noqa: E402

srv.Project = Project
srv.PROJECTS_DIR = WORK / "projects"

# ---------------------------------------------------------------------------
# T1 — los nombres nuevos ya no llevan acentos
# ---------------------------------------------------------------------------
print("T1 el nombre de la carpeta")

casos = [
    ("Conservó la fortuna, mentira", "conservo-la-fortuna-mentira"),
    ("El día que lo enterró", "el-dia-que-lo-enterro"),
    ("Año nuevo", "ano-nuevo"),
    ("Café  con   leche", "cafe-con-leche"),
    ("¿Cuánto te cobran de más?", "cuanto-te-cobran-de-mas"),
]
for texto, esperado in casos:
    check(f"T1a «{texto}» → «{esperado}»", slugify(texto) == esperado,
          slugify(texto))
check("T1b un nombre vacío sigue teniendo respaldo",
      slugify("   ") == "proyecto", slugify("   "))
check("T1c el resultado solo tiene letras simples, números y guiones",
      all(re.fullmatch(r"[a-z0-9-]+", slugify(t)) for t, _ in casos))

# ---------------------------------------------------------------------------
# T2 — contra el servidor de verdad, pidiendo como pide el navegador
# ---------------------------------------------------------------------------
print("\nT2 abrir proyectos desde el navegador")

# Un proyecto que YA existe con tilde (creado antes de este arreglo)
viejo = Project.create("conservó-la-fortuna-mentira")
viejo.state["display_name"] = "Conservó la fortuna, mentira"
viejo.save()
viejo.set("format", "short")
(viejo.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": 1, "section": "Gancho", "duration": 10.0,
     "narration": "Hola."}]}), encoding="utf-8")
Project.create("proyecto-normal")

httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"


def pedir(ruta: str):
    """Como lo pide el navegador: los acentos van codificados."""
    url = BASE + urllib.parse.quote(ruta, safe="/")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


try:
    # La dirección llega codificada de verdad: si no, la prueba no prueba nada
    codificada = urllib.parse.quote("/api/projects/conservó-la-fortuna-mentira",
                                    safe="/")
    check("T2a el navegador codifica el acento (así llega al servidor)",
          "%C3%B3" in codificada, codificada)

    estado, cuerpo = pedir("/api/projects/conservó-la-fortuna-mentira")
    check("T2b abrir un proyecto CON TILDE ya no da «No encontrado»",
          estado == 200, f"HTTP {estado}: {cuerpo}")
    check("T2c y devuelve el proyecto correcto",
          cuerpo.get("display_name") == "Conservó la fortuna, mentira",
          str(cuerpo)[:120])

    for sufijo, que in (("/log", "el registro de su corrida"),
                        ("/shorts-plan", "su plan de Shorts"),
                        ("/estimate", "su estimación de costo")):
        est, _ = pedir(f"/api/projects/conservó-la-fortuna-mentira{sufijo}")
        check(f"T2d {que} también se encuentra", est == 200, f"HTTP {est}")

    est, _ = pedir("/api/projects/proyecto-normal")
    check("T2e los proyectos sin acentos siguen funcionando igual",
          est == 200, f"HTTP {est}")

    # ---------------------------------------------------------------------
    # T3 — un 404 sigue siendo 404, pero deja rastro
    # ---------------------------------------------------------------------
    print("\nT3 el 404 deja rastro")

    est, _ = pedir("/api/direccion-inventada")
    check("T3a una dirección que no existe sigue dando 404", est == 404,
          f"HTTP {est}")
    log = elog.raw_text()
    check("T3b y AHORA queda registrada en el log de eventos",
          "Dirección no reconocida" in log, log[-200:])
    check("T3c con el método y la ruta, para poder diagnosticar",
          "GET /api/direccion-inventada" in log)

    # ---------------------------------------------------------------------
    # T4 — descodificar no abrió ningún agujero
    # ---------------------------------------------------------------------
    print("\nT4 servir archivos sigue siendo seguro")

    for intento in ("/files/proyecto-normal/../../../etc/passwd",
                    "/files/proyecto-normal/..%2f..%2f..%2fetc%2fpasswd"):
        est, _ = pedir(intento)
        check(f"T4a no se escapa de la carpeta ({intento[:38]}…)",
              est in (403, 404), f"HTTP {est}")
finally:
    httpd.shutdown()

# ---------------------------------------------------------------------------
# T5 — el arreglo está donde debe
# ---------------------------------------------------------------------------
print("\nT5 el código")

SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T5a la ruta se descodifica en un solo sitio",
      "def _ruta(self)" in SRV and "urllib.parse.unquote" in SRV)
check("T5b y las cuatro clases de petición la usan",
      SRV.count("path = self._ruta()") == 4,
      str(SRV.count("path = self._ruta()")))
check("T5c los 404 pasan por el que deja rastro",
      SRV.count("self._no_encontrado()") == 4,
      str(SRV.count("self._no_encontrado()")))
check("T5d se explica POR QUÉ, para que nadie lo deshaga sin querer",
      "codifica los acentos, siempre" in SRV)

PRJ = (ROOT / "ytstudio" / "project.py").read_text(encoding="utf-8")
check("T5e los nombres se limpian con unicodedata",
      "unicodedata.normalize" in PRJ and "combining" in PRJ)
check("T5f y se aclara que el nombre bonito se guarda aparte",
      "display_name" in PRJ.split("def slugify")[1][:1200])

# ---------------------------------------------------------------------------
# T6 — documentación
# ---------------------------------------------------------------------------
print("\nT6 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T6a el manual {nombre} explica el «No encontrado» con tildes",
          "No encontrado" in texto)
    check(f"T6b el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T6c el CHANGELOG cuenta lo que arregló la v0.65.2",
      "## v0.65.2" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.65.2: los proyectos con tilde se abren.")
