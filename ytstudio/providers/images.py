"""Proveedores de imágenes IA para B-roll y miniatura."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ytstudio.providers.replicate_util import replicate_call


class OpenAIImages:
    # gpt-image-1 solo admite estos tamaños; se elige por orientación del video
    _VALID = {"1024x1024", "1536x1024", "1024x1536", "auto"}

    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        want = str(cfg["providers"]["images"].get("size", "")).lower()
        self.size = self._normalize(want, cfg)

    @staticmethod
    def _normalize(want: str, cfg: dict) -> str:
        if want in OpenAIImages._VALID:
            return want
        # Traducir cualquier tamaño (ej. 1792x1024 de DALL·E 3) al de gpt-image-1
        # según la orientación del video configurado.
        w = cfg.get("video", {}).get("width", 1920)
        h = cfg.get("video", {}).get("height", 1080)
        if "x" in want:  # respetar la orientación pedida si la trae el tamaño
            try:
                w, h = (int(x) for x in want.split("x"))
            except ValueError:
                pass
        ratio = w / h if h else 1.78
        if ratio > 1.2:
            return "1536x1024"   # horizontal (16:9)
        if ratio < 0.83:
            return "1024x1536"   # vertical (9:16, shorts)
        return "1024x1024"       # cuadrado

    def generate(self, prompt: str, out: Path) -> Path:
        import base64
        result = self.client.images.generate(
            model="gpt-image-1", prompt=prompt, size=self.size, n=1,
        )
        out.write_bytes(base64.b64decode(result.data[0].b64_json))
        from ytstudio import pricing, usage
        usage.record("openai", "imagen", 1, "img", pricing.img_cost_mid("openai"))
        return out


class ReplicateImages:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        icfg = cfg["providers"]["images"]
        self.model = icfg.get("model", "black-forest-labs/flux-1.1-pro")
        # FLUX permite safety_tolerance 1 (estricto) a 6 (permisivo). El 2 por
        # defecto marca como NSFW mucho contenido histórico/bélico legítimo
        # (batallas, documentales); 6 evita esos falsos positivos.
        self.safety = int(icfg.get("safety_tolerance", 6))
        # Aspecto según el formato del proyecto (16:9 largo · 9:16 Short/Reel)
        v = cfg.get("video", {})
        self.aspect = ("9:16" if int(v.get("height", 1080)) > int(v.get("width", 1920))
                       else "16:9")

    def generate(self, prompt: str, out: Path) -> Path:
        from ytstudio.providers.replicate_util import download_with_retry
        output = replicate_call(self.client, self.model, {
            "prompt": prompt, "aspect_ratio": self.aspect,
            "output_format": "jpg", "safety_tolerance": self.safety,
        })
        url = output[0] if isinstance(output, list) else output
        download_with_retry(str(url), out)
        from ytstudio import pricing, usage
        usage.record("replicate", f"imagen ({self.model.split('/')[-1]})", 1,
                     "img", pricing.img_cost_mid("replicate", self.model))
        return out


# Modelos de CONSISTENCIA DE IDENTIDAD (escenas con personajes del elenco):
# generan la imagen guiándose por las fotos de referencia del personaje.
# Cada modelo espera las referencias con un nombre de input distinto.
_REF_INPUTS = {
    "google/nano-banana": ("image_input", True),      # lista de imágenes
    "bytedance/seedream-4": ("image_input", True),
    "black-forest-labs/flux-kontext-pro": ("input_image", False),  # una sola
    "black-forest-labs/flux-kontext-max": ("input_image", False),
}


class ReplicateRefImages:
    """Generación con referencias de personaje vía Replicate."""

    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        icfg = cfg.get("providers", {}).get("images", {}) or {}
        self.model = icfg.get("ref_model", "google/nano-banana")
        v = cfg.get("video", {})
        self.aspect = ("9:16" if int(v.get("height", 1080)) > int(v.get("width", 1920))
                       else "16:9")

    def generate_with_refs(self, prompt: str, refs: list[Path],
                           out: Path) -> Path:
        import contextlib
        from ytstudio.providers.replicate_util import download_with_retry
        key, is_list = _REF_INPUTS.get(self.model, ("image_input", True))
        with contextlib.ExitStack() as stack:
            files = [stack.enter_context(open(p, "rb")) for p in refs]
            inputs: dict = {"prompt": prompt,
                            key: files if is_list else files[0],
                            "aspect_ratio": self.aspect}
            if "nano-banana" in self.model:
                inputs["output_format"] = "jpg"
            output = replicate_call(self.client, self.model, inputs)
        url = output[0] if isinstance(output, list) else output
        download_with_retry(str(url), out)
        from ytstudio import pricing, usage
        usage.record("replicate",
                     f"imagen con personaje ({self.model.split('/')[-1]})",
                     1, "img", pricing.img_cost_mid("replicate", self.model))
        return out


def get_ref_images(cfg: dict):
    """Generador con referencias, o None (sin token): las escenas con
    personaje caen al generador normal (sin identidad fija) con aviso."""
    import os
    if not os.environ.get("REPLICATE_API_TOKEN"):
        return None
    return ReplicateRefImages(cfg)


class MockImages:
    """Tarjetas placeholder (degradado + texto del prompt) generadas con PIL.
    Permiten previsualizar el montaje completo sin generar imágenes reales."""

    def __init__(self, cfg: dict):
        self.width = cfg["video"]["width"]
        self.height = cfg["video"]["height"]

    def generate(self, prompt: str, out: Path) -> Path:
        from PIL import Image, ImageDraw, ImageFont

        # Colores deterministas derivados del prompt
        h = hashlib.md5(prompt.encode()).digest()
        top = (40 + h[0] % 80, 40 + h[1] % 80, 60 + h[2] % 120)
        bottom = (10 + h[3] % 40, 10 + h[4] % 40, 20 + h[5] % 60)

        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        for y in range(self.height):
            t = y / self.height
            color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
            draw.line([(0, y), (self.width, y)], fill=color)

        from ytstudio.utils.media import find_font
        font_path = find_font(bold=True)
        font = (ImageFont.truetype(font_path, 44) if font_path
                else ImageFont.load_default(size=44))
        text = "[B-ROLL] " + (prompt[:90] + "…" if len(prompt) > 90 else prompt)
        draw.text((60, self.height // 2 - 30), text, fill=(235, 235, 235), font=font)
        img.save(out, quality=90)
        return out
