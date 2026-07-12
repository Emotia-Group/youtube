"""FASE 1 — Ingesta: normaliza todos los materiales del proyecto (texto
pegado y archivos por categoría) a un brief creativo.

Categorías de archivos:
- guion       documentos con el guion o la idea (txt, md, pdf, docx, pptx, xlsx)
- voz         nota de voz o narración grabada → se transcribe como base del guion
- broll       imágenes y videos PROPIOS para usar en el montaje
- referencia  imagen o video cuyo estilo/tema se analiza con visión
- auto        se infiere por el tipo de archivo
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ytstudio.providers import get_llm, get_stt
from ytstudio.utils.extract import extract_text
from ytstudio.utils.media import extract_audio, extract_frames

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".wma"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
TEXT_EXT = {".txt", ".md"}
DOC_EXT = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls"}

CATEGORIES = ("guion", "voz", "broll", "referencia")

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


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT or ext in DOC_EXT:
        return "text"
    raise ValueError(
        f"Tipo de archivo no soportado: {path.name}. Formatos válidos: "
        "texto (txt, md, pdf, docx, pptx, xlsx), audio (mp3, wav, m4a…), "
        "video (mp4, webm, mov…), imagen (jpg, png, webp…).")


def default_category(kind: str) -> str:
    return {"text": "guion", "audio": "voz",
            "image": "broll", "video": "broll"}[kind]


def add_asset(project, source: Path, category: str = "auto",
              data: bytes | None = None) -> dict:
    """Registra un archivo en 01_input/. `data` permite pasar el contenido
    directamente (subidas desde la UI); si es None, se copia desde `source`."""
    kind = kind_of(source)
    if category in ("auto", "", None):
        category = default_category(kind)
    if category not in CATEGORIES:
        raise ValueError(f"Categoría desconocida: {category}")

    assets = project.get("assets") or []
    asset_id = (max((a["id"] for a in assets), default=0)) + 1
    dest = project.path("input") / f"{asset_id:02d}_{Path(source).name}"
    if data is not None:
        dest.write_bytes(data)
    else:
        shutil.copy(source, dest)
    asset = {"id": asset_id, "file": dest.name, "name": Path(source).name,
             "category": category, "kind": kind}
    assets.append(asset)
    project.set("assets", assets)
    return asset


def remove_asset(project, asset_id: int) -> None:
    assets = project.get("assets") or []
    keep = []
    for a in assets:
        if a["id"] == asset_id:
            (project.path("input") / a["file"]).unlink(missing_ok=True)
        else:
            keep.append(a)
    project.set("assets", keep)


def set_text_input(project, text: str) -> None:
    (project.path("input") / "texto.txt").write_text(text, encoding="utf-8")
    project.set("has_text_input", bool(text.strip()))


def _migrate_legacy_input(project) -> None:
    """Proyectos creados antes del modelo de assets: convierte el input_meta
    único en un asset (o en texto pegado) para que sigan funcionando."""
    input_dir = project.path("input")
    meta = project.get("input_meta")
    if not meta or project.get("assets") or (input_dir / "texto.txt").exists():
        return
    old = input_dir / meta["file"]
    if not old.exists():
        return
    if old.suffix.lower() in TEXT_EXT:
        set_text_input(project, old.read_text(encoding="utf-8"))
    else:
        category = {"voice": "voz", "voz": "voz", "image": "referencia",
                    "video": "referencia", "referencia": "referencia",
                    "broll": "broll"}.get(meta["type"], "auto")
        add_asset(project, old, category)


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    input_dir = project.path("input")
    lang = cfg.get("language", "es")
    _migrate_legacy_input(project)
    assets = project.get("assets") or []
    stt = None

    script_parts: list[str] = []     # candidatos a guion (docs + texto pegado)
    context_parts: list[str] = []    # contexto adicional (transcripciones…)
    frames: list[Path] = []          # imágenes para análisis con visión
    forced_script = False

    text_file = input_dir / "texto.txt"
    if text_file.exists() and text_file.read_text(encoding="utf-8").strip():
        script_parts.append(text_file.read_text(encoding="utf-8").strip())

    for asset in assets:
        path = input_dir / asset["file"]
        cat, kind = asset["category"], asset["kind"]
        if cat == "guion" and kind == "text":
            script_parts.append(extract_text(path).strip())
            forced_script = True
        elif cat == "voz" and kind == "audio":
            stt = stt or get_stt(cfg)
            transcript = stt.transcribe(path)
            (input_dir / f"transcripcion_{asset['id']:02d}.txt").write_text(
                transcript, encoding="utf-8")
            # Sin guion escrito, la narración transcrita ES la base del guion
            (script_parts if not forced_script else context_parts).append(transcript)
        elif cat == "referencia":
            if kind == "image":
                frames.append(path)
            elif kind == "video":
                audio = extract_audio(path, input_dir / f"audio_ref_{asset['id']:02d}.mp3")
                stt = stt or get_stt(cfg)
                transcript = stt.transcribe(audio)
                context_parts.append(f"Transcripción del video de referencia:\n{transcript}")
                frames += extract_frames(path, input_dir / f"frames_{asset['id']:02d}",
                                         count=4)
            elif kind == "text":
                context_parts.append(extract_text(path).strip())
        # broll: no se analiza aquí — se usa directamente en el montaje

    raw_text = "\n\n".join(p for p in script_parts if p)
    broll_count = sum(1 for a in assets if a["category"] == "broll")

    system = (f"Eres un estratega de contenido de YouTube. Analizas el material de "
              f"entrada de un creador y produces un brief creativo en {lang}. "
              f"Responde en el JSON pedido.")
    prompt_parts = []
    if raw_text:
        prompt_parts.append(f"Material principal (guion o idea):\n<<<\n{raw_text}\n>>>")
    for ctx in context_parts:
        prompt_parts.append(f"Contexto adicional:\n<<<\n{ctx[:4000]}\n>>>")
    if frames:
        prompt_parts.append(
            "Analiza también las imágenes adjuntas (referencia visual o fotogramas "
            "del video de referencia) y extrae estilo, tema y elementos clave.")
    if broll_count:
        prompt_parts.append(
            f"El creador aporta {broll_count} archivos propios de B-roll que se "
            "usarán en el montaje.")
    if not prompt_parts:
        raise RuntimeError("El proyecto no tiene ningún material de entrada.")
    prompt_parts.append(
        "Devuelve: topic (tema del video), summary (brief creativo de 3-6 frases), "
        "key_points (5-10 puntos que debe cubrir el video) y detected_type "
        "('script' si el material principal ya es un guion completo listo para "
        "narrar, 'idea' en caso contrario).")

    analysis = llm.complete_json(system, "\n\n".join(prompt_parts),
                                 schema=ANALYSIS_SCHEMA, purpose="ingest_analysis")
    if forced_script:
        analysis["detected_type"] = "script"

    brief = {
        "input_type": analysis["detected_type"],
        "raw_text": raw_text,
        "reference_frames": [str(f) for f in frames],
        **analysis,
    }
    (input_dir / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    project.set("brief", brief)


# --- compat con la CLI (un solo archivo o texto) ---

def stage_input(project, source: Path | None, text: str | None, forced: str) -> dict:
    if text is not None:
        set_text_input(project, text)
        detected = "script" if len(text.split()) > 350 or forced == "script" else "idea"
        meta = {"type": detected, "file": "texto.txt"}
    else:
        category = {"script": "guion", "idea": "guion", "voice": "voz",
                    "image": "referencia", "video": "referencia",
                    "auto": "auto"}.get(forced, "auto")
        asset = add_asset(project, source, category)
        meta = {"type": asset["category"], "file": asset["file"]}
    project.set("input_meta", meta)
    return meta
