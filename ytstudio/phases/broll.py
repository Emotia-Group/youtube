"""FASE 6 — B-roll: asigna primero los archivos propios del creador
(categoría 'broll') repartidos uniformemente entre las escenas y genera con
IA la imagen (o clip) de las escenas restantes."""
from __future__ import annotations

import shutil
from pathlib import Path

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_images, get_llm, get_videogen
from ytstudio.utils.media import run_ffmpeg


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


# Palabras que suelen disparar el filtro de seguridad en contenido histórico
_SOFTEN = {
    "blood": "", "bloody": "", "gore": "", "gory": "", "corpse": "statue",
    "dead body": "fallen figure", "death": "history", "dead": "ancient",
    "kill": "defeat", "killing": "conflict", "slaughter": "clash",
    "massacre": "great battle", "naked": "robed", "nude": "clothed",
    "violence": "drama", "violent": "intense", "wound": "mark",
    "wounded": "weary", "severed": "broken",
}


def _soften_prompt(prompt: str) -> str:
    """Suaviza un prompt marcado como sensible: reemplaza términos crudos por
    equivalentes tolerables y añade señales de contenido apto, sin perder el
    tema histórico/documental."""
    import re
    out = prompt
    for bad, good in _SOFTEN.items():
        out = re.sub(rf"\b{re.escape(bad)}\b", good, out, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out).strip(" ,")
    return ("tasteful, safe-for-work, non-graphic historical documentary "
            "illustration, no gore, no nudity, artistic and respectful. " + out)


def _fallback_image(out: Path, cfg: dict, palette: list[str]) -> Path:
    """Fondo cinematográfico neutro (degradado oscuro con viñeta y grano sutil),
    sin texto — para una escena cuya imagen fue rechazada. Se ve como un plano
    atmosférico, no como un error."""
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
        schema=schema, max_tokens=16000, purpose="broll_semantic")
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
    shape = "vertical" if vertical else "wide horizontal"
    full_prompt = (
        f"{prompt}. Reframe as a {shape} medium shot of this exact person: "
        "head and shoulders fully visible, centered, looking at the camera, "
        "same clothing and appearance, natural coherent background")
    try:
        notify("🧑 La foto del personaje no coincide con el formato del video: "
               "el director la reencuadra con el modelo de identidad…")
        ref_images.generate_with_refs(full_prompt, [img], dest)
        return dest if dest.exists() else None
    except Exception as e:
        notify(f"⚠ No se pudo reencuadrar la foto del personaje con IA ({e}) "
               "— se compondrá la foto entera sobre fondo desenfocado.")
        return None


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
    audio de su escena (vo_XXX.mp3, cortado de la pista única de voz). El clip
    entra al montaje como video MUDO — la voz la pone la pista continua, así
    que los labios quedan en sincronía sin tocar el motor de tiempos.

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

    def _still_fallback(targets: list[dict]) -> None:
        import shutil as _sh
        dest = broll_dir / f"personaje{img.suffix.lower() or '.jpg'}"
        if not dest.exists():
            _sh.copyfile(img, dest)
        # Foto con aspecto muy distinto al video → el director intenta
        # reencuadrarla con IA (identidad); si no, el montaje la compone
        # entera sobre fondo desenfocado — la cara nunca se corta.
        prompt = next((s.get("broll_prompt") for s in targets
                       if s.get("broll_prompt")),
                      "portrait of the narrator speaking to the camera")
        wide = _reframe_character_still(dest, prompt, broll_dir, cfg)
        use = wide or dest
        for s in targets:
            s["broll_image"] = use.name
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
    todo = [s for s in char_scenes
            if not (broll_dir / f"lipsync_{s['id']:03d}.mp4").exists()]
    if todo:
        notify(f"🧑 Generando {len(todo)} escena(s) de PERSONAJE con lipsync "
               f"({ls.model.split('/')[-1]}, {workers} en paralelo — tarda "
               "minutos por clip)…")

    from ytstudio.progress import get_sink
    sink = get_sink()

    def _gen(s: dict) -> None:
        usage_mod.bind(usage_items)
        _bind_worker_logging(sink)
        clip = broll_dir / f"lipsync_{s['id']:03d}.mp4"
        if clip.exists():  # reanudable
            return
        vo = vo_dir / f"vo_{s['id']:03d}.mp3"
        if not vo.exists():
            raise RuntimeError(f"Falta el audio de la escena {s['id']} "
                               "(rehaz desde Voz).")
        ls.generate(img, vo, clip, seconds=float(s.get("duration") or 5))

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
    if cfg["providers"]["images"].get("name") == "replicate":
        # con crédito bajo Replicate limita a 6/min: más hilos solo generan 429
        img_workers = min(img_workers, 2)
    vid_workers = max(1, int(perf.get("parallel_video", 2)))

    ai_scenes = [s for s in scenes
                 if s.get("broll_source") not in ("user", "manual", "lipsync")]

    # 2a) Imágenes. Un fallo de INFRAESTRUCTURA (auth, red) detiene la fase
    #     (reanudable). Un rechazo de CONTENIDO (NSFW) de UNA imagen no puede
    #     tumbar todo el proyecto: se reintenta con el prompt suavizado y, si
    #     persiste, se usa un fondo cinematográfico neutro para esa escena.
    concept = project.get("concept") or {}
    palette = (concept.get("visual_style") or {}).get("palette") or []
    nsfw_scenes: list[int] = []

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

    def _gen_one(scene: dict, prompt: str, img: Path) -> None:
        """Escalera de UNA imagen: identidad (si hay elenco) → normal →
        prompt suavizado → fondo neutro. La usan la imagen principal y la
        segunda mitad de las escenas con pantalla dividida."""
        # Escena con personajes del elenco → modelo de IDENTIDAD con sus
        # fotos de referencia (misma cara en todas sus escenas).
        refs = _scene_refs(scene)
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
        # Rechazo de contenido: reintento con prompt suavizado
        try:
            images.generate(_soften_prompt(prompt), img)
            return
        except Exception as e:
            if not _is_content_error(e):
                raise
        # Sigue rechazado: fondo cinematográfico neutro (el video se completa)
        _fallback_image(img, cfg, palette)
        nsfw_scenes.append(scene["id"])

    def _gen_image(scene: dict) -> None:
        usage_mod.bind(usage_items)
        _bind_worker_logging(sink)
        img = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if not img.exists():  # reanudable
            _gen_one(scene, scene["broll_prompt"], img)
        # Pantalla dividida: la SEGUNDA mitad tiene su propia imagen
        if scene.get("layout") == "dividida" and scene.get("broll_prompt_b"):
            img_b = broll_dir / f"scene_{scene['id']:03d}_b.jpg"
            if not img_b.exists():
                _gen_one(scene, scene["broll_prompt_b"], img_b)
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
    if nsfw_scenes:
        project.add_warning(
            "El generador marcó como sensible el prompt de "
            f"{len(nsfw_scenes)} escena(s) ({', '.join(map(str, nsfw_scenes))}) "
            "y usó un fondo neutro. Puedes reformular ese texto del guion y "
            "«Rehacer desde Imágenes», o subir tu propio B-roll para esas "
            "escenas.")

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
