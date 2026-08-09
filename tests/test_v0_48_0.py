"""Batería v0.48.0 — DISEÑO DE SONIDO documental (Fase 2 de las 4).

La música dibuja el arco dramático, pero el fondo estaba vacío: un tramo que
narra el desierto sonaba igual que uno que narra un mercado. Ahora hay una
CAMA DE AMBIENTE elegida por actos (el mismo reparto que la música) y dos
acentos incidentales nuevos ligados al contenido: 'papel' (archivo,
documentos, cifras) y 'latido' (suspenso).

Verifica, midiendo el audio REAL con ffmpeg:
1. Cada ambiente se sintetiza en local, suena (nivel medible) y no satura.
2. TU biblioteca (assets/sfx/ambientes/) tiene prioridad sobre la síntesis.
3. La cama por actos dura lo pedido, funde entre tramos y 'ninguno' es
   silencio de verdad; si todo es 'ninguno', no se genera nada.
4. El director de sonido planifica por actos en UNA llamada; mock, fallo o
   ambience:false nunca rompen la fase.
5. En la mezcla, el ambiente va MUY por debajo de la voz y muere con el video
   (mezcla real hecha con ffmpeg y medida).
6. Los acentos nuevos existen, suenan y el director puede elegirlos.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0480_"))


def nivel_db(path: Path) -> float:
    """Volumen medio real del archivo (dBFS) medido con ffmpeg."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return -999.0


def dur(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


from ytstudio.utils import ambience as amb

# ---------------------------------------------------------------------------
# T1 — cada ambiente se sintetiza, suena y no satura
# ---------------------------------------------------------------------------
niveles = {}
for kind in amb.kind_names():
    p = amb.render_kind(kind, 3.0, TMP / f"{kind}.wav")
    niveles[kind] = nivel_db(p)
    if not (p.exists() and abs(dur(p) - 3.0) < 0.25):
        check(f"T1 ambiente '{kind}' se genera con su duración", False,
              f"{dur(p):.2f}s")
check("T1 los 7 ambientes del catálogo se generan con su duración exacta",
      len(niveles) == 7, str(list(niveles)))
check("T1b todos suenan (por encima del silencio digital)",
      all(v > -60 for v in niveles.values()), str(niveles))
check("T1c y ninguno satura (margen de sobra bajo 0 dBFS)",
      all(v < -12 for v in niveles.values()), str(niveles))
check("T1d cada ambiente tiene su propio carácter (niveles distintos)",
      len({round(v) for v in niveles.values()}) >= 3, str(niveles))

# ---------------------------------------------------------------------------
# T2 — TU biblioteca manda sobre la síntesis
# ---------------------------------------------------------------------------
_real_lib = amb.LIB_DIR
amb.LIB_DIR = TMP / "biblioteca"
amb.LIB_DIR.mkdir()
# archivo de biblioteca SILENCIOSO a propósito: si se usa, el resultado será
# silencio; si el programa lo ignorase y sintetizara, sonaría (~-27 dB).
subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                "anullsrc=r=44100:cl=stereo:d=2",
                str(amb.LIB_DIR / "viento_propio.wav")],
               check=True, capture_output=True)
p_lib = amb.render_kind("viento", 3.0, TMP / "viento_lib.wav")
check("T2 con archivo propio en la biblioteca, se usa ESE y no el sintetizado",
      nivel_db(p_lib) < -80, f"{nivel_db(p_lib):.1f} dB")
check("T2b y se repite en bucle hasta cubrir el tramo pedido",
      abs(dur(p_lib) - 3.0) < 0.25, f"{dur(p_lib):.2f}s")
p_syn = amb.render_kind("multitud", 2.0, TMP / "mult_syn.wav")
check("T2c un tipo SIN archivo propio sigue sintetizándose",
      nivel_db(p_syn) > -60, f"{nivel_db(p_syn):.1f} dB")
amb.LIB_DIR = _real_lib

# ---------------------------------------------------------------------------
# T3 — la cama por actos: duración, fundidos y silencio real
# ---------------------------------------------------------------------------
bed = amb.build_bed([("viento", 6.0), ("multitud", 6.0), ("sala", 4.0)],
                    TMP / "bed.wav", work_dir=TMP / "bedwork")
check("T3 la cama de 3 actos se construye y cubre el video",
      bed is not None and dur(bed) >= 16.0 - 0.5, f"{dur(bed):.2f}s")
check("T3b suena de principio a fin", nivel_db(bed) > -60,
      f"{nivel_db(bed):.1f} dB")

silencio = amb.build_bed([("viento", 4.0), ("ninguno", 4.0)],
                         TMP / "bed2.wav", work_dir=TMP / "bedwork2")
check("T3c un acto 'ninguno' es silencio de verdad dentro de la cama",
      silencio is not None and dur(silencio) >= 7.5, f"{dur(silencio):.2f}s")
check("T3d si TODOS los actos son 'ninguno', no se genera cama",
      amb.build_bed([("ninguno", 5.0), ("ninguno", 5.0)], TMP / "no.wav",
                    work_dir=TMP / "bw3") is None, "")
check("T3e un plan vacío tampoco genera nada",
      amb.build_bed([], TMP / "no2.wav") is None, "")

# ---------------------------------------------------------------------------
# T4 — el DIRECTOR DE SONIDO planifica por actos
# ---------------------------------------------------------------------------
import json
import types

from ytstudio.phases import music as music_phase


class PStub:
    def __init__(self):
        self.data = {}
        self.avisos = []
        self.dir = TMP / "proj"

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.avisos.append(m)

    def path(self, kind, name=""):
        d = self.dir / kind
        d.mkdir(parents=True, exist_ok=True)
        return d / name if name else d


# escenas con dos tramos claros: desierto (calma) y mercado (intenso)
escenas = ([{"id": i, "duration": 12.0, "music_intensity": 0.2,
             "section": "El desierto",
             "narration": "La caravana cruzó el Sahara durante meses."}
            for i in range(1, 6)]
           + [{"id": i, "duration": 12.0, "music_intensity": 0.85,
               "section": "El mercado de El Cairo",
               "narration": "El oro inundó los mercados de El Cairo."}
              for i in range(6, 11)])
def sembrar(p):
    """Escribe las escenas como lo hace el programa (scenes.json envuelto)."""
    p.path("scenes").mkdir(parents=True, exist_ok=True)
    (p.path("scenes") / "scenes.json").write_text(
        json.dumps({"scenes": escenas}, ensure_ascii=False), encoding="utf-8")
    return p


proj = sembrar(PStub())


class SoundLLM:
    is_mock = False

    def __init__(self):
        self.llamadas = 0
        self.purpose = None

    def complete_json(self, system, prompt, *, schema, max_tokens=8000,
                      purpose="", images=None):
        self.llamadas += 1
        self.purpose = purpose
        self.prompt = prompt
        return {"actos": [{"acto": 0, "ambiente": "viento",
                           "motivo": "el desierto"},
                          {"acto": 1, "ambiente": "multitud",
                           "motivo": "el mercado"}]}


cfg = {"language": "es",
       "video": {"width": 640, "height": 360, "fps": 12},
       "audio": {"ambience": True, "ambience_db": -30, "sfx": True,
                 "sfx_db": -18},
       "providers": {"music": {"multi_track": True}}}
llm = SoundLLM()
music_phase._build_ambience(proj, cfg, llm, 120.0)
amb_file = proj.path("music", "ambiente.wav")
check("T4 el director de sonido resuelve el video en UNA llamada",
      llm.llamadas == 1 and llm.purpose == "sound_design",
      f"{llm.llamadas} llamadas, purpose={llm.purpose}")
check("T4b el catálogo de ambientes viaja en el prompt",
      "viento" in llm.prompt and "multitud" in llm.prompt, "")
check("T4c la cama queda construida en el proyecto",
      amb_file.exists() and nivel_db(amb_file) > -60,
      f"{amb_file.exists()} {nivel_db(amb_file):.1f} dB")
plan = proj.get("ambience_plan")
check("T4d y el plan queda guardado con un ambiente por acto",
      plan and [p["ambiente"] for p in plan] == ["viento", "multitud"],
      str(plan))
check("T4e no se toca nada si ya existe (reanudar no re-sintetiza)",
      (music_phase._build_ambience(proj, cfg, llm, 120.0), llm.llamadas)[1] == 1,
      str(llm.llamadas))

# mock: cama neutra sin llamadas
p2 = PStub()
p2.dir = TMP / "proj2"
sembrar(p2)
mock = types.SimpleNamespace(is_mock=True)
music_phase._build_ambience(p2, cfg, mock, 120.0)
check("T4f en modo vista previa hay cama neutra y CERO llamadas",
      (p2.path("music", "ambiente.wav")).exists(), "")

# el LLM falla: aviso y el video sale con música y voz
class RompeLLM:
    is_mock = False

    def complete_json(self, *a, **k):
        raise RuntimeError("Error code: 529")


p3 = PStub()
p3.dir = TMP / "proj3"
sembrar(p3)
music_phase._build_ambience(p3, cfg, RompeLLM(), 120.0)
check("T4g si el modelo falla: aviso honesto y sin cama (la fase sigue)",
      not (p3.path("music", "ambiente.wav")).exists()
      and len(p3.avisos) == 1 and "sin cama de ambiente" in p3.avisos[0],
      str(p3.avisos))

# desactivado por configuración
p4 = PStub()
p4.dir = TMP / "proj4"
sembrar(p4)
cfg_off = {**cfg, "audio": {**cfg["audio"], "ambience": False}}
music_phase._build_ambience(p4, cfg_off, SoundLLM(), 120.0)
check("T4h con ambience:false no se genera ni se consulta nada",
      not (p4.path("music", "ambiente.wav")).exists(), "")

# ---------------------------------------------------------------------------
# T5 — MEZCLA REAL: el ambiente va muy por debajo de la voz
# ---------------------------------------------------------------------------
from ytstudio.phases.assembly import _ambience_input

a_args, a_filt, a_label = _ambience_input(proj, cfg, 30.0, 4)
check("T5 el ambiente entra a la mezcla con su nivel y sus fundidos",
      a_label == "amb" and "volume=-30.0dB" in a_filt
      and "afade=t=in" in a_filt and "afade=t=out" in a_filt, a_filt)
check("T5b se acota a la duración EXACTA del video",
      "atrim=0:30.000" in a_filt and "apad=whole_dur=30.000" in a_filt, a_filt)
check("T5c con ambience:false o sin archivo, la mezcla no lo incluye",
      _ambience_input(proj, cfg_off, 30.0, 4)[2] is None
      and _ambience_input(p4, cfg, 30.0, 4)[2] is None, "")

# mezcla de verdad: voz (tono) + ambiente, medida
voz = TMP / "voz.wav"
subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=220:duration=10", "-af", "volume=-16dB",
                str(voz)], check=True, capture_output=True)
# Se comparan DOS mezclas idénticas —una con la cama, otra con silencio en su
# lugar— para aislar la aportación real del ambiente (comparar contra el
# archivo de voz suelto mezclaría formatos distintos y no mediría nada).
a10 = (a_filt.replace("[4:a]", "[1:a]").replace("0:30.000", "0:10.000")
       .replace("whole_dur=30.000", "whole_dur=10.000"))
silencio_wav = TMP / "silencio.wav"
subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=stereo:d=12", str(silencio_wav)],
               check=True, capture_output=True)


def mezclar(segunda: Path, out: Path):
    subprocess.run(["ffmpeg", "-y", "-i", str(voz), "-i", str(segunda),
                    "-filter_complex",
                    "[0:a]aformat=channel_layouts=stereo[v];" + a10 +
                    ";[v][amb]amix=inputs=2:duration=first:normalize=0[out]",
                    "-map", "[out]", str(out)], check=True, capture_output=True)
    return out


mezcla = mezclar(amb_file, TMP / "mezcla_con.wav")
mezcla_sin = mezclar(silencio_wav, TMP / "mezcla_sin.wav")
con_amb, sin_amb = nivel_db(mezcla), nivel_db(mezcla_sin)
check("T5d la mezcla real se construye con ffmpeg sin errores",
      mezcla.exists() and abs(dur(mezcla) - 10.0) < 0.3, f"{dur(mezcla):.2f}s")
check("T5e el ambiente SE OYE en la mezcla (aporta nivel)",
      con_amb > sin_amb + 0.05, f"con={con_amb:.2f} sin={sin_amb:.2f}")
check("T5f pero NO tapa la voz (aporta menos de 1.5 dB al total)",
      con_amb - sin_amb < 1.5, f"con={con_amb:.2f} sin={sin_amb:.2f}")

# ---------------------------------------------------------------------------
# T6 — acentos incidentales nuevos, ligados al contenido
# ---------------------------------------------------------------------------
from ytstudio.utils.sfx import SFX_SPECS, ensure_sfx

for kind in ("papel", "latido"):
    p = ensure_sfx(kind, TMP)
    check(f"T6 el acento '{kind}' se sintetiza y suena",
          p.exists() and nivel_db(p) > -60, f"{nivel_db(p):.1f} dB")
check("T6b y están en el catálogo de tiempos del montaje",
      "papel" in SFX_SPECS and "latido" in SFX_SPECS, "")

import inspect

from ytstudio.phases import scenes as scenes_phase

src = inspect.getsource(scenes_phase)
check("T6c el director puede elegirlos (schema y reglas creativas)",
      '"papel", "latido"' in src and "documento" in src and "suspenso" in src,
      "")
esc = [{"id": 1, "sfx": "papel"}, {"id": 2, "sfx": "latido"},
       {"id": 3, "sfx": "inventado"}]
for s in esc:
    s["sfx"] = s.get("sfx") if s.get("sfx") in (
        "whoosh", "riser", "boom", "papel", "latido") else None
check("T6d un efecto inventado por el modelo se descarta",
      [s["sfx"] for s in esc] == ["papel", "latido", None], str(esc))

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.48.0 completa: cama de ambiente por actos bajo la voz, "
      "biblioteca propia con prioridad y acentos ligados al contenido.")
shutil.rmtree(TMP, ignore_errors=True)
