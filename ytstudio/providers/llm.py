"""Proveedor LLM: Claude (Anthropic) para las fases creativas y de análisis,
más un mock determinista para probar el pipeline sin claves de API."""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path


class ClaudeLLM:
    def __init__(self, cfg: dict):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = cfg["providers"]["llm"].get("model", "claude-opus-4-8")

    def complete(self, system: str, prompt: str, *, schema: dict | None = None,
                 images: list[Path] | None = None, max_tokens: int = 16000,
                 purpose: str = "") -> str:
        content: list[dict] = []
        for img in images or []:
            media_type = mimetypes.guess_type(img.name)[0] or "image/jpeg"
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(img.read_bytes()).decode(),
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
        if schema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

        with self.client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            raise RuntimeError("El modelo rechazó la petición (stop_reason=refusal).")
        return next(b.text for b in message.content if b.type == "text")

    def complete_json(self, system: str, prompt: str, *, schema: dict,
                      images: list[Path] | None = None, max_tokens: int = 16000,
                      purpose: str = "") -> dict:
        text = self.complete(system, prompt, schema=schema, images=images,
                             max_tokens=max_tokens, purpose=purpose)
        return json.loads(text)


class MockLLM:
    """Respuestas deterministas por fase — permite recorrer el pipeline entero
    (y validar el montaje con ffmpeg) sin ninguna clave de API."""

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def complete(self, system: str, prompt: str, *, schema: dict | None = None,
                 images=None, max_tokens: int = 16000, purpose: str = "") -> str:
        if schema is not None:
            return json.dumps(self._mock_for(purpose), ensure_ascii=False)
        return self._mock_text(purpose)

    def complete_json(self, system: str, prompt: str, *, schema: dict,
                      images=None, max_tokens: int = 16000, purpose: str = "") -> dict:
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
                "title": "La historia que nadie te contó",
                "description": "Un recorrido fascinante por una historia poco conocida.\n\n"
                               "Capítulos:\n00:00 Introducción",
                "tags": ["historia", "documental", "curiosidades"],
                "thumbnail_text": "NADIE TE LO CONTÓ",
            }
        if purpose == "ingest_analysis":
            return {
                "topic": "Una historia fascinante de ejemplo",
                "summary": "Brief de ejemplo generado por MockLLM para probar el pipeline.",
                "key_points": ["Punto uno", "Punto dos", "Punto tres"],
                "detected_type": "idea",
            }
        return {}
