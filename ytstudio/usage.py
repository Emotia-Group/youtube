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


# --- TOPE DE PRESUPUESTO --------------------------------------------------
# Freno de mano: ninguna generación puede gastar más de lo autorizado. Se
# comprueba ANTES de cada llamada que cuesta dinero, así un bucle de
# reintentos o un modelo caro no puede vaciar el saldo sin avisar.
# El tope es compartido por TODOS los hilos de la generación (los workers
# gastan en paralelo), por eso vive en un contenedor global y no por-hilo.

class BudgetExceeded(RuntimeError):
    """El gasto autorizado para esta generación se agotó."""


_budget = {"cap": 0.0, "spent": 0.0}
_budget_lock = threading.Lock()


def set_cap(usd: float, reset: bool = True) -> None:
    """Fija el tope de esta generación (0 o negativo = sin tope).

    reset=False al RECALCULAR el tope a mitad de corrida: el gasto ya
    incurrido debe seguir contando (si no, cada recálculo regalaría un
    presupuesto nuevo y el freno no serviría de nada)."""
    with _budget_lock:
        _budget["cap"] = float(usd or 0)
        if reset:
            _budget["spent"] = 0.0


def add_spend(usd: float) -> None:
    """Suma gasto REAL confirmado (dinero ya comprometido con el proveedor)."""
    with _budget_lock:
        _budget["spent"] += float(usd or 0)


def spent() -> float:
    with _budget_lock:
        return round(_budget["spent"], 4)


def cap() -> float:
    with _budget_lock:
        return _budget["cap"]


def check_budget(next_usd: float, what: str = "esta generación") -> None:
    """Lanza BudgetExceeded si autorizar `next_usd` pasaría del tope."""
    with _budget_lock:
        limit = _budget["cap"]
        if limit <= 0:
            return
        so_far = _budget["spent"]
    if so_far + float(next_usd or 0) > limit:
        raise BudgetExceeded(
            f"TOPE DE PRESUPUESTO ALCANZADO: llevas ${so_far:.2f} gastados en "
            f"esta generación y {what} costaría ~${float(next_usd or 0):.2f}, "
            f"por encima del tope de ${limit:.2f}. Se detiene aquí para no "
            "seguir gastando. Sube el tope en ⚙ Configuración → Presupuesto "
            "(budget.max_usd) o reduce escenas/modelos caros, y pulsa "
            "«Generar video» para reanudar: lo ya generado no se repite ni se "
            "vuelve a cobrar.")


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
