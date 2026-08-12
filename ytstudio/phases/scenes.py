"""FASE 4 — Escenas / storyboard: divide el guion en escenas de 10-25 s de
narración, cada una con su prompt de B-roll, tipo (imagen o video IA),
animación y texto en pantalla."""
from __future__ import annotations

import json

from ytstudio.phases.script import load_script
from ytstudio.prompt_safety import SENSIBILIDADES, auditar_fidelidad
from ytstudio.providers import get_llm

# Campos creativos por escena (dirección de arte + banda sonora):
# - overlay_*: rótulo cinematográfico SOLO en momentos clave (tipado: el
#   montaje le da un diseño distinto a cada tipo).
# - music_intensity: arco dramático de la música (0 = mínima, 1 = clímax).
# - pause_after: respiro dramático tras la escena (la música sube en él).
# - sfx: efecto de sonido incidental en el corte de entrada de la escena.
_CREATIVE_PROPS = {
    "overlay_type": {"type": "string",
                     "enum": ["ninguno", "personaje", "lugar", "fecha",
                              "dato", "lista", "conclusion", "hook"]},
    "overlay_text": {"type": "string"},
    "overlay_kicker": {"type": "string"},
    "overlay_emphasis": {"type": "string"},
    "music_intensity": {"type": "number"},
    "pause_after": {"type": "number"},
    "pace": {"type": "string", "enum": ["ligado", "normal", "amplio"]},
    "sfx": {"type": "string",
            "enum": ["ninguno", "whoosh", "riser", "boom", "papel", "latido"]},
    "transition": {"type": "string", "enum": ["corte", "fundido"]},
    # Composición de pantalla: 'dividida' = dos visuales a la vez (arriba/
    # abajo en vertical, izquierda/derecha en horizontal) para comparaciones.
    "layout": {"type": "string", "enum": ["completo", "dividida"]},
    "broll_prompt_b": {"type": "string"},
    # Sticker de aspecto nativo (formatos cortos): imitación visual animada
    # de los stickers de IG/TikTok — recurso de retención, no clicable.
    "sticker_type": {"type": "string",
                     "enum": ["ninguno", "encuesta", "pregunta", "countdown"]},
    "sticker_text": {"type": "string"},
    "sticker_a": {"type": "string"},
    "sticker_b": {"type": "string"},
    # Texto LEGIBLE dentro de la imagen (casi siempre vacío): cuando la escena
    # lo define, esa imagen se genera con el modelo de mejor tipografía.
    "image_text": {"type": "string"},
    # SENSIBILIDAD del contenido: el registro documental correspondiente se
    # antepone al prompt DESDE EL PRIMER INTENTO (ver ytstudio/prompt_safety).
    "sensibilidad": {"type": "string", "enum": list(SENSIBILIDADES)},
}

SCENES_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "section": {"type": "string"},
                    "narration": {"type": "string"},
                    "broll_prompt": {"type": "string"},
                    "broll_type": {"type": "string", "enum": ["image", "video"]},
                    "animation": {"type": "string",
                                  "enum": ["zoom_in", "zoom_out", "pan_left",
                                           "pan_right", "static"]},
                    **_CREATIVE_PROPS,
                },
                "required": ["id", "section", "narration", "broll_prompt",
                             "broll_type", "animation", *_CREATIVE_PROPS],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scenes"],
    "additionalProperties": False,
}

# Reglas de dirección creativa compartidas por los dos flujos con LLM
# (guion nuevo y narración propia). Criterio de documental/serie: los rótulos
# son un acento, no un hábito; la música cuenta el arco; el silencio es un
# recurso.
CREATIVE_RULES = """\
RÓTULOS EN PANTALLA (overlay_*): son acentos cinematográficos, NO subtítulos.
- Úsalos SOLO en momentos clave: como máximo en 1 de cada 3-4 escenas. En el
  resto: overlay_type='ninguno' y textos vacíos.
- Momentos que SÍ merecen rótulo: primera aparición de un personaje relevante;
  un lugar o una fecha que sitúan la acción; una cifra o dato crucial; los
  ítems de una enumeración ("Razón 1…"); la conclusión más importante de una
  sección o del video.
- overlay_text: el dato en sí, 1-5 palabras (ej. "Alejandro Magno", "331 a. C.",
  "40 000 soldados"). EXCEPCIÓN conclusion: puede ser una frase corta completa
  de hasta 8 palabras (ej. "El veredicto es tuyo") — se compone en pantalla
  como una declaración tipográfica grande.
- overlay_kicker: contexto en 1-3 palabras que se muestra pequeño encima
  (ej. kicker "REY DE MACEDONIA" + text "Alejandro Magno"; kicker "BATALLA DE
  GAUGAMELA" + text "331 a. C."; kicker "RAZÓN 2" + text "La logística").
  Puede ir vacío si el texto se explica solo.
- overlay_emphasis: LA palabra de overlay_text que carga el peso dramático
  (se destaca en negrita, ej. "veredicto"). Vacío si no aplica.
- overlay_type: personaje | lugar | fecha | dato | lista | conclusion — elige
  el que corresponda al contenido (cada tipo tiene un diseño distinto).
- IMPORTANTE: usa palabras que aparezcan en la narración de ESA escena (el
  rótulo se sincroniza con el momento en que el narrador las dice).

MÚSICA (music_intensity, 0.0-1.0): dibuja el arco dramático de la historia.
- Gancho inicial 0.65-0.8 · desarrollo/exposición 0.35-0.55 · tensión creciente
  0.6-0.75 · clímax 0.85-1.0 · cierre 0.45-0.6.
- Cambia de forma gradual (±0.15 entre escenas contiguas); reserva los saltos
  bruscos para golpes dramáticos reales.

RESPIROS ENTRE ESCENAS (pause_after, segundos): silencio de la voz tras la
escena, donde la música respira y sube — recurso cinematográfico, úsalo con
intención.
- 0 en la mayoría de escenas. 0.8-1.6 tras una revelación, una pregunta al
  espectador, o el final de una sección. Máximo en 1 de cada 6 escenas.

RITMO DENTRO DE LA ESCENA (pace): cuánto aire dejar ENTRE LAS FRASES de esta
escena (respiros breves al final de cada frase, sin cortar nunca la voz).
- 'ligado': frases encadenadas, sin aire extra — para secuencias de tensión,
  acción rápida, enumeraciones ágiles o un gancho urgente.
- 'normal': respiro natural entre frases (lo habitual en un documental).
- 'amplio': más aire, tono contemplativo — para pasajes solemnes, reflexivos,
  paisajísticos o el desenlace. Que NO sea todo 'amplio': cansa.

EFECTOS DE SONIDO (sfx): acento en el corte de ENTRADA de la escena.
- 'whoosh' al cambiar de sección/lugar/tiempo · 'riser' en la escena que
  desemboca en el clímax (crea anticipación) · 'boom' en una revelación
  impactante · 'papel' cuando se narra un documento, un registro, una cifra
  de archivo · 'latido' en suspenso sostenido (peligro, cuenta atrás, una
  espera tensa) · 'ninguno' en el resto (máximo 1 de cada 4 escenas).

PANTALLA DIVIDIDA (layout): 'completo' casi siempre. 'dividida' SOLO cuando la
narración COMPARA dos cosas de verdad (antes/después, esto vs aquello, opción
A vs B): entonces broll_prompt_b describe el SEGUNDO visual (mismo estilo) y
el montaje muestra ambos a la vez. Si layout='completo', broll_prompt_b va
vacío. Máximo 1-2 escenas divididas por video.

FIDELIDAD FACTUAL AL GUION (más importante que el estilo — un prompt correcto
y sobrio es mejor que uno bonito que CONTRADICE lo narrado): antes de
escribir cada broll_prompt, extrae los HECHOS CONCRETOS que la narración de
ESA escena afirma y codifícalos de forma literal e inequívoca:
- ESTADO: si la narración dice que algo/alguien está muerto, sin vida,
  hallado sin vida, inerte, etc., el prompt debe decirlo EXPLÍCITAMENTE
  ("dead", "lifeless body", "carcass", "motionless") — nunca un sujeto en
  postura que pueda leerse como dormido o vivo en reposo.
- IDENTIDAD DEL SUJETO: si la narración habla de un ANIMAL, nombra la
  especie en CADA mención del cuerpo o una herida (ej. "dead goat", "cow
  carcass") — nunca dejes "body"/"wound" ambiguo: sin especie explícita el
  generador de imágenes tiende a dibujar anatomía HUMANA por defecto.
- UBICACIÓN EXACTA: si la narración da una ubicación concreta de una marca,
  herida o detalle (cuello, pecho, espalda…), esa ubicación exacta va en el
  prompt tal cual — nunca una zona genérica del cuerpo.
- CANTIDAD Y GEOMETRÍA EXACTAS: si la narración da un número o una forma
  («tres orificios en triángulo», «ocho ovejas»), el prompt lo dice en
  inglés de forma REDUNDANTE y verificable («exactly three puncture wounds,
  no more, arranged in a clean triangle»). Los generadores fallan contando:
  sin el número repetido y la disposición descrita, dibujan otra cantidad.
  Con grupos grandes (≥6 sujetos), además del número describe la escena de
  conjunto para que el estado se lea igual en TODOS («all of them dead,
  none standing»).

CONTENIDO SENSIBLE (campo 'sensibilidad'): marca la escena cuando lo que hay
que mostrar podría chocar con los filtros de los generadores de imágenes:
muerte_animal · restos_humanos · herida_lesion · violencia_historica ·
medico_anatomico · arte_desnudo · armas_conflicto · sustancias. En el resto,
'ninguna'.
- Marcarla NO censura la escena: el programa antepone el registro documental
  adecuado (clínico, sobrio, sin sangre) para que la imagen SALGA A LA
  PRIMERA en vez de ser rechazada. Los HECHOS (especie, estado sin vida,
  cantidad, ubicación) se mantienen intactos: no los suavices tú.
- Escribe el prompt en ese mismo registro: muestra el SUJETO y la ESCENA, no
  el detalle morboso. Nada de sangre, vísceras, primeros planos de heridas ni
  sufrimiento — ni aportan al documental ni pasan los filtros.
- Si dudas entre ser más literal o más "artístico", elige literal: la
  fidelidad a lo narrado manda sobre la elegancia visual.

TEXTO DENTRO DE LA IMAGEN (image_text): por defecto NINGUNO.
- Casi siempre image_text va vacío y el broll_prompt dice explícitamente que
  no haya texto legible; si aparecen periódicos, documentos o pantallas como
  atrezo, se describen "out of focus, unreadable print" (los generadores
  escriben letras inventadas y en inglés — texto ilegible que arruina el
  plano).
- SOLO cuando la narración depende de que se LEA un texto (un titular, una
  palabra clave, un letrero), escribe en image_text el texto EXACTO que debe
  verse (máx. 6 palabras) EN EL IDIOMA DE LA NARRACIÓN — jamás en inglés si
  el video no es en inglés. Máximo 2-3 escenas por video: el programa genera
  esas imágenes con el modelo de mejor tipografía disponible.

TRANSICIÓN (transition): cómo ENTRA la escena desde la anterior.
- 'corte': corte seco, sin transición (por defecto). Da ritmo y es lo más
  común en documentales; úsalo en la mayoría de escenas, sobre todo en
  secuencias rápidas, enumeraciones y acción encadenada.
- 'fundido': breve caída a negro compartida con la escena anterior. Resérvalo
  para los CAMBIOS de sección, saltos de tiempo/lugar y los momentos
  dramáticos (tras una revelación o un respiro). Que NO sean todas iguales:
  como mucho 1 de cada 3-4 escenas.
"""


WORDS_PER_SECOND = 2.5  # ritmo medio de narración (≈150 palabras/min)

# ---------------------------------------------------------------------------
# Pase de DIRECCIÓN DE ARTE: revisión de TODO el storyboard como conjunto.
# El primer pase diseña escena a escena; este segundo pase lee el video
# completo y unifica: biblia visual global (época, paleta, luz, lenguaje de
# cámara, textura, motivos recurrentes), prompts reescritos con detalle
# profesional y coherencia entre escenas, auditoría de riesgo de movimiento
# de las escenas de video IA, y revisión global de rótulos / transiciones /
# sfx / arco musical (que funcionen como sistema, no como decisiones sueltas).
# ---------------------------------------------------------------------------

DIRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "bible": {
            "type": "object",
            "properties": {
                "era_setting": {"type": "string"},
                "palette": {"type": "string"},
                "lighting": {"type": "string"},
                "camera_language": {"type": "string"},
                "texture_grade": {"type": "string"},
                "motifs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["era_setting", "palette", "lighting",
                         "camera_language", "texture_grade", "motifs"],
            "additionalProperties": False,
        },
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "broll_prompt": {"type": "string"},
                    "motion_risk": {"type": "string",
                                    "enum": ["baja", "media", "alta"]},
                    **_CREATIVE_PROPS,
                },
                "required": ["id", "broll_prompt", "motion_risk",
                             *_CREATIVE_PROPS],
                "additionalProperties": False,
            },
        },
    },
    "required": ["bible", "scenes"],
    "additionalProperties": False,
}


# Máximo de escenas por LLAMADA en los pases que devuelven todas las escenas.
# Un video largo (~200 escenas de un guion de 20 min) supera el límite de
# tokens de SALIDA del modelo y el JSON llega cortado — la fase moría con un
# críptico «Unterminated string» (pasó de verdad). Por encima de este número
# el trabajo se hace por TANDAS.
_SCENES_PER_CALL = 40

_BIBLE_SCHEMA = {
    "type": "object",
    "properties": {"bible": DIRECTION_SCHEMA["properties"]["bible"]},
    "required": ["bible"], "additionalProperties": False}

_DIR_SCENES_SCHEMA = {
    "type": "object",
    "properties": {"scenes": DIRECTION_SCHEMA["properties"]["scenes"]},
    "required": ["scenes"], "additionalProperties": False}


def _board_lines(scenes: list[dict]) -> str:
    """Storyboard compacto para el pase de dirección: narración + decisiones
    actuales de cada escena, para que el director de arte revise el CONJUNTO."""
    lines = []
    for s in scenes:
        extras = []
        if s.get("overlay_type") and s.get("overlay_type") != "ninguno":
            extras.append(f"rótulo {s['overlay_type']}: "
                          f"{s.get('overlay_text', '')}")
        if s.get("transition"):
            extras.append(f"entra {s['transition']}")
        if s.get("sfx") and s.get("sfx") != "ninguno":
            extras.append(f"sfx {s['sfx']}")
        if isinstance(s.get("music_intensity"), (int, float)):
            extras.append(f"música {float(s['music_intensity']):.2f}")
        if s.get("pace"):
            extras.append(f"ritmo {s['pace']}")
        kind = "VIDEO IA (con movimiento)" if s.get("broll_type") == "video" \
            else "imagen"
        lines.append(
            f"[{s['id']}] ({s.get('section', '')} · {kind}"
            + (f" · {', '.join(extras)}" if extras else "") + ")\n"
            f"    narración: {s.get('narration', '')}\n"
            f"    prompt actual: {s.get('broll_prompt', '')}")
    return "\n".join(lines)


def _art_direction_pass(llm, project, scenes: list[dict], concept: dict,
                        lang: str, short_form: bool = False,
                        template_rules: str = "") -> None:
    """Segundo pase con el storyboard COMPLETO. Nunca rompe la fase: si el
    modelo falla, se conservan las decisiones del primer pase con un aviso."""
    if getattr(llm, "is_mock", False) or not scenes:
        return
    from ytstudio.progress import notify
    prefix = concept["visual_style"]["prompt_prefix"]
    cast_names, cast_rules = _cast_rules(project)
    notify("🎨 Pase de dirección de arte: revisando el video COMPLETO "
           "(coherencia visual, detalle de prompts, movimiento, rótulos y "
           "sonido como conjunto)…")
    system = (
        f"Eres el DIRECTOR DE ARTE y director de fotografía senior de un "
        f"estudio de documentales en {lang}. Recibes un storyboard ya montado "
        "y haces el PASE FINAL de coherencia de TODO el video como conjunto — "
        "como una biblia de arte de producción real: un solo mundo visual, "
        "prompts con nivel de detalle profesional y una banda sonora y "
        "rotulación que funcionan como sistema.")
    bible_instr = (
        "1) BIBLIA VISUAL (bible) — lee TODO el storyboard y define el mundo "
        "visual ÚNICO del video: época y lugar (era_setting), paleta de color "
        "(palette), luz (lighting), lenguaje de cámara (camera_language: "
        "encuadres, ópticas, alturas de cámara), textura y acabado "
        "(texture_grade: grano, contraste, grading) y 2-4 MOTIVOS visuales "
        "recurrentes (motifs) que unan el video (un objeto, un elemento del "
        "paisaje, un gesto de luz que reaparece en momentos clave).")
    rules_24 = (
        "2) PROMPTS (broll_prompt de CADA escena, EN INGLÉS, empezando "
        f"SIEMPRE con el prefijo de estilo \"{prefix}\") — reescríbelos "
        "aplicando la biblia:\n"
        "- FIDELIDAD FACTUAL PRIMERO (ver regla FIDELIDAD FACTUAL AL GUION "
        "más abajo): antes de embellecer, verifica que el prompt no "
        "contradiga ningún hecho concreto de la narración de esa escena "
        "(estado con/sin vida, especie del sujeto, ubicación exacta de "
        "heridas/marcas). Es MÁS IMPORTANTE que la coherencia visual.\n"
        "- COHERENCIA TOTAL entre escenas: misma época, paleta, luz y acabado "
        "en todas; los personajes, lugares y objetos que se repiten se "
        "describen IGUAL en cada aparición (mismo vestuario, mismos rasgos, "
        "misma arquitectura); usa los motivos recurrentes donde sumen.\n"
        "- DETALLE PROFESIONAL: sujeto y acción concretos + composición y "
        "encuadre (wide/medium/close-up, ángulo) + luz y atmósfera + textura. "
        "2-4 frases por prompt; nada genérico.\n"
        "- Lo que se VE corresponde exactamente a lo que se DICE en esa "
        "escena.\n"
        "- Sin texto ni letras dentro de la imagen (salvo el image_text "
        "exacto de las escenas que lo definan); sin personas famosas "
        "reales.\n\n"
        "3) AUDITORÍA DE MOVIMIENTO (motion_risk) — los modelos de video IA "
        "fallan con movimientos complejos; clasifica cada escena:\n"
        "- 'alta': personas caminando o gesticulando, manos manipulando "
        "objetos, caras hablando, multitudes interactuando, acción rápida, "
        "texto que deba leerse.\n"
        "- 'media': movimiento moderado de sujetos. · 'baja': sujetos casi "
        "estáticos (en escenas de imagen usa 'baja').\n"
        "En las escenas de VIDEO IA con riesgo 'alta', REESCRIBE el prompt "
        "para que el movimiento lo pongan la CÁMARA (dolly lento, paneo, "
        "parallax) y la ATMÓSFERA (polvo, humo, brasas, lluvia, telas al "
        "viento, cambios de luz) con los sujetos casi estáticos en una pose "
        "potente — cinematográfico y sin artefactos.\n\n"
        "4) REVISIÓN GLOBAL de rótulos, transiciones, sfx, ritmo y música "
        "COMO CONJUNTO (devuelve los campos ajustados en cada escena):\n"
        + CREATIVE_RULES
        + (SHORT_FORM_RULES if short_form else "")
        + template_rules +
        "- Verifica el conjunto: UN clímax musical y arco gradual; rótulos "
        "como sistema coherente (mismo estilo de kicker, sin repetir datos); "
        "fundidos solo en fronteras de sección o momentos dramáticos; sfx "
        "sin fatiga; variedad de ritmo.\n"
        + cast_rules)
    try:
        if len(scenes) <= _SCENES_PER_CALL:
            prompt = (
                "Haz el pase de dirección de arte de este video completo:\n\n"
                + bible_instr + "\n\n" + rules_24 +
                "\nDevuelve TODAS las escenas (mismos ids, mismo orden).\n\n"
                f"STORYBOARD ACTUAL ({len(scenes)} escenas):\n"
                f"{_board_lines(scenes)}")
            result = llm.complete_json(system, prompt, schema=DIRECTION_SCHEMA,
                                       max_tokens=64000, purpose="direction")
            by_id = {int(d.get("id", -1)): d
                     for d in (result.get("scenes") or [])}
            bible = result.get("bible") or {}
        else:
            # VIDEO LARGO: la respuesta con todas las escenas no cabe en una
            # sola llamada — biblia primero, prompts por tandas.
            bible, by_id = _direction_in_batches(llm, system, scenes,
                                                 bible_instr, rules_24)
    except Exception as e:
        project.add_warning(
            f"El pase de dirección de arte no se pudo aplicar ({e}): se "
            "conservan las decisiones escena a escena del primer pase.")
        return
    project.set("art_direction", bible)
    risky_video: list[int] = []
    applied = 0
    for s in scenes:
        d = by_id.get(int(s["id"]))
        if not d:
            continue  # escena no devuelta → conserva el primer pase
        new_prompt = (d.get("broll_prompt") or "").strip()
        if new_prompt:
            s["broll_prompt"] = new_prompt
            applied += 1
        if d.get("motion_risk") in ("baja", "media", "alta"):
            s["motion_risk"] = d["motion_risk"]
            if s["motion_risk"] == "alta" and s.get("broll_type") == "video":
                risky_video.append(s["id"])
        for key in _CREATIVE_PROPS:
            if key in d:
                s[key] = d[key]
    notify(f"🎨 Dirección de arte aplicada: {applied}/{len(scenes)} prompts "
           "unificados con la biblia visual del video.")
    if risky_video:
        notify("🎥 Auditoría de movimiento: "
               f"{len(risky_video)} escena(s) de video con riesgo alto "
               f"({', '.join(map(str, risky_video))}) — sus prompts se "
               "reescribieron hacia movimiento de cámara y atmósfera (sujetos "
               "casi estáticos) para evitar artefactos del modelo.")


def _direction_in_batches(llm, system: str, scenes: list[dict],
                          bible_instr: str, rules_24: str):
    """Pase de dirección para videos LARGOS (> _SCENES_PER_CALL escenas):
    (1) UNA llamada corta define la biblia leyendo el storyboard entero;
    (2) los prompts se reescriben por tandas — cada tanda recibe la biblia
    y el ÍNDICE completo del video para no perder la visión de conjunto.
    Devuelve (bible, {id: escena_dirigida})."""
    import json as _json
    from ytstudio.progress import notify
    board = _board_lines(scenes)
    prompt_b = ("Define SOLO la biblia visual de este video (las escenas se "
                "trabajarán después):\n\n" + bible_instr +
                f"\n\nSTORYBOARD ACTUAL ({len(scenes)} escenas):\n{board}")
    bible = llm.complete_json(system, prompt_b, schema=_BIBLE_SCHEMA,
                              max_tokens=16000, purpose="direction")["bible"]
    index = "\n".join(f"[{s['id']}] {s.get('section', '')} — "
                      f"{(s.get('narration') or '')[:70]}" for s in scenes)
    by_id: dict[int, dict] = {}
    total = -(-len(scenes) // _SCENES_PER_CALL)
    for n, start in enumerate(range(0, len(scenes), _SCENES_PER_CALL), 1):
        chunk = scenes[start:start + _SCENES_PER_CALL]
        notify(f"🎨 Dirección de arte (tanda {n}/{total}): escenas "
               f"{chunk[0]['id']}–{chunk[-1]['id']}…")
        prompt = (
            "La BIBLIA VISUAL de este video ya está definida:\n"
            + _json.dumps(bible, ensure_ascii=False) +
            "\n\nÍNDICE COMPLETO del video (solo para que mantengas la "
            "visión de conjunto):\n" + index +
            "\n\nHaz el pase de dirección de arte SOLO de las escenas de "
            "esta tanda, aplicando la biblia y estas reglas:\n\n" + rules_24 +
            "\nDevuelve TODAS las escenas de esta tanda (mismos ids, mismo "
            f"orden).\n\nESCENAS DE ESTA TANDA ({len(chunk)}):\n"
            + _board_lines(chunk))
        result = llm.complete_json(system, prompt, schema=_DIR_SCENES_SCHEMA,
                                   max_tokens=32000, purpose="direction")
        for d in (result.get("scenes") or []):
            by_id[int(d.get("id", -1))] = d
    return bible, by_id


def _schema_with_cast(base_schema: dict, cast_names: list[str]) -> dict:
    """Copia del schema de escenas con el campo 'characters' (enum del
    ELENCO): el director etiqueta qué personajes aparecen en cada escena.
    Solo se añade cuando hay elenco — sin él, el schema queda intacto."""
    import copy
    if not cast_names:
        return base_schema
    schema = copy.deepcopy(base_schema)
    item = schema["properties"]["scenes"]["items"]
    item["properties"]["characters"] = {
        "type": "array", "items": {"type": "string", "enum": cast_names}}
    item["required"] = [*item["required"], "characters"]
    return schema


def _cast_rules(project) -> tuple[list[str], str]:
    """(nombres del elenco, bloque de reglas para el prompt del director)."""
    from ytstudio.characters import cast_brief, roster
    names = [c.get("name") for c in roster(project) if c.get("name")]
    if not names:
        return [], ""
    rules = (
        "\nELENCO DEL VIDEO (personajes con IDENTIDAD VISUAL FIJA — sus "
        "escenas se generan con sus fotos de referencia):\n"
        + cast_brief(project) + "\n"
        "- 'characters': los nombres del ELENCO que aparecen VISUALMENTE en "
        "esa escena (lista vacía si ninguno). Sé preciso: solo cuando la "
        "escena de verdad los muestra.\n"
        "- En el broll_prompt de esas escenas descríbelos por su ROL y acción "
        "(ej. 'the young king raising his sword'), NO inventes sus rasgos: la "
        "cara y el aspecto los ponen las fotos de referencia.\n")
    return names, rules


def _normalize_cast(scenes: list[dict], cast_names: list[str]) -> None:
    """Sanea las etiquetas: solo nombres del elenco, sin duplicados."""
    valid = {n.strip().lower(): n for n in cast_names}
    for s in scenes:
        seen, out = set(), []
        for n in (s.get("characters") or []):
            k = (n or "").strip().lower()
            if k in valid and k not in seen:
                out.append(valid[k])
                seen.add(k)
        s["characters"] = out


def scene_seconds(cfg: dict, project=None) -> float:
    """Ritmo visual: cada cuántos segundos cambia la imagen. Prioridad:
    referencia analizada en ESTE proyecto > estilo guardado del canal >
    configuración."""
    if project is not None:
        for link in (project.get("brief") or {}).get("links", []):
            rhythm = (link or {}).get("rhythm") or {}
            avg = rhythm.get("avg_shot_seconds")
            if avg:
                target = min(15.0, max(3.5, float(avg)))
                project.add_warning(
                    f"ℹ Ritmo visual tomado del video de referencia: "
                    f"~{target:.0f} s por plano.")
                return target
        if project.get("style_id"):
            from ytstudio.library import load_style
            style = load_style(project.get("style_id")) or {}
            if style.get("scene_seconds"):
                target = float(style["scene_seconds"])
                project.add_warning(
                    f"ℹ Ritmo visual del estilo «{style.get('name', '')}»: "
                    f"~{target:.0f} s por plano.")
                return target
    return float(cfg.get("video", {}).get("scene_seconds", 6))


def _assign_video_scenes(scenes: list[dict], cfg: dict) -> None:
    """Marca deterministamente N escenas como video (broll_type='video'),
    repartidas uniformemente, según providers.videogen.max_scenes. Así el
    usuario obtiene EXACTAMENTE el número de escenas de video que pidió, en
    vez de dejarlo al criterio del modelo. El resto quedan como imagen."""
    vg = cfg.get("providers", {}).get("videogen", {})
    n = vg.get("max_scenes", 0) if vg.get("name", "none") != "none" else 0
    n = min(int(n or 0), len(scenes))
    if n <= 0:
        for s in scenes:
            s["broll_type"] = "image"
        return
    if n >= len(scenes):
        idxs = set(range(len(scenes)))
    else:  # distribuidas uniformemente, incluyendo la primera (el gancho)
        idxs = {round(i * (len(scenes) - 1) / (n - 1)) if n > 1 else 0
                for i in range(n)}
    for i, s in enumerate(scenes):
        s["broll_type"] = "video" if i in idxs else "image"


def _default_intensity(i: int, n: int) -> float:
    """Arco musical por defecto (sin criterio del LLM): gancho fuerte, valle de
    desarrollo, clímax hacia el 85 % y cierre suave. Interpolación lineal."""
    keys = [(0.0, 0.7), (0.2, 0.45), (0.6, 0.55), (0.85, 0.9), (1.0, 0.5)]
    x = i / (n - 1) if n > 1 else 0.5
    for (x0, y0), (x1, y1) in zip(keys, keys[1:]):
        if x <= x1:
            return round(y0 + (y1 - y0) * (x - x0) / (x1 - x0), 2)
    return keys[-1][1]


_OVERLAY_TYPES = {"personaje", "lugar", "fecha", "dato", "lista", "conclusion",
                  "hook"}

# Reglas adicionales para formatos de REDES SOCIALES (vertical/cuadrado/4:5):
# lenguaje visual propio — gancho en texto grande al abrir, rótulos más
# frecuentes, ritmo alto. Se añaden a las CREATIVE_RULES, no las sustituyen.
SHORT_FORM_RULES = """\
FORMATO CORTO DE REDES (este video): reglas ADICIONALES.
- La ESCENA 1 lleva SIEMPRE overlay_type='hook': el gancho del guion
  condensado en overlay_text (máx. 8 palabras, con gancho de verdad — una
  promesa, un dato chocante o una pregunta). overlay_emphasis = LA palabra
  más fuerte. Es el texto grande de apertura estilo TikTok/Reels.
- Rótulos MÁS frecuentes que en un video largo: hasta 1 de cada 2 escenas
  puede llevar overlay (dato/lista/conclusion) — el espectador ve el video
  sin sonido muchas veces; el texto sostiene la historia.
- Ritmo: transiciones 'corte' casi siempre; pace 'ligado' dominante.
- STICKER (sticker_type, opcional): COMO MÁXIMO UNO en todo el video, solo
  si el momento lo pide de verdad:
  · 'encuesta' cuando la narración plantea una disyuntiva al espectador —
    sticker_text = la pregunta corta, sticker_a/sticker_b = las 2 opciones
    (1-3 palabras). · 'pregunta' cuando se le pide opinión abierta
    (sticker_text = la pregunta; la respuesta va a comentarios).
  · 'countdown' justo ANTES de una revelación (sticker_text = rótulo de
    anticipación, ej. "EL RESULTADO EN…").
  En el resto de escenas sticker_type='ninguno' y textos vacíos.
"""


def _normalize_creative(scenes: list[dict], short_form: bool = False) -> None:
    """Valida y compacta los campos creativos: los flat overlay_* del esquema
    se convierten en un objeto `overlay` (o None), y los valores numéricos se
    acotan. `on_screen_text` se mantiene sincronizado para la interfaz y los
    proyectos antiguos. En formatos cortos garantiza el gancho visual de la
    escena 1 aunque el modelo no lo haya puesto (respaldo determinista)."""
    n = len(scenes)
    for i, s in enumerate(scenes):
        o_type = s.pop("overlay_type", None) or "ninguno"
        max_len = 70 if o_type in ("conclusion", "hook") else 48
        o_text = (s.pop("overlay_text", "") or "").strip()[:max_len]
        o_kicker = (s.pop("overlay_kicker", "") or "").strip()[:36]
        o_emph = (s.pop("overlay_emphasis", "") or "").strip()[:24]
        if o_type in _OVERLAY_TYPES and o_text:
            s["overlay"] = {"type": o_type, "text": o_text, "kicker": o_kicker,
                            "emphasis": o_emph}
        else:
            s["overlay"] = None
        s["on_screen_text"] = o_text if s["overlay"] else ""

        mi = s.get("music_intensity")
        if not isinstance(mi, (int, float)):
            mi = _default_intensity(i, n)
        s["music_intensity"] = round(min(1.0, max(0.0, float(mi))), 2)

        pa = s.get("pause_after")
        pa = float(pa) if isinstance(pa, (int, float)) else 0.0
        s["pause_after"] = round(min(2.0, max(0.0, pa)), 2)

        s["pace"] = s.get("pace") if s.get("pace") in \
            ("ligado", "normal", "amplio") else "normal"

        s["sfx"] = s.get("sfx") if s.get("sfx") in (
            "whoosh", "riser", "boom", "papel", "latido") else None

        s["transition"] = s.get("transition") if s.get("transition") in \
            ("corte", "fundido") else None

        # Pantalla dividida: solo válida con su segundo prompt; en el 16:9
        # largo se fuerza 'completo' (v1: el lenguaje de comparación en
        # pantalla es de los formatos cortos).
        pb = (s.get("broll_prompt_b") or "").strip()
        if (s.get("layout") == "dividida" and pb and short_form
                and s.get("broll_type") != "video"):
            s["layout"], s["broll_prompt_b"] = "dividida", pb
        else:
            s["layout"] = "completo"
            s.pop("broll_prompt_b", None)

        # Texto legible dentro de la imagen: solo si el director lo definió
        it = (s.pop("image_text", "") or "").strip()[:60]
        if it:
            s["image_text"] = it

        # Sensibilidad del contenido (para el encuadre documental preventivo)
        sens = (s.get("sensibilidad") or "").strip()
        if sens in SENSIBILIDADES and sens != "ninguna":
            s["sensibilidad"] = sens
        else:
            s.pop("sensibilidad", None)

        # Sticker: imitación visual nativa, SOLO formatos cortos y con texto
        st = s.pop("sticker_type", None)
        st_text = (s.pop("sticker_text", "") or "").strip()[:80]
        st_a = (s.pop("sticker_a", "") or "").strip()[:24]
        st_b = (s.pop("sticker_b", "") or "").strip()[:24]
        if short_form and st in ("encuesta", "pregunta", "countdown") and st_text:
            s["sticker"] = {"type": st, "text": st_text, "a": st_a, "b": st_b}
        else:
            s["sticker"] = None

    # Sticker: COMO MÁXIMO UNO por video (si el modelo puso varios, gana el
    # primero — más de un sticker deja de parecer nativo y cansa).
    seen_sticker = False
    for s in scenes:
        if s.get("sticker"):
            if seen_sticker:
                s["sticker"] = None
            seen_sticker = True

    # Formato corto: la escena 1 SIEMPRE abre con gancho visual. Si el modelo
    # no lo puso (o corre el modo preview), se condensa el arranque de la
    # narración — nunca un corto sin texto de apertura.
    if short_form and scenes:
        first = scenes[0]
        if not first.get("overlay") or first["overlay"].get("type") != "hook":
            words = (first.get("narration") or "").split()
            text = " ".join(words[:8]).rstrip(".,;:") + ("…" if len(words) > 8
                                                         else "")
            if text.strip("…"):
                first["overlay"] = {"type": "hook", "text": text[:70],
                                    "kicker": "", "emphasis": ""}
                first["on_screen_text"] = first["overlay"]["text"]


def _split_sentences(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p for p in parts if p]


def _mechanical_scenes(script_md: str, prompt_prefix: str,
                       target_seconds: float = 6.0) -> list[dict]:
    """División del guion sin LLM (modo preview): agrupa frases en escenas del
    ritmo pedido respetando las secciones '## ' y rota las animaciones.
    Preserva el texto EXACTO del guion del usuario."""
    animations = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    max_words = max(6, round(target_seconds * WORDS_PER_SECOND))
    sections: list[tuple[str, list[str]]] = []
    current = ("Narración", [])
    for line in script_md.splitlines():
        if line.startswith("## "):
            if current[1]:
                sections.append(current)
            current = (line[3:].strip() or "Sección", [])
        elif line.strip():
            current[1].append(line.strip())
    if current[1]:
        sections.append(current)

    scenes: list[dict] = []
    for section, lines in sections:
        chunk: list[str] = []
        words = 0
        def flush():
            nonlocal chunk, words
            if chunk:
                scenes.append({
                    "id": len(scenes) + 1,
                    "section": section,
                    "narration": " ".join(chunk),
                    "broll_prompt": f"{prompt_prefix}, {section}".strip(", "),
                    "broll_type": "image",
                    "animation": animations[len(scenes) % len(animations)],
                    "on_screen_text": "",
                })
                chunk, words = [], 0
        for sentence in _split_sentences(" ".join(lines)):
            chunk.append(sentence)
            words += len(sentence.split())
            if words >= max_words:
                flush()
        flush()
    return scenes


def _atomize(segments: list[dict], target: float) -> list[dict]:
    """Convierte los segmentos del STT en 'átomos' de como mucho ~target
    segundos: los segmentos más largos que el ritmo se parten por tiempo,
    repartiendo su texto por palabras (para el subtítulo). Así la imagen puede
    cambiar dentro de una frase larga."""
    atoms: list[dict] = []
    for seg in segments:
        dur = seg["end"] - seg["start"]
        n = max(1, round(dur / target)) if dur > target * 1.4 else 1
        if n == 1:
            atoms.append(dict(seg))
            continue
        words = seg["text"].split()
        per = max(1, len(words) // n)
        for i in range(n):
            a = seg["start"] + dur * i / n
            b = seg["start"] + dur * (i + 1) / n
            chunk = words[i * per: (i + 1) * per] if i < n - 1 else words[i * per:]
            atoms.append({"start": a, "end": b, "text": " ".join(chunk)})
    return atoms


def _group_narration(segments: list[dict], target_seconds: float = 6.0) -> list[dict]:
    """Divide la narración transcrita (con tiempos del audio real) en escenas de
    ~target_seconds. Cada escena lleva su tramo exacto de audio
    [audio_start, audio_end]; la imagen cambia a ese ritmo."""
    atoms = _atomize(segments, target_seconds)
    scenes: list[dict] = []
    cur: list[dict] = []
    for a in atoms:
        cur.append(a)
        if cur[-1]["end"] - cur[0]["start"] >= target_seconds * 0.85:
            scenes.append(_scene_from_group(cur, len(scenes) + 1))
            cur = []
    if cur:
        # evita una última escena minúscula: fúndela con la anterior
        if scenes and cur[-1]["end"] - cur[0]["start"] < target_seconds * 0.4:
            prev = scenes[-1]
            prev["narration"] = (prev["narration"] + " "
                                 + " ".join(s["text"] for s in cur)).strip()
            prev["audio_end"] = round(cur[-1]["end"], 3)
        else:
            scenes.append(_scene_from_group(cur, len(scenes) + 1))
    # Fronteras CONTINUAS: el fin de cada escena es el inicio de la siguiente.
    # Whisper deja huecos entre segmentos (pausas, respiraciones); si se
    # descartaran, el video quedaría más corto que la narración y la voz se
    # desincronizaría. La fase de voz ancla además la primera escena a 0 y la
    # última al final real del audio.
    for a, b in zip(scenes, scenes[1:]):
        a["audio_end"] = b["audio_start"]
    return scenes


def _scene_from_group(group: list[dict], idx: int) -> dict:
    return {
        "id": idx,
        "section": "Narración",
        "narration": " ".join(s["text"] for s in group).strip(),
        "audio_start": round(group[0]["start"], 3),
        "audio_end": round(group[-1]["end"], 3),
        "broll_type": "image",
        "animation": ["zoom_in", "pan_right", "zoom_out", "pan_left"][(idx - 1) % 4],
        "on_screen_text": "",
    }


def _broll_for_fixed(llm, concept, scenes, lang, videogen_scenes,
                     project=None, short_form: bool = False,
                     template_rules: str = "") -> None:
    """Rellena broll_prompt / on_screen_text / section de escenas ya fijadas por
    el audio, para que el B-roll sea coherente con lo que se dice en cada tramo.
    Modifica `scenes` en el sitio."""
    prefix = concept["visual_style"]["prompt_prefix"]
    if getattr(llm, "is_mock", False):
        for s in scenes:
            s["broll_prompt"] = f"{prefix}, {s['narration'][:60]}".strip(", ")
        return

    schema = {
        "type": "object",
        "properties": {"scenes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "broll_prompt": {"type": "string"},
                "broll_type": {"type": "string", "enum": ["image", "video"]},
                "animation": {"type": "string", "enum": ["zoom_in", "zoom_out",
                              "pan_left", "pan_right", "static"]},
                "section": {"type": "string"},
                **_CREATIVE_PROPS,
            },
            "required": ["broll_prompt", "broll_type", "animation", "section",
                         *_CREATIVE_PROPS],
            "additionalProperties": False,
        }}},
        "required": ["scenes"], "additionalProperties": False,
    }
    cast_names, cast_rules = _cast_rules(project) if project else ([], "")
    schema = _schema_with_cast(schema, cast_names)
    system = (
        f"Eres a la vez director de fotografía, editor senior y director "
        f"creativo de documentales y videos largos de YouTube en {lang}. Las "
        "escenas y su narración YA están fijadas por el audio del narrador; tú "
        "diseñas el apoyo visual, los rótulos y la dirección de la banda "
        "sonora de cada una con criterio cinematográfico.")
    # Por TANDAS: un video largo (~200 escenas) no cabe en una sola respuesta
    # del modelo — el JSON llegaba cortado y la fase moría («Unterminated
    # string», caso real con un video de ~20 min).
    from ytstudio.progress import notify
    got: list[dict] = []
    tandas = -(-len(scenes) // _SCENES_PER_CALL)
    for n_t, start in enumerate(range(0, len(scenes), _SCENES_PER_CALL), 1):
        chunk = scenes[start:start + _SCENES_PER_CALL]
        if tandas > 1:
            notify(f"🎬 Diseño de escenas (tanda {n_t}/{tandas}): escenas "
                   f"{chunk[0]['id']}–{chunk[-1]['id']}…")
        narr = "\n".join(f"[{s['id']}] {s['narration']}" for s in chunk)
        parte = (f"(Es la TANDA {n_t} de {tandas} de un video de "
                 f"{len(scenes)} escenas — mantén un criterio consistente "
                 "con el resto.)\n" if tandas > 1 else "")
        prompt = (
            f"Para cada una de estas {len(chunk)} escenas (en el mismo orden "
            "y cantidad), diseña el apoyo audiovisual de lo que se dice:\n"
            + parte +
            "- broll_prompt: prompt EN INGLÉS, detallado, que ilustre el "
            f"contenido de esa narración concreta, comenzando con el prefijo "
            f"de estilo \"{prefix}\". Sin texto ni letras en la imagen (salvo "
            "el image_text exacto de las escenas que lo definan), sin "
            "personas reales.\n"
            + (f"- broll_type: 'video' solo en las {videogen_scenes} de mayor "
               "impacto del video completo, el resto 'image'.\n"
               if videogen_scenes else "- broll_type: siempre 'image'.\n")
            + "- animation: alterna zoom_in/zoom_out/pan_left/pan_right.\n"
            "- section: título temático corto del tramo (para los capítulos).\n\n"
            + CREATIVE_RULES
            + (SHORT_FORM_RULES if short_form else "")
            + template_rules
            + cast_rules
            + f"\nNARRACIÓN POR ESCENA:\n{narr}")
        try:
            result = llm.complete_json(system, prompt, schema=schema,
                                       max_tokens=32000, purpose="broll_fixed")
            got += list(result["scenes"])[:len(chunk)]
        except Exception as e:
            # UNA tanda fallida no puede tumbar el storyboard entero (y
            # obligar a re-pagar las tandas buenas al reanudar): sus escenas
            # salen con un prompt básico desde la narración — el pase de
            # dirección de arte (que corre después) las reescribe con la
            # biblia visual, así que en la práctica se recuperan solas.
            anims = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
            got += [{"broll_prompt":
                     f"{prefix}, {(s.get('narration') or '')[:80]}".strip(", "),
                     "broll_type": "image",
                     "animation": anims[i % 4], "section": "Narración"}
                    for i, s in enumerate(chunk)]
            aviso = (f"El diseño de las escenas {chunk[0]['id']}–"
                     f"{chunk[-1]['id']} falló ({e}): salen con un prompt "
                     "básico que el pase de dirección de arte refina después.")
            if project is not None:
                project.add_warning(aviso)
            else:
                notify("⚠ " + aviso)
    for i, s in enumerate(scenes):
        b = got[i] if i < len(got) else {}
        s["broll_prompt"] = b.get("broll_prompt") or f"{prefix}, {s['narration'][:50]}"
        s["broll_type"] = b.get("broll_type", "image")
        if cast_names:
            s["characters"] = b.get("characters") or []
        s["animation"] = b.get("animation", s["animation"])
        if b.get("section"):
            s["section"] = b["section"]
        for key in _CREATIVE_PROPS:
            if key in b:
                s[key] = b[key]
    if cast_names:
        _normalize_cast(scenes, cast_names)


_ELEMENTS_SCHEMA = {
    "type": "object",
    "properties": {"scenes": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "elements": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string",
                             "enum": ["persona", "lugar", "entidad", "mapa",
                                      "cifra", "fecha"]},
                    "consulta": {"type": "string"},
                    "etiqueta": {"type": "string"},
                    "momento": {"type": "string"},
                },
                "required": ["tipo", "consulta", "etiqueta", "momento"],
                "additionalProperties": False,
            }},
        },
        "required": ["id", "elements"],
        "additionalProperties": False,
    }}},
    "required": ["scenes"], "additionalProperties": False,
}


def _archive_pass(llm, project, scenes: list[dict], lang: str, cfg: dict,
                  short_form: bool) -> None:
    """DOCUMENTALISTA DE ARCHIVO: recorre la narración ya fijada y decide qué
    menciones concretas merecen material de apoyo SOBREPUESTO al B-roll — la
    foto real del personaje o el lugar, la cifra con cuenta ascendente, la
    fecha en tarjeta. Es un acento documental, no papel tapiz: pocas y buenas.
    Los elementos se resuelven después (banco local → Wikimedia → generado) y
    el montaje los anima en el instante exacto de la mención."""
    if short_form or getattr(llm, "is_mock", False) \
            or not cfg["video"].get("elements", True):
        return
    from ytstudio.progress import notify
    notify("📎 Documentalista de archivo: buscando menciones que merecen "
           "material de apoyo (fotos reales, cifras, fechas)…")
    system = (
        f"Eres el DOCUMENTALISTA DE ARCHIVO de un documental en {lang}. "
        "Detectas en la narración las menciones que un editor profesional "
        "apoyaría con un inserto sobre el B-roll: la foto real de una persona "
        "o lugar célebre, una cifra impactante, una fecha clave. Eres "
        "selectivo: un inserto cada 3-4 escenas como MUCHO — el exceso "
        "abarata el video.")
    tandas = -(-len(scenes) // _SCENES_PER_CALL)
    got: dict[int, list] = {}
    for n_t, start in enumerate(range(0, len(scenes), _SCENES_PER_CALL), 1):
        chunk = scenes[start:start + _SCENES_PER_CALL]
        narr = "\n".join(
            f"[{s['id']}] {s['narration']}"
            + (f"  (ya lleva rótulo: {s['overlay']['text']})"
               if s.get("overlay") else "")
            for s in chunk)
        prompt = (
            f"(Tanda {n_t}/{tandas}.) Para estas escenas, marca SOLO las "
            "menciones que de verdad merecen un inserto de archivo:\n"
            "- tipo 'persona'/'lugar'/'entidad': algo FAMOSO con foto "
            "canónica (Elon Musk, El Cairo, la UNESCO). consulta = nombre "
            "del artículo de Wikipedia. NUNCA personas no públicas.\n"
            "- tipo 'mapa': cuando ubicar el sitio aporta (un imperio, una "
            "ruta). consulta = 'X location map'.\n"
            "- tipo 'cifra'/'fecha': el dato EXACTO como se narra "
            "(consulta = '60.000 personas', '1324').\n"
            "- etiqueta: pie de 2-4 palabras en el idioma del video.\n"
            "- momento: las palabras EXACTAS de la narración donde se "
            "menciona (para sincronizar el inserto con la voz).\n"
            "Reglas duras: máximo UN elemento por escena; máximo "
            f"{max(2, len(chunk) // 3)} en esta tanda; nada en escenas cuyo "
            "rótulo ya muestra ese mismo dato; ante la duda, ninguno "
            "(elements=[] en casi todas las escenas es lo normal).\n\n"
            f"NARRACIÓN POR ESCENA:\n{narr}")
        try:
            res = llm.complete_json(system, prompt, schema=_ELEMENTS_SCHEMA,
                                    max_tokens=16000,
                                    purpose="archive_elements")
            for row in res.get("scenes", []):
                els = [e for e in (row.get("elements") or [])
                       if e.get("consulta") and e.get("momento")][:1]
                if els:
                    got[int(row.get("id", -1))] = els
        except Exception as e:
            project.add_warning(
                f"El documentalista de archivo no pudo revisar las escenas "
                f"{chunk[0]['id']}–{chunk[-1]['id']} ({e}): salen sin "
                "insertos (el video no se detiene por un adorno).")
    cap = max(3, len(scenes) // 3)   # densidad: acento, no papel tapiz
    for s in scenes:
        els = got.get(s["id"])
        if els and cap > 0 and not s.get("sticker"):
            s["elements"] = els
            cap -= 1
    n = sum(len(s.get("elements") or []) for s in scenes)
    if n:
        notify(f"📎 {n} inserto(s) de archivo planificados "
               "(fotos con licencia libre, cifras y fechas animadas).")


def _auditar_prompts(project, scenes: list[dict]) -> None:
    """Comprobación GRATUITA (sin modelo) de que los prompts no se dejaron por
    el camino los hechos que la narración afirma: la CANTIDAD exacta y el
    ESTADO sin vida — los dos que fallaron en los videos reales del creador.

    Hasta ahora esto solo lo cazaba el control de calidad con visión, es
    decir, DESPUÉS de pagar la imagen. Aquí se detecta antes de gastar nada."""
    from ytstudio.progress import notify
    fallos: list[str] = []
    for s in scenes:
        faltan = auditar_fidelidad(s.get("narration") or "",
                                   s.get("broll_prompt") or "")
        if faltan:
            fallos.append(f"escena {s['id']}: falta {', '.join(faltan)}")
    if not fallos:
        return
    project.add_warning(
        f"🔍 Fidelidad de los prompts: {len(fallos)} escena(s) podrían no "
        "reflejar un hecho de su narración — " + " · ".join(fallos[:6])
        + (" · y más" if len(fallos) > 6 else "")
        + ". El control de calidad con visión las revisará; si te importa, "
        "corrígelas en el storyboard antes de generar (ahí es gratis).")
    notify(f"🔍 Auditoría de fidelidad: {len(fallos)} escena(s) con un hecho "
           "posiblemente ausente del prompt (revisa el aviso del panel).")


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    concept = project.get("concept")
    script_md = load_script(project)
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)  # nombre completo del idioma para el LLM
    videogen_scenes = cfg["providers"]["videogen"].get("max_scenes", 0)

    target = scene_seconds(cfg, project)

    from ytstudio.catalog import is_short_form, short_template
    short_form = is_short_form(cfg)
    tpl = short_template(project, cfg)
    tpl_rules = ("\n" + tpl["scene_rules"] + "\n") if tpl and \
        tpl.get("scene_rules") else ""

    # MODO NARRACIÓN PROPIA: escenas alineadas al audio real del usuario.
    narration = project.get("narration")
    if narration and narration.get("segments"):
        scenes = _group_narration(narration["segments"], target)
        _broll_for_fixed(llm, concept, scenes, lang, videogen_scenes,
                         project=project, short_form=short_form,
                         template_rules=tpl_rules)
        _assign_video_scenes(scenes, cfg)  # nº de escenas de video determinista
        _art_direction_pass(llm, project, scenes, concept, lang,
                            short_form=short_form,
                            template_rules=tpl_rules)
        _normalize_creative(scenes, short_form=short_form)
        _auditar_prompts(project, scenes)
        _archive_pass(llm, project, scenes, lang, cfg, short_form)
        _assign_shots(project, scenes, cfg)
        _write_outputs(project, scenes)
        return

    # Sin LLM real (modo preview): dividir el guion real mecánicamente en vez
    # de sustituirlo por escenas de ejemplo.
    if getattr(llm, "is_mock", False):
        scenes = _mechanical_scenes(
            script_md, concept["visual_style"]["prompt_prefix"], target)
        if scenes:
            _assign_video_scenes(scenes, cfg)
            _normalize_creative(scenes, short_form=short_form)
            _assign_shots(project, scenes, cfg)
            _write_outputs(project, scenes)
            return

    system = (
        f"Eres a la vez editor senior, director de fotografía y director "
        f"creativo de documentales, series y videos largos de YouTube en {lang}. "
        "Conviertes guiones en storyboards listos para producción con IA, con "
        "criterio cinematográfico: los rótulos son acentos puntuales, la música "
        "dibuja el arco dramático y el silencio es un recurso narrativo."
    )
    words = max(6, round(target * WORDS_PER_SECOND))
    lo, hi = max(4, words - 4), words + 6
    broll_type_rule = (
        f"- 'broll_type': usa 'video' solo en las {videogen_scenes} escenas de "
        "mayor impacto (gancho/clímax); el resto 'image'.\n" if videogen_scenes
        else "- 'broll_type': siempre 'image'.\n")
    prompt = (
        "Divide este guion en escenas para el montaje. Reglas:\n"
        f"- Cada escena cubre ~{target:.0f} segundos de narración "
        f"(aprox. {lo}-{hi} palabras) — la imagen cambia a ese ritmo. NO cambies "
        "ni recortes el texto del guion: el campo 'narration' debe contener el "
        "texto EXACTO, y la concatenación de todas las escenas debe reconstruir "
        "el guion completo.\n"
        "- 'section': encabezado del guion al que pertenece.\n"
        "- 'broll_prompt': prompt EN INGLÉS para generar la imagen/video IA de "
        f"fondo, coherente con lo que se dice en esa escena. Detallado y SIEMPRE "
        f"comenzando con el prefijo de estilo \"{concept['visual_style']['prompt_prefix']}\". "
        "Sin texto ni letras dentro de la imagen (salvo el image_text exacto "
        "de las escenas que lo definan), sin personas famosas reales.\n"
        + broll_type_rule +
        "- 'animation': varía entre zoom_in, zoom_out, pan_left, pan_right "
        "(evita repetir la misma dos veces seguidas).\n\n"
        + CREATIVE_RULES
        + (SHORT_FORM_RULES if short_form else "")
        + tpl_rules
        + f"\nGUION:\n<<<\n{script_md}\n>>>"
    )

    cast_names, cast_rules = _cast_rules(project)
    if cast_rules:
        prompt += cast_rules
    result = llm.complete_json(system, prompt,
                               schema=_schema_with_cast(SCENES_SCHEMA,
                                                        cast_names),
                               max_tokens=64000, purpose="scenes")
    scenes = result["scenes"]
    for i, s in enumerate(scenes, start=1):
        s["id"] = i  # ids consecutivos garantizados
    _normalize_cast(scenes, cast_names)
    _assign_video_scenes(scenes, cfg)  # nº de escenas de video determinista
    _art_direction_pass(llm, project, scenes, concept, lang,
                        short_form=short_form,
                        template_rules=tpl_rules)
    _normalize_creative(scenes, short_form=short_form)
    _auditar_prompts(project, scenes)
    _archive_pass(llm, project, scenes, lang, cfg, short_form)
    _assign_shots(project, scenes, cfg)
    _write_outputs(project, scenes)


def _assign_shots(project, scenes: list[dict], cfg: dict) -> None:
    """Reparte qué escenas muestran al PERSONAJE narrador (lipsync) y cuáles
    B-roll, respetando el % de presencia elegido con criterio NARRATIVO — con
    las señales que el propio director ya puso en las escenas:

      · el gancho (escena 1) y el cierre (última) piden la cara del narrador
        (primera persona: abre y cierra mirando a cámara),
      · los picos dramáticos (music_intensity alta) y los arranques de
        sección son los otros momentos naturales de personaje,
      · el resto ilustra con B-roll.

    Determinista y sin costo: usa las señales existentes, no llama al LLM.
    El usuario puede forzar escena a escena desde el Editor (shot_overrides)."""
    from ytstudio.characters import narrator
    ch = project.get("character") or {}
    has_img = narrator(project) is not None
    # narrador añadido después (sin % configurado) → 30% por defecto
    share = ch.get("presence")
    share = 0.3 if (has_img and share is None) else float(share or 0.0)
    if not has_img or share <= 0 or not scenes:
        for s in scenes:
            s.pop("shot", None)
        return
    # peso de cada escena ≈ su duración (span de audio o nº de palabras)
    def weight(s):
        if s.get("audio_start") is not None and s.get("audio_end") is not None:
            return max(0.5, float(s["audio_end"]) - float(s["audio_start"]))
        return max(1, len((s.get("narration") or "").split()))
    total = sum(weight(s) for s in scenes)
    score = []
    last_section = None
    for i, s in enumerate(scenes):
        pts = float(s.get("music_intensity") or 0.5)
        if i == 0:
            pts += 2.0            # gancho en primera persona
        if i == len(scenes) - 1:
            pts += 1.6            # cierre mirando a cámara
        if s.get("section") != last_section:
            pts += 0.3            # arranque de bloque narrativo (bono leve:
                                  # nunca debe ganarle a un clímax real)
        last_section = s.get("section")
        score.append((pts, i))
    acc = 0.0
    chosen: set[int] = set()
    for _, i in sorted(score, reverse=True):
        if acc / total >= share:
            break
        chosen.add(i)
        acc += weight(scenes[i])
    for i, s in enumerate(scenes):
        s["shot"] = "personaje" if i in chosen else "broll"


def _write_outputs(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Storyboard", ""]
    ad = project.get("art_direction") or {}
    if ad:
        md += ["## Dirección de arte (biblia visual del video)",
               f"- **Época/lugar:** {ad.get('era_setting', '')}",
               f"- **Paleta:** {ad.get('palette', '')}",
               f"- **Luz:** {ad.get('lighting', '')}",
               f"- **Cámara:** {ad.get('camera_language', '')}",
               f"- **Textura/acabado:** {ad.get('texture_grade', '')}",
               f"- **Motivos recurrentes:** "
               f"{', '.join(ad.get('motifs') or [])}",
               ""]
    for s in scenes:
        kind = s["broll_type"]
        if s.get("motion_risk"):
            kind += f", movimiento: riesgo {s['motion_risk']}"
        if s.get("layout") == "dividida":
            kind += ", PANTALLA DIVIDIDA"
        md += [f"## Escena {s['id']} — {s['section']} ({s['animation']}, {kind})",
               f"**Narración:** {s['narration']}",
               f"**B-roll:** {s['broll_prompt']}"]
        if s.get("layout") == "dividida" and s.get("broll_prompt_b"):
            md.append(f"**B-roll B (segunda mitad):** {s['broll_prompt_b']}")
        o = s.get("overlay")
        if o:
            kick = f" ({o['kicker']})" if o.get("kicker") else ""
            md.append(f"**Rótulo [{o['type']}]:** {o['text']}{kick}")
        extras = [f"música {s['music_intensity']:.2f}" if "music_intensity" in s else ""]
        if s.get("transition"):
            extras.append(f"entra: {s['transition']}")
        if s.get("pause_after"):
            extras.append(f"respiro {s['pause_after']:.1f}s")
        if s.get("sfx"):
            extras.append(f"sfx {s['sfx']}")
        if s.get("sticker"):
            extras.append(f"sticker {s['sticker']['type']}: "
                          f"«{s['sticker']['text']}»")
        md.append(f"*({', '.join(x for x in extras if x)})*")
        md.append("")
    project.path("scenes", "storyboard.md").write_text("\n".join(md), encoding="utf-8")
    project.set("scene_count", len(scenes))


def load_scenes(project) -> list[dict]:
    from ytstudio.project import read_json_tolerant
    return read_json_tolerant(project.path("scenes", "scenes.json"))["scenes"]


def save_scenes(project, scenes: list[dict]) -> None:
    project.path("scenes", "scenes.json").write_text(
        json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
