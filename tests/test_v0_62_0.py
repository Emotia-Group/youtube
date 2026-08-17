"""Batería v0.62.0 — el selector de plantillas: fichas y confirmación.

El selector eran dos botones pegados y un solo clic cambiaba de interfaz:
mirar las opciones bastaba para acabar en otra plantilla sin querer. Ahora
cada plantilla es una FICHA con miniatura y el cambio pide CONFIRMACIÓN.

1.  El servidor sirve la ficha de CADA plantilla: nombre, frase, en qué se
    nota y los colores de su miniatura. Si mañana se añade una tercera y se
    olvida la ficha, esto se pone rojo.
2.  Los colores de la miniatura son colores de verdad y la disposición es una
    de las conocidas: la miniatura se dibuja sola con esos datos.
3.  Las DOS interfaces piden confirmación: elegir no cambia nada; solo el
    «Sí, cambiar…» llama al servidor.
4.  El cambio, cuando se confirma, sigue funcionando y sigue guardándose
    fuera de Git — y una plantilla inventada se rechaza.
5.  Los dos manuales cuentan el paso nuevo.
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


from ytstudio.webui import server as srv  # noqa: E402

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# T1 — cada plantilla registrada trae su ficha
# ---------------------------------------------------------------------------
print("T1 la ficha de cada plantilla")
fichas = srv.template_cards()
check("T1a hay una ficha por plantilla registrada",
      len(fichas) == len(srv.TEMPLATES), f"{len(fichas)} vs {len(srv.TEMPLATES)}")

for f in fichas:
    falta = [c for c in ("id", "label", "name", "tagline", "desc", "bullets",
                         "preview") if not f.get(c)]
    check(f"T1b la ficha «{f['id']}» está completa", not falta, str(falta))
    check(f"T1c la ficha «{f['id']}» explica en qué se nota",
          len(f["bullets"]) >= 2 and len(f["desc"]) > 40, str(f["bullets"]))
    check(f"T1d el nombre corto de «{f['id']}» cabe en la ficha",
          0 < len(f["name"]) <= 24, f["name"])

cat = srv.api_get_config()
check("T1e el catálogo sirve las fichas, no solo los nombres",
      isinstance(cat["ui_templates"], list)
      and all("preview" in t and "desc" in t for t in cat["ui_templates"]), "")
check("T1f el catálogo dice cuál está puesta",
      cat["ui_template"] in srv.TEMPLATES, str(cat["ui_template"]))

# ---------------------------------------------------------------------------
# T2 — con esos datos se puede DIBUJAR la miniatura
# ---------------------------------------------------------------------------
print("\nT2 los datos de la miniatura")
for f in fichas:
    p = f["preview"]
    colores = [k for k in ("bg", "surface", "ink", "line", "accent")
               if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(p.get(k, "")))]
    check(f"T2a «{f['id']}» trae sus cinco colores en hexadecimal",
          not colores, str(colores))
    check(f"T2b «{f['id']}» declara una disposición conocida",
          p.get("layout") in ("top", "side"), str(p.get("layout")))
# Dos plantillas con la MISMA cara no se distinguirían en el selector.
caras = {(f["preview"].get("layout"), f["preview"].get("bg")) for f in fichas}
check("T2c ninguna plantilla se ve igual que otra en su miniatura",
      len(caras) == len(fichas), str(caras))

# ---------------------------------------------------------------------------
# T3 — las dos interfaces piden confirmación
# ---------------------------------------------------------------------------
print("\nT3 nada cambia sin confirmar")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T3a la interfaz {nombre} dibuja la miniatura de cada plantilla",
          "tplMiniatura" in html and "tplgrid" in html, "")
    check(f"T3b la interfaz {nombre} elige primero y confirma después",
          "Usar esta plantilla" in html and "Sí, cambiar" in html
          and "Cancelar" in html, "")
    check(f"T3c la interfaz {nombre} avisa de qué va a pasar",
          "La página se recarga" in html and "no se tocan" in html, "")
    check(f"T3d la interfaz {nombre} marca la que está en uso",
          "en uso" in html, "")

# El clic de la FICHA no puede llamar al servidor: solo apunta la elección.
# (En la nueva, la ficha llama a pintar(); en la clásica, a elegirPlantilla().)
check("T3e la ficha de la nueva solo apunta la elección",
      "onclick: () => pintar(elegida ? null : o)" in NUEVA
      and NUEVA.count("/api/ui-template") == 1, "")
check("T3f la ficha de la clásica solo apunta la elección",
      "elegirPlantilla(" in CLASICA and CLASICA.count("/api/ui-template") == 1,
      "")
# La llamada al servidor vive junto al «Sí, cambiar»: si alguien la devuelve
# al botón de la ficha, este trozo deja de cumplirse.
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    i_api = html.index("/api/ui-template")
    i_si = html.index("Sí, cambiar")
    check(f"T3g en la {nombre} el cambio cuelga del botón de confirmar",
          abs(i_api - i_si) < 1200, f"distancia {abs(i_api - i_si)}")

# ---------------------------------------------------------------------------
# T4 — confirmado, el cambio sigue funcionando (y se guarda fuera de Git)
# ---------------------------------------------------------------------------
print("\nT4 el cambio, cuando se confirma")
local = ROOT / "config.local.yaml"
copia = local.read_text(encoding="utf-8") if local.exists() else None
try:
    otra = [k for k in srv.TEMPLATES if k != srv.ui_template()][0]
    r = srv.api_set_ui_template({"template": otra})
    check("T4a guarda la plantilla elegida", r["template"] == otra, str(r))
    check("T4b y el programa la da por activa", srv.ui_template() == otra, "")
    check("T4c queda en config.local.yaml (fuera de Git)",
          local.exists() and otra in local.read_text(encoding="utf-8"), "")
    try:
        srv.api_set_ui_template({"template": "no-existe"})
        check("T4d una plantilla inventada se rechaza", False, "no falló")
    except srv.ApiError as e:
        check("T4d una plantilla inventada se rechaza", e.status == 400, str(e))
finally:
    if copia is None:
        local.unlink(missing_ok=True)
    else:
        local.write_text(copia, encoding="utf-8")
check("T4e la preferencia del creador quedó como estaba",
      (local.read_text(encoding="utf-8") if local.exists() else None) == copia, "")

# ---------------------------------------------------------------------------
# T5 — los manuales cuentan el paso nuevo
# ---------------------------------------------------------------------------
print("\nT5 los dos manuales")
for nombre, archivo in (("nueva", "MANUAL.md"), ("clasica", "MANUAL-clasica.md")):
    texto = (ROOT / archivo).read_text(encoding="utf-8").lower()
    check(f"T5a el manual «{nombre}» explica la confirmación",
          "confirmación" in texto and "usar esta plantilla" in texto, "")
    check(f"T5b el manual «{nombre}» habla de las fichas con miniatura",
          "miniatura" in texto, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.62.0 completa: el selector muestra cada plantilla con su "
      "cara y no cambia nada sin que lo confirmes.")
