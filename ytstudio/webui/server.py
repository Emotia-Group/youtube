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
from ytstudio.pipeline import PHASE_LABELS, PHASE_ORDER, PHASES, run_pipeline
from ytstudio.project import DIRS, PROJECTS_DIR, Project, slugify

STATIC_DIR = Path(__file__).parent / "static"


def get_version() -> dict:
    """Identifica exactamente qué código está corriendo este servidor —
    para poder verificar desde la propia UI si un 'git pull' surtió efecto."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cd", "--date=format:%d %b %H:%M"],
            cwd=ROOT, capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        commit, date = out.split("|", 1)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, timeout=3).stdout.strip()
        return {"commit": commit, "date": date, "modified": bool(dirty)}
    except Exception:
        return {"commit": "desconocido", "date": "", "modified": False}

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
    out = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if not (p / "project.json").exists():
            continue
        try:  # un proyecto dañado no debe tumbar toda la lista
            out.append(_project_summary(p.name))
        except Exception as e:
            traceback.print_exc()
            out.append({"slug": p.name, "phases": {}, "done": 0,
                        "total": len(PHASE_ORDER), "running": False,
                        "error": f"No se pudo leer: {e}"})
    return out


def api_create_project(body: dict) -> dict:
    from ytstudio.phases.ingest import add_asset, set_text_input

    slug = slugify(body.get("slug") or "")
    if not slug:
        raise ApiError(400, "Falta el nombre del proyecto.")
    if Project.exists(slug):
        raise ApiError(409, f"El proyecto '{slug}' ya existe.")

    text = (body.get("text") or "").strip()
    files = body.get("files") or []  # [{name, data_base64, category}]
    if not text and not files:
        raise ApiError(400, "Escribe un texto o adjunta al menos un archivo.")

    project = Project.create(slug)
    if text:
        set_text_input(project, text)
    for f in files:
        try:
            add_asset(project, Path(Path(f["name"]).name),
                      f.get("category", "auto"),
                      data=base64.b64decode(f["data_base64"]))
        except ValueError as e:
            raise ApiError(400, str(e))

    # Preset de estilo por proyecto (override del global)
    preset = body.get("style_preset")
    if preset and preset in STYLE_PRESETS:
        (project.dir / "config.yaml").write_text(
            yaml.safe_dump({"style": {"preset": preset}}, allow_unicode=True), encoding="utf-8")
    return {"slug": slug, "assets": project.get("assets") or []}


def api_add_assets(slug: str, body: dict) -> dict:
    from ytstudio.phases.ingest import add_asset

    project = Project(slug)
    for f in body.get("files") or []:
        try:
            add_asset(project, Path(Path(f["name"]).name),
                      f.get("category", "auto"),
                      data=base64.b64decode(f["data_base64"]))
        except ValueError as e:
            raise ApiError(400, str(e))
    # Material nuevo → hay que reanalizar desde el principio
    project.reset_from("ingest", PHASE_ORDER)
    return {"assets": project.get("assets") or []}


def api_delete_asset(slug: str, asset_id: int) -> dict:
    from ytstudio.phases.ingest import remove_asset

    project = Project(slug)
    remove_asset(project, asset_id)
    project.reset_from("ingest", PHASE_ORDER)
    return {"assets": project.get("assets") or []}


def api_delete_project(slug: str) -> dict:
    import shutil
    if RUNS.get(slug, {}).get("running"):
        raise ApiError(409, "No se puede borrar mientras se está generando.")
    project = Project(slug)
    if not project.dir.exists():
        raise ApiError(404, "El proyecto no existe.")
    shutil.rmtree(project.dir)
    RUNS.pop(slug, None)
    return {"deleted": slug}


def api_save_keys(body: dict) -> dict:
    """Guarda claves de API en .env (merge línea a línea) y en el proceso."""
    import os
    allowed = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY",
               "REPLICATE_API_TOKEN"}
    updates = {k: v.strip() for k, v in (body.get("keys") or {}).items()
               if k in allowed and isinstance(v, str) and v.strip()}
    if not updates:
        raise ApiError(400, "No hay claves para guardar.")

    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    for key, value in updates.items():
        pattern = re.compile(rf"^\s*{key}\s*=")
        replaced = False
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            lines.append(f"{key}={value}")
        os.environ[key] = value
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"saved": True, "keys": key_status()}


def api_project_detail(slug: str) -> dict:
    project = Project(slug)
    detail = _project_summary(slug)
    detail["phase_info"] = project.state.get("phases", {})
    detail["assets"] = project.get("assets") or []
    detail["has_text_input"] = bool(project.get("has_text_input"))
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
            raise ApiError(409, "Ya se está generando este proyecto.")
        state = {"running": True, "lines": [], "error": None, "phase": None}
        RUNS[slug] = state

    from_phase = body.get("from") or None
    to_phase = body.get("to") or None

    def log(msg: str) -> None:
        state["lines"].append(str(msg))
        m = re.match(r"▶ (\w+)", str(msg))
        if m:  # fase actualmente en ejecución (para resaltarla en la UI)
            state["phase"] = m.group(1)
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
            state["phase"] = None

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
        "version": get_version(),
        "phases": [{"name": n, "desc": d, "label": PHASE_LABELS.get(n, n)}
                   for n, _, d in PHASES],
    }


def api_save_config(body: dict) -> dict:
    cfg = body.get("config")
    if not isinstance(cfg, dict):
        raise ApiError(400, "Config inválida.")
    # Se guarda en config.local.yaml (fuera de Git) — nunca en config.yaml,
    # que es parte del repositorio y un 'git pull' lo sobreescribiría.
    (ROOT / "config.local.yaml").write_text(
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

    def _serve_file(self, path: Path, no_cache: bool = False) -> None:
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
        # La SPA (index.html) nunca debe quedar cacheada por el navegador —
        # si no, un git pull en el servidor puede seguir mostrando la UI
        # vieja hasta que se fuerce un refresco manual.
        if no_cache:
            self.send_header("Cache-Control", "no-store, must-revalidate")
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
                self._serve_file(STATIC_DIR / "index.html", no_cache=True)
            elif path == "/api/catalog" or path == "/api/config":
                self._json(api_get_config())
            elif path == "/api/projects":
                self._json(api_list_projects())
            elif m := re.fullmatch(r"/api/projects/([\w-]+)", path):
                self._json(api_project_detail(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/log", path):
                run = RUNS.get(m.group(1),
                               {"running": False, "lines": [], "error": None,
                                "phase": None})
                self._json({k: run.get(k) for k in
                            ("running", "lines", "error", "phase")})
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
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/assets", path):
                self._json(api_add_assets(m.group(1), self._body()))
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
            elif path == "/api/keys":
                self._json(api_save_keys(self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/script", path):
                self._json(api_save_script(m.group(1), self._body()))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_DELETE(self):
        try:
            path = self.path.split("?")[0]
            if m := re.fullmatch(r"/api/projects/([\w-]+)/assets/(\d+)", path):
                self._json(api_delete_asset(m.group(1), int(m.group(2))))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)", path):
                self._json(api_delete_project(m.group(1)))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"🎬 ytstudio UI → {url}")
    print("   (deja esta ventana abierta; Ctrl+C para detener)")
    if open_browser:
        import webbrowser
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
