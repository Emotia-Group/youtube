"""Proveedores de texto-a-voz. Todos devuelven la ruta del audio generado.

CADA PROVEEDOR NOMBRA SUS VOCES A SU MANERA, y eso causa un fallo que costó
una corrida entera al creador: ElevenLabs usa códigos como
«onwK4e9ZLuTAKqWW03F9», Cartesia exige un UUID, OpenAI nombres cortos
(«onyx») y Edge nombres largos («es-MX-JorgeNeural»). El programa guarda UNA
sola voz en la configuración, así que al cambiar de proveedor la voz del
anterior se queda puesta y el nuevo la rechaza — pero el rechazo llegaba en
la fase 5 de 11, después de gastar dinero y varios minutos.

Ahora cada proveedor comprueba que la voz configurada tenga SU formato: si no
lo tiene, usa la suya por defecto y lo avisa, en vez de tirar la corrida. Y
`ytstudio.catalog.tts_voice_problem()` lo detecta ANTES de empezar, cuando
corregirlo no cuesta nada.
"""
from __future__ import annotations

import os
from pathlib import Path

from ytstudio.utils.media import make_silence


def _pick_voice(cfg: dict, proveedor: str, por_defecto: str) -> str:
    """La voz configurada si encaja con el proveedor; si no, la de la casa.

    Nunca lanza: quedarse sin voz a mitad de una corrida es peor que usar la
    voz por defecto avisando."""
    from ytstudio.catalog import voice_matches_provider
    voz = (cfg.get("providers", {}).get("tts", {}).get("voice") or "").strip()
    if not voz:
        return por_defecto
    if voice_matches_provider(proveedor, voz):
        return voz
    try:
        from ytstudio.progress import notify
        notify(f"⚠ La voz «{voz}» no tiene el formato que usa {proveedor} "
               f"(seguramente quedó del proveedor anterior). Se usa la voz "
               f"por defecto. Cámbiala en Ajustes → Voz en off.")
    except Exception:
        pass
    return por_defecto


class ElevenLabsTTS:
    DEFAULT_VOICE = "onwK4e9ZLuTAKqWW03F9"  # "Daniel" — multilingüe

    def __init__(self, cfg: dict):
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        self.voice = _pick_voice(cfg, "elevenlabs", self.DEFAULT_VOICE)

    def synthesize(self, text: str, out: Path) -> Path:
        audio = self.client.text_to_speech.convert(
            voice_id=self.voice,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        with open(out, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        from ytstudio import usage
        # ElevenLabs cobra por plan de suscripción, no por llamada aislada —
        # se registran los caracteres reales sin costo en USD (ver nota en la UI).
        usage.record("elevenlabs", "voz (plan de suscripción)", len(text),
                    "caracteres", 0.0)
        return out


class CartesiaTTS:
    """Cartesia Sonic: voz neuronal de pago POR USO, un orden de magnitud más
    barata que ElevenLabs (~$11 frente a ~$120 por millón de caracteres). Para
    un canal que produce en volumen es la diferencia entre $54 y $5 al mes.

    Ventaja que no se ve en el precio: al cobrar por uso, su gasto SÍ entra en
    el libro y en el tope de presupuesto — con ElevenLabs, que cobra por plan,
    el gasto de voz queda invisible para el control de costos."""

    DEFAULT_VOICE = "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c"  # narrador neutro
    DEFAULT_MODEL = "sonic-2"

    def __init__(self, cfg: dict):
        self.api_key = os.environ["CARTESIA_API_KEY"]
        tcfg = cfg["providers"]["tts"]
        self.voice = _pick_voice(cfg, "cartesia", self.DEFAULT_VOICE)
        self.model = tcfg.get("model") or self.DEFAULT_MODEL
        # Cartesia necesita saber el idioma del texto (no lo deduce)
        self.language = str(cfg.get("language", "es"))[:2]

    def synthesize(self, text: str, out: Path) -> Path:
        import json
        import urllib.request

        from ytstudio import pricing, usage
        usd = pricing.tts_cost(len(text), "cartesia")
        usage.check_budget(usd, "un tramo de voz de Cartesia")
        body = json.dumps({
            "model_id": self.model,
            "transcript": text,
            "voice": {"mode": "id", "id": self.voice},
            "language": self.language,
            "output_format": {"container": "mp3", "sample_rate": 44100,
                              "bit_rate": 128000},
        }).encode()
        req = urllib.request.Request(
            "https://api.cartesia.ai/tts/bytes", data=body,
            headers={"X-API-Key": self.api_key,
                     "Cartesia-Version": "2024-06-10",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                audio = resp.read()
        except Exception as e:
            detail = ""
            body_err = getattr(e, "read", None)
            if callable(body_err):
                try:
                    detail = f" — {body_err().decode('utf-8', 'replace')[:300]}"
                except Exception:
                    pass
            raise RuntimeError(
                f"Cartesia no pudo sintetizar la voz ({e}){detail}. Revisa "
                "CARTESIA_API_KEY y que el identificador de voz exista en tu "
                "cuenta (providers.tts.voice).") from e
        out.write_bytes(audio)
        # El cobro ocurre al responder la API: se anota en cuanto hay audio.
        usage.record("cartesia", "voz TTS", len(text), "caracteres", usd)
        usage.add_spend(usd)
        return out


class OpenAITTS:
    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        self.voice = _pick_voice(cfg, "openai", "onyx")

    def synthesize(self, text: str, out: Path) -> Path:
        with self.client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=self.voice, input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(out)
        from ytstudio import pricing, usage
        usage.record("openai", "voz TTS", len(text), "caracteres",
                    pricing.tts_cost(len(text), "openai"))
        return out


class EdgeTTS:
    """TTS gratuito basado en las voces neuronales de Microsoft Edge."""

    def __init__(self, cfg: dict):
        self.voice = _pick_voice(cfg, "edge", "es-MX-JorgeNeural")

    def synthesize(self, text: str, out: Path) -> Path:
        import asyncio
        import edge_tts

        async def _run():
            await edge_tts.Communicate(text, self.voice).save(str(out))

        asyncio.run(_run())
        return out


class MockTTS:
    """Genera silencio con duración proporcional al texto (~2.6 palabras/s),
    para poder validar tiempos y montaje sin un TTS real."""

    WORDS_PER_SECOND = 2.6

    def __init__(self, cfg: dict):
        pass

    def synthesize(self, text: str, out: Path) -> Path:
        seconds = max(1.5, len(text.split()) / self.WORDS_PER_SECOND)
        return make_silence(out, seconds)
