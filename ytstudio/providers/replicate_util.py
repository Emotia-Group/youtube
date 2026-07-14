"""Utilidad común para los proveedores basados en Replicate (imágenes FLUX,
video Kling/Wan, música MusicGen).

- Resuelve la última versión del modelo dinámicamente (los hashes de versión
  de Replicate caducan; depender de uno fijo provoca 404 con el tiempo).
- Usa predicciones con polling (`wait`) en vez de una única petición larga, así
  los modelos lentos como Kling (varios minutos por clip) no expiran por
  timeout de lectura.
- Traduce los errores crípticos de Replicate a mensajes claros en español.
"""
from __future__ import annotations

import threading

# Canal opcional para mostrar avisos (p.ej. esperas por límite de velocidad) en
# el registro de progreso de la interfaz. Es por-hilo, así que ejecuciones
# simultáneas de proyectos distintos no se mezclan. Si nadie lo configura, los
# avisos van a stdout (visible en la consola).
_progress = threading.local()


def set_progress(fn) -> None:
    """El pipeline lo conecta al log de la ejecución en curso."""
    _progress.fn = fn


def _notify(msg: str) -> None:
    fn = getattr(_progress, "fn", None)
    (fn or print)(msg)


def _resolve_version(client, model: str) -> str | None:
    """Devuelve el id de versión a usar. Si el modelo ya trae ':hash', lo usa;
    si es un slug 'owner/name', consulta la última versión publicada."""
    if ":" in model:
        return model.split(":", 1)[1]
    try:
        m = client.models.get(model)
        version = getattr(m, "latest_version", None)
        if version is not None:
            return version.id
    except Exception:
        pass
    return None  # sin versión → se usará client.run con el slug tal cual


def _reset_seconds(msg: str) -> float | None:
    """Extrae el tiempo de espera que indica Replicate en un 429
    (ej. 'resets in ~4s' o 'retry after 10')."""
    import re
    m = re.search(r"resets? in ~?(\d+(?:\.\d+)?)\s*s", msg, re.I) \
        or re.search(r"retry[- ]after[:=]?\s*(\d+(?:\.\d+)?)", msg, re.I)
    return float(m.group(1)) if m else None


def _once(client, model: str, inputs: dict):
    version_id = _resolve_version(client, model)
    if version_id:
        # Polling: no sufre el read-timeout de una sola petición larga.
        pred = client.predictions.create(version=version_id, input=inputs)
        pred.wait()
        if pred.status != "succeeded":
            raise RuntimeError(
                f"Replicate no completó la generación (estado: {pred.status})"
                + (f": {pred.error}" if getattr(pred, "error", None) else ""))
        return pred.output
    return client.run(model, input=inputs)


def replicate_call(client, model: str, inputs: dict, max_retries: int = 10):
    import time
    for attempt in range(max_retries + 1):
        try:
            return _once(client, model, inputs)
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            # Límite de velocidad (429): esperar el tiempo indicado y reintentar.
            # Con <$5 de crédito Replicate limita a ~6 peticiones/min (1 cada
            # ~10 s), así que las escenas se espacian solas en vez de fallar.
            # El "resets in ~Ns" que informa Replicate suele quedarse corto, por
            # eso se aplica un suelo de 12 s: total ~2 min de reintentos, más
            # que suficiente para atravesar el límite reducido.
            is_rate = "429" in msg or "throttled" in low or "rate limit" in low
            if is_rate and attempt < max_retries:
                wait = _reset_seconds(msg) or 0
                delay = min(max(wait, 10) + 2, 60)
                _notify(
                    f"⏳ Replicate limita las peticiones (crédito bajo): "
                    f"esperando {delay:.0f}s y reintentando "
                    f"({attempt + 1}/{max_retries})…")
                time.sleep(delay)
                continue
            _raise_clear(e, msg, low, model)


def _raise_clear(e, msg, low, model):
    if "429" in msg or "throttled" in low or "rate limit" in low:
        raise RuntimeError(
            "Replicate está limitando las peticiones porque tu crédito es "
            "bajo (menos de $5): permite solo 6 imágenes por minuto y aún "
            "así se agotó tras varios reintentos. Opciones: añade saldo en "
            "https://replicate.com/account/billing, reduce el nº de escenas "
            "(ritmo visual más pausado en ⚙ Configuración), o usa OpenAI "
            "para imágenes (no tiene ese límite)."
        ) from e
    if "401" in msg or "invalid token" in low or "authentication" in low \
            or "unauthenticated" in low:
        raise RuntimeError(
            "El token de Replicate no es válido. Importante: FLUX, Kling y "
            "MusicGen se usan A TRAVÉS de Replicate, así que necesitas un "
            "token de replicate.com — NO la clave de KlingAI ni la de "
            "OpenAI. Consíguelo en https://replicate.com/account/api-tokens "
            "(empieza por 'r8_') y pégalo en ⚙ Configuración → Replicate. "
            "Alternativa rápida: cambia el proveedor de imágenes a OpenAI "
            "en ⚙ Configuración (tu clave de OpenAI ya está activa)."
        ) from e
    if "402" in msg or "payment" in low or "billing" in low \
            or "insufficient" in low or "spend" in low:
        raise RuntimeError(
            "Replicate rechazó la petición por facturación: añade un método "
            "de pago o saldo en https://replicate.com/account/billing. "
            "Alternativa: usa OpenAI para imágenes en ⚙ Configuración."
        ) from e
    if "404" in msg or "could not be found" in low or "not found" in low:
        raise RuntimeError(
            f"El modelo de Replicate '{model}' no se encontró. Revisa el "
            "nombre en ⚙ Configuración o deja el modelo por defecto. Si es un "
            "modelo con versión, puede que esa versión ya no exista."
        ) from e
    raise
