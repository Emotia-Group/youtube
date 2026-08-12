"""ENCUADRE DOCUMENTAL de los prompts + auditoría de fidelidad.

Dos problemas reales que este módulo resuelve:

1. EL ENCUADRE LLEGABA TARDE. Una escena que narra un animal hallado sin vida
   salía al generador «en crudo»: el filtro de contenido la rechazaba, y solo
   ENTONCES se reintentaba con un prompt suavizado. Resultado: tiempo perdido,
   a veces dinero (una predicción rechazada puede facturarse igual) y una
   imagen peor. Ahora el registro documental va DESDE EL PRIMER INTENTO.

   Importante sobre CÓMO se encuadra: no se le declara al modelo que la
   petición «no viola sus políticas» — los filtros no leen declaraciones, y
   ese tipo de frase suele contar como señal de manipulación y empeora el
   resultado. Lo que de verdad funciona es pedir la imagen QUE SÍ ES
   admisible: registro clínico y respetuoso, sin sangre ni detalle gratuito,
   con el contexto real (documental de divulgación). Eso además se ve mejor.

2. EL SUAVIZADO DESTRUÍA LOS HECHOS. El reintento sustituía «dead» por
   «ancient», «corpse» por «statue» y «wound» por «mark»: exactamente los
   hechos que la fidelidad factual se había esforzado en fijar. Un cabrito
   muerto se convertía en «un cabrito antiguo». Aquí se suaviza quitando SOLO
   lo gratuito (sangre, vísceras, gore) y conservando especie, estado, número
   y ubicación.

Además, `auditar_fidelidad()` comprueba SIN COSTE que el prompt no se dejó
por el camino los hechos que la narración afirma (cuántos, y si están sin
vida) — la comprobación que antes solo hacía el control con visión, ya
pagando.
"""
from __future__ import annotations

import re
import unicodedata

# Categorías de sensibilidad que el director puede marcar en cada escena, con
# el registro visual que las hace admisibles Y mejores como documental.
FRAMINGS: dict[str, str] = {
    "muerte_animal": (
        "natural-history documentary photograph, wildlife forensic record, "
        "clinical and respectful treatment, animal shown intact and still, "
        "no blood, no wounds in close-up, no gore, muted natural tones"),
    "restos_humanos": (
        "archaeological documentary photograph, museum exhibit register, "
        "respectful and non-graphic, historical artefacts and remains as "
        "displayed in a museum, no gore, no distress"),
    "herida_lesion": (
        "medical-educational illustration for a documentary, clinical and "
        "diagrammatic, clean clinical presentation, no blood, no gore, "
        "textbook style"),
    "violencia_historica": (
        "historical documentary illustration, the AFTERMATH and the setting "
        "rather than the act itself, restrained and sober, no blood, no "
        "combat close-ups, museum-painting register"),
    "medico_anatomico": (
        "scientific anatomical illustration for an educational documentary, "
        "textbook diagram style, clinical, neutral background"),
    "arte_desnudo": (
        "classical museum artwork register, draped and modest, art-history "
        "documentary photograph of a sculpture or painting"),
    "armas_conflicto": (
        "museum artefact photograph for a history documentary, object on "
        "display, no people, no action, archival register"),
    "sustancias": (
        "educational public-health documentary photograph, neutral and "
        "clinical, informational register, no consumption shown"),
}

SENSIBILIDADES = ("ninguna", *FRAMINGS)

# Red de seguridad DETERMINISTA: si el director no marcó la escena, estas
# señales en el prompt (o en la narración) la marcan igual. Ordenadas: la
# primera categoría que coincide manda.
_SEÑALES: list[tuple[str, tuple[str, ...]]] = [
    ("restos_humanos", ("human remains", "skeleton", "skull", "mummy",
                        "corpse of a man", "corpse of a woman", "cadaver",
                        "esqueleto", "momia", "restos humanos", "craneo")),
    ("muerte_animal", ("dead animal", "animal carcass", "carcass", "dead goat",
                       "dead sheep", "dead cow", "dead bird", "dead fish",
                       "lifeless animal", "animal muerto", "cadaver de",
                       "res muerta", "oveja muerta", "ganado muerto")),
    ("herida_lesion", ("wound", "wounds", "puncture", "injury", "injured",
                       "lesion", "bleeding", "herida", "heridas", "lesion",
                       "orificio", "mordedura")),
    ("violencia_historica", ("battle", "war", "massacre", "slaughter",
                             "execution", "invasion", "siege", "batalla",
                             "guerra", "masacre", "matanza", "ejecucion",
                             "degollado", "sacrificio")),
    ("medico_anatomico", ("anatomy", "dissection", "autopsy", "organs",
                          "surgery", "anatomia", "diseccion", "autopsia",
                          "organos", "cirugia", "necropsia")),
    ("armas_conflicto", ("weapon", "rifle", "sword", "gun", "knife blade",
                         "arma", "espada", "fusil", "cuchillo")),
    ("arte_desnudo", ("nude", "naked", "desnudo", "desnuda")),
    ("sustancias", ("drug", "cocaine", "heroin", "opium", "droga", "cocaina",
                    "heroina", "opio")),
]

# Términos GRATUITOS: no aportan al documental y son los que de verdad
# disparan los filtros. Se quitan sin tocar los hechos.
_GRATUITOS = {
    "blood": "", "bloody": "", "blood-soaked": "", "bloodied": "",
    "gore": "", "gory": "", "graphic": "", "gruesome": "", "grisly": "",
    "mutilated": "", "dismembered": "", "entrails": "", "viscera": "",
    "disemboweled": "", "brutal": "", "brutally": "", "torture": "",
    "agony": "", "suffering": "", "screaming": "",
}

# Sustituciones que CONSERVAN el hecho, solo cambian el registro a clínico.
# EN ORDEN: las expresiones de varias palabras van primero, para no dejar
# duplicados («puncture wounds» → «puncture clinical puncture marks»).
# Lo que NUNCA se toca: dead, lifeless, carcass, deceased, la especie, el
# número y la ubicación — son los hechos que la narración afirma.
_CLINICO: list[tuple[str, str]] = [
    (r"puncture wounds", "puncture marks"),
    (r"puncture wound", "puncture mark"),
    (r"open wounds?", "clinical lesions"),
    (r"dead body", "lifeless body"),
    # «lesion», no «mark»: el suavizado viejo dejaba una MANCHA genérica y se
    # perdía que había una herida. «lesion» es registro clínico y conserva el
    # hecho.
    (r"wounds", "clinical lesions"),
    (r"wound", "clinical lesion"),
    (r"injuries", "clinical lesions"),
    (r"injury", "clinical lesion"),
    (r"corpses", "lifeless bodies"),
    (r"corpse", "lifeless body"),
    (r"slaughter", "aftermath"),
    (r"massacre", "historical aftermath"),
    (r"killing", "historical conflict"),
    (r"kill", "defeat"),
    (r"naked", "draped"),
    (r"nude", "draped figure"),
    (r"severed", "detached"),
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Detección COMPUESTA: «muerte + sujeto». Una lista de frases fijas nunca
# cubre las variantes del español («oveja muerta», «ovejas muertas», «las
# reses sin vida»); combinar marcador de muerte + sustantivo sí.
_MUERTE_MARCA = ("muert", "sin vida", "cadaver", "fallecid", "inerte",
                 "dead", "lifeless", "carcass", "deceased")
_ANIMALES = ("oveja", "ovejas", "cabra", "cabras", "cabrito", "vaca", "vacas",
             "res", "reses", "ganado", "animal", "animales", "perro", "gato",
             "caballo", "cerdo", "ave", "aves", "pajaro", "pez", "peces",
             "goat", "goats", "sheep", "cow", "cows", "cattle", "animal",
             "animals", "dog", "cat", "horse", "bird", "birds", "fish")
_HUMANOS = ("hombre", "mujer", "nino", "nina", "persona", "personas",
            "cuerpo humano", "humano", "humanos", "soldado", "soldados",
            "man", "woman", "child", "person", "people", "human", "soldier")


def detectar_sensibilidad(prompt: str, narracion: str = "") -> str:
    """Categoría detectada en el texto, o 'ninguna'. Es la red de seguridad
    para cuando el director no marcó la escena (o el proyecto viene de una
    versión anterior)."""
    texto = _norm(prompt) + " " + _norm(narracion)
    for categoria, señales in _SEÑALES:
        if any(s in texto for s in señales):
            return categoria
    # Regla compuesta, por si ninguna frase fija coincidió
    if any(m in texto for m in _MUERTE_MARCA):
        if any(re.search(rf"\b{a}\b", texto) for a in _HUMANOS):
            return "restos_humanos"
        if any(re.search(rf"\b{a}\b", texto) for a in _ANIMALES):
            return "muerte_animal"
    return "ninguna"


def encuadrar(prompt: str, sensibilidad: str = "", narracion: str = "") -> tuple[str, str]:
    """(prompt encuadrado, categoría aplicada). Antepone el registro
    documental que corresponda; si no hay nada sensible, devuelve el prompt
    intacto (no se estorba a las escenas normales con texto de más)."""
    categoria = sensibilidad if sensibilidad in FRAMINGS else ""
    if not categoria:
        detectada = detectar_sensibilidad(prompt, narracion)
        categoria = detectada if detectada != "ninguna" else ""
    if not categoria:
        return prompt, "ninguna"
    encuadre = FRAMINGS[categoria]
    if _norm(encuadre)[:40] in _norm(prompt):     # ya venía encuadrado
        return prompt, categoria
    return f"{encuadre}. {prompt}", categoria


def suavizar(prompt: str) -> str:
    """Segundo intento tras un rechazo de contenido: quita lo GRATUITO y pasa
    a registro clínico, CONSERVANDO los hechos (especie, estado sin vida,
    número, ubicación). El suavizado anterior los destruía."""
    out = prompt
    for palabra, reemplazo in _GRATUITOS.items():
        out = re.sub(rf"\b{re.escape(palabra)}\b", reemplazo, out, flags=re.I)
    for patron, reemplazo in _CLINICO:
        out = re.sub(rf"\b{patron}\b", reemplazo, out, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out).strip(" ,.")
    return ("educational documentary illustration, clinical and respectful, "
            "non-graphic, no blood, no gore, suitable for a general "
            "audience. " + out)


# --- auditoría de fidelidad (sin coste, sin modelo) ------------------------

_NUM_ES = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
}
_NUM_EN = {
    1: ("one", "single"), 2: ("two", "pair"), 3: ("three",), 4: ("four",),
    5: ("five",), 6: ("six",), 7: ("seven",), 8: ("eight",), 9: ("nine",),
    10: ("ten",), 11: ("eleven",), 12: ("twelve",), 13: ("thirteen",),
    14: ("fourteen",), 15: ("fifteen",), 16: ("sixteen",),
    17: ("seventeen",), 18: ("eighteen",), 19: ("nineteen",),
    20: ("twenty",),
}
_MUERTE_ES = ("muerto", "muerta", "muertos", "muertas", "sin vida", "cadaver",
              "cadaveres", "fallecido", "fallecida", "inerte", "difunto")
_MUERTE_EN = ("dead", "lifeless", "carcass", "carcasses", "deceased",
              "motionless", "remains")

# UBICACIÓN EXACTA: si la narración sitúa una marca o herida en una parte
# concreta del cuerpo, el prompt tiene que decirlo — «una herida en el cuello»
# dibujada en el costado contradice lo narrado igual que un número equivocado.
_PARTES: dict[str, tuple[str, ...]] = {
    "cuello": ("neck", "throat"),
    "garganta": ("throat", "neck"),
    "pecho": ("chest", "breast"),
    "torax": ("chest", "thorax"),
    "espalda": ("back",),
    "lomo": ("back", "loin"),
    "cabeza": ("head", "skull"),
    "craneo": ("skull", "head"),
    "vientre": ("belly", "abdomen"),
    "abdomen": ("abdomen", "belly"),
    "costado": ("side", "flank"),
    "flanco": ("flank", "side"),
    "pata": ("leg", "paw", "hoof"),
    "patas": ("legs", "paws", "hooves"),
    "pierna": ("leg",),
    "brazo": ("arm",),
    "hombro": ("shoulder",),
    "oreja": ("ear",),
    "ojo": ("eye",),
    "ubre": ("udder",),
    "cola": ("tail",),
}


def _numeros_narrados(narracion: str) -> set[int]:
    """Cantidades CONCRETAS y pequeñas que afirma la narración (las que un
    generador de imágenes puede respetar y suele fallar). Se ignoran las
    cifras grandes: «60.000 personas» no es una cantidad dibujable."""
    t = _norm(narracion)
    out: set[int] = set()
    for m in re.finditer(r"\b(\d{1,2})\b", t):
        n = int(m.group(1))
        if 2 <= n <= 20:
            out.add(n)
    for palabra, n in _NUM_ES.items():
        if re.search(rf"\b{palabra}\b", t) and n >= 2:
            out.add(n)
    return out


def auditar_fidelidad(narracion: str, prompt: str) -> list[str]:
    """Hechos de la narración que el prompt NO refleja. Lista vacía = bien.

    Comprueba lo que de verdad falló en los videos del creador: la CANTIDAD
    exacta y el ESTADO sin vida. Es determinista y gratis — el control con
    visión sigue existiendo, pero ya no es la primera línea de defensa."""
    faltan: list[str] = []
    p = _norm(prompt)

    for n in sorted(_numeros_narrados(narracion)):
        formas = [str(n), *(_NUM_EN.get(n) or ())]
        if not any(re.search(rf"\b{f}\b", p) for f in formas):
            faltan.append(f"la cantidad «{n}» que afirma la narración")

    if any(m in _norm(narracion) for m in _MUERTE_ES) \
            and not any(m in p for m in _MUERTE_EN):
        faltan.append("el estado SIN VIDA que afirma la narración")

    # Ubicación exacta: solo se exige cuando la narración habla de una marca,
    # herida u orificio EN esa parte (mencionar «la cabeza del imperio» no es
    # una ubicación anatómica).
    n = _norm(narracion)
    if any(w in n for w in ("herida", "heridas", "orificio", "orificios",
                            "marca", "marcas", "mordedura", "corte", "lesion",
                            "perforacion", "punzada")):
        for parte, equivalentes in _PARTES.items():
            if re.search(rf"\b{parte}\b", n) and not any(
                    re.search(rf"\b{e}\b", p) for e in equivalentes):
                faltan.append(f"la ubicación «{parte}» que afirma la narración")
                break   # una basta para avisar; no se satura al creador
    return faltan
