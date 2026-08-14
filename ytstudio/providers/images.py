"""Proveedores de imágenes IA para B-roll y miniatura."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ytstudio.providers.replicate_util import replicate_call


def _rate_limit_wait(exc: Exception, attempt: int) -> float | None:
    """Segundos que hay que esperar ante un límite de peticiones, o None si el
    error NO es un límite. OpenAI dice en el mensaje cuánto falta («Please try
    again in 12s»): se respeta ese número; si no lo trae, espera creciente."""
    import re
    msg = str(exc)
    code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None)
    if code != 429 and "rate_limit" not in msg and "429" not in msg:
        return None
    m = re.search(r"try again in ([\d.]+)\s*(ms|s)\b", msg, re.I)
    if m:
        secs = float(m.group(1)) / (1000 if m.group(2).lower() == "ms" else 1)
        return min(90.0, max(2.0, secs + 2.0))  # +2s de margen
    return min(90.0, 15.0 * attempt)


class OpenAIImages:
    # La familia gpt-image solo admite estos tamaños; se elige por orientación
    _VALID = {"1024x1024", "1536x1024", "1024x1536", "auto"}
    # gpt-image-1 SE APAGA el 23 de octubre de 2026: el modelo por defecto pasa
    # a ser gpt-image-2, que además renderiza mejor el texto dentro de la
    # imagen (que es justo para lo que usamos este proveedor) y sale más
    # barato en calidad media. Se puede fijar otro con providers.images.model,
    # pero solo valen modelos de OpenAI: un slug de Replicate se ignora.
    MODEL = "gpt-image-2"
    _VALID_QUALITY = {"low", "medium", "high", "auto"}
    RATE_RETRIES = 6          # reintentos ante límite de peticiones
    # Valores por defecto A NIVEL DE CLASE: el proveedor sigue siendo usable
    # aunque se construya sin pasar por __init__ (así lo hacen las baterías de
    # pruebas, que sustituyen el SDK y no tienen clave de API).
    model = MODEL
    quality = "medium"

    def __init__(self, cfg: dict):
        from openai import OpenAI
        from ytstudio import pricing
        self.client = OpenAI()
        icfg = cfg["providers"]["images"]
        self.model = pricing.effective_image_model(
            "openai", str(icfg.get("model", "")))
        # La CALIDAD manda el precio en gpt-image-2 mucho más que el tamaño
        # (de medio centavo a ~$0.21 por imagen). 'medium' es el punto donde
        # el texto ya sale limpio sin pagar el máximo.
        q = str(icfg.get("quality", "medium")).lower()
        self.quality = q if q in self._VALID_QUALITY else "medium"
        want = str(icfg.get("size", "")).lower()
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
        import time

        from ytstudio import pricing, usage
        from ytstudio.progress import notify
        usd = pricing.img_cost_mid("openai", self.model)
        usage.check_budget(usd, "una imagen de OpenAI")

        # LÍMITE DE PETICIONES: gpt-image-1 admite MUY pocas imágenes por
        # minuto (5 en cuentas nuevas). Un 429 es TRANSITORIO — la propia API
        # dice cuántos segundos faltan — y antes tumbaba la fase entera
        # dejando pagadas las imágenes ya generadas (caso real del creador:
        # 8 imágenes hechas y el proyecto muerto).
        last: Exception | None = None
        for attempt in range(1, self.RATE_RETRIES + 1):
            try:
                result = self.client.images.generate(
                    model=self.model, prompt=prompt, size=self.size, n=1,
                    quality=self.quality,
                )
                break
            except Exception as e:
                wait = _rate_limit_wait(e, attempt)
                if wait is None:
                    raise
                last = e
                if attempt == self.RATE_RETRIES:
                    raise RuntimeError(
                        "OpenAI está limitando las imágenes de este proyecto "
                        f"({self.model}) y no cedió tras {self.RATE_RETRIES} "
                        "esperas. Las imágenes ya generadas se conservan: "
                        "reanuda con «Rehacer desde Imágenes» dentro de un "
                        "rato, baja performance.parallel_images, o sube el "
                        "límite de tu cuenta en platform.openai.com. "
                        f"({e})") from e
                notify(f"⏳ OpenAI limita las imágenes por minuto; espero "
                       f"{wait:.0f}s y reintento "
                       f"({attempt}/{self.RATE_RETRIES - 1})…")
                time.sleep(wait)
        # El cobro ocurre al responder la API: se anota AQUÍ, antes de tocar
        # el disco, para que ningún fallo posterior deje gasto invisible.
        usage.record("openai", f"imagen ({self.model})", 1, "img", usd)
        usage.add_spend(usd)
        out.write_bytes(base64.b64decode(result.data[0].b64_json))
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
        # Aspecto según el formato del proyecto (16:9, 9:16, 1:1, 4:5…)
        from ytstudio.catalog import aspect_for
        self.aspect = aspect_for(cfg)

    def generate(self, prompt: str, out: Path) -> Path:
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        charge = {"provider": "replicate",
                  "label": f"imagen ({self.model.split('/')[-1]})",
                  "qty": 1, "unit": "img",
                  "usd": pricing.img_cost_mid("replicate", self.model)}
        run_and_download(self.client, self.model, {
            "prompt": prompt, "aspect_ratio": self.aspect,
            "output_format": "jpg", "safety_tolerance": self.safety,
        }, out, charge=charge)
        return out


class ReplicateUpscale:
    """ESCALADO: sube la resolución de una imagen YA generada.

    Es la pieza del MODO HÍBRIDO, la ruta de ahorro más grande del programa:
    generar el B-roll con un modelo barato (FLUX schnell, ~$0.003) y subirlo
    después a resolución de entrega (~$0.002) cuesta una fracción de generar
    con FLUX 1.1 Pro (~$0.045) — del orden de $0.50 contra $4.50 en un
    documental de 100 escenas.

    Lo que el escalado NO hace es inventar la microtextura y el detalle de
    iluminación que distinguen a un modelo caro: recupera resolución, no
    calidad de origen. Por eso el modo híbrido se aplica al B-roll de relleno
    y el config permite dejar las escenas clave en el modelo bueno.

    Si el escalado falla, la imagen ORIGINAL se conserva y el video sigue
    adelante: nunca es motivo para tumbar una fase ya pagada.
    """

    def __init__(self, cfg: dict):
        import replicate
        self.client = replicate
        icfg = cfg.get("providers", {}).get("images", {}) or {}
        self.model = icfg.get("upscale_model", "nightmareai/real-esrgan")
        self.target_w = int(cfg.get("video", {}).get("width", 1920))

    def _scale_for(self, img: Path) -> int:
        """Factor entero mínimo que alcanza el ancho del video (2, 3 o 4), o 0
        si la imagen YA da la talla. Pedir 4x sobre una imagen que casi cabe es
        pagar y esperar de más; escalar una que ya cabe es tirar el dinero."""
        try:
            from PIL import Image
            with Image.open(img) as im:
                w = im.width
        except Exception:
            return 0        # sin poder medirla, no se arriesga un gasto
        if w <= 0 or w >= self.target_w:
            return 0
        import math
        return max(2, min(4, math.ceil(self.target_w / w)))

    def upscale(self, img: Path) -> Path:
        """Escala la imagen EN SU SITIO. Devuelve siempre una ruta usable:
        la escalada si salió bien, la original si no. Las imágenes que ya
        llegan a la resolución del video se dejan intactas y NO se cobran —
        eso incluye los respaldos locales y el B-roll propio del creador."""
        from ytstudio import pricing
        from ytstudio.progress import notify
        from ytstudio.providers.replicate_util import run_and_download
        scale = self._scale_for(img)
        if not scale:
            return img
        big = img.with_name(img.stem + "_up" + img.suffix)
        charge = {"provider": "replicate",
                  "label": f"escalado x{scale} ({self.model.split('/')[-1]})",
                  "qty": 1, "unit": "img",
                  "usd": pricing.upscale_cost_mid(self.model)}
        try:
            with open(img, "rb") as f:
                # net_retries bajo: si el escalado no sale, la imagen original
                # ya sirve — no merece la pena retener la fase por ella.
                run_and_download(self.client, self.model,
                                 {"image": f, "scale": scale},
                                 big, charge=charge, net_retries=2)
        except Exception as e:
            notify(f"⚠ No se pudo escalar {img.name} ({e}); se conserva la "
                   "imagen original.")
            big.unlink(missing_ok=True)
            return img
        if not big.exists() or big.stat().st_size == 0:
            big.unlink(missing_ok=True)
            return img
        big.replace(img)
        return img


def get_upscaler(cfg: dict):
    """Escalador, o None si está apagado o falta el token de Replicate."""
    import os
    icfg = cfg.get("providers", {}).get("images", {}) or {}
    if not icfg.get("upscale"):
        return None
    from ytstudio.progress import notify
    if not os.environ.get("REPLICATE_API_TOKEN"):
        notify("⚠ El escalado está activado pero falta REPLICATE_API_TOKEN: "
               "las imágenes se usan a su resolución original.")
        return None
    try:
        return ReplicateUpscale(cfg)
    except Exception as e:
        # El escalado es una MEJORA opcional (típico: falta `pip install
        # replicate`). Sin él el video sale igual, solo que a la resolución
        # de origen — nunca es motivo para tumbar la fase de imágenes.
        notify(f"⚠ El escalado no se pudo preparar ({e}): las imágenes se "
               "usan a su resolución original.")
        return None


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
        from ytstudio.catalog import aspect_for
        self.aspect = aspect_for(cfg)

    def generate_with_refs(self, prompt: str, refs: list[Path],
                           out: Path) -> Path:
        import contextlib
        from ytstudio import pricing
        from ytstudio.providers.replicate_util import run_and_download
        key, is_list = _REF_INPUTS.get(self.model, ("image_input", True))
        charge = {"provider": "replicate",
                  "label": f"imagen con personaje "
                           f"({self.model.split('/')[-1]})",
                  "qty": 1, "unit": "img",
                  "usd": pricing.img_cost_mid("replicate", self.model)}
        with contextlib.ExitStack() as stack:
            files = [stack.enter_context(open(p, "rb")) for p in refs]
            inputs: dict = {"prompt": prompt,
                            key: files if is_list else files[0],
                            "aspect_ratio": self.aspect}
            if "nano-banana" in self.model:
                inputs["output_format"] = "jpg"
            run_and_download(self.client, self.model, inputs, out,
                             charge=charge)
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
