"""Batería v0.67.2 — guardar el proyecto ya no falla en Windows.

EL FALLO. La v0.67.0 arregló que la interfaz leyera `project.json` a medias:
en vez de escribir encima del archivo, se escribe en uno aparte y se mueve a
su sitio de un golpe. En Linux y Mac eso funciona siempre. En Windows NO:
Windows no deja sustituir un archivo que otro programa tenga abierto en ese
instante, y contesta «Acceso denegado» (WinError 5).

Como la interfaz lee `project.json` cada segundo y medio mientras se genera el
video, tarde o temprano una lectura y un guardado coinciden. Y entonces el
error no salía por pantalla como un aviso: reventaba dentro del guardado, que
es lo que llaman todas las fases al apuntar su progreso. Habría abortado la
generación a media faena, tirando minutos de trabajo y el dinero ya gastado.

Lo vio el creador al correr `probar.bat` en su equipo. El arreglo espera un
poco y reintenta —la lectura que estorba dura microsegundos, así que casi
siempre basta el primer reintento— y, si tras ~0,7 s siguiera bloqueado (un
antivirus revisando la carpeta), escribe directamente encima: es la mala
menor, porque quien lee ya sabe reintentar y fallar aquí costaría la corrida.

CÓMO SE PRUEBA SIN WINDOWS. Estas baterías corren en cualquier sistema, así
que aquí se IMITA el comportamiento de Windows: se sustituye `os.replace` por
una versión que da «acceso denegado» cuando el archivo de destino está
abierto. Así el fallo se reproduce a voluntad en cualquier equipo.

No usa claves ni internet.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


import ytstudio.project as pm  # noqa: E402
from ytstudio.project import Project, read_json_tolerant  # noqa: E402

WORK = Path(tempfile.mkdtemp(prefix="yt0672-"))
pm.PROJECTS_DIR = WORK

REPLACE_REAL = os.replace

# ---------------------------------------------------------------------------
# T1 — el guardado aguanta un «acceso denegado» pasajero
# ---------------------------------------------------------------------------
print("T1 un bloqueo pasajero, como el de Windows")

p = Project.create("bloqueo-pasajero")
restantes = {"n": 3}   # las 3 primeras veces «Windows» dice que no


def _replace_falla_al_principio(src, dst):
    if restantes["n"] > 0:
        restantes["n"] -= 1
        raise PermissionError(5, "Acceso denegado", str(src), 5, str(dst))
    return REPLACE_REAL(src, dst)


os.replace = _replace_falla_al_principio
try:
    p.set("titulo", "Los fareros")
    guardo = True
except Exception as e:                                  # pragma: no cover
    guardo = False
    print("     ", repr(e))
finally:
    os.replace = REPLACE_REAL

check("T1a guardar no revienta aunque el primer intento sea rechazado", guardo)
check("T1b se reintentó de verdad (se agotaron los rechazos)",
      restantes["n"] == 0, f"quedaban {restantes['n']}")
check("T1c y el dato quedó guardado",
      guardo and Project("bloqueo-pasajero").get("titulo") == "Los fareros")
check("T1d sin dejar archivos temporales tirados",
      not list(p.dir.glob("*.tmp")), str([f.name for f in p.dir.glob("*.tmp")]))

# ---------------------------------------------------------------------------
# T2 — un bloqueo que no se suelta nunca no puede tumbar la generación
# ---------------------------------------------------------------------------
print("\nT2 un bloqueo permanente (un antivirus, por ejemplo)")


def _replace_siempre_denegado(src, dst):
    raise PermissionError(5, "Acceso denegado", str(src), 5, str(dst))


p2 = Project.create("bloqueo-permanente")
os.replace = _replace_siempre_denegado
t0 = time.monotonic()
try:
    p2.set("titulo", "El faro del fin del mundo")
    aguanto = True
except Exception as e:                                  # pragma: no cover
    aguanto = False
    print("     ", repr(e))
finally:
    os.replace = REPLACE_REAL
tardanza = time.monotonic() - t0

check("T2a el guardado NO lanza el error hacia arriba", aguanto,
      "reventaría la fase a media generación")
check("T2b el dato acaba en el disco igualmente",
      aguanto and json.loads(p2.state_path.read_text(encoding="utf-8"))
      ["data"]["titulo"] == "El faro del fin del mundo")
# Reintentar está bien; quedarse colgado, no. Todo el forcejeo cabe en ~1 s.
check("T2c y no se queda colgado esperando", tardanza < 3.0,
      f"tardó {tardanza:.1f}s")
check("T2d sin dejar archivos temporales tirados",
      not list(p2.dir.glob("*.tmp")), str([f.name for f in p2.dir.glob("*.tmp")]))

# ---------------------------------------------------------------------------
# T3 — la carrera de verdad: la interfaz leyendo mientras el motor guarda
# ---------------------------------------------------------------------------
print("\nT3 la interfaz leyendo mientras el motor guarda (a la manera de Windows)")

p3 = Project.create("carrera")
DESTINO = str(p3.state_path)
abiertos: set[str] = set()


def _replace_estilo_windows(src, dst):
    """Como Windows: si alguien tiene el destino abierto, «acceso denegado»."""
    if str(dst) in abiertos:
        raise PermissionError(5, "Acceso denegado", str(src), 5, str(dst))
    return REPLACE_REAL(src, dst)


errores_lectura: list[str] = []
parar = threading.Event()


def _interfaz():
    """Lee como la interfaz: abre el archivo, lo lee y espera al siguiente."""
    while not parar.is_set():
        abiertos.add(DESTINO)
        try:
            read_json_tolerant(p3.state_path)
        except Exception as e:                          # pragma: no cover
            errores_lectura.append(repr(e))
            return
        finally:
            abiertos.discard(DESTINO)
        time.sleep(0.002)


os.replace = _replace_estilo_windows
lector = threading.Thread(target=_interfaz, daemon=True)
lector.start()
fallo_guardando = None
try:
    for i in range(150):
        p3.set("contador", i)
except Exception as e:                                  # pragma: no cover
    fallo_guardando = repr(e)
finally:
    parar.set()
    lector.join(timeout=5)
    os.replace = REPLACE_REAL

check("T3a 150 guardados con la interfaz encima: ninguno revienta",
      fallo_guardando is None, fallo_guardando or "")
check("T3b y ninguna lectura sale rota",
      not errores_lectura, "; ".join(errores_lectura[:2]))
check("T3c lo último guardado es lo que queda en disco",
      Project("carrera").get("contador") == 149,
      str(Project("carrera").get("contador")))
check("T3d sin archivos temporales tirados",
      not list(p3.dir.glob("*.tmp")), str([f.name for f in p3.dir.glob("*.tmp")]))

# ---------------------------------------------------------------------------
# T4 — leer también aguanta el «acceso denegado» de Windows
# ---------------------------------------------------------------------------
print("\nT4 leer mientras el archivo se está sustituyendo")

p4 = Project.create("lectura")
p4.set("titulo", "Faros")
lecturas = {"n": 2}
read_bytes_real = Path.read_bytes


def _read_bytes_ocupado(self):
    if str(self) == str(p4.state_path) and lecturas["n"] > 0:
        lecturas["n"] -= 1
        raise PermissionError(5, "Acceso denegado", str(self))
    return read_bytes_real(self)


Path.read_bytes = _read_bytes_ocupado
try:
    leido = read_json_tolerant(p4.state_path)
    leyo = True
except Exception as e:                                  # pragma: no cover
    leyo = False
    leido = {}
    print("     ", repr(e))
finally:
    Path.read_bytes = read_bytes_real

check("T4a leer reintenta si Windows dice «ocupado»", leyo)
check("T4b se agotaron los rechazos (reintentó de verdad)", lecturas["n"] == 0)
check("T4c y devolvió el contenido bueno",
      leyo and leido.get("data", {}).get("titulo") == "Faros")

# ---------------------------------------------------------------------------
# T4bis — abrir un proyecto ya no lo reescribe «por si acaso»
# ---------------------------------------------------------------------------
print("\nT4bis abrir un proyecto no lo reescribe si no hay nada que migrar")

# Cada pregunta de la interfaz al servidor ABRE el proyecto, y abrirlo lo
# reescribía siempre por si venía de una versión antigua en otra codificación.
# Con la interfaz preguntando cada segundo y medio, eso son decenas de
# escrituras por minuto sin que nada haya cambiado: disco gastado para nada y,
# en Windows, muchísimas más ocasiones de chocar con una lectura.
p5 = Project.create("sin-migrar")
p5.set("titulo", "Los faros")
sello = p5.state_path.stat().st_mtime_ns
time.sleep(0.02)
for _ in range(20):
    Project("sin-migrar")
check("T4bis-a abrir 20 veces un proyecto sano no toca el archivo",
      p5.state_path.stat().st_mtime_ns == sello)

# Pero lo que SÍ hay que migrar, se sigue migrando.
viejo = WORK / "de-otra-epoca"
viejo.mkdir()
(viejo / "project.json").write_bytes(json.dumps(
    {"slug": "de-otra-epoca", "phases": {}, "data": {"titulo": "Canción"},
     "created_at": 1, "display_name": "Canción"},
    ensure_ascii=False).encode("cp1252"))
pv = Project("de-otra-epoca")
crudo = (viejo / "project.json").read_bytes()
check("T4bis-b un proyecto viejo en otra codificación se lee bien",
      pv.get("titulo") == "Canción")
check("T4bis-c y se reescribe en UTF-8 de una vez",
      "Canción".encode("utf-8") in crudo)

incompleto = WORK / "incompleto"
incompleto.mkdir()
(incompleto / "project.json").write_text(
    json.dumps({"slug": "incompleto", "phases": {}, "data": {}}),
    encoding="utf-8")
Project("incompleto")
guardado = json.loads((incompleto / "project.json").read_text(encoding="utf-8"))
check("T4bis-d a un proyecto sin fecha ni nombre se le ponen y se guarda",
      bool(guardado.get("created_at"))
      and guardado.get("display_name") == "incompleto")

# La función de leer sigue sirviendo igual a quien no pregunta por la
# codificación (la usan la biblioteca, las escenas, los metadatos…).
check("T4bis-e leer un JSON normal sigue devolviendo solo el contenido",
      isinstance(read_json_tolerant(incompleto / "project.json"), dict))

# ---------------------------------------------------------------------------
# T5 — que el arreglo siga escrito donde debe
# ---------------------------------------------------------------------------
print("\nT5 el arreglo, en su sitio")

fuente = Path(pm.__file__).read_text(encoding="utf-8")
check("T5a el reemplazo tiene su propia función con reintentos",
      "def _poner_en_su_sitio" in fuente)
check("T5b que atrapa el «acceso denegado» de Windows",
      "except PermissionError" in fuente.split("def _poner_en_su_sitio")[1]
      .split("\n    def ")[0])
check("T5c y como último recurso escribe encima antes que fallar",
      "self.state_path.write_text(" in fuente.split("def _poner_en_su_sitio")[1]
      .split("\n    def ")[0])
check("T5d leer también aguanta el «acceso denegado»",
      "except PermissionError" in fuente.split("def read_json_tolerant")[1]
      .split("\nclass ")[0])
# El comentario ya no puede prometer que en Windows va de seguido: era mentira.
check("T5e el comentario no promete que Windows sustituye sin problemas",
      "os.replace es atómico también en Windows" not in fuente)

shutil.rmtree(WORK, ignore_errors=True)

# ---------------------------------------------------------------------------
# T6 — documentación al día
# ---------------------------------------------------------------------------
print("\nT6 documentación")

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T6a el CHANGELOG cuenta el arreglo de la v0.67.2",
      "## v0.67.2" in CHANGELOG)
activa = re.search(r"^## v([0-9]+\.[0-9]+\.[0-9]+)", CHANGELOG, re.M)
for nombre, ruta in (("nuevo", "MANUAL.md"), ("clásico", "MANUAL-clasica.md")):
    texto = (ROOT / ruta).read_text(encoding="utf-8")
    m = re.search(r"MANUAL_VERSION:\s*([0-9]+\.[0-9]+\.[0-9]+)", texto)
    check(f"T6b el manual {nombre} va a la par del programa",
          bool(m) and bool(activa) and m.group(1) == activa.group(1),
          f"manual {m.group(1) if m else '?'} · programa "
          f"{activa.group(1) if activa else '?'}")

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.67.2: guardar el proyecto aguanta el bloqueo de archivos de "
      "Windows y nunca tumba la generación.")
