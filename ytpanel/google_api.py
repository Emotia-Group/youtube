"""Cliente de las APIs de YouTube con la biblioteca estándar (urllib).

Por qué no google-api-python-client aquí: el panel necesita un flujo OAuth que
vuelva a SU PROPIO servidor web (botón «Conectar canal» → Google → callback),
tokens por canal con refresco silencioso, y baterías de prueba sin red — todo
eso son dos POST y unos GET con JSON. Menos dependencias, menos formas de
romperse. La fase publish de ytstudio conserva su cliente oficial para la
subida reanudable de archivos grandes, que ahí sí aporta.

El «transporte» es inyectable: las pruebas pasan una función falsa y ejercitan
OAuth, refresco y sync completos sin tocar internet.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ytpanel import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DATA_API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"

# Se piden desde el día uno los permisos que el panel completo va a usar:
# gestionar el canal (fase 2 editará títulos/miniaturas/playlists) y leer
# métricas + ingresos. Pedir solo lectura ahora obligaría a reconectar los 20
# canales cuando llegue la fase de edición.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]

# Costo en unidades de cuota de la Data API (las llamadas a Analytics no
# gastan de esta cuota: tienen la suya aparte, holgada para 20 canales).
UNITS_LIST = 1
UNITS_WRITE = 50   # update/insert/delete y subir miniatura cuestan 50 c/u


class ApiHttpError(RuntimeError):
    """Respuesta no-2xx de una API de Google, con el motivo ya extraído."""

    def __init__(self, status: int, reason: str, message: str):
        super().__init__(f"HTTP {status} ({reason}): {message}")
        self.status = status
        self.reason = reason
        self.message = message


class ReauthNeeded(RuntimeError):
    """El refresh token murió (revocado, caducado o app aún en Testing):
    toca reconectar el canal desde la interfaz."""


def default_transport(method: str, url: str, headers: dict,
                      body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:  # 4xx/5xx traen JSON con el motivo
        return e.code, e.read()


def _parse_error(status: int, body: bytes) -> ApiHttpError:
    reason, message = "", ""
    try:
        err = json.loads(body.decode("utf-8", "replace")).get("error") or {}
        if isinstance(err, dict):
            message = err.get("message", "")
            errors = err.get("errors") or []
            if errors and isinstance(errors[0], dict):
                reason = errors[0].get("reason", "")
        else:  # el endpoint de tokens responde {"error": "...", "error_description": "..."}
            reason = str(err)
    except (ValueError, AttributeError):
        message = body.decode("utf-8", "replace")[:200]
    return ApiHttpError(status, reason or "error", message or "sin detalle")


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def load_client_secrets() -> dict:
    """client_secrets.json de Google Cloud (el mismo de ytstudio). Acepta los
    dos formatos que genera la consola: «installed» (app de escritorio, la
    recomendada: permite redirigir a localhost sin registrar el puerto) y
    «web»."""
    path = config.client_secrets_path()
    if not path.exists():
        raise RuntimeError(
            "Falta client_secrets.json en la carpeta del programa. Créalo en "
            "Google Cloud (APIs y servicios → Credenciales → ID de cliente "
            "OAuth, tipo «App de escritorio») con YouTube Data API v3 y "
            "YouTube Analytics API habilitadas. Es el mismo archivo que usa "
            "la publicación de ytstudio.")
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("installed") or data.get("web") or {}
    client_id = block.get("client_id", "")
    client_secret = block.get("client_secret", "")
    if not client_id or not client_secret:
        raise RuntimeError("client_secrets.json no trae client_id/client_secret "
                           "(¿descargaste el JSON del cliente OAuth correcto?).")
    return {"client_id": client_id, "client_secret": client_secret}


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """URL de autorización. prompt=consent garantiza refresh_token en CADA
    conexión (sin él, la segunda autorización de una misma cuenta llega sin
    refresh y el canal moriría a la hora); select_account permite elegir la
    siguiente cuenta/canal de marca al conectar los 20."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _token_post(fields: dict, transport) -> dict:
    body = urllib.parse.urlencode(fields).encode("ascii")
    status, raw = (transport or default_transport)(
        "POST", TOKEN_URL,
        {"Content-Type": "application/x-www-form-urlencoded"}, body)
    if status != 200:
        if b"invalid_grant" in raw:
            raise ReauthNeeded(
                "Google rechazó el refresh token (invalid_grant): la "
                "autorización fue revocada o caducó. Reconecta el canal.")
        raise _parse_error(status, raw)
    return json.loads(raw.decode("utf-8"))


def exchange_code(secrets: dict, code: str, redirect_uri: str,
                  transport=None) -> dict:
    """Código del callback → token. Devuelve el dict que guarda la bóveda."""
    data = _token_post({
        "client_id": secrets["client_id"],
        "client_secret": secrets["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }, transport)
    if not data.get("refresh_token"):
        raise RuntimeError(
            "Google no envió refresh_token. Suele pasar al reautorizar sin "
            "prompt=consent; vuelve a intentar la conexión desde el panel.")
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
        "scope": data.get("scope", ""),
    }


def refresh(secrets: dict, token: dict, transport=None) -> dict:
    data = _token_post({
        "client_id": secrets["client_id"],
        "client_secret": secrets["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }, transport)
    return token | {
        "access_token": data["access_token"],
        "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
    }


# ---------------------------------------------------------------------------
# Llamadas a las APIs
# ---------------------------------------------------------------------------

class YouTubeAPI:
    """Cliente autenticado de UN canal: refresca su token solo, avisa al
    dueño para persistirlo (on_token_refresh) y cuenta la cuota que gasta."""

    def __init__(self, secrets: dict, token: dict, *, transport=None,
                 on_token_refresh=None):
        self.secrets = secrets
        self.token = dict(token)
        self.transport = transport or default_transport
        self.on_token_refresh = on_token_refresh
        self.quota_units = 0
        self._sleep = time.sleep  # inyectable en pruebas

    def _refresh_now(self) -> None:
        self.token = refresh(self.secrets, self.token, self.transport)
        if self.on_token_refresh:
            self.on_token_refresh(self.token)

    def _call(self, method: str, url: str, params: dict, units: int = 0,
              json_body: dict | None = None, raw_body: bytes | None = None,
              content_type: str | None = None) -> dict:
        self.quota_units += units
        if self.token.get("expires_at", 0) <= time.time():
            self._refresh_now()
        clean = {k: v for k, v in params.items() if v is not None}
        full = url + ("?" + urllib.parse.urlencode(clean) if clean else "")
        body = None
        extra: dict = {}
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            extra["Content-Type"] = "application/json; charset=utf-8"
        elif raw_body is not None:
            body = raw_body
            extra["Content-Type"] = content_type or "application/octet-stream"
        refreshed = False
        for attempt in range(3):
            status, raw = self.transport(
                method, full,
                {"Authorization": f"Bearer {self.token['access_token']}"}
                | extra, body)
            if 200 <= status < 300:
                return json.loads(raw.decode("utf-8")) if raw.strip() else {}
            if status == 401 and not refreshed:
                # El access token murió antes de expires_at (revocación de
                # sesión, reloj del equipo…): un refresh y otro intento.
                refreshed = True
                self._refresh_now()
                continue
            if 500 <= status < 600 and attempt < 2:
                self._sleep(1 + attempt)
                continue
            raise _parse_error(status, raw)
        raise _parse_error(status, raw)  # inalcanzable salvo bucle agotado

    def _get(self, url: str, params: dict, units: int = 0) -> dict:
        return self._call("GET", url, params, units)

    # --- Data API (gasta cuota) ---------------------------------------

    def channels_mine(self) -> dict:
        """El canal DUEÑO del token (por eso mine=true y no un id: cada token
        ya es la identidad de su canal, incluidos los canales de marca)."""
        return self._get(f"{DATA_API}/channels", {
            "part": "snippet,statistics,contentDetails", "mine": "true",
        }, units=UNITS_LIST)

    def playlist_items(self, playlist_id: str, max_results: int = 50) -> dict:
        return self._get(f"{DATA_API}/playlistItems", {
            "part": "contentDetails", "playlistId": playlist_id,
            "maxResults": min(50, max_results),
        }, units=UNITS_LIST)

    def videos_list(self, video_ids: list[str]) -> dict:
        return self._get(f"{DATA_API}/videos", {
            "part": "snippet,statistics,contentDetails,status",
            "id": ",".join(video_ids[:50]), "maxResults": 50,
        }, units=UNITS_LIST)

    def playlists_mine(self) -> dict:
        return self._get(f"{DATA_API}/playlists", {
            "part": "snippet,status,contentDetails", "mine": "true",
            "maxResults": 50,
        }, units=UNITS_LIST)

    # --- Data API: escritura (fase 2; 50 unidades cada operación) -------

    def videos_snippet(self, video_id: str) -> dict:
        """El snippet FRESCO de un video, justo antes de editarlo: si alguien
        cambió algo desde el último sync, se edita sobre lo real, no sobre la
        copia local (y videos.update BORRA todo campo que no se reenvíe)."""
        items = self._get(f"{DATA_API}/videos", {
            "part": "snippet", "id": video_id}, units=UNITS_LIST).get("items") or []
        if not items:
            raise ApiHttpError(404, "notFound",
                               f"El video {video_id} ya no existe en YouTube.")
        return items[0]["snippet"]

    def videos_update_snippet(self, video_id: str, snippet: dict) -> dict:
        return self._call("PUT", f"{DATA_API}/videos", {"part": "snippet"},
                          units=UNITS_WRITE,
                          json_body={"id": video_id, "snippet": snippet})

    def thumbnails_set(self, video_id: str, image: bytes, mime: str) -> dict:
        return self._call("POST", f"{UPLOAD_API}/thumbnails/set",
                          {"videoId": video_id}, units=UNITS_WRITE,
                          raw_body=image, content_type=mime)

    def playlist_insert(self, title: str, description: str = "",
                        privacy: str = "public") -> dict:
        return self._call("POST", f"{DATA_API}/playlists",
                          {"part": "snippet,status"}, units=UNITS_WRITE,
                          json_body={"snippet": {"title": title,
                                                 "description": description},
                                     "status": {"privacyStatus": privacy}})

    def playlist_item_insert(self, playlist_id: str, video_id: str) -> dict:
        return self._call("POST", f"{DATA_API}/playlistItems",
                          {"part": "snippet"}, units=UNITS_WRITE,
                          json_body={"snippet": {
                              "playlistId": playlist_id,
                              "resourceId": {"kind": "youtube#video",
                                             "videoId": video_id}}})

    def playlist_item_update(self, item_id: str, playlist_id: str,
                             video_id: str, position: int) -> dict:
        # La API exige reenviar playlistId y resourceId aunque solo cambie
        # la posición.
        return self._call("PUT", f"{DATA_API}/playlistItems",
                          {"part": "snippet"}, units=UNITS_WRITE,
                          json_body={"id": item_id, "snippet": {
                              "playlistId": playlist_id,
                              "position": position,
                              "resourceId": {"kind": "youtube#video",
                                             "videoId": video_id}}})

    def playlist_item_delete(self, item_id: str) -> dict:
        return self._call("DELETE", f"{DATA_API}/playlistItems",
                          {"id": item_id}, units=UNITS_WRITE)

    def playlist_items_full(self, playlist_id: str) -> dict:
        """Items con snippet (título y posición) para el editor de playlists."""
        return self._get(f"{DATA_API}/playlistItems", {
            "part": "snippet,contentDetails", "playlistId": playlist_id,
            "maxResults": 50,
        }, units=UNITS_LIST)

    # --- Analytics API (cuota aparte, no descuenta de las 10 000) ------

    def analytics_daily(self, start_date: str, end_date: str, metrics: str,
                        currency: str | None = None) -> dict:
        return self._get(ANALYTICS_API, {
            "ids": "channel==MINE", "dimensions": "day", "sort": "day",
            "startDate": start_date, "endDate": end_date,
            "metrics": metrics, "currency": currency,
        })
