"""Batería v0.56.0 — reportes y alertas (fase 3), sin red y sin claves.

Lo que se vigila aquí es sobre todo que el panel NO MIENTA:

1. Un día sin datos se ve como hueco, nunca como «cero vistas».
2. «Sin ingresos» (canal fuera del Programa de Socios) no es «cero dólares».
3. Con más de 8 canales no se inventan colores: los menores se suman en
   «Otros» y el gráfico dice cuántos agrupó.
4. El RPM se calcula sobre las vistas del mismo periodo.
5. Cada regla de alerta se comprueba con un caso que SÍ debe dispararla y
   otro que NO — una alerta que salta siempre es tan inútil como ninguna.
6. Los CSV se abren de un doble clic en el Excel en español (BOM, «;» y
   decimales con coma).
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
import urllib.error
import urllib.request

TMP = Path(tempfile.mkdtemp(prefix="v0560_"))
os.environ["YTPANEL_DATA_DIR"] = str(TMP / "panel_data")

from ytpanel import alerts, db, reports  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


HOY = dt.date(2026, 8, 13)
UMBRALES = {"alertas": {"caida_vistas_pct": 25, "subida_vistas_pct": 40,
                        "caida_ingresos_pct": 25, "dias_sin_publicar": 21,
                        "dias_sin_sincronizar": 3, "video_despunta_x": 2.0,
                        "minimo_vistas": 100}}


def nueva_db(nombre):
    return db.connect(TMP / f"{nombre}.db")


def dia(delta):
    return (HOY - dt.timedelta(days=delta)).isoformat()


def poblar(conn, cid, titulo, dias, vistas, revenue=None, **extra):
    """Canal con `dias` días de datos terminando ayer (delta=1)."""
    db.upsert_channel(conn, cid, title=titulo, **extra)
    filas = {}
    for i in range(dias):
        filas[dia(dias - i)] = {"views": vistas, "watch_minutes": vistas * 5,
                                "subs_gained": 10, "subs_lost": 4,
                                "likes": vistas // 10, "comments": vistas // 50}
    db.upsert_daily(conn, cid, filas)
    if revenue is not None:
        db.set_revenue(conn, cid, {f: revenue for f in filas})


# ---------------------------------------------------------------------------
# Comparativa
# ---------------------------------------------------------------------------
c = nueva_db("reportes")
poblar(c, "UC_A", "Canal A", 30, 1000, revenue=2.0)
poblar(c, "UC_B", "Canal B", 30, 500)          # sin ingresos: fuera de YPP
poblar(c, "UC_C", "Canal C", 5, 300)           # llegó tarde: solo 5 días

comp = reports.comparativa(c, ["UC_A", "UC_B", "UC_C"], days=30,
                           metrica="views")
serie = {s["channel_id"]: s for s in comp["series"]}
check("C1 todas las series comparten el mismo eje de fechas",
      len(comp["fechas"]) == 30
      and all(len(s["valores"]) == 30 for s in comp["series"]), "")
check("C2 un canal sin datos en un día deja HUECO (None), no un cero falso",
      serie["UC_C"]["valores"][0] is None
      and serie["UC_C"]["valores"][-1] == 300, serie["UC_C"]["valores"][:3])
check("C3 el total de cada serie suma solo los días conocidos",
      serie["UC_C"]["total"] == 5 * 300
      and serie["UC_A"]["total"] == 30 * 1000, "")
check("C4 las series salen ordenadas de mayor a menor (la leyenda también)",
      [s["channel_id"] for s in comp["series"]] == ["UC_A", "UC_B", "UC_C"],
      [s["channel_id"] for s in comp["series"]])

comp_rev = reports.comparativa(c, ["UC_A", "UC_B"], days=30,
                               metrica="revenue")
srev = {s["channel_id"]: s for s in comp_rev["series"]}
check("C5 «sin ingresos» viaja como None (nunca como 0 dólares)",
      all(v is None for v in srev["UC_B"]["valores"])
      and srev["UC_B"]["total"] is None
      and srev["UC_A"]["total"] == 60.0, srev["UC_B"]["total"])

comp_h = reports.comparativa(c, ["UC_A"], days=30, metrica="watch_hours")
check("C6 las horas vistas se derivan de los minutos (5000 min = 83,33 h)",
      comp_h["series"][0]["valores"][-1] == 83.33,
      comp_h["series"][0]["valores"][-1])
comp_s = reports.comparativa(c, ["UC_A"], days=30, metrica="subs_net")
check("C7 los suscriptores netos son ganados menos perdidos (10-4=6)",
      comp_s["series"][0]["valores"][-1] == 6, "")

try:
    reports.comparativa(c, ["UC_A"], days=30, metrica="inventada")
    check("C8 una métrica desconocida se rechaza", False, "no lanzó")
except ValueError:
    check("C8 una métrica desconocida se rechaza", True, "")

# Folding: 12 canales → 7 + «Otros»
c2 = nueva_db("muchos")
for i in range(12):
    poblar(c2, f"UC_{i:02d}", f"Canal {i:02d}", 10, 1000 - i * 50)
muchos = reports.comparativa(c2, [f"UC_{i:02d}" for i in range(12)], days=10)
check("C9 con 12 canales se pintan 8 series: los 7 mayores y «Otros»",
      len(muchos["series"]) == 8
      and muchos["series"][-1]["channel_id"] == "__otros__"
      and muchos["agrupados"] == 5, len(muchos["series"]))
check("C9b «Otros» suma de verdad a los 5 canales agrupados",
      muchos["series"][-1]["valores"][0]
      == sum(1000 - i * 50 for i in range(7, 12)),
      muchos["series"][-1]["valores"][0])

# ---------------------------------------------------------------------------
# Tabla dinámica
# ---------------------------------------------------------------------------
piv = reports.pivote(c, ["UC_A", "UC_B", "UC_C"], days=30, agrupacion="canal")
por = {f["clave"]: f for f in piv["filas"]}
check("P1 agrupado por canal: una fila por canal, la mayor primero",
      [f["clave"] for f in piv["filas"]] == ["UC_A", "UC_B", "UC_C"],
      [f["clave"] for f in piv["filas"]])
check("P2 el RPM son los ingresos por cada mil vistas del MISMO periodo",
      por["UC_A"]["revenue"] == 60.0 and por["UC_A"]["views"] == 30000
      and por["UC_A"]["rpm"] == 2.0, por["UC_A"])
check("P3 un canal sin ingresos deja ingresos y RPM en «sin dato», no en 0",
      por["UC_B"]["revenue"] is None and por["UC_B"]["rpm"] is None, "")
check("P4 el total de la red suma todo y trae su propio RPM",
      piv["total"]["views"] == 30000 + 15000 + 1500
      and piv["total"]["revenue"] == 60.0, piv["total"])

sem = reports.pivote(c, ["UC_A"], days=28, agrupacion="semana")
check("P5 agrupado por semana: 28 días caen en 4 o 5 semanas naturales",
      4 <= len(sem["filas"]) <= 5
      and sum(f["views"] for f in sem["filas"]) == 28000,
      [f["etiqueta"] for f in sem["filas"]])
mes = reports.pivote(c, ["UC_A"], days=30, agrupacion="mes")
check("P6 agrupado por mes: etiqueta legible en español",
      any("agosto 2026" in f["etiqueta"] for f in mes["filas"]),
      [f["etiqueta"] for f in mes["filas"]])
dias_p = reports.pivote(c, ["UC_A"], days=7, agrupacion="dia")
check("P7 agrupado por día: 7 filas en orden cronológico",
      len(dias_p["filas"]) == 7
      and dias_p["filas"][0]["clave"] < dias_p["filas"][-1]["clave"], "")
try:
    reports.pivote(c, ["UC_A"], days=7, agrupacion="galaxia")
    check("P8 una agrupación desconocida se rechaza", False, "no lanzó")
except ValueError:
    check("P8 una agrupación desconocida se rechaza", True, "")

check("P9 sin canales seleccionados no revienta: devuelve tabla vacía",
      reports.pivote(c, [], days=30)["filas"] == []
      and reports.comparativa(c, [], days=30)["series"] == [], "")

# ---------------------------------------------------------------------------
# Top videos
# ---------------------------------------------------------------------------
db.upsert_videos(c, "UC_A", [
    {"video_id": "v1", "title": "El más visto", "views": 9000, "likes": 400,
     "comments": 50, "published_at": "2026-07-01T10:00:00Z"},
    {"video_id": "v2", "title": "El segundo", "views": 3000, "likes": 300,
     "comments": 60, "published_at": "2026-07-15T10:00:00Z"},
])
tv = reports.top_videos(c, ["UC_A", "UC_B"], 10)
check("V1 el ranking ordena por vistas y trae el nombre del canal",
      [v["video_id"] for v in tv] == ["v1", "v2"] and tv[0]["canal"] == "Canal A",
      "")
check("V2 la interacción es (me gusta + comentarios) por cada 100 vistas: "
      "el segundo video interactúa MÁS aunque se vea menos",
      tv[0]["interaccion"] == 5.0 and tv[1]["interaccion"] == 12.0,
      [v["interaccion"] for v in tv])

# ---------------------------------------------------------------------------
# CSV para Excel en español
# ---------------------------------------------------------------------------
csv = reports.a_csv([("a", "Texto"), ("b", "Número"), ("c", "Vacío")],
                    [{"a": "Faros; y mares", "b": 1234.5, "c": None},
                     {"a": 'Comillas "raras"', "b": 7, "c": 0}])
texto = csv.decode("utf-8-sig")
lineas = texto.strip().split("\r\n")
check("X1 el archivo empieza con BOM (sin él Excel se come las tildes)",
      csv.startswith(b"\xef\xbb\xbf"), csv[:6])
check("X2 encabezados y separador «;» (el que espera el Excel en español)",
      lineas[0] == "Texto;Número;Vacío", lineas[0])
check("X3 los decimales van con coma",
      ";1234,50;" in lineas[1], lineas[1])
check("X4 «sin dato» queda como celda VACÍA, no como cero",
      lineas[1].endswith(";"), lineas[1])
check("X5 un texto con «;» va entrecomillado (si no, partiría la fila)",
      lineas[1].startswith('"Faros; y mares"'), lineas[1])
check("X6 las comillas internas se duplican, como manda el formato",
      '"Comillas ""raras"""' in lineas[2], lineas[2])
check("X7 el CSV del pivote incluye la fila de totales al final",
      reports.csv_pivote(c, ["UC_A"], 30, "canal").decode("utf-8-sig")
      .strip().split("\r\n")[-1].startswith("Total de la red"), "")
check("X8 el detalle diario trae una fila por canal y día",
      len(reports.csv_diario(c, ["UC_A", "UC_B"], 7).decode("utf-8-sig")
          .strip().split("\r\n")) == 1 + 14, "")

# ---------------------------------------------------------------------------
# Alertas: cada regla con su caso que dispara y su caso que NO
# ---------------------------------------------------------------------------
def reglas(conn):
    return {a["regla"] for a in alerts.revisar(conn, UMBRALES, HOY)}


sano = nueva_db("sano")
poblar(sano, "UC_OK", "Canal sano", 30, 1000, revenue=2.0,
       token_status="ok", last_sync=f"{dia(0)} 03:00:00")
db.upsert_videos(sano, "UC_OK", [
    {"video_id": f"v{i}", "title": f"Video {i}", "views": 1000,
     "published_at": dia(i * 3) + "T10:00:00Z"} for i in range(6)])
check("A0 un canal sano no genera NINGUNA alerta (si no, serían ruido)",
      reglas(sano) == set(), reglas(sano))

# Token caído
malo = nueva_db("token")
poblar(malo, "UC_R", "Canal revocado", 30, 1000, token_status="reauth",
       last_sync=f"{dia(0)} 03:00:00")
check("A1 token caído → alerta CRÍTICA (sin eso no entra nada del canal)",
      "token_caido" in reglas(malo)
      and [a for a in alerts.revisar(malo, UMBRALES, HOY)
           if a["regla"] == "token_caido"][0]["severidad"] == "critica", "")

# Sin sincronizar
viejo = nueva_db("viejo")
poblar(viejo, "UC_V", "Canal olvidado", 30, 1000, token_status="ok",
       last_sync=f"{dia(5)} 03:00:00")
db.upsert_videos(viejo, "UC_V", [
    {"video_id": "v1", "title": "Reciente", "views": 500,
     "published_at": dia(2) + "T10:00:00Z"}])
check("A2 5 días sin sincronizar dispara aviso; 1 día no",
      "sin_sincronizar" in reglas(viejo), reglas(viejo))
db.upsert_channel(viejo, "UC_V", last_sync=f"{dia(1)} 03:00:00")
check("A2b …y con el sync de ayer la alerta desaparece",
      "sin_sincronizar" not in reglas(viejo), reglas(viejo))

# Caída y subida de vistas
def canal_con_curva(nombre, previos, actuales, rev_prev=None, rev_act=None):
    conn = nueva_db(nombre)
    db.upsert_channel(conn, "UC_X", title="Curva", token_status="ok",
                      last_sync=f"{dia(0)} 03:00:00")
    filas, money = {}, {}
    for i in range(14):
        fecha = dia(14 - i)
        valor = previos if i < 7 else actuales
        filas[fecha] = {"views": valor, "watch_minutes": valor,
                        "subs_gained": 1, "subs_lost": 0}
        if rev_prev is not None:
            money[fecha] = rev_prev if i < 7 else rev_act
    db.upsert_daily(conn, "UC_X", filas)
    if money:
        db.set_revenue(conn, "UC_X", money)
    db.upsert_videos(conn, "UC_X", [
        {"video_id": "v1", "title": "Reciente", "views": 100,
         "published_at": dia(3) + "T10:00:00Z"}])
    return conn


check("A3 vistas a la mitad (-50%) dispara «caída de vistas»",
      "caida_vistas" in reglas(canal_con_curva("caida", 1000, 500)), "")
check("A3b una bajada del 10% NO dispara nada (sería ruido diario)",
      "caida_vistas" not in reglas(canal_con_curva("leve", 1000, 900)), "")
check("A3c un canal minúsculo tampoco dispara porcentajes (bajo el mínimo)",
      "caida_vistas" not in reglas(canal_con_curva("chico", 10, 1)), "")
check("A4 vistas al doble dispara la BUENA señal, no un aviso",
      "subida_vistas" in reglas(canal_con_curva("subida", 500, 1000)), "")
check("A5 ingresos a la mitad dispara «caída de ingresos»",
      "caida_ingresos" in reglas(
          canal_con_curva("dinero", 1000, 1000, rev_prev=2.0, rev_act=0.5)), "")
check("A5b con los ingresos estables no salta",
      "caida_ingresos" not in reglas(
          canal_con_curva("estable", 1000, 1000, rev_prev=2.0, rev_act=2.0)), "")

# Canal apagado
apagado = nueva_db("apagado")
poblar(apagado, "UC_P", "Canal apagado", 30, 1000, token_status="ok",
       last_sync=f"{dia(0)} 03:00:00")
db.upsert_videos(apagado, "UC_P", [
    {"video_id": "v1", "title": "El último", "views": 1000,
     "published_at": dia(40) + "T10:00:00Z"}])
check("A6 40 días sin publicar dispara «canal apagado» (umbral 21)",
      "sin_publicar" in reglas(apagado), reglas(apagado))

# Video que despunta
pega = nueva_db("pega")
poblar(pega, "UC_H", "Canal con hit", 30, 1000, token_status="ok",
       last_sync=f"{dia(0)} 03:00:00")
db.upsert_videos(pega, "UC_H", [
    {"video_id": f"v{i}", "title": f"Normal {i}", "views": 1000,
     "published_at": dia(60 + i) + "T10:00:00Z"} for i in range(5)]
    + [{"video_id": "hit", "title": "El que pegó", "views": 9000,
        "published_at": dia(5) + "T10:00:00Z"}])
lista_pega = alerts.revisar(pega, UMBRALES, HOY)
check("A7 un video reciente 9× sobre la mediana sale como oportunidad",
      any(a["regla"] == "video_despunta" and "El que pegó" in a["titulo"]
          for a in lista_pega), [a["regla"] for a in lista_pega])
check("A7b …y solo se avisa de UNO por canal (la bandeja debe ser útil)",
      sum(1 for a in lista_pega if a["regla"] == "video_despunta") == 1, "")

# Cola con errores
cola = nueva_db("cola")
poblar(cola, "UC_C2", "Canal", 30, 1000, token_status="ok",
       last_sync=f"{dia(0)} 03:00:00")
db.upsert_videos(cola, "UC_C2", [
    {"video_id": "v1", "title": "Reciente", "views": 100,
     "published_at": dia(2) + "T10:00:00Z"}])
jid = db.enqueue_job(cola, "UC_C2", "video_update", {}, 51)
db.update_job(cola, jid, status="error", nota="403")
check("A8 una edición fallida en la cola se avisa (sus cambios NO están "
      "en YouTube)", "cola_errores" in reglas(cola), reglas(cola))

# Forma y orden
todas = alerts.revisar(malo, UMBRALES, HOY)
check("A9 cada alerta trae icono, severidad en palabras, explicación y qué "
      "hacer (el color nunca es la única señal)",
      all(a["icono"] and a["severidad_texto"] and a["detalle"] and a["accion"]
          for a in todas), "")
mezcla = alerts.revisar(canal_con_curva("orden", 500, 1000), UMBRALES, HOY)
check("A10 las buenas señales van al final: primero lo que urge",
      [a["severidad"] for a in mezcla] == sorted(
          [a["severidad"] for a in mezcla],
          key=lambda s: {"critica": 0, "aviso": 1, "buena": 2}[s]), "")
check("A11 el resumen cuenta por severidad",
      alerts.resumen(todas)["criticas"] == 1
      and alerts.resumen([])["total"] == 0, "")

# ---------------------------------------------------------------------------
# Servidor
# ---------------------------------------------------------------------------
os.environ["YTPANEL_DATA_DIR"] = str(TMP / "srv")
from ytpanel import config as _cfg  # noqa: E402
_cfg.data_dir()
srv_conn = db.connect()
poblar(srv_conn, "UC_S1", "Servidor A", 30, 1000, revenue=2.0,
       token_status="ok", last_sync=f"{dia(0)} 03:00:00")
poblar(srv_conn, "UC_S2", "Servidor B", 30, 400, token_status="ok",
       last_sync=f"{dia(0)} 03:00:00")
srv_conn.close()

from ytpanel import server as srv  # noqa: E402

httpd = srv.make_server(0)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"


def pedir(ruta):
    try:
        with urllib.request.urlopen(BASE + ruta, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


st, cuerpo, _ = pedir("/api/reportes/comparativa?days=30&metrica=views")
datos = json.loads(cuerpo)
check("S1 la comparativa por API cubre todos los canales si no se filtra",
      st == 200 and len(datos["series"]) == 2 and len(datos["fechas"]) == 30, st)
st, cuerpo, _ = pedir("/api/reportes/comparativa?canales=UC_S1&days=30")
check("S1b …y respeta el filtro de canales",
      st == 200 and len(json.loads(cuerpo)["series"]) == 1, st)
st, cuerpo, _ = pedir("/api/reportes/comparativa?canales=UC_INVENTADO")
check("S1c un canal inexistente en la URL se rechaza con explicación",
      st == 400 and "canales" in json.loads(cuerpo)["error"], cuerpo[:80])
st, cuerpo, _ = pedir("/api/reportes/comparativa?metrica=inventada")
check("S1d una métrica inexistente responde 400, no 500", st == 400, st)
st, cuerpo, _ = pedir("/api/reportes/pivote?agrupacion=semana&days=28")
check("S2 el pivote por API agrupa y devuelve totales",
      st == 200 and json.loads(cuerpo)["total"]["views"] > 0, st)
st, cuerpo, _ = pedir("/api/reportes/videos")
check("S3 el ranking de videos responde aunque no haya videos",
      st == 200 and "videos" in json.loads(cuerpo), st)
st, cuerpo, _ = pedir("/api/alertas")
check("S4 /api/alertas devuelve lista y resumen",
      st == 200 and "alertas" in json.loads(cuerpo)
      and "criticas" in json.loads(cuerpo)["resumen"], st)

st, cuerpo, cab = pedir("/api/export/pivote.csv?days=30&agrupacion=canal")
check("S5 la descarga del CSV llega como adjunto con nombre y BOM",
      st == 200 and "attachment" in cab.get("Content-Disposition", "")
      and ".csv" in cab.get("Content-Disposition", "")
      and cuerpo.startswith(b"\xef\xbb\xbf"), cab.get("Content-Disposition"))
st, cuerpo, _ = pedir("/api/export/diario.csv?days=7")
check("S5b el detalle diario también se descarga",
      st == 200 and cuerpo.count(b"\r\n") == 1 + 14, cuerpo.count(b"\r\n"))
st, _, _ = pedir("/api/export/videos.csv")
check("S5c y el de videos", st == 200, st)
st, cuerpo, _ = pedir("/api/reportes/pivote?days=abc")
check("S6 un «days» que no es número responde 400 con mensaje claro",
      st == 400 and "days" in json.loads(cuerpo)["error"], st)

st, cuerpo, _ = pedir("/api/overview")
check("S7 el estado del panel ya trae el resumen de alertas",
      st == 200 and "alertas" in json.loads(cuerpo)["estado"], st)

httpd.shutdown()

# ---------------------------------------------------------------------------
# Configuración: los bloques anidados se fusionan
# ---------------------------------------------------------------------------
cfg = _cfg.load_panel_config()
check("F1 tocar un umbral no deja los demás en cero (fusión profunda)",
      isinstance(cfg.get("alertas"), dict)
      and len(cfg["alertas"]) >= 7
      and cfg["alertas"]["dias_sin_publicar"] > 0, cfg.get("alertas"))

# ---------------------------------------------------------------------------
c.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.56.0 completa: los reportes comparan sin mentir (hueco "
      "≠ cero, sin datos ≠ sin dinero), el RPM cuadra, los CSV se abren en "
      "Excel y cada alerta salta cuando debe y calla cuando no.")
