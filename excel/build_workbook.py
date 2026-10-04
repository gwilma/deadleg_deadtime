"""Build excel/waterhammer.xlsx: the water hammer screening model as live
spreadsheet formulas (no macros), mirroring waterhammer/model.py.

    python excel/build_workbook.py

The property tables are written from waterhammer/properties.py so the two
implementations share one set of data. excel/check_workbook.py recalculates
the workbook with LibreOffice and compares it with the Python model.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from waterhammer.model import VALVE_CLOSURE_TIMES  # noqa: E402
from waterhammer.properties import (  # noqa: E402
    _WATER_DENSITY,
    _WATER_SOUND_SPEED,
    _WATER_VAPOUR_PRESSURE,
    ALUMINIUM,
    MATERIALS,
    PRESETS,
)

OUT = ROOT / "excel" / "waterhammer.xlsx"
MOC_REACHES = 10
MOC_ROWS = 6000  # time steps available on the MOC sheet

# Economist-like palette (see docs): red accent, blue-grey text and rules
RED = "E3120B"
INK = "121212"
GREY = "758D99"
PALE = "EBEDFA"
INPUT_FILL = PatternFill("solid", fgColor="FFF6D5")
HEAD_FONT = Font(name="Arial", bold=True, color=INK, size=11)
TITLE_FONT = Font(name="Arial", bold=True, color=INK, size=16)
BODY = Font(name="Arial", color=INK, size=10)
NOTE = Font(name="Arial", color=GREY, size=9, italic=True)
RULE = Border(top=Side(style="thin", color=RED))

MAT_KEYS = list(MATERIALS)  # copper, stainless, pex, pb, pert
E_GRID = [0, 20, 40, 60, 80, 100]


def name(wb: Workbook, nm: str, ref: str) -> None:
    wb.defined_names[nm] = DefinedName(nm, attr_text=ref)


def build() -> Path:
    wb = Workbook()
    model = wb.active
    model.title = "Model"
    calc = wb.create_sheet("Calc")
    moc = wb.create_sheet("MOC")
    data = wb.create_sheet("Data")

    # ------------------------------------------------------------------ Data
    data["A1"] = "Property data (written from waterhammer/properties.py; edit with care)"
    data["A1"].font = HEAD_FONT
    data.append([])
    data.append(["Water T (C)", "Density (kg/m3)", "Speed of sound (m/s)", "Vapour pressure (Pa abs)"])
    w0 = data.max_row + 1
    for (t, rho), (_, c), (_, pv) in zip(_WATER_DENSITY, _WATER_SOUND_SPEED, _WATER_VAPOUR_PRESSURE):
        data.append([t, rho, c, pv])
    w1 = data.max_row
    name(wb, "W_T", f"Data!$A${w0}:$A${w1}")
    name(wb, "W_rho", f"Data!$B${w0}:$B${w1}")
    name(wb, "W_c", f"Data!$C${w0}:$C${w1}")
    name(wb, "W_pv", f"Data!$D${w0}:$D${w1}")

    data.append([])
    data.append(["Material", "Poisson", "Roughness (m)"] + [f"E at {t} C (Pa)" for t in E_GRID])
    m0 = data.max_row + 1
    grid_row = data.max_row
    for key in MAT_KEYS + ["aluminium"]:
        mat = ALUMINIUM if key == "aluminium" else MATERIALS[key]
        data.append([key, mat.poisson, mat.roughness] + [mat.young_modulus(t) for t in E_GRID])
    m1 = data.max_row
    name(wb, "M_key", f"Data!$A${m0}:$A${m1}")
    name(wb, "M_nu", f"Data!$B${m0}:$B${m1}")
    name(wb, "M_rough", f"Data!$C${m0}:$C${m1}")
    name(wb, "M_E", f"Data!$D${m0}:$I${m1}")
    for j, t in enumerate(E_GRID):  # numeric grid row for MATCH
        data.cell(row=m1 + 1, column=4 + j, value=t)
    data.cell(row=m1 + 1, column=1, value="(temperature grid)")
    name(wb, "E_grid", f"Data!$D${m1 + 1}:$I${m1 + 1}")
    del grid_row

    data.append([])
    data.append(["Pipe preset", "OD (mm)", "Wall (mm)", "Material", "Al layer (mm)"])
    p0 = data.max_row + 1
    for key, p in PRESETS.items():
        mkey = next(k for k, m in MATERIALS.items() if m is p.material)
        data.append([key, p.outer_diameter_mm, p.wall_mm, mkey, p.aluminium_mm])
    data.append(["custom", None, None, None, None])
    p1 = data.max_row
    name(wb, "P_key", f"Data!$A${p0}:$A${p1}")
    name(wb, "P_od", f"Data!$B${p0}:$B${p1}")
    name(wb, "P_wall", f"Data!$C${p0}:$C${p1}")
    name(wb, "P_mat", f"Data!$D${p0}:$D${p1}")
    name(wb, "P_al", f"Data!$E${p0}:$E${p1}")

    data.append([])
    data.append(["Valve type", "Effective closure time (s)"])
    v0 = data.max_row + 1
    for k, t in VALVE_CLOSURE_TIMES.items():
        data.append([k, t])
    data.append(["custom", None])
    v1 = data.max_row
    name(wb, "V_key", f"Data!$A${v0}:$A${v1}")
    name(wb, "V_t", f"Data!$B${v0}:$B${v1}")

    data.append([])
    data.append(["Restraint"])
    r0 = data.max_row + 1
    for k in ["anchored", "expansion_joints", "upstream_anchor"]:
        data.append([k])
    r1 = data.max_row
    name(wb, "R_key", f"Data!$A${r0}:$A${r1}")
    data.column_dimensions["A"].width = 22
    for col in "BCDEFGHI":
        data.column_dimensions[col].width = 16

    # ----------------------------------------------------------------- Model
    model["A1"] = "Water hammer screening: domestic hot water pipe"
    model["A1"].font = TITLE_FONT
    model["A2"] = ("Yellow cells are inputs. Method and sources: docs/water_hammer.md and "
                   "docs/physics/water_hammer_physics.pdf. Same model as the Python package `waterhammer`.")
    model["A2"].font = NOTE
    model["A4"] = "Inputs"
    model["A4"].font = HEAD_FONT
    for c in "ABCD":
        model[f"{c}4"].border = RULE

    inputs = [
        ("in_preset", "Pipe preset", "copper_10x0.6", "", "pick 'custom' to use the four rows below"),
        ("in_od", "Custom OD", 12, "mm", ""),
        ("in_wall", "Custom wall", 2.0, "mm", ""),
        ("in_mat", "Custom material", "pex", "", ", ".join(MAT_KEYS)),
        ("in_al", "Custom Al layer", 0, "mm", "> 0 for multilayer (MLCP) pipe"),
        ("in_L", "Length, valve to reflection point", 8, "m", "manifold, larger main, cylinder or vessel"),
        ("in_flow", "Flow rate", 6, "l/min", ""),
        ("in_p", "Rest (static) pressure", 3.0, "bar g", ""),
        ("in_T", "Water temperature", 55, "C", ""),
        ("in_valve", "Valve type", "solenoid", "", "pick 'custom' to use the row below"),
        ("in_tc", "Custom closure time", 0.05, "s", "effective closure time"),
        ("in_restraint", "Pipe restraint", "anchored", "", "anchored / expansion_joints / upstream_anchor"),
        ("in_maxsurge", "Surge limit", 2.0, "bar", "EN 806-2 / DIN 1988-200 / VDI 6006"),
        ("in_rating", "Pipe and fitting rating", 10.0, "bar g", "at the hot water temperature"),
        ("in_vadv", "Advisory velocity", 1.5, "m/s", "UPC 610.12 hot water"),
        ("in_n", "Arrester gas index n", 1.4, "", "1.0 isothermal, 1.4 adiabatic"),
    ]
    row = 5
    for nm, label, val, unit, note in inputs:
        model.cell(row=row, column=1, value=label).font = BODY
        c = model.cell(row=row, column=2, value=val)
        c.fill, c.font = INPUT_FILL, Font(name="Arial", bold=True, color=INK, size=10)
        model.cell(row=row, column=3, value=unit).font = BODY
        model.cell(row=row, column=4, value=note).font = NOTE
        name(wb, nm, f"Model!$B${row}")
        row += 1
    dv = [
        ("in_preset", f"=Data!$A${p0}:$A${p1}"),
        ("in_mat", f"=Data!$A${m0}:$A${m1 - 1}"),
        ("in_valve", f"=Data!$A${v0}:$A${v1}"),
        ("in_restraint", f"=Data!$A${r0}:$A${r1}"),
    ]
    for nm, src in dv:
        r = 5 + [i[0] for i in inputs].index(nm)
        v = DataValidation(type="list", formula1=src, allow_blank=False)
        model.add_data_validation(v)
        v.add(f"B{r}")

    # ------------------------------------------------------------------ Calc
    calc["A1"] = "Intermediate quantities (all SI unless stated)"
    calc["A1"].font = HEAD_FONT
    calc.append(["Name", "Value", "Unit", "Formula / meaning"])
    for c in calc[2]:
        c.font = HEAD_FONT
    crow = [3]

    def cval(nm: str, formula, unit: str = "", desc: str = "") -> None:
        r = crow[0]
        calc.cell(row=r, column=1, value=nm).font = BODY
        calc.cell(row=r, column=2, value=formula).font = BODY
        calc.cell(row=r, column=3, value=unit).font = BODY
        calc.cell(row=r, column=4, value=desc).font = NOTE
        name(wb, nm, f"Calc!$B${r}")
        crow[0] += 1

    pick = 'IF(in_preset="custom",{c},INDEX({col},MATCH(in_preset,P_key,0)))'
    cval("x_od", "=" + pick.format(c="in_od", col="P_od"), "mm", "outside diameter")
    cval("x_wall", "=" + pick.format(c="in_wall", col="P_wall"), "mm", "wall thickness")
    cval("x_mat", "=" + pick.format(c="in_mat", col="P_mat"), "", "wall material")
    cval("x_al", "=" + pick.format(c="in_al", col="P_al"), "mm", "aluminium layer")
    cval("x_D", "=(x_od-2*x_wall)/1000", "m", "bore D")
    cval("x_e", "=x_wall/1000", "m", "wall e")
    cval("x_area", "=PI()*x_D^2/4", "m2", "bore area")
    cval("x_T", "=MAX(0,MIN(99.999,in_T))", "C", "temperature clamped to the table")
    cval("x_jw", "=MATCH(x_T,W_T,1)", "", "water table row")
    interp_w = "INDEX({y},x_jw)+(x_T-INDEX(W_T,x_jw))*(INDEX({y},x_jw+1)-INDEX({y},x_jw))/(INDEX(W_T,x_jw+1)-INDEX(W_T,x_jw))"
    cval("x_rho", "=" + interp_w.format(y="W_rho"), "kg/m3", "water density")
    cval("x_c", "=" + interp_w.format(y="W_c"), "m/s", "speed of sound in water")
    cval("x_K", "=x_rho*x_c^2", "Pa", "isentropic bulk modulus K = rho c^2")
    cval("x_pv", "=" + interp_w.format(y="W_pv"), "Pa abs", "vapour pressure")
    cval("x_mu", "=2.414E-5*10^(247.8/(in_T+273.15-140))", "Pa s", "viscosity (Vogel)")
    cval("x_jm", "=MATCH(x_mat,M_key,0)", "", "material row")
    cval("x_jal", '=MATCH("aluminium",M_key,0)', "", "aluminium row")
    cval("x_je", "=MATCH(x_T,E_grid,1)", "", "modulus temperature column")
    interp_e = "INDEX(M_E,{r},x_je)+(x_T-INDEX(E_grid,x_je))*(INDEX(M_E,{r},x_je+1)-INDEX(M_E,{r},x_je))/(INDEX(E_grid,x_je+1)-INDEX(E_grid,x_je))"
    cval("x_Ebase", "=" + interp_e.format(r="x_jm"), "Pa", "wall modulus")
    cval("x_Eal", "=" + interp_e.format(r="x_jal"), "Pa", "aluminium modulus")
    cval("x_Ehoop", "=IF(x_al=0,x_Ebase,x_al/x_wall*x_Eal+(1-x_al/x_wall)*x_Ebase)", "Pa",
         "hoop modulus (thickness-weighted for MLCP)")
    cval("x_nu", "=INDEX(M_nu,x_jm)", "", "Poisson's ratio")
    cval("x_rough", "=INDEX(M_rough,x_jm)", "m", "roughness")
    cval("x_psi", "=2*(x_e/x_D)*(1+x_nu)+CHOOSE(MATCH(in_restraint,R_key,0),"
         "x_D*(1-x_nu^2)/(x_D+x_e),x_D/(x_D+x_e),x_D*(1-x_nu/2)/(x_D+x_e))", "",
         "restraint factor (Wylie & Streeter eq. 2.21)")
    cval("x_a", "=SQRT((x_K/x_rho)/(1+x_psi*x_K*x_D/(x_Ehoop*x_e)))", "m/s", "wave speed")
    cval("x_tc", '=IF(in_valve="custom",in_tc,INDEX(V_t,MATCH(in_valve,V_key,0)))', "s", "closure time")
    cval("x_Q", "=in_flow/60000", "m3/s", "flow")
    cval("x_v", "=x_Q/x_area", "m/s", "velocity")
    cval("x_Tcrit", "=2*in_L/x_a", "s", "critical time 2L/a")
    cval("x_djk", "=x_rho*x_a*x_v", "Pa", "Joukowsky rho a v")
    cval("x_regime", '=IF(x_tc<=x_Tcrit,"rapid","slow")', "", "")
    cval("x_dcf", "=IF(x_tc<=x_Tcrit,x_djk,2*x_rho*in_L*x_v/x_tc)", "Pa", "closed form (Joukowsky / Michaud)")
    cval("x_Re", "=x_rho*x_v*x_D/x_mu", "", "Reynolds number")
    cval("x_f", "=IF(x_Re<2300,64/x_Re,0.25/LOG10(x_rough/x_D/3.7+5.74/x_Re^0.9)^2)", "",
         "Darcy friction factor (Swamee-Jain)")
    cval("x_g", 9.81, "m/s2", "")
    cval("x_patm", 101325, "Pa", "")
    cval("x_ps", "=in_p*1E5", "Pa", "rest pressure (gauge)")
    cval("x_hres", "=x_ps/(x_rho*x_g)", "m", "head at reflection point")
    cval("x_hf", "=x_f*in_L/x_D*x_v^2/(2*x_g)", "m", "friction head at full flow")
    cval("x_hv0", "=x_hres-x_hf", "m", "head at the valve while flowing (must be > 0)")
    cval("x_N", MOC_REACHES, "", "MOC reaches")
    cval("x_dt", "=in_L/x_N/x_a", "s", "MOC time step dx/a")
    cval("x_B", "=x_a/(x_g*x_area)", "s/m2", "characteristic impedance a/(gA)")
    cval("x_R", "=x_f*(in_L/x_N)/(2*x_g*x_D*x_area^2)", "s2/m5", "friction coefficient per reach")
    cval("x_tend", "=x_tc+6*2*in_L/x_a", "s", "simulated time")
    cval("x_steps", "=ROUNDUP(x_tend/x_dt,0)", "", "time steps used")
    cval("x_rows_ok", f"=x_steps<={MOC_ROWS - 1}", "", "FALSE = MOC sheet too short; use Python")
    first, last = 7, 7 + MOC_ROWS - 1
    cval("x_hpeak", f'=_xlfn.MAXIFS(MOC!$N${first - 1}:$N${last},MOC!$A${first - 1}:$A${last},"<="&x_steps)', "m",
         "peak head at the valve")
    cval("x_hmin", f'=_xlfn.MINIFS(MOC!$AB${first - 1}:$AB${last},MOC!$A${first - 1}:$A${last},"<="&x_steps)', "m",
         "lowest head anywhere in the pipe")
    cval("x_dmoc", "=x_hpeak*x_rho*x_g-x_ps", "Pa", "MOC surge above rest pressure")
    cval("x_ddes", "=MAX(x_dcf,x_dmoc)", "Pa", "design surge")
    cval("x_peak", "=x_ps+x_ddes", "Pa", "peak gauge pressure")
    cval("x_pmin", "=x_hmin*x_rho*x_g", "Pa", "minimum gauge pressure")
    cval("x_pvg", "=x_pv-x_patm", "Pa", "vapour pressure (gauge)")
    cval("x_dallow", "=in_maxsurge*1E5", "Pa", "")
    cval("ok_surge", "=x_ddes<=x_dallow", "", "")
    cval("ok_peak", "=x_peak<=in_rating*1E5", "", "")
    cval("ok_min", "=x_pmin>x_pvg", "", "")
    cval("ok_vel", "=x_v<=in_vadv", "", "advisory")
    cval("x_required", "=NOT(AND(ok_surge,ok_peak,ok_min))", "", "")
    cval("x_tneed", "=IF(x_djk<=x_dallow,0,2*x_rho*in_L*x_v/x_dallow)", "s",
         "closure time meeting the limit (Michaud estimate)")
    cval("x_qallow", "=x_dallow/(x_rho*x_a)*x_area*60000", "l/min", "flow passing even instant closure")
    cval("x_darr", "=MIN(x_dallow,in_rating*1E5-x_ps)", "Pa", "allowed rise for the arrester")
    cval("x_ke", "=0.5*x_rho*x_area*in_L*x_v^2", "J", "kinetic energy of the column")
    cval("x_p0", "=x_ps+x_patm", "Pa abs", "arrester precharge")
    cval("x_work", "=IF(ABS(in_n-1)<1E-9,x_p0*LN((x_p0+x_darr)/x_p0),"
         "x_p0*(((x_p0+x_darr)/x_p0)^((in_n-1)/in_n)-1)/(in_n-1))", "J/m3", "gas work per unit precharge volume")
    cval("x_varr", "=IF(x_darr<=0,1E9,x_ke/x_work*1E6)", "ml", "arrester precharge volume")
    calc.column_dimensions["A"].width = 14
    calc.column_dimensions["B"].width = 18
    calc.column_dimensions["D"].width = 60

    # ------------------------------------------------------------------- MOC
    n = MOC_REACHES
    hcols = [3 + 1 + i for i in range(n + 1)]  # D..N
    qcols = [hcols[-1] + 1 + i for i in range(n + 1)]  # O..Y
    cp_col, kv_col, min_col, p_col = qcols[-1] + 1, qcols[-1] + 2, qcols[-1] + 3, qcols[-1] + 4
    tx_col = p_col + 1  # time for the chart, blank (NA) after the simulated period
    from openpyxl.utils import get_column_letter as L

    moc["A1"] = ("Method of characteristics: reservoir (constant head) - pipe - closing valve. "
                 "H = piezometric head (m, gauge), Q = flow (m3/s); node 0 is the reflection point, "
                 f"node {n} the valve.")
    moc["A1"].font = NOTE
    moc["A3"] = "Rows beyond 'time steps used' (Calc) are ignored."
    moc["A3"].font = NOTE
    head = ["step", "t (s)", "tau"] + [f"H{i}" for i in range(n + 1)] + [f"Q{i}" for i in range(n + 1)] + \
           ["CP valve", "kv", "min H", "valve p (bar g)", "t for chart (s)"]
    for j, h in enumerate(head, start=1):
        moc.cell(row=5, column=j, value=h).font = HEAD_FONT
    r0_ = first - 1  # row 6 = step 0
    moc.cell(row=r0_, column=1, value=0)
    moc.cell(row=r0_, column=2, value=0)
    moc.cell(row=r0_, column=3, value=1)
    for i in range(n + 1):
        moc.cell(row=r0_, column=hcols[i], value=f"=x_hres-x_hf*{i}/x_N")
        moc.cell(row=r0_, column=qcols[i], value="=x_Q")
    moc.cell(row=r0_, column=min_col, value=f"=MIN({L(hcols[0])}{r0_}:{L(hcols[-1])}{r0_})")
    moc.cell(row=r0_, column=p_col, value=f"={L(hcols[-1])}{r0_}*x_rho*x_g/1E5")
    moc.cell(row=r0_, column=tx_col, value=0)

    def cp(i: int, r: int) -> str:  # C+ from node i-1 at the previous row
        h, q = f"{L(hcols[i - 1])}{r - 1}", f"{L(qcols[i - 1])}{r - 1}"
        return f"({h}+x_B*{q}-x_R*{q}*ABS({q}))"

    def cm(i: int, r: int) -> str:  # C- from node i+1 at the previous row
        h, q = f"{L(hcols[i + 1])}{r - 1}", f"{L(qcols[i + 1])}{r - 1}"
        return f"({h}-x_B*{q}+x_R*{q}*ABS({q}))"

    for r in range(first, last + 1):
        moc.cell(row=r, column=1, value=f"=A{r - 1}+1")
        moc.cell(row=r, column=2, value=f"=A{r}*x_dt")
        moc.cell(row=r, column=3, value=f"=IF(OR(x_tc=0,B{r}>=x_tc),0,1-B{r}/x_tc)")
        moc.cell(row=r, column=hcols[0], value="=x_hres")
        moc.cell(row=r, column=qcols[0], value=f"=(x_hres-{cm(0, r)})/x_B")
        for i in range(1, n):
            moc.cell(row=r, column=hcols[i], value=f"=({cp(i, r)}+{cm(i, r)})/2")
            moc.cell(row=r, column=qcols[i], value=f"=({cp(i, r)}-{cm(i, r)})/(2*x_B)")
        cpc, kvc = f"{L(cp_col)}{r}", f"{L(kv_col)}{r}"
        moc.cell(row=r, column=cp_col, value="=" + cp(n, r))
        moc.cell(row=r, column=kv_col, value=f"=(C{r}*x_Q)^2/x_hv0")
        moc.cell(row=r, column=qcols[n],
                 value=f"=IF(OR({kvc}=0,{cpc}<=0),0,(-{kvc}*x_B+SQRT(({kvc}*x_B)^2+4*{kvc}*{cpc}))/2)")
        moc.cell(row=r, column=hcols[n], value=f"={cpc}-x_B*{L(qcols[n])}{r}")
        moc.cell(row=r, column=min_col, value=f"=MIN({L(hcols[0])}{r}:{L(hcols[-1])}{r})")
        moc.cell(row=r, column=p_col, value=f"=IF(A{r}<=x_steps,{L(hcols[-1])}{r}*x_rho*x_g/1E5,NA())")
        moc.cell(row=r, column=tx_col, value=f"=IF(A{r}<=x_steps,B{r},NA())")
    moc.freeze_panes = "D6"

    # --------------------------------------------------------------- Results
    model["F4"] = "Results"
    model["F4"].font = HEAD_FONT
    for c in "FGHI":
        model[f"{c}4"].border = RULE
    results = [
        ("Pipe", '=x_od&" x "&x_wall&" mm "&x_mat&IF(x_al>0," (Al "&x_al&" mm)","")', ""),
        ("Bore", "=x_D*1000", "mm"),
        ("Closure time", "=x_tc", "s"),
        ("Velocity", "=x_v", "m/s"),
        ("Wave speed a", "=x_a", "m/s"),
        ("Critical time 2L/a", "=x_Tcrit*1000", "ms"),
        ("Closure regime", "=x_regime", ""),
        ("Joukowsky surge", "=x_djk/1E5", "bar"),
        ("Closed-form surge", "=x_dcf/1E5", "bar"),
        ("MOC surge", "=x_dmoc/1E5", "bar"),
        ("Design surge (larger)", "=x_ddes/1E5", "bar"),
        ("Peak pressure", "=x_peak/1E5", "bar g"),
        ("Minimum pressure (unphysical below vapour pressure)", "=x_pmin/1E5", "bar g"),
    ]
    rr = 5
    for label, f, unit in results:
        model.cell(row=rr, column=6, value=label).font = BODY
        c = model.cell(row=rr, column=7, value=f)
        c.font = BODY
        c.number_format = "0.00"
        model.cell(row=rr, column=8, value=unit).font = BODY
        rr += 1
    rr += 1
    model.cell(row=rr, column=6, value="Checks").font = HEAD_FONT
    for c in "FGHI":
        model[f"{c}{rr}"].border = RULE
    rr += 1
    checks = [
        ("Surge above rest pressure", "=x_ddes/1E5", "=in_maxsurge", "ok_surge", "bar", "governs"),
        ("Peak pressure", "=x_peak/1E5", "=in_rating", "ok_peak", "bar g", "governs"),
        ("Minimum vs vapour pressure", "=x_pmin/1E5", "=x_pvg/1E5", "ok_min", "bar g", "governs"),
        ("Velocity", "=x_v", "=in_vadv", "ok_vel", "m/s", "advisory"),
    ]
    model.cell(row=rr, column=6, value="Check").font = HEAD_FONT
    model.cell(row=rr, column=7, value="Value").font = HEAD_FONT
    model.cell(row=rr, column=8, value="Limit").font = HEAD_FONT
    model.cell(row=rr, column=9, value="Result").font = HEAD_FONT
    rr += 1
    status_cells = []
    for label, val, lim, ok, unit, kind in checks:
        model.cell(row=rr, column=6, value=f"{label} ({unit})").font = BODY
        for col, f in ((7, val), (8, lim)):
            c = model.cell(row=rr, column=col, value=f)
            c.number_format = "0.00"
            c.font = BODY
        fail = "FAIL" if kind == "governs" else "ADVISE"
        model.cell(row=rr, column=9, value=f'=IF({ok},"PASS","{fail}")').font = Font(name="Arial", bold=True, size=10)
        status_cells.append(f"I{rr}")
        rr += 1
    rr += 1
    model.cell(row=rr, column=6, value="Verdict").font = HEAD_FONT
    v = model.cell(row=rr, column=7, value='=IF(x_required,"MITIGATION REQUIRED","No mitigation required")')
    v.font = Font(name="Arial", bold=True, size=12, color=INK)
    verdict_cell = f"G{rr}"
    rr += 1
    model.cell(row=rr, column=6, value="Model check").font = BODY
    model.cell(row=rr, column=7, value='=IF(x_hv0<=0,"Flow not deliverable: friction exceeds rest pressure",'
               'IF(x_rows_ok,"OK","MOC sheet too short for this case: use the Python model"))').font = BODY
    rr += 2
    model.cell(row=rr, column=6, value="If mitigation is required").font = HEAD_FONT
    for c in "FGHI":
        model[f"{c}{rr}"].border = RULE
    rr += 1
    recs = [
        ("Arrester precharge volume (indicative)", "=IF(x_required,x_varr,\"-\")", "ml"),
        ("Closure time meeting the limit (Michaud)", "=x_tneed", "s"),
        ("Flow passing even instant closure", "=x_qallow", "l/min"),
    ]
    for label, f, unit in recs:
        model.cell(row=rr, column=6, value=label).font = BODY
        c = model.cell(row=rr, column=7, value=f)
        c.number_format = "0.00"
        c.font = BODY
        model.cell(row=rr, column=8, value=unit).font = BODY
        rr += 1
    model.cell(row=rr, column=6, value=("The Python model refines the closure time against the MOC simulation; "
                                        "here, enter it as a custom closure time and check the MOC surge.")).font = NOTE

    red_font = Font(name="Arial", bold=True, color=RED)
    for ref in status_cells:
        model.conditional_formatting.add(ref, FormulaRule(formula=[f'{ref}="FAIL"'], font=red_font))
    model.conditional_formatting.add(verdict_cell, FormulaRule(formula=["x_required"], font=Font(
        name="Arial", bold=True, size=12, color=RED)))

    model.column_dimensions["A"].width = 32
    model.column_dimensions["B"].width = 16
    model.column_dimensions["C"].width = 7
    model.column_dimensions["D"].width = 40
    model.column_dimensions["E"].width = 3
    model.column_dimensions["F"].width = 40
    model.column_dimensions["G"].width = 22
    model.column_dimensions["H"].width = 9
    model.column_dimensions["I"].width = 9
    for r in model.iter_rows(min_row=5, max_row=40, min_col=1, max_col=9):
        for c in r:
            c.alignment = Alignment(vertical="center")

    # Valve pressure trace (plain line, no gridlines: Tufte / Economist)
    model["A23"] = "Pressure at the valve (bar g) against time (s), from the MOC sheet"
    model["A23"].font = HEAD_FONT
    ch = ScatterChart()
    ch.style = 1
    ch.height, ch.width = 8, 18
    ch.legend = None
    ch.x_axis.title = None
    ch.x_axis.majorGridlines = None
    ch.y_axis.majorGridlines = None
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    xs = Reference(moc, min_col=tx_col, min_row=r0_, max_row=last)
    ys = Reference(moc, min_col=p_col, min_row=r0_, max_row=last)
    s = Series(ys, xs)
    s.graphicalProperties.line.solidFill = RED
    s.graphicalProperties.line.width = 19050
    s.marker.symbol = "none"
    s.smooth = False
    ch.series.append(s)
    ch.x_axis.tickLblPos = "low"
    model.add_chart(ch, "A25")

    wb.calculation.fullCalcOnLoad = True
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    recalc_with_libreoffice(OUT)
    return OUT


def recalc_with_libreoffice(path: Path) -> None:
    """Store calculated values in the file (so previews and viewers that do not
    recalculate show results). Skipped if LibreOffice is not installed;
    Excel recalculates on open either way."""
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("soffice"):
        print("LibreOffice not found: saved without cached values")
        return
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", d, str(path)],
                       check=True, capture_output=True, timeout=600)
        shutil.copyfile(Path(d) / path.name, path)


if __name__ == "__main__":
    print(build())
