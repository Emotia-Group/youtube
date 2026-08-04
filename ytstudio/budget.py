"""TOPE DE GASTO DINÁMICO — protege el saldo sin estorbar una producción real.

Un tope fijo no puede servir a los dos propósitos a la vez: $8 es enorme para
una prueba de 3 escenas (donde un fallo en bucle se comió $11.85 sin que nada
lo frenara) y ridículamente pequeño para un documental de 15 minutos con
personaje narrador (que legítimamente cuesta ~$40). El número correcto no es
una constante: es una función de LO QUE SE VA A GENERAR.

Por eso el tope se calcula a partir de la estimación que el propio programa ya
hace antes de generar:

    tope = (costo ALTO estimado de lo que FALTA por generar) x margen

con un piso mínimo (para que una prueba diminuta no quede con un tope tan
ajustado que salte por cualquier cosa) y, si el usuario lo pide, un techo
absoluto manual.

Dos detalles que lo hacen fiable:

· Se calcula sobre lo que FALTA, no sobre el video entero: al reanudar un
  proyecto a medias, el tope no incluye lo ya generado (que no se vuelve a
  cobrar), así que no queda inflado.
· Se RECALCULA antes de cada fase. Al arrancar solo se conoce el pronóstico
  grueso de la configuración; después de la fase de Escenas se conoce el
  número EXACTO de escenas, cuáles son video y cuántos segundos de personaje
  hay — que es justo lo que se va a pagar en la fase siguiente.

El margen absorbe la variación normal (reintentos legítimos, un modelo que
cobra en el extremo alto de su rango) sin dejar pasar un desbocamiento: la
pérdida real del usuario fue ~10x lo esperable para esa prueba, no 1.4x.
"""
from __future__ import annotations

DEFAULT_MARGIN = 1.4     # colchón sobre el costo alto estimado
DEFAULT_MIN_USD = 1.5    # piso: por debajo de esto el tope sería hipersensible


def _cfg(cfg: dict) -> dict:
    return (cfg or {}).get("budget") or {}


def remaining_cost(project, cfg: dict, est: dict | None = None) -> float:
    """Costo ALTO estimado de las fases que todavía NO están completadas."""
    from ytstudio.estimate import estimate
    est = est if est is not None else estimate(project, cfg)
    total = 0.0
    for item in est.get("items") or []:
        key = item.get("fase_key") or ""
        try:
            done = key and project.phase_status(key) == "done"
        except Exception:
            done = False
        if done:
            continue
        costo = item.get("costo") or [0, 0]
        total += float(costo[1] if len(costo) > 1 else costo[0])
    return round(total, 4)


def compute_cap(project, cfg: dict, est: dict | None = None) -> dict:
    """Tope para esta generación. Devuelve también las piezas del cálculo,
    para poder explicárselo al usuario en el registro en vez de soltarle un
    número mágico."""
    b = _cfg(cfg)
    margin = float(b.get("margin", DEFAULT_MARGIN) or DEFAULT_MARGIN)
    floor = float(b.get("min_usd", DEFAULT_MIN_USD) or 0)
    manual = float(b.get("max_usd", 0) or 0)

    try:
        pending = remaining_cost(project, cfg, est)
    except Exception:
        pending = 0.0

    auto = max(floor, round(pending * margin, 2))
    cap = auto
    limited_by_manual = False
    if manual > 0 and manual < cap:
        # Techo absoluto elegido a mano: manda si es MÁS restrictivo que el
        # automático (candado extra, no un permiso para gastar más).
        cap = manual
        limited_by_manual = True
    return {"cap": round(cap, 2), "auto": auto, "pending_high": pending,
            "margin": margin, "floor": floor, "manual": manual,
            "limited_by_manual": limited_by_manual}


def explain(info: dict) -> str:
    """Una línea para el registro: de dónde sale el tope."""
    if info.get("limited_by_manual"):
        return (f"tope ${info['cap']:.2f} (techo manual; el automático habría "
                f"sido ${info['auto']:.2f})")
    if info.get("pending_high", 0) * info.get("margin", 1) < info.get("floor", 0):
        return (f"tope ${info['cap']:.2f} (mínimo de seguridad; lo pendiente "
                f"estima ~${info['pending_high']:.2f})")
    return (f"tope ${info['cap']:.2f} = ~${info['pending_high']:.2f} estimado "
            f"x {info['margin']:.1f} de margen")
