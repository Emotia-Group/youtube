"""Batería v0.57.0 — los seis detalles que reportaste tras el video de prueba.

1. El PERSONAJE con lipsync salía recortado al mentón cuando su foto venía en
   otra relación de aspecto (9:16 en un video 16:9): el reencuadre existía,
   pero solo se aplicaba a las escenas cuyo lipsync FALLABA. Ahora la foto se
   adapta al formato ANTES de generar los clips.
2. El personaje se DESINCRONIZABA en las pausas: el clip se generaba con el
   tramo de la grabación ORIGINAL, no con el de la pista final (la que suena,
   con las pausas ya ajustadas por el director).
3. Los INSERTOS sonaban todos con el mismo 'pop' de app: ahora hay paletas de
   acento y cada tipo de inserto suena distinto dentro de la suya.
4. Seguían apareciendo TEXTOS ILEGIBLES: el ruteo a gpt-image-1 solo miraba
   el image_text declarado; ahora también detecta el objeto escrito en el
   prompt, invierte las peticiones de «texto borroso» y la visión reporta el
   texto inventado como defecto.
5. Los SUBTÍTULOS empezaban con «• »: Whisper copiaba el formato del guion en
   viñetas que se le pasa como contexto de vocabulario.
6. Un localizador sin cartografía real dibujaba una FICHA VACÍA de
   coordenadas: ahora se resuelve con una imagen real del lugar, o no se pone.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
import subprocess
import tempfile

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0570_"))

from PIL import Image

from ytstudio.phases import assembly as asm
from ytstudio.phases import broll as broll_phase
from ytstudio.phases import subtitles as subs_phase
from ytstudio.phases import voiceover as vo_phase
from ytstudio.utils import sfx as sfxlib
from ytstudio.utils.media import probe_duration, probe_video_size, run_ffmpeg
from ytstudio.utils.text import (clean_vocab_hint, strip_bullets,
                                 strip_bullets_segments)


class PStub:
    def __init__(self, name="proj"):
        self.data, self.avisos = {}, []
        self.dir = TMP / name

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


CFG = {"language": "es",
       "video": {"width": 1920, "height": 1080, "fps": 24, "elements": False},
       "providers": {"images": {}, "lipsync": {"model": "stub/omni"}},
       "performance": {"parallel_video": 1},
       "audio": {}}


# ---------------------------------------------------------------------------
# T1 — la foto del personaje se adapta al formato ANTES de hablar
# ---------------------------------------------------------------------------
class RefStub:
    """Modelo de identidad: devuelve la foto reencuadrada al formato pedido."""

    def __init__(self, size=(1920, 1080)):
        self.size = size
        self.prompts = []

    def generate_with_refs(self, prompt, refs, out):
        self.prompts.append(prompt)
        Image.new("RGB", self.size, (120, 90, 60)).save(out)
        return out


class LipsyncStub:
    model = "stub/omni"

    def __init__(self):
        self.calls = []

    def generate(self, image, audio, out, seconds):
        self.calls.append((Path(image), Path(audio), seconds))
        w, h = Image.open(image).size
        dur = probe_duration(audio)
        run_ffmpeg(["-f", "lavfi", "-i",
                    f"testsrc=size={w}x{h}:rate=12:duration={dur:.2f}",
                    "-pix_fmt", "yuv420p", str(out)], "clip de prueba")
        return out


def proyecto_personaje(name, *, durations=(6.0, 8.0), foto=(1080, 1920)):
    """Proyecto con narración propia, pista final de voz y 2 escenas de
    personaje. La pista lleva un TONO solo dentro de la segunda escena: así se
    puede comprobar de qué tramo se cortó el audio del lipsync."""
    p = PStub(name)
    inp = p.path("input")
    Image.new("RGB", foto, (30, 40, 70)).save(inp / "narrador.jpg")
    p.set("assets", [{"id": 1, "category": "personaje", "kind": "image",
                      "file": "narrador.jpg"}])
    p.set("characters", [{"id": "ch1", "name": "Narrador", "description": "",
                          "asset_ids": [1], "narrator": True}])
    total = sum(durations)
    t0, t1 = durations[0], total
    tl = p.path("voiceover", "narration_timeline.wav")
    run_ffmpeg(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={total}",
                "-f", "lavfi", "-i",
                f"sine=frequency=440:duration={t1 - t0:.2f}",
                "-filter_complex",
                f"[1:a]adelay={int(t0 * 1000)}|{int(t0 * 1000)}[b];"
                "[0:a][b]amix=inputs=2:duration=first[out]",
                "-map", "[out]", "-c:a", "pcm_s16le", str(tl)],
               "pista de voz de prueba")
    p.set("voice_timeline", tl.name)
    scenes = [{"id": i + 1, "duration": d, "shot": "personaje",
               "animation": "static", "narration": "texto",
               "broll_prompt": "the narrator speaking to camera"}
              for i, d in enumerate(durations)]
    return p, scenes


_real_get_lipsync = broll_phase and None
import ytstudio.providers as prov_mod
import ytstudio.providers.images as img_mod

ls_stub = LipsyncStub()
ref_stub = RefStub()
prov_mod.get_lipsync = lambda cfg: ls_stub
img_mod.get_ref_images = lambda cfg: ref_stub

proj, escenas = proyecto_personaje("p_lipsync")
ids = broll_phase._generate_character_scenes(proj, escenas,
                                             proj.path("broll"), CFG)
plate = proj.path("broll", "personaje_wide.jpg")
check("T1 la foto 9:16 se reencuadra al formato del video ANTES de generar",
      plate.exists() and Image.open(plate).size == (1920, 1080),
      str(plate.exists()))
check("T1b y es ESA foto la que se le entrega al modelo de lipsync "
      "(no la vertical original)",
      len(ls_stub.calls) == 2
      and all(c[0].name == "personaje_wide.jpg" for c in ls_stub.calls),
      str([c[0].name for c in ls_stub.calls]))
check("T1c los clips nacen ya con el aspecto del video",
      all(probe_video_size(proj.path("broll", f"lipsync_{i:03d}.mp4"))
          == (1920, 1080) for i in (1, 2)), "")
check("T1d el prompt del reencuadre pide la cabeza completa, sin recortes",
      ref_stub.prompts and "never crop the top of the head"
      in ref_stub.prompts[0], str(ref_stub.prompts[:1]))
check("T1e las escenas quedan resueltas por el lipsync", ids == {1, 2},
      str(ids))

# sin modelo de identidad no se puede reencuadrar: la foto entera se compone
# sobre fondo desenfocado (la cara NUNCA se corta)
img_mod.get_ref_images = lambda cfg: None
ls_stub2 = LipsyncStub()
prov_mod.get_lipsync = lambda cfg: ls_stub2
proj2, escenas2 = proyecto_personaje("p_sinref")
broll_phase._generate_character_scenes(proj2, escenas2, proj2.path("broll"),
                                       CFG)
clip_vert = proj2.path("broll", "lipsync_001.mp4")
check("T1f sin modelo de identidad, el clip sale con el aspecto de la foto",
      probe_video_size(clip_vert) == (1080, 1920), "")
esc_v = {"id": 1, "duration": 3.0, "animation": "static",
         "broll_video": "lipsync_001.mp4", "broll_image": "lipsync_001.jpg",
         "broll_source": "lipsync"}
out_v = TMP / "vertical.mp4"
Image.new("RGB", (1080, 1920), (10, 10, 10)).save(
    proj2.path("broll", "lipsync_001.jpg"))
asm._render_scene(esc_v, proj2, CFG, out_v, fade={})
check("T1g y el montaje lo compone ENTERO sobre fondo desenfocado "
      "(nunca recortado al mentón)",
      out_v.exists() and probe_video_size(out_v) == (1920, 1080), "")
src_render = inspect.getsource(asm._render_scene)
check("T1h el montaje decide por el aspecto REAL del clip",
      "_aspect_off(probe_video_size(vid)" in src_render, "")

img_mod.get_ref_images = lambda cfg: ref_stub
prov_mod.get_lipsync = lambda cfg: ls_stub

# ---------------------------------------------------------------------------
# T2 — el lipsync se genera con el audio que de VERDAD se va a oír
# ---------------------------------------------------------------------------
def volumen(path):
    from ytstudio.utils.media import _segment_mean_db
    return _segment_mean_db(path, 0.0, probe_duration(path))


aud1, aud2 = (proj.path("voiceover", f"lipsync_audio_{i:03d}.wav")
              for i in (1, 2))
check("T2 cada escena recibe un tramo con la duración EXACTA de la escena",
      abs(probe_duration(aud1) - 6.0) < 0.05
      and abs(probe_duration(aud2) - 8.0) < 0.05,
      f"{probe_duration(aud1):.2f} / {probe_duration(aud2):.2f}")
v1, v2 = volumen(aud1), volumen(aud2)
check("T2b y es el tramo que le corresponde en la LÍNEA DE TIEMPO FINAL "
      "(el tono vive solo dentro de la escena 2)",
      v1 is not None and v2 is not None and v2 > v1 + 20, f"{v1} vs {v2}")
check("T2c el tramo sale de la pista final, no de la grabación original",
      "narration_timeline" in inspect.getsource(vo_phase.timeline_segment)
      or "voice_timeline" in inspect.getsource(vo_phase.timeline_segment), "")
check("T2d el inicio de cada escena es la suma de las anteriores",
      vo_phase.scene_start_in_video(escenas, escenas[1]) == 6.0,
      str(vo_phase.scene_start_in_video(escenas, escenas[1])))

# reanudar NO re-paga… pero un clip con firma vieja SÍ se rehace
antes = len(ls_stub.calls)
broll_phase._generate_character_scenes(proj, escenas, proj.path("broll"), CFG)
check("T2e al reanudar con las mismas entradas no se re-genera (ni se paga)",
      len(ls_stub.calls) == antes, str(len(ls_stub.calls)))
(proj.path("broll", "lipsync_001.sig")).write_text("firma-vieja",
                                                   encoding="utf-8")
broll_phase._generate_character_scenes(proj, escenas, proj.path("broll"), CFG)
check("T2f un clip generado con otra foto u otro audio se REHACE",
      len(ls_stub.calls) == antes + 1, str(len(ls_stub.calls)))

# el montaje jamás ralentiza un clip de lipsync (romper la sincronía)
corto = TMP / "corto.mp4"
run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=12:duration=2",
            "-pix_fmt", "yuv420p", str(corto)], "clip corto")
import shutil as _sh
_sh.copyfile(corto, proj.path("broll", "corto.mp4"))
Image.new("RGB", (1920, 1080), (5, 5, 5)).save(proj.path("broll", "p.jpg"))
esc_ls = {"id": 9, "duration": 5.0, "animation": "static",
          "broll_video": "corto.mp4", "broll_image": "p.jpg",
          "broll_source": "lipsync"}
out_ls = TMP / "ls.mp4"
asm._render_scene(esc_ls, proj, CFG, out_ls, fade={})
check("T2g un clip de lipsync más corto que su escena se congela, NO se "
      "ralentiza (la cámara lenta desincronizaba los labios)",
      "tpad=stop_mode=clone" in src_render and out_ls.exists()
      and abs(probe_duration(out_ls) - 5.0) < 0.1,
      f"{probe_duration(out_ls) if out_ls.exists() else 'sin salida'}")
esc_broll = {**esc_ls, "id": 10, "broll_source": "ai"}
out_br = TMP / "br.mp4"
asm._render_scene(esc_broll, proj, CFG, out_br, fade={})
check("T2h y un B-roll normal sigue con su cámara lenta de siempre",
      out_br.exists() and abs(probe_duration(out_br) - 5.0) < 0.1, "")

# ---------------------------------------------------------------------------
# T3 — el sonido de los insertos: paletas, no un 'pop' para todo
# ---------------------------------------------------------------------------
check("T3 cada tipo de inserto suena distinto dentro de la paleta",
      sfxlib.insert_kind({"tipo": "lugar", "mode": "photo"}, "archivo")
      == "papel"
      and sfxlib.insert_kind({"tipo": "cifra"}, "archivo") == "clic"
      and sfxlib.insert_kind({"tipo": "mapa"}, "archivo") == "aire",
      "")
check("T3b la paleta 'ninguno' deja los insertos mudos",
      sfxlib.insert_kind({"tipo": "cifra"}, "ninguno") is None, "")
check("T3c también se puede fijar UN efecto suelto para todos",
      sfxlib.insert_kind({"tipo": "cifra"}, "sello") == "sello", "")
nuevos = ("clic", "aire", "cuerda", "sello")
sfx_dir = TMP / "sfx"
sfx_dir.mkdir(exist_ok=True)
check("T3d los efectos nuevos se sintetizan en local (sin descargas)",
      all(sfxlib.ensure_sfx(k, sfx_dir).exists() for k in nuevos), "")
check("T3e y duran lo que un acento, no una transición",
      all(sfxlib.SFX_SPECS[k]["dur"] <= 2.0 for k in nuevos), "")

esc_sfx = [{"duration": 8.0, "sfx": None,
            "elements": [{"files": ["x.png"], "at": 2.0, "tipo": "cifra"}]}]
cfg_auto = {**CFG, "audio": {"element_sfx": "auto"},
            "style": {"preset": "documental_cinematografico"}}
a, f, lab = asm._sfx_graph(esc_sfx, cfg_auto, TMP, first_input=2)
check("T3f en 'auto' el acento lo elige el ESTILO del video "
      "(documental → tic de proyector, no 'pop' de app)",
      any("sfx_clic" in x for x in a), str(a))
cfg_off = {**CFG, "audio": {"element_sfx": "ninguno"}}
a2, f2, lab2 = asm._sfx_graph(esc_sfx, cfg_off, TMP, first_input=2)
check("T3g con 'ninguno' no se mezcla ningún acento de inserto",
      lab2 is None, str(f2))
from ytstudio.catalog import STYLE_PRESETS
check("T3h cada estilo trae su paleta",
      all(p.get("insert_sfx") in sfxlib.INSERT_PALETTES
          for k, p in STYLE_PRESETS.items() if k != "ninguno"),
      str({k: p.get("insert_sfx") for k, p in STYLE_PRESETS.items()}))

# ---------------------------------------------------------------------------
# T4 — texto LEGIBLE como estándar
# ---------------------------------------------------------------------------
check("T4 una escena con un objeto escrito se detecta aunque el director no "
      "declare image_text",
      broll_phase._shows_text(
          {"broll_prompt": "1929 stock ticker and a newspaper front page"}),
      "")
check("T4b una escena sin texto no se rutea (no encarece el video)",
      not broll_phase._shows_text(
          {"broll_prompt": "a lone whaling ship in a storm at dusk"}), "")
check("T4c las peticiones de «texto ilegible» se INVIERTEN",
      broll_phase._drop_illegible(
          "newspapers with out of focus, unreadable print, dramatic light")
      == "newspapers with sharp legible text, dramatic light",
      broll_phase._drop_illegible(
          "newspapers with out of focus, unreadable print, dramatic light"))
src_run = inspect.getsource(broll_phase.run)
check("T4d el ruteo al modelo tipográfico usa esa detección",
      "_shows_text(s)" in src_run and "_shows_text(scene)" in src_run, "")
src_qa = inspect.getsource(broll_phase._qa_batches)
check("T4e y la revisión con visión reporta el TEXTO INVENTADO como defecto",
      "TEXTO INVENTADO" in src_qa, "")
from ytstudio.phases import scenes as scenes_phase
check("T4f al director se le pide legible por defecto, y se le prohíbe pedir "
      "texto borroso",
      "PROHIBIDO pedir texto" in scenes_phase.CREATIVE_RULES
      and "image_text es OBLIGATORIO" in scenes_phase.CREATIVE_RULES, "")

# ---------------------------------------------------------------------------
# T5 — ni una viñeta en los subtítulos
# ---------------------------------------------------------------------------
check("T5 el contexto que se le pasa a Whisper va SIN viñetas ni numeración",
      clean_vocab_hint("• La prensa de la época\n- Otro punto\n1. Tercero")
      == "La prensa de la época Otro punto Tercero",
      clean_vocab_hint("• La prensa\n- Otro\n1. Tercero"))
check("T5b y si aun así llegara una, se quita del texto y de las palabras",
      strip_bullets_segments(
          [{"text": "• La prensa de la época",
            "words": [{"text": "•", "start": 0.0, "end": 0.1},
                      {"text": "La", "start": 0.1, "end": 0.3}]}])
      == [{"text": "La prensa de la época",
           "words": [{"text": "La", "start": 0.1, "end": 0.3}]}], "")
check("T5c los guiones de diálogo NO se tocan (en español abren parlamento)",
      strip_bullets("—No lo sabía") == "—No lo sabía", strip_bullets("—No"))
cues = subs_phase.build_cues(
    [{"id": 1, "duration": 6.0, "vo_duration": 5.0,
      "narration": "• La prensa de la época se regocijaba."}], 42, 2)
check("T5d y ningún subtítulo sale con la viñeta impresa",
      cues and all("•" not in c["text"] for c in cues),
      str([c["text"] for c in cues]))

# ---------------------------------------------------------------------------
# T6 — un localizador sin mapa real no deja una ficha vacía
# ---------------------------------------------------------------------------
from ytstudio.utils import elements as elib
from ytstudio.utils import maps as mapslib

_bank = elib.BANK_DIR
elib.BANK_DIR = TMP / "banco_vacio"
elib.geo_lookup = lambda q, lang="es": (44.2, -70.3)
mapslib.render_map_frames = lambda *a, **k: None    # servicio caído
foto = TMP / "nueva_inglaterra.jpg"
Image.new("RGB", (600, 400), (80, 70, 60)).save(foto)
elib.wiki_photo = lambda q, lang, out_dir: {"file": foto,
                                            "credit": f"{q}: dominio público"}
p6 = PStub("p6")
esc6 = [{"id": 3, "duration": 6.0,
         "narration": "Los balleneros de Nueva Inglaterra.",
         "elements": [{"tipo": "mapa", "consulta": "Nueva Inglaterra",
                       "etiqueta": "Nueva Inglaterra",
                       "momento": "Nueva Inglaterra"}]}]
cfg6 = {**CFG, "video": {**CFG["video"], "elements": True,
                         "elements_web": True, "elements_ai": False,
                         "overlay_accent": "E8C46B"}}
broll_phase._resolve_elements(p6, cfg6, esc6, p6.path("broll"))
el6 = (esc6[0].get("elements") or [{}])[0]
check("T6 sin cartografía real, la mención se resuelve con una imagen REAL "
      "del lugar (no con una retícula de coordenadas vacía)",
      el6.get("mode") == "photo" and el6.get("files"), str(el6))
check("T6b con su crédito de licencia libre",
      any("Nueva Inglaterra" in c for c in (p6.get("element_credits") or [])),
      str(p6.get("element_credits")))

elib.wiki_photo = lambda q, lang, out_dir: None
p7 = PStub("p7")
esc7 = [{"id": 4, "duration": 6.0, "narration": "x",
         "elements": [{"tipo": "mapa", "consulta": "Lugar Sin Foto",
                       "etiqueta": "Lugar", "momento": "x"}]}]
broll_phase._resolve_elements(p7, cfg7 := cfg6, esc7, p7.path("broll"))
check("T6c y si tampoco hay imagen, el inserto DESAPARECE (nada vacío en "
      "pantalla) con aviso honesto",
      not esc7[0].get("elements") and p7.avisos
      and "mapa" in p7.avisos[0], str(p7.avisos))
check("T6d el módulo de mapas ya no dibuja fichas de coordenadas",
      not hasattr(mapslib, "_grid_backdrop"), "")
elib.BANK_DIR = _bank

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.57.0 completa: encuadre y sincronía del personaje, "
      "acentos de inserto por estilo, texto legible como estándar, "
      "subtítulos sin viñetas y localizadores con material real.")
