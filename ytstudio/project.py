"""Estado del proyecto: carpeta por video, project.json reanudable."""
from __future__ import annotations

import json
import os
import re
import threading
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
    cp1252 en Windows; se leen con fallback y se devuelven como dict.

    Además REINTENTA si el archivo llega a medias: mientras se genera un video,
    el motor guarda el estado cada pocos segundos y la interfaz lo lee cada
    segundo y medio. Si la lectura caía justo en mitad de la escritura, el
    programa contestaba «El servidor respondió con error» sin que nada
    estuviera roto de verdad. Ahora se espera un instante y se vuelve a leer.
    """
    from pathlib import Path as _P
    ruta = _P(path)
    ultimo: Exception | None = None
    for intento in range(4):
        raw = ruta.read_bytes()
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                return json.loads(raw.decode(enc))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                ultimo = e
                continue
        try:  # último recurso: reemplazar bytes inválidos, no perder el proyecto
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            ultimo = e
        time.sleep(0.05 * (intento + 1))
    raise ultimo


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
        """Guarda el estado ENTERO de una vez.

        Escribir directamente sobre project.json lo dejaba vacío durante un
        instante en cada guardado. La interfaz, que pregunta por el proyecto
        cada segundo y medio mientras se genera, caía a veces justo en ese
        instante y mostraba un error de servidor a mitad de una corrida que iba
        bien. Ahora se escribe en un archivo aparte y se pone en su sitio de un
        solo golpe (os.replace es atómico también en Windows): quien lea, lee
        siempre la versión anterior completa o la nueva completa, nunca media.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        # El nombre del temporal lleva quién lo escribe: si el motor y la
        # interfaz guardan a la vez, cada uno usa el suyo y no se pisan.
        tmp = self.state_path.with_name(
            f"{self.state_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self.state_path)
        finally:
            if tmp.exists():
                try: tmp.unlink()
                except OSError: pass

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
