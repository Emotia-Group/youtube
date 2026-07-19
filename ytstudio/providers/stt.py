"""Proveedores de voz-a-texto (transcripción de notas de voz y videos).

Además de texto plano, exponen `transcribe_segments()` que devuelve segmentos
con marcas de tiempo — la base para alinear la narración del usuario con las
escenas del video.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.utils.media import probe_duration


def _restore_punctuation(seg_text: str, words: list[dict]) -> list[dict]:
    """Repone comas y puntos en las palabras con tiempo.

    La API de Whisper con timestamps por palabra devuelve cada palabra SIN
    puntuación (aunque el texto del segmento sí la trae) — al reconstruir el
    subtítulo desde las palabras (para tener el tiempo exacto) se perdían
    todas las comas y puntos. El texto del segmento conserva la puntuación y
    tiene las mismas palabras en el mismo orden, así que se emparejan por
    posición y se usa el token puntuado (conservando el tiempo real)."""
    tokens = seg_text.split()
    if len(tokens) != len(words):
        return words  # conteo distinto (caso raro): mejor no arriesgar el orden
    out = []
    for w, tok in zip(words, tokens):
        out.append({**w, "text": tok})
    return out


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
                # "word" da el tiempo de CADA palabra — es lo que permite
                # sincronizar subtítulos y rótulos con la voz real en vez de
                # estimar por proporción de caracteres.
                timestamp_granularities=["segment", "word"],
            )

        def get(o, k):
            return o[k] if isinstance(o, dict) else getattr(o, k)

        words_raw = getattr(result, "words", None) or []
        words = [{"start": float(get(w, "start")), "end": float(get(w, "end")),
                  "text": (get(w, "word") or "").strip()}
                 for w in words_raw if (get(w, "word") or "").strip()]
        words.sort(key=lambda w: w["start"])

        segments = getattr(result, "segments", None) or []
        seg_starts = [float(get(s, "start")) for s in segments]
        seg_bounds = seg_starts + [float(get(segments[-1], "end"))] if segments else []

        # Asignación ÚNICA de cada palabra a un segmento por bisección (no por
        # ventana ±0.05s): dos segmentos consecutivos pueden solaparse un poco
        # en sus tiempos, y una ventana por segmento dejaba la misma palabra en
        # AMBOS — la palabra aparecía duplicada en el subtítulo ("historia
        # historia"). Con bisección cada palabra cae en un único segmento.
        import bisect
        seg_words: list[list[dict]] = [[] for _ in segments]
        for w in words:
            if not seg_bounds:
                break
            idx = bisect.bisect_right(seg_starts, w["start"]) - 1
            idx = max(0, min(idx, len(segments) - 1))
            seg_words[idx].append(w)

        out = []
        for s, sw in zip(segments, seg_words):
            text = (get(s, "text") or "").strip()
            if not text:
                continue
            start, end = float(get(s, "start")), float(get(s, "end"))
            out.append({"start": start, "end": end, "text": text,
                        "words": _restore_punctuation(text, sw)})
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
            words_txt = s.split()
            wchars = sum(len(w) for w in words_txt) or 1
            words, wt = [], t
            for w in words_txt:
                wdur = seg_dur * len(w) / wchars
                words.append({"start": round(wt, 3), "end": round(wt + wdur, 3),
                             "text": w})
                wt += wdur
            segments.append({"start": round(t, 3), "end": round(t + seg_dur, 3),
                             "text": s, "words": words})
            t += seg_dur
        return segments
