"""Command line: python -m waterhammer --pipe copper_10x0.6 --length 8 --flow 6 --valve solenoid"""

from __future__ import annotations

import argparse
import json
import sys

from .model import VALVE_CLOSURE_TIMES, Inputs, Limits, assess
from .properties import MATERIALS, PRESETS, Pipe


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="waterhammer", description=__doc__)
    g = p.add_argument_group("pipe (a preset, or OD/wall/material)")
    g.add_argument("--pipe", choices=sorted(PRESETS), help="pipe preset")
    g.add_argument("--od", type=float, help="outside diameter, mm")
    g.add_argument("--wall", type=float, help="wall thickness, mm")
    g.add_argument("--material", choices=sorted(MATERIALS), default="copper")
    g.add_argument("--aluminium", type=float, default=0.0, help="Al layer, mm (multilayer pipe)")
    p.add_argument("--length", type=float, required=True, help="m, valve to nearest reflection point")
    p.add_argument("--flow", type=float, required=True, help="l/min")
    v = p.add_mutually_exclusive_group()
    v.add_argument("--valve", choices=sorted(VALVE_CLOSURE_TIMES), default="single_lever_mixer")
    v.add_argument("--closure-time", type=float, help="effective valve closure time, s")
    p.add_argument("--pressure", type=float, default=3.0, help="rest (static) pressure, bar gauge")
    p.add_argument("--temperature", type=float, default=55.0, help="C")
    p.add_argument("--restraint", choices=["anchored", "expansion_joints", "upstream_anchor"], default="anchored")
    p.add_argument("--max-surge", type=float, default=2.0, help="bar")
    p.add_argument("--rating", type=float, default=10.0, help="pipe/fitting pressure rating at temperature, bar")
    p.add_argument("--no-sim", action="store_true", help="closed-form only")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.pipe:
        pipe = PRESETS[a.pipe]
    elif a.od and a.wall:
        pipe = Pipe(a.od, a.wall, MATERIALS[a.material], aluminium_mm=a.aluminium)
    else:
        print("give --pipe, or --od and --wall", file=sys.stderr)
        return 2
    tc = a.closure_time if a.closure_time is not None else VALVE_CLOSURE_TIMES[a.valve]
    res = assess(Inputs(pipe, a.length, a.flow, a.pressure, a.temperature, tc, a.restraint,
                        Limits(max_surge_bar=a.max_surge, pressure_rating_bar=a.rating), simulate=not a.no_sim))
    if a.json:
        print(json.dumps(res.to_dict(), indent=2, default=str))
        return 0
    print(pipe.describe())
    print(f"L = {a.length:g} m, Q = {a.flow:g} l/min, rest pressure {a.pressure:g} bar, {a.temperature:g} C, "
          f"closure {tc * 1e3:.0f} ms")
    print(f"velocity {res.velocity_m_s:.2f} m/s | wave speed {res.wave_speed_m_s:.0f} m/s | "
          f"2L/a {res.critical_time_s * 1e3:.1f} ms ({res.regime} closure)")
    moc = "n/a" if res.moc_surge_bar is None else f"{res.moc_surge_bar:.2f}"
    print(f"surge: Joukowsky {res.joukowsky_bar:.2f} bar, closed form {res.closed_form_surge_bar:.2f} bar, "
          f"MOC {moc} bar -> design {res.design_surge_bar:.2f} bar; peak {res.peak_gauge_bar:.2f} bar g")
    for c in res.checks:
        tag = "PASS" if c.passed else ("FAIL" if c.governs else "ADVISE")
        print(f"  [{tag:6}] {c.name}: {c.value:.2f} vs {c.limit:.2f} {c.unit}")
    print("MITIGATION REQUIRED" if res.mitigation_required else "No mitigation required")
    for r in res.recommendations:
        print(f"  - {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
