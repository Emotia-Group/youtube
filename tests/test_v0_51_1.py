"""Batería v0.51.1 — `probar.bat` sin ffmpeg en el PATH (caso real de Windows).

El creador corrió `probar.bat` y 34 de 51 baterías fallaron con
«FileNotFoundError: [WinError 2] El sistema no puede encontrar el archivo
especificado» — con el programa PERFECTAMENTE SANO (genera videos sin
problema).

Causa: en Windows es normal tener ffmpeg en C:\\ffmpeg\\bin SIN añadirlo al
PATH del sistema. El programa se las arregla solo (`require_ffmpeg()` lo busca
ahí y lo añade al PATH de su proceso), pero cada batería corre en su PROPIO
proceso y no pasaba por esa ayuda: se quedaba sin ffmpeg.

Verifica:
1. El runner localiza ffmpeg una vez y hereda ese PATH a todas las baterías.
2. Sin ffmpeg, avisa UNA vez, claro y arriba — no 34 errores crípticos.
3. Y entonces NO dice «todo en verde» (sería mentir sobre lo comprobado).
4. Con ffmpeg, el veredicto de confianza se mantiene igual que siempre.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import inspect
import os
import shutil
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


import probar_todo

TMP = Path(tempfile.mkdtemp(prefix="v0511_"))

# ---------------------------------------------------------------------------
# T1 — el runner localiza ffmpeg y lo hereda a las baterías hijas
# ---------------------------------------------------------------------------
path_resuelto = probar_todo._asegurar_ffmpeg()
tiene_ffmpeg = shutil.which("ffmpeg") is not None
check("T1 con ffmpeg instalado, el runner devuelve un PATH utilizable",
      (path_resuelto is not None) == tiene_ffmpeg,
      f"ffmpeg={tiene_ffmpeg} path={'sí' if path_resuelto else 'no'}")

# el PATH resuelto viaja al proceso hijo (que es donde estaba el problema)
sonda = TMP / "sonda.py"
sonda.write_text(
    "import shutil, sys\n"
    "sys.exit(0 if shutil.which('ffmpeg') else 3)\n", encoding="utf-8")
_prev = probar_todo.FFMPEG_PATH
probar_todo.FFMPEG_PATH = path_resuelto
ok, _, _ = probar_todo.run_one(sonda)
check("T1b la batería HIJA ve ffmpeg gracias al PATH heredado del runner",
      ok == tiene_ffmpeg, f"hija_ve_ffmpeg={ok}")

# y si el runner no lo encontró, no se inventa un PATH
probar_todo.FFMPEG_PATH = None
src_run = inspect.getsource(probar_todo.run_one)
check("T1c el PATH solo se fuerza cuando de verdad se localizó ffmpeg",
      "if FFMPEG_PATH:" in src_run and 'env["PATH"] = FFMPEG_PATH' in src_run,
      "")
probar_todo.FFMPEG_PATH = _prev

# ---------------------------------------------------------------------------
# T2 — sin ffmpeg: UN aviso claro, no 34 errores crípticos
#
# El aviso se comprueba sobre la FUNCIÓN que lo produce, no vaciando el PATH:
# en Windows eso no esconde ffmpeg (el programa lo busca igual en C:\ffmpeg,
# que es justo lo que debe hacer), así que la simulación por PATH solo
# funcionaba en Linux — y la batería fallaba en el equipo del creador con el
# programa correcto.
# ---------------------------------------------------------------------------
aviso = probar_todo.aviso_sin_ffmpeg()
check("T2 el aviso dice sin rodeos que no se encuentra ffmpeg",
      "NO ENCUENTRO FFMPEG" in aviso, aviso[:120])
check("T2b explica dónde ponerlo en Windows (C:\\ffmpeg) con el enlace",
      "C:\\ffmpeg" in aviso and "gyan.dev" in aviso, "")
check("T2c y también para Linux/Mac",
      "apt install ffmpeg" in aviso and "brew install ffmpeg" in aviso, "")
check("T2d advierte de que el resultado no será concluyente",
      "no puede ser concluyente" in aviso, "")
src_main = inspect.getsource(probar_todo.main)
check("T2e el corredor lo imprime UNA sola vez, al principio",
      src_main.count("aviso_sin_ffmpeg()") == 1
      and "if FFMPEG_PATH is None:" in src_main, "")

# ---------------------------------------------------------------------------
# T3 — el veredicto no miente sobre lo que se comprobó
# ---------------------------------------------------------------------------
sin_ff = probar_todo.veredicto_verde(52, 300, con_ffmpeg=False)
con_ff = probar_todo.veredicto_verde(52, 300, con_ffmpeg=True)
check("T3 sin ffmpeg el veredicto es PARCIAL, nunca «todo en verde»",
      "VERDE PARCIAL" in sin_ff and "TODO EN VERDE" not in sin_ff, sin_ff)
check("T3b y dice exactamente qué NO se comprobó",
      "No se comprobaron voz, audio ni montaje" in sin_ff, "")
check("T3c sin ffmpeg NO se invita a generar con confianza",
      "con confianza" not in sin_ff, sin_ff)
check("T3d con ffmpeg el veredicto de siempre se mantiene",
      "TODO EN VERDE" in con_ff and "puedes generar con confianza" in con_ff,
      con_ff)

# ---------------------------------------------------------------------------
# T4 — el corredor completo, de verdad (camino normal, con ffmpeg)
# ---------------------------------------------------------------------------
if tiene_ffmpeg:
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "probar_todo.py"),
                        "v0_51_0"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                       timeout=300)
    con = (r.stdout or "") + (r.stderr or "")
    check("T4 con ffmpeg no aparece ninguna advertencia",
          "NO ENCUENTRO FFMPEG" not in con and "VERDE PARCIAL" not in con, "")
    check("T4b y el veredicto de confianza es el de siempre",
          "TODO EN VERDE" in con and "puedes generar con confianza" in con,
          con[-300:])
else:
    print("[OK ] T4 (omitido: este equipo no tiene ffmpeg instalado)")

# ---------------------------------------------------------------------------
# T5 — el manual explica el requisito
# ---------------------------------------------------------------------------
manual = (ROOT / "MANUAL.md").read_text(encoding="utf-8")
check("T5 el manual menciona ffmpeg como requisito y cómo resolverlo",
      "ffmpeg" in manual.lower() and "C:\\ffmpeg" in manual, "")

# ---------------------------------------------------------------------------
shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.51.1 completa: la prueba encuentra ffmpeg sola y, si no "
      "está, lo dice claro en vez de fallar 34 veces sin explicación.")
