"""Configuración de la Torre de Control (ytpanel).

Convive con ytstudio en el mismo repositorio: lee el bloque `panel:` de
config.yaml (y de config.local.yaml, que manda), y guarda TODO lo suyo en
panel_data/ — base de datos y clave de cifrado. Esa carpeta vive fuera de Git
a propósito: contiene los tokens de acceso a tus canales.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "port": 8766,              # ytstudio usa 8765; el panel vive al lado
    "history_days": 90,        # histórico pedido en la PRIMERA sincronización
    "resync_overlap_days": 3,  # Analytics consolida tarde: se re-piden los últimos días
    "max_recent_videos": 50,   # últimos videos por canal en cada sync
    "quota_budget": 10000,     # cuota diaria de la Data API (para el medidor de la UI)
    "quota_reserve": 500,      # unidades que la cola de ediciones NUNCA toca,
                               # reservadas para el sync nocturno de métricas
    "currency": "USD",         # moneda de los ingresos estimados
    "alertas": {               # umbrales de los avisos automáticos
        "caida_vistas_pct": 25,      # % de caída (7 días vs. 7 anteriores)
        "subida_vistas_pct": 40,     # % de subida que merece celebrarse
        "caida_ingresos_pct": 25,
        "dias_sin_publicar": 21,
        "dias_sin_sincronizar": 3,
        "video_despunta_x": 2.0,     # veces la mediana del canal
        "minimo_vistas": 100,        # por debajo, los % son ruido
    },
}


def data_dir() -> Path:
    """Carpeta de datos del panel. La variable YTPANEL_DATA_DIR la reubica —
    las baterías de prueba la apuntan a un directorio temporal para no tocar
    (ni ver) tus canales reales."""
    base = os.environ.get("YTPANEL_DATA_DIR")
    path = Path(base) if base else ROOT / "panel_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "panel.db"


def key_path() -> Path:
    return data_dir() / "panel.key"


def client_secrets_path() -> Path:
    """El MISMO client_secrets.json que usa la fase publish de ytstudio: un
    solo proyecto de Google Cloud para todo el sistema (crear varios para
    multiplicar cuota va contra las políticas de la API). YTPANEL_CLIENT_SECRETS
    lo reubica en las pruebas."""
    override = os.environ.get("YTPANEL_CLIENT_SECRETS")
    return Path(override) if override else ROOT / "client_secrets.json"


def load_panel_config() -> dict:
    """DEFAULTS + bloque `panel:` de config.yaml y config.local.yaml (en ese
    orden; el local manda). El .env se carga igual que en ytstudio."""
    from ytstudio.config import load_dotenv
    load_dotenv()
    cfg = copy.deepcopy(DEFAULTS)
    for name in ("config.yaml", "config.local.yaml"):
        path = ROOT / name
        if not path.exists():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # un YAML roto no debe tumbar el panel; la UI ya avisa de config
        block = data.get("panel") or {}
        if isinstance(block, dict):
            for clave, valor in block.items():
                if valor is None:
                    continue
                # Los bloques anidados (alertas) se FUSIONAN, no se
                # reemplazan: cambiar un umbral no debe borrar los otros
                # seis y dejarlos en cero sin que nadie lo note.
                if isinstance(valor, dict) and isinstance(cfg.get(clave), dict):
                    cfg[clave] = cfg[clave] | valor
                else:
                    cfg[clave] = valor
    return cfg
