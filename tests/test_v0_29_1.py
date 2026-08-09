"""Batería v0.29.1: schemas compatibles con la API de structured output.

Error REAL en producción (v0.29.0, fase metadatos):
  «output_config.format.schema: For 'array' type, 'minItems' values other
   than 0 or 1 are not supported (got: [2, 5])»
Causa: en v0.27.0 puse minItems/maxItems=3 en el schema de metadatos. El
MockLLM aceptaba cualquier schema, así que las pruebas no lo detectaron y el
fallo apareció con la API real, TRAS pagar todas las fases anteriores.

T1  check_schema detecta minItems inválido y las demás palabras no admitidas,
    con la ruta exacta; acepta minItems 0/1 y los schemas válidos.
T2  TODOS los schemas reales del programa pasan la validación (incluidos los
    dinámicos: elenco de personajes y B-roll con visión).
T3  El schema de metadatos ya NO trae minItems/maxItems.
T4  El contrato «exactamente 3 opciones» se sigue cumpliendo aunque el LLM
    devuelva 5, 1 o ninguna (lo garantiza _norm_meta, no el schema).
T5  El MockLLM valida el schema igual que la API (una llamada con schema
    inválido revienta en pruebas locales, sin clave).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.providers.llm import MockLLM, check_schema

print("T1 check_schema detecta lo que la API rechaza")
bad = {"type": "object", "properties": {
    "opts": {"type": "array", "minItems": 3, "items": {"type": "string"}}}}
try:
    check_schema(bad)
    check("minItems=3 se detecta", False)
except ValueError as e:
    check("minItems=3 se detecta con mensaje claro",
          "minItems" in str(e) and "0 o 1" in str(e), str(e))
    check("el mensaje incluye la RUTA del problema",
          "properties.opts" in str(e), str(e))
for kw, val in (("maxItems", 3), ("pattern", "^x$"), ("minLength", 2),
                ("format", "email"), ("oneOf", [{"type": "string"}])):
    s = {"type": "object", "properties": {"a": {"type": "array", kw: val}}}
    try:
        check_schema(s)
        check(f"'{kw}' se detecta", False)
    except ValueError as e:
        check(f"'{kw}' se detecta", kw in str(e))
# válidos
check_schema({"type": "array", "minItems": 1, "items": {"type": "string"}})
check_schema({"type": "array", "minItems": 0, "items": {"type": "string"}})
check("minItems 0 y 1 se aceptan", True)
# anidado profundo (el caso real: dentro de properties → items → properties)
deep = {"type": "object", "properties": {"scenes": {"type": "array", "items": {
    "type": "object", "properties": {
        "tags": {"type": "array", "minItems": 2, "items": {"type": "string"}}}}}}}
try:
    check_schema(deep)
    check("detecta anidado profundo", False)
except ValueError as e:
    check("detecta anidado profundo con su ruta", "tags" in str(e), str(e))

print("T2 todos los schemas REALES del programa son válidos")
from ytstudio.phases.concept import CONCEPT_SCHEMA
from ytstudio.phases.ingest import ANALYSIS_SCHEMA
from ytstudio.phases.metadata import METADATA_SCHEMA
from ytstudio.phases.scenes import SCENES_SCHEMA, _schema_with_cast
for nombre, sch in (("concept", CONCEPT_SCHEMA), ("ingest", ANALYSIS_SCHEMA),
                    ("metadata", METADATA_SCHEMA), ("scenes", SCENES_SCHEMA)):
    try:
        check_schema(sch)
        check(f"schema de {nombre} válido", True)
    except ValueError as e:
        check(f"schema de {nombre} válido", False, str(e))
try:
    check_schema(_schema_with_cast(SCENES_SCHEMA, ["Alejandro", "Filipo"]))
    check("schema dinámico con ELENCO válido", True)
except ValueError as e:
    check("schema dinámico con ELENCO válido", False, str(e))
# Schemas INLINE (los que se construyen dentro de una función): se recorren
# con AST buscando los dicts que de verdad son schemas — un dict literal con
# "type": "object"/"array" — y se validan. Así no hay falsos positivos con el
# "format" de ffmpeg ni con los comentarios del propio validador.
import ast
from pathlib import Path


def _literal(node):
    """Convierte un dict literal de AST a Python (None si no es literal)."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


offenders = []
n_inline = 0
for p in sorted((ROOT / "ytstudio").rglob("*.py")):
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        d = _literal(node)
        if not isinstance(d, dict) or d.get("type") not in ("object", "array"):
            continue
        n_inline += 1
        try:
            check_schema(d)
        except ValueError as e:
            offenders.append(f"{p.name}:{node.lineno}: {e}")
check(f"los {n_inline} schemas literales del código son válidos",
      not offenders, str(offenders))

print("T3 el schema de metadatos quedó limpio")
def _has(node, key):
    if isinstance(node, dict):
        return key in node or any(_has(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_has(v, key) for v in node)
    return False
check("metadata sin minItems", not _has(METADATA_SCHEMA, "minItems"))
check("metadata sin maxItems", not _has(METADATA_SCHEMA, "maxItems"))
check("metadata conserva las 3 listas de opciones",
      all(k in METADATA_SCHEMA["properties"] for k in
          ("title_options", "description_options", "thumbnail_options")))

print("T4 «exactamente 3 opciones» lo garantiza el código, no el schema")
from ytstudio.phases.metadata import _norm_meta
concepto = {"title_options": ["Alt A", "Alt B", "Alt C"]}
# el LLM devuelve 5 → se recorta a 3
cinco = {"title_options": [{"title": f"T{i}", "angle": "a"} for i in range(5)],
         "description_options": [{"description": f"D{i}", "angle": "a"} for i in range(5)],
         "thumbnail_options": [{"kicker": "", "text": f"TX{i}",
                                "accent_word": "X", "scene_id": 1} for i in range(5)],
         "tags": ["a"]}
n5 = _norm_meta(dict(cinco), concepto)
check("5 opciones → se recortan a 3",
      len(n5["title_options"]) == 3 and len(n5["description_options"]) == 3
      and len(n5["thumbnail_options"]) == 3,
      f"{len(n5['title_options'])}/{len(n5['description_options'])}/{len(n5['thumbnail_options'])}")
# el LLM devuelve 1 → se completa a 3
uno = {"title_options": [{"title": "Único", "angle": "a"}],
       "description_options": [{"description": "D", "angle": "a"}],
       "thumbnail_options": [{"kicker": "", "text": "TX", "accent_word": "X",
                              "scene_id": 1}],
       "tags": ["a"]}
n1 = _norm_meta(dict(uno), concepto)
check("1 opción → se completa a 3",
      len(n1["title_options"]) == 3 and len(n1["description_options"]) == 3
      and len(n1["thumbnail_options"]) == 3)
check("al completar títulos se usan los del concepto",
      n1["title_options"][1]["title"] in ("Alt A", "Alt B", "Alt C"),
      str(n1["title_options"]))
# el LLM no devuelve nada de opciones → nunca revienta
n0 = _norm_meta({"tags": ["a"], "thumbnail_text": "IMPACTO"}, concepto)
check("sin opciones → 3 de todo sin reventar",
      len(n0["title_options"]) == 3 and len(n0["description_options"]) == 3
      and len(n0["thumbnail_options"]) == 3)

print("T5 el MockLLM valida igual que la API (red de seguridad en pruebas)")
mock = MockLLM({})
try:
    mock.complete_json("s", "p", schema=bad, purpose="metadata")
    check("el mock RECHAZA un schema inválido", False)
except ValueError:
    check("el mock RECHAZA un schema inválido", True)
out = mock.complete_json("s", "p", schema=METADATA_SCHEMA, purpose="metadata")
check("el mock sigue funcionando con el schema real",
      len(out.get("title_options", [])) == 3, str(out.keys()))

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
