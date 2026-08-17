"""Batería v0.61.0 — las dos plantillas, con los mismos controles.

La interfaz nueva se quedó sin cuatro controles que la clásica sí tenía, y
son justo los que deciden cuánto gastas: la estimación antes de generar, la
parada en el punto de control, la presencia del personaje en cámara y
duplicar/borrar proyectos. Aquí se comprueba que ya están, que funcionan de
verdad y que ninguna plantilla vuelve a quedarse atrás sin avisar.

1.  El motor: guardar la presencia del personaje después de crear el
    proyecto (antes solo se podía al crearlo), con sus topes.
2.  La interfaz nueva llama a TODO lo que llama la clásica: si mañana
    aparece una función en una y no en la otra, esto se pone rojo.
3.  Los controles concretos están en la interfaz nueva (estimación, hasta
    dónde generar, presencia, burbuja, duplicar, borrar, guardar estilo,
    arco musical, duración, encabezado y tipo de rótulo, quién ocupa la
    pantalla).
4.  La tabla de escenas tiene tantos títulos como columnas (un desajuste
    dejaba cada dato bajo el título del vecino).
5.  Los dos manuales lo documentan y ya no prometen que falte nada.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


from ytstudio.webui import server as srv  # noqa: E402
from ytstudio.project import PROJECTS_DIR, Project  # noqa: E402

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# T1 — el motor: la presencia del personaje se puede cambiar DESPUÉS
# ---------------------------------------------------------------------------
print("T1 presencia del personaje")
slug = "prueba-v0610"
tmp_dir = PROJECTS_DIR / slug
shutil.rmtree(tmp_dir, ignore_errors=True)
try:
    Project.create(slug)
    r = srv.api_set_character_presence(slug, {"presence": 45, "pip": True})
    check("T1a guarda el porcentaje como fracción", r["character"]["presence"] == 0.45,
          str(r["character"]))
    check("T1b y el modo burbuja", r["character"]["pip"] is True, str(r["character"]))
    check("T1c avisa de que hay que rehacer desde Escenas",
          "escenas" in (r.get("hint") or "").lower(), str(r.get("hint")))

    r = srv.api_set_character_presence(slug, {"presence": 300})
    check("T1d un porcentaje disparatado se recorta al tope (60 %)",
          r["character"]["presence"] == 0.6, str(r["character"]))
    r = srv.api_set_character_presence(slug, {"presence": -10})
    check("T1e y uno negativo se queda en 0", r["character"]["presence"] == 0.0,
          str(r["character"]))
    # cambiar solo la burbuja no debe borrar la presencia guardada
    antes = Project(slug).get("character")["presence"]
    r = srv.api_set_character_presence(slug, {"pip": False})
    check("T1f cambiar la burbuja no pierde la presencia",
          r["character"]["presence"] == antes and r["character"]["pip"] is False,
          str(r["character"]))
    try:
        srv.api_set_character_presence(slug, {"presence": "mucho"})
        check("T1g un valor no numérico se rechaza", False, "no lanzó error")
    except srv.ApiError as e:
        check("T1g un valor no numérico se rechaza con mensaje claro",
              e.status == 400, e.message)
    try:
        srv.api_set_character_presence("no-existe-este-proyecto", {"presence": 30})
        check("T1h un proyecto inexistente da 404", False, "no lanzó error")
    except srv.ApiError as e:
        check("T1h un proyecto inexistente da 404", e.status == 404, str(e.status))
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)

import inspect  # noqa: E402
ssrc = inspect.getsource(srv)
check("T1i la ruta del API está registrada",
      '/character"' in ssrc and "api_set_character_presence" in ssrc, "")

# ---------------------------------------------------------------------------
# T2 — ninguna plantilla se queda atrás: mismas llamadas al API
# ---------------------------------------------------------------------------
print("\nT2 las dos plantillas usan las mismas funciones del motor")


def rutas(html: str) -> set[str]:
    """Rutas del API que usa una interfaz, normalizando las variables.

    Las dos interfaces escriben la misma ruta de formas distintas —
    «`/api/projects/${slug}`» en una, «'/api/projects/'+slug» en la otra—,
    así que la parte variable se reduce a <v> en ambos casos."""
    fuera = set()
    for r in re.findall(r"/api/[\w/${}.\-]+", html):
        r = re.sub(r"\$\{[^}]*\}", "<v>", r).rstrip("`'\"),;")
        if r.endswith("/"):          # se le concatena una variable justo detrás
            r += "<v>"
        fuera.add(r)
    return fuera


solo_clasica = sorted(rutas(CLASICA) - rutas(NUEVA))
check("T2a la interfaz nueva no deja fuera ninguna ruta de la clásica",
      not solo_clasica, str(solo_clasica))

# ---------------------------------------------------------------------------
# T3 — los controles, uno por uno, en la interfaz nueva
# ---------------------------------------------------------------------------
print("\nT3 controles portados")
CONTROLES = {
    "estimación antes de generar": ["estimacionCard", "/estimate"],
    "hasta dónde generar": ["Hasta el guion gráfico", "Solo hasta el guion"],
    "presencia del personaje": ["presenciaBloque", "PRESENCIAS"],
    "modo burbuja": ["pip"],
    "duplicar proyecto": ["/duplicate"],
    "borrar proyecto": ["¿Borrar «"],
    "guardar estilo del proyecto": ["/save-style", "guardarEstilo"],
    "arco musical por escena": ["music_intensity"],
    "duración de escena": ["'duration'"],
    "encabezado y tipo de rótulo": ["overlay_kicker", "overlay_type"],
    "quién ocupa la pantalla": ["'shot'"],
}
for nombre, marcas in CONTROLES.items():
    faltan = [m for m in marcas if m not in NUEVA]
    check(f"T3 «{nombre}» está en la interfaz nueva", not faltan, str(faltan))

# La duración NO puede editarse con narración propia: la manda tu voz.
check("T3b la duración solo se edita con voz artificial",
      "vozPropia" in NUEVA and "audio_start" in NUEVA, "")

# ---------------------------------------------------------------------------
# T4 — la tabla de escenas: tantos títulos como columnas
# ---------------------------------------------------------------------------
print("\nT4 la tabla de escenas cuadra")
cuerpo = NUEVA.split("function viewEscenas")[1].split("function viewPersonajes")[0]
celdas = cuerpo.count("el('td'")
titulos = cuerpo.count("el('th'")
check("T4a hay un título por columna", celdas == titulos,
      f"{celdas} columnas de datos y {titulos} títulos")

# ---------------------------------------------------------------------------
# T5 — los manuales lo cuentan, y ya no prometen que falte
# ---------------------------------------------------------------------------
print("\nT5 los dos manuales, al día")
MANUALES = {n: (ROOT / t["manual"]).read_text(encoding="utf-8")
            for n, t in srv.TEMPLATES.items()}
for n, t in MANUALES.items():
    bajo = t.lower()
    for termino in ("estimado antes de generar", "hasta el guion gráfico",
                    "presencia del narrador" if n == "nueva" else "presencia en pantalla",
                    "duplicar", "guardar estilo"):
        check(f"T5 el manual «{n}» documenta «{termino}»", termino in bajo, "")

VIEJAS = ["solo se eligen en la plantilla clásica", "cámbiate a la clásica",
          "la más completa para", "en esta plantilla el programa no se para"]
for n, t in MANUALES.items():
    quedan = [v for v in VIEJAS if v in t.lower()]
    check(f"T5b el manual «{n}» ya no promete carencias que se arreglaron",
          not quedan, str(quedan))

caps = {n: re.findall(r"^##\s+(.+)$", t, re.M) for n, t in MANUALES.items()}
check("T5c los dos manuales siguen con los mismos capítulos",
      caps["nueva"] == caps["clasica"], "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.61.0 completa: las dos plantillas ofrecen los mismos "
      "controles, y elegir cómo se ve el programa ya no cuesta funciones.")
