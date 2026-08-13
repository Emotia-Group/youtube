"""Reportes: comparar canales, agrupar métricas y exportar.

Todo sale de la base LOCAL — no gasta una sola unidad de cuota. Ese es el
premio de haber guardado el histórico desde la fase 1: puedes preguntar por
180 días de 20 canales tantas veces como quieras.

Tres piezas:
  comparativa   una métrica, varios canales, alineados por fecha
  pivote        totales por canal / día / semana / mes, con derivadas (RPM)
  top_videos    ranking de videos de TODA la red (acumulado histórico)

y `a_csv` para llevárselo a Excel.
"""
from __future__ import annotations

import datetime as _dt
import io

from ytpanel import db

# Un gráfico con 20 líneas de colores no se lee, y la paleta solo garantiza
# 8 colores distinguibles (incluso para daltonismo). Con más canales se
# pintan los 7 mayores y el resto se suma en «Otros» — 8 series en total.
MAX_SERIES = 8

METRICAS = {
    "views": {"etiqueta": "Vistas", "columna": "views", "decimales": 0},
    "watch_hours": {"etiqueta": "Horas vistas", "columna": None, "decimales": 1},
    "subs_net": {"etiqueta": "Suscriptores netos", "columna": None,
                 "decimales": 0},
    "revenue": {"etiqueta": "Ingresos (US$)", "columna": "revenue",
                "decimales": 2},
    "likes": {"etiqueta": "Me gusta", "columna": "likes", "decimales": 0},
    "comments": {"etiqueta": "Comentarios", "columna": "comments",
                 "decimales": 0},
}

AGRUPACIONES = ("canal", "dia", "semana", "mes")


def _valor(fila, metrica: str):
    """Una fila de channel_daily → el número de la métrica pedida.
    Devuelve None cuando NO HAY DATO (ingresos de un canal fuera del
    Programa de Socios), que no es lo mismo que cero."""
    if metrica == "watch_hours":
        return round((fila["watch_minutes"] or 0) / 60, 2)
    if metrica == "subs_net":
        return (fila["subs_gained"] or 0) - (fila["subs_lost"] or 0)
    if metrica == "revenue":
        return fila["revenue"]  # puede ser None a propósito
    return fila[METRICAS[metrica]["columna"]] or 0


def _rango(conn, channel_ids: list[str], days: int) -> list[str]:
    """Eje de fechas común: los últimos `days` días terminando en el último
    día CON DATOS de los canales elegidos (Analytics llega con ~2 días de
    retraso; anclar a «hoy» dejaría el gráfico con una cola vacía)."""
    if not channel_ids:
        return []
    marcas = ",".join("?" * len(channel_ids))
    fila = conn.execute(
        f"SELECT MAX(date) AS fin FROM channel_daily WHERE channel_id IN "
        f"({marcas})", channel_ids).fetchone()
    if not fila or not fila["fin"]:
        return []
    fin = _dt.date.fromisoformat(fila["fin"])
    ini = fin - _dt.timedelta(days=days - 1)
    return [(ini + _dt.timedelta(days=i)).isoformat()
            for i in range((fin - ini).days + 1)]


def comparativa(conn, channel_ids: list[str], days: int = 28,
                metrica: str = "views") -> dict:
    """Una serie por canal sobre el mismo eje de fechas.

    Los días sin dato quedan como None (hueco en la línea), no como 0: un
    canal que aún no existía o que no se ha sincronizado tan atrás no tuvo
    «cero vistas», simplemente no hay información."""
    if metrica not in METRICAS:
        raise ValueError(f"Métrica desconocida: {metrica}")
    fechas = _rango(conn, channel_ids, days)
    if not fechas:
        return {"fechas": [], "series": [], "metrica": metrica,
                "etiqueta": METRICAS[metrica]["etiqueta"], "agrupados": 0}
    titulos = {c["channel_id"]: (c["title"] or c["channel_id"])
               for c in db.list_channels(conn)}
    desde, hasta = fechas[0], fechas[-1]

    series = []
    for cid in channel_ids:
        filas = conn.execute(
            "SELECT * FROM channel_daily WHERE channel_id=? AND date>=? "
            "AND date<=?", (cid, desde, hasta)).fetchall()
        por_fecha = {f["date"]: _valor(f, metrica) for f in filas}
        valores = [por_fecha.get(f) for f in fechas]
        conocidos = [v for v in valores if v is not None]
        series.append({
            "channel_id": cid,
            "titulo": titulos.get(cid, cid),
            "valores": valores,
            "total": round(sum(conocidos), 2) if conocidos else None,
        })

    # Los mayores primero: el orden de la leyenda es el orden de importancia
    series.sort(key=lambda s: (s["total"] is None, -(s["total"] or 0)))
    agrupados = 0
    if len(series) > MAX_SERIES:
        visibles, resto = series[:MAX_SERIES - 1], series[MAX_SERIES - 1:]
        agrupados = len(resto)
        sumados = []
        for i in range(len(fechas)):
            trozo = [s["valores"][i] for s in resto
                     if s["valores"][i] is not None]
            sumados.append(round(sum(trozo), 2) if trozo else None)
        totales = [s["total"] for s in resto if s["total"] is not None]
        visibles.append({
            "channel_id": "__otros__",
            "titulo": f"Otros {agrupados} canales",
            "valores": sumados,
            "total": round(sum(totales), 2) if totales else None,
        })
        series = visibles
    return {"fechas": fechas, "series": series, "metrica": metrica,
            "etiqueta": METRICAS[metrica]["etiqueta"], "agrupados": agrupados}


def _clave_grupo(fecha: str, agrupacion: str) -> tuple[str, str]:
    """(clave de orden, etiqueta legible) del grupo al que cae una fecha."""
    d = _dt.date.fromisoformat(fecha)
    if agrupacion == "dia":
        return fecha, fecha
    if agrupacion == "semana":
        año, semana, _ = d.isocalendar()
        lunes = d - _dt.timedelta(days=d.weekday())
        return f"{año}-W{semana:02d}", f"Semana {semana} ({lunes.isoformat()})"
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{d.year}-{d.month:02d}", f"{meses[d.month - 1]} {d.year}"


def _fila_vacia(clave: str, etiqueta: str) -> dict:
    return {"clave": clave, "etiqueta": etiqueta, "views": 0,
            "watch_hours": 0.0, "subs_net": 0, "likes": 0, "comments": 0,
            "revenue": None, "rpm": None, "dias": 0}


def _cerrar(fila: dict) -> dict:
    """Redondeos y métricas derivadas, una vez sumado todo el grupo."""
    fila["watch_hours"] = round(fila["watch_hours"], 1)
    if fila["revenue"] is not None:
        fila["revenue"] = round(fila["revenue"], 2)
        # RPM = ingresos por cada mil vistas. Es LA métrica para comparar
        # canales de tamaños distintos: dice cuánto rinde la audiencia.
        fila["rpm"] = (round(fila["revenue"] / fila["views"] * 1000, 2)
                       if fila["views"] else None)
    return fila


def pivote(conn, channel_ids: list[str], days: int = 28,
           agrupacion: str = "canal") -> dict:
    """Tabla dinámica: filas agrupadas por canal o por periodo, con los
    totales de la red al pie."""
    if agrupacion not in AGRUPACIONES:
        raise ValueError(f"Agrupación desconocida: {agrupacion}")
    fechas = _rango(conn, channel_ids, days)
    if not fechas:
        return {"filas": [], "total": _fila_vacia("total", "Total"),
                "agrupacion": agrupacion, "desde": "", "hasta": ""}
    desde, hasta = fechas[0], fechas[-1]
    titulos = {c["channel_id"]: (c["title"] or c["channel_id"])
               for c in db.list_channels(conn)}
    marcas = ",".join("?" * len(channel_ids))
    filas_db = conn.execute(
        f"SELECT * FROM channel_daily WHERE channel_id IN ({marcas}) "
        f"AND date>=? AND date<=? ORDER BY date",
        channel_ids + [desde, hasta]).fetchall()

    grupos: dict[str, dict] = {}
    for f in filas_db:
        if agrupacion == "canal":
            clave = f["channel_id"]
            etiqueta = titulos.get(clave, clave)
        else:
            clave, etiqueta = _clave_grupo(f["date"], agrupacion)
        fila = grupos.setdefault(clave, _fila_vacia(clave, etiqueta))
        fila["views"] += f["views"] or 0
        fila["watch_hours"] += (f["watch_minutes"] or 0) / 60
        fila["subs_net"] += (f["subs_gained"] or 0) - (f["subs_lost"] or 0)
        fila["likes"] += f["likes"] or 0
        fila["comments"] += f["comments"] or 0
        fila["dias"] += 1
        if f["revenue"] is not None:
            fila["revenue"] = (fila["revenue"] or 0) + f["revenue"]

    total = _fila_vacia("total", "Total de la red")
    for fila in grupos.values():
        for k in ("views", "watch_hours", "subs_net", "likes", "comments",
                  "dias"):
            total[k] += fila[k]
        if fila["revenue"] is not None:
            total["revenue"] = (total["revenue"] or 0) + fila["revenue"]

    filas = [_cerrar(f) for f in grupos.values()]
    if agrupacion == "canal":
        filas.sort(key=lambda f: -f["views"])
    else:
        filas.sort(key=lambda f: f["clave"])
    return {"filas": filas, "total": _cerrar(total), "agrupacion": agrupacion,
            "desde": desde, "hasta": hasta}


def top_videos(conn, channel_ids: list[str], limite: int = 50) -> list[dict]:
    """Ranking de videos de toda la red.

    OJO: los contadores de un video son ACUMULADOS desde su publicación (es
    lo que da la Data API), no del periodo elegido. La interfaz lo dice para
    que nadie lea «vistas de los últimos 28 días» donde pone otra cosa."""
    if not channel_ids:
        return []
    marcas = ",".join("?" * len(channel_ids))
    titulos = {c["channel_id"]: (c["title"] or c["channel_id"])
               for c in db.list_channels(conn)}
    filas = conn.execute(
        f"SELECT video_id, channel_id, title, published_at, views, likes, "
        f"comments, duration_seconds FROM videos WHERE channel_id IN "
        f"({marcas}) ORDER BY views DESC LIMIT ?",
        channel_ids + [limite]).fetchall()
    out = []
    for f in filas:
        v = dict(f)
        v["canal"] = titulos.get(v["channel_id"], v["channel_id"])
        # Interacción: cuánta gente reacciona por cada 100 que ven. Compara
        # videos de tamaños muy distintos sin que gane siempre el más visto.
        v["interaccion"] = (round((v["likes"] + v["comments"])
                                  / v["views"] * 100, 2) if v["views"] else 0)
        out.append(v)
    return out


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------

def a_csv(columnas: list[tuple[str, str]], filas: list[dict]) -> bytes:
    """CSV pensado para ABRIRSE DE UN DOBLE CLIC en Excel en español:
    separador «;», decimales con coma y BOM UTF-8 (sin el BOM, Excel se come
    las tildes). `columnas` es [(clave, encabezado), …]."""
    salida = io.StringIO()
    salida.write(";".join(_celda(e) for _, e in columnas) + "\r\n")
    for fila in filas:
        salida.write(";".join(_celda(fila.get(c)) for c, _ in columnas)
                     + "\r\n")
    return b"\xef\xbb\xbf" + salida.getvalue().encode("utf-8")


def _celda(valor) -> str:
    if valor is None:
        return ""          # celda vacía ≠ 0: mantiene la distinción
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, float):
        return f"{valor:.2f}".replace(".", ",")
    if isinstance(valor, int):
        return str(valor)
    texto = str(valor).replace('"', '""')
    if any(c in texto for c in ';"\r\n'):
        return f'"{texto}"'
    return texto


COLUMNAS_PIVOTE = [
    ("etiqueta", "Grupo"), ("views", "Vistas"), ("watch_hours", "Horas vistas"),
    ("subs_net", "Suscriptores netos"), ("likes", "Me gusta"),
    ("comments", "Comentarios"), ("revenue", "Ingresos (US$)"),
    ("rpm", "RPM (US$/1000 vistas)"), ("dias", "Días con datos"),
]

COLUMNAS_VIDEOS = [
    ("canal", "Canal"), ("title", "Video"), ("published_at", "Publicado"),
    ("views", "Vistas"), ("likes", "Me gusta"), ("comments", "Comentarios"),
    ("interaccion", "Interacción (%)"), ("video_id", "ID"),
]


def csv_pivote(conn, channel_ids, days, agrupacion) -> bytes:
    datos = pivote(conn, channel_ids, days, agrupacion)
    return a_csv(COLUMNAS_PIVOTE, datos["filas"] + [datos["total"]])


def csv_videos(conn, channel_ids, limite=200) -> bytes:
    return a_csv(COLUMNAS_VIDEOS, top_videos(conn, channel_ids, limite))


def csv_diario(conn, channel_ids, days) -> bytes:
    """El detalle día a día: la materia prima para tus propias tablas
    dinámicas en Excel."""
    fechas = _rango(conn, channel_ids, days)
    if not fechas:
        return a_csv([("date", "Fecha")], [])
    titulos = {c["channel_id"]: (c["title"] or c["channel_id"])
               for c in db.list_channels(conn)}
    marcas = ",".join("?" * len(channel_ids))
    filas = conn.execute(
        f"SELECT * FROM channel_daily WHERE channel_id IN ({marcas}) "
        f"AND date>=? AND date<=? ORDER BY date, channel_id",
        channel_ids + [fechas[0], fechas[-1]]).fetchall()
    out = []
    for f in filas:
        d = dict(f)
        d["canal"] = titulos.get(d["channel_id"], d["channel_id"])
        d["watch_hours"] = round((d["watch_minutes"] or 0) / 60, 2)
        d["subs_net"] = (d["subs_gained"] or 0) - (d["subs_lost"] or 0)
        out.append(d)
    return a_csv([
        ("date", "Fecha"), ("canal", "Canal"), ("views", "Vistas"),
        ("watch_hours", "Horas vistas"), ("subs_gained", "Subs ganados"),
        ("subs_lost", "Subs perdidos"), ("subs_net", "Subs netos"),
        ("likes", "Me gusta"), ("comments", "Comentarios"),
        ("shares", "Compartidos"), ("revenue", "Ingresos (US$)"),
    ], out)
