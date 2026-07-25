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


def _is_transient_network_error(e: Exception) -> bool:
    """Cortes de red pasajeros (reinicio de conexión, timeout, DNS
    momentáneo): no son un problema del modelo ni de la cuenta, se resuelven
    solos con un reintento. Cubre tanto errores tipados (ConnectionError,
    TimeoutError — incluye ConnectionResetError/ConnectionAbortedError en
    cualquier SO) como el WinError 10054/10053 que Windows reporta como texto
    dentro de una excepción genérica al atravesar capas de librerías."""
    if isinstance(e, (ConnectionError, TimeoutError)):
        return True
    msg = str(e).lower()
    return any(s in msg for s in (
        "winerror 10054", "winerror 10053", "winerror 10060",
        "connection reset", "connection aborted", "forcibly closed",
        "remote end closed connection", "read timed out", "timed out",
    ))


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


def replicate_call(client, model: str, inputs: dict, max_retries: int = 10,
                    net_retries: int = 5):
    import time
    net_attempt = 0
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
            # Corte de red pasajero (ej. WinError 10054 al reiniciarse la
            # conexión): antes esto detenía la fase entera a la primera; se
            # reintenta con espera creciente antes de rendirse.
            if _is_transient_network_error(e) and net_attempt < net_retries:
                net_attempt += 1
                delay = min(2 ** net_attempt, 30)
                _notify(
                    f"⚠ Corte de red pasajero con Replicate: reintentando en "
                    f"{delay}s ({net_attempt}/{net_retries})…")
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
    if _is_transient_network_error(e):
        raise RuntimeError(
            f"Corte de conexión con Replicate tras varios reintentos: {msg} "
            "Suele ser Wi-Fi/VPN inestable o el propio Replicate cortando la "
            "descarga a medio camino — revisa tu conexión y pulsa «Generar "
            "video» de nuevo para reanudar desde aquí."
        ) from e
    raise


def download_with_retry(url: str, out, max_retries: int = 5) -> None:
    """urlretrieve() con el mismo reintento ante cortes de red pasajeros que
    replicate_call(): la descarga del resultado es una petición de red aparte
    y puede cortarse aunque la predicción ya haya terminado bien."""
    import time
    import urllib.request
    for attempt in range(max_retries + 1):
        try:
            urllib.request.urlretrieve(url, out)
            return
        except Exception as e:
            if _is_transient_network_error(e) and attempt < max_retries:
                delay = min(2 ** (attempt + 1), 30)
                _notify(
                    f"⚠ Corte de red pasajero al descargar el resultado: "
                    f"reintentando en {delay}s ({attempt + 1}/{max_retries})…")
                time.sleep(delay)
                continue
            raise
