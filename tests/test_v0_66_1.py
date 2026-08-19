"""Batería v0.66.1 — un recorte dura lo que dura su tramo, y los errores de
la descarga se explican.

Dos fallos que el creador vio nada más fusionar la v0.66.0:

1.  LA FICHA MENTÍA. En modo recorte, el modelo propone un tramo («del
    minuto 1:04 al 1:59») y, aparte, estima una duración para la pieza. Los
    dos datos se guardaban sin cuadrarlos, así que la ficha del Short podía
    decir 38 s mientras el video que salía duraba 53 s. Todo lo que se
    calcula a partir de la duración (la duración objetivo del proyecto, la
    escena, el aviso de los 60 s de copyright) trabajaba con un dato falso.
    En un recorte la pieza ES el tramo: manda el tramo.

2.  EL ERROR DE DESCARGA VENÍA EN CRUDO. Si el enlace no servía, el creador
    veía «ERROR: Unsupported URL: https://…» a mitad del montaje, sin saber
    qué hacer. Ahora se traduce y se le dice la salida: el modo «pieza
    nueva» no necesita descargar nada.

No usa claves ni internet.
"""

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


WORK = Path(tempfile.mkdtemp(prefix="v0661_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"
import ytstudio.eventlog as el  # noqa: E402
el.LOG_PATH = WORK / "data" / "events.log"

import yaml  # noqa: E402

from ytstudio import clip, derive  # noqa: E402
from ytstudio.project import Project  # noqa: E402

CFG = {"language": "es", "providers": {"llm": {"name": "mock"}}}

# ---------------------------------------------------------------------------
# T1 — el tramo y la duración dicen lo mismo
# ---------------------------------------------------------------------------
print("T1 el tramo manda")

c = derive.ajustar_tramo({"desde": 64, "hasta": 119, "duracion": 38})
check("T1a la duración se toma del tramo, no de la estimación",
      c["duracion"] == 55, str(c["duracion"]))
check("T1b y el tramo se queda como estaba",
      (c["desde"], c["hasta"]) == (64, 119), f"{c['desde']}-{c['hasta']}")

largo = derive.ajustar_tramo({"desde": 10, "hasta": 400, "duracion": 45})
check("T1c un tramo de más de 60 s se corta a 60 (o lo bloquean por copyright)",
      largo["duracion"] == 60 and largo["hasta"] == 70.0,
      f"{largo['duracion']}s · {largo['desde']}-{largo['hasta']}")

corto = derive.ajustar_tramo({"desde": 5, "hasta": 8, "duracion": 40})
check("T1d un tramo de tres segundos se estira al mínimo",
      corto["duracion"] == derive.DURACION_MIN, str(corto["duracion"]))

sin_tramo = derive.ajustar_tramo({"duracion": 42})
check("T1e sin tramo, se cae a la duración de la ficha",
      sin_tramo["duracion"] == 42 and sin_tramo["hasta"] == 42.0,
      str(sin_tramo))

reves = derive.ajustar_tramo({"desde": 90, "hasta": 30, "duracion": 35})
check("T1f un tramo del revés no rompe nada",
      reves["hasta"] > reves["desde"] and reves["duracion"] == 35,
      str(reves))

roto = derive.ajustar_tramo({"desde": "x", "hasta": None, "duracion": "y"})
check("T1g y con datos basura tampoco",
      derive.DURACION_MIN <= roto["duracion"] <= derive.DURACION_MAX,
      str(roto))

# ---------------------------------------------------------------------------
# T2 — el proyecto que nace de ese candidato
# ---------------------------------------------------------------------------
print("\nT2 el Short que nace")

SOURCE = {"url": "https://youtu.be/ABC123XYZ", "titulo": "El video largo",
          "slug": "largo", "marcas": [{"t": 70, "t_fin": 74, "texto": "Una frase."}]}

CAND = {"nombre": "recorte de prueba", "idea": "Un momento fuerte",
        "guion": "Da igual lo que ponga aquí: en un recorte no se usa.",
        "gancho_tipo": "pregunta_personal", "funcion": "promesa",
        "desde": 64, "hasta": 119, "duracion": 38, "modo": "recorte",
        "titulo_youtube": "El dato que nadie esperaba", "hashtags": ["#uno"],
        "texto_pantalla": "NADIE LO DIJO", "cta": "Míralo entero",
        "origen_url": SOURCE["url"], "origen_titulo": SOURCE["titulo"],
        "origen_slug": "largo"}

slug = derive.create_short_project(dict(CAND), CFG, source=SOURCE)
q = Project(slug)
qcfg = yaml.safe_load((q.dir / "config.yaml").read_text(encoding="utf-8"))

check("T2a nace en modo recorte", q.get("shorts_modo") == "recorte",
      str(q.get("shorts_modo")))
check("T2b la duración objetivo es la del tramo (55 s), no la estimada (38 s)",
      abs(qcfg["video"]["target_minutes"] - 55 / 60) < 0.01,
      str(qcfg["video"]["target_minutes"]))
check("T2c la ficha del Short dice esos mismos segundos",
      (q.get("shorts_plan") or {}).get("duracion") == 55,
      str((q.get("shorts_plan") or {}).get("duracion")))
check("T2d y la escena del recorte también",
      abs(float(q.get("total_duration") or 0) - 55) < 0.6,
      str(q.get("total_duration")))
check("T2e el tramo guardado para descargar es el mismo",
      (q.get("clip_source") or {}).get("hasta") == 119,
      str((q.get("clip_source") or {}).get("hasta")))
check("T2f y el origen apuntado, también",
      (q.get("derived_from") or {}).get("hasta") == 119,
      str(q.get("derived_from")))

# El texto que ve el creador en la ficha del proyecto tiene que decir 55 s
ficha = (q.path("input") / "ficha_short.md").read_text(encoding="utf-8")
check("T2g la ficha que lee el creador dice 55 s, no 38 s",
      "**Duración objetivo:** 55 s" in ficha,
      next((l for l in ficha.splitlines() if "Duración" in l), "(sin línea)"))

# En «pieza nueva» NO se toca nada: el tramo solo señala de dónde salió la idea
nuevo = dict(CAND, modo="nuevo", nombre="pieza nueva de prueba")
slug2 = derive.create_short_project(nuevo, CFG, source=SOURCE)
q2 = Project(slug2)
q2cfg = yaml.safe_load((q2.dir / "config.yaml").read_text(encoding="utf-8"))
check("T2h una pieza NUEVA conserva su duración estimada",
      abs(q2cfg["video"]["target_minutes"] - 38 / 60) < 0.01,
      str(q2cfg["video"]["target_minutes"]))

# ---------------------------------------------------------------------------
# T3 — lo mismo, pasando por la normalización de una propuesta
# ---------------------------------------------------------------------------
print("\nT3 la propuesta llega cuadrada")

crudos = [dict(CAND, funcion="promesa"), dict(CAND, funcion="emocion",
                                             desde=200, hasta=380)]
norm = derive.normalize(crudos, SOURCE, 2, modo="recorte", puede_recortar=True)
check("T3a todo recorte sale con su duración cuadrada",
      all(abs((x["hasta"] - x["desde"]) - x["duracion"]) < 0.5 for x in norm),
      str([(x["desde"], x["hasta"], x["duracion"]) for x in norm]))
check("T3b y ninguno pasa de 60 s",
      all(x["duracion"] <= derive.DURACION_MAX for x in norm),
      str([x["duracion"] for x in norm]))

sin_recorte = derive.normalize([dict(CAND)], SOURCE, 1, modo="recorte",
                               puede_recortar=False)
check("T3c sin poder recortar, la pieza es nueva y su tramo no se toca",
      sin_recorte[0]["modo"] == "nuevo" and sin_recorte[0]["duracion"] == 38,
      str(sin_recorte[0]["duracion"]))

# ---------------------------------------------------------------------------
# T4 — el error de descarga, en cristiano
# ---------------------------------------------------------------------------
print("\nT4 cuando el enlace no sirve")


class _YdlFalso:
    """Imita a yt_dlp lo justo para reventar como revienta él."""
    def __init__(self, mensaje):
        self.mensaje = mensaje

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        raise RuntimeError(self.mensaje)


def _fallo_al_descargar(mensaje):
    import yt_dlp
    real = yt_dlp.YoutubeDL
    yt_dlp.YoutubeDL = lambda opts: _YdlFalso(mensaje)
    try:
        clip.download_segment("https://youtu.be/ABC123XYZ", 10, 40,
                              WORK / "dl", {})
        return ""
    except Exception as e:  # noqa: BLE001
        return str(e)
    finally:
        yt_dlp.YoutubeDL = real


if clip.available():
    msg = _fallo_al_descargar(
        "\x1b[0;31mERROR:\x1b[0m Unsupported URL: https://youtu.be/ABC123XYZ")
    check("T4a el error crudo de yt-dlp no llega al creador",
          "Unsupported URL" not in msg, msg[:160])
    check("T4b se le dice qué pasa con el enlace",
          "enlace" in msg.lower() or "dirección" in msg.lower(), msg[:160])
    check("T4c y se le da la salida: el modo «pieza nueva»",
          "pieza nueva" in msg, msg[:200])
    check("T4d sin códigos de color de consola",
          "\x1b" not in msg and "[0;31m" not in msg, repr(msg[:80]))

    caido = _fallo_al_descargar(
        "ERROR: Unable to connect to proxy: Tunnel connection failed")
    check("T4e un fallo de conexión se explica como tal",
          "conexión" in caido.lower() or "internet" in caido.lower(),
          caido[:160])
    privado = _fallo_al_descargar("ERROR: Private video. Sign in")
    check("T4f y un video privado, como tal",
          "privado" in privado.lower(), privado[:160])
else:
    print("   (yt-dlp no instalado: T4 se salta)")
    check("T4z sin yt-dlp el recorte se declara imposible",
          derive.modo_disponible(SOURCE, {})[1] is False)

# La traducción, por su cuenta
check("T4g «Unsupported URL» se traduce",
      "Unsupported" not in derive._limpiar_error_ytdlp(
          "ERROR: Unsupported URL: https://x"),
      derive._limpiar_error_ytdlp("ERROR: Unsupported URL: https://x")[:120])
check("T4h y el 429 se sigue traduciendo como antes",
      "429" in derive._limpiar_error_ytdlp("ERROR: HTTP Error 429: Too Many Requests"))

# ---------------------------------------------------------------------------
# T5 — que las baterías sigan probando lo que dicen probar
# ---------------------------------------------------------------------------
print("\nT5 las pruebas de siempre")

e2e = (ROOT / "tests" / "test_e2e_derivado.py").read_text(encoding="utf-8")
check("T5a la prueba de punta a punta fija el modo «pieza nueva»",
      '"modo"] = "nuevo"' in e2e or "'modo'] = 'nuevo'" in e2e)
check("T5b y comprueba que el proyecto nació así",
      'shorts_modo") == "nuevo"' in e2e)

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T5c el CHANGELOG cuenta lo que arregló la v0.66.1",
      "## v0.66.1" in CHANGELOG)

for nombre, ruta in (("nuevo", "MANUAL.md"), ("clásico", "MANUAL-clasica.md")):
    texto = (ROOT / ruta).read_text(encoding="utf-8")
    check(f"T5d el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.66.1: el recorte dura lo que su tramo y los errores se explican.")
