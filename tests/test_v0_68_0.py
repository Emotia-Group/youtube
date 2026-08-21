"""Batería v0.68.0 — el framework de Shorts, al día en el programa.

El creador actualizó el Framework Universal de Shorts y detectó que sus
ajustes nuevos no estaban en ytstudio. Lo que faltaba, y esta batería
comprueba que ya está:

1.  ENCUADRE A SANGRE (§3.1). La imagen ocupa los cuatro bordes. El fondo
    desenfocado deja zona muerta y el framework lo desaconseja: deja de ser
    el defecto. Y como al pasar de 16:9 a 9:16 solo cabe un tercio del
    ancho, se elige POR DÓNDE se recorta — izquierda, centro o derecha—,
    tanto en la configuración como Short a Short.
2.  NADA A HUESO (§3.2). Un Short puede montarse con varios fragmentos del
    video largo, y entonces cada empalme corta la imagen, la voz y la
    música a la vez. Fundido entre planos, fundido y brecha en la voz, y
    una cama musical CONTINUA por debajo, elegida por medición (la pista
    más plana) del propio mundo sonoro del video largo.
3.  MINIATURA VERTICAL (§4.1). 1080x1920, texto dentro de su zona segura,
    color de acento aclarado para que se lea sobre la imagen, menos de
    2 MB, y la prueba a 150 px —el tamaño al que se ve de verdad— al lado.
4.  AUDITORÍA. Se miden las BANDAS (¿llega la imagen a los cuatro bordes?)
    y el bitrate, y el informe recuerda los dos puntos que ninguna máquina
    ve: bordes y empalmes.

Ninguna prueba usa claves ni internet: el video original se fabrica en
local y la descarga se sustituye por ese archivo.
"""

import re
import shutil
import subprocess
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


WORK = Path(tempfile.mkdtemp(prefix="v0680_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as elog  # noqa: E402
elog.LOG_PATH = WORK / "data" / "events.log"

from ytstudio import clip, derive, shorts  # noqa: E402
from ytstudio.project import DIRS, Project  # noqa: E402
from ytstudio.utils import thumbs  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

CFG = {"language": "es",
       "video": {"width": 1080, "height": 1920, "fps": 30,
                 "overlay_accent": "7A1F1F"},
       "subtitles": {"font": "Arial", "font_size": 80, "max_lines": 2,
                     "safe_zone": True},
       "audio": {"target_lufs": -14, "target_tp": -1.0},
       "shorts": {"reencuadre": "a_sangre", "punto_recorte": "derecha",
                  "velo": True, "fundido": 0.35, "brecha": 0.25,
                  "cama_musical": "auto", "cama_db": -20,
                  "clip_height": 1080}}

CFGYAML = (ROOT / "config.yaml").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# T1 — encuadre a sangre y punto de recorte
# ---------------------------------------------------------------------------
print("T1 la imagen llena el cuadro, y se elige por dónde se recorta")

check("T1a el reencuadre por defecto es A SANGRE",
      clip.REENCUADRE_POR_DEFECTO == "a_sangre")
check("T1b el fondo desenfocado sigue disponible, pero no recomendado",
      "fondo_desenfocado" in clip.REENCUADRES
      and "no recomendado" in clip.REENCUADRES["fondo_desenfocado"]["label"])
check("T1c el nombre viejo (recorte_centrado) se sigue entendiendo",
      clip.normalizar_modo("recorte_centrado") == "a_sangre")
check("T1d hay tres puntos de recorte",
      set(clip.PUNTOS_RECORTE) == {"izquierda", "centro", "derecha"})

izq = clip.reframe_filter("a_sangre", 1080, 1920, "izquierda")
cen = clip.reframe_filter("a_sangre", 1080, 1920, "centro")
der = clip.reframe_filter("a_sangre", 1080, 1920, "derecha")
check("T1e el recorte a sangre llena el cuadro, sin bandas",
      "crop=" in cen and "scale=1080:1920" in cen and "pad=" not in cen)
check("T1f y desplaza la ventana según el punto elegido",
      "(iw-ow)*0.0000" in izq and "(iw-ow)*0.5000" in cen
      and "(iw-ow)*1.0000" in der)
check("T1g se escala con lanczos (se amplía casi el doble)",
      "flags=lanczos" in cen)
check("T1h un número entre 0 y 1 también vale como punto",
      abs(clip.punto_a_fraccion(0.25) - 0.25) < 1e-6
      and clip.punto_a_fraccion("loquesea") == 0.5)

check("T1i la configuración trae el encuadre a sangre y el punto",
      "reencuadre: a_sangre" in CFGYAML and "punto_recorte: centro" in CFGYAML)
check("T1j y los ajustes de empalme y cama musical",
      all(k in CFGYAML for k in ("fundido:", "brecha:", "cama_musical:",
                                 "cama_db:", "velo:")))

# El velo degradado, para que el texto se lea sobre la imagen
velo = clip.velo_png(WORK / "velo.png", 108, 192)
check("T1k el velo se genera como PNG con transparencia", velo.exists())
try:
    from PIL import Image
    with Image.open(velo) as im:
        px = im.convert("RGBA").load()
        arriba, medio, abajo = px[54, 2][3], px[54, 96][3], px[54, 189][3]
    check("T1l el velo es DEGRADADO (oscuro en los extremos, limpio en el "
          "centro): una caja opaca volvería a meter la banda que se quitó",
          arriba > 100 and abajo > 100 and medio == 0,
          f"arriba={arriba} medio={medio} abajo={abajo}")
except ImportError:
    print("      (sin PIL: T1l se omite)")

# El color de acento, aclarado para que tenga contraste sobre imagen
check("T1m un acento oscuro se aclara para el texto sobre vídeo",
      shorts.accent_over_image("7A1F1F") != "7A1F1F")
check("T1n uno que ya es claro se deja como está",
      shorts.accent_over_image("E8C46B") == "E8C46B")

# ---------------------------------------------------------------------------
# T2 — varios fragmentos: fundidos, brecha y cama musical
# ---------------------------------------------------------------------------
print("\nT2 el montaje de varios fragmentos")

uno = clip.tramos_de({"desde": 10, "hasta": 40})
varios = clip.tramos_de({"tramos": [{"desde": 1, "hasta": 5},
                                    {"desde": 9, "hasta": 12}]})
check("T2a un proyecto antiguo (desde/hasta) se lee igual",
      len(uno) == 1 and uno[0]["desde"] == 10.0)
check("T2b y uno nuevo puede traer varios fragmentos", len(varios) == 2)

cues = clip.cues_de_tramos(
    [{"t": 2.0, "t_fin": 4.0, "texto": "uno"},
     {"t": 10.0, "t_fin": 11.5, "texto": "dos"}],
    [{"desde": 1, "hasta": 5}, {"desde": 9, "hasta": 12}], 0.25)
check("T2c los subtítulos de CADA fragmento se trasladan a la línea de "
      "tiempo del montaje",
      len(cues) == 2 and abs(cues[1]["start"] - 5.25) < 0.05, str(cues))

ajustado = derive.ajustar_tramo({"tramos": [{"desde": 100, "hasta": 120},
                                            {"desde": 300, "hasta": 318}],
                                 "desde": 0, "hasta": 0})
check("T2d la duración es la SUMA de los fragmentos más el aire, no la "
      "distancia entre el primero y el último",
      ajustado["duracion"] == 38, str(ajustado["duracion"]))
largo = derive.ajustar_tramo({"tramos": [{"desde": 0, "hasta": 50},
                                         {"desde": 100, "hasta": 140}],
                              "desde": 0, "hasta": 0})
check("T2e y nunca pasa de 60 s (ahí una reclamación BLOQUEA el video)",
      largo["duracion"] <= 60, str(largo["duracion"]))

check("T2f el director puede proponer fragmentos",
      "tramos" in derive.CANDIDATE_SCHEMA["properties"]["candidatos"]["items"]
      ["properties"])
encargo = derive._prompt(
    {"url": "u", "titulo": "t", "marcas": []}, 3,
    list(derive.HOOK_STRUCTURES), "recorte", True)
check("T2g y se le explica para qué sirven",
      "'tramos'" in encargo and "cama musical continua" in encargo)

# ---------------------------------------------------------------------------
# T3 — el montaje de verdad (necesita ffmpeg)
# ---------------------------------------------------------------------------
print("\nT3 el Short montado, medido en el archivo")

if not HAS_FFMPEG:
    print("      (sin ffmpeg: T3 se omite)")
else:
    origen = WORK / "largo.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=60",
         "-f", "lavfi", "-i", "sine=frequency=200:duration=60:sample_rate=48000",
         "-af", "volume=-26dB", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(origen)], check=True)
    biblioteca = WORK / "musica"
    biblioteca.mkdir()
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "anoisesrc=d=40:c=pink:a=0.2",
         "-af", "lowpass=f=800", "-c:a", "libmp3lame",
         str(biblioteca / "cama.mp3")], check=True)
    cfg = {**CFG, "providers": {"music": {"library_dir": str(biblioteca)}}}

    CAND = {"nombre": "Montaje", "idea": "La idea",
            "texto_pantalla": "EL 73% SE EQUIVOCA", "titulo_youtube": "T",
            "modo": "recorte", "punto_recorte": "derecha",
            "tramos": [{"desde": 5, "hasta": 17}, {"desde": 30, "hasta": 40}]}
    FUENTE = {"url": "https://youtu.be/PRUEBA", "titulo": "El video largo",
              "marcas": [{"t": 6.0, "t_fin": 9.0, "texto": "Frase del uno."},
                         {"t": 31.0, "t_fin": 34.0, "texto": "Frase del dos."}]}

    proyecto = Project.create("montaje-real")
    clip.scaffold(proyecto, CAND, FUENTE)
    guardado = proyecto.get("clip_source") or {}
    check("T3a el proyecto guarda los dos fragmentos",
          len(guardado.get("tramos") or []) == 2)
    check("T3b y el punto de recorte elegido para esta pieza",
          guardado.get("punto_recorte") == "derecha")
    check("T3c los subtítulos guardados cubren LOS DOS fragmentos",
          len(guardado.get("marcas") or []) == 2)

    real_dl = clip.download_segment
    real_aire = clip.AIRE_SEGUNDOS
    clip.download_segment = lambda url, d, h, w, c: origen
    clip.AIRE_SEGUNDOS = 0.0
    try:
        salida = clip.render(proyecto, cfg)
    finally:
        clip.download_segment, clip.AIRE_SEGUNDOS = real_dl, real_aire

    info = shorts.probe(salida)
    check("T3d el montaje sale VERTICAL 1080x1920",
          (info["width"], info["height"]) == (1080, 1920), str(info))
    check("T3e y dura la suma de los fragmentos más el aire (12+10+0,25)",
          abs(info["duration"] - 22.25) < 1.0, f"{info['duration']:.2f}s")
    bandas = (proyecto.get("shorts_audit") or {}).get("bandas") or {}
    check("T3f la imagen llega a los cuatro bordes: ni una banda",
          bandas.get("perdido", 1) < shorts.BANDA_AVISO, str(bandas))
    check("T3g la cama musical continua está puesta",
          (proyecto.get("cama_musical") or "").endswith(".mp3"),
          str(proyecto.get("cama_musical")))
    loud = proyecto.get("loudness") or {}
    check("T3h la sonoridad se mide y se corrige a -14 LUFS",
          loud.get("lufs") is not None and abs(loud["lufs"] + 14) <= 1.0,
          str(loud))
    srt = (proyecto.dir / DIRS["subtitles"] / "subtitulos.srt").read_text(
        encoding="utf-8")
    check("T3i el SRT trae los subtítulos de los dos fragmentos, cada uno "
          "en su sitio del montaje",
          "Frase del uno." in srt and "Frase del dos." in srt
          and "00:00:13," in srt, srt.replace("\n", " ")[:160])
    check("T3j el SRT se entrega en su carpeta, no junto al MP4 (si no, "
          "VLC lo dibuja ENCIMA del que ya va quemado)",
          (proyecto.dir / DIRS["subtitles"] / "subtitulos.srt").exists()
          and not (proyecto.dir / DIRS["final"] / "subtitulos.srt").exists())

    # El otro reencuadre también monta, aunque no sea el recomendado
    p2 = Project.create("montaje-fondo")
    clip.scaffold(p2, CAND, FUENTE)
    clip.download_segment = lambda url, d, h, w, c: origen
    clip.AIRE_SEGUNDOS = 0.0
    try:
        s2 = clip.render(p2, {**cfg, "shorts": {**cfg["shorts"],
                                                "reencuadre": "fondo_desenfocado"}})
    finally:
        clip.download_segment, clip.AIRE_SEGUNDOS = real_dl, real_aire
    i2 = shorts.probe(s2)
    check("T3k el fondo desenfocado también monta con fundidos",
          (i2["width"], i2["height"]) == (1080, 1920), str(i2))

# ---------------------------------------------------------------------------
# T4 — la auditoría ve las bandas y el bitrate
# ---------------------------------------------------------------------------
print("\nT4 lo que la revisión técnica mide ahora")

if not HAS_FFMPEG:
    print("      (sin ffmpeg: T4a-T4b se omiten)")
else:
    con_bandas = WORK / "bandas.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1080x608:rate=30:duration=8",
         "-f", "lavfi", "-i", "sine=frequency=200:duration=8:sample_rate=48000",
         "-vf", "pad=1080:1920:0:656:black", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
         str(con_bandas)], check=True)
    ficha = shorts.audit_file(con_bandas)
    check("T4a un vertical con bandas se detecta solo",
          any("BANDAS" in m for m in ficha["problemas"]),
          str(ficha["problemas"]))
    check("T4b y se dice cuánta superficie está muerta",
          (ficha["bandas"] or {}).get("perdido", 0) > 0.5,
          str(ficha["bandas"]))

base = {"width": 1080, "height": 1920, "duration": 30, "has_audio": True,
        "vcodec": "h264", "acodec": "aac", "sample_rate": 48000}
bad, warn, ok = shorts.evaluate({**base, "bitrate": 2_000_000}, None)
check("T4c un bitrate bajo se avisa", any("Bitrate" in m for m in warn))
bad2, warn2, ok2 = shorts.evaluate({**base, "bitrate": 10_000_000}, None)
check("T4d y uno de publicación pasa", any("Bitrate" in m for m in ok2))

informe = "\n".join(shorts.report_lines([shorts.audit_file(WORK / "no-existe.mp4")]))
check("T4e el informe recuerda mirar los CUATRO BORDES",
      "CUATRO BORDES" in informe)
check("T4f y que ningún empalme sea un corte a hueso",
      "corte a hueso" in informe)

# ---------------------------------------------------------------------------
# T5 — la miniatura vertical
# ---------------------------------------------------------------------------
print("\nT5 la miniatura del Short")

try:
    from PIL import Image
except ImportError:
    print("      (sin PIL: T5 se omite)")
else:
    pm = Project.create("miniatura-vertical")
    opciones = [{"text": "ENTERRÓ SU DINERO", "kicker": "HISTORIA",
                 "accent_word": "DINERO"},
                {"text": "NADIE LO VIO VENIR", "kicker": "CANAL",
                 "accent_word": "VENIR"},
                {"text": "UN ERROR QUE COSTÓ MUCHO DINERO A TODOS",
                 "kicker": "DINERO", "accent_word": "ERROR"}]
    nombres = thumbs.render_thumbnails(pm, CFG, opciones, [])
    zona = shorts.miniatura_margins(1080, 1920)
    for i, n in enumerate(nombres, 1):
        f = pm.path("final", n)
        with Image.open(f) as im:
            tam = im.size
            # Solo el texto blanco: el filo de acento del diseño «panel» es
            # una barra de lado a lado, y contarla como texto haría saltar la
            # prueba por una franja decorativa que no dice nada.
            from PIL import ImageChops
            r, g, b = im.convert("RGB").split()
            minimo = ImageChops.darker(ImageChops.darker(r, g), b)
            caja = minimo.point(lambda v: 255 if v > 200 else 0).getbbox()
        check(f"T5a miniatura {i}: 1080x1920 vertical", tam == (1080, 1920),
              str(tam))
        check(f"T5b miniatura {i}: por debajo de 2 MB",
              f.stat().st_size <= shorts.MINIATURA_MAX_BYTES,
              f"{f.stat().st_size // 1024} KB")
        check(f"T5c miniatura {i}: el texto cae DENTRO de la zona segura de "
              "la parrilla del canal",
              caja is not None and caja[1] >= zona["top"] - 2
              and caja[3] <= 1920 - zona["bottom"] + 2
              and caja[0] >= zona["left"] - 2
              and caja[2] <= 1080 - zona["right"] + 2, str(caja))
        check(f"T5d miniatura {i}: se guarda su prueba a 150 px",
              f.with_name(f.stem + "_prueba150px.png").exists())
    with Image.open(pm.path("final", "miniatura_1_prueba150px.png")) as pr:
        check("T5e la prueba mide de verdad 150 px de ancho de miniatura",
              pr.width == shorts.MINIATURA_PRUEBA_PX + 40, str(pr.size))
    check("T5f se avisa cuando el texto no cabe a ese tamaño (3-4 palabras)",
          any("150 px" in w for w in (pm.get("warnings") or [])),
          str(pm.get("warnings")))

    ph = Project.create("miniatura-horizontal")
    nh = thumbs.render_thumbnails(
        ph, {"video": {"width": 1920, "height": 1080}},
        [{"text": "UN TITULAR", "kicker": "", "accent_word": "TITULAR"}], [])
    with Image.open(ph.path("final", nh[0])) as im:
        check("T5g en horizontal no cambia nada (1280x720, sin prueba)",
              im.size == (1280, 720)
              and not ph.path("final", "miniatura_1_prueba150px.png").exists())

# ---------------------------------------------------------------------------
# T6 — la lista de antes de publicar
# ---------------------------------------------------------------------------
print("\nT6 la lista «antes de publicar»")

pc = Project.create("checklist-0680")
items = shorts.publish_checklist(pc, CFG)
etiquetas = [i["label"] for i in items]
check("T6a la miniatura es obligatoria en la lista",
      any("Miniatura vertical" in e for e in etiquetas), str(etiquetas))
check("T6b y se recuerda mirarla a 150 px",
      any("150 px" in e for e in etiquetas))
check("T6c la lista avisa de los subtítulos junto al MP4",
      any("mismo nombre" in e for e in etiquetas))

# ---------------------------------------------------------------------------
# T7 — enchufado: servidor e interfaces
# ---------------------------------------------------------------------------
print("\nT7 enchufado al programa")

SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T7a la interfaz de Configuración guarda los ajustes de Shorts",
      '("shorts", "reencuadre")' in SRV and '("shorts", "punto_recorte")' in SRV
      and '("shorts", "cama_musical")' in SRV)
check("T7b el plan viaja con los puntos de recorte disponibles",
      'plan["puntos"]' in SRV and 'plan["punto_defecto"]' in SRV)
check("T7c la ficha del proyecto trae sus fragmentos",
      'detail["clip_tramos"]' in SRV)

for nombre, ruta in (("nueva", ROOT / "ytstudio/webui/static/index.html"),
                     ("clásica", ROOT / "ytstudio/webui/static/index-clasica.html")):
    html = ruta.read_text(encoding="utf-8")
    check(f"T7d la plantilla {nombre} deja elegir cómo se pasa a vertical",
          "a_sangre" in html and "fondo_desenfocado" in html)
    check(f"T7e la plantilla {nombre} deja elegir por dónde se recorta",
          "punto_recorte" in html)
    check(f"T7f la plantilla {nombre} ofrece la cama musical",
          "cama_musical" in html)
    check(f"T7g la plantilla {nombre} enseña los fragmentos del original",
          "fragmentos" in html.lower())

# ---------------------------------------------------------------------------
# T8 — documentación
# ---------------------------------------------------------------------------
print("\nT8 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T8a el manual {nombre} explica el encuadre a sangre",
          "a sangre" in texto.lower())
    check(f"T8b el manual {nombre} explica por dónde se recorta",
          "por dónde se recorta" in texto.lower())
    check(f"T8c el manual {nombre} habla de la prueba de 150 px",
          "150 px" in texto)
    check(f"T8d el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*0\.68\.0", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T8e el CHANGELOG cuenta lo que trae la v0.68.0",
      "## v0.68.0" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.68.0: el framework de Shorts, al día en el programa.")
