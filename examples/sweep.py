"""Copper and PE-X dead legs at 1-6 l/min: delivery times and outlet traces.

    python examples/sweep.py [--length 5] [--out results/sweep]

Writes sweep.csv (one row per pipe and flow) and, with matplotlib, PNG figures.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from deadleg import PRESETS, Scenario, simulate

PIPES = ["copper_10x0.6", "copper_12x0.6", "pex_10x1.5", "pex_12x2.0"]
FLOWS = [1, 2, 3, 4, 5, 6]
T_INITIAL, T_INLET = 20.0, 55.0
THRESHOLDS = (40.0, 50.0)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # categorical slots 1-4, fixed order


def run(length: float):
    rows, traces = [], {}
    for name in PIPES:
        pipe = PRESETS[name]
        for q in FLOWS:
            sc = Scenario(pipe, length, q, duration=1.0, T_initial=T_INITIAL, T_inlet=T_INLET)
            plug = sc.plug_flow_time()
            sc.duration = 3 * plug + 20
            r = simulate(sc)
            row = {"pipe": pipe.name, "flow_l_per_min": q, "plug_flow_time_s": round(plug, 2)}
            for T in THRESHOLDS:
                row[f"time_to_{T:g}C_s"] = round(r.time_to_reach(T), 2)
                row[f"volume_to_{T:g}C_l"] = round(r.volume_to_reach(T), 3)
            row["delay_over_plug_at_50C"] = round(r.time_to_reach(50.0) / plug, 2)
            rows.append(row)
            traces[(name, q)] = r
    return rows, traces


def plot(rows, traces, length, out: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e4e4e0", "grid.linewidth": 0.8, "font.size": 10})

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, q in zip(axes, (1, 6)):
        for name, col in zip(PIPES, COLORS):
            r = traces[(name, q)]
            ax.plot(r.t, r.T_out, color=col, lw=2, label=PRESETS[name].name)
        ax.axhline(50, color="#9a9a94", lw=1, ls="--")
        ax.set_title(f"{q} l/min, {length:g} m run")
        ax.set_xlabel("time since tap opened (s)")
        ax.set_xlim(0, max(traces[(n, q)].time_to_reach(52) for n in PIPES) * 1.3)
    axes[0].set_ylabel("outlet temperature (°C)")
    axes[1].legend(frameon=False, loc="lower right")
    fig.suptitle(f"Outlet temperature after the tap opens: inlet {T_INLET:g} °C, pipe initially {T_INITIAL:g} °C")
    fig.tight_layout()
    fig.savefig(out / "outlet_traces.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for name, col in zip(PIPES, COLORS):
        sub = [r for r in rows if r["pipe"] == PRESETS[name].name]
        q = [r["flow_l_per_min"] for r in sub]
        axes[0].plot(q, [r["time_to_50C_s"] for r in sub], color=col, lw=2, marker="o", ms=5, label=PRESETS[name].name)
        axes[0].plot(q, [r["plug_flow_time_s"] for r in sub], color=col, lw=1, ls=":")
        axes[1].plot(q, [r["volume_to_50C_l"] for r in sub], color=col, lw=2, marker="o", ms=5, label=PRESETS[name].name)
    axes[0].set_ylabel("time to 50 °C at outlet (s)")
    axes[0].set_title("Delivery time (dotted: pure plug flow)")
    axes[1].set_ylabel("water run off before 50 °C (l)")
    axes[1].set_title("Water wasted")
    for ax in axes:
        ax.set_xlabel("flow (l/min)")
        ax.set_ylim(bottom=0)
    axes[1].legend(frameon=False)
    fig.suptitle(f"{length:g} m dead leg, inlet {T_INLET:g} °C, pipe initially {T_INITIAL:g} °C")
    fig.tight_layout()
    fig.savefig(out / "delivery_vs_flow.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=5.0)
    ap.add_argument("--out", default="results/sweep")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, traces = run(a.length)
    with open(out / "sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    try:
        plot(rows, traces, a.length, out)
    except ImportError:
        print("matplotlib not installed; skipped figures")
