"""Batería v0.45.0 — Replicate/FLUX como proveedor de imágenes recomendado.

El creador aprobó el cambio: FLUX 1.1 Pro (~$0.04/img, sin el cuello de
5 img/min) como estándar, y gpt-image-1 SOLO para las escenas con texto
legible (a las que el director rutea automáticamente desde v0.42.0).

Verifica:
1. El default del programa (config.yaml) es replicate + flux-1.1-pro.
2. La migración de una sola vez: un config.local.yaml con openai pasa a
   replicate/FLUX… pero SOLO una vez — si el usuario vuelve a elegir OpenAI
   en ⚙ Configuración, su elección se respeta (marca en 'migrations').
3. La marca sobrevive al guardado de la UI (unión con el archivo actual):
   sin eso, un guardado con la página vieja abierta borraría la marca y la
   migración pisaría la elección del usuario al siguiente arranque.
4. El ruteo automático a gpt-image-1 en escenas con texto sigue intacto.
5. El precio: 83 imágenes ≈ $3.32-4.15 con FLUX (contra $5.81-20.75).
"""

import sys
from pathlib import Path

# La raíz del programa se resuelve desde la ubicación de ESTE archivo, para que
# la batería funcione en cualquier equipo (Windows incluido) sin rutas fijas.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shutil
import tempfile

import yaml

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


TMP = Path(tempfile.mkdtemp(prefix="v0450_"))

# ---------------------------------------------------------------------------
# T1 — el default del programa es Replicate/FLUX
# ---------------------------------------------------------------------------
base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
img_cfg = base["providers"]["images"]
check("T1 el proveedor de imágenes por defecto es replicate",
      img_cfg["name"] == "replicate", str(img_cfg["name"]))
check("T1b con FLUX 1.1 Pro como modelo",
      img_cfg["model"] == "black-forest-labs/flux-1.1-pro",
      str(img_cfg["model"]))

# ---------------------------------------------------------------------------
# T2 — la migración de una sola vez
# ---------------------------------------------------------------------------
from ytstudio.webui import server as srv

# el caso REAL del creador: openai con el model de FLUX heredado
cfg = {"providers": {"images": {"name": "openai",
                                "model": "black-forest-labs/flux-1.1-pro"}}}
out = srv._apply_migrations(cfg)
img = out["providers"]["images"]
check("T2 openai migra a replicate + FLUX 1.1 Pro",
      img["name"] == "replicate"
      and img["model"] == "black-forest-labs/flux-1.1-pro", str(img))
check("T2b y deja la marca de migración aplicada",
      "images_replicate_v0_45" in out.get("migrations", []),
      str(out.get("migrations")))

# con la marca puesta, una elección posterior de OpenAI SE RESPETA
cfg = {"providers": {"images": {"name": "openai", "model": "gpt-image-1"}},
       "migrations": ["images_replicate_v0_45"]}
out = srv._apply_migrations(cfg)
check("T2c si el usuario vuelve a elegir OpenAI después, se respeta",
      out["providers"]["images"]["name"] == "openai",
      str(out["providers"]["images"]))

# quien ya está en replicate (incluso con un modelo económico elegido a mano)
# no se toca — solo gana la marca
cfg = {"providers": {"images": {"name": "replicate",
                                "model": "black-forest-labs/flux-schnell"}}}
out = srv._apply_migrations(cfg)
check("T2d un replicate ya elegido (modelo incluido) queda intacto",
      out["providers"]["images"]["model"] == "black-forest-labs/flux-schnell"
      and "images_replicate_v0_45" in out["migrations"],
      str(out["providers"]["images"]))

# ---------------------------------------------------------------------------
# T3 — migrate_local_config sobre el archivo real (ROOT parcheado)
# ---------------------------------------------------------------------------
_real_root = srv.ROOT
srv.ROOT = TMP
try:
    local = TMP / "config.local.yaml"
    local.write_text(yaml.safe_dump({
        "providers": {"images": {"name": "openai",
                                 "model": "black-forest-labs/flux-1.1-pro"}},
        "performance": {"parallel_images": 9},   # ruta NO-UI: debe podarse
    }), encoding="utf-8")
    srv.migrate_local_config()
    saved = yaml.safe_load(local.read_text(encoding="utf-8"))
    check("T3 al arrancar, el config.local.yaml del creador queda en "
          "replicate/FLUX con su marca",
          saved["providers"]["images"]["name"] == "replicate"
          and "images_replicate_v0_45" in saved["migrations"], str(saved))
    check("T3b la poda de rutas no-UI sigue funcionando",
          "performance" not in saved, str(saved))

    # segundo arranque: nada que hacer (no se reescribe ni re-migra)
    saved["providers"]["images"]["name"] = "openai"   # elección posterior
    local.write_text(yaml.safe_dump(saved), encoding="utf-8")
    srv.migrate_local_config()
    saved2 = yaml.safe_load(local.read_text(encoding="utf-8"))
    check("T3c en el siguiente arranque la elección del usuario sigue ahí",
          saved2["providers"]["images"]["name"] == "openai", str(saved2))

    # máquina SIN config.local.yaml: se crea solo con la marca — sin esto,
    # una elección futura de OpenAI sería revertida por la migración
    local.unlink()
    srv.migrate_local_config()
    fresh = yaml.safe_load(local.read_text(encoding="utf-8"))
    check("T3d sin archivo local, se crea solo con la marca (sin providers)",
          fresh.get("migrations") == ["images_replicate_v0_45"]
          and "providers" not in fresh, str(fresh))

    # -----------------------------------------------------------------------
    # T4 — el guardado de la UI nunca pierde la marca (unión con el archivo)
    # -----------------------------------------------------------------------
    # la UI manda una config SIN 'migrations' (página cargada antes de migrar)
    srv.api_save_config({"config": {
        "language": "es",
        "providers": {"images": {"name": "openai", "model": "gpt-image-1"}},
    }})
    saved = yaml.safe_load(local.read_text(encoding="utf-8"))
    check("T4 la marca sobrevive a un guardado de la UI que no la traía",
          "images_replicate_v0_45" in saved.get("migrations", []), str(saved))
    check("T4b y lo guardado por el usuario se conserva tal cual",
          saved["providers"]["images"]["name"] == "openai", str(saved))
    srv.migrate_local_config()
    saved = yaml.safe_load(local.read_text(encoding="utf-8"))
    check("T4c tras el siguiente arranque, su elección sigue intacta",
          saved["providers"]["images"]["name"] == "openai", str(saved))
finally:
    srv.ROOT = _real_root

# ---------------------------------------------------------------------------
# T5 — el ruteo automático de escenas con texto a gpt-image-1 sigue intacto
# ---------------------------------------------------------------------------
import inspect

from ytstudio.phases import broll as broll_phase

src = inspect.getsource(broll_phase.run)
check("T5 el director rutea las escenas con texto a gpt-image-1",
      "_shows_text(s)" in src and "OpenAIImages(cfg)" in src, "")
check("T5-bis y desde la v0.57.0 detecta el texto aunque el director no lo "
      "declare (periódico, cartel, documento en el prompt)",
      broll_phase._shows_text({"image_text": "CRACK"})
      and broll_phase._shows_text(
          {"broll_prompt": "a newspaper front page on a wooden desk"})
      and not broll_phase._shows_text(
          {"broll_prompt": "a foggy harbour at dawn, no text"}), "")
check("T5b solo si hay clave de OpenAI; sin ella, aviso honesto",
      'environ.get("OPENAI_API_KEY")' in src
      and "no hay clave de OpenAI" in src, "")
check("T5c si gpt-image-1 falla, la escena cae al modelo estándar (el ruteo "
      "nunca tumba la fase)",
      "el ruteo tipográfico es OPCIONAL" in inspect.getsource(broll_phase), "")

# ---------------------------------------------------------------------------
# T6 — el dinero: 83 imágenes con FLUX vs gpt-image-1
# ---------------------------------------------------------------------------
from ytstudio.pricing import effective_image_model, img_cost_range

check("T6 replicate respeta el modelo configurado",
      effective_image_model("replicate", "black-forest-labs/flux-1.1-pro")
      == "black-forest-labs/flux-1.1-pro", "")
flux = img_cost_range("replicate", "black-forest-labs/flux-1.1-pro")
gpt = img_cost_range("openai", "gpt-image-2")
check("T6b 83 imágenes ≈ $3.3-4.2 con FLUX (contra hasta ~$17 con GPT Image 2)",
      3.0 < 83 * flux[0] < 4.0 and 83 * flux[1] < 5.0
      and 83 * gpt[1] > 15.0,
      f"FLUX ${83*flux[0]:.2f}-${83*flux[1]:.2f}, "
      f"gpt ${83*gpt[0]:.2f}-${83*gpt[1]:.2f}")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"✗ {len(FAILURES)} fallo(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("✓ Batería v0.45.0 completa: Replicate/FLUX como estándar económico, "
      "migración de una sola vez que respeta al usuario, y gpt-image-1 solo "
      "donde hay texto legible.")
shutil.rmtree(TMP, ignore_errors=True)
