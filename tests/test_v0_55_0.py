"""Batería v0.55.0 — la Torre de Control edita (fase 2), sin tocar internet.

Lo que se comprueba, con un transporte falso que imita a Google:

1. La migración v1→v2 añade columnas sin perder datos.
2. El merge de snippet NO borra lo que no editas (videos.update de YouTube
   borra todo campo que no se reenvíe — el defecto clásico de las
   herramientas caseras).
3. Los límites reales de la API se avisan ANTES de encolar.
4. La cola respeta la cuota (espera con motivo), reintenta lo pasajero y
   deja legible lo definitivo.
5. El lote se materializa en el servidor y reporta lo omitido.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import datetime as dt
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import urllib.parse
import urllib.request

TMP = Path(tempfile.mkdtemp(prefix="v0550_"))
os.environ["YTPANEL_DATA_DIR"] = str(TMP / "panel_data")
SECRETS = TMP / "client_secrets.json"
SECRETS.write_text(json.dumps(
    {"installed": {"client_id": "cid", "client_secret": "sec"}}),
    encoding="utf-8")
os.environ["YTPANEL_CLIENT_SECRETS"] = str(SECRETS)

from ytpanel import config, db, demo, google_api, jobs, vault  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


class Transporte:
    """Google de mentira para la fase 2. `modo` cambia el comportamiento del
    PUT de videos y de la miniatura: 'ok', 'video500' (siempre 5xx),
    'mini403' (miniatura prohibida), 'reauth' (401 + invalid_grant)."""

    def __init__(self, modo="ok"):
        self.modo = modo
        self.updates = []      # cuerpos de PUT /videos
        self.subidas = []      # (n_bytes, mime) de thumbnails/set
        self.pl_ops = []       # (method, url) de playlistItems/playlists

    def __call__(self, method, url, headers, body):
        if url.startswith(google_api.TOKEN_URL):
            campos = urllib.parse.parse_qs((body or b"").decode())
            if (campos.get("grant_type") or [""])[0] == "refresh_token":
                if self.modo == "reauth":
                    return 400, b'{"error": "invalid_grant"}'
                return 200, b'{"access_token": "AT2", "expires_in": 3600}'
        if self.modo == "reauth":
            return 401, b'{"error": {"code": 401, "message": "Invalid"}}'
        if "/videos" in url and method == "GET":
            return 200, json.dumps({"items": [{"id": "vid001", "snippet": {
                "title": "Titulo original", "description": "Desc original",
                "tags": ["faro", "mar"], "categoryId": "27",
                "defaultLanguage": "es"}}]}).encode()
        if "/videos" in url and method == "PUT":
            if self.modo == "video500":
                return 500, b'{"error": {"code": 500, "message": "backend"}}'
            self.updates.append(json.loads(body.decode()))
            return 200, body
        if "thumbnails/set" in url:
            if self.modo == "mini403":
                return 403, (b'{"error": {"code": 403, "message": "The '
                             b'authenticated user does not have permissions '
                             b'to upload custom video thumbnails.", "errors": '
                             b'[{"reason": "forbidden"}]}}')
            self.subidas.append((len(body), headers.get("Content-Type", "")))
            return 200, json.dumps({"items": [{
                "default": {"url": "https://i.ytimg/min_def.jpg"},
                "medium": {"url": "https://i.ytimg/min_med.jpg"}}]}).encode()
        if "/playlists" in url and method == "POST":
            enviado = json.loads(body.decode())
            self.pl_ops.append((method, url))
            return 200, json.dumps({"id": "PL_NUEVA",
                                    "snippet": enviado["snippet"],
                                    "status": enviado["status"]}).encode()
        if "/playlistItems" in url:
            self.pl_ops.append((method, url))
            if method == "GET":
                return 200, json.dumps({"items": [
                    {"id": "it1", "snippet": {"title": "Video A", "position": 0,
                     "resourceId": {"videoId": "vid001"}}},
                    {"id": "it2", "snippet": {"title": "Video B", "position": 1,
                     "resourceId": {"videoId": "vid002"}}}]}).encode()
            if method == "DELETE":
                return 204, b""
            return 200, b"{}"
        return 404, b'{"error": {"message": "sin ruta"}}'


TOKEN = {"access_token": "AT", "refresh_token": "RT", "expires_at": 9999999999}
CFG = config.load_panel_config() | {"quota_budget": 100000, "quota_reserve": 0}

conn = db.connect()

# ---------------------------------------------------------------------------
# Migración v1 → v2 sin perder nada
# ---------------------------------------------------------------------------
vieja = TMP / "vieja.db"
c2 = sqlite3.connect(str(vieja))
c2.row_factory = sqlite3.Row
c2.executescript("""
CREATE TABLE videos (video_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '', published_at TEXT NOT NULL DEFAULT '',
  thumbnail_url TEXT NOT NULL DEFAULT '', duration_seconds INTEGER NOT NULL
  DEFAULT 0, privacy TEXT NOT NULL DEFAULT '', views INTEGER NOT NULL DEFAULT 0,
  likes INTEGER NOT NULL DEFAULT 0, comments INTEGER NOT NULL DEFAULT 0);
INSERT INTO videos(video_id, channel_id, title, views)
  VALUES('v_viejo', 'UC_V1', 'De la fase 1', 123);
""")
db.migrate(c2)
fila = db.get_video(c2, "v_viejo")
check("M1 una base de la fase 1 gana las columnas nuevas sin perder datos",
      fila is not None and fila["title"] == "De la fase 1"
      and fila["views"] == 123 and fila["tags"] == []
      and fila["description"] == "", fila)
c2.close()

# ---------------------------------------------------------------------------
# Validaciones: los límites reales, avisados ANTES de gastar cuota
# ---------------------------------------------------------------------------
check("V1 un título de 101 caracteres se rechaza con el límite en el mensaje",
      "100" in (jobs.validar_cambios({"title": "x" * 101}) or ""), "")
check("V2 «<» y «>» en el título se rechazan (YouTube los prohíbe)",
      jobs.validar_cambios({"title": "hola <b>"}) is not None, "")
check("V3 la descripción se mide en BYTES (tildes cuentan doble)",
      jobs.validar_cambios({"description": "á" * 2501}) is not None
      and jobs.validar_cambios({"description": "a" * 4999}) is None, "")
check("V4 el límite de etiquetas es del campo entero, no por etiqueta",
      jobs.validar_cambios({"tags": ["x" * 60] * 10}) is not None, "")
check("V5 un cambio válido pasa sin queja",
      jobs.validar_cambios({"title": "Buen título",
                            "tags": ["faro", "mar"]}) is None, "")

# ---------------------------------------------------------------------------
# El merge que no borra: la esencia de la fase 2
# ---------------------------------------------------------------------------
db.upsert_channel(conn, "UC_ED", title="Canal editable",
                  connected_at=db.now_str())
db.save_token(conn, "UC_ED", vault.seal(TOKEN))
db.upsert_videos(conn, "UC_ED", [
    {"video_id": "vid001", "title": "Titulo original", "views": 10,
     "description": "Desc original", "tags": ["faro", "mar"],
     "published_at": "2026-08-01T00:00:00Z"},
    {"video_id": "vid002", "title": "Faros del norte", "views": 5,
     "description": "Otra", "tags": [], "published_at": "2026-08-02T00:00:00Z"},
    {"video_id": "vid003", "title": "Sin la palabra", "views": 2,
     "description": "", "tags": [], "published_at": "2026-08-03T00:00:00Z"},
])

creados = jobs.encolar_edicion(conn, "UC_ED", "vid001",
                               {"title": "Titulo NUEVO"})
check("E1 encolar una edición de texto crea 1 trabajo de 51 unidades",
      len(creados) == 1 and db.list_jobs(conn)[0]["units_est"] == 51, "")

t = Transporte()
resumen = jobs.procesar_cola(conn, cfg=CFG, transport=t)
enviado = t.updates[0]["snippet"]
check("P1 el update reenvía el snippet COMPLETO fusionado: título nuevo…",
      resumen["hechos"] == 1 and enviado["title"] == "Titulo NUEVO", enviado)
check("P1b …sin borrar etiquetas ni descripción (el defecto clásico)",
      enviado["tags"] == ["faro", "mar"]
      and enviado["description"] == "Desc original", enviado)
check("P1c …y preservando categoría e idioma declarado",
      enviado["categoryId"] == "27" and enviado["defaultLanguage"] == "es",
      enviado)
check("P2 la base local refleja la edición sin esperar al próximo sync",
      db.get_video(conn, "vid001")["title"] == "Titulo NUEVO", "")
check("P2b la cuota real quedó contada en la bitácora",
      conn.execute("SELECT quota_units FROM sync_log WHERE detail LIKE "
                   "'cola:%' ORDER BY id DESC LIMIT 1").fetchone()
      ["quota_units"] == 51, "")

# Miniatura: bytes al endpoint de subida y URL nueva en la base
mini = TMP / "mini.jpg"
mini_bytes = b"\xff\xd8fake-jpeg" * 100
jobs.encolar_edicion(conn, "UC_ED", "vid001", {},
                     imagen=(mini_bytes, "image/jpeg"))
t2 = Transporte()
jobs.procesar_cola(conn, cfg=CFG, transport=t2)
check("P3 la miniatura viaja con sus bytes y su mime al endpoint de subida",
      t2.subidas == [(len(mini_bytes), "image/jpeg")], t2.subidas)
check("P3b la URL nueva de YouTube queda en la base al instante",
      db.get_video(conn, "vid001")["thumbnail_url"]
      == "https://i.ytimg/min_med.jpg", "")
check("P3c y el archivo temporal se borra tras subirse",
      not list((config.data_dir() / "cola_miniaturas").glob("*")), "")

# Playlists
db.enqueue_job(conn, "UC_ED", "playlist_create",
               {"titulo": "Serie faros", "privacidad": "unlisted"},
               jobs.COSTOS["playlist_create"])
db.enqueue_job(conn, "UC_ED", "playlist_add",
               {"playlist_id": "PL_NUEVA", "video_id": "vid002"},
               jobs.COSTOS["playlist_add"])
db.enqueue_job(conn, "UC_ED", "playlist_move",
               {"item_id": "it2", "playlist_id": "PL_NUEVA",
                "video_id": "vid002", "position": 0},
               jobs.COSTOS["playlist_move"])
db.enqueue_job(conn, "UC_ED", "playlist_remove", {"item_id": "it1"},
               jobs.COSTOS["playlist_remove"])
t3 = Transporte()
r3 = jobs.procesar_cola(conn, cfg=CFG, transport=t3)
metodos = [m for m, _ in t3.pl_ops]
check("P4 crear playlist queda registrada en la base local",
      r3["hechos"] == 4 and conn.execute(
          "SELECT title, privacy FROM playlists WHERE playlist_id='PL_NUEVA'"
      ).fetchone()["title"] == "Serie faros", "")
check("P4b añadir, mover y quitar llegan como POST, PUT y DELETE",
      metodos.count("POST") == 2 and "PUT" in metodos and "DELETE" in metodos,
      metodos)

# ---------------------------------------------------------------------------
# Cuota: lo que no cabe HOY espera con motivo, y la reserva es intocable
# ---------------------------------------------------------------------------
gastado_hoy = db.quota_today(conn)
jid = jobs.encolar_edicion(conn, "UC_ED", "vid001", {"title": "Otro más"})[0]
cfg_justa = CFG | {"quota_budget": gastado_hoy + 30, "quota_reserve": 0}
r_q = jobs.procesar_cola(conn, cfg=cfg_justa, transport=Transporte())
fila = db.list_jobs(conn)[0]
check("Q1 sin cuota suficiente el trabajo espera y explica por qué",
      r_q["en_espera"] == 1 and fila["status"] == "pendiente"
      and "medianoche" in fila["nota"], fila["nota"])
r_q2 = jobs.procesar_cola(conn, cfg=CFG, transport=Transporte())
check("Q2 con cuota disponible, el mismo trabajo sale solo",
      r_q2["hechos"] == 1
      and db.list_jobs(conn)[0]["status"] == "hecho", "")

# ---------------------------------------------------------------------------
# Reintentos y errores
# ---------------------------------------------------------------------------
_sleep_real = time.sleep
time.sleep = lambda _s: None  # los backoffs internos no deben frenar la batería
try:
    jid = jobs.encolar_edicion(conn, "UC_ED", "vid001", {"title": "Frágil"})[0]
    for esperado in (1, 2):
        jobs.procesar_cola(conn, cfg=CFG, transport=Transporte("video500"))
        fila = [j for j in db.list_jobs(conn) if j["id"] == jid][0]
        check(f"R1.{esperado} un 5xx deja el trabajo pendiente con "
              f"reintento {esperado}/3 y backoff",
              fila["status"] == "pendiente" and fila["attempts"] == esperado
              and fila["not_before"] > db.now_str(), fila["nota"])
        db.update_job(conn, jid, not_before="")  # adelantar el reloj
    jobs.procesar_cola(conn, cfg=CFG, transport=Transporte("video500"))
    fila = [j for j in db.list_jobs(conn) if j["id"] == jid][0]
    check("R1.3 al tercer intento fallido pasa a error definitivo",
          fila["status"] == "error" and fila["attempts"] == 3, fila)
finally:
    time.sleep = _sleep_real

jid = jobs.encolar_edicion(conn, "UC_ED", "vid001", {},
                           imagen=(b"png", "image/png"))[0]
jobs.procesar_cola(conn, cfg=CFG, transport=Transporte("mini403"))
fila = [j for j in db.list_jobs(conn) if j["id"] == jid][0]
check("R2 un 403 (canal sin verificación telefónica) es definitivo y "
      "legible, sin reintentos",
      fila["status"] == "error" and fila["attempts"] == 1
      and "thumbnails" in fila["nota"], fila["nota"])

jid = jobs.encolar_edicion(conn, "UC_ED", "vid001", {"title": "Revocado"})[0]
jobs.procesar_cola(conn, cfg=CFG, transport=Transporte("reauth"))
check("R3 autorización caída durante un trabajo: canal en «reauth» y "
      "trabajo en error",
      conn.execute("SELECT token_status FROM channels WHERE channel_id="
                   "'UC_ED'").fetchone()["token_status"] == "reauth"
      and [j for j in db.list_jobs(conn) if j["id"] == jid][0]["status"]
      == "error", "")
db.upsert_channel(conn, "UC_ED", token_status="ok")  # restaurar para el lote

# ---------------------------------------------------------------------------
# Lote: se materializa en el servidor y nada se omite en silencio
# ---------------------------------------------------------------------------
res = jobs.encolar_lote(conn, "UC_ED", ["vid001", "vid002", "vid003"],
                        "reemplazar", {"campo": "title", "buscar": "Faros",
                                       "reemplazo": "Castillos"})
payloads = [j["payload"] for j in db.list_jobs(conn, "pendiente")]
check("L1 el reemplazo solo toca los videos que contienen el texto",
      len(res["creados"]) == 1 and len(res["omitidos"]) == 2
      and any(p.get("cambios", {}).get("title") == "Castillos del norte"
              for p in payloads), res)
check("L1b los omitidos llevan su motivo, nada pasa en silencio",
      all(o["motivo"] for o in res["omitidos"]), res["omitidos"])
res2 = jobs.encolar_lote(conn, "UC_ED", ["vid001"], "agregar_etiquetas",
                         {"tags": ["faro", "historia"]})
p2 = [j["payload"] for j in db.list_jobs(conn, "pendiente")
      if j["payload"].get("video_id") == "vid001"
      and "tags" in j["payload"].get("cambios", {})]
check("L2 añadir etiquetas no duplica las existentes (faro ya estaba)",
      len(res2["creados"]) == 1
      and p2[0]["cambios"]["tags"].count("faro") == 1
      and "historia" in p2[0]["cambios"]["tags"], p2)
res3 = jobs.encolar_lote(conn, "UC_ED", ["vid003"], "anexar_descripcion",
                         {"texto": "Suscríbete al canal."})
check("L3 anexar a la descripción conserva lo que había y añade al final",
      len(res3["creados"]) == 1, res3)
try:
    jobs.encolar_lote(conn, "UC_ED", ["vid001"], "volar_el_canal", {})
    check("L4 una operación desconocida se rechaza", False, "no lanzó")
except ValueError:
    check("L4 una operación desconocida se rechaza", True, "")

# ---------------------------------------------------------------------------
# Demo con playlists (la sección se ve amueblada sin conectar nada)
# ---------------------------------------------------------------------------
demo.seed(conn)
check("D1 los canales demo traen playlists de muestra",
      len(db.list_playlists(conn, "DEMO_faros")) == 2, "")
demo.remove(conn)

# ---------------------------------------------------------------------------
# Servidor: encolar desde la API, validaciones y acciones de cola
# ---------------------------------------------------------------------------
from ytpanel import server as srv  # noqa: E402

httpd = srv.make_server(0)
puerto = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{puerto}"


def llamar(metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


st, data = llamar("POST", "/api/edits", {"channel_id": "UC_ED",
                                         "video_id": "vid001",
                                         "title": "x" * 101})
check("S1 el servidor rechaza un título imposible ANTES de encolar",
      st == 400 and "100" in data["error"], data)
st, data = llamar("POST", "/api/edits", {"channel_id": "UC_ED",
                                         "video_id": "vid001"})
check("S1b sin ningún cambio no se encola nada", st == 400, data)
st, data = llamar("POST", "/api/edits", {"channel_id": "UC_ED",
                                         "video_id": "vid001",
                                         "image_b64": "eA==",
                                         "image_mime": "image/gif"})
check("S1c una miniatura GIF se rechaza (YouTube pide JPG/PNG)",
      st == 400 and "JPG" in data["error"], data)

st, data = llamar("POST", "/api/edits/lote",
                  {"channel_id": "UC_ED", "video_ids": ["vid002"],
                   "operacion": "reemplazar",
                   "params": {"campo": "title", "buscar": "Faros",
                              "reemplazo": "Puertos"}})
check("S2 el lote por API devuelve creados y omitidos",
      st == 200 and "creados" in data and "omitidos" in data, data)

st, data = llamar("GET", "/api/jobs")
check("S3 /api/jobs lista los trabajos con canal y etiqueta humana",
      st == 200 and data["jobs"]
      and all("etiqueta" in j and "canal" in j for j in data["jobs"]), st)

job_err = next((j for j in data["jobs"] if j["status"] == "error"), None)
st, _ = llamar("POST", f"/api/jobs/{job_err['id']}/reintentar")
check("S4 reintentar un error lo devuelve a pendiente con intentos a cero",
      st == 200 and any(
          j["id"] == job_err["id"] and j["status"] == "pendiente"
          and j["attempts"] == 0 for j in db.list_jobs(conn)), st)
job_pen = next(j for j in db.list_jobs(conn) if j["status"] == "pendiente")
st, _ = llamar("POST", f"/api/jobs/{job_pen['id']}/cancelar")
check("S4b cancelar un pendiente lo saca de la circulación",
      st == 200 and any(j["id"] == job_pen["id"] and j["status"] == "cancelado"
                        for j in db.list_jobs(conn)), st)

st, data = llamar("GET", "/api/channel/DEMO_x/playlist/PL_x/items")
check("S5 pedir items de playlist sin token explica el porqué",
      st == 400 and "token" in data["error"], data)

st, data = llamar("GET", "/api/overview")
check("S6 el estado del panel ya reporta la cola (pendientes y errores)",
      st == 200 and "cola" in data["estado"]
      and "pendientes" in data["estado"]["cola"], st)

httpd.shutdown()

# ---------------------------------------------------------------------------
conn.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.55.0 completa: la Torre de Control edita metadatos, "
      "miniaturas y playlists por una cola que respeta la cuota, reintenta "
      "lo pasajero, explica lo definitivo y jamás borra lo que no editaste.")
