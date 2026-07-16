"""Canal de progreso compartido: permite que cualquier fase escriba avisos en
el registro de la interfaz (descargas largas, análisis, esperas…) sin tener
que pasar el callback de log por todas las funciones.

Es por-hilo: ejecuciones simultáneas de proyectos distintos no se mezclan. Si
nadie configura un sink, los avisos van a stdout (visibles en la consola)."""
from __future__ import annotations

import threading

_state = threading.local()


def set_sink(fn) -> None:
    """El pipeline lo conecta al log de la ejecución en curso."""
    _state.fn = fn


def notify(msg: str) -> None:
    fn = getattr(_state, "fn", None)
    (fn or print)(msg)
