"""Interfaz web local de ytstudio.

Servidor HTTP (stdlib, sin dependencias extra) que expone una API REST sobre
el pipeline y sirve la SPA de ytstudio/webui/static/. Ejecución:

    python -m ytstudio ui [--port 8765]

El pipeline corre en un hilo en segundo plano por proyecto; la UI hace
polling del estado y del log.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

from ytstudio.catalog import CATALOG, STYLE_PRESETS, key_status
from ytstudio.config import ROOT, load_config
from ytstudio.pipeline import PHASE_ORDER, PHASES, run_pipeline
from ytstudio.project import DIRS, PROJECTS_DIR, Project, slugify

STATIC_DIR = Path(__file__).parent / "static"

# Estado de las ejecuciones en curso: slug -> {running, lines, error}
RUNS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Lógica de la API
# ---------------------------------------------------------------------------

def _project_summary(slug: str) -> dict:
    project = Project(slug)
    phases = {name: project.phase_status(name) for name in PHASE_ORDER}
    run = RUNS.get(slug, {})
    return {
        "slug": slug,
        "phases": phases,
        "done": sum(1 for s in phases.values() if s == "done"),
        "total": len(PHASE_ORDER),
        "running": bool(run.get("running")),
        "input_meta": project.get("input_meta"),
        "total_duration": project.get("total_duration"),
        "scene_count": project.get("scene_count"),
    }


def api_list_projects() -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []
    return [_project_summary(p.name) for p in sorted(PROJECTS_DIR.iterdir())
            if (p / "project.json").exists()]


def api_create_project(body: dict) -> dict:
    from ytstudio.phases.ingest import stage_input

    slug = slugify(body.get("slug") or "")
    if not slug:
        raise ApiError(400, "Falta el nombre del proyecto.")
    if Project.exists(slug):
        raise ApiError(409, f"El proyecto '{slug}' ya existe.")

    text = body.get("text") or None
    file_info = body.get("file")  # {name, data_base64}
    if not text and not file_info:
        raise ApiError(400, "Indica un texto o adjunta un archivo.")

    project = Project.create(slug)
    source = None
    if file_info:
        name = Path(file_info["name"]).name  # sin rutas
        source = project.path("input") / name
        source.write_bytes(base64.b64decode(file_info["data_base64"]))
        text = None
    try:
        meta = stage_input(project, source, text, body.get("type", "auto"))
    except ValueError as e:
        raise ApiError(400, str(e))

    # Preset de estilo por proyecto (override del global)
    preset = body.get("style_preset")
    if preset and preset in STYLE_PRESETS:
        (project.dir / "config.yaml").write_text(
            yaml.safe_dump({"style": {"preset": preset}}, allow_unicode=True), encoding="utf-8")
    return {"slug": slug, "input": meta}


def api_project_detail(slug: str) -> dict:
    project = Project(slug)
    detail = _project_summary(slug)
    detail["phase_info"] = project.state.get("phases", {})
    detail["concept"] = project.get("concept")
    detail["metadata"] = project.get("metadata")
    detail["brief"] = project.get("brief")

    script = project.dir / DIRS["script"] / "guion.md"
    detail["has_script"] = script.exists()

    scenes_file = project.dir / DIRS["scenes"] / "scenes.json"
    if scenes_file.exists():
        detail["scenes"] = json.loads(scenes_file.read_text(encoding="utf-8"))["scenes"]
    final = project.dir / DIRS["final"] / "video_final.mp4"
    detail["final_video"] = f"{DIRS['final']}/video_final.mp4" if final.exists() else None
    thumb = project.dir / DIRS["final"] / "miniatura.jpg"
    detail["thumbnail"] = f"{DIRS['final']}/miniatura.jpg" if thumb.exists() else None
    meta_file = project.dir / DIRS["final"] / "metadata.json"
    if meta_file.exists():
        detail["metadata_full"] = json.loads(meta_file.read_text(encoding="utf-8"))
    return detail


def api_run(slug: str, body: dict) -> dict:
    with RUNS_LOCK:
        if RUNS.get(slug, {}).get("running"):
            raise ApiError(409, "El pipeline ya está en ejecución para este proyecto.")
        state = {"running": True, "lines": [], "error": None}
        RUNS[slug] = state

    from_phase = body.get("from") or None
    to_phase = body.get("to") or None

    def log(msg: str) -> None:
        state["lines"].append(str(msg))
        print(f"[{slug}] {msg}")

    def worker() -> None:
        try:
            project = Project(slug)
            cfg = load_config(project.dir)
            run_pipeline(project, cfg, from_phase=from_phase, to_phase=to_phase,
                         log=log)
            log("✅ Ejecución terminada.")
        except Exception as e:
            state["error"] = str(e)
            log(f"❌ {e}")
            traceback.print_exc()
        finally:
            state["running"] = False

    threading.Thread(target=worker, daemon=True).start()
    return {"started": True}


def api_get_script(slug: str) -> dict:
    path = Project(slug).dir / DIRS["script"] / "guion.md"
    if not path.exists():
        raise ApiError(404, "Aún no hay guion (ejecuta hasta la fase 'script').")
    return {"content": path.read_text(encoding="utf-8")}


def api_save_script(slug: str, body: dict) -> dict:
    project = Project(slug)
    path = project.path("script", "guion.md")
    path.write_text(body.get("content", ""), encoding="utf-8")
    # Editar el guion invalida las fases posteriores
    project.reset_from("scenes", PHASE_ORDER)
    project.mark_phase("script", "done", edited=True)
    return {"saved": True}


def api_get_config() -> dict:
    return {
        "config": load_config(),
        "catalog": CATALOG,
        "style_presets": STYLE_PRESETS,
        "keys": key_status(),
        "phases": [{"name": n, "desc": d} for n, _, d in PHASES],
    }


def api_save_config(body: dict) -> dict:
    cfg = body.get("config")
    if not isinstance(cfg, dict):
        raise ApiError(400, "Config inválida.")
    (ROOT / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"saved": True}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# Handler HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # --- utilidades ---
    def _json(self, data, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self._json({"error": "No encontrado"}, 404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        rng = self.headers.get("Range")
        if rng:  # soporte básico de Range para el <video> del navegador
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            start = int(m.group(1) or 0)
            end = int(m.group(2) or len(data) - 1)
            end = min(end, len(data) - 1)
            chunk = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _project_file(self, slug: str, rel: str) -> None:
        base = (PROJECTS_DIR / slug).resolve()
        target = (base / rel).resolve()
        if not str(target).startswith(str(base)):
            self._json({"error": "Ruta inválida"}, 403)
            return
        self._serve_file(target)

    def log_message(self, fmt, *args):  # silenciar el log por request
        pass

    # --- rutas ---
    def do_GET(self):
        try:
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._serve_file(STATIC_DIR / "index.html")
            elif path == "/api/catalog" or path == "/api/config":
                self._json(api_get_config())
            elif path == "/api/projects":
                self._json(api_list_projects())
            elif m := re.fullmatch(r"/api/projects/([\w-]+)", path):
                self._json(api_project_detail(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/log", path):
                run = RUNS.get(m.group(1), {"running": False, "lines": [], "error": None})
                self._json({k: run[k] for k in ("running", "lines", "error")})
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/script", path):
                self._json(api_get_script(m.group(1)))
            elif m := re.fullmatch(r"/files/([\w-]+)/(.+)", path):
                self._project_file(m.group(1), m.group(2))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        try:
            path = self.path.split("?")[0]
            if path == "/api/projects":
                self._json(api_create_project(self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/run", path):
                self._json(api_run(m.group(1), self._body()))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_PUT(self):
        try:
            path = self.path.split("?")[0]
            if path == "/api/config":
                self._json(api_save_config(self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/script", path):
                self._json(api_save_script(m.group(1), self._body()))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)


def serve(port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"🎬 ytstudio UI → http://localhost:{port}")
    print("   (Ctrl+C para detener)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
