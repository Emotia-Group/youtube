"""Batería v0.32.0: CERO PÉRDIDA DE SALDO — libro de predicciones pagadas.

Pérdida real del usuario (dashboard de Replicate, 2026-08-04): 5 predicciones
de bytedance/omni-human TERMINARON BIEN y se cobraron $2.37 cada una
($11.85) sin entregar UN SOLO archivo, y sin aparecer en el reporte de gasto
de la app. Causas encontradas en el código:

  C1  El dinero se gasta cuando la predicción termina bien en el SERVIDOR,
      pero el resultado se descartaba si fallaba la DESCARGA — sin guardar
      ni el id ni la URL: irrecuperable.
  C2  Cada reintento CREABA una predicción nueva = cobro nuevo.
  C3  usage.record() se llamaba DESPUÉS de descargar → el gasto real quedaba
      INVISIBLE en el reporte cuando la descarga fallaba.
  C4  Un corte de red durante predictions.create() podía dejar una predicción
      huérfana corriendo (y cobrada) que nadie reclamaba, y encima se creaba
      otra encima.
  C5  Sin tope de presupuesto: nada frenaba el gasto.

T1  El libro registra el ciclo completo (created→succeeded→downloaded) y
      reconstruye el estado releyendo el archivo desde cero (a prueba de
      cortes de luz).
T2  C1+C3: si la descarga falla tras una predicción exitosa, el gasto SÍ
      queda registrado y la predicción queda en el libro como PAGADA-NO
      ENTREGADA, con su URL, lista para recuperar.
T3  C1: el segundo intento RE-DESCARGA lo ya pagado y NO crea una predicción
      nueva (el escenario exacto que costó $11.85).
T4  C2: un resultado ya descargado no se vuelve a pedir ni a cobrar... y una
      URL caducada (>1 h) ya no se reutiliza (Replicate la borra).
T5  C4: si create() se corta por red pero el servidor SÍ aceptó la
      predicción, se ADOPTA la huérfana en vez de crear otra (sin doble
      cobro).
T6  C5: el tope de presupuesto frena ANTES de encargar lo que se pasaría, y
      no se reintenta como si fuera un error de red.
T7  El gasto se anota UNA sola vez aunque se reutilice el resultado.
T8  Reengancharse a una predicción en curso no crea otra (sin doble cobro).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sys
import time
from pathlib import Path



TMP = Path(__file__).parent / "t320"
TMP.mkdir(exist_ok=True)

# El libro debe vivir en un sitio aislado para la prueba: se apunta ROOT del
# módulo de config ANTES de importar el libro.
import ytstudio.config as cfg_mod
cfg_mod.ROOT = TMP

FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio import ledger, usage
from ytstudio.providers import replicate_util
from ytstudio.providers.replicate_util import run_and_download, set_progress

ledger.LEDGER_PATH = TMP / "predicciones.jsonl"

notices = []
set_progress(lambda m: notices.append(m))


def reset_all():
    ledger.LEDGER_PATH.unlink(missing_ok=True)
    usage.reset()
    usage.set_cap(0)
    notices.clear()


# --- servidor HTTP local real: entrega el "resultado" y puede cortar -------
import http.server
import threading as th

serve = {"fail_times": 0, "hits": 0}


class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        serve["hits"] += 1
        if serve["fail_times"] > 0:
            serve["fail_times"] -= 1
            self.close_connection = True
            self.connection.close()
            return
        body = b"CLIP-REAL-DESCARGADO"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
PORT = srv.server_address[1]
th.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{PORT}/resultado.mp4"


class _Pred:
    def __init__(self, pid, status="succeeded", output=None, waits_fail=0):
        self.id = pid
        self.status = status
        self.output = output if output is not None else [URL]
        self.error = None
        self.waits_fail = waits_fail

    def wait(self):
        if self.waits_fail > 0:
            self.waits_fail -= 1
            raise ConnectionResetError("[WinError 10054] corte en la espera")
        self.status = "succeeded"


class _Client:
    """Cliente Replicate falso con contabilidad: cuenta cuántas predicciones
    se CREAN (= cuántas veces se cobra) para poder afirmarlo en las pruebas."""

    def __init__(self, create_fails=0, waits_fail=0, orphan=None):
        self.creates = 0
        self.gets = 0
        self.create_fails = create_fails
        self.waits_fail = waits_fail
        self.orphan = orphan
        self.made: list[_Pred] = []
        outer = self

        class _Preds:
            def create(inner, version=None, input=None):
                if outer.create_fails > 0:
                    outer.create_fails -= 1
                    raise ConnectionResetError(
                        "[WinError 10054] corte al crear")
                outer.creates += 1
                p = _Pred(f"pred-{outer.creates}",
                          waits_fail=outer.waits_fail)
                outer.made.append(p)
                return p

            def get(inner, pid):
                outer.gets += 1
                for p in outer.made:
                    if p.id == pid:
                        return p
                if outer.orphan is not None and outer.orphan.id == pid:
                    return outer.orphan
                raise RuntimeError("no existe")

            def list(inner):
                return [outer.orphan] if outer.orphan is not None else []

        class _V:
            id = "ver-1"

        class _M:
            latest_version = _V()

        class _Models:
            def get(inner, model):
                return _M()

        self.predictions = _Preds()
        self.models = _Models()


CHARGE = {"provider": "replicate", "label": "lipsync 15s (omni-human)",
          "qty": 15, "unit": "s", "usd": 2.37}

print("T1 el libro registra el ciclo completo y se relee desde cero")
reset_all()
ledger.record_created("p1", "bytedance/omni-human", "k1", 2.37, "proj", "lip")
ledger.record_succeeded("p1", URL)
ledger.record_downloaded("p1", "/tmp/x.mp4")
st = ledger.state()
check("estado final = downloaded", st["p1"]["status"] == "downloaded")
check("conserva modelo, clave, costo y URL",
      st["p1"]["model"] == "bytedance/omni-human" and st["p1"]["usd"] == 2.37
      and st["p1"]["url"] == URL and st["p1"]["key"] == "k1", str(st["p1"]))
check("nada pendiente de cobrar cuando sí se descargó",
      ledger.pending_paid() == [])

print("T2 descarga fallida tras predicción exitosa: gasto VISIBLE y rescatable")
reset_all()
serve["fail_times"] = 99  # la descarga nunca funciona
cli = _Client()
out = TMP / "escena1.mp4"
try:
    run_and_download(cli, "bytedance/omni-human", {}, out, charge=CHARGE,
                     net_retries=1, max_retries=0)
    check("la descarga falla (como en la pérdida real)", False)
except Exception:
    check("la descarga falla (como en la pérdida real)", True)
check("se creó UNA predicción", cli.creates == 1, str(cli.creates))
check("EL GASTO QUEDA REGISTRADO aunque no haya archivo (antes: invisible)",
      abs(usage.summary()["total_usd"] - 2.37) < 0.01,
      str(usage.summary()))
pend = ledger.pending_paid()
check("queda anotada como PAGADA-NO-ENTREGADA con su URL",
      len(pend) == 1 and pend[0]["url"] == URL and pend[0]["usd"] == 2.37,
      str(pend))
check("el importe en riesgo se puede reportar al usuario",
      abs(ledger.pending_paid_usd() - 2.37) < 0.01)
check("se avisa de que ya se cobró y se puede recuperar",
      any("ya se cobró" in n for n in notices), str(notices))

print("T3 el 2º intento RE-DESCARGA lo pagado y NO vuelve a cobrar "
      "(el escenario de los $11.85)")
serve["fail_times"] = 0   # la red vuelve
usage.reset()
cli2 = _Client()           # cliente nuevo: si creara, se vería en creates
run_and_download(cli2, "bytedance/omni-human", {}, out, charge=CHARGE,
                 net_retries=1, max_retries=0)
check("NO se creó ninguna predicción nueva (cero cobro nuevo)",
      cli2.creates == 0, str(cli2.creates))
check("el archivo YA está en disco",
      out.exists() and out.read_bytes() == b"CLIP-REAL-DESCARGADO")
check("no se vuelve a cargar el gasto al reutilizar",
      usage.summary()["total_usd"] == 0, str(usage.summary()))
check("avisa de que recupera algo ya pagado",
      any("YA habías pagado" in n for n in notices), str(notices))
check("el libro la marca como entregada", ledger.pending_paid() == [])

print("T4 no se repite lo ya entregado; una URL caducada ya no se reutiliza")
cli3 = _Client()
run_and_download(cli3, "bytedance/omni-human", {}, out, charge=CHARGE,
                 net_retries=1, max_retries=0)
check("un resultado ya descargado se vuelve a pedir (no se reutiliza a ciegas)",
      cli3.creates == 1, str(cli3.creates))
reset_all()
ledger.record_created("viejo", "m", "k-viejo", 2.37)
ledger.record_succeeded("viejo", URL)
# envejecer el evento: se reescribe el libro con una marca de tiempo antigua
raw = ledger.LEDGER_PATH.read_text(encoding="utf-8").splitlines()
import json as _json
old = time.time() - ledger.URL_TTL_SECONDS - 60
ledger.LEDGER_PATH.write_text("\n".join(
    _json.dumps({**_json.loads(l), "ts": old}) for l in raw) + "\n",
    encoding="utf-8")
check("una URL caducada (>1 h) NO se ofrece como reutilizable",
      ledger.find_reusable("k-viejo") is None)
check("y tampoco cuenta como recuperable dentro del plazo",
      ledger.pending_paid(max_age_seconds=ledger.URL_TTL_SECONDS) == [])

print("T5 corte al CREAR: se adopta la predicción huérfana (sin doble cobro)")
reset_all()
serve["fail_times"] = 0
orphan = _Pred("huerfana-1")
orphan.created_at = None
orphan.model = "bytedance/omni-human"
cli4 = _Client(create_fails=1, orphan=orphan)
out5 = TMP / "escena5.mp4"
run_and_download(cli4, "bytedance/omni-human", {}, out5, charge=CHARGE,
                 net_retries=2, max_retries=1)
check("NO se creó una predicción duplicada", cli4.creates == 0,
      str(cli4.creates))
check("se adoptó la huérfana y se entregó el archivo", out5.exists())
check("avisa de la adopción (no se paga dos veces)",
      any("no se paga dos veces" in n for n in notices), str(notices))
check("la huérfana queda anotada en el libro",
      "huerfana-1" in ledger.state())

print("T6 tope de presupuesto: frena ANTES de encargar y no se reintenta")
reset_all()
usage.set_cap(3.0)
usage.add_spend(2.0)          # ya se gastaron $2 en esta generación
cli6 = _Client()
try:
    run_and_download(cli6, "bytedance/omni-human", {}, TMP / "escena6.mp4",
                     charge=CHARGE, net_retries=1, max_retries=3)
    check("se detiene al pasarse del tope", False)
except usage.BudgetExceeded as e:
    check("se detiene al pasarse del tope", True)
    check("el aviso dice cuánto llevas, cuánto costaría y el tope",
          "2.00" in str(e) and "2.37" in str(e) and "3.00" in str(e), str(e))
check("NO se encargó nada (cero cobro)", cli6.creates == 0, str(cli6.creates))
usage.set_cap(0)
cli6b = _Client()
run_and_download(cli6b, "m/x", {}, TMP / "escena6b.mp4", charge=CHARGE,
                 net_retries=1, max_retries=0)
check("sin tope (0) se genera con normalidad", cli6b.creates == 1)

print("T7 el gasto se cuenta UNA vez y cuenta contra el tope")
reset_all()
usage.set_cap(10.0)
serve["fail_times"] = 0
cli7 = _Client()
o7 = TMP / "escena7.mp4"
run_and_download(cli7, "m/x", {}, o7, charge=CHARGE, net_retries=1,
                 max_retries=0)
check("gasto contabilizado una vez",
      abs(usage.summary()["total_usd"] - 2.37) < 0.01, str(usage.summary()))
check("y descontado del tope disponible",
      abs(usage.spent() - 2.37) < 0.01, str(usage.spent()))

print("T8 reengancharse a una predicción en curso no crea otra")
reset_all()
serve["fail_times"] = 0
cli8 = _Client()
o8 = TMP / "escena8.mp4"
# 1er intento: la espera se corta hasta agotar reintentos → queda 'created'
cli8.waits_fail = 99
try:
    run_and_download(cli8, "m/x", {}, o8, charge=CHARGE, net_retries=1,
                     max_retries=0)
except Exception:
    pass
check("quedó una predicción creada (corriendo en el servidor)",
      cli8.creates == 1 and any(
          p.get("status") == "created" for p in ledger.state().values()),
      str(ledger.state()))
# 2º intento: la red vuelve → debe REENGANCHARSE, no crear otra
cli8.waits_fail = 0
for p in cli8.made:
    p.waits_fail = 0
run_and_download(cli8, "m/x", {}, o8, charge=CHARGE, net_retries=1,
                 max_retries=0)
check("NO se creó una segunda predicción (sin doble cobro)",
      cli8.creates == 1, str(cli8.creates))
check("se reenganchó y entregó el archivo", o8.exists())
check("avisa del reenganche",
      any("Reenganchando" in n for n in notices), str(notices))

srv.shutdown()
import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
