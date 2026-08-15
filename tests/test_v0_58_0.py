"""Batería v0.58.0 — el MANUAL, ahora con capturas y una receta por formato.

El creador pidió un manual que cualquier persona sin conocimientos técnicos
pueda seguir: paso a paso para cada tipo de video, con capturas de pantalla y
sin jerga. Aquí eso deja de ser una promesa y se convierte en comprobaciones
que fallan si el manual se degrada.

Verifica:
1. Las capturas existen de verdad, son PNG y todas las que el manual nombra
   están en disco (un manual con imágenes rotas es peor que uno sin ellas).
2. Ninguna captura queda huérfana (si está en docs/manual, se usa).
3. El servidor SIRVE esas imágenes (ruta /docs/manual/…) y no deja salir de
   esa carpeta.
4. El visor del manual RENDERIZA imágenes (antes las mostraba como texto
   crudo: «![alt](ruta)»).
5. Hay una receta paso a paso para CADA formato de video del catálogo, y las
   plantillas de corto están todas documentadas.
6. Los nombres de la interfaz que el manual menciona son los de verdad
   (pestañas y menús): un manual que nombra pestañas inexistentes desorienta
   más que ayudar.
7. Sigue siendo un manual sin jerga: los términos inevitables se explican.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import re  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


MANUAL = (ROOT / "MANUAL.md").read_text(encoding="utf-8")
bajo = MANUAL.lower()
IMG_DIR = ROOT / "docs" / "manual"

# ---------------------------------------------------------------------------
# T1 — las capturas existen y ninguna referencia está rota
# ---------------------------------------------------------------------------
refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", MANUAL)
check("T1 el manual incluye capturas de pantalla", len(refs) >= 10,
      f"{len(refs)} imágenes")

rotas = [r for r in refs if not (ROOT / r).is_file()]
check("T1b ninguna captura referenciada falta en disco", not rotas, str(rotas))

check("T1c las capturas viven en docs/manual y son PNG",
      all(r.startswith("docs/manual/") and r.endswith(".png") for r in refs),
      str([r for r in refs
           if not (r.startswith("docs/manual/") and r.endswith(".png"))]))

en_disco = {f"docs/manual/{p.name}" for p in IMG_DIR.glob("*.png")}
huerfanas = sorted(en_disco - set(refs))
check("T1d no hay capturas huérfanas (todas se usan en el manual)",
      not huerfanas, str(huerfanas))

# Peso razonable: el repositorio no es un álbum de fotos.
pesadas = [p.name for p in IMG_DIR.glob("*.png") if p.stat().st_size > 900_000]
check("T1e ninguna captura es desproporcionada (<900 KB)", not pesadas,
      str(pesadas))

# ---------------------------------------------------------------------------
# T2 — el servidor sirve las capturas (y solo esas)
# ---------------------------------------------------------------------------
import inspect  # noqa: E402

from ytstudio.webui import server as srv  # noqa: E402

ssrc = inspect.getsource(srv)
check("T2 hay una ruta que sirve las capturas del manual",
      "/docs/manual/" in ssrc, "")

rutas = re.findall(r'r"/docs/manual/\(([^)]+)\)"', ssrc)
# Sin «/» en el patrón no se puede pedir «…/docs/manual/../../.env»: la ruta
# solo alcanza archivos sueltos de esa carpeta.
check("T2b la ruta no admite subcarpetas ni saltos de directorio",
      bool(rutas) and "/" not in rutas[0], str(rutas))

# ---------------------------------------------------------------------------
# T3 — el visor renderiza las imágenes en vez de escupir el markdown
# ---------------------------------------------------------------------------
html = (ROOT / "ytstudio" / "webui" / "static" / "index.html").read_text(
    encoding="utf-8")
inline = html.split("function mdInline")[1][:900] if "function mdInline" in html else ""
check("T3 el visor del manual convierte las imágenes a <img>",
      "<img" in inline, "")
check("T3b y lo hace ANTES que los enlaces (si no, «![x](y)» sale roto)",
      inline.find("!\\[") < inline.find("\\[([^\\]]+)\\]"), "")

# ---------------------------------------------------------------------------
# T4 — una receta por formato y todas las plantillas de corto
# ---------------------------------------------------------------------------
from ytstudio.catalog import FORMATS, SHORT_TEMPLATES  # noqa: E402

# Cómo se reconoce cada formato del catálogo dentro del texto del manual.
# Si mañana se añade un formato nuevo y nadie lo documenta, esto se pone rojo.
_SEÑA = {"long": "video largo", "short": "youtube short",
         "reel": "instagram reel", "tiktok": "tiktok",
         "ad_square": "cuadrado 1:1", "ad_45": "4:5"}
sin_seña = [k for k in FORMATS if k not in _SEÑA]
check("T4 la lista de formatos del manual está al día con el catálogo",
      not sin_seña, str(sin_seña))
faltan_fmt = [k for k, s in _SEÑA.items() if k in FORMATS and s not in bajo]
check("T4b el manual documenta los 6 formatos de video", not faltan_fmt,
      str(faltan_fmt))

faltan_tpl = [k for k, t in SHORT_TEMPLATES.items()
              if t["label"].split(" — ")[0].split(" ", 1)[-1].lower() not in bajo]
check("T4c y las 7 plantillas de corto", not faltan_tpl, str(faltan_tpl))

check("T4d hay una receta paso a paso por tipo de video",
      bajo.count("receta") >= 6, str(bajo.count("receta")))

# ---------------------------------------------------------------------------
# T5 — los nombres de la interfaz son los REALES
# ---------------------------------------------------------------------------
# Pestañas del proyecto, tal y como las pinta la interfaz
pestañas = re.search(r"const tabs=\[(.+?)\];", html)
nombres = re.findall(r"\['([^']+)'", pestañas.group(1)) if pestañas else []
faltan_tabs = [t for t in nombres if t.lower() not in bajo]
check("T5 el manual nombra las pestañas que existen de verdad",
      nombres and not faltan_tabs, str(faltan_tabs))

menus = ["Nuevo proyecto", "Canales y estilos", "Manual de uso",
         "Log de eventos", "Configuración"]
faltan_menu = [m for m in menus if m.lower() not in bajo or m not in html]
check("T5b y los cinco menús del lateral", not faltan_menu, str(faltan_menu))

# Nombres de pestañas que YA NO existen y que confundían al lector
viejos = [n for n in ("pestaña material", "pestaña personajes",
                      "pestaña escenas", "📚 biblioteca") if n in bajo]
check("T5c y no arrastra nombres de pantallas que ya no existen", not viejos,
      str(viejos))

# ---------------------------------------------------------------------------
# T6 — sigue siendo un manual para cualquiera
# ---------------------------------------------------------------------------
# Los términos técnicos inevitables se explican en el propio texto
for termino, explicacion in (("prompt", "descripción"),
                             ("lipsync", "mueva la boca"),
                             ("ducking", "baja la música"),
                             ("clave de api", "contraseña"),
                             ("b-roll", "imágenes")):
    check(f"T6 explica «{termino}» en palabras normales",
          termino in bajo and explicacion in bajo, "")

check("T6b avisa del gasto por segundo del personaje en cámara",
      "por segundo" in bajo and "lipsync" in bajo, "")
check("T6c enseña la estrategia de probar barato y publicar caro",
      "flux schnell" in bajo and "rehacer desde" in bajo, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.58.0 completa: el manual enseña con capturas reales, "
      "tiene una receta por formato y llama a las pantallas por su nombre.")
