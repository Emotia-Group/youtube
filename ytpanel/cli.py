"""CLI de la Torre de Control.

  python -m ytpanel ui                  # interfaz web (recomendada)
  python -m ytpanel sync                # sincronizar todos los canales
  python -m ytpanel sync --canal UC...  # solo uno
  python -m ytpanel canales             # lista y estado
  python -m ytpanel demo [--quitar]     # datos de demostración

`sync` está pensado para programarlo (Programador de tareas de Windows o
cron) y tener la sincronización nocturna sin dejar el panel abierto.
"""
from __future__ import annotations

import argparse
import sys

from ytpanel import config, db, demo, jobs, sync


def cmd_ui(args) -> None:
    from ytpanel.server import serve
    serve(port=args.port, open_browser=not args.no_browser)


def cmd_sync(args) -> None:
    conn = db.connect()
    try:
        if args.canal:
            resumenes = [sync.sync_channel(conn, args.canal, log=print)]
        else:
            resumenes = sync.sync_all(conn, log=print)
    finally:
        conn.close()
    if not resumenes:
        print("No hay canales conectados. Abre el panel (python -m ytpanel ui) "
              "y pulsa «Conectar canal».")
        return
    fallos = [r for r in resumenes if not r["ok"]]
    quota = sum(r["quota"] for r in resumenes)
    print(f"\nSincronizados {len(resumenes) - len(fallos)}/{len(resumenes)} "
          f"canales · {quota} unidades de cuota Data API")
    for r in fallos:
        print(f"  ✖ {r['channel_id']}: {r['error']}")
    if fallos:
        sys.exit(1)  # visible en el programador de tareas


def cmd_canales(args) -> None:
    conn = db.connect()
    try:
        canales = db.list_channels(conn)
    finally:
        conn.close()
    if not canales:
        print("No hay canales. Abre el panel y pulsa «Conectar canal».")
        return
    for c in canales:
        icono = {"ok": "✔", "reauth": "⚠", "sin_token": "·"}.get(
            c["token_status"], "?")
        demo_tag = "  [demo]" if c["is_demo"] else ""
        print(f"  {icono} {c['title'] or c['channel_id']:<30} "
              f"{c['subscriber_count']:>9} subs   último sync: "
              f"{c['last_sync'] or 'nunca'}{demo_tag}")


def cmd_cola(args) -> None:
    conn = db.connect()
    try:
        if args.procesar:
            resumen = jobs.procesar_cola(conn, log=print)
            print(f"\nHechos {resumen['hechos']} · errores {resumen['errores']}"
                  f" · en espera {resumen['en_espera']}"
                  f" · {resumen['unidades']} unidades de cuota")
            if resumen["errores"]:
                sys.exit(1)
            return
        lista = db.list_jobs(conn)
        if not lista:
            print("La cola está vacía.")
            return
        for j in lista[:40]:
            etiqueta = jobs.ETIQUETAS.get(j["kind"], j["kind"])
            print(f"  #{j['id']:>4}  {j['status']:<10} {etiqueta:<22} "
                  f"{j['channel_id']:<26} {j['nota'][:60]}")
    finally:
        conn.close()


def cmd_demo(args) -> None:
    conn = db.connect()
    try:
        if args.quitar:
            n = demo.remove(conn)
            print(f"Canales de demostración quitados: {n}")
        else:
            n = demo.seed(conn)
            print(f"Canales de demostración creados: {n}. "
                  f"Ábrelos con: python -m ytpanel ui")
    finally:
        conn.close()


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="ytpanel",
        description="Torre de Control: panel multicanal de YouTube.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ui = sub.add_parser("ui", help="Abrir la interfaz web local")
    p_ui.add_argument("--port", type=int, default=None,
                      help="Puerto (por defecto, panel.port de config.yaml: 8766)")
    p_ui.add_argument("--no-browser", action="store_true",
                      help="No abrir el navegador automáticamente")
    p_ui.set_defaults(func=cmd_ui)

    p_sync = sub.add_parser("sync", help="Sincronizar canales (para cron)")
    p_sync.add_argument("--canal", help="Solo este channel_id")
    p_sync.set_defaults(func=cmd_sync)

    p_can = sub.add_parser("canales", help="Listar canales conectados")
    p_can.set_defaults(func=cmd_canales)

    p_cola = sub.add_parser("cola", help="Ver o procesar la cola de ediciones")
    p_cola.add_argument("--procesar", action="store_true",
                        help="Ejecutar los trabajos pendientes ahora")
    p_cola.set_defaults(func=cmd_cola)

    p_demo = sub.add_parser("demo", help="Cargar o quitar datos de demostración")
    p_demo.add_argument("--quitar", action="store_true")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
