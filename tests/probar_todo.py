"""Corre TODAS las baterías de prueba de ytstudio y resume el resultado.

Para qué sirve: comprobar que el programa está sano ANTES de gastar dinero en
una generación real. No usa ninguna clave de API ni conexión a internet: cada
batería trabaja con proveedores falsos, audio sintético y ffmpeg local, en
carpetas temporales — tus proyectos no se tocan.

Uso:
    py tests/probar_todo.py              # todas
    py tests/probar_todo.py 42           # solo las que contienen «42»
    py tests/probar_todo.py narracion    # (sin tildes; busca en el nombre)
    py tests/probar_todo.py --lista      # ver qué baterías hay, sin correr

En Windows tienes el atajo «probar.bat» (doble clic) en la carpeta del
programa; en Linux/Mac, «./probar.sh».
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
TIMEOUT = 900  # segundos por batería (los montajes con ffmpeg tardan)
FFMPEG_PATH: str | None = None   # PATH con ffmpeg ya localizado (ver main)

# Que los símbolos (✔ ✘ 🧪) no rompan la salida en una consola no-UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # consola antigua o salida redirigida
        pass


def _version() -> str:
    """Versión activa: la del primer encabezado del CHANGELOG."""
    try:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        m = re.search(r"^##\s*(v[\d.]+)", text, re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def _asegurar_ffmpeg() -> str | None:
    """Deja ffmpeg accesible para las baterías y devuelve el PATH resultante
    (o None si no se encontró).

    POR QUÉ ESTO EXISTE: en Windows es normal tener ffmpeg en C:\\ffmpeg\\bin
    SIN añadirlo al PATH del sistema. El programa se las arregla solo (busca
    ahí y lo añade al PATH de su proceso al arrancar una generación), pero
    cada batería corre en su PROPIO proceso y no pasaba por esa ayuda: se
    quedaba sin ffmpeg y fallaba con un críptico «[WinError 2] El sistema no
    puede encontrar el archivo especificado» — 34 baterías en rojo con el
    programa perfectamente sano (caso real del creador). Aquí se resuelve una
    vez y el PATH ya resuelto se hereda a todas."""
    sys.path.insert(0, str(ROOT))
    try:
        from ytstudio.utils.media import require_ffmpeg
        require_ffmpeg()          # en Windows añade C:\ffmpeg\... al PATH
        return os.environ["PATH"]
    except Exception:
        return None


def _natural(path: Path):
    """Orden natural: v0.9 antes que v0.10 (y las viejas 'vNN' al final)."""
    nums = [int(n) for n in re.findall(r"\d+", path.stem)]
    return (len(nums), nums, path.stem)


def collect(filtro: str = "") -> list[Path]:
    files = sorted((p for p in TESTS_DIR.glob("test_*.py")), key=_natural)
    if filtro:
        f = filtro.lower()
        files = [p for p in files if f in p.stem.lower()]
    return files


def run_one(path: Path) -> tuple[bool, float, str]:
    """Cada batería corre en su PROPIO proceso: son guiones independientes con
    estado global (parches a proveedores, rutas), y así una no contamina a
    otra ni un cuelgue tumba la suite."""
    start = time.time()
    # UTF-8 obligatorio en el hijo: las baterías imprimen ✔/✘ y acentos, y al
    # capturar su salida por tubería Python usa la codificación del sistema
    # (cp1252 en un Windows en español) — cada ✔ reventaría con
    # UnicodeEncodeError y TODA la suite fallaría en la máquina del creador
    # sin que el programa tenga nada malo.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if FFMPEG_PATH:
        env["PATH"] = FFMPEG_PATH   # ffmpeg localizado por el runner (ver arriba)
    try:
        proc = subprocess.run(
            [sys.executable, str(path)], cwd=str(ROOT), timeout=TIMEOUT,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, time.time() - start, out
    except subprocess.TimeoutExpired:
        return False, time.time() - start, f"La batería superó {TIMEOUT}s."


def _tail(out: str, n: int = 12) -> str:
    """Últimas líneas útiles (las que explican el fallo)."""
    lines = [ln for ln in out.splitlines() if ln.strip()]
    marcadas = [ln for ln in lines if "✘" in ln or "FALL" in ln or "Error" in ln]
    return "\n".join(f"      {ln}" for ln in (marcadas or lines)[-n:])


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if "--lista" in args:
        for p in collect():
            print("  " + p.stem)
        return 0
    filtro = next((a for a in args if not a.startswith("-")), "")

    files = collect(filtro)
    if not files:
        print(f"No hay baterías que coincidan con «{filtro}».")
        return 1

    global FFMPEG_PATH
    FFMPEG_PATH = _asegurar_ffmpeg()

    print(f"🧪 ytstudio {_version()} — {len(files)} batería(s) de prueba")
    print("   Sin claves de API ni internet; tus proyectos no se tocan.")
    if FFMPEG_PATH is None:
        # Sin ffmpeg, dos tercios de las baterías fallarían con un error
        # críptico. Mejor decirlo UNA vez, claro y arriba, que 34 veces abajo.
        print("\n" + "─" * 62)
        print("⚠ NO ENCUENTRO FFMPEG — la prueba no puede ser concluyente.")
        print("  Las baterías de voz, audio y montaje necesitan ffmpeg para")
        print("  crear y medir archivos de prueba; sin él fallarán aunque el")
        print("  programa esté perfecto.")
        print("  · Windows: descomprime ffmpeg en C:\\ffmpeg (debe existir")
        print("    C:\\ffmpeg\\bin\\ffmpeg.exe) — https://www.gyan.dev/ffmpeg/builds/")
        print("  · Linux/Mac: apt install ffmpeg  ·  brew install ffmpeg")
        print("  Corren igual las baterías que no lo necesitan.")
        print("─" * 62)
    print()

    fallos: list[tuple[Path, str]] = []
    t0 = time.time()
    for i, path in enumerate(files, 1):
        etiqueta = f"[{i:2d}/{len(files)}] {path.stem:<22}"
        print(f"{etiqueta} … ", end="", flush=True)
        ok, secs, out = run_one(path)
        print(f"{'✔ OK  ' if ok else '✘ FALLA'} ({secs:5.1f}s)")
        if not ok:
            fallos.append((path, out))

    total = time.time() - t0
    print("\n" + "─" * 62)
    if not fallos:
        if FFMPEG_PATH is None:
            # Sin ffmpeg no se probaron voz, audio ni montaje: decir «todo en
            # verde» aquí sería mentir sobre lo que de verdad se comprobó.
            print(f"◐ VERDE PARCIAL — {len(files)} baterías en {total:.0f}s, "
                  "pero SIN ffmpeg.")
            print("  No se comprobaron voz, audio ni montaje. Instala ffmpeg y")
            print("  repite la prueba antes de una generación importante.")
            return 0
        print(f"✔ TODO EN VERDE — {len(files)} baterías en {total:.0f}s.")
        print("  El programa está sano: puedes generar con confianza.")
        return 0

    print(f"✘ {len(fallos)} de {len(files)} baterías FALLARON ({total:.0f}s):\n")
    if FFMPEG_PATH is None:
        print("  ⚠ FALTA FFMPEG: esa es casi con seguridad la ÚNICA causa de")
        print("    estos fallos (todas las baterías de voz, audio y montaje lo")
        print("    necesitan). Instálalo como se indica arriba y vuelve a")
        print("    correr la prueba antes de sacar conclusiones.\n")
    for path, out in fallos:
        print(f"  ▸ {path.stem}")
        print(_tail(out))
        print()
    print("Copia este resumen y pásaselo a Claude para que lo diagnostique.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(130)
    except BrokenPipeError:
        # La salida se estaba enviando a otro programa (| more, | head) que se
        # cerró antes: no es un error de las pruebas.
        sys.exit(0)
