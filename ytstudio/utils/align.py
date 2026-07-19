"""Mapeo de tiempos reales de la narración del usuario al tiempo LOCAL de cada
escena ya montada. Es la base para sincronizar subtítulos y rótulos con la voz
real (timestamps por palabra de Whisper) en vez de estimar por proporción de
caracteres — la voz de una escena no siempre fluye a ritmo constante."""
from __future__ import annotations


def flatten_words(segments: list[dict]) -> list[dict]:
    """Todas las palabras (con tiempos reales, en el audio ORIGINAL) de la
    transcripción, en orden. Vacío si el proyecto es de una versión anterior
    sin timestamps por palabra (los llamadores deben tener un respaldo).

    Filtra duplicados REALES: la misma palabra asignada a dos segmentos (bug
    antiguo de la transcripción) aparece dos veces con el mismo texto y el
    mismo tiempo de inicio. Solo se descarta ese caso — un simple solape de
    tiempos NO basta, porque los timestamps de Whisper a veces se solapan
    unos milisegundos entre palabras legítimas y se perderían palabras."""
    words: list[dict] = []
    for seg in segments or []:
        words.extend(seg.get("words") or [])
    words.sort(key=lambda w: w["start"])
    out: list[dict] = []
    for w in words:
        if out and abs(float(w["start"]) - float(out[-1]["start"])) < 0.02 \
                and ((w.get("text") or "").strip().lower()
                     == (out[-1].get("text") or "").strip().lower()):
            continue  # duplicado exacto (misma palabra, mismo instante)
        out.append(w)
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


def video_time_fn(intro: float, insertions: list[tuple[float, float]]):
    """Mapa GLOBAL de tiempo: convierte un instante del audio ORIGINAL (t) al
    instante en el VIDEO montado. Es la única fuente de verdad para sincronizar
    voz, subtítulos y rótulos — sustituye al viejo offset por escena, que no
    podía representar pausas insertadas DENTRO de una escena.

    video(t) = intro + t + (silencios insertados en puntos p <= t)

    `insertions` = lista de (punto_en_audio_original, duración_del_silencio).
    Como los puntos de inserción caen SIEMPRE en huecos entre palabras, ninguna
    palabra coincide con un punto de inserción (el mapa no es ambiguo)."""
    import bisect
    pts = sorted(insertions)
    ps = [p for p, _ in pts]
    cum: list[float] = []
    acc = 0.0
    for _, d in pts:
        acc += d
        cum.append(acc)

    def video(t: float) -> float:
        k = bisect.bisect_right(ps, t)  # nº de inserciones con p <= t
        return intro + t + (cum[k - 1] if k > 0 else 0.0)

    return video


def local_time(scene: dict, t: float) -> float:
    """Convierte un tiempo del audio ORIGINAL (t) al tiempo LOCAL dentro de la
    escena ya montada — sumando su aire de entrada (vo_offset, solo la
    primera escena) y acotado al tramo de voz real (vo_duration)."""
    a = float(scene.get("audio_start") or 0.0)
    b = float(scene.get("audio_end") or a)
    vo = float(scene.get("vo_duration") or max(0.0, b - a))
    off = float(scene.get("vo_offset") or 0.0)
    return off + min(max(0.0, t - a), vo)
