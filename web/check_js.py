"""Run web/model.js under Node for several cases and compare with the Python model.

    python web/check_js.py      (needs node)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from build_page import model_js  # noqa: E402

from waterhammer import MATERIALS, PRESETS, VALVE_CLOSURE_TIMES, Inputs, Limits, Pipe, assess  # noqa: E402

CASES = [
    dict(pipe="copper_10x0.6", length=8, flow=6, valve="solenoid"),
    dict(pipe="pex_12x2.0", length=8, flow=6, valve="single_lever_mixer"),
    dict(pipe="mlcp_12x1.6", length=15, flow=4, valve="quarter_turn", temperature=60),
    dict(pipe="copper_15x0.7", length=3, flow=4, valve="screw_down", pressure=4.0),
    dict(pipe="custom", od=12, wall=2.0, material="pex", al=0, length=10, flow=4, closure=0.0,
         restraint="expansion_joints"),
    dict(pipe="pb_15x1.9", length=20, flow=3, valve="thermostatic_shower", maxSurge=3.0, rating=6.0),
]
DEFAULTS = dict(pressure=3.0, temperature=55.0, restraint="anchored", maxSurge=2.0, rating=10.0,
                advisoryVelocity=1.5, gasIndex=1.4)


def python(c: dict) -> dict:
    c = {**DEFAULTS, **c}
    pipe = (Pipe(c["od"], c["wall"], MATERIALS[c["material"]], aluminium_mm=c["al"]) if c["pipe"] == "custom"
            else PRESETS[c["pipe"]])
    tc = c.get("closure", VALVE_CLOSURE_TIMES.get(c.get("valve", ""), None))
    r = assess(Inputs(pipe, c["length"], c["flow"], c["pressure"], c["temperature"], tc, c["restraint"],
                      Limits(max_surge_bar=c["maxSurge"], pressure_rating_bar=c["rating"],
                             advisory_velocity_m_s=c["advisoryVelocity"]), True, c["gasIndex"]))
    return {"waveSpeed": r.wave_speed_m_s, "velocity": r.velocity_m_s, "closedFormBar": r.closed_form_surge_bar,
            "mocSurgeBar": r.moc_surge_bar, "designSurgeBar": r.design_surge_bar, "minBar": r.min_gauge_bar,
            "required": r.mitigation_required, "minClosureTime": r.min_closure_time_s,
            "maxFlowInstant": r.max_flow_for_instant_closure_l_min, "arresterMl": r.arrester_precharge_volume_ml}


def main() -> int:
    runner = """
const M = require(process.argv[2]);
const cases = JSON.parse(process.argv[3]);
const D = %s;
const out = cases.map(c0 => {
  const c = Object.assign({}, D, c0);
  const pipe = c.pipe === "custom" ? M.makePipe(c.od, c.wall, c.material, c.al)
    : (p => M.makePipe(p.od, p.wall, p.material, p.al, p.name))(M.DATA.presets[c.pipe]);
  const closure = c.closure !== undefined ? c.closure : M.DATA.valves[c.valve];
  const r = M.assess(Object.assign({}, c, {pipe, closure}));
  delete r.trace; delete r.checks;
  return r;
});
console.log(JSON.stringify(out));
""" % json.dumps(DEFAULTS)
    with tempfile.TemporaryDirectory() as d:
        mjs = Path(d) / "model.js"
        mjs.write_text(model_js())
        rjs = Path(d) / "run.js"
        rjs.write_text(runner)
        res = subprocess.run(["node", str(rjs), str(mjs), json.dumps(CASES)], capture_output=True, text=True,
                             check=True)
    js = json.loads(res.stdout)
    worst = 0.0
    for c, j in zip(CASES, js):
        p = python(c)
        print(c)
        for k, pv in p.items():
            jv = j[k]
            if isinstance(pv, bool) or pv is None:
                ok = pv == jv
                print(f"  {k:15} js {jv!s:>14}  python {pv!s:>14}  {'ok' if ok else 'MISMATCH'}")
                worst = max(worst, 0 if ok else 1)
                continue
            rel = abs(jv - pv) / max(abs(pv), 1e-9)
            worst = max(worst, rel)
            print(f"  {k:15} js {jv:14.6f}  python {pv:14.6f}  rel diff {rel:.1e}")
    print(f"worst relative difference {worst:.1e}")
    return 0 if worst < 1e-9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
