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
        self.model = lcfg.get("model", "zsxkib/sonic")

    def generate(self, image: Path, audio: Path, out: Path,
                 seconds: float) -> Path:
        import contextlib
        import urllib.request
        from ytstudio.providers.replicate_util import replicate_call
        img_key, aud_key, extras = _MODEL_INPUTS.get(
            self.model, ("image", "audio", {}))
        with contextlib.ExitStack() as stack:
            inputs = {img_key: stack.enter_context(open(image, "rb")),
                      aud_key: stack.enter_context(open(audio, "rb")),
                      **extras}
            output = replicate_call(self.client, self.model, inputs)
        url = output[0] if isinstance(output, list) else output
        urllib.request.urlretrieve(str(url), out)
        from ytstudio import pricing, usage
        usage.record("replicate",
                     f"lipsync {seconds:.0f}s ({self.model.split('/')[-1]})",
                     round(seconds, 1), "s",
                     pricing.lipsync_cost_mid(seconds, self.model))
        return out
