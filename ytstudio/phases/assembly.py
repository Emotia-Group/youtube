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
                                  require_ffmpeg, run_ffmpeg)

FADE = 0.3        # fundido corto (corte suave entre escenas)
FADE_OPEN = 0.6   # apertura y cierre del video (un poco más largo)
FADE_SLOW = 0.55  # fundido dramático (tras un respiro/pausa)

# Códigos ISO-639-2 para la pista de subtítulos del mp4
_LANG3 = {"es": "spa", "en": "eng", "pt": "por", "fr": "fra", "de": "deu",
          "it": "ita", "ja": "jpn", "ko": "kor", "zh": "chi", "ru": "rus"}


def _kenburns(animation: str, frames: int, w: int, h: int, fps: int) -> str:
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
    # Sobreescala a 2560 (no 3840): con zoom máximo 1.14 sobre salida 1920
    # bastan ~2200 px — las imágenes fuente son de 1536, así que 3840 solo
    # añadía cómputo sin ganar detalle. Render ~2x más rápido, misma calidad.
    return (f"scale=2560:-2,setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps}")


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
    }
    return layouts.get(otype, layouts["dato"])


def _drawtext(font: str, textfile: Path, size: int, color: str,
              x_expr: str, y_expr: str, alpha: str, extra: str = "") -> str:
    return (f"drawtext=fontfile='{filter_path(font)}':"
            f"textfile='{filter_path(textfile)}':expansion=none:"
            f"fontsize={size}:fontcolor={color}:"
            f"borderw=2:bordercolor=black@0.35:"
            f"shadowcolor=black@0.6:shadowx=0:shadowy=2:"
            f"x='{x_expr}':y='{y_expr}':alpha='{alpha}'{extra}")


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

    sans = find_font(bold=True)
    if not sans:
        return []  # sin fuentes localizables se omite el rótulo, no se falla

    # La conclusión se compone como declaración tipográfica a gran tamaño
    if overlay["type"] == "conclusion":
        return _statement_filters(scene, overlay, dur, cfg, out_dir, accent)

    main_font = find_font(bold=True, serif=True) if lay["serif"] else sans

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
    filters.append(_drawtext(main_font, tfile, main_size, "white", mx, my, alpha))
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


def _statement_filters(scene: dict, overlay: dict, dur: float, cfg: dict,
                       out_dir: Path, accent: str) -> list[str]:
    """Conclusión como declaración tipográfica: bloque de líneas apiladas en
    mayúsculas a la izquierda, mezcla de pesos (la línea con la palabra clave
    va en negrita), entrada escalonada línea a línea y salida conjunta."""
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    regular = find_font(bold=False) or find_font(bold=True)
    bold = find_font(bold=True)
    if not regular or not bold:
        return []

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
                                 "white", x_expr, str(y0 + i * lh), alpha))
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


def _render_scene(scene: dict, project, cfg, out: Path, fade: dict) -> None:
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    dur = scene["duration"]
    frames = max(1, round(dur * fps))

    vo = project.path("voiceover", scene["vo_file"])
    filters = []

    if scene.get("broll_video"):
        vid = project.path("broll", scene["broll_video"])
        try:
            vid_dur = probe_duration(vid)
        except Exception:
            vid_dur = None
        if vid_dur and vid_dur < dur - 0.05:
            # Clip más corto que la escena → cámara lenta sutil hasta cubrirla
            # (nunca repetir el clip en bucle: el salto se nota y abarata).
            inputs = ["-i", str(vid)]
            factor = dur / vid_dur
            filters.append(
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setpts={factor:.5f}*PTS,fps={fps},setsar=1[v0]")
        else:
            inputs = ["-i", str(vid)]
            filters.append(
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},fps={fps},setsar=1[v0]")
    else:
        inputs = ["-i", str(project.path("broll", scene["broll_image"]))]
        filters.append(f"[0:v]{_kenburns(scene['animation'], frames, w, h, fps)}[v0]")

    label = "v0"
    for i, dt in enumerate(_overlay_filters(scene, dur, cfg, out.parent), start=1):
        filters.append(f"[{label}]{dt}[t{i}]")
        label = f"t{i}"
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
    filters.append("[1:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]")

    run_ffmpeg([
        *inputs, "-i", str(vo),
        "-filter_complex", ";".join(filters),
        "-map", f"[{label}]", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
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
    from ytstudio.utils.sfx import SFX_SPECS, ensure_sfx

    events: list[tuple[str, float]] = []  # (tipo, inicio en s)
    t = 0.0
    for s in scenes:
        kind = s.get("sfx")
        if kind in SFX_SPECS and t > 0.5:  # sin efecto en el arranque del video
            start = max(0.0, t - SFX_SPECS[kind]["before_cut"])
            events.append((kind, start))
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
        "video": {k: v.get(k) for k in
                  ("width", "height", "fps", "transition", "overlays",
                   "overlay_accent")},
        "scenes": [{
            "id": s["id"], "img": s.get("broll_image"),
            "vid": s.get("broll_video"), "anim": s.get("animation"),
            "dur": s.get("duration"), "overlay": s.get("overlay"),
            "ost": s.get("on_screen_text"), "at": s.get("overlay_at"),
            "off": s.get("vo_offset"), "fade": p,
            "src": [stamp(s.get("broll_image")), stamp(s.get("broll_video"))],
        } for s, p in zip(scenes, plans)],
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

    # 2) Concatenación de escenas (rutas con '/' también en Windows)
    concat_list = scenes_dir / "list.txt"
    scene_files = [(scenes_dir / "scene_{:03d}.mp4".format(s["id"])).resolve()
                   for s in scenes]
    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in scene_files) + "\n",
        encoding="utf-8")
    body = final_dir / "cuerpo.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", str(body)], "concatenación")

    # 3) Mezcla de audio (envolvente de intensidad + ducking + SFX + loudness)
    #    y subtítulos. El grafo va en un archivo (-filter_complex_script):
    #    en videos largos supera el límite de línea de comandos de Windows.
    music = project.path("music", project.get("music_file"))
    music_db = cfg["audio"].get("music_db", -21)
    swing_db = cfg["audio"].get("intensity_db", 8)
    duck = cfg["audio"].get("duck", True)
    burn = cfg["video"].get("burn_subtitles", False)

    total = probe_duration(body)

    # Voz: en narración propia se usa la grabación CONTINUA del usuario como
    # pista única (alineada desde t=0 y ajustada a la duración del video), en
    # vez de los trozos por escena — así suena exactamente como la grabó, sin
    # cortes ni silencios entre escenas. En TTS se usa el audio del cuerpo.
    narration = project.get("narration")
    use_user_voice = bool(narration and any("audio_start" in s for s in scenes))

    sfx_args, sfx_filters, sfx_label = _sfx_graph(scenes, cfg, final_dir,
                                                  first_input=2)
    args = ["-i", str(body), "-i", str(music), *sfx_args]
    afilters: list[str] = []

    if use_user_voice:
        notify("🎙 Voz: usando tu narración CONTINUA como pista única "
               "(con respiros solo en tus pausas naturales).")
        narr_idx = 2 + (len(sfx_args) // 2)
        tl = project.get("voice_timeline")
        tl_path = project.path("voiceover", tl) if tl else None
        voice_src = (tl_path if tl_path and tl_path.exists()
                     else project.path("input", narration["file"]))
        args += ["-i", str(voice_src)]
        base = (f"[{narr_idx}:a]aresample=44100,aformat=channel_layouts=stereo,"
                f"atrim=0:{total:.3f},apad=whole_dur={total:.3f}")
        if duck:  # se consume 2 veces (sidechain + mezcla) → asplit obligatorio
            afilters.append(f"{base},asplit=2[vsc][vmx]")
            voice_sc, voice_mx = "vsc", "vmx"
        else:
            afilters.append(f"{base}[vmx]")
            voice_sc, voice_mx = None, "vmx"
        next_idx = narr_idx + 1
    else:
        voice_sc = voice_mx = "0:a"  # ffmpeg auto-divide los pads de entrada
        next_idx = 2 + (len(sfx_args) // 2)

    envelope = _music_envelope(scenes, music_db, swing_db)
    afilters.append(f"[1:a]volume='{envelope}':eval=frame[m]")
    if duck:
        afilters.append(f"[m][{voice_sc}]sidechaincompress=threshold=0.05:"
                        "ratio=8:attack=80:release=400[md]")
        music_label = "md"
    else:
        music_label = "m"

    afilters += sfx_filters
    mix_in = f"[{voice_mx}][{music_label}]" + (f"[{sfx_label}]" if sfx_label else "")
    n_mix = 3 if sfx_label else 2
    # Cierre: fundido de salida del audio completo (tras loudnorm, para que la
    # normalización no lo contrarreste) — el final deja de sentirse abrupto.
    end_fade = float(cfg["audio"].get("end_fade", 3.0))
    fade = (f",afade=t=out:st={max(0.0, total - end_fade):.2f}:d={end_fade:.2f}"
            if end_fade > 0 else "")
    afilters.append(f"{mix_in}amix=inputs={n_mix}:duration=first:normalize=0,"
                    f"loudnorm=I=-14:TP=-1.5:LRA=11{fade}[aout]")

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
    run_ffmpeg([*args, "-filter_complex_script", str(script), *maps, *codecs,
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(output)], "mezcla final")
    project.set("final_video", str(output))
