"""Batería v0.42.1 — fixes de los hallazgos del log real (85fc2521):

1. Enumeraciones/anáforas YA NO se cortan (los 5 cortes malos de
   2-mansa-musa: «ni en América Latina, ni en Europa…», «tuvo la visión,
   tuvo la generosidad…», «luego las rutas comerciales…»).
2. Los redos REALES se siguen cortando (cobertura completa del intento).
3. Eco retórico de extensión protegido (pausa < 1.2 s).
4. _sniff_media_type: tipo real por bytes mágicos (el 400 del QA visión).
5. Troceo por tandas de _broll_for_fixed y del pase de dirección de arte
   (el «Unterminated string» del video de ~20 min).
6. _verify_factual honesto: si la visión falla, no afirma «todas respetan».
7. Pulido de transcripción reencuadrado (grabación del propio creador).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import sys
from pathlib import Path



FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def mk_words(spec):
    words, t = [], 0.0
    for text, gap in spec:
        words.append({"start": round(t, 3), "end": round(t + 0.25, 3),
                      "text": text})
        t += 0.25 + gap
    return words


def as_segments(words):
    return [{"start": words[0]["start"], "end": words[-1]["end"],
             "text": " ".join(w["text"] for w in words), "words": words}]


from ytstudio import narration_fix as nf

# ---------------------------------------------------------------------------
# T1 — LOS 5 CORTES MALOS DEL LOG: enumeraciones anafóricas intocables
# ---------------------------------------------------------------------------
words = mk_words([
    ("no", 0.02), ("en", 0.02), ("Estados", 0.02), ("Unidos,", 0.7),
    ("ni", 0.02), ("en", 0.02), ("América", 0.02), ("Latina,", 0.7),
    ("ni", 0.02), ("en", 0.02), ("Europa,", 0.8),
    ("ni", 0.02), ("en", 0.02), ("Asia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T1 enumeración «ni en X, ni en Y, ni en Z» intocable", not cuts,
      str([(c["text"], c["reason"]) for c in cuts]))

words = mk_words([
    ("tuvo", 0.02), ("la", 0.02), ("visión,", 1.9),
    ("tuvo", 0.02), ("la", 0.02), ("generosidad,", 1.9),
    ("tuvo", 0.02), ("la", 0.02), ("audacia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T1b anáfora «tuvo la X, tuvo la Y» intocable (aun con pausas de ~2s)",
      not cuts, str([(c["text"], c["reason"]) for c in cuts]))

words = mk_words([
    ("primero", 0.02), ("las", 0.02), ("aldeas,", 1.4),
    ("luego", 0.02), ("las", 0.02), ("rutas", 0.02), ("comerciales,", 1.4),
    ("luego", 0.02), ("las", 0.02), ("ciudades.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T1c enumeración «luego las…» intocable", not cuts,
      str([(c["text"], c["reason"]) for c in cuts]))

words = mk_words([
    ("no", 0.02), ("con", 0.02), ("violencia,", 0.9),
    ("no", 0.02), ("con", 0.02), ("amenazas,", 0.02),
    ("sino", 0.02), ("con", 0.02), ("oro.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T1d «no con violencia, no con amenazas» intocable", not cuts,
      str([(c["text"], c["reason"]) for c in cuts]))

# ---------------------------------------------------------------------------
# T2 — los REDOS reales se siguen cortando (cobertura completa)
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("registró", 0.02), ("veterinario", 2.0),
    ("El", 0.02), ("registro", 0.02), ("veterinario", 0.02),
    ("oficial", 0.02), ("es", 0.02), ("la", 0.02), ("evidencia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T2 redo truncado clásico se sigue cortando",
      len(cuts) == 1 and cuts[0]["start"] <= 0.01, str(cuts))

words = mk_words([
    ("El", 0.02), ("registró", 0.02), ("veterinario.", 2.0),
    ("El", 0.02), ("registro", 0.02), ("veterinario", 0.02),
    ("oficial", 0.02), ("es", 0.02), ("la", 0.02), ("evidencia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T2b redo con puntuación (pausa 2s ≥ 1.2) se sigue cortando",
      len(cuts) == 1 and cuts[0]["start"] <= 0.01, str(cuts))

words = mk_words([
    ("El", 0.02), ("pánico", 0.02), ("rural", 0.02), ("creció", 0.02),
    ("sin", 0.02), ("freno.", 1.0),
    ("El", 0.02), ("pánico", 0.02), ("rural", 0.02), ("creció", 0.02),
    ("sin", 0.02), ("freno.", 0.4), ("Nadie", 0.02), ("dormía.", 0.0),
])
cuts = nf.detect_sentence_restarts(words)
check("T2c frase completa repetida idéntica se sigue cortando",
      len(cuts) == 1 and cuts[0]["start"] <= 0.01, str(cuts))

# ---------------------------------------------------------------------------
# T3 — eco retórico de EXTENSIÓN protegido con pausa corta
# ---------------------------------------------------------------------------
words = mk_words([
    ("Nadie", 0.02), ("sabía", 0.02), ("su", 0.02), ("nombre.", 0.8),
    ("Nadie", 0.02), ("sabía", 0.02), ("su", 0.02), ("nombre", 0.02),
    ("hasta", 0.02), ("hoy.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
check("T3 eco retórico de extensión (pausa 0.8 < 1.2) intocable", not cuts,
      str([(c["text"], c["reason"]) for c in cuts]))

# ---------------------------------------------------------------------------
# T4 — tipo de imagen real por bytes mágicos (el 400 del QA con visión)
# ---------------------------------------------------------------------------
from ytstudio.providers.llm import _sniff_media_type

png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 20
webp = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8
check("T4 PNG con nombre .jpg → image/png (el caso del 400)",
      _sniff_media_type(png, "scene_003.jpg") == "image/png", "")
check("T4b JPEG real → image/jpeg",
      _sniff_media_type(jpg, "scene_003.jpg") == "image/jpeg", "")
check("T4c WEBP → image/webp",
      _sniff_media_type(webp, "x.jpg") == "image/webp", "")
check("T4d bytes desconocidos → por extensión",
      _sniff_media_type(b"????????????", "foto.png") == "image/png", "")

# ---------------------------------------------------------------------------
# T5 — troceo por tandas en scenes (el «Unterminated string»)
# ---------------------------------------------------------------------------
import re

from ytstudio.phases import scenes as sc


class PStub:
    def __init__(self):
        self.data = {}
        self.warnings = []

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.warnings.append(m)


class ChunkLLM:
    """Devuelve una escena por cada [id] que ve en el prompt; registra cada
    llamada (schema y tamaño) para verificar el troceo."""

    is_mock = False

    def __init__(self):
        self.calls = []

    def complete_json(self, system, prompt, *, schema=None, images=None,
                      max_tokens=16000, purpose=""):
        # En las tandas de dirección, el prompt trae además el ÍNDICE
        # COMPLETO del video: solo cuentan los ids de la tanda en sí.
        zone = prompt.split("ESCENAS DE ESTA TANDA")[-1]
        ids = [int(m) for m in re.findall(r"^\[(\d+)\]", zone, re.M)]
        props = set((schema or {}).get("properties", {}))
        self.calls.append({"purpose": purpose, "props": props,
                           "n_ids": len(ids), "max_tokens": max_tokens})
        if props == {"bible"}:
            return {"bible": {"era_setting": "imperio de Malí s. XIV",
                              "palette": "oro y ocre", "lighting": "dura",
                              "camera_language": "gran angular",
                              "texture_grade": "grano fino",
                              "motifs": ["oro", "arena"]}}
        return {"scenes": [
            {"id": i, "broll_prompt": f"P-{i}", "broll_type": "image",
             "animation": "zoom_in", "section": f"s{i}",
             "motion_risk": "baja"} for i in ids]}


# _broll_for_fixed: 95 escenas → 3 tandas de ≤40
scenes95 = [{"id": i + 1, "narration": f"narración de la escena {i + 1}",
             "broll_type": "image", "animation": "zoom_in",
             "section": "Narración"} for i in range(95)]
llm = ChunkLLM()
concept = {"visual_style": {"prompt_prefix": "STYLEPFX"}}
sc._broll_for_fixed(llm, concept, scenes95, "español", 0)
check("T5 _broll_for_fixed en 3 tandas (95 escenas)",
      len(llm.calls) == 3 and [c["n_ids"] for c in llm.calls] == [40, 40, 15],
      str([(c["purpose"], c["n_ids"]) for c in llm.calls]))
check("T5b cada escena recibió SU prompt (mapeo por tanda correcto)",
      all(s["broll_prompt"] == f"P-{s['id']}" for s in scenes95),
      str([(s["id"], s["broll_prompt"]) for s in scenes95[:3]]
          + [(s["id"], s["broll_prompt"]) for s in scenes95[-3:]]))

# con pocas escenas: UNA llamada, sin mención de tandas
scenes5 = [{"id": i + 1, "narration": f"escena {i + 1}",
            "broll_type": "image", "animation": "zoom_in",
            "section": "Narración"} for i in range(5)]
llm2 = ChunkLLM()
sc._broll_for_fixed(llm2, concept, scenes5, "español", 0)
check("T5c con 5 escenas: una sola llamada", len(llm2.calls) == 1, "")

# _art_direction_pass: 90 escenas → 1 llamada de biblia + 3 tandas
scenes90 = [{"id": i + 1, "narration": f"narración {i + 1}",
             "broll_prompt": f"orig-{i + 1}", "broll_type": "image",
             "animation": "zoom_in", "section": "Narración"}
            for i in range(90)]
llm3 = ChunkLLM()
p = PStub()
sc._art_direction_pass(llm3, p, scenes90, concept, "español")
bible_calls = [c for c in llm3.calls if c["props"] == {"bible"}]
scene_calls = [c for c in llm3.calls if c["props"] == {"scenes"}]
check("T5d dirección de arte: 1 biblia + 3 tandas (90 escenas)",
      len(bible_calls) == 1 and len(scene_calls) == 3
      and [c["n_ids"] for c in scene_calls] == [40, 40, 10],
      str([(c["purpose"], c["props"], c["n_ids"]) for c in llm3.calls]))
check("T5e la biblia quedó guardada",
      (p.get("art_direction") or {}).get("era_setting", "").startswith("imperio"),
      str(p.get("art_direction")))
check("T5f los 90 prompts se aplicaron por tandas",
      all(s["broll_prompt"] == f"P-{s['id']}" for s in scenes90), "")

# con pocas escenas: una sola llamada con el schema completo
llm4 = ChunkLLM()
p2 = PStub()
scenes6 = [dict(s) for s in scenes90[:6]]
sc._art_direction_pass(llm4, p2, scenes6, concept, "español")
check("T5g con 6 escenas: una sola llamada (bible+scenes)",
      len(llm4.calls) == 1 and llm4.calls[0]["props"] == {"bible", "scenes"},
      str([(c["props"]) for c in llm4.calls]))

# los schemas nuevos son válidos para salida estructurada
from ytstudio.providers.llm import check_schema

check_schema(sc._BIBLE_SCHEMA)
check_schema(sc._DIR_SCENES_SCHEMA)
check("T5h schemas de tandas válidos", True)

# ---------------------------------------------------------------------------
# T6 — llm.complete lanza error CLARO si la respuesta se corta (max_tokens)
# ---------------------------------------------------------------------------
import inspect

# v0.42.2: el corte por max_tokens ya no muere de inmediato — se reintenta con
# el techo ampliado (complete) y, si vuelve a cortarse, el error es claro. La
# detección vive ahora en _once; el mensaje accionable, en complete.
_llm_mod = sys.modules["ytstudio.providers.llm"]
src = (inspect.getsource(_llm_mod.ClaudeLLM.complete)
       + inspect.getsource(_llm_mod.ClaudeLLM._once))
check("T6 stop_reason max_tokens → error claro (no JSON críptico)",
      'stop_reason == "max_tokens"' in src and "tandas" in src, "")

# ---------------------------------------------------------------------------
# T7 — _verify_factual honesto cuando la visión falla
# ---------------------------------------------------------------------------
import tempfile

from PIL import Image

from ytstudio import progress
from ytstudio.phases import broll as br

tmp = Path(tempfile.mkdtemp(prefix="v0421_"))
Image.new("RGB", (64, 64), (10, 40, 120)).save(tmp / "scene_001.jpg")


class FailingLLM:
    is_mock = False

    def complete_json(self, *a, **k):
        raise RuntimeError("Error code: 400 - media type mismatch")


msgs = []
progress.set_sink(msgs.append)
p3 = PStub()
br._verify_factual(p3, FailingLLM(), {"providers": {"images": {}}},
                   [{"id": 1, "narration": "un valle", "broll_type": "image"}],
                   tmp, lambda *a: None, skip=set())
progress.set_sink(None)
check("T7 visión fallida → avisa del fallo",
      any("no se pudo completar" in w for w in p3.warnings), str(p3.warnings))
check("T7b y NO afirma «todas las imágenes respetan»",
      not any("respetan" in m for m in msgs), str(msgs))

# ---------------------------------------------------------------------------
# T8 — pulido de transcripción reencuadrado (grabación del propio creador)
# ---------------------------------------------------------------------------
from ytstudio.phases import ingest as ig

src8 = inspect.getsource(ig._polish_transcript)
check("T8 el prompt del pulido aclara que es la grabación del creador",
      "SU PROPIA grabación" in src8, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.42.1 completa: hallazgos del log real corregidos y "
      "verificados.")
import shutil
shutil.rmtree(tmp, ignore_errors=True)
