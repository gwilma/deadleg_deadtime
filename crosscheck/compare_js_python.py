"""Run the same cases through the Python package and the JavaScript port and compare.

    python crosscheck/compare_js_python.py
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from deadleg import PRESETS, Scenario, simulate

HERE = Path(__file__).parent


def python_case(c, nx=200, nr=6, axial=True):
    air = c.get("airArea", None)
    vol = math.inf if air == "inf" else (None if air is None else air * c["length"])
    sc = Scenario(PRESETS[c["pipe"]], c["length"], c["flow"], duration=c["duration"], T_initial=c["T0"],
                  T_inlet=c["Tin"], air_volume=vol, air_loss_UA=c.get("airUA", 0.0),
                  T_environment=c.get("Tenv"), n_axial=nx, n_radial=nr, wall_axial_conduction=axial)
    return simulate(sc)


def main(nx=200, nr=6, axial=True):
    cases = json.loads((HERE / "cases.json").read_text())
    out = HERE / "js_results.json"
    subprocess.run(["node", str(HERE / "run_js.js"), str(HERE / "cases.json"), str(out), str(nx), str(nr),
                    "1" if axial else "0"], check=True)
    js = json.loads(out.read_text())
    rows = []
    for c in cases:
        p = python_case(c, nx, nr, axial)
        j = js[c["id"]]
        n = min(len(p.t), len(j["t"]))
        dT = np.max(np.abs(p.T_out[:n] - np.array(j["Tout"][:n])))
        dTa = np.max(np.abs(p.T_air[:n] - np.array(j["Tair"][:n])))
        row = {"case": c["id"], "steps_py": len(p.t), "steps_js": len(j["t"]), "max_dT_out": dT, "max_dT_air": dTa}
        for T in (40, 45, 50):
            row[f"t{T}_py"] = p.time_to_reach(T)
            row[f"t{T}_js"] = j[f"t{T}"]
        row["ebal_js"] = j["ebal"]
        rows.append(row)
    return rows


if __name__ == "__main__":
    for r in main():
        print({k: (f"{v:.3g}" if isinstance(v, float) else v) for k, v in r.items()})
