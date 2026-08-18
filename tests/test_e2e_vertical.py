"""Integración end-to-end VERTICAL (v0.63.0): monta un Short completo en modo
mock y comprueba en el ARCHIVO REAL —no en la configuración— que:

- los subtítulos quemados dejan libre la franja inferior que la app reserva al
  enlace al video largo,
- la sonoridad del video terminado cae en el objetivo aunque la voz de partida
  venga muy baja (aquí se graba a propósito casi inaudible),
- el pico real se queda por debajo del techo,
- y el montaje deja guardadas la auditoría y la medición.

No usa claves ni internet. Necesita ffmpeg."""
import re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
WORK = Path(tempfile.mkdtemp(prefix="vert_e2e_"))
import ytstudio.project as prj; prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el; el.LOG_PATH = WORK / "data" / "events.log"
from ytstudio.project import Project
from ytstudio.phases import ingest
from ytstudio.pipeline import run_pipeline

bursts = [(0.4,3.0),(3.4,6.5),(7.0,10.0),(10.4,13.6)]
expr = "+".join(f"between(t\\,{a}\\,{b})" for a,b in bursts)
voz = WORK/"voz.wav"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi",
  "-i", f"aevalsrc=0.05*sin(2*PI*180*t)*({expr}):s=44100:d=14.0",
  "-c:a","pcm_s16le",str(voz)], check=True)

p = Project.create("vert"); ingest.add_asset(p, voz, "voz")
cfg = {"language":"es","style":{"preset":"documental_cinematografico"},
 "video":{"width":1080,"height":1920,"fps":24,"target_minutes":1,"scene_padding":0.35,
   "transition":"auto","burn_subtitles":True,"scene_seconds":5,"overlays":True,
   "overlay_accent":"E8C46B"},
 "providers":{"llm":{"name":"mock"},"tts":{"name":"mock"},"stt":{"name":"mock"},
   "images":{"name":"mock","size":"1024x1536"},"videogen":{"name":"none","max_scenes":0},
   "music":{"name":"mock","library_dir":"assets/music"}},
 "reference":{"max_minutes":12,"video_height":480},
 "performance":{"parallel_images":3,"parallel_video":1,"parallel_tts":3,"parallel_render":2},
 "audio":{"music_db":-21,"duck":True,"vo_lufs":-16,"intensity_db":8,"sfx":True,
   "sfx_db":-18,"end_fade":1.5,"intro_seconds":0.8,"outro_seconds":2.0,
   "scene_breath":0.3,"sentence_breath":0.18,"trim_silence":True,"silence_keep":0.4,
   "target_lufs":-14,"target_tp":-1.0,"final_gain_db":1.0,"final_limit":0.9},
 "subtitles":{"max_chars_per_line":20,"max_lines":2,"font":"Arial","font_size":80,
   "safe_zone":True},
 "publish":{"enabled":False}}

logs=[]
try:
    run_pipeline(p, cfg, to_phase="assembly", log=logs.append)
except Exception as e:
    print("PIPELINE FALLÓ:", e); print("\n".join(logs[-30:])); sys.exit(1)

fails=[]
def ck(n,c,d=""):
    print(f"[{'OK ' if c else 'FAIL'}] {n}" + (f" — {d}" if d and not c else ""))
    if not c: fails.append(n)

ass = (p.dir/"08_subtitles"/"subtitulos.ass").read_text(encoding="utf-8")
style = [l for l in ass.splitlines() if l.startswith("Style: Default")][0]
mv = int(style.split(",")[-2])
ck("el .ass real deja libre la franja del enlace (MarginV>=430)", mv>=430, f"MarginV={mv}")
ck("y respeta el aire lateral (90 px)", int(style.split(",")[-4])>=90, style.split(",")[-4])

from ytstudio.utils.media import measure_loudness
final = Path(p.get("final_video"))
m = measure_loudness(final)
ck("el video vertical sale medido en el objetivo -14 LUFS",
   m and abs(m["input_i"]+14.0)<=1.0, str(m))
ck("y con el pico real por debajo de -1,0 dBTP",
   m and m["input_tp"]<=-1.0, str(m))

a = p.get("shorts_audit")
ck("el montaje dejó guardada la auditoría del vertical", bool(a))
ck("y no reporta problemas", a and not a["problemas"], str((a or {}).get("problemas")))
ck("la sonoridad quedó registrada en el proyecto", bool(p.get("loudness")), str(p.get("loudness")))
ck("el registro de eventos cuenta la corrección de sonoridad",
   "Sonoridad del video final" in el.raw_text())

print("\n" + ("✘ " + ", ".join(fails) if fails else "✔ E2E VERTICAL EN VERDE"))
sys.exit(1 if fails else 0)
