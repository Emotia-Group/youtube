"""Batería v0.51.3 — tu material propio deja de contar como «cambio local».

El creador vio en la interfaz «⚠ hay cambios locales sin actualizar» teniendo
la última versión recién descargada. No era un error suyo: las carpetas donde
el propio programa le pide poner SU material (`assets/elements/` para el banco
y `assets/sfx/` para efectos y ambientes) no estaban protegidas en .gitignore
—`assets/music/` sí lo estaba—, así que cada archivo suyo aparecía como cambio
del repositorio. Y el aviso, además, no decía de qué hablaba.

Verifica:
1. El material propio (banco, efectos, ambientes, música) queda IGNORADO por
   git, comprobado con git de verdad sobre archivos reales.
2. Los README y las carpetas del programa SIGUEN versionados (un `git pull`
   debe poder crear las carpetas en un equipo nuevo).
3. El aviso de la interfaz nombra los archivos y no exagera.
4. La lectura del estado de git no corta los nombres.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
import subprocess

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def ignorado(rel: str) -> bool:
    """¿git ignora esta ruta? Se le pregunta a git, no se adivina."""
    r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(ROOT),
                       capture_output=True)
    return r.returncode == 0


# ---------------------------------------------------------------------------
# T1 — el material del creador queda fuera del repositorio
# ---------------------------------------------------------------------------
mio = {
    "banco de personajes": "assets/elements/personajes/elon-musk.jpg",
    "banco de lugares": "assets/elements/lugares/El Cairo.png",
    "banco de mapas": "assets/elements/mapas/imperio-mali.png",
    "clip del banco": "assets/elements/entidades/unesco.mp4",
    "efecto propio": "assets/sfx/whoosh_mio.wav",
    "ambiente propio": "assets/sfx/ambientes/viento_desierto.mp3",
    "pista de música": "assets/music/documental.mp3",
}
for etiqueta, rel in mio.items():
    check(f"T1 git ignora tu {etiqueta}", ignorado(rel), rel)

# ---------------------------------------------------------------------------
# T2 — lo del PROGRAMA sigue versionado (si no, un equipo nuevo se queda sin
#      las carpetas ni las instrucciones)
# ---------------------------------------------------------------------------
del_programa = ["assets/elements/README.md", "assets/sfx/README.md",
                "assets/music/README.md", "assets/hooks/hooks_virales.json",
                "assets/elements/personajes/.gitkeep",
                "assets/sfx/ambientes/.gitkeep"]
for rel in del_programa:
    check(f"T2 «{rel}» sigue en el repositorio", not ignorado(rel), "")

rastreados = subprocess.run(["git", "ls-files", "assets/"], cwd=str(ROOT),
                            capture_output=True, text=True).stdout.split()
check("T2b las 5 categorías del banco viajan con el programa",
      sum(1 for f in rastreados if f.endswith(".gitkeep")
          and "elements/" in f) == 5,
      str([f for f in rastreados if f.endswith('.gitkeep')]))

# ---------------------------------------------------------------------------
# T3 — de verdad: crear material propio no ensucia el estado del repositorio
# ---------------------------------------------------------------------------
creados: list[Path] = []
try:
    for rel in mio.values():
        p = ROOT / rel
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"material de prueba")
        creados.append(p)
    sucio = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                           capture_output=True, text=True).stdout
    intrusos = [ln for ln in sucio.splitlines()
                if "assets/" in ln or "assets\\" in ln]
    check("T3 con tu material dentro, git NO reporta cambios en assets/",
          not intrusos, str(intrusos[:4]))
finally:
    for p in creados:
        p.unlink(missing_ok=True)

# ---------------------------------------------------------------------------
# T4 — el aviso de la interfaz: preciso, no alarmista
# ---------------------------------------------------------------------------
from ytstudio.webui.server import get_version

v = get_version()
check("T4 el estado del programa informa CUÁNTOS y CUÁLES archivos cambiaron",
      "modified_files" in v and "modified_count" in v
      and isinstance(v["modified_files"], list), str(list(v)))
check("T4b los nombres llegan completos (no se come la primera letra)",
      all(not f.startswith("itignore") and f == f.strip()
          for f in v["modified_files"]), str(v["modified_files"]))
# El parseo se comprueba con una salida REAL de git (incluye el espacio
# inicial que antes se comía la primera letra del nombre)
from ytstudio.webui.server import archivos_modificados

muestra = (" M .gitignore\n"
           "?? assets/elements/personajes/elon-musk.jpg\n"
           "A  ytstudio/webui/server.py\n"
           " D .env.ejemplo\n")
parsed = archivos_modificados(muestra)
check("T4c los nombres se leen íntegros, empiecen por punto o no",
      parsed == [".gitignore", "assets/elements/personajes/elon-musk.jpg",
                 "ytstudio/webui/server.py", ".env.ejemplo"], str(parsed))
check("T4c2 una salida vacía no inventa archivos",
      archivos_modificados("") == [] and archivos_modificados("\n\n") == [],
      "")

html = (ROOT / "ytstudio" / "webui" / "static" / "index.html").read_text(
    encoding="utf-8")
check("T4d la interfaz ya no dice «cambios locales sin actualizar» "
      "(sonaba a «estás desactualizado»)",
      "cambios locales sin actualizar" not in html, "")
check("T4e ahora nombra los archivos modificados del programa",
      "archivo(s) del programa modificados" in html
      and "modified_files" in html, "")

# el aviso GRANDE de «actualización descargada pero no aplicada» sigue intacto
check("T4f y se conserva el aviso de reiniciar tras actualizar",
      "NO aplicada" in html and "server_version" in html, "")

# ---------------------------------------------------------------------------
# T5 — el manual explica qué es normal y qué no
# ---------------------------------------------------------------------------
manual = (ROOT / "MANUAL.md").read_text(encoding="utf-8")
check("T5 el manual aclara el aviso de archivos modificados",
      "archivo(s) del programa modificados" in manual
      or "archivos del programa modificados" in manual, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.51.3 completa: tu material propio vive en tu equipo sin "
      "ensuciar el repositorio, y el aviso dice exactamente qué pasa.")
