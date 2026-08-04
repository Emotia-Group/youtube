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
import time
from pathlib import Path

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


def _rewind_inputs(inputs: dict) -> None:
    """Rebobina los archivos abiertos de los inputs antes de (re)enviarlos.
    Al reintentar una llamada, los handles ya fueron leídos hasta el final por
    el intento anterior: sin esto, el reintento sube archivos VACÍOS y el
    modelo falla del lado del servidor con errores crípticos (p. ej. Kling:
    «'NoneType' object has no attribute 'read'»)."""
    def _seek0(v):
        if hasattr(v, "seek"):
            try:
                v.seek(0)
            except Exception:
                pass
    for v in inputs.values():
        if isinstance(v, (list, tuple)):
            for x in v:
                _seek0(x)
        else:
            _seek0(v)


class PersistentNetworkError(RuntimeError):
    """Corte de red que YA agotó sus reintentos de reconexión: el bucle
    exterior de replicate_call no debe re-crear la predicción (re-crearla
    volvería a cobrar el modelo completo)."""


def _wait_prediction(client, pred, net_retries: int = 5):
    """Espera una predicción YA CREADA, reanudando el sondeo si la conexión se
    corta a mitad de la espera. Clave: la generación sigue corriendo en el
    servidor (y ya está cobrada) — re-consultar la MISMA predicción no cuesta
    nada, mientras que re-crearla volvería a cobrar el modelo completo."""
    import time
    attempt = 0
    while True:
        try:
            pred.wait()
        except Exception as e:
            if not _is_transient_network_error(e):
                raise
            if attempt >= net_retries:
                raise PersistentNetworkError(
                    "La conexión con Replicate se cortó repetidamente mientras "
                    "se esperaba el resultado y no se pudo reconectar "
                    f"({net_retries} intentos). Detalle: {e}. Suele ser "
                    "Wi-Fi/VPN/antivirus cortando conexiones largas — prueba "
                    "otra red y vuelve a generar (lo ya completado se reanuda)."
                ) from e
            attempt += 1
            delay = min(2 ** attempt, 30)
            _notify(
                f"⚠ Corte de red esperando el resultado: reconectando en "
                f"{delay}s ({attempt}/{net_retries}) — la generación sigue "
                "en el servidor, no se cobra de nuevo…")
            time.sleep(delay)
            try:
                pred = client.predictions.get(pred.id)
            except Exception:
                pass  # el próximo pred.wait() reintenta la conexión
            continue
        if pred.status != "succeeded":
            raise RuntimeError(
                f"Replicate no completó la generación (estado: {pred.status})"
                + (f": {pred.error}" if getattr(pred, "error", None) else ""))
        return pred.output


def _first_url(output):
    """La URL del resultado (la salida puede venir como lista o suelta)."""
    if isinstance(output, (list, tuple)):
        return str(output[0]) if output else ""
    return str(output or "")


def _adopt_orphan(client, model: str, since: float, known_ids: set):
    """Tras un corte de red en `predictions.create()` NO se sabe si la
    predicción llegó a crearse en el servidor: si se creó, ya está corriendo y
    se COBRARÁ, y crear otra sería pagar dos veces. Antes de reintentar se
    buscan las predicciones recién creadas de este mismo modelo y se adopta la
    huérfana en vez de duplicarla."""
    try:
        page = client.predictions.list()
        items = getattr(page, "results", None) or list(page)
    except Exception:
        return None
    for p in items:
        pid = getattr(p, "id", None)
        if not pid or pid in known_ids:
            continue
        if getattr(p, "status", "") in ("canceled", "failed"):
            continue
        created = getattr(p, "created_at", None)
        ts = _parse_ts(created)
        if ts is not None and ts < since - 5:
            continue  # anterior a nuestro intento: no es nuestra
        ver = str(getattr(p, "version", "") or "")
        mdl = str(getattr(p, "model", "") or "")
        if model.split(":")[0] in mdl or (ver and ver in model):
            return p
    return None


def _parse_ts(value) -> float | None:
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _once(client, model: str, inputs: dict, net_retries: int = 5,
          reuse_key: str = "", charge: dict | None = None,
          known_ids: set | None = None):
    """Una ejecución completa: crear (o adoptar/reenganchar) la predicción,
    esperarla y devolver su salida. Registra en el LIBRO cada paso en el que
    el dinero entra en riesgo, para que nada pagado se pierda."""
    from ytstudio import ledger, usage
    known_ids = known_ids if known_ids is not None else set()
    version_id = _resolve_version(client, model)
    if not version_id:
        # Sin versión resoluble no hay id de predicción que anotar; es el
        # camino de respaldo (client.run) y no admite recuperación.
        return client.run(model, input=inputs)

    usd = float((charge or {}).get("usd") or 0)

    # 1) ¿Hay algo YA PAGADO o en curso para esta misma escena? Reutilízalo.
    if reuse_key:
        prev = ledger.find_reusable(reuse_key)
        if prev and prev.get("status") == "succeeded" and prev.get("url"):
            _notify("💰 Recuperando un resultado que YA habías pagado (no se "
                    "vuelve a cobrar)…")
            return {"__pred_id__": prev["id"], "__reused__": True,
                    "output": prev["url"]}
        if prev and prev.get("status") == "created":
            try:
                running = client.predictions.get(prev["id"])
                _notify("💰 Reenganchando una generación que sigue corriendo "
                        "en el servidor (ya cobrada, no se duplica)…")
                out = _wait_prediction(client, running, net_retries)
                ledger.record_succeeded(prev["id"], _first_url(out))
                return {"__pred_id__": prev["id"], "output": out}
            except PersistentNetworkError:
                raise
            except Exception:
                pass  # no se pudo reenganchar: se crea una nueva más abajo

    # 2) Crear. A partir de aquí el dinero puede cobrarse: se anota SIEMPRE.
    if usd:
        usage.check_budget(usd, (charge or {}).get("label") or "esta llamada")
    started = time.time()
    try:
        pred = client.predictions.create(version=version_id, input=inputs)
    except Exception as e:
        if _is_transient_network_error(e):
            orphan = _adopt_orphan(client, model, started, known_ids)
            if orphan is not None:
                _notify("💰 La conexión se cortó al lanzar la generación, pero "
                        "el servidor SÍ la había aceptado: se adopta esa "
                        "misma (no se paga dos veces)…")
                pred = orphan
            else:
                raise
        else:
            raise
    pid = getattr(pred, "id", "") or ""
    if pid:
        known_ids.add(pid)
        ledger.record_created(pid, model, reuse_key, usd,
                              (charge or {}).get("project") or "",
                              (charge or {}).get("label") or "")

    # 3) Esperar. Si termina bien, el cobro es un hecho: se registra el gasto
    #    AQUÍ (no tras la descarga), para que jamás haya dinero invisible.
    try:
        out = _wait_prediction(client, pred, net_retries)
    except Exception as e:
        if pid and not isinstance(e, PersistentNetworkError):
            ledger.record_failed(pid, str(e))
        raise
    if pid:
        ledger.record_succeeded(pid, _first_url(out))
    _charge_now(charge)
    return {"__pred_id__": pid, "output": out}


def _charge_now(charge: dict | None) -> None:
    """Anota el gasto REAL en cuanto la predicción termina bien. Antes esto
    ocurría después de descargar el archivo: si la descarga fallaba, el
    dinero ya gastado NO aparecía en el reporte (así se perdieron $11.85 sin
    dejar rastro)."""
    if not charge:
        return
    from ytstudio import usage
    usd = float(charge.get("usd") or 0)
    usage.record(charge.get("provider", "replicate"), charge.get("label", ""),
                 float(charge.get("qty") or 1), charge.get("unit", "u"), usd)
    usage.add_spend(usd)


def _call_raw(client, model: str, inputs: dict, max_retries: int = 10,
              net_retries: int = 5, reuse_key: str = "",
              charge: dict | None = None):
    """Como replicate_call pero devuelve el sobre con el id de la predicción,
    para que quien descargue pueda cerrar el círculo en el libro."""
    net_attempt = 0
    known_ids: set = set()
    for attempt in range(max_retries + 1):
        try:
            _rewind_inputs(inputs)
            return _once(client, model, inputs, net_retries, reuse_key,
                         charge, known_ids)
        except PersistentNetworkError:
            raise  # ya se reintentó la reconexión; re-crear re-cobraría
        except Exception as e:
            from ytstudio import usage
            if isinstance(e, usage.BudgetExceeded):
                raise  # el freno de mano no se reintenta
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


def replicate_call(client, model: str, inputs: dict, max_retries: int = 10,
                    net_retries: int = 5, reuse_key: str = "",
                    charge: dict | None = None):
    """Ejecuta un modelo y devuelve su salida.

    net_retries: cuántos cortes de red pasajeros se reintentan. Los
    proveedores CON degradación por escena (lipsync, clips de video) pasan un
    valor bajo — si su red está caída de verdad, mejor caer rápido a la
    imagen fija que retener la fase varios minutos por escena."""
    env = _call_raw(client, model, inputs, max_retries, net_retries,
                    reuse_key, charge)
    return env["output"] if isinstance(env, dict) and "output" in env else env


def run_and_download(client, model: str, inputs: dict, out,
                     charge: dict | None = None, net_retries: int = 5,
                     max_retries: int = 10):
    """EL camino seguro para cualquier generación que cuesta dinero: crear (o
    recuperar) la predicción, esperarla, descargar el archivo y CERRAR EL
    CÍRCULO en el libro.

    La clave de reutilización es el propio archivo de destino (`out`), que es
    estable entre ejecuciones: la escena 1 de este proyecto siempre apunta al
    mismo archivo. Así, si una descarga falla, el siguiente intento re-usa la
    predicción YA PAGADA en vez de encargar —y pagar— otra igual."""
    out = Path(out)
    reuse_key = f"{model}::{out}"
    env = _call_raw(client, model, inputs, max_retries, net_retries,
                    reuse_key, charge)
    pid = env.get("__pred_id__", "") if isinstance(env, dict) else ""
    output = env["output"] if isinstance(env, dict) and "output" in env else env
    url = _first_url(output)
    try:
        download_with_retry(url, out)
    except Exception as e:
        if pid:
            _notify(
                "⚠ La generación TERMINÓ BIEN (y por tanto ya se cobró) pero "
                "la descarga falló. Queda anotada en el libro de predicciones: "
                "vuelve a pulsar «Generar video» dentro de la próxima hora y se "
                "re-descargará SIN volver a cobrar.")
        raise
    if pid:
        from ytstudio import ledger
        ledger.record_downloaded(pid, out)
    return out


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
