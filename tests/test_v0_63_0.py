"""Batería v0.63.0 — zona segura del vertical y sonoridad MEDIDA.

Tres defectos reales del video vertical, y su arreglo:

1.  LOS SUBTÍTULOS TAPABAN EL ENLACE. En 9:16 se quemaban a 60 px del borde
    inferior, dentro de la franja de 430 px que la app reserva al nombre del
    canal y al ENLACE A VÍDEO RELACIONADO — el único mecanismo por el que una
    vista de Short se convierte en un clic al video largo.
2.  LA SONORIDAD SE ESTIMABA. Se aplicaba una ganancia fija de +1 dB
    confiando en que la suma diera ~-14 LUFS. Ahora se MIDE el archivo
    terminado y se corrige con una ganancia constante.
3.  EL LIMITADOR SUBÍA EL VOLUMEN. `alimiter` autonivela por defecto:
    limit=0.9 multiplicaba la salida por 1/0.9 y dejaba el techo real en
    0 dBFS en vez de -0,9 dB. Se desactiva con level=disabled.

Y la función nueva: la AUDITORÍA del archivo terminado, en la consola
(`python -m ytstudio auditar`) y en las dos interfaces.

Ninguna prueba usa claves ni internet. Las que miden audio necesitan ffmpeg.
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


from ytstudio import shorts  # noqa: E402
from ytstudio.catalog import FORMATS  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

# ---------------------------------------------------------------------------
# T1 — la zona segura: qué franja NO es nuestra
# ---------------------------------------------------------------------------
print("T1 zona segura del vertical")

V916 = {"video": {"width": 1080, "height": 1920}, "subtitles": {}}
H169 = {"video": {"width": 1920, "height": 1080}, "subtitles": {}}
V45 = {"video": {"width": 1080, "height": 1350}, "subtitles": {}}

check("T1a un 9:16 es encuadre de Shorts", shorts.is_shorts_frame(V916))
check("T1b un 16:9 no lo es", not shorts.is_shorts_frame(H169))
check("T1c un 4:5 (anuncio) no lo es", not shorts.is_shorts_frame(V45))

m = shorts.safe_margins(V916)
check("T1d los márgenes de 1080x1920 son los del framework",
      m == {"top": 390, "bottom": 430, "side": 90, "width": 900,
            "height": 1100}, str(m))
check("T1e en horizontal no hay zona segura que aplicar",
      shorts.safe_margins(H169) is None)

# Un vertical de otra resolución recibe los mismos márgenes EN PROPORCIÓN,
# no en píxeles fijos (que dejarían un 720x1280 medio tapado).
m720 = shorts.safe_margins({"video": {"width": 720, "height": 1280}})
check("T1f los márgenes escalan con la resolución",
      m720 and abs(m720["bottom"] / 1280 - 430 / 1920) < 0.01, str(m720))

# ---------------------------------------------------------------------------
# T2 — los subtítulos ya no tapan el enlace al video largo
# ---------------------------------------------------------------------------
print("\nT2 los subtítulos quemados dejan libre la franja del enlace")

ml, mr, mv = shorts.subtitle_margins(V916)
check("T2a en vertical suben por encima de la franja inferior",
      mv >= m["bottom"], f"MarginV={mv}, franja={m['bottom']}")
check("T2b respetan también el aire lateral",
      ml >= m["side"] and mr >= m["side"], f"{ml}/{mr}")
check("T2c en horizontal nada cambia",
      shorts.subtitle_margins(H169) == (80, 80, 60),
      str(shorts.subtitle_margins(H169)))
check("T2d se puede desactivar con subtitles.safe_zone: false",
      shorts.subtitle_margins(
          {"video": {"width": 1080, "height": 1920},
           "subtitles": {"safe_zone": False}}) == (80, 80, 60))

# El texto tiene que CABER en los 900 px útiles: si no, el motor de subtítulos
# parte la línea y aparece una tercera fila fuera de lo previsto.
for fid in ("short", "reel", "tiktok"):
    sub = FORMATS[fid]["overrides"]["subtitles"]
    ancho = sub["max_chars_per_line"] * sub["font_size"] * 0.55
    check(f"T2e el subtítulo de «{fid}» cabe en los 900 px útiles",
          ancho <= 900, f"~{ancho:.0f} px con {sub['font_size']}px "
                        f"x {sub['max_chars_per_line']} caracteres")

# Y el .ass que se escribe de verdad lleva esos márgenes, no los de siempre.
SUBS = (ROOT / "ytstudio" / "phases" / "subtitles.py").read_text(encoding="utf-8")
check("T2f el .ass usa los márgenes calculados, no valores fijos",
      "{ml},{mr},{mv},1" in SUBS and "subtitle_margins" in SUBS)

# ---------------------------------------------------------------------------
# T3 — el limitador ya no sube el volumen por su cuenta
# ---------------------------------------------------------------------------
print("\nT3 el limitador de picos es transparente")

ASM = (ROOT / "ytstudio" / "phases" / "assembly.py").read_text(encoding="utf-8")
MEDIA = (ROOT / "ytstudio" / "utils" / "media.py").read_text(encoding="utf-8")
check("T3a la mezcla final desactiva el autonivelado del limitador",
      "alimiter=limit={tp_limit}:level=disabled" in ASM)
check("T3b la corrección de sonoridad también",
      "level=disabled" in MEDIA)

# ---------------------------------------------------------------------------
# T4 — la sonoridad se MIDE y se corrige de verdad (necesita ffmpeg)
# ---------------------------------------------------------------------------
print("\nT4 sonoridad medida y corregida")

if not HAS_FFMPEG:
    print("      (sin ffmpeg: T4 se omite)")
else:
    from ytstudio.utils.media import measure_loudness, normalize_loudness

    tmp = Path(tempfile.mkdtemp(prefix="v0630_"))
    apagado = tmp / "apagado.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=22:sample_rate=48000",
         "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:r=24:d=22",
         "-af", "volume=-24dB", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(apagado)], check=True)

    antes = measure_loudness(apagado)
    check("T4a se mide la sonoridad real del archivo",
          antes and antes.get("input_i") is not None, str(antes))
    check("T4b y el archivo de prueba está efectivamente apagado",
          antes["input_i"] < -30, f"{antes['input_i']} LUFS")

    res = normalize_loudness(apagado, target_i=-14.0, target_tp=-1.0)
    despues = (res or {}).get("after") or {}
    check("T4c tras corregir, el archivo cae en el objetivo (-14 LUFS)",
          despues.get("input_i") is not None
          and abs(despues["input_i"] + 14.0) <= 0.6,
          f"{despues.get('input_i')} LUFS")
    check("T4d el pico real queda por debajo de -1,0 dBTP",
          despues.get("input_tp") is not None and despues["input_tp"] <= -1.0,
          f"{despues.get('input_tp')} dBTP")
    check("T4e volver a corregir no vuelve a tocar nada (es idempotente)",
          normalize_loudness(apagado)["gain_db"] == 0.0)
    check("T4f el video no se recodifica al corregir el audio",
          '"-c:v", "copy"' in MEDIA)

    # ---------------------------------------------------------------------
    # T5 — la auditoría mide y avisa
    # ---------------------------------------------------------------------
    print("\nT5 auditoría del archivo terminado")

    r = shorts.audit_file(apagado)
    check("T5a la ficha trae duración, tamaño y códec",
          (r["info"] or {}).get("width") == 1080
          and (r["info"] or {}).get("vcodec") == "h264", str(r["info"]))
    check("T5b y la sonoridad medida", (r["sonoridad"] or {}).get("input_i")
          is not None)
    check("T5c un archivo correcto no inventa problemas", not r["problemas"],
          str(r["problemas"]))

    # Un horizontal NO se clasifica como Short: eso es un problema, no un aviso
    hor = tmp / "horizontal.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=300:duration=8:sample_rate=48000",
         "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=24:d=8",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(hor)], check=True)
    rh = shorts.audit_file(hor)
    check("T5d un horizontal se marca como PROBLEMA (no será Short)",
          any("no es vertical" in p.lower() or "NO es vertical" in p
              for p in rh["problemas"]), str(rh["problemas"]))

    # Un vertical apagado tiene que salir como problema grave de sonoridad
    apagado2 = tmp / "apagado2.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=220:duration=22:sample_rate=48000",
         "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:r=24:d=22",
         "-af", "volume=-30dB", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(apagado2)], check=True)
    r2 = shorts.audit_file(apagado2)
    check("T5e un vertical apagado sale como PROBLEMA de sonoridad",
          any("LUFS" in p for p in r2["problemas"]), str(r2["problemas"]))
    check("T5f y el aviso explica que la plataforma NO sube lo que suena bajo",
          any("NO sube" in p for p in r2["problemas"]))

    # Auditar una CARPETA entera
    check("T5g se puede auditar una carpeta completa",
          len(shorts.audit_paths([tmp])) == 3,
          str(len(shorts.audit_paths([tmp]))))

    informe = "\n".join(shorts.report_lines([r2]))
    check("T5h el informe dice lo que una medición NO puede ver",
          "doble pista" in informe or "sonido apagado" in informe)

    # El comando de consola funciona de verdad
    out = subprocess.run([sys.executable, "-m", "ytstudio", "auditar", str(tmp)],
                         capture_output=True, text=True, cwd=str(ROOT),
                         encoding="utf-8", errors="replace")
    check("T5i «python -m ytstudio auditar CARPETA» funciona",
          out.returncode == 0 and "AUDITORÍA" in out.stdout,
          (out.stderr or out.stdout)[-400:])

    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
# T6 — la regla dura de los 60 segundos
# ---------------------------------------------------------------------------
print("\nT6 la regla de los 60 segundos")

largo = shorts.evaluate(
    {"duration": 78.0, "width": 1080, "height": 1920, "vcodec": "h264",
     "acodec": "aac", "sample_rate": 48000, "has_audio": True}, None)[1]
check("T6a un vertical de más de 60 s avisa del BLOQUEO global",
      any("bloquea" in a.lower() for a in largo), str(largo))
corto = shorts.evaluate(
    {"duration": 40.0, "width": 1080, "height": 1920, "vcodec": "h264",
     "acodec": "aac", "sample_rate": 48000, "has_audio": True}, None)[1]
check("T6b por debajo de 60 s no molesta con ese aviso",
      not any("bloquea" in a.lower() for a in corto), str(corto))
check("T6c el montaje comprueba la regla contra la música del proyecto",
      "60" in ASM and "reclamación de copyright" in ASM)

# ---------------------------------------------------------------------------
# T7 — está enchufado: configuración, servidor y las DOS interfaces
# ---------------------------------------------------------------------------
print("\nT7 enchufado al programa")

CFG = (ROOT / "config.yaml").read_text(encoding="utf-8")
check("T7a config.yaml trae el objetivo de sonoridad", "target_lufs: -14" in CFG)
check("T7b y el interruptor de la zona segura", "safe_zone: true" in CFG)

from ytstudio.webui import server as srv  # noqa: E402
check("T7c el servidor expone la medición del proyecto",
      hasattr(srv, "api_audit_project"))
SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T7d con su ruta /audit", "/audit" in SRV)
check("T7e y el detalle del proyecto lleva la última medición",
      '"shorts_audit"' in SRV or "'shorts_audit'" in SRV)

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T7f la interfaz {nombre} muestra la revisión técnica",
          "Revisión técnica" in html)
    check(f"T7g la interfaz {nombre} deja volver a medir",
          "/audit" in html and "Medir el archivo" in html)

# ---------------------------------------------------------------------------
# T8 — los dos manuales lo cuentan
# ---------------------------------------------------------------------------
print("\nT8 los manuales al día")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T8a el manual {nombre} explica la zona segura",
          "zona segura" in texto.lower())
    check(f"T8b el manual {nombre} explica la revisión técnica",
          "Revisión técnica" in texto or "revisión técnica" in texto)
    # Se comprueba que el manual DECLARE una versión, no que sea esta: una
    # batería no puede exigir seguir siendo la más nueva del programa.
    check(f"T8c el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T8d el CHANGELOG cuenta lo que trajo la v0.63.0",
      "## v0.63.0" in CHANGELOG)

# ---------------------------------------------------------------------------
print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.63.0: zona segura, sonoridad medida y auditoría — todo correcto.")
