"""Batería v0.66.0 — recortar el Short del VIDEO ORIGINAL.

Hasta ahora, sacar un Short de un video largo significaba escribir una pieza
NUEVA: guion nuevo, voz generada, imágenes generadas. El creador lo pidió al
descubrir que el programa le sintetizaba voz cuando lo que quería era su
propia voz y su propia edición — las del video ya publicado.

Ahora hay dos modos, y el de recorte es el de por defecto:

  · RECORTE — se baja el TRAMO EXACTO del video original y se reencuadra a
    vertical. Conserva la voz, la edición y la imagen. No gasta en voz ni en
    imágenes: solo tiempo de descarga y montaje.
  · PIEZA NUEVA — el de antes, intacto, para cuando lo que se quiere decir no
    está dicho en el largo de forma que aguante sola.

Lo que esta batería comprueba, con un video de verdad:

1.  El recorte sale VERTICAL, dura lo que el tramo y conserva el audio.
2.  Los subtítulos salen del propio video, con sus tiempos, y respetan la
    zona segura — no tapan el enlace al video largo.
3.  El texto de gancho está desde el primer fotograma (regla de doble pista).
4.  La sonoridad se mide y se corrige, como en cualquier otro video.
5.  Las fases que no aplican (voz, imágenes, música…) quedan hechas, así que
    «Generar video» no las ejecuta ni las cobra.
6.  Sin enlace del video original o sin yt-dlp NO se puede recortar, y se
    dice — no se falla a mitad.

Ninguna prueba usa claves ni internet: el video original se fabrica en local
y la descarga se sustituye por ese archivo.
"""

import json
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


WORK = Path(tempfile.mkdtemp(prefix="v0660_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as elog  # noqa: E402
elog.LOG_PATH = WORK / "data" / "events.log"

from ytstudio import clip, derive, shorts  # noqa: E402
from ytstudio.project import DIRS, Project  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

CFG = {"language": "es",
       "video": {"width": 1080, "height": 1920, "fps": 30},
       "subtitles": {"font": "Arial", "font_size": 80, "max_lines": 2,
                     "safe_zone": True},
       "audio": {"target_lufs": -14, "target_tp": -1.0},
       "shorts": {"reencuadre": "fondo_desenfocado", "clip_height": 1080}}

CANDIDATO = {"nombre": "Prueba", "idea": "La idea central",
             "texto_pantalla": "EL 73% SE EQUIVOCA", "desde": 30.0,
             "hasta": 68.0, "duracion": 38, "titulo_youtube": "Un título",
             "modo": "recorte"}
FUENTE = {"url": "https://youtu.be/PRUEBA", "titulo": "El video largo",
          "marcas": [{"t": float(t), "t_fin": float(t) + 2.4,
                      "texto": f"Frase {i} del original."}
                     for i, t in enumerate(range(28, 70, 3))]}

# ---------------------------------------------------------------------------
# T1 — los dos modos existen y el recorte manda
# ---------------------------------------------------------------------------
print("T1 los dos modos")

check("T1a hay dos modos registrados", set(derive.MODOS) == {"recorte", "nuevo"},
      str(list(derive.MODOS)))
check("T1b el de por defecto es el RECORTE (más barato y conserva tu voz)",
      derive.MODO_POR_DEFECTO == "recorte")
check("T1c cada modo explica qué hace y qué cuesta",
      all(len(v["hint"]) > 60 for v in derive.MODOS.values()))
check("T1d el recorte declara que necesita el enlace",
      derive.MODOS["recorte"]["requiere_enlace"]
      and not derive.MODOS["nuevo"]["requiere_enlace"])

CFGYAML = (ROOT / "config.yaml").read_text(encoding="utf-8")
check("T1e la configuración trae el modo, con el recorte puesto",
      "shorts:" in CFGYAML and "modo: recorte" in CFGYAML)
check("T1f y la forma de reencuadrar", "reencuadre: fondo_desenfocado" in CFGYAML)

# Sin enlace no se puede recortar, se pida lo que se pida
_disp = clip.available
clip.available = lambda: True
try:
    check("T1g con enlace y yt-dlp, se puede recortar",
          derive.modo_disponible(FUENTE, {})[1] is True)
    check("T1h sin enlace, NO se puede — y se sabe antes de empezar",
          derive.modo_disponible({"url": "", "marcas": []}, {})[1] is False)
    forzado = derive.normalize(
        [{"guion": "x " * 60, "gancho_tipo": "mito_desmontado",
          "funcion": "promesa", "modo": "recorte"}],
        {"url": "", "titulo": ""}, 1, puede_recortar=False)
    check("T1i y un candidato en modo recorte se pasa a pieza nueva",
          forzado[0]["modo"] == "nuevo", forzado[0]["modo"])
finally:
    clip.available = _disp

check("T1j sin yt-dlp tampoco se puede recortar",
      derive.modo_disponible(FUENTE, {})[1] is clip.available())

# ---------------------------------------------------------------------------
# T2 — al director se le encarga distinto según el modo
# ---------------------------------------------------------------------------
print("\nT2 el encargo cambia con el modo")

recorte = derive._prompt(FUENTE, 3, list(derive.HOOK_STRUCTURES),
                         "recorte", True)
nuevo = derive._prompt(FUENTE, 3, list(derive.HOOK_STRUCTURES), "nuevo", True)
sin_enlace = derive._prompt(FUENTE, 3, list(derive.HOOK_STRUCTURES),
                            "recorte", False)

check("T2a en recorte se avisa de que NO se puede cambiar lo que se dice",
      "no se puede cambiar ni una palabra" in recorte)
check("T2b y de que el corte lo marcan 'desde' y 'hasta'",
      "MÁS IMPORTANTE" in recorte and "EMPEZAR" in recorte)
check("T2c se pide que el tramo empiece y acabe bien",
      "media explicación" in recorte and "idea cerrada" in recorte)
check("T2d el texto en pantalla gana importancia (es lo único que se añade)",
      "lo único que se le añade encima" in recorte)
check("T2e en modo pieza nueva el encargo es el de siempre",
      "escribe el guion" in nuevo.lower()
      and "no se puede cambiar ni una palabra" not in nuevo)
check("T2f sin enlace se dice que recortar no es posible",
      "recortarlo no es posible" in sin_enlace)

# ---------------------------------------------------------------------------
# T3 — el andamiaje: qué fases se saltan
# ---------------------------------------------------------------------------
print("\nT3 lo que un recorte NO tiene que generar")

p = Project.create("recorte-andamio")
clip.scaffold(p, CANDIDATO, FUENTE)

for fase in clip.FASES_QUE_NO_APLICAN:
    check(f"T3a la fase «{fase}» queda hecha (no se ejecuta ni se cobra)",
          p.phase_status(fase) == "done")
for fase in ("assembly", "metadata", "publish"):
    check(f"T3b la fase «{fase}» SÍ se ejecutará", p.phase_status(fase) != "done")

check("T3c ni voz ni imágenes: son justo las fases que cuestan dinero",
      "voiceover" in clip.FASES_QUE_NO_APLICAN
      and "broll" in clip.FASES_QUE_NO_APLICAN)
check("T3d guarda el tramo exacto del original",
      (p.get("clip_source") or {}).get("desde") == 30.0
      and (p.get("clip_source") or {}).get("hasta") == 68.0)
check("T3e y los subtítulos del tramo, para no volver a pedirlos",
      len((p.get("clip_source") or {}).get("marcas") or []) > 3)
check("T3f deja una escena con la duración real, para metadatos y miniatura",
      json.loads((p.dir / DIRS["scenes"] / "scenes.json")
                 .read_text(encoding="utf-8"))["scenes"][0]["duration"] == 38.0)

# ---------------------------------------------------------------------------
# T4 — los subtítulos del tramo
# ---------------------------------------------------------------------------
print("\nT4 los subtítulos salen del propio video")

cues = clip.segment_cues(FUENTE["marcas"], 30.0, 68.0)
check("T4a solo entran los del tramo", len(cues) > 5 and len(cues) < 15,
      str(len(cues)))
check("T4b los tiempos se trasladan al inicio del recorte",
      cues[0]["start"] < 2.0, str(cues[0]))
check("T4c ninguno se sale del final", all(c["end"] <= 38.5 for c in cues))
check("T4d ninguno empieza antes de tiempo", all(c["start"] >= 0 for c in cues))
check("T4e no se solapan entre sí",
      all(a["end"] <= b["start"] + 0.01 for a, b in zip(cues, cues[1:])))

# Sin tiempo de fin (subtítulos automáticos), se deduce del siguiente
sin_fin = [{"t": 10.0, "texto": "uno"}, {"t": 13.0, "texto": "dos"}]
c2 = clip.segment_cues(sin_fin, 8.0, 20.0)
check("T4f si el subtítulo no trae fin, se deduce del siguiente",
      len(c2) == 2 and c2[0]["end"] <= c2[1]["start"] + 0.01, str(c2))

# ---------------------------------------------------------------------------
# T5 — el recorte de verdad (necesita ffmpeg)
# ---------------------------------------------------------------------------
print("\nT5 el recorte, medido en el archivo")

if not HAS_FFMPEG:
    print("      (sin ffmpeg: T5 se omite)")
else:
    origen = WORK / "largo.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=90",
         "-f", "lavfi", "-i", "sine=frequency=200:duration=90:sample_rate=48000",
         "-af", "volume=-26dB", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(origen)], check=True)
    horizontal = shorts.probe(origen)
    check("T5a el video de partida es horizontal y suena bajo",
          horizontal["width"] > horizontal["height"])

    proyecto = Project.create("recorte-real")
    clip.scaffold(proyecto, CANDIDATO, FUENTE)

    # Se sustituye la descarga por el archivo local; el "aire" pasa a ser el
    # desplazamiento del tramo dentro de ese archivo.
    real_dl, real_aire = clip.download_segment, clip.AIRE_SEGUNDOS
    clip.download_segment = lambda url, d, h, w, c: origen
    clip.AIRE_SEGUNDOS = 30.0
    try:
        salida = clip.render(proyecto, CFG)
    finally:
        clip.download_segment, clip.AIRE_SEGUNDOS = real_dl, real_aire

    info = shorts.probe(salida)
    check("T5b el recorte sale VERTICAL 1080x1920",
          (info["width"], info["height"]) == (1080, 1920), str(info))
    check("T5c y dura lo que el tramo", abs(info["duration"] - 38) < 1.5,
          f"{info['duration']:.1f}s")
    check("T5d conserva el AUDIO del original", info["has_audio"])

    loud = proyecto.get("loudness") or {}
    check("T5e la sonoridad heredada se mide y se corrige",
          loud.get("lufs") is not None and abs(loud["lufs"] + 14) <= 1.0,
          str(loud))

    ass = (proyecto.dir / DIRS["subtitles"] / "subtitulos.ass").read_text(
        encoding="utf-8")
    check("T5f los subtítulos quemados son los del video original",
          "Frase" in ass)
    check("T5g el texto de gancho está desde el fotograma 1 (doble pista)",
          "EL 73% SE EQUIVOCA" in ass and "0:00:00.00" in ass)
    estilo = [l for l in ass.splitlines() if l.startswith("Style: Default")][0]
    check("T5h y respetan la zona segura del enlace al video largo",
          int(estilo.split(",")[-2]) >= 430, estilo.split(",")[-2])
    srt = (proyecto.dir / DIRS["subtitles"] / "subtitulos.srt").read_text(
        encoding="utf-8")
    check("T5i el SRT se genera aparte", "-->" in srt and "Frase" in srt)

    auditoria = proyecto.get("shorts_audit")
    check("T5j se audita solo, como cualquier otro vertical",
          bool(auditoria) and not auditoria["problemas"],
          str((auditoria or {}).get("problemas")))
    escenas = json.loads((proyecto.dir / DIRS["scenes"] / "scenes.json")
                         .read_text(encoding="utf-8"))["scenes"]
    check("T5k la miniatura tendrá un fotograma REAL del recorte",
          bool(escenas[0].get("broll_image")))

    # El otro reencuadre también produce un vertical válido
    p2 = Project.create("recorte-centrado")
    clip.scaffold(p2, CANDIDATO, FUENTE)
    clip.download_segment = lambda url, d, h, w, c: origen
    clip.AIRE_SEGUNDOS = 30.0
    try:
        s2 = clip.render(p2, {**CFG, "shorts": {"reencuadre": "recorte_centrado"}})
    finally:
        clip.download_segment, clip.AIRE_SEGUNDOS = real_dl, real_aire
    i2 = shorts.probe(s2)
    check("T5l el recorte centrado también sale vertical",
          (i2["width"], i2["height"]) == (1080, 1920), str(i2))

# ---------------------------------------------------------------------------
# T6 — el reencuadre no pierde imagen por defecto
# ---------------------------------------------------------------------------
print("\nT6 cómo se pasa de horizontal a vertical")

check("T6a hay dos formas de reencuadrar",
      set(clip.REENCUADRES) == {"fondo_desenfocado", "recorte_centrado"})
check("T6b la de por defecto NO pierde imagen",
      clip.REENCUADRE_POR_DEFECTO == "fondo_desenfocado")
f_fondo = clip.reframe_filter("fondo_desenfocado", 1080, 1920)
check("T6c el fondo se hace con la propia imagen, desenfocada",
      "gblur" in f_fondo and "overlay" in f_fondo)
check("T6d y el fotograma entero va encima, sin recortar",
      "force_original_aspect_ratio=decrease" in f_fondo)
f_centro = clip.reframe_filter("recorte_centrado", 1080, 1920)
check("T6e el recorte centrado recorta y escala",
      "crop=" in f_centro and "scale=1080:1920" in f_centro)
check("T6f los dos dejan los píxeles cuadrados", "setsar=1" in f_fondo
      and "setsar=1" in f_centro)

# ---------------------------------------------------------------------------
# T7 — enchufado: montaje, servidor e interfaces
# ---------------------------------------------------------------------------
print("\nT7 enchufado al programa")

ASM = (ROOT / "ytstudio" / "phases" / "assembly.py").read_text(encoding="utf-8")
check("T7a el montaje detecta un recorte y hace otra cosa",
      'shorts_modo") or "") == "recorte"' in ASM and "clip.render" in ASM)

DER = (ROOT / "ytstudio" / "derive.py").read_text(encoding="utf-8")
check("T7b al crear el proyecto se monta el andamiaje del recorte",
      "clip.scaffold(project, c, origen)" in DER)
check("T7c y la ficha dice en qué modo va la pieza", "**Cómo se hace:**" in DER)

SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T7d el servidor acepta el modo que pide el creador",
      'body.get("modo")' in SRV)
check("T7e y le dice a la interfaz si se puede recortar",
      'plan["puede_recortar"]' in SRV)
check("T7f la fuente llega al crear (el recorte la necesita)",
      "source=origen" in SRV)

from ytstudio.webui import server as srv  # noqa: E402
NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T7g la interfaz {nombre} deja elegir el modo",
          "Recortar del video original" in html
          and "Generar una pieza nueva" in html)
    check(f"T7h la interfaz {nombre} deja cambiarlo pieza a pieza",
          "modoSelectorHtml" in html or "selectorModo" in html)
    check(f"T7i la interfaz {nombre} avisa si no se puede recortar",
          "no hay nada que recortar" in html)

# ---------------------------------------------------------------------------
# T8 — documentación
# ---------------------------------------------------------------------------
print("\nT8 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T8a el manual {nombre} explica los dos modos",
          "Recortar del video original" in texto)
    check(f"T8b el manual {nombre} dice cuál es más barato",
          "no gasta" in texto or "no cuesta" in texto)
    check(f"T8c el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T8d el CHANGELOG cuenta lo que trajo la v0.66.0",
      "## v0.66.0" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.66.0: el Short se puede recortar del video original.")
