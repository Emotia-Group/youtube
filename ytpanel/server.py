"""Interfaz web local de la Torre de Control.

Mismo patrón que la UI de ytstudio: servidor HTTP de la biblioteca estándar,
API REST en JSON y una SPA en static/index.html. Solo escucha en 127.0.0.1
— este proceso guarda tokens de tus canales y no debe verse desde la red.

    python -m ytpanel ui [--port 8766]

El flujo «Conectar canal» vive aquí: /api/oauth/start entrega la URL de
Google y /oauth/callback recibe el código, identifica el canal autorizado,
guarda su token en la bóveda y dispara la primera sincronización en segundo
plano.
"""
from __future__ import annotations

import json
import re
import secrets as _secrets
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import base64

from ytpanel import config, db, demo, google_api, jobs, sync, vault

STATIC_DIR = Path(__file__).parent / "static"

# Estados anti-CSRF del flujo OAuth: state → momento de creación. Se validan
# y consumen en el callback; caducan a los 10 minutos.
_OAUTH_STATES: dict[str, float] = {}
_OAUTH_TTL = 600

# Una sincronización a la vez; la UI hace polling de las líneas del log.
SYNC = {"running": False, "lines": [], "result": None, "started": ""}
# La cola de ediciones corre aparte del sync (y también de una en una).
COLA = {"running": False, "lines": []}
_LOCK = threading.Lock()


def get_version() -> str:
    """Versión activa (primer encabezado del CHANGELOG), como en ytstudio."""
    try:
        text = (config.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:2000]
        m = re.search(r"^## (v\d+\.\d+\.\d+)", text, re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _estado(conn) -> dict:
    cfg = config.load_panel_config()
    return {
        "version": get_version(),
        "cifrado": vault.available(),
        "client_secrets": config.client_secrets_path().exists(),
        "cuota_hoy": db.quota_today(conn),
        "quota_budget": int(cfg["quota_budget"]),
        "sync": {"running": SYNC["running"],
                 "lines": SYNC["lines"][-12:], "started": SYNC["started"]},
        "cola": db.cola_resumen(conn) | {"running": COLA["running"]},
    }


def _sync_worker(channel_id: str | None) -> None:
    """Corre en un hilo con SU PROPIA conexión (SQLite es por-hilo)."""
    conn = db.connect()
    try:
        def log(msg: str) -> None:
            with _LOCK:
                SYNC["lines"].append(msg)
        if channel_id:
            result = [sync.sync_channel(conn, channel_id, log=log)]
        else:
            result = sync.sync_all(conn, log=log)
        with _LOCK:
            SYNC["result"] = result
    except Exception:  # el hilo no tiene a quién lanzar; se registra y muestra
        with _LOCK:
            SYNC["lines"].append("✖ Error inesperado en la sincronización:")
            SYNC["lines"].extend(traceback.format_exc().splitlines()[-3:])
    finally:
        conn.close()
        with _LOCK:
            SYNC["running"] = False


def start_sync(channel_id: str | None = None) -> bool:
    with _LOCK:
        if SYNC["running"]:
            return False
        SYNC.update(running=True, lines=[], result=None,
                    started=db.now_str())
    threading.Thread(target=_sync_worker, args=(channel_id,),
                     daemon=True).start()
    return True


def _cola_worker() -> None:
    conn = db.connect()
    try:
        def log(msg: str) -> None:
            with _LOCK:
                COLA["lines"].append(msg)
        jobs.procesar_cola(conn, log=log)
    except Exception:
        with _LOCK:
            COLA["lines"].append("✖ Error inesperado procesando la cola:")
            COLA["lines"].extend(traceback.format_exc().splitlines()[-3:])
    finally:
        conn.close()
        with _LOCK:
            COLA["running"] = False


def start_cola() -> bool:
    """Arranca el procesado de la cola en segundo plano (si no está ya).
    Se dispara solo tras cada encolado: con cuota disponible la edición es
    casi inmediata; sin cuota, queda en espera con su motivo."""
    with _LOCK:
        if COLA["running"]:
            return False
        COLA.update(running=True, lines=[])
    threading.Thread(target=_cola_worker, daemon=True).start()
    return True


class Handler(BaseHTTPRequestHandler):

    # --- infraestructura ------------------------------------------------

    def log_message(self, *_args) -> None:  # sin ruido en la consola
        pass

    def _json(self, obj, status: int = 200) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _html(self, text: str, status: int = 200) -> None:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _redirect(self, where: str) -> None:
        self.send_response(302)
        self.send_header("Location", where)
        self.end_headers()

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            raise ApiError(400, "Cuerpo JSON inválido.")

    def _redirect_uri(self) -> str:
        return f"http://localhost:{self.server.server_port}/oauth/callback"

    # --- rutas ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (nombre que exige la stdlib)
        parsed = urllib.parse.urlparse(self.path)
        path, query = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self._html(
                    (STATIC_DIR / "index.html").read_text(encoding="utf-8"))
            if path == "/api/overview":
                conn = db.connect()
                try:
                    data = db.overview(conn)
                    data["estado"] = _estado(conn)
                finally:
                    conn.close()
                return self._json(data)
            m = re.fullmatch(r"/api/channel/([\w-]+)", path)
            if m:
                days = min(365, max(7, int((query.get("days") or ["90"])[0])))
                conn = db.connect()
                try:
                    detail = db.channel_detail(conn, m.group(1), days)
                finally:
                    conn.close()
                if not detail:
                    raise ApiError(404, "Canal no encontrado.")
                return self._json(detail)
            if path == "/api/sync/status":
                with _LOCK:
                    return self._json({"running": SYNC["running"],
                                       "lines": SYNC["lines"][-30:],
                                       "result": SYNC["result"],
                                       "started": SYNC["started"]})
            if path == "/api/jobs":
                estado = (query.get("estado") or [None])[0]
                conn = db.connect()
                try:
                    lista = db.list_jobs(conn, estado)
                    canales = {c["channel_id"]: c["title"]
                               for c in db.list_channels(conn)}
                finally:
                    conn.close()
                for j in lista:
                    j["canal"] = canales.get(j["channel_id"], j["channel_id"])
                    j["etiqueta"] = jobs.ETIQUETAS.get(j["kind"], j["kind"])
                with _LOCK:
                    corriendo = COLA["running"]
                return self._json({"jobs": lista, "running": corriendo})
            m = re.fullmatch(r"/api/channel/([\w-]+)/playlist/([\w-]+)/items",
                             path)
            if m:
                return self._playlist_items(m.group(1), m.group(2))
            if path == "/api/oauth/start":
                return self._oauth_start()
            if path == "/oauth/callback":
                return self._oauth_callback(query)
            raise ApiError(404, "No encontrado.")
        except ApiError as e:
            self._json({"error": str(e)}, e.status)
        except Exception:
            traceback.print_exc()
            self._json({"error": "Error interno del panel."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        try:
            # Anti-CSRF: el panel guarda tokens. Un formulario en cualquier web
            # podría disparar POSTs a localhost; si el navegador declara un
            # Origin, debe ser este mismo panel (curl y el CLI no mandan Origin
            # y pasan). Los GET no mutan nada, no lo necesitan.
            origin = self.headers.get("Origin", "")
            if origin and urllib.parse.urlparse(origin).hostname not in (
                    "localhost", "127.0.0.1"):
                raise ApiError(403, "Origen no permitido.")
            if path == "/api/sync":
                body = self._body()
                started = start_sync(body.get("channel_id") or None)
                return self._json({"started": started,
                                   "running": True})
            if path == "/api/demo":
                conn = db.connect()
                try:
                    n = demo.seed(conn)
                finally:
                    conn.close()
                return self._json({"canales": n})
            if path == "/api/demo/quitar":
                conn = db.connect()
                try:
                    n = demo.remove(conn)
                finally:
                    conn.close()
                return self._json({"quitados": n})
            m = re.fullmatch(r"/api/channel/([\w-]+)/desconectar", path)
            if m:
                conn = db.connect()
                try:
                    db.delete_channel(conn, m.group(1))
                finally:
                    conn.close()
                return self._json({"desconectado": True})
            if path == "/api/edits":
                return self._encolar_edicion(self._body())
            if path == "/api/edits/lote":
                return self._encolar_lote(self._body())
            if path == "/api/playlists":
                return self._crear_playlist(self._body())
            if path in ("/api/playlist/add", "/api/playlist/remove",
                        "/api/playlist/move"):
                return self._playlist_op(path.rsplit("/", 1)[1], self._body())
            m = re.fullmatch(r"/api/jobs/(\d+)/(reintentar|cancelar)", path)
            if m:
                return self._job_accion(int(m.group(1)), m.group(2))
            if path == "/api/cola/procesar":
                return self._json({"started": start_cola(), "running": True})
            raise ApiError(404, "No encontrado.")
        except ApiError as e:
            self._json({"error": str(e)}, e.status)
        except Exception:
            traceback.print_exc()
            self._json({"error": "Error interno del panel."}, 500)

    # --- Edición (todo termina en la cola; nada escribe directo) --------

    def _encolar_edicion(self, body: dict) -> None:
        channel_id = body.get("channel_id") or ""
        video_id = body.get("video_id") or ""
        if not channel_id or not video_id:
            raise ApiError(400, "Faltan channel_id o video_id.")
        cambios = {k: body[k] for k in ("title", "description", "tags")
                   if k in body}
        imagen = None
        if body.get("image_b64"):
            mime = body.get("image_mime", "")
            if mime not in ("image/jpeg", "image/png"):
                raise ApiError(400, "La miniatura debe ser JPG o PNG.")
            try:
                contenido = base64.b64decode(body["image_b64"], validate=True)
            except (ValueError, TypeError):
                raise ApiError(400, "La imagen llegó corrupta; vuelve a elegirla.")
            if len(contenido) > 2 * 1024 * 1024:
                raise ApiError(400, f"La miniatura pesa "
                               f"{len(contenido) / 1024 / 1024:.1f} MB; "
                               "YouTube admite 2 MB.")
            imagen = (contenido, mime)
        if not cambios and not imagen:
            raise ApiError(400, "No hay ningún cambio que aplicar.")
        conn = db.connect()
        try:
            creados = jobs.encolar_edicion(conn, channel_id, video_id,
                                           cambios, imagen)
        except ValueError as e:
            raise ApiError(400, str(e))
        finally:
            conn.close()
        start_cola()
        return self._json({"jobs": creados})

    def _encolar_lote(self, body: dict) -> None:
        conn = db.connect()
        try:
            resultado = jobs.encolar_lote(
                conn, body.get("channel_id") or "",
                body.get("video_ids") or [],
                body.get("operacion") or "", body.get("params") or {})
        except ValueError as e:
            raise ApiError(400, str(e))
        finally:
            conn.close()
        if resultado["creados"]:
            start_cola()
        return self._json(resultado)

    def _crear_playlist(self, body: dict) -> None:
        titulo = (body.get("titulo") or "").strip()
        if not titulo:
            raise ApiError(400, "La playlist necesita un título.")
        privacidad = body.get("privacidad", "public")
        if privacidad not in ("public", "unlisted", "private"):
            raise ApiError(400, "Privacidad inválida.")
        conn = db.connect()
        try:
            job_id = db.enqueue_job(
                conn, body.get("channel_id") or "", "playlist_create",
                {"titulo": titulo, "descripcion": body.get("descripcion", ""),
                 "privacidad": privacidad}, jobs.COSTOS["playlist_create"])
        finally:
            conn.close()
        start_cola()
        return self._json({"jobs": [job_id]})

    def _playlist_op(self, accion: str, body: dict) -> None:
        channel_id = body.get("channel_id") or ""
        kind = {"add": "playlist_add", "remove": "playlist_remove",
                "move": "playlist_move"}[accion]
        requeridos = {"playlist_add": ("playlist_id", "video_id"),
                      "playlist_remove": ("item_id",),
                      "playlist_move": ("item_id", "playlist_id", "video_id",
                                        "position")}[kind]
        payload = {}
        for campo in requeridos:
            if body.get(campo) in (None, ""):
                raise ApiError(400, f"Falta {campo}.")
            payload[campo] = body[campo]
        conn = db.connect()
        try:
            job_id = db.enqueue_job(conn, channel_id, kind, payload,
                                    jobs.COSTOS[kind])
        finally:
            conn.close()
        start_cola()
        return self._json({"jobs": [job_id]})

    def _job_accion(self, job_id: int, accion: str) -> None:
        conn = db.connect()
        try:
            fila = conn.execute("SELECT status FROM jobs WHERE id=?",
                                (job_id,)).fetchone()
            if not fila:
                raise ApiError(404, "Ese trabajo no existe.")
            if accion == "reintentar":
                if fila["status"] not in ("error", "cancelado"):
                    raise ApiError(400, "Solo se reintentan trabajos en error.")
                db.update_job(conn, job_id, status="pendiente", attempts=0,
                              not_before="", nota="")
            else:
                if fila["status"] not in ("pendiente", "error"):
                    raise ApiError(400, "Ese trabajo ya no se puede cancelar.")
                db.update_job(conn, job_id, status="cancelado")
        finally:
            conn.close()
        if accion == "reintentar":
            start_cola()
        return self._json({"ok": True})

    def _playlist_items(self, channel_id: str, playlist_id: str) -> None:
        """Los items se leen EN VIVO (1 unidad): una playlist cambia desde
        muchos sitios y un editor sobre una copia vieja reordena a ciegas."""
        conn = db.connect()
        try:
            blob = db.get_token_blob(conn, channel_id)
            if blob is None:
                raise ApiError(400, "El canal no tiene token (¿es demo?).")
            token = vault.unseal(blob)
            client = google_api.load_client_secrets()

            def persist(tok: dict) -> None:
                db.save_token(conn, channel_id, vault.seal(tok))

            api = google_api.YouTubeAPI(client, token,
                                        on_token_refresh=persist)
            try:
                resp = api.playlist_items_full(playlist_id)
            except google_api.ApiHttpError as e:
                raise ApiError(502, f"YouTube respondió: {e.message}")
            db.record_sync(conn, channel_id, started_at=db.now_str(), ok=True,
                           detail="cola: lectura de playlist",
                           quota_units=api.quota_units)
        except RuntimeError as e:
            raise ApiError(400, str(e))
        finally:
            conn.close()
        items = []
        for it in resp.get("items") or []:
            sn = it.get("snippet") or {}
            items.append({
                "item_id": it.get("id", ""),
                "video_id": ((sn.get("resourceId") or {}).get("videoId")
                             or (it.get("contentDetails") or {})
                             .get("videoId", "")),
                "title": sn.get("title", ""),
                "position": sn.get("position", 0),
            })
        items.sort(key=lambda x: x["position"])
        return self._json({"items": items})

    # --- OAuth ----------------------------------------------------------

    def _oauth_start(self) -> None:
        try:
            client = google_api.load_client_secrets()
        except RuntimeError as e:
            raise ApiError(400, str(e))
        state = _secrets.token_urlsafe(24)
        now = time.time()
        with _LOCK:
            for s, ts in list(_OAUTH_STATES.items()):  # limpieza de caducados
                if now - ts > _OAUTH_TTL:
                    _OAUTH_STATES.pop(s, None)
            _OAUTH_STATES[state] = now
        url = google_api.build_auth_url(client["client_id"],
                                        self._redirect_uri(), state)
        self._json({"url": url})

    def _oauth_callback(self, query: dict) -> None:
        if query.get("error"):
            return self._html(_pagina(
                "Conexión cancelada",
                "No se autorizó el acceso al canal. Puedes volver a "
                "intentarlo cuando quieras."))
        state = (query.get("state") or [""])[0]
        code = (query.get("code") or [""])[0]
        with _LOCK:
            valido = _OAUTH_STATES.pop(state, None)
        if not valido or time.time() - valido > _OAUTH_TTL:
            return self._html(_pagina(
                "Enlace caducado",
                "El intento de conexión caducó o no salió de este panel. "
                "Vuelve a pulsar «Conectar canal»."), 400)
        if not code:
            return self._html(_pagina(
                "Falta el código", "Google no envió el código de "
                "autorización. Vuelve a intentarlo."), 400)
        try:
            client = google_api.load_client_secrets()
            token = google_api.exchange_code(client, code, self._redirect_uri())
            api = google_api.YouTubeAPI(client, token)
            items = api.channels_mine().get("items") or []
            if not items:
                raise RuntimeError(
                    "La cuenta autorizada no tiene canal de YouTube. Si es un "
                    "canal de marca, elígelo en la pantalla de cuentas de "
                    "Google al conectar.")
            ch = items[0]
            channel_id = ch["id"]
            title = (ch.get("snippet") or {}).get("title", channel_id)
            conn = db.connect()
            try:
                db.upsert_channel(conn, channel_id, title=title,
                                  connected_at=db.now_str(), token_status="ok",
                                  is_demo=0)
                db.save_token(conn, channel_id, vault.seal(token))
            finally:
                conn.close()
            start_sync(channel_id)  # primera foto del canal, en segundo plano
            self._redirect("/?conectado=" + urllib.parse.quote(title))
        except (RuntimeError, google_api.ApiHttpError,
                google_api.ReauthNeeded) as e:
            self._html(_pagina("No se pudo conectar el canal", str(e)), 400)


def _pagina(titulo: str, cuerpo: str) -> str:
    """Página mínima para los desvíos del flujo OAuth (el navegador viene de
    Google, fuera de la SPA). Los textos pueden traer mensajes de error de la
    API: se escapan siempre."""
    import html
    titulo, cuerpo = html.escape(titulo), html.escape(cuerpo)
    return (f"<!doctype html><meta charset='utf-8'>"
            f"<title>{titulo} — Torre de Control</title>"
            f"<body style='font-family:system-ui;max-width:38rem;margin:4rem auto;"
            f"line-height:1.6;padding:0 1rem'>"
            f"<h1 style='font-size:1.3rem'>{titulo}</h1><p>{cuerpo}</p>"
            f"<p><a href='/'>&larr; Volver a la Torre de Control</a></p>")


def make_server(port: int = 0) -> ThreadingHTTPServer:
    """Separado de serve() para que las pruebas levanten el servidor en un
    puerto efímero y lo apaguen limpio."""
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int | None = None, open_browser: bool = True) -> None:
    port = port or int(config.load_panel_config()["port"])
    server = make_server(port)
    url = f"http://localhost:{port}"
    print(f"🎛️ Torre de Control → {url}")
    print("   (deja esta ventana abierta; Ctrl+C para detener)")
    if open_browser:
        import webbrowser
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
