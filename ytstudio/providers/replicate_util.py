"""Utilidad común para los proveedores basados en Replicate (imágenes FLUX,
video Kling/Wan, música MusicGen). Traduce los errores crípticos de Replicate
—sobre todo el 401 de token inválido— a mensajes claros en español."""
from __future__ import annotations


def replicate_call(client, model: str, inputs: dict):
    try:
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
        raise
