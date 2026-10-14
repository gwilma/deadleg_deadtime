"""Figures for physics.tex, drawn in a Tufte manner: no boxes, range frames,
direct labels, sparse ticks, ink only where there is data.

    python docs/physics/make_figures.py [ref29_dir]
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from deadleg import PRESETS, Material, Pipe, Scenario, simulate
from deadleg.analytic import schumann_outlet

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
REPO = Path(__file__).resolve().parents[2]

INK = "#222222"
GREY = "#8c8c8c"
ACCENT = "#a6192e"  # one accent colour, used sparingly

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["TeX Gyre Pagella", "Palatino", "URW Palladio L", "P052", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 9,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "lines.linewidth": 1.2,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

# Typeset labels with LaTeX and Palatino (mathpazo) when available, to match
# the tufte-latex document; otherwise fall back to a generic serif.
try:
    import shutil

    if shutil.which("latex") and shutil.which("kpsewhich"):
        plt.rcParams.update({"pgf.texsystem": "pdflatex", "pgf.rcfonts": False,
                             "pgf.preamble": r"\usepackage[sc]{mathpazo}\usepackage[T1]{fontenc}\usepackage{textcomp}"})
        TEX = True
    else:
        TEX = False
except Exception:
    TEX = False
DEG = r"\textdegree{}" if TEX else "\N{DEGREE SIGN}"
TIMES = r"$\times$" if TEX else "\N{MULTIPLICATION SIGN}"
DASH = "--" if TEX else "\N{EN DASH}"


def pipe_label(pipe):
    return pipe.name.replace(" x ", TIMES)


def save(fig, name):
    fig.savefig(OUT / name, **({"backend": "pgf"} if TEX else {}))
    plt.close(fig)


def range_frame(ax, x, y):
    """Tufte's range frame: axis lines span only the data."""
    ax.spines["bottom"].set_bounds(min(x), max(x))
    ax.spines["left"].set_bounds(min(y), max(y))
    ax.spines["bottom"].set_position(("outward", 4))
    ax.spines["left"].set_position(("outward", 4))


def outlet_traces():
    pipes = ["copper_10x0.6", "copper_12x0.6", "pex_10x1.5", "pex_12x2.0"]
    shades = [INK, GREY, ACCENT, "#d4848f"]
    fig, ax = plt.subplots(figsize=(4.3, 2.6))
    ends = []
    for name, col in zip(pipes, shades):
        r = simulate(Scenario(PRESETS[name], 5.0, 3.0, duration=25.0, T_initial=20.0, T_inlet=55.0))
        k = np.searchsorted(r.t, 20.0)
        ax.plot(r.t[: k + 1], r.T_out[: k + 1], color=col)
        ends.append((r.T_out[k], name, col))
    # Direct labels at the line ends, nudged apart so they do not collide.
    ends.sort(reverse=True)
    y = [e[0] for e in ends]
    for j in range(1, len(y)):
        y[j] = min(y[j], y[j - 1] - 2.6)
    for (t_end, name, col), yl in zip(ends, y):
        ax.plot([20.1, 20.8], [t_end, yl], color=col, lw=0.5)
        ax.text(21.0, yl, pipe_label(PRESETS[name]), color=col, va="center", fontsize=8)
    ax.set_xlim(0, 27)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_yticks([20, 30, 40, 50, 55])
    ax.set_xlabel("seconds after the tap opens")
    ax.set_ylabel(f"outlet, {DEG}C")
    range_frame(ax, [0, 20], [20, 55])
    save(fig, "outlet_traces.pdf")


def radial_profiles():
    fig, axes = plt.subplots(1, 2, figsize=(4.3, 2.3), sharey=True)
    for ax, name in zip(axes, ["copper_10x0.6", "pex_12x2.0"]):
        pipe = PRESETS[name]
        nr = 24
        sc = Scenario(pipe, 5.0, 3.0, duration=50.0, T_initial=20.0, T_inlet=55.0, n_radial=nr)
        t_front = 2.5 / (3.0 / 60000.0 / pipe.bore_area)
        times = [t_front + d for d in (1, 3, 10, 30)]
        sc.snapshot_times = times
        r = simulate(sc)
        i = int(0.5 * sc.n_axial)
        rf = np.linspace(pipe.inner_radius, pipe.outer_radius, nr + 1)
        rc = 0.5 * (rf[:-1] + rf[1:])
        depth = (rc - pipe.inner_radius) * 1e3
        for (t, snap), shade in zip(sorted(r.snapshots.items()), ["#bbbbbb", "#888888", "#555555", INK]):
            ax.plot(depth, snap["T_wall"][i], color=shade)
            ax.plot([-0.12 * depth.max()], [snap["T_water"][i]], "o", ms=3, color=shade, clip_on=False)
            label = f"{t - t_front:.0f} s"
            if name.startswith("copper") and t - t_front > 2:
                label = f"3{DASH}30 s" if t - t_front < 5 else ""
            ax.text(depth[-1] + 0.04 * depth.max(), snap["T_wall"][i][-1], label, fontsize=7, va="center", color=shade)
        ax.set_title(pipe_label(pipe), fontsize=9, loc="left")
        ax.set_xlabel("depth into wall, mm")
        ax.set_xticks([0, round(depth.max() + (rc[0] - pipe.inner_radius) * 1e3, 1)])
        range_frame(ax, [0, depth.max()], [20, 55])
    axes[0].set_ylabel(f"{DEG}C")
    axes[0].set_yticks([20, 30, 40, 50, 55])
    fig.tight_layout(w_pad=2.5)
    save(fig, "radial_profiles.pdf")


def schumann():
    pipe = Pipe(0.010, 0.0006, Material("lumped", 1e6, 8940.0, 385.0, 0.0))
    h = 3000.0
    u = 3.0 / 60000.0 / pipe.bore_area
    fig, ax = plt.subplots(figsize=(4.3, 2.2))
    for nx, col, ls in ((25, GREY, "-"), (200, INK, "-")):
        r = simulate(Scenario(pipe, 5.0, 3.0, duration=20.0, T_initial=0.0, T_inlet=1.0, h_inner=h, h_outer=0.0,
                              n_radial=1, n_axial=nx, wall_axial_conduction=False, air_volume=math.inf))
        ax.plot(r.t, r.T_out, color=col, ls=ls, lw=1)
        ax.text(r.t[-1] + 0.3, r.T_out[-1] - (0.06 if nx == 25 else -0.02), f"model, {nx} cells", fontsize=7,
                color=col, va="center")
    t = np.linspace(0, 20, 400)
    exact = schumann_outlet(t, 5.0, u, h, 2 * math.pi * pipe.inner_radius, r.rho_cp_water * pipe.bore_area,
                            pipe.wall_heat_capacity_per_m)
    ax.plot(t, exact, color=ACCENT, lw=2.2, alpha=0.45, zorder=0)
    ax.text(9.5, 0.45, f"exact (Anzelius{DASH}Schumann)", color=ACCENT, fontsize=8)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_yticks([0, 0.5, 1])
    ax.set_xlabel("seconds")
    ax.set_ylabel(r"$\theta_{out}$")
    range_frame(ax, [0, 20], [0, 1])
    save(fig, "schumann.pdf")


def parity(results_csv: Path):
    rows = list(csv.DictReader(open(results_csv)))
    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    for mfr, col in (("A", INK), ("B", ACCENT)):
        sub = [r for r in rows if r["manufacturer"] == mfr]
        m = np.array([float(r["measured_s"]) for r in sub])
        p = np.array([float(r["model_s"]) for r in sub])
        ax.hlines(p, m - 5, m, color=col, lw=0.8, alpha=0.6)
        ax.plot(m - 2.5, p, "o", ms=3, color=col)
    ax.plot([0, 165], [0, 165], color=GREY, lw=0.6, zorder=0)
    ax.text(100, 45, "Manufacturer A", color=INK, fontsize=8)
    ax.text(100, 33, "Manufacturer B (hold-out)", color=ACCENT, fontsize=8)
    ax.set_xticks([0, 40, 80, 120, 160])
    ax.set_yticks([0, 40, 80, 120, 160])
    ax.set_xlabel(f"field trial, s to 45 {DEG}C")
    ax.set_ylabel(f"model, s to 45 {DEG}C")
    ax.set_aspect("equal")
    range_frame(ax, [0, 160], [0, 160])
    save(fig, "parity.pdf")


if __name__ == "__main__":
    outlet_traces()
    radial_profiles()
    schumann()
    res = REPO / "results" / "ref29_air_1.5x0.3m" / "ref29_delivery_times.csv"
    if res.exists():
        parity(res)
    print("figures in", OUT)
