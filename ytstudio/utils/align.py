"""Mapeo de tiempos reales de la narración del usuario al tiempo LOCAL de cada
escena ya montada. Es la base para sincronizar subtítulos y rótulos con la voz
real (timestamps por palabra de Whisper) en vez de estimar por proporción de
caracteres — la voz de una escena no siempre fluye a ritmo constante."""
from __future__ import annotations


def flatten_words(segments: list[dict]) -> list[dict]:
    """Todas las palabras (con tiempos reales, en el audio ORIGINAL) de la
    transcripción, en orden. Vacío si el proyecto es de una versión anterior
    sin timestamps por palabra (los llamadores deben tener un respaldo).

    Filtra duplicados: dos palabras NUNCA pueden solaparse en el tiempo (nadie
    pronuncia dos palabras a la vez) — si sus intervalos se solapan es que la
    misma palabra quedó asignada a dos segmentos (bug ya corregido en la
    transcripción, pero esto protege proyectos con datos ya guardados)."""
    words: list[dict] = []
    for seg in segments or []:
        words.extend(seg.get("words") or [])
    words.sort(key=lambda w: w["start"])
    out: list[dict] = []
    prev_end = -1.0
    for w in words:
        if w["start"] < prev_end - 0.02:
            continue  # se solapa con la palabra anterior: duplicado
        out.append(w)
        prev_end = max(prev_end, float(w["end"]))
    return out


def assign_words(scenes: list[dict], words: list[dict]) -> dict[int, list[dict]]:
    """Asigna cada palabra a EXACTAMENTE una escena, por su tiempo de inicio
    real. Las escenas son contiguas (audio_end[i] == audio_start[i+1]); un
    filtro ingenuo con tolerancia en ambos bordes duplicaría la palabra que
    cae justo en la frontera (apareció en los subtítulos de las dos escenas
    en pruebas). Se usa bisección sobre los límites reales: cada palabra cae
    en una única escena. Devuelve {scene_id: [palabras]}."""
    import bisect

    user = [s for s in scenes if "audio_start" in s]
    out: dict[int, list[dict]] = {s["id"]: [] for s in user}
    if not user or not words:
        return out
    bounds = [float(s["audio_start"]) for s in user] + [float(user[-1]["audio_end"])]
    for w in words:
        idx = bisect.bisect_right(bounds, w["start"]) - 1
        idx = max(0, min(idx, len(user) - 1))
        out[user[idx]["id"]].append(w)
    return out


def local_time(scene: dict, t: float) -> float:
    """Convierte un tiempo del audio ORIGINAL (t) al tiempo LOCAL dentro de la
    escena ya montada — sumando su aire de entrada (vo_offset, solo la
    primera escena) y acotado al tramo de voz real (vo_duration)."""
    a = float(scene.get("audio_start") or 0.0)
    b = float(scene.get("audio_end") or a)
    vo = float(scene.get("vo_duration") or max(0.0, b - a))
    off = float(scene.get("vo_offset") or 0.0)
    return off + min(max(0.0, t - a), vo)
