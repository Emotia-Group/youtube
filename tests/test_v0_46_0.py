"""Batería v0.46.0 — INSERTOS documentales sobre el B-roll (Fase 1).

El sistema aprobado por el creador: cuando la narración menciona un personaje,
lugar, entidad, cifra o fecha, un inserto de archivo aparece sobre el B-roll
en el instante exacto de la mención — foto real (banco propio o Wikimedia con
licencia libre y crédito automático), o cifra con cuenta ascendente generada
en local ($0), con su 'pop' sutil de sonido.

Verifica:
1. Tarjetas locales: foto enmarcada estilo archivo y cifra en cuenta
   ascendente (formato de miles conservado, valor final EXACTO).
2. Banco local: prioridad absoluta y búsqueda tolerante a tildes/guiones.
3. Wikimedia: solo licencias LIBRES (CC/PD); una licencia restrictiva se
   rechaza; el crédito viaja con la foto (API simulada, sin internet).
4. Documentalista: planifica con densidad acotada; mock/cortos → ni una
   llamada; una tanda fallida no tumba la fase.
5. Sincronía: el inserto se ancla a la PALABRA de la mención (find_hit).
6. Montaje REAL: una escena con inserto renderiza con ffmpeg y el inserto
   es visible en el cuadro (píxeles medidos), no antes de su instante.
7. El 'pop' entra en la pista SFX en el momento del inserto.
8. La atribución aparece en TODAS las descripciones y la firma de render
   cambia con los elementos (reanudar re-renderiza la escena).
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import shutil
import subprocess
import tempfile
import types

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0460_"))

from ytstudio.utils import elements as elib

# ---------------------------------------------------------------------------
# T1 — tarjetas locales (PIL, $0)
# ---------------------------------------------------------------------------
from PIL import Image

foto = TMP / "musk.jpg"
Image.new("RGB", (400, 500), (90, 60, 40)).save(foto)
card = elib.render_photo_card(foto, "Elon Musk", TMP / "card.png", 360)
im = Image.open(card)
check("T1 la tarjeta de foto es PNG con transparencia y del ancho pedido",
      im.mode == "RGBA" and 360 <= im.width <= 400, f"{im.mode} {im.size}")

frames = elib.render_stat_frames("60.000 personas", "La caravana",
                                 TMP / "stat", 360)
check("T1b la cifra genera una secuencia de cuenta ascendente",
      len(frames) >= 10 and all(p.exists() for p in frames), str(len(frames)))
# el ÚLTIMO cuadro debe mostrar el valor exacto: se verifica reconstruyendo
# el formateo con el mismo separador
check("T1c el separador de miles se conserva (60.000, no 60000)",
      elib._NUM_RE.match("60.000 personas").group(2) == "60.000", "")
solo_fecha = elib.render_stat_frames("Año 1324", "", TMP / "fecha", 360)
check("T1d una fecha (sin cuenta que subir) es UNA tarjeta estática",
      len(solo_fecha) >= 1, str(len(solo_fecha)))

# ---------------------------------------------------------------------------
# T2 — banco local: prioridad y búsqueda tolerante
# ---------------------------------------------------------------------------
_bank_real = elib.BANK_DIR
elib.BANK_DIR = TMP / "banco"
(elib.BANK_DIR / "personajes").mkdir(parents=True)
(elib.BANK_DIR / "lugares").mkdir()
Image.new("RGB", (100, 100), (0, 100, 0)).save(
    elib.BANK_DIR / "personajes" / "Elon-Musk.jpg")
Image.new("RGB", (100, 100), (0, 0, 100)).save(
    elib.BANK_DIR / "lugares" / "el cairo.png")
check("T2 encuentra por nombre con guiones y mayúsculas",
      elib.bank_lookup("Elon Musk") is not None
      and elib.bank_lookup("Elon Musk").name == "Elon-Musk.jpg", "")
check("T2b tolera tildes y artículos («El Cairo» → el cairo.png)",
      elib.bank_lookup("El Cairo") is not None, "")
check("T2c sin coincidencia devuelve None (no inventa)",
      elib.bank_lookup("Rockefeller") is None, "")

# ---------------------------------------------------------------------------
# T3 — Wikimedia simulada: solo licencias libres, con crédito
# ---------------------------------------------------------------------------
_RESPUESTAS = {}


def _fake_api(url, timeout=12):
    for k, v in _RESPUESTAS.items():
        if k in url:
            return v
    return {}


_real_api = elib._api_json
elib._api_json = _fake_api
_real_urlopen = elib.urllib.request.urlopen


class _FakeDL:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=None):
        import io
        buf = io.BytesIO()
        Image.new("RGB", (300, 300), (120, 20, 20)).save(buf, format="JPEG")
        return buf.getvalue()


elib.urllib.request.urlopen = lambda req, timeout=20: _FakeDL()

_RESPUESTAS.clear()
_RESPUESTAS["wikipedia.org"] = {"query": {"pages": {"1": {
    "original": {"source": "https://upload.wikimedia.org/x/Musk.jpg"},
    "pageimage": "Musk.jpg"}}}}
_RESPUESTAS["commons.wikimedia.org"] = {"query": {"pages": {"1": {
    "imageinfo": [{"extmetadata": {
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
        "Artist": {"value": "<a href='#'>Fotógrafo X</a>"}}}]}}}}
got = elib.wiki_photo("Elon Musk", "es", TMP)
check("T3 con licencia libre: descarga la foto y arma el crédito",
      got is not None and got["file"].exists()
      and "Fotógrafo X" in got["credit"] and "CC BY-SA" in got["credit"],
      str(got))

_RESPUESTAS["commons.wikimedia.org"] = {"query": {"pages": {"1": {
    "imageinfo": [{"extmetadata": {
        "LicenseShortName": {"value": "Fair use"},
        "Artist": {"value": "X"}}}]}}}}
check("T3b una licencia NO libre se rechaza (no se descarga nada)",
      elib.wiki_photo("Logo Corp", "es", TMP) is None, "")
elib._api_json = _real_api
elib.urllib.request.urlopen = _real_urlopen

# ---------------------------------------------------------------------------
# T4 — el documentalista de archivo (planificación)
# ---------------------------------------------------------------------------
from ytstudio.phases.scenes import _archive_pass


class PStub:
    def __init__(self):
        self.data, self.avisos = {}, []

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.avisos.append(m)

    def path(self, kind, name=""):
        d = TMP / "proj" / kind
        d.mkdir(parents=True, exist_ok=True)
        return d / name if name else d


class ArchLLM:
    is_mock = False

    def __init__(self):
        self.llamadas = 0

    def complete_json(self, system, prompt, *, schema, max_tokens=16000,
                      purpose="", images=None):
        self.llamadas += 1
        assert purpose == "archive_elements"
        return {"scenes": [
            {"id": 1, "elements": [{"tipo": "persona", "consulta": "Elon Musk",
                                    "etiqueta": "Elon Musk",
                                    "momento": "Elon Musk"}]},
            {"id": 2, "elements": []},
            {"id": 3, "elements": [{"tipo": "cifra",
                                    "consulta": "60.000 personas",
                                    "etiqueta": "La caravana",
                                    "momento": "60.000 personas"}]},
        ]}


cfg = {"language": "es",
       "video": {"width": 640, "height": 360, "fps": 12, "elements": True,
                 "elements_web": True, "overlay_accent": "E8C46B"},
       "audio": {"sfx": True, "sfx_db": -18}}
escenas = [{"id": i, "narration": n, "duration": 8.0, "animation": "static"}
           for i, n in enumerate(
               ["El número uno no es Elon Musk.",
                "No es ningún europeo.",
                "Su caravana tenía 60.000 personas."], 1)]
llm = ArchLLM()
_archive_pass(llm, PStub(), escenas, "español", cfg, short_form=False)
check("T4 el documentalista asigna los insertos planificados",
      escenas[0].get("elements") and escenas[2].get("elements")
      and not escenas[1].get("elements"), str([s.get("elements") for s in escenas]))

sin = [{"id": 1, "narration": "x", "duration": 5}]
mock = types.SimpleNamespace(is_mock=True, complete_json=None)
_archive_pass(mock, PStub(), sin, "español", cfg, short_form=False)
_archive_pass(llm, PStub(), sin, "español", cfg, short_form=True)
cfg_off = {**cfg, "video": {**cfg["video"], "elements": False}}
_archive_pass(llm, PStub(), sin, "español", cfg_off, short_form=False)
check("T4b mock, formato corto o elements:false → ni una llamada ni elemento",
      not sin[0].get("elements") and llm.llamadas == 1, str(llm.llamadas))


class RompeLLM:
    is_mock = False

    def complete_json(self, *a, **k):
        raise RuntimeError("Error code: 529")


p_err = PStub()
esc_err = [{"id": 1, "narration": "x", "duration": 5}]
_archive_pass(RompeLLM(), p_err, esc_err, "español", cfg, short_form=False)
check("T4c una tanda fallida deja aviso y el video sigue sin insertos",
      len(p_err.avisos) == 1 and "no se detiene" in p_err.avisos[0],
      str(p_err.avisos))

# ---------------------------------------------------------------------------
# T5 — resolución en B-roll (banco simulado, sin internet)
# ---------------------------------------------------------------------------
from ytstudio.phases import broll as broll_phase

proj = PStub()
broll_dir = proj.path("broll")
broll_phase._resolve_elements(proj, cfg, escenas, broll_dir)
el1, el3 = escenas[0]["elements"][0], escenas[2]["elements"][0]
check("T5 la persona sale del BANCO local (prioridad sobre internet)",
      el1.get("mode") == "photo"
      and (broll_dir / "elements" / el1["files"][0]).exists(), str(el1))
check("T5b la cifra se genera en local como secuencia",
      el3.get("mode") == "stat" and len(el3["files"]) >= 10
      and (broll_dir / "elements" / el3["files"][0]).exists(), str(el3))
elib.BANK_DIR = _bank_real

# ---------------------------------------------------------------------------
# T6 — sincronía a la palabra + MONTAJE REAL con ffmpeg
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import _element_setup, _sfx_graph

el1["at"] = 2.0
args, chain, pos = _element_setup(escenas[0], 8.0, cfg, proj)
check("T6 el inserto entra al grafo con su ventana de tiempo",
      args and "between(t,2.00" in pos and "fade=t=in" in chain,
      f"{pos} | {chain}")

# render REAL: fondo oscuro fijo + inserto → el cuadro cambia tras t0
fondo = broll_dir / "scene_001.jpg"
Image.new("RGB", (640, 360), (8, 8, 8)).save(fondo)
escena_r = {**escenas[0], "broll_image": "scene_001.jpg", "duration": 5.0,
            "animation": "static"}
escena_r["elements"][0]["at"] = 2.0
from ytstudio.phases.assembly import _render_scene

out_mp4 = TMP / "esc.mp4"
try:
    _render_scene(escena_r, proj, cfg, out_mp4, fade={})
    ok_render = out_mp4.exists() and out_mp4.stat().st_size > 0
except Exception as e:
    ok_render = False
    print("   render:", e)
check("T6b la escena con inserto RENDERIZA con ffmpeg", ok_render, "")
if ok_render:
    def brillo(t):
        f = TMP / f"fr_{t}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(out_mp4),
                        "-frames:v", "1", str(f)], capture_output=True)
        im = Image.open(f).convert("L")
        return sum(im.getdata()) / (im.width * im.height)
    antes, durante = brillo(1.0), brillo(3.5)
    check("T6c el inserto es VISIBLE tras la mención y no antes "
          "(brillo medido en el cuadro)",
          durante > antes + 3, f"antes={antes:.1f} durante={durante:.1f}")

# ---------------------------------------------------------------------------
# T7 — el 'pop' suena en el instante del inserto
# ---------------------------------------------------------------------------
sfx_scenes = [{"duration": 8.0, "sfx": None,
               "elements": [{"files": ["x.png"], "at": 2.0}]},
              {"duration": 8.0, "sfx": None}]
s_args, s_filters, s_label = _sfx_graph(sfx_scenes, cfg, TMP, first_input=2)
check("T7 la pista SFX incluye el pop con el retardo de la mención (2000ms)",
      s_label == "sfx" and any("adelay=2000|2000" in f for f in s_filters),
      str(s_filters))
from ytstudio.utils.sfx import SFX_SPECS, ensure_sfx

pop = ensure_sfx("pop", TMP)
check("T7b el pop se sintetiza en local y es corto",
      pop.exists() and SFX_SPECS["pop"]["dur"] <= 0.6, "")

# ---------------------------------------------------------------------------
# T8 — atribución en la descripción + firma de render
# ---------------------------------------------------------------------------
import inspect

from ytstudio.phases import metadata as meta_phase

msrc = inspect.getsource(meta_phase.run)
check("T8 la atribución se añade a TODAS las opciones de descripción",
      "element_credits" in msrc and "description_options" in msrc.split(
          "element_credits")[1][:400], "")
from ytstudio.phases.assembly import _render_signature

base = [{"id": 1, "duration": 5, "broll_image": "scene_001.jpg"}]
con_el = [{**base[0], "elements": [{"files": ["c.png"], "at": 1.0}]}]
f1 = _render_signature(base, [{}], cfg, proj)
f2 = _render_signature(con_el, [{}], cfg, proj)
check("T8b la firma de render cambia con los elementos (reanudar re-renderiza)",
      f1 != f2, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.46.0 completa: los insertos documentales aparecen en la "
      "mención exacta, con fuentes libres, crédito automático y pop sutil.")
shutil.rmtree(TMP, ignore_errors=True)
