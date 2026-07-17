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


def _semantic_map(llm, scenes: list[dict], assets: list[dict],
                  lang: str) -> dict[int, int]:
    """Asigna cada B-roll del usuario a la escena cuya narración ilustra,
    usando las descripciones de visión de la ingesta. Devuelve
    {índice_escena: índice_asset}. Un asset por escena; el material que no
    encaja en ninguna parte no se fuerza (mejor generar que descolocar)."""
    listing = "\n".join(
        f"- asset {i}: [{a['kind']}] {a.get('description') or a['name']}"
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


def _assign_user_asset(scene: dict, asset: dict, project, broll_dir: Path) -> None:
    src = project.path("input", asset["file"])
    if asset["kind"] == "image":
        dest = broll_dir / f"scene_{scene['id']:03d}{Path(asset['file']).suffix}"
        if not dest.exists():
            shutil.copy(src, dest)
        scene["broll_image"] = dest.name
        scene.pop("broll_video", None)
    else:  # video propio: clip + fotograma para miniatura/respaldo
        clip = broll_dir / f"scene_{scene['id']:03d}{Path(asset['file']).suffix}"
        if not clip.exists():
            shutil.copy(src, clip)
        frame = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if not frame.exists():
            run_ffmpeg(["-i", str(clip), "-frames:v", "1", "-q:v", "3",
                        str(frame)], "fotograma b-roll propio")
        scene["broll_video"] = clip.name
        scene["broll_image"] = frame.name
    scene["broll_source"] = "user"


def run(project, cfg) -> None:
    images = get_images(cfg)
    videogen = get_videogen(cfg)
    scenes = load_scenes(project)
    broll_dir = project.path("broll")

    # 1) B-roll propio del creador: asignación SEMÁNTICA (cada material va a
    #    la escena cuya narración ilustra, según su descripción de visión).
    #    Si no hay IA disponible, reparto uniforme como respaldo.
    user_assets = _user_broll_assets(project)
    mapping: dict[int, int] | None = None
    llm = get_llm(cfg)
    if user_assets and not getattr(llm, "is_mock", False):
        try:
            mapping = _semantic_map(llm, scenes, user_assets,
                                    cfg.get("language", "es"))
            unused = [a["name"] for i, a in enumerate(user_assets)
                      if i not in mapping.values()]
            if unused:
                project.add_warning(
                    "B-roll propio sin usar (no encajaba con ninguna escena "
                    "del guion): " + ", ".join(unused))
        except Exception as e:
            project.add_warning(f"Asignación inteligente de B-roll no "
                                f"disponible (reparto uniforme): {e}")
    if mapping is None:
        mapping = _spread(len(user_assets), len(scenes))
    for scene_idx, asset_idx in mapping.items():
        _assign_user_asset(scenes[scene_idx], user_assets[asset_idx],
                           project, broll_dir)

    # 2) IA para las escenas sin material propio — EN PARALELO: cada imagen o
    #    clip es una llamada de red independiente; generarlos en serie era el
    #    mayor cuello de botella del pipeline (mismo costo, mucho menos tiempo).
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ytstudio.progress import notify

    perf = cfg.get("performance", {})
    img_workers = max(1, int(perf.get("parallel_images", 4)))
    if cfg["providers"]["images"].get("name") == "replicate":
        # con crédito bajo Replicate limita a 6/min: más hilos solo generan 429
        img_workers = min(img_workers, 2)
    vid_workers = max(1, int(perf.get("parallel_video", 2)))

    ai_scenes = [s for s in scenes if s.get("broll_source") != "user"]

    # 2a) Imágenes (obligatorias: un fallo detiene la fase, reanudable)
    def _gen_image(scene: dict) -> None:
        img = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if not img.exists():  # reanudable
            images.generate(scene["broll_prompt"], img)

    todo_imgs = [s for s in ai_scenes
                 if not (broll_dir / f"scene_{s['id']:03d}.jpg").exists()]
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

    # 2b) Clips de video IA (opcionales: cada fallo degrada ESA escena a
    #     imagen animada, sin detener el proyecto)
    video_scenes = [s for s in ai_scenes if s.get("broll_type") == "video"]
    videogen_warning = None
    if video_scenes and videogen is not None:
        def _gen_clip(scene: dict) -> None:
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
