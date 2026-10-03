"""Compare the model with the Ref 29 field trial (Ridge & Jones, FairHeat, 2022).

    python examples/ref29_validation.py [path/to/ref29] [--out results/ref29]

Each test: an HIU feeds a manifold and then L metres of MLCP pipe, all
starting at ~19 degC after a cold flush; the outlet probe was read every 5 s
and the delivery time is the first reading at or above 45 degC. The paper also
measured H, the time for the HIU + manifold alone to reach 45 degC.

Model inputs (assumptions, since the paper does not report them):
* pipe inlet = 19 degC until H, then a step to T_supply (default 50 degC, the
  steady outlet seen in Figs 3 and 4);
* pipe wall = homogenised MLCP (deadleg.properties.MLCP), Table 1 dimensions;
* air held at 20 degC (routing and ambient were not reported).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from deadleg import MLCP, Pipe, Scenario, simulate
from deadleg.io import compare, load_trace

T0 = 19.0
T_TARGET = 45.0
READ_INTERVAL = 5.0
PAPER_SLOPE = 1.262  # s per (kg / (l/s)), fitted on Manufacturer A
PAPER_DENSITY = 1015.0  # kg/m3 implied by the paper's Fig 5


def scenario_for(od_mm, wall_mm, length, flow_lpm, H, T_supply, duration, **kw):
    pipe = Pipe(od_mm / 1e3, wall_mm / 1e3, kw.pop("material", MLCP))
    inlet = ([0.0, H - 1e-3, H + 1e-3, 1e5], [T0, T0, T_supply, T_supply])
    return Scenario(
        pipe, length, flow_lpm, duration=duration, T_initial=T0, T_inlet=inlet,
        air_volume=math.inf, T_environment=20.0, n_axial=kw.pop("n_axial", 250), **kw,
    )


def run(data_dir: Path, out_dir: Path, T_supply: float):
    rows = list(csv.DictReader(open(data_dir / "delivery_time_tests.csv")))
    tested = [r for r in rows if r["result_vs_45s"] != "not tested"]
    out_rows = []
    for r in tested:
        od, wall, length = float(r["OD_mm"]), float(r["wall_mm_table1"]), float(r["length_m"])
        flow, H = float(r["flow_l_per_min"]), float(r["H_s_table2"])
        sc = scenario_for(od, wall, length, flow, H, T_supply, duration=1.0)
        C = sc.plug_flow_time()
        sc.duration = H + 3 * C + 90
        res = simulate(sc)
        t_model = res.time_to_reach(T_TARGET)
        reading = READ_INTERVAL * math.ceil(t_model / READ_INTERVAL - 1e-9)
        mass = sc.pipe.wall_area * PAPER_DENSITY * length
        t_paper = H + float(r["C_s_clear_time_calc"]) + PAPER_SLOPE * mass / (flow / 60.0)
        out_rows.append({
            "manufacturer": r["manufacturer"], "OD_mm": od, "wall_mm": wall, "length_m": length,
            "flow_l_per_min": flow, "H_s": H, "C_s_model_geometry": round(C, 2),
            "measured_s": float(r["time_to_45C_s"]),
            "model_s": round(t_model, 2), "model_reading_s": reading,
            "model_warmup_T_s": round(t_model - H - C, 2),
            "paper_formula_s": round(t_paper, 2),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "ref29_delivery_times.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    stats = {}
    for mfr in ("A", "B"):
        sub = [r for r in out_rows if r["manufacturer"] == mfr]
        meas = np.array([r["measured_s"] for r in sub])
        # The probe reading lags the true crossing by 0-5 s, so compare the
        # continuous model time against the middle of the reading window.
        for key, val in (("model", "model_s"), ("model_reading", "model_reading_s"), ("paper_formula", "paper_formula_s")):
            pred = np.array([r[val] for r in sub])
            ref = meas - READ_INTERVAL / 2 if val != "model_reading_s" else meas
            e = pred - ref
            stats[f"{mfr}_{key}"] = {"n": len(sub), "bias_s": round(float(e.mean()), 2), "rmse_s": round(float(np.sqrt((e**2).mean())), 2)}

    traces = {}
    for name, fname, tcol, Tcol, length in (
        ("fig3_5m", "fig3_trace_mfrB_14p2mm_6lpm_5m.csv", "time_s", "outlet_temp_C_approx", 5.0),
        ("fig4_25m", "fig4_trace_mfrB_14p2mm_6lpm_25m.csv", "time_s_shifted_minus5_recommended", "outlet_temp_C_approx", 25.0),
    ):
        t, T = load_trace(data_dir / fname, tcol, Tcol)
        sc = scenario_for(20.0, 2.8, length, 6.0, 5.7, T_supply, duration=float(t.max()) + 5)
        res = simulate(sc)
        traces[name] = {"t_meas": t, "T_meas": T, "t_model": res.t, "T_model": res.T_out}
        stats[name] = compare(res, t, T, (T_TARGET,), READ_INTERVAL)

    (out_dir / "ref29_summary.json").write_text(json.dumps(stats, indent=2))
    return out_rows, stats, traces


def plot(rows, traces, out_dir: Path, T_supply: float):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e4e4e0", "grid.linewidth": 0.8, "font.size": 10})
    colors = {"A": "#2a78d6", "B": "#eb6834"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    ax = axes[0]
    for mfr, label in (("A", "Mfr A (paper's fitting set)"), ("B", "Mfr B (hold-out)")):
        sub = [r for r in rows if r["manufacturer"] == mfr]
        ax.scatter([r["measured_s"] for r in sub], [r["model_reading_s"] for r in sub], s=36, color=colors[mfr],
                   edgecolor="white", linewidth=1, label=label, zorder=3)
    lim = max(max(r["measured_s"], r["model_reading_s"]) for r in rows) * 1.05
    ax.plot([0, lim], [0, lim], color="#9a9a94", lw=1)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("measured time to 45 °C (s)")
    ax.set_ylabel("model, as a 5 s probe reading (s)")
    ax.set_title("Delivery time, 46 field tests")
    ax.legend(frameon=False, loc="upper left")
    for ax, (name, title) in zip(axes[1:], (("fig3_5m", "Mfr B 20 mm, 6 l/min, 5 m (Fig 3)"),
                                            ("fig4_25m", "Mfr B 20 mm, 6 l/min, 25 m (Fig 4)"))):
        tr = traces[name]
        ax.plot(tr["t_model"], tr["T_model"], color="#2a78d6", lw=2, label="model")
        ax.plot(tr["t_meas"], tr["T_meas"], "o", color="#eb6834", ms=5, label="measured (digitised)")
        ax.axhline(45, color="#9a9a94", lw=1, ls="--")
        ax.set_xlabel("time since tap opened (s)")
        ax.set_ylabel("outlet temperature (°C)")
        ax.set_title(title)
        ax.legend(frameon=False, loc="lower right")
    fig.suptitle(f"Model vs Ref 29 field trial (no fitting; supply {T_supply:g} °C from time H, MLCP homogenised)")
    fig.tight_layout()
    fig.savefig(out_dir / "ref29_comparison.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", nargs="?", default="/mnt/project-files/ref29")
    ap.add_argument("--out", default="results/ref29")
    ap.add_argument("--supply", type=float, default=50.0)
    a = ap.parse_args()
    rows, stats, traces = run(Path(a.data_dir), Path(a.out), a.supply)
    print(json.dumps(stats, indent=2))
    try:
        plot(rows, traces, Path(a.out), a.supply)
    except ImportError:
        print("matplotlib not installed; skipped figures")
