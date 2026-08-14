"""Proveedores de voz-a-texto (transcripción de notas de voz y videos).

Además de texto plano, exponen `transcribe_segments()` que devuelve segmentos
con marcas de tiempo — la base para alinear la narración del usuario con las
escenas del video.
"""
from __future__ import annotations

from pathlib import Path

from ytstudio.utils.media import probe_duration


def _core(s: str) -> str:
    """Núcleo alfanumérico de un token (sin signos): base para emparejar el
    token puntuado del segmento con la palabra cronometrada de Whisper."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFC", s or "")
    return "".join(re.findall(r"[^\W_]+", s, flags=re.UNICODE)).lower()


def _restore_punctuation(seg_text: str, words: list[dict]) -> list[dict]:
    """Repone comas y puntos en las palabras con tiempo.

    La API de Whisper con timestamps por palabra devuelve cada palabra SIN
    puntuación (aunque el texto del segmento sí la trae) — al reconstruir el
    subtítulo desde las palabras (para tener el tiempo exacto) se perdían
    todas las comas y puntos. El texto del segmento conserva la puntuación.

    Caso común: mismo número de tokens → emparejamiento por posición. Cuando
    el conteo NO cuadra (un número que Whisper parte, un guion suelto, unos
    puntos suspensivos como token aparte), ANTES se abandonaba y el segmento
    ENTERO perdía la puntuación (los signos que faltaban en los subtítulos
    quemados). Ahora se alinea por el núcleo alfanumérico de cada palabra:
    cada palabra cronometrada toma el token puntuado cuyo núcleo coincide, y
    la puntuación pegada a fronteras de token (comas, puntos) se conserva.
    Una palabra sin token que le corresponda conserva su texto (sin signos)
    en vez de arrastrar a todo el bloque."""
    tokens = seg_text.split()
    if not words or not tokens:
        return words
    if len(tokens) == len(words):
        return [{**w, "text": tok} for w, tok in zip(words, tokens)]
    out: list[dict] = []
    ti = 0
    for w in words:
        wc = _core(w.get("text", ""))
        j = ti
        while j < len(tokens) and wc and _core(tokens[j]) != wc:
            j += 1
        if wc and j < len(tokens):
            out.append({**w, "text": tokens[j]})
            ti = j + 1
        else:
            out.append({**w, "text": w.get("text", "")})  # sin par: intacta
    return out


class OpenAISTT:
    is_mock = False

    # Whisper API rechaza archivos de más de 25MB. Una narración de ~25 min
    # a 128kbps ya lo supera — y el creador va subiendo la duración de sus
    # videos. Por encima de este umbral se transcribe una COPIA mono a
    # 48kbps (misma duración → mismos timestamps; la voz no pierde
    # inteligibilidad): 24MB a 48kbps ≈ 69 minutos de narración.
    MAX_UPLOAD_BYTES = 24 * 1024 * 1024

    def __init__(self, cfg: dict):
        from openai import OpenAI
        self.client = OpenAI()
        self.language = cfg.get("language", "es")

    def _uploadable(self, audio: Path) -> tuple[Path, bool]:
        """(archivo a subir, hay_que_borrarlo). Si pesa de más, copia mono a
        48kbps; si NI ASÍ cabe (>69 min), error claro en vez del críptico
        413 de la API."""
        if audio.stat().st_size <= self.MAX_UPLOAD_BYTES:
            return audio, False
        from ytstudio.progress import notify
        from ytstudio.utils.media import run_ffmpeg
        small = audio.with_name(audio.stem + "_stt48k.mp3")
        notify(f"🎙 Tu narración pesa "
               f"{audio.stat().st_size / 1024 / 1024:.0f}MB (el límite de "
               "Whisper es 25MB): se transcribe una copia ligera mono a "
               "48kbps — mismos tiempos, misma calidad de transcripción.")
        run_ffmpeg(["-i", str(audio), "-ac", "1", "-b:a", "48k",
                    "-c:a", "libmp3lame", str(small)],
                   "copia ligera para transcripción")
        if small.stat().st_size > self.MAX_UPLOAD_BYTES:
            small.unlink(missing_ok=True)
            raise RuntimeError(
                "La narración supera ~69 minutos y no cabe en el límite de "
                "25MB de Whisper ni comprimida. Divide la grabación en dos "
                "archivos de voz (se transcriben y unen en orden) o recórtala.")
        return small, True

    def transcribe(self, audio: Path, hint: str = "") -> str:
        upload, temp = self._uploadable(audio)
        try:
            with open(upload, "rb") as f:
                kwargs = {"prompt": hint[:800]} if hint else {}
                result = self.client.audio.transcriptions.create(
                    model="whisper-1", file=f, language=self.language,
                    **kwargs,
                )
        finally:
            if temp:
                upload.unlink(missing_ok=True)
        from ytstudio import pricing, usage
        minutes = probe_duration(audio) / 60.0
        usage.record("openai", "transcripción de referencia (Whisper)", minutes,
                    "min", pricing.stt_cost(minutes, "openai"))
        return result.text

    def transcribe_segments(self, audio: Path, hint: str = "") -> list[dict]:
        upload, temp = self._uploadable(audio)
        try:
            with open(upload, "rb") as f:
                # `prompt` sesga el vocabulario de Whisper hacia los términos
                # del material del proyecto (nombres propios, tecnicismos):
                # sin él, «macacos rhesus» se transcribe como lo más parecido
                # y frecuente («masivos»). Máx ~224 tokens: se pasa un
                # extracto.
                kwargs = {"prompt": hint[:800]} if hint else {}
                result = self.client.audio.transcriptions.create(
                    model="whisper-1", file=f, language=self.language,
                    **kwargs,
                    response_format="verbose_json",
                    # "word" da el tiempo de CADA palabra — es lo que permite
                    # sincronizar subtítulos y rótulos con la voz real en vez
                    # de estimar por proporción de caracteres.
                    timestamp_granularities=["segment", "word"],
                )
        finally:
            if temp:
                upload.unlink(missing_ok=True)

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
        from ytstudio import pricing, usage
        minutes = probe_duration(audio) / 60.0
        usage.record("openai", "transcripción (Whisper)", minutes, "min",
                    pricing.stt_cost(minutes, "openai"))
        return out


class AssemblyAISTT:
    """AssemblyAI por lotes: $0.0025/min frente a $0.006 de Whisper.

    El motivo de fondo no es el precio (la transcripción es una partida
    marginal) sino la CALIDAD DE LAS MARCAS DE TIEMPO por palabra, que es de
    lo que vive todo el sistema de respiraciones, recorte de pausas y sincronía
    de subtítulos y rótulos (`utils/align.py`). AssemblyAI las da mejor y ya
    puntuadas, así que aquí no hace falta reponer comas como con Whisper.

    Sin límite de 25MB: el audio se sube entero, sin la copia ligera a 48kbps.
    """

    is_mock = False
    BASE = "https://api.assemblyai.com/v2"
    POLL_SECONDS = 3
    MAX_WAIT_SECONDS = 3600

    def __init__(self, cfg: dict):
        import os
        self.api_key = os.environ["ASSEMBLYAI_API_KEY"]
        self.language = str(cfg.get("language", "es"))[:2]

    def _headers(self, **extra) -> dict:
        return {"authorization": self.api_key, **extra}

    def _request(self, url: str, data=None, headers=None, method=None):
        import json
        import urllib.request
        req = urllib.request.Request(url, data=data,
                                     headers=headers or self._headers(),
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            detail = ""
            body = getattr(e, "read", None)
            if callable(body):
                try:
                    detail = f" — {body().decode('utf-8', 'replace')[:300]}"
                except Exception:
                    pass
            raise RuntimeError(
                f"AssemblyAI falló en {url.rsplit('/', 1)[-1]} ({e}){detail}. "
                "Revisa ASSEMBLYAI_API_KEY.") from e

    def _job(self, audio: Path, hint: str = "") -> str:
        """Sube el audio, encarga la transcripción y espera a que termine.
        Devuelve el id del trabajo ya completado."""
        import json
        import time

        from ytstudio.progress import notify
        up = self._request(f"{self.BASE}/upload", data=audio.read_bytes(),
                           headers=self._headers(
                               **{"content-type": "application/octet-stream"}))
        body: dict = {"audio_url": up["upload_url"],
                      "language_code": self.language,
                      "punctuate": True, "format_text": True}
        if hint:
            # Sesga el vocabulario hacia los términos del proyecto (nombres
            # propios, tecnicismos), igual que el `prompt` de Whisper.
            terms = [w for w in dict.fromkeys(hint.split()) if len(w) > 3]
            if terms:
                body["word_boost"] = terms[:200]
                body["boost_param"] = "high"
        job = self._request(f"{self.BASE}/transcript",
                            data=json.dumps(body).encode(),
                            headers=self._headers(
                                **{"content-type": "application/json"}))
        jid = job["id"]
        waited = 0
        while waited < self.MAX_WAIT_SECONDS:
            info = self._request(f"{self.BASE}/transcript/{jid}")
            status = info.get("status")
            if status == "completed":
                return jid
            if status == "error":
                raise RuntimeError(
                    f"AssemblyAI no pudo transcribir: {info.get('error')}")
            if waited and waited % 30 == 0:
                notify(f"🎙 AssemblyAI sigue transcribiendo… ({waited}s)")
            time.sleep(self.POLL_SECONDS)
            waited += self.POLL_SECONDS
        raise RuntimeError(
            "AssemblyAI no devolvió la transcripción en una hora. Reanuda la "
            "fase o cambia providers.stt.name a 'openai'.")

    def _charge(self, audio: Path, label: str) -> None:
        from ytstudio import pricing, usage
        minutes = probe_duration(audio) / 60.0
        usage.record("assemblyai", label, minutes, "min",
                     pricing.stt_cost(minutes, "assemblyai"))

    def transcribe(self, audio: Path, hint: str = "") -> str:
        jid = self._job(audio, hint)
        info = self._request(f"{self.BASE}/transcript/{jid}")
        self._charge(audio, "transcripción de referencia (AssemblyAI)")
        return info.get("text") or ""

    def transcribe_segments(self, audio: Path, hint: str = "") -> list[dict]:
        jid = self._job(audio, hint)
        # `sentences` da la frase COMPLETA con sus palabras cronometradas —
        # justo la unidad que necesitan los subtítulos y los rótulos.
        data = self._request(f"{self.BASE}/transcript/{jid}/sentences")
        out = []
        for s in data.get("sentences") or []:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            words = [{"start": float(w["start"]) / 1000.0,
                      "end": float(w["end"]) / 1000.0,
                      "text": (w.get("text") or "").strip()}
                     for w in (s.get("words") or [])
                     if (w.get("text") or "").strip()]
            out.append({"start": float(s["start"]) / 1000.0,
                        "end": float(s["end"]) / 1000.0,
                        "text": text, "words": words})
        self._charge(audio, "transcripción (AssemblyAI)")
        return out


class MockSTT:
    """Transcripción de ejemplo. `transcribe_segments` reparte un texto de
    muestra a lo largo de la duración real del audio, para poder validar toda
    la alineación audio↔escenas sin un STT real."""

    is_mock = True

    SAMPLE = ("Bienvenidos a este documental. Hoy vamos a explorar una historia "
              "fascinante que muy pocos conocen. Todo comenzó hace muchos años, "
              "cuando nadie imaginaba lo que estaba por suceder. Los protagonistas "
              "de esta historia se enfrentaron a enormes desafíos. Y contra todo "
              "pronóstico, lograron algo extraordinario. Esto es lo que realmente "
              "ocurrió, y por qué sigue siendo relevante hoy.")

    def __init__(self, cfg: dict):
        pass

    def transcribe(self, audio: Path, hint: str = "") -> str:
        return self.SAMPLE

    def transcribe_segments(self, audio: Path, hint: str = "") -> list[dict]:
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
