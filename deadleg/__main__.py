"""Command line interface.

    python -m deadleg run scenarios/copper_10mm_3lpm.json --out results/
    python -m deadleg compare scenario.json measured.csv --temp-col outlet_temp_C --interval 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import compare, load_scenario, load_trace, summary, write_result_csv
from .model import simulate


def main(argv=None):
    ap = argparse.ArgumentParser(prog="deadleg")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="simulate a scenario file")
    run.add_argument("scenario")
    run.add_argument("--out", help="directory for <name>.csv and <name>_summary.json")
    cmp_ = sub.add_parser("compare", help="compare a scenario with a measured outlet trace")
    cmp_.add_argument("scenario")
    cmp_.add_argument("measured")
    cmp_.add_argument("--time-col", default="time_s")
    cmp_.add_argument("--temp-col")
    cmp_.add_argument("--threshold", type=float, action="append")
    cmp_.add_argument("--interval", type=float, help="probe reading interval, s")
    args = ap.parse_args(argv)

    sc = load_scenario(args.scenario)
    result = simulate(sc)
    if args.cmd == "run":
        s = summary(result)
        print(json.dumps(s, indent=2))
        if args.out:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(args.scenario).stem
            write_result_csv(result, out / f"{stem}.csv")
            (out / f"{stem}_summary.json").write_text(json.dumps(s, indent=2))
    else:
        t, T = load_trace(args.measured, args.time_col, args.temp_col)
        print(json.dumps(compare(result, t, T, tuple(args.threshold or [45.0]), args.interval), indent=2))


if __name__ == "__main__":
    main()
