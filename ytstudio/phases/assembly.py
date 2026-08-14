"""FASE 9 — Montaje: renderiza cada escena (Ken Burns sobre imagen o clip de
video IA, rótulos cinematográficos animados, fundidos), concatena, y mezcla el
audio con criterio de banda sonora: la música sigue el arco de intensidad de
la historia (envolvente por escena), respira en las pausas de la voz (ducking)
y se acentúa con efectos incidentales (whoosh/riser/boom) en los cortes clave.
Termina normalizando a -14 LUFS y aplicando los subtítulos."""
from __future__ import annotations

import hashlib
import json
import shutil
import unicodedata
from pathlib import Path

from ytstudio.phases.scenes import load_scenes
from ytstudio.utils.media import (filter_path, find_font, probe_duration,
                                  probe_video_size,
                                  require_ffmpeg, run_ffmpeg)

FADE = 0.3        # fundido corto (corte suave entre escenas)
FADE_OPEN = 0.6   # apertura y cierre del video (un poco más largo)
FADE_SLOW = 0.55  # fundido dramático (tras un respiro/pausa)

# Códigos ISO-639-2 para la pista de subtítulos del mp4
# Código ISO 639-2 del stream de subtítulos, desde el catálogo de idiomas
# (única fuente de verdad) + extras históricos.
from ytstudio.catalog import LANGUAGES as _LANGS
_LANG3 = {l["code"]: l["lang3"] for l in _LANGS}
_LANG3.update({"it": "ita", "ja": "jpn", "ko": "kor"})


def _kenburns(animation: str, frames: int, w: int, h: int, fps: int,
              cover: bool = True) -> str:
    """Filtro zoompan para el movimiento de cámara sobre una imagen fija.
    Se sobreescala la imagen antes para evitar el jitter típico de zoompan."""
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z_in = f"1+0.14*on/{frames}"
    z_out = f"1.14-0.14*on/{frames}"
    presets = {
        "zoom_in": (z_in, cx, cy),
        "zoom_out": (z_out, cx, cy),
        "pan_left": ("1.12", f"(iw-iw/zoom)*(1-on/{frames})", cy),
        "pan_right": ("1.12", f"(iw-iw/zoom)*on/{frames}", cy),
        "static": ("1.001", cx, cy),
    }
    z, x, y = presets.get(animation, presets["zoom_in"])
    # CROP DE COBERTURA a la relación de aspecto de salida ANTES de escalar:
    # sin esto, una imagen que no sea 16:9 (una referencia de personaje en
    # vertical, un B-roll subido en otro formato…) llega a zoompan con OTRO
    # aspecto, y zoompan la ESTIRA de forma no uniforme al ajustarla a WxH
    # (caras "anchas" — el defecto que se veía en el video). El camino de
    # video (broll_video, más abajo en _render_scene) ya hacía este mismo
    # recorte de cobertura; aquí faltaba. Tras el recorte, la imagen YA tiene
    # el aspecto de salida, así que escalar a 2560 lo conserva sin más.
    # (cover=False cuando la entrada YA viene compuesta exactamente a WxH,
    # p. ej. la composición sobre fondo desenfocado de _still_filter.)
    pre = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
           f"crop={w}:{h}," if cover else "")
    # Sobreescala a 2560 (no 3840): con zoom máximo 1.14 sobre salida 1920
    # bastan ~2200 px — las imágenes fuente son de 1536, así que 3840 solo
    # añadía cómputo sin ganar detalle. Render ~2x más rápido, misma calidad.
    return (f"{pre}scale=2560:-2,setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps}")


# Umbral de desajuste de aspecto para pasar de recorte de cobertura a
# composición con fondo desenfocado: 4:3 sobre 16:9 da 1.33 (se recorta bien);
# 1:1 da 1.78 y 9:16 da 3.16 (recortar cortaría el sujeto).
_BLURPAD_MISMATCH = 1.45


def _probe_image_size(path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return None


def _aspect_off(size: tuple[int, int] | None, w: int, h: int) -> float:
    """Cuánto se aleja el aspecto de la fuente del de salida (1.0 = idéntico).
    0.0 cuando no se pudo medir (no fuerza ninguna decisión)."""
    if not size or not size[0] or not size[1]:
        return 0.0
    out_ar, src_ar = w / h, size[0] / size[1]
    return max(out_ar / src_ar, src_ar / out_ar)


def _contain_chain(w: int, h: int) -> str:
    """Composición ENTERA sobre fondo ampliado y desenfocado (estándar
    televisivo): nada del sujeto se pierde aunque el aspecto no coincida."""
    return (f"split=2[cbg][cfg];"
            f"[cbg]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},boxblur=32:2[cbb];"
            f"[cfg]scale={w}:{h}:force_original_aspect_ratio=decrease[cff];"
            f"[cbb][cff]overlay=(W-w)/2:(H-h)/2")


def _still_filter(img_path, animation: str, frames: int, w: int, h: int,
                  fps: int) -> str:
    """Cadena de filtros de una escena de imagen fija. Con un aspecto parecido
    al de salida: recorte de cobertura + Ken Burns (llena el cuadro, estilo
    cine). Con un aspecto MUY distinto (retrato o cuadrada sobre 16:9, o
    apaisada sobre un Short vertical), el recorte cortaría el sujeto — una
    cara en retrato pierde los ojos —: se compone la imagen ENTERA sobre su
    propio fondo ampliado y desenfocado (estándar televisivo) y el Ken Burns
    anima la composición completa."""
    size = _probe_image_size(img_path)
    if size and size[1]:
        out_ar, src_ar = w / h, size[0] / size[1]
        if max(out_ar / src_ar, src_ar / out_ar) >= _BLURPAD_MISMATCH:
            kb = _kenburns(animation, frames, w, h, fps, cover=False)
            return (
                f"split=2[kbg][kfg];"
                f"[kbg]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},boxblur=32:2[kbb];"
                f"[kfg]scale={w}:{h}:force_original_aspect_ratio=decrease[kff];"
                f"[kbb][kff]overlay=(W-w)/2:(H-h)/2,{kb}")
    return _kenburns(animation, frames, w, h, fps)


# ---------------------------------------------------------------------------
# Rótulos cinematográficos
# ---------------------------------------------------------------------------

def _spaced(text: str) -> str:
    """Versalitas con tracking (espaciado entre letras), estilo documental."""
    return " ".join(text.upper())


def _norm_txt(s: str) -> str:
    """minúsculas y sin tildes, para buscar el rótulo dentro de la narración."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _narration_moment(scene: dict, dur: float) -> float | None:
    """Momento (s, local a la escena) en que el narrador dice el texto del
    rótulo. En narración propia se calcula en la fase de voz con los timestamps
    reales de Whisper (scene['overlay_at']); si no, se estima por la posición
    del texto dentro de la narración."""
    if scene.get("overlay_at") is not None:
        return float(scene["overlay_at"])
    overlay = scene.get("overlay") or {}
    narr = _norm_txt(scene.get("narration") or "")
    if not narr:
        return None
    vo = float(scene.get("vo_duration") or dur)
    cand = _norm_txt(overlay.get("text") or "")
    idx = narr.find(cand) if cand else -1
    if idx < 0:  # sin match exacto: la palabra significativa más larga
        for w in sorted((w for w in cand.split() if len(w) >= 4),
                        key=len, reverse=True):
            idx = narr.find(w)
            if idx >= 0:
                break
    if idx < 0:
        return None
    return float(scene.get("vo_offset") or 0.0) + vo * idx / max(1, len(narr))


def _fit(size: int, text: str) -> int:
    """Reduce el cuerpo si el texto es largo para que no se salga del encuadre."""
    n = max(1, len(text))
    return max(int(size * 0.55), int(size * min(1.0, (20 / n) ** 0.5)))


def _overlay_layout(otype: str, w: int, h: int) -> dict:
    """Composición por tipo de rótulo. Todos animados: fundido + deriva sutil.
    - lugar/fecha: 'locator' documental arriba-izquierda, en versalitas.
    - personaje: tercio inferior izquierdo, nombre en serif (no pisa subtítulos).
    - dato: cifra protagonista centrada en el tercio superior.
    - lista: ítem de enumeración, centrado, algo menor.
    - conclusion: frase en serif centrada, fundidos lentos.
    """
    left = int(w * 0.062)
    layouts = {
        "lugar": {"align": "left", "x": left, "y": int(h * 0.082),
                  "size": int(h * 0.042), "serif": False, "upper": True,
                  "drift": "x", "slow": False},
        "fecha": {"align": "left", "x": left, "y": int(h * 0.082),
                  "size": int(h * 0.042), "serif": False, "upper": True,
                  "drift": "x", "slow": False},
        "personaje": {"align": "left", "x": left, "y": int(h * 0.66),
                      "size": int(h * 0.058), "serif": True, "upper": False,
                      "drift": "x", "slow": False},
        "dato": {"align": "center", "x": 0, "y": int(h * 0.145),
                 "size": int(h * 0.072), "serif": False, "upper": False,
                 "drift": "y", "slow": False},
        "lista": {"align": "center", "x": 0, "y": int(h * 0.14),
                  "size": int(h * 0.054), "serif": False, "upper": False,
                  "drift": "y", "slow": False},
        "conclusion": {"align": "center", "x": 0, "y": int(h * 0.28),
                       "size": int(h * 0.058), "serif": True, "upper": False,
                       "drift": "y", "slow": True},
        # hook: gancho de apertura estilo TikTok/Reels — se renderiza aparte
        # (_hook_filters), esta entrada solo evita el fallback a 'dato'.
        "hook": {"align": "center", "x": 0, "y": int(h * 0.26),
                 "size": int(h * 0.055), "serif": False, "upper": False,
                 "drift": "y", "slow": False},
    }
    return layouts.get(otype, layouts["dato"])


def _drawtext(font: str, textfile: Path, size: int, color: str,
              x_expr: str, y_expr: str, alpha: str, extra: str = "",
              borderw: int = 2, bordercolor: str = "black@0.35") -> str:
    return (f"drawtext=fontfile='{filter_path(font)}':"
            f"textfile='{filter_path(textfile)}':expansion=none:"
            f"fontsize={size}:fontcolor={color}:"
            f"borderw={borderw}:bordercolor={bordercolor}:"
            f"shadowcolor=black@0.6:shadowx=0:shadowy=2:"
            f"x='{x_expr}':y='{y_expr}':alpha='{alpha}'{extra}")


def _brand_font(cfg: dict, bold: bool = True,
                serif_default: bool = False) -> str | None:
    """Fuente de los RÓTULOS (no de los stickers, que imitan apps nativas y
    no llevan branding): si el estilo del canal fija una familia (v0.41.0),
    manda ella para TODO rótulo por igual; si no, se preserva el criterio
    editorial de siempre (serif solo para 'personaje', sans en el resto)."""
    family = cfg["video"].get("overlay_font_family")
    if family:
        return find_font(bold=bold, family=family)
    return find_font(bold=bold, serif=serif_default)


def _brand_text_color(cfg: dict) -> str:
    """Color del cuerpo del rótulo (blanco por defecto, o el del branding
    del canal/estilo si lo fija)."""
    return "0x" + str(cfg["video"].get("overlay_text_color", "FFFFFF")).lstrip("#")


def _overlay_data(scene: dict) -> dict | None:
    """El rótulo de la escena, con la migración de los proyectos antiguos
    (texto plano → diseño de 'dato')."""
    overlay = scene.get("overlay")
    if not overlay and scene.get("on_screen_text"):
        overlay = {"type": "dato", "text": scene["on_screen_text"],
                   "kicker": "", "emphasis": ""}
    return overlay or None


def _lower_third_plan(scene: dict, cfg: dict, out_dir: Path) -> dict | None:
    """Compone el rótulo CON DISEÑO (placa + filete + jerarquía) como PNG y
    devuelve su geometría, o None si este rótulo no lleva placa (gancho y
    conclusión tienen lenguaje propio) o si la composición no fue posible —
    en ese caso el montaje usa el camino drawtext de siempre."""
    overlay = _overlay_data(scene)
    if not overlay or not cfg["video"].get("overlays", True):
        return None
    if not cfg["video"].get("overlay_plate", True):
        return None   # el creador prefiere el rótulo sin placa (modo clásico)
    otype = overlay.get("type", "dato")
    from ytstudio.utils import lower_thirds as lt
    if otype not in lt.LAYOUTS:
        return None   # hook / conclusion: composiciones propias
    text = (overlay.get("text") or "").strip()
    if not text:
        return None
    try:
        return lt.render(
            text, overlay.get("kicker") or "", overlay.get("emphasis") or "",
            otype, out_dir / f"lt_{scene['id']:03d}.png",
            width=cfg["video"]["width"], height=cfg["video"]["height"],
            style=str(cfg["video"].get("overlay_style", "documental")),
            accent=str(cfg["video"].get("overlay_accent", "E8C46B")),
            text_color=str(cfg["video"].get("overlay_text_color", "FFFFFF")),
            font_main=_brand_font(cfg, bold=True,
                                  serif_default=otype == "personaje"),
            font_kicker=_brand_font(cfg, bold=True),
            serif=otype == "personaje")
    except Exception:
        return None   # nunca se cae por un adorno: se usa el rótulo clásico


def _lower_third_setup(scene: dict, dur: float, cfg: dict,
                       out_dir: Path) -> tuple[list[str], str, str]:
    """(args de entrada, cadena con [1:v] de marcador, posición) del rótulo
    con placa. Entra deslizándose desde la izquierda un instante ANTES de que
    la narración diga esas palabras, se sostiene y se despide."""
    plan = _lower_third_plan(scene, cfg, out_dir)
    if plan is None:
        return [], "", ""
    fps = cfg["video"]["fps"]
    moment = _narration_moment(scene, dur)
    t0 = (max(0.25, min(moment - 0.35, dur - 2.2)) if moment is not None
          else (0.45 if dur > 4 else 0.25))
    t1 = min(dur - 0.75, t0 + 4.8)
    if t1 < t0 + 0.8:
        t1 = max(t0 + 0.8, dur - 0.4)
    chain = (f"[1:v]format=rgba,"
             f"fade=t=in:st={t0:.2f}:d=0.45:alpha=1,"
             f"fade=t=out:st={t1:.2f}:d=0.55:alpha=1")
    # Deriva de entrada: el bloque llega desde la izquierda y se asienta
    slide = f"{plan['x']}-26*max(0,1-(t-{t0:.2f})/0.9)"
    pos = (f"x='{slide}':y={plan['y']}:"
           f"enable='between(t,{t0:.2f},{t1 + 0.6:.2f})'")
    args = ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}",
            "-i", str(plan["file"])]
    return args, chain, pos


def _overlay_filters(scene: dict, dur: float, cfg: dict, out_dir: Path) -> list[str]:
    """Filtros drawtext del rótulo de la escena (o [] si no lleva). El rótulo
    entra con fundido y una deriva sutil, se sostiene unos segundos y se va:
    nunca queda estático toda la escena."""
    overlay = scene.get("overlay")
    if not overlay and scene.get("on_screen_text"):
        # Proyectos antiguos: texto plano → se le da el diseño de 'dato'
        overlay = {"type": "dato", "text": scene["on_screen_text"], "kicker": ""}
    if not overlay or not cfg["video"].get("overlays", True):
        return []

    w, h = cfg["video"]["width"], cfg["video"]["height"]
    accent = "0x" + str(cfg["video"].get("overlay_accent", "E8C46B")).lstrip("#")
    lay = _overlay_layout(overlay["type"], w, h)

    sans = _brand_font(cfg, bold=True)
    if not sans:
        return []  # sin fuentes localizables se omite el rótulo, no se falla

    # La conclusión se compone como declaración tipográfica a gran tamaño
    if overlay["type"] == "conclusion":
        return _statement_filters(scene, overlay, dur, cfg, out_dir, accent)
    # El gancho de apertura (formatos cortos) tiene su propio lenguaje
    if overlay["type"] == "hook":
        return _hook_filters(scene, overlay, dur, cfg, out_dir, accent)
    # Los tipos con PLACA (locator, personaje, dato, lista) se componen como
    # imagen en _lower_third_setup: placa, filete y palabra de énfasis en
    # color, que drawtext no puede dar. Aquí solo queda el camino de
    # RESPALDO (si la composición falla, el rótulo sale como siempre).
    if _lower_third_plan(scene, cfg, out_dir) is not None:
        return []

    main_font = _brand_font(cfg, bold=True, serif_default=lay["serif"])

    text = overlay["text"].strip()
    kicker = (overlay.get("kicker") or "").strip()
    if lay["upper"]:
        text = _spaced(text)

    # Tiempos: SINCRONIZADO con la narración — el rótulo entra un instante
    # (gabela) antes de que el narrador diga esas palabras. Si no se localiza
    # el momento, entra poco después del corte. Se sostiene y se despide antes
    # del final; en escenas cortas se comprime.
    slow = lay["slow"]
    moment = _narration_moment(scene, dur)
    if moment is not None:
        t0 = max(0.25, min(moment - 0.35, dur - 2.2))
    else:
        t0 = 0.45 if dur > 4 else 0.25
    fi = 0.8 if slow else 0.5
    fo = 0.9 if slow else 0.6
    hold = 6.0 if slow else 4.8
    t1 = min(dur - 0.75, t0 + hold)
    if t1 < t0 + fi + 0.3:
        t1 = max(t0 + fi + 0.3, dur - 0.4)
    alpha = (f"if(lt(t,{t0:.2f}),0,"
             f"if(lt(t,{t0 + fi:.2f}),(t-{t0:.2f})/{fi:.2f},"
             f"if(lt(t,{t1:.2f}),1,max(0,1-(t-{t1:.2f})/{fo:.2f}))))")
    drift = f"max(0,1-(t-{t0:.2f})/0.9)"

    filters: list[str] = []
    kick_size = int(h * 0.026)
    gap = int(kick_size * 1.55)
    main_size = _fit(lay["size"], text)

    def pos(base_x: int, base_y: int, center: bool) -> tuple[str, str]:
        x = f"(w-text_w)/2" if center else str(base_x)
        y = str(base_y)
        if lay["drift"] == "x" and not center:
            x = f"{base_x}-26*{drift}"
        elif lay["drift"] == "y":
            y = f"{base_y}+16*{drift}"
        return x, y

    center = lay["align"] == "center"
    y_main = lay["y"] + (gap if kicker else 0)

    if kicker:
        kfile = out_dir / f"ostext_{scene['id']:03d}_kick.txt"
        kfile.write_text(_spaced(kicker)[:120], encoding="utf-8")
        kx, ky = pos(lay["x"], lay["y"], center)
        filters.append(_drawtext(sans, kfile, kick_size, accent, kx, ky, alpha))

    tfile = out_dir / f"ostext_{scene['id']:03d}_main.txt"
    tfile.write_text(text[:120], encoding="utf-8")
    mx, my = pos(lay["x"], y_main, center)
    filters.append(_drawtext(main_font, tfile, main_size, _brand_text_color(cfg),
                             mx, my, alpha))
    return filters


def _wrap_lines(text: str, max_chars: int = 13) -> list[str]:
    """Parte la frase en líneas cortas (1-3 palabras) para apilarlas en bloque,
    al estilo de los cierres tipográficos de documentales."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and len(cand) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _hook_filters(scene: dict, overlay: dict, dur: float, cfg: dict,
                  out_dir: Path, accent: str) -> list[str]:
    """GANCHO VISUAL DE APERTURA (formatos cortos): el texto grande de los
    primeros segundos, estilo TikTok/Reels — centrado, en bloque de líneas
    cortas, entrada INMEDIATA (el espectador decide en <2 s si se queda: aquí
    no hay fundidos lentos), un golpe de escala al aparecer y salida rápida
    cuando la narración avanza. La línea con la palabra clave va en el color
    de acento."""
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    bold = _brand_font(cfg, bold=True)
    if not bold:
        return []
    text_color = _brand_text_color(cfg)
    text = overlay["text"].strip()
    lines = _wrap_lines(text, max_chars=14)
    emphasis = _norm_txt(overlay.get("emphasis") or "")

    longest = max(len(ln) for ln in lines)
    size = min(int(h * 0.062), int(w * 0.86 / (longest * 0.60)),
               int(h * 0.34 / (len(lines) * 1.16)))
    lh = int(size * 1.16)
    block_h = len(lines) * lh
    # Bloque en el tercio superior: no pisa la cara del sujeto (centro) ni
    # los subtítulos quemados (abajo).
    y0 = max(int(h * 0.10), int(h * 0.30 - block_h / 2))

    # Tiempos: entra YA (0.12 s), se sostiene ~2/3 del gancho y sale rápido.
    t0, fi = 0.05, 0.12
    t1 = min(max(2.2, dur * 0.66), dur - 0.35)
    fo = 0.25
    filters: list[str] = []
    for i, line in enumerate(lines):
        lfile = out_dir / f"hook_{scene['id']:03d}_{i}.txt"
        lfile.write_text(line, encoding="utf-8")
        ti = t0 + i * 0.07  # cascada casi simultánea (golpe, no desfile)
        alpha = (f"if(lt(t,{ti:.2f}),0,if(lt(t,{ti + fi:.2f}),"
                 f"(t-{ti:.2f})/{fi:.2f},if(lt(t,{t1:.2f}),1,"
                 f"max(0,1-(t-{t1:.2f})/{fo:.2f}))))")
        # golpe de escala: la línea cae 14px y clava en su sitio al entrar
        y_expr = (f"{y0 + i * lh}-14*max(0,1-(t-{ti:.2f})/0.22)")
        color = accent if (emphasis and emphasis in _norm_txt(line)) else text_color
        filters.append(_drawtext(bold, lfile, size, color,
                                 "(w-text_w)/2", y_expr, alpha,
                                 borderw=4, bordercolor="black@0.85"))
    return filters


def _statement_filters(scene: dict, overlay: dict, dur: float, cfg: dict,
                       out_dir: Path, accent: str) -> list[str]:
    """Conclusión como declaración tipográfica: bloque de líneas apiladas en
    mayúsculas a la izquierda, mezcla de pesos (la línea con la palabra clave
    va en negrita), entrada escalonada línea a línea y salida conjunta."""
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    regular = _brand_font(cfg, bold=False) or _brand_font(cfg, bold=True)
    bold = _brand_font(cfg, bold=True)
    if not regular or not bold:
        return []
    text_color = _brand_text_color(cfg)

    text = overlay["text"].strip().upper()
    lines = _wrap_lines(text)
    emphasis = _norm_txt(overlay.get("emphasis") or "")
    if not emphasis:  # sin indicación: la palabra más larga carga el peso
        emphasis = _norm_txt(max(text.split(), key=len))

    # Cuerpo: grande, pero acotado por el ancho (línea más larga) y el alto
    longest = max(len(ln) for ln in lines)
    size = min(int(h * 0.085), int(w * 0.80 / (longest * 0.62)),
               int(h * 0.52 / (len(lines) * 1.18)))
    lh = int(size * 1.18)
    x0 = int(w * 0.08)
    kicker = (overlay.get("kicker") or "").strip()
    block_h = len(lines) * lh + (int(h * 0.05) if kicker else 0)
    y0 = max(int(h * 0.12), int((h - block_h) * 0.44))

    # Tiempos: sincronizado con la narración si se encuentra el momento; las
    # líneas entran escalonadas y el bloque se despide junto.
    moment = _narration_moment(scene, dur)
    stagger = 0.22
    lead_all = stagger * (len(lines) - 1)
    if moment is not None:
        t0 = max(0.3, min(moment - 0.35, dur - 2.6 - lead_all))
    else:
        t0 = max(0.3, min(0.6, dur - 2.6 - lead_all))
    fi, fo = 0.55, 0.9
    t1 = min(dur - 0.85, t0 + lead_all + 6.5)
    if t1 < t0 + lead_all + fi + 0.4:
        t1 = max(t0 + lead_all + fi + 0.4, dur - 0.4)

    filters: list[str] = []
    if kicker:
        kfile = out_dir / f"ostext_{scene['id']:03d}_kick.txt"
        kfile.write_text(_spaced(kicker)[:120], encoding="utf-8")
        alpha = (f"if(lt(t,{t0:.2f}),0,if(lt(t,{t0 + fi:.2f}),"
                 f"(t-{t0:.2f})/{fi:.2f},if(lt(t,{t1:.2f}),1,"
                 f"max(0,1-(t-{t1:.2f})/{fo:.2f}))))")
        filters.append(_drawtext(bold, kfile, int(h * 0.026), accent,
                                 str(x0), str(y0 - int(h * 0.05)), alpha))

    for i, line in enumerate(lines):
        lfile = out_dir / f"ostext_{scene['id']:03d}_l{i}.txt"
        lfile.write_text(line, encoding="utf-8")
        ti = t0 + i * stagger
        alpha = (f"if(lt(t,{ti:.2f}),0,if(lt(t,{ti + fi:.2f}),"
                 f"(t-{ti:.2f})/{fi:.2f},if(lt(t,{t1:.2f}),1,"
                 f"max(0,1-(t-{t1:.2f})/{fo:.2f}))))")
        x_expr = f"{x0}-30*max(0,1-(t-{ti:.2f})/0.9)"
        is_bold = emphasis and emphasis in _norm_txt(line)
        filters.append(_drawtext(bold if is_bold else regular, lfile, size,
                                 text_color, x_expr, str(y0 + i * lh), alpha))
    return filters


def _plan_transitions(scenes: list[dict], cfg: dict,
                      mode_override: str | None = None) -> list[dict]:
    """Decide, para cada escena, si entra/sale con fundido a negro y con qué
    duración — para que las transiciones VARÍEN en vez de ser todas iguales,
    sin perder el aire cinematográfico:

    - El video ABRE y CIERRA con un fundido (apertura/cierre desde/hacia negro).
    - Entre escenas la transición se decide por escena (campo 'transition') o,
      si no lo trae, por el ritmo de la historia: fundido al cambiar de sección
      o tras un respiro dramático; corte seco (sin transición) en el resto.
    - El fundido de una frontera es simétrico: si una escena entra con fundido,
      la anterior sale con fundido (breve caída a negro compartida).
    El modo global (video.transition) puede forzar 'fade' (todas) o 'none'
    (ninguna); 'auto' (por defecto) aplica la lógica anterior."""
    mode = mode_override or cfg.get("video", {}).get("transition", "auto")
    n = len(scenes)

    def wants_fade(i: int) -> bool:
        """¿La escena i entra con fundido (frontera con la i-1)?"""
        if i <= 0:
            return False
        if mode == "fade":
            return True
        if mode == "none":
            return False
        tr = scenes[i].get("transition")
        if tr in ("corte", "fundido"):
            return tr == "fundido"
        # Fallback sin criterio del modelo: fundido al cambiar de sección o
        # tras un respiro dramático de la escena anterior.
        if scenes[i - 1].get("pause_after"):
            return True
        return scenes[i].get("section") != scenes[i - 1].get("section")

    plans: list[dict] = []
    for i, s in enumerate(scenes):
        fin = fout = False
        fin_d = fout_d = FADE
        if mode != "none":
            if i == 0:
                fin, fin_d = True, FADE_OPEN
            if i == n - 1:
                fout, fout_d = True, FADE_OPEN
        if i > 0 and wants_fade(i):
            fin = True
            if scenes[i - 1].get("pause_after"):
                fin_d = FADE_SLOW
        if i < n - 1 and wants_fade(i + 1):
            fout = True
            if s.get("pause_after"):
                fout_d = FADE_SLOW
        plans.append({"fin": fin, "fin_d": round(fin_d, 3),
                      "fout": fout, "fout_d": round(fout_d, 3)})
    return plans


def _auto_interrupt(scene: dict, cfg: dict) -> str:
    """RUPTURA DE PATRÓN en la entrada de la escena (solo formatos cortos):
    micro-efecto que resetea la atención en cada corte, como en la edición
    nativa de TikTok/Reels. Determinista a partir de las señales que el
    director ya puso — sin costo ni llamadas extra:
      · 'flash' cuando la escena entra con un golpe (sfx boom),
      · 'zoom' (golpe de zoom que asienta) en cortes secos alternados,
      · '' (nada) en la escena 1 (el gancho manda), en los fundidos (el
        fundido YA es la transición) y en las escenas intermedias restantes
        (un efecto en cada corte cansa: el patrón se rompe, no se sustituye).
    """
    from ytstudio.catalog import is_short_form
    if not is_short_form(cfg):
        return ""
    if scene.get("id", 1) == 1 or scene.get("transition") == "fundido":
        return ""
    if scene.get("sfx") == "boom":
        return "flash"
    return "zoom" if scene.get("id", 0) % 2 == 0 else ""


def _interrupt_filter(kind: str, fps: int, w: int, h: int) -> str:
    """Filtro del micro-efecto de entrada. 'zoom': arranca 1.10x y asienta a
    1.0 en ~0.25 s (golpe de zoom clásico). 'flash': destello blanco de
    ~0.09 s. Ambos son ffmpeg puro: costo cero."""
    if kind == "zoom":
        k = max(2, round(0.25 * fps))
        z = f"if(lte(on,{k}),1.10-0.10*on/{k},1.001)"
        return (f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s={w}x{h}:fps={fps}")
    if kind == "flash":
        return "fade=t=in:st=0:d=0.09:color=white"
    return ""


def _split_filter(animation: str, frames: int, w: int, h: int,
                  fps: int) -> tuple[list[str], str]:
    """PANTALLA DIVIDIDA (dos imágenes a la vez, para comparaciones antes/
    después): arriba/abajo en formatos verticales, izquierda/derecha en
    horizontales y cuadrados. Cada mitad lleva su recorte de cobertura y su
    Ken Burns propio (mitades PARES para el submuestreo del códec), con una
    línea divisoria. Devuelve (filtros, etiqueta_final); las entradas 0 y 1
    son las dos imágenes."""
    vertical = h > w
    if vertical:
        ha = (h // 2) // 2 * 2
        hb = h - ha
        dims = [(w, ha), (w, hb)]
        stack, div = "vstack=inputs=2", f"drawbox=y={ha - 3}:h=6:t=fill"
    else:
        wa = (w // 2) // 2 * 2
        wb = w - wa
        dims = [(wa, h), (wb, h)]
        stack, div = "hstack=inputs=2", f"drawbox=x={wa - 3}:w=6:t=fill"
    filters = []
    for i, (dw, dh) in enumerate(dims):
        kb = _kenburns(animation if i == 0 else "zoom_out", frames, dw, dh, fps)
        filters.append(f"[{i}:v]{kb}[mit{i}]")
    filters.append(f"[mit0][mit1]{stack},{div}:c=black@0.85,setsar=1[vsplit]")
    return filters, "vsplit"


def _bubble_chain(idx: int, diameter: int) -> str:
    """Burbuja CIRCULAR para la persona que reacciona (sin pantalla verde):
    recorte cuadrado centrado, escala al diámetro y máscara circular por
    canal alfa — el look de las burbujas de reacción de TikTok/CapCut."""
    r = diameter // 2
    return (f"[{idx}:v]crop='min(iw,ih)':'min(iw,ih)',"
            f"scale={diameter}:{diameter},format=yuva444p,"
            f"geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
            f"a='if(lte((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{(r - 2) * (r - 2)}),"
            f"255,0)'")


def _chroma_chain(idx: int, target_h: int) -> str:
    """Recorte de PANTALLA VERDE de la persona que reacciona: chroma key +
    limpieza del reborde verde (despill), escalada a la franja inferior."""
    return (f"[{idx}:v]scale=-2:{target_h},format=yuva444p,"
            f"chromakey=0x00b140:0.28:0.06,despill=type=green")


def _reaction_inputs(scene: dict, project, cfg) -> tuple[list[str], str, str]:
    """(argumentos -i extra, cadena de filtro, posición del overlay) para la
    capa de REACCIÓN de esta escena, o ([], '', '') si no hay. Dos fuentes:
    · video de reacción del usuario (continuo: cada escena toma SU tramo,
      sincronizado con la línea de tiempo vía -ss),
    · clip de lipsync del personaje en modo burbuja (pip_video: ya viene
      cortado al tramo exacto de la escena)."""
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    if scene.get("pip_video"):
        src = project.path("broll", scene["pip_video"])
        d = int(min(w, h) * 0.34)
        margin = int(min(w, h) * 0.04)
        chain = _bubble_chain(1, d)  # el índice real lo fija _render_scene
        pos = f"{margin}:H-h-{margin + int(h * 0.09)}"
        return ["-i", str(src)], chain, pos
    # Capa opcional: no exige nada nuevo del proyecto (objetos antiguos o
    # parciales sin .get simplemente no llevan reacción).
    reaction = (project.get("reaction") if hasattr(project, "get") else None) or {}
    if reaction.get("file"):
        src = project.path("input", reaction["file"])
        if not src.exists():
            return [], "", ""
        offset = float(scene.get("_start") or 0.0)
        args = ["-ss", f"{offset:.3f}", "-i", str(src)]
        if reaction.get("chroma"):
            chain = _chroma_chain(1, int(h * 0.44))
            pos = "(W-w)/2:H-h"      # franja inferior, estilo pantalla verde
        else:
            d = int(min(w, h) * 0.30)
            margin = int(min(w, h) * 0.04)
            chain = _bubble_chain(1, d)
            pos = f"{margin}:H-h-{margin + int(h * 0.09)}"
        return args, chain, pos
    return [], "", ""


def _sticker_setup(scene: dict, dur: float, cfg: dict,
                   out_dir: Path) -> tuple[list[str], str, str, list[str]]:
    """Prepara el STICKER de la escena (imitación visual nativa, renderizada
    con PIL). Devuelve (args de entrada extra, cadena del sticker con [1:v]
    de marcador, posición del overlay, filtros posteriores — el número vivo
    del countdown). El sticker entra deslizándose con fundido tras el gancho,
    se sostiene y se despide antes del corte."""
    st = scene.get("sticker") or {}
    if not st.get("type"):
        return [], "", "", []
    from ytstudio.utils import stickers as stk
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    fps = cfg["video"]["fps"]
    card_w = int(min(w, h) * 0.56)
    png = out_dir / f"sticker_{scene['id']:03d}.png"
    post: list[str] = []
    t0 = 0.7 if scene.get("id", 1) != 1 else 1.6   # tras el gancho en escena 1
    t1 = max(t0 + 1.2, dur - 0.45)
    geom = None
    if st["type"] == "encuesta":
        stk.render_poll(st.get("text", ""), st.get("a", ""), st.get("b", ""),
                        card_w, png)
    elif st["type"] == "pregunta":
        stk.render_question(st.get("text", ""), card_w, png)
    else:  # countdown
        png, geom = png, None
        _, geom = stk.render_countdown(st.get("text", ""), card_w, png)
    # posición: centro-derecha, entre el gancho (arriba) y subtítulos (abajo)
    x_final = w - card_w - int(w * 0.05)
    y_final = int(h * 0.36)
    slide = f"{x_final}+40*max(0,1-(t-{t0:.2f})/0.35)"
    chain = (f"[1:v]format=rgba,"
             f"fade=t=in:st={t0:.2f}:d=0.28:alpha=1,"
             f"fade=t=out:st={t1:.2f}:d=0.3:alpha=1")
    pos = f"x='{slide}':y={y_final}:enable='between(t,{t0:.2f},{t1 + 0.35:.2f})'"
    args = ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}",
            "-i", str(png)]
    if st["type"] == "countdown" and geom:
        # número VIVO: cuenta segundos reales hacia el final del sticker
        font = find_font(bold=True)
        if font:
            end = t1
            num_x = x_final + card_w // 2
            num_y = y_final + geom["num_y"] + (geom["num_h"] - geom["size"]) // 2
            post.append(
                f"drawtext=fontfile='{filter_path(font)}':"
                f"text='%{{eif\\:max(1\\,ceil({end:.2f}-t))\\:d}}':"
                f"fontsize={geom['size']}:fontcolor=white:"
                f"x={num_x}-text_w/2:y={num_y}:"
                f"enable='between(t,{t0:.2f},{t1 + 0.3:.2f})'")
    return args, chain, pos, post


def _element_setup(scene: dict, dur: float, cfg: dict,
                   project) -> tuple[list[str], str, str]:
    """Prepara el INSERTO documental de la escena (tarjeta de archivo o cifra
    animada del documentalista). Devuelve (args de entrada, cadena con [1:v]
    de marcador, posición del overlay) o vacío. El inserto entra deslizándose
    en el instante de la mención (el['at'], anclado a la palabra real), se
    sostiene ~4s y se despide — arriba a la derecha, lejos de rótulos (abajo/
    centro) y subtítulos."""
    els = [e for e in (scene.get("elements") or []) if e.get("files")]
    if not els or not cfg["video"].get("elements", True):
        return [], "", ""
    el = els[0]
    eldir = project.path("broll", "elements")
    files = [eldir / f for f in el["files"]]
    if not all(f.exists() for f in files):
        return [], "", ""
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    at = float(el.get("at") or 0.9)
    t0 = min(max(0.35, at), max(0.35, dur - 2.4))
    t1 = min(dur - 0.35, t0 + 4.2)
    if t1 - t0 < 1.4:
        return [], "", ""   # escena demasiado corta para el inserto
    x_final = f"W-w-{int(w * 0.045)}"
    y = int(h * 0.16)
    slide = f"{x_final}+40*max(0,1-(t-{t0:.2f})/0.35)"
    pos = (f"x='{slide}':y={y}:eof_action=repeat:"
           f"enable='between(t,{t0:.2f},{t1 + 0.3:.2f})'")
    if el.get("mode") == "video":
        # CLIP de archivo: se escala al ancho de tarjeta y se enmarca como una
        # copia impresa (el mismo lenguaje que las fotos), en bucle si el clip
        # es más corto que la ventana del inserto.
        card_w = int(min(w, h) * 0.34)
        border = max(4, int(card_w * 0.035))
        args = ["-stream_loop", "-1", "-i", str(files[0]),
                "-t", f"{t1 + 0.4:.3f}"]
        chain = (f"[1:v]scale={card_w}:-2,"
                 f"pad=iw+{border * 2}:ih+{border * 2}:{border}:{border}:"
                 f"color=0xF8F6F0,fps={fps},format=rgba,"
                 f"setpts=PTS-STARTPTS+{t0:.3f}/TB,"
                 f"fade=t=in:st={t0:.2f}:d=0.3:alpha=1,"
                 f"fade=t=out:st={t1:.2f}:d=0.3:alpha=1")
        return args, chain, pos
    if el.get("mode") == "stat" and len(files) > 1:
        # Secuencia de CUENTA ASCENDENTE (14 cuadros a 12 fps ≈ 1.2s):
        # desplazada al instante de la mención; el último cuadro (el valor
        # real) se sostiene con eof_action=repeat.
        patt = str(files[0].parent / "f_%02d.png")
        args = ["-framerate", "12", "-i", patt]
        chain = (f"[1:v]format=rgba,setpts=PTS-STARTPTS+{t0:.3f}/TB,"
                 f"fade=t=in:st={t0:.2f}:d=0.2:alpha=1")
    else:
        args = ["-loop", "1", "-framerate", str(fps),
                "-t", f"{t1 + 0.4:.3f}", "-i", str(files[0])]
        chain = (f"[1:v]format=rgba,"
                 f"fade=t=in:st={t0:.2f}:d=0.3:alpha=1,"
                 f"fade=t=out:st={t1:.2f}:d=0.3:alpha=1")
    return args, chain, pos


def _render_scene(scene: dict, project, cfg, out: Path, fade: dict) -> None:
    """Renderiza la escena SOLO VIDEO (sin pista de audio). El audio del video
    completo es UNA pista continua (voz + música + SFX) que se mezcla al final
    sobre el cuerpo concatenado — meter audio por escena era la fuente del
    desfase: el contenedor mp4 corría los cuadros ~23 ms (1 cuadro AAC) en
    cada transición, y los cortes y rótulos llegaban tarde respecto a la voz
    y los subtítulos. Sin pista de audio, la concatenación es EXACTA al
    cuadro (verificado: 0.00 ms de error en 12 escenas)."""
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    dur = scene["duration"]
    frames = max(1, round(dur * fps))

    filters = []

    img_b = scene.get("broll_image_b")
    if scene.get("broll_video"):
        vid = project.path("broll", scene["broll_video"])
        try:
            vid_dur = probe_duration(vid)
        except Exception:
            vid_dur = None
        inputs = ["-i", str(vid)]
        # ENCUADRE DEL CLIP: si su aspecto es MUY distinto al del video (la
        # foto vertical de un personaje animada con lipsync sobre un 16:9), el
        # recorte de cobertura se comería la cara — se compone entero sobre su
        # propio fondo desenfocado, igual que las imágenes fijas.
        if _aspect_off(probe_video_size(vid), w, h) >= _BLURPAD_MISMATCH:
            fit = _contain_chain(w, h)
        else:
            fit = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                   f"crop={w}:{h}")
        stretch = ""
        if vid_dur and vid_dur < dur - 0.05:
            if scene.get("broll_source") == "lipsync":
                # LIPSYNC: jamás ralentizar — los labios dejarían de coincidir
                # con la voz (la cámara lenta desincronizaba justo las escenas
                # donde el personaje habla). Se congela el último cuadro: el
                # habla queda intacta y el resto de la escena lo sostiene.
                stretch = ("tpad=stop_mode=clone:stop_duration="
                           f"{dur - vid_dur + 0.2:.3f},")
            else:
                # Clip más corto que la escena → cámara lenta sutil hasta
                # cubrirla (nunca en bucle: el salto se nota y abarata).
                stretch = f"setpts={dur / vid_dur:.5f}*PTS,"
        filters.append(f"[0:v]{fit},{stretch}fps={fps},setsar=1[v0]")
        label = "v0"
    elif (scene.get("layout") == "dividida" and img_b
          and (project.path("broll", img_b)).exists()):
        # PANTALLA DIVIDIDA: dos imágenes (entradas 0 y 1) compuestas a la vez
        img_path = project.path("broll", scene["broll_image"])
        inputs = ["-i", str(img_path), "-i", str(project.path("broll", img_b))]
        sp, label = _split_filter(scene["animation"], frames, w, h, fps)
        filters.extend(sp)
    else:
        img_path = project.path("broll", scene["broll_image"])
        inputs = ["-i", str(img_path)]
        filters.append(f"[0:v]{_still_filter(img_path, scene['animation'], frames, w, h, fps)}[v0]")
        label = "v0"

    # Capa de REACCIÓN (video del usuario o burbuja del personaje): sobre el
    # visual base, debajo de rupturas y rótulos.
    r_args, r_chain, r_pos = _reaction_inputs(scene, project, cfg)
    if r_args:
        r_idx = len([a for a in inputs if a == "-i"])  # índice real de entrada
        inputs += r_args
        r_chain = r_chain.replace("[1:v]", f"[{r_idx}:v]", 1)
        filters.append(f"{r_chain}[rx]")
        filters.append(f"[{label}][rx]overlay={r_pos}:eof_action=pass[vr]")
        label = "vr"

    # Ruptura de patrón en la entrada (formatos cortos): ANTES de los rótulos,
    # para que el golpe de zoom no mueva el texto.
    intr = _interrupt_filter(_auto_interrupt(scene, cfg), fps, w, h)
    if intr:
        filters.append(f"[{label}]{intr}[vi]")
        label = "vi"
    for i, dt in enumerate(_overlay_filters(scene, dur, cfg, out.parent), start=1):
        filters.append(f"[{label}]{dt}[t{i}]")
        label = f"t{i}"
    # RÓTULO CON PLACA (locator, personaje, dato, lista): imagen compuesta con
    # placa, filete de acento y palabra de énfasis en color.
    l_args, l_chain, l_pos = _lower_third_setup(scene, dur, cfg, out.parent)
    if l_args:
        l_idx = len([a for a in inputs if a == "-i"])
        inputs += l_args
        filters.append(l_chain.replace("[1:v]", f"[{l_idx}:v]", 1) + "[lt]")
        filters.append(f"[{label}][lt]overlay={l_pos}[vlt]")
        label = "vlt"
    # STICKER nativo animado (después de la ruptura: los stickers de la app
    # no se zoomean con el contenido — así parece puesto por la plataforma)
    s_args, s_chain, s_pos, s_post = _sticker_setup(scene, dur, cfg, out.parent)
    if s_args:
        s_idx = len([a for a in inputs if a == "-i"])
        inputs += s_args
        filters.append(s_chain.replace("[1:v]", f"[{s_idx}:v]", 1) + "[stk]")
        filters.append(f"[{label}][stk]overlay={s_pos}[vsk]")
        label = "vsk"
        for j, pf in enumerate(s_post):
            filters.append(f"[{label}]{pf}[vsn{j}]")
            label = f"vsn{j}"
    # INSERTO documental (tarjeta de archivo / cifra animada) en el instante
    # de la mención — encima del visual, debajo de los fundidos de escena.
    e_args, e_chain, e_pos = _element_setup(scene, dur, cfg, project)
    if e_args:
        e_idx = len([a for a in inputs if a == "-i"])
        inputs += e_args
        filters.append(e_chain.replace("[1:v]", f"[{e_idx}:v]", 1) + "[elc]")
        filters.append(f"[{label}][elc]overlay={e_pos}[vel]")
        label = "vel"
    # Transición variable por escena (fundido de entrada/salida independientes)
    segs = []
    if fade.get("fin"):
        segs.append(f"fade=t=in:st=0:d={fade['fin_d']}")
    if fade.get("fout"):
        fo_d = fade["fout_d"]
        segs.append(f"fade=t=out:st={max(0.0, dur - fo_d):.3f}:d={fo_d}")
    if segs:
        filters.append(f"[{label}]{','.join(segs)}[v2]")
        label = "v2"

    # -frames:v EXACTO: cada escena mide exactamente los cuadros que el mapa
    # de tiempos asume (sin -t redondeado que podía colar un cuadro de más).
    run_ffmpeg([
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{label}]", "-an",
        "-frames:v", str(frames),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        str(out),
    ], f"escena {scene['id']}")


# ---------------------------------------------------------------------------
# Banda sonora: envolvente de intensidad + efectos incidentales
# ---------------------------------------------------------------------------

def _thin_points(pts: list[tuple[float, float]], limit: int = 140) -> list:
    """Reduce los puntos de la envolvente: quita los tramos planos y, si aún
    hay demasiados (videos muy largos), muestrea — la expresión de ffmpeg se
    evalúa anidada y no conviene que crezca sin límite."""
    if len(pts) > 2:
        kept = [pts[0]]
        for prev, cur, nxt in zip(pts, pts[1:], pts[2:]):
            if abs(cur[1] - prev[1]) > 0.2 or abs(cur[1] - nxt[1]) > 0.2:
                kept.append(cur)
        kept.append(pts[-1])
        pts = kept
    if len(pts) > limit:
        step = len(pts) / (limit - 1)
        pts = [pts[min(len(pts) - 1, round(i * step))] for i in range(limit)]
    return pts


def _music_envelope(scenes: list[dict], music_db: float, swing_db: float) -> str:
    """Expresión de volumen (multiplicador lineal) que sigue la intensidad
    musical de cada escena, interpolando entre los centros de escena."""
    t = 0.0
    pts: list[tuple[float, float]] = []
    for s in scenes:
        dur = float(s["duration"])
        intensity = float(s.get("music_intensity", 0.55))
        pts.append((t + dur / 2, music_db + (intensity - 0.6) * swing_db))
        t += dur
    pts = _thin_points(pts)
    amps = [(tk, 10 ** (db / 20)) for tk, db in pts]
    if len(amps) == 1:
        return f"{amps[0][1]:.4f}"
    expr = f"{amps[-1][1]:.4f}"
    for (t0, a0), (t1, a1) in reversed(list(zip(amps, amps[1:]))):
        seg = f"{a0:.4f}+{a1 - a0:.4f}*(t-{t0:.2f})/{t1 - t0:.2f}"
        expr = f"if(lt(t,{t1:.2f}),{seg},{expr})"
    return f"if(lt(t,{amps[0][0]:.2f}),{amps[0][1]:.4f},{expr})"


def _sfx_graph(scenes: list[dict], cfg: dict, work_dir: Path,
               first_input: int) -> tuple[list[str], list[str], str | None]:
    """Pista de efectos incidentales. Devuelve (args de inputs, filtros,
    etiqueta de salida o None). Cada tipo de efecto es UN input reutilizado
    con asplit + adelay por aparición."""
    if not cfg["audio"].get("sfx", True):
        return [], [], None
    from ytstudio.utils.sfx import SFX_SPECS, ensure_sfx, insert_kind

    # ACENTO DE LOS INSERTOS: paleta elegida en ⚙ Configuración → Audio. En
    # 'auto' manda el estilo del video (un documental histórico suena a papel
    # de archivo, no al 'pop' de una app), y dentro de la paleta cada tipo de
    # inserto — foto, cifra, mapa — tiene su propio sonido.
    palette = str(cfg["audio"].get("element_sfx", "auto") or "auto").strip()
    if palette in ("", "auto"):
        from ytstudio.catalog import get_style_preset
        palette = (get_style_preset(cfg) or {}).get("insert_sfx") or "archivo"

    events: list[tuple[str, float]] = []  # (tipo, inicio en s)
    t = 0.0
    for s in scenes:
        kind = s.get("sfx")
        if kind in SFX_SPECS and t > 0.5:  # sin efecto en el arranque del video
            start = max(0.0, t - SFX_SPECS[kind]["before_cut"])
            events.append((kind, start))
        # los INSERTOS documentales entran con su acento en la mención
        for el in (s.get("elements") or []):
            if not (el.get("files") and el.get("at") is not None):
                continue
            k = insert_kind(el, palette)
            if k in SFX_SPECS:
                # los acentos que CRECEN (aire, cuerda) arrancan antes para
                # que su cima caiga justo cuando entra la tarjeta
                events.append((k, max(0.0, t + float(el["at"])
                                      - SFX_SPECS[k]["before_cut"])))
        t += float(s["duration"])
    if not events:
        return [], [], None

    kinds = sorted({k for k, _ in events})
    paths = {k: ensure_sfx(k, work_dir) for k in kinds}
    idx = {k: first_input + i for i, k in enumerate(kinds)}
    args: list[str] = []
    for k in kinds:
        args += ["-i", str(paths[k])]

    sfx_db = cfg["audio"].get("sfx_db", -18)
    filters: list[str] = []
    labels: list[str] = []
    counts = {k: sum(1 for kk, _ in events if kk == k) for k in kinds}
    for k in kinds:
        outs = "".join(f"[{k}{j}]" for j in range(counts[k]))
        pre = (f"[{idx[k]}:a]atrim=0:4,aresample=44100,"
               f"aformat=channel_layouts=stereo,volume={sfx_db}dB")
        filters.append(f"{pre},asplit={counts[k]}{outs}" if counts[k] > 1
                       else f"{pre}[{k}0]")
    seen = {k: 0 for k in kinds}
    for k, start in events:
        j = seen[k]
        seen[k] += 1
        ms = int(round(start * 1000))
        filters.append(f"[{k}{j}]adelay={ms}|{ms}[d{k}{j}]")
        labels.append(f"[d{k}{j}]")
    if len(labels) == 1:
        filters.append(f"{labels[0]}anull[sfx]")
    else:
        filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:"
                       "duration=longest:normalize=0[sfx]")
    return args, filters, "sfx"


def _ambience_input(project, cfg, total: float,
                    idx: int) -> tuple[list[str], str, str | None]:
    """(args de entrada, filtro, etiqueta) de la CAMA DE AMBIENTE, o vacío si
    no hay o está desactivada.

    Va por debajo de todo: entra con un fundido, se acota a la duración exacta
    del video y muere con él. Al nivel de `ambience_db` (−30 dB por defecto)
    no compite con la voz — solo llena el fondo que antes estaba vacío."""
    amb_path = project.path("music", "ambiente.wav")
    if not cfg["audio"].get("ambience", True) or not amb_path.exists():
        return [], "", None
    amb_db = float(cfg["audio"].get("ambience_db", -30))
    fade = min(3.0, max(0.5, total * 0.02))
    filt = (f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,"
            f"atrim=0:{total:.3f},apad=whole_dur={total:.3f},"
            f"volume={amb_db}dB,afade=t=in:st=0:d={fade:.2f},"
            f"afade=t=out:st={max(0.0, total - fade):.2f}:d={fade:.2f}[amb]")
    return ["-i", str(amb_path)], filt, "amb"


def _render_signature(scenes, plans, cfg, project) -> str:
    """Huella de todo lo que afecta al render de cada escena (imagen/video,
    animación, duración, rótulo, transición y ajustes de video). Si cambia, se
    re-renderizan las escenas aunque el .mp4 exista — así reajustar las
    transiciones (o los rótulos) SÍ se ve al reanudar el montaje."""
    v = cfg.get("video", {})

    def stamp(name):
        # El material puede regenerarse CON EL MISMO NOMBRE (p.ej. cuando el
        # prompt de la escena cambió): el nombre solo no basta — se firma
        # también tamaño y fecha del archivo para re-renderizar la escena.
        if not name:
            return None
        try:
            st = project.path("broll", name).stat()
            return [st.st_size, int(st.st_mtime)]
        except OSError:
            return None

    payload = {
        # Versión del formato de escena: subirla invalida TODAS las escenas
        # cacheadas (v2 = escenas SOLO VIDEO; las viejas llevaban pista de
        # audio, que desfasaba las transiciones).
        "fmt": 2,
        "video": {k: v.get(k) for k in
                  ("width", "height", "fps", "transition", "overlays",
                   "overlay_accent", "overlay_style", "overlay_plate",
                   "overlay_text_color", "overlay_font_family")},
        "scenes": [{
            "id": s["id"], "img": s.get("broll_image"),
            "vid": s.get("broll_video"), "anim": s.get("animation"),
            "dur": s.get("duration"), "overlay": s.get("overlay"),
            "ost": s.get("on_screen_text"), "at": s.get("overlay_at"),
            "off": s.get("vo_offset"), "fade": p,
            "layout": s.get("layout"), "imgb": s.get("broll_image_b"),
            "pip": s.get("pip_video"), "sfx": s.get("sfx"),
            "trans": s.get("transition"), "sticker": s.get("sticker"),
            "elements": s.get("elements"),
            "src": [stamp(s.get("broll_image")), stamp(s.get("broll_video")),
                    stamp(s.get("broll_image_b")), stamp(s.get("pip_video"))],
        } for s, p in zip(scenes, plans)],
        # La capa de reacción afecta TODAS las escenas (archivo y modo)
        "reaction": project.get("reaction"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def run(project, cfg) -> None:
    require_ffmpeg()
    scenes = load_scenes(project)
    final_dir = project.path("final")
    scenes_dir = final_dir / "escenas"
    scenes_dir.mkdir(exist_ok=True)

    style_transition = None
    if project.get("style_id"):
        from ytstudio.library import load_style
        style_transition = (load_style(project.get("style_id")) or {}).get(
            "transition")
    plans = _plan_transitions(scenes, cfg, style_transition)

    # BRANDING DE RÓTULOS del canal/estilo (v0.41.0): familia tipográfica y
    # colores. Se resuelve UNA vez aquí y se SUPERPONE (solo lo que el estilo
    # fija de verdad) en una copia local de cfg — el resto del render
    # (overlay/hook/statement) sigue leyendo cfg["video"] como siempre. Sin
    # estilo, o con un estilo sin branding propio, cfg queda intacto: mismo
    # comportamiento que antes de v0.41.0 (incluida tu propia personalización
    # global de overlay_accent, que un estilo sin colores propios no pisa).
    import copy as _copy
    from ytstudio.library import branding_overrides_for_project
    cfg = _copy.deepcopy(cfg)
    cfg.setdefault("video", {}).update(branding_overrides_for_project(project))

    # Corrección del LAZO DE SINCRONÍA (medida por la fase de subtítulos
    # sobre la pista de voz real): los rótulos se corren lo mismo que los
    # subtítulos, para que aparezcan cuando la palabra SUENA. Solo en
    # memoria — entra en la firma de render, así que re-renderiza lo justo.
    shift = float(project.get("sync_shift") or 0.0)
    if abs(shift) > 0.001:
        for s in scenes:
            if s.get("overlay_at") is not None:
                s["overlay_at"] = round(
                    min(max(0.0, float(s["overlay_at"]) + shift),
                        max(0.1, float(s["duration"]) - 0.5)), 3)

    # Si algo visual cambió desde el último render, limpiar las escenas
    # cacheadas (si no, un reajuste de transiciones/rótulos no se vería).
    sig = _render_signature(scenes, plans, cfg, project)
    if project.get("assembly_sig") != sig:
        for old in scenes_dir.glob("scene_*.mp4"):
            old.unlink(missing_ok=True)
        project.set("assembly_sig", sig)

    # 1) Render de cada escena — EN PARALELO (reanudable). Cada escena es un
    #    ffmpeg independiente; 2-3 a la vez aprovechan los núcleos del CPU.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ytstudio.progress import notify

    # Inicio de cada escena en la línea de tiempo: el video de REACCIÓN es
    # continuo y cada escena toma exactamente SU tramo (sincronizado).
    t_acc = 0.0
    for s in scenes:
        s["_start"] = round(t_acc, 3)
        t_acc += float(s.get("duration") or 0)

    jobs = [(s, p) for s, p in zip(scenes, plans)
            if not (scenes_dir / f"scene_{s['id']:03d}.mp4").exists()]
    workers = max(1, int(cfg.get("performance", {}).get("parallel_render", 2)))
    if jobs:
        notify(f"🎬 Montando {len(jobs)} escenas ({workers} en paralelo)…")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_render_scene, s, project, cfg,
                            scenes_dir / f"scene_{s['id']:03d}.mp4", p): s
                for s, p in jobs}
            done = 0
            for future in as_completed(futures):
                future.result()  # un fallo detiene la fase (reanudable)
                done += 1
                if done % 5 == 0 or done == len(jobs):
                    notify(f"🎬 Escena {done}/{len(jobs)} montada")

    # 2) Concatenación de escenas (rutas con '/' también en Windows). Las
    #    escenas son SOLO VIDEO: la concatenación es exacta al cuadro (con
    #    pista de audio por escena, el contenedor corría los cuadros ~23 ms
    #    por transición y los cortes/rótulos llegaban tarde respecto a la voz).
    concat_list = scenes_dir / "list.txt"
    scene_files = [(scenes_dir / "scene_{:03d}.mp4".format(s["id"])).resolve()
                   for s in scenes]
    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in scene_files) + "\n",
        encoding="utf-8")
    body = final_dir / "cuerpo.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", str(body)], "concatenación")

    # AUTOCOMPROBACIÓN: el cuerpo debe durar EXACTAMENTE la suma de escenas
    # (±1 cuadro). Si no, algo desalinearía voz/subtítulos — mejor un aviso
    # claro ahora que un video desfasado.
    fps = float(cfg["video"].get("fps", 24))
    expected = sum(max(1, round(float(s["duration"]) * fps)) for s in scenes) / fps
    body_dur = probe_duration(body)
    if abs(body_dur - expected) > 1.5 / fps:
        from ytstudio import eventlog
        msg = (f"Autocomprobación del montaje: el cuerpo mide {body_dur:.3f}s "
               f"y las escenas suman {expected:.3f}s (deriva "
               f"{1000 * (body_dur - expected):+.0f} ms). Reporta este aviso — "
               "indica un problema de sincronía en la concatenación.")
        project.add_warning(msg)
        eventlog.log("error", msg, project=getattr(project, "slug", None),
                     phase="assembly")

    # 3) Mezcla de audio (envolvente de intensidad + ducking + SFX + loudness)
    #    y subtítulos. El grafo va en un archivo (-filter_complex_script):
    #    en videos largos supera el límite de línea de comandos de Windows.
    music = project.path("music", project.get("music_file"))
    music_db = cfg["audio"].get("music_db", -21)
    swing_db = cfg["audio"].get("intensity_db", 8)
    duck = cfg["audio"].get("duck", True)
    burn = cfg["video"].get("burn_subtitles", False)

    total = probe_duration(body)

    # Voz: SIEMPRE una única pista continua (narration_timeline.wav) — con
    # narración propia es tu grabación con respiros; con TTS son los clips
    # colocados en el inicio exacto de cada escena. Las escenas van SIN audio
    # (el audio por escena desfasaba las transiciones), así que esta pista es
    # la única fuente de la voz.
    narration = project.get("narration")
    use_user_voice = bool(narration and any("audio_start" in s for s in scenes))

    sfx_args, sfx_filters, sfx_label = _sfx_graph(scenes, cfg, final_dir,
                                                  first_input=2)
    args = ["-i", str(body), "-i", str(music), *sfx_args]
    afilters: list[str] = []

    tl = project.get("voice_timeline")
    tl_path = project.path("voiceover", tl) if tl else None
    if not (tl_path and tl_path.exists()):
        if use_user_voice and narration.get("file") and \
                project.path("input", narration["file"]).exists():
            tl_path = project.path("input", narration["file"])  # respaldo
        else:
            raise RuntimeError(
                "Falta la pista continua de voz (narration_timeline.wav) — "
                "este proyecto se generó con una versión anterior. Usa "
                "«Rehacer desde Voz» para reconstruirla.")
    notify("🎙 Voz: pista única continua para todo el video "
           + ("(tu narración con respiros)." if use_user_voice
              else "(clips TTS en los inicios exactos de escena)."))
    narr_idx = 2 + (len(sfx_args) // 2)
    args += ["-i", str(tl_path)]
    base = (f"[{narr_idx}:a]aresample=44100,aformat=channel_layouts=stereo,"
            f"atrim=0:{total:.3f},apad=whole_dur={total:.3f}")
    if duck:  # se consume 2 veces (sidechain + mezcla) → asplit obligatorio
        afilters.append(f"{base},asplit=2[vsc][vmx]")
        voice_sc, voice_mx = "vsc", "vmx"
    else:
        afilters.append(f"{base}[vmx]")
        voice_sc, voice_mx = None, "vmx"
    next_idx = narr_idx + 1

    # CAMA DE AMBIENTE (v0.48.0): por debajo de todo, da lugar a cada tramo.
    amb_args, amb_filter, amb_label = _ambience_input(project, cfg, total,
                                                      next_idx)
    if amb_args:
        args += amb_args
        afilters.append(amb_filter)
        next_idx += 1

    envelope = _music_envelope(scenes, music_db, swing_db)
    afilters.append(f"[1:a]volume='{envelope}':eval=frame[m]")
    if duck:
        afilters.append(f"[m][{voice_sc}]sidechaincompress=threshold=0.05:"
                        "ratio=8:attack=80:release=400[md]")
        music_label = "md"
    else:
        music_label = "m"

    afilters += sfx_filters
    mix_in = (f"[{voice_mx}][{music_label}]"
              + (f"[{sfx_label}]" if sfx_label else "")
              + (f"[{amb_label}]" if amb_label else ""))
    n_mix = 2 + (1 if sfx_label else 0) + (1 if amb_label else 0)
    # Cierre: fundido LARGO del audio (mínimo 2.5s) que muere EXACTAMENTE con
    # la imagen — un fundido corto que arrancaba al acabar la voz sonaba a
    # «la música termina antes que el video, y de golpe».
    end_fade = float(cfg["audio"].get("end_fade", 1.5))
    fade_d = max(end_fade, 2.5) if end_fade > 0 else 0.0
    fade = (f",afade=t=out:st={max(0.0, total - fade_d):.2f}:d={fade_d:.2f}"
            if fade_d > 0 else "")
    # LOUDNESS: ganancia fija de acabado + limitador de picos (alimiter).
    # ¡NO se usa el loudnorm de una sola pasada! Su normalización DINÁMICA
    # reacciona a las caídas de volumen —una pausa dramática de la voz, un
    # «silencio estratégico» de la música— SUBIENDO la ganancia y frenándola
    # en seco, y hunde la mezcla ENTERA (voz incluida) a casi-silencio justo
    # en esa escena. ERA la causa del «recorte» que se oía siempre en el
    # mismo punto: se reprodujo y midió con el audio real (la voz caía a −90 dB
    # con loudnorm, y quedaba intacta sin él). La voz ya viene normalizada
    # (clean_narration I=−16); una ganancia fija + alimiter da una loudness
    # estable (~−14 LUFS, apta para YouTube) SIN tocar la dinámica de la voz.
    final_gain = float(cfg["audio"].get("final_gain_db", 1.0))
    tp_limit = float(cfg["audio"].get("final_limit", 0.9))
    afilters.append(f"{mix_in}amix=inputs={n_mix}:duration=first:normalize=0,"
                    f"volume={final_gain}dB,alimiter=limit={tp_limit}{fade}[aout]")

    output = final_dir / "video_final.mp4"
    graph = list(afilters)
    sub_input = next_idx

    if burn:
        ass = project.path("subtitles", "subtitulos.ass")
        graph.append(f"[0:v]ass='{filter_path(ass)}'[vout]")
        maps = ["-map", "[vout]", "-map", "[aout]"]
        codecs = ["-c:v", "libx264", "-preset", "medium", "-crf", "19",
                  "-pix_fmt", "yuv420p"]
    else:
        srt = project.path("subtitles", "subtitulos.srt")
        lang = _LANG3.get(cfg.get("language", "es"), "und")
        args += ["-i", str(srt)]
        maps = ["-map", "0:v", "-map", "[aout]", "-map", f"{sub_input}:0"]
        codecs = ["-c:v", "copy", "-c:s", "mov_text",
                  "-metadata:s:s:0", f"language={lang}"]

    script = final_dir / "mezcla.filters"
    script.write_text(";\n".join(graph), encoding="utf-8")
    # -t DURO al total del cuerpo: ningún stream (video, audio, subtítulos)
    # puede exceder la duración del video — defensa definitiva contra
    # cualquier entrada o muxer que intente estirar el resultado.
    run_ffmpeg([*args, "-filter_complex_script", str(script), *maps, *codecs,
                "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}",
                "-movflags", "+faststart",
                str(output)], "mezcla final")

    # AUTOCOMPROBACIÓN FINAL: el video terminado debe durar lo que el cuerpo.
    # SIEMPRE se registra el diagnóstico por stream en el 🧾 Log de eventos —
    # si algo deriva, el log identifica el stream exacto (video, audio o
    # subtítulos) con sus duraciones medidas, no una cifra global ambigua.
    from ytstudio import eventlog
    slug = getattr(project, "slug", None)
    try:
        diag = _stream_durations(output)
        tl_dur = probe_duration(tl_path)
        eventlog.log("info",
                     f"Diagnóstico de sincronía — cuerpo:{total:.3f}s "
                     f"voz:{tl_dur:.3f}s "
                     + " ".join(f"{k}:{v:.3f}s" for k, v in diag.items()),
                     project=slug, phase="assembly")
        final_dur = max(diag.values()) if diag else probe_duration(output)
        if abs(final_dur - total) > 0.25:
            msg = (f"Autocomprobación final: hay un stream de "
                   f"{final_dur:.2f}s y se esperaban {total:.2f}s "
                   f"({' '.join(f'{k}={v:.2f}s' for k, v in diag.items())}). "
                   "Reporta este aviso con el Log de eventos.")
            project.add_warning(msg)
            eventlog.log("error", msg, project=slug, phase="assembly")
            for s in scenes:
                try:
                    sp = scenes_dir / f"scene_{s['id']:03d}.mp4"
                    eventlog.log("info",
                                 f"  escena {s['id']}: mp4={probe_duration(sp):.3f}s "
                                 f"esperada={float(s['duration']):.3f}s",
                                 project=slug, phase="assembly")
                except Exception:
                    pass
        else:
            notify(f"✅ Sincronía verificada: video {final_dur:.2f}s = "
                   f"escenas {total:.2f}s (una sola línea de tiempo).")
    except Exception:
        pass

    # MEDICIÓN DE CONTENIDO (no de contenedor): ¿los subtítulos caen donde la
    # voz SUENA de verdad? Se comparan los arranques de habla reales de la
    # pista de voz (fin de cada silencio medido) contra el inicio del
    # subtítulo más cercano. La mediana firmada va SIEMPRE al Log de eventos:
    # convierte el «se siente desfasado» en un número con signo.
    try:
        _measure_content_sync(project, tl_path)
    except Exception:
        pass
    project.set("final_video", str(output))


def _measure_content_sync(project, tl_path: Path) -> None:
    import re as _re
    from ytstudio import eventlog
    from ytstudio.utils.media import detect_silences
    srt = project.path("subtitles", "subtitulos.srt")
    if not srt.exists():
        return
    cue_starts = []
    for m in _re.finditer(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) -->",
                          srt.read_text(encoding="utf-8")):
        h, mi, s, ms = (int(x) for x in m.groups())
        cue_starts.append(h * 3600 + mi * 60 + s + ms / 1000)
    if not cue_starts:
        return
    onsets = [e for _, e in detect_silences(tl_path, min_d=0.3)]
    tl_len = probe_duration(tl_path)
    onsets = [o for o in onsets if o < tl_len - 0.5]  # fuera el fin de archivo
    diffs = []
    for o in onsets:
        near = min(cue_starts, key=lambda c: abs(c - o))
        if abs(near - o) <= 1.5:
            diffs.append(near - o)
    if len(diffs) < 2:
        return
    diffs.sort()
    med = diffs[len(diffs) // 2]
    slug = getattr(project, "slug", None)
    eventlog.log("info",
                 f"Contenido voz↔subtítulos: desfase mediano "
                 f"{'+' if med > 0 else ''}{med * 1000:.0f} ms "
                 f"(medido en {len(diffs)} arranques de habla; + = subtítulo "
                 "tarde, − = subtítulo adelantado).",
                 project=slug, phase="assembly")
    if abs(med) > 0.4:
        project.add_warning(
            f"Los subtítulos están {'retrasados' if med > 0 else 'adelantados'} "
            f"~{abs(med) * 1000:.0f} ms respecto a tu voz real. Usa «Rehacer "
            "desde Análisis» para re-transcribir con calibración automática.")


def _stream_durations(path: Path) -> dict:
    """Duración medida de CADA stream del archivo (video/audio/subtítulos) —
    la duración 'global' de un mp4 es la del stream más largo y esconde cuál
    se estiró."""
    import json as _json
    import subprocess
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,duration", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    out: dict = {}
    try:
        for i, s in enumerate(_json.loads(r.stdout).get("streams", [])):
            key = f"{s.get('codec_type', 's')}{i}"
            try:
                out[key] = float(s.get("duration") or 0)
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    return out
