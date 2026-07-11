"""Estado del proyecto: carpeta por video, project.json reanudable."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ytstudio.config import ROOT

PROJECTS_DIR = ROOT / "projects"

# Subcarpetas estándar de un proyecto (una por fase con artefactos)
DIRS = {
    "input": "01_input",
    "concept": "02_concept",
    "script": "03_script",
    "scenes": "04_scenes",
    "voiceover": "05_voiceover",
    "broll": "06_broll",
    "music": "07_music",
    "subtitles": "08_subtitles",
    "final": "09_final",
}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", text).strip("-")[:60] or "proyecto"


class Project:
    def __init__(self, slug: str):
        self.slug = slug
        self.dir = PROJECTS_DIR / slug
        self.state_path = self.dir / "project.json"
        self.state: dict = {"slug": slug, "phases": {}, "data": {}}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())

    # --- rutas ---
    def path(self, key: str, *parts: str) -> Path:
        p = self.dir / DIRS[key]
        p.mkdir(parents=True, exist_ok=True)
        return p.joinpath(*parts) if parts else p

    # --- estado ---
    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2)
        )

    def phase_status(self, phase: str) -> str:
        return self.state["phases"].get(phase, {}).get("status", "pending")

    def mark_phase(self, phase: str, status: str, **info) -> None:
        entry = self.state["phases"].setdefault(phase, {})
        entry["status"] = status
        entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        entry.update(info)
        self.save()

    def reset_from(self, phase: str, order: list[str]) -> None:
        """Invalida una fase y todas las posteriores (para re-ejecutar)."""
        if phase not in order:
            raise ValueError(f"Fase desconocida: {phase}")
        for p in order[order.index(phase):]:
            self.state["phases"].pop(p, None)
        self.save()

    # --- datos compartidos entre fases ---
    def get(self, key: str, default=None):
        return self.state["data"].get(key, default)

    def set(self, key: str, value) -> None:
        self.state["data"][key] = value
        self.save()

    @classmethod
    def create(cls, slug: str) -> "Project":
        p = cls(slug)
        p.dir.mkdir(parents=True, exist_ok=True)
        for d in DIRS.values():
            (p.dir / d).mkdir(exist_ok=True)
        p.save()
        return p

    @classmethod
    def exists(cls, slug: str) -> bool:
        return (PROJECTS_DIR / slug / "project.json").exists()
