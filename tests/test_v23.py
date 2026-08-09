"""Batería v23: duplicados de Whisper, puntuación y cola final.

T1  _restore_punctuation repone comas/puntos conservando el tiempo real.
T2  transcribe_segments: una palabra en el solape de dos segmentos cae en
    UNO SOLO (antes quedaba duplicada -> "historia historia" en subtítulos).
T3  flatten_words descarta duplicados que se solapan en el tiempo (red de
    seguridad para proyectos ya guardados con el bug viejo).
T4  outro/end_fade: el fundido de cierre sigue sin tocar la voz con los
    nuevos valores por defecto (outro >= end_fade).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys



from ytstudio.providers.stt import OpenAISTT, _restore_punctuation
from ytstudio.utils.align import flatten_words

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 _restore_punctuation")
words = [{"start": 0.0, "end": 0.3, "text": "hoy"},
         {"start": 0.3, "end": 0.6, "text": "vamos"},
         {"start": 0.6, "end": 0.9, "text": "a"},
         {"start": 0.9, "end": 1.4, "text": "explorar"}]
restored = _restore_punctuation("Hoy, vamos a explorar.", words)
check("conserva tiempos", [w["start"] for w in restored] == [w["start"] for w in words])
check("repone la coma", restored[0]["text"] == "Hoy,")
check("repone el punto final", restored[-1]["text"] == "explorar.")
# v0.24.3: conteo distinto ya NO borra la puntuación de todo el bloque; se
# alinea por núcleo alfanumérico y cada palabra cronometrada toma su token.
mismatched = _restore_punctuation("Hoy, vamos a explorar muchísimo.", words)  # 5 tokens vs 4 words
check("conteo distinto: repone la coma por alineación de núcleo",
      mismatched[0]["text"] == "Hoy,")
check("conteo distinto: no se pierde ninguna palabra cronometrada",
      len(mismatched) == len(words))

print("T2 transcribe_segments: sin duplicados en el solape de segmentos")


from types import SimpleNamespace


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    class _Audio:
        def __init__(self, outer):
            self._outer = outer

        class _Transcriptions:
            def __init__(self, outer):
                self._outer = outer

            def create(self, **kwargs):
                return self._outer._payload

        @property
        def transcriptions(self):
            return self._Transcriptions(self._outer)

    @property
    def audio(self):
        return self._Audio(self)


# Segmentos con SOLAPE deliberado (como puede devolver Whisper): seg A
# termina en 5.00, seg B empieza en 4.98. La palabra "historia" arranca en
# 4.99 -> caía dentro de la ventana ±0.05 de AMBOS segmentos (bug viejo).
# El SDK real devuelve objetos (atributos), no dicts: se simula igual.
payload = SimpleNamespace(
    words=[
        SimpleNamespace(word="Esta", start=4.50, end=4.75),
        SimpleNamespace(word="es", start=4.75, end=4.90),
        SimpleNamespace(word="historia", start=4.99, end=5.35),
        SimpleNamespace(word="real", start=5.35, end=5.60),
    ],
    segments=[
        SimpleNamespace(start=4.20, end=5.00, text="Esta es historia"),
        SimpleNamespace(start=4.98, end=6.00, text="historia real."),
    ],
)
stt = OpenAISTT.__new__(OpenAISTT)  # evita __init__ (no crea cliente OpenAI real)
stt.client = _FakeClient(payload)
stt.language = "es"
import ytstudio.providers.stt as sttmod
orig_open = open
# transcribe_segments abre el archivo de audio; usamos un WAV mínimo real.
import subprocess
import tempfile
from pathlib import Path
tmp_wav = Path(tempfile.mkdtemp()) / "a.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=8000:cl=mono", "-t", "0.2", str(tmp_wav)], check=True)

segments = stt.transcribe_segments(tmp_wav)
all_words = flatten_words(segments)
texts = [w["text"] for w in all_words]
check("«historia» aparece UNA sola vez en total", texts.count("historia") + texts.count("historia,") == 1,
      str(texts))
check("cada segmento tiene sus propias palabras (sin repetir)",
      len(segments[0]["words"]) + len(segments[1]["words"]) == len(payload.words),
      f"{[len(s['words']) for s in segments]}")

print("T3 flatten_words descarta solapes (datos ya guardados con el bug viejo)")
legacy_segments = [
    {"words": [{"start": 1.0, "end": 1.3, "text": "hola"},
              {"start": 1.3, "end": 1.6, "text": "mundo"}]},
    {"words": [{"start": 1.3, "end": 1.6, "text": "mundo"},  # duplicado exacto
              {"start": 1.6, "end": 1.9, "text": "real"}]},
]
flat = flatten_words(legacy_segments)
check("descarta el duplicado solapado", [w["text"] for w in flat] == ["hola", "mundo", "real"],
      str([w["text"] for w in flat]))

print("T4 outro/end_fade no tocan la voz")
import yaml
cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
outro = cfg["audio"]["outro_seconds"]
end_fade = cfg["audio"]["end_fade"]
check("el fundido cabe dentro de la cola (nunca invade la voz)", end_fade <= outro,
      f"outro={outro} end_fade={end_fade}")
check("la cola se acortó frente a v22 (menos espacio vacío)", outro < 3.5 and end_fade < 3.0,
      f"outro={outro} end_fade={end_fade}")

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
