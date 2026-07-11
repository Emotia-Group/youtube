"""FASE 11 — Publicación (opcional): sube el video a YouTube con la Data API.
Requiere client_secrets.json (OAuth de Google Cloud) en la raíz del repo y
publish.enabled: true en config.yaml. Si está deshabilitada, solo deja el
paquete final listo en 09_final/."""
from __future__ import annotations

import json
from pathlib import Path

from ytstudio.config import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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
        token_path.write_text(creds.to_json())
    return creds


def run(project, cfg) -> None:
    meta = json.loads(project.path("final", "metadata.json").read_text())
    video = Path(project.get("final_video"))

    if not cfg.get("publish", {}).get("enabled", False):
        print("  publish.enabled=false — el video queda listo en:")
        print(f"    video:     {video}")
        print(f"    miniatura: {meta.get('thumbnail')}")
        print(f"    metadatos: {project.path('final', 'metadata.json')}")
        print(f"    subtítulos: {project.path('subtitles', 'subtitulos.srt')}")
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
        youtube.thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(thumb)).execute()
    project.set("youtube_id", video_id)
