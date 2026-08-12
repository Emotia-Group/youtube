"""Batería v0.42.0 — debug general (7 frentes del proyecto 2-chupacabras).

Ejercita CÓDIGO REAL:
- narration_fix: conectores intocables, guardas de empalme, redos de frase
  con puntuación (el error que v0.40.0 dejó pasar), revisión IA solo-alta.
- ingest: pulido de transcripción por contexto (caso «monos masivos»).
- stt: parámetro `hint` (sesgo de vocabulario Whisper).
- scenes: image_text en schema/reglas/normalización + reglas de cantidad.
- broll: escalera con plano atmosférico seguro y vecino desenfocado (ffmpeg/
  PIL reales, run() completo con proveedores falsos), QA factual con visión
  (regeneración + firma de caché) y énfasis tipográfico sin OpenAI.
- music: actos por arco de intensidad + banda sonora multi-pista REAL con
  crossfades (ffmpeg, verificación espectral del cambio de pista).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path



FAILURES = []


def check(name, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


# ---------------------------------------------------------------------------
# Utilidades: palabras sintéticas con tiempos
# ---------------------------------------------------------------------------

def mk_words(spec):
    """spec: lista de (texto, gap_después). Cada palabra dura 0.25s."""
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
# T1 — «es decir» (conector) YA NO se corta (caso real: gageo en «el tejido»)
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("corte", 0.02), ("mostró", 0.02), ("un", 0.02),
    ("método", 0.02), ("de", 0.02), ("sección", 0.02), ("térmica;", 0.40),
    ("es", 0.02), ("decir,", 0.35),
    ("el", 0.02), ("tejido", 0.02), ("fue", 0.02), ("sellado", 0.02),
    ("con", 0.02), ("calor", 0.02), ("extremo.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
bad = [c for c in cuts if "decir" in nf.norm(c["text"])]
check("T1 conector «es decir» intocable", not bad,
      f"cortes: {[c['text'] for c in cuts]}")
check("T1b sin ningún corte en la frase", not cuts,
      f"cortes: {[(c['text'], c['reason']) for c in cuts]}")

# «o sea» tampoco (era FILLER_PHRASES)
words = mk_words([("Era", 0.02), ("grande,", 0.4), ("o", 0.02),
                  ("sea,", 0.4), ("enorme", 0.02), ("de", 0.02),
                  ("verdad.", 0.0)])
cuts = nf.detect_all(as_segments(words))
check("T1c conector «o sea» intocable",
      not any("sea" in nf.norm(c["text"]) for c in cuts),
      f"cortes: {[c['text'] for c in cuts]}")

# ---------------------------------------------------------------------------
# T2 — muletillas: vocal aislada SÍ; palabra tras puntuación NO
# ---------------------------------------------------------------------------
words = mk_words([("Todo", 0.02), ("cambió", 0.4), ("eh", 0.4),
                  ("desde", 0.02), ("entonces.", 0.0)])
cuts = nf.detect_fillers(words)
check("T2 «eh» aislada se corta", len(cuts) == 1 and cuts[0]["text"] == "eh",
      str(cuts))

words = mk_words([("Se", 0.02), ("acabó.", 0.5), ("Bueno,", 0.4),
                  ("sigamos", 0.02), ("adelante.", 0.0)])
cuts = nf.detect_fillers(words)
check("T2b «Bueno,» tras punto NO se corta", not cuts, str(cuts))

words = mk_words([("Y", 0.02), ("entonces", 0.4), ("este", 0.4),
                  ("apareció", 0.02), ("la", 0.02), ("bestia.", 0.0)])
cuts = nf.detect_fillers(words)
check("T2c «este» aislada sin puntuación previa SÍ se corta",
      len(cuts) == 1 and cuts[0]["text"] == "este", str(cuts))

words = mk_words([("Compré", 0.02), ("este", 0.02), ("libro", 0.02),
                  ("ayer.", 0.0)])
check("T2d «este» en frase fluida intocable",
      not nf.detect_fillers(words), "")

# ---------------------------------------------------------------------------
# T3 — falso arranque clásico (truncado, sin puntuación): sigue cortándose
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("registró", 0.02), ("veterinario", 2.0),
    ("El", 0.02), ("registro", 0.02), ("veterinario", 0.02),
    ("oficial", 0.02), ("es", 0.02), ("la", 0.02), ("evidencia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
covered = any(c["start"] <= 0.0 and c["end"] > 0.5 for c in cuts)
check("T3 falso arranque truncado se corta", covered, str(cuts))

# ---------------------------------------------------------------------------
# T4 — NUEVO: redo con puntuación de Whisper («El registró veterinario.»)
# — el caso que v0.40.0 dejó pasar («se repite la frase del error»)
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("registró", 0.02), ("veterinario.", 2.0),
    ("El", 0.02), ("registro", 0.02), ("veterinario", 0.02),
    ("oficial", 0.02), ("es", 0.02), ("la", 0.02), ("evidencia.", 0.0),
])
cuts = nf.detect_all(as_segments(words))
covered = [c for c in cuts if c["start"] <= 0.01 and c["end"] > 0.7]
check("T4 redo con puntuación se corta", bool(covered), str(cuts))
if covered:
    # el corte termina ANTES del reintento, con margen de guarda (≥90 ms)
    retry_start = words[3]["start"]
    check("T4b guarda antes del reintento",
          covered[0]["end"] <= retry_start - 0.09,
          f"end={covered[0]['end']} retry={retry_start}")

# ---------------------------------------------------------------------------
# T5 — anáfora retórica protegida
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("registro", 0.02), ("dice", 0.02), ("esto.", 0.45),
    ("El", 0.02), ("registro", 0.02), ("dice", 0.02), ("aquello", 0.02),
    ("distinto.", 0.0),
])
check("T5 anáfora («El registro dice…» ×2) intocable",
      not nf.detect_all(as_segments(words)),
      str(nf.detect_all(as_segments(words))))

# eco corto de 2 palabras (recurso retórico) protegido
words = mk_words([("La", 0.02), ("caída.", 0.6), ("La", 0.02),
                  ("caída", 0.02), ("fue", 0.02), ("brutal.", 0.0)])
check("T5b eco corto de 2 palabras intocable",
      not nf.detect_sentence_restarts(words), "")

# ---------------------------------------------------------------------------
# T6 — frase completa repetida idéntica tras pausa (redo real): corta la 1.ª
# ---------------------------------------------------------------------------
words = mk_words([
    ("El", 0.02), ("pánico", 0.02), ("rural", 0.02), ("se", 0.02),
    ("había", 0.02), ("visto", 0.02), ("alimentado", 0.02), ("por", 0.02),
    ("monos", 0.02), ("masivos.", 1.0),
    ("El", 0.02), ("pánico", 0.02), ("rural", 0.02), ("se", 0.02),
    ("había", 0.02), ("visto", 0.02), ("alimentado", 0.02), ("por", 0.02),
    ("monos", 0.02), ("masivos.", 0.4),
    ("Nadie", 0.02), ("dormía.", 0.0),
])
cuts = nf.detect_sentence_restarts(words)
second_start = words[10]["start"]
check("T6 frase completa repetida: corta la primera",
      len(cuts) == 1 and cuts[0]["start"] <= 0.01
      and cuts[0]["end"] <= second_start - 0.09, str(cuts))

# ---------------------------------------------------------------------------
# T7 — guardas de empalme en muletilla (anti-gageo)
# ---------------------------------------------------------------------------
words = mk_words([("Seguimos", 0.4), ("eh", 0.4), ("adelante.", 0.0)])
cuts = nf.detect_fillers(words)
nxt = words[2]["start"]
check("T7 fin del corte con guarda ≥100ms antes de la siguiente palabra",
      cuts and cuts[0]["end"] <= nxt - 0.10 + 1e-6,
      f"end={cuts[0]['end'] if cuts else None} next={nxt}")
check("T7b inicio del corte no invade la palabra previa",
      cuts and cuts[0]["start"] >= words[0]["end"] - 1e-6, str(cuts))

# ---------------------------------------------------------------------------
# T8 — revisión IA: SOLO seguridad 'alta' se corta; prompt protege conectores
# ---------------------------------------------------------------------------


class FakeLLM:
    is_mock = False

    def __init__(self, responses):
        self.responses = responses          # por purpose
        self.calls = []                     # (purpose, prompt)

    def complete_json(self, system, prompt, *, schema=None, images=None,
                      max_tokens=16000, purpose=""):
        self.calls.append((purpose, prompt, len(images or [])))
        r = self.responses[purpose]
        return r.pop(0) if isinstance(r, list) else r


words = mk_words([("Uno", 0.1), ("dos", 0.1), ("tres", 0.1), ("cuatro", 0.1),
                  ("cinco", 0.0)])
llm = FakeLLM({"narration_fix": {"errores": [
    {"inicio_palabra": 0, "fin_palabra": 0, "tipo": "muletilla",
     "motivo": "x", "seguridad": "alta"},
    {"inicio_palabra": 2, "fin_palabra": 2, "tipo": "repeticion",
     "motivo": "y", "seguridad": "media"},
]}})
out = nf.review_with_llm(llm, as_segments(words))
check("T8 revisión IA aplica solo 'alta'",
      len(out) == 1 and out[0]["text"] == "Uno", str(out))
sent = llm.calls[0][1]
check("T8b el prompt de revisión prohíbe conectores y exige contigüidad",
      "es decir" in sent and "contiguos" in sent.lower(), "")

# ---------------------------------------------------------------------------
# T9 — corte REAL de audio con ffmpeg: duración final = original - cortes
# ---------------------------------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="v042_"))
src = tmp / "voz.mp3"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=300:duration=6", "-c:a", "libmp3lame",
                str(src)], check=True)
from ytstudio.utils.media import probe_duration
dur0 = probe_duration(src)
dest = tmp / "voz_fix.mp3"
ok = nf.apply_to_audio(src, dest, [{"start": 2.0, "end": 2.8}])
dur1 = probe_duration(dest)
check("T9 corte real de audio", ok and abs((dur0 - dur1) - 0.8) < 0.15,
      f"{dur0:.2f}→{dur1:.2f}")

# ---------------------------------------------------------------------------
# T10 — pulido de transcripción: «monos masivos» → «monos macacos rhesus»
# ---------------------------------------------------------------------------
from ytstudio.phases.ingest import _apply_transcript_fix, _polish_transcript

segments = [{
    "start": 0.0, "end": 3.0,
    "text": "El pánico creció por monos masivos, según la prensa.",
    "words": [
        {"start": 0.0, "end": 0.2, "text": "El"},
        {"start": 0.2, "end": 0.5, "text": "pánico"},
        {"start": 0.5, "end": 0.8, "text": "creció"},
        {"start": 0.8, "end": 1.0, "text": "por"},
        {"start": 1.0, "end": 1.4, "text": "monos"},
        {"start": 1.4, "end": 1.9, "text": "masivos,"},
        {"start": 1.9, "end": 2.2, "text": "según"},
        {"start": 2.2, "end": 2.4, "text": "la"},
        {"start": 2.4, "end": 3.0, "text": "prensa."},
    ]}]
n = _apply_transcript_fix(segments, "monos masivos",
                          "monos macacos rhesus")
w = segments[0]["words"]
merged = [x for x in w if "macacos" in x["text"]]
check("T10 sustitución aplicada", n == 1 and len(merged) == 1, str(w))
check("T10b tiempo del tramo intacto",
      merged and merged[0]["start"] == 1.0 and merged[0]["end"] == 1.9,
      str(merged))
check("T10c puntuación conservada",
      merged and merged[0]["text"].endswith(","), str(merged))
check("T10d texto del segmento reconstruido",
      "monos macacos rhesus, según" in segments[0]["text"],
      segments[0]["text"])


class PStub:
    """Proyecto mínimo con el mismo contrato que Project (path/get/set)."""

    def __init__(self, root):
        self.root = Path(root)
        self.data = {}
        self.warnings = []
        from ytstudio.project import DIRS
        self.DIRS = DIRS

    def path(self, key, *parts):
        p = self.root / self.DIRS[key]
        p.mkdir(parents=True, exist_ok=True)
        return p.joinpath(*parts) if parts else p

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.warnings.append(m)


proj = PStub(tmp / "p1")
segments2 = json.loads(json.dumps(segments))  # copia limpia ya corregida? no:
segments2 = [{
    "start": 0.0, "end": 2.0, "text": "Vieron monos masivos en la selva.",
    "words": [
        {"start": 0.0, "end": 0.3, "text": "Vieron"},
        {"start": 0.3, "end": 0.7, "text": "monos"},
        {"start": 0.7, "end": 1.2, "text": "masivos"},
        {"start": 1.2, "end": 1.5, "text": "en"},
        {"start": 1.5, "end": 1.7, "text": "la"},
        {"start": 1.7, "end": 2.0, "text": "selva."},
    ]}]
llm = FakeLLM({"transcript_polish": {"correcciones": [
    {"original": "monos masivos", "corregido": "monos macacos rhesus",
     "seguridad": "alta"},
    {"original": "la selva", "corregido": "la sierra", "seguridad": "media"},
]}})
out = _polish_transcript(proj, {"audio": {}}, llm, segments2, "español")
check("T11 pulido aplica solo 'alta'",
      "macacos rhesus" in out[0]["text"] and "sierra" not in out[0]["text"],
      out[0]["text"])
check("T11b aviso de corrección emitido",
      any("macacos rhesus" in w for w in proj.warnings), str(proj.warnings))
check("T11c registro transcript_fixes",
      proj.get("transcript_fixes") and len(proj.get("transcript_fixes")) == 1,
      str(proj.get("transcript_fixes")))

# ---------------------------------------------------------------------------
# T12 — STT: parámetro hint (sesgo de vocabulario)
# ---------------------------------------------------------------------------
import inspect

from ytstudio.providers.stt import MockSTT, OpenAISTT

sig = inspect.signature(OpenAISTT.transcribe_segments)
check("T12 OpenAISTT.transcribe_segments acepta hint",
      "hint" in sig.parameters, str(sig))
mock_stt = MockSTT({})
segs = mock_stt.transcribe_segments(src, hint="chupacabras macacos rhesus")
check("T12b MockSTT tolera hint", bool(segs), "")

# ---------------------------------------------------------------------------
# T13 — scenes: image_text + reglas de cantidad/texto + schemas válidos
# ---------------------------------------------------------------------------
from ytstudio.phases import scenes as sc
from ytstudio.providers.llm import check_schema

check("T13 image_text en _CREATIVE_PROPS", "image_text" in sc._CREATIVE_PROPS, "")
try:
    check_schema(sc.SCENES_SCHEMA)
    check_schema(sc.DIRECTION_SCHEMA)
    check("T13b schemas válidos para salida estructurada", True)
except Exception as e:
    check("T13b schemas válidos para salida estructurada", False, str(e))
check("T13c regla de CANTIDAD Y GEOMETRÍA",
      "CANTIDAD Y GEOMETRÍA" in sc.CREATIVE_RULES, "")
# La regla del idioma cambió en la v0.53.0: antes se forzaba SIEMPRE el
# idioma de la narración, y eso era un error (un papiro en arameo dentro de un
# documental en español debe leerse en arameo). Lo que se sigue garantizando:
# que NUNCA salga en inglés por defecto en un video que no lo es.
check("T13d regla de TEXTO DENTRO DE LA IMAGEN",
      "TEXTO DENTRO DE LA IMAGEN" in sc.CREATIVE_RULES
      and "EL IDIOMA LO MANDA LA ESCENA" in sc.CREATIVE_RULES
      and "jamás en inglés" in sc.CREATIVE_RULES, "")

test_scenes = [
    {"id": 1, "narration": "hola mundo esta es una escena", "broll_type": "image",
     "animation": "zoom_in", "image_text": "  EL MISTERIO  "},
    {"id": 2, "narration": "otra escena", "broll_type": "image",
     "animation": "zoom_out", "image_text": ""},
]
sc._normalize_creative(test_scenes)
check("T13e normalización conserva image_text con contenido",
      test_scenes[0].get("image_text") == "EL MISTERIO", str(test_scenes[0].get("image_text")))
check("T13f normalización elimina image_text vacío",
      "image_text" not in test_scenes[1], "")

# ---------------------------------------------------------------------------
# T14 — broll: run() completo con escalera (plano atmosférico y vecino)
# ---------------------------------------------------------------------------
from PIL import Image

from ytstudio.phases import broll as br


def write_jpg(out, color):
    Image.new("RGB", (320, 180), color).save(out, quality=90)


class FakeImages:
    """Rechaza como NSFW los prompts con 'forbidden'; el plano atmosférico
    ('establishing shot') pasa. Registra cada prompt aceptado."""

    def __init__(self, reject_all=False):
        self.prompts = []
        self.reject_all = reject_all

    def generate(self, prompt, out):
        if self.reject_all or ("forbidden" in prompt
                               and "establishing shot" not in prompt):
            raise RuntimeError("prompt flagged as NSFW by safety checker")
        self.prompts.append(prompt)
        write_jpg(out, (40, 90, 160))
        return out


class MockishLLM:
    is_mock = True


def make_broll_project(root, prompts):
    p = PStub(root)
    p.set("concept", {"visual_style": {"prompt_prefix": "STYLEPFX",
                                       "palette": ["1c2030", "08090e"]}})
    scenes = [{"id": i + 1, "section": "s", "narration": f"escena {i + 1}",
               "broll_prompt": pr, "broll_type": "image",
               "animation": "zoom_in", "duration": 5.0}
              for i, pr in enumerate(prompts)]
    p.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}), encoding="utf-8")
    return p


cfg_broll = {
    "language": "es",
    "video": {"width": 320, "height": 180},
    "providers": {"images": {"name": "fake"}, "videogen": {"name": "none"}},
    "performance": {"parallel_images": 2},
}

fake = FakeImages()
old = (br.get_images, br.get_videogen, br.get_llm)
br.get_images = lambda cfg: fake
br.get_videogen = lambda cfg: None
br.get_llm = lambda cfg: MockishLLM()
try:
    p = make_broll_project(tmp / "b1", ["a calm forest", "a forbidden scene"])
    br.run(p, cfg_broll)
    img2 = p.path("broll", "scene_002.jpg")
    check("T14 escena rechazada obtiene plano atmosférico REAL",
          img2.exists() and any("establishing shot" in x for x in fake.prompts),
          str(fake.prompts))
    check("T14b aviso de plano atmosférico",
          any("plano atmosférico" in w for w in p.warnings), str(p.warnings))

    # rechazo TOTAL → vecina desenfocada / degradado (sin costo)
    fake2 = FakeImages(reject_all=True)
    br.get_images = lambda cfg: fake2
    p2 = make_broll_project(tmp / "b2", ["uno", "dos"])
    # una vecina preexistente clara para verificar el desenfoque/oscurecido
    write_jpg(p2.path("broll", "scene_001.jpg"), (250, 60, 60))
    br.run(p2, cfg_broll)
    out2 = p2.path("broll", "scene_002.jpg")
    im = Image.open(out2).convert("RGB")
    px = list(im.getdata())
    mean_r = sum(c[0] for c in px) / len(px)
    check("T14c vecina desenfocada y oscurecida como respaldo",
          out2.exists() and 40 < mean_r < 200,
          f"mean_r={mean_r:.0f}")
    check("T14d aviso de respaldo local",
          any("vecina desenfocada" in w for w in p2.warnings), str(p2.warnings))

    # image_text sin OpenAI → prompt con énfasis tipográfico + aviso
    fake3 = FakeImages()
    br.get_images = lambda cfg: fake3
    p3 = make_broll_project(tmp / "b3", ["front page of a newspaper"])
    sc3 = json.loads(p3.path("scenes", "scenes.json").read_text())
    sc3["scenes"][0]["image_text"] = "EL MISTERIO"
    p3.path("scenes", "scenes.json").write_text(json.dumps(sc3))
    import os as _os
    saved_key = _os.environ.pop("OPENAI_API_KEY", None)
    try:
        br.run(p3, cfg_broll)
    finally:
        if saved_key:
            _os.environ["OPENAI_API_KEY"] = saved_key
    check("T14e prompt exige el texto EXACTO en el idioma del guion",
          any('"EL MISTERIO"' in x and "español" in x for x in fake3.prompts),
          str(fake3.prompts))
    check("T14f aviso de falta de clave OpenAI para tipografía",
          any("OPENAI_API_KEY" in w or "OpenAI" in w for w in p3.warnings),
          str(p3.warnings))
finally:
    br.get_images, br.get_videogen, br.get_llm = old

# ---------------------------------------------------------------------------
# T15 — QA factual con visión: regeneración + firma de caché + honestidad
# ---------------------------------------------------------------------------
p4 = PStub(tmp / "b4")
broll_dir = p4.path("broll")
scene_bad = {"id": 2, "narration": "Ocho ovejas muertas en el corral.",
             "broll_prompt": "sheep in a field", "broll_type": "image"}
scene_ok = {"id": 1, "narration": "Un valle tranquilo.",
            "broll_prompt": "a quiet valley", "broll_type": "image"}
write_jpg(broll_dir / "scene_001.jpg", (10, 120, 40))
write_jpg(broll_dir / "scene_002.jpg", (10, 40, 120))
fixed_prompt = ("STYLEPFX exactly eight dead sheep, no more no fewer, all "
                "lifeless on the ground, none standing")
qa_llm = FakeLLM({"broll_qa": [
    {"reviews": [
        {"scene": 1, "fiel": True, "problema": "", "prompt_corregido": ""},
        {"scene": 2, "fiel": False,
         "problema": "las ovejas aparecen vivas y de pie",
         "prompt_corregido": fixed_prompt}]},
    {"reviews": [
        {"scene": 2, "fiel": False, "problema": "sigue habiendo una de pie",
         "prompt_corregido": "x"}]},
]})
regen = []
# fact_check_retries=1 fija el contrato que ESTA batería vigila (v0.42.0: UNA
# corrección por escena). Desde la v0.53.0 el valor por defecto es 2 rondas y
# eso lo cubre test_v0_53_0; aquí interesa que se regenere SOLO la escena
# infiel, con su prompt corregido, y que el aviso final sea honesto.
br._verify_factual(p4, qa_llm,
                   {"providers": {"images": {"fact_check_retries": 1}}},
                   [scene_ok, scene_bad], broll_dir,
                   lambda s, pr, img: (regen.append(pr),
                                       write_jpg(img, (200, 200, 40))),
                   skip=set())
check("T15 regenera SOLO la escena infiel con el prompt corregido",
      regen == [fixed_prompt], str(regen))
check("T15b broll_prompt actualizado", scene_bad["broll_prompt"] == fixed_prompt, "")
import hashlib
sigs = json.loads((broll_dir / "prompts.json").read_text())
want = hashlib.md5((fixed_prompt + "|chars:").encode()).hexdigest()
check("T15c firma de caché actualizada (sin recobros al reanudar)",
      sigs.get("2") == want, str(sigs))
check("T15d segunda mirada avisa si sigue infiel",
      any("pueden seguir" in w for w in p4.warnings), str(p4.warnings))
check("T15e la visión recibió las imágenes",
      qa_llm.calls and qa_llm.calls[0][2] == 2, str([c[2] for c in qa_llm.calls]))

# fact_check desactivable
qa2 = FakeLLM({"broll_qa": {"reviews": []}})
br._verify_factual(p4, qa2, {"providers": {"images": {"fact_check": False}}},
                   [scene_ok], broll_dir, lambda *a: None, skip=set())
check("T15f fact_check=false no gasta visión", not qa2.calls, "")

# ---------------------------------------------------------------------------
# T16 — música: actos por intensidad + banda sonora multi-pista REAL
# ---------------------------------------------------------------------------
from ytstudio.phases import music as mu

scenes_m = ([{"duration": 15.0, "music_intensity": 0.3}] * 5
            + [{"duration": 15.0, "music_intensity": 0.55}] * 4
            + [{"duration": 15.0, "music_intensity": 0.9}] * 4)
acts = mu._acts_from_scenes(scenes_m)
check("T16 actos por arco de intensidad",
      len(acts) == 3 and [a["band"] for a in acts] == ["calma", "media", "alta"],
      str([(a["band"], a["dur"]) for a in acts]))
check("T16b duración conservada",
      abs(sum(a["dur"] for a in acts) - 15.0 * 13) < 0.01, "")
check("T16c ningún acto menor a 60s", all(a["dur"] >= 60 for a in acts), "")

# actos cortos se funden
acts2 = mu._acts_from_scenes([{"duration": 10, "music_intensity": 0.3},
                              {"duration": 10, "music_intensity": 0.9},
                              {"duration": 10, "music_intensity": 0.3}])
check("T16d video corto queda en un solo acto", len(acts2) == 1, str(acts2))

# --- multi-pista real con ffmpeg ---
lib = tmp / "musiclib"
lib.mkdir()
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=220:duration=10", "-c:a", "libmp3lame",
                str(lib / "calma_amanecer.mp3")], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=600:duration=10", "-c:a", "libmp3lame",
                str(lib / "tension_final.mp3")], check=True)

cfg_music = {"language": "es",
             "providers": {"music": {"name": "library",
                                     "library_dir": str(lib)}}}
lm = mu.LibraryMusic(cfg_music)
tracks = lm.list_tracks()
check("T16e list_tracks ve las 2 pistas", len(tracks) == 2, str(tracks))

p5 = PStub(tmp / "p5")
scenes_j = [{"id": 1, "section": "intro", "narration": "arranque tranquilo",
             "duration": 65.0, "music_intensity": 0.3},
            {"id": 2, "section": "medio", "narration": "sube la cosa",
             "duration": 65.0, "music_intensity": 0.6},
            {"id": 3, "section": "climax", "narration": "el clímax",
             "duration": 65.0, "music_intensity": 0.95}]
p5.path("scenes", "scenes.json").write_text(
    json.dumps({"scenes": scenes_j}), encoding="utf-8")
music_llm = FakeLLM({"music_pick_acts": {
    "files": ["calma_amanecer.mp3", "calma_amanecer.mp3",
              "tension_final.mp3"],
    "reason": "arco de tensión"}})
out_music = p5.path("music", "musica.mp3")
ok = mu._try_multi_track(p5, cfg_music, lm, music_llm, tracks,
                         {"music_direction": {"mood": "tension"}},
                         "chupacabras", "es", 195.0, out_music)
dur = probe_duration(out_music) if out_music.exists() else 0
check("T16f banda sonora por actos construida", ok and out_music.exists(), "")
check("T16g duración total ≈ video + 2s", abs(dur - 197.0) < 2.0,
      f"dur={dur:.1f}")
check("T16h music_choice registrado",
      (p5.get("music_choice") or {}).get("source") == "biblioteca_arco",
      str(p5.get("music_choice")))


def band_rms(path, t0, t1):
    """Nivel medio (dB) por encima de 400 Hz en el tramo [t0,t1] — separa la
    pista de 220 Hz de la de 600 Hz."""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af",
         f"atrim={t0}:{t1},highpass=f=400,highpass=f=400,volumedetect",
         "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else -99.0


early = band_rms(out_music, 5, 15)      # acto 1: 220 Hz → poco > 400 Hz
late = band_rms(out_music, 140, 160)    # acto 3: 600 Hz → mucho > 400 Hz
check("T16i el clímax suena con OTRA pista (verificación espectral)",
      late - early > 12, f"early={early:.1f}dB late={late:.1f}dB")

# multi_track desactivable
ok2 = mu._try_multi_track(
    p5, {"providers": {"music": {"multi_track": False}}}, lm, music_llm,
    tracks, {}, "t", "es", 195.0, out_music)
check("T16j multi_track=false respetado", ok2 is False, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.42.0 completa: todos los frentes verificados con código real.")
shutil.rmtree(tmp, ignore_errors=True)
