"""Batería v0.60.0 — dos plantillas de interfaz y un manual para cada una.

El creador quiere la interfaz nueva por defecto SIN perder la anterior, poder
cambiar cuando quiera, y que el manual que lee tenga siempre las capturas de
la plantilla que tiene delante. Aquí eso deja de ser una promesa:

1.  Las dos plantillas existen, se sirven de verdad y un valor inválido no
    puede dejar al creador sin interfaz.
2.  La elección se guarda donde no la pisa un `git pull`.
3.  Cada plantilla tiene SU manual, y el endpoint sirve el que toca.
4.  Ninguna captura está rota ni huérfana, y el servidor las sirve sin dejar
    salir de su carpeta.
5.  Los dos manuales están SINCRONIZADOS: mismos capítulos y mismo contenido
    compartido. Si alguien mejora uno y olvida el otro, esto se pone rojo.
6.  Cada manual habla de SU plantilla (no nombra pestañas de la otra).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import re  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

import yaml  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


from ytstudio.webui import server as srv  # noqa: E402

IMG_DIR = ROOT / "docs" / "manual"

# ---------------------------------------------------------------------------
# T1 — las dos plantillas existen y se sirven
# ---------------------------------------------------------------------------
print("T1 plantillas")
check("T1a hay dos plantillas declaradas", set(srv.TEMPLATES) == {"nueva", "clasica"},
      str(list(srv.TEMPLATES)))
check("T1b la nueva es la de por defecto", srv.DEFAULT_TEMPLATE == "nueva",
      srv.DEFAULT_TEMPLATE)
for name, tpl in srv.TEMPLATES.items():
    html = srv.STATIC_DIR / tpl["html"]
    check(f"T1c el archivo de la plantilla «{name}» existe", html.is_file(), str(html))
    check(f"T1d y su manual «{tpl['manual']}» existe",
          (ROOT / tpl["manual"]).is_file(), tpl["manual"])

check("T1e un valor desconocido cae a la de por defecto (nunca sin interfaz)",
      srv.ui_template({"ui": {"template": "pirata"}}) == "nueva")
check("T1f y una config sin el bloque ui tampoco rompe",
      srv.ui_template({}) == "nueva")
check("T1g la elección válida se respeta",
      srv.ui_template({"ui": {"template": "clasica"}}) == "clasica")

# La ruta «/» sirve el HTML de la plantilla activa, no uno fijo
import inspect  # noqa: E402
ssrc = inspect.getsource(srv)
check("T1h la raíz sirve la plantilla activa, no un archivo fijo",
      'TEMPLATES[ui_template()]["html"]' in ssrc, "")

# ---------------------------------------------------------------------------
# T2 — la elección se guarda fuera del repositorio
# ---------------------------------------------------------------------------
print("\nT2 guardado de la elección")
check("T2a el ajuste está en el config del repositorio",
      (yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
       .get("ui", {}).get("template")) in srv.TEMPLATES, "")
check("T2b y la interfaz puede guardarlo (está en _UI_CONFIG_PATHS)",
      ("ui", "template") in srv._UI_CONFIG_PATHS, "")

# El guardado real, sin tocar el config del creador: se hace sobre una copia
tmp = Path(tempfile.mkdtemp(prefix="v0600_"))
local = ROOT / "config.local.yaml"
backup = tmp / "config.local.yaml.bak"
if local.exists():
    shutil.copy(local, backup)
try:
    srv.api_set_ui_template({"template": "clasica"})
    guardado = yaml.safe_load(local.read_text(encoding="utf-8")) or {}
    check("T2c guardar la plantilla la deja escrita en config.local.yaml",
          guardado.get("ui", {}).get("template") == "clasica", str(guardado.get("ui")))
    try:
        srv.api_set_ui_template({"template": "pirata"})
        check("T2d una plantilla inválida se rechaza", False, "no lanzó error")
    except srv.ApiError as e:
        check("T2d una plantilla inválida se rechaza con un mensaje claro",
              e.status == 400 and "pirata" in e.message, e.message)
    # el manual servido es el de la plantilla activa
    man = srv.api_manual()
    check("T2e el endpoint sirve el manual de la plantilla activa",
          man["template"] == "clasica"
          and "PLANTILLA: clasica" in man["content"], man.get("template"))
    srv.api_set_ui_template({"template": "nueva"})
    man = srv.api_manual()
    check("T2f y cambia al de la otra al cambiar de plantilla",
          man["template"] == "nueva" and "PLANTILLA: nueva" in man["content"],
          man.get("template"))
finally:
    if backup.exists():
        shutil.copy(backup, local)
    else:
        local.unlink(missing_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
# T3 — las capturas: ninguna rota, ninguna huérfana, servidas con seguridad
# ---------------------------------------------------------------------------
print("\nT3 capturas")
MANUALES = {name: (ROOT / tpl["manual"]).read_text(encoding="utf-8")
            for name, tpl in srv.TEMPLATES.items()}

usadas: set[str] = set()
for name, texto in MANUALES.items():
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", texto)
    usadas.update(refs)
    check(f"T3a el manual «{name}» incluye capturas", len(refs) >= 10, str(len(refs)))
    rotas = [r for r in refs if not (ROOT / r).is_file()]
    check(f"T3b ninguna captura rota en «{name}»", not rotas, str(rotas))
    # cada manual usa SU carpeta (y la del panel, que es común)
    propia = srv.TEMPLATES[name]["shots"]
    ajenas = [r for r in refs
              if not r.startswith((f"docs/manual/{propia}/", "docs/manual/panel/"))]
    check(f"T3c «{name}» solo usa sus capturas y las del panel", not ajenas,
          str(ajenas))

en_disco = {str(p.relative_to(ROOT)) for p in IMG_DIR.rglob("*.png")}
huerfanas = sorted(en_disco - usadas)
check("T3d no hay capturas huérfanas", not huerfanas, str(huerfanas))
pesadas = [str(p.name) for p in IMG_DIR.rglob("*.png") if p.stat().st_size > 900_000]
check("T3e ninguna captura es desproporcionada (<900 KB)", not pesadas, str(pesadas))

rutas = re.findall(r'r"/docs/manual/\(([^)]+)\)/\(([^)]+)\)"', ssrc)
check("T3f el servidor sirve las capturas por carpeta de plantilla",
      bool(rutas), "no se encontró la ruta /docs/manual/<carpeta>/<archivo>")
check("T3g y la ruta no permite salir de la carpeta de capturas",
      bool(rutas) and all("/" not in g for g in rutas[0]), str(rutas))
check("T3h con comprobación de ruta en el manejador",
      "_manual_image" in ssrc and "Ruta inválida" in ssrc, "")

# ---------------------------------------------------------------------------
# T4 — los dos manuales, sincronizados
# ---------------------------------------------------------------------------
print("\nT4 los dos manuales van a la par")
caps = {n: re.findall(r"^##\s+(.+)$", t, re.M) for n, t in MANUALES.items()}
nueva, clasica = caps["nueva"], caps["clasica"]
check("T4a los dos manuales tienen los mismos capítulos", nueva == clasica,
      str([c for c in nueva if c not in clasica]
          + [c for c in clasica if c not in nueva]))
check("T4b y son 19 o más", len(nueva) >= 19, str(len(nueva)))

versiones = {n: re.search(r"MANUAL_VERSION:\s*([0-9.]+)", t) for n, t in MANUALES.items()}
check("T4c los dos declaran su versión", all(versiones.values()), "")
if all(versiones.values()):
    check("T4d y es la MISMA en los dos",
          len({m.group(1) for m in versiones.values()}) == 1,
          str({n: m.group(1) for n, m in versiones.items()}))
    prog = re.search(r"^## v(\d+\.\d+\.\d+)",
                     (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:2000], re.M)
    check("T4e y coincide con la del programa",
          prog and versiones["nueva"].group(1) == prog.group(1),
          f"manual={versiones['nueva'].group(1)} programa={prog.group(1) if prog else '?'}")

# El contenido COMPARTIDO tiene que estar en los dos: si mañana alguien
# actualiza los precios en uno solo, esto lo caza.
COMPARTIDO = ["modo híbrido", "flux schnell", "veo 3.1", "gpt image 2",
              "cartesia", "assemblyai", "tope de presupuesto", "banco de elementos",
              "punto de control", "lipsync", "fact_check", "probar.bat",
              "torre de control", "glosario", "c:\\ffmpeg"]
for termino in COMPARTIDO:
    falta = [n for n, t in MANUALES.items() if termino not in t.lower()]
    check(f"T4f «{termino}» está documentado en los dos manuales", not falta,
          str(falta))

# ---------------------------------------------------------------------------
# T5 — cada manual describe SU plantilla
# ---------------------------------------------------------------------------
print("\nT5 cada manual, el suyo")
html_nueva = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
tabs = re.search(r"const tabs = \[(.+?)\];", html_nueva)
nombres_nueva = re.findall(r"'([A-ZÁÉÍÓÚa-z]+)'\]", tabs.group(1)) if tabs else []
faltan = [t for t in nombres_nueva if t.lower() not in MANUALES["nueva"].lower()]
check("T5a el manual de la nueva nombra sus pestañas reales",
      nombres_nueva and not faltan, str(faltan))

html_clasica = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
tabs_c = re.search(r"const tabs=\[(.+?)\];", html_clasica)
nombres_clasica = re.findall(r"\['([^']+)'", tabs_c.group(1)) if tabs_c else []
faltan_c = [t for t in nombres_clasica if t.lower() not in MANUALES["clasica"].lower()]
check("T5b el manual de la clásica nombra sus pestañas reales",
      nombres_clasica and not faltan_c, str(faltan_c))

# Los dos explican cómo cambiar de plantilla: es la primera duda al ver otra
# interfaz de la esperada.
for n, t in MANUALES.items():
    check(f"T5c el manual «{n}» explica cómo cambiar de plantilla",
          "plantilla de la interfaz" in t.lower(), "")

# Y el selector existe en las DOS interfaces (si no, se entra en una sin
# salida: la clásica no tendría forma de volver a la nueva).
check("T5d la interfaz nueva tiene el selector de plantilla",
      "plantillaSelector" in html_nueva and "/api/ui-template" in html_nueva, "")
check("T5e la interfaz clásica también",
      "plantillaCard" in html_clasica and "/api/ui-template" in html_clasica, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.60.0 completa: dos plantillas vivas, cada una con su "
      "manual y sus capturas, y ninguna puede quedarse atrás de la otra.")
