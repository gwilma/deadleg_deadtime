"""Charts of the model against the Ref 29 field trial, drawn with Altair.

    python examples/ref29_plots.py results/ref29_air_1.5x0.3m --air-area 0.45 \
        [--data /mnt/project-files/ref29] [--fonts /path/to/SourceSansPro]

Reads ref29_delivery_times.csv written by ref29_validation.py, reruns the two
traced tests, and writes three PNGs (and Vega-Lite HTML) to the same folder.

Style: Tufte's principles (small multiples, direct labels instead of legends,
no chart junk, the reading uncertainty shown rather than hidden) in the house
style of The Economist (red rule and tag, left-aligned bold title with a
subtitle, horizontal gridlines only, y-axis labels on the right, blue palette,
a humanist sans; Source Sans Pro stands in for the proprietary Econ Sans).
Needs altair, pandas, vl-convert-python and pillow.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import altair as alt
import pandas as pd

from ref29_validation import READ_INTERVAL, scenario_for
from deadleg import simulate
from deadleg.io import load_trace

FONT = "Source Sans Pro"
RED = "#E3120B"
INK = "#0C0C0C"
INK_2 = "#3F5661"
GRID = "#B7C6CF"
BLUE = "#006BA2"
FLOW_COLORS = {4: "#5DA4CF", 6: "#006BA2", 9: "#0B3B66"}  # one-hue ramp, light to dark with flow
MFR_COLORS = {"A": BLUE, "B": RED}
SOURCE = "Sources: Ridge & Jones, FairHeat field trial (2022); deadleg model"
SCALE = 2


def economist_theme():
    return {
        "config": {
            "font": FONT,
            "background": "#FFFFFF",
            "padding": {"top": 34, "left": 14, "right": 14, "bottom": 34},
            "view": {"stroke": None},
            "title": {"anchor": "start", "font": FONT, "fontSize": 20, "fontWeight": 700, "color": INK,
                      "subtitleFont": FONT, "subtitleFontSize": 14, "subtitleColor": INK, "subtitlePadding": 6,
                      "offset": 14},
            "axis": {"labelFont": FONT, "titleFont": FONT, "labelFontSize": 13, "titleFontSize": 13,
                     "labelColor": INK_2, "titleColor": INK_2, "titleFontWeight": 400,
                     "gridColor": GRID, "gridWidth": 1, "tickColor": INK, "domainColor": INK},
            "axisX": {"grid": False, "domainWidth": 1, "tickSize": 4},
            "axisY": {"orient": "right", "domain": False, "ticks": False, "labelPadding": 4,
                      "titleAngle": 0, "titleAlign": "right", "titleAnchor": "end", "titleY": -8, "titleX": 0},
            "header": {"labelFont": FONT, "labelFontSize": 14, "labelFontWeight": 700, "labelColor": INK,
                       "labelAnchor": "start", "title": None},
            "text": {"font": FONT, "fontSize": 13, "color": INK},
        }
    }


alt.theme.register("economist", enable=True)(economist_theme)


def frame(png: Path):
    """The Economist's red rule across the top and red tag at top left, plus a source line."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(img)
    w, h = img.size
    d.rectangle([0, 0, w, 3 * SCALE], fill=RED)
    d.rectangle([14 * SCALE, 0, 14 * SCALE + 44 * SCALE, 14 * SCALE], fill=RED)
    try:
        font = ImageFont.truetype(str(FONT_DIR / "SourceSansPro-Regular.ttf"), 12 * SCALE) if FONT_DIR else None
    except OSError:
        font = None
    d.text((14 * SCALE, h - 24 * SCALE), SOURCE, fill="#595959", font=font or ImageFont.load_default())
    img.save(png)


def save(chart, out: Path, name: str):
    chart.save(out / f"{name}.html")
    png = out / f"{name}.png"
    chart.save(png, scale_factor=SCALE)
    frame(png)
    return png


def small_multiples(df: pd.DataFrame, air_label: str):
    df = df.copy()
    df["panel"] = "Manufacturer " + df["manufacturer"] + ", " + df["OD_mm"].map(lambda v: f"{v:g}") + "mm"
    df.loc[df.manufacturer == "B", "panel"] += " (hold-out)"
    df["flow"] = df["flow_l_per_min"].astype(int)
    df["window_lo"] = df["measured_s"] - READ_INTERVAL
    df["label"] = df["flow"].astype(str) + " l/min"
    flows = sorted(FLOW_COLORS)
    color = alt.Color("flow:O", scale=alt.Scale(domain=flows, range=[FLOW_COLORS[f] for f in flows]), legend=None)
    x = alt.X("length_m:Q", title="Pipe run, metres", scale=alt.Scale(domain=[3, 30]),
              axis=alt.Axis(values=[5, 15, 25]))
    y_scale = alt.Scale(domain=[0, 170], nice=False)

    target = alt.Chart(pd.DataFrame({"y": [45]})).mark_rule(color=INK, strokeDash=[3, 3], strokeWidth=1).encode(y="y:Q")
    order = sorted(df["panel"].unique(), key=lambda p: (p.split(",")[0], float(p.split(", ")[1].split("mm")[0])))
    panels = []
    for i, panel in enumerate(order):
        sub = df[df.panel == panel]
        base = alt.Chart(sub)
        model = base.mark_line(strokeWidth=2.5).encode(
            x=x, y=alt.Y("model_s:Q", title=None, scale=y_scale, axis=alt.Axis(values=list(range(0, 161, 40)))),
            color=color, detail="flow:O")
        measured = base.mark_rule(strokeWidth=7, strokeCap="butt").encode(
            x="length_m:Q", y="window_lo:Q", y2="measured_s:Q", color=color)
        edge = base.mark_tick(color=INK, thickness=1.5, size=10).encode(x="length_m:Q", y="measured_s:Q")
        # Direct labels at the right-hand end of each model line (Tufte: no legend box).
        ends = sub.loc[sub.groupby("flow")["length_m"].idxmax()]
        lines = ends[sub.groupby("flow")["length_m"].count().reindex(ends["flow"]).values > 1]
        lone = ends.drop(lines.index)  # a flow tested at one length only: label to the left of its bar
        labels = alt.layer(
            alt.Chart(lines).mark_text(align="left", dx=6).encode(x="length_m:Q", y="model_s:Q", text="label:N"),
            alt.Chart(lone).mark_text(align="right", dx=-9).encode(x="length_m:Q", y="measured_s:Q", text="label:N"),
        )
        panels.append(alt.layer(target, model, measured, edge, labels).properties(
            width=250, height=230, title=alt.Title(panel, fontSize=14, subtitle="")))
    return alt.concat(*panels, columns=3, spacing=30).properties(
        title=alt.Title(
            "A physical model, with nothing fitted, tracks the field trial",
            subtitle=[
                "Seconds for hot water to reach 45°C at the tap, by pipe, flow and run length. "
                "Lines: model. Bars: field trial; the true crossing lies within each 5-second",
                f"reading window, which ends at the black tick. Dashed line: 45-second target. Model air body {air_label}.",
            ],
        )
    )


def parity(df: pd.DataFrame, stats: dict[str, tuple[float, float]]):
    df = df.copy()
    df["window_lo"] = df["measured_s"] - READ_INTERVAL
    df["who"] = df["manufacturer"].map({"A": "Manufacturer A (paper's fitting set)", "B": "Manufacturer B (hold-out)"})
    lim = 170
    diag = alt.Chart(pd.DataFrame({"x": [0, lim], "y": [0, lim]})).mark_line(color=INK, strokeWidth=1).encode(
        x=alt.X("x:Q", title="Field trial, seconds to 45°C", scale=alt.Scale(domain=[0, lim], nice=False),
                axis=alt.Axis(values=list(range(0, 161, 20)))),
        y=alt.Y("y:Q", title="Model, seconds to 45°C", scale=alt.Scale(domain=[0, lim], nice=False),
                axis=alt.Axis(values=list(range(0, 161, 20)))))
    color = alt.Color("manufacturer:N", scale=alt.Scale(domain=["A", "B"], range=[MFR_COLORS["A"], MFR_COLORS["B"]]),
                      legend=None)
    window = alt.Chart(df).mark_rule(strokeWidth=2, opacity=0.6).encode(
        x="window_lo:Q", x2="measured_s:Q", y="model_s:Q", color=color)
    dots = alt.Chart(df).mark_circle(size=70, opacity=1, stroke="white", strokeWidth=1.5).encode(
        x=alt.X("measured_mid:Q"), y="model_s:Q", color=color,
        tooltip=["manufacturer", "OD_mm", "length_m", "flow_l_per_min", "measured_s", "model_s"])
    df["measured_mid"] = df["measured_s"] - READ_INTERVAL / 2
    dots = dots.properties(data=df)
    notes = pd.DataFrame([
        {"x": 6, "y": 158, "t": f"Manufacturer A: error {stats['A'][1]:.1f}s RMS, bias {stats['A'][0]:+.1f}s", "c": "A"},
        {"x": 6, "y": 146, "t": f"Manufacturer B (hold-out): error {stats['B'][1]:.1f}s RMS, bias {stats['B'][0]:+.1f}s", "c": "B"},
        {"x": 150, "y": 158, "t": "model slower", "c": "n"},
        {"x": 150, "y": 118, "t": "model faster", "c": "n"},
    ])
    note_marks = alt.Chart(notes).mark_text(align="left", fontSize=13).encode(x="x:Q", y="y:Q", text="t:N")
    swatch = alt.Chart(notes[notes.c != "n"]).mark_circle(size=70, opacity=1).encode(
        x=alt.value(0), y="y:Q", color=alt.Color("c:N", scale=alt.Scale(domain=["A", "B"], range=[MFR_COLORS["A"], MFR_COLORS["B"]]), legend=None))
    return alt.layer(diag, window, dots, note_marks, swatch).properties(
        width=520, height=440,
        title=alt.Title("Predicted against measured delivery time",
                        subtitle=["All 46 field tests. Dots sit mid-way through each 5-second reading window",
                                  "(horizontal bars); points on the diagonal are exact"]),
    ).resolve_scale(color="independent")


def traces(data_dir: Path, air_area: float):
    rows = []
    specs = (("5m run (Fig 3)", "fig3_trace_mfrB_14p2mm_6lpm_5m.csv", "time_s", 5.0),
             ("25m run (Fig 4)", "fig4_trace_mfrB_14p2mm_6lpm_25m.csv", "time_s_shifted_minus5_recommended", 25.0))
    for name, fname, tcol, length in specs:
        t, T = load_trace(data_dir / fname, tcol, "outlet_temp_C_approx")
        res = simulate(scenario_for(20.0, 2.8, length, 6.0, 5.7, 50.0, duration=float(t.max()) + 5, air_area=air_area))
        step = max(1, len(res.t) // 600)
        rows += [{"run": name, "t": a, "T": b, "kind": "model"} for a, b in zip(res.t[::step], res.T_out[::step])]
        rows += [{"run": name, "t": a, "T": b, "kind": "trial"} for a, b in zip(t, T)]
    df = pd.DataFrame(rows)
    target = alt.Chart(pd.DataFrame({"y": [45]})).mark_rule(color=INK, strokeDash=[3, 3], strokeWidth=1).encode(y="y:Q")
    lab = pd.DataFrame([
        {"run": "5m run (Fig 3)", "t": 28, "T": 42.5, "txt": "Model", "c": BLUE},
        {"run": "5m run (Fig 3)", "t": 22, "T": 51.6, "txt": "Field trial (digitised)", "c": INK},
    ])
    panels = []
    for i, (name, *_rest) in enumerate(specs):
        sub = df[df.run == name]
        x = alt.X("t:Q", title="Seconds after the tap opens")
        y = alt.Y("T:Q", title=None, scale=alt.Scale(domain=[15, 53], zero=False, nice=False),
                  axis=alt.Axis(values=[20, 30, 40, 50]))
        model = alt.Chart(sub[sub.kind == "model"]).mark_line(color=BLUE, strokeWidth=2.5).encode(x=x, y=y)
        trial = alt.Chart(sub[sub.kind == "trial"]).mark_circle(color=INK, size=36, opacity=1).encode(x="t:Q", y="T:Q")
        layers = [target, model, trial]
        if i == 0:
            layers.append(alt.Chart(lab).mark_text(align="left", fontWeight=600).encode(
                x="t:Q", y="T:Q", text="txt:N", color=alt.Color("c:N", scale=None)))
        panels.append(alt.layer(*layers).properties(width=380, height=260, title=alt.Title(name, fontSize=14, subtitle="")))
    return alt.hconcat(*panels, spacing=34).properties(
        title=alt.Title("Warm-up at the outlet: 20mm pipe at 6 litres a minute",
                        subtitle="Outlet temperature, °C. Dashed line: 45°C. Model supply steps to 50°C when the heat unit delivers hot water."))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--air-area", type=float, default=math.inf)
    ap.add_argument("--data", default="/mnt/project-files/ref29")
    ap.add_argument("--fonts", help="folder of SourceSansPro-*.ttf files")
    a = ap.parse_args()
    FONT_DIR = Path(a.fonts) if a.fonts else None
    if FONT_DIR:
        import vl_convert as vlc

        vlc.register_font_directory(str(FONT_DIR))
    out = Path(a.results_dir)
    df = pd.read_csv(out / "ref29_delivery_times.csv")
    air_label = "held at 19°C" if math.isinf(a.air_area) else f"{a.air_area:g}m² cross-section, enclosed"
    import json

    s = json.loads((out / "ref29_summary.json").read_text())
    stats = {m: (s[f"{m}_model"]["bias_s"], s[f"{m}_model"]["rmse_s"]) for m in ("A", "B")}
    for name, chart in (("ref29_by_test", small_multiples(df, air_label)),
                        ("ref29_parity", parity(df, stats)),
                        ("ref29_traces", traces(Path(a.data), a.air_area))):
        print(save(chart, out, name))
else:
    FONT_DIR = None
