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


def replicate_call(client, model: str, inputs: dict):
    try:
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
    except Exception as e:
        msg = str(e)
        low = msg.lower()
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
