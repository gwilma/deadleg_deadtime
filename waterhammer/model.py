"""Water hammer screening for a domestic hot water pipe ending at a tap.

The situation modelled: water flows at Q through a pipe of length L from a
point of near-constant pressure (the "reflection point": a larger main, a
manifold, a cylinder or an accumulator) to a valve that closes in time t_c.

Two estimates of the pressure rise at the valve are made:

1. Closed form. Joukowsky's dp = rho a v when t_c <= 2L/a (rapid closure),
   otherwise Michaud's dp = 2 rho L v / t_c (slow closure, linear decrease of
   velocity). See Wylie & Streeter (1993) ch. 1-3; Thorley (2004) ch. 2.
2. Method of characteristics (MOC) simulation of the same pipe with a
   constant-head upstream boundary, steady friction and an orifice valve whose
   open area falls to zero over t_c. A real valve chokes most of the flow
   near the end of its stroke, so this is usually higher than Michaud.

The verdict uses the larger of the two and compares it with the limits in
`Limits`. Sources for every limit are in docs/water_hammer.md.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from .properties import (
    G,
    P_ATM,
    PRESETS,
    Pipe,
    water_bulk_modulus,
    water_density,
    water_vapour_pressure,
    water_viscosity,
)

# Indicative effective closure times (s): the time over which the valve
# actually throttles the flow, not the full handle travel. Measure if it
# matters. See docs/water_hammer.md for where these come from.
VALVE_CLOSURE_TIMES: dict[str, float] = {
    "solenoid": 0.02,  # washing machine, dishwasher, sensor tap, electric shower, WC flush valve
    "single_lever_mixer": 0.1,  # lever flicked shut; ceramic cartridge
    "quarter_turn": 0.15,  # ceramic-disc quarter-turn tap or ball valve, closed briskly
    "thermostatic_shower": 0.3,
    "screw_down": 1.0,  # traditional compression (washer) tap
}


@dataclass
class Limits:
    """Acceptance limits. Defaults and their sources: docs/water_hammer.md."""

    max_surge_bar: float = 2.0  # rise above rest pressure; EN 806-2 / DIN 1988-200 / VDI 6006
    max_peak_bar: float | None = None  # absolute ceiling, gauge; None = pipe/fitting rating below
    pressure_rating_bar: float = 10.0  # lowest PN of pipe/fittings at the hot water temperature
    advisory_velocity_m_s: float = 1.5  # hot water, UPC 610.12 / CDA; DIN 1988-300 allows 2 m/s

    def peak_limit_bar(self) -> float:
        return self.max_peak_bar if self.max_peak_bar is not None else self.pressure_rating_bar


@dataclass
class Inputs:
    pipe: Pipe
    length_m: float  # valve to reflection point
    flow_l_min: float
    static_pressure_bar: float = 3.0  # gauge, at rest (no flow); typical PRV / HIU setting
    temperature_c: float = 55.0
    closure_time_s: float = 0.1
    restraint: str = "anchored"  # anchored | expansion_joints | upstream_anchor
    limits: Limits = field(default_factory=Limits)
    simulate: bool = True
    gas_polytropic_index: float = 1.4  # arrester sizing; 1.0 isothermal, 1.4 adiabatic (conservative)

    def __post_init__(self):
        if self.length_m <= 0 or self.flow_l_min <= 0 or self.closure_time_s < 0:
            raise ValueError("length and flow must be positive and closure time non-negative")


def restraint_factor(pipe: Pipe, restraint: str) -> float:
    """Thick-wall pipe restraint coefficient psi (Wylie & Streeter, eq. 2.21)."""
    d, e, nu = pipe.inner_diameter, pipe.wall, pipe.poisson
    thick = 2 * (e / d) * (1 + nu)
    if restraint == "anchored":  # anchored against axial movement throughout (clipped, buried)
        return thick + d * (1 - nu**2) / (d + e)
    if restraint == "expansion_joints":  # free to move axially
        return thick + d / (d + e)
    if restraint == "upstream_anchor":  # anchored at the upstream end only
        return thick + d * (1 - nu / 2) / (d + e)
    raise ValueError(f"unknown restraint {restraint!r}")


def wave_speed(pipe: Pipe, t_c: float, restraint: str = "anchored") -> float:
    """Pressure wave speed a (m/s) in a liquid-filled elastic pipe (Korteweg)."""
    k = water_bulk_modulus(t_c)
    rho = water_density(t_c)
    e_wall = pipe.hoop_modulus(t_c)
    psi = restraint_factor(pipe, restraint)
    return math.sqrt((k / rho) / (1 + psi * k * pipe.inner_diameter / (e_wall * pipe.wall)))


def friction_factor(re: float, rel_rough: float) -> float:
    """Darcy friction factor: laminar below Re 2300, Swamee-Jain above."""
    if re < 2300:
        return 64 / max(re, 1e-9)
    return 0.25 / math.log10(rel_rough / 3.7 + 5.74 / re**0.9) ** 2


def surge_closed_form(rho: float, a: float, v: float, length: float, t_close: float) -> tuple[float, str]:
    """(pressure rise Pa, regime)."""
    t_crit = 2 * length / a
    if t_close <= t_crit:
        return rho * a * v, "rapid"
    return 2 * rho * length * v / t_close, "slow"


@dataclass
class MocResult:
    peak_gauge_pa: float
    min_gauge_pa: float
    times: list[float]
    valve_gauge_pa: list[float]


def simulate_moc(pipe: Pipe, length: float, flow_m3s: float, static_gauge_pa: float, t_c: float,
                 t_close: float, restraint: str = "anchored", reaches: int = 20,
                 closure_exponent: float = 1.0, periods_after: float = 6.0) -> MocResult:
    """Reservoir - pipe - valve MOC (Wylie & Streeter ch. 3), steady friction.

    The valve discharges to atmosphere; its open area fraction is
    (1 - t/t_close)^closure_exponent. No column separation model: when the
    pressure falls to vapour pressure the result is flagged, not modelled.
    """
    rho = water_density(t_c)
    a = wave_speed(pipe, t_c, restraint)
    area, d = pipe.bore_area, pipe.inner_diameter
    v0 = flow_m3s / area
    re = rho * v0 * d / water_viscosity(t_c)
    f = friction_factor(re, pipe.material.roughness / d)

    n = max(reaches, 4)
    dx = length / n
    dt = dx / a
    b = a / (G * area)
    r = f * dx / (2 * G * d * area**2)

    h_res = static_gauge_pa / (rho * G)  # head at the reflection point (gauge)
    hf = f * length / d * v0**2 / (2 * G)
    h_valve0 = h_res - hf
    if h_valve0 <= 0:
        raise ValueError("friction exceeds the static pressure: this flow cannot be delivered")

    h = [h_res - hf * i / n for i in range(n + 1)]
    q = [flow_m3s] * (n + 1)
    t_end = t_close + periods_after * 2 * length / a
    steps = int(math.ceil(t_end / dt))
    times, valve_p = [0.0], [h_valve0 * rho * G]
    peak = min_h = h_valve0
    for k in range(1, steps + 1):
        t = k * dt
        tau = 0.0 if t >= t_close or t_close == 0 else (1 - t / t_close) ** closure_exponent
        hn, qn = h[:], q[:]
        for i in range(1, n):
            cp = h[i - 1] + b * q[i - 1] - r * q[i - 1] * abs(q[i - 1])
            cm = h[i + 1] - b * q[i + 1] + r * q[i + 1] * abs(q[i + 1])
            hn[i] = (cp + cm) / 2
            qn[i] = (cp - cm) / (2 * b)
        cm = h[1] - b * q[1] + r * q[1] * abs(q[1])
        hn[0] = h_res
        qn[0] = (h_res - cm) / b
        cp = h[n - 1] + b * q[n - 1] - r * q[n - 1] * abs(q[n - 1])
        kv = (tau * flow_m3s) ** 2 / h_valve0
        if kv == 0 or cp <= 0:
            qn[n] = 0.0
        else:
            qn[n] = (-kv * b + math.sqrt((kv * b) ** 2 + 4 * kv * cp)) / 2
        hn[n] = cp - b * qn[n]
        h, q = hn, qn
        peak = max(peak, h[n])
        min_h = min(min_h, min(h))
        times.append(t)
        valve_p.append(h[n] * rho * G)
    return MocResult(peak * rho * G, min_h * rho * G, times, valve_p)


@dataclass
class Check:
    name: str
    value: float
    limit: float
    unit: str
    passed: bool
    governs: bool  # True = failing it means mitigation is required; False = advisory
    note: str = ""


@dataclass
class Assessment:
    inputs: dict
    velocity_m_s: float
    wave_speed_m_s: float
    critical_time_s: float
    regime: str
    joukowsky_bar: float
    closed_form_surge_bar: float
    moc_surge_bar: float | None
    design_surge_bar: float
    peak_gauge_bar: float
    min_gauge_bar: float | None
    checks: list[Check]
    mitigation_required: bool
    min_closure_time_s: float  # shortest effective closure time that meets the surge limit
    max_flow_for_instant_closure_l_min: float
    arrester_precharge_volume_ml: float | None
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def assess(inp: Inputs) -> Assessment:
    lim = inp.limits
    t = inp.temperature_c
    rho = water_density(t)
    a = wave_speed(inp.pipe, t, inp.restraint)
    q = inp.flow_l_min / 60_000
    v = q / inp.pipe.bore_area
    L = inp.length_m
    t_crit = 2 * L / a
    p_static = inp.static_pressure_bar * 1e5
    dp_allow = lim.max_surge_bar * 1e5

    dp_jk = rho * a * v
    dp_cf, regime = surge_closed_form(rho, a, v, L, inp.closure_time_s)

    moc_surge = min_gauge = None
    if inp.simulate:
        res = simulate_moc(inp.pipe, L, q, p_static, t, inp.closure_time_s, inp.restraint)
        moc_surge = res.peak_gauge_pa - p_static
        min_gauge = res.min_gauge_pa
    dp_design = max(dp_cf, moc_surge or 0.0)
    peak = p_static + dp_design
    if min_gauge is None:
        min_gauge = p_static - dp_design  # first negative wave reflected back from the reservoir
    p_vap_gauge = water_vapour_pressure(t) - P_ATM

    checks = [
        Check("Surge above rest pressure", dp_design / 1e5, lim.max_surge_bar, "bar",
              dp_design <= dp_allow, True,
              "EN 806-2 / DIN 1988-200 / VDI 6006: pressure rise from valve operation <= 2 bar"),
        Check("Peak pressure (gauge)", peak / 1e5, lim.peak_limit_bar(), "bar",
              peak <= lim.peak_limit_bar() * 1e5, True,
              "Must not exceed the pressure rating of pipe and fittings at temperature "
              "(Water Supply (Water Fittings) Regs 1999 Sch. 2 paras 3, 5, 12)"),
        Check("Minimum pressure vs vapour pressure (gauge)", min_gauge / 1e5, p_vap_gauge / 1e5, "bar",
              min_gauge > p_vap_gauge, True,
              "Below vapour pressure the column separates and the collapse can exceed Joukowsky"),
        Check("Flow velocity", v, lim.advisory_velocity_m_s, "m/s",
              v <= lim.advisory_velocity_m_s, False,
              "Advisory: UPC 610.12 / CDA 1.5 m/s for hot water; DIN 1988-300 2 m/s for single connection pipes"),
    ]
    required = any(not c.passed for c in checks if c.governs)

    # Shortest valve closure time that meets the surge limit, by the same
    # "larger of Michaud and MOC" rule as the design surge.
    if dp_jk <= dp_allow:
        t_need = 0.0
    else:
        t_need = 2 * rho * L * v / dp_allow
        if inp.simulate:
            t_need = max(t_need, _closure_time_for_limit(inp, q, p_static, dp_allow, t_need))
    v_allow = dp_allow / (rho * a)
    q_allow = v_allow * inp.pipe.bore_area * 60_000

    vol = None
    if required:
        vol = arrester_volume(rho, inp.pipe.bore_area, L, v, p_static, min(dp_allow, lim.peak_limit_bar() * 1e5 - p_static),
                              inp.gas_polytropic_index)

    recs: list[str] = []
    if required:
        recs.append(f"Fit a water hammer arrester (e.g. ASSE 1010 certified) as close as possible to the "
                    f"quick-closing valve; indicative gas precharge volume >= {vol * 1e6:.0f} ml "
                    f"(precharged to rest pressure; check the manufacturer's sizing).")
        if t_need is not None and t_need > inp.closure_time_s:
            recs.append(f"Or use a valve whose effective closure time is >= {t_need:.2f} s "
                        f"(the pipe's critical time 2L/a is {t_crit * 1e3:.0f} ms).")
        recs.append(f"Or reduce velocity: a flow of <= {q_allow:.1f} l/min (v <= {v_allow:.2f} m/s) keeps even "
                    f"instantaneous closure within {lim.max_surge_bar:g} bar; upsize the pipe or fit a flow regulator.")
        recs.append("Or shorten the run to the nearest reflection point (larger main, manifold, cylinder) "
                    "or reduce rest pressure with a PRV if the peak-pressure check fails.")
    elif v > lim.advisory_velocity_m_s:
        recs.append("No arrester needed on surge grounds, but velocity is above the advisory limit "
                    "(noise and erosion-corrosion in copper); consider the next pipe size up.")
    else:
        recs.append("No mitigation required for this valve and flow.")

    inputs = asdict(inp)
    inputs["pipe"] = inp.pipe.describe()
    return Assessment(inputs, v, a, t_crit, regime, dp_jk / 1e5, dp_cf / 1e5,
                      None if moc_surge is None else moc_surge / 1e5, dp_design / 1e5, peak / 1e5,
                      min_gauge / 1e5, checks, required, t_need, q_allow, vol, recs)


def _closure_time_for_limit(inp: Inputs, q: float, p_static: float, dp_allow: float, guess: float) -> float:
    """Bisect the MOC model for the closure time giving a surge of dp_allow."""
    def surge(tc: float) -> float:
        r = simulate_moc(inp.pipe, inp.length_m, q, p_static, inp.temperature_c, tc, inp.restraint)
        return r.peak_gauge_pa - p_static

    lo, hi = guess, guess
    while surge(lo) <= dp_allow and lo > 1e-3:
        lo /= 2
    while surge(hi) > dp_allow:
        hi *= 2
        if hi > 60:
            return math.inf
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if surge(mid) > dp_allow else (lo, mid)
    return hi


def arrester_volume(rho: float, area: float, length: float, v: float, p_static_gauge: float,
                    dp_allow: float, n: float = 1.4) -> float:
    """Gas precharge volume V0 (m3) that absorbs the column's kinetic energy
    while the pressure rises from rest pressure by no more than dp_allow.

    Energy balance (pipe and water elasticity ignored, so conservative):
        1/2 rho A L v^2 = p0 V0 [ (p1/p0)^((n-1)/n) - 1 ] / (n - 1)    (n != 1)
                        = p0 V0 ln(p1/p0)                              (n == 1)
    with p0, p1 absolute. This is the classic air-chamber sizing method.
    """
    if dp_allow <= 0:
        return math.inf
    ke = 0.5 * rho * area * length * v**2
    p0 = p_static_gauge + P_ATM
    ratio = (p0 + dp_allow) / p0
    if abs(n - 1) < 1e-9:
        work_per_v0 = p0 * math.log(ratio)
    else:
        work_per_v0 = p0 * (ratio ** ((n - 1) / n) - 1) / (n - 1)
    return ke / work_per_v0


def assess_simple(pipe: str | Pipe, length_m: float, flow_l_min: float, valve: str | float = "single_lever_mixer",
                  **kwargs) -> Assessment:
    """Convenience wrapper: pipe preset name, valve type name or closure time in s."""
    p = PRESETS[pipe] if isinstance(pipe, str) else pipe
    tc = VALVE_CLOSURE_TIMES[valve] if isinstance(valve, str) else float(valve)
    return assess(Inputs(p, length_m, flow_l_min, closure_time_s=tc, **kwargs))
