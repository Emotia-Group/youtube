"""Bóveda de tokens: los credenciales OAuth de cada canal, cifrados en reposo.

Cifra con Fernet (paquete `cryptography`) usando una clave local generada la
primera vez en panel_data/panel.key. Si el paquete no está instalado, el panel
SIGUE funcionando pero guarda los tokens sin cifrar (prefijo PLAIN1) y lo
avisa en la interfaz — mejor un aviso honesto que una falsa sensación de
seguridad. Instalarlo después re-cifra solo: al siguiente guardado del token.
"""
from __future__ import annotations

import json
import os

from ytpanel import config

_PREF_FERNET = b"FERN1:"
_PREF_PLAIN = b"PLAIN1:"


_PROBE: dict = {}


def available() -> bool:
    """¿Se puede cifrar DE VERDAD? No basta con que `import cryptography`
    funcione: hay instalaciones rotas (falta _cffi_backend, binarios de otra
    arquitectura…) donde el paquete importa pero Fernet revienta al usarse —
    incluso con excepciones que no heredan de Exception (panics de pyo3). Se
    prueba un cifrado real una vez y se recuerda el veredicto."""
    if "ok" not in _PROBE:
        try:
            from cryptography.fernet import Fernet
            f = Fernet(Fernet.generate_key())
            _PROBE["ok"] = f.decrypt(f.encrypt(b"sonda")) == b"sonda"
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:  # instalación rota: se degrada con aviso, no se cae
            _PROBE["ok"] = False
    return _PROBE["ok"]


def _fernet():
    from cryptography.fernet import Fernet
    path = config.key_path()
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        try:
            os.chmod(path, 0o600)  # solo el dueño; en Windows no aplica y no pasa nada
        except OSError:
            pass
    return Fernet(path.read_bytes().strip())


def seal(token: dict) -> bytes:
    """dict de token → blob para guardar en la base de datos."""
    raw = json.dumps(token, ensure_ascii=False).encode("utf-8")
    if available():
        return _PREF_FERNET + _fernet().encrypt(raw)
    return _PREF_PLAIN + raw


def unseal(blob: bytes) -> dict:
    """blob de la base de datos → dict de token. Acepta ambos formatos, así un
    token guardado sin `cryptography` sigue siendo legible tras instalarlo."""
    blob = bytes(blob)
    if blob.startswith(_PREF_FERNET):
        return json.loads(_fernet().decrypt(blob[len(_PREF_FERNET):]))
    if blob.startswith(_PREF_PLAIN):
        return json.loads(blob[len(_PREF_PLAIN):].decode("utf-8"))
    raise ValueError("Formato de token desconocido en la bóveda.")
