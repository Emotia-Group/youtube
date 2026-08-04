"""Orquestador: ejecuta las fases en orden, con estado reanudable por fase."""
from __future__ import annotations

import time

from ytstudio.phases import (assembly, broll, concept, ingest, metadata, music,
                             publish, scenes, script, subtitles, voiceover)

PHASES: list[tuple[str, object, str]] = [
    ("ingest", ingest, "Ingesta y análisis del input"),
    ("concept", concept, "Concepto y estilo"),
    ("script", script, "Guion completo"),
    ("scenes", scenes, "Escenas / storyboard"),
    ("voiceover", voiceover, "Voz en off (TTS)"),
    ("broll", broll, "B-roll generado con IA"),
    ("music", music, "Musicalización"),
    ("subtitles", subtitles, "Subtítulos"),
    ("assembly", assembly, "Montaje y edición"),
    ("metadata", metadata, "Metadatos y miniatura"),
    ("publish", publish, "Publicación en YouTube"),
]

PHASE_ORDER = [name for name, _, _ in PHASES]

# Etiquetas cortas y humanas para la interfaz
PHASE_LABELS = {
    "ingest": "Análisis",
    "concept": "Concepto",
    "script": "Guion",
    "scenes": "Escenas",
    "voiceover": "Voz",
    "broll": "Imágenes",
    "music": "Música",
    "subtitles": "Subtítulos",
    "assembly": "Montaje",
    "metadata": "Metadatos",
    "publish": "Publicación",
}


def run_pipeline(project, cfg, *, from_phase: str | None = None,
                 to_phase: str | None = None, log=print) -> None:
    # Verificar ffmpeg desde el inicio (en Windows también lo busca en
    # C:\ffmpeg\bin y lo añade al PATH) — mejor un error claro ahora que
    # un fallo críptico en mitad del pipeline.
    from ytstudio.utils.media import require_ffmpeg
    require_ffmpeg()

    # Registro de eventos persistente (novedades, errores y tiempos): todo lo
    # que aparece en el progreso queda guardado para diagnóstico y para poder
    # compartirlo. El estado de la fase actual acompaña a cada evento.
    from ytstudio import eventlog
    slug = getattr(project, "slug", None)
    cur = {"phase": None}

    # Gasto REAL (tokens/imágenes/voz/video que de verdad se generaron en esta
    # ejecución) — se acumula al histórico del proyecto al terminar, para que
    # el reporte cubra TODO el proyecto aunque se haya generado en varias
    # sesiones (reanudar no cuenta de nuevo lo ya hecho, y aquí tampoco).
    from ytstudio import usage
    usage.reset()

    def emit(level: str, msg: str, **kw) -> None:
        eventlog.log(level, msg, project=slug, phase=cur["phase"], **kw)

    def sink(msg) -> None:
        log(msg)
        emit("info", str(msg))

    # Los avisos de espera por límite de velocidad de Replicate y el canal de
    # progreso general (descargas, análisis…) van al log de la UI y al de
    # eventos.
    from ytstudio.providers import replicate_util
    replicate_util.set_progress(sink)
    from ytstudio import progress
    progress.set_sink(sink)

    # FRENO DE MANO: tope de gasto DINÁMICO, calculado sobre lo que falta por
    # generar (ver budget.py). Se recalcula antes de cada fase, porque la
    # estimación se vuelve exacta en cuanto existen las escenas reales.
    from ytstudio import budget as budget_mod

    def refresh_cap(reset: bool = False) -> None:
        try:
            info = budget_mod.compute_cap(project, cfg)
            usage.set_cap(info["cap"], reset=reset)
            return info
        except Exception:
            return None

    cap_info = refresh_cap(reset=True)
    if cap_info:
        sink(f"🛡 Presupuesto de esta corrida: {budget_mod.explain(cap_info)}.")

    # RESULTADOS YA PAGADOS Y NO ENTREGADOS: si una descarga falló en una
    # ejecución anterior, el dinero YA se gastó y el resultado sigue
    # disponible un rato. Se avisa para que se recupere (al regenerar esa
    # escena se re-descarga sin volver a cobrar).
    try:
        from ytstudio import ledger
        pend = ledger.pending_paid(max_age_seconds=ledger.URL_TTL_SECONDS)
        if pend:
            sink(f"💰 Hay {len(pend)} resultado(s) ya PAGADOS "
                 f"(~${ledger.pending_paid_usd(pend):.2f}) que no llegaron a "
                 "descargarse. Se reutilizarán automáticamente en vez de "
                 "volver a encargarlos.")
    except Exception:
        pass

    if from_phase:
        project.reset_from(from_phase, PHASE_ORDER)

    project.set("warnings", [])  # avisos frescos por ejecución
    emit("info", f"Generación iniciada (desde «{from_phase or 'inicio'}» "
                 f"hasta «{to_phase or 'fin'}»).")
    run_start = time.time()
    seen_warnings = 0

    try:
        for name, module, desc in PHASES:
            cur["phase"] = name
            if project.phase_status(name) == "done":
                log(f"✔ {name:<10} {desc} (ya completada)")
                if name == to_phase:
                    break
                continue

            # El tope se re-mide con el estado ACTUAL del proyecto: tras la
            # fase de Escenas ya se sabe el número exacto de escenas, cuáles
            # son video y cuántos segundos de personaje hay — justo lo que se
            # va a pagar en la fase de B-roll, la única cara del pipeline.
            refresh_cap()

            sink(f"▶ {name:<10} {desc}…")
            start = time.time()
            try:
                module.run(project, cfg)
            except Exception as e:
                secs = round(time.time() - start, 1)
                project.mark_phase(name, "failed", error=str(e))
                emit("error", f"{desc}: {e}", seconds=secs)
                raise RuntimeError(f"La fase '{name}' falló: {e}") from e
            secs = round(time.time() - start, 1)
            project.mark_phase(name, "done", seconds=secs)
            # Avisos nuevos acumulados por esta fase (B-roll sin usar, NSFW, etc.)
            warnings = project.get("warnings") or []
            for w in warnings[seen_warnings:]:
                emit("warn", w)
            seen_warnings = len(warnings)
            emit("info", f"{desc}: completada", seconds=secs)
            log(f"✔ {name:<10} completada en {secs:.1f}s")

            # PUNTO DE CONTROL del storyboard: el último momento en que
            # corregir es GRATIS. Todo lo anterior cuesta centavos; la fase
            # siguiente que gasta (B-roll) concentra casi el 100% del dinero.
            if name == "scenes":
                _storyboard_checkpoint(project, cfg, sink)

            if name == to_phase:
                break
    finally:
        # El gasto YA incurrido se guarda SIEMPRE, incluso si una fase falló a
        # mitad de camino — ese dinero/tiempo se gastó de verdad.
        _persist_usage(project, round(time.time() - run_start, 1))
        _warn_unclaimed(project, emit)

    cur["phase"] = None
    emit("info", f"Generación finalizada en {time.time() - run_start:.1f}s.")


def _storyboard_checkpoint(project, cfg, sink) -> None:
    """Resumen destacado al quedar listo el storyboard: qué se va a generar,
    cuánto costará y dónde revisarlo ANTES de gastar. Es el punto natural
    para corregir un prompt, el reparto de personaje o el % de presencia:
    aquí una corrección cuesta $0; después de generar, cuesta otra generación.
    """
    try:
        from ytstudio import budget as budget_mod
        from ytstudio.estimate import estimate
        est = estimate(project, cfg)
        info = budget_mod.compute_cap(project, cfg, est)
        paid = [i for i in (est.get("items") or [])
                if (i.get("costo") or [0, 0])[1] > 0
                and project.phase_status(i.get("fase_key") or "") != "done"]
        n = est.get("escenas") or project.get("scene_count") or 0
        dur = est.get("duracion_min") or 0
        sink("─" * 62)
        sink(f"📋 PUNTO DE CONTROL — storyboard listo: {n} escenas · "
             f"~{dur:.1f} min de video")
        sink("   Revísalo en 04_scenes/storyboard.md (biblia visual, prompt de "
             "cada escena, riesgo de movimiento y reparto de personaje).")
        if paid:
            sink(f"   💰 Falta por generar: ~${sum((i['costo'][0]) for i in paid):.2f}"
                 f"-${sum((i['costo'][1]) for i in paid):.2f} · "
                 f"{budget_mod.explain(info)}")
            for i in paid:
                sink(f"      · {i['fase']}: {i['detalle']} → "
                     f"${i['costo'][0]:.2f}-${i['costo'][1]:.2f}")
        else:
            sink("   💰 No queda nada de pago por generar.")
        sink("   ⚠ Corregir AQUÍ no cuesta nada; corregir después de generar "
             "cuesta volver a generar.")
        sink("─" * 62)
    except Exception:
        pass


def _warn_unclaimed(project, emit) -> None:
    """Al terminar, deja constancia CLARA de cualquier resultado que se pagó
    y no se recibió. Antes esto era invisible: se cobraban clips que nunca
    llegaban y ni el registro ni el reporte de gasto lo mencionaban."""
    try:
        from ytstudio import ledger
        pend = ledger.pending_paid(max_age_seconds=ledger.URL_TTL_SECONDS)
        if not pend:
            return
        total = ledger.pending_paid_usd(pend)
        msg = (f"⚠ SALDO EN RIESGO: {len(pend)} generación(es) terminaron bien "
               f"en Replicate (ya cobradas, ~${total:.2f}) pero su archivo no "
               "llegó a descargarse. Pulsa «Generar video» de nuevo DENTRO DE "
               "LA PRÓXIMA HORA y se re-descargarán sin volver a cobrar "
               "(después de ese plazo Replicate borra el resultado). "
               "Detalle: " + ", ".join(
                   f"{p.get('label') or p.get('model', '')} [{p.get('id', '')[:12]}]"
                   for p in pend[:5]))
        project.add_warning(msg)
        emit("warn", msg)
    except Exception:
        pass


def _persist_usage(project, elapsed_seconds: float) -> None:
    from ytstudio import usage
    new_items = usage.get_state()
    if new_items:
        project.set("usage_items", (project.get("usage_items") or []) + new_items)
    time_report = project.get("time_report") or {"total_seconds": 0.0}
    time_report["last_run_seconds"] = elapsed_seconds
    time_report["total_seconds"] = round(
        time_report.get("total_seconds", 0.0) + elapsed_seconds, 1)
    project.set("time_report", time_report)
