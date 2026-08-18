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
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.parse
from urllib.parse import parse_qs, urlparse

import yaml

from ytstudio.catalog import (CATALOG, FORMATS, LANGUAGES,
                              OVERLAY_BRANDING_PRESETS, OVERLAY_FONT_FAMILIES,
                              SHORT_TEMPLATES, STYLE_PRESETS, key_status)
from ytstudio.config import ROOT, load_config
from ytstudio.pipeline import PHASE_LABELS, PHASE_ORDER, PHASES, run_pipeline
from ytstudio.utils.sfx import PALETTE_LABELS
from ytstudio.project import (DIRS, PROJECTS_DIR, Project, read_json_tolerant,
                             slugify)

STATIC_DIR = Path(__file__).parent / "static"


def archivos_modificados(porcelain: str) -> list[str]:
    """Rutas de `git status --porcelain`, completas.

    Cada línea trae 2 columnas de estado + un espacio antes de la ruta. OJO:
    NO se puede limpiar el bloque entero con .strip() antes de partirlo — se
    come el espacio inicial de la primera línea y con él la primera letra del
    archivo («.gitignore» salía como «gitignore»)."""
    return [ln[3:].strip() for ln in porcelain.splitlines()
            if len(ln) > 3 and ln[3:].strip()]


def get_version() -> dict:
    """Identifica exactamente qué código está corriendo este servidor —
    para poder verificar desde la propia UI si un 'git pull' surtió efecto.
    El número (SemVer: Mayor.Menor.Revisión, ej. v0.19.0) sale de la primera
    entrada de CHANGELOG.md; el commit y la hora local, de git."""
    import re
    import subprocess
    version = ""
    try:
        head = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:2000]
        m = re.search(r"^## (v\d+\.\d+\.\d+)", head, re.M)
        version = m.group(1) if m else ""
    except Exception:
        pass
    try:
        out = subprocess.run(
            # format-local: hora del sistema del usuario, no la del commit (UTC)
            ["git", "log", "-1", "--format=%h|%cd", "--date=format-local:%d %b %H:%M"],
            cwd=ROOT, capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        commit, date = out.split("|", 1)
        # QUÉ archivos, no solo «hay algo»: el aviso anterior era vago (sonaba
        # a «tu programa está desactualizado») y además saltaba por el
        # material propio del creador dentro de assets/. Ahora se nombran.
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, timeout=3).stdout
        archivos = archivos_modificados(dirty)
        return {"version": version, "commit": commit, "date": date,
                "modified": bool(archivos), "modified_files": archivos[:12],
                "modified_count": len(archivos)}
    except Exception:
        return {"version": version, "commit": "desconocido", "date": "",
                "modified": False, "modified_files": [], "modified_count": 0}


# Versión del CÓDIGO CARGADO en este proceso (capturada al arrancar). Tras un
# actualizar.bat, el disco tiene la versión nueva pero el proceso sigue siendo
# el viejo hasta reiniciar iniciar.bat — get_version() leería el CHANGELOG
# nuevo y engañaría. La UI compara ambas y pide reiniciar si difieren (antes
# el síntoma era críptico: rutas nuevas del API respondían «No encontrado»).
SERVER_VERSION = get_version().get("version", "")


# ---------------------------------------------------------------------------
# PLANTILLAS DE LA INTERFAZ
# ---------------------------------------------------------------------------
# El programa se ve de dos maneras distintas y el creador elige cuál usar sin
# perder la otra. Cada plantilla tiene SU archivo de interfaz, SU manual y SU
# juego de capturas: un manual con pantallas que no coinciden con lo que tienes
# delante enseña peor que no tener manual.

#
# Cada entrada lleva además con qué CARA se presenta en Ajustes: un nombre
# corto, una frase de qué es, unas líneas de en qué se nota, y los colores con
# los que la interfaz dibuja su miniatura. La miniatura se dibuja SOLA a partir
# de esos colores y del `layout` (barra arriba o barra lateral), así que una
# plantilla nueva solo tiene que añadirse aquí: no hay que tocar el selector ni
# guardar ninguna captura.

TEMPLATES: dict[str, dict] = {
    "nueva": {"label": "Nueva (editorial, clara u oscura)",
              "html": "index.html", "manual": "MANUAL.md",
              "shots": "nueva",
              "name": "Nueva",
              "tagline": "Editorial · clara u oscura",
              "desc": "Aire, tipografía de revista y la navegación arriba. "
                      "Es la única con modo claro, y la que mejor se ve en "
                      "pantallas anchas y en el móvil.",
              "bullets": ["Modo claro y modo oscuro",
                          "Menú arriba, ancho completo",
                          "Pensada para pantallas grandes y móvil"],
              "preview": {"layout": "top", "bg": "#f3f2f2",
                          "surface": "#eae9e9", "ink": "#201f1d",
                          "line": "#d8d5d2", "accent": "#b68235",
                          "radius": 2}},
    "clasica": {"label": "Clásica (oscura, la anterior)",
                "html": "index-clasica.html", "manual": "MANUAL-clasica.md",
                "shots": "clasica",
                "name": "Clásica",
                "tagline": "Oscura · la de siempre",
                "desc": "Barra lateral fija con la lista de proyectos siempre "
                        "a la vista, tarjetas redondeadas y color oscuro. Es "
                        "la interfaz con la que nació el programa.",
                "bullets": ["Siempre oscura",
                            "Lista de proyectos en la barra lateral",
                            "Todo a un clic, sin cambiar de pantalla"],
                "preview": {"layout": "side", "bg": "#0c0e13",
                            "surface": "#141821", "ink": "#e8eaf0",
                            "line": "#262d3d", "accent": "#f0b429",
                            "radius": 5}},
}
DEFAULT_TEMPLATE = "nueva"


def template_cards() -> list[dict]:
    """Lo que necesita el selector de Ajustes para pintar cada plantilla: cómo
    se llama, qué es, en qué se nota y con qué colores dibujar su miniatura."""
    return [{"id": k,
             "label": v["label"],
             "name": v.get("name") or v["label"],
             "tagline": v.get("tagline", ""),
             "desc": v.get("desc", ""),
             "bullets": list(v.get("bullets") or []),
             "preview": dict(v.get("preview") or {})}
            for k, v in TEMPLATES.items()]


def ui_template(cfg: dict | None = None) -> str:
    """Plantilla activa. Un valor desconocido en el config no puede dejar el
    programa sin interfaz: se cae a la de por defecto."""
    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = {}
    name = str(((cfg.get("ui") or {}).get("template") or "")).strip().lower()
    return name if name in TEMPLATES else DEFAULT_TEMPLATE


def api_set_ui_template(body: dict) -> dict:
    """Cambia la plantilla y la deja guardada en config.local.yaml (fuera de
    Git, como el resto de las preferencias)."""
    name = str(body.get("template") or "").strip().lower()
    if name not in TEMPLATES:
        raise ApiError(400, f"Plantilla desconocida: {name!r}. "
                            f"Opciones: {', '.join(TEMPLATES)}.")
    path = ROOT / "config.local.yaml"
    try:
        current = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        current = {}
    current.setdefault("ui", {})["template"] = name
    path.write_text(yaml.safe_dump(current, allow_unicode=True,
                                   sort_keys=False), encoding="utf-8")
    return {"template": name, "label": TEMPLATES[name]["label"]}


def manual_path(template: str | None = None) -> Path:
    """Archivo de manual de una plantilla. Si esa versión aún no existe, se
    sirve la general: mejor un manual con capturas de la otra interfaz que
    ningún manual."""
    tpl = TEMPLATES.get(template or ui_template(), TEMPLATES[DEFAULT_TEMPLATE])
    path = ROOT / tpl["manual"]
    return path if path.exists() else ROOT / "MANUAL.md"


def manual_version(template: str | None = None) -> str:
    """Versión que declara el MANUAL (marca MANUAL_VERSION). Sirve para avisar
    en la interfaz cuando el manual se quedó atrás respecto al programa — y
    para que la batería de pruebas lo detecte sola."""
    path = manual_path(template)
    if not path.exists():
        return ""
    m = re.search(r"MANUAL_VERSION:\s*([0-9]+\.[0-9]+\.[0-9]+)",
                  path.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def api_manual() -> dict:
    """El manual DE LA PLANTILLA ACTIVA + la versión que documenta y la del
    programa, para que la interfaz avise si se quedó desactualizado. Las
    versiones se comparan sin la «v» inicial: el CHANGELOG las escribe
    «v0.51.0» y la marca «0.51.0»."""
    tpl = ui_template()
    path = manual_path(tpl)
    prog = str((get_version() or {}).get("version", "")).lstrip("v")
    return {"content": path.read_text(encoding="utf-8") if path.exists() else "",
            "manual_version": manual_version(tpl),
            "program_version": prog,
            "template": tpl, "template_label": TEMPLATES[tpl]["label"]}


def api_changelog() -> dict:
    path = ROOT / "CHANGELOG.md"
    return {"content": path.read_text(encoding="utf-8") if path.exists() else ""}


def api_events(query: dict) -> dict:
    from ytstudio import eventlog
    project = (query.get("project") or [None])[0]
    try:
        limit = int((query.get("limit") or ["300"])[0])
    except ValueError:
        limit = 300
    return {"events": eventlog.recent(limit=min(2000, max(1, limit)),
                                      project=project)}


def api_estimate(slug: str) -> dict:
    from ytstudio.estimate import estimate
    project = Project(slug)
    cfg = load_config(project.dir)
    return estimate(project, cfg)


# --- Canales y estilos ------------------------------------------------------

def api_library() -> dict:
    from ytstudio import library
    return {"channels": library.list_channels(),
            "styles": library.list_styles()}


def api_channel_create(body: dict) -> dict:
    from ytstudio import library
    try:
        return library.create_channel(body.get("name", ""),
                                      body.get("description", ""))
    except ValueError as e:
        raise ApiError(400, str(e))


def api_channel_update(channel_id: str, body: dict) -> dict:
    from ytstudio import library
    try:
        return library.update_channel(channel_id, body.get("name"),
                                      body.get("description"))
    except ValueError as e:
        raise ApiError(400, str(e))


def api_channel_delete(channel_id: str) -> dict:
    from ytstudio import library
    library.delete_channel(channel_id)
    return {"deleted": True}


def api_style_create(body: dict) -> dict:
    from ytstudio import library
    try:
        return library.create_style(body)
    except ValueError as e:
        raise ApiError(400, str(e))


def api_style_update(style_id: str, body: dict) -> dict:
    from ytstudio import library
    try:
        return library.update_style(style_id, body)
    except ValueError as e:
        raise ApiError(400, str(e))


def api_style_delete(style_id: str) -> dict:
    from ytstudio import library
    library.delete_style(style_id)
    return {"deleted": True}


def api_save_style_from_project(slug: str, body: dict) -> dict:
    from ytstudio import library
    project = Project(slug)
    try:
        return library.save_style_from_project(
            project, body.get("name", ""), body.get("channel_id"))
    except ValueError as e:
        raise ApiError(400, str(e))

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
    failed = any((project.state["phases"].get(n) or {}).get("status") == "failed"
                for n in PHASE_ORDER)
    return {
        "slug": slug,
        "display_name": project.state.get("display_name") or slug,
        "created_at": project.state.get("created_at") or 0,
        "phases": phases,
        "done": sum(1 for s in phases.values() if s == "done"),
        "total": len(PHASE_ORDER),
        "running": bool(run.get("running")),
        "has_error": bool(run.get("error")) or failed,
        "input_meta": project.get("input_meta"),
        "total_duration": project.get("total_duration"),
        "scene_count": project.get("scene_count"),
        # MINIATURA Y FORMATO en el resumen (no solo en el detalle): sin esto
        # la Biblioteca y la lista de proyectos no tienen con qué pintar la
        # imagen del video, y todas las fichas salen vacías e iguales.
        "thumbnail": (f"{DIRS['final']}/miniatura.jpg"
                      if (project.dir / DIRS["final"] / "miniatura.jpg").exists()
                      else None),
        "format": project.get("format") or "long",
        "short_template": project.get("short_template"),
        "video_aspect": _project_aspect(project),
    }


def _project_aspect(project) -> dict:
    """Proporción REAL del proyecto, para que la ficha se vea como el video:
    un Reel como teléfono vertical, un anuncio cuadrado como cuadrado."""
    try:
        pv = load_config(project.dir).get("video", {})
        return {"w": int(pv.get("width", 1920)), "h": int(pv.get("height", 1080))}
    except Exception:
        return {"w": 1920, "h": 1080}


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
            out.append({"slug": p.name, "display_name": p.name, "created_at": 0,
                        "phases": {}, "done": 0, "total": len(PHASE_ORDER),
                        "running": False, "has_error": True,
                        "error": f"No se pudo leer: {e}"})
    # Más reciente primero — antes salían por orden alfabético del slug.
    out.sort(key=lambda s: s.get("created_at") or 0, reverse=True)
    return out


def api_duplicate_project(slug: str, body: dict | None = None) -> dict:
    body = body or {}
    import shutil
    src = Project(slug)
    if not src.state_path.exists():
        raise ApiError(404, "Proyecto no encontrado.")
    if RUNS.get(slug, {}).get("running"):
        raise ApiError(409, "Espera a que termine de generarse antes de duplicarlo.")
    # El nombre se pide ANTES de duplicar (en la UI) para que el slug interno
    # —el que aparece en el Log de eventos y en las rutas de archivos— nazca
    # ya con el nombre elegido, en vez de encadenar «-copia-copia-copia» y
    # dejarlo enterrado bajo un nombre visible distinto.
    wanted_name = (body.get("name") or "").strip()
    base = slugify(wanted_name) if wanted_name else f"{slug}-copia"
    new_slug = base
    i = 2
    while Project.exists(new_slug):
        new_slug = f"{base}-{i}"
        i += 1
    shutil.copytree(src.dir, PROJECTS_DIR / new_slug)
    dup = Project(new_slug)
    dup.state["slug"] = new_slug
    dup.state["created_at"] = time.time()
    dup.state["display_name"] = (
        wanted_name or f"{src.state.get('display_name') or slug} (copia)")
    dup.save()
    return {"slug": new_slug}


def api_rename_project(slug: str, body: dict) -> dict:
    project = Project(slug)
    if not project.state_path.exists():
        raise ApiError(404, "Proyecto no encontrado.")
    name = (body.get("name") or "").strip()
    if not name:
        raise ApiError(400, "Escribe un nombre.")
    project.state["display_name"] = name[:120]
    project.save()
    return {"display_name": project.state["display_name"]}


def api_create_project(body: dict) -> dict:
    from ytstudio.phases.ingest import add_asset, set_text_input

    slug = slugify(body.get("slug") or "")
    if not slug:
        raise ApiError(400, "Falta el nombre del proyecto.")
    if Project.exists(slug):
        raise ApiError(409, f"El proyecto '{slug}' ya existe.")

    text = (body.get("text") or "").strip()
    files = body.get("files") or []  # [{name, data_base64, category}]
    links = [u.strip() for u in (body.get("links") or [])
             if u.strip().startswith(("http://", "https://"))]
    if not text and not files and not links:
        raise ApiError(400, "Escribe un texto o adjunta al menos un archivo.")

    project = Project.create(slug)
    if text:
        set_text_input(project, text)
    if links:
        project.set("links", links)
    if body.get("channel_id"):
        project.set("channel_id", body["channel_id"])
    if body.get("style_id"):
        project.set("style_id", body["style_id"])
    for f in files:
        try:
            add_asset(project, Path(Path(f["name"]).name),
                      f.get("category", "auto"),
                      data=base64.b64decode(f["data_base64"]))
        except ValueError as e:
            raise ApiError(400, str(e))
    # Personaje narrador: % del video en que aparece haciendo lipsync
    if any(f.get("category") == "personaje" for f in files):
        try:
            pres = min(60, max(0, int(body.get("character_presence") or 30)))
        except (TypeError, ValueError):
            pres = 30
        project.set("character", {"presence": pres / 100,
                                  "pip": bool(body.get("character_pip"))})

    # Overrides POR PROYECTO (preset de estilo + formato) en su config.yaml —
    # load_config(project.dir) los mezcla sobre la config global al generar.
    overrides: dict = {}
    preset = body.get("style_preset")
    if preset and preset in STYLE_PRESETS:
        overrides["style"] = {"preset": preset}
    fmt = body.get("format") or "long"
    if fmt in FORMATS and FORMATS[fmt].get("overrides"):
        for k, v in FORMATS[fmt]["overrides"].items():
            sub = overrides.setdefault(k, {})
            sub.update(v)
    project.set("format", fmt)
    # Plantilla de formato (solo cortos): Top 3, historia con giro, etc.
    tpl = body.get("short_template") or "libre"
    if fmt != "long" and tpl in SHORT_TEMPLATES:
        project.set("short_template", tpl)
    if overrides:
        (project.dir / "config.yaml").write_text(
            yaml.safe_dump(overrides, allow_unicode=True), encoding="utf-8")
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
               "REPLICATE_API_TOKEN", "CARTESIA_API_KEY", "ASSEMBLYAI_API_KEY"}
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
    detail["warnings"] = project.get("warnings") or []
    detail["assets"] = project.get("assets") or []
    detail["has_text_input"] = bool(project.get("has_text_input"))
    detail["concept"] = project.get("concept")
    detail["metadata"] = project.get("metadata")
    detail["brief"] = project.get("brief")

    script = project.dir / DIRS["script"] / "guion.md"
    detail["has_script"] = script.exists()

    scenes_file = project.dir / DIRS["scenes"] / "scenes.json"
    if scenes_file.exists():
        detail["scenes"] = read_json_tolerant(scenes_file)["scenes"]
    from ytstudio.characters import narrator as _narr, roster as _roster
    detail["has_character"] = _narr(project) is not None
    detail["character"] = project.get("character") or {}
    by_id = {a["id"]: a for a in (project.get("assets") or [])}
    detail["characters_roster"] = [
        {**c, "files": [by_id[i]["file"] for i in (c.get("asset_ids") or [])
                        if i in by_id]}
        for c in _roster(project)]
    final = project.dir / DIRS["final"] / "video_final.mp4"
    detail["final_video"] = f"{DIRS['final']}/video_final.mp4" if final.exists() else None
    thumb = project.dir / DIRS["final"] / "miniatura.jpg"
    detail["thumbnail"] = f"{DIRS['final']}/miniatura.jpg" if thumb.exists() else None
    meta_file = project.dir / DIRS["final"] / "metadata.json"
    if meta_file.exists():
        detail["metadata_full"] = read_json_tolerant(meta_file)
    from ytstudio import usage
    usage_items = project.get("usage_items") or []
    detail["usage_report"] = usage.summarize(usage_items) if usage_items else None
    detail["time_report"] = project.get("time_report")
    detail["manual_broll"] = project.get("manual_broll") or {}
    detail["broll_auto_replace"] = bool(project.get("broll_auto_replace"))
    detail["broll_review"] = project.get("broll_review") is not False  # default on
    # Formato/plantilla y ASPECTO real del proyecto: la UI muestra el preview
    # (storyboard, editor y video) en la proporción verdadera — un Reel se ve
    # como teléfono 9:16, un Ad como cuadrado, no todo como 16:9.
    detail["format"] = project.get("format") or "long"
    detail["short_template"] = project.get("short_template")
    detail["video_aspect"] = _project_aspect(project)
    detail["shorts_audit"] = project.get("shorts_audit")
    detail["loudness"] = project.get("loudness")
    # DE DÓNDE SALIÓ (si es un Short derivado) y ADÓNDE APUNTA: sin esto se
    # pierde el enlace al video largo, que es todo el objetivo de la pieza.
    detail["derived_from"] = project.get("derived_from")
    detail["shorts_plan"] = project.get("shorts_plan")
    # LISTA DE COMPROBACIÓN de publicación (solo verticales): se calcula en
    # vivo para que refleje el título/descripción que el creador tenga
    # elegidos AHORA, no los de cuando corrió la fase de publicación.
    try:
        from ytstudio import shorts as _shorts
        cfg = load_config(project.dir)
        if _shorts.is_shorts_frame(cfg) and detail.get("final_video"):
            detail["publish_checklist"] = _shorts.publish_checklist(project, cfg)
    except Exception:
        detail["publish_checklist"] = project.get("publish_checklist")
    return detail


def _derive_source(body: dict):
    """De dónde sale el material: un proyecto de la casa o un enlace.

    Devuelve (source, cfg, nota). `nota` explica un cambio de plan — por
    ejemplo, que YouTube no dejó leer el enlace y se usó el material del
    propio proyecto, que es MEJOR fuente y no depende de la red."""
    from ytstudio import derive
    url = (body.get("url") or "").strip()
    slug = (body.get("slug") or "").strip()

    if url:
        try:
            return derive.source_from_url(url, load_config()), load_config(), ""
        except Exception as e:
            motivo = str(e)
            _log_derive("error", f"No se pudo leer el enlace {url}: {motivo}",
                        slug or None)
            # RESCATE: si el proyecto de la casa ya tiene escenas, su
            # material es más rico que unos subtítulos automáticos y no
            # depende de YouTube. Mejor eso que dejar al creador tirado.
            if slug:
                try:
                    source = derive.source_from_project(slug)
                except ValueError:
                    raise ApiError(400, motivo)
                nota = ("No se pudo leer el enlace de YouTube, así que los "
                        "Shorts se sacaron del material de ESTE proyecto, que "
                        "es incluso mejor fuente (tiene el guion exacto, no "
                        "subtítulos automáticos). Motivo del enlace: "
                        + motivo)
                _log_derive("warn", nota, slug)
                return source, load_config(Project(slug).dir), nota
            raise ApiError(400, motivo)

    if not slug:
        raise ApiError(400, "Indica un proyecto o pega el enlace del video "
                            "largo de YouTube.")
    try:
        source = derive.source_from_project(slug)
    except ValueError as e:
        raise ApiError(409, str(e))
    return source, load_config(Project(slug).dir), ""


def _log_derive(level: str, mensaje: str, slug: str | None = None) -> None:
    """Deja constancia en el 🧾 Log de eventos. Antes, un fallo al leer el
    video largo solo se veía en la ventana negra: la interfaz mostraba el
    error crudo y el registro no se enteraba."""
    try:
        from ytstudio import eventlog
        eventlog.log(level, mensaje, project=slug, phase="shorts")
    except Exception:
        pass


def api_derive_propose(body: dict) -> dict:
    """Lee el video largo y propone Shorts. NO crea nada todavía: el creador
    ve la tanda, la revisa y decide."""
    from ytstudio import derive
    try:
        source, cfg, nota = _derive_source(body)
    except (RuntimeError, ValueError) as e:
        _log_derive("error", str(e), body.get("slug") or None)
        raise ApiError(400, str(e))
    try:
        n = max(1, min(int(body.get("n") or 5), len(derive.CAMPAIGN)))
    except (TypeError, ValueError):
        n = 5
    _log_derive("info", f"Buscando {n} Shorts en «{source['titulo']}» "
                        f"({len(source['marcas'])} líneas de texto leídas).",
                source.get("slug") or None)
    try:
        candidatos = derive.propose(source, cfg, n=n)
    except Exception as e:
        _log_derive("error", f"El director falló al proponer Shorts: {e}",
                    source.get("slug") or None)
        raise
    if not candidatos:
        raise ApiError(422, "No se encontró ningún momento que aguante solo "
                            "como Short en ese video.")
    plan = derive.save_plan(source, candidatos, body.get("desde") or None)
    plan["estructuras"] = {k: v["label"]
                           for k, v in derive.HOOK_STRUCTURES.items()}
    plan["nota"] = nota
    _log_derive("info", f"{len(candidatos)} Short(s) propuestos de "
                        f"«{source['titulo']}».", source.get("slug") or None)
    return plan


def api_derive_create(body: dict) -> dict:
    """Convierte en proyectos de verdad los candidatos elegidos."""
    from ytstudio import derive
    candidatos = body.get("candidatos") or []
    if not candidatos:
        raise ApiError(400, "No has elegido ningún Short.")
    cfg = load_config()
    creados = []
    for c in candidatos:
        if c.get("gancho_tipo") not in derive.HOOK_STRUCTURES:
            raise ApiError(400, "Un candidato llegó con una estructura de "
                                "gancho desconocida.")
        c.setdefault("funcion", derive.CAMPAIGN[0]["id"])
        c.setdefault("dia", derive.CAMPAIGN_BY_ID[c["funcion"]]["dia"])
        c["plantilla"] = derive.HOOK_STRUCTURES[c["gancho_tipo"]]["plantilla"]
        slug = derive.create_short_project(
            c, cfg, channel_id=body.get("channel_id") or "",
            style_id=body.get("style_id") or "")
        c["slug"] = slug
        creados.append({"slug": slug, "nombre": c.get("nombre", ""),
                        "dia": c.get("dia")})
    origen = body.get("origen") or {}
    if origen.get("slug"):
        try:
            derive.save_plan(origen, candidatos, body.get("desde") or None)
        except Exception:
            pass
    return {"creados": creados}


def api_derive_plan(slug: str) -> dict:
    """El último plan guardado junto a un video largo de la casa."""
    from ytstudio import derive
    p = derive.plan_path({"slug": slug})
    if p is None or not p.exists():
        return {}
    return read_json_tolerant(p)


def api_audit_project(slug: str) -> dict:
    """Vuelve a MEDIR el video final del proyecto contra las especificaciones
    de publicación de vídeo vertical. Es gratis: solo lee el archivo."""
    from ytstudio import shorts
    project = Project(slug)
    final = project.dir / DIRS["final"] / "video_final.mp4"
    if not final.exists():
        raise ApiError(409, "Todavía no hay video final que medir: genera "
                            "primero hasta el Montaje.")
    result = shorts.audit_file(final)
    project.set("shorts_audit", result)
    return {"resultado": result, "informe": shorts.report_lines([result])}


def _scene_or_404(project, scene_id: int) -> dict:
    scenes_file = project.dir / DIRS["scenes"] / "scenes.json"
    if not scenes_file.exists():
        raise ApiError(409, "Genera primero hasta el guion gráfico (Storyboard) "
                            "para poder subir B-roll por escena.")
    scenes = read_json_tolerant(scenes_file)["scenes"]
    scene = next((s for s in scenes if s.get("id") == scene_id), None)
    if scene is None:
        raise ApiError(404, "Escena no encontrada.")
    return scene


def api_scene_broll_upload(slug: str, scene_id: int, body: dict) -> dict:
    from ytstudio.phases.ingest import kind_of
    project = Project(slug)
    scene = _scene_or_404(project, scene_id)
    f = body.get("file") or {}
    if not f.get("data_base64"):
        raise ApiError(400, "Falta el archivo.")
    name = Path(f.get("name") or "").name
    try:
        kind = kind_of(Path(name))
    except ValueError as e:
        raise ApiError(400, str(e))
    if kind not in ("image", "video"):
        raise ApiError(400, "El B-roll de una escena debe ser una imagen o un video.")
    btype = scene.get("broll_type", "image")
    if btype == "image" and kind == "video":
        raise ApiError(400, "El director planificó esta escena como imagen fija "
                            "(no como video). Sube una imagen, o deja que se "
                            "genere automáticamente.")
    manual_dir = project.path("broll", "manual")
    manual_dir.mkdir(parents=True, exist_ok=True)
    for old in manual_dir.glob(f"scene_{scene_id:03d}.*"):
        old.unlink(missing_ok=True)
    data = base64.b64decode(f["data_base64"])
    ext = Path(name).suffix.lower() or (".mp4" if kind == "video" else ".jpg")
    dest = manual_dir / f"scene_{scene_id:03d}{ext}"
    dest.write_bytes(data)
    manual = project.get("manual_broll") or {}
    manual[str(scene_id)] = {"file": dest.name, "kind": kind,
                             "orig": name, "size": len(data)}
    project.set("manual_broll", manual)
    # Solo se rehace el B-roll y el montaje (las escenas cuyo material cambió):
    # ni el guion, ni la voz, ni los tiempos se tocan.
    project.reset_from("broll", PHASE_ORDER)
    return {"ok": True, "kind": kind,
            "downgrade": btype == "video" and kind == "image"}


def api_scene_broll_delete(slug: str, scene_id: int) -> dict:
    project = Project(slug)
    manual = project.get("manual_broll") or {}
    if manual.pop(str(scene_id), None) is not None:
        for old in project.path("broll", "manual").glob(f"scene_{scene_id:03d}.*"):
            old.unlink(missing_ok=True)
        project.set("manual_broll", manual)
        project.reset_from("broll", PHASE_ORDER)
    return {"ok": True}


def api_set_broll_policy(slug: str, body: dict) -> dict:
    project = Project(slug)
    if "auto_replace" in body:
        project.set("broll_auto_replace", bool(body.get("auto_replace")))
    if "review" in body:
        project.set("broll_review", bool(body.get("review")))
    return {"broll_auto_replace": bool(project.get("broll_auto_replace")),
            "broll_review": project.get("broll_review") is not False}


def api_run(slug: str, body: dict) -> dict:
    with RUNS_LOCK:
        if RUNS.get(slug, {}).get("running"):
            raise ApiError(409, "Ya se está generando este proyecto.")
        state = {"running": True, "lines": [], "error": None, "phase": None,
                 "run_start": time.time(), "est_total_sec": None}
        RUNS[slug] = state

    from_phase = body.get("from") or None
    to_phase = body.get("to") or None

    # Línea base para el % completo / tiempo restante en vivo: SOLO las fases
    # que realmente se van a ejecutar en esta corrida (entre from_phase y
    # to_phase, saltando las que ya estén "done", igual que run_pipeline).
    # Antes se usaba el estimado del video COMPLETO sin importar hasta dónde
    # se pidiera generar, lo que mostraba "~22 min" al pedir solo "Análisis".
    try:
        from ytstudio.estimate import estimate as _estimate
        _proj = Project(slug)
        _est = _estimate(_proj, load_config(_proj.dir))
        _phase_secs = _est.get("phase_seconds") or {}
        lo = PHASE_ORDER.index(from_phase) if from_phase in PHASE_ORDER else 0
        hi = (PHASE_ORDER.index(to_phase) if to_phase in PHASE_ORDER
              else len(PHASE_ORDER) - 1)
        scoped = sum(
            float(_phase_secs.get(name, 0.0))
            for name in PHASE_ORDER[lo:hi + 1]
            if _proj.phase_status(name) != "done"
        )
        state["est_total_sec"] = max(20.0, scoped) if scoped > 0 else max(
            20.0, float(_est.get("total_min_medio") or 0) * 60)
    except Exception:
        pass

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


def _run_progress(slug: str) -> dict:
    run = RUNS.get(slug, {"running": False, "lines": [], "error": None, "phase": None})
    out = {k: run.get(k) for k in ("running", "lines", "error", "phase")}
    out["percent"], out["eta_seconds"] = None, None
    if run.get("running") and run.get("run_start"):
        elapsed = time.time() - run["run_start"]
        est = run.get("est_total_sec")
        if est and est > 0:
            out["percent"] = min(99, round(100 * elapsed / est))
            out["eta_seconds"] = max(0, round(est - elapsed))
    return out


def _materialized_roster(project) -> list[dict]:
    """Elenco persistido (materializa la migración v0.28 al primer cambio)."""
    from ytstudio.characters import roster
    chars = roster(project)
    if chars and not project.get("characters"):
        project.set("characters", chars)
    return project.get("characters") or []


def api_character_create(slug: str, body: dict) -> dict:
    from ytstudio.phases.ingest import add_asset

    project = Project(slug)
    name = (body.get("name") or "").strip()[:40]
    if not name:
        raise ApiError(400, "Ponle un nombre al personaje.")
    chars = _materialized_roster(project)
    if any(c["name"].strip().lower() == name.lower() for c in chars):
        raise ApiError(409, f"Ya existe un personaje llamado «{name}».")
    asset_ids = []
    for f in (body.get("files") or []):
        a = add_asset(project, Path(Path(f["name"]).name), "personaje",
                      data=base64.b64decode(f["data_base64"]))
        asset_ids.append(a["id"])
    ch = {"id": f"ch{max((int(c['id'][2:]) for c in chars if c['id'][2:].isdigit()), default=0) + 1}",
          "name": name, "description": (body.get("description") or "").strip()[:300],
          "asset_ids": asset_ids, "narrator": bool(body.get("narrator"))}
    if ch["narrator"]:
        for c in chars:
            c["narrator"] = False
    chars.append(ch)
    project.set("characters", chars)
    if ch["narrator"] and not project.get("character"):
        project.set("character", {"presence": 0.3})
    return {"characters": chars,
            "hint": "Rehaz desde «Escenas» para que el director use el "
                    "elenco actualizado."}


def api_character_update(slug: str, cid: str, body: dict) -> dict:
    project = Project(slug)
    chars = _materialized_roster(project)
    ch = next((c for c in chars if c["id"] == cid), None)
    if ch is None:
        raise ApiError(404, "Personaje no encontrado.")
    if "name" in body and (body["name"] or "").strip():
        ch["name"] = body["name"].strip()[:40]
    if "description" in body:
        ch["description"] = (body["description"] or "").strip()[:300]
    if "narrator" in body:
        if body["narrator"]:
            for c in chars:
                c["narrator"] = c["id"] == cid
        else:
            ch["narrator"] = False
    project.set("characters", chars)
    return {"characters": chars}


def api_set_character_presence(slug: str, body: dict) -> dict:
    """Cuánto sale EN CÁMARA el personaje narrador (y si va en burbuja).

    Hasta ahora solo se podía elegir al CREAR el proyecto: quien se lo pensaba
    después tenía que empezar de cero. Y es el ajuste que más manda en la
    factura del lipsync, que se cobra por segundo en pantalla."""
    project = Project(slug)
    if not project.state_path.exists():
        raise ApiError(404, "Proyecto no encontrado.")
    actual = dict(project.get("character") or {})
    if "presence" in body:
        try:
            pres = int(body.get("presence"))
        except (TypeError, ValueError):
            raise ApiError(400, "La presencia se indica en porcentaje (0-60).")
        # El tope de 60 % es el mismo de la creación: por encima, el video deja
        # de ser un documental ilustrado y el lipsync se dispara de precio.
        actual["presence"] = min(60, max(0, pres)) / 100
    if "pip" in body:
        actual["pip"] = bool(body.get("pip"))
    project.set("character", actual)
    return {"character": actual,
            "hint": "Rehaz desde «Escenas» para que el director reparta las "
                    "apariciones con la presencia nueva."}


def api_character_add_files(slug: str, cid: str, body: dict) -> dict:
    from ytstudio.phases.ingest import add_asset

    project = Project(slug)
    chars = _materialized_roster(project)
    ch = next((c for c in chars if c["id"] == cid), None)
    if ch is None:
        raise ApiError(404, "Personaje no encontrado.")
    for f in (body.get("files") or []):
        a = add_asset(project, Path(Path(f["name"]).name), "personaje",
                      data=base64.b64decode(f["data_base64"]))
        ch.setdefault("asset_ids", []).append(a["id"])
    project.set("characters", chars)
    return {"characters": chars}


def api_character_delete(slug: str, cid: str) -> dict:
    from ytstudio.phases.ingest import remove_asset

    project = Project(slug)
    chars = _materialized_roster(project)
    ch = next((c for c in chars if c["id"] == cid), None)
    if ch is None:
        raise ApiError(404, "Personaje no encontrado.")
    for aid in (ch.get("asset_ids") or []):
        remove_asset(project, aid)
    was_narrator = bool(ch.get("narrator"))
    chars = [c for c in chars if c["id"] != cid]
    if was_narrator and chars and not any(c.get("narrator") for c in chars):
        chars[0]["narrator"] = True  # el rol de narrador no se queda huérfano
    project.set("characters", chars)
    return {"characters": chars}


def api_select_metadata(slug: str, body: dict) -> dict:
    """Elige una de las 3 opciones de título / descripción / miniatura.
    Actualiza metadata.json y (para la miniatura) copia la variante elegida
    como miniatura.jpg — la que usa la publicación. Sin re-ejecutar fases."""
    import shutil as _sh

    kind = body.get("kind")
    if kind not in ("title", "description", "thumbnail"):
        raise ApiError(400, "kind debe ser title, description o thumbnail.")
    try:
        idx = int(body.get("index"))
    except (TypeError, ValueError):
        raise ApiError(400, "Falta el índice de la opción.")
    project = Project(slug)
    meta_path = project.dir / DIRS["final"] / "metadata.json"
    if not meta_path.exists():
        raise ApiError(404, "Aún no hay metadatos (ejecuta hasta 'metadata').")
    meta = read_json_tolerant(meta_path)
    options = meta.get(f"{kind}_options" if kind != "thumbnail"
                       else "thumbnail_options") or []
    files = meta.get("thumbnails") or []
    limit = len(files) if kind == "thumbnail" else len(options)
    if not 0 <= idx < limit:
        raise ApiError(400, f"Opción {idx + 1} fuera de rango.")
    if kind == "title":
        meta["title"] = options[idx]["title"]
    elif kind == "description":
        meta["description"] = options[idx]["description"]
    else:
        _sh.copyfile(project.path("final", files[idx]),
                     project.path("final", "miniatura.jpg"))
    meta.setdefault("chosen", {})[kind] = idx
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    project.set("metadata", {k: meta.get(k) for k in ("title", "tags", "thumbnail")})
    return {"ok": True, "chosen": meta["chosen"]}


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


# Campos del EDITOR de escenas y qué invalida cada uno. Regla: el editor solo
# toca lo que se puede remontar BARATO (sin volver a llamar al LLM ni regenerar
# B-roll): rótulos, animación, transición, sfx, intensidad musical y — solo en
# modo TTS — la duración de la escena. La narración y el orden no se editan
# aquí (cambiarlos exige regenerar voz/B-roll: hazlo desde el Guion).
_EDIT_VISUAL = {"animation", "transition", "sfx", "music_intensity"}
_EDIT_ANIMS = {"zoom_in", "zoom_out", "pan_left", "pan_right", "static"}


def api_edit_scenes(slug: str, body: dict) -> dict:
    from ytstudio.phases.scenes import load_scenes, save_scenes

    project = Project(slug)
    scenes = load_scenes(project)
    if not scenes:
        raise ApiError(404, "Este proyecto aún no tiene escenas.")
    by_id = {int(s["id"]): s for s in scenes}
    use_user_voice = any("audio_start" in s for s in scenes)

    need_broll = need_subtitles = need_assembly = overlay_changed = False
    shot_overrides = dict(project.get("shot_overrides") or {})
    for e in (body.get("edits") or []):
        s = by_id.get(int(e.get("id", -1)))
        if s is None:
            continue
        if (e.get("shot") in ("personaje", "broll")
                and e["shot"] != s.get("shot")):
            # forzar personaje/B-roll en esta escena → regenerar su material
            s["shot"] = e["shot"]
            shot_overrides[str(s["id"])] = e["shot"]
            need_broll = True
        if "animation" in e and e["animation"] in _EDIT_ANIMS:
            s["animation"] = e["animation"]; need_assembly = True
        if "transition" in e and e["transition"] in ("corte", "fundido"):
            s["transition"] = e["transition"]; need_assembly = True
        if "sfx" in e and e["sfx"] in ("ninguno", "whoosh", "riser", "boom"):
            s["sfx"] = e["sfx"]; need_assembly = True
        if "music_intensity" in e:
            try:
                s["music_intensity"] = min(1.0, max(0.0, float(e["music_intensity"])))
                need_assembly = True
            except (TypeError, ValueError):
                pass
        if "overlay_text" in e or "overlay_kicker" in e or "overlay_type" in e:
            text = (e.get("overlay_text")
                    if "overlay_text" in e
                    else (s.get("overlay") or {}).get("text", "")) or ""
            text = text.strip()[:44]
            if text:
                s["overlay"] = {
                    "type": (e.get("overlay_type")
                             or (s.get("overlay") or {}).get("type") or "dato"),
                    "text": text,
                    "kicker": ((e.get("overlay_kicker")
                                if "overlay_kicker" in e
                                else (s.get("overlay") or {}).get("kicker", ""))
                               or "").strip()[:36],
                    "emphasis": (s.get("overlay") or {}).get("emphasis", ""),
                }
            else:
                s["overlay"] = None
                s["overlay_at"] = None
            s["on_screen_text"] = text
            overlay_changed = need_assembly = True
        if ("duration" in e and not use_user_voice and "audio_start" not in s
                and s.get("vo_duration")):
            # Solo TTS y tras la fase de voz: la duración es editable (con voz
            # propia la manda la voz; antes de la voz no hay piso fiable)
            try:
                fps = float(load_config(project.dir).get("video", {}).get("fps", 24))
                want = float(e["duration"])
                floor = float(s.get("vo_duration") or 1.0) + 0.2
                frames = max(1, round(max(floor, min(60.0, want)) * fps))
                s["duration"] = round(frames / fps, 5)
                need_subtitles = True
            except (TypeError, ValueError):
                pass

    if not (need_broll or need_subtitles or need_assembly):
        return {"saved": False, "rerun_from": None}

    if need_broll:
        project.set("shot_overrides", shot_overrides)
    if need_subtitles and not use_user_voice:
        # La línea de tiempo TTS se recompila aquí mismo (barato, sin LLM)
        from ytstudio.phases.voiceover import _build_tts_timeline
        vo_dir = project.path("voiceover")
        _build_tts_timeline(scenes, vo_dir)
        project.set("total_duration",
                    round(sum(float(s["duration"]) for s in scenes), 2))
    if overlay_changed and use_user_voice:
        # Re-anclar el rótulo al instante en que se pronuncia (sin re-fases)
        from ytstudio.phases.voiceover import _sync_overlays
        narration = project.get("narration") or {}
        vmap = project.get("voice_map")
        if vmap:
            _sync_overlays(scenes, narration.get("segments") or [], vmap)

    save_scenes(project, scenes)
    rerun = ("broll" if need_broll
             else "subtitles" if need_subtitles else "assembly")
    project.reset_from(rerun, PHASE_ORDER)
    return {"saved": True, "rerun_from": rerun}


def api_elements_list() -> dict:
    """Inventario del BANCO DE ELEMENTOS (material de superposición propio)."""
    from ytstudio.utils.elements import CATEGORIES, bank_list
    return {"categories": list(CATEGORIES), "items": bank_list()}


def api_elements_add(body: dict) -> dict:
    from ytstudio.utils.elements import bank_add
    cat = str(body.get("category") or "")
    f = body.get("file") or {}
    if not f.get("data_base64"):
        raise ApiError(400, "Falta el archivo.")
    try:
        data = base64.b64decode(f["data_base64"])
        return {"ok": True,
                "item": bank_add(cat, f.get("name") or "", data)}
    except ValueError as e:
        raise ApiError(400, str(e))


def api_elements_delete(category: str, filename: str) -> dict:
    from ytstudio.utils.elements import bank_delete
    try:
        return {"ok": bank_delete(category, urllib.parse.unquote(filename))}
    except ValueError as e:
        raise ApiError(400, str(e))


def api_get_config() -> dict:
    return {
        "config": load_config(),
        "catalog": CATALOG,
        "style_presets": STYLE_PRESETS,
        "languages": LANGUAGES,
        "formats": {k: {"label": v["label"], "short": k != "long"}
                    for k, v in FORMATS.items()},
        "short_templates": {k: {"label": v["label"], "hint": v["hint"]}
                            for k, v in SHORT_TEMPLATES.items()},
        "overlay_font_families": OVERLAY_FONT_FAMILIES,
        "insert_sfx_options": [{"id": k, "label": v}
                               for k, v in PALETTE_LABELS.items()],
        "overlay_branding_presets": OVERLAY_BRANDING_PRESETS,
        "keys": key_status(),
        "version": get_version(),
        "server_version": SERVER_VERSION,
        "ui_template": ui_template(),
        "ui_templates": template_cards(),
        "phases": [{"name": n, "desc": d, "label": PHASE_LABELS.get(n, n)}
                   for n, _, d in PHASES],
    }


# SOLO estos ajustes los controla la interfaz de Configuración. Guardar en
# config.local.yaml cualquier otra cosa congelaba los valores por defecto de
# ese momento y anulaba mejoras futuras (p.ej. dejaba 'transition: fade' fijo
# aunque el nuevo defecto sea 'auto'). Se guarda solo esta lista; el resto
# fluye siempre desde config.yaml (el del repo, actualizable con git pull).
_UI_CONFIG_PATHS = (
    ("language",),
    ("ui", "template"),  # plantilla de la interfaz elegida por el creador
    ("style", "preset"),
    ("video", "target_minutes"), ("video", "width"), ("video", "height"),
    ("video", "burn_subtitles"), ("video", "scene_seconds"),
    ("audio", "music_db"), ("audio", "duck"), ("audio", "element_sfx"),
    ("providers",),  # el usuario elige proveedores/modelos
    ("migrations",),  # marcas de migraciones ya aplicadas (ver _apply_migrations)
)


def _prune_to_ui(cfg: dict) -> dict:
    """Extrae de `cfg` solo las rutas que gestiona la interfaz."""
    out: dict = {}
    for path in _UI_CONFIG_PATHS:
        src = cfg
        ok = True
        for key in path:
            if isinstance(src, dict) and key in src:
                src = src[key]
            else:
                ok = False
                break
        if not ok:
            continue
        dst = out
        for key in path[:-1]:
            dst = dst.setdefault(key, {})
        dst[path[-1]] = src
    return out


def _apply_migrations(cfg: dict) -> dict:
    """Cambios de configuración recomendada que se aplican UNA sola vez — la
    marca queda en 'migrations', así que si después el usuario elige otra
    cosa en ⚙ Configuración, su elección se respeta para siempre.

    images_replicate_v0_45: el proveedor de imágenes recomendado pasa de
    gpt-image-1 (~$0.07-0.25/img y un límite de 5 img/min que frenaba la
    fase) a Replicate FLUX 1.1 Pro (~$0.04/img, sin ese cuello de botella).
    gpt-image-1 sigue entrando SOLO en las escenas con texto legible, a las
    que el director rutea por su cuenta.

    models_retired_v0_58: los proveedores APAGARON algunos modelos con fecha
    (Imagen 4 Fast el 17/08/2026, gpt-image-1 el 23/10/2026). Un config que
    los nombre no es una preferencia que respetar: es una avería esperando a
    ocurrir a mitad de la fase de imágenes, con parte del proyecto ya pagado.
    Se sustituyen por su relevo, una sola vez, y se avisa por consola."""
    done = list(cfg.get("migrations") or [])
    if "images_replicate_v0_45" not in done:
        img = (cfg.get("providers") or {}).get("images") or {}
        if img.get("name") == "openai":
            img["name"] = "replicate"
            img["model"] = "black-forest-labs/flux-1.1-pro"
            cfg.setdefault("providers", {})["images"] = img
        done.append("images_replicate_v0_45")
    if "models_retired_v0_58" not in done:
        from ytstudio.pricing import retirement
        img = (cfg.get("providers") or {}).get("images") or {}
        for key in ("model", "ref_model"):
            info = retirement(str(img.get(key, "")))
            if not info:
                continue
            fecha, relevo = info
            print(f"  ⚠ «{img[key]}» dejó de existir el {fecha}: tu "
                  f"configuración pasa a «{relevo}». Puedes cambiarlo en "
                  "⚙ Configuración.")
            img[key] = relevo
            cfg.setdefault("providers", {})["images"] = img
        done.append("models_retired_v0_58")
    cfg["migrations"] = done
    return cfg


def migrate_local_config() -> None:
    """Al arrancar: recorta config.local.yaml a lo que controla la UI, para
    liberar defaults congelados por versiones antiguas (transiciones,
    rendimiento, overlays, audio avanzado…), y aplica las migraciones de una
    sola vez. Si el archivo no existe se crea solo con las marcas — sin eso,
    una elección futura del usuario podría ser revertida por una migración
    vieja al siguiente arranque."""
    path = ROOT / "config.local.yaml"
    current = {}
    if path.exists():
        try:
            current = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return
    pruned = _apply_migrations(_prune_to_ui(current))
    if pruned != current:
        path.write_text(
            yaml.safe_dump(pruned, allow_unicode=True, sort_keys=False),
            encoding="utf-8")


def api_save_config(body: dict) -> dict:
    cfg = body.get("config")
    if not isinstance(cfg, dict):
        raise ApiError(400, "Config inválida.")
    # Se guarda en config.local.yaml (fuera de Git) — nunca en config.yaml,
    # que es parte del repositorio y un 'git pull' lo sobreescribiría. Solo se
    # persiste lo que la UI controla (ver _UI_CONFIG_PATHS): así los defaults
    # nuevos del programa nunca quedan tapados por un guardado antiguo.
    saved = _prune_to_ui(cfg)
    # Las marcas de migración del archivo actual nunca se pierden en un
    # guardado (la UI podría tener cargada una config anterior a la
    # migración): sin la unión, la migración se re-aplicaría al siguiente
    # arranque y pisaría lo que el usuario acaba de elegir.
    path = ROOT / "config.local.yaml"
    try:
        prev = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        prev = {}
    marks = list(dict.fromkeys([*(prev.get("migrations") or []),
                                *(saved.get("migrations") or [])]))
    if marks:
        saved["migrations"] = marks
    path.write_text(
        yaml.safe_dump(saved, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
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

    def handle_one_request(self):
        """Igual que el original, pero SIN escupir una traza cuando el
        navegador corta la conexión.

        Es lo más normal del mundo: recargas la página, cierras la pestaña o
        una consulta larga se cancela, y el navegador cierra el socket a
        medias. Python lo trataba como un error grave e imprimía un
        «ConnectionAbortedError [WinError 10053]» de treinta líneas en la
        ventana negra — que asusta y no significa nada. No es un fallo del
        programa: no hay nada que arreglar ni que reportar."""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

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

    def _download(self, data: bytes, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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

    def _manual_image(self, folder: str, name: str) -> None:
        """Sirve una captura del manual (docs/manual/<plantilla>/<archivo>)."""
        base = (ROOT / "docs" / "manual").resolve()
        target = (base / folder / name).resolve()
        if not str(target).startswith(str(base)):
            self._json({"error": "Ruta inválida"}, 403)
            return
        self._serve_file(target)

    def _element_file(self, category: str, name: str) -> None:
        """Sirve un archivo del BANCO DE ELEMENTOS para la vista previa."""
        from ytstudio.utils.elements import BANK_DIR
        base = BANK_DIR.resolve()
        target = (base / category / urllib.parse.unquote(name)).resolve()
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
            query = parse_qs(urlparse(self.path).query)
            if path in ("/", "/index.html"):
                # La PLANTILLA elegida decide qué interfaz se sirve. Las dos
                # hablan con este mismo motor y con los mismos proyectos.
                self._serve_file(
                    STATIC_DIR / TEMPLATES[ui_template()]["html"],
                    no_cache=True)
            elif path == "/api/events":
                self._json(api_events(query))
            elif path == "/api/events/download":
                from ytstudio import eventlog
                self._download(eventlog.raw_text().encode("utf-8"),
                               "ytstudio-eventos.log")
            elif path == "/api/catalog" or path == "/api/config":
                self._json(api_get_config())
            elif path == "/api/projects":
                self._json(api_list_projects())
            elif m := re.fullmatch(r"/api/projects/([\w-]+)", path):
                self._json(api_project_detail(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/log", path):
                self._json(_run_progress(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/script", path):
                self._json(api_get_script(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/estimate", path):
                self._json(api_estimate(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/shorts-plan", path):
                self._json(api_derive_plan(m.group(1)))
            elif path == "/api/changelog":
                self._json(api_changelog())
            elif path == "/api/manual":
                self._json(api_manual())
            elif path == "/api/library":
                self._json(api_library())
            elif path == "/api/elements":
                self._json(api_elements_list())
            elif m := re.fullmatch(r"/docs/manual/([\w-]+)/([\w.-]+)", path):
                # CAPTURAS DEL MANUAL, una carpeta por plantilla. La ruta es la
                # misma que se escribe en el archivo (docs/manual/…), así las
                # imágenes se ven igual en GitHub y dentro del programa.
                self._manual_image(m.group(1), m.group(2))
            elif m := re.fullmatch(r"/elements/([\w-]+)/(.+)", path):
                self._element_file(m.group(1), m.group(2))
            elif m := re.fullmatch(r"/files/([\w-]+)/(.+)", path):
                self._project_file(m.group(1), m.group(2))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            # Un fallo inesperado TAMBIÉN queda en el 🧾 Log de eventos: antes
            # solo se veía en la ventana negra, y la interfaz mostraba el
            # mensaje crudo del error sin que quedara rastro de nada.
            _log_derive("error", f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        try:
            path = self.path.split("?")[0]
            if path == "/api/projects":
                self._json(api_create_project(self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/run", path):
                self._json(api_run(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/duplicate", path):
                self._json(api_duplicate_project(m.group(1), self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/scenes/(\d+)/broll", path):
                self._json(api_scene_broll_upload(m.group(1), int(m.group(2)),
                                                  self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/assets", path):
                self._json(api_add_assets(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/audit", path):
                self._json(api_audit_project(m.group(1)))
            elif path == "/api/shorts/propose":
                self._json(api_derive_propose(self._body()))
            elif path == "/api/shorts/create":
                self._json(api_derive_create(self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/save-style", path):
                self._json(api_save_style_from_project(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/metadata/select", path):
                self._json(api_select_metadata(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/characters", path):
                self._json(api_character_create(m.group(1), self._body()), 201)
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/characters/([\w-]+)/files", path):
                self._json(api_character_add_files(m.group(1), m.group(2), self._body()))
            elif path == "/api/channels":
                self._json(api_channel_create(self._body()), 201)
            elif m := re.fullmatch(r"/api/channels/([\w-]+)", path):
                self._json(api_channel_update(m.group(1), self._body()))
            elif path == "/api/elements":
                self._json(api_elements_add(self._body()), 201)
            elif path == "/api/styles":
                self._json(api_style_create(self._body()), 201)
            elif m := re.fullmatch(r"/api/styles/([\w-]+)", path):
                self._json(api_style_update(m.group(1), self._body()))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            # Un fallo inesperado TAMBIÉN queda en el 🧾 Log de eventos: antes
            # solo se veía en la ventana negra, y la interfaz mostraba el
            # mensaje crudo del error sin que quedara rastro de nada.
            _log_derive("error", f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def do_PUT(self):
        try:
            path = self.path.split("?")[0]
            if path == "/api/config":
                self._json(api_save_config(self._body()))
            elif path == "/api/keys":
                self._json(api_save_keys(self._body()))
            elif path == "/api/ui-template":
                self._json(api_set_ui_template(self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/script", path):
                self._json(api_save_script(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/rename", path):
                self._json(api_rename_project(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/broll-policy", path):
                self._json(api_set_broll_policy(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/character", path):
                self._json(api_set_character_presence(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/scenes", path):
                self._json(api_edit_scenes(m.group(1), self._body()))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/characters/([\w-]+)", path):
                self._json(api_character_update(m.group(1), m.group(2), self._body()))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            # Un fallo inesperado TAMBIÉN queda en el 🧾 Log de eventos: antes
            # solo se veía en la ventana negra, y la interfaz mostraba el
            # mensaje crudo del error sin que quedara rastro de nada.
            _log_derive("error", f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def do_DELETE(self):
        try:
            path = self.path.split("?")[0]
            if m := re.fullmatch(r"/api/projects/([\w-]+)/assets/(\d+)", path):
                self._json(api_delete_asset(m.group(1), int(m.group(2))))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/characters/([\w-]+)", path):
                self._json(api_character_delete(m.group(1), m.group(2)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)/scenes/(\d+)/broll", path):
                self._json(api_scene_broll_delete(m.group(1), int(m.group(2))))
            elif m := re.fullmatch(r"/api/elements/([\w-]+)/(.+)", path):
                self._json(api_elements_delete(m.group(1), m.group(2)))
            elif m := re.fullmatch(r"/api/channels/([\w-]+)", path):
                self._json(api_channel_delete(m.group(1)))
            elif m := re.fullmatch(r"/api/styles/([\w-]+)", path):
                self._json(api_style_delete(m.group(1)))
            elif m := re.fullmatch(r"/api/projects/([\w-]+)", path):
                self._json(api_delete_project(m.group(1)))
            else:
                self._json({"error": "No encontrado"}, 404)
        except ApiError as e:
            self._json({"error": e.message}, e.status)
        except Exception as e:
            traceback.print_exc()
            # Un fallo inesperado TAMBIÉN queda en el 🧾 Log de eventos: antes
            # solo se veía en la ventana negra, y la interfaz mostraba el
            # mensaje crudo del error sin que quedara rastro de nada.
            _log_derive("error", f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    migrate_local_config()  # libera defaults congelados de versiones antiguas
    from ytstudio import eventlog
    eventlog.log("info",
                 f"Programa iniciado ({SERVER_VERSION or 'versión desconocida'}).")
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
