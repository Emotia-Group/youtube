"""Batería v0.45.1 — el corrector de narración NUNCA borra contenido legítimo.

Reproduce los dos desastres del log ytstudioeventos_4 (proyecto 3-mansa-musa,
corrida del 2026-08-08 23:22, «✂ Narración: se corrigieron 2 tropiezo(s)
(51.9s menos)»):

  A) «✂ Corregido en tu narración [0.0s]: se quitó «1 1 2 3 4 5 6 7 8 9 10 11
     12 11 12 13ja 3 4 5 6 7 8» — Conteo/prueba de micrófono…»
     22 palabras que se llevaron ~48 SEGUNDOS de audio: dentro iban el gancho
     de apertura y el párrafo de Forbes. Los tiempos de la transcripción no
     correspondían a ese texto.

  B) «✂ Corregido en tu narración [198.7s]: se quitó «entre el 50 y el 60 por
     ciento de oro» — …lo reformula como…»
     Cirugía en mitad de una frase fluida donde NO había nada que corregir:
     se comió desde el final de «producía» hasta «por ciento».

Verifica que ambos se descartan, que los cortes legítimos siguen pasando, y
que el corte ya no se traga silencios largos que no le corresponden.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import subprocess
import tempfile

from ytstudio import narration_fix as nf

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0451_"))


def W(text, start, end):
    return {"text": text, "start": start, "end": end}


# ---------------------------------------------------------------------------
# T1 — EL CASO A: 22 palabras que dicen llevarse 48 segundos
# ---------------------------------------------------------------------------
# Transcripción con tiempos DISPARATADOS: el conteo ocupa 0-48s según Whisper,
# y dentro de ese rango caen las palabras REALES del gancho.
conteo = [W(str(n), i * 2.2, i * 2.2 + 0.4)
          for i, n in enumerate("1 1 2 3 4 5 6 7 8 9 10 11 12 11 12 13 3 4 5 "
                                "6 7 8".split())]
gancho = [W(t, 8.0 + i * 0.5, 8.4 + i * 0.5) for i, t in enumerate(
    "En 1324, un hombre cruzó el desierto del Sahara. Su caravana tenía "
    "60.000 personas.".split())]
words_a = conteo + gancho
corte_a = {"kind": "falso_arranque", "start": 0.0, "end": 48.4,
           "text": " ".join(w["text"] for w in conteo),
           "reason": "conteo previo (revisión IA)", "confidence": "alta"}
keep, drop = nf.validate_cuts([corte_a], words_a, silences=[(0.0, 0.2)],
                              total_seconds=1298.0)
check("T1 el corte de 48s con el gancho dentro se DESCARTA",
      keep == [] and len(drop) == 1, f"keep={len(keep)}")
check("T1b y el motivo dice exactamente qué no cuadra",
      "palabras" in drop[0]["drop_reason"]
      and ("no corresponden" in drop[0]["drop_reason"]
           or "no pueden ocupar" in drop[0]["drop_reason"]),
      drop[0]["drop_reason"])

# la misma valla, sin palabras extra dentro: el ritmo imposible basta
corte_solo = {**corte_a, "end": 40.0}
keep, drop = nf.validate_cuts([corte_solo], conteo, silences=[(0.0, 0.2)])
check("T1c 22 palabras tampoco pueden ocupar 40s aunque no arrastren texto",
      keep == [] and "no pueden ocupar" in drop[0]["drop_reason"],
      str(drop and drop[0]["drop_reason"]))

# ---------------------------------------------------------------------------
# T2 — EL CASO B: cirugía en mitad de habla fluida (audio REAL con ffmpeg)
# ---------------------------------------------------------------------------
# Audio de verdad: 3s de tono continuo (habla fluida), 1s de silencio, 3s más.
# El silencio se MIDE con ffmpeg, igual que en la fase de ingesta.
audio = TMP / "narracion.wav"
subprocess.run(
    ["ffmpeg", "-y", "-f", "lavfi", "-i",
     "sine=frequency=220:duration=3", "-f", "lavfi", "-i",
     "anullsrc=r=44100:cl=mono:d=1", "-f", "lavfi", "-i",
     "sine=frequency=220:duration=3", "-filter_complex",
     "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]", "-map", "[a]", str(audio)],
    check=True, capture_output=True)
from ytstudio.utils.media import detect_silences, probe_duration

silencios = detect_silences(audio, noise_db=-35, min_d=0.12)
dur = probe_duration(audio)
check("T2 el silencio real de la grabación se mide en la onda",
      any(2.8 < s0 < 3.2 and 3.8 < s1 < 4.2 for s0, s1 in silencios),
      str(silencios))

fluidas = [W(t, 0.5 + i * 0.25, 0.7 + i * 0.25) for i, t in enumerate(
    "el Imperio de Malí producía entre el 50 y el 60 por ciento de oro".split())]
corte_b = {"kind": "falso_arranque", "start": 1.75, "end": 2.6,
           "text": "entre el 50 y el 60 por ciento de oro",
           "reason": "lo reformula (revisión IA)", "confidence": "alta"}
keep, drop = nf.validate_cuts([corte_b], fluidas, silences=silencios,
                              total_seconds=dur)
check("T2b el corte en mitad de habla fluida se DESCARTA",
      keep == [] and len(drop) == 1, f"keep={len(keep)}")
check("T2c y el motivo lo dice en claro (ningún borde en silencio)",
      "silencio medido" in drop[0]["drop_reason"], drop[0]["drop_reason"])

# ---------------------------------------------------------------------------
# T3 — un tropiezo LEGÍTIMO sigue corrigiéndose (no rompimos la función)
# ---------------------------------------------------------------------------
# El caso real del usuario: «El registró veterinario» …pausa… y lo repite.
legit = [W("El", 2.0, 2.2), W("registró", 2.2, 2.8), W("veterinario", 2.8, 3.0),
         W("El", 4.0, 4.2), W("registro", 4.2, 4.8),
         W("veterinario", 4.8, 5.4), W("oficial", 5.4, 6.0)]
corte_ok = {"kind": "falso_arranque", "start": 1.95, "end": 3.5,
            "text": "El registró veterinario", "reason": "reinicio de frase",
            "confidence": "alta"}
keep, drop = nf.validate_cuts([corte_ok], legit, silences=silencios,
                              total_seconds=dur)
check("T3 el falso arranque legítimo SÍ se corrige (borde en la pausa real)",
      len(keep) == 1 and not drop, f"keep={len(keep)} drop={len(drop)}")

# sin medición de silencio disponible, las otras vallas siguen operando
keep, drop = nf.validate_cuts([corte_ok], legit, silences=None)
check("T3b si no se pudo medir el silencio, el corte legítimo pasa igual",
      len(keep) == 1, str(drop))

# ---------------------------------------------------------------------------
# T4 — tope por corte y tope global
# ---------------------------------------------------------------------------
largo_words = [W(f"p{i}", i * 0.5, i * 0.5 + 0.4) for i in range(60)]
largo = {"kind": "muletilla", "start": 0.0, "end": 25.0,
         "text": " ".join(f"p{i}" for i in range(60)), "reason": "x",
         "confidence": "alta"}
keep, drop = nf.validate_cuts([largo], largo_words, silences=[(0.0, 30.0)])
check("T4 nada que dure más de 20s se acepta como «tropiezo»",
      keep == [] and "nunca es tan largo" in drop[0]["drop_reason"],
      str(drop and drop[0]["drop_reason"]))

# muchos cortes pequeños y plausibles, pero que juntos se comen la grabación
muchos, palabras = [], []
for k in range(30):
    t = k * 10.0
    palabras += [W(f"a{k}", t, t + 1.0), W(f"b{k}", t + 1.0, t + 2.0)]
    muchos.append({"kind": "repeticion", "start": t, "end": t + 2.0,
                   "text": f"a{k} b{k}", "reason": "x", "confidence": "alta"})
keep, drop = nf.validate_cuts(muchos, palabras, silences=None,
                              total_seconds=300.0)
check("T4b si entre todas superan el tope global, no se toca NADA",
      keep == [] and len(drop) == 30
      and "tope de seguridad" in drop[0]["drop_reason"],
      f"keep={len(keep)} drop={len(drop)}")

# ---------------------------------------------------------------------------
# T5 — las vallas miden VOZ, no duración: tragarse silencio no borra contenido
# ---------------------------------------------------------------------------
# 3 palabras seguidas de una pausa enorme: el corte dura 40s pero solo se
# lleva 1.2s de voz. Debe PASAR (si no, el empalme deja un hueco muerto y el
# tropiezo se queda en el video).
tras_pausa = [W("El", 0.0, 0.4), W("registró", 0.4, 0.9),
              W("veterinario", 0.9, 1.2), W("El", 41.0, 41.4),
              W("registro", 41.4, 42.0), W("veterinario", 42.0, 42.6)]
corte_pausa = {"kind": "falso_arranque", "start": 0.0,
               "end": nf._cut_end(tras_pausa, 2),
               "text": "El registró veterinario", "reason": "reinicio",
               "confidence": "alta"}
keep, drop = nf.validate_cuts([corte_pausa], tras_pausa, silences=[(1.3, 40.9)],
                              total_seconds=60.0)
check("T5 un corte que absorbe una pausa larga PASA (solo 1.2s son voz)",
      len(keep) == 1, str(drop and drop[0]["drop_reason"]))
check("T5b y el empalme se pega al reintento, sin dejar hueco muerto",
      keep and 40.6 <= keep[0]["end"] <= 41.0, str(keep and keep[0]["end"]))
# el mismo corte, pero con la VOZ estirada 40s: eso sí es imposible
falso = [W("El", 0.0, 0.4), W("registró", 20.0, 20.5), W("veterinario", 40.0, 40.5),
         W("El", 41.0, 41.4)]
keep, drop = nf.validate_cuts(
    [{**corte_pausa, "end": 40.8}], falso, silences=[(0.5, 41.0)],
    total_seconds=60.0)
check("T5c pero 3 palabras que dicen ocupar 40s de HABLA se descartan",
      keep == [] and "habla" in drop[0]["drop_reason"],
      str(drop and drop[0]["drop_reason"]))

# ---------------------------------------------------------------------------
# T6 — la revisión IA ya avisa de las duplicaciones del transcriptor
# ---------------------------------------------------------------------------
import inspect

src = inspect.getsource(nf.review_with_llm)
check("T6 el prompt prohíbe cortar tramos sin ninguna pausa alrededor",
      "SIN NINGUNA PAUSA" in src and "DUPLICA" in src, "")

# ---------------------------------------------------------------------------
# T7 — la ingesta conecta la valla y avisa de lo descartado
# ---------------------------------------------------------------------------
from ytstudio.phases import ingest as ingest_phase

isrc = inspect.getsource(ingest_phase._fix_narration)
check("T7 la ingesta valida los cortes contra el audio antes de aplicarlos",
      "validate_cuts" in isrc and "detect_silences" in isrc, "")
check("T7b y avisa de cada corrección descartada, diciendo que no tocó nada",
      "Descarté una corrección" in isrc and "INTACTA" in isrc, "")
check("T7c el aviso de un corte aplicado ahora dice cuántos segundos quita",
      "end'] - c['start']" in isrc, "")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.45.1 completa: los dos cortes que te borraron narración "
      "quedan descartados y los tropiezos de verdad se siguen corrigiendo.")
shutil.rmtree(TMP, ignore_errors=True)
