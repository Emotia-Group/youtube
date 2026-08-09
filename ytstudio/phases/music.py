"""FASE 7 — Musicalización: obtiene la pista de fondo con la duración total
del video.

Con biblioteca local, la pista NO se elige al azar: la IA compara los títulos
y metadatos de las pistas con el concepto del video (mood, género, tema) y
elige la que mejor acompaña. Si ninguna encaja de verdad y hay Replicate
configurado, se GENERA una pista a medida (MusicGen); si no, se usa la más
cercana avisando. La música es opcional: ante cualquier fallo se degrada a un
pad ambiental en vez de detener el proyecto."""
from __future__ import annotations

import os

from ytstudio.providers import get_llm, get_music
from ytstudio.providers.music import LibraryMusic, MockMusic, ReplicateMusic


def _pick_track(llm, tracks: list[dict], concept: dict, topic: str,
                lang: str) -> tuple[str, bool, str]:
    """Devuelve (archivo elegido, encaja_de_verdad, motivo)."""
    md = concept.get("music_direction") or {}
    listing = "\n".join(
        f"- {t['file']}"
        + (f" · título: \"{t['title']}\"" if t.get("title") else "")
        + (f" · artista: {t['artist']}" if t.get("artist") else "")
        + (f" · {t['seconds']}s" if t.get("seconds") else "")
        for t in tracks)
    schema = {
        "type": "object",
        "properties": {
            "file": {"type": "string",
                     "enum": [t["file"] for t in tracks]},
            "fits": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["file", "fits", "reason"],
        "additionalProperties": False,
    }
    result = llm.complete_json(
        f"Eres supervisor musical de documentales y videos de YouTube en {lang}. "
        "Eliges la música de fondo que mejor sirve a la historia.",
        f"TEMA DEL VIDEO: {topic}\n"
        f"DIRECCIÓN MUSICAL DEL CONCEPTO: {md}\n\n"
        f"PISTAS DISPONIBLES EN LA BIBLIOTECA:\n{listing}\n\n"
        "Elige la pista que mejor acompaña el tono y el tema (file = la mejor "
        "opción SIEMPRE, aunque no sea perfecta). fits = true solo si esa "
        "pista realmente funciona para este video; false si ninguna encaja y "
        "sería mejor generar música a medida. reason: una frase.",
        schema=schema, purpose="music_pick")
    return result["file"], bool(result["fits"]), result.get("reason", "")


def _band(x: float) -> str:
    return "calma" if x < 0.45 else ("media" if x <= 0.7 else "alta")


def _acts_from_scenes(scenes: list[dict], min_len: float = 60.0,
                      max_acts: int = 6) -> list[dict]:
    """Divide el video en ACTOS musicales contiguos según el arco de
    music_intensity que dibujó el director: tramos de calma, desarrollo y
    clímax. Los actos muy cortos se funden con el vecino (una pista por
    menos de un minuto no se percibe como acto, solo como salto)."""
    acts: list[dict] = []
    for s in scenes:
        d = float(s.get("duration") or 0)
        b = _band(float(s.get("music_intensity", 0.55)))
        if acts and acts[-1]["band"] == b:
            acts[-1]["dur"] += d
            acts[-1]["scenes"].append(s)
        else:
            acts.append({"band": b, "dur": d, "scenes": [s]})
    # fundir actos cortos con su vecino (el anterior; el primero, con el 2º)
    i = 0
    while len(acts) > 1 and i < len(acts):
        if acts[i]["dur"] < min_len:
            if i > 0:
                acts[i - 1]["dur"] += acts[i]["dur"]
                acts[i - 1]["scenes"] += acts[i]["scenes"]
            else:  # el primero se funde con el segundo (orden temporal)
                acts[1]["dur"] += acts[0]["dur"]
                acts[1]["scenes"] = acts[0]["scenes"] + acts[1]["scenes"]
            acts.pop(i)
            i = 0
            continue
        i += 1
    # tope de actos: fundir el par adyacente más corto hasta cumplir
    while len(acts) > max_acts:
        k = min(range(len(acts) - 1),
                key=lambda x: acts[x]["dur"] + acts[x + 1]["dur"])
        acts[k]["dur"] += acts[k + 1]["dur"]
        acts[k]["scenes"] += acts[k + 1]["scenes"]
        acts.pop(k + 1)
    return acts


def _pick_tracks_for_acts(llm, tracks: list[dict], concept: dict, topic: str,
                          lang: str, acts: list[dict]) -> dict:
    """El supervisor musical elige UNA pista por acto (con variedad y
    coherencia A-B-A permitida). Devuelve {"files": [por acto], "reason"}."""
    md = concept.get("music_direction") or {}
    listing = "\n".join(
        f"- {t['file']}"
        + (f" · título: \"{t['title']}\"" if t.get("title") else "")
        + (f" · artista: {t['artist']}" if t.get("artist") else "")
        + (f" · {t['seconds']}s" if t.get("seconds") else "")
        for t in tracks)
    acts_txt = "\n".join(
        f"- acto {i + 1}: {a['dur']:.0f}s · intensidad {a['band']} · trata "
        f"de: {(a['scenes'][0].get('section') or '')} — "
        f"«{(a['scenes'][0].get('narration') or '')[:120]}»"
        for i, a in enumerate(acts))
    schema = {
        "type": "object",
        "properties": {
            "files": {"type": "array",
                      "items": {"type": "string",
                                "enum": [t["file"] for t in tracks]}},
            "reason": {"type": "string"},
        },
        "required": ["files", "reason"],
        "additionalProperties": False,
    }
    result = llm.complete_json(
        f"Eres supervisor musical de documentales y videos de YouTube en "
        f"{lang}. Diseñas la banda sonora POR ACTOS: cada tramo del video "
        "lleva la pista que sirve a su momento dramático.",
        f"TEMA DEL VIDEO: {topic}\n"
        f"DIRECCIÓN MUSICAL DEL CONCEPTO: {md}\n\n"
        f"ACTOS DEL VIDEO (en orden):\n{acts_txt}\n\n"
        f"PISTAS DISPONIBLES EN LA BIBLIOTECA:\n{listing}\n\n"
        "Elige la pista de cada acto (files = un archivo por acto, en el "
        "MISMO orden). Criterio: la energía y el tono de la pista deben "
        "corresponder a la intensidad del acto (calma/media/alta) y al tema; "
        "busca VARIEDAD entre actos contiguos (que la banda sonora respire y "
        "evolucione), aunque repetir una pista en actos no contiguos (A-B-A) "
        "da coherencia y está bien. reason: una frase con tu lógica.",
        schema=schema, purpose="music_pick_acts")
    return result


def _assemble_acts(music: LibraryMusic, tracks: list[dict], files: list[str],
                   acts: list[dict], out, xfade: float = 3.0):
    """Construye la pista final: cada acto loopeado a su duración y fundido
    con el siguiente (acrossfade) — la música evoluciona sin cortes secos."""
    from ytstudio.utils.media import run_ffmpeg
    by_file = {t["file"]: t for t in tracks}
    parts = []
    for i, (fname, act) in enumerate(zip(files, acts)):
        part = out.parent / f"acto_{i:02d}.mp3"
        # cada juntura consume `xfade` s del total: se genera de más
        extra = xfade if i < len(acts) - 1 else 2.0
        music.generate_track(by_file[fname]["path"], act["dur"] + extra, part)
        parts.append(part)
    if len(parts) == 1:
        parts[0].replace(out)
        return out
    args = []
    for p in parts:
        args += ["-i", str(p)]
    graph, cur = [], "[0:a]"
    for i in range(1, len(parts)):
        nxt = f"[x{i}]"
        graph.append(f"{cur}[{i}:a]acrossfade=d={xfade:.1f}:c1=tri:c2=tri"
                     f"{nxt}")
        cur = nxt
    run_ffmpeg(args + ["-filter_complex", ";".join(graph), "-map", cur,
                       "-c:a", "libmp3lame", "-q:a", "4", str(out)],
               "banda sonora por actos", timeout=600)
    for p in parts:
        p.unlink(missing_ok=True)
    return out


def _try_multi_track(project, cfg, music: LibraryMusic, llm, tracks,
                     concept, topic, lang, total, out) -> bool:
    """Banda sonora en ARCO con varias pistas de la biblioteca. True si la
    construyó; False para caer al flujo de pista única."""
    from ytstudio.progress import notify
    if not cfg.get("providers", {}).get("music", {}).get("multi_track", True):
        return False
    if len(tracks) < 2 or total < 180:
        return False  # video corto o biblioteca de una pista: una sola basta
    try:
        from ytstudio.phases.scenes import load_scenes
        scenes = load_scenes(project)
    except Exception:
        return False
    if not scenes or not all(s.get("duration") for s in scenes):
        return False
    acts = _acts_from_scenes(scenes)
    if len(acts) < 2:
        return False
    try:
        result = _pick_tracks_for_acts(llm, tracks, concept, topic, lang, acts)
        files = list(result.get("files") or [])
        if len(files) != len(acts):
            raise ValueError(f"el supervisor devolvió {len(files)} pistas "
                             f"para {len(acts)} actos")
        _assemble_acts(music, tracks, files, acts, out)
        distinct = len(set(files))
        notify(f"🎼 Banda sonora en arco: {len(acts)} actos con {distinct} "
               "pista(s) de tu biblioteca, fundidas entre sí (crossfade) "
               "siguiendo la intensidad dramática.")
        project.set("music_file", out.name)
        project.set("music_choice", {
            "source": "biblioteca_arco",
            "acts": [{"file": f, "seconds": round(a["dur"], 1),
                      "intensidad": a["band"]}
                     for f, a in zip(files, acts)],
            "reason": result.get("reason", "")})
        return True
    except Exception as e:
        project.add_warning(f"Banda sonora por actos no disponible ({e}) — "
                            "se usa una sola pista de la biblioteca.")
        return False


_AMBIENCE_SCHEMA = {
    "type": "object",
    "properties": {"actos": {"type": "array", "items": {
        "type": "object",
        "properties": {"acto": {"type": "integer"},
                       "ambiente": {"type": "string"},
                       "motivo": {"type": "string"}},
        "required": ["acto", "ambiente", "motivo"],
        "additionalProperties": False}}},
    "required": ["actos"], "additionalProperties": False,
}


def _build_ambience(project, cfg, llm, total: float) -> None:
    """DIRECTOR DE SONIDO: bajo la música y la voz, una cama de AMBIENTE que
    da lugar a cada tramo (viento en el desierto, murmullo en el mercado, sala
    en los tramos de archivo). Se decide por ACTOS —los mismos que la música—
    en UNA sola llamada, y se sintetiza en local si no tienes biblioteca.

    Es una capa de apoyo: cualquier fallo la quita y el video sale igual."""
    from ytstudio.progress import notify
    from ytstudio.utils import ambience as amb
    if not cfg.get("audio", {}).get("ambience", True):
        return
    out = project.path("music", "ambiente.wav")
    if out.exists():
        return                      # reanudación: ya construida
    try:
        from ytstudio.phases.scenes import load_scenes
        scenes = load_scenes(project)
    except Exception:
        return
    if not scenes or not all(s.get("duration") for s in scenes):
        return
    acts = _acts_from_scenes(scenes, min_len=45.0, max_acts=8)
    if not acts:
        return

    plan: list[tuple[str, float]] = []
    reasons: list[str] = []
    if getattr(llm, "is_mock", False):
        plan = [("sala", a["dur"]) for a in acts]
    else:
        from ytstudio.catalog import lang_name
        acts_txt = "\n".join(
            f"[{i}] {a['dur']:.0f}s · intensidad {a['band']} · "
            + " / ".join(dict.fromkeys(
                s.get("section", "") for s in a["scenes"] if s.get("section")))
            + " — «" + " ".join(
                (s.get("narration") or "") for s in a["scenes"][:3])[:260] + "»"
            for i, a in enumerate(acts))
        try:
            res = llm.complete_json(
                f"Eres el DIRECTOR DE SONIDO de un documental en "
                f"{lang_name(cfg)}. Eliges el ambiente de fondo de cada tramo: "
                "el sonido del LUGAR o del clima emocional, por debajo de la "
                "música y la voz. Sobrio: el ambiente acompaña, no protagoniza.",
                "Elige UN ambiente por acto de este catálogo:\n"
                + amb.catalog_text()
                + "\n- ninguno: silencio de fondo (úsalo cuando el tramo pide "
                "desnudez o cuando ningún ambiente encaja de verdad).\n\n"
                "Criterio: el ambiente debe corresponder a lo que se NARRA en "
                "ese tramo (un desierto suena a viento; un mercado, a "
                "multitud; un tramo de documentos y cifras, a sala). No "
                "repitas el mismo en todos los actos si la historia cambia de "
                "lugar; tampoco los alternes sin motivo.\n\n"
                f"ACTOS:\n{acts_txt}",
                schema=_AMBIENCE_SCHEMA, max_tokens=8000,
                purpose="sound_design")
            by_act = {int(r.get("acto", -1)): r for r in res.get("actos", [])}
            for i, a in enumerate(acts):
                r = by_act.get(i) or {}
                kind = r.get("ambiente") if r.get("ambiente") in amb.KINDS \
                    else "ninguno"
                plan.append((kind, a["dur"]))
                if kind != "ninguno":
                    reasons.append(f"{kind} ({a['dur']:.0f}s)")
        except Exception as e:
            project.add_warning(
                f"El diseño de ambiente no se pudo consultar ({e}): el video "
                "sale con música y voz, sin cama de ambiente.")
            return
    try:
        # el ambiente cubre el video entero (el último tramo estira la cola)
        if plan:
            plan[-1] = (plan[-1][0], plan[-1][1] + 3.0)
        built = amb.build_bed(plan, out, work_dir=project.path("music"))
    except Exception as e:
        project.add_warning(f"La cama de ambiente no se pudo construir ({e}): "
                            "el video sale con música y voz.")
        return
    if built is None:
        return
    project.set("ambience_plan", [{"ambiente": k, "seconds": round(d, 1)}
                                  for k, d in plan])
    notify("🎧 Diseño de sonido: cama de ambiente por actos"
           + (" — " + ", ".join(reasons) if reasons else "")
           + " (por debajo de la música y la voz).")


def run(project, cfg) -> None:
    music = get_music(cfg)
    concept = project.get("concept")
    total = project.get("total_duration")
    if not total:
        raise RuntimeError("Ejecuta primero la fase 'voiceover' (define la duración).")

    # Cama de AMBIENTE (independiente de qué proveedor de música se use)
    try:
        _build_ambience(project, cfg, get_llm(cfg), total)
    except Exception as e:
        project.add_warning(f"Diseño de ambiente omitido ({e}).")

    out = project.path("music", "musica.mp3")
    mood = concept["music_direction"]["mood"]
    seconds = total + 2.0

    # Biblioteca local: elegir la pista con criterio de supervisor musical
    if isinstance(music, LibraryMusic):
        llm = get_llm(cfg)
        tracks = music.list_tracks()
        topic = (project.get("brief") or {}).get("topic", "")
        lang = cfg.get("language", "es")
        if tracks and not getattr(llm, "is_mock", False):
            # ARCO MULTI-PISTA: en videos largos, un acto musical por tramo
            # de intensidad (la queja real: 24 pistas en la biblioteca y el
            # video entero sonaba plano con una sola).
            if _try_multi_track(project, cfg, music, llm, tracks, concept,
                                topic, lang, total, out):
                return
            try:
                fname, fits, reason = _pick_track(
                    llm, tracks, concept,
                    (project.get("brief") or {}).get("topic", ""),
                    cfg.get("language", "es"))
                chosen = next(t for t in tracks if t["file"] == fname)
                if not fits and os.environ.get("REPLICATE_API_TOKEN"):
                    # Ninguna pista sirve → generar música a medida
                    try:
                        ReplicateMusic(cfg).generate(mood, seconds, out)
                        project.set("music_file", out.name)
                        project.set("music_choice", {
                            "source": "generada", "reason": reason})
                        return
                    except Exception as e:
                        project.add_warning(
                            f"No se pudo generar música a medida ({e}) — se "
                            f"usa la pista más cercana: {fname}")
                elif not fits:
                    project.add_warning(
                        f"Ninguna pista de la biblioteca encaja del todo "
                        f"({reason}) — se usa la más cercana: {fname}. "
                        "Configura Replicate para generar música a medida.")
                music.generate_track(chosen["path"], seconds, out)
                project.set("music_file", out.name)
                project.set("music_choice", {
                    "source": "biblioteca", "file": fname, "reason": reason})
                return
            except Exception as e:
                project.add_warning(f"Selección musical con IA no disponible "
                                    f"(pista por mood/aleatoria): {e}")

    try:
        music.generate(mood, seconds, out)
    except Exception as e:
        if isinstance(music, MockMusic):
            raise  # el pad sintético no debería fallar; si lo hace, es real
        MockMusic(cfg).generate(mood, seconds, out)
        project.add_warning(
            f"Música IA no disponible — se usó música ambiental sencilla. {e}")
    project.set("music_file", out.name)
