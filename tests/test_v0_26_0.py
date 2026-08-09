"""Batería v0.26.0: modelos económicos + precios por modelo + 10 idiomas +
formatos verticales (Shorts/Reels/TikTok) + editor de escenas.

T1  Catálogo: 10 idiomas con nombre completo; lang_name() da el nombre (no la
    sigla) para el LLM; todo idioma tiene lang3 para el mp4.
T2  Precios por modelo: la estimación con flux-schnell es MUY inferior a la
    de flux-1.1-pro (el ahorro se refleja); ídem video ltx vs kling.
T3  Formatos: crear proyecto con format=short escribe overrides verticales y
    load_config los mezcla (1080x1920, burn_subtitles, subs grandes);
    is_vertical() los detecta. El formato 'long' no toca nada.
T4  Aspecto por formato: los proveedores de imagen/video piden 9:16 con
    config vertical y 16:9 con horizontal.
T5  Editor de escenas: edición visual → rehacer desde montaje; rótulo en modo
    voz-propia re-ancla overlay_at; duración en TTS recompila la línea de
    tiempo y rehace desde subtítulos; con voz propia la duración NO se toca.
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import sys
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


print("T1 idiomas")
from ytstudio.catalog import FORMATS, LANGUAGES, is_vertical, lang_name
codes = [l["code"] for l in LANGUAGES]
check("los 10 idiomas pedidos están",
      set(codes) == {"es", "en", "zh", "hi", "fr", "ar", "bn", "pt", "ru", "de"},
      str(codes))
check("todos tienen nombre completo y lang3",
      all(l.get("label") and l.get("prompt") and l.get("lang3") for l in LANGUAGES))
check("lang_name devuelve el NOMBRE, no la sigla",
      lang_name({"language": "zh"}).startswith("chino") and
      lang_name({"language": "hi"}).startswith("hindi"),
      f"zh={lang_name({'language':'zh'})}")
check("idioma desconocido cae a la sigla sin romper",
      lang_name({"language": "xx"}) == "xx")
from ytstudio.phases.assembly import _LANG3
check("subtítulos mp4: lang3 para hindi/árabe/bengalí",
      _LANG3.get("hi") == "hin" and _LANG3.get("ar") == "ara" and _LANG3.get("bn") == "ben",
      str(_LANG3))

print("T2 precios por modelo reflejan el ahorro")
from ytstudio.estimate import estimate


class _P:  # proyecto mínimo para estimar
    slug = "_t"
    def get(self, k, d=None):
        return {"total_duration": 120, "scene_count": 20}.get(k, d)


def cfg_with(img_model, vid_model="", vid_scenes=0):
    return {"providers": {
        "llm": {"name": "mock"},
        "images": {"name": "replicate", "model": img_model},
        "videogen": {"name": "replicate" if vid_scenes else "none",
                     "model": vid_model, "max_scenes": vid_scenes},
        "tts": {"name": "mock"}, "stt": {"name": "mock"},
        "music": {"name": "library"}},
        "video": {"target_minutes": 2, "scene_seconds": 6},
        "performance": {}}


import os
os.environ.setdefault("REPLICATE_API_TOKEN", "test-token")  # para active()
e_pro = estimate(_P(), cfg_with("black-forest-labs/flux-1.1-pro"))
e_cheap = estimate(_P(), cfg_with("black-forest-labs/flux-schnell"))
img_pro = next(i for i in e_pro["items"] if "Imágenes IA" in i["fase"])
img_cheap = next(i for i in e_cheap["items"] if "Imágenes IA" in i["fase"])
print(f"     flux-1.1-pro: ${img_pro['costo']}  flux-schnell: ${img_cheap['costo']}")
check("flux-schnell estima ~10x más barato que flux-1.1-pro",
      img_cheap["costo"][1] * 5 < img_pro["costo"][0],
      f"{img_cheap['costo']} vs {img_pro['costo']}")
check("el nombre del modelo aparece en la estimación",
      "schnell" in img_cheap["fase"], img_cheap["fase"])
e_kling = estimate(_P(), cfg_with("black-forest-labs/flux-schnell",
                                  "kwaivgi/kling-v2.1", 3))
e_ltx = estimate(_P(), cfg_with("black-forest-labs/flux-schnell",
                                "lightricks/ltx-video", 3))
v_kling = next(i for i in e_kling["items"] if "Video IA" in i["fase"])
v_ltx = next(i for i in e_ltx["items"] if "Video IA" in i["fase"])
print(f"     kling-v2.1: ${v_kling['costo']} {v_kling['minutos']}min  ltx: ${v_ltx['costo']} {v_ltx['minutos']}min")
check("ltx-video estima mucho más barato Y más rápido que kling v2.1",
      v_ltx["costo"][1] < v_kling["costo"][0] and
      v_ltx["minutos"][1] < v_kling["minutos"][0],
      f"{v_ltx} vs {v_kling}")

print("T3 formatos verticales")
check("FORMATS tiene long/short/reel/tiktok",
      # v0.35.0 añadió formatos de Meta Ads: los 4 originales deben SEGUIR,
      # pero el conjunto ya no es exactamente ese (superset permitido).
      {"long", "short", "reel", "tiktok"} <= set(FORMATS))
sv = FORMATS["short"]["overrides"]["video"]
check("short = 1080x1920 con subs quemados",
      sv["width"] == 1080 and sv["height"] == 1920 and sv["burn_subtitles"])
check("long no fuerza overrides", FORMATS["long"]["overrides"] == {})
check("is_vertical detecta 9:16 y no 16:9",
      is_vertical({"video": sv}) and not is_vertical({"video": {"width": 1920, "height": 1080}}))
# crear proyecto con formato y verificar el merge de config real
from ytstudio.webui.server import api_create_project
from ytstudio.config import load_config
from ytstudio.project import PROJECTS_DIR, Project
slug = "__test-v26-short__"
if (PROJECTS_DIR / slug).exists():
    shutil.rmtree(PROJECTS_DIR / slug)
api_create_project({"slug": slug, "text": "idea de prueba", "format": "reel"})
proj = Project(slug)
cfg_merged = load_config(proj.dir)
print(f"     video merge: {cfg_merged['video']['width']}x{cfg_merged['video']['height']} "
      f"target={cfg_merged['video']['target_minutes']}min subs={cfg_merged['subtitles']['font_size']}px")
check("el proyecto guarda su formato", proj.get("format") == "reel")
check("load_config mezcla el override vertical del proyecto",
      cfg_merged["video"]["width"] == 1080 and cfg_merged["video"]["height"] == 1920)
check("duración objetivo de Reel ~1.4 min", abs(cfg_merged["video"]["target_minutes"] - 1.4) < 0.01)
check("subtítulos grandes para vertical", cfg_merged["subtitles"]["font_size"] >= 80)
check("la config GLOBAL sigue 16:9 (no se contaminó)",
      load_config()["video"]["width"] == 1920)

print("T4 aspecto 9:16 en proveedores")
try:
    from ytstudio.providers.images import ReplicateImages
    from ytstudio.providers.videogen import ReplicateVideo
    vcfg = {"providers": {"images": {"model": "m"}, "videogen": {"model": "m"}},
            "video": {"width": 1080, "height": 1920}}
    hcfg = {"providers": {"images": {"model": "m"}, "videogen": {"model": "m"}},
            "video": {"width": 1920, "height": 1080}}
    check("imágenes piden 9:16 en vertical", ReplicateImages(vcfg).aspect == "9:16")
    check("imágenes piden 16:9 en horizontal", ReplicateImages(hcfg).aspect == "16:9")
    check("video pide 9:16 en vertical", ReplicateVideo(vcfg).aspect == "9:16")
except ImportError:
    print("     (lib replicate no instalada aquí: se valida solo la lógica)")
    import re
    src = (ROOT / "ytstudio/providers/images.py").read_text()
    check("images deriva aspect de la config (no 16:9 fijo)",
          'self.aspect' in src and '"aspect_ratio": self.aspect' in src)
    src2 = (ROOT / "ytstudio/providers/videogen.py").read_text()
    check("videogen deriva aspect de la config (no 16:9 fijo)",
          'self.aspect' in src2 and '"aspect_ratio": self.aspect' in src2)

print("T5 editor de escenas")
from ytstudio.webui.server import api_edit_scenes
from ytstudio.phases.scenes import save_scenes
# proyecto TTS (sin audio_start) con 2 escenas y voz ya medida
scenes_tts = [
    {"id": 1, "section": "a", "narration": "uno", "broll_prompt": "x",
     "broll_type": "image", "animation": "zoom_in", "transition": "corte",
     "sfx": "ninguno", "music_intensity": 0.4, "pace": "normal",
     "overlay": None, "on_screen_text": "", "duration": 6.0,
     "vo_duration": 4.0, "vo_file": "vo_001.mp3"},
    {"id": 2, "section": "b", "narration": "dos", "broll_prompt": "y",
     "broll_type": "image", "animation": "static", "transition": "fundido",
     "sfx": "boom", "music_intensity": 0.8, "pace": "normal",
     "overlay": {"type": "dato", "text": "Antes", "kicker": "", "emphasis": ""},
     "on_screen_text": "Antes", "duration": 5.0,
     "vo_duration": 4.0, "vo_file": "vo_002.mp3"},
]
save_scenes(proj, scenes_tts)
for ph in ("subtitles", "assembly"):
    proj.mark_phase(ph, "done", seconds=1)
# 1) edición visual → rehacer desde MONTAJE
r1 = api_edit_scenes(slug, {"edits": [{"id": 1, "animation": "pan_left"}]})
check("edición visual → rerun_from=assembly", r1["rerun_from"] == "assembly", str(r1))
check("la animación quedó guardada",
      Project(slug) and __import__("json").loads(
          (proj.dir / "04_scenes" / "scenes.json").read_text(encoding="utf-8")
      )["scenes"][0]["animation"] == "pan_left")
check("assembly quedó invalidada (pendiente)",
      Project(slug).phase_status("assembly") == "pending")
# 2) duración TTS → recompila línea de tiempo y rehace desde subtítulos
vo_dir = proj.path("voiceover")
import subprocess
for n in ("vo_001.mp3", "vo_002.mp3"):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "aevalsrc=0.2*sin(2*PI*220*t):s=44100:d=4",
                    "-c:a", "libmp3lame", str(vo_dir / n)], check=True)
proj.mark_phase("subtitles", "done", seconds=1)
r2 = api_edit_scenes(slug, {"edits": [{"id": 1, "duration": 9.0}]})
check("duración TTS → rerun_from=subtitles", r2["rerun_from"] == "subtitles", str(r2))
sc = __import__("json").loads((proj.dir / "04_scenes" / "scenes.json")
                              .read_text(encoding="utf-8"))["scenes"]
check("la duración se cuantizó a cuadros y quedó ~9.0", abs(sc[0]["duration"] - 9.0) < 0.05,
      str(sc[0]["duration"]))
from ytstudio.utils.media import probe_duration
tl = vo_dir / "narration_timeline.wav"
check("la línea de tiempo TTS se recompiló a la nueva suma",
      tl.exists() and abs(probe_duration(tl) - (sc[0]["duration"] + sc[1]["duration"])) < 0.1,
      f"{probe_duration(tl) if tl.exists() else '—'} vs {sc[0]['duration']+sc[1]['duration']}")
# 3) duración con VOZ PROPIA → ignorada
scenes_uv = [dict(s, audio_start=0.0 + i * 4, audio_end=4.0 + i * 4)
             for i, s in enumerate(scenes_tts)]
save_scenes(proj, scenes_uv)
r3 = api_edit_scenes(slug, {"edits": [{"id": 1, "duration": 20.0}]})
sc3 = __import__("json").loads((proj.dir / "04_scenes" / "scenes.json")
                               .read_text(encoding="utf-8"))["scenes"]
# las escenas se re-guardaron con duración 6.0; pedir 20.0 debe IGNORARSE
check("con voz propia la duración NO se toca",
      abs(sc3[0]["duration"] - 6.0) < 0.05 and not r3["saved"],
      f"dur={sc3[0]['duration']} (r={r3})")
# 4) quitar un rótulo
r4 = api_edit_scenes(slug, {"edits": [{"id": 2, "overlay_text": ""}]})
sc4 = __import__("json").loads((proj.dir / "04_scenes" / "scenes.json")
                               .read_text(encoding="utf-8"))["scenes"]
check("rótulo eliminado al vaciar el texto", sc4[1]["overlay"] is None, str(sc4[1]["overlay"]))

shutil.rmtree(PROJECTS_DIR / slug, ignore_errors=True)
print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
