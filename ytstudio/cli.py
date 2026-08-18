"""CLI del sistema.

Uso típico:
  python -m ytstudio new mi-video --text "Idea del video…"
  python -m ytstudio new mi-video --file nota_de_voz.m4a
  python -m ytstudio run mi-video                # todas las fases
  python -m ytstudio run mi-video --to script    # pausa para revisar el guion
  python -m ytstudio run mi-video --from scenes  # re-ejecuta desde una fase
  python -m ytstudio status mi-video
  python -m ytstudio auditar C:\\videos\\shorts   # medir verticales ya hechos
  python -m ytstudio shorts mi-video --crear     # sacar Shorts del video largo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ytstudio.config import load_config
from ytstudio.pipeline import PHASE_ORDER, PHASES, run_pipeline
from ytstudio.project import PROJECTS_DIR, Project, slugify


def cmd_new(args) -> None:
    from ytstudio.phases.ingest import stage_input

    slug = slugify(args.slug)
    if Project.exists(slug) and not args.force:
        sys.exit(f"El proyecto '{slug}' ya existe (usa --force para recrearlo).")

    text = args.text
    source = Path(args.file).expanduser() if args.file else None
    if not text and not source:
        sys.exit("Indica el input con --text \"…\" o --file ruta/al/archivo")
    if source and not source.exists():
        sys.exit(f"No existe el archivo: {source}")

    project = Project.create(slug)
    meta = stage_input(project, source, text, args.type)
    print(f"Proyecto '{slug}' creado en {project.dir}")
    print(f"Input detectado: {meta['type']} ({meta['file']})")
    print(f"Siguiente paso:  python -m ytstudio run {slug}")


def cmd_run(args) -> None:
    if not Project.exists(args.slug):
        sys.exit(f"No existe el proyecto '{args.slug}'. Créalo con 'new'.")
    project = Project(args.slug)
    cfg = load_config(project.dir)
    run_pipeline(project, cfg, from_phase=getattr(args, "from"), to_phase=args.to)

    final = project.get("final_video")
    if final and project.phase_status("assembly") == "done":
        print(f"\n🎬 Video final: {final}")


def cmd_status(args) -> None:
    if not Project.exists(args.slug):
        sys.exit(f"No existe el proyecto '{args.slug}'.")
    project = Project(args.slug)
    print(f"Proyecto: {args.slug} ({project.dir})\n")
    for name, _, desc in PHASES:
        status = project.phase_status(name)
        icon = {"done": "✔", "failed": "✖", "pending": "·"}.get(status, "?")
        info = project.state["phases"].get(name, {})
        extra = f"  ({info.get('error')})" if status == "failed" else ""
        print(f"  {icon} {name:<10} {desc:<32} [{status}]{extra}")
    if project.get("total_duration"):
        print(f"\nDuración estimada: {project.get('total_duration'):.1f}s "
              f"({project.get('scene_count')} escenas)")


def cmd_list(args) -> None:
    if not PROJECTS_DIR.exists():
        print("No hay proyectos.")
        return
    for p in sorted(PROJECTS_DIR.iterdir()):
        if (p / "project.json").exists():
            project = Project(p.name)
            done = sum(1 for ph in PHASE_ORDER
                       if project.phase_status(ph) == "done")
            print(f"  {p.name:<30} {done}/{len(PHASE_ORDER)} fases")


def cmd_phases(args) -> None:
    for i, (name, _, desc) in enumerate(PHASES, 1):
        print(f"  {i:>2}. {name:<10} {desc}")


def cmd_shorts(args) -> None:
    """Saca Shorts de un video largo: uno de tus proyectos o cualquier enlace
    de YouTube."""
    from ytstudio import derive

    origen = args.origen
    if origen.startswith(("http://", "https://")):
        cfg = load_config()
        source = derive.source_from_url(origen, cfg)
    else:
        if not Project.exists(origen):
            sys.exit(f"No existe el proyecto '{origen}'. Pásale un nombre de "
                     "proyecto o un enlace de YouTube.")
        cfg = load_config(Project(origen).dir)
        source = derive.source_from_project(origen)

    print(f"\nVideo largo: {source['titulo']}")
    print(f"Material leído: {len(source['marcas'])} líneas con su minuto\n")
    candidatos = derive.propose(source, cfg, n=args.n)
    if not candidatos:
        sys.exit("El director no encontró ningún momento que aguante solo.")

    rot = derive.rotation_report(candidatos)
    for c in candidatos:
        h = derive.HOOK_STRUCTURES[c["gancho_tipo"]]["label"]
        print(f"  {derive.campaign_label(c['dia']):>4}  {c['duracion']:>2}s  "
              f"{h:<34} {c['nombre']}")
        print(f"        gancho: {c['guion'].split('.')[0].strip()[:90]}…")
        print(f"        texto en pantalla: {c['texto_pantalla']}")
    print()
    if not rot["suficiente"]:
        print(f"  ⚠ Solo {rot['estructuras']} estructura(s) de gancho "
              f"distintas (mínimo {rot['minimo']}). Repetir la misma fórmula "
              "fatiga a la audiencia y es el patrón que las políticas "
              "describen como producción en masa.\n")

    plan = derive.save_plan(source, candidatos, args.desde)
    print("Calendario alrededor del video largo:")
    for x in plan["calendario"]:
        print(f"  {x['etiqueta']:>4}  {x['fecha']}  {x['funcion']:<16} "
              f"{x['nombre']}")

    if not args.crear:
        print("\n(Nada creado todavía: añade --crear para convertirlos en "
              "proyectos.)")
        return
    print()
    for c in candidatos:
        slug = derive.create_short_project(c, cfg)
        c["slug"] = slug
        print(f"  ✔ proyecto '{slug}' creado — "
              f"python -m ytstudio run {slug}")
    derive.save_plan(source, candidatos, args.desde)


def cmd_auditar(args) -> None:
    """Mide vídeos verticales YA producidos (los del programa o los que
    vengan de fuera) contra las especificaciones de publicación."""
    import shutil as _shutil

    from ytstudio import shorts

    for tool in ("ffprobe", "ffmpeg"):
        if not _shutil.which(tool):
            sys.exit(f"No se encuentra '{tool}'. Instálalo desde "
                     "https://ffmpeg.org/download.html")

    rutas = list(args.ruta)
    # Sin ruta: se audita el video final de los proyectos indicados por nombre
    if not rutas:
        sys.exit("Indica una carpeta o uno o más archivos de video.")
    resultados = shorts.audit_paths(rutas)
    if not resultados:
        sys.exit("No se encontraron archivos de video en esa ruta.")
    if args.json:
        import json as _json
        print(_json.dumps(resultados, indent=2, ensure_ascii=False))
        return
    print("\n".join(shorts.report_lines(resultados)))


def cmd_ui(args) -> None:
    from ytstudio.webui.server import serve
    serve(port=args.port, open_browser=not args.no_browser)


def main() -> None:
    # En Windows, la salida redirigida usa cp1252 y los emojis del log
    # romperían con UnicodeEncodeError — forzamos UTF-8 tolerante.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="ytstudio",
        description="Sistema inteligente de creación de videos largos para YouTube.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Crear un proyecto desde un input")
    p_new.add_argument("slug", help="Nombre del proyecto")
    p_new.add_argument("--text", help="Idea o guion como texto directo")
    p_new.add_argument("--file", help="Archivo de input: guion (.txt/.md), nota de "
                       "voz (.mp3/.m4a…), imagen (.jpg/.png) o video de referencia (.mp4…)")
    p_new.add_argument("--type", default="auto",
                       choices=["auto", "script", "idea", "voice", "image", "video"],
                       help="Forzar el tipo de input (por defecto: autodetectar)")
    p_new.add_argument("--force", action="store_true")
    p_new.set_defaults(func=cmd_new)

    p_run = sub.add_parser("run", help="Ejecutar el pipeline (reanudable)")
    p_run.add_argument("slug")
    p_run.add_argument("--to", choices=PHASE_ORDER,
                       help="Detenerse tras esta fase (ej. --to script para revisar)")
    p_run.add_argument("--from", dest="from", choices=PHASE_ORDER,
                       help="Re-ejecutar desde esta fase (invalida las posteriores)")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Estado de las fases de un proyecto")
    p_status.add_argument("slug")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="Listar proyectos")
    p_list.set_defaults(func=cmd_list)

    p_phases = sub.add_parser("phases", help="Listar las fases del pipeline")
    p_phases.set_defaults(func=cmd_phases)

    p_sh = sub.add_parser(
        "shorts", help="Sacar Shorts de un video largo (un proyecto tuyo o un "
                       "enlace de YouTube)")
    p_sh.add_argument("origen", help="Nombre de un proyecto o enlace de YouTube")
    p_sh.add_argument("--n", type=int, default=5,
                      help="Cuántos Shorts proponer (por defecto 5, máximo 7)")
    p_sh.add_argument("--crear", action="store_true",
                      help="Crear los proyectos de verdad (sin esto solo "
                           "propone y guarda el plan)")
    p_sh.add_argument("--desde", default=None,
                      help="Fecha del video largo (AAAA-MM-DD) para el "
                           "calendario. Por defecto, hoy")
    p_sh.set_defaults(func=cmd_shorts)

    p_aud = sub.add_parser(
        "auditar", help="Medir videos verticales contra las especificaciones "
                        "de publicación (resolución, códecs, duración, sonoridad)")
    p_aud.add_argument("ruta", nargs="*",
                       help="Carpeta con videos, o uno o varios archivos")
    p_aud.add_argument("--json", action="store_true",
                       help="Salida en JSON en vez del informe legible")
    p_aud.set_defaults(func=cmd_auditar)

    p_ui = sub.add_parser("ui", help="Abrir la interfaz web local")
    p_ui.add_argument("--port", type=int, default=8765)
    p_ui.add_argument("--no-browser", action="store_true",
                      help="No abrir el navegador automáticamente")
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
