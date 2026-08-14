"""Fábrica de proveedores. Cada categoría (llm, tts, stt, images, videogen,
music) se resuelve desde config.yaml a una implementación concreta.

Si falta la clave de API de un proveedor, se degrada automáticamente a su
versión mock (con aviso) para que el pipeline siga siendo ejecutable en modo
preview."""
from __future__ import annotations

import os

_warned: set[str] = set()


def _warn_mock(category: str, name: str, env_var: str) -> None:
    if category not in _warned:
        _warned.add(category)
        print(f"  ⚠ {category}: falta {env_var} para '{name}' — usando mock "
              f"(modo preview)")


def get_llm(cfg: dict):
    from ytstudio.providers import llm
    name = cfg["providers"]["llm"]["name"]
    if name == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            _warn_mock("llm", name, "ANTHROPIC_API_KEY")
            return llm.MockLLM(cfg)
        return llm.ClaudeLLM(cfg)
    if name == "mock":
        return llm.MockLLM(cfg)
    raise ValueError(f"Proveedor LLM desconocido: {name}")


_REQUIRED_KEYS = {
    "elevenlabs": "ELEVENLABS_API_KEY",
    "openai": "OPENAI_API_KEY",
    "replicate": "REPLICATE_API_TOKEN",
    "cartesia": "CARTESIA_API_KEY",
    "assemblyai": "ASSEMBLYAI_API_KEY",
}


def _resolve(category: str, name: str) -> str:
    """Devuelve 'mock' si el proveedor necesita una clave que no está definida."""
    env_var = _REQUIRED_KEYS.get(name)
    if env_var and not os.environ.get(env_var):
        _warn_mock(category, name, env_var)
        return "mock"
    return name


def get_tts(cfg: dict):
    from ytstudio.providers import tts
    name = _resolve("tts", cfg["providers"]["tts"]["name"])
    return {
        "elevenlabs": tts.ElevenLabsTTS,
        "cartesia": tts.CartesiaTTS,
        "openai": tts.OpenAITTS,
        "edge": tts.EdgeTTS,
        "mock": tts.MockTTS,
    }[name](cfg)


def get_stt(cfg: dict):
    from ytstudio.providers import stt
    name = _resolve("stt", cfg["providers"]["stt"]["name"])
    return {"openai": stt.OpenAISTT, "assemblyai": stt.AssemblyAISTT,
            "mock": stt.MockSTT}[name](cfg)


def _warn_retired(cfg: dict) -> None:
    """Aviso ANTES de generar si el config nombra un modelo que su proveedor
    ya retiró. Sin esto el fallo llega como un error críptico de la API a
    mitad de la fase de imágenes, con parte del proyecto ya pagado."""
    from ytstudio import pricing
    icfg = cfg.get("providers", {}).get("images", {}) or {}
    for key in ("model", "ref_model"):
        model = str(icfg.get(key, ""))
        info = pricing.retirement(model)
        if not info:
            continue
        fecha, relevo = info
        print(f"  ⚠ imágenes: «{model}» fue retirado por su proveedor el "
              f"{fecha}. Cambia providers.images.{key} a «{relevo}» en "
              "⚙ Configuración antes de generar.")


def get_images(cfg: dict):
    from ytstudio.providers import images
    _warn_retired(cfg)
    name = _resolve("images", cfg["providers"]["images"]["name"])
    return {
        "openai": images.OpenAIImages,
        "replicate": images.ReplicateImages,
        "mock": images.MockImages,
    }[name](cfg)


def get_videogen(cfg: dict):
    from ytstudio.providers import videogen
    name = cfg["providers"]["videogen"]["name"]
    if name == "none":
        return None
    env_var = _REQUIRED_KEYS.get(name)
    if env_var and not os.environ.get(env_var):
        _warn_mock("videogen", name, env_var)
        return None  # sin video IA → Ken Burns sobre la imagen de la escena
    return {"replicate": videogen.ReplicateVideo}[name](cfg)


def get_lipsync(cfg: dict):
    """Proveedor de personaje con lipsync, o None (sin clave / desactivado):
    sin él, las escenas de personaje degradan a su imagen fija con Ken Burns."""
    from ytstudio.providers import lipsync
    name = cfg.get("providers", {}).get("lipsync", {}).get("name", "replicate")
    if name in ("none", "", None):
        return None
    env_var = _REQUIRED_KEYS.get(name)
    if env_var and not os.environ.get(env_var):
        _warn_mock("lipsync", name, env_var)
        return None
    return {"replicate": lipsync.ReplicateLipsync}[name](cfg)


def get_music(cfg: dict):
    from ytstudio.providers import music
    name = _resolve("music", cfg["providers"]["music"]["name"])
    if name == "library":
        return music.LibraryMusic(cfg)
    return {
        "replicate": music.ReplicateMusic,
        "elevenlabs": music.ElevenLabsMusic,
        "mock": music.MockMusic,
    }[name](cfg)
