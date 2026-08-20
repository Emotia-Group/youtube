"""Batería v0.67.1 — el canal ya vuelve a traer sus estilos.

EL FALLO. En el formulario de proyecto nuevo de la plantilla nueva, elegir un
canal dejaba el desplegable de estilos con una sola opción («Sin estilo
guardado») y ninguna más: la cascada no traía nada, así que no se podía
reutilizar un estilo guardado desde ahí.

LA CAUSA. La lista de estilos se repinta con `replaceChildren`, que es un
método NATIVO del navegador. El ayudante `el()` de la interfaz sí aplana las
listas que se le pasan —por eso `el('select', {}, estilos.map(...))` funciona—,
pero `replaceChildren` NO: convierte el array en texto y se queda sin opciones.
Había que desplegarlo con «...».

Es una trampa fácil de repetir, así que esta batería no busca un texto
concreto: LEE el código de las tres interfaces y comprueba que ningún método
del DOM reciba una lista sin desplegar. Y comprueba que el detector caza el
fallo original, para que no sea un adorno que da luz verde pase lo que pase.

No usa claves ni internet.
"""

import re
import sys
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
# T1 — la cascada canal → estilo vuelve a traer los estilos
# ---------------------------------------------------------------------------
print("T1 la cascada de canal a estilo")

# El desplegable de estilos se repinta al cambiar de canal. `replaceChildren`
# es del NAVEGADOR y no aplana listas como sí hace el ayudante `el()`: si se le
# pasa el array de estilos tal cual, lo convierte en texto y el desplegable se
# queda sin opciones. Tiene que ir con «...».
casc = NUEVA.split("function pintarEstilos")[1].split("\n  }")[0]
check("T1a los estilos se filtran por el canal elegido",
      "s.channel_id === st.channel_id" in casc)
check("T1b y se vuelcan al desplegable uno a uno, no como lista",
      "...suyos.map(" in casc)
check("T1c cambiar de canal repinta la lista de estilos",
      "pintarEstilos(); apunta();" in NUEVA)
check("T1d un canal con un solo estilo lo deja ya elegido",
      "suyos.length === 1" in casc)
check("T1e «Sin canal» enseña todos los estilos",
      "!st.channel_id ||" in casc)


# Y que la trampa no se repita en ningún otro sitio: los métodos NATIVOS del
# DOM no aplanan arrays, así que todo argumento que sea una lista tiene que
# llevar «...» delante. Esto se comprueba leyendo el código, no buscando un
# texto concreto: es lo único que habría cazado el fallo original.
NATIVOS_DOM = ("replaceChildren", "append", "prepend", "replaceWith",
               "before", "after")


def _argumentos(texto, i):
    """Texto de los argumentos de la llamada cuyo '(' está en i."""
    prof, j, cad, esc = 0, i, None, False
    while j < len(texto):
        c = texto[j]
        if cad:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == cad:
                cad = None
        elif c in "'\"`":
            cad = c
        elif c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
            if prof == 0:
                return texto[i + 1:j]
        j += 1
    return None


def _partir(args):
    """Parte el texto en argumentos de nivel superior."""
    fuera, act, prof, cad, esc = [], "", 0, None, False
    for c in args:
        if cad:
            act += c
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == cad:
                cad = None
            continue
        if c in "'\"`":
            cad = c
            act += c
            continue
        if c in "([{":
            prof += 1
        elif c in ")]}":
            prof -= 1
        if c == "," and prof == 0:
            fuera.append(act)
            act = ""
        else:
            act += c
    if act.strip():
        fuera.append(act)
    return fuera


def _en_nivel_0(arg, aguja):
    prof, cad, esc = 0, None, False
    for k, c in enumerate(arg):
        if cad:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == cad:
                cad = None
            continue
        if c in "'\"`":
            cad = c
            continue
        if c in "([{":
            prof += 1
        elif c in ")]}":
            prof -= 1
        elif prof == 0 and arg.startswith(aguja, k):
            return True
    return False


def listas_sin_desplegar(texto, etiqueta):
    """Llamadas a métodos del DOM a las que se les pasa un array entero."""
    malas = []
    for m in re.finditer(r"\.(" + "|".join(NATIVOS_DOM) + r")\s*\(", texto):
        args = _argumentos(texto, m.end() - 1)
        if args is None:
            continue
        for arg in _partir(args):
            a = arg.strip()
            if not a or a.startswith("..."):
                continue
            if (a.startswith("[") or _en_nivel_0(a, ".map(")
                    or _en_nivel_0(a, ".filter(")):
                linea = texto[:m.start()].count("\n") + 1
                malas.append(f"{etiqueta}:{linea} .{m.group(1)}({a[:60]}…)")
    return malas


PLANTILLAS = {"nueva": NUEVA, "clásica": CLASICA,
              "panel": (ROOT / "ytpanel" / "static" / "index.html")
              .read_text(encoding="utf-8")}
for nombre, html in PLANTILLAS.items():
    malas = listas_sin_desplegar(html, nombre)
    check(f"T2a en la plantilla {nombre} ningún método del DOM recibe una "
          f"lista sin desplegar", not malas, " · ".join(malas[:3]))

# El detector tiene que cazar de verdad el fallo original (si no, es un
# adorno que da luz verde pase lo que pase).
ROTO = """
  selEstilo.replaceChildren(
    el('option', { value: '' }, 'Sin estilo'),
    suyos.map(s => el('option', { value: s.id }, s.name)));
"""
check("T2b el detector reconoce el fallo que se arregló",
      bool(listas_sin_desplegar(ROTO, "prueba")))
SANO = """
  selEstilo.replaceChildren(
    el('option', { value: '' }, 'Sin estilo'),
    ...suyos.map(s => el('option', { value: s.id }, s.name)));
"""
check("T2c y no se queja del código correcto",
      not listas_sin_desplegar(SANO, "prueba"))

# ---------------------------------------------------------------------------
# T3 — el canal y el estilo elegidos llegan de verdad al proyecto
# ---------------------------------------------------------------------------
print("\nT3 lo elegido llega al proyecto")

from ytstudio.webui import server as srv  # noqa: E402

crear = (Path(srv.__file__).read_text(encoding="utf-8")
         .split("def api_create_project")[1].split("\ndef ")[0])
check("T3a el servidor guarda el canal del proyecto",
      'project.set("channel_id", body["channel_id"])' in crear)
check("T3b y el estilo guardado",
      'project.set("style_id", body["style_id"])' in crear)
check("T3c la interfaz envía los dos",
      "body.style_id = st.style_id" in NUEVA
      and "body.channel_id = st.channel_id" in NUEVA)
# El estilo es lo que de verdad evita volver a pagar el análisis: la fase de
# concepto lo lee del proyecto.
concepto = (ROOT / "ytstudio" / "phases" / "concept.py").read_text(encoding="utf-8")
check("T3d y la fase de concepto usa el estilo guardado",
      'project.get("style_id")' in concepto)

# El borrador tiene que recordar también el canal y el estilo: si no, volver
# de Ajustes dejaba el formulario a medias otra vez.
check("T3e el borrador recuerda el canal y el estilo",
      "channel_id: st.channel_id" in NUEVA and "style_id: st.style_id" in NUEVA)

# ---------------------------------------------------------------------------
# T4 — documentación al día
# ---------------------------------------------------------------------------
print("\nT4 documentación")

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T4a el CHANGELOG cuenta el arreglo de la v0.67.1", "## v0.67.1" in CHANGELOG)
activa = re.search(r"^## v([0-9]+\.[0-9]+\.[0-9]+)", CHANGELOG, re.M)
for nombre, ruta in (("nuevo", "MANUAL.md"), ("clásico", "MANUAL-clasica.md")):
    texto = (ROOT / ruta).read_text(encoding="utf-8")
    m = re.search(r"MANUAL_VERSION:\s*([0-9]+\.[0-9]+\.[0-9]+)", texto)
    check(f"T4b el manual {nombre} va a la par del programa",
          bool(m) and bool(activa) and m.group(1) == activa.group(1),
          f"manual {m.group(1) if m else '?'} · programa "
          f"{activa.group(1) if activa else '?'}")

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.67.1: el canal trae sus estilos y ningún método del DOM recibe "
      "una lista sin desplegar.")
