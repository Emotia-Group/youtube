"""Base de datos local del panel (SQLite, stdlib).

Guarda el histórico COMPLETO de métricas diarias por canal — YouTube Studio
solo muestra ventanas; aquí el registro es tuyo y crece cada noche. Política
de datos de la API respetada por diseño: los datos viven mientras el canal
siga conectado, y desconectarlo borra todo lo suyo (delete_channel).

Tablas:
  channels       ficha y snapshot del canal (subs/vistas/videos totales)
  tokens         credenciales OAuth por canal (blob cifrado por vault.py)
  channel_daily  una fila por canal y día: vistas, minutos, subs, ingresos…
  videos         últimos videos con sus contadores
  sync_log       cada sincronización: cuándo, resultado y cuota gastada
  meta           versión del esquema y ajustes internos
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ytpanel import config

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
  channel_id       TEXT PRIMARY KEY,
  title            TEXT NOT NULL DEFAULT '',
  handle           TEXT NOT NULL DEFAULT '',
  thumbnail_url    TEXT NOT NULL DEFAULT '',
  uploads_playlist TEXT NOT NULL DEFAULT '',
  subscriber_count INTEGER NOT NULL DEFAULT 0,
  view_count       INTEGER NOT NULL DEFAULT 0,
  video_count      INTEGER NOT NULL DEFAULT 0,
  connected_at     TEXT NOT NULL DEFAULT '',
  last_sync        TEXT NOT NULL DEFAULT '',
  token_status     TEXT NOT NULL DEFAULT 'sin_token',   -- ok | reauth | sin_token
  monetization     TEXT NOT NULL DEFAULT 'desconocido', -- ok | sin_acceso | desconocido
  is_demo          INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tokens (
  channel_id TEXT PRIMARY KEY REFERENCES channels(channel_id) ON DELETE CASCADE,
  blob       BLOB NOT NULL,
  updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS channel_daily (
  channel_id       TEXT NOT NULL,
  date             TEXT NOT NULL,             -- YYYY-MM-DD (día de Analytics)
  views            INTEGER NOT NULL DEFAULT 0,
  watch_minutes    REAL NOT NULL DEFAULT 0,
  avg_view_seconds REAL NOT NULL DEFAULT 0,
  subs_gained      INTEGER NOT NULL DEFAULT 0,
  subs_lost        INTEGER NOT NULL DEFAULT 0,
  likes            INTEGER NOT NULL DEFAULT 0,
  comments         INTEGER NOT NULL DEFAULT 0,
  shares           INTEGER NOT NULL DEFAULT 0,
  revenue          REAL,                      -- NULL = sin dato (no es lo mismo que 0)
  PRIMARY KEY (channel_id, date)
);
CREATE TABLE IF NOT EXISTS videos (
  video_id         TEXT PRIMARY KEY,
  channel_id       TEXT NOT NULL,
  title            TEXT NOT NULL DEFAULT '',
  published_at     TEXT NOT NULL DEFAULT '',
  thumbnail_url    TEXT NOT NULL DEFAULT '',
  duration_seconds INTEGER NOT NULL DEFAULT 0,
  privacy          TEXT NOT NULL DEFAULT '',
  views            INTEGER NOT NULL DEFAULT 0,
  likes            INTEGER NOT NULL DEFAULT 0,
  comments         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id, published_at DESC);
CREATE TABLE IF NOT EXISTS sync_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id  TEXT NOT NULL DEFAULT '',
  started_at  TEXT NOT NULL,
  finished_at TEXT NOT NULL DEFAULT '',
  ok          INTEGER NOT NULL DEFAULT 0,
  detail      TEXT NOT NULL DEFAULT '',
  quota_units INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT ''
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Abre (y migra) la base. Cada hilo abre la suya: SQLite no comparte
    conexiones entre hilos y el servidor atiende en varios."""
    conn = sqlite3.connect(str(path or config.db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO NOTHING", (str(SCHEMA_VERSION),))
    conn.commit()


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Escritura (upserts idempotentes: re-sincronizar nunca duplica)
# ---------------------------------------------------------------------------

_CHANNEL_FIELDS = {
    "title", "handle", "thumbnail_url", "uploads_playlist", "subscriber_count",
    "view_count", "video_count", "connected_at", "last_sync", "token_status",
    "monetization", "is_demo",
}


def upsert_channel(conn: sqlite3.Connection, channel_id: str, **fields) -> None:
    """Inserta o actualiza SOLO los campos provistos — así el sync de métricas
    no pisa connected_at, y marcar token_status no borra el snapshot."""
    bad = set(fields) - _CHANNEL_FIELDS
    if bad:
        raise ValueError(f"Campos desconocidos de canal: {sorted(bad)}")
    cols = list(fields)
    sets = ", ".join(f"{c}=excluded.{c}" for c in cols) or "channel_id=channel_id"
    conn.execute(
        f"INSERT INTO channels(channel_id{''.join(',' + c for c in cols)}) "
        f"VALUES(?{',?' * len(cols)}) "
        f"ON CONFLICT(channel_id) DO UPDATE SET {sets}",
        [channel_id] + [fields[c] for c in cols])
    conn.commit()


_DAILY_BASE = ("views", "watch_minutes", "avg_view_seconds", "subs_gained",
               "subs_lost", "likes", "comments", "shares")


def upsert_daily(conn: sqlite3.Connection, channel_id: str,
                 rows: dict[str, dict]) -> int:
    """Guarda métricas base por día. La columna revenue NO se toca aquí: viene
    de otra consulta (set_revenue) y puede fallar sola (canal fuera de YPP) sin
    arrastrar a las demás métricas."""
    n = 0
    for date, m in sorted(rows.items()):
        values = [m.get(k, 0) or 0 for k in _DAILY_BASE]
        conn.execute(
            "INSERT INTO channel_daily(channel_id, date, "
            + ", ".join(_DAILY_BASE) + ") VALUES(?,?" + ",?" * len(_DAILY_BASE) + ") "
            "ON CONFLICT(channel_id, date) DO UPDATE SET "
            + ", ".join(f"{k}=excluded.{k}" for k in _DAILY_BASE),
            [channel_id, date] + values)
        n += 1
    conn.commit()
    return n


def set_revenue(conn: sqlite3.Connection, channel_id: str,
                by_date: dict[str, float]) -> None:
    for date, value in by_date.items():
        conn.execute(
            "INSERT INTO channel_daily(channel_id, date, revenue) VALUES(?,?,?) "
            "ON CONFLICT(channel_id, date) DO UPDATE SET revenue=excluded.revenue",
            (channel_id, date, value))
    conn.commit()


def upsert_videos(conn: sqlite3.Connection, channel_id: str,
                  videos: list[dict]) -> None:
    for v in videos:
        conn.execute(
            "INSERT INTO videos(video_id, channel_id, title, published_at, "
            " thumbnail_url, duration_seconds, privacy, views, likes, comments) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(video_id) DO UPDATE SET title=excluded.title, "
            " thumbnail_url=excluded.thumbnail_url, "
            " duration_seconds=excluded.duration_seconds, privacy=excluded.privacy, "
            " views=excluded.views, likes=excluded.likes, comments=excluded.comments",
            (v["video_id"], channel_id, v.get("title", ""), v.get("published_at", ""),
             v.get("thumbnail_url", ""), v.get("duration_seconds", 0),
             v.get("privacy", ""), v.get("views", 0), v.get("likes", 0),
             v.get("comments", 0)))
    conn.commit()


def save_token(conn: sqlite3.Connection, channel_id: str, blob: bytes) -> None:
    conn.execute(
        "INSERT INTO tokens(channel_id, blob, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(channel_id) DO UPDATE SET blob=excluded.blob, "
        " updated_at=excluded.updated_at",
        (channel_id, blob, now_str()))
    conn.commit()


def get_token_blob(conn: sqlite3.Connection, channel_id: str) -> bytes | None:
    row = conn.execute("SELECT blob FROM tokens WHERE channel_id=?",
                       (channel_id,)).fetchone()
    return bytes(row["blob"]) if row else None


def record_sync(conn: sqlite3.Connection, channel_id: str, *, started_at: str,
                ok: bool, detail: str = "", quota_units: int = 0) -> None:
    conn.execute(
        "INSERT INTO sync_log(channel_id, started_at, finished_at, ok, detail, "
        " quota_units) VALUES(?,?,?,?,?,?)",
        (channel_id, started_at, now_str(), 1 if ok else 0, detail, quota_units))
    conn.commit()


def delete_channel(conn: sqlite3.Connection, channel_id: str) -> None:
    """Desconectar = borrar TODO lo del canal (token, métricas, videos,
    historial de syncs). Es lo que exige la política de datos de la API y lo
    que uno espera al pulsar «desconectar»."""
    for table in ("tokens", "channel_daily", "videos", "sync_log"):
        conn.execute(f"DELETE FROM {table} WHERE channel_id=?", (channel_id,))
    conn.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Lectura (lo que pinta la interfaz)
# ---------------------------------------------------------------------------

def list_channels(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM channels ORDER BY is_demo, title").fetchall()]


def series(conn: sqlite3.Connection, channel_id: str, days: int) -> list[dict]:
    """Últimos `days` días CON datos, en orden cronológico. Se ancla al último
    día disponible (Analytics llega con ~2 días de retraso; anclar a «hoy»
    dejaría las ventanas cojas y los deltas mentirían)."""
    rows = conn.execute(
        "SELECT date, views, watch_minutes, avg_view_seconds, subs_gained, "
        " subs_lost, likes, comments, shares, revenue FROM channel_daily "
        "WHERE channel_id=? ORDER BY date DESC LIMIT ?",
        (channel_id, days)).fetchall()
    return [dict(r) for r in reversed(rows)]


def _window(serie: list[dict], key: str, n: int, offset: int = 0):
    seg = serie[max(0, len(serie) - offset - n): max(0, len(serie) - offset)]
    return [d[key] for d in seg]


def _sum(values, none_if_empty: bool = False):
    vals = [v for v in values if v is not None]
    if none_if_empty and not vals:
        return None
    return sum(vals)


def channel_summary(conn: sqlite3.Connection, ch: dict) -> dict:
    """La tarjeta de un canal: ventanas de 7/28 días, deltas y sparkline."""
    serie = series(conn, ch["channel_id"], 56)  # 28 actuales + 28 previos
    views_7 = _sum(_window(serie, "views", 7))
    views_prev_7 = _sum(_window(serie, "views", 7, offset=7))
    views_28 = _sum(_window(serie, "views", 28))
    views_prev_28 = _sum(_window(serie, "views", 28, offset=28))
    revenue_28 = _sum(_window(serie, "revenue", 28), none_if_empty=True)
    last_video = conn.execute(
        "SELECT video_id, title, published_at, views FROM videos "
        "WHERE channel_id=? ORDER BY published_at DESC LIMIT 1",
        (ch["channel_id"],)).fetchone()
    return dict(ch) | {
        "views_7d": views_7,
        "views_prev_7d": views_prev_7,
        "views_28d": views_28,
        "views_prev_28d": views_prev_28,
        "watch_minutes_28d": _sum(_window(serie, "watch_minutes", 28)),
        "subs_net_7d": (_sum(_window(serie, "subs_gained", 7))
                        - _sum(_window(serie, "subs_lost", 7))),
        "revenue_28d": revenue_28,
        "sparkline": [{"date": d["date"], "views": d["views"]}
                      for d in serie[-28:]],
        "last_video": dict(last_video) if last_video else None,
        "last_date": serie[-1]["date"] if serie else "",
    }


def overview(conn: sqlite3.Connection) -> dict:
    channels = [channel_summary(conn, ch) for ch in list_channels(conn)]
    revenues = [c["revenue_28d"] for c in channels if c["revenue_28d"] is not None]
    return {
        "channels": channels,
        "totals": {
            "channels": len(channels),
            "connected": sum(1 for c in channels if not c["is_demo"]),
            "subscribers": sum(c["subscriber_count"] for c in channels),
            "views_28d": sum(c["views_28d"] for c in channels),
            "views_prev_28d": sum(c["views_prev_28d"] for c in channels),
            "watch_hours_28d": round(
                sum(c["watch_minutes_28d"] for c in channels) / 60, 1),
            "revenue_28d": sum(revenues) if revenues else None,
        },
    }


def channel_detail(conn: sqlite3.Connection, channel_id: str,
                   days: int = 90) -> dict | None:
    row = conn.execute("SELECT * FROM channels WHERE channel_id=?",
                       (channel_id,)).fetchone()
    if not row:
        return None
    videos = [dict(r) for r in conn.execute(
        "SELECT * FROM videos WHERE channel_id=? ORDER BY published_at DESC "
        "LIMIT 50", (channel_id,)).fetchall()]
    syncs = [dict(r) for r in conn.execute(
        "SELECT started_at, finished_at, ok, detail, quota_units FROM sync_log "
        "WHERE channel_id=? ORDER BY id DESC LIMIT 5", (channel_id,)).fetchall()]
    return {"channel": channel_summary(conn, dict(row)),
            "series": series(conn, channel_id, days),
            "videos": videos, "syncs": syncs}


def quota_today(conn: sqlite3.Connection) -> int:
    """Unidades de Data API gastadas HOY según nuestro registro. Es el gasto de
    este programa, no el del proyecto entero de Google Cloud (si otra
    herramienta comparte proyecto, Google suma aparte)."""
    today = time.strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COALESCE(SUM(quota_units), 0) AS u FROM sync_log "
        "WHERE started_at LIKE ?", (today + "%",)).fetchone()
    return int(row["u"])
