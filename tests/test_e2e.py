"""Integración end-to-end con VOZ PROPIA en modo mock: confirma que el motor
de tiempos v24, los subtítulos por mapa global, el montaje y el log de eventos
encajan sin errores y producen un video final."""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_e2e_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el
el.LOG_PATH = WORK / "data" / "events.log"

from ytstudio.project import Project
from ytstudio.phases import ingest
from ytstudio.pipeline import run_pipeline

# Narración sintética de ~14s con ráfagas y huecos reales
bursts = [(0.4, 3.0), (3.4, 6.5), (7.0, 10.0), (10.4, 13.6)]
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in bursts)
voz = WORK / "voz.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", f"aevalsrc=0.4*sin(2*PI*180*t)*({expr}):s=44100:d=14.0",
                "-c:a", "pcm_s16le", str(voz)], check=True)

p = Project.create("e2e")
ingest.add_asset(p, voz, "voz")

cfg = {
    "language": "es",
    "style": {"preset": "documental_cinematografico"},
    "video": {"width": 640, "height": 360, "fps": 24, "target_minutes": 1,
              "scene_padding": 0.35, "transition": "auto", "burn_subtitles": True,
              "scene_seconds": 5, "overlays": True, "overlay_accent": "E8C46B"},
    "providers": {
        "llm": {"name": "mock"}, "tts": {"name": "mock"}, "stt": {"name": "mock"},
        "images": {"name": "mock", "size": "1536x1024"},
        "videogen": {"name": "none", "max_scenes": 0},
        "music": {"name": "mock", "library_dir": "assets/music"},
    },
    "reference": {"max_minutes": 12, "video_height": 480},
    "performance": {"parallel_images": 3, "parallel_video": 1, "parallel_tts": 3,
                    "parallel_render": 2},
    "audio": {"music_db": -21, "duck": True, "vo_lufs": -16, "intensity_db": 8,
              "sfx": True, "sfx_db": -18, "end_fade": 1.5, "intro_seconds": 0.8,
              "outro_seconds": 2.0, "scene_breath": 0.3, "sentence_breath": 0.18,
              "trim_silence": True, "silence_keep": 0.4},
    "subtitles": {"max_chars_per_line": 42, "max_lines": 2, "font": "Arial",
                  "font_size": 40},
    "publish": {"enabled": False},
}

logs = []
try:
    run_pipeline(p, cfg, to_phase="assembly", log=logs.append)
except Exception as e:
    print("PIPELINE FALLÓ:", e)
    print("\n".join(logs[-25:]))
    sys.exit(1)

final = p.get("final_video")
ok = final and Path(final).exists() and Path(final).stat().st_size > 5000
print("video final:", final, "->", "OK" if ok else "FALTA")

# El proyecto usó la narración propia (voice_map presente) y quedó sincronía
vm = p.get("voice_map")
print("voice_map:", "presente" if vm else "AUSENTE",
      f"({len(vm['insertions'])} inserciones)" if vm else "")

# Eventos registrados (novedades + tiempos por fase + fin)
evs = el.recent(limit=200, project="e2e")
phases_timed = {e.get("phase") for e in evs if e.get("seconds") is not None}
print("eventos:", len(evs), "| fases con tiempo:", sorted(x for x in phases_timed if x))
has_start = any("iniciada" in e["message"] for e in evs)
has_end = any("finalizada" in e["message"] for e in evs)

assert ok, "no se generó el video final"
assert vm is not None, "no se usó la narración propia"
assert len(evs) >= 8, "faltan eventos en el log"
assert has_start and has_end, "faltan eventos de inicio/fin"
assert "voiceover" in phases_timed and "assembly" in phases_timed, "faltan tiempos por fase"

# Sincronía global: duración del video ≈ suma de duraciones de escena
from ytstudio.utils.media import probe_duration
from ytstudio.phases.scenes import load_scenes
scenes = load_scenes(p)
sum_durs = sum(s["duration"] for s in scenes)
vdur = probe_duration(Path(final))
print(f"duración video={vdur:.2f}s  suma escenas={sum_durs:.2f}s")
assert abs(vdur - sum_durs) < 0.5, f"desfase de duración {vdur} vs {sum_durs}"

shutil.rmtree(WORK, ignore_errors=True)
print("\nE2E EN VERDE ✔")
