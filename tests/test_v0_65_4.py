"""Batería v0.65.4 — la voz de un proveedor puesta en otro tiraba la corrida.

Caso real del creador: la fase de Voz murió con «Cartesia no pudo sintetizar
la voz — invalid voice specification: voice ID must be a valid UUID», después
de 4 minutos y $0.67 gastados en las fases anteriores.

La causa es de diseño y afecta a los cuatro proveedores: cada casa nombra sus
voces a su manera —ElevenLabs «onwK4e9ZLuTAKqWW03F9», Cartesia un UUID,
OpenAI «onyx», Edge «es-MX-JorgeNeural»— pero el programa guarda UNA sola voz
en `providers.tts.voice`. Al cambiar de proveedor en Ajustes, la voz del
anterior se queda puesta y el nuevo la rechaza. Y el rechazo llegaba en la
fase 5 de 11: con el dinero de las cuatro anteriores ya gastado.

Dos redes, no una:

1.  ANTES DE EMPEZAR, `tts_voice_problem()` lo detecta y avisa en la corrida
    y en el panel de Atención — cuando corregirlo es gratis.
2.  Y SI AUN ASÍ SE LLEGA, cada proveedor comprueba que la voz tenga SU
    formato: si no, usa la suya por defecto y lo avisa. Perder la voz elegida
    es molesto; perder la corrida entera es caro.

Las comprobaciones son laxas a propósito: cazan el desajuste evidente y dejan
pasar una voz nueva que el catálogo aún no conozca. Bloquear una voz legítima
sería peor que dejar pasar una rara.

Ninguna prueba usa claves ni internet.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


from ytstudio.catalog import (CATALOG, tts_voice_problem,  # noqa: E402
                              voice_matches_provider)

# ---------------------------------------------------------------------------
# T1 — cada formato de voz se reconoce
# ---------------------------------------------------------------------------
print("T1 el formato de cada casa")

CASOS = [
    ("cartesia", "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c", True),
    ("cartesia", "onwK4e9ZLuTAKqWW03F9", False),      # el caso real
    ("elevenlabs", "onwK4e9ZLuTAKqWW03F9", True),
    ("elevenlabs", "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c", False),
    ("edge", "es-MX-JorgeNeural", True),
    ("edge", "onyx", False),
    ("openai", "onyx", True),
    ("openai", "es-MX-JorgeNeural", False),
]
for prov, voz, esperado in CASOS:
    check(f"T1a {prov} + «{voz[:26]}»",
          voice_matches_provider(prov, voz) is esperado)

check("T1b una voz vacía no es un problema (se usa la de la casa)",
      voice_matches_provider("cartesia", ""))
check("T1c un proveedor que no sabemos comprobar pasa sin molestar",
      voice_matches_provider("mock", "lo-que-sea")
      and voice_matches_provider("inventado", "xyz"))

# Las voces que el propio catálogo ofrece TIENEN que pasar su comprobación:
# si no, el programa se estaría contradiciendo a sí mismo.
for opcion in CATALOG["tts"]["options"]:
    for v in (opcion.get("voices") or []):
        check(f"T1d el catálogo se respeta a sí mismo: {opcion['name']}/{v['id'][:22]}",
              voice_matches_provider(opcion["name"], v["id"]), v["id"])

# ---------------------------------------------------------------------------
# T2 — el aviso ANTES de gastar
# ---------------------------------------------------------------------------
print("\nT2 el aviso antes de empezar")

CRUZADO = {"language": "es",
           "providers": {"tts": {"name": "cartesia",
                                 "voice": "onwK4e9ZLuTAKqWW03F9"}}}
BUENO = {"language": "es",
         "providers": {"tts": {"name": "cartesia",
                               "voice": "11111111-2222-3333-4444-555555555555"}}}

aviso = tts_voice_problem(CRUZADO)
check("T2a el caso real se detecta", aviso is not None)
check("T2b el aviso nombra la voz que está mal",
      "onwK4e9ZLuTAKqWW03F9" in (aviso or ""))
check("T2c explica POR QUÉ pasa (se cambió de proveedor)",
      "cambiar de proveedor" in (aviso or ""))
check("T2d da un ejemplo del formato correcto",
      "5c5ad5e7" in (aviso or ""))
check("T2e y dice dónde arreglarlo", "Ajustes" in (aviso or ""))
check("T2f una configuración correcta NO genera aviso falso",
      tts_voice_problem(BUENO) is None)
check("T2g ni una sin voz elegida",
      tts_voice_problem({"providers": {"tts": {"name": "cartesia"}}}) is None)

PIPE = (ROOT / "ytstudio" / "pipeline.py").read_text(encoding="utf-8")
check("T2h la corrida lo comprueba al arrancar",
      "tts_voice_problem" in PIPE)
check("T2i y lo deja en el panel de Atención, no solo en el log",
      "project.add_warning(problema)" in PIPE)

# ---------------------------------------------------------------------------
# T3 — la segunda red: el proveedor no se cae
# ---------------------------------------------------------------------------
print("\nT3 el proveedor usa su voz por defecto en vez de morir")

from ytstudio.providers import tts  # noqa: E402

os.environ.setdefault("CARTESIA_API_KEY", "prueba")
c = tts.CartesiaTTS(CRUZADO)
check("T3a Cartesia descarta la voz cruzada",
      c.voice != "onwK4e9ZLuTAKqWW03F9", c.voice)
check("T3b y usa la suya, que sí es un UUID válido",
      c.voice == tts.CartesiaTTS.DEFAULT_VOICE
      and voice_matches_provider("cartesia", c.voice), c.voice)
check("T3c una voz suya correcta se respeta tal cual",
      tts.CartesiaTTS(BUENO).voice
      == "11111111-2222-3333-4444-555555555555")

ed = tts.EdgeTTS({"providers": {"tts": {"name": "edge", "voice": "onyx"}}})
check("T3d Edge descarta un nombre de OpenAI",
      ed.voice == "es-MX-JorgeNeural", ed.voice)
check("T3e y respeta una voz suya",
      tts.EdgeTTS({"providers": {"tts": {"name": "edge",
                                         "voice": "es-ES-AlvaroNeural"}}}).voice
      == "es-ES-AlvaroNeural")

TTS_SRC = (ROOT / "ytstudio" / "providers" / "tts.py").read_text(encoding="utf-8")
check("T3f los CUATRO proveedores pasan por la misma comprobación",
      TTS_SRC.count("_pick_voice(cfg,") == 4,
      str(TTS_SRC.count("_pick_voice(cfg,")))
check("T3g y ninguno vuelve a leer la voz a pelo",
      '["tts"].get("voice") or' not in TTS_SRC)
check("T3h la sustitución se avisa, no se hace a escondidas",
      "notify(" in TTS_SRC.split("def _pick_voice")[1][:1200])
check("T3i y se explica por qué existe todo esto",
      "una corrida entera al creador" in TTS_SRC)

# ---------------------------------------------------------------------------
# T4 — documentación
# ---------------------------------------------------------------------------
print("\nT4 manuales y registro de cambios")

for nombre, ruta in (("nuevo", ROOT / "MANUAL.md"),
                     ("clásico", ROOT / "MANUAL-clasica.md")):
    texto = ruta.read_text(encoding="utf-8")
    check(f"T4a el manual {nombre} avisa de la voz al cambiar de proveedor",
          "voice ID" in texto or "cambias de proveedor de voz" in texto)
    check(f"T4b el manual {nombre} declara qué versión documenta",
          bool(re.search(r"MANUAL_VERSION:\s*[0-9]+\.[0-9]+\.[0-9]+", texto)))

CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
check("T4c el CHANGELOG cuenta lo que arregló la v0.65.4",
      "## v0.65.4" in CHANGELOG)

print("\n" + "=" * 62)
if FAILURES:
    print(f"✘ {len(FAILURES)} comprobación(es) fallaron:")
    for f in FAILURES:
        print(f"   · {f}")
    sys.exit(1)
print("✔ v0.65.4: la voz de otro proveedor ya no tira la corrida.")
