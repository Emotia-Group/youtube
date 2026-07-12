"""Carga de configuración: config.yaml global + overrides por proyecto."""
import copy
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_config(project_dir: Path | None = None) -> dict:
    load_dotenv()
    cfg_path = ROOT / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    if project_dir:
        local = project_dir / "config.yaml"
        if local.exists():
            cfg = _deep_merge(cfg, yaml.safe_load(local.read_text(encoding="utf-8")) or {})

    # El preset de estilo puede fijar los fps del render (ej. 24 para cine)
    from ytstudio.catalog import get_style_preset
    preset = get_style_preset(cfg)
    if preset and preset.get("fps"):
        cfg.setdefault("video", {})["fps"] = preset["fps"]
    return cfg
