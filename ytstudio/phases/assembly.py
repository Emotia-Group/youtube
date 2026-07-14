"""FASE 9 — Montaje: renderiza cada escena (Ken Burns sobre imagen o clip de
video IA, rótulos cinematográficos animados, fundidos), concatena, y mezcla el
audio con criterio de banda sonora: la música sigue el arco de intensidad de
la historia (envolvente por escena), respira en las pausas de la voz (ducking)
y se acentúa con efectos incidentales (whoosh/riser/boom) en los cortes clave.
Termina normalizando a -14 LUFS y aplicando los subtítulos."""
from __future__ import annotations

from pathlib import Path

from ytstudio.phases.scenes import load_scenes
from ytstudio.utils.media import (filter_path, find_font, require_ffmpeg,
                                  run_ffmpeg)

FADE = 0.3  # fundido de entrada/salida por escena (s)

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
    return (f"scale=3840:-2,setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps}")


# ---------------------------------------------------------------------------
# Rótulos cinematográficos
# ---------------------------------------------------------------------------

def _spaced(text: str) -> str:
    """Versalitas con tracking (espaciado entre letras), estilo documental."""
    return " ".join(text.upper())


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
    main_font = find_font(bold=True, serif=True) if lay["serif"] else sans

    text = overlay["text"].strip()
    kicker = (overlay.get("kicker") or "").strip()
    if lay["upper"]:
        text = _spaced(text)

    # Tiempos: aparece poco después del corte, se sostiene y se despide antes
    # del final. En escenas cortas se comprime.
    slow = lay["slow"]
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


def _render_scene(scene: dict, project, cfg, out: Path) -> None:
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    dur = scene["duration"]
    frames = max(1, round(dur * fps))
    use_fade = cfg["video"].get("transition", "fade") == "fade"

    vo = project.path("voiceover", scene["vo_file"])
    filters = []

    if scene.get("broll_video"):
        inputs = ["-stream_loop", "-1",
                  "-i", str(project.path("broll", scene["broll_video"]))]
        filters.append(f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                       f"crop={w}:{h},fps={fps},setsar=1[v0]")
    else:
        inputs = ["-i", str(project.path("broll", scene["broll_image"]))]
        filters.append(f"[0:v]{_kenburns(scene['animation'], frames, w, h, fps)}[v0]")

    label = "v0"
    for i, dt in enumerate(_overlay_filters(scene, dur, cfg, out.parent), start=1):
        filters.append(f"[{label}]{dt}[t{i}]")
        label = f"t{i}"
    if use_fade:
        filters.append(f"[{label}]fade=t=in:st=0:d={FADE},"
                       f"fade=t=out:st={max(0.0, dur - FADE):.3f}:d={FADE}[v2]")
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


def run(project, cfg) -> None:
    require_ffmpeg()
    scenes = load_scenes(project)
    final_dir = project.path("final")
    scenes_dir = final_dir / "escenas"
    scenes_dir.mkdir(exist_ok=True)

    # 1) Render de cada escena (reanudable)
    for scene in scenes:
        out = scenes_dir / f"scene_{scene['id']:03d}.mp4"
        if not out.exists():
            _render_scene(scene, project, cfg, out)

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

    envelope = _music_envelope(scenes, music_db, swing_db)
    afilters = [f"[1:a]volume='{envelope}':eval=frame[m]"]
    if duck:
        afilters.append("[m][0:a]sidechaincompress=threshold=0.05:ratio=8:"
                        "attack=80:release=400[md]")
        music_label = "md"
    else:
        music_label = "m"

    sfx_args, sfx_filters, sfx_label = _sfx_graph(scenes, cfg, final_dir,
                                                  first_input=2)
    afilters += sfx_filters
    mix_in = f"[0:a][{music_label}]" + (f"[{sfx_label}]" if sfx_label else "")
    n_mix = 3 if sfx_label else 2
    afilters.append(f"{mix_in}amix=inputs={n_mix}:duration=first:normalize=0,"
                    "loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

    output = final_dir / "video_final.mp4"
    args = ["-i", str(body), "-i", str(music), *sfx_args]
    graph = list(afilters)
    sub_input = 2 + (len(sfx_args) // 2)

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
