"""Motor de sincronización: trae los datos de cada canal a la base local.

Por canal y por corrida (3 unidades de cuota Data API + Analytics aparte):
  1. Ficha y snapshot del canal (subs, vistas y videos totales).
  2. Últimos videos de la playlist de subidas, con sus contadores.
  3. Métricas diarias de Analytics: la primera vez pide `history_days` hacia
     atrás; después, incremental desde el último día guardado MENOS un solape
     (Analytics re-consolida los últimos días; re-pedirlos corrige sin costo).
  4. Ingresos en consulta SEPARADA: si el canal no está en el Programa de
     Socios (o el permiso monetario no da), esa consulta falla SOLA y el resto
     de métricas queda intacto — el canal se marca «sin_acceso» y a seguir.
"""
from __future__ import annotations

import datetime as _dt
import re

from ytpanel import config, db, google_api, vault

BASE_METRICS = ("views,estimatedMinutesWatched,averageViewDuration,"
                "subscribersGained,subscribersLost,likes,comments,shares")

_METRIC_TO_COLUMN = {
    "views": "views",
    "estimatedMinutesWatched": "watch_minutes",
    "averageViewDuration": "avg_view_seconds",
    "subscribersGained": "subs_gained",
    "subscribersLost": "subs_lost",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "estimatedRevenue": "revenue",
}

_DURATION_RE = re.compile(
    r"P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?")


def iso_duration_seconds(value: str) -> int:
    """'PT1H2M3S' → 3723. Tolerante: si no parsea, 0 (mejor que romper un sync
    de 20 canales por un duration raro)."""
    m = _DURATION_RE.fullmatch(value or "")
    if not m:
        return 0
    d, h, mi, s = (int(m.group(k) or 0) for k in ("d", "h", "m", "s"))
    return ((d * 24 + h) * 60 + mi) * 60 + s


def daily_rows(resp: dict) -> dict[str, dict]:
    """Respuesta de Analytics (columnHeaders + rows) → {fecha: {columna: valor}}."""
    headers = [h.get("name", "") for h in resp.get("columnHeaders", [])]
    out: dict[str, dict] = {}
    for row in resp.get("rows") or []:
        record = dict(zip(headers, row))
        date = record.pop("day", None)
        if date:
            out[date] = {_METRIC_TO_COLUMN.get(k, k): v
                         for k, v in record.items()}
    return out


def parse_videos(resp: dict) -> list[dict]:
    videos = []
    for item in resp.get("items") or []:
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        thumbs = snippet.get("thumbnails") or {}
        thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
        videos.append({
            "video_id": item.get("id", ""),
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail_url": thumb,
            "duration_seconds": iso_duration_seconds(
                (item.get("contentDetails") or {}).get("duration", "")),
            "privacy": (item.get("status") or {}).get("privacyStatus", ""),
            # Los contadores llegan como strings, y pueden faltar (ocultos)
            "views": int(stats.get("viewCount") or 0),
            "likes": int(stats.get("likeCount") or 0),
            "comments": int(stats.get("commentCount") or 0),
            # El snippet completo: es lo que edita la fase 2 (videos.update
            # BORRA lo que no se reenvía, así que hay que tenerlo entero)
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags") or [],
            "category_id": snippet.get("categoryId", ""),
        })
    return videos


def parse_playlists(resp: dict) -> list[dict]:
    out = []
    for item in resp.get("items") or []:
        snippet = item.get("snippet") or {}
        out.append({
            "playlist_id": item.get("id", ""),
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "privacy": (item.get("status") or {}).get("privacyStatus", ""),
            "item_count": int((item.get("contentDetails") or {})
                              .get("itemCount") or 0),
        })
    return out


def _date_range(conn, channel_id: str, cfg: dict, today: str) -> tuple[str, str]:
    row = conn.execute("SELECT MAX(date) AS last FROM channel_daily "
                       "WHERE channel_id=?", (channel_id,)).fetchone()
    end = _dt.date.fromisoformat(today)
    if row and row["last"]:
        start = (_dt.date.fromisoformat(row["last"])
                 - _dt.timedelta(days=int(cfg["resync_overlap_days"])))
    else:
        start = end - _dt.timedelta(days=int(cfg["history_days"]))
    return start.isoformat(), end.isoformat()


def sync_channel(conn, channel_id: str, *, cfg: dict | None = None,
                 transport=None, today: str | None = None, log=None) -> dict:
    """Sincroniza UN canal. Devuelve un resumen y deja rastro en sync_log.
    Nunca lanza por errores de API: el resumen trae el error legible, porque
    un canal caído no debe frenar a los otros 19."""
    log = log or (lambda _msg: None)
    cfg = cfg or config.load_panel_config()
    today = today or _dt.date.today().isoformat()
    started = db.now_str()
    resumen = {"channel_id": channel_id, "ok": False, "quota": 0,
               "videos": 0, "dias": 0, "error": None}

    def fail(msg: str, *, token_status: str | None = None, quota: int = 0):
        if token_status:
            db.upsert_channel(conn, channel_id, token_status=token_status)
        db.record_sync(conn, channel_id, started_at=started, ok=False,
                       detail=msg, quota_units=quota)
        log(f"  ✖ {msg}")
        resumen["error"] = msg
        resumen["quota"] = quota
        return resumen

    blob = db.get_token_blob(conn, channel_id)
    if blob is None:
        return fail("El canal no tiene token guardado: conéctalo desde el panel.",
                    token_status="sin_token")
    try:
        token = vault.unseal(blob)
        secrets = google_api.load_client_secrets()
    except (ValueError, RuntimeError) as e:
        return fail(str(e))

    def persist(tok: dict) -> None:
        db.save_token(conn, channel_id, vault.seal(tok))

    api = google_api.YouTubeAPI(secrets, token, transport=transport,
                                on_token_refresh=persist)
    try:
        # 1 · Ficha y snapshot
        items = (api.channels_mine().get("items") or [])
        if not items:
            return fail("La API no devolvió el canal (¿token de otra cuenta?).",
                        quota=api.quota_units)
        ch = items[0]
        snippet, stats = ch.get("snippet") or {}, ch.get("statistics") or {}
        thumbs = snippet.get("thumbnails") or {}
        uploads = ((ch.get("contentDetails") or {})
                   .get("relatedPlaylists") or {}).get("uploads", "")
        db.upsert_channel(
            conn, channel_id,
            title=snippet.get("title", ""),
            handle=snippet.get("customUrl", ""),
            thumbnail_url=(thumbs.get("medium") or thumbs.get("default")
                           or {}).get("url", ""),
            uploads_playlist=uploads,
            subscriber_count=int(stats.get("subscriberCount") or 0),
            view_count=int(stats.get("viewCount") or 0),
            video_count=int(stats.get("videoCount") or 0),
            token_status="ok")
        log(f"  · {snippet.get('title', channel_id)}: ficha actualizada")

        # 2 · Últimos videos
        if uploads:
            ids = [((it.get("contentDetails") or {}).get("videoId") or "")
                   for it in (api.playlist_items(
                       uploads, int(cfg["max_recent_videos"])).get("items") or [])]
            ids = [i for i in ids if i]
            if ids:
                videos = parse_videos(api.videos_list(ids))
                db.upsert_videos(conn, channel_id, videos)
                resumen["videos"] = len(videos)
                log(f"  · {len(videos)} videos al día")

        # 2b · Playlists del canal (1 unidad; las borradas en YouTube caen
        # aquí). Si esta lectura falla, no arrastra al resto del sync.
        try:
            listas = parse_playlists(api.playlists_mine())
            db.replace_playlists(conn, channel_id, listas)
            if listas:
                log(f"  · {len(listas)} playlists")
        except google_api.ApiHttpError as e:
            log(f"  · playlists no disponibles ({e.reason})")

        # 3 · Métricas diarias
        start, end = _date_range(conn, channel_id, cfg, today)
        rows = daily_rows(api.analytics_daily(start, end, BASE_METRICS))
        resumen["dias"] = db.upsert_daily(conn, channel_id, rows)
        log(f"  · métricas {start} → {end} ({resumen['dias']} días)")

        # 4 · Ingresos (consulta aparte, tolerante)
        try:
            money = daily_rows(api.analytics_daily(
                start, end, "estimatedRevenue", currency=cfg["currency"]))
            db.set_revenue(conn, channel_id,
                           {d: m.get("revenue") for d, m in money.items()
                            if m.get("revenue") is not None})
            db.upsert_channel(conn, channel_id, monetization="ok")
            log(f"  · ingresos: {len(money)} días")
        except google_api.ApiHttpError as e:
            # Canal fuera de YPP o sin permiso monetario: no es un fallo del
            # sync, es un hecho del canal — se registra y se sigue.
            db.upsert_channel(conn, channel_id, monetization="sin_acceso")
            log(f"  · ingresos no disponibles ({e.reason})")

        db.upsert_channel(conn, channel_id, last_sync=db.now_str())
        db.record_sync(conn, channel_id, started_at=started, ok=True,
                       detail=f"{resumen['dias']} días, {resumen['videos']} videos",
                       quota_units=api.quota_units)
        resumen.update(ok=True, quota=api.quota_units)
        return resumen

    except google_api.ReauthNeeded as e:
        return fail(str(e), token_status="reauth", quota=api.quota_units)
    except google_api.ApiHttpError as e:
        return fail(str(e), quota=api.quota_units)
    except OSError as e:
        # Sin internet o DNS caído: un mensaje legible en la bitácora, no un
        # traceback — y el resto de canales siguen su turno.
        return fail(f"Error de red hablando con Google: {e}",
                    quota=api.quota_units)


def sync_all(conn, *, cfg: dict | None = None, transport=None,
             today: str | None = None, log=None) -> list[dict]:
    """Todos los canales conectados (los demo no llaman a ninguna API)."""
    log = log or (lambda _msg: None)
    cfg = cfg or config.load_panel_config()
    resumenes = []
    for ch in db.list_channels(conn):
        if ch["is_demo"]:
            continue
        log(f"⟳ {ch['title'] or ch['channel_id']}")
        resumenes.append(sync_channel(conn, ch["channel_id"], cfg=cfg,
                                      transport=transport, today=today, log=log))
    return resumenes
