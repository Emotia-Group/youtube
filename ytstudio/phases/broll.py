"""FASE 6 — B-roll: asigna primero los archivos propios del creador
(categoría 'broll') repartidos uniformemente entre las escenas y genera con
IA la imagen (o clip) de las escenas restantes."""
from __future__ import annotations

import shutil
from pathlib import Path

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_images, get_videogen
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

    # 1) B-roll propio del creador, repartido uniformemente
    user_assets = _user_broll_assets(project)
    mapping = _spread(len(user_assets), len(scenes))
    for scene_idx, asset_idx in mapping.items():
        _assign_user_asset(scenes[scene_idx], user_assets[asset_idx],
                           project, broll_dir)

    # 2) IA para las escenas sin material propio
    for scene in scenes:
        if scene.get("broll_source") == "user":
            continue
        img = broll_dir / f"scene_{scene['id']:03d}.jpg"
        if not img.exists():  # reanudable
            images.generate(scene["broll_prompt"], img)
        scene["broll_image"] = img.name

        if scene.get("broll_type") == "video" and videogen is not None:
            clip = broll_dir / f"scene_{scene['id']:03d}.mp4"
            if not clip.exists():
                # imagen como fotograma inicial → coherencia visual del clip
                videogen.generate(scene["broll_prompt"], clip, image=img)
            scene["broll_video"] = clip.name
        else:
            scene["broll_type"] = "image"
            scene.pop("broll_video", None)

    save_scenes(project, scenes)
