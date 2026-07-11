"""Proveedores de texto-a-voz. Todos devuelven la ruta del audio generado."""
from __future__ import annotations

import os
from pathlib import Path

from ytstudio.utils.media import make_silence


class ElevenLabsTTS:
    DEFAULT_VOICE = "onwK4e9ZLuTAKqWW03F9"  # "Daniel" — multilingüe

    def __init__(self, cfg: dict):
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        self.voice = cfg["providers"]["tts"].get("voice") or self.DEFAULT_VOICE

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
        return out


class OpenAITTS:
    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        self.voice = cfg["providers"]["tts"].get("voice") or "onyx"

    def synthesize(self, text: str, out: Path) -> Path:
        with self.client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice=self.voice, input=text,
            response_format="mp3",
        ) as response:
            response.stream_to_file(out)
        return out


class EdgeTTS:
    """TTS gratuito basado en las voces neuronales de Microsoft Edge."""

    def __init__(self, cfg: dict):
        self.voice = cfg["providers"]["tts"].get("voice") or "es-MX-JorgeNeural"

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
