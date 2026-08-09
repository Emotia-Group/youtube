"""Batería v0.21.0: arquitectura de UNA SOLA LÍNEA DE TIEMPO.

La causa raíz demostrada: escenas mp4 con pista AAC propia → el contenedor
corría los cuadros +23ms por transición (cortes/rótulos tarde vs voz/subs).
Verifica: escenas SOLO video, pista de voz continua en AMBOS modos (propia y
TTS), cuerpo exacto al cuadro, y autocomprobación de punta a punta."""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path



WORK = Path(tempfile.mkdtemp(prefix="ytstudio_v0210_"))
import ytstudio.project as prj
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el
el.LOG_PATH = WORK / "data" / "events.log"

from ytstudio.project import Project
from ytstudio.phases import ingest
from ytstudio.pipeline import run_pipeline
from ytstudio.utils.media import probe_duration

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def audio_streams(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=codec_type", "-of", "json",
                        str(f)], capture_output=True, text=True)
    return len(json.loads(r.stdout).get("streams", []))


CFG = {
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


def verify(slug, mode):
    p = Project(slug)
    scenes_dir = p.dir / "09_final" / "escenas"
    mp4s = sorted(scenes_dir.glob("scene_*.mp4"))
    check(f"[{mode}] escenas renderizadas", len(mp4s) >= 2, str(len(mp4s)))
    check(f"[{mode}] TODAS las escenas SIN pista de audio",
          all(audio_streams(m) == 0 for m in mp4s),
          str([(m.name, audio_streams(m)) for m in mp4s]))
    # cuerpo exacto al cuadro
    from ytstudio.phases.scenes import load_scenes
    scenes = load_scenes(p)
    fps = 24.0
    expected = sum(max(1, round(float(s["duration"]) * fps)) for s in scenes) / fps
    body = p.dir / "09_final" / "cuerpo.mp4"
    bd = probe_duration(body)
    check(f"[{mode}] cuerpo EXACTO ({bd:.4f}s vs {expected:.4f}s)",
          abs(bd - expected) <= 1.5 / fps, f"drift={1000*(bd-expected):+.1f}ms")
    # pista de voz continua presente y de la longitud del cuerpo (± pad)
    tl = p.get("voice_timeline")
    tlp = p.path("voiceover", tl) if tl else None
    check(f"[{mode}] pista de voz continua presente", tlp and tlp.exists(), str(tl))
    if tlp and tlp.exists():
        td = probe_duration(tlp)
        check(f"[{mode}] pista de voz ≈ cuerpo ({td:.3f}s vs {bd:.3f}s)",
              abs(td - bd) < 0.35, f"diff={td-bd:+.3f}")
    # sin avisos de autocomprobación fallida
    warns = p.get("warnings") or []
    check(f"[{mode}] autocomprobaciones en verde (sin avisos de deriva)",
          not any("Autocomprobación" in w for w in warns), str(warns))
    final = p.get("final_video")
    check(f"[{mode}] video final generado",
          final and Path(final).exists() and Path(final).stat().st_size > 5000)
    fd = probe_duration(Path(final))
    check(f"[{mode}] video final == cuerpo ({fd:.3f}s vs {bd:.3f}s)",
          abs(fd - bd) <= 0.25, f"diff={fd-bd:+.3f}")


# ---------- MODO 1: narración propia -------------------------------------
print("MODO 1: narración propia (voz del usuario)")
bursts = [(0.4, 3.0), (3.4, 6.5), (7.0, 10.0), (10.4, 13.6)]
expr = "+".join(f"between(t\\,{a}\\,{b})" for a, b in bursts)
voz = WORK / "voz.wav"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", f"aevalsrc=0.4*sin(2*PI*180*t)*({expr}):s=44100:d=14.0",
                "-c:a", "pcm_s16le", str(voz)], check=True)
p1 = Project.create("e2e-voz")
ingest.add_asset(p1, voz, "voz")
logs1 = []
run_pipeline(p1, CFG, to_phase="assembly", log=logs1.append)
verify("e2e-voz", "voz propia")
check("[voz propia] el log confirma la verificación de sincronía",
      any("Sincronía verificada" in l for l in logs1),
      "\n".join(logs1[-6:]))

# ---------- MODO 2: TTS (guion escrito, voz sintética) --------------------
print("MODO 2: guion escrito + voz TTS")
p2 = Project.create("e2e-tts")
ingest.set_text_input(p2, "Este es un guion de prueba para validar la voz "
                          "sintética con la nueva línea de tiempo unificada. "
                          "Cada escena debe quedar perfectamente sincronizada "
                          "con los subtítulos y la música de fondo del video.")
logs2 = []
run_pipeline(p2, CFG, to_phase="assembly", log=logs2.append)
verify("e2e-tts", "TTS")
check("[TTS] el log confirma la verificación de sincronía",
      any("Sincronía verificada" in l for l in logs2),
      "\n".join(logs2[-6:]))

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
