"""Screening table: longest run (valve to reflection point) that needs no
water hammer mitigation, for small DHW pipes, 1-6 l/min and common valves.

    python examples/waterhammer_sweep.py   -> results/waterhammer/screening.csv
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from waterhammer import assess_simple  # noqa: E402

PIPES = ["copper_10x0.6", "copper_12x0.6", "copper_15x0.7", "pex_10x1.5", "pex_12x2.0", "mlcp_12x1.6"]
VALVES = ["solenoid", "single_lever_mixer", "quarter_turn", "screw_down"]
FLOWS = [1, 2, 3, 4, 5, 6]
LENGTHS = [1, 2, 3, 5, 8, 10, 15, 20, 25, 30]


def main():
    out = Path(__file__).resolve().parents[1] / "results" / "waterhammer" / "screening.csv"
    rows = []
    for pipe in PIPES:
        for valve in VALVES:
            for flow in FLOWS:
                ok = 0
                last = None
                for L in LENGTHS:
                    try:
                        r = assess_simple(pipe, L, flow, valve)
                    except ValueError:  # friction exceeds supply pressure
                        break
                    last = r
                    if r.mitigation_required:
                        break
                    ok = L
                rows.append({
                    "pipe": pipe, "valve": valve, "flow_l_min": flow,
                    "velocity_m_s": round(last.velocity_m_s, 2) if last else "",
                    "wave_speed_m_s": round(last.wave_speed_m_s) if last else "",
                    "joukowsky_bar": round(last.joukowsky_bar, 2) if last else "",
                    "max_length_without_mitigation_m": f">={ok}" if ok == LENGTHS[-1] else ok,
                })
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # compact pivot for the docs: max length by pipe/valve (rows) and flow (cols)
    print("| pipe | valve | " + " | ".join(f"{f} l/min" for f in FLOWS) + " |")
    print("|---|---|" + "---|" * len(FLOWS))
    for pipe in PIPES:
        for valve in VALVES:
            cells = [str(r["max_length_without_mitigation_m"]) for r in rows if r["pipe"] == pipe and r["valve"] == valve]
            print(f"| {pipe} | {valve} | " + " | ".join(cells) + " |")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
