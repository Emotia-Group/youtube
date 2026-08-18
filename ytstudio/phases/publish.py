"""FASE 11 — Publicación (opcional): sube el video a YouTube con la Data API.
Requiere client_secrets.json (OAuth de Google Cloud) en la raíz del repo y
publish.enabled: true en config.yaml. Si está deshabilitada, solo deja el
paquete final listo en 09_final/ — y, en los verticales, imprime la LISTA DE
COMPROBACIÓN de publicación para que nada se suba a medias."""
from __future__ import annotations

import json
from pathlib import Path

from ytstudio.config import ROOT

# youtube.upload = subir el video y su miniatura.
# youtube.force-ssl = subir el archivo de subtítulos (captions). Se añadió en
# la v0.65.0: un token.json anterior no lo trae — la subida del video sigue
# funcionando igual, y si los subtítulos fallan por permisos se avisa cómo
# renovar la autorización (borrar token.json y volver a publicar).
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = ROOT / "token.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets = ROOT / "client_secrets.json"
            if not secrets.exists():
                raise RuntimeError(
                    "Falta client_secrets.json (OAuth de Google Cloud) en la raíz.")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _print_checklist(project, cfg) -> list[dict]:
    """Imprime la lista de comprobación del vertical y la deja guardada para
    la interfaz. Devuelve los puntos."""
    from ytstudio import shorts
    if not shorts.is_shorts_frame(cfg):
        return []
    items = shorts.publish_checklist(project, cfg)
    project.set("publish_checklist", items)
    print("  Lista de comprobación del Short:")
    for it in items:
        icono = {True: "✔", False: "✖", None: "☐"}[it["ok"]]
        print(f"    {icono} {it['label']}")
        if it["ok"] is False and it.get("detail"):
            print(f"        {it['detail']}")
    pendientes = [it for it in items if it["ok"] is False]
    if pendientes:
        project.add_warning(
            "La lista de comprobación del Short tiene "
            f"{len(pendientes)} punto(s) en rojo (pestaña Video/Corrida). "
            "Conviene resolverlos antes de subirlo.")
    return items


def _prepare_short_body(project, meta: dict) -> None:
    """Últimos retoques de metadatos de un Short justo antes de subir: sin el
    hashtag de Shorts y con el enlace al video largo en la descripción. Es la
    misma red de seguridad de la fase de metadatos, aplicada al resultado
    ELEGIDO (por si el creador editó a mano)."""
    from ytstudio.shorts import short_metadata_fixups
    derived = project.get("derived_from") or {}
    short_metadata_fixups(meta, derived.get("url") or "")


def _upload_captions(youtube, video_id: str, srt: Path, lang: str) -> None:
    """Sube el SRT como pista de subtítulos. El framework lo pide aparte de
    los quemados: cuesta cero, da accesibilidad y texto indexable."""
    from googleapiclient.http import MediaFileUpload
    youtube.captions().insert(
        part="snippet",
        body={"snippet": {"videoId": video_id, "language": lang,
                          "name": "", "isDraft": False}},
        media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream"),
    ).execute()


def run(project, cfg) -> None:
    from ytstudio import shorts
    from ytstudio.project import read_json_tolerant
    meta = read_json_tolerant(project.path("final", "metadata.json"))
    video = Path(project.get("final_video"))
    vertical = shorts.is_shorts_frame(cfg)
    derived = project.get("derived_from") or {}

    if vertical:
        _prepare_short_body(project, meta)

    _print_checklist(project, cfg)

    if not cfg.get("publish", {}).get("enabled", False):
        print("  publish.enabled=false — el video queda listo en:")
        print(f"    video:     {video}")
        print(f"    miniatura: {meta.get('thumbnail')}")
        print(f"    metadatos: {project.path('final', 'metadata.json')}")
        print(f"    subtítulos: {project.path('subtitles', 'subtitulos.srt')}")
        if vertical and derived.get("url"):
            print(f"  Al subirlo: Studio → el Short → Video relacionado → "
                  f"{derived['url']}")
        return

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    youtube = build("youtube", "v3", credentials=_credentials())
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description"][:5000],
            "tags": meta["tags"][:30],
            "categoryId": cfg["publish"].get("category_id", "27"),
            "defaultLanguage": cfg.get("language", "es"),
        },
        "status": {
            "privacyStatus": cfg["publish"].get("privacy", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024,
                                   resumable=True),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  subiendo… {int(status.progress() * 100)}%")
    video_id = response["id"]
    print(f"  video subido: https://youtu.be/{video_id}")

    thumb = meta.get("thumbnail")
    if thumb and Path(thumb).exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(thumb)).execute()
        except Exception as e:
            # En Shorts, las miniaturas personalizadas se despliegan
            # gradualmente por canal: si este canal aún no la tiene, el video
            # ya está subido y esto NO debe tirar la fase.
            project.add_warning(
                "La miniatura no se pudo poner desde aquí "
                f"({e}). Si es un Short, puede que tu canal todavía no tenga "
                "la función de miniaturas de Shorts: elige el fotograma en "
                "Studio y sube la miniatura cuando te aparezca la opción.")
    project.set("youtube_id", video_id)

    # SRT aparte: accesibilidad + texto indexable para búsqueda
    srt = project.path("subtitles", "subtitulos.srt")
    if srt.exists():
        try:
            _upload_captions(youtube, video_id, srt, cfg.get("language", "es"))
            print("  subtítulos (SRT) subidos como pista aparte")
        except Exception as e:
            project.add_warning(
                "El video se subió bien, pero los subtítulos (SRT) no se "
                f"pudieron subir como pista aparte ({e}). Suele ser un "
                "permiso que falta en una autorización antigua: borra "
                "token.json de la carpeta del programa y vuelve a publicar "
                "(pedirá autorizar de nuevo), o sube el archivo "
                "08_subtitles/subtitulos.srt a mano en Studio → Subtítulos.")

    # EL PASO QUE NO SE PUEDE AUTOMATIZAR: el enlace a video relacionado no
    # existe en la API — solo se pone a mano en Studio. Sin él, la vista del
    # Short se regala. Se recuerda aquí, donde ya se sabe la URL de destino.
    if vertical and derived.get("url"):
        aviso = (f"Short subido: https://youtu.be/{video_id} — falta UN paso "
                 "a mano: Studio → Contenido → este Short → Video "
                 f"relacionado → {derived['url']}. Es el único mecanismo que "
                 "convierte una vista del Short en un clic al video largo, y "
                 "no se puede poner desde fuera de Studio.")
        print(f"  ⚠ {aviso}")
        project.add_warning(aviso)
