"""Proveedor LLM: Claude (Anthropic) para las fases creativas y de análisis,
más un mock determinista para probar el pipeline sin claves de API."""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path


def _sniff_media_type(data: bytes, name: str) -> str:
    """Tipo real de la imagen por sus BYTES, no por la extensión: algunos
    generadores devuelven PNG aunque se les pida .jpg, y la API rechaza con
    un 400 la imagen cuyo media_type declarado no coincide con el contenido
    (pasó de verdad: el control de calidad con visión falló entero por una
    'jpg' que era PNG)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return mimetypes.guess_type(name)[0] or "image/jpeg"

# Palabras clave de JSON Schema que la API de structured output NO admite.
# Un schema con cualquiera de ellas se rechaza ENTERO con un error 400 críptico
# a mitad del pipeline (pasó de verdad: 'minItems: 3' tumbó la fase de
# metadatos tras haber pagado ya todas las fases anteriores). Se valida ANTES
# de llamar — y también en el mock, para que las pruebas locales sin clave
# detecten un schema inválido igual que lo haría la API real.
_UNSUPPORTED_KEYWORDS = (
    "maxItems", "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "uniqueItems", "oneOf", "anyOf", "allOf", "not", "$ref",
)


def check_schema(schema, _path: str = "schema") -> None:
    """Verifica que un JSON Schema sea compatible con structured output.
    Lanza ValueError con la ruta exacta del problema (no un 400 genérico)."""
    if isinstance(schema, list):
        for i, item in enumerate(schema):
            check_schema(item, f"{_path}[{i}]")
        return
    if not isinstance(schema, dict):
        return
    for key in _UNSUPPORTED_KEYWORDS:
        if key in schema:
            raise ValueError(
                f"Schema no admitido por la API en {_path}: '{key}' no está "
                "soportado en structured output. Quítalo del schema y exige "
                "esa restricción en el PROMPT (y sanea el resultado en "
                "código).")
    # minItems solo admite 0 o 1
    if "minItems" in schema and schema["minItems"] not in (0, 1):
        raise ValueError(
            f"Schema no admitido por la API en {_path}: 'minItems' solo "
            f"acepta 0 o 1 (tiene {schema['minItems']!r}). Pide la cantidad "
            "exacta en el PROMPT y ajústala en código.")
    for key, value in schema.items():
        if isinstance(value, (dict, list)):
            check_schema(value, f"{_path}.{key}")


class _Truncated(Exception):
    """La respuesta se cortó por el límite de tokens (uso interno)."""

    def __init__(self, max_tokens: int):
        super().__init__(f"respuesta cortada en {max_tokens} tokens")
        self.max_tokens = max_tokens


def _server_wait(e: Exception, attempt: int) -> float | None:
    """Segundos de espera si el error es TRANSITORIO del servidor de Anthropic
    (límite de peticiones 429, sobrecarga 529, 5xx, o corte de conexión), o
    None si es un error real (400/401/404…) que debe subir intacto.

    Un video largo hace ~25 llamadas grandes seguidas (tandas de escenas,
    dirección de arte, control factual con visión…): sin esto, el primer 429
    de Anthropic mataría la fase igual que el de OpenAI mató la de imágenes
    (el SDK reintenta solo 2 veces con esperas cortas — insuficiente para un
    límite de tokens-por-minuto)."""
    code = getattr(e, "status_code", None)
    transient = (code in (429, 529)
                 or (isinstance(code, int) and code >= 500)
                 or type(e).__name__ in ("APIConnectionError",
                                         "APITimeoutError"))
    if not transient:
        return None
    retry_after = 0.0
    try:
        headers = getattr(getattr(e, "response", None), "headers", None) or {}
        retry_after = float(headers.get("retry-after") or 0)
    except (TypeError, ValueError):
        pass
    return min(120.0, max(retry_after + 1.0, 20.0 * attempt))


class ClaudeLLM:
    is_mock = False

    def __init__(self, cfg: dict):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = cfg["providers"]["llm"].get("model", "claude-opus-4-8")

    # Techo de salida del modelo (Opus 4.8/5: 128K). El límite de salida NO se
    # reserva ni se cobra: solo se paga lo que el modelo genera de verdad. Por
    # eso pedir un techo alto es GRATIS y evita respuestas cortadas.
    MAX_OUTPUT = 128000
    SERVER_RETRIES = 4   # reintentos ante 429/529/5xx/corte de conexión

    # Profundidad de razonamiento por PROPÓSITO: las tareas creativas (guion,
    # escenas, dirección de arte, concepto) razonan a fondo; las auxiliares
    # (describir B-roll, elegir música, pulir transcripción, revisar con
    # visión) no necesitan tanto — bajarlas a 'medium' ahorra tokens de
    # razonamiento sin tocar la calidad del video.
    EFFORT_BY_PURPOSE = {
        "broll_describe": "medium", "broll_semantic": "medium",
        "broll_review": "medium", "broll_qa": "medium",
        "music_pick": "medium", "music_pick_acts": "medium",
        "transcript_polish": "medium", "ingest_analysis": "medium",
        "archive_elements": "medium", "sound_design": "medium",
    }

    def complete(self, system: str, prompt: str, *, schema: dict | None = None,
                 images: list[Path] | None = None, max_tokens: int = 64000,
                 purpose: str = "") -> str:
        """Una llamada al modelo. Si la respuesta se corta por el límite de
        tokens, se REINTENTA UNA VEZ con el techo ampliado — el gasto de la
        llamada cortada se registra igual (se pagó), pero la fase no muere."""
        try:
            return self._resilient(system, prompt, schema=schema,
                                   images=images, max_tokens=max_tokens,
                                   purpose=purpose)
        except _Truncated as e:
            bigger = min(self.MAX_OUTPUT, max(e.max_tokens * 3, 96000))
            if bigger <= e.max_tokens:
                raise RuntimeError(
                    "La respuesta del modelo se cortó incluso con el techo "
                    f"máximo de tokens ({e.max_tokens}) — la petición es "
                    "demasiado grande y debe partirse en tandas.") from None
            from ytstudio.progress import notify
            notify(f"↻ La respuesta se cortó por el límite de tokens "
                   f"({e.max_tokens}); se reintenta con {bigger} "
                   "(el modelo solo cobra lo que genera).")
            try:
                return self._resilient(system, prompt, schema=schema,
                                       images=images, max_tokens=bigger,
                                       purpose=purpose)
            except _Truncated:
                raise RuntimeError(
                    f"La respuesta del modelo se cortó dos veces (hasta "
                    f"{bigger} tokens): la petición es demasiado grande y "
                    "debe partirse en tandas.") from None

    def _resilient(self, system: str, prompt: str, **kw) -> str:
        """_once con reintentos ante errores TRANSITORIOS del servidor: espera
        lo que pida el retry-after (o 20s·intento, tope 120s) y avisa en el
        log. Los errores reales (400/401/404, refusal, truncado) suben tal
        cual — reintentarlos sería gastar dinero en el mismo fallo."""
        import time

        from ytstudio.progress import notify
        for attempt in range(1, self.SERVER_RETRIES + 1):
            try:
                return self._once(system, prompt, **kw)
            except (_Truncated, RuntimeError):
                raise
            except Exception as e:
                wait = _server_wait(e, attempt)
                if wait is None or attempt == self.SERVER_RETRIES:
                    raise
                code = getattr(e, "status_code", None)
                tag = f"{type(e).__name__}{f' {code}' if code else ''}"
                notify(f"⏳ Anthropic no responde ({tag}): espero "
                       f"{wait:.0f}s y reintento "
                       f"({attempt}/{self.SERVER_RETRIES - 1})…")
                time.sleep(wait)
        raise RuntimeError("inalcanzable")  # el bucle siempre retorna o lanza

    def _once(self, system: str, prompt: str, *, schema: dict | None = None,
              images: list[Path] | None = None, max_tokens: int = 64000,
              purpose: str = "") -> str:
        content: list[dict] = []
        for img in images or []:
            data = img.read_bytes()
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _sniff_media_type(data, img.name),
                    "data": base64.standard_b64encode(data).decode(),
                },
            })
        content.append({"type": "text", "text": prompt})

        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": content}],
        )
        out_cfg: dict = {}
        effort = self.EFFORT_BY_PURPOSE.get(purpose, "high")
        if effort != "high":   # 'high' es el default de la API: no se envía
            out_cfg["effort"] = effort
        if schema is not None:
            check_schema(schema)  # falla claro ANTES de gastar la llamada
            out_cfg["format"] = {"type": "json_schema", "schema": schema}
        if "effort" in out_cfg:
            # Va por extra_body y no como kwarg tipado: un SDK algo viejo
            # rechazaría el parámetro desconocido y rompería TODAS las
            # llamadas. OJO: extra_body PISA el kwarg homónimo al armar el
            # cuerpo, así que effort y format viajan JUNTOS en un único
            # output_config — separados, el effort borraría el format y la
            # respuesta llegaría sin JSON estructurado.
            kwargs["extra_body"] = {"output_config": out_cfg}
        elif out_cfg:
            kwargs["output_config"] = out_cfg

        with self.client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()
        # EL GASTO SE ANOTA SIEMPRE, PASE LO QUE PASE. La API cobra los tokens
        # que generó aunque la respuesta se rechace o se corte: si se anotara
        # después de los controles de abajo, ese dinero quedaría INVISIBLE en
        # el reporte (pasó de verdad — una respuesta cortada de 16 000 tokens
        # de Opus no apareció en el gasto de la corrida).
        self._record_usage(message, purpose)
        if message.stop_reason == "refusal":
            raise RuntimeError("El modelo rechazó la petición (stop_reason=refusal).")
        if message.stop_reason == "max_tokens":
            # Con pensamiento adaptativo, max_tokens acota PENSAMIENTO +
            # RESPUESTA: en una petición grande el razonamiento puede
            # consumirlo entero y el JSON llega cortado (revienta después con
            # un críptico «Unterminated string»). Lo maneja complete() con un
            # reintento de techo ampliado.
            raise _Truncated(max_tokens)
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            # Respuesta sin texto (solo bloques de razonamiento): tratarla
            # como cortada — el reintento con más techo la completa.
            raise _Truncated(max_tokens)
        return text

    def _record_usage(self, message, purpose: str) -> None:
        # Gasto REAL (no estimado): la API devuelve los tokens exactos que
        # cobró esta llamada.
        from ytstudio import pricing, usage
        u = getattr(message, "usage", None)
        if u is None:
            return
        in_tok = int(getattr(u, "input_tokens", 0) or 0)
        out_tok = int(getattr(u, "output_tokens", 0) or 0)
        in_price, out_price = pricing.llm_price(self.model)
        usd = (in_tok * in_price + out_tok * out_price) / 1e6
        usage.record("anthropic", purpose or "llm", in_tok + out_tok, "tokens", usd)

    def complete_json(self, system: str, prompt: str, *, schema: dict,
                      images: list[Path] | None = None, max_tokens: int = 64000,
                      purpose: str = "") -> dict:
        text = self.complete(system, prompt, schema=schema, images=images,
                             max_tokens=max_tokens, purpose=purpose)
        return json.loads(text)


class MockLLM:
    """Respuestas deterministas por fase — permite recorrer el pipeline entero
    (y validar el montaje con ffmpeg) sin ninguna clave de API."""

    is_mock = True

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def complete(self, system: str, prompt: str, *, schema: dict | None = None,
                 images=None, max_tokens: int = 64000, purpose: str = "") -> str:
        if schema is not None:
            # El mock valida el schema IGUAL que la API: así un schema
            # inválido se detecta en las pruebas locales (sin clave) y no en
            # producción a mitad del pipeline.
            check_schema(schema)
            return json.dumps(self._mock_for(purpose), ensure_ascii=False)
        return self._mock_text(purpose)

    def complete_json(self, system: str, prompt: str, *, schema: dict,
                      images=None, max_tokens: int = 64000, purpose: str = "") -> dict:
        check_schema(schema)
        return self._mock_for(purpose)

    # --- contenidos de ejemplo ---
    def _mock_text(self, purpose: str) -> str:
        if purpose == "script":
            return (
                "## Gancho\n¿Sabías que la historia que estás a punto de escuchar "
                "cambió la forma en que entendemos el mundo? Quédate, porque en los "
                "próximos minutos lo vas a descubrir.\n\n"
                "## Desarrollo\nTodo comenzó con una idea simple pero poderosa. "
                "Una idea que, contra todo pronóstico, transformó su época.\n\n"
                "## Cierre\nY así llegamos al final de esta historia. Si te gustó, "
                "suscríbete y deja tu comentario. Nos vemos en el próximo video."
            )
        return "Contenido de ejemplo generado por MockLLM."

    def _mock_for(self, purpose: str) -> dict:
        if purpose == "concept":
            return {
                "title_options": ["La historia que nadie te contó",
                                  "El secreto detrás de todo",
                                  "Lo que descubrimos cambió todo"],
                "angle": "Narrativa documental con giros de intriga",
                "audience": "Curiosos de 18-45 años interesados en historias",
                "tone": "Documental cercano, con suspenso moderado",
                "structure": ["Gancho", "Contexto", "Desarrollo", "Clímax", "Cierre con CTA"],
                "visual_style": {
                    "description": "Ilustración cinematográfica, luz cálida, alto contraste",
                    "prompt_prefix": "cinematic illustration, warm dramatic lighting, high detail",
                    "palette": ["#1a1a2e", "#e94560", "#f5d061"],
                },
                "music_direction": {"mood": "cinematic", "description": "Pads atmosféricos con pulso suave"},
                "duration_minutes": 1,
            }
        if purpose == "scenes":
            return {"scenes": [
                {"id": 1, "section": "Gancho",
                 "narration": "¿Sabías que la historia que estás a punto de escuchar cambió la forma en que entendemos el mundo? Quédate, porque en los próximos minutos lo vas a descubrir.",
                 "broll_prompt": "mysterious ancient library at night, single candle, dramatic shadows",
                 "broll_type": "image", "animation": "zoom_in", "on_screen_text": "Una historia increíble"},
                {"id": 2, "section": "Desarrollo",
                 "narration": "Todo comenzó con una idea simple pero poderosa. Una idea que, contra todo pronóstico, transformó su época.",
                 "broll_prompt": "inventor sketching ideas by lamplight, vintage workshop, warm tones",
                 "broll_type": "image", "animation": "pan_right", "on_screen_text": ""},
                {"id": 3, "section": "Cierre",
                 "narration": "Y así llegamos al final de esta historia. Si te gustó, suscríbete y deja tu comentario. Nos vemos en el próximo video.",
                 "broll_prompt": "sunrise over a city skyline, hopeful atmosphere, golden hour",
                 "broll_type": "image", "animation": "zoom_out", "on_screen_text": "Suscríbete"},
            ]}
        if purpose == "metadata":
            return {
                "title_options": [
                    {"title": "La historia que nadie te contó",
                     "angle": "curiosidad / bucle abierto"},
                    {"title": "3 claves que lo explican todo",
                     "angle": "dato / beneficio concreto"},
                    {"title": "Todo lo que creías es falso",
                     "angle": "contradicción / autoridad"},
                ],
                "description_options": [
                    {"description": "Un recorrido fascinante por una historia "
                                    "poco conocida.\n\nCapítulos:\n00:00 Introducción"
                                    "\n\n#historia #documental",
                     "angle": "SEO"},
                    {"description": "¿Y si todo fue distinto?\n\nCapítulos:\n"
                                    "00:00 Introducción\n\n#historia",
                     "angle": "narrativa"},
                    {"description": "La historia, directa y sin rodeos.\n\n"
                                    "Capítulos:\n00:00 Introducción\n\n#historia",
                     "angle": "directa"},
                ],
                "tags": ["historia", "documental", "curiosidades"],
                "thumbnail_options": [
                    {"kicker": "EXPEDIENTE", "text": "NADIE TE LO CONTÓ",
                     "accent_word": "NADIE", "scene_id": 1},
                    {"kicker": "", "text": "LA VERDAD OCULTA",
                     "accent_word": "VERDAD", "scene_id": 2},
                    {"kicker": "HISTORIA", "text": "TODO ERA FALSO",
                     "accent_word": "FALSO", "scene_id": 3},
                ],
            }
        if purpose == "ingest_analysis":
            return {
                "topic": "Una historia fascinante de ejemplo",
                "summary": "Brief de ejemplo generado por MockLLM para probar el pipeline.",
                "key_points": ["Punto uno", "Punto dos", "Punto tres"],
                "detected_type": "idea",
            }
        return {}
