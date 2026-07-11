"""FASE 1 — Ingesta: detecta el tipo de input (guion listo, idea en texto,
nota de voz, imagen o video de referencia) y lo normaliza a un brief creativo."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ytstudio.providers import get_llm, get_stt
from ytstudio.utils.media import extract_audio, extract_frames

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
TEXT_EXT = {".txt", ".md"}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "detected_type": {"type": "string", "enum": ["script", "idea"]},
    },
    "required": ["topic", "summary", "key_points", "detected_type"],
    "additionalProperties": False,
}


def detect_input_type(source: Path | None, text: str | None, forced: str) -> str:
    if forced != "auto":
        return forced
    if text is not None:
        # Heurística: un texto largo con estructura suele ser un guion listo
        return "script" if len(text.split()) > 350 else "idea"
    ext = source.suffix.lower()
    if ext in AUDIO_EXT:
        return "voice"
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT:
        content = source.read_text()
        return "script" if len(content.split()) > 350 else "idea"
    raise ValueError(f"No sé interpretar el archivo: {source.name}")


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    input_dir = project.path("input")
    meta = project.get("input_meta")
    if not meta:
        raise RuntimeError("El proyecto no tiene input. Créalo con 'ytstudio new'.")

    input_type = meta["type"]
    lang = cfg.get("language", "es")
    raw_text, frames = "", []

    if input_type in ("script", "idea"):
        raw_text = (input_dir / meta["file"]).read_text()
    elif input_type == "voice":
        stt = get_stt(cfg)
        raw_text = stt.transcribe(input_dir / meta["file"])
        (input_dir / "transcripcion.txt").write_text(raw_text)
    elif input_type == "video":
        video = input_dir / meta["file"]
        audio = extract_audio(video, input_dir / "audio_referencia.mp3")
        stt = get_stt(cfg)
        raw_text = stt.transcribe(audio)
        (input_dir / "transcripcion.txt").write_text(raw_text)
        frames = extract_frames(video, input_dir / "frames", count=6)
    elif input_type == "image":
        frames = [input_dir / meta["file"]]

    system = (f"Eres un estratega de contenido de YouTube. Analizas el material de "
              f"entrada de un creador y produces un brief creativo en {lang}. "
              f"Responde en el JSON pedido.")
    prompt_parts = [f"Tipo de input declarado: {input_type}."]
    if raw_text:
        prompt_parts.append(f"Material de entrada:\n<<<\n{raw_text}\n>>>")
    if frames:
        prompt_parts.append(
            "Analiza también las imágenes adjuntas (referencia visual o fotogramas "
            "del video de referencia) y extrae estilo, tema y elementos clave.")
    prompt_parts.append(
        "Devuelve: topic (tema del video), summary (brief creativo de 3-6 frases), "
        "key_points (5-10 puntos que debe cubrir el video) y detected_type "
        "('script' si el texto ya es un guion completo listo para narrar, "
        "'idea' en caso contrario).")

    analysis = llm.complete_json(system, "\n\n".join(prompt_parts),
                                 schema=ANALYSIS_SCHEMA, purpose="ingest_analysis")

    brief = {
        "input_type": input_type,
        "raw_text": raw_text,
        "reference_frames": [str(f) for f in frames],
        **analysis,
    }
    (input_dir / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2))
    project.set("brief", brief)


def stage_input(project, source: Path | None, text: str | None, forced: str) -> dict:
    """Copia el input a 01_input/ y registra su tipo (se llama desde 'new')."""
    input_dir = project.path("input")
    input_type = detect_input_type(source, text, forced)
    if text is not None:
        file = input_dir / "input.txt"
        file.write_text(text)
    else:
        file = input_dir / source.name
        shutil.copy(source, file)
    meta = {"type": input_type, "file": file.name}
    project.set("input_meta", meta)
    return meta
