"""FASE 6 — B-roll: asigna primero los archivos propios del creador
(categoría 'broll') repartidos uniformemente entre las escenas y genera con
IA la imagen (o clip) de las escenas restantes."""
from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path

from ytstudio import prompt_safety as ps
from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_images, get_llm, get_videogen
from ytstudio.utils.media import run_ffmpeg


# OBJETOS ESCRITOS que aparecen en un prompt de B-roll. Si la escena muestra
# uno, en pantalla se va a leer algo — y ese algo tiene que ser LEGIBLE: es el
# estándar de calidad del programa. Estas escenas se rutean al modelo con
# mejor tipografía aunque el director no haya declarado image_text.
_TEXT_PROPS = (
    "newspaper|newsprint|front page|headline|tabloid|gazette|press clipping|"
    "sign|signage|signboard|storefront|shop window|marquee|billboard|poster|"
    "placard|banner|plaque|inscription|engraving|epitaph|gravestone|"
    "tombstone|headstone|document|documents|letter|letters|envelope|telegram|"
    "manuscript|scroll|parchment|papyrus|contract|certificate|diploma|ledger|"
    "logbook|register|diary|journal entry|book cover|title page|open book|"
    "map legend|chart|graph|diagram|blackboard|chalkboard|whiteboard|"
    "notice|notice board|leaflet|pamphlet|flyer|label|price tag|nameplate|"
    "screen showing|computer screen|display showing|ticker|stock ticker|"
    "typewriter page|printed page|handwritten note|note pinned|"
    "wanted poster|propaganda poster|street name|road sign|shop sign"
)
# Con fronteras de palabra («design» no es un letrero, «resigned» tampoco) y
# admitiendo el plural («newspapers», «signs»).
_TEXT_PROPS_RE = re.compile(rf"\b(?:{_TEXT_PROPS})s?\b", re.I)
# La receta ANTERIOR pedía texto ilegible a propósito («out of focus,
# unreadable print»). Producía justo lo que el creador ve como defecto:
# garabatos. Se desactiva allá donde aparezca.
_ILLEGIBLE_RE = re.compile(
    r"(?:\b(?:blurred|blurry|out of focus|defocused|smudged|indistinct|"
    r"illegible|unreadable|unintelligible|scribbled|faux|fake|invented|"
    r"nonsense|gibberish|abstract)\b[\s,]*)+"
    r"\b(?:text|print|lettering|letters|writing|handwriting|type|typography|"
    r"words|headline|script|characters)\b",
    re.I)


def _shows_text(scene: dict) -> bool:
    """¿En esta escena se va a leer algo? Por declaración del director
    (image_text) o porque su prompt describe un objeto escrito."""
    if (scene.get("image_text") or "").strip():
        return True
    prompt = " ".join(filter(None, (scene.get("broll_prompt"),
                                    scene.get("broll_prompt_b"))))
    return bool(_TEXT_PROPS_RE.search(prompt))


def _drop_illegible(prompt: str) -> str:
    """Da la vuelta a las peticiones de texto ilegible/borroso del prompt: en
    su lugar se pide texto NÍTIDO Y LEGIBLE (sustituir, y no solo borrar,
    deja la frase bien construida y empuja al generador en la dirección
    correcta)."""
    out = _ILLEGIBLE_RE.sub("sharp legible text", prompt or "")
    return re.sub(r"\s{2,}", " ", out).strip(" ,;")


def _user_broll_assets(project) -> list[dict]:
    return [a for a in (project.get("assets") or [])
            if a["category"] == "broll" and a["kind"] in ("image", "video")]


def _detect_green_screen(video: Path, work_dir: Path) -> bool:
    """¿El video se grabó sobre PANTALLA VERDE? Se extrae un fotograma y se
    muestrean los BORDES (donde en una grabación de reacción está el fondo,
    no la persona): si una fracción clara es verde saturado, es chroma.
    Determinista y local — el usuario no tiene que configurar nada."""
    try:
        from PIL import Image
        frame = work_dir / "reaccion_probe.jpg"
        run_ffmpeg(["-ss", "0.5", "-i", str(video), "-frames:v", "1",
                    "-q:v", "3", str(frame)], "fotograma de reacción")
        img = Image.open(frame).convert("RGB")
        w, h = img.size
        px = img.load()
        band_w, band_h = max(2, w // 10), max(2, h // 10)
        samples, green = 0, 0
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                if x > band_w and x < w - band_w and y > band_h:
                    continue  # solo bordes laterales y superior
                r, g, b = px[x, y]
                samples += 1
                if g > 90 and g > r * 1.35 and g > b * 1.35:
                    green += 1
        frame.unlink(missing_ok=True)
        return samples > 0 and green / samples > 0.30
    except Exception:
        return False


def _setup_reaction(project, broll_dir: Path) -> None:
    """VIDEO DE REACCIÓN (categoría 🎭 Reacción): la persona que reacciona se
    compone SOBRE el contenido durante todo el video — con chroma key si se
    grabó en pantalla verde (detectado automáticamente) o en una burbuja
    circular si no. Aquí solo se registra y clasifica; la composición con el
    desfase exacto de cada escena la hace el montaje."""
    from ytstudio.progress import notify
    videos = [a for a in (project.get("assets") or [])
              if a.get("category") == "reaccion" and a.get("kind") == "video"]
    if not videos:
        if project.get("reaction"):
            project.set("reaction", None)  # se quitó el archivo → sin overlay
        return
    asset = videos[-1]  # el más reciente manda
    src = project.path("input", asset["file"])
    chroma = _detect_green_screen(src, broll_dir)
    project.set("reaction", {"file": asset["file"], "chroma": chroma})
    notify("🎭 Video de reacción detectado: se compone sobre el contenido "
           + ("recortando la PANTALLA VERDE (chroma key)." if chroma else
              "en una burbuja circular (no se detectó pantalla verde)."))


def _bind_worker_logging(sink) -> None:
    """Los generadores corren en hilos TRABAJADORES, que no heredan el canal
    de avisos (thread-local) del hilo de la fase: cada worker lo re-vincula
    aquí para que sus mensajes (reintentos de red, esperas de Replicate…)
    lleguen al log de la UI en vez de perderse en stdout."""
    if sink is None:
        return
    from ytstudio import progress
    from ytstudio.providers import replicate_util
    progress.set_sink(sink)
    replicate_util.set_progress(sink)


def _is_content_error(e: Exception) -> bool:
    """¿El fallo es un rechazo de CONTENIDO del generador (no infraestructura)?
    Esos degradan solo la escena; auth/red/rate detienen la fase."""
    m = str(e).lower()
    return any(k in m for k in ("nsfw", "safety", "flagged", "sensitive",
                                "content policy", "not allowed",
                                "e005", "moderat"))


# El suavizado de prompts rechazados vive en ytstudio/prompt_safety.py:
# el que había aquí sustituía «dead»→«ancient» y «wound»→«mark», es decir,
# deshacía la fidelidad factual que el director acababa de fijar.


def _neighbor_blur(out: Path, broll_dir: Path, sid: int, cfg: dict) -> bool:
    """Respaldo SIN COSTO para una escena rechazada: la imagen de la escena
    vecina más cercana, muy desenfocada y oscurecida — mantiene la atmósfera
    y la paleta del video en vez de un degradado que se ve «vacío»."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        w, h = cfg["video"]["width"], cfg["video"]["height"]
        for d in (1, -1, 2, -2, 3, -3, 4, -4):
            p = broll_dir / f"scene_{sid + d:03d}.jpg"
            if not p.exists():
                continue
            img = Image.open(p).convert("RGB")
            scale = max(w / img.width, h / img.height)
            img = img.resize((round(img.width * scale),
                              round(img.height * scale)))
            x, y = (img.width - w) // 2, (img.height - h) // 2
            img = img.crop((x, y, x + w, y + h))
            img = img.filter(ImageFilter.GaussianBlur(radius=max(10, w // 55)))
            img = ImageEnhance.Brightness(img).enhance(0.5)
            img.save(out, quality=88)
            return True
    except Exception:
        pass
    return False


def _fallback_image(out: Path, cfg: dict, palette: list[str],
                    broll_dir: Path | None = None,
                    scene_id: int | None = None) -> Path:
    """Fondo cinematográfico para una escena cuya imagen fue rechazada: la
    escena vecina desenfocada (misma atmósfera) o, si no hay ninguna, un
    degradado oscuro con la paleta del video. Se ve como un plano
    atmosférico, no como un error."""
    if broll_dir is not None and scene_id is not None:
        if _neighbor_blur(out, broll_dir, scene_id, cfg):
            return out
    w, h = cfg["video"]["width"], cfg["video"]["height"]

    def _rgb(hexa, default):
        try:
            s = str(hexa).lstrip("#")
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except Exception:
            return default

    top = _rgb(palette[0] if palette else None, (28, 32, 46))
    bottom = _rgb(palette[-1] if len(palette) > 1 else None, (8, 9, 14))
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            draw.line([(0, y), (w, y)],
                      fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        img.save(out, quality=90)
    except Exception:
        # sin PIL: degradado con ffmpeg
        c1 = "0x%02x%02x%02x" % top
        run_ffmpeg(["-f", "lavfi", "-i",
                    f"gradients=s={w}x{h}:c0={c1}:c1=0x08090e:x0=0:y0=0:"
                    f"x1=0:y1={h}", "-frames:v", "1", "-q:v", "3", str(out)],
                   "fondo neutro")
    return out


def _spread(n_assets: int, n_scenes: int) -> dict[int, int]:
    """Reparte n_assets entre n_scenes de forma uniforme.
    Devuelve {índice_escena: índice_asset}."""
    if not n_assets or not n_scenes:
        return {}
    count = min(n_assets, n_scenes)
    positions = [round(i * (n_scenes - 1) / max(1, count - 1)) if count > 1 else 0
                 for i in range(count)]
    mapping, used = {}, set()
    for asset_idx, pos in enumerate(positions):
        while pos in used and pos < n_scenes - 1:
            pos += 1
        if pos not in used:
            mapping[pos] = asset_idx
            used.add(pos)
    return mapping


def _numbered_map(scenes: list[dict], assets: list[dict]) -> dict[int, int]:
    """Asignación DETERMINISTA por número de archivo: si un B-roll se llama
    scene_003.mp4, 03_batalla.jpg, (3).png, etc. y existe la escena 3, va a
    ESA escena — el orden que el creador indicó con el nombre manda (es
    típico reutilizar material exportado de un proyecto anterior, que ya
    viene numerado por escena). Cero tokens y cero sorpresas. Los archivos
    sin número (o con número sin escena) pasan al reparto semántico."""
    import re
    ids = {s["id"] for s in scenes}
    idx_by_id = {s["id"]: i for i, s in enumerate(scenes)}
    mapping: dict[int, int] = {}
    for ai, a in enumerate(assets):
        stem = Path(a.get("name") or a["file"]).stem
        m = (re.search(r"(?:escena|scene)[\s_-]*(\d{1,3})", stem, re.I)
             or re.match(r"^\(?(\d{1,3})\)?(?:[\s_.-]|$)", stem))
        if not m:
            continue
        sid = int(m.group(1))
        if sid in ids and idx_by_id[sid] not in mapping:
            mapping[idx_by_id[sid]] = ai
    return mapping


def _semantic_map(llm, scenes: list[dict], assets: list[dict],
                  lang: str) -> dict[int, int]:
    """Asigna cada B-roll del usuario a la escena cuya narración ilustra,
    usando las descripciones de visión de la ingesta. Devuelve
    {índice_escena: índice_asset}. Un asset por escena; el material que no
    encaja en ninguna parte no se fuerza (mejor generar que descolocar)."""
    listing = "\n".join(
        f"- asset {i}: [{a['kind']}] «{a['name']}» — "
        f"{a.get('description') or 'sin descripción'}"
        for i, a in enumerate(assets))
    scenes_txt = "\n".join(f"[escena {i}] ({s.get('section', '')}) "
                           f"{s['narration']}" for i, s in enumerate(scenes))
    schema = {
        "type": "object",
        "properties": {"assignments": {"type": "array", "items": {
            "type": "object",
            "properties": {"asset": {"type": "integer"},
                           "scene": {"type": "integer"}},
            "required": ["asset", "scene"], "additionalProperties": False,
        }}},
        "required": ["assignments"], "additionalProperties": False,
    }
    result = llm.complete_json(
        f"Eres editor senior de documentales en {lang}. Colocas el material de "
        "archivo del creador exactamente donde el guion lo pide.",
        "MATERIAL DEL CREADOR (B-roll propio):\n" + listing +
        "\n\nESCENAS DEL VIDEO (con su narración):\n" + scenes_txt +
        "\n\nAsigna cada asset a la escena cuyo contenido ILUSTRA lo que se "
        "narra en ella (tema, personaje, lugar, época, acción). Reglas:\n"
        "- Máximo un asset por escena.\n"
        "- scene = -1 si el asset no encaja de verdad en ninguna escena "
        "(mejor generar imagen nueva que colocar material fuera de contexto).\n"
        "- Prioriza los emparejamientos más claros.",
        schema=schema, max_tokens=32000, purpose="broll_semantic")
    mapping: dict[int, int] = {}
    used_assets: set[int] = set()
    for pair in result["assignments"]:
        ai, si = pair["asset"], pair["scene"]
        if (0 <= ai < len(assets) and 0 <= si < len(scenes)
                and si not in mapping and ai not in used_assets):
            mapping[si] = ai
            used_assets.add(ai)
    return mapping


def _copy_fresh(src: Path, dest: Path) -> bool:
    """Copia src→dest salvo que dest ya sea la MISMA copia (mismo tamaño).
    Un simple `if not dest.exists()` dejaba pegado material viejo cuando el
    archivo fuente cambió con el mismo nombre. Devuelve True si copió."""
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        return False
    shutil.copy(src, dest)
    return True


def _assign_user_asset(scene: dict, asset: dict, project, broll_dir: Path) -> None:
    src = project.path("input", asset["file"])
    if asset["kind"] == "image":
        dest = broll_dir / f"scene_{scene['id']:03d}{Path(asset['file']).suffix}"
        _copy_fresh(src, dest)
        scene["broll_image"] = dest.name
        scene.pop("broll_video", None)
    else:  # video propio: clip + fotograma para miniatura/respaldo
        clip = broll_dir / f"scene_{scene['id']:03d}{Path(asset['file']).suffix}"
        copied = _copy_fresh(src, clip)
        frame = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if copied or not frame.exists():
            run_ffmpeg(["-i", str(clip), "-frames:v", "1", "-q:v", "3",
                        str(frame)], "fotograma b-roll propio")
        scene["broll_video"] = clip.name
        scene["broll_image"] = frame.name
    scene["broll_source"] = "user"


def _place_manual_broll(project, scenes: list[dict], broll_dir: Path,
                        cfg: dict) -> set[int]:
    """Coloca el B-roll que subiste a mano a escenas CONCRETAS (pestaña
    Storyboard). Máxima prioridad: gana sobre el reparto semántico y sobre la
    generación IA. Respeta el tipo que decidió el director — una escena de
    video acepta video (ideal) o imagen (se degrada a Ken Burns, con aviso);
    una de imagen solo acepta imagen. Devuelve los ids con material manual.

    Los archivos se referencian DENTRO de 06_broll/manual/ (no se copian a la
    raíz): no chocan con el material IA ni con la caché por firma."""
    manual = project.get("manual_broll") or {}
    if not manual:
        return set()
    from ytstudio.progress import notify
    placed: set[int] = set()
    downgraded: list[int] = []
    by_id = {s["id"]: s for s in scenes}
    for sid_str, info in manual.items():
        scene = by_id.get(int(sid_str))
        src = broll_dir / "manual" / info["file"]
        if scene is None or not src.exists():
            continue
        if info["kind"] == "image":
            scene["broll_image"] = f"manual/{info['file']}"
            scene.pop("broll_video", None)
            if scene.get("broll_type") == "video":
                scene["broll_type"] = "image"
                downgraded.append(scene["id"])
        else:  # video propio: se necesita un fotograma para revisión/miniatura
            frame = broll_dir / "manual" / f"{Path(info['file']).stem}_frame.jpg"
            if not frame.exists():
                run_ffmpeg(["-i", str(src), "-frames:v", "1", "-q:v", "3",
                            str(frame)], "fotograma b-roll manual")
            scene["broll_video"] = f"manual/{info['file']}"
            scene["broll_image"] = f"manual/{frame.name}"
            scene["broll_type"] = "video"
        scene["broll_source"] = "manual"
        placed.add(scene["id"])
    if downgraded:
        notify(f"ℹ Subiste una imagen a {len(downgraded)} escena(s) que el "
               f"director planeó como video ({', '.join(map(str, downgraded))}): "
               "se usan como imagen con movimiento (Ken Burns).")
    return placed


def _review_manual_broll(project, llm, scenes: list[dict], placed: set[int],
                         broll_dir: Path, cfg: dict) -> None:
    """El director REVISA con visión cada B-roll que subiste y juzga si de
    verdad ilustra lo que se narra en esa escena. Guarda su veredicto (encaja
    sí/no + motivo) para mostrártelo. Si activaste «el director reemplaza lo
    que no encaje», los que no encajan se descartan y se generan con IA (se te
    notifica el motivo). Si no, se respeta SIEMPRE tu elección y solo se avisa.

    Solo se revisa lo que cambió desde la última vez (no re-gasta tokens)."""
    if not placed:
        return
    from ytstudio.progress import notify
    # Revisión configurable: se puede desactivar para ahorrar tokens (no se
    # gasta nada de visión IA; tu B-roll se usa tal cual, sin veredicto).
    if project.get("broll_review") is False:
        notify("👁 Revisión del director desactivada: tu B-roll se usa tal "
               "cual (ahorro de tokens).")
        return
    manual = project.get("manual_broll") or {}
    auto_replace = bool(project.get("broll_auto_replace"))
    lang = cfg.get("language", "es")
    by_id = {s["id"]: s for s in scenes}

    def sig(info):
        return f"{info.get('file')}:{info.get('size')}"

    pending = [sid for sid in placed
               if manual.get(str(sid), {}).get("reviewed_sig") != sig(manual.get(str(sid), {}))
               or "review" not in manual.get(str(sid), {})]
    if not pending:
        return

    if getattr(llm, "is_mock", False):
        for sid in pending:
            info = manual.get(str(sid), {})
            info["review"] = {"fits": True,
                              "reason": "sin revisión (modo vista previa)"}
            info["reviewed_sig"] = sig(info)
        project.set("manual_broll", manual)
        return

    notify(f"👁 El director revisa {len(pending)} B-roll(s) que subiste…")
    schema = {
        "type": "object",
        "properties": {"reviews": {"type": "array", "items": {
            "type": "object",
            "properties": {"scene": {"type": "integer"},
                           "fits": {"type": "boolean"},
                           "reason": {"type": "string"}},
            "required": ["scene", "fits", "reason"],
            "additionalProperties": False}}},
        "required": ["reviews"], "additionalProperties": False}
    replaced: list[tuple[int, str]] = []
    for start in range(0, len(pending), 6):
        chunk = pending[start:start + 6]
        images: list[Path] = []
        manifest: list[str] = []
        order: list[int] = []
        for sid in chunk:
            frame = broll_dir / (by_id[sid].get("broll_image") or "")
            if not frame.exists():
                continue
            images.append(frame)
            manifest.append(f"- escena {sid}: narración «{by_id[sid]['narration'][:220]}»")
            order.append(sid)
        if not images:
            continue
        try:
            result = llm.complete_json(
                f"Eres editor senior de documentales en {lang}. Juzgas si una "
                "imagen de B-roll ilustra de verdad lo que se narra en su "
                "escena (tema, personaje, lugar, época, acción). Eres exigente "
                "pero justo: una imagen atmosférica coherente SÍ encaja; una "
                "que contradice o nada tiene que ver, NO.",
                "Las imágenes adjuntas corresponden, EN ORDEN, a estas "
                "escenas:\n" + "\n".join(manifest) +
                "\n\nPara cada escena (por su número) di fits=true si la imagen "
                "ilustra bien su narración, false si no; reason: una frase "
                "concreta explicando por qué.",
                schema=schema, images=images, purpose="broll_review")
        except Exception as e:
            project.add_warning(f"No se pudo revisar el B-roll subido "
                                f"({e}) — se respeta tu elección sin cambios.")
            return
        verdicts = {r["scene"]: r for r in result.get("reviews", [])}
        for sid in order:
            v = verdicts.get(sid)
            info = manual.get(str(sid), {})
            if not v:
                info["review"] = {"fits": True, "reason": "no evaluada"}
                info["reviewed_sig"] = sig(info)
                continue
            info["review"] = {"fits": bool(v["fits"]),
                              "reason": v.get("reason", "")}
            info["reviewed_sig"] = sig(info)
            if v["fits"]:
                continue
            if auto_replace:
                # Descartar tu material y dejar que la IA genere esa escena.
                (broll_dir / "manual" / info["file"]).unlink(missing_ok=True)
                fr = broll_dir / "manual" / f"{Path(info['file']).stem}_frame.jpg"
                fr.unlink(missing_ok=True)
                reason = info.get("review", {}).get("reason", "")
                manual.pop(str(sid), None)
                s = by_id[sid]
                s["broll_source"] = None
                s.pop("broll_video", None)
                s.pop("broll_image", None)
                placed.discard(sid)
                replaced.append((sid, reason))
            else:
                project.add_warning(
                    f"El director revisó tu B-roll de la escena {sid} y cree "
                    f"que NO ilustra bien lo que se narra: {v.get('reason', '')} "
                    "Se respeta tu elección; quítalo en Storyboard si prefieres "
                    "que se genere automáticamente.")
    project.set("manual_broll", manual)
    for sid, reason in replaced:
        project.add_warning(
            f"El director reemplazó por IA tu B-roll de la escena {sid} (no "
            f"encajaba): {reason}".strip())
    if replaced:
        ids = ", ".join(str(sid) for sid, _ in replaced)
        notify(f"🔄 El director generará con IA {len(replaced)} escena(s) cuyo "
               f"B-roll no encajaba ({ids}).")


_QA_SCHEMA = {
    "type": "object",
    "properties": {"reviews": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "scene": {"type": "integer"},
            "fiel": {"type": "boolean"},
            "problema": {"type": "string"},
            "prompt_corregido": {"type": "string"},
        },
        "required": ["scene", "fiel", "problema", "prompt_corregido"],
        "additionalProperties": False}}},
    "required": ["reviews"], "additionalProperties": False}


def _qa_frame(scene: dict, broll_dir: Path) -> Path | None:
    """Qué imagen se revisa de esta escena.

    Para las escenas de IMAGEN, la propia imagen. Para las de CLIP DE VIDEO,
    un fotograma del INTERIOR del clip: la imagen inicial ya se verificó, pero
    el generador de video se aleja de ella al animar — un animal que la
    narración da por muerto puede acabar moviéndose. Ese fotograma se guarda
    para no re-extraerlo al reanudar."""
    still = broll_dir / f"scene_{scene['id']:03d}.jpg"
    clip_name = scene.get("broll_video")
    if not clip_name:
        return still if still.exists() else None
    clip = broll_dir / clip_name
    if not clip.exists():
        return still if still.exists() else None
    mid = broll_dir / "qa" / f"scene_{scene['id']:03d}_mid.jpg"
    if mid.exists():
        return mid
    mid.parent.mkdir(parents=True, exist_ok=True)
    try:
        from ytstudio.utils.media import probe_duration
        t = max(0.1, probe_duration(clip) * 0.6)
        run_ffmpeg(["-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                    "-q:v", "3", str(mid)], f"fotograma QA escena {scene['id']}")
        return mid if mid.exists() else (still if still.exists() else None)
    except Exception:
        return still if still.exists() else None


def _qa_batches(llm, cfg, targets: list[dict], broll_dir: Path,
                project) -> dict[int, dict] | None:
    """Pasa las imágenes por visión en tandas y devuelve {id: veredicto}.
    Devuelve None si alguna tanda FALLÓ: sin veredictos completos no se puede
    afirmar nada (v0.42.0 decía «todas las imágenes respetan lo narrado»
    justo después de que la llamada de visión fallara con un 400)."""
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)
    verdicts: dict[int, dict] = {}
    system = (
        f"Eres el director de fotografía que hace CONTROL DE CALIDAD de un "
        f"documental en {lang}. Comparas cada imagen generada con los HECHOS "
        "CONCRETOS que afirma la narración de su escena. Solo te importan "
        "las CONTRADICCIONES de hechos: estado (vivo/muerto), especie y "
        "anatomía del sujeto, número exacto y disposición de elementos, "
        "ubicación exacta de heridas o marcas, el objeto clave narrado. Una "
        "ilustración parcial o atmosférica NO es infiel; una que CONTRADICE "
        "lo narrado, SÍ. Y vigilas un defecto de acabado que arruina la "
        "calidad: el TEXTO INVENTADO — letras deformes o palabras sin "
        "sentido en periódicos, carteles, documentos o rótulos.")
    jobs: list[tuple[list[Path], str]] = []
    for start in range(0, len(targets), 6):
        chunk = targets[start:start + 6]
        images, manifest = [], []
        for s in chunk:
            p = _qa_frame(s, broll_dir)
            if p is None or not p.exists():
                continue
            images.append(p)
            # Los CLIPS se revisan por un fotograma de su INTERIOR: el
            # generador de video puede alejarse de la imagen inicial (que sí
            # se verificó) y, por ejemplo, poner en movimiento a un animal
            # que la narración da por muerto.
            marca = " [FOTOGRAMA INTERIOR DE UN CLIP EN MOVIMIENTO]" \
                if s.get("broll_video") else ""
            manifest.append(f"- escena {s['id']}{marca}: narración «"
                            f"{(s.get('narration') or '')[:280]}»")
        if not images:
            continue
        prompt = (
            "Las imágenes adjuntas corresponden, EN ORDEN, a estas "
            "escenas:\n" + "\n".join(manifest) +
            "\n\nPara cada escena (por su número):\n"
            "- fiel=false SOLO si la imagen CONTRADICE un hecho concreto de "
            "su narración (animales vivos donde se narran muertos, anatomía "
            "humana donde el sujeto es un animal, otra cantidad o "
            "disposición que la narrada, una herida en otra parte del "
            "cuerpo). Ante la duda, fiel=true.\n"
            "- En los marcados como FOTOGRAMA INTERIOR DE UN CLIP: revisa "
            "además que el MOVIMIENTO no contradiga lo narrado (un sujeto que "
            "la narración da por muerto no puede aparecer moviéndose, de pie "
            "o con los ojos abiertos).\n"
            "- fiel=false TAMBIÉN si en la imagen se lee TEXTO INVENTADO: "
            "letras deformes, palabras sin sentido o un idioma equivocado en "
            "un periódico, cartel, documento, lápida o rótulo. Un texto "
            "correcto y legible está BIEN; un texto tan pequeño o lejano que "
            "no se distingue como escritura, también.\n"
            "- problema: una frase concreta con el hecho contradicho o con el "
            "texto ilegible (vacía si fiel).\n"
            "- prompt_corregido: SOLO si fiel=false — el prompt completo EN "
            "INGLÉS para regenerar la imagen, manteniendo el estilo del "
            "original pero codificando los hechos de forma REDUNDANTE e "
            "inequívoca (número exacto repetido, especie en cada mención, "
            "estado sin vida explícito, ubicación exacta). Si el problema era "
            "el texto: o pides el texto EXACTO y legible que debe leerse "
            f"(en {lang}, bien escrito), o reencuadras para que ese objeto "
            "escrito no salga — nunca 'blurred/unreadable text'. Vacío si "
            "fiel.")
        jobs.append((images, prompt))
    if not jobs:
        return verdicts

    # En PARALELO (2 a la vez): en un video de 84 escenas son ~14 tandas de
    # visión — en serie añadían 7-14 minutos a la fase. Los hilos re-vinculan
    # el acumulador de gasto y el canal de avisos, como el resto de la fase.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from ytstudio import usage as usage_mod
    from ytstudio.progress import get_sink
    usage_items = usage_mod.get_state()
    sink = get_sink()

    def _review(job):
        usage_mod.bind(usage_items)
        _bind_worker_logging(sink)
        images, prompt = job
        return llm.complete_json(system, prompt, schema=_QA_SCHEMA,
                                 images=images, purpose="broll_qa")

    failed: Exception | None = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_review, j) for j in jobs]
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as e:
                failed = failed or e
                continue
            for r in result.get("reviews", []):
                verdicts[int(r.get("scene", -1))] = r
    if failed is not None:
        project.add_warning(f"El control de calidad factual con visión "
                            f"no se pudo completar ({failed}) — las imágenes "
                            "quedan como salieron.")
        return None
    return verdicts


def _resolve_elements(project, cfg, scenes: list[dict], broll_dir: Path,
                      images=None) -> None:
    """Materializa los ELEMENTOS de archivo planificados por el documentalista:
    banco local del creador → foto libre de Wikimedia (con atribución que va
    sola a la descripción) → tarjeta generada en local (cifras y fechas, $0).
    Todo es un ADORNO: cualquier fallo quita ese elemento y sigue — jamás
    detiene la fase ni cuesta reintentos."""
    targets = [(s, el) for s in scenes for el in (s.get("elements") or [])]
    if not targets:
        return
    from ytstudio.progress import notify
    from ytstudio.utils import elements as elib
    from ytstudio.utils import maps as mapslib
    eldir = broll_dir / "elements"
    eldir.mkdir(exist_ok=True)
    card_w = int(min(cfg["video"]["width"], cfg["video"]["height"]) * 0.34)
    accent = str(cfg["video"].get("overlay_accent", "E8C46B"))
    lang_code = cfg.get("language", "es")
    permitir_web = cfg["video"].get("elements_web", True)
    notify(f"📎 Material de archivo: preparando {len(targets)} inserto(s) "
           "(banco propio → Wikimedia con licencia libre → generado local)…")
    credits: set[str] = set()
    sin_fuente: list[str] = []
    ilustradas: list[str] = []
    mapas: list[str] = []          # sin cartografía real: cayeron a imagen
    concept = project.get("concept") or {}
    prefix_ai = ((concept.get("visual_style") or {}).get("prompt_prefix")
                 or "cinematic documentary still")
    if images is None or getattr(images, "is_mock", False):
        cfg = {**cfg, "video": {**cfg["video"], "elements_ai": False}}

    # Presupuesto de ilustraciones IA: los insertos se resuelven en PARALELO,
    # así que la reserva tiene que ser atómica — comprobar y restar por
    # separado dejaba que tres hilos pasaran el mismo control y se generara
    # (y pagara) más de lo autorizado.
    ai_budget = [int(cfg["video"].get("elements_ai_max", 3))
                 if cfg["video"].get("elements_ai", False) else 0]
    ai_lock = threading.Lock()

    def _reservar_ia() -> bool:
        with ai_lock:
            if ai_budget[0] <= 0:
                return False
            ai_budget[0] -= 1
            return True

    def _foto_insert(s, el, consulta: str, *, ai_prompt: str | None = None,
                     categorias=elib.CATEGORIES, motivo: str = "") -> bool:
        """Tarjeta de ARCHIVO para una mención: banco propio → foto libre de
        Wikimedia → ilustración IA (si el creador la autorizó). Devuelve si se
        resolvió; el que no se resuelve sale del plan (mejor nada que un
        adorno vacío)."""
        sid = s["id"]
        src = elib.bank_lookup(consulta, categorias)
        # CLIP DE VIDEO del banco: se copia al proyecto y se compone como
        # inserto en movimiento (el montaje lo escala y enmarca).
        if src is not None and elib.is_video(src):
            clip = eldir / f"clip_{sid:03d}{src.suffix.lower()}"
            shutil.copyfile(src, clip)
            el["files"] = [clip.name]
            el["mode"] = "video"
            return True
        credit = None
        if src is None and permitir_web:
            got = elib.wiki_photo(consulta, lang_code, eldir)
            if got:
                src, credit = got["file"], got["credit"]
        if src is None and _reservar_ia():
            # ÚLTIMO recurso, y solo si el creador lo autorizó: una
            # ilustración editorial generada (cuesta lo que una imagen del
            # B-roll). El presupuesto se comparte entre todos los insertos.
            try:
                ai = eldir / f"ai_{sid:03d}.jpg"
                images.generate(
                    ai_prompt or (f"editorial documentary illustration of "
                                  f"{consulta}, {prefix_ai}, muted palette, "
                                  "no text, no letters, no watermark"), ai)
                src = ai
                ilustradas.append(f"{consulta} (escena {sid})")
            except Exception:
                src = None
                with ai_lock:      # el fallo devuelve el cupo al presupuesto
                    ai_budget[0] += 1
        if src is None:
            sin_fuente.append(f"{consulta} ({motivo + ', ' if motivo else ''}"
                              f"escena {sid})")
            el["files"] = []
            return False
        card = eldir / f"card_{sid:03d}.png"
        elib.render_photo_card(src, el.get("etiqueta", ""), card, card_w,
                               accent)
        el["files"] = [card.name]
        el["mode"] = "photo"
        if credit:
            el["credit"] = credit
            credits.add(credit)
        return True

    def _uno(s, el):
        sid = s["id"]
        if el.get("files") and all((eldir / f).exists() for f in el["files"]):
            return   # reanudación: ya resuelto
        tipo = el.get("tipo", "cifra")
        if tipo in ("cifra", "fecha"):
            frames = elib.render_stat_frames(
                el.get("consulta", ""), el.get("etiqueta", ""),
                eldir / f"stat_{sid:03d}", card_w, accent)
            el["files"] = [str(p.relative_to(eldir)) for p in frames]
            el["mode"] = "stat"
            return
        if tipo == "mapa":
            # LOCALIZADOR: cartografía REAL de OpenStreetMap centrada en las
            # coordenadas del lugar, con el pin cayendo sobre el punto. Un
            # archivo propio del banco con ese nombre tiene prioridad.
            propio = elib.bank_lookup(el.get("consulta", ""), ("mapas",))
            if propio is not None and not elib.is_video(propio):
                card = eldir / f"card_{sid:03d}.png"
                elib.render_photo_card(propio, el.get("etiqueta", ""), card,
                                       card_w, accent)
                el["files"] = [card.name]
                el["mode"] = "photo"
                return
            lugar = el.get("consulta", "").replace(" location map", "").strip()
            coords = elib.geo_lookup(lugar, lang_code) if permitir_web else None
            res = None
            if coords is not None:
                res = mapslib.render_map_frames(
                    el.get("etiqueta") or lugar, coords[0], coords[1],
                    eldir / f"map_{sid:03d}", card_w=card_w, accent=accent,
                    zoom=int(cfg["video"].get("elements_map_zoom", 5)),
                    allow_web=permitir_web)
            if res is not None:
                el["files"] = [f"map_{sid:03d}/{n}" for n in res["files"]]
                el["mode"] = "stat"   # secuencia animada, como las cifras
                el["credit"] = mapslib.OSM_CREDIT
                credits.add(mapslib.OSM_CREDIT)
                return
            # SIN CARTOGRAFÍA REAL (sin coordenadas, sin red o el servicio de
            # teselas no respondió): antes salía una ficha de coordenadas con
            # una retícula VACÍA, que no aporta nada al video. Ahora la
            # mención cae a una imagen REAL del lugar — el retrato del sitio o
            # su mapa histórico en Wikimedia — y, si tampoco la hay, el
            # inserto desaparece.
            mapas.append(f"{lugar} (escena {sid})")
            _foto_insert(
                s, el, lugar, motivo="mapa",
                categorias=("mapas", "lugares"),
                ai_prompt=(f"emblematic period-accurate view of {lugar}, "
                           f"wide establishing shot of its most recognizable "
                           f"landscape or landmark, {prefix_ai}, muted "
                           "palette, no text, no letters, no labels, no "
                           "watermark"))
            return
        _foto_insert(s, el, el.get("consulta", ""))

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_uno, s, el) for s, el in targets]
        for f in futures:
            try:
                f.result()
            except Exception:
                pass   # adorno: nunca tumba la fase
    for s, el in targets:   # los que quedaron sin material salen del plan
        if not el.get("files"):
            s["elements"] = [e for e in s["elements"] if e is not el]
    prev = set(project.get("element_credits") or [])
    project.set("element_credits", sorted(prev | credits))
    if ilustradas:
        notify(f"🎨 {len(ilustradas)} inserto(s) sin foto libre se ilustraron "
               "con IA (lo autorizaste con elements_ai).")
    if mapas:
        notify("🗺 Sin cartografía real para " + ", ".join(mapas[:4])
               + (" y más" if len(mapas) > 4 else "")
               + ": esos localizadores se resuelven con una imagen real del "
                 "lugar (nunca con una ficha de coordenadas vacía).")
    if sin_fuente:
        project.add_warning(
            "Sin foto de licencia libre para: " + ", ".join(sin_fuente[:6])
            + (" y más" if len(sin_fuente) > 6 else "")
            + ". Puedes añadir tu propio archivo (imagen o clip) desde "
            "📚 Biblioteca → Banco de elementos y «Rehacer desde Imágenes»"
            + ("" if cfg["video"].get("elements_ai") else
               ", o activar `elements_ai` para ilustrarlos con IA (cuesta "
               "como una imagen de B-roll cada uno)") + ".")


def _verify_factual(project, llm, cfg, ai_scenes: list[dict],
                    broll_dir: Path, gen_one, skip: set[int]) -> None:
    """El director REVISA con visión lo que se ve en cada escena contra los
    hechos de su narración, y corrige lo que los contradice.

    Tres cosas que lo hacen fiable sin dispararse de precio:
    - Los CLIPS de video se revisan por un fotograma de su interior, no por la
      imagen que los originó: el generador puede animar a un sujeto que la
      narración da por muerto.
    - Un clip infiel NO se re-genera (cuesta 10 veces más que una imagen): la
      escena baja a su imagen fija, que ya está verificada y no cuesta nada.
    - Se corrige en RONDAS (`fact_check_retries`, 2 por defecto): cada ronda
      revisa solo lo regenerado, así el gasto crece con los fallos reales y
      no con el tamaño del video.
    """
    from ytstudio.progress import notify
    img_cfg = cfg.get("providers", {}).get("images", {})
    if not img_cfg.get("fact_check", True):
        return
    if getattr(llm, "is_mock", False):
        return
    targets = [s for s in ai_scenes
               if s["id"] not in skip
               and (broll_dir / f"scene_{s['id']:03d}.jpg").exists()]
    if not targets:
        return
    rondas = max(1, min(4, int(img_cfg.get("fact_check_retries", 2))))
    notify(f"👁 Control de calidad factual: el director compara "
           f"{len(targets)} escena(s) con los hechos de su narración…")

    import hashlib
    import json as _json

    def _firmar(scenes: list[dict]) -> None:
        """Actualiza la caché para que al reanudar NO se re-cobre lo ya
        corregido."""
        sig_path = broll_dir / "prompts.json"
        try:
            sigs = _json.loads(sig_path.read_text(encoding="utf-8"))
        except Exception:
            sigs = {}
        for s in scenes:
            src = ((s.get("broll_prompt") or "") + "|chars:"
                   + ",".join(s.get("characters") or []))
            sigs[str(s["id"])] = hashlib.md5(src.encode("utf-8")).hexdigest()
        sig_path.write_text(_json.dumps(sigs, indent=0), encoding="utf-8")

    pendientes = targets
    degradados: list[int] = []
    agotado = False          # se acabaron las rondas con algo aún sin verificar
    for ronda in range(1, rondas + 1):
        verdicts = _qa_batches(llm, cfg, pendientes, broll_dir, project)
        if verdicts is None:
            return  # la revisión falló (ya avisó): no se afirma nada
        bad = []
        for s in pendientes:
            v = verdicts.get(s["id"])
            if not v or v.get("fiel", True):
                continue
            bad.append((s, v.get("problema", ""),
                        (v.get("prompt_corregido") or "").strip()))
        if not bad:
            if ronda == 1:
                notify("👁 Control factual: todo lo que se ve respeta lo "
                       "narrado.")
            else:
                notify(f"👁 Control factual: corregido en {ronda - 1} ronda(s).")
            return

        # CLIPS infieles → bajan a su imagen fija (verificada y GRATIS)
        rehacer = []
        for s, problema, fixed in bad:
            if s.get("broll_video"):
                s.pop("broll_video", None)
                (broll_dir / "qa" /
                 f"scene_{s['id']:03d}_mid.jpg").unlink(missing_ok=True)
                degradados.append(s["id"])
                project.add_warning(
                    f"🎥 Escena {s['id']}: el CLIP de video se apartaba de lo "
                    f"narrado ({problema}). Se queda con su imagen fija "
                    "animada, que sí lo respeta — no se paga otro clip.")
            elif fixed:
                rehacer.append((s, problema, fixed))

        if not rehacer:
            break
        notify(f"🔁 Ronda {ronda}/{rondas}: {len(rehacer)} imagen(es) "
               f"contradicen su narración "
               f"({', '.join(str(s['id']) for s, _, _ in rehacer)}): se "
               "regeneran con el prompt corregido.")
        redone: list[dict] = []
        for s, problema, fixed in rehacer:
            img = broll_dir / f"scene_{s['id']:03d}.jpg"
            try:
                img.unlink(missing_ok=True)
                gen_one(s, fixed, img)
                s["broll_prompt"] = fixed
                redone.append(s)
                project.add_warning(
                    f"🖼 Escena {s['id']}: la imagen contradecía la narración "
                    f"({problema}) — se regeneró con el prompt corregido "
                    f"(ronda {ronda}).")
            except Exception as e:
                project.add_warning(
                    f"🖼 Escena {s['id']}: la imagen contradice la narración "
                    f"({problema}) y no se pudo regenerar ({e}). Revísala en "
                    "el Storyboard o sube tu propio B-roll.")
        if not redone:
            break
        _firmar(redone)
        pendientes = redone          # la siguiente ronda solo mira lo nuevo
    else:
        # El bucle terminó SIN break: se agotaron las rondas y lo último que
        # se regeneró se quedó sin una mirada que lo confirme.
        agotado = True

    if agotado and pendientes:
        project.add_warning(
            "Tras " + str(rondas) + " ronda(s) de corrección, la(s) escena(s) "
            + ", ".join(str(s["id"]) for s in pendientes) + " pueden seguir "
            "sin respetar un hecho de la narración (los generadores fallan "
            "contando o con anatomías poco comunes). Revísalas en el "
            "Storyboard: puedes editar el prompt a mano o subir tu B-roll.")
    if degradados:
        notify(f"🎥 {len(set(degradados))} clip(s) de video bajaron a imagen "
               "fija por no respetar lo narrado (sin costo adicional).")



_REFRAME_MISMATCH = 1.45  # 1:1 sobre 16:9 da 1.78 (reencuadrar); 4:3 da 1.33 (ok)


def _aspect_mismatch(img_path: Path, cfg: dict) -> float:
    """Cuánto difiere el aspecto de la imagen del de salida (1.0 = idéntico,
    siempre >= 1). Por encima de _REFRAME_MISMATCH el recorte de cobertura
    cortaría el sujeto (un retrato sobre 16:9 pierde los ojos)."""
    from PIL import Image
    v = cfg.get("video", {})
    out_ar = int(v.get("width", 1920)) / int(v.get("height", 1080))
    with Image.open(img_path) as im:
        src_ar = im.width / im.height
    return max(out_ar / src_ar, src_ar / out_ar)


def _reframe_character_still(img: Path, prompt: str, broll_dir: Path,
                             cfg: dict) -> Path | None:
    """La foto del personaje con un aspecto muy distinto al del video no cabe
    en el encuadre: el director la REGENERA con el modelo de identidad (la
    foto como referencia) ya en el formato del video, para que el personaje
    se vea completo. Devuelve el reencuadre, o None si no se pudo (sin token,
    modelo caído…) — en ese caso el montaje compone la foto ENTERA sobre su
    propio fondo desenfocado, así que la cara nunca queda cortada."""
    from ytstudio.progress import notify
    try:
        if _aspect_mismatch(img, cfg) < _REFRAME_MISMATCH:
            return None  # el recorte de cobertura encuadra bien tal cual
    except Exception:
        return None
    dest = broll_dir / "personaje_wide.jpg"
    if dest.exists():  # reanudable
        return dest
    from ytstudio.providers.images import get_ref_images
    ref_images = get_ref_images(cfg)
    if ref_images is None:
        return None
    v = cfg.get("video", {})
    vertical = int(v.get("height", 1080)) > int(v.get("width", 1920))
    from ytstudio.catalog import aspect_for
    shape = "vertical" if vertical else "wide horizontal"
    full_prompt = (
        f"{prompt}. Reframe as a {shape} {aspect_for(cfg)} medium shot of "
        "this exact person: same face, same clothing and same appearance, "
        "head and shoulders fully inside the frame with natural headroom "
        "(never crop the top of the head or the chin), subject centered, "
        "looking at the camera, natural coherent background extended to fill "
        "the whole frame, no black bars, no letterboxing")
    try:
        notify("🧑 La foto del personaje no coincide con el formato del video: "
               "el director la reencuadra con el modelo de identidad…")
        ref_images.generate_with_refs(full_prompt, [img], dest)
    except Exception as e:
        notify(f"⚠ No se pudo reencuadrar la foto del personaje con IA ({e}) "
               "— se compondrá la foto entera sobre fondo desenfocado.")
        return None
    if not dest.exists():
        return None
    # El reencuadre solo vale si de verdad SALIÓ en el formato del video:
    # un modelo que devuelve la misma vertical no arregla nada.
    try:
        if _aspect_mismatch(dest, cfg) >= _REFRAME_MISMATCH:
            notify("⚠ El reencuadre del personaje volvió con el mismo formato "
                   "vertical — se compondrá la foto entera sobre fondo "
                   "desenfocado (la cara nunca se corta).")
            dest.unlink(missing_ok=True)
            return None
    except Exception:
        pass
    return dest


def _character_plate(img: Path, prompt: str, broll_dir: Path,
                     cfg: dict) -> Path:
    """La foto del personaje LISTA para el formato del video: se copia al
    proyecto y, si su aspecto no encaja (una foto 9:16 en un video 16:9), se
    reencuadra con el modelo de identidad. Esta es la imagen que alimenta el
    lipsync Y la que se ve si el lipsync falla — así el encuadre es el mismo
    en las dos rutas."""
    import shutil as _sh
    dest = broll_dir / f"personaje{img.suffix.lower() or '.jpg'}"
    if not dest.exists():
        _sh.copyfile(img, dest)
    return _reframe_character_still(dest, prompt, broll_dir, cfg) or dest


def _lipsync_signature(plate: Path, audio: Path, scene: dict) -> str:
    """Huella de las entradas de un clip de lipsync (foto + audio + duración
    de la escena). Si cambia cualquiera, el clip guardado ya no sirve."""
    import hashlib
    h = hashlib.sha1()
    for p in (plate, audio):
        try:
            h.update(p.name.encode("utf-8"))
            h.update(p.read_bytes())
        except OSError:
            h.update(b"?")
    h.update(f"{float(scene.get('duration') or 0):.3f}".encode())
    return h.hexdigest()[:16]


def _character_image(project, cfg: dict | None = None):
    """Imagen del personaje NARRADOR (del elenco): su primera foto subida o,
    si no tiene, su referencia autogenerada. None si no hay narrador."""
    from ytstudio.characters import (character_images, ensure_reference,
                                     narrator)
    ch = narrator(project)
    if ch is None:
        return None
    imgs = character_images(project, ch)
    if imgs:
        return imgs[0]
    if cfg is not None:
        try:
            return ensure_reference(project, cfg, ch)
        except Exception:
            return None
    return None


def _generate_character_scenes(project, scenes: list[dict], broll_dir,
                               cfg: dict) -> set[int]:
    """Escenas de PERSONAJE (lipsync): el personaje habla el tramo EXACTO de
    audio de su escena, cortado de la PISTA FINAL de voz (la que se va a oír,
    con las pausas ya ajustadas por el director). El clip entra al montaje
    como video MUDO — la voz la pone la pista continua, así que los labios
    quedan en sincronía sin tocar el motor de tiempos.

    Y la foto del personaje se adapta al formato del video ANTES de generar
    los clips: si se entrega una foto 9:16 a un video 16:9, el clip nace
    vertical y el montaje tendría que recortarlo hasta el mentón.

    Degradación limpia: sin proveedor/clave, o si un clip falla, esa escena
    usa la imagen fija del personaje con Ken Burns (y se avisa)."""
    from ytstudio.progress import notify

    overrides = project.get("shot_overrides") or {}
    for s in scenes:
        ov = overrides.get(str(s["id"]))
        if ov in ("personaje", "broll"):
            s["shot"] = ov
    char_scenes = [s for s in scenes if s.get("shot") == "personaje"]
    if not char_scenes:
        return set()
    img = _character_image(project, cfg)
    if img is None:
        for s in char_scenes:
            s["shot"] = "broll"
        project.add_warning(
            "Hay escenas marcadas como PERSONAJE pero no subiste su imagen "
            "(categoría 🧑 Personaje en Archivos): se generan como B-roll.")
        return set()

    # LA FOTO SE ADAPTA AL FORMATO **ANTES** DE HABLAR: el lipsync devuelve un
    # clip con el aspecto de la foto que se le entrega. Con una foto 9:16 en un
    # video 16:9, TODAS las escenas de personaje salían recortadas al mentón
    # (el reencuadre existía, pero solo se aplicaba a las que fallaban). Ahora
    # se reencuadra primero y el clip nace ya en el formato del video.
    prompt0 = next((s.get("broll_prompt") for s in char_scenes
                    if s.get("broll_prompt")),
                   "portrait of the narrator speaking to the camera")
    plate = _character_plate(img, prompt0, broll_dir, cfg)

    def _still_fallback(targets: list[dict]) -> None:
        # Si no se pudo reencuadrar, el montaje compone la foto ENTERA sobre
        # fondo desenfocado — la cara nunca se corta.
        for s in targets:
            s["broll_image"] = plate.name
            s["broll_type"] = "image"
            s.pop("broll_video", None)
            s["broll_source"] = "lipsync"
            if s.get("animation") == "static":
                s["animation"] = "zoom_in"

    from ytstudio.providers import get_lipsync
    ls = get_lipsync(cfg)
    if ls is None:
        _still_fallback(char_scenes)
        project.add_warning(
            "Lipsync desactivado o sin REPLICATE_API_TOKEN: el personaje "
            "aparece como imagen fija con movimiento (sin hablar). Actívalo "
            "en ⚙ Configuración → Personaje narrador.")
        return {s["id"] for s in char_scenes}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ytstudio import usage as usage_mod
    from ytstudio.utils.media import run_ffmpeg
    usage_items = usage_mod.get_state()
    vo_dir = project.path("voiceover")
    workers = max(1, int(cfg.get("performance", {}).get("parallel_video", 2)))

    from ytstudio.progress import get_sink
    sink = get_sink()

    def _lipsync_audio(s: dict) -> Path:
        """El audio que mueve los labios: el tramo de la PISTA FINAL de voz
        que suena en esta escena — con las pausas ya ajustadas por el director
        y la duración exacta de la escena. Cortar el tramo de la grabación
        original (vo_XXX.mp3) desincronizaba el personaje en cuanto el
        director recortaba o ampliaba una pausa. Respaldo: el vo_ de siempre
        (TTS o proyectos sin pista de voz)."""
        from ytstudio.phases.voiceover import timeline_segment
        from ytstudio.utils.media import probe_duration
        seg = vo_dir / f"lipsync_audio_{s['id']:03d}.wav"
        fresh = False
        if seg.exists():
            # Caché obsoleta: si la escena cambió de duración desde que se
            # cortó este tramo, el audio ya no es el que sonará.
            try:
                fresh = abs(probe_duration(seg)
                            - float(s.get("duration") or 0)) <= 0.12
            except Exception:
                fresh = False
        if not fresh:
            try:
                if timeline_segment(project, scenes, s, seg) is None:
                    seg = None
            except Exception:
                seg = None
        if seg is not None and seg.exists():
            return seg
        vo = vo_dir / f"vo_{s['id']:03d}.mp3"
        if not vo.exists():
            raise RuntimeError(f"Falta el audio de la escena {s['id']} "
                               "(rehaz desde Voz).")
        return vo

    # FIRMA del clip: con qué foto y con qué audio EXACTO se generó. Un clip
    # en caché solo vale si su firma coincide — así un clip hecho con la foto
    # sin reencuadrar o con el audio anterior al ajuste de pausas se rehace en
    # vez de quedarse desincronizado para siempre. (Se avisa: cuesta.)
    audios: dict[int, Path] = {}
    sigs: dict[int, str] = {}
    for s in char_scenes:
        try:
            a = _lipsync_audio(s)
            audios[s["id"]] = a
            sigs[s["id"]] = _lipsync_signature(plate, a, s)
        except Exception:
            pass   # sin audio: _gen levantará el error con su mensaje claro

    def _cached(s: dict) -> bool:
        clip = broll_dir / f"lipsync_{s['id']:03d}.mp4"
        sig_f = broll_dir / f"lipsync_{s['id']:03d}.sig"
        return (clip.exists() and sig_f.exists()
                and sig_f.read_text(encoding="utf-8").strip()
                == sigs.get(s["id"], ""))

    todo = [s for s in char_scenes if not _cached(s)]
    stale = [s for s in todo
             if (broll_dir / f"lipsync_{s['id']:03d}.mp4").exists()]
    if stale:
        notify(f"🔁 {len(stale)} clip(s) de personaje se rehacen: se "
               "generaron con la foto sin adaptar al formato o con el audio "
               "anterior al ajuste de pausas del director (por eso el "
               "encuadre y la sincronía fallaban).")
    if todo:
        notify(f"🧑 Generando {len(todo)} escena(s) de PERSONAJE con lipsync "
               f"({ls.model.split('/')[-1]}, {workers} en paralelo — tarda "
               "minutos por clip)…")

    def _gen(s: dict) -> None:
        usage_mod.bind(usage_items)
        _bind_worker_logging(sink)
        clip = broll_dir / f"lipsync_{s['id']:03d}.mp4"
        if _cached(s):   # reanudable
            return
        audio = audios.get(s["id"]) or _lipsync_audio(s)
        ls.generate(plate, audio, clip, seconds=float(s.get("duration") or 5))
        sig = sigs.get(s["id"]) or _lipsync_signature(plate, audio, s)
        (broll_dir / f"lipsync_{s['id']:03d}.sig").write_text(
            sig, encoding="utf-8")

    failed: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_gen, s): s for s in char_scenes}
        for future in as_completed(futures):
            s = futures[future]
            try:
                future.result()
                notify(f"🧑 Personaje listo (escena {s['id']})")
            except Exception as e:
                failed.append(s)
                notify(f"⚠ Lipsync de la escena {s['id']} falló — usará la "
                       f"imagen fija del personaje. {e}")
    ok = [s for s in char_scenes if s not in failed
          and (broll_dir / f"lipsync_{s['id']:03d}.mp4").exists()]
    # Modo BURBUJA (character.pip): el personaje NO ocupa la pantalla — se
    # compone en una burbuja circular sobre el B-roll de su escena (estilo
    # reacción). La escena conserva su flujo normal de imagen; el clip de
    # lipsync viaja aparte como pip_video.
    pip_mode = bool((project.get("character") or {}).get("pip"))
    for s in ok:
        clip = broll_dir / f"lipsync_{s['id']:03d}.mp4"
        if pip_mode:
            s["pip_video"] = clip.name
            continue
        poster = broll_dir / f"lipsync_{s['id']:03d}.jpg"
        if not poster.exists():
            run_ffmpeg(["-i", str(clip), "-frames:v", "1", str(poster)],
                       "fotograma del personaje")
        s["broll_video"] = clip.name
        s["broll_image"] = poster.name
        s["broll_type"] = "video"
        s["broll_source"] = "lipsync"
    if failed:
        if pip_mode:
            # sin burbuja esa escena: queda su B-roll normal (nada que romper)
            project.add_warning(
                f"El lipsync falló en {len(failed)} escena(s) "
                f"({', '.join(str(s['id']) for s in failed)}): salen sin la "
                "burbuja del personaje (solo B-roll). «Rehacer desde "
                "Imágenes» reintenta solo esas.")
        else:
            _still_fallback(failed)
            project.add_warning(
                f"El lipsync falló en {len(failed)} escena(s) "
                f"({', '.join(str(s['id']) for s in failed)}): usan la imagen "
                "fija del personaje. «Rehacer desde Imágenes» reintenta solo "
                "esas.")
    # En modo burbuja las escenas de personaje SIGUEN generando su B-roll de
    # fondo (no se marcan como resueltas por el lipsync).
    return set() if pip_mode else {s["id"] for s in char_scenes}


def run(project, cfg) -> None:
    images = get_images(cfg)
    videogen = get_videogen(cfg)
    scenes = load_scenes(project)
    broll_dir = project.path("broll")
    (broll_dir / "manual").mkdir(exist_ok=True)
    llm = get_llm(cfg)

    # 0) B-roll MANUAL por escena (subido en Storyboard): máxima prioridad, y
    #    el director lo revisa con visión (encaja o no, con aviso).
    placed_manual = _place_manual_broll(project, scenes, broll_dir, cfg)
    _review_manual_broll(project, llm, scenes, placed_manual, broll_dir, cfg)

    # 0a) Video de REACCIÓN (si lo subiste): se registra y clasifica (chroma
    #     o burbuja) para que el montaje lo componga sobre el contenido.
    _setup_reaction(project, broll_dir)

    # 0b) PERSONAJE narrador con lipsync: las escenas que el director marcó
    #     como 'personaje' (más tus ajustes del Editor) muestran al personaje
    #     hablando su tramo exacto de la narración. Ganan sobre cualquier
    #     otro material de esa escena.
    lipsync_ids = _generate_character_scenes(project, scenes, broll_dir, cfg)
    if lipsync_ids & placed_manual:
        project.add_warning(
            "Escena(s) "
            + ", ".join(str(i) for i in sorted(lipsync_ids & placed_manual))
            + ": son de PERSONAJE, así que tu B-roll manual de esas escenas "
            "no se usa (cámbialas a B-roll en el Editor si lo prefieres).")
        placed_manual -= lipsync_ids

    # 1) B-roll propio del creador: asignación SEMÁNTICA (cada material va a
    #    la escena cuya narración ilustra, según su descripción de visión).
    #    Si no hay IA disponible, reparto uniforme como respaldo.
    user_assets = _user_broll_assets(project)
    from ytstudio.progress import notify as _notify

    # 1a) Por NÚMERO DE ARCHIVO (determinista, prioridad máxima): scene_003,
    #     03_batalla, (3)… van a la escena de ese número — el orden que TÚ
    #     indicaste con el nombre manda sobre el criterio del director.
    numbered = _numbered_map(scenes, user_assets)
    if numbered:
        _notify(f"📌 {len(numbered)} B-roll(s) asignados por su NÚMERO de "
                "archivo a la escena correspondiente: "
                + ", ".join(f"«{user_assets[a]['name']}»→escena "
                            f"{scenes[i]['id']}" for i, a in numbered.items()))

    rest_assets = [a for i, a in enumerate(user_assets)
                   if i not in numbered.values()]
    rest_scenes = [s for i, s in enumerate(scenes) if i not in numbered]
    mapping: dict[int, int] | None = None
    if rest_assets and not getattr(llm, "is_mock", False):
        try:
            sub = _semantic_map(llm, rest_scenes, rest_assets,
                                cfg.get("language", "es"))
            # traducir índices del subconjunto a índices globales
            sidx = {i: scenes.index(s) for i, s in enumerate(rest_scenes)}
            aidx = {i: user_assets.index(a) for i, a in enumerate(rest_assets)}
            mapping = {sidx[si]: aidx[ai] for si, ai in sub.items()}
            unused = [a["name"] for i, a in enumerate(rest_assets)
                      if i not in sub.values()]
            if unused:
                project.add_warning(
                    "B-roll propio sin usar (no encajaba con ninguna escena "
                    "del guion): " + ", ".join(unused) + ". Consejo: ponle al "
                    "archivo el número de la escena (ej. escena_5.jpg) o "
                    "súbelo directo a su escena en el Storyboard.")
        except Exception as e:
            project.add_warning(f"Asignación inteligente de B-roll no "
                                f"disponible (reparto uniforme): {e}")
    if mapping is None:
        mapping = _spread(len(rest_assets), len(scenes))
        mapping = {si: user_assets.index(rest_assets[ai])
                   for si, ai in mapping.items()
                   if si not in numbered and ai < len(rest_assets)}
    mapping.update(numbered)
    # Las escenas con B-roll MANUAL ya están resueltas: no se les reparte
    # material semántico encima.
    if placed_manual:
        mapping = {i: a for i, a in mapping.items()
                   if scenes[i]["id"] not in placed_manual}
    # Las escenas de PERSONAJE (lipsync) ya tienen su material
    mapping = {i: a for i, a in mapping.items()
               if scenes[i].get("broll_source") != "lipsync"}

    # Caché HONESTA del material por escena: cada escena se firma con lo que
    # debe mostrar (hash del prompt IA, o el archivo propio asignado). Si al
    # reanudar la firma cambió — el guion se rehízo, o la asignación
    # inteligente movió un B-roll propio a otra escena — el material viejo ya
    # NO ilustra esa narración: se borra y se rehace (con aviso). Sin esto,
    # una imagen vieja se quedaba pegada en la escena equivocada y el video
    # salía «desfasado» respecto a la voz. Los proyectos previos sin firma
    # adoptan la actual sin regenerar nada (cero costo sorpresa).
    import hashlib
    import json as _json
    from ytstudio.progress import notify
    sig_path = broll_dir / "prompts.json"
    try:
        sigs = _json.loads(sig_path.read_text(encoding="utf-8"))
    except Exception:
        sigs = {}
    stale: list[int] = []
    for idx, s in enumerate(scenes):
        if s["id"] in placed_manual or s.get("broll_source") == "lipsync":
            continue  # manual y personaje: material gestionado aparte
        if idx in mapping:
            sig = "user:" + user_assets[mapping[idx]]["file"]
        else:
            sig_src = ((s.get("broll_prompt") or "") + "|chars:"
                       + ",".join(s.get("characters") or []))
            sig = hashlib.md5(sig_src.encode("utf-8")).hexdigest()
        key = str(s["id"])
        cached = list(broll_dir.glob(f"scene_{s['id']:03d}.*"))
        if sigs.get(key) not in (None, sig) and cached:
            for p in cached:
                p.unlink(missing_ok=True)
            stale.append(s["id"])
        sigs[key] = sig
    sig_path.write_text(_json.dumps(sigs, indent=0), encoding="utf-8")
    if stale:
        notify(f"🔄 El contenido de {len(stale)} escena(s) cambió desde la "
               f"última generación ({', '.join(map(str, stale))}): su material "
               "se rehace para que corresponda a la narración actual.")

    for scene_idx, asset_idx in mapping.items():
        _assign_user_asset(scenes[scene_idx], user_assets[asset_idx],
                           project, broll_dir)

    # 2) IA para las escenas sin material propio — EN PARALELO: cada imagen o
    #    clip es una llamada de red independiente; generarlos en serie era el
    #    mayor cuello de botella del pipeline (mismo costo, mucho menos tiempo).
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ytstudio import usage as usage_mod
    from ytstudio.progress import notify

    # El gasto real (imágenes/clips) se registra DENTRO de los hilos del pool
    # más abajo — comparten este acumulador (los hilos nuevos no heredan el
    # del hilo que arrancó la generación).
    usage_items = usage_mod.get_state()

    perf = cfg.get("performance", {})
    img_workers = max(1, int(perf.get("parallel_images", 4)))
    _img_name = cfg["providers"]["images"].get("name")
    if _img_name == "replicate":
        # con crédito bajo Replicate limita a 6/min: más hilos solo generan 429
        img_workers = min(img_workers, 2)
    elif _img_name == "openai":
        # la familia gpt-image admite MUY pocas imágenes por minuto (5 en cuentas
        # nuevas): con 4 hilos el 429 es inevitable. Con 2 el ritmo se acerca
        # al límite y los reintentos con espera absorben lo que sobre.
        img_workers = min(img_workers, 2)
    vid_workers = max(1, int(perf.get("parallel_video", 2)))

    ai_scenes = [s for s in scenes
                 if s.get("broll_source") not in ("user", "manual", "lipsync")]

    # ELEMENTOS de archivo (insertos documentales): se materializan ANTES de
    # las imágenes — descargas rápidas y tarjetas locales; un fallo aquí quita
    # el adorno, nunca la fase.
    try:
        _resolve_elements(project, cfg, scenes, broll_dir, images=images)
    except Exception as e:
        project.add_warning(f"El material de archivo no se pudo preparar "
                            f"({e}): el video sale sin insertos documentales.")

    # 2a) Imágenes. Un fallo de INFRAESTRUCTURA (auth, red) detiene la fase
    #     (reanudable). Un rechazo de CONTENIDO (NSFW) de UNA imagen no puede
    #     tumbar todo el proyecto: se reintenta con el prompt suavizado y, si
    #     persiste, se usa un fondo cinematográfico neutro para esa escena.
    concept = project.get("concept") or {}
    palette = (concept.get("visual_style") or {}).get("palette") or []
    prefix = (concept.get("visual_style") or {}).get("prompt_prefix") or \
        "cinematic documentary still"
    from ytstudio.catalog import lang_name
    lang = lang_name(cfg)
    nsfw_scenes: list[int] = []       # quedaron con respaldo local sin costo
    safe_scenes: list[int] = []       # quedaron con plano atmosférico seguro
    encuadradas: list[int] = []       # salieron con registro documental
    suavizadas: list[int] = []        # necesitaron el segundo intento

    # ELENCO: referencias de identidad por personaje, resueltas EN SERIE antes
    # del pool (genera la referencia del personaje sin fotos una sola vez).
    from ytstudio.characters import references_for
    from ytstudio.providers.images import get_ref_images
    ref_images = get_ref_images(cfg)
    cast_needed = sorted({n for s in ai_scenes
                          for n in (s.get("characters") or [])})
    char_refs: dict[str, list] = {}
    if cast_needed:
        if ref_images is None:
            project.add_warning(
                "Hay escenas con personajes del ELENCO pero falta "
                "REPLICATE_API_TOKEN para el modelo de identidad: se generan "
                "sin referencia (la cara puede variar entre escenas).")
        else:
            for n in cast_needed:
                char_refs[n] = references_for(project, cfg, [n])

    def _scene_refs(scene: dict) -> list:
        out = []
        for n in (scene.get("characters") or []):
            for p in char_refs.get(n, []):
                if p not in out:
                    out.append(p)
        return out[:6]

    from ytstudio.progress import get_sink
    sink = get_sink()

    # MODO HÍBRIDO (providers.images.upscale): generar barato y subir la
    # resolución después. El escalador se salta solo las imágenes que ya dan
    # la talla, así que activarlo nunca cobra de más por el B-roll propio del
    # creador ni por los respaldos locales.
    from ytstudio.providers.images import get_upscaler
    upscaler = get_upscaler(cfg)
    if upscaler is not None:
        notify(f"⬆ Escalado activado ({upscaler.model.split('/')[-1]}): las "
               f"imágenes por debajo de {upscaler.target_w}px se suben a la "
               "resolución del video.")

    # Escenas con TEXTO dentro de la imagen: las que el director declaró
    # (image_text) Y las que su prompt describe con un objeto escrito
    # (periódico, cartel, documento, lápida…). En TODAS el texto debe salir
    # LEGIBLE — es el estándar de calidad del programa —, así que se rutean al
    # modelo con mejor tipografía disponible. Elección DINÁMICA por escena: el
    # resto sigue con el modelo configurado (más económico).
    text_images = None
    text_ids = sorted({s["id"] for s in ai_scenes if _shows_text(s)})
    if text_ids:
        import os as _os
        from ytstudio.providers.images import OpenAIImages
        if isinstance(images, OpenAIImages):
            text_images = images   # ya es de OpenAI: no abras un segundo
        elif _os.environ.get("OPENAI_API_KEY"):
            try:
                text_images = OpenAIImages(cfg)
                notify(f"🔤 {len(text_ids)} escena(s) muestran texto "
                       f"({', '.join(map(str, text_ids))}): se generan con "
                       f"{text_images.model} (la mejor tipografía disponible) "
                       "para que se lea de verdad, en el idioma del guion.")
            except Exception as e:
                project.add_warning(
                    "No se pudo preparar el modelo de texto de OpenAI para "
                    f"las escenas con texto ({e}).")
        if text_images is None:
            project.add_warning(
                "Escena(s) " + ", ".join(map(str, text_ids)) + " muestran "
                "texto en la imagen, pero no hay clave de OpenAI "
                "(gpt-image): se usa el modelo estándar con énfasis "
                "tipográfico. Revisa esas imágenes — los modelos estándar "
                "suelen deformar las letras. Configura tu OPENAI_API_KEY en "
                "⚙ Configuración para tipografía de verdad.")

    def _texted(scene: dict, prompt: str) -> str:
        """Exigencia de TEXTO LEGIBLE, el estándar del programa.

        · Con image_text: el prompt pide ESE texto exacto y ningún otro.
        · Sin image_text pero con un objeto escrito en el prompt (periódico,
          cartel, documento): se exige que lo que se lea sean palabras REALES
          y correctas, y se desactiva cualquier «unreadable/blurred text» que
          arrastre el prompt (era la vieja receta y producía garabatos).

        EL IDIOMA LO MANDA LA ESCENA: por defecto el del video, pero un papiro
        en arameo dentro de un documental en español debe leerse EN ARAMEO —
        forzar el idioma de la narración sería un error histórico visible en
        pantalla. El director lo indica en image_text_lang."""
        txt = (scene.get("image_text") or "").strip()
        idioma = (scene.get("image_text_lang") or "").strip() or lang
        propio = idioma.strip().lower() != lang.strip().lower()
        detalle = (f'in {idioma} script, historically accurate lettering for '
                   'that language, NOT translated and NOT transliterated'
                   if propio else f'written in {idioma}')
        if txt:
            return (f'{_drop_illegible(prompt)}. The only legible text in the '
                    f'image is exactly "{txt}" ({detalle}), spelled '
                    "correctly, integrated naturally into the scene "
                    "(headline, sign or document), clean professional "
                    "typography. No other text or letters anywhere.")
        if not _shows_text(scene):
            return prompt
        return (f"{_drop_illegible(prompt)}. Any text visible in the image "
                f"must be REAL, correctly spelled words {detalle}, sharp and "
                "fully readable, with clean typography true to the period — "
                "never invented glyphs, scrambled letters or gibberish. Keep "
                "it to a few short words.")

    def _safe_prompt() -> str:
        """Plano atmosférico del MISMO mundo visual, sin sujetos: pasa
        cualquier filtro de contenido y sigue siendo una imagen real del
        video (no un fondo sintético)."""
        return (f"{prefix}, quiet atmospheric establishing shot of the "
                "story's setting, empty landscape with dramatic light and "
                "haze, no people, no animals, no text, tasteful, safe for "
                "work")

    def _gen_one(scene: dict, prompt: str, img: Path) -> None:
        """Escalera de UNA imagen: modelo de texto (si la escena pide texto
        legible) → identidad (si hay elenco) → normal → prompt suavizado →
        plano atmosférico seguro → respaldo local (vecino desenfocado o
        degradado). La usan la imagen principal y la segunda mitad de las
        escenas con pantalla dividida."""
        prompt = _texted(scene, prompt)
        # ENCUADRE DOCUMENTAL DESDE EL PRIMER INTENTO: si la escena es
        # sensible (marcada por el director o detectada aquí), el registro
        # clínico va delante YA — antes, el primer intento salía en crudo,
        # lo rechazaba el filtro y solo entonces se suavizaba: tiempo
        # perdido, a veces dinero, y una imagen peor.
        prompt, _categoria = ps.encuadrar(prompt, scene.get("sensibilidad", ""),
                                          scene.get("narration", ""))
        if _categoria != "ninguna":
            encuadradas.append(scene["id"])
        refs = _scene_refs(scene)
        # Texto en pantalla SIN personajes del elenco → mejor tipografía
        if _shows_text(scene) and text_images is not None and not refs:
            try:
                text_images.generate(prompt, img)
                return
            except Exception as e:
                if not _is_content_error(e):
                    # el ruteo tipográfico es OPCIONAL: nunca tumba la fase
                    project.add_warning(
                        f"El modelo de texto falló en la escena {scene['id']} ({e}) "
                        "— se usa el modelo estándar para esa imagen.")
                # y sigue la escalera normal
        # Escena con personajes del elenco → modelo de IDENTIDAD con sus
        # fotos de referencia (misma cara en todas sus escenas).
        if refs and ref_images is not None:
            try:
                ref_images.generate_with_refs(prompt, refs, img)
                return
            except Exception as e:
                if not _is_content_error(e):
                    raise
                # rechazo de contenido → sigue el flujo normal suavizado
        try:
            images.generate(prompt, img)
            return
        except Exception as e:
            if not _is_content_error(e):
                raise  # infraestructura → detiene la fase (reanudable)
        # Rechazo de contenido: reintento suavizado que CONSERVA los hechos
        # (especie, estado sin vida, número, ubicación) y quita solo lo
        # gratuito — el suavizado anterior convertía «dead goat» en «ancient
        # goat» y deshacía la fidelidad factual.
        try:
            images.generate(ps.suavizar(prompt), img)
            suavizadas.append(scene["id"])
            return
        except Exception as e:
            if not _is_content_error(e):
                raise
        # Sigue rechazado: plano atmosférico SEGURO del mismo mundo visual —
        # una imagen real (cuesta una imagen más) en vez de un fondo vacío.
        try:
            images.generate(_safe_prompt(), img)
            safe_scenes.append(scene["id"])
            return
        except Exception:
            pass  # último recurso: respaldo local sin costo
        _fallback_image(img, cfg, palette, broll_dir=broll_dir,
                        scene_id=scene["id"])
        nsfw_scenes.append(scene["id"])

    def _gen_image(scene: dict) -> None:
        usage_mod.bind(usage_items)
        _bind_worker_logging(sink)
        img = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if not img.exists():  # reanudable
            _gen_one(scene, scene["broll_prompt"], img)
        # El escalado va FUERA del `if`: si la fase se cortó entre generar y
        # escalar, al reanudar la imagen ya existe pero se quedó pequeña. Como
        # `upscale()` se salta gratis lo que ya da la talla, llamarlo siempre
        # repara ese caso sin cobrar dos veces por lo ya escalado.
        if upscaler is not None:
            upscaler.upscale(img)
        # Pantalla dividida: la SEGUNDA mitad tiene su propia imagen
        if scene.get("layout") == "dividida" and scene.get("broll_prompt_b"):
            img_b = broll_dir / f"scene_{scene['id']:03d}_b.jpg"
            if not img_b.exists():
                _gen_one(scene, scene["broll_prompt_b"], img_b)
            if upscaler is not None:
                upscaler.upscale(img_b)
            scene["broll_image_b"] = img_b.name

    def _split_pending(s: dict) -> bool:
        return (s.get("layout") == "dividida" and s.get("broll_prompt_b")
                and not (broll_dir / f"scene_{s['id']:03d}_b.jpg").exists())

    todo_imgs = [s for s in ai_scenes
                 if not (broll_dir / f"scene_{s['id']:03d}.jpg").exists()
                 or _split_pending(s)]
    if todo_imgs:
        notify(f"🖼 Generando {len(todo_imgs)} imágenes "
               f"({img_workers} en paralelo)…")
        with ThreadPoolExecutor(max_workers=img_workers) as pool:
            futures = {pool.submit(_gen_image, s): s for s in todo_imgs}
            done = 0
            for future in as_completed(futures):
                future.result()  # un fallo real detiene la fase (reanudable)
                done += 1
                notify(f"🖼 Imagen {done}/{len(todo_imgs)} lista "
                       f"(escena {futures[future]['id']})")
    for s in ai_scenes:
        s["broll_image"] = f"scene_{s['id']:03d}.jpg"
        if (s.get("layout") == "dividida"
                and (broll_dir / f"scene_{s['id']:03d}_b.jpg").exists()):
            s["broll_image_b"] = f"scene_{s['id']:03d}_b.jpg"
    if encuadradas:
        notify(f"🎞 {len(set(encuadradas))} escena(s) de contenido delicado "
               "salieron con registro documental desde el primer intento "
               "(clínico y sobrio, con los hechos intactos).")
    if suavizadas:
        project.add_warning(
            f"Las escenas {', '.join(map(str, sorted(set(suavizadas))))} "
            "necesitaron un segundo intento con el prompt en registro más "
            "clínico. Los hechos (especie, estado, cantidad, ubicación) se "
            "conservan; revísalas por si el tono cambió.")
    if safe_scenes:
        project.add_warning(
            "El generador marcó como sensible el prompt de "
            f"{len(safe_scenes)} escena(s) ({', '.join(map(str, safe_scenes))}) "
            "incluso suavizado: se generó en su lugar un plano atmosférico "
            "del mismo mundo visual (sin los sujetos del guion). Puedes "
            "reformular ese texto y «Rehacer desde Imágenes», o subir tu "
            "propio B-roll para esas escenas.")
    if nsfw_scenes:
        project.add_warning(
            "El generador rechazó TODOS los intentos (incluido el plano "
            f"atmosférico) en {len(nsfw_scenes)} escena(s) "
            f"({', '.join(map(str, nsfw_scenes))}): se usó la escena vecina "
            "desenfocada como fondo (o un degradado si no había vecina). "
            "Reformula ese texto del guion y «Rehacer desde Imágenes», o "
            "sube tu propio B-roll para esas escenas.")

    # 2a-bis) CONTROL DE CALIDAD FACTUAL con visión: el director compara cada
    #         imagen generada con los HECHOS de su narración y regenera (una
    #         vez) las que la contradicen — ovejas vivas donde el guion dice
    #         muertas, 4 orificios donde narró 3 en triángulo, anatomía
    #         humana donde el sujeto es un animal.
    from ytstudio.providers.images import MockImages
    if not isinstance(images, MockImages):
        _verify_factual(project, llm, cfg, ai_scenes, broll_dir, _gen_one,
                        set(nsfw_scenes) | set(safe_scenes))

    # 2b) Clips de video IA (opcionales: cada fallo degrada ESA escena a
    #     imagen animada, sin detener el proyecto)
    video_scenes = [s for s in ai_scenes if s.get("broll_type") == "video"]
    videogen_warning = None
    if video_scenes and videogen is not None:
        def _gen_clip(scene: dict) -> None:
            usage_mod.bind(usage_items)
            _bind_worker_logging(sink)
            clip = broll_dir / f"scene_{scene['id']:03d}.mp4"
            if not clip.exists():
                # imagen como fotograma inicial → coherencia visual del clip
                videogen.generate(scene["broll_prompt"], clip,
                                  image=broll_dir / scene["broll_image"],
                                  seconds=float(scene.get("duration", 5)))

        todo_clips = [s for s in video_scenes
                      if not (broll_dir / f"scene_{s['id']:03d}.mp4").exists()]
        if todo_clips:
            notify(f"🎥 Generando {len(todo_clips)} clips de video "
                   f"({vid_workers} en paralelo — Kling tarda varios minutos "
                   "por clip)…")
        with ThreadPoolExecutor(max_workers=vid_workers) as pool:
            futures = {pool.submit(_gen_clip, s): s for s in todo_clips}
            for future in as_completed(futures):
                s = futures[future]
                try:
                    future.result()
                    notify(f"🎥 Clip de video listo (escena {s['id']})")
                except Exception as e:
                    videogen_warning = str(e)
                    notify(f"⚠ Clip de la escena {s['id']} falló — esa escena "
                           "usará imagen animada.")
    for s in video_scenes:
        if (broll_dir / f"scene_{s['id']:03d}.mp4").exists():
            s["broll_video"] = f"scene_{s['id']:03d}.mp4"
        else:
            s["broll_type"] = "image"
            s.pop("broll_video", None)
    for s in ai_scenes:
        if s.get("broll_type") != "video":
            s["broll_type"] = "image"
            s.pop("broll_video", None)

    if videogen_warning:
        project.add_warning(f"Algunos clips de video IA fallaron — esas "
                            f"escenas usan imagen animada. {videogen_warning}")
    save_scenes(project, scenes)
