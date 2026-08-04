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
        # Aspecto según el formato del proyecto (16:9 largo · 9:16 vertical)
        v = cfg.get("video", {})
        self.aspect = ("9:16" if int(v.get("height", 1080)) > int(v.get("width", 1920))
                       else "16:9")

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
