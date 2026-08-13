"""Datos de demostración: ver la Torre de Control amueblada sin conectar nada.

Cuatro canales ficticios y deterministas (misma semilla → mismos números) que
cubren los estados reales que la interfaz debe saber pintar: uno monetizado
con ingresos, uno sin acceso a ingresos (fuera de YPP), uno con la
autorización caída («Reconectar») y uno joven que apenas arranca. Se marcan
is_demo=1: el sync real los ignora y «Quitar demo» los borra de raíz.
"""
from __future__ import annotations

import datetime as _dt
import random

from ytpanel import db

_CANALES = [
    {"channel_id": "DEMO_faros", "title": "Faros del Mundo",
     "handle": "@farosdelmundo", "base": 5200.0, "growth": 1.012,
     "avg_secs": 340, "monetization": "ok", "token_status": "ok",
     "subs": 48200, "views_total": 6_900_000},
    {"channel_id": "DEMO_cronicas", "title": "Crónicas del Mar",
     "handle": "@cronicasdelmar", "base": 2100.0, "growth": 1.004,
     "avg_secs": 410, "monetization": "sin_acceso", "token_status": "ok",
     "subs": 9800, "views_total": 1_150_000},
    {"channel_id": "DEMO_mentes", "title": "Mentes Curiosas",
     "handle": "@mentescuriosas", "base": 3400.0, "growth": 0.998,
     "avg_secs": 265, "monetization": "ok", "token_status": "reauth",
     "subs": 21500, "views_total": 3_400_000},
    {"channel_id": "DEMO_semillas", "title": "Semillas de Historia",
     "handle": "@semillasdehistoria", "base": 260.0, "growth": 1.028,
     "avg_secs": 300, "monetization": "desconocido", "token_status": "ok",
     "subs": 830, "views_total": 41_000},
]

_TITULOS = [
    "El faro que sobrevivió a tres guerras", "La ruta perdida de los balleneros",
    "Por qué el mar Cantábrico ruge en otoño", "El misterio del torrero de 1911",
    "Cómo se construye un rompeolas", "La isla que aparece cada 18 años",
    "El naufragio que cambió las cartas náuticas", "Historia de la luz de Fresnel",
    "El puerto que se tragó la arena", "Tres días sin relevo: diario de un farero",
    "La tormenta del siglo, contada por los que la vieron",
    "Mapas antiguos: leer el mar como en 1700",
]


def seed(conn, days: int = 120) -> int:
    """Crea (o recrea) los canales demo. Determinista con Random(54)."""
    remove(conn)
    rng = random.Random(54)
    hoy = _dt.date.today() - _dt.timedelta(days=2)  # Analytics llega con retraso
    ahora = db.now_str()
    for indice, canal in enumerate(_CANALES):
        cid = canal["channel_id"]
        db.upsert_channel(
            conn, cid, title=canal["title"], handle=canal["handle"],
            thumbnail_url="", uploads_playlist="",
            subscriber_count=canal["subs"], view_count=canal["views_total"],
            video_count=len(_TITULOS), connected_at=ahora, last_sync=ahora,
            token_status=canal["token_status"],
            monetization=canal["monetization"], is_demo=1)

        rows: dict[str, dict] = {}
        money: dict[str, float] = {}
        nivel = canal["base"]
        for i in range(days):
            fecha = (hoy - _dt.timedelta(days=days - 1 - i)).isoformat()
            finde = _dt.date.fromisoformat(fecha).weekday() >= 5
            vistas = max(0, int(nivel * (1.25 if finde else 1.0)
                                * rng.uniform(0.82, 1.18)))
            ganados = max(0, int(vistas / 250 * rng.uniform(0.6, 1.4)))
            rows[fecha] = {
                "views": vistas,
                "watch_minutes": round(vistas * canal["avg_secs"] / 60, 1),
                "avg_view_seconds": round(
                    canal["avg_secs"] * rng.uniform(0.9, 1.1), 1),
                "subs_gained": ganados,
                "subs_lost": int(ganados * rng.uniform(0.15, 0.35)),
                "likes": int(vistas * 0.04),
                "comments": int(vistas * 0.004),
                "shares": int(vistas * 0.002),
            }
            if canal["monetization"] == "ok":
                money[fecha] = round(vistas / 1000 * rng.uniform(1.8, 3.2), 2)
            nivel *= canal["growth"]
        db.upsert_daily(conn, cid, rows)
        if money:
            db.set_revenue(conn, cid, money)

        # Cada canal rota la lista de títulos y espacia distinto sus subidas:
        # cuatro tarjetas con el mismo «último video» cantarían a demo barata.
        titulos = _TITULOS[indice * 3:] + _TITULOS[:indice * 3]
        videos = []
        for j, titulo in enumerate(titulos):
            publicado = hoy - _dt.timedelta(days=2 + indice * 3 + j * (8 + indice))
            videos.append({
                "video_id": f"{cid}_v{j:02d}", "title": titulo,
                "published_at": publicado.isoformat() + "T16:00:00Z",
                "thumbnail_url": "",
                "duration_seconds": rng.randint(8 * 60, 18 * 60),
                "privacy": "public",
                "views": int(canal["base"] * rng.uniform(4, 55)),
                "likes": 0, "comments": 0,
            })
        for v in videos:
            v["likes"] = int(v["views"] * 0.04)
            v["comments"] = int(v["views"] * 0.004)
        db.upsert_videos(conn, cid, videos)
    return len(_CANALES)


def remove(conn) -> int:
    """Borra los canales demo y todo lo suyo."""
    demo = [c["channel_id"] for c in db.list_channels(conn) if c["is_demo"]]
    for cid in demo:
        db.delete_channel(conn, cid)
    return len(demo)
