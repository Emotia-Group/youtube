"""Estado del proyecto: carpeta por video, project.json reanudable."""
from __future__ import annotations

import json
import re
import time
import unicodedata
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
    """Nombre de carpeta a partir de un título, SIN acentos ni eñes.

    El nombre bonito (con sus tildes) se guarda aparte en `display_name` y es
    el que se ve en pantalla: aquí solo se fabrica el nombre de la CARPETA.

    Por qué se quitan los acentos: ese texto acaba siendo una carpeta en el
    disco y una dirección web. Un proyecto llamado «conservó-la-fortuna»
    viajaba del navegador al servidor como «conserv%C3%B3-la-fortuna» y
    dejaba de encontrarse; y las carpetas con acentos dan guerra además en
    Windows y en Git según la codificación del equipo. Con nombres simples
    no hay nada que pueda torcerse.

    Los proyectos que YA existen con acentos siguen funcionando: el servidor
    descodifica la dirección antes de buscarlos."""
    # NFKD separa la letra de su tilde («ó» -> «o» + acento) y luego se
    # descartan los acentos sueltos. La ñ se trata igual (-> n).
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    # Lo que no sea a-z, 0-9, guion o espacio (alfabetos no latinos, símbolos
    # raros) se cambia por un guion. Un título escrito ENTERO en otro
    # alfabeto acabaría en «proyecto»: quien lo cree recibe un aviso de
    # nombre repetido y puede ponerle uno en el alfabeto latino.
    text = re.sub(r"[^a-z0-9_\s-]", "-", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")[:60] or "proyecto"


def read_json_tolerant(path) -> dict:
    """Lee un JSON aunque venga en una codificación antigua. Los archivos de
    proyecto creados por versiones previas (antes de forzar UTF-8) quedaron en
    cp1252 en Windows; se leen con fallback y se devuelven como dict."""
    from pathlib import Path as _P
    raw = _P(path).read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    # Último recurso: reemplazar bytes inválidos para no perder el proyecto
    return json.loads(raw.decode("utf-8", errors="replace"))


class Project:
    def __init__(self, slug: str):
        self.slug = slug
        self.dir = PROJECTS_DIR / slug
        self.state_path = self.dir / "project.json"
        self.state: dict = {"slug": slug, "phases": {}, "data": {},
                            "created_at": time.time(), "display_name": slug}
        if self.state_path.exists():
            self.state = read_json_tolerant(self.state_path)
            if not self.state.get("created_at"):
                # Proyectos de versiones anteriores no tienen fecha de creación
                # guardada: se usa la fecha de la carpeta como aproximación
                # razonable (en Windows st_ctime SÍ es la fecha de creación).
                try:
                    self.state["created_at"] = self.dir.stat().st_ctime
                except OSError:
                    self.state["created_at"] = 0
            if not self.state.get("display_name"):
                self.state["display_name"] = slug
            # Re-guardar en UTF-8 para migrar los proyectos antiguos de una vez
            try:
                self.save()
            except Exception:
                pass

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
        , encoding="utf-8")

    def phase_status(self, phase: str) -> str:
        return self.state["phases"].get(phase, {}).get("status", "pending")

    def mark_phase(self, phase: str, status: str, **info) -> None:
        entry = self.state["phases"].setdefault(phase, {})
        entry["status"] = status
        entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        entry.update(info)
        self.save()

    def add_warning(self, msg: str) -> None:
        """Acumula un aviso no fatal (ej. un proveedor opcional que falló) para
        mostrarlo en la interfaz sin detener el proyecto."""
        warnings = self.state["data"].setdefault("warnings", [])
        if msg not in warnings:
            warnings.append(msg)
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
