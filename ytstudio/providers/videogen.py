"""Video generativo por escena (opcional). Para videos largos lo habitual es
B-roll en imagen con animación Ken Burns; el video IA se reserva para escenas
clave por su costo (config: providers.videogen.max_scenes)."""
from __future__ import annotations

from pathlib import Path


class ReplicateVideo:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        self.model = cfg["providers"]["videogen"].get(
            "model", "kwaivgi/kling-v1.6-standard")

    def generate(self, prompt: str, out: Path, image: Path | None = None,
                 seconds: float = 5.0) -> Path:
        import contextlib
        import urllib.request
        from ytstudio.providers.replicate_util import replicate_call
        # Kling genera clips de 5 o 10 s. Se pide el que mejor cubre la escena:
        # el montaje ajusta el resto con cámara lenta sutil (nunca repitiendo
        # el clip en bucle).
        duration = 10 if seconds > 7.5 else 5
        with contextlib.ExitStack() as stack:
            inputs: dict = {"prompt": prompt, "aspect_ratio": "16:9",
                            "duration": duration}
            if image is not None:
                inputs["start_image"] = stack.enter_context(open(image, "rb"))
            output = replicate_call(self.client, self.model, inputs)
        url = output[0] if isinstance(output, list) else output
        urllib.request.urlretrieve(str(url), out)
        from ytstudio import pricing, usage
        usage.record("replicate", f"clip de video {duration}s", 1, "clip",
                    pricing.video_cost_mid(duration))
        return out
