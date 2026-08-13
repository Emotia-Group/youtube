"""Cola de trabajos: TODAS las escrituras a YouTube pasan por aquí.

Por qué una cola y no llamadas directas: editar cuesta cuota de verdad (50
unidades por operación, de 10 000 diarias). Una edición en lote sobre 20
canales puede no caber en la cuota de hoy — la cola ejecuta lo que cabe,
deja el resto EN ESPERA con su motivo visible y lo retoma cuando la cuota
se reinicia (medianoche, hora del Pacífico). Además guarda una reserva
(`panel.quota_reserve`) para que las ediciones nunca dejen sin cuota al
sync nocturno de métricas.

Reglas de ejecución:
- El snippet se relee FRESCO justo antes de cada update: videos.update
  BORRA todo campo que no se reenvíe, así que se fusiona sobre lo que hay
  en YouTube en ese momento, no sobre la copia local.
- Errores 5xx o de red: reintento con backoff (hasta 3 intentos).
- Errores 4xx: definitivos, con el mensaje de Google legible en la cola.
- Autorización caída: el canal queda en «Reconectar» y el trabajo en error.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ytpanel import config, db, google_api, vault

# Costo estimado por tipo (video_update lee el snippet fresco: +1)
COSTOS = {
    "video_update": 51,
    "thumbnail_set": 50,
    "playlist_create": 50,
    "playlist_add": 50,
    "playlist_remove": 50,
    "playlist_move": 50,
}

ETIQUETAS = {
    "video_update": "Editar metadatos",
    "thumbnail_set": "Cambiar miniatura",
    "playlist_create": "Crear playlist",
    "playlist_add": "Añadir a playlist",
    "playlist_remove": "Quitar de playlist",
    "playlist_move": "Reordenar playlist",
}

MAX_INTENTOS = 3
NOTA_ESPERA = ("En espera: la cuota diaria no alcanza hoy. La cola se "
               "reanuda sola tras el reinicio de medianoche (hora del "
               "Pacífico).")


# ---------------------------------------------------------------------------
# Validación (los límites reales de YouTube, avisados ANTES de encolar)
# ---------------------------------------------------------------------------

def validar_cambios(cambios: dict) -> str | None:
    """None si todo bien; si no, el motivo en claro. Los límites son los de
    la API: pasarse no da un aviso amable, da un 400 tras gastar cuota."""
    if "title" in cambios:
        t = cambios["title"]
        if not t or not t.strip():
            return "El título no puede quedar vacío."
        if len(t) > 100:
            return f"El título tiene {len(t)} caracteres; YouTube admite 100."
        if "<" in t or ">" in t:
            return "YouTube no permite «<» ni «>» en el título."
    if "description" in cambios:
        d = cambios["description"]
        octetos = len(d.encode("utf-8"))
        if octetos > 5000:
            return (f"La descripción ocupa {octetos} bytes; YouTube admite "
                    "5 000 (los emojis y tildes cuentan más de uno).")
        if "<" in d or ">" in d:
            return "YouTube no permite «<» ni «>» en la descripción."
    if "tags" in cambios:
        tags = cambios["tags"]
        if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            return "Las etiquetas deben ser una lista de textos."
        total = sum(len(t) + 2 for t in tags)  # margen por comillas/comas
        if total > 480:
            return (f"Las etiquetas suman ~{total} caracteres; el límite del "
                    "campo es 500 en total, no por etiqueta.")
        if any("<" in t or ">" in t for t in tags):
            return "YouTube no permite «<» ni «>» en las etiquetas."
    return None


# ---------------------------------------------------------------------------
# Encolar
# ---------------------------------------------------------------------------

def encolar_edicion(conn, channel_id: str, video_id: str, cambios: dict,
                    imagen: tuple[bytes, str] | None = None) -> list[int]:
    """Crea 1 trabajo por la parte de texto y 1 por la miniatura (si viene).
    La imagen se guarda en disco, no en la base: las bases con blobs de 2 MB
    engordan y esto es una cola, no un archivo."""
    creados = []
    if cambios:
        error = validar_cambios(cambios)
        if error:
            raise ValueError(error)
        creados.append(db.enqueue_job(
            conn, channel_id, "video_update",
            {"video_id": video_id, "cambios": cambios},
            COSTOS["video_update"]))
    if imagen:
        contenido, mime = imagen
        carpeta = config.data_dir() / "cola_miniaturas"
        carpeta.mkdir(exist_ok=True)
        ext = "png" if "png" in mime else "jpg"
        ruta = carpeta / f"mini_{video_id}_{int(time.time() * 1000)}.{ext}"
        ruta.write_bytes(contenido)
        creados.append(db.enqueue_job(
            conn, channel_id, "thumbnail_set",
            {"video_id": video_id, "ruta": str(ruta), "mime": mime},
            COSTOS["thumbnail_set"]))
    return creados


OPERACIONES_LOTE = ("reemplazar", "anexar_descripcion", "agregar_etiquetas",
                    "agregar_a_playlist")


def encolar_lote(conn, channel_id: str, video_ids: list[str], operacion: str,
                 params: dict) -> dict:
    """El lote se materializa AQUÍ, desde la base local, no en el navegador:
    así lo que se encola es exactamente lo que la vista previa enseñó.
    Devuelve creados y omitidos (con su motivo) para que nada pase en
    silencio."""
    if operacion not in OPERACIONES_LOTE:
        raise ValueError(f"Operación de lote desconocida: {operacion}")
    creados, omitidos = [], []
    for vid in video_ids:
        video = db.get_video(conn, vid)
        if not video or video["channel_id"] != channel_id:
            omitidos.append({"video_id": vid, "motivo": "no es de este canal"})
            continue
        cambios: dict = {}
        if operacion == "reemplazar":
            campo = params.get("campo", "title")
            if campo not in ("title", "description"):
                raise ValueError("El reemplazo solo aplica a título o descripción.")
            buscar = params.get("buscar", "")
            if not buscar:
                raise ValueError("Indica el texto a buscar.")
            actual = video[campo]
            if buscar not in actual:
                omitidos.append({"video_id": vid,
                                 "motivo": f"no contiene «{buscar}»"})
                continue
            cambios[campo] = actual.replace(buscar, params.get("reemplazo", ""))
        elif operacion == "anexar_descripcion":
            texto = params.get("texto", "")
            if not texto:
                raise ValueError("Indica el texto a añadir.")
            if texto.strip() in video["description"]:
                omitidos.append({"video_id": vid, "motivo": "ya lo contiene"})
                continue
            cambios["description"] = (video["description"].rstrip()
                                      + "\n\n" + texto).strip()
        elif operacion == "agregar_etiquetas":
            nuevas = [t.strip() for t in params.get("tags", []) if t.strip()]
            if not nuevas:
                raise ValueError("Indica al menos una etiqueta.")
            faltan = [t for t in nuevas if t.lower()
                      not in {x.lower() for x in video["tags"]}]
            if not faltan:
                omitidos.append({"video_id": vid, "motivo": "ya las tiene"})
                continue
            cambios["tags"] = video["tags"] + faltan
        elif operacion == "agregar_a_playlist":
            pid = params.get("playlist_id", "")
            if not pid:
                raise ValueError("Elige una playlist.")
            creados.append(db.enqueue_job(
                conn, channel_id, "playlist_add",
                {"playlist_id": pid, "video_id": vid},
                COSTOS["playlist_add"]))
            continue
        error = validar_cambios(cambios)
        if error:
            omitidos.append({"video_id": vid, "motivo": error})
            continue
        creados.append(db.enqueue_job(
            conn, channel_id, "video_update",
            {"video_id": vid, "cambios": cambios}, COSTOS["video_update"]))
    return {"creados": creados, "omitidos": omitidos}


# ---------------------------------------------------------------------------
# Procesar
# ---------------------------------------------------------------------------

def _api_para(conn, channel_id: str, cache: dict, transport):
    if channel_id in cache:
        return cache[channel_id]
    blob = db.get_token_blob(conn, channel_id)
    if blob is None:
        cache[channel_id] = None
        return None
    token = vault.unseal(blob)
    secrets = google_api.load_client_secrets()

    def persist(tok: dict) -> None:
        db.save_token(conn, channel_id, vault.seal(tok))

    api = google_api.YouTubeAPI(secrets, token, transport=transport,
                                on_token_refresh=persist)
    cache[channel_id] = api
    return api


def _ejecutar(conn, api, job: dict) -> str:
    kind, p = job["kind"], job["payload"]
    if kind == "video_update":
        vid, cambios = p["video_id"], p["cambios"]
        fresh = api.videos_snippet(vid)
        snippet = {
            "title": cambios.get("title", fresh.get("title", "")),
            "description": cambios.get("description",
                                       fresh.get("description", "")),
            "tags": cambios.get("tags", fresh.get("tags") or []),
            # Sin categoryId el update entero es rechazado; y los idiomas,
            # si no se reenvían, se BORRAN. Se preserva todo lo que había.
            "categoryId": fresh.get("categoryId") or "22",
        }
        for campo in ("defaultLanguage", "defaultAudioLanguage"):
            if fresh.get(campo):
                snippet[campo] = fresh[campo]
        api.videos_update_snippet(vid, snippet)
        db.update_video_local(conn, vid, title=snippet["title"],
                              description=snippet["description"],
                              tags=snippet["tags"])
        editado = " + ".join(sorted(cambios)) or "nada"
        return f"{editado} de {vid}"
    if kind == "thumbnail_set":
        ruta = Path(p["ruta"])
        if not ruta.exists():
            raise google_api.ApiHttpError(
                410, "archivo_perdido",
                "La imagen encolada ya no está en disco; vuelve a subirla.")
        resp = api.thumbnails_set(p["video_id"], ruta.read_bytes(), p["mime"])
        thumbs = (resp.get("items") or [{}])[0]
        url = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        if url:
            db.update_video_local(conn, p["video_id"], thumbnail_url=url)
        ruta.unlink(missing_ok=True)  # ya vive en YouTube; aquí era equipaje
        return f"miniatura de {p['video_id']}"
    if kind == "playlist_create":
        resp = api.playlist_insert(p["titulo"], p.get("descripcion", ""),
                                   p.get("privacidad", "public"))
        sn = resp.get("snippet") or {}
        conn.execute(
            "INSERT OR REPLACE INTO playlists(playlist_id, channel_id, title, "
            " description, privacy, item_count, updated_at) VALUES(?,?,?,?,?,?,?)",
            (resp.get("id", ""), job["channel_id"], sn.get("title", p["titulo"]),
             sn.get("description", ""), (resp.get("status") or {})
             .get("privacyStatus", p.get("privacidad", "public")), 0,
             db.now_str()))
        conn.commit()
        return f"playlist «{p['titulo']}»"
    if kind == "playlist_add":
        api.playlist_item_insert(p["playlist_id"], p["video_id"])
        return f"{p['video_id']} → playlist"
    if kind == "playlist_remove":
        api.playlist_item_delete(p["item_id"])
        return "video quitado de la playlist"
    if kind == "playlist_move":
        api.playlist_item_update(p["item_id"], p["playlist_id"],
                                 p["video_id"], int(p["position"]))
        return f"posición {p['position']}"
    raise ValueError(f"Tipo de trabajo desconocido: {kind}")


def procesar_cola(conn, *, cfg: dict | None = None, transport=None,
                  log=None) -> dict:
    log = log or (lambda _m: None)
    cfg = cfg or config.load_panel_config()
    presupuesto = int(cfg["quota_budget"]) - int(cfg.get("quota_reserve", 500))
    apis: dict = {}
    resumen = {"hechos": 0, "errores": 0, "en_espera": 0, "unidades": 0}
    for job in db.due_jobs(conn):
        costo = COSTOS.get(job["kind"], 50)
        if db.quota_today(conn) + costo > presupuesto:
            db.update_job(conn, job["id"], nota=NOTA_ESPERA)
            resumen["en_espera"] += 1
            continue  # otro trabajo más barato podría caber aún
        etiqueta = ETIQUETAS.get(job["kind"], job["kind"])
        api = _api_para(conn, job["channel_id"], apis, transport)
        if api is None:
            db.update_job(conn, job["id"], status="error",
                          nota="El canal no tiene token: conéctalo de nuevo.")
            resumen["errores"] += 1
            continue
        db.update_job(conn, job["id"], status="en_curso", nota="")
        antes = api.quota_units
        try:
            detalle = _ejecutar(conn, api, job)
            gastado = api.quota_units - antes
            db.record_sync(conn, job["channel_id"], started_at=db.now_str(),
                           ok=True, detail=f"cola: {etiqueta} — {detalle}",
                           quota_units=gastado)
            db.update_job(conn, job["id"], status="hecho", nota=detalle)
            resumen["hechos"] += 1
            resumen["unidades"] += gastado
            log(f"  ✔ {etiqueta}: {detalle}")
        except google_api.ReauthNeeded as e:
            db.upsert_channel(conn, job["channel_id"], token_status="reauth")
            db.update_job(conn, job["id"], status="error", nota=str(e))
            resumen["errores"] += 1
            log(f"  ✖ {etiqueta}: {e}")
        except (google_api.ApiHttpError, OSError, ValueError) as e:
            transitorio = (isinstance(e, OSError)
                           or (isinstance(e, google_api.ApiHttpError)
                               and e.status >= 500))
            intentos = job["attempts"] + 1
            if transitorio and intentos < MAX_INTENTOS:
                luego = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(time.time() + 60 * intentos))
                db.update_job(conn, job["id"], status="pendiente",
                              attempts=intentos, not_before=luego,
                              nota=f"Reintento {intentos}/{MAX_INTENTOS}: {e}")
                resumen["en_espera"] += 1
            else:
                db.update_job(conn, job["id"], status="error",
                              attempts=intentos, nota=str(e))
                resumen["errores"] += 1
            # Lo ya gastado en el intento cuenta igual (Google también lo cuenta)
            gastado = api.quota_units - antes
            if gastado:
                db.record_sync(conn, job["channel_id"], started_at=db.now_str(),
                               ok=False, detail=f"cola: {etiqueta} — {e}",
                               quota_units=gastado)
            log(f"  ✖ {etiqueta}: {e}")
    return resumen
