"""Batería v0.22.0 — subtítulos que caen donde la voz SUENA.

NOTA HISTÓRICA (actualizada tras v0.42.2): esta batería nació validando la
CALIBRACIÓN de Whisper (`whisper_calibration`), una función que se RETIRÓ a
propósito en v0.24.0 por poco fiable — medía -158 ms y +226 ms sobre la MISMA
grabación (±380 ms de dispersión), porque el emparejamiento con respiraciones
sesgaba la mediana. La sustituyó el LAZO CERRADO de subtítulos: se mide el
desfase sobre el resultado renderizado y se corrige con esa medición.

Las comprobaciones de calibración se retiraron con la función; lo que sigue
verificándose es la GARANTÍA de cara al usuario, que no cambió: con un STT
cuyos tiempos vienen +400 ms tarde, los subtítulos del video final caen sobre
la voz real (desfase medido ≈ 0).

El caso del usuario: contenedor perfecto pero subtítulos corridos vs la voz
real → coordenadas Whisper derivadas. Simula un STT cuyos tiempos vienen
+400ms tarde y verifica que: (1) la calibración mide y corrige el offset;
(2) el pipeline completo produce subtítulos que caen donde la voz SUENA;
(3) la medición de contenido reporta desfase ~0 tras calibrar."""

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



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_v0220_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el
el.LOG_PATH = WORK / "data" / "events.log"

from ytstudio.project import Project
from ytstudio.phases import ingest
from ytstudio.pipeline import run_pipeline
from ytstudio.utils.media import detect_silences, probe_duration

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# Voz sintética: 4 frases con silencios reales entre ellas
BURSTS = [(0.3, 3.2), (3.9, 7.1), (7.8, 10.6), (11.3, 14.0)]
TOTAL = 14.6
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in BURSTS)
voz = WORK / "voz.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", f"aevalsrc=0.4*sin(2*PI*180*t)*({expr}):s=44100:d={TOTAL}",
                "-c:a", "pcm_s16le", str(voz)], check=True)

DRIFT = 0.40  # Whisper marca todo +400ms tarde (deriva real de whisper-1)
FRASES = ["Primera frase del documental histórico.",
          "Segunda frase con datos importantes.",
          "Tercera frase de gran tension narrativa.",
          "Cuarta frase con el veredicto final."]


class _DriftedSTT:
    """STT que 'transcribe' con timestamps corridos +DRIFT vs la onda real."""
    is_mock = False

    def transcribe(self, audio):
        return " ".join(FRASES)

    def transcribe_segments(self, audio):
        segs = []
        for (a, b), texto in zip(BURSTS, FRASES):
            ws = texto.split()
            dur = (b - a) / len(ws)
            words = [{"start": round(a + i * dur + DRIFT, 3),
                      "end": round(a + (i + 1) * dur - 0.03 + DRIFT, 3),
                      "text": w} for i, w in enumerate(ws)]
            segs.append({"start": round(a + DRIFT, 3), "end": round(b + DRIFT, 3),
                        "text": texto, "words": words})
        return segs


import ytstudio.phases.ingest as ingest_mod
orig_get_stt = ingest_mod.get_stt
ingest_mod.get_stt = lambda cfg: _DriftedSTT()

CFG = {
    "language": "es", "style": {"preset": "documental_cinematografico"},
    "video": {"width": 640, "height": 360, "fps": 24, "target_minutes": 1,
              "scene_padding": 0.35, "transition": "auto", "burn_subtitles": False,
              "scene_seconds": 5, "overlays": True, "overlay_accent": "E8C46B"},
    "providers": {"llm": {"name": "mock"}, "tts": {"name": "mock"},
                  "stt": {"name": "mock"},
                  "images": {"name": "mock", "size": "1536x1024"},
                  "videogen": {"name": "none", "max_scenes": 0},
                  "music": {"name": "mock", "library_dir": "assets/music"}},
    "reference": {"max_minutes": 12, "video_height": 480},
    "performance": {"parallel_images": 3, "parallel_video": 1, "parallel_tts": 3,
                    "parallel_render": 2},
    "audio": {"music_db": -21, "duck": True, "vo_lufs": -16, "intensity_db": 8,
              "sfx": True, "sfx_db": -18, "end_fade": 1.5, "intro_seconds": 0.8,
              "outro_seconds": 2.0, "scene_breath": 0.3, "sentence_breath": 0.18,
              "trim_silence": False, "silence_keep": 0.4},
    "subtitles": {"max_chars_per_line": 42, "max_lines": 2, "font": "Arial",
                  "font_size": 40},
    "publish": {"enabled": False},
}

print("T1 el pipeline completo digiere un STT con +400ms de deriva")
p = Project.create("drift")
ingest.add_asset(p, voz, "voz")
logs = []
try:
    run_pipeline(p, CFG, to_phase="assembly", log=logs.append)
finally:
    ingest_mod.get_stt = orig_get_stt

p = Project("drift")
# (calibración retirada en v0.24.0 — ver nota de cabecera)
narr = p.get("narration")
seg0 = narr["segments"][0]
# El re-anclaje del primer segmento se retiró junto con la calibración
# (v0.24.0): los tiempos de Whisper se conservan TAL CUAL y la sincronía la
# garantiza el lazo cerrado de subtítulos, que se verifica en T2. Aquí solo
# se comprueba que la narración quedó registrada con sus tiempos crudos.
check("la narración conserva los tiempos crudos del STT (+400ms de deriva)",
      abs(float(seg0["start"]) - 0.7) < 0.15, str(seg0["start"]))

print("T2 los subtítulos caen donde la voz SUENA (medición de contenido)")
evs = el.recent(limit=100, project="drift")
sync_ev = next((e for e in evs if "voz↔subtítulos" in e["message"]), None)
check("la medición de contenido quedó en el log", sync_ev is not None,
      str([e["message"][:60] for e in evs[:8]]))
if sync_ev:
    m = re.search(r"([+-]?\d+) ms", sync_ev["message"])
    med = int(m.group(1)) if m else 9999
    check(f"desfase mediano voz↔subtítulos ≈ 0 (medido: {med:+d} ms)",
          abs(med) <= 200, sync_ev["message"])
warns = p.get("warnings") or []
check("sin aviso de subtítulos desfasados",
      not any("retrasados" in w or "adelantados" in w for w in warns), str(warns))
check("el lazo cerrado de sincronía dejó su medición en el log",
      any("Lazo de sincronía" in e["message"] for e in evs),
      str([e["message"][:60] for e in evs][-6:]))

print("T3 sin deriva el pipeline corre igual (sin tocar los tiempos)")


class _PerfectSTT(_DriftedSTT):
    def transcribe_segments(self, audio):
        segs = super().transcribe_segments(audio)
        for s in segs:
            s["start"] = round(s["start"] - DRIFT, 3)
            s["end"] = round(s["end"] - DRIFT, 3)
            for w in s["words"]:
                w["start"] = round(w["start"] - DRIFT, 3)
                w["end"] = round(w["end"] - DRIFT, 3)
        return segs


ingest_mod.get_stt = lambda cfg: _PerfectSTT()
p2 = Project.create("nodrift")
ingest.add_asset(p2, voz, "voz")
try:
    run_pipeline(p2, CFG, to_phase="voiceover", log=lambda m: None)
finally:
    ingest_mod.get_stt = orig_get_stt
p2 = Project("nodrift")
check("la fase de voz se completó con timestamps ya correctos",
      p2.phase_status("voiceover") == "done", p2.phase_status("voiceover"))
check("no quedó ningún resto de la calibración retirada",
      p2.get("whisper_calibration") is None,
      str(p2.get("whisper_calibration")))

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
