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
        # Aspecto según el formato (Kling solo genera 16:9/9:16/1:1:
        # para 4:5 se pide 1:1 y el montaje lo recorta con cobertura)
        from ytstudio.catalog import aspect_for
        self.aspect = aspect_for(cfg, allowed=("16:9", "9:16", "1:1"))

    def generate(self, prompt: str, out: Path, image: Path | None = None,
                 seconds: float = 5.0) -> Path:
        import contextlib
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        # Kling genera clips de 5 o 10 s. Se pide el que mejor cubre la escena:
        # el montaje ajusta el resto con cámara lenta sutil (nunca repitiendo
        # el clip en bucle).
        duration = 10 if seconds > 7.5 else 5
        charge = {"provider": "replicate",
                  "label": f"clip de video {duration}s "
                           f"({self.model.split('/')[-1]})",
                  "qty": 1, "unit": "clip",
                  "usd": pricing.video_cost_mid(duration, self.model)}
        with contextlib.ExitStack() as stack:
            inputs: dict = {"prompt": prompt, "aspect_ratio": self.aspect,
                            "duration": duration}
            if image is not None:
                inputs["start_image"] = stack.enter_context(open(image, "rb"))
            # net_retries bajo: si falla, la escena degrada a imagen animada —
            # mejor caer rápido que retener la fase minutos por clip.
            run_and_download(self.client, self.model, inputs, out,
                             charge=charge, net_retries=2)
        return out
