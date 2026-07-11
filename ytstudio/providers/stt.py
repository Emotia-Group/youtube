"""Proveedores de voz-a-texto (transcripción de notas de voz y videos)."""
from __future__ import annotations

from pathlib import Path


class OpenAISTT:
    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        self.language = cfg.get("language", "es")

    def transcribe(self, audio: Path) -> str:
        with open(audio, "rb") as f:
            result = self.client.audio.transcriptions.create(
                model="whisper-1", file=f, language=self.language,
            )
        return result.text


class MockSTT:
    def __init__(self, cfg: dict):
        pass

    def transcribe(self, audio: Path) -> str:
        return ("Transcripción de ejemplo: quiero un video sobre una historia "
                "fascinante, contada en tono documental con un gancho fuerte.")
