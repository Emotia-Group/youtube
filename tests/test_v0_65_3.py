"""Batería v0.65.3 — «actualicé y sigo en la versión de antes».

Caso real del creador: pulsó actualizar.bat, el .bat dijo «Listo. Ya puedes
abrir el programa», y la interfaz seguía mostrando v0.65.0. Los arreglos que
esperaba nunca llegaron a su equipo.

El .bat hacía `git pull` y a continuación imprimía «Listo» SIN MIRAR SI HABÍA
FUNCIONADO. Si el pull fallaba —cambios locales, rama sin subir, historial
separado— el mensaje era exactamente el mismo que si hubiera ido bien. Un
programa que dice que se actualizó cuando no lo hizo es peor que uno que no
se actualiza: manda a buscar el fallo al sitio equivocado.

Ahora el .bat:
  · dice en qué rama está y de qué versión parte,
  · comprueba si el pull funcionó y, si no, NO dice que sí,
  · distingue «actualizado de X a Y» de «ya estabas al día»,
  · y recuerda que hay que cerrar y reabrir el programa.

Esta batería lee el .bat: no puede ejecutarlo (es de Windows), pero sí puede
comprobar que las salidas de emergencia existen y que ninguna ruta miente.
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


BAT = (ROOT / "actualizar.bat").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# T1 — el fallo que originó todo: decir «Listo» sin comprobar nada
# ---------------------------------------------------------------------------
print("T1 el .bat ya no miente")

check("T1a comprueba si el pull funcionó",
      "if errorlevel 1 goto :fallo" in BAT)
check("T1b y tiene adónde saltar si falla", "\n:fallo" in BAT)
check("T1c si falla, lo dice CLARO y con la versión en la que te quedas",
      "NO SE PUDO ACTUALIZAR" in BAT and "Sigues en %ANTES_V%" in BAT)
check("T1d y sale con código de error, no fingiendo éxito",
      BAT.rstrip().endswith("exit /b 1"))

# El «Listo» incondicional que causó el problema no puede volver
tras_pull = BAT.split("git pull --ff-only")[1]
check("T1e ningún «Listo» suelto después del pull",
      "Listo. Ya puedes abrir" not in BAT, "quedó el mensaje viejo")
check("T1f el camino de éxito solo se alcanza tras pasar la comprobación",
      tras_pull.index("if errorlevel 1 goto :fallo")
      < tras_pull.index("ACTUALIZADO"),
      "el mensaje de éxito está antes de comprobar")

# ---------------------------------------------------------------------------
# T2 — dice lo suficiente para diagnosticar sin ayuda
# ---------------------------------------------------------------------------
print("\nT2 lo que informa")

check("T2a dice en qué RAMA estás (la causa más habitual)",
      "echo  Rama:" in BAT)
check("T2b la versión ANTES de actualizar", "Version ahora:" in BAT)
check("T2c y la versión DESPUÉS", "DESPUES_V" in BAT)
check("T2d distingue «actualizado» de «ya estabas al día»",
      "YA ESTABAS AL DIA" in BAT and "ACTUALIZADO:" in BAT)
check("T2e si no había nada nuevo, sugiere mirar la rama",
      "git branch -r" in BAT)
check("T2f recuerda CERRAR Y REABRIR el programa",
      "CIERRALO" in BAT and "iniciar.bat" in BAT)
check("T2g y pide copiar la salida si algo falla",
      "pasaselo a Claude" in BAT)

# ---------------------------------------------------------------------------
# T3 — la versión sale de donde debe (el CHANGELOG, como la interfaz)
# ---------------------------------------------------------------------------
print("\nT3 de dónde sale la versión")

check("T3a la lee del CHANGELOG, igual que la interfaz",
      'findstr /b /c:"## v" CHANGELOG.md' in BAT)
check("T3b se lee dos veces: antes y después del pull",
      BAT.count('findstr /b /c:"## v" CHANGELOG.md') == 2,
      str(BAT.count('findstr /b /c:"## v" CHANGELOG.md')))

# Y esa lectura tiene que dar la versión REAL del repositorio
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
primera = next((l for l in CHANGELOG.splitlines() if l.startswith("## v")), "")
version_real = primera.split()[1] if len(primera.split()) > 1 else ""
check("T3c el CHANGELOG empieza por un encabezado de versión legible",
      bool(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version_real)),
      repr(version_real))

# ---------------------------------------------------------------------------
# T4 — no se ha roto lo que ya funcionaba
# ---------------------------------------------------------------------------
print("\nT4 lo que ya hacía, lo sigue haciendo")

check("T4a instala las dependencias nuevas",
      "pip install -r requirements.txt" in BAT)
check("T4b se sitúa en la carpeta del programa",
      'cd /d "%~dp0"' in BAT)
check("T4c avisa si falta Git", "No se encontro Git" in BAT)
check("T4d y si la carpeta no es un repositorio",
      "no es un repositorio de Git" in BAT)
check("T4e usa --ff-only: nunca abre un editor a media actualización",
      "--ff-only" in BAT)

# pull.bat ya era honesto: los dos tienen que seguir siéndolo
PULL = (ROOT / "pull.bat").read_text(encoding="utf-8")
check("T4f pull.bat sigue comprobando el resultado igual",
      "if errorlevel 1 goto :fallo" in PULL)

# ---------------------------------------------------------------------------
# T5 — documentación
# ---------------------------------------------------------------------------
print("\nT5 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T5a el manual {nombre} enseña a comprobar que actualizaste",
          "sigo en la versión de antes" in texto
          or "sigues en la versión de antes" in texto.lower())
    check(f"T5b el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

check("T5c el CHANGELOG cuenta lo que arregló la v0.65.3",
      "## v0.65.3" in CHANGELOG)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.65.3: actualizar.bat ya no dice que actualizó cuando no lo hizo.")
