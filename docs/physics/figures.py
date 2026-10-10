"""Figures for water_hammer_physics.tex, drawn with Altair.

Style: Tufte (direct labels, no legends or boxes, minimal non-data ink) with
The Economist's palette and a condensed sans (Roboto Condensed standing in
for Econ Sans Condensed). Needs altair, vl-convert-python, pandas.

    python docs/physics/figures.py   -> docs/physics/figures/*.pdf
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import vl_convert as vlc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from waterhammer import PRESETS, Pipe, simulate_moc, wave_speed  # noqa: E402
from waterhammer.properties import COPPER, PB, PEX, water_density  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
FONT = "Roboto Condensed"
RED, BLUE, CYAN, GREEN, OLIVE = "#E3120B", "#006BA2", "#3EBCD2", "#379A8B", "#B4BA39"
INK, GREY, GRID = "#0C0C0C", "#758D99", "#D9D9D9"
T = 55.0
W, H = 330, 190


@alt.theme.register("economist_tufte", enable=True)
def economist_tufte():
    return {
        "config": {
            "background": "white",
            "font": FONT,
            "view": {"stroke": None},
            "title": {"anchor": "start", "font": FONT, "fontSize": 13, "fontWeight": "bold", "color": INK,
                      "subtitleFont": FONT, "subtitleFontSize": 11, "subtitleColor": INK, "offset": 10},
            "axis": {"labelFont": FONT, "titleFont": FONT, "labelFontSize": 10, "titleFontSize": 10,
                     "labelColor": INK, "titleColor": GREY, "titleFontWeight": "normal",
                     "domain": False, "ticks": False, "gridColor": GRID, "gridWidth": 0.5, "labelPadding": 4},
            "axisX": {"grid": False, "domain": True, "domainColor": INK, "domainWidth": 1,
                      "ticks": True, "tickColor": INK, "tickSize": 4},
            "axisY": {"grid": True, "titleAngle": 0, "titleAlign": "left", "titleY": -8, "titleX": 0,
                      "titleBaseline": "bottom"},
            "header": {"labelFont": FONT, "labelFontSize": 11, "labelColor": INK, "labelFontWeight": "bold",
                       "labelAnchor": "start", "titleFontSize": 0},
            "text": {"font": FONT, "fontSize": 10},
            "legend": {"disable": True},
        }
    }




def save(chart: alt.Chart, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = chart.to_json()
    (OUT / f"{name}.pdf").write_bytes(vlc.vegalite_to_pdf(spec))
    (OUT / f"{name}.png").write_bytes(vlc.vegalite_to_png(spec, scale=2))
    print("wrote", name)


def end_labels(df: pd.DataFrame, x: str, y: str, key: str, colors: dict, dx: int = 4) -> alt.Chart:
    last = df.sort_values(x).groupby(key).tail(1)
    return alt.Chart(last).mark_text(align="left", dx=dx, fontSize=10, fontWeight="bold").encode(
        x=f"{x}:Q", y=f"{y}:Q", text=f"{key}:N",
        color=alt.Color(f"{key}:N", scale=alt.Scale(domain=list(colors), range=list(colors.values()))))


# 1. Wave speed against bore/wall ratio ------------------------------------
def fig_wave_speed():
    rows = []
    for label, mat in (("Copper", COPPER), ("PE-X", PEX), ("PB", PB)):
        for k in range(60):
            ratio = 3 * (40 / 3) ** (k / 59)
            e = 1.0
            p = Pipe(ratio * e + 2 * e, e, mat)
            rows.append({"material": label, "D/e": ratio, "a": wave_speed(p, T)})
    df = pd.DataFrame(rows)
    colors = {"Copper": BLUE, "PE-X": RED, "PB": CYAN}
    pts = []
    offsets = {"copper_10x0.6": (-6, 14, "right"), "copper_15x0.7": (6, -8, "left"), "pex_12x2.0": (-6, -10, "right"),
               "pex_10x1.5": (6, -10, "left"), "mlcp_12x1.6": (-6, -8, "right"), "mlcp_16x2.0": (6, 6, "left")}
    for key, (dx, dy, al) in offsets.items():
        p = PRESETS[key]
        pts.append({"pipe": p.name, "D/e": p.inner_diameter / p.wall, "a": wave_speed(p, T),
                    "dx": dx, "dy": dy, "align": al})
    pts = pd.DataFrame(pts)
    x = alt.X("D/e:Q", scale=alt.Scale(type="log", domain=[3, 40], nice=False), axis=alt.Axis(values=[3, 5, 10, 20, 40]),
              title="Bore / wall thickness, D/e (log scale)")
    y = alt.Y("a:Q", scale=alt.Scale(domain=[0, 1500]), title="Wave speed, m/s")
    lines = alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=x, y=y, color=alt.Color("material:N", scale=alt.Scale(domain=list(colors), range=list(colors.values()))))
    dots = alt.Chart(pts).mark_point(filled=True, size=28, color=INK).encode(x="D/e:Q", y="a:Q")
    dl = alt.layer(*[alt.Chart(pts[pts["pipe"] == r.pipe]).mark_text(
        align=r.align, dx=r.dx, dy=r.dy, fontSize=9, color=GREY).encode(x="D/e:Q", y="a:Q", text="pipe:N")
        for r in pts.itertuples()])
    ends = df.sort_values("D/e").groupby("material").tail(1).assign(dy=[0, -7, 7])
    el = alt.layer(*[alt.Chart(ends[ends.material == m]).mark_text(
        align="left", dx=4, dy=float(ends[ends.material == m].dy.iloc[0]), fontSize=10, fontWeight="bold",
        color=colors[m]).encode(x="D/e:Q", y="a:Q", text="material:N") for m in colors])
    ch = (lines + el + dots + dl).properties(
        width=W, height=H, title=alt.Title("Plastic pipe carries pressure waves four to five times slower",
                                           subtitle="Wave speed at 55 °C, pipe anchored against axial movement"))
    save(ch, "wave_speed")


# 2. Surge against closure time, normalised --------------------------------
def fig_closure():
    rows = []
    for k in range(80):
        r = 0.1 * 300 ** (k / 79)
        rows.append({"tc/Tc": r, "ratio": 1.0 if r <= 1 else 1 / r, "series": "Joukowsky / Michaud"})
    cases = {"Copper 10 x 0.6, 8 m, 6 L/min": (PRESETS["copper_10x0.6"], 8, 6),
             "PE-X 12 x 2.0, 8 m, 6 L/min": (PRESETS["pex_12x2.0"], 8, 6)}
    for label, (p, L, f) in cases.items():
        a = wave_speed(p, T)
        tcrit = 2 * L / a
        q = f / 60000
        jk = water_density(T) * a * q / p.bore_area
        for k in range(25):
            r = 0.1 * 300 ** (k / 24)
            res = simulate_moc(p, L, q, 3e5, T, r * tcrit, reaches=20)
            rows.append({"tc/Tc": r, "ratio": (res.peak_gauge_pa - 3e5) / jk, "series": label})
    df = pd.DataFrame(rows)
    colors = {"Joukowsky / Michaud": GREY, "Copper 10 x 0.6, 8 m, 6 L/min": BLUE,
              "PE-X 12 x 2.0, 8 m, 6 L/min": RED}
    base = alt.Chart(df).encode(
        x=alt.X("tc/Tc:Q", scale=alt.Scale(type="log", domain=[0.1, 30], nice=False), axis=alt.Axis(values=[0.1, 0.3, 1, 3, 10, 30]),
                title="Valve closure time / critical time 2L/a (log scale)"),
        y=alt.Y("ratio:Q", scale=alt.Scale(domain=[0, 1.1]), axis=alt.Axis(values=[0, 0.25, 0.5, 0.75, 1], format=".2f"),
                title="Surge / Joukowsky surge"),
        color=alt.Color("series:N", scale=alt.Scale(domain=list(colors), range=list(colors.values()))))
    lines = base.mark_line(strokeWidth=2).encode(strokeDash=alt.condition(
        alt.datum.series == "Joukowsky / Michaud", alt.value([4, 3]), alt.value([1, 0])))
    lab = pd.DataFrame([
        {"tc/Tc": 0.11, "ratio": 1.04, "t": "Joukowsky plateau (closure faster than 2L/a)", "c": GREY},
        {"tc/Tc": 6.5, "ratio": 0.27, "t": "Michaud, 2L/a ÷ t", "c": GREY},
        {"tc/Tc": 1.25, "ratio": 0.93, "t": "Copper (MOC)", "c": BLUE},
        {"tc/Tc": 2.2, "ratio": 0.5, "t": "PE-X (MOC)", "c": RED},
    ])
    txt = alt.Chart(lab).mark_text(align="left", fontSize=10).encode(
        x="tc/Tc:Q", y="ratio:Q", text="t:N", color=alt.Color("c:N", scale=None))
    ch = (lines + txt).properties(width=W, height=H, title=alt.Title(
        "Only valves that close within 2L/a see the full Joukowsky surge",
        subtitle="Peak surge at the valve; orifice valve, linear area closure, 3 bar rest pressure"))
    save(ch, "closure_time")


# 3. Pressure trace at the valve ------------------------------------------
def fig_trace():
    p, L, f = PRESETS["pex_12x2.0"], 8, 6
    rows, surge = [], {}
    colors = {"Lever mixer, 0.1 s": RED, "Slower valve, 0.3 s": BLUE}
    for label, tc in (("Lever mixer, 0.1 s", 0.1), ("Slower valve, 0.3 s", 0.3)):
        r = simulate_moc(p, L, f / 60000, 3e5, T, tc, reaches=20, periods_after=12)
        surge[tc] = (r.peak_gauge_pa - 3e5) / 1e5
        step = max(1, len(r.times) // 600)
        for t, pv in list(zip(r.times, r.valve_gauge_pa))[::step]:
            rows.append({"t": t * 1000, "p": pv / 1e5, "case": label})
    df = pd.DataFrame(rows)
    df = df[df.t <= 600]
    lines = alt.Chart(df).mark_line(strokeWidth=1.6).encode(
        x=alt.X("t:Q", title="Time after the valve starts to close, ms", scale=alt.Scale(domain=[0, 600])),
        y=alt.Y("p:Q", title="Pressure at the valve, bar g", scale=alt.Scale(domain=[0, 6])),
        color=alt.Color("case:N", scale=alt.Scale(domain=list(colors), range=list(colors.values()))))
    rules = pd.DataFrame([{"y": 5.0, "t": "Limit: rest pressure + 2 bar"}, {"y": 3.0, "t": "Rest pressure"}])
    rl = alt.Chart(rules).mark_rule(color=GREY, strokeDash=[4, 3], strokeWidth=1).encode(y="y:Q")
    rules["t"] = ["Limit: rest + 2 bar", "Rest pressure"]
    rt = alt.Chart(rules).mark_text(align="left", dx=6, color=GREY, fontSize=10).encode(
        y="y:Q", x=alt.value(W), text="t:N")
    lab = pd.DataFrame([{"t": 112, "p": 5.75, "s": f"Lever mixer, 0.1 s: {surge[0.1]:.1f} bar surge", "c": RED},
                        {"t": 175, "p": 0.3, "s": f"0.3 s closure: {surge[0.3]:.1f} bar", "c": BLUE}])
    lt = alt.Chart(lab).mark_text(align="left", fontSize=10, fontWeight="bold").encode(
        x="t:Q", y="p:Q", text="s:N", color=alt.Color("c:N", scale=None))
    ch = (rl + rt + lines + lt).properties(width=W, height=H, title=alt.Title(
        "Tripling the closure time brings the surge within the limit",
        subtitle="PE-X 12 x 2.0, 8 m run, 6 L/min, 55 °C (method of characteristics)"))
    save(ch, "trace")


# 4. Screening: longest run without mitigation ----------------------------
def fig_screening():
    src = ROOT / "results" / "waterhammer" / "screening.csv"
    rows = []
    with src.open() as fh:
        for r in csv.DictReader(fh):
            if r["pipe"] not in ("copper_10x0.6", "pex_12x2.0"):
                continue
            v = r["max_length_without_mitigation_m"]
            rows.append({"pipe": PRESETS[r["pipe"]].name, "valve": r["valve"].replace("_", " "),
                         "flow": int(r["flow_l_min"]), "L": 30 if v.startswith(">=") else float(v)})
    df = pd.DataFrame(rows)
    colors = {"solenoid": RED, "single lever mixer": BLUE, "quarter turn": CYAN, "screw down": OLIVE}
    base = alt.Chart().encode(
        x=alt.X("flow:Q", title="Flow, L/min", scale=alt.Scale(domain=[1, 6]), axis=alt.Axis(values=[1, 2, 3, 4, 5, 6], labelOverlap=False)),
        y=alt.Y("L:Q", title=None, scale=alt.Scale(domain=[0, 30]), axis=alt.Axis(values=[0, 10, 20, 30])),
        color=alt.Color("valve:N", scale=alt.Scale(domain=list(colors), range=list(colors.values()))))
    lines = base.mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=16, filled=True))
    dys = {"quarter turn": -6, "single lever mixer": 6, "solenoid": 0, "screw down": 0}
    last = alt.layer(*[alt.Chart().transform_filter(
        (alt.datum.flow == 6) & (alt.datum.valve == v)).mark_text(
        align="left", dx=6, dy=dy, fontSize=9, fontWeight="bold", color=colors[v]).encode(
        x="flow:Q", y="L:Q", text="valve:N") for v, dy in dys.items()])
    ch = alt.layer(lines, last, data=df).properties(width=150, height=150).facet(
        column=alt.Column("pipe:N", title=None, sort=["Copper 10 x 0.6", "PE-X 12 x 2.0"]),
        spacing=70).properties(title=alt.Title(
            "Solenoid valves need protection on almost any small-bore run",
            subtitle="Longest run in metres (valve to reflection point) needing no mitigation; 3 bar, 55 °C; capped at 30 m"))
    save(ch, "screening")


if __name__ == "__main__":
    fig_wave_speed()
    fig_closure()
    fig_trace()
    fig_screening()
