"""ESTUDIO DE SERIES ANIMADAS: la biblia de cada serie, compartida por todos
sus episodios.

Una serie guarda lo que debe mantenerse IDÉNTICO capítulo a capítulo: los
personajes (rasgos, vestimenta, personalidad, voz y fotos de referencia), las
locaciones (con sus imágenes de referencia), las escenas recurrentes, el
jingle, las canciones propias y las voces (elegidas del catálogo, subidas o
CLONADAS). Cada episodio es un proyecto normal del programa que, al crearse,
recibe una copia de esa biblia: el elenco con sus referencias, las locaciones,
el mapa de voces por personaje y el jingle — así el director trabaja siempre
con la misma cara, la misma ropa y la misma voz para cada personaje.

Todo vive en data/series/<id>/ (fuera de git, como projects/): material del
creador.

Estructura de serie.json:
  {"id": "sr_x", "name": "...", "description": "...",
   "audience": "ninos" | "adultos",
   "characters":  [{"id": "pj_x", "name", "description", "clothing",
                    "personality", "voice": {"provider", "voice_id"},
                    "images": ["personajes/pj_x/01_foto.jpg"],
                    "narrator": false}],
   "locations":   [{"id": "lc_x", "name", "description", "ambience",
                    "images": ["locaciones/lc_x/01_foto.jpg"]}],
   "scenes":      [{"id": "es_x", "name", "location", "characters": [],
                    "description"}],       # escenas recurrentes de la serie
   "jingle":      "musica/jingle.mp3" | null,
   "songs":       ["musica/cancion.mp3"],
   "voices":      [{"id": "vz_x", "name", "kind": "clonada" | "muestra",
                    "provider", "voice_id", "files": ["voces/vz_x/01.mp3"]}],
   "narrator_voice": {"provider", "voice_id"} | null,
   "episodes":    [{"slug", "number", "title"}]}
"""
from __future__ import annotations

import json
import re
import shutil
import time
import unicodedata
import uuid
from pathlib import Path

from ytstudio.config import ROOT

SERIES_DIR = ROOT / "data" / "series"

AUDIENCES = {"ninos": "niños", "adultos": "adultos"}

# Campos editables de cada entidad (el resto lo gestiona el programa)
SERIE_FIELDS = ("name", "description", "audience")
CHARACTER_FIELDS = ("name", "description", "clothing", "personality",
                    "narrator", "voice")
LOCATION_FIELDS = ("name", "description", "ambience")
SCENE_FIELDS = ("name", "location", "characters", "description")

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg", ".m4v"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".wma"}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def norm_name(text: str) -> str:
    """Minúsculas y sin acentos, para comparar nombres con tolerancia (las
    claves de voice_cast se guardan así)."""
    t = unicodedata.normalize("NFD", (text or "").strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


_norm = norm_name


def _safe_name(name: str) -> str:
    """Nombre de archivo sin rutas ni caracteres conflictivos."""
    base = Path(name or "archivo").name
    base = re.sub(r"[^\w.\- ]", "-", base, flags=re.UNICODE)
    return base[:80] or "archivo"


def serie_dir(serie_id: str) -> Path:
    return SERIES_DIR / serie_id


def _write(serie: dict) -> None:
    d = serie_dir(serie["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "serie.json").write_text(
        json.dumps(serie, ensure_ascii=False, indent=2), encoding="utf-8")


def list_series() -> list[dict]:
    if not SERIES_DIR.exists():
        return []
    from ytstudio.project import read_json_tolerant
    out = []
    for f in sorted(SERIES_DIR.glob("*/serie.json")):
        try:
            out.append(read_json_tolerant(f))
        except Exception:
            continue
    out.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return out


def load_serie(serie_id: str) -> dict | None:
    f = serie_dir(serie_id) / "serie.json"
    if not f.exists():
        return None
    from ytstudio.project import read_json_tolerant
    return read_json_tolerant(f)


def _require(serie_id: str) -> dict:
    serie = load_serie(serie_id)
    if serie is None:
        raise ValueError("Serie no encontrada.")
    return serie


def create_serie(fields: dict) -> dict:
    name = (fields.get("name") or "").strip()
    if not name:
        raise ValueError("La serie necesita un nombre.")
    if any(_norm(s.get("name")) == _norm(name) for s in list_series()):
        raise ValueError(f"Ya existe una serie llamada «{name}».")
    audience = fields.get("audience")
    serie = {
        "id": _new_id("sr"), "name": name,
        "description": (fields.get("description") or "").strip()[:600],
        "audience": audience if audience in AUDIENCES else "ninos",
        "created_at": _now(),
        "characters": [], "locations": [], "scenes": [],
        "jingle": None, "songs": [], "voices": [],
        "narrator_voice": None, "episodes": [],
    }
    _write(serie)
    return serie


def update_serie(serie_id: str, fields: dict) -> dict:
    serie = _require(serie_id)
    for key in SERIE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "name":
            if (value or "").strip():
                serie["name"] = value.strip()
        elif key == "audience":
            if value in AUDIENCES:
                serie["audience"] = value
        else:
            serie[key] = (value or "").strip()[:600]
    if "narrator_voice" in fields:
        serie["narrator_voice"] = _clean_voice(fields.get("narrator_voice"))
    _write(serie)
    return serie


def delete_serie(serie_id: str) -> None:
    shutil.rmtree(serie_dir(serie_id), ignore_errors=True)


def _clean_voice(voice) -> dict | None:
    """Normaliza la voz de un personaje/narrador: proveedor + identificador."""
    if not isinstance(voice, dict):
        return None
    provider = str(voice.get("provider") or "").strip().lower()
    voice_id = str(voice.get("voice_id") or "").strip()
    if not voice_id:
        return None
    return {"provider": provider or None, "voice_id": voice_id}


def _save_files(serie: dict, subdir: str, files: list[dict],
                kinds: set[str] | None = None) -> list[str]:
    """Guarda archivos subidos (base64) en data/series/<id>/<subdir>/ y
    devuelve sus rutas relativas. `kinds` restringe por extensión."""
    import base64
    d = serie_dir(serie["id"]) / subdir
    d.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    existing = len(list(d.glob("*")))
    for f in files or []:
        name = _safe_name(f.get("name") or "")
        ext = Path(name).suffix.lower()
        if kinds is not None and ext not in kinds:
            valid = ", ".join(sorted(e.lstrip(".") for e in kinds))
            raise ValueError(
                f"«{name}» no es un formato válido aquí (usa: {valid}).")
        existing += 1
        dest = d / f"{existing:02d}_{name}"
        dest.write_bytes(base64.b64decode(f.get("data_base64") or ""))
        saved.append(str(dest.relative_to(serie_dir(serie["id"]))).replace(
            "\\", "/"))
    return saved


def _frames_from_video(serie: dict, subdir: str, rel: str) -> list[str]:
    """Fotogramas de referencia a partir de un VIDEO subido (para «clonarme»:
    el aspecto sale de fotogramas reales). Sin ffmpeg devuelve lista vacía —
    el video queda guardado igual."""
    src = serie_dir(serie["id"]) / rel
    out_dir = serie_dir(serie["id"]) / subdir / f"{src.stem}_frames"
    try:
        from ytstudio.utils.media import extract_frames
        frames = extract_frames(src, out_dir, count=3)
        return [str(p.relative_to(serie_dir(serie["id"]))).replace("\\", "/")
                for p in frames]
    except Exception:
        return []


# --- Personajes -------------------------------------------------------------

def add_character(serie_id: str, fields: dict,
                  files: list[dict] | None = None) -> dict:
    serie = _require(serie_id)
    name = (fields.get("name") or "").strip()[:40]
    if not name:
        raise ValueError("Ponle un nombre al personaje.")
    if any(_norm(c["name"]) == _norm(name) for c in serie["characters"]):
        raise ValueError(f"Ya existe un personaje llamado «{name}».")
    ch = {
        "id": _new_id("pj"), "name": name,
        "description": (fields.get("description") or "").strip()[:400],
        "clothing": (fields.get("clothing") or "").strip()[:300],
        "personality": (fields.get("personality") or "").strip()[:300],
        "voice": _clean_voice(fields.get("voice")),
        "images": [], "narrator": bool(fields.get("narrator")),
    }
    if ch["narrator"]:
        for c in serie["characters"]:
            c["narrator"] = False
    serie["characters"].append(ch)
    _write(serie)
    if files:
        add_character_files(serie_id, ch["id"], files)
        serie = _require(serie_id)
        ch = next(c for c in serie["characters"] if c["id"] == ch["id"])
    return ch


def update_character(serie_id: str, char_id: str, fields: dict) -> dict:
    serie = _require(serie_id)
    ch = next((c for c in serie["characters"] if c["id"] == char_id), None)
    if ch is None:
        raise ValueError("Personaje no encontrado.")
    for key in CHARACTER_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "name":
            if (value or "").strip():
                ch["name"] = value.strip()[:40]
        elif key == "narrator":
            if value:
                for c in serie["characters"]:
                    c["narrator"] = c["id"] == char_id
            else:
                ch["narrator"] = False
        elif key == "voice":
            ch["voice"] = _clean_voice(value)
        else:
            ch[key] = (value or "").strip()[:400]
    _write(serie)
    return ch


def add_character_files(serie_id: str, char_id: str,
                        files: list[dict]) -> dict:
    """Fotos Y VIDEOS de referencia del personaje. De cada video se extraen
    fotogramas (si hay ffmpeg) que se usan como imágenes de identidad — la
    base de «clonarme»: un avatar con TU cara a partir de tu material."""
    serie = _require(serie_id)
    ch = next((c for c in serie["characters"] if c["id"] == char_id), None)
    if ch is None:
        raise ValueError("Personaje no encontrado.")
    subdir = f"personajes/{char_id}"
    saved = _save_files(serie, subdir, files, kinds=_IMAGE_EXT | _VIDEO_EXT)
    for rel in saved:
        if Path(rel).suffix.lower() in _VIDEO_EXT:
            ch["images"] += _frames_from_video(serie, subdir, rel)
        else:
            ch["images"].append(rel)
    _write(serie)
    return ch


def delete_character(serie_id: str, char_id: str) -> None:
    serie = _require(serie_id)
    if not any(c["id"] == char_id for c in serie["characters"]):
        raise ValueError("Personaje no encontrado.")
    serie["characters"] = [c for c in serie["characters"]
                           if c["id"] != char_id]
    shutil.rmtree(serie_dir(serie_id) / "personajes" / char_id,
                  ignore_errors=True)
    _write(serie)


def clone_avatar(serie_id: str, name: str, files: list[dict],
                 description: str = "") -> dict:
    """«CLONARME»: crea un personaje-avatar a partir de fotos y videos
    PROPIOS. Es un personaje normal del elenco (misma consistencia), marcado
    como narrador si la serie aún no tiene uno."""
    serie = _require(serie_id)
    if not files:
        raise ValueError("Sube al menos una foto o un video tuyo.")
    has_narrator = any(c.get("narrator") for c in serie["characters"])
    ch = add_character(serie_id, {
        "name": (name or "").strip() or "Yo",
        "description": (description or "").strip()
        or "avatar del creador, generado a partir de sus fotos y videos",
        "narrator": not has_narrator,
    }, files)
    return ch


# --- Locaciones -------------------------------------------------------------

def add_location(serie_id: str, fields: dict,
                 files: list[dict] | None = None) -> dict:
    serie = _require(serie_id)
    name = (fields.get("name") or "").strip()[:60]
    if not name:
        raise ValueError("Ponle un nombre a la locación.")
    if any(_norm(l["name"]) == _norm(name) for l in serie["locations"]):
        raise ValueError(f"Ya existe una locación llamada «{name}».")
    loc = {
        "id": _new_id("lc"), "name": name,
        "description": (fields.get("description") or "").strip()[:400],
        "ambience": (fields.get("ambience") or "").strip()[:200],
        "images": [],
    }
    serie["locations"].append(loc)
    _write(serie)
    if files:
        add_location_files(serie_id, loc["id"], files)
        serie = _require(serie_id)
        loc = next(l for l in serie["locations"] if l["id"] == loc["id"])
    return loc


def update_location(serie_id: str, loc_id: str, fields: dict) -> dict:
    serie = _require(serie_id)
    loc = next((l for l in serie["locations"] if l["id"] == loc_id), None)
    if loc is None:
        raise ValueError("Locación no encontrada.")
    for key in LOCATION_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "name":
            if (value or "").strip():
                loc["name"] = value.strip()[:60]
        else:
            loc[key] = (value or "").strip()[:400]
    _write(serie)
    return loc


def add_location_files(serie_id: str, loc_id: str, files: list[dict]) -> dict:
    serie = _require(serie_id)
    loc = next((l for l in serie["locations"] if l["id"] == loc_id), None)
    if loc is None:
        raise ValueError("Locación no encontrada.")
    saved = _save_files(serie, f"locaciones/{loc_id}", files,
                        kinds=_IMAGE_EXT)
    loc["images"] += saved
    _write(serie)
    return loc


def delete_location(serie_id: str, loc_id: str) -> None:
    serie = _require(serie_id)
    if not any(l["id"] == loc_id for l in serie["locations"]):
        raise ValueError("Locación no encontrada.")
    serie["locations"] = [l for l in serie["locations"] if l["id"] != loc_id]
    shutil.rmtree(serie_dir(serie_id) / "locaciones" / loc_id,
                  ignore_errors=True)
    _write(serie)


# --- Escenas recurrentes ----------------------------------------------------

def add_scene(serie_id: str, fields: dict) -> dict:
    """Escena RECURRENTE de la serie (ej. «la cocina de la abuela, con Lola y
    Tato desayunando»): el director la reutiliza tal cual cuando el guion
    pasa por ella — misma locación, mismos personajes, misma puesta."""
    serie = _require(serie_id)
    name = (fields.get("name") or "").strip()[:80]
    if not name:
        raise ValueError("Ponle un nombre a la escena.")
    sc = {
        "id": _new_id("es"), "name": name,
        "location": (fields.get("location") or "").strip()[:60],
        "characters": [str(c).strip()[:40]
                       for c in (fields.get("characters") or []) if str(c).strip()],
        "description": (fields.get("description") or "").strip()[:400],
    }
    serie["scenes"].append(sc)
    _write(serie)
    return sc


def update_scene(serie_id: str, scene_id: str, fields: dict) -> dict:
    serie = _require(serie_id)
    sc = next((s for s in serie["scenes"] if s["id"] == scene_id), None)
    if sc is None:
        raise ValueError("Escena no encontrada.")
    for key in SCENE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key == "name":
            if (value or "").strip():
                sc["name"] = value.strip()[:80]
        elif key == "characters":
            sc["characters"] = [str(c).strip()[:40]
                                for c in (value or []) if str(c).strip()]
        else:
            sc[key] = (value or "").strip()[:400]
    _write(serie)
    return sc


def delete_scene(serie_id: str, scene_id: str) -> None:
    serie = _require(serie_id)
    serie["scenes"] = [s for s in serie["scenes"] if s["id"] != scene_id]
    _write(serie)


# --- Música: jingle y canciones --------------------------------------------

def set_music(serie_id: str, kind: str, file: dict) -> dict:
    """Guarda el JINGLE de la serie (kind='jingle': uno, se reemplaza) o una
    CANCIÓN propia (kind='cancion': se acumulan)."""
    serie = _require(serie_id)
    if kind not in ("jingle", "cancion"):
        raise ValueError("kind debe ser 'jingle' o 'cancion'.")
    saved = _save_files(serie, "musica", [file], kinds=_AUDIO_EXT)
    if kind == "jingle":
        old = serie.get("jingle")
        if old:
            (serie_dir(serie_id) / old).unlink(missing_ok=True)
        serie["jingle"] = saved[0]
    else:
        serie["songs"].append(saved[0])
    _write(serie)
    return serie


def delete_music(serie_id: str, rel: str) -> dict:
    serie = _require(serie_id)
    rel = rel.replace("\\", "/")
    if serie.get("jingle") == rel:
        serie["jingle"] = None
    serie["songs"] = [s for s in serie["songs"] if s != rel]
    target = (serie_dir(serie_id) / rel).resolve()
    if str(target).startswith(str(serie_dir(serie_id).resolve())):
        target.unlink(missing_ok=True)
    _write(serie)
    return serie


# --- Voces: subir y CLONAR --------------------------------------------------

def add_voice(serie_id: str, name: str, files: list[dict],
              clone: bool = False) -> tuple[dict, str]:
    """Registra una voz de la serie a partir de archivos de AUDIO o VIDEO
    (de un video se extrae la pista de audio, si hay ffmpeg).

    clone=True intenta CLONARLA de verdad con ElevenLabs (voz instantánea a
    partir de las muestras): la voz resultante se puede asignar a cualquier
    personaje o al narrador y el TTS habla con ella. Sin clave de ElevenLabs
    la voz queda guardada como MUESTRA (sirve como referencia y para clonar
    más adelante), avisando con claridad. Devuelve (voz, aviso)."""
    serie = _require(serie_id)
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("Ponle un nombre a la voz.")
    if not files:
        raise ValueError("Sube al menos un archivo de audio (o video con voz).")
    vid = _new_id("vz")
    saved = _save_files(serie, f"voces/{vid}", files,
                        kinds=_AUDIO_EXT | _VIDEO_EXT)
    # De los videos se extrae la pista de audio (muestras del clon)
    samples: list[Path] = []
    for rel in saved:
        p = serie_dir(serie_id) / rel
        if p.suffix.lower() in _VIDEO_EXT:
            try:
                from ytstudio.utils.media import extract_audio
                samples.append(extract_audio(
                    p, p.with_name(p.stem + "_audio.mp3")))
            except Exception:
                continue
        else:
            samples.append(p)
    voice = {"id": vid, "name": name, "kind": "muestra",
             "provider": None, "voice_id": None, "files": saved}
    hint = ""
    if clone:
        try:
            voice_id = _clone_with_elevenlabs(name, samples)
            voice.update({"kind": "clonada", "provider": "elevenlabs",
                          "voice_id": voice_id})
            hint = (f"Voz «{name}» clonada en ElevenLabs: asígnala a un "
                    "personaje o al narrador y el programa hablará con ella.")
        except Exception as e:
            hint = (f"No se pudo clonar la voz todavía ({e}). Quedó guardada "
                    "como muestra: revisa tu clave de ElevenLabs en "
                    "⚙ Configuración y vuelve a intentarlo.")
    serie["voices"].append(voice)
    _write(serie)
    return voice, hint


def _clone_with_elevenlabs(name: str, samples: list[Path]) -> str:
    """Clona una voz con ElevenLabs (Instant Voice Cloning) y devuelve su
    voice_id. Requiere ELEVENLABS_API_KEY."""
    import os
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("falta la clave de ElevenLabs")
    if not samples:
        raise RuntimeError("no hay muestras de audio utilizables")
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=key)
    handles = [open(p, "rb") for p in samples[:5]]
    try:
        # El SDK cambió de sitio la clonación entre versiones: 2.x la sirve en
        # voices.ivc.create y 1.x en voices.add — se intentan ambas.
        if hasattr(client.voices, "ivc"):
            created = client.voices.ivc.create(name=name[:60], files=handles)
        else:
            created = client.voices.add(name=name[:60], files=handles)
    finally:
        for h in handles:
            h.close()
    voice_id = getattr(created, "voice_id", None)
    if not voice_id:
        raise RuntimeError("ElevenLabs no devolvió el identificador de la voz")
    from ytstudio import usage
    usage.record("elevenlabs", f"clonación de voz «{name}»", 1, "voz", 0.0)
    return voice_id


def delete_voice(serie_id: str, voice_id: str) -> None:
    serie = _require(serie_id)
    if not any(v["id"] == voice_id for v in serie["voices"]):
        raise ValueError("Voz no encontrada.")
    serie["voices"] = [v for v in serie["voices"] if v["id"] != voice_id]
    shutil.rmtree(serie_dir(serie_id) / "voces" / voice_id,
                  ignore_errors=True)
    _write(serie)


def resolve_voice(serie: dict, voice) -> dict | None:
    """Voz utilizable para TTS: acepta {'provider','voice_id'} directos o
    {'voice_id': 'vz_...'} que refiere una voz clonada de la serie."""
    voice = voice or {}
    vid = str(voice.get("voice_id") or "").strip()
    if not vid:
        return None
    if vid.startswith("vz_"):
        v = next((v for v in serie.get("voices", []) if v["id"] == vid), None)
        if v and v.get("voice_id"):
            return {"provider": v.get("provider"), "voice_id": v["voice_id"]}
        return None
    return {"provider": voice.get("provider"), "voice_id": vid}


# --- El puente con los episodios (proyectos) --------------------------------

def materialize_episode(project, serie: dict, number: int | None = None,
                        title: str = "") -> None:
    """Copia la biblia de la serie DENTRO del episodio recién creado: elenco
    con sus fotos, locaciones con sus referencias, mapa de voces por
    personaje, voz del narrador y jingle. A partir de aquí el episodio es un
    proyecto normal — pero el director trabaja con las mismas caras, las
    mismas locaciones y las mismas voces que el resto de la serie."""
    import yaml
    from ytstudio.phases.ingest import add_asset

    project.set("serie_id", serie["id"])
    project.set("serie_name", serie.get("name"))
    project.set("serie_audience", serie.get("audience") or "ninos")
    if number:
        project.set("episode_number", int(number))
    if title:
        project.set("episode_title", str(title)[:120])

    # 1) ELENCO: cada personaje de la serie entra al proyecto con sus fotos
    #    (assets de categoría 'personaje') y su descripción completa — rasgos
    #    + vestimenta: la ropa es parte de la identidad visual del personaje.
    chars: list[dict] = []
    for i, ch in enumerate(serie.get("characters", []), start=1):
        asset_ids = []
        for rel in ch.get("images", []):
            src = serie_dir(serie["id"]) / rel
            if not src.exists():
                continue
            try:
                a = add_asset(project, Path(src.name), "personaje",
                              data=src.read_bytes())
                asset_ids.append(a["id"])
            except ValueError:
                continue
        desc = "; ".join(x for x in (
            ch.get("description"),
            f"vestimenta: {ch['clothing']}" if ch.get("clothing") else "",
            ch.get("personality")) if x)
        chars.append({"id": f"ch{i}", "name": ch["name"],
                      "description": desc[:400], "asset_ids": asset_ids,
                      "narrator": bool(ch.get("narrator")),
                      "serie_char_id": ch["id"]})
    if chars and not any(c["narrator"] for c in chars):
        chars[0]["narrator"] = True
    if chars:
        project.set("characters", chars)
        # Presencia amplia por defecto: en una serie animada los personajes
        # SON el video (no un narrador ocasional de documental).
        if not project.get("character"):
            project.set("character", {"presence": 0.5})

    # 2) LOCACIONES: referencias copiadas a 06_broll/locations/ — la misma
    #    mecánica de identidad que el elenco, aplicada a los lugares.
    locs: list[dict] = []
    loc_dir = project.path("broll") / "locations"
    for l in serie.get("locations", []):
        refs = []
        loc_dir.mkdir(parents=True, exist_ok=True)
        for k, rel in enumerate(l.get("images", []), start=1):
            src = serie_dir(serie["id"]) / rel
            if not src.exists():
                continue
            dest = loc_dir / f"{l['id']}_{k:02d}{src.suffix.lower()}"
            shutil.copyfile(src, dest)
            refs.append(f"locations/{dest.name}")
        locs.append({"id": l["id"], "name": l["name"],
                     "description": l.get("description", ""),
                     "ambience": l.get("ambience", ""), "ref_files": refs})
    if locs:
        project.set("locations", locs)

    # 3) ESCENAS RECURRENTES: guía directa para el director.
    if serie.get("scenes"):
        project.set("serie_scenes", serie["scenes"])

    # 4) VOCES POR PERSONAJE: mapa nombre → voz (para que cada personaje
    #    hable con LA SUYA, sin confundirse de identidad entre escenas).
    voice_cast: dict[str, dict] = {}
    for ch in serie.get("characters", []):
        v = resolve_voice(serie, ch.get("voice"))
        if v:
            voice_cast[_norm(ch["name"])] = {**v, "name": ch["name"]}
    if voice_cast:
        project.set("voice_cast", voice_cast)

    # 5) VOZ DEL NARRADOR: entra como la voz TTS del proyecto (override en su
    #    config.yaml — se mezcla sobre la global al generar).
    narrator_v = resolve_voice(serie, serie.get("narrator_voice"))
    if narrator_v and narrator_v.get("voice_id"):
        cfg_path = project.dir / "config.yaml"
        try:
            current = yaml.safe_load(
                cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            current = {}
        tts = current.setdefault("providers", {}).setdefault("tts", {})
        tts["voice"] = narrator_v["voice_id"]
        if narrator_v.get("provider"):
            tts["name"] = narrator_v["provider"]
        cfg_path.write_text(yaml.safe_dump(current, allow_unicode=True),
                            encoding="utf-8")

    # 6) JINGLE y CANCIONES: el jingle abre cada episodio; las canciones
    #    entran a la selección musical del supervisor.
    if serie.get("jingle"):
        src = serie_dir(serie["id"]) / serie["jingle"]
        if src.exists():
            dest = project.path("music") / f"jingle_serie{src.suffix.lower()}"
            shutil.copyfile(src, dest)
            project.set("serie_jingle", dest.name)
    songs = []
    for rel in serie.get("songs", []):
        src = serie_dir(serie["id"]) / rel
        if src.exists():
            dest = project.path("music") / f"serie_{_safe_name(src.name)}"
            shutil.copyfile(src, dest)
            songs.append(dest.name)
    if songs:
        project.set("serie_songs", songs)

    # 7) Registrar el episodio en la serie
    serie.setdefault("episodes", [])
    if not any(e.get("slug") == project.slug for e in serie["episodes"]):
        serie["episodes"].append({
            "slug": project.slug,
            "number": int(number) if number else len(serie["episodes"]) + 1,
            "title": (title or project.state.get("display_name")
                      or project.slug)[:120]})
        _write(serie)


def series_tracks(project) -> list[dict]:
    """Canciones propias de la serie como pistas elegibles por el supervisor
    musical (mismo formato que la biblioteca local)."""
    out = []
    for name in project.get("serie_songs") or []:
        p = project.path("music") / name
        if p.exists():
            title = re.sub(r"^serie_", "", p.stem).replace("_", " ")
            out.append({"file": p.name, "path": p,
                        "title": f"{title} (canción de la serie)",
                        "artist": "", "seconds": 0})
    return out


# --- Bloques de instrucciones para el guionista y el director ---------------

def _bible_lines(project) -> list[str]:
    chars = project.get("characters") or []
    locs = project.get("locations") or []
    lines: list[str] = []
    if chars:
        lines.append("PERSONAJES DE LA SERIE (identidad FIJA, episodio a "
                     "episodio):")
        for c in chars:
            lines.append(f"- {c['name']}: {c.get('description') or ''}"
                         + (" [narrador]" if c.get("narrator") else ""))
    if locs:
        lines.append("LOCACIONES DE LA SERIE (aspecto FIJO — cada una tiene "
                     "imágenes de referencia):")
        for l in locs:
            amb = f" · ambiente: {l['ambience']}" if l.get("ambience") else ""
            lines.append(f"- {l['name']}: {l.get('description') or ''}{amb}")
    for sc in project.get("serie_scenes") or []:
        who = ", ".join(sc.get("characters") or [])
        lines.append(f"- ESCENA RECURRENTE «{sc['name']}» (en "
                     f"{sc.get('location') or 'cualquier locación'}"
                     + (f", con {who}" if who else "") + "): "
                     + (sc.get("description") or ""))
    return lines


def series_script_block(project) -> str:
    """Instrucciones del GUIONISTA para un episodio de serie animada: elenco
    y locaciones obligatorios, diálogo etiquetado y tono según la audiencia.
    Vacío si el proyecto no pertenece a una serie."""
    if not project.get("serie_id"):
        return ""
    audience = project.get("serie_audience") or "ninos"
    tone = ("para NIÑOS: lenguaje sencillo y cálido, frases cortas, humor "
            "blanco, cero violencia y una moraleja clara"
            if audience == "ninos" else
            "para ADULTOS: humor y conflicto más maduros, sin perder el tono "
            "de la serie")
    lines = [
        f"EPISODIO DE SERIE ANIMADA «{project.get('serie_name') or ''}» "
        f"({tone}).",
        "- Escribe el episodio como DIÁLOGO: cada línea hablada por un "
        "personaje empieza con su nombre y dos puntos (ej. «Lola: ¡Vamos!»). "
        "Las partes del narrador van con «Narrador: ». USA SOLO los "
        "personajes del elenco (no inventes otros con nombre propio).",
        "- La historia transcurre en las locaciones de la serie: menciónalas "
        "POR SU NOMBRE cuando la acción pase por ellas.",
    ]
    ep = project.get("episode_number")
    ti = project.get("episode_title")
    if ep or ti:
        lines.append(f"- Este es el episodio {ep or '?'}"
                     + (f": «{ti}»" if ti else "") + ".")
    lines += _bible_lines(project)
    return "\n".join(lines)


def series_scene_block(project) -> str:
    """Instrucciones del DIRECTOR (storyboard) para un episodio de serie:
    respeto absoluto a la identidad de personajes y locaciones, y quién
    habla en cada escena. Vacío si el proyecto no pertenece a una serie."""
    if not project.get("serie_id"):
        return ""
    lines = [
        "ESTE VIDEO ES UN EPISODIO DE SERIE ANIMADA: la coherencia manda.",
        "- 'speaker': el personaje que HABLA la narración de esa escena "
        "(o 'Narrador'). Cada escena la habla UNA sola voz: si el guion "
        "cambia de hablante, corta ahí la escena.",
        "- En 'narration' conserva el texto del guion SIN la etiqueta "
        "«Nombre: » (la etiqueta dice quién habla; no se lee en voz alta).",
        "- 'location': la locación de la serie donde ocurre la escena "
        "('ninguna' solo si de verdad no aplica). NO reinventes su aspecto "
        "en el broll_prompt: nómbrala y describe la ACCIÓN; su aspecto lo "
        "ponen las imágenes de referencia.",
        "- Con los personajes igual: descríbelos por nombre, rol y acción — "
        "la cara, la ropa y el estilo salen de sus referencias.",
    ]
    lines += _bible_lines(project)
    return "\n".join(lines)


# --- El DIRECTOR DE LA SERIE: análisis de material --------------------------

def director_report(serie: dict, script_text: str) -> dict:
    """Analiza un guion contra el material de la serie y dice, entidad por
    entidad, QUÉ SE REUTILIZA y QUÉ SE GENERARÁ — la coherencia se garantiza
    reutilizando las referencias existentes; lo que falte se genera UNA vez
    y queda fijado para los episodios siguientes.

    Determinista (sin costo de IA): compara nombres sin acentos."""
    text = _norm(script_text or "")
    rep: dict = {"characters": [], "locations": [], "scenes": [],
                 "music": {}, "voices": {}, "actions": []}

    for ch in serie.get("characters", []):
        appears = _norm(ch["name"]) in text
        has_img = bool(ch.get("images"))
        voice = resolve_voice(serie, ch.get("voice"))
        rep["characters"].append({
            "name": ch["name"], "appears": appears,
            "images": len(ch.get("images") or []),
            "plan": ("reutilizar sus referencias" if has_img else
                     "generar su retrato UNA vez y fijarlo"),
            "voice": ("propia" if voice else "falta asignar"),
        })
        if appears and not has_img:
            rep["actions"].append(
                f"«{ch['name']}» aparece en el guion sin fotos: se generará "
                "su retrato una única vez (o súbele fotos para fijar tú su "
                "aspecto).")
        if appears and not voice:
            rep["actions"].append(
                f"«{ch['name']}» no tiene voz asignada: hablará con la voz "
                "del narrador. Asígnale una en la ficha del personaje.")

    for l in serie.get("locations", []):
        appears = _norm(l["name"]) in text
        has_img = bool(l.get("images"))
        rep["locations"].append({
            "name": l["name"], "appears": appears,
            "images": len(l.get("images") or []),
            "plan": ("reutilizar sus referencias" if has_img else
                     "generar su referencia UNA vez y fijarla"),
        })
        if appears and not has_img:
            rep["actions"].append(
                f"La locación «{l['name']}» no tiene imágenes: se generará "
                "una referencia y se reutilizará en toda la serie.")

    for sc in serie.get("scenes", []):
        hits = [w for w in (_norm(sc.get("name")),) if w and w in text]
        rep["scenes"].append({"name": sc["name"], "appears": bool(hits)})

    rep["music"] = {
        "jingle": bool(serie.get("jingle")),
        "songs": len(serie.get("songs") or []),
    }
    if not serie.get("jingle"):
        rep["actions"].append(
            "La serie no tiene jingle: súbelo en 🎵 Música para que abra "
            "todos los episodios.")
    cloned = [v for v in serie.get("voices", []) if v.get("kind") == "clonada"]
    rep["voices"] = {"total": len(serie.get("voices") or []),
                     "cloned": len(cloned)}
    mentioned = [c["name"] for c in rep["characters"] if c["appears"]]
    rep["summary"] = (
        f"En el guion aparecen {len(mentioned)} personaje(s) de la serie"
        + (f" ({', '.join(mentioned[:6])})" if mentioned else "")
        + f" y {sum(1 for l in rep['locations'] if l['appears'])} "
          "locación(es). Lo que ya tiene referencia se REUTILIZA tal cual; "
          "lo que falte se genera una única vez y queda fijado para toda la "
          "serie.")
    return rep
