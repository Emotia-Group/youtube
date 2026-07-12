"""CLI del sistema.

Uso típico:
  python -m ytstudio new mi-video --text "Idea del video…"
  python -m ytstudio new mi-video --file nota_de_voz.m4a
  python -m ytstudio run mi-video                # todas las fases
  python -m ytstudio run mi-video --to script    # pausa para revisar el guion
  python -m ytstudio run mi-video --from scenes  # re-ejecuta desde una fase
  python -m ytstudio status mi-video
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


def cmd_ui(args) -> None:
    from ytstudio.webui.server import serve
    serve(port=args.port)


def main() -> None:
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

    p_ui = sub.add_parser("ui", help="Abrir la interfaz web local")
    p_ui.add_argument("--port", type=int, default=8765)
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
