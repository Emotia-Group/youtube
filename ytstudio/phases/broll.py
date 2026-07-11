"""FASE 6 — B-roll: genera con IA la imagen (o clip de video) de cada escena
según su broll_prompt y el estilo visual del concepto."""
from __future__ import annotations

from ytstudio.phases.scenes import load_scenes, save_scenes
from ytstudio.providers import get_images, get_videogen


def run(project, cfg) -> None:
    images = get_images(cfg)
    videogen = get_videogen(cfg)
    scenes = load_scenes(project)
    broll_dir = project.path("broll")

    for scene in scenes:
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
