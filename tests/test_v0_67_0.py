"""Batería v0.67.0 — lo que se había perdido al cambiar de plantilla, la ruta
de navegación y el borrador del proyecto nuevo.

Tres cosas, y un fallo de fondo que salió al probarlas:

1.  LA PLANTILLA NUEVA HABÍA PERDIDO MEDIO FORMULARIO. Al crear un proyecto
    ya no se podían subir archivos, ni pegar enlaces de referencia, ni elegir
    la presencia del personaje, ni el canal. Sin archivos, un proyecto NO se
    podía crear a partir de un PDF o de una narración grabada: había que
    escribir algo a mano aunque el material estuviera listo. También faltaban
    el aviso de modo vista previa, la pantalla de Concepto, las descargas del
    video terminado y el gasto real por proveedor.

2.  NO HABÍA RUTA DE NAVEGACIÓN. Ninguna de las dos plantillas decía dónde
    estabas ni cómo subir un nivel, y el botón Atrás del navegador no hacía
    nada porque ninguna pantalla tenía dirección propia.

3.  EL FORMULARIO SE BORRABA SOLO. Empezar un proyecto, salir a Ajustes a
    poner una clave y volver dejaba el formulario en blanco.

4.  EL ESTADO DEL PROYECTO SE GUARDABA A MEDIAS. `project.json` se escribía
    encima de sí mismo, así que quedaba vacío un instante en cada guardado.
    La interfaz, que lo lee cada segundo y medio mientras se genera, caía a
    veces justo en ese instante y contestaba «El servidor respondió con
    error» sin que nada estuviera roto. Ahora se escribe aparte y se pone en
    su sitio de un solo golpe.

No usa claves ni internet.
"""

import json
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


STATIC = ROOT / "ytstudio" / "webui" / "static"
NUEVA = (STATIC / "index.html").read_text(encoding="utf-8")
CLASICA = (STATIC / "index-clasica.html").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# T1 — el formulario de proyecto nuevo vuelve a estar completo en las DOS
# ---------------------------------------------------------------------------
print("T1 el formulario de proyecto nuevo, completo en las dos plantillas")

# Las seis clases de material que el motor sabe repartir por carpetas.
for cat in ("guion", "voz", "broll", "referencia", "personaje", "reaccion"):
    check(f"T1a la plantilla nueva pide material de tipo «{cat}»",
          f"'{cat}'" in NUEVA.split("const CATS_NUEVO")[1].split("];")[0])

check("T1b la plantilla nueva envía los archivos al crear",
      "data_base64: await leerB64(p.file)" in NUEVA)
check("T1c y los enlaces de referencia",
      "links: enlaces.value.split" in NUEVA)
check("T1d y la presencia del personaje cuando hay personaje",
      "body.character_presence" in NUEVA and "body.character_pip" in NUEVA)
check("T1e y el canal elegido",
      "body.channel_id = st.channel_id" in NUEVA)
check("T1f el aviso de modo vista previa está en las dos",
      "Modo vista previa" in NUEVA and "Modo vista previa" in CLASICA)
check("T1g se puede crear un proyecto SOLO con archivos (sin escribir nada)",
      "!texto.value.trim() && !enCola.length && !enlaces.value.trim()" in NUEVA)
check("T1h se avisa del límite de 300 MB antes de subir",
      "300 * 1024 * 1024" in NUEVA and "300*1024*1024" in CLASICA)

# El servidor tiene que seguir aceptando exactamente eso.
from ytstudio.webui import server as srv  # noqa: E402

fuente_crear = Path(srv.__file__).read_text(encoding="utf-8")
crear = fuente_crear.split("def api_create_project")[1].split("\ndef ")[0]
for campo in ("files", "links", "channel_id", "style_id",
              "character_presence", "character_pip", "short_template"):
    check(f"T1i el servidor lee «{campo}» al crear", f'"{campo}"' in crear)

# ---------------------------------------------------------------------------
# T2 — nada de lo que hacía la clásica se quedó fuera de la nueva
# ---------------------------------------------------------------------------
print("\nT2 paridad de funciones entre las dos plantillas")

check("T2a la nueva tiene pantalla de Concepto", "function viewConcepto" in NUEVA)
check("T2b con títulos, ángulo, audiencia, tono, música y estructura",
      all(t in NUEVA for t in ("title_options", "c.angle", "c.audience",
                               "c.tone", "music_direction", "c.structure")))
check("T2c y la paleta del estilo visual", "visual.palette" in NUEVA)
check("T2d la nueva ofrece descargar los subtítulos",
      "subtitulos.srt" in NUEVA and "subtitulos.srt" in CLASICA)
check("T2e y la miniatura", "download: 'miniatura.jpg'" in NUEVA)
check("T2f el gasto real se desglosa por proveedor en las dos",
      "by_provider" in NUEVA and "by_provider" in CLASICA)
check("T2g la lista de proyectos se puede filtrar por estado",
      "'running', 'En curso'" in NUEVA)
check("T2h y renombrar sin entrar al proyecto",
      "Nombre nuevo del proyecto" in NUEVA)
check("T2i el Material avisa de que hay texto pegado",
      "has_text_input" in NUEVA and "has_text_input" in CLASICA)

# La pestaña de guion es una pestaña más: se puede saltar a otra desde ella.
guion = NUEVA.split("function viewGuion")[1].split("\nfunction ")[0]
check("T2j desde el guion se puede saltar a cualquier otra pestaña",
      guion.count("projHeader('guion'") == 2)

# ---------------------------------------------------------------------------
# T3 — la ruta de navegación (migas de pan) en las dos plantillas
# ---------------------------------------------------------------------------
print("\nT3 la ruta de navegación")

for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T3a la plantilla {nombre} pinta la barra de ruta",
          'id="ruta"' in html and "function pintarRuta" in html)
    check(f"T3b la plantilla {nombre} da dirección propia a cada pantalla",
          "history.pushState" in html and "history.replaceState" in html)
    check(f"T3c el botón Atrás del navegador funciona en la {nombre}",
          "'popstate'" in html or '"popstate"' in html)
    check(f"T3d y arranca en la pantalla de la dirección en la {nombre}",
          "location.hash" in html)
    check(f"T3e la {nombre} no pide un icono que no existe",
          'rel="icon"' in html)

# Las pantallas que viven dentro de un proyecto llevan su nombre en la ruta.
pantallas = NUEVA.split("const PANTALLAS_PROYECTO = [")[1].split("]")[0]
for p in ("corrida", "material", "concepto", "guion", "escenas",
          "personajes", "metadatos", "shorts"):
    check(f"T3f «{p}» cuelga del proyecto en la ruta", f"'{p}'" in pantallas)

# ---------------------------------------------------------------------------
# T4 — el borrador del proyecto nuevo
# ---------------------------------------------------------------------------
print("\nT4 el borrador del proyecto nuevo")

for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T4a la {nombre} guarda el borrador en el navegador",
          "'ytstudio.borrador.nuevo'" in html)
    check(f"T4b la {nombre} lo recupera al volver",
          "function restaurarBorrador" in html or "leerBorrador()" in html)
    check(f"T4c la {nombre} lo borra al crear el proyecto",
          "borrarBorrador()" in html)
    check(f"T4d la {nombre} avisa de que los archivos hay que volver a elegirlos",
          "volver a elegirlos" in html)
    check(f"T4e la {nombre} deja empezar de cero",
          "Empezar de cero" in html)
    check(f"T4f la {nombre} no guarda en cada tecla (espera a que pares)",
          "setTimeout" in html and "400" in html)

# Un borrador recién abierto y sin tocar NO debe anunciarse como recuperado.
check("T4g un borrador vacío no se anuncia",
      "function borradorConAlgo" in NUEVA and "function borradorConAlgo" in CLASICA)

# ---------------------------------------------------------------------------
# T5 — el estado del proyecto se guarda entero o no se guarda
# ---------------------------------------------------------------------------
print("\nT5 el estado del proyecto nunca se lee a medias")

from ytstudio.project import Project, read_json_tolerant  # noqa: E402
import ytstudio.project as proyecto_mod  # noqa: E402

WORK = Path(tempfile.mkdtemp(prefix="yt067-"))
proyecto_mod.PROJECTS_DIR = WORK

p = Project.create("prueba-atomica")
p.set("titulo", "Los fareros")
check("T5a el proyecto se guarda y se relee",
      Project("prueba-atomica").get("titulo") == "Los fareros")

# Guardar NO puede dejar el archivo vacío en ningún instante: se escribe en
# un temporal y se mueve encima de un golpe.
fuente = Path(proyecto_mod.__file__).read_text(encoding="utf-8")
check("T5b guardar es atómico (os.replace, también en Windows)",
      "os.replace(tmp, self.state_path)" in fuente)
check("T5c cada hilo usa su propio temporal",
      "threading.get_ident()" in fuente)
check("T5d no queda basura si la escritura falla",
      "tmp.unlink()" in fuente)

# Mil guardados con la interfaz leyendo a la vez: ni una lectura rota. Antes
# de arreglarlo, esta prueba fallaba a los pocos ciclos.
errores: list[str] = []
parar = threading.Event()


def _leer():
    while not parar.is_set():
        try:
            read_json_tolerant(p.state_path)
        except Exception as e:                      # pragma: no cover
            errores.append(repr(e))
            return


lector = threading.Thread(target=_leer, daemon=True)
lector.start()
for i in range(400):
    p.set("contador", i)
parar.set()
lector.join(timeout=5)
check("T5e leer el proyecto mientras se guarda 400 veces nunca falla",
      not errores, "; ".join(errores[:2]))

# Un archivo de verdad corrupto sí tiene que dar la cara (no fingir que está
# vacío: eso perdería el proyecto en silencio).
roto = WORK / "roto.json"
roto.write_text("{esto no es json", encoding="utf-8")
try:
    read_json_tolerant(roto)
    check("T5f un JSON corrupto se avisa, no se traga", False, "no lanzó error")
except json.JSONDecodeError:
    check("T5f un JSON corrupto se avisa, no se traga", True)

# Y un proyecto roto no puede tumbar la lista entera.
lista = fuente_crear.split("def api_list_projects")[1].split("\ndef ")[0]
check("T5g un proyecto dañado no tumba la lista", "except Exception" in lista)

shutil.rmtree(WORK, ignore_errors=True)

# ---------------------------------------------------------------------------
# T6 — la documentación al día
# ---------------------------------------------------------------------------
print("\nT6 documentación")

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T6a el CHANGELOG cuenta lo que trae la v0.67.0", "## v0.67.0" in CHANGELOG)

for nombre, ruta in (("nuevo", "MANUAL.md"), ("clásico", "MANUAL-clasica.md")):
    texto = (ROOT / ruta).read_text(encoding="utf-8")
    m = re.search(r"MANUAL_VERSION:\s*([0-9]+\.[0-9]+\.[0-9]+)", texto)
    check(f"T6b el manual {nombre} declara la versión que documenta", bool(m))
    check(f"T6c el manual {nombre} está al día", bool(m) and m.group(1) == "0.67.0",
          m.group(1) if m else "sin marca")
    check(f"T6d el manual {nombre} explica la ruta de navegación",
          "ruta de navegación" in texto.lower() or "migas" in texto.lower())
    check(f"T6e el manual {nombre} explica el borrador",
          "borrador" in texto.lower())

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.67.0: formulario completo, ruta de navegación, borrador y "
      "guardado atómico del proyecto.")
