"""Proveedores de voz-a-texto (transcripción de notas de voz y videos).

Además de texto plano, exponen `transcribe_segments()` que devuelve segmentos
con marcas de tiempo — la base para alinear la narración del usuario con las
escenas del video.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.utils.media import probe_duration


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

    def transcribe_segments(self, audio: Path) -> list[dict]:
        with open(audio, "rb") as f:
            result = self.client.audio.transcriptions.create(
                model="whisper-1", file=f, language=self.language,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = getattr(result, "segments", None) or []
        out = []
        for s in segments:
            get = (lambda k: s[k]) if isinstance(s, dict) else (lambda k: getattr(s, k))
            text = (get("text") or "").strip()
            if text:
                out.append({"start": float(get("start")),
                            "end": float(get("end")), "text": text})
        return out


class MockSTT:
    """Transcripción de ejemplo. `transcribe_segments` reparte un texto de
    muestra a lo largo de la duración real del audio, para poder validar toda
    la alineación audio↔escenas sin un STT real."""

    SAMPLE = ("Bienvenidos a este documental. Hoy vamos a explorar una historia "
              "fascinante que muy pocos conocen. Todo comenzó hace muchos años, "
              "cuando nadie imaginaba lo que estaba por suceder. Los protagonistas "
              "de esta historia se enfrentaron a enormes desafíos. Y contra todo "
              "pronóstico, lograron algo extraordinario. Esto es lo que realmente "
              "ocurrió, y por qué sigue siendo relevante hoy.")

    def __init__(self, cfg: dict):
        pass

    def transcribe(self, audio: Path) -> str:
        return self.SAMPLE

    def transcribe_segments(self, audio: Path) -> list[dict]:
        import re
        duration = probe_duration(audio)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", self.SAMPLE)
                     if s.strip()]
        total_chars = sum(len(s) for s in sentences) or 1
        segments, t = [], 0.0
        for s in sentences:
            seg_dur = duration * len(s) / total_chars
            segments.append({"start": round(t, 3),
                             "end": round(t + seg_dur, 3), "text": s})
            t += seg_dur
        return segments
