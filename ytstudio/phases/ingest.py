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

from ytstudio.progress import notify
from ytstudio.providers import get_llm, get_stt
from ytstudio.utils.extract import extract_text
from ytstudio.utils.media import extract_audio, extract_frames

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".wma"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
TEXT_EXT = {".txt", ".md"}
DOC_EXT = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls"}

CATEGORIES = ("guion", "voz", "broll", "referencia", "personaje", "reaccion")

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


def _describe_broll(project, llm, assets, input_dir, lang: str) -> None:
    """Describe con visión IA cada imagen/video de B-roll del usuario (1-2
    frases: contenido, ambiente, época). La descripción se guarda en el asset
    (cache: no se re-analiza al reanudar) y es la base para colocar cada
    material EXACTAMENTE en la escena del guion a la que corresponde."""
    pending = [a for a in assets if a["category"] == "broll"
               and a["kind"] in ("image", "video") and not a.get("description")]
    if not pending:
        return
    if getattr(llm, "is_mock", False):
        for a in pending:  # sin IA: el nombre del archivo como pista
            a["description"] = Path(a["name"]).stem.replace("-", " ").replace("_", " ")
        project.set("assets", assets)
        return

    schema = {
        "type": "object",
        "properties": {"descriptions": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "integer"},
                           "description": {"type": "string"}},
            "required": ["id", "description"], "additionalProperties": False,
        }}},
        "required": ["descriptions"], "additionalProperties": False,
    }
    for chunk_start in range(0, len(pending), 8):  # tandas de 8 assets
        chunk = pending[chunk_start:chunk_start + 8]
        images: list[Path] = []
        manifest: list[str] = []
        for a in chunk:
            path = input_dir / a["file"]
            try:
                if a["kind"] == "image":
                    images.append(path)
                    manifest.append(f"- id {a['id']}: imagen '{a['name']}' (1 imagen)")
                else:
                    fr = extract_frames(path, input_dir / f"bframes_{a['id']:02d}",
                                        count=2)
                    images += fr
                    manifest.append(f"- id {a['id']}: video '{a['name']}' "
                                    f"({len(fr)} fotogramas)")
            except Exception as e:
                project.add_warning(f"No se pudo analizar el B-roll "
                                    f"'{a['name']}': {e}")
        if not images:
            continue
        try:
            result = llm.complete_json(
                "Eres documentalista de archivo audiovisual. Describes material "
                f"de B-roll para poder colocarlo en el guion correcto. Responde en {lang}.",
                "Las imágenes adjuntas corresponden, EN ORDEN, a estos materiales:\n"
                + "\n".join(manifest) +
                "\n\nDescribe cada material (por su id) en 1-2 frases: qué se ve, "
                "ambiente/época, tono. Sé concreto: la descripción se usará para "
                "emparejarlo con la parte del guion que le corresponde.",
                schema=schema, images=images, purpose="broll_describe")
            got = {d["id"]: d["description"] for d in result["descriptions"]}
            for a in chunk:
                if got.get(a["id"]):
                    a["description"] = got[a["id"]].strip()[:400]
        except Exception as e:
            project.add_warning(f"Análisis con visión del B-roll no disponible "
                                f"(se usará reparto uniforme): {e}")
            return
    project.set("assets", assets)


def run(project, cfg) -> None:
    llm = get_llm(cfg)
    input_dir = project.path("input")
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)  # nombre completo del idioma para el LLM
    _migrate_legacy_input(project)
    assets = project.get("assets") or []
    stt = None

    script_parts: list[str] = []     # candidatos a guion (docs + texto pegado)
    context_parts: list[str] = []    # contexto adicional (transcripciones…)
    frames: list[Path] = []          # imágenes para análisis con visión
    voice_audios: list[Path] = []    # narración grabada por el usuario
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
            voice_audios.append(path)  # se procesan juntos más abajo
        elif cat == "voz" and kind == "video":
            # Nota de voz grabada en un contenedor de VIDEO (frecuente: los
            # grabadores del navegador y algunos celulares exportan audio-only
            # como .webm o .mp4). Antes esto se descartaba EN SILENCIO — el
            # narración quedaba vacía y el programa generaba guion y voz
            # propios sin avisar. Se extrae la pista de audio y se usa igual
            # que una narración normal.
            audio = extract_audio(path, input_dir / f"voz_audio_{asset['id']:02d}.mp3")
            voice_audios.append(audio)
        elif cat == "voz":
            project.add_warning(
                f"No se pudo usar «{asset['name']}» como tu narración (no se "
                "reconoce como audio ni video con audio) — el video se genera "
                "con guion y voz propios. Formatos válidos: mp3, wav, m4a, "
                "ogg, opus, flac, aac, wma, o un video con audio.")
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
        # broll: se describe con visión más abajo (para colocarlo por contexto)

    # --- Enlaces web de referencia (YouTube, Vimeo, Wistia, artículos…) ---
    # Con yt-dlp instalado se hace el análisis PROFUNDO: guion/transcripción,
    # ritmo de cortes, capítulos y fotogramas para visión. Sin yt-dlp (o si el
    # video no es descargable) se usan los metadatos públicos de la página.
    from ytstudio.utils import refvideo
    from ytstudio.utils.web import fetch_link_info, link_summary
    link_infos: list[dict] = []
    deep_ok = refvideo.available()
    for i, url in enumerate(project.get("links") or []):
        if deep_ok:
            ref_dir = input_dir / f"ref_{i:02d}"
            done = ref_dir / "analysis.json"
            try:
                if done.exists():  # cache al reanudar (no re-descargar)
                    analysis = json.loads(done.read_text(encoding="utf-8"))
                else:
                    stt = stt or get_stt(cfg)
                    analysis = refvideo.analyze_reference_video(
                        url, ref_dir, cfg, stt=stt)
                link_infos.append(analysis)
                context_parts.append(
                    "ANÁLISIS COMPLETO DEL VIDEO DE REFERENCIA (replica su "
                    "fórmula: estructura, gancho, ritmo, tono y estilo — "
                    "adaptándola al tema nuevo, sin copiar frases):\n"
                    + refvideo.analysis_summary(analysis))
                frames += [Path(f) for f in analysis.get("frames", [])
                           if Path(f).exists()][:6]
                continue
            except Exception as e:
                project.add_warning(
                    f"No se pudo descargar el video de referencia ({url}) — "
                    f"se usan solo sus metadatos públicos. {e}")
        info = fetch_link_info(url)
        link_infos.append(info)
        if info.get("error"):
            project.add_warning(f"Enlace de referencia no accesible ({url}): "
                                f"{info['error']}")
        else:
            context_parts.append("Video/página de referencia (analiza su "
                                 "estilo, fórmula y tema para replicarlos):\n"
                                 + link_summary(info))
    if (project.get("links")) and not deep_ok:
        project.add_warning(
            "Análisis profundo de videos de referencia desactivado: instala "
            "yt-dlp (ejecuta actualizar.bat o «py -m pip install yt-dlp») para "
            "analizar guion, ritmo de cortes y estilo del video enlazado.")

    # --- B-roll propio: descripción con visión para asignarlo por contexto ---
    if any(a["category"] == "broll" and a["kind"] in ("image", "video")
           and not a.get("description") for a in assets):
        notify("👁 Analizando tu material de B-roll con visión IA…")
    _describe_broll(project, llm, assets, input_dir, lang)

    # --- Narración grabada por el usuario: limpiar + transcribir con tiempos ---
    project.set("narration", None)
    voz_assets = [a for a in assets if a["category"] == "voz"]
    if voz_assets and not voice_audios:
        # Red de seguridad: hay material marcado como "tu voz" pero ninguno se
        # pudo aprovechar (los avisos de arriba explican por qué asset a
        # asset) — que quede clarísimo que el video usará voz sintética, en
        # vez de fallar en silencio.
        project.add_warning(
            "Ninguno de tus archivos de voz se pudo usar como narración — "
            "revisa los avisos anteriores. El video se genera con guion y "
            "voz sintética (IA) en su lugar.")
    if voice_audios:
        from ytstudio.utils.media import clean_narration, concat_audios
        trim = cfg.get("audio", {}).get("trim_silence", True)
        keep = cfg.get("audio", {}).get("silence_keep", 0.4)
        raw = concat_audios(voice_audios, input_dir / "narration_raw.mp3")
        clean = clean_narration(raw, input_dir / "narration_clean.mp3",
                                trim_silence=trim, keep=keep,
                                lufs=cfg.get("audio", {}).get("vo_lufs", -16))
        stt = stt or get_stt(cfg)
        if getattr(stt, "is_mock", False):
            # Sin clave de transcripción real (OPENAI_API_KEY / proveedor STT
            # en ⚙ Configuración) el "mock" NO transcribe tu voz: rellena un
            # texto de muestra genérico sincronizado con la duración de tu
            # audio. El AUDIO que suena sí es el tuyo, pero el GUION y los
            # subtítulos serían de relleno — hay que dejarlo clarísimo.
            project.add_warning(
                "No hay un proveedor de transcripción real configurado (STT) "
                "— tu grabación se usará como audio, pero el guion y los "
                "subtítulos serán de MUESTRA, no lo que realmente dijiste. "
                "Configura tu clave de OpenAI en ⚙ Configuración para "
                "transcribir tu voz de verdad.")
        segments = stt.transcribe_segments(clean)
        # La sincronía fina de subtítulos/rótulos con la voz REAL se corrige
        # en LAZO CERRADO al generar los subtítulos (se mide sobre el
        # resultado y se corrige con esa medición) — corregir aquí los
        # tiempos de Whisper resultó frágil: el emparejamiento con
        # respiraciones sesgaba la mediana (±380ms entre corridas iguales).
        if not segments:
            # Sin segmentos no hay dónde anclar las escenas — si esto pasara
            # en silencio, el video caería de nuevo a guion y voz sintética
            # SIN avisar (el mismo fallo silencioso de arriba).
            project.add_warning(
                "No se detectó voz en tu grabación (revisa que el archivo "
                "no esté vacío o silenciado) — el video se genera con guion "
                "y voz sintética (IA) en su lugar.")
        (input_dir / "narracion.txt").write_text(
            " ".join(s["text"] for s in segments), encoding="utf-8")
        project.set("narration", {"file": clean.name, "segments": segments})
        # La narración transcrita es la base del guion (salvo que haya guion escrito)
        if not forced_script:
            script_parts.insert(0, " ".join(s["text"] for s in segments))
            forced_script = True   # se respeta como guion definitivo

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
        descs = [f"- {a['name']}: {a.get('description', 'sin describir')}"
                 for a in assets if a["category"] == "broll"]
        prompt_parts.append(
            f"El creador aporta {broll_count} archivos propios de B-roll que se "
            "usarán en el montaje:\n" + "\n".join(descs))
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

    # En el brief los enlaces van compactos (la transcripción completa queda
    # en 01_input/ref_XX/analysis.json): el brief viaja en varios prompts.
    brief_links = []
    for li in link_infos:
        c = {k: v for k, v in li.items() if k not in ("transcript", "frames")}
        if li.get("transcript"):
            c["transcript_excerpt"] = li["transcript"][:1200]
        brief_links.append(c)

    brief = {
        "input_type": analysis["detected_type"],
        "raw_text": raw_text,
        "reference_frames": [str(f) for f in frames],
        "links": brief_links,
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
