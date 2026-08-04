"""LIBRO DE PREDICCIONES PAGADAS — la contabilidad que evita perder saldo.

El dinero en Replicate se gasta en el momento en que la predicción TERMINA
BIEN en su servidor, no cuando el archivo llega a tu disco. Entre esos dos
momentos hay una descarga por red que puede fallar (y falló: 5 clips de
omni-human cobrados a $2.37 sin un solo archivo entregado). Sin dejar rastro
del id ni de la URL, ese dinero era irrecuperable Y además invisible en el
reporte de gasto.

Este libro registra CADA predicción en disco, en el momento exacto en que el
dinero entra en riesgo:

    created    → se creó la predicción (a partir de aquí puede cobrarse)
    succeeded  → terminó bien; se guarda la URL del resultado (YA cobrada)
    downloaded → el archivo está en disco (el dinero rindió su fruto)
    failed     → terminó mal o se perdió la conexión sin resultado

Con eso el programa puede, antes de crear NADA:
  · re-descargar un resultado que ya pagaste (sin volver a cobrar),
  · re-engancharse a una predicción que sigue corriendo (sin duplicarla),
  · y decirte exactamente qué pagaste y no recibiste.

Formato: JSONL de eventos (solo se AÑADEN líneas, nunca se reescribe el
archivo). Es a prueba de cortes de luz y de escrituras simultáneas de varios
hilos; el estado de cada predicción se reconstruye releyendo sus eventos.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ytstudio.config import ROOT

LEDGER_PATH = ROOT / "predicciones.jsonl"

# Las URLs de resultado de Replicate caducan (~1 h). Pasado ese plazo el
# archivo ya no se puede recuperar ni siquiera re-consultando la predicción.
URL_TTL_SECONDS = 3600

_lock = threading.Lock()


def _append(event: dict) -> None:
    """Añade un evento. Nunca lanza: el libro es una salvaguarda, jamás puede
    tumbar una generación que por lo demás va bien."""
    event["ts"] = time.time()
    try:
        with _lock:
            LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _events() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    out = []
    try:
        with _lock:
            raw = LEDGER_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # línea a medio escribir por un corte: se ignora
    return out


def state() -> dict[str, dict]:
    """Estado actual de cada predicción, reconstruido de sus eventos."""
    preds: dict[str, dict] = {}
    for e in _events():
        pid = e.get("id")
        if not pid:
            continue
        p = preds.setdefault(pid, {"id": pid, "status": "created"})
        for k, v in e.items():
            if k not in ("event", "ts"):
                p[k] = v
        ev = e.get("event")
        if ev:
            p["status"] = ev
            p[f"ts_{ev}"] = e.get("ts")
    return preds


# --- registro de eventos -------------------------------------------------

def record_created(pred_id: str, model: str, key: str, usd: float = 0.0,
                   project: str = "", label: str = "") -> None:
    _append({"event": "created", "id": pred_id, "model": model, "key": key,
             "usd": round(float(usd or 0), 4), "project": project,
             "label": label})


def record_succeeded(pred_id: str, url: str, usd: float | None = None) -> None:
    e = {"event": "succeeded", "id": pred_id, "url": str(url or "")}
    if usd is not None:
        e["usd"] = round(float(usd), 4)
    _append(e)


def record_downloaded(pred_id: str, path) -> None:
    _append({"event": "downloaded", "id": pred_id, "path": str(path)})


def record_failed(pred_id: str, error: str = "") -> None:
    _append({"event": "failed", "id": pred_id, "error": str(error)[:300]})


# --- consultas de recuperación -------------------------------------------

def find_reusable(key: str) -> dict | None:
    """Predicción YA PAGADA (o en curso) para esta misma clave, que se puede
    aprovechar en vez de crear —y cobrar— una nueva.

    Devuelve la más reciente que esté:
      · 'succeeded' y aún no descargada, con la URL todavía dentro del plazo
        de caducidad → se re-descarga gratis;
      · 'created' (sigue corriendo en el servidor) → se re-engancha.
    """
    if not key:
        return None  # sin clave estable no hay nada que reutilizar con
                     # seguridad (dos llamadas distintas no deben cruzarse)
    best = None
    for p in state().values():
        if p.get("key") != key:
            continue
        if p.get("status") == "succeeded" and p.get("url"):
            age = time.time() - (p.get("ts_succeeded") or 0)
            if age > URL_TTL_SECONDS:
                continue  # la URL ya caducó: no sirve de nada reintentarla
        elif p.get("status") != "created":
            continue      # downloaded (ya entregada) o failed (nada que sacar)
        if best is None or (p.get("ts_created") or 0) >= (best.get("ts_created") or 0):
            best = p
    return best


def pending_paid(max_age_seconds: float | None = None) -> list[dict]:
    """Predicciones que TERMINARON BIEN (y por tanto se cobraron) pero cuyo
    archivo nunca llegó a disco: el dinero gastado sin producto. Es la lista
    que se le muestra al usuario para recuperarlo (o para reclamarlo)."""
    out = []
    for p in state().values():
        if p.get("status") != "succeeded":
            continue
        if max_age_seconds is not None:
            if time.time() - (p.get("ts_succeeded") or 0) > max_age_seconds:
                continue
        out.append(p)
    return sorted(out, key=lambda p: p.get("ts_succeeded") or 0, reverse=True)


def pending_paid_usd(preds: list[dict] | None = None) -> float:
    preds = pending_paid() if preds is None else preds
    return round(sum(float(p.get("usd") or 0) for p in preds), 2)
