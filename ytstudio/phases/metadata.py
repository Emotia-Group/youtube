"""FASE 10 — Metadatos: 3 títulos, 3 descripciones y 3 MINIATURAS
profesionales (diseños distintos) por video, cada elemento con su estrategia
de CTR. Todo sale de UNA sola llamada al LLM (igual que antes: sin llamadas
extra) y las miniaturas se dibujan en local con PIL (milisegundos): la fase
no se alarga de forma perceptible."""
from __future__ import annotations

import json
import shutil

from ytstudio.phases.scenes import load_scenes
from ytstudio.providers import get_llm

_OPT = {"type": "object", "additionalProperties": False}

# NOTA: NADA de minItems/maxItems en los arrays. La API de structured output
# de Anthropic solo admite minItems 0 o 1 y rechaza el schema entero con
# «For 'array' type, 'minItems' values other than 0 or 1 are not supported».
# El «exactamente 3» se pide en el PROMPT y lo garantiza _norm_meta() (que
# rellena o recorta) — así el contrato se cumple sin schema inválido.
METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title_options": {
            "type": "array",
            "items": {**_OPT, "properties": {
                "title": {"type": "string"},
                "angle": {"type": "string"}},
                "required": ["title", "angle"]},
        },
        "description_options": {
            "type": "array",
            "items": {**_OPT, "properties": {
                "description": {"type": "string"},
                "angle": {"type": "string"}},
                "required": ["description", "angle"]},
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_options": {
            "type": "array",
            "items": {**_OPT, "properties": {
                "kicker": {"type": "string"},
                "text": {"type": "string"},
                "accent_word": {"type": "string"},
                "scene_id": {"type": "integer"}},
                "required": ["kicker", "text", "accent_word", "scene_id"]},
        },
    },
    "required": ["title_options", "description_options", "tags",
                 "thumbnail_options"],
    "additionalProperties": False,
}


def _chapters(scenes: list[dict]) -> list[tuple[str, float]]:
    """Un capítulo por cambio de sección, con su timestamp de inicio."""
    chapters, t = [], 0.0
    last = None
    for s in scenes:
        if s["section"] != last:
            chapters.append((s["section"], t))
            last = s["section"]
        t += s["duration"]
    return chapters


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _norm_meta(meta: dict, concept: dict) -> dict:
    """Red de seguridad: garantiza >=3 opciones aunque el LLM (o un proyecto
    antiguo/mock) devuelva menos, rellenando desde el concepto."""
    tos = [o for o in (meta.get("title_options") or [])
           if (o.get("title") or "").strip()]
    for t in (concept.get("title_options") or []):
        if len(tos) >= 3:
            break
        if all(t != o["title"] for o in tos):
            tos.append({"title": t, "angle": "del concepto original"})
    if not tos:
        tos = [{"title": "La historia completa", "angle": "genérico"}]
    while len(tos) < 3:
        tos.append(dict(tos[-1]))
    dos = [o for o in (meta.get("description_options") or [])
           if (o.get("description") or "").strip()]
    if not dos:
        dos = [{"description": meta.get("description") or "", "angle": "única"}]
    while len(dos) < 3:
        dos.append(dict(dos[-1]))
    ths = [o for o in (meta.get("thumbnail_options") or [])
           if (o.get("text") or "").strip()]
    if not ths:
        base = (meta.get("thumbnail_text") or tos[0]["title"]).split()[:4]
        ths = [{"kicker": "", "text": " ".join(base),
                "accent_word": base[-1] if base else "", "scene_id": 1}]
    while len(ths) < 3:
        ths.append(dict(ths[-1]))
    meta["title_options"], meta["description_options"] = tos[:3], dos[:3]
    meta["thumbnail_options"] = ths[:3]
    return meta


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    concept = project.get("concept") or {}
    scenes = load_scenes(project)
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)  # nombre completo del idioma para el LLM
    chapters = _chapters(scenes)
    chapters_txt = "\n".join(f"{_ts(t)} {name}" for name, t in chapters)
    total = sum(float(s.get("duration") or 0) for s in scenes)
    scene_list = "\n".join(
        f"  id {s['id']} · {s['section']}: {(s.get('broll_prompt') or '')[:90]}"
        for s in scenes)

    system = (
        f"Eres estratega de CTR y SEO de YouTube de primer nivel. Escribes en "
        f"{lang}. Diseñas títulos, descripciones y miniaturas GANADORAS: "
        "específicas, con carga emocional real y cero clickbait engañoso — la "
        "promesa siempre se cumple en el video.")
    prompt = (
        f"Concepto del video:\n{json.dumps(concept, ensure_ascii=False)[:4000]}\n\n"
        + (f"Capítulos reales (INCLÚYELOS tal cual en cada descripción):\n"
           f"{chapters_txt}\n\n" if total >= 120 and len(chapters) >= 2 else "")
        + f"Escenas disponibles como fondo de miniatura:\n{scene_list}\n\n"
        "Devuelve:\n"
        "- title_options: 3 títulos con ESTRATEGIAS DISTINTAS de CTR — uno de "
        "curiosidad/misterio (bucle abierto), uno de dato/beneficio concreto, "
        "uno de contradicción/autoridad. Máx. 70 caracteres cada uno, palabra "
        "clave al principio. En 'angle' explica en una línea la estrategia.\n"
        "- description_options: 3 descripciones completas con enfoques "
        "distintos — (1) SEO: palabras clave naturales en el primer párrafo, "
        "(2) narrativa: gancho emocional que extiende la promesa, (3) directa: "
        "concisa y escaneable. Cada una: 2 párrafos"
        + (", luego la sección 'Capítulos:' con los timestamps de arriba"
           if total >= 120 and len(chapters) >= 2 else "")
        + " y 3-5 hashtags al final. En 'angle', el enfoque en una línea.\n"
        "- tags: 15-25 tags.\n"
        "- thumbnail_options: 3 conceptos de miniatura. Cada uno: 'text' de "
        "2-4 palabras GIGANTES de alto impacto (NO repitas el título literal; "
        "que texto y título se complementen), 'accent_word' = LA palabra de "
        "'text' con más carga (se pinta en el color del canal), 'kicker' = "
        "contexto de 1-3 palabras (o vacío), y 'scene_id' = la escena cuya "
        "imagen es más icónica/emocional como fondo (id de la lista; elige "
        "TRES escenas distintas).")
    meta = llm.complete_json(system, prompt, schema=METADATA_SCHEMA,
                             purpose="metadata")
    meta = _norm_meta(meta, concept)

    # ATRIBUCIÓN del material de archivo (Wikimedia): las licencias libres
    # piden crédito — se añade solo, a TODAS las opciones de descripción,
    # para que la elección del creador nunca lo pierda.
    credits = project.get("element_credits") or []
    if credits:
        bloque = ("\n\nMaterial de archivo (Wikimedia Commons):\n"
                  + "\n".join(f"• {c}" for c in credits))
        for o in meta["description_options"]:
            o["description"] = o["description"].rstrip() + bloque

    # Miniaturas: 3 diseños profesionales locales (PIL) — sin IA extra
    from ytstudio.utils.thumbs import render_thumbnails
    thumb_files = render_thumbnails(project, cfg, meta["thumbnail_options"],
                                    scenes)
    meta["thumbnails"] = thumb_files
    meta["chosen"] = {"title": 0, "description": 0, "thumbnail": 0}
    # Elección por defecto = primera opción; se cambia desde la pestaña Video
    meta["title"] = meta["title_options"][0]["title"]
    meta["description"] = meta["description_options"][0]["description"]
    meta["chapters"] = [{"time": _ts(t), "title": name} for name, t in chapters]
    if thumb_files:
        shutil.copyfile(project.path("final", thumb_files[0]),
                        project.path("final", "miniatura.jpg"))
    meta["thumbnail"] = str(project.path("final", "miniatura.jpg"))

    project.path("final", "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    project.set("metadata", {k: meta[k] for k in ("title", "tags", "thumbnail")})
