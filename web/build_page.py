"""Build web/index.html: the water hammer calculator as one self-contained page.

    python web/build_page.py

The page's model (web/model.js) is a port of waterhammer/model.py; this script
injects the property tables from waterhammer/properties.py so all three
versions (Python, Excel, web) use one data set. web/check_js.py compares the
JavaScript with the Python model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from waterhammer.model import VALVE_CLOSURE_TIMES  # noqa: E402
from waterhammer.properties import (  # noqa: E402
    _WATER_DENSITY,
    _WATER_SOUND_SPEED,
    _WATER_VAPOUR_PRESSURE,
    ALUMINIUM,
    MATERIALS,
    PRESETS,
)


def data() -> dict:
    mats = {k: {"name": m.name, "poisson": m.poisson, "roughness": m.roughness, "modulus": m.modulus}
            for k, m in MATERIALS.items()}
    presets = {}
    for key, p in PRESETS.items():
        mkey = next(k for k, m in MATERIALS.items() if m is p.material)
        presets[key] = {"name": p.name, "od": p.outer_diameter_mm, "wall": p.wall_mm, "material": mkey,
                        "al": p.aluminium_mm}
    return {
        "water": {"density": _WATER_DENSITY, "sound": _WATER_SOUND_SPEED, "vapour": _WATER_VAPOUR_PRESSURE},
        "materials": mats,
        "aluminium": {"modulus": ALUMINIUM.modulus},
        "presets": presets,
        "valves": VALVE_CLOSURE_TIMES,
    }


def model_js() -> str:
    src = (HERE / "model.js").read_text()
    return src.replace("/*DATA*/null", json.dumps(data(), separators=(",", ":")))


def build() -> Path:
    page = (HERE / "template.html").read_text().replace("/*MODEL*/", model_js())
    out = HERE / "index.html"
    out.write_text(page)
    return out


if __name__ == "__main__":
    print(build())
