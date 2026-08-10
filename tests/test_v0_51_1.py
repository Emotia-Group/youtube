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
# ---------------------------------------------------------------------------
def correr_runner(con_ffmpeg: bool, filtro: str = "v0_51_0") -> str:
    """Ejecuta el runner de verdad, con o sin ffmpeg visible en el PATH."""
    vacio = TMP / "bin_vacio"
    vacio.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if not con_ffmpeg:
        # PATH sin ffmpeg pero con lo mínimo para arrancar Python
        env["PATH"] = str(vacio)
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "probar_todo.py"),
                        filtro],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=300)
    return (r.stdout or "") + (r.stderr or "")


sin = correr_runner(con_ffmpeg=False)
check("T2 sin ffmpeg lo dice explícitamente y arriba del todo",
      "NO ENCUENTRO FFMPEG" in sin, sin[:200])
check("T2b explica dónde ponerlo en Windows (C:\\ffmpeg) con el enlace",
      "C:\\ffmpeg" in sin and "gyan.dev" in sin, "")
check("T2c y también para Linux/Mac",
      "apt install ffmpeg" in sin and "brew install ffmpeg" in sin, "")
check("T2d el aviso sale UNA vez, no por cada batería",
      sin.count("NO ENCUENTRO FFMPEG") == 1,
      str(sin.count("NO ENCUENTRO FFMPEG")))

# ---------------------------------------------------------------------------
# T3 — sin ffmpeg NO se declara «todo en verde» (honestidad del veredicto)
# ---------------------------------------------------------------------------
check("T3 el veredicto sin ffmpeg es PARCIAL, no «todo en verde»",
      "VERDE PARCIAL" in sin and "TODO EN VERDE" not in sin, sin[-400:])
check("T3b y avisa de qué NO se comprobó",
      "No se comprobaron voz, audio ni montaje" in sin, "")

# ---------------------------------------------------------------------------
# T4 — con ffmpeg, todo sigue como siempre
# ---------------------------------------------------------------------------
if tiene_ffmpeg:
    con = correr_runner(con_ffmpeg=True)
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
