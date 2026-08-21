"""Batería v0.69.0 — el Estudio de series animadas.

Lo que el creador pidió, y esta batería comprueba que ya está:

1.  SERIES CON BIBLIA PROPIA. Crear serie (audiencia niños/adultos) con
    personajes (rasgos + VESTIMENTA + personalidad + voz + fotos/videos),
    locaciones con referencia, escenas recurrentes, jingle, canciones y
    voces — todo en data/series/, fuera de Git.
2.  COHERENCIA ENTRE EPISODIOS. Al crear un episodio, la biblia se
    materializa dentro del proyecto: elenco con sus fotos, locaciones con
    sus referencias, mapa de voces por personaje, voz del narrador y jingle.
3.  CADA PERSONAJE HABLA CON SU VOZ Y SE ANIMA CON SU CARA. El director
    etiqueta hablante y locación por escena (schema + saneo), toda escena
    con hablante del elenco se genera como personaje (lipsync propio), y las
    etiquetas de diálogo no se leen en voz alta.
4.  EL JINGLE ABRE EL EPISODIO. Se mezcla al frente de la música ya elegida
    sin cambiar la duración del video.
5.  EL DIRECTOR DE LA SERIE analiza un guion: qué se reutiliza, qué se
    generará una única vez y qué falta por resolver.
6.  CLONACIONES. «Clonarme» crea un personaje-avatar desde fotos/videos;
    «Clonar mi voz» degrada con claridad a MUESTRA cuando no hay clave de
    ElevenLabs.
7.  API + INTERFACES. Las rutas /api/series existen y las DOS plantillas
    traen la pantalla de Series con todas las opciones pedidas.

Ninguna prueba usa claves ni internet.
"""

import base64
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


WORK = Path(tempfile.mkdtemp(prefix="v0690_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as elog  # noqa: E402
elog.LOG_PATH = WORK / "data" / "events.log"
import ytstudio.series as se  # noqa: E402
se.SERIES_DIR = WORK / "data" / "series"

from ytstudio import locations as loc_mod  # noqa: E402
from ytstudio.catalog import FORMATS  # noqa: E402
from ytstudio.project import Project  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfalso-para-pruebas").decode()

CFG = {"language": "es",
       "video": {"width": 1920, "height": 1080, "fps": 24,
                 "scene_seconds": 6, "scene_padding": 0.35},
       "audio": {"outro_seconds": 2.0},
       "performance": {"parallel_tts": 2},
       "providers": {"llm": {"name": "mock"}, "tts": {"name": "mock"},
                     "stt": {"name": "mock"}, "images": {"name": "mock"},
                     "videogen": {"name": "none"}, "lipsync": {"name": "none"},
                     "music": {"name": "mock"}}}

# ---------------------------------------------------------------------------
# T1 — la biblia de la serie: CRUD completo
# ---------------------------------------------------------------------------
print("T1 crear serie, personajes, locaciones, escenas, música y voces")

serie = se.create_serie({"name": "Los Amigos del Bosque",
                         "description": "aventuras en el bosque",
                         "audience": "ninos"})
check("T1a la serie se crea con su id y su audiencia",
      serie["id"].startswith("sr_") and serie["audience"] == "ninos")
try:
    se.create_serie({"name": "los amigos del bosque"})
    check("T1b el nombre repetido se rechaza", False)
except ValueError as e:
    check("T1b el nombre repetido se rechaza", "Ya existe" in str(e))

lola = se.add_character(serie["id"], {
    "name": "Lola", "description": "zorrita roja de ojos grandes",
    "clothing": "bufanda azul y botas amarillas", "personality": "curiosa",
    "voice": {"provider": "elevenlabs", "voice_id": "vozLola123"}},
    [{"name": "lola.png", "data_base64": PNG}])
check("T1c el personaje guarda rasgos, VESTIMENTA, personalidad y voz",
      lola["clothing"].startswith("bufanda")
      and lola["voice"]["voice_id"] == "vozLola123" and len(lola["images"]) == 1)
check("T1d sus fotos viven en la carpeta de la serie",
      (se.serie_dir(serie["id"]) / lola["images"][0]).exists())

tato = se.add_character(serie["id"], {"name": "Tato", "narrator": True})
se.update_character(serie["id"], lola["id"], {"narrator": True})
s2 = se.load_serie(serie["id"])
narradores = [c["name"] for c in s2["characters"] if c.get("narrator")]
check("T1e el rol de narrador es único (pasa de Tato a Lola)",
      narradores == ["Lola"])

cueva = se.add_location(serie["id"], {
    "name": "La Cueva", "description": "cueva cálida con cristales",
    "ambience": "goteo de agua"}, [{"name": "cueva.png", "data_base64": PNG}])
check("T1f la locación guarda descripción, ambiente e imágenes",
      cueva["ambience"] == "goteo de agua" and len(cueva["images"]) == 1)

esc = se.add_scene(serie["id"], {"name": "El desayuno", "location": "La Cueva",
                                 "characters": ["Lola", "Tato"],
                                 "description": "desayunan juntos"})
check("T1g la escena recurrente enlaza locación y personajes",
      esc["location"] == "La Cueva" and esc["characters"] == ["Lola", "Tato"])

se.set_music(serie["id"], "jingle", {"name": "jingle.mp3", "data_base64": PNG})
se.set_music(serie["id"], "cancion", {"name": "tema.mp3", "data_base64": PNG})
s2 = se.load_serie(serie["id"])
check("T1h el jingle y la canción quedan guardados",
      s2["jingle"] and len(s2["songs"]) == 1)
se.set_music(serie["id"], "jingle", {"name": "jingle2.mp3", "data_base64": PNG})
s2 = se.load_serie(serie["id"])
check("T1i subir OTRO jingle reemplaza al anterior (solo hay uno)",
      "jingle2" in s2["jingle"] and len(s2["songs"]) == 1)

voz, hint = se.add_voice(serie["id"], "Mi voz",
                         [{"name": "muestra.mp3", "data_base64": PNG}],
                         clone=True)
check("T1j sin clave de ElevenLabs la voz queda como MUESTRA, avisando",
      voz["kind"] == "muestra" and "clave" in hint.lower())
check("T1k resolve_voice traduce la referencia vz_ a una voz utilizable",
      se.resolve_voice(s2, {"voice_id": voz["id"]}) is None  # muestra: aún no habla
      and se.resolve_voice(s2, {"provider": "openai", "voice_id": "onyx"})
      == {"provider": "openai", "voice_id": "onyx"})

se.delete_character(serie["id"], tato["id"])
check("T1l borrar un personaje borra también su carpeta",
      not (se.serie_dir(serie["id"]) / "personajes" / tato["id"]).exists())

# «Clonarme»: personaje-avatar a partir de material propio
avatar = se.clone_avatar(serie["id"], "Yo", [{"name": "yo.png",
                                              "data_base64": PNG}])
check("T1m «Clonarme» crea un personaje-avatar con mis fotos",
      avatar["name"] == "Yo" and len(avatar["images"]) == 1)

# ---------------------------------------------------------------------------
# T2 — materializar la biblia dentro de un episodio
# ---------------------------------------------------------------------------
print("\nT2 el episodio nace con la biblia de la serie puesta")

se.update_serie(serie["id"], {"narrator_voice": {"provider": "openai",
                                                 "voice_id": "onyx"}})
serie_full = se.load_serie(serie["id"])
ep = Project.create("bosque-ep-01")
se.materialize_episode(ep, serie_full, 1, "El tesoro del río")

chars = ep.get("characters") or []
lola_ep = next((c for c in chars if c["name"] == "Lola"), None)
check("T2a el elenco entra al episodio con sus fotos como assets",
      lola_ep is not None and len(lola_ep["asset_ids"]) == 1)
check("T2b la vestimenta viaja en la descripción (es parte de la identidad)",
      "bufanda azul" in (lola_ep or {}).get("description", ""))
check("T2c las locaciones entran con sus referencias copiadas",
      (ep.get("locations") or [{}])[0].get("ref_files")
      and (ep.path("broll") / ep.get("locations")[0]["ref_files"][0]).exists())
vc = ep.get("voice_cast") or {}
check("T2d el mapa de voces por personaje usa nombres sin acentos",
      vc.get("lola", {}).get("voice_id") == "vozLola123")
check("T2e la voz del narrador queda como override del episodio",
      "onyx" in (ep.dir / "config.yaml").read_text(encoding="utf-8"))
check("T2f el jingle y las canciones se copian a la carpeta de música",
      ep.get("serie_jingle") and (ep.path("music") / ep.get("serie_jingle")).exists()
      and len(ep.get("serie_songs") or []) == 1)
serie_full = se.load_serie(serie["id"])
check("T2g el episodio queda registrado en la serie",
      serie_full["episodes"] and serie_full["episodes"][0]["slug"] == "bosque-ep-01"
      and serie_full["episodes"][0]["title"] == "El tesoro del río")
tracks = se.series_tracks(ep)
check("T2h las canciones de la serie entran a la selección musical",
      len(tracks) == 1 and "canción de la serie" in tracks[0]["title"])
check("T2i las locaciones del episodio se leen con el módulo de locaciones",
      len(loc_mod.references_for(ep, CFG, ["la cueva"])) == 1)
check("T2j los bloques del guionista y del director llevan la biblia",
      "Lola" in se.series_script_block(ep) and "La Cueva" in se.series_scene_block(ep)
      and "speaker" in se.series_scene_block(ep))

# ---------------------------------------------------------------------------
# T3 — el formato «serie» en el catálogo y el API
# ---------------------------------------------------------------------------
print("\nT3 el formato de episodio de serie, en el catálogo y el API")

check("T3a el formato 'serie' existe y es largo 16:9",
      "serie" in FORMATS and "Serie animada" in FORMATS["serie"]["label"])
check("T3b el episodio deja aire para el jingle (intro más larga)",
      FORMATS["serie"]["overrides"]["audio"]["intro_seconds"] >= 3.0)

from ytstudio.webui import server as srv  # noqa: E402

cfg_api = srv.api_get_config()
check("T3c el API declara que 'serie' NO es formato corto",
      cfg_api["formats"]["serie"]["short"] is False
      and cfg_api["formats"]["serie"]["serie"] is True
      and cfg_api["formats"]["short"]["short"] is True)

r = srv.api_create_project({"slug": "bosque-ep-02", "text": "Lola: ¡hola!",
                            "serie_id": serie["id"], "episode_number": 2,
                            "episode_title": "La tormenta"})
ep2 = Project("bosque-ep-02")
check("T3d crear un proyecto con serie_id lo convierte en episodio",
      r.get("serie_id") == serie["id"] and ep2.get("format") == "serie"
      and ep2.get("episode_number") == 2)
check("T3e el episodio nace con el elenco materializado",
      any(c["name"] == "Lola" for c in ep2.get("characters") or []))

detail = srv.api_series_detail(serie["id"])
check("T3f la ficha de la serie enseña sus episodios con estado",
      len(detail["episodes"]) == 2
      and all("done" in e or e.get("missing") for e in detail["episodes"]))

rutas = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
for ruta in ("/api/series", "clone-avatar", "series-files", "/analyze"):
    check(f"T3g la ruta «{ruta}» está en el servidor", ruta in rutas)

# ---------------------------------------------------------------------------
# T4 — el director etiqueta hablante y locación, y reparte los planos
# ---------------------------------------------------------------------------
print("\nT4 hablante y locación por escena, sin confundir identidades")

from ytstudio.phases.scenes import (SCENES_SCHEMA, _assign_shots,  # noqa: E402
                                    _normalize_cast, _schema_with_cast)

schema = _schema_with_cast(SCENES_SCHEMA, ["Lola", "Yo"],
                           location_names=["La Cueva"], series_mode=True)
props = schema["properties"]["scenes"]["items"]["properties"]
req = schema["properties"]["scenes"]["items"]["required"]
check("T4a el schema del director exige speaker y location en episodios",
      "speaker" in props and "location" in props
      and "speaker" in req and "location" in req)
check("T4b el hablante solo puede ser del elenco (o el Narrador)",
      set(props["speaker"]["enum"]) == {"Lola", "Yo", "Narrador"}
      and set(props["location"]["enum"]) == {"La Cueva", "ninguna"})
check("T4c sin elenco, el schema queda intacto (nada cambia para el resto)",
      _schema_with_cast(SCENES_SCHEMA, []) is SCENES_SCHEMA)

escenas = [
    {"id": 1, "speaker": "  lola ", "characters": [], "location": "LA CUEVA"},
    {"id": 2, "speaker": "Desconocido", "characters": ["Lola"],
     "location": "el mar"},
    {"id": 3, "speaker": "Narrador", "characters": [], "location": "ninguna"},
]
_normalize_cast(escenas, ["Lola", "Yo"], location_names=["La Cueva"])
check("T4d el hablante se sanea y SIEMPRE aparece en su escena",
      escenas[0]["speaker"] == "Lola" and escenas[0]["characters"] == ["Lola"])
check("T4e un hablante desconocido cae al Narrador; una locación falsa, a nada",
      escenas[1]["speaker"] == "Narrador" and escenas[1]["location"] is None
      and escenas[0]["location"] == "La Cueva")

_assign_shots(ep, escenas, CFG)
check("T4f en un episodio, quien habla SALE en pantalla (lipsync propio)",
      escenas[0]["shot"] == "personaje" and escenas[1]["shot"] == "broll"
      and escenas[2]["shot"] == "broll")

from ytstudio.phases.broll import _character_plate  # noqa: E402
import inspect  # noqa: E402
check("T4g cada personaje tiene su propia lámina (stem por personaje)",
      "stem" in inspect.signature(_character_plate).parameters)

# ---------------------------------------------------------------------------
# T5 — cada personaje habla con SU voz; las etiquetas no se leen
# ---------------------------------------------------------------------------
print("\nT5 voz por personaje y etiquetas de diálogo fuera del audio")

from ytstudio.phases.voiceover import strip_speaker_labels  # noqa: E402

texto = "Lola: ¡Vamos a la cueva!\nNarrador: Y así empezó todo."
limpio = strip_speaker_labels(texto, {"Lola", "Narrador"})
check("T5a las etiquetas «Nombre:» no se leen en voz alta",
      "Lola:" not in limpio and "Narrador:" not in limpio
      and "¡Vamos a la cueva!" in limpio)
check("T5b solo se quitan nombres conocidos (no cualquier «palabra:»)",
      "Hora: 15:00" in strip_speaker_labels("Hora: 15:00", {"Lola"}))

if HAS_FFMPEG:
    from ytstudio.phases.scenes import save_scenes  # noqa: E402
    from ytstudio.phases import voiceover  # noqa: E402
    ep3 = Project.create("bosque-ep-03")
    ep3.set("serie_id", serie["id"])
    ep3.set("voice_cast", {"lola": {"provider": "elevenlabs",
                                    "voice_id": "vozLola123",
                                    "name": "Lola"}})
    ep3.set("characters", [{"id": "ch1", "name": "Lola", "description": "",
                            "asset_ids": [], "narrator": True}])
    save_scenes(ep3, [
        {"id": 1, "narration": "Lola: ¡Hola amigos del bosque!",
         "speaker": "Lola", "pace": "normal"},
        {"id": 2, "narration": "Narrador: Y todos rieron felices.",
         "speaker": "Narrador", "pace": "normal"},
    ])
    voiceover.run(ep3, CFG)
    vo_dir = ep3.path("voiceover")
    check("T5c la fase de voz genera cada escena y la pista continua",
          (vo_dir / "vo_001.mp3").exists() and (vo_dir / "vo_002.mp3").exists()
          and (vo_dir / "narration_timeline.wav").exists())
    check("T5d las duraciones quedan medidas para el montaje",
          ep3.get("total_duration") and ep3.get("total_duration") > 0)
else:
    print("     (sin ffmpeg: se omite la corrida de la fase de voz)")

# ---------------------------------------------------------------------------
# T6 — el jingle abre el episodio sin cambiar la duración
# ---------------------------------------------------------------------------
print("\nT6 el jingle de la serie, mezclado al frente de la música")

if HAS_FFMPEG:
    from ytstudio.phases.music import _apply_jingle  # noqa: E402
    from ytstudio.utils.media import make_silence, probe_duration  # noqa: E402
    ep4 = Project.create("bosque-ep-04")
    make_silence(ep4.path("music") / "musica.mp3", 12.0)
    make_silence(ep4.path("music") / "jingle_serie.mp3", 4.0)
    ep4.set("music_file", "musica.mp3")
    ep4.set("serie_jingle", "jingle_serie.mp3")
    _apply_jingle(ep4, CFG)
    con = ep4.path("music") / "musica_con_jingle.mp3"
    check("T6a la mezcla con jingle existe y pasa a ser LA música del episodio",
          con.exists() and ep4.get("music_file") == "musica_con_jingle.mp3")
    if con.exists():
        check("T6b la duración del video no cambia (el jingle se mezcla)",
              abs(probe_duration(con) - 12.0) < 0.6,
              f"duró {probe_duration(con):.2f}s")
    antes = con.stat().st_mtime if con.exists() else 0
    _apply_jingle(ep4, CFG)
    check("T6c re-ejecutar no re-mezcla (reanudable)",
          con.exists() and con.stat().st_mtime == antes)
else:
    print("     (sin ffmpeg: se omite la mezcla del jingle)")

# Sin jingle no pasa nada: la música queda intacta
ep5 = Project.create("bosque-ep-05")
ep5.set("music_file", "musica.mp3")
from ytstudio.phases.music import _apply_jingle as _aj  # noqa: E402
_aj(ep5, CFG)
check("T6d un proyecto sin jingle sigue igual que siempre",
      ep5.get("music_file") == "musica.mp3")

# ---------------------------------------------------------------------------
# T7 — el director de la serie analiza el guion
# ---------------------------------------------------------------------------
print("\nT7 el informe del director: reutilizar, generar, resolver")

serie_full = se.load_serie(serie["id"])
rep = se.director_report(serie_full,
                         "Narrador: Lola entró en La Cueva.\nLola: ¡hola!")
c_lola = next(c for c in rep["characters"] if c["name"] == "Lola")
l_cueva = next(l for l in rep["locations"] if l["name"] == "La Cueva")
check("T7a detecta quién aparece (sin importar acentos ni mayúsculas)",
      c_lola["appears"] and l_cueva["appears"])
check("T7b lo que tiene referencia se REUTILIZA",
      "reutilizar" in c_lola["plan"] and "reutilizar" in l_cueva["plan"])
c_yo = next(c for c in rep["characters"] if c["name"] == "Yo")
check("T7c lo que no aparece en el guion queda marcado como tal",
      not c_yo["appears"])
sin_voz = se.create_serie({"name": "Prueba Sin Material"})
se.add_character(sin_voz["id"], {"name": "Pepe"})
rep2 = se.director_report(se.load_serie(sin_voz["id"]), "Pepe: hola")
check("T7d avisa de lo que falta: retrato por generar, voz sin asignar, jingle",
      any("retrato" in a for a in rep2["actions"])
      and any("voz" in a for a in rep2["actions"])
      and any("jingle" in a for a in rep2["actions"]))
check("T7e el resumen cuenta el plan en una frase",
      "REUTILIZA" in rep["summary"])

# ---------------------------------------------------------------------------
# T8 — las DOS plantillas traen el Estudio de series completo
# ---------------------------------------------------------------------------
print("\nT8 la pantalla de Series, en las dos plantillas")

for nombre, ruta in (("nueva", ROOT / "ytstudio/webui/static/index.html"),
                     ("clasica", ROOT / "ytstudio/webui/static/index-clasica.html")):
    html = ruta.read_text(encoding="utf-8")
    check(f"T8a la plantilla {nombre} tiene la pantalla de Series",
          "/api/series" in html and "Series" in html)
    for opcion in ("Crear serie", "Clonarme", "Clonar mi voz", "jingle",
                   "locaci", "narrador", "Crear el episodio",
                   "director de la serie", "clone-avatar", "series-files"):
        check(f"T8b la plantilla {nombre} ofrece «{opcion}»", opcion in html)

# ---------------------------------------------------------------------------
# T9 — documentación
# ---------------------------------------------------------------------------
print("\nT9 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T9a el manual {nombre} trae la receta de la serie animada",
          "Serie animada" in texto and "Clonarme" in texto
          and "Clonar mi voz" in texto)
    check(f"T9b el manual {nombre} explica la pantalla de Series",
          "biblia" in texto.lower() and "locaci" in texto.lower()
          and "jingle" in texto.lower())
    check(f"T9c el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*0\.69\.0", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T9d el CHANGELOG cuenta lo que trae la v0.69.0",
      "## v0.69.0" in CHANGELOG and "Estudio de series" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.69.0: el Estudio de series animadas, con coherencia de "
      "personajes, locaciones, voces y música entre episodios.")
