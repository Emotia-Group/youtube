"""Batería v0.64.0 — sacar Shorts de un video largo.

La función que faltaba: hasta ahora un Short nacía de cero (le dabas un tema).
Ahora se puede partir de un video largo —un proyecto de la casa o cualquier
enlace de YouTube— y sacarle las piezas que aguantan solas.

Lo que se comprueba:

1.  El material sale con su MINUTO. Sin el minuto no se puede señalar de dónde
    viene cada Short (el lector que ya existía tiraba los tiempos a propósito).
2.  Las reglas del framework llegan al director: una sola idea, gancho antes
    del medio segundo, texto en pantalla desde el fotograma 1, un solo CTA
    hacia el VIDEO LARGO, y nunca más de 60 s.
3.  La ROTACIÓN de estructuras de gancho se exige y se comprueba: repetir la
    misma fórmula es el patrón que las políticas describen como producción en
    masa.
4.  El calendario reparte las piezas alrededor del video largo (D-4 → D+9).
5.  Cada Short creado nace vertical, con su guion como GUION (no como idea),
    con su plantilla de estructura y APUNTANDO al video largo.
6.  Y se genera de verdad: hay un end-to-end aparte (test_e2e_derivado).

Ninguna prueba usa claves ni internet: el director trabaja en modo prueba.
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


WORK = Path(tempfile.mkdtemp(prefix="v0640_"))
import ytstudio.project as prj  # noqa: E402
prj.PROJECTS_DIR = WORK / "projects"

from ytstudio import derive  # noqa: E402
from ytstudio.catalog import SHORT_TEMPLATES  # noqa: E402
from ytstudio.config import load_config  # noqa: E402
from ytstudio.project import DIRS, Project  # noqa: E402

CFG = {"language": "es", "providers": {"llm": {"name": "mock"}}}


def _proyecto_largo(slug="largo", escenas=30, youtube_id="ABC123XYZ"):
    p = Project.create(slug)
    p.state["display_name"] = "El documental largo"
    p.save()
    p.set("metadata", {"title": "La historia que nadie contó"})
    p.set("concept", {"angle": "Investigación", "tone": "Sobrio",
                      "audience": "Adultos"})
    if youtube_id:
        p.set("youtube_id", youtube_id)
    (p.dir / DIRS["scenes"] / "scenes.json").write_text(json.dumps({"scenes": [
        {"id": i, "section": "Desarrollo", "duration": 30.0,
         "narration": f"Frase número {i} de la narración."}
        for i in range(1, escenas + 1)]}), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# T1 — el material del video largo, con su minuto
# ---------------------------------------------------------------------------
print("T1 leer el video largo")

_proyecto_largo()
src = derive.source_from_project("largo")
check("T1a se leen las frases del video largo", len(src["marcas"]) == 30,
      str(len(src["marcas"])))
check("T1b cada frase trae SU MINUTO (sin eso no se puede señalar nada)",
      src["marcas"][1]["t"] == 30.0 and src["marcas"][2]["t"] == 60.0,
      str(src["marcas"][:3]))
check("T1c y la duración total sale de las escenas", src["duracion"] == 900.0,
      str(src["duracion"]))
check("T1d se conserva el enlace al video largo publicado",
      src["url"] == "https://youtu.be/ABC123XYZ", src["url"])

# Un proyecto sin escenas no se puede leer, y hay que decirlo con claridad
Project.create("vacio")
try:
    derive.source_from_project("vacio")
    check("T1e un proyecto sin escenas avisa en vez de romperse", False,
          "no lanzó nada")
except ValueError as e:
    check("T1e un proyecto sin escenas avisa en vez de romperse",
          "escenas" in str(e).lower(), str(e))

# El lector de subtítulos CON tiempos (el que ya existía los tiraba)
vtt = WORK / "sub.vtt"
vtt.write_text("WEBVTT\n\n00:00:05.000 --> 00:00:08.000\nPrimera frase\n\n"
               "00:01:12.500 --> 00:01:15.000\nSegunda frase\n",
               encoding="utf-8")
marcas = derive._parse_vtt_timed(vtt)
check("T1f los subtítulos se leen con su tiempo",
      [m["t"] for m in marcas] == [5.0, 72.5], str(marcas))

# La transcripción se reparte por TODO el video: si se recortara por el final,
# todos los Shorts saldrían del principio.
largo = {"marcas": [{"t": i * 10.0, "seccion": "", "texto": f"linea {i} " + "x" * 60}
                    for i in range(400)]}
bloque = derive.transcript_block(largo, max_chars=2000)
check("T1g al recortar la transcripción se conserva el final del video",
      "linea 39" in bloque or int(bloque.strip().splitlines()[-1]
                                  .split("linea ")[1].split()[0]) > 300,
      bloque.strip().splitlines()[-1][:60])

# ---------------------------------------------------------------------------
# T2 — las reglas que se le exigen al director
# ---------------------------------------------------------------------------
print("\nT2 las reglas del framework llegan al director")

prompt = derive._prompt(src, 5, list(derive.HOOK_STRUCTURES))
sistema = derive._system_prompt("español")
for etiqueta, texto in (
        ("una sola idea por Short", "UNA SOLA IDEA"),
        ("el gancho va antes del medio segundo", "medio segundo"),
        ("texto en pantalla desde el fotograma 1", "primer fotograma"),
        ("la regla de doble pista (se ve sin sonido)", "SIN SONIDO"),
        ("el bloque de PAGO, sin el que no hay «me gusta»", "PAGO"),
        ("el cierre que enlaza con el principio", "ENLACE CON EL PRINCIPIO"),
        ("nunca más de 60 segundos", "más de 60"),
        ("rotar las estructuras de gancho", "ROTA LAS ESTRUCTURAS"),
        ("sin el hashtag de Shorts", "mito de 2021")):
    check(f"T2a el director recibe: {etiqueta}", texto in prompt, texto)
check("T2b y trabaja con el modelo de adquisición (llevar al video largo)",
      "ADQUISICIÓN" in sistema and "NUNCA la suscripción" in sistema)
check("T2c con el final ABIERTO: la resolución está en el largo",
      "ABIERTO" in sistema)

# ---------------------------------------------------------------------------
# T3 — la propuesta, normalizada
# ---------------------------------------------------------------------------
print("\nT3 la propuesta")

cands = derive.propose(src, CFG, n=5)
check("T3a devuelve candidatos", len(cands) >= 3, str(len(cands)))
check("T3b ninguno pasa de 60 s (por encima, una reclamación bloquea)",
      all(c["duracion"] <= 60 for c in cands),
      str([c["duracion"] for c in cands]))
check("T3c ninguno baja de la banda útil",
      all(c["duracion"] >= derive.DURACION_MIN for c in cands))
check("T3d cada uno trae su guion completo",
      all(len((c.get("guion") or "").split()) > 40 for c in cands))
check("T3e cada uno trae el texto que va en pantalla",
      all((c.get("texto_pantalla") or "").strip() for c in cands))
check("T3f cada uno apunta al video largo del que salió",
      all(c["origen_url"] == "https://youtu.be/ABC123XYZ" for c in cands))
check("T3g cada uno sabe de qué minuto sale",
      all(isinstance(c.get("desde"), (int, float)) for c in cands))
check("T3h van ordenados por su día de campaña",
      [c["dia"] for c in cands] == sorted(c["dia"] for c in cands))
check("T3i cada estructura de gancho trae su plantilla de guion",
      all(c["plantilla"] in SHORT_TEMPLATES for c in cands),
      str([c["plantilla"] for c in cands]))

# Dos piezas NUNCA pueden ocupar el mismo hueco de campaña
repes = [{"guion": "x " * 60, "gancho_tipo": "mito_desmontado",
          "funcion": "promesa", "duracion": 40} for _ in range(4)]
norm = derive.normalize(repes, src, 4)
check("T3j si el director repite hueco de campaña, se reparte igualmente",
      len({c["funcion"] for c in norm}) == 4,
      str([c["funcion"] for c in norm]))

# Un candidato sin guion no se cuela
check("T3k un candidato sin guion se descarta",
      len(derive.normalize([{"guion": "  ", "gancho_tipo": "mito_desmontado",
                             "funcion": "promesa"}], src, 3)) == 0)

# Una duración inventada por encima del minuto se corrige sola
check("T3l una duración imposible se recorta a 60 s",
      derive.normalize([{"guion": "x " * 60, "gancho_tipo": "mito_desmontado",
                         "funcion": "promesa", "duracion": 300}],
                       src, 1)[0]["duracion"] == 60)

# ---------------------------------------------------------------------------
# T4 — rotación de ganchos: no es estética, es la defensa
# ---------------------------------------------------------------------------
print("\nT4 rotación de estructuras de gancho")

check("T4a hay seis estructuras registradas",
      len(derive.HOOK_STRUCTURES) == 6, str(len(derive.HOOK_STRUCTURES)))
check("T4b la tanda de ejemplo rota lo suficiente",
      derive.rotation_report(cands)["suficiente"],
      str(derive.rotation_report(cands)))

iguales = [{"gancho_tipo": "mito_desmontado"} for _ in range(5)]
r = derive.rotation_report(iguales)
check("T4c cinco piezas con el mismo gancho se marcan como insuficientes",
      not r["suficiente"] and r["estructuras"] == 1, str(r))
check("T4d y se cuentan las repetidas seguidas", r["repetidas_seguidas"] == 4,
      str(r))

# ---------------------------------------------------------------------------
# T5 — el calendario de campaña
# ---------------------------------------------------------------------------
print("\nT5 calendario alrededor del video largo")

check("T5a hay siete huecos, de D-4 a D+9", len(derive.CAMPAIGN) == 7)
check("T5b van de lo general a lo específico",
      [c["dia"] for c in derive.CAMPAIGN] == [-4, -2, 0, 2, 4, 7, 9],
      str([c["dia"] for c in derive.CAMPAIGN]))
check("T5c la pieza de EXPANSIÓN (la que trae público nuevo) va después",
      derive.CAMPAIGN_BY_ID["expansion"]["dia"] > 0)
cal = derive.calendar(cands, "2026-09-10")
check("T5d el calendario da fechas reales", all(x["fecha"][:4] == "2026" for x in cal),
      str(cal[:1]))
check("T5e con su etiqueta legible",
      all(x["etiqueta"].startswith("D") for x in cal), str([x["etiqueta"] for x in cal]))
check("T5f y explica para qué sirve cada hueco", all(len(x["para"]) > 20 for x in cal))
check("T5g la etiqueta del día del video largo es D0",
      derive.campaign_label(0) == "D0" and derive.campaign_label(-4) == "D-4"
      and derive.campaign_label(7) == "D+7")

# ---------------------------------------------------------------------------
# T6 — de candidato a proyecto de verdad
# ---------------------------------------------------------------------------
print("\nT6 los proyectos que nacen")

slug = derive.create_short_project(cands[0], CFG)
q = Project(slug)
qcfg = load_config(q.dir)
check("T6a nace en formato Short", q.get("format") == "short", str(q.get("format")))
check("T6b vertical 1080x1920",
      (qcfg["video"]["width"], qcfg["video"]["height"]) == (1080, 1920),
      f"{qcfg['video']['width']}x{qcfg['video']['height']}")
check("T6c con subtítulos quemados", qcfg["video"]["burn_subtitles"])
check("T6d con la duración de la pieza, no la del video largo",
      abs(qcfg["video"]["target_minutes"] - cands[0]["duracion"] / 60) < 0.02,
      str(qcfg["video"]["target_minutes"]))
check("T6e con la plantilla de estructura que le toca",
      q.get("short_template") == cands[0]["plantilla"],
      str(q.get("short_template")))
check("T6f APUNTANDO al video largo",
      (q.get("derived_from") or {}).get("url") == "https://youtu.be/ABC123XYZ",
      str(q.get("derived_from")))
check("T6g y guarda de qué minuto salió",
      (q.get("derived_from") or {}).get("desde") is not None)

assets = q.get("assets") or []
check("T6h el guion entra como GUION, no como idea suelta",
      any(a["category"] == "guion" for a in assets), str(assets))
guion = (q.dir / DIRS["input"] / "guion_short.md").read_text(encoding="utf-8")
check("T6i y es el guion del candidato, palabra por palabra",
      cands[0]["guion"].split(".")[0] in guion, guion[:80])

ficha = (q.dir / DIRS["input"] / "ficha_short.md").read_text(encoding="utf-8")
for etiqueta, texto in (("el título para YouTube", cands[0]["titulo_youtube"]),
                        ("el enlace al video largo", "https://youtu.be/ABC123XYZ"),
                        ("que el enlace se pone A MANO en Studio", "A MANO"),
                        ("que se puede añadir DESPUÉS de publicar", "DESPUÉS de publicar")):
    check(f"T6j la ficha guarda {etiqueta}", texto in ficha, texto[:40])

# Dos Shorts con el mismo nombre no se pisan
otro = derive.create_short_project(cands[0], CFG)
check("T6k un nombre repetido no pisa el proyecto anterior",
      otro != slug and Project.exists(slug) and Project.exists(otro),
      f"{slug} vs {otro}")

# ---------------------------------------------------------------------------
# T7 — enchufado: servidor, consola y las DOS interfaces
# ---------------------------------------------------------------------------
print("\nT7 enchufado al programa")

from ytstudio.webui import server as srv  # noqa: E402
srv.Project = Project
plan = srv.api_derive_propose({"slug": "largo", "n": 5, "desde": "2026-09-10"})
check("T7a el servidor propone sin crear nada",
      len(plan["candidatos"]) >= 3 and "calendario" in plan)
antes = len(srv.api_list_projects())
creados = srv.api_derive_create({"candidatos": plan["candidatos"],
                                 "origen": plan["origen"]})["creados"]
check("T7b y crea los elegidos cuando se le pide",
      len(srv.api_list_projects()) == antes + len(creados), str(creados))
check("T7c el plan queda guardado junto al video largo",
      bool(srv.api_derive_plan("largo").get("candidatos")))
d = srv.api_project_detail(creados[0]["slug"])
check("T7d el detalle del Short dice de dónde salió",
      (d.get("derived_from") or {}).get("url") == "https://youtu.be/ABC123XYZ")
check("T7e y trae su ficha para publicar",
      bool((d.get("shorts_plan") or {}).get("titulo_youtube")))

for cuerpo, esperado in (({}, "Indica un proyecto"),
                         ({"slug": "no-existe-nada"}, "No existe")):
    try:
        srv.api_derive_propose(cuerpo)
        check(f"T7f error claro: {esperado}", False, "no lanzó nada")
    except srv.ApiError as e:
        check(f"T7f error claro: {esperado}",
              esperado.lower() in e.message.lower(), e.message)

CLI = (ROOT / "ytstudio" / "cli.py").read_text(encoding="utf-8")
check("T7g la consola tiene «python -m ytstudio shorts»",
      '"shorts"' in CLI and "--crear" in CLI)
check("T7h y no crea nada sin pedirlo expresamente",
      "Nada creado todavía" in CLI)

SRV = (ROOT / "ytstudio" / "webui" / "server.py").read_text(encoding="utf-8")
check("T7i el servidor expone proponer y crear",
      "/api/shorts/propose" in SRV and "/api/shorts/create" in SRV)

NUEVA = (srv.STATIC_DIR / "index.html").read_text(encoding="utf-8")
CLASICA = (srv.STATIC_DIR / "index-clasica.html").read_text(encoding="utf-8")
for nombre, html in (("nueva", NUEVA), ("clásica", CLASICA)):
    check(f"T7j la interfaz {nombre} tiene su pestaña de Shorts",
          "'Shorts'" in html or '"Shorts"' in html)
    check(f"T7k la interfaz {nombre} propone y crea",
          "/api/shorts/propose" in html and "/api/shorts/create" in html)
    check(f"T7l la interfaz {nombre} avisa si hay poca variedad de gancho",
          "producción en masa" in html)
    check(f"T7m la interfaz {nombre} recuerda poner el enlace a mano en Studio",
          "Video relacionado" in html and "después de publicar" in html)
    check(f"T7n la interfaz {nombre} deja claro que crear no gasta",
          "no se gasta" in html or "ni se gasta" in html)

# ---------------------------------------------------------------------------
# T8 — documentación
# ---------------------------------------------------------------------------
print("\nT8 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T8a el manual {nombre} explica cómo sacar Shorts de un video largo",
          "Sacar Shorts" in texto or "sacar Shorts" in texto)
    check(f"T8b el manual {nombre} avisa de que el Short NO arrastra al largo",
          "no arrastra" in texto or "NO arrastra" in texto)
    check(f"T8c el manual {nombre} explica el enlace a video relacionado",
          "Video relacionado" in texto or "video relacionado" in texto)
    # Que DECLARE una versión, no que sea esta: una batería no puede exigir
    # seguir siendo la más nueva del programa.
    check(f"T8d el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T8e el CHANGELOG cuenta lo que trajo la v0.64.0",
      "## v0.64.0" in CHANGELOG)

shutil.rmtree(WORK, ignore_errors=True)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.64.0: sacar Shorts de un video largo — todo correcto.")
