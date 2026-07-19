"""Rastreador de gasto REAL por proveedor durante una generación.

A diferencia de estimate.py (una predicción ANTES de generar, con rangos),
esto registra lo que de verdad ocurrió: tokens reales de cada llamada a
Claude, y el conteo real de imágenes/segundos de video/caracteres de voz/
minutos transcritos que efectivamente se generaron — convertido a USD con las
mismas tarifas de pricing.py. Es por-hilo (como progress.py): ejecuciones
simultáneas de proyectos distintos no se mezclan."""
from __future__ import annotations

import threading

_state = threading.local()


def reset() -> list:
    """Nuevo acumulador para el hilo actual (el de la fase que arranca la
    generación). Devuelve la lista para poder compartirla con los hilos de un
    ThreadPoolExecutor — ver `bind()`."""
    items: list = []
    _state.items = items
    return items


def bind(items: list) -> None:
    """Usa `items` (el acumulador de OTRO hilo) como el de este hilo. Los
    hilos de un ThreadPoolExecutor no heredan el estado por hilo del hilo
    que los lanzó — sin esto, el gasto de imágenes/voz/video generados EN
    PARALELO se perdía en acumuladores nuevos que nadie leía."""
    _state.items = items


def get_state() -> list:
    items = getattr(_state, "items", None)
    if items is None:
        items = _state.items = []
    return items


def record(provider: str, label: str, qty: float, unit: str, usd: float) -> None:
    items = get_state()
    items.append({"provider": provider, "label": label,
                  "qty": round(qty, 3), "unit": unit, "usd": round(float(usd), 4)})


def summarize(items: list) -> dict:
    """Agrupa una lista de registros de gasto por proveedor. Función pura —
    la usa tanto `summary()` (el hilo en curso) como el reporte acumulado del
    proyecto (una lista guardada, sin nada que ver con el hilo actual)."""
    by_provider: dict[str, dict] = {}
    for it in items:
        e = by_provider.setdefault(it["provider"], {"provider": it["provider"],
                                                     "usd": 0.0, "details": []})
        e["usd"] += it["usd"]
        e["details"].append(it)
    out = sorted(by_provider.values(), key=lambda x: -x["usd"])
    for e in out:
        e["usd"] = round(e["usd"], 4)
    return {"by_provider": out, "total_usd": round(sum(e["usd"] for e in out), 4)}


def summary() -> dict:
    return summarize(get_state())
