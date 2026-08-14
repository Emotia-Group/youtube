"""Video generativo por escena (opcional). Para videos largos lo habitual es
B-roll en imagen con animación Ken Burns; el video IA se reserva para escenas
clave por su costo (config: providers.videogen.max_scenes)."""
from __future__ import annotations

from pathlib import Path

# Cada familia de modelos nombra distinto el fotograma inicial y admite
# duraciones distintas. Kling trabaja en clips de 5 o 10 s; Veo, de 4, 6 u 8.
# (clave de la imagen inicial, duraciones admitidas)
_VIDEO_SPECS = {
    "google/veo-3.1": ("image", (4, 6, 8)),
    "google/veo-3.1-fast": ("image", (4, 6, 8)),
    "google/veo-3.1-lite": ("image", (4, 6, 8)),
}
_DEFAULT_SPEC = ("start_image", (5, 10))


def clip_duration_for(model: str, seconds: float) -> int:
    """Duración real del clip que se pedirá a ese modelo para cubrir una
    escena de `seconds`. La usan el proveedor y la estimación previa, para que
    el tope de gasto cuente los mismos segundos que se van a pagar."""
    durations = _VIDEO_SPECS.get(model, _DEFAULT_SPEC)[1]
    longer = [d for d in durations if d >= seconds - 0.5]
    return min(longer) if longer else max(durations)


class ReplicateVideo:
    def __init__(self, cfg: dict):
        import replicate
        from ytstudio import pricing
        self.client = replicate
        self.model = cfg["providers"]["videogen"].get(
            "model", "kwaivgi/kling-v1.6-standard")
        # Aspecto según el formato (Kling solo genera 16:9/9:16/1:1:
        # para 4:5 se pide 1:1 y el montaje lo recorta con cobertura)
        from ytstudio.catalog import aspect_for
        self.aspect = aspect_for(cfg, allowed=("16:9", "9:16", "1:1"))
        self.image_key, self.durations = _VIDEO_SPECS.get(
            self.model, _DEFAULT_SPEC)
        # VEO 3.1 es el único que devuelve el clip CON SU PROPIO SONIDO
        # (ambiente sincronizado con lo que se ve). Se conserva en un archivo
        # aparte junto al clip: el montaje sigue usando el video mudo.
        self.native_audio = pricing.has_native_audio(self.model)

    def _duration_for(self, seconds: float) -> int:
        """La duración admitida que mejor cubre la escena. Se prefiere no
        quedarse corto: el montaje ajusta el sobrante con cámara lenta sutil,
        pero un clip corto obligaría a repetirlo en bucle."""
        return clip_duration_for(self.model, seconds)

    def _extract_audio(self, clip: Path) -> Path | None:
        """Separa la pista nativa del clip a un archivo propio. Devuelve None
        si el clip llegó mudo (o si ffmpeg no encuentra pista de audio)."""
        from ytstudio.utils.media import run_ffmpeg
        out = clip.with_name(clip.stem + "_amb.m4a")
        try:
            run_ffmpeg(["-i", str(clip), "-vn", "-acodec", "aac", "-b:a",
                        "128k", str(out)], f"audio nativo de {clip.name}",
                       timeout=180)
        except Exception:
            out.unlink(missing_ok=True)
            return None
        if not out.exists() or out.stat().st_size == 0:
            out.unlink(missing_ok=True)
            return None
        return out

    def generate(self, prompt: str, out: Path, image: Path | None = None,
                 seconds: float = 5.0) -> Path:
        import contextlib
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        duration = self._duration_for(seconds)
        charge = {"provider": "replicate",
                  "label": f"clip de video {duration}s "
                           f"({self.model.split('/')[-1]})",
                  "qty": 1, "unit": "clip",
                  "usd": pricing.video_cost_mid(duration, self.model)}
        with contextlib.ExitStack() as stack:
            inputs: dict = {"prompt": prompt, "aspect_ratio": self.aspect,
                            "duration": duration}
            if image is not None:
                inputs[self.image_key] = stack.enter_context(open(image, "rb"))
            # net_retries bajo: si falla, la escena degrada a imagen animada —
            # mejor caer rápido que retener la fase minutos por clip.
            run_and_download(self.client, self.model, inputs, out,
                             charge=charge, net_retries=2)
        if self.native_audio:
            self._extract_audio(out)
        return out
