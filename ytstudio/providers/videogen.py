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

    def generate(self, prompt: str, out: Path, image: Path | None = None) -> Path:
        import contextlib
        import urllib.request
        with contextlib.ExitStack() as stack:
            inputs: dict = {"prompt": prompt, "aspect_ratio": "16:9", "duration": 5}
            if image is not None:
                inputs["start_image"] = stack.enter_context(open(image, "rb"))
            output = self.client.run(self.model, input=inputs)
        url = output[0] if isinstance(output, list) else output
        urllib.request.urlretrieve(str(url), out)
        return out
