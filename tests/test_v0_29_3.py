"""Batería v0.29.3: reintento ante cortes de red pasajeros (WinError 10054).

Bug real (log del usuario, test-2-hetty, 2026-07-25): la fase de Imágenes
falló POR COMPLETO con "[WinError 10054] Se ha forzado la interrupción de
una conexión existente por el host remoto" — un corte de red de Windows,
casi siempre transitorio. replicate_call() solo reintentaba en 429 (límite
de velocidad); cualquier otro error (incluyendo este) se propagaba de
inmediato y detenía toda la fase, exigiendo reanudar a mano. Además
urllib.request.urlretrieve() (la descarga del resultado, ya con la
predicción resuelta) no tenía NINGÚN reintento.

T1  _is_transient_network_error reconoce ConnectionResetError/TimeoutError y
    los mensajes de texto (WinError 10054/10053/10060, "connection reset",
    "forcibly closed", etc.) — y NO confunde con ellos un error real de
    modelo/cuenta (404, 401, 402, contenido NSFW).
T2  replicate_call: ante 2 cortes de red pasajeros seguidos y éxito al
    tercer intento, DEVUELVE el resultado (no detiene la fase) — probado
    con un cliente falso real que lanza las excepciones reales.
T3  replicate_call: si el corte de red NUNCA cede (agota net_retries),
    termina en un RuntimeError con mensaje claro y accionable (no un
    traceback críptico).
T4  replicate_call: un error real (401, modelo inválido) NO se reintenta
    como si fuera de red — sigue fallando de inmediato con su mensaje claro
    de siempre (sin regresión de v0.28.0/v0.29.x).
T5  download_with_retry: mismo patrón (falla transitoriamente 2 veces,
    tercer intento escribe el archivo real) usando un servidor HTTP local
    real (no mock) que corta la conexión las 2 primeras veces.
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



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio.providers.replicate_util import (
    _is_transient_network_error, replicate_call, download_with_retry,
    set_progress,
)

# Silenciar los avisos de reintento en la consola de prueba (se listan aparte)
notices = []
set_progress(lambda m: notices.append(m))

print("T1 detección de errores de red transitorios vs. errores reales")
check("ConnectionResetError → transitorio",
      _is_transient_network_error(ConnectionResetError("boom")))
check("TimeoutError → transitorio",
      _is_transient_network_error(TimeoutError("boom")))
check("mensaje con WinError 10054 → transitorio",
      _is_transient_network_error(OSError(
          "[WinError 10054] Se ha forzado la interrupción de una conexión "
          "existente por el host remoto")))
check("mensaje 'Connection aborted' → transitorio",
      _is_transient_network_error(Exception("Connection aborted.")))
check("mensaje 'Remote end closed connection' → transitorio",
      _is_transient_network_error(Exception(
          "Remote end closed connection without response")))
check("404 modelo no encontrado → NO transitorio",
      not _is_transient_network_error(
          Exception("404: Model not found")))
check("401 token inválido → NO transitorio",
      not _is_transient_network_error(
          Exception("401 Unauthorized: invalid token")))
check("rechazo de contenido NSFW → NO transitorio",
      not _is_transient_network_error(
          Exception("The input or output was flagged as sensitive (E005)")))


class _FakeClient:
    """Cliente Replicate falso: predictions.create()/pred.wait() simulan el
    polling real; se le dice cuántas veces fallar con qué excepción antes de
    devolver un resultado, para ejercer replicate_call() de verdad (sin
    mockear la función que se está probando)."""

    def __init__(self, fail_times, exc_factory):
        self.fail_times = fail_times
        self.exc_factory = exc_factory
        self.calls = 0

        class _Predictions:
            def create(inner_self, version=None, input=None):
                self.calls += 1
                if self.calls <= self.fail_times:
                    raise self.exc_factory()
                return _Pred()

        class _Models:
            def get(inner_self, model):
                raise Exception("sin versión resoluble")  # fuerza client.run

        self.predictions = _Predictions()
        self.models = _Models()

    def run(self, model, input=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc_factory()
        return ["https://ejemplo.invalido/resultado.jpg"]


class _Pred:
    status = "succeeded"
    output = ["https://ejemplo.invalido/resultado.jpg"]
    error = None

    def wait(self):
        pass


print("T2 corte de red pasajero (2 fallos) + éxito al 3er intento → NO detiene la fase")
t0 = time.time()
client = _FakeClient(2, lambda: ConnectionResetError(
    "[WinError 10054] Se ha forzado la interrupción de una conexión "
    "existente por el host remoto"))
result = replicate_call(client, "owner/modelo-inventado-para-prueba", {},
                        net_retries=5)
elapsed = time.time() - t0
check("devuelve el resultado tras los reintentos",
      result == ["https://ejemplo.invalido/resultado.jpg"], str(result))
check("hizo 3 intentos en total (2 fallos + 1 éxito)", client.calls == 3,
      str(client.calls))
check("esperó con backoff creciente antes de devolver (no instantáneo)",
      elapsed >= 2.0, f"{elapsed:.1f}s")
check("avisó del corte de red (no falló en silencio)",
      any("Corte de red pasajero" in n for n in notices), str(notices))

print("T3 corte de red que NUNCA cede → RuntimeError claro (no traceback críptico)")
notices.clear()
client2 = _FakeClient(999, lambda: ConnectionResetError(
    "[WinError 10054] Se ha forzado la interrupción de una conexión "
    "existente por el host remoto"))
try:
    replicate_call(client2, "owner/modelo-inventado-para-prueba", {},
                   net_retries=2)
    check("lanzó RuntimeError al agotar los reintentos", False)
except RuntimeError as e:
    check("lanzó RuntimeError al agotar los reintentos", True)
    check("el mensaje es accionable (menciona reintentar/conexión)",
          "conexión" in str(e).lower() or "Generar video" in str(e),
          str(e))
except Exception as e:
    check("lanzó RuntimeError (no otra excepción cruda)", False,
          f"{type(e).__name__}: {e}")

print("T4 error REAL (401 token inválido) → falla de inmediato, sin reintentar como red")
client3 = _FakeClient(999, lambda: Exception("401 Unauthorized: invalid token"))
try:
    replicate_call(client3, "owner/modelo-inventado-para-prueba", {})
    check("lanzó RuntimeError con el mensaje claro de token inválido", False)
except RuntimeError as e:
    check("lanzó RuntimeError con el mensaje claro de token inválido",
          "token" in str(e).lower(), str(e))
check("NO reintentó (1 sola llamada, error real detectado al toque)",
      client3.calls == 1, str(client3.calls))

print("T5 download_with_retry: corte de conexión real en 2 intentos, éxito al 3º "
      "(servidor HTTP local real, no simulado)")
import http.server
import socket
import threading as th
from pathlib import Path

TMP = Path(__file__).parent / "t293"
TMP.mkdir(exist_ok=True)
attempts = {"n": 0}


class _FlakyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            # cortar la conexión a medio camino, sin cerrar limpio (simula
            # el corte de red real que produce WinError 10054/Connection
            # reset en el lado del cliente)
            self.close_connection = True
            try:
                self.wfile._sock.setsockopt(
                    socket.SOL_SOCKET, socket.SO_LINGER,
                    __import__("struct").pack("ii", 1, 0))
            except Exception:
                pass
            self.connection.close()
            return
        body = b"contenido de prueba real"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = http.server.HTTPServer(("127.0.0.1", 0), _FlakyHandler)
port = server.server_address[1]
th.Thread(target=server.serve_forever, daemon=True).start()
try:
    out = TMP / "descarga.bin"
    out.unlink(missing_ok=True)
    download_with_retry(f"http://127.0.0.1:{port}/x", out, max_retries=5)
    check("el archivo se descargó tras los reintentos",
          out.exists() and out.read_bytes() == b"contenido de prueba real")
    check("tardó al menos 2 reintentos con espera (no fue instantáneo)",
          attempts["n"] == 3, str(attempts["n"]))
finally:
    server.shutdown()

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
