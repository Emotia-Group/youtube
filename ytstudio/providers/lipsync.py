"""Personaje narrador con LIPSYNC: a partir de UNA imagen del personaje y el
tramo de audio EXACTO de la escena (vo_XXX.mp3, cortado de la pista única de
voz), genera un clip del personaje hablando. El clip entra al montaje como
video MUDO de la escena — la voz la pone la pista continua global, así que
los labios quedan sincronizados sin tocar el motor de sincronía.

Cada modelo de Replicate espera nombres de input distintos; se mapean aquí.
"""
from __future__ import annotations

from pathlib import Path

# input mapping por modelo: (clave_imagen, clave_audio, extras)
_MODEL_INPUTS = {
    "bytedance/omni-human": ("image", "audio", {}),
    "zsxkib/sonic": ("image", "audio", {"dynamic_scale": 1.0}),
    "cjwbw/sadtalker": ("source_image", "driven_audio", {"still": True,
                                                         "preprocess": "full"}),
}


class ReplicateLipsync:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        lcfg = cfg.get("providers", {}).get("lipsync", {}) or {}
        self.model = lcfg.get("model", "cjwbw/sadtalker")

    def generate(self, image: Path, audio: Path, out: Path,
                 seconds: float) -> Path:
        import contextlib
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        img_key, aud_key, extras = _MODEL_INPUTS.get(
            self.model, ("image", "audio", {}))
        # El gasto se declara ANTES: run_and_download lo anota en cuanto la
        # predicción termina bien (aunque luego falle la descarga) y lo cuenta
        # contra el tope de presupuesto ANTES de encargarla.
        charge = {"provider": "replicate",
                  "label": f"lipsync {seconds:.0f}s "
                           f"({self.model.split('/')[-1]})",
                  "qty": round(seconds, 1), "unit": "s",
                  "usd": pricing.lipsync_cost_mid(seconds, self.model)}
        with contextlib.ExitStack() as stack:
            inputs = {img_key: stack.enter_context(open(image, "rb")),
                      aud_key: stack.enter_context(open(audio, "rb")),
                      **extras}
            # net_retries bajo: si falla, la escena degrada a imagen fija —
            # mejor caer rápido que retener la fase minutos por escena.
            run_and_download(self.client, self.model, inputs, out,
                             charge=charge, net_retries=2)
        return out
