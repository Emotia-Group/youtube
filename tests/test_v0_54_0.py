"""Batería v0.54.0 — la Torre de Control (ytpanel), de punta a punta y sin red.

Todo el panel se ejercita con un TRANSPORTE FALSO que imita a Google: OAuth
(intercambio de código, refresco, invalid_grant), Data API (canal, playlist,
videos) y Analytics (métricas diarias e ingresos, incluido el 403 de un canal
fuera de YPP). Ni una sola llamada sale de esta máquina, y los datos viven en
carpetas temporales (YTPANEL_DATA_DIR) — tus canales reales ni se ven.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import datetime as dt
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import urllib.request

TMP = Path(tempfile.mkdtemp(prefix="v0540_"))
os.environ["YTPANEL_DATA_DIR"] = str(TMP / "panel_data")
SECRETS = TMP / "client_secrets.json"
SECRETS.write_text(json.dumps(
    {"installed": {"client_id": "cid-prueba", "client_secret": "sec-prueba"}}),
    encoding="utf-8")
os.environ["YTPANEL_CLIENT_SECRETS"] = str(SECRETS)

from ytpanel import config, db, demo, google_api, sync, vault  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


HOY = "2026-08-13"


class TransportFalso:
    """Imita los endpoints de Google. `modo_ingresos` gobierna la consulta
    monetaria: 'ok' responde ingresos, '403' la rechaza (canal sin YPP).
    `falla_auth` simula token revocado: la API da 401 y el refresh,
    invalid_grant."""

    def __init__(self, modo_ingresos="ok", falla_auth=False):
        self.modo_ingresos = modo_ingresos
        self.falla_auth = falla_auth
        self.calls = []
        self.refrescos = 0

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        if url.startswith(google_api.TOKEN_URL):
            campos = urllib.parse.parse_qs((body or b"").decode())
            grant = (campos.get("grant_type") or [""])[0]
            if grant == "authorization_code":
                return 200, json.dumps({
                    "access_token": "AT1", "refresh_token": "RT_SECRETO_123",
                    "expires_in": 3600, "scope": "x"}).encode()
            if self.falla_auth:
                return 400, b'{"error": "invalid_grant"}'
            self.refrescos += 1
            return 200, json.dumps({"access_token": "AT2",
                                    "expires_in": 3600}).encode()
        if self.falla_auth:
            return 401, (b'{"error": {"code": 401, "message": "Invalid '
                         b'Credentials", "errors": [{"reason": '
                         b'"authError"}]}}')
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "/channels" in url:
            return 200, json.dumps({"items": [{
                "id": "UC_PRUEBA",
                "snippet": {"title": "Canal de Prueba",
                            "customUrl": "@canaldeprueba",
                            "thumbnails": {"default": {"url": ""}}},
                "statistics": {"subscriberCount": "1200",
                               "viewCount": "34000", "videoCount": "12"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU_PRUEBA"}},
            }]}).encode()
        if "/playlistItems" in url:
            return 200, json.dumps({"items": [
                {"contentDetails": {"videoId": "vid001"}},
                {"contentDetails": {"videoId": "vid002"}},
            ]}).encode()
        if "/videos" in url:
            return 200, json.dumps({"items": [
                {"id": "vid001",
                 "snippet": {"title": "El faro de prueba",
                             "publishedAt": "2026-08-01T16:00:00Z",
                             "thumbnails": {"medium": {"url": ""}}},
                 "contentDetails": {"duration": "PT10M3S"},
                 "status": {"privacyStatus": "public"},
                 "statistics": {"viewCount": "5000", "likeCount": "200",
                                "commentCount": "20"}},
                {"id": "vid002",
                 "snippet": {"title": "Segundo video",
                             "publishedAt": "2026-08-08T16:00:00Z",
                             "thumbnails": {}},
                 "contentDetails": {"duration": "PT8M"},
                 "status": {"privacyStatus": "unlisted"},
                 "statistics": {"viewCount": "900"}},
            ]}).encode()
        if url.startswith(google_api.ANALYTICS_API):
            ini = dt.date.fromisoformat(q["startDate"][0])
            fin = dt.date.fromisoformat(q["endDate"][0])
            fechas = [(ini + dt.timedelta(days=i)).isoformat()
                      for i in range((fin - ini).days + 1)]
            if q["metrics"][0] == "estimatedRevenue":
                if self.modo_ingresos == "403":
                    return 403, (b'{"error": {"code": 403, "message": '
                                 b'"Insufficient permission", "errors": '
                                 b'[{"reason": "forbidden"}]}}')
                return 200, json.dumps({
                    "columnHeaders": [{"name": "day"},
                                      {"name": "estimatedRevenue"}],
                    "rows": [[f, 1.5] for f in fechas]}).encode()
            return 200, json.dumps({
                "columnHeaders": [{"name": "day"}, {"name": "views"},
                                  {"name": "estimatedMinutesWatched"},
                                  {"name": "averageViewDuration"},
                                  {"name": "subscribersGained"},
                                  {"name": "subscribersLost"},
                                  {"name": "likes"}, {"name": "comments"},
                                  {"name": "shares"}],
                "rows": [[f, 100, 500.0, 300.0, 4, 1, 8, 2, 1]
                         for f in fechas]}).encode()
        return 404, b'{"error": {"message": "sin ruta"}}'


# ---------------------------------------------------------------------------
# Base de datos: esquema, upserts y ventanas
# ---------------------------------------------------------------------------
conn = db.connect()
db.migrate(conn)  # idempotente: correrla dos veces no debe romper nada
check("T1 el esquema se crea y migrar dos veces no rompe",
      conn.execute("SELECT COUNT(*) c FROM channels").fetchone()["c"] == 0, "")

db.upsert_channel(conn, "UC_X", title="Canal X", subscriber_count=10)
db.upsert_channel(conn, "UC_X", token_status="reauth")
fila = conn.execute("SELECT * FROM channels WHERE channel_id='UC_X'").fetchone()
check("T2 el upsert parcial actualiza SOLO lo enviado (el título sobrevive)",
      fila["title"] == "Canal X" and fila["token_status"] == "reauth",
      dict(fila))

db.upsert_daily(conn, "UC_X", {"2026-08-01": {"views": 5}})
db.upsert_daily(conn, "UC_X", {"2026-08-01": {"views": 9}})
filas = conn.execute("SELECT COUNT(*) c, MAX(views) v FROM channel_daily "
                     "WHERE channel_id='UC_X'").fetchone()
check("T3 re-sincronizar un día lo ACTUALIZA, nunca lo duplica",
      filas["c"] == 1 and filas["v"] == 9, dict(filas))

# Serie sintética conocida: día i (0..55) → i vistas
base = dt.date(2026, 6, 1)
db.upsert_daily(conn, "UC_VENTANAS",
                {(base + dt.timedelta(days=i)).isoformat(): {"views": i}
                 for i in range(56)})
db.upsert_channel(conn, "UC_VENTANAS", title="Ventanas")
resumen = db.channel_summary(
    conn, dict(conn.execute("SELECT * FROM channels WHERE "
                            "channel_id='UC_VENTANAS'").fetchone()))
check("T4 ventanas 7/28 días y sus periodos previos (ancladas al último dato)",
      resumen["views_7d"] == sum(range(49, 56))
      and resumen["views_prev_7d"] == sum(range(42, 49))
      and resumen["views_28d"] == sum(range(28, 56))
      and resumen["views_prev_28d"] == sum(range(28)),
      {k: resumen[k] for k in ("views_7d", "views_prev_7d", "views_28d",
                               "views_prev_28d")})
check("T4b la sparkline trae exactamente los últimos 28 días",
      len(resumen["sparkline"]) == 28
      and resumen["sparkline"][-1]["views"] == 55, "")
check("T5 sin NINGÚN dato de ingresos el total es None (no un 0 engañoso)",
      resumen["revenue_28d"] is None, str(resumen["revenue_28d"]))
db.set_revenue(conn, "UC_VENTANAS", {(base + dt.timedelta(days=55)).isoformat(): 2.5})
resumen = db.channel_summary(
    conn, dict(conn.execute("SELECT * FROM channels WHERE "
                            "channel_id='UC_VENTANAS'").fetchone()))
check("T5b con un día de ingresos, el total 28d los suma",
      resumen["revenue_28d"] == 2.5, str(resumen["revenue_28d"]))

# ---------------------------------------------------------------------------
# Bóveda: cifrado real y modo degradado
# ---------------------------------------------------------------------------
token_demo = {"access_token": "AT", "refresh_token": "RT_SECRETO_123",
              "expires_at": 9999999999}
blob = vault.seal(token_demo)
check("T6 la bóveda hace ida y vuelta sin perder nada",
      vault.unseal(blob) == token_demo, "")
if vault.available():
    check("T6b con cryptography instalada, el blob NO contiene el refresh "
          "token en claro", b"RT_SECRETO_123" not in blob, "")
else:
    check("T6b sin cryptography, el blob queda marcado PLAIN1 (aviso honesto)",
          blob.startswith(b"PLAIN1:"), blob[:12])

_disponible = vault.available
vault.available = lambda: False
blob_plano = vault.seal(token_demo)
check("T6c el modo degradado (sin cryptography) también hace ida y vuelta",
      blob_plano.startswith(b"PLAIN1:")
      and vault.unseal(blob_plano) == token_demo, "")
vault.available = _disponible
check("T6d un token guardado en claro se sigue leyendo tras instalar "
      "cryptography", vault.unseal(blob_plano) == token_demo, "")

# ---------------------------------------------------------------------------
# OAuth: URL, intercambio y refresco
# ---------------------------------------------------------------------------
url = google_api.build_auth_url("cid-prueba", "http://localhost:8766/oauth/callback",
                                "estado123")
check("T7 la URL de autorización pide los permisos del panel completo",
      "youtube.force-ssl" in url and "yt-analytics-monetary.readonly" in url
      and "yt-analytics.readonly" in url, url)
check("T7b …con refresh token garantizado (offline + consent) y elección de "
      "cuenta", "access_type=offline" in url and "consent" in url
      and "select_account" in url and "state=estado123" in url, url)

t = TransportFalso()
token = google_api.exchange_code(google_api.load_client_secrets(), "codigo-x",
                                 "http://localhost:8766/oauth/callback",
                                 transport=t)
check("T8 el intercambio de código entrega refresh token y caducidad futura",
      token["refresh_token"] == "RT_SECRETO_123"
      and token["expires_at"] > time.time(), "")

api = google_api.YouTubeAPI(google_api.load_client_secrets(),
                            token | {"expires_at": 0}, transport=t,
                            on_token_refresh=lambda tk: None)
api.channels_mine()
check("T9 un token caducado se refresca solo antes de llamar",
      t.refrescos == 1 and api.token["access_token"] == "AT2", "")

t_rev = TransportFalso(falla_auth=True)
try:
    google_api.refresh(google_api.load_client_secrets(),
                       token, transport=t_rev)
    check("T9b invalid_grant levanta ReauthNeeded", False, "no lanzó")
except google_api.ReauthNeeded:
    check("T9b invalid_grant levanta ReauthNeeded", True, "")

# ---------------------------------------------------------------------------
# Sync completo, cuota, ingresos 403, incremental y reauth
# ---------------------------------------------------------------------------
CFG = config.load_panel_config()
db.upsert_channel(conn, "UC_PRUEBA", title="(pendiente)", connected_at=db.now_str())
db.save_token(conn, "UC_PRUEBA", vault.seal(token))
t_sync = TransportFalso()
r = sync.sync_channel(conn, "UC_PRUEBA", cfg=CFG, transport=t_sync, today=HOY)
canal = conn.execute("SELECT * FROM channels WHERE channel_id='UC_PRUEBA'").fetchone()
check("T10 el sync completo actualiza la ficha del canal",
      r["ok"] and canal["title"] == "Canal de Prueba"
      and canal["subscriber_count"] == 1200
      and canal["uploads_playlist"] == "UU_PRUEBA", r)
check("T10b …trae los videos con duración y contadores",
      r["videos"] == 2 and conn.execute(
          "SELECT duration_seconds FROM videos WHERE video_id='vid001'"
      ).fetchone()["duration_seconds"] == 603, "")
check("T10c …y las métricas diarias del rango inicial (history_days)",
      r["dias"] == CFG["history_days"] + 1, r["dias"])
check("T10d los ingresos se fusionan y el canal queda monetization=ok",
      canal["monetization"] == "ok" and conn.execute(
          "SELECT revenue FROM channel_daily WHERE channel_id='UC_PRUEBA' "
          "AND date=?", (HOY,)).fetchone()["revenue"] == 1.5, "")
check("T11 la cuota contada es 3 unidades (canal + playlist + videos; "
      "Analytics no gasta de aquí)", r["quota"] == 3, r["quota"])
check("T11b y quota_today la refleja en el medidor",
      db.quota_today(conn) >= 3, db.quota_today(conn))

t_inc = TransportFalso()
r2 = sync.sync_channel(conn, "UC_PRUEBA", cfg=CFG, transport=t_inc,
                       today="2026-08-14")
urls_analytics = [u for m, u in t_inc.calls
                  if u.startswith(google_api.ANALYTICS_API)]
qs = urllib.parse.parse_qs(urllib.parse.urlparse(urls_analytics[0]).query)
esperado = (dt.date.fromisoformat(HOY)
            - dt.timedelta(days=CFG["resync_overlap_days"])).isoformat()
check("T12 el segundo sync es INCREMENTAL: pide desde el último día menos el "
      "solape de consolidación", qs["startDate"][0] == esperado,
      f"pidió {qs['startDate'][0]}, esperaba {esperado}")
check("T12b y solo re-escribe ese tramo",
      r2["ok"] and r2["dias"] == CFG["resync_overlap_days"] + 2, r2["dias"])

db.upsert_channel(conn, "UC_SIN_YPP", connected_at=db.now_str())
db.save_token(conn, "UC_SIN_YPP", vault.seal(token))
r3 = sync.sync_channel(conn, "UC_SIN_YPP", cfg=CFG,
                       transport=TransportFalso(modo_ingresos="403"), today=HOY)
canal3 = conn.execute("SELECT * FROM channels WHERE channel_id='UC_SIN_YPP'").fetchone()
check("T13 un canal sin acceso a ingresos NO rompe su sync: métricas sí, "
      "monetization=sin_acceso", r3["ok"] and r3["dias"] > 0
      and canal3["monetization"] == "sin_acceso", r3)

db.upsert_channel(conn, "UC_REVOCADO", connected_at=db.now_str())
db.save_token(conn, "UC_REVOCADO", vault.seal(token))
r4 = sync.sync_channel(conn, "UC_REVOCADO", cfg=CFG,
                       transport=TransportFalso(falla_auth=True), today=HOY)
canal4 = conn.execute("SELECT * FROM channels WHERE channel_id='UC_REVOCADO'").fetchone()
check("T14 autorización revocada → canal marcado «reauth» y error legible, "
      "sin tumbar nada", not r4["ok"] and canal4["token_status"] == "reauth"
      and "Reconecta" in (r4["error"] or ""), r4)

check("T14b el sync de un canal caído queda en la bitácora como fallo",
      conn.execute("SELECT ok FROM sync_log WHERE channel_id='UC_REVOCADO' "
                   "ORDER BY id DESC LIMIT 1").fetchone()["ok"] == 0, "")

# ---------------------------------------------------------------------------
# Demo determinista
# ---------------------------------------------------------------------------
n = demo.seed(conn)
demo_rows = [c for c in db.list_channels(conn) if c["is_demo"]]
check("T15 la demo crea 4 canales y re-crearla no duplica",
      n == 4 and len(demo_rows) == 4 and demo.seed(conn) == 4
      and len([c for c in db.list_channels(conn) if c["is_demo"]]) == 4, "")
faros = db.channel_summary(
    conn, dict(conn.execute("SELECT * FROM channels WHERE "
                            "channel_id='DEMO_faros'").fetchone()))
mentes = conn.execute("SELECT token_status FROM channels WHERE "
                      "channel_id='DEMO_mentes'").fetchone()
check("T15b cubre los estados reales: monetizado con ingresos y canal en "
      "«reconectar»", faros["revenue_28d"] is not None
      and faros["views_28d"] > 0 and mentes["token_status"] == "reauth", "")
quitados = demo.remove(conn)
check("T15c «quitar demo» borra los 4 canales y TODOS sus datos",
      quitados == 4
      and not [c for c in db.list_channels(conn) if c["is_demo"]]
      and conn.execute("SELECT COUNT(*) c FROM channel_daily WHERE channel_id "
                       "LIKE 'DEMO_%'").fetchone()["c"] == 0, "")

# ---------------------------------------------------------------------------
# Parsers sueltos
# ---------------------------------------------------------------------------
check("T16 duraciones ISO: PT1H2M3S=3723, PT15S=15, vacío=0, P1DT1H=90000",
      sync.iso_duration_seconds("PT1H2M3S") == 3723
      and sync.iso_duration_seconds("PT15S") == 15
      and sync.iso_duration_seconds("") == 0
      and sync.iso_duration_seconds("P1DT1H") == 90000, "")
check("T17 panel_data/ está en .gitignore (ahí viven los tokens)",
      "panel_data/" in (ROOT / ".gitignore").read_text(encoding="utf-8"), "")

# ---------------------------------------------------------------------------
# Servidor web de punta a punta (puerto efímero)
# ---------------------------------------------------------------------------
# La fase de servidor parte de cero: desconectar los canales sintéticos de las
# fases anteriores ejercita de paso que delete_channel borra TODO lo suyo.
for cid in ("UC_X", "UC_VENTANAS", "UC_PRUEBA", "UC_SIN_YPP", "UC_REVOCADO"):
    db.delete_channel(conn, cid)
check("T17b desconectar canales no deja huérfanos en ninguna tabla",
      not db.list_channels(conn) and conn.execute(
          "SELECT COUNT(*) c FROM channel_daily").fetchone()["c"] == 0
      and conn.execute("SELECT COUNT(*) c FROM tokens").fetchone()["c"] == 0,
      "")

from ytpanel import server as srv  # noqa: E402

httpd = srv.make_server(0)
puerto = httpd.server_address[1]
hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
hilo.start()
BASE = f"http://127.0.0.1:{puerto}"


def GET(ruta):
    try:
        with urllib.request.urlopen(BASE + ruta, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def POST(ruta, cuerpo=b"{}"):
    req = urllib.request.Request(BASE + ruta, data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, cuerpo = GET("/")
check("T18 la portada sirve la SPA de la Torre de Control",
      st == 200 and "Torre de Control" in cuerpo.decode("utf-8"), st)

POST("/api/demo")
st, cuerpo = GET("/api/overview")
data = json.loads(cuerpo)
check("T19 /api/overview entrega canales, totales y estado",
      st == 200 and data["totals"]["channels"] == 4
      and len(data["channels"][0]["sparkline"]) == 28
      and data["estado"]["client_secrets"] is True
      and isinstance(data["estado"]["cuota_hoy"], int),
      f"status {st}, totales {data.get('totals')}")

st, cuerpo = GET("/api/channel/DEMO_faros?days=30")
det = json.loads(cuerpo)
check("T20 el detalle trae serie del rango pedido, videos y bitácora",
      st == 200 and len(det["series"]) == 30 and len(det["videos"]) > 0, st)
check("T20b un canal inexistente responde 404 con error en español",
      GET("/api/channel/NO_EXISTE")[0] == 404, "")

st, cuerpo = GET("/api/oauth/start")
check("T21 /api/oauth/start entrega la URL de Google cuando hay credenciales",
      st == 200 and json.loads(cuerpo)["url"].startswith(
          "https://accounts.google.com/o/oauth2"), st)

os.environ["YTPANEL_CLIENT_SECRETS"] = str(TMP / "no_existe.json")
st, cuerpo = GET("/api/oauth/start")
check("T21b sin client_secrets.json el error explica QUÉ falta y dónde",
      st == 400 and "client_secrets.json" in json.loads(cuerpo)["error"], st)
os.environ["YTPANEL_CLIENT_SECRETS"] = str(SECRETS)

st, _ = GET("/oauth/callback?state=falso&code=x")
check("T21c un callback con state desconocido se rechaza (anti-CSRF)",
      st == 400, st)

POST("/api/demo/quitar")
data = json.loads(GET("/api/overview")[1])
check("T22 quitar la demo desde la API deja el panel en cero",
      data["totals"]["channels"] == 0, data["totals"])

httpd.shutdown()
hilo.join(timeout=5)

# ---------------------------------------------------------------------------
conn.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.54.0 completa: la Torre de Control conecta, cifra, "
      "sincroniza incremental, tolera canales sin YPP, marca los tokens "
      "caídos y sirve el panel entero sin tocar internet.")
