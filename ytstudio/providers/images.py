"""Proveedores de imágenes IA para B-roll y miniatura."""
from __future__ import annotations

import hashlib
from pathlib import Path


class OpenAIImages:
    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        self.size = cfg["providers"]["images"].get("size", "1792x1024")

    def generate(self, prompt: str, out: Path) -> Path:
        import base64
        result = self.client.images.generate(
            model="gpt-image-1", prompt=prompt, size=self.size, n=1,
        )
        out.write_bytes(base64.b64decode(result.data[0].b64_json))
        return out


class ReplicateImages:
    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        self.model = cfg["providers"]["images"].get(
            "model", "black-forest-labs/flux-1.1-pro")

    def generate(self, prompt: str, out: Path) -> Path:
        import urllib.request
        output = self.client.run(self.model, input={
            "prompt": prompt, "aspect_ratio": "16:9",
            "output_format": "jpg", "safety_tolerance": 2,
        })
        url = output[0] if isinstance(output, list) else output
        urllib.request.urlretrieve(str(url), out)
        return out


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
