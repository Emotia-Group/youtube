"""Batería v0.51.0 — MANUAL DE USO integrado y que no puede quedarse atrás.

El creador pidió un manual completo, claro y práctico, dentro del programa
(como el log de eventos), «que se actualice automáticamente con cada ajuste
que amerite la renovación».

La parte de «actualizarse solo» no puede ser una promesa: aquí se convierte en
COMPROBACIONES QUE FALLAN si el manual se desactualiza. Cuando esta batería se
pone en rojo, el manual necesita una revisión — y `probar.bat` lo dice.

Verifica:
1. El manual existe, declara la versión que documenta y coincide con la del
   programa (CHANGELOG). Esta es LA valla anti-obsolescencia.
2. Cubre todas las fases, todos los proveedores de clave y las funciones
   principales del programa.
3. Los ajustes de configuración que menciona EXISTEN de verdad, y los que
   cuestan dinero están documentados.
4. Endpoint y menú funcionando, con aviso si el manual se queda atrás.
5. El texto es práctico: sin jerga innecesaria, con secciones de antes,
   durante y después, y con las advertencias de dinero.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import re

import yaml

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


MANUAL = ROOT / "MANUAL.md"
texto = MANUAL.read_text(encoding="utf-8") if MANUAL.exists() else ""
bajo = texto.lower()

# ---------------------------------------------------------------------------
# T1 — LA VALLA: el manual declara su versión y coincide con la del programa
# ---------------------------------------------------------------------------
check("T1 el manual existe", MANUAL.exists(), "")
m = re.search(r"MANUAL_VERSION:\s*([0-9]+\.[0-9]+\.[0-9]+)", texto)
check("T1b declara qué versión documenta (marca MANUAL_VERSION)",
      m is not None, "")
head = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:2000]
prog = re.search(r"^## v(\d+\.\d+\.\d+)", head, re.M)
check("T1c el CHANGELOG declara la versión del programa", prog is not None, "")
if m and prog:
    check("T1d EL MANUAL ESTÁ AL DÍA con la versión del programa "
          "(si esto falla, hay que revisarlo y actualizar su marca)",
          m.group(1) == prog.group(1),
          f"manual={m.group(1)} programa={prog.group(1)}")

# ---------------------------------------------------------------------------
# T2 — cubre TODO lo que el programa hace
# ---------------------------------------------------------------------------
from ytstudio.pipeline import PHASE_LABELS

faltan = [lab for lab in PHASE_LABELS.values() if lab.lower() not in bajo]
check("T2 documenta las 11 fases del pipeline", not faltan, str(faltan))

claves = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "REPLICATE_API_TOKEN",
          "ELEVENLABS_API_KEY"]
check("T2b explica las 4 claves de API y para qué sirve cada una",
      all(k in texto for k in claves),
      str([k for k in claves if k not in texto]))

funciones = {
    "banco de elementos": "banco de elementos",
    "insertos documentales": "inserto",
    "mapas localizadores": "mapa",
    "cama de ambiente": "ambiente",
    "rótulos": "rótulo",
    "personaje narrador / lipsync": "lipsync",
    "elenco de personajes": "elenco",
    "formatos cortos": "shorts",
    "estilos de canal": "estilo",
    "punto de control": "punto de control",
    "reanudar": "reanuda",
    "tope de presupuesto": "tope de presupuesto",
    "corrector de narración": "tropiezo",
    "control de calidad factual": "fact_check",
    "subtítulos": "subtítulo",
    "miniaturas": "miniatura",
    "probar.bat": "probar.bat",
}
sin_doc = [k for k, v in funciones.items() if v not in bajo]
check("T2c documenta las funciones principales del programa", not sin_doc,
      str(sin_doc))

# ---------------------------------------------------------------------------
# T3 — los ajustes que menciona EXISTEN (y los caros están documentados)
# ---------------------------------------------------------------------------
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def existe(ruta: str) -> bool:
    cur = cfg
    for parte in ruta.split("."):
        if not isinstance(cur, dict) or parte not in cur:
            return False
        cur = cur[parte]
    return True


mencionados = set(re.findall(r"`([a-z_]+(?:\.[a-z_]+)+)`", texto))
# Los ARCHIVOS con extensión (panel.bat, client_secrets.json…) le parecen
# rutas de ajuste a la regex, pero no lo son — y desde la v0.54.0 existe el
# bloque `panel:` en config.yaml, así que «panel.bat» buscaba cfg[panel][bat]
# y salía «inventado» con el manual diciendo la verdad. Un ajuste real nunca
# termina en extensión de archivo.
_EXTENSIONES = (".bat", ".sh", ".json", ".yaml", ".yml", ".md", ".py")
mencionados = {r for r in mencionados if not r.endswith(_EXTENSIONES)}
inventados = [r for r in mencionados
              if r.split(".")[0] in cfg and not existe(r)]
check("T3 ningún ajuste mencionado en el manual es inventado", not inventados,
      str(inventados))

# los ajustes que MUEVEN DINERO tienen que estar explicados sí o sí
caros = ["providers.videogen.max_scenes", "providers.images.model",
         "video.elements_ai", "providers.images.fact_check"]
sin_explicar = [c for c in caros
                if c.split(".")[-1] not in texto and c not in texto]
check("T3b los ajustes que afectan al gasto están explicados",
      not sin_explicar, str(sin_explicar))
check("T3c y se avisa de los interruptores del corrector de narración",
      "fix_narration_ai" in texto and "fix_narration" in texto, "")

# ---------------------------------------------------------------------------
# T4 — endpoint, menú y aviso de desactualización
# ---------------------------------------------------------------------------
import inspect

from ytstudio.webui import server as srv

res = srv.api_manual()
check("T4 el endpoint sirve el manual con ambas versiones",
      res["content"].startswith("# Manual de uso")
      and res["manual_version"] and "manual_version" in res
      and "program_version" in res, str(list(res)))
check("T4b las versiones se comparan sin la «v» (formatos compatibles)",
      not res["program_version"].startswith("v"), res["program_version"])

ssrc = inspect.getsource(srv)
check("T4c la ruta /api/manual está registrada", '"/api/manual"' in ssrc, "")

html = (ROOT / "ytstudio" / "webui" / "static" / "index.html").read_text(
    encoding="utf-8")
check("T4d hay un menú «Manual de uso» junto al log de eventos",
      "showManual()" in html and "📖 Manual de uso" in html, "")
cuerpo_visor = html.split("async function showManual")[1][:2000] \
    if "async function showManual" in html else ""
check("T4e el visor avisa si el manual se quedó atrás",
      "stale" in cuerpo_visor and "manual_version" in cuerpo_visor, "")
check("T4f el manual tiene índice y buscador",
      "filterManual" in html and "man-toc" in html, "")
check("T4g las tablas del manual se renderizan (no salen como texto plano)",
      "mdToHtml" in html and "<table" in html, "")

# ---------------------------------------------------------------------------
# T5 — es un manual PRÁCTICO, no una ficha técnica
# ---------------------------------------------------------------------------
secciones = re.findall(r"^##\s+(.+)$", texto, re.M)
check("T5 está organizado en secciones navegables (10 o más)",
      len(secciones) >= 10, str(len(secciones)))
check("T5b cubre ANTES, DURANTE y DESPUÉS de generar",
      "antes de generar" in bajo and "durante la generación" in bajo
      and ("después" in bajo), "")
check("T5c dice qué SÍ y qué NO hacer",
      "qué sí y qué no" in bajo or ("**sí:**" in bajo and "**no:**" in bajo),
      "")
check("T5d tiene tabla de costos reales y consejos de ahorro",
      "ahorrar dinero" in bajo and "$" in texto and "flux schnell" in bajo, "")
check("T5e tiene solución de problemas frecuentes",
      "problemas frecuentes" in bajo and "429" in texto, "")
check("T5f incluye glosario para los términos inevitables",
      "glosario" in bajo and "b-roll" in bajo, "")
check("T5g explica cómo pedir ayuda con el log de eventos",
      "log de eventos" in bajo and "descargar" in bajo, "")

# tablas: la forma más clara de consultar de un vistazo
check("T5h usa tablas de consulta rápida",
      texto.count("|---") >= 6, str(texto.count("|---")))

# advertencia del error más caro que ya le costó dinero al creador
check("T5i advierte del error caro: rehacer desde Guion borra las imágenes "
      "pagadas",
      "nunca rehagas" in bajo or "no rehagas" in bajo, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    print("\n  → Si falló T1d, el manual quedó atrás: revísalo, actualiza lo "
          "que cambió y sube su marca MANUAL_VERSION.")
    sys.exit(1)
print("✓ Batería v0.51.0 completa: el manual está dentro del programa, "
      "cubre todas sus funciones y no puede quedarse atrás sin avisar.")
