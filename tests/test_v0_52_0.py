"""Batería v0.52.0 — encuadre documental preventivo + fidelidad auditada gratis.

Dos problemas reales que se cierran aquí:

A) EL ENCUADRE LLEGABA TARDE. Una escena que narra un animal hallado sin vida
   salía al generador en crudo, el filtro la rechazaba y SOLO ENTONCES se
   suavizaba: tiempo perdido, a veces dinero (una predicción rechazada puede
   facturarse) y una imagen peor.

B) EL SUAVIZADO DESTRUÍA LOS HECHOS. El reintento cambiaba «dead»→«ancient»,
   «corpse»→«statue» y «wound»→«mark»: deshacía exactamente la fidelidad
   factual que el director acababa de fijar. Un cabrito muerto se convertía en
   «un cabrito antiguo».

Y se añade la comprobación que faltaba: verificar SIN COSTE que el prompt
refleja los hechos de la narración (cantidad y estado sin vida), en vez de
depender solo del control con visión, que ya se paga.
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import inspect
import tempfile

from ytstudio import prompt_safety as ps

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0520_"))

# ---------------------------------------------------------------------------
# T1 — detección de contenido delicado (red de seguridad determinista)
# ---------------------------------------------------------------------------
casos = {
    "muerte_animal": ("a dead goat lying in a field", "Hallaron la cabra muerta."),
    "restos_humanos": ("ancient human skeleton in a tomb", "Los restos humanos"),
    "herida_lesion": ("three puncture wounds on the neck", "tres orificios"),
    "violencia_historica": ("a medieval battle scene", "la batalla de 1324"),
    "medico_anatomico": ("anatomy diagram of the heart", "la autopsia reveló"),
    "armas_conflicto": ("an ancient sword on display", "la espada del rey"),
}
for esperada, (prompt, narr) in casos.items():
    got = ps.detectar_sensibilidad(prompt, narr)
    check(f"T1 detecta «{esperada}»", got == esperada, f"detectó {got}")

check("T1b una escena normal NO se marca (no se estorba a lo cotidiano)",
      ps.detectar_sensibilidad("a golden desert caravan at sunrise",
                               "La caravana cruzó el desierto") == "ninguna",
      "")
check("T1c también detecta desde el español de la narración",
      ps.detectar_sensibilidad("cinematic shot of a farm",
                               "Encontraron ocho ovejas muertas")
      == "muerte_animal", "")

# ---------------------------------------------------------------------------
# T2 — el encuadre va DESDE EL PRIMER INTENTO y no toca lo normal
# ---------------------------------------------------------------------------
crudo = "documentary still, a dead goat with three puncture marks on the neck"
enc, cat = ps.encuadrar(crudo, "", "Hallaron la cabra muerta con tres orificios")
check("T2 una escena delicada sale ya encuadrada", cat == "muerte_animal"
      and enc != crudo, cat)
check("T2b el encuadre pide registro documental clínico y sin sangre",
      "documentary" in enc.lower() and "no blood" in enc.lower()
      and "clinical" in enc.lower(), enc[:120])
check("T2c y CONSERVA el prompt original completo detrás",
      crudo in enc, enc[:160])

normal = "cinematic desert caravan at golden hour"
enc2, cat2 = ps.encuadrar(normal, "", "La caravana cruzó el Sahara")
check("T2d una escena normal se queda EXACTAMENTE igual",
      enc2 == normal and cat2 == "ninguna", enc2)

# la marca del director manda sobre la detección
enc3, cat3 = ps.encuadrar("a quiet museum room", "restos_humanos", "")
check("T2e si el director marcó la escena, manda su marca",
      cat3 == "restos_humanos" and "museum" in enc3.lower(), cat3)
check("T2f encuadrar dos veces no duplica el texto",
      ps.encuadrar(enc, "", "")[0] == enc, "")

# NO se le miente al modelo: el encuadre describe la imagen admisible, no
# declara cumplimiento (esas fórmulas no funcionan y empeoran el resultado)
todos = " ".join(ps.FRAMINGS.values()).lower()
check("T2g el encuadre NO declara cumplimiento de políticas (no funciona)",
      "policy" not in todos and "policies" not in todos
      and "does not violate" not in todos and "allowed" not in todos, "")

# ---------------------------------------------------------------------------
# T3 — EL FALLO GRAVE: el suavizado ya no destruye los hechos
# ---------------------------------------------------------------------------
factual = ("cinematic documentary still, exactly three dead goats, all "
           "lifeless, with three puncture wounds on the neck, blood pooling, "
           "gore, mutilated bodies")
suave = ps.suavizar(factual)
cuerpo = suave.split("audience. ", 1)[-1].lower()

for hecho, etiqueta in [("three", "la cantidad"), ("dead", "el estado sin vida"),
                        ("goats", "la especie"), ("neck", "la ubicación")]:
    check(f"T3 el suavizado CONSERVA {etiqueta} («{hecho}»)",
          hecho in cuerpo, cuerpo[:160])
for malo in ("blood", "gore", "mutilated"):
    check(f"T3b y quita lo gratuito («{malo}»)", malo not in cuerpo,
          cuerpo[:160])
check("T3c no deja duplicados al reescribir («puncture clinical puncture»)",
      "clinical puncture" not in cuerpo, cuerpo[:160])
check("T3d el suavizado añade el registro documental",
      "documentary" in suave.lower() and "non-graphic" in suave.lower(), "")

# la regresión concreta que nos costó imágenes equivocadas
viejo_destructivo = {"dead": "ancient", "corpse": "statue", "wound": "mark",
                     "death": "history"}
for palabra, destruido in viejo_destructivo.items():
    entrada = f"a {palabra} sheep in a field"
    salida = ps.suavizar(entrada).lower()
    check(f"T3e «{palabra}» ya NO se convierte en «{destruido}»",
          destruido not in salida.split("audience. ")[-1], salida[-80:])

# ---------------------------------------------------------------------------
# T4 — auditoría de fidelidad GRATIS (antes solo lo veía la visión, pagando)
# ---------------------------------------------------------------------------
faltan = ps.auditar_fidelidad("Encontraron tres cabras muertas en el corral.",
                              "a goat standing in a farmyard")
check("T4 caza la cantidad ausente y el estado ausente", len(faltan) == 2,
      str(faltan))
check("T4b y lo dice en claro",
      any("cantidad" in f for f in faltan)
      and any("SIN VIDA" in f for f in faltan), str(faltan))

ok = ps.auditar_fidelidad(
    "Encontraron tres cabras muertas en el corral.",
    "exactly three dead goats, lifeless, in a farmyard")
check("T4c un prompt fiel no genera ninguna queja", ok == [], str(ok))

check("T4d acepta el número escrito con cifra o con letra",
      ps.auditar_fidelidad("Había 8 ovejas muertas",
                           "eight dead sheep in a field") == [], "")
check("T4e las cifras GRANDES no se exigen (60.000 no es dibujable)",
      ps.auditar_fidelidad("Su caravana tenía 60.000 personas",
                           "a vast caravan crossing the desert") == [], "")
check("T4f una narración sin hechos duros no molesta",
      ps.auditar_fidelidad("El imperio prosperó durante décadas",
                           "a golden city at dawn") == [], "")

# ---------------------------------------------------------------------------
# T5 — integración: director, auditoría y generador
# ---------------------------------------------------------------------------
from ytstudio.phases import broll as broll_phase
from ytstudio.phases import scenes as scenes_phase

src_sc = inspect.getsource(scenes_phase)
check("T5 el director puede marcar la sensibilidad de cada escena",
      '"sensibilidad"' in src_sc and "muerte_animal" in src_sc, "")
check("T5b y las reglas le explican que NO debe suavizar los hechos",
      "no los suavices" in src_sc.lower(), "")

# normalización: un valor inventado por el modelo se descarta
escenas = [{"id": 1, "sensibilidad": "muerte_animal", "narration": "x",
            "overlay_type": "ninguno", "music_intensity": 0.5},
           {"id": 2, "sensibilidad": "inventada", "narration": "x",
            "overlay_type": "ninguno", "music_intensity": 0.5}]
scenes_phase._normalize_creative(escenas)
check("T5c una sensibilidad válida se conserva y una inventada se descarta",
      escenas[0].get("sensibilidad") == "muerte_animal"
      and "sensibilidad" not in escenas[1],
      str([s.get("sensibilidad") for s in escenas]))


class PStub:
    def __init__(self):
        self.avisos = []
        self.data = {}

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def add_warning(self, m):
        self.avisos.append(m)


p = PStub()
scenes_phase._auditar_prompts(p, [
    {"id": 4, "narration": "Tres cabras muertas.", "broll_prompt": "a goat"},
    {"id": 5, "narration": "El desierto al amanecer.",
     "broll_prompt": "desert at dawn"}])
check("T5d la fase de escenas avisa de los prompts infieles ANTES de pagar",
      len(p.avisos) == 1 and "escena 4" in p.avisos[0]
      and "escena 5" not in p.avisos[0], str(p.avisos))
check("T5e y recuerda que corregirlo en el storyboard es gratis",
      "gratis" in p.avisos[0], p.avisos[0][-90:])

src_br = inspect.getsource(broll_phase)
check("T5f el generador encuadra ANTES del primer intento",
      "ps.encuadrar(" in src_br
      and src_br.index("ps.encuadrar(") < src_br.index("images.generate(prompt"),
      "")
check("T5g el reintento usa el suavizado que conserva los hechos",
      "ps.suavizar(" in src_br, "")
check("T5h el suavizador destructivo ya no existe en la fase",
      "_SOFTEN = {" not in src_br and '"corpse": "statue"' not in src_br, "")
check("T5i el log informa de las escenas encuadradas y suavizadas",
      "registro documental desde el primer intento" in src_br
      and "segundo intento" in src_br, "")

# ---------------------------------------------------------------------------
import shutil

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.52.0 completa: el contenido delicado sale bien a la "
      "primera y los hechos de tu narración sobreviven a todos los reintentos.")
