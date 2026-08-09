"""Batería v0.40.0: CORRECTOR DE ERRORES DE NARRACIÓN.

Caso REAL reportado por el creador (El_Chupacabras0.mp3):
    «El registró veterinario» …pausa 2s… «El registro veterinario oficial
     es la evidencia…»
El narrador arrancó mal, se detuvo y reinició. Hasta v0.39 ese falso
arranque terminaba en el video Y en los subtítulos.

Regla de oro del módulo: ante la duda NO se corta (un falso positivo destruye
contenido legítimo; un falso negativo solo deja el tropiezo que ya estaba).

T1  EL CASO DEL USUARIO: se detecta el falso arranque, se corta desde el
    inicio del intento hasta el reintento, y el texto resultante queda
    limpio y completo.
T2  Los otros tres detectores: repetición inmediata, muletilla aislada y
    corrección explícita («voy de nuevo»).
T3  NO se corta lo legítimo (lo más importante): anáfora retórica, frases
    completas repetidas con intención, muletillas dentro de una frase
    fluida, palabras cortas que coinciden por casualidad y enumeraciones.
T4  Tiempos: al quitar tramos, los segmentos restantes se DESPLAZAN para
    seguir cuadrando con el audio recortado (sin huecos ni solapes).
T5  AUDIO REAL: se corta con ffmpeg y el resultado dura exactamente lo
    esperado — el error ya no se oye (medido sobre un audio sintético donde
    el tramo del error es un tono distinto).
T6  La capa con IA: acepta lo que marca con evidencia, descarta 'baja'
    seguridad e índices inválidos, y no revienta si el modelo falla.
T7  Integración: config, avisos por corrección y degradación segura (si algo
    falla, la narración queda intacta).
"""

import os
import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import subprocess
import sys
from pathlib import Path



FAILS = []


def check(name, cond, detail=""):
    print(("  ✔ " if cond else "  ✘ ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


from ytstudio import narration_fix as nf

TMP = Path(__file__).parent / "t400"
TMP.mkdir(exist_ok=True)


def seg(words):
    """Construye un segmento con palabras (texto, inicio, fin)."""
    ws = [{"text": t, "start": round(s, 3), "end": round(e, 3)}
          for t, s, e in words]
    return {"start": ws[0]["start"], "end": ws[-1]["end"],
            "text": " ".join(w["text"] for w in ws), "words": ws}


def line(words_text, t0=0.0, dur=0.35, gap=0.05, gaps=None):
    """Palabras consecutivas desde t0; `gaps` fija pausas concretas {i: seg}."""
    out, t = [], t0
    for i, w in enumerate(words_text):
        out.append((w, t, t + dur))
        t += dur + ((gaps or {}).get(i, gap))
    return out


print("T1 EL CASO REAL DEL USUARIO (falso arranque con pausa de 2s)")
# «El registró veterinario» [pausa 2.0s] «El registro veterinario oficial es la evidencia.»
w = line(["El", "registró", "veterinario"], t0=0.0, gaps={2: 2.0})
w += line(["El", "registro", "veterinario", "oficial", "es", "la",
           "evidencia."], t0=w[-1][2] + 2.0)
segments = [seg(w)]
cuts = nf.detect_all(segments)
check("se detecta exactamente 1 tropiezo", len(cuts) == 1, str(cuts))
if cuts:
    c = cuts[0]
    check("es un falso arranque", c["kind"] == "falso_arranque", c["kind"])
    check("el corte empieza en el intento fallido (t≈0)", c["start"] < 0.05,
          str(c["start"]))
    # v0.42.0: el corte YA NO termina exactamente en el inicio nominal del
    # reintento — deja una GUARDA de 100-350 ms dentro de la pausa (Whisper
    # trae ±100 ms de error y el empalme al ras se comía el ataque de la
    # palabra siguiente: el "gageo" reportado por el usuario).
    check("y termina dentro de la pausa, con guarda antes del reintento",
          w[3][1] - 0.36 <= c["end"] <= w[3][1] - 0.09,
          f"{c['end']} vs {w[3][1]}")
    check("el texto quitado es el intento fallido",
          nf.norm(c["text"]) == nf.norm("El registró veterinario"), c["text"])
    check("el motivo explica la evidencia (repetición + pausa)",
          "repite" in c["reason"] and "pausa" in c["reason"], c["reason"])
    check("seguridad alta (3 palabras coincidentes)",
          c["confidence"] == "alta", c["confidence"])
fixed = nf.apply_to_segments(segments, cuts)
texto = " ".join(s["text"] for s in fixed)
check("el texto final queda limpio y completo",
      texto == "El registro veterinario oficial es la evidencia.", texto)
# v0.42.0: queda la guarda de empalme al frente (≤0.36 s de la pausa
# original) — los tiempos igual se desplazan hacia el inicio.
check("y arranca casi en t=0 (solo queda la guarda de empalme)",
      0.0 <= fixed[0]["start"] <= 0.36, str(fixed[0]["start"]))

print("T2 los otros detectores")
w2 = line(["Hoy", "el", "el", "registro", "cambió."])
c2 = nf.detect_all([seg(w2)])
check("repetición inmediata «el el»",
      len(c2) == 1 and c2[0]["kind"] == "repeticion", str(c2))
check("el texto tras corregir no repite",
      " ".join(s["text"] for s in nf.apply_to_segments([seg(w2)], c2))
      == "Hoy el registro cambió.")

w3 = line(["Entonces"], t0=0.0, gaps={0: 0.5})
w3 += line(["eh"], t0=1.0, gaps={0: 0.6})
w3 += line(["seguimos", "con", "el", "caso."], t0=2.0)
c3 = nf.detect_all([seg(w3)])
check("muletilla aislada «eh» entre pausas",
      any(x["kind"] == "muletilla" for x in c3), str(c3))

w4 = line(["El", "chupacabras", "mide", "dos"], t0=0.0, gaps={3: 0.5})
w4 += line(["corrijo"], t0=2.2, gaps={0: 0.5})
w4 += line(["El", "chupacabras", "mide", "un", "metro."], t0=3.2)
c4 = nf.detect_all([seg(w4)])
check("corrección explícita «corrijo» borra el intento anterior",
      any(x["kind"] == "correccion_explicita" for x in c4), str(c4))
t4 = " ".join(s["text"] for s in nf.apply_to_segments([seg(w4)], c4))
check("queda solo la versión corregida",
      t4 == "El chupacabras mide un metro.", t4)

print("T3 NO se corta lo legítimo (lo más importante)")
# anáfora retórica: dos frases COMPLETAS que empiezan igual
wa = line(["El", "registro", "dice", "una", "cosa."], t0=0.0, gaps={4: 0.8})
wa += line(["El", "registro", "dice", "otra", "cosa."], t0=2.8)
check("anáfora retórica con frases completas: NO se corta",
      nf.detect_all([seg(wa)]) == [], str(nf.detect_all([seg(wa)])))
# muletilla DENTRO de una frase fluida («este libro»)
wb = line(["Compré", "este", "libro", "ayer."])
check("«este» dentro de una frase fluida: NO se corta",
      nf.detect_all([seg(wb)]) == [], str(nf.detect_all([seg(wb)])))
# coincidencia casual de palabra corta tras pausa
wc = line(["Llegó", "la", "noche"], t0=0.0, gaps={2: 0.6})
wc += line(["la", "bestia", "salió", "a", "cazar."], t0=1.8)
check("palabra corta coincidente («la») tras pausa: NO se corta",
      nf.detect_all([seg(wc)]) == [], str(nf.detect_all([seg(wc)])))
# enumeración con repetición intencional
wd = line(["Uno,", "dos,", "tres,", "cuatro."])
check("enumeración: NO se corta", nf.detect_all([seg(wd)]) == [])
# pausa larga sin repetición (respiración normal)
we = line(["Aquella", "noche"], t0=0.0, gaps={1: 1.5})
we += line(["todo", "cambió", "para", "siempre."], t0=2.0)
check("pausa dramática sin repetición: NO se corta",
      nf.detect_all([seg(we)]) == [])

print("T4 desplazamiento de tiempos multi-segmento")
s1 = seg(line(["Uno", "dos"], t0=0.0))
s2 = seg(line(["El", "dato"], t0=3.0, gaps={1: 1.0}))
s3 = seg(line(["El", "dato", "correcto", "es", "este."], t0=5.0))
cuts_m = nf.detect_all([s1, s2, s3])
check("detecta el falso arranque entre segmentos", len(cuts_m) == 1,
      str(cuts_m))
res = nf.apply_to_segments([s1, s2, s3], cuts_m)
check("el segmento del intento fallido desaparece", len(res) == 2, str(len(res)))
removed = sum(c["end"] - c["start"] for c in cuts_m)
check("los tiempos del último segmento se desplazan lo cortado",
      abs(res[-1]["start"] - (s3["start"] - removed)) < 0.02,
      f"{res[-1]['start']} vs {s3['start'] - removed}")
check("sin solapes ni retrocesos entre segmentos",
      all(a["end"] <= b["start"] + 0.001 for a, b in zip(res, res[1:])))
check("las palabras dentro del segmento quedan ordenadas",
      all(x["end"] <= y["start"] + 0.001
          for s in res for x, y in zip(s["words"], s["words"][1:])))

print("T5 AUDIO REAL: el error deja de oírse")
# audio de 6s: 0-2s tono GRAVE (el error), 2-6s tono AGUDO (lo bueno)
src = TMP / "src.mp3"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-filter_complex",
                "sine=frequency=220:duration=2[a];sine=frequency=880:duration=4[b];"
                "[a][b]concat=n=2:v=0:a=1", str(src)], check=True)
out = TMP / "out.mp3"
ok = nf.apply_to_audio(src, out, [{"start": 0.0, "end": 2.0,
                                   "kind": "falso_arranque", "text": "x",
                                   "reason": "r"}])
check("se escribió el audio recortado", ok and out.exists())
from ytstudio.utils.media import probe_duration
dur = probe_duration(out)
check(f"dura ~4s (se quitaron los 2s del error) [{dur:.2f}s]",
      3.8 <= dur <= 4.25)
# el tono grave (el error) ya no está: se mide la energía en su banda
res_txt = subprocess.run(
    ["ffmpeg", "-hide_banner", "-v", "info", "-i", str(out),
     "-af", "bandpass=f=220:width_type=h:w=40,volumedetect",
     "-f", "null", "-"], capture_output=True, text=True).stderr
mean_220 = [l for l in res_txt.splitlines() if "mean_volume" in l]
res_txt2 = subprocess.run(
    ["ffmpeg", "-hide_banner", "-v", "info", "-i", str(out),
     "-af", "bandpass=f=880:width_type=h:w=120,volumedetect",
     "-f", "null", "-"], capture_output=True, text=True).stderr
mean_880 = [l for l in res_txt2.splitlines() if "mean_volume" in l]


def db(lines):
    return float(lines[0].split("mean_volume:")[1].split("dB")[0]) if lines else 0.0


check(f"el tono del ERROR (220Hz) quedó muy por debajo del bueno (880Hz) "
      f"[{db(mean_220):.1f}dB vs {db(mean_880):.1f}dB]",
      db(mean_220) < db(mean_880) - 12)
check("sin cortes: no se reescribe el audio",
      nf.apply_to_audio(src, TMP / "n.mp3", []) is False)

print("T6 capa con IA")


class _LLM:
    is_mock = False

    def __init__(self, errores):
        self.errores = errores

    def complete_json(self, system, prompt, schema=None, max_tokens=None,
                      purpose=None):
        self.prompt = prompt
        return {"errores": self.errores}


segs_ai = [seg(line(["La", "bestia", "atacó", "el", "ganado", "aquella",
                     "noche."]))]
ai = nf.review_with_llm(_LLM([
    {"inicio_palabra": 0, "fin_palabra": 1, "tipo": "falso_arranque",
     "motivo": "reformulación", "seguridad": "alta"},
    {"inicio_palabra": 3, "fin_palabra": 3, "tipo": "muletilla",
     "motivo": "dudoso", "seguridad": "baja"},
    {"inicio_palabra": 99, "fin_palabra": 120, "tipo": "repeticion",
     "motivo": "fuera de rango", "seguridad": "alta"},
]), segs_ai)
check("acepta el marcado con evidencia", len(ai) == 1, str(ai))
check("descarta seguridad 'baja' (ante la duda no se corta)",
      all("dudoso" not in c["reason"] for c in ai))
check("descarta índices fuera de rango", all(c["start"] < 10 for c in ai))
check("marca el origen de la revisión", "revisión IA" in ai[0]["reason"])


class _Boom:
    is_mock = False

    def complete_json(self, *a, **k):
        raise RuntimeError("modelo caído")


check("si el modelo falla, no rompe nada (lista vacía)",
      nf.review_with_llm(_Boom(), segs_ai) == [])


class _Mock:
    is_mock = True

    def complete_json(self, *a, **k):
        raise AssertionError("no debe llamarse en modo preview")


check("en modo preview no se llama al modelo",
      nf.review_with_llm(_Mock(), segs_ai) == [])

print("T7 integración en la fase de ingesta")
import inspect

from ytstudio.phases import ingest as ing
from ytstudio.config import load_config

src_ing = inspect.getsource(ing)
check("la fase llama al corrector tras transcribir",
      "_fix_narration(" in src_ing and "fix_narration" in src_ing)
check("es desactivable por configuración",
      load_config().get("audio", {}).get("fix_narration") is True)
check("la revisión con IA también es opcional",
      "fix_narration_ai" in (ROOT / "config.yaml")
      .read_text(encoding="utf-8"))
fx = inspect.getsource(ing._fix_narration)
check("avisa de CADA corrección con texto y motivo",
      "add_warning" in fx and "se quitó" in fx)
check("nunca deja la narración vacía", "if not new_segments" in fx)
check("ante cualquier fallo devuelve la narración intacta",
      "except Exception" in fx and "se usa tal cual la grabaste" in fx)

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAILS:
    print("FALLARON:", FAILS)
    sys.exit(1)
print("TODO EN VERDE ✔")
