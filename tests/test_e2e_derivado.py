"""Integración end-to-end de un SHORT DERIVADO (v0.64.0): saca un Short de un
video largo y lo genera entero en modo prueba, comprobando en el ARCHIVO REAL
que sale vertical, por debajo del minuto, medido y apuntando a su origen.

Es la prueba que de verdad importa de la función: que un Short salido de un
video largo no solo se proponga bien, sino que se GENERE.

No usa claves ni internet. Necesita ffmpeg.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WORK = Path(tempfile.mkdtemp(prefix="e2e_deriv_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el  # noqa: E402
el.LOG_PATH = WORK / "data" / "events.log"

import yaml  # noqa: E402

from ytstudio import derive, shorts  # noqa: E402
from ytstudio.config import _deep_merge  # noqa: E402
from ytstudio.pipeline import run_pipeline  # noqa: E402
from ytstudio.project import DIRS, Project  # noqa: E402
from ytstudio.utils.media import probe_duration  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


# --- un video largo ya generado, con sus escenas y su enlace de YouTube
p = Project.create("largo")
p.set("metadata", {"title": "La historia que nadie contó"})
p.set("youtube_id", "ABC123XYZ")
p.set("concept", {"angle": "Investigación", "tone": "Sobrio",
                  "audience": "Adultos"})
(p.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": i, "section": "Desarrollo", "duration": 30.0,
     "narration": f"Frase número {i} de la narración."}
    for i in range(1, 31)]}), encoding="utf-8")

CFG_MOCK = {"language": "es", "providers": {"llm": {"name": "mock"}}}
source = derive.source_from_project("largo")
candidatos = derive.propose(source, CFG_MOCK, n=3)
slug = derive.create_short_project(candidatos[0], CFG_MOCK)
print(f"Short derivado: {slug} · objetivo {candidatos[0]['duracion']}s")

BASE = {
    "language": "es", "style": {"preset": "documental_cinematografico"},
    "video": {"width": 1920, "height": 1080, "fps": 24, "target_minutes": 10,
              "scene_padding": 0.35, "transition": "auto",
              "burn_subtitles": False, "scene_seconds": 6, "overlays": True,
              "overlay_accent": "E8C46B"},
    "providers": {"llm": {"name": "mock"}, "tts": {"name": "mock"},
                  "stt": {"name": "mock"},
                  "images": {"name": "mock", "size": "1536x1024"},
                  "videogen": {"name": "none", "max_scenes": 0},
                  "music": {"name": "mock", "library_dir": "assets/music"}},
    "reference": {"max_minutes": 12, "video_height": 480},
    "performance": {"parallel_images": 3, "parallel_video": 1,
                    "parallel_tts": 3, "parallel_render": 2},
    "audio": {"music_db": -21, "duck": True, "vo_lufs": -16,
              "intensity_db": 8, "sfx": True, "sfx_db": -18, "end_fade": 1.5,
              "intro_seconds": 0.8, "outro_seconds": 2.0, "scene_breath": 0.3,
              "sentence_breath": 0.18, "trim_silence": True,
              "silence_keep": 0.4, "target_lufs": -14, "target_tp": -1.0,
              "final_gain_db": 1.0, "final_limit": 0.9},
    "subtitles": {"max_chars_per_line": 42, "max_lines": 2, "font": "Arial",
                  "font_size": 54, "safe_zone": True},
    "publish": {"enabled": False},
}
q = Project(slug)
cfg = _deep_merge(BASE, yaml.safe_load(
    (q.dir / "config.yaml").read_text(encoding="utf-8")))

logs = []
try:
    run_pipeline(q, cfg, to_phase="assembly", log=logs.append)
except Exception as e:
    print("PIPELINE FALLÓ:", e)
    print("\n".join(logs[-25:]))
    sys.exit(1)

brief = q.get("brief") or {}
check("el guion derivado entra como GUION, no como idea",
      brief.get("input_type") == "script", str(brief.get("input_type")))
guion = (q.dir / DIRS["script"] / "guion.md").read_text(encoding="utf-8")
check("y el guion del Short se respeta palabra por palabra",
      candidatos[0]["guion"].split(".")[0] in guion, guion[:100])

final = Path(q.get("final_video"))
dur = probe_duration(final)
info = shorts.probe(final)
check("el video sale vertical 1080x1920",
      (info["width"], info["height"]) == (1080, 1920), str(info))
check("dura menos de 60 s (por encima, una reclamación lo bloquea)",
      dur < 60, f"{dur:.1f}s")
check("y no es un recorte inútil de tres segundos", dur > 15, f"{dur:.1f}s")
check("se parece a la duración pedida",
      abs(dur - candidatos[0]["duracion"]) < 20,
      f"{dur:.1f}s vs {candidatos[0]['duracion']}s")

audit = q.get("shorts_audit")
check("el montaje lo auditó solo", bool(audit))
check("y no encontró problemas", audit and not audit["problemas"],
      str((audit or {}).get("problemas")))
loud = q.get("loudness") or {}
check("la sonoridad quedó en el objetivo",
      loud.get("lufs") is not None and abs(loud["lufs"] + 14) <= 1.0,
      str(loud))
check("SIGUE apuntando al video largo (sin eso, la vista se regala)",
      (q.get("derived_from") or {}).get("url") == "https://youtu.be/ABC123XYZ",
      str(q.get("derived_from")))

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print(f"✔ El Short derivado se genera completo ({dur:.1f}s vertical).")
