"""Alertas e insights: que el panel te BUSQUE a ti, no al revés.

Con 20 canales, revisar 20 tarjetas cada mañana no escala. Estas reglas
miran el histórico ya guardado (cero cuota) y sacan a flote lo que merece
tu atención hoy: una autorización caída, un canal que se apagó, una caída
de ingresos… y también lo bueno, porque un video que despunta es una
oportunidad que caduca.

Cada alerta lleva severidad, icono, EXPLICACIÓN y qué hacer. El color nunca
es la única señal: siempre hay icono y texto (también para quien no
distingue colores).

Umbrales configurables en config.yaml, bloque `panel.alertas`.
"""
from __future__ import annotations

import datetime as _dt

from ytpanel import db

ICONOS = {"critica": "⛔", "aviso": "⚠", "buena": "▲"}
ETIQUETAS = {"critica": "Crítico", "aviso": "Atención", "buena": "Buena señal"}
_ORDEN = {"critica": 0, "aviso": 1, "buena": 2}


def _alerta(severidad, regla, titulo, detalle, accion, canal=None) -> dict:
    return {
        "regla": regla,
        "severidad": severidad,
        "icono": ICONOS[severidad],
        "severidad_texto": ETIQUETAS[severidad],
        "titulo": titulo,
        "detalle": detalle,
        "accion": accion,
        "channel_id": (canal or {}).get("channel_id", ""),
        "canal": (canal or {}).get("title", "") or (canal or {}).get(
            "channel_id", ""),
    }


def _pct(actual, previo):
    """Variación porcentual, o None si no hay base con la que comparar."""
    if not previo:
        return None
    return (actual - previo) / previo * 100


def _dias_desde(fecha_iso: str, hoy: _dt.date) -> int | None:
    if not fecha_iso:
        return None
    try:
        return (hoy - _dt.date.fromisoformat(fecha_iso[:10])).days
    except ValueError:
        return None


def _recortar(texto: str, tope: int = 48) -> str:
    """Corta por la última palabra entera: «…contada por los que la vi» se
    lee raro, «…contada por los que…» no."""
    if len(texto) <= tope:
        return texto
    corte = texto[:tope].rsplit(" ", 1)[0]
    return (corte or texto[:tope]).rstrip(" ,;:.") + "…"


def _mediana(valores: list[float]) -> float:
    if not valores:
        return 0
    orden = sorted(valores)
    medio = len(orden) // 2
    if len(orden) % 2:
        return orden[medio]
    return (orden[medio - 1] + orden[medio]) / 2


def revisar(conn, cfg: dict | None = None, hoy: _dt.date | None = None
            ) -> list[dict]:
    """Todas las alertas activas, las más urgentes primero."""
    from ytpanel import config as _config
    cfg = cfg or _config.load_panel_config()
    umbrales = cfg.get("alertas") or {}
    hoy = hoy or _dt.date.today()

    caida_v = float(umbrales.get("caida_vistas_pct", 25))
    subida_v = float(umbrales.get("subida_vistas_pct", 40))
    caida_i = float(umbrales.get("caida_ingresos_pct", 25))
    sin_publicar = int(umbrales.get("dias_sin_publicar", 21))
    sin_sync = int(umbrales.get("dias_sin_sincronizar", 3))
    despunta_x = float(umbrales.get("video_despunta_x", 2.0))
    minimo = int(umbrales.get("minimo_vistas", 100))

    alertas: list[dict] = []
    for canal in db.list_channels(conn):
        resumen = db.channel_summary(conn, canal)
        nombre = canal["title"] or canal["channel_id"]

        # 1 · La autorización se cayó: sin esto no entra NADA de este canal
        if canal["token_status"] == "reauth":
            alertas.append(_alerta(
                "critica", "token_caido",
                f"{nombre}: hay que reconectar el canal",
                "Google rechazó la autorización (revocada, o caducada porque "
                "la app OAuth sigue «En pruebas», donde los tokens duran 7 "
                "días). Mientras tanto no entran métricas ni se aplican "
                "ediciones.",
                "Pulsa «＋ Conectar canal» y elige de nuevo este canal.",
                canal))

        # 2 · Lleva días sin sincronizar (los demo no sincronizan nunca)
        if not canal["is_demo"] and canal["token_status"] != "reauth":
            dias = _dias_desde((canal["last_sync"] or "")[:10], hoy)
            if dias is None:
                alertas.append(_alerta(
                    "aviso", "nunca_sincronizado",
                    f"{nombre}: nunca se ha sincronizado",
                    "El canal está conectado pero todavía no tiene datos.",
                    "Pulsa «⟳ Sincronizar».", canal))
            elif dias >= sin_sync:
                alertas.append(_alerta(
                    "aviso", "sin_sincronizar",
                    f"{nombre}: {dias} días sin sincronizar",
                    "Las métricas que ves están congeladas en esa fecha.",
                    "Sincroniza, o programa «ytpanel sync» cada noche.",
                    canal))

        # 3 · Caída (o subida) de vistas: 7 días contra los 7 anteriores
        previo = resumen["views_prev_7d"] or 0
        actual = resumen["views_7d"] or 0
        if previo >= minimo:
            variacion = _pct(actual, previo)
            if variacion is not None and variacion <= -caida_v:
                alertas.append(_alerta(
                    "aviso", "caida_vistas",
                    f"{nombre}: las vistas cayeron {abs(variacion):.0f}%",
                    f"{actual:,} vistas en 7 días contra {previo:,} de los 7 "
                    "anteriores.".replace(",", "."),
                    "Mira si coincide con un cambio de formato, de miniatura "
                    "o con un hueco de publicación.", canal))
            elif variacion is not None and variacion >= subida_v:
                alertas.append(_alerta(
                    "buena", "subida_vistas",
                    f"{nombre}: las vistas subieron {variacion:.0f}%",
                    f"{actual:,} vistas en 7 días contra {previo:,} de los 7 "
                    "anteriores.".replace(",", "."),
                    "Averigua qué video tira y repite la fórmula mientras "
                    "está caliente.", canal))

        # 4 · Los ingresos se desploman (solo canales con datos de YPP)
        serie = db.series(conn, canal["channel_id"], 14)
        con_dinero = [d["revenue"] for d in serie if d["revenue"] is not None]
        if len(con_dinero) >= 14:
            ult, ant = sum(con_dinero[-7:]), sum(con_dinero[-14:-7])
            variacion = _pct(ult, ant)
            if variacion is not None and ant >= 1 and variacion <= -caida_i:
                alertas.append(_alerta(
                    "aviso", "caida_ingresos",
                    f"{nombre}: los ingresos cayeron {abs(variacion):.0f}%",
                    f"US$ {ult:.2f} en 7 días contra US$ {ant:.2f} de los 7 "
                    "anteriores. Puede ser estacionalidad del CPM o menos "
                    "vistas.",
                    "Compara el RPM en Reportes: si el RPM aguanta, el "
                    "problema son las vistas, no la monetización.", canal))

        # 5 · El canal se apagó
        ultimo = conn.execute(
            "SELECT MAX(published_at) AS p FROM videos WHERE channel_id=?",
            (canal["channel_id"],)).fetchone()
        dias_pub = _dias_desde((ultimo["p"] or "")[:10], hoy) if ultimo else None
        if dias_pub is not None and dias_pub >= sin_publicar:
            alertas.append(_alerta(
                "aviso", "sin_publicar",
                f"{nombre}: {dias_pub} días sin publicar",
                "Los canales que dejan de publicar pierden alcance: el "
                "algoritmo deja de proponerlos.",
                "Programa la próxima subida (ytstudio ya produce el video).",
                canal))

        # 6 · Un video despunta: oportunidad con fecha de caducidad
        videos = [dict(r) for r in conn.execute(
            "SELECT title, views, published_at FROM videos WHERE channel_id=? "
            "ORDER BY published_at DESC LIMIT 30",
            (canal["channel_id"],)).fetchall()]
        if len(videos) >= 5:
            mediana = _mediana([v["views"] for v in videos])
            recientes = [v for v in videos
                         if (_dias_desde(v["published_at"], hoy) or 999) <= 30]
            for v in recientes:
                if mediana > 0 and v["views"] >= mediana * despunta_x:
                    veces = v["views"] / mediana
                    alertas.append(_alerta(
                        "buena", "video_despunta",
                        f"{nombre}: «{_recortar(v['title'])}» va {veces:.1f}× "
                        "sobre la media",
                        f"{v['views']:,} vistas contra una mediana de "
                        f"{int(mediana):,} en el canal.".replace(",", "."),
                        "Aprovéchalo: fíjalo en el canal, añádelo a una "
                        "playlist y considera una segunda parte.", canal))
                    break  # uno por canal: la bandeja debe seguir siendo útil

    # 7 · Ediciones que se quedaron atascadas
    errores = db.cola_resumen(conn)["errores"]
    if errores:
        alertas.append(_alerta(
            "aviso", "cola_errores",
            f"{errores} edición(es) fallaron en la cola",
            "Sus cambios NO están aplicados en YouTube.",
            "Abre la cola desde la cabecera: cada trabajo dice qué pasó y "
            "tiene botón «Reintentar»."))

    alertas.sort(key=lambda a: (_ORDEN[a["severidad"]], a["canal"]))
    return alertas


def resumen(alertas: list[dict]) -> dict:
    return {
        "total": len(alertas),
        "criticas": sum(1 for a in alertas if a["severidad"] == "critica"),
        "avisos": sum(1 for a in alertas if a["severidad"] == "aviso"),
        "buenas": sum(1 for a in alertas if a["severidad"] == "buena"),
    }
