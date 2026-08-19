"""Batería v0.65.1 — el enlace de YouTube que se atragantaba.

Caso real del creador: pidió 5 Shorts pegando el enlace de un video y le salió
una traza cruda en la interfaz («ERROR: Unable to download video subtitles for
'en': HTTP Error 429: Too Many Requests»), el registro de eventos no se enteró
de nada, y la consola escupió además un ConnectionAbortedError.

Cuatro problemas encadenados, y su arreglo:

1.  SE PEDÍAN TRES PISTAS DE SUBTÍTULOS (el idioma del proyecto, su variante
    «-orig» e inglés) aunque solo se usara la primera: tres descargas contra
    YouTube por consulta, que es justo lo que dispara el bloqueo por
    «demasiadas peticiones». Ahora se mira qué pistas existen —eso viene en
    los metadatos, sin descargar— y se pide EXACTAMENTE UNA.
2.  UN FALLO EN UNA PISTA MATABA TODO. El error de yt-dlp no era ni
    RuntimeError ni ValueError, así que escapaba al manejador genérico y
    llegaba crudo a la pantalla, con códigos de color incluidos.
3.  NO QUEDABA RASTRO EN EL LOG. Estos endpoints nunca escribían en él.
4.  EL RUIDO DE CONEXIÓN. Cerrar la pestaña imprimía treinta líneas de
    traza que no significan nada.

Y el rescate: si el enlace falla pero el proyecto ya tiene escenas, se usan
ESAS —que son mejor fuente: el guion exacto, no subtítulos automáticos— y se
avisa del cambio.

Ninguna prueba usa claves ni internet: el enlace se simula.
"""

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


WORK = Path(tempfile.mkdtemp(prefix="v0651_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as elog  # noqa: E402
elog.LOG_PATH = WORK / "data" / "events.log"

from ytstudio import derive  # noqa: E402
from ytstudio.project import DIRS, Project  # noqa: E402

# ---------------------------------------------------------------------------
# T1 — el error de YouTube, traducido a algo que se pueda leer
# ---------------------------------------------------------------------------
print("T1 el mensaje de error")

CRUDO = ("\x1b[0;31mERROR:\x1b[0m Unable to download video subtitles for "
         "'en': HTTP Error 429: Too Many Requests")
msg = derive._limpiar_error_ytdlp(CRUDO)
check("T1a el 429 se explica sin jerga",
      "limitando" in msg and "429" in msg, msg[:90])
check("T1b sin códigos de color de consola",
      "\x1b" not in msg and "[0;31m" not in msg and "ERROR:" not in msg,
      repr(msg[:50]))
check("T1c dice qué hacer: esperar, o dejar el enlace vacío",
      "Espera" in msg and "VAC" in msg)
check("T1d aclara que NO es culpa del programa", "NO es un fallo" in msg)

priv = derive._limpiar_error_ytdlp("ERROR: Private video. Sign in if you...")
check("T1e un video privado se explica aparte",
      "privado" in priv.lower(), priv[:60])
noexiste = derive._limpiar_error_ytdlp("ERROR: Video unavailable")
check("T1f un video no disponible también",
      "no está disponible" in noexiste, noexiste[:60])

# ---------------------------------------------------------------------------
# T2 — se pide UNA sola pista de subtítulos, la correcta
# ---------------------------------------------------------------------------
print("\nT2 elegir la pista de subtítulos")

pick = derive._elegir_idioma_subtitulos
check("T2a prefiere los subtítulos PROPIOS del idioma del proyecto",
      pick({"subtitles": {"es": [{}], "en": [{}]},
            "automatic_captions": {"es": [{}]}}, "es") == ("es", False))
check("T2b si no hay propios, tira de los automáticos del mismo idioma",
      pick({"subtitles": {},
            "automatic_captions": {"es": [{}], "en": [{}]}}, "es")
      == ("es", True))
check("T2c una variante regional gana a otro idioma (es-419 antes que en)",
      pick({"subtitles": {},
            "automatic_captions": {"es-419": [{}], "en": [{}]}}, "es")[0]
      == "es-419",
      str(pick({"subtitles": {},
                "automatic_captions": {"es-419": [{}], "en": [{}]}}, "es")))
check("T2d si no está tu idioma, usa el del video antes que rendirse",
      pick({"language": "de", "subtitles": {},
            "automatic_captions": {"de": [{}]}}, "es")[0] == "de")
check("T2e sin ninguna pista, lo dice (None)",
      pick({"subtitles": {}, "automatic_captions": {}}, "es") == (None, False))
check("T2f el chat en directo no es una pista de subtítulos",
      pick({"subtitles": {"live_chat": [{}]},
            "automatic_captions": {}}, "es") == (None, False))

DER = (ROOT / "ytstudio" / "derive.py").read_text(encoding="utf-8")
check("T2g los metadatos se consultan SIN descargar (una petición menos)",
      "extract_info(url, download=False)" in DER)
check("T2h y luego se pide exactamente una pista",
      '"subtitleslangs": [code]' in DER)
check("T2i un fallo de una pista ya no tira la operación entera",
      '"ignoreerrors": True' in DER)
check("T2j y el 429 se reintenta con espera antes de rendirse",
      "_con_reintentos" in DER and "esperas = [0, 4, 12]" in DER)

# ---------------------------------------------------------------------------
# T3 — el rescate: si el enlace falla, se usa el propio proyecto
# ---------------------------------------------------------------------------
print("\nT3 el rescate al material del proyecto")

p = Project.create("test-3-hetty")
p.state["display_name"] = "test-3-hetty"
p.save()
p.set("metadata", {"title": "Herencia financiera"})
(p.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
    {"id": i, "section": "Desarrollo", "duration": 25.0,
     "narration": f"Frase {i} del guion."} for i in range(1, 25)]}),
    encoding="utf-8")

from ytstudio.webui import server as srv  # noqa: E402
srv.Project = Project
_original = derive.source_from_url


def _falla(url, cfg, work_dir=None):
    raise RuntimeError("YouTube está limitando las peticiones (error 429).")


derive.source_from_url = _falla
try:
    plan = srv.api_derive_propose({"slug": "test-3-hetty",
                                   "url": "https://youtu.be/h04ZlUQCqQA",
                                   "n": 5})
    check("T3a el enlace falla, pero la propuesta SALE igual",
          len(plan["candidatos"]) > 0, str(len(plan.get("candidatos", []))))
    check("T3b se avisa de que se cambió de fuente",
          "material de ESTE proyecto" in (plan.get("nota") or ""),
          (plan.get("nota") or "")[:80])
    check("T3c la nota conserva el motivo original",
          "429" in (plan.get("nota") or ""))
    check("T3d y explica que el proyecto es MEJOR fuente",
          "mejor fuente" in (plan.get("nota") or ""))

    # Sin proyecto detrás no hay rescate posible, pero el error es legible
    try:
        srv.api_derive_propose({"url": "https://youtu.be/x", "n": 3})
        check("T3e sin proyecto, error controlado", False, "no lanzó nada")
    except srv.ApiError as e:
        check("T3e sin proyecto, error controlado y legible",
              "429" in e.message and "Traceback" not in e.message,
              e.message[:60])

    # Un proyecto SIN escenas tampoco puede rescatar: se explica, no se rompe
    Project.create("sin-escenas")
    try:
        srv.api_derive_propose({"slug": "sin-escenas",
                                "url": "https://youtu.be/x", "n": 3})
        check("T3f un proyecto sin escenas no rescata, pero avisa", False,
              "no lanzó nada")
    except srv.ApiError as e:
        check("T3f un proyecto sin escenas no rescata, pero avisa",
              "429" in e.message, e.message[:60])
finally:
    derive.source_from_url = _original

# ---------------------------------------------------------------------------
# T4 — todo queda en el registro de eventos
# ---------------------------------------------------------------------------
print("\nT4 el registro de eventos")

log = elog.raw_text()
check("T4a el fallo al leer el enlace queda registrado",
      "No se pudo leer el enlace" in log)
check("T4b el rescate también", "material de ESTE proyecto" in log)
check("T4c y la propuesta que sí salió", "Short(s) propuestos" in log)
check("T4d los eventos van marcados como fase «shorts»",
      '"phase": "shorts"' in log)
check("T4e y los fallos con nivel de error", '"level": "error"' in log)

SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T4f un error inesperado (500) también deja rastro",
      "_log_derive(\"error\", f\"{self.command} {self.path}" in SRV)

# ---------------------------------------------------------------------------
# T5 — el ruido de conexión ya no asusta
# ---------------------------------------------------------------------------
print("\nT5 el ruido de la ventana negra")

check("T5a cerrar la pestaña ya no imprime una traza",
      "def handle_one_request" in SRV
      and "ConnectionAbortedError" in SRV
      and "BrokenPipeError" in SRV)
check("T5b y se explica por qué no es un fallo",
      "no significa nada" in SRV or "no hay nada que arreglar" in SRV)

# ---------------------------------------------------------------------------
# T6 — la interfaz enseña la nota del rescate
# ---------------------------------------------------------------------------
print("\nT6 la interfaz")

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T6a la interfaz {nombre} muestra la nota del cambio de fuente",
          "plan.nota" in html and "Se usó otra fuente" in html)

# ---------------------------------------------------------------------------
# T7 — documentación
# ---------------------------------------------------------------------------
print("\nT7 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T7a el manual {nombre} explica qué hacer con el error 429",
          "429" in texto)
    check(f"T7b el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T7c el CHANGELOG cuenta lo que arregló la v0.65.1",
      "## v0.65.1" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.65.1: el enlace de YouTube ya no se atraganta.")
