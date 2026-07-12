"""FASE 9 — Montaje: renderiza cada escena (Ken Burns sobre imagen o clip de
video IA, texto en pantalla, fundidos), concatena, mezcla la voz con la música
(ducking + normalización a -14 LUFS) y aplica los subtítulos."""
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
    if scene.get("on_screen_text"):
        font = find_font(bold=True)
        # Sin fuente localizable se omite el texto en pantalla (no fallar el render)
        if font:
            # textfile= evita el doble escapado del parser de filtros: el texto
            # va en un archivo UTF-8 y admite cualquier carácter.
            textfile = out.parent / f"ostext_{scene['id']:03d}.txt"
            textfile.write_text(scene["on_screen_text"], encoding="utf-8")
            filters.append(
                f"[{label}]drawtext=fontfile='{filter_path(font)}':"
                f"textfile='{filter_path(textfile)}':expansion=none:"
                f"fontsize={int(h * 0.055)}:fontcolor=white:borderw=3:bordercolor=black@0.85:"
                f"x=(w-text_w)/2:y=h*0.10[v1]")
            label = "v1"
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

    # 3) Mezcla de audio (música + ducking + loudness) y subtítulos
    music = project.path("music", project.get("music_file"))
    music_db = cfg["audio"].get("music_db", -21)
    duck = cfg["audio"].get("duck", True)
    burn = cfg["video"].get("burn_subtitles", False)

    afilters = [f"[1:a]volume={music_db}dB[m]"]
    if duck:
        afilters.append("[m][0:a]sidechaincompress=threshold=0.05:ratio=8:"
                        "attack=80:release=400[md]")
        music_label = "md"
    else:
        music_label = "m"
    afilters.append(f"[0:a][{music_label}]amix=inputs=2:duration=first:normalize=0,"
                    "loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

    output = final_dir / "video_final.mp4"
    args = ["-i", str(body), "-i", str(music)]

    if burn:
        ass = project.path("subtitles", "subtitulos.ass")
        filter_complex = (";".join(afilters)
                          + f";[0:v]ass='{filter_path(ass)}'[vout]")
        args += ["-filter_complex", filter_complex,
                 "-map", "[vout]", "-map", "[aout]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                 "-pix_fmt", "yuv420p"]
    else:
        srt = project.path("subtitles", "subtitulos.srt")
        lang = _LANG3.get(cfg.get("language", "es"), "und")
        args += ["-i", str(srt),
                 "-filter_complex", ";".join(afilters),
                 "-map", "0:v", "-map", "[aout]", "-map", "2:0",
                 "-c:v", "copy", "-c:s", "mov_text",
                 "-metadata:s:s:0", f"language={lang}"]

    args += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]
    run_ffmpeg(args, "mezcla final")
    project.set("final_video", str(output))
