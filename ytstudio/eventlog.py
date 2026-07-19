"""Registro de eventos persistente: novedades, errores y TIEMPOS de cada
acción del programa. Sirve para diagnosticar y para compartir el historial
(descargable desde la interfaz).

Se guarda en data/events.log (fuera de Git) en formato JSON-lines — una línea
por evento, fácil de leer y de filtrar. El archivo no crece sin límite: se
conserva la cola de los últimos eventos."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "data" / "events.log"
_LOCK = threading.Lock()
_MAX_LINES = 5000

LEVELS = ("info", "warn", "error")


def log(level: str, message: str, *, phase: str | None = None,
        project: str | None = None, seconds: float | None = None) -> None:
    """Añade un evento. level: info | warn | error."""
    entry: dict = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "level": level if level in LEVELS else "info",
                   "message": str(message)[:2000]}
    if phase:
        entry["phase"] = phase
    if project:
        entry["project"] = project
    if seconds is not None:
        entry["seconds"] = round(float(seconds), 1)
    line = json.dumps(entry, ensure_ascii=False)
    with _LOCK:
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            _trim()
        except OSError:
            pass  # el log jamás debe tumbar el programa


def _trim() -> None:
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_LINES:
            LOG_PATH.write_text("\n".join(lines[-_MAX_LINES:]) + "\n",
                                encoding="utf-8")
    except OSError:
        pass


def recent(limit: int = 300, project: str | None = None) -> list[dict]:
    """Últimos eventos (los más recientes primero), opcionalmente de un
    proyecto concreto."""
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for ln in reversed(lines):
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if project and e.get("project") != project:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


def raw_text() -> str:
    try:
        return LOG_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def path() -> Path:
    return LOG_PATH
