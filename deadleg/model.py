"""Transient model of hot water displacing cold water along a pipe.

State, on an axial grid of ``n_axial`` cells of length dx:

* ``Tw[i]``      bulk water temperature in cell i
* ``Tp[i, j]``   pipe wall temperature in cell i, radial shell j (j=0 at the bore)
* ``Ta``         temperature of the single, well mixed body of air around the pipe

Each time step is split into three operators (see docs/derivation.md):

1. radial heat exchange water -> wall -> air, solved implicitly (backward Euler)
   for every cell together with the air node, which couples all cells;
2. axial conduction along the wall, implicit;
3. advection of the water by exactly one cell (the time step is dx/u while
   water flows), which transports the temperature profile without numerical
   diffusion, so the hot front stays sharp unless heat transfer smears it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
from scipy.linalg import solve_banded

from . import correlations as corr
from . import properties as props
from .pipes import Pipe

DEFAULT_AIR_AREA = 0.01  # m2 of air cross-section per metre of pipe (a 100 x 100 mm void)

InletSpec = float | Callable[[float], float] | tuple[Sequence[float], Sequence[float]]


@dataclass
class Scenario:
    """Everything needed to run one simulation.

    ``flow`` is a constant flow rate in l/min (then ``duration`` is required),
    or a schedule of ``(duration_s, flow_l_per_min)`` segments, where a zero
    flow segment models a stagnant period (e.g. cooling between draws).

    ``T_inlet`` is a constant (degC), a function of time, or a
    ``(times_s, temps_C)`` table that is linearly interpolated.

    ``air_volume`` is the volume of the air body in m3. ``None`` uses
    ``DEFAULT_AIR_AREA * length``; ``math.inf`` holds the air at
    ``T_initial`` (a large room).
    """

    pipe: Pipe
    length: float  # m
    flow: float | Sequence[tuple[float, float]]
    duration: float | None = None  # s
    T_initial: float = 20.0  # water, wall and air at t = 0, degC
    T_inlet: InletSpec = 55.0
    air_volume: float | None = None
    air_loss_UA: float = 0.0  # W/K from the air body to a fixed environment
    T_environment: float | None = None  # defaults to T_initial
    h_inner: float | None = None  # W/m2K, overrides the correlation
    h_outer: float | None = None  # W/m2K, overrides convection + radiation
    n_axial: int = 200
    n_radial: int = 6
    wall_axial_conduction: bool = True
    dt_stagnant: float = 1.0  # s, time step during zero-flow segments
    T_ref_water: float | None = None  # degC at which water rho*cp is evaluated
    snapshot_times: Sequence[float] = ()

    def schedule(self) -> list[tuple[float, float]]:
        if isinstance(self.flow, (int, float)):
            if self.duration is None:
                raise ValueError("a constant flow needs a duration")
            return [(float(self.duration), float(self.flow))]
        return [(float(d), float(q)) for d, q in self.flow]

    def inlet_function(self) -> Callable[[float], float]:
        spec = self.T_inlet
        if callable(spec):
            return spec
        if isinstance(spec, (int, float)):
            value = float(spec)
            return lambda t: value
        times, temps = (np.asarray(a, dtype=float) for a in spec)
        return lambda t: float(np.interp(t, times, temps))

    @property
    def water_volume(self) -> float:
        return self.pipe.bore_area * self.length

    def plug_flow_time(self, flow_lpm: float | None = None) -> float:
        """Time for pure displacement of the pipe contents, s."""
        q = flow_lpm if flow_lpm is not None else self.schedule()[0][1]
        return self.water_volume / (q / 60000.0)


@dataclass
class Result:
    scenario: Scenario
    x: np.ndarray  # cell centres, m
    t: np.ndarray  # midpoint of each step, s
    dt: np.ndarray
    flow: np.ndarray  # l/min during each step
    T_in: np.ndarray
    T_out: np.ndarray  # temperature of the water leaving during each step
    T_air: np.ndarray  # at the end of each step
    T_wall_mean: np.ndarray
    volume_out: np.ndarray  # cumulative litres delivered by the end of each step
    energy: dict[str, np.ndarray]  # cumulative J, relative to T_initial
    snapshots: dict[float, dict[str, np.ndarray]] = field(default_factory=dict)
    rho_cp_water: float = 0.0

    @property
    def t_end(self) -> np.ndarray:
        return self.t + self.dt / 2

    def time_to_reach(self, T: float) -> float:
        """First time the outlet temperature reaches T (linear interpolation
        between step midpoints); nan if it never does."""
        return _first_crossing(self.t, self.T_out, T)

    def volume_to_reach(self, T: float) -> float:
        """Litres run off before the outlet reaches T."""
        t = self.time_to_reach(T)
        if math.isnan(t):
            return math.nan
        v_start = self.volume_out - self.flow / 60.0 * self.dt
        v_mid = v_start + self.flow / 60.0 * self.dt / 2
        return float(np.interp(t, self.t, v_mid))

    def energy_balance_error(self) -> float:
        """(energy in - out - stored - lost) / energy in, at the end of the run."""
        e = self.energy
        stored = e["water"][-1] + e["wall"][-1] + e["air"][-1]
        net_in = e["in"][-1] - e["out"][-1]
        return float((net_in - stored - e["environment"][-1]) / max(abs(e["in"][-1]), 1e-12))

    def outlet_at(self, times) -> np.ndarray:
        return np.interp(np.asarray(times, dtype=float), self.t, self.T_out)


def _first_crossing(t, y, level) -> float:
    above = np.nonzero(y >= level)[0]
    if above.size == 0:
        return math.nan
    k = above[0]
    if k == 0:
        return float(t[0])
    t0, t1, y0, y1 = t[k - 1], t[k], y[k - 1], y[k]
    return float(t0 + (level - y0) * (t1 - t0) / (y1 - y0))


def _thomas(a, b, c, d):
    """Solve many tridiagonal systems at once.

    a, b, c: (m, n) sub-, main and super-diagonals (a[:, 0] and c[:, -1] unused).
    d: (m, n, k) right-hand sides, k per system.
    """
    n = b.shape[1]
    cp = np.empty_like(b)
    dp = np.empty_like(d)
    cp[:, 0] = c[:, 0] / b[:, 0]
    dp[:, 0] = d[:, 0] / b[:, 0, None]
    for i in range(1, n):
        m = b[:, i] - a[:, i] * cp[:, i - 1]
        cp[:, i] = c[:, i] / m
        dp[:, i] = (d[:, i] - a[:, i, None] * dp[:, i - 1]) / m[:, None]
    x = np.empty_like(d)
    x[:, -1] = dp[:, -1]
    for i in range(n - 2, -1, -1):
        x[:, i] = dp[:, i] - cp[:, i, None] * x[:, i + 1]
    return x


def simulate(sc: Scenario) -> Result:
    pipe, mat = sc.pipe, sc.pipe.material
    nx, nr = int(sc.n_axial), int(sc.n_radial)
    if nx < 1 or nr < 1:
        raise ValueError("n_axial and n_radial must be at least 1")
    L = float(sc.length)
    dx = L / nx
    x = (np.arange(nx) + 0.5) * dx
    ri, ro = pipe.inner_radius, pipe.outer_radius
    T0 = float(sc.T_initial)
    T_env = T0 if sc.T_environment is None else float(sc.T_environment)
    inlet = sc.inlet_function()
    schedule = sc.schedule()

    # Water: constant rho*cp so that enthalpy is carried exactly by the
    # advection step. Transport properties in the correlations vary with T.
    T_ref = sc.T_ref_water
    if T_ref is None:
        T_ref = 0.5 * (T0 + inlet(0.0))
    rho_cp_w = float(props.water_density(T_ref) * props.water_cp(T_ref))
    Ai = pipe.bore_area
    Cw = rho_cp_w * Ai  # J/K per metre

    # Wall: nr shells of equal thickness. All conductances are per metre.
    rf = np.linspace(ri, ro, nr + 1)
    rc = 0.5 * (rf[:-1] + rf[1:])
    shell_area = math.pi * (rf[1:] ** 2 - rf[:-1] ** 2)
    Cp = mat.volumetric_heat_capacity * shell_area
    k = mat.conductivity
    R_in = math.log(rc[0] / ri) / (2 * math.pi * k)
    R_out = math.log(ro / rc[-1]) / (2 * math.pi * k)
    G_shell = 2 * math.pi * k / np.log(rc[1:] / rc[:-1])  # between shells j and j+1

    # Air body.
    air_volume = DEFAULT_AIR_AREA * L if sc.air_volume is None else float(sc.air_volume)
    air_fixed = math.isinf(air_volume)
    Ca = 0.0 if air_fixed else float(props.air_density(T0) * props.air_cp(T0)) * air_volume
    UA = float(sc.air_loss_UA)

    Tw = np.full(nx, T0)
    Tp = np.full((nx, nr), T0)
    Ta = T0

    rec = {k_: [] for k_ in ("t", "dt", "flow", "T_in", "T_out", "T_air", "T_wall", "vol")}
    en = {k_: [] for k_ in ("in", "out", "water", "wall", "air", "environment", "pipe_to_air")}
    E_in = E_out = Q_env = Q_pa = 0.0
    vol = 0.0
    snapshots: dict[float, dict[str, np.ndarray]] = {}
    pending_snaps = sorted(float(s) for s in sc.snapshot_times)

    n = nr + 1
    a = np.zeros((nx, n))
    b = np.zeros((nx, n))
    c = np.zeros((nx, n))
    d = np.zeros((nx, n, 2))

    t = 0.0
    for seg_duration, q_lpm in schedule:
        if q_lpm < 0:
            raise ValueError("flow must be non-negative")
        if q_lpm > 0:
            u = q_lpm / 60000.0 / Ai
            dt = dx / u
        else:
            u = 0.0
            dt = float(sc.dt_stagnant)
        steps = max(1, int(round(seg_duration / dt)))

        # Axial wall conduction matrix; the same for every shell once each
        # row is divided by the shell area.
        if sc.wall_axial_conduction and nx > 1:
            lam = mat.diffusivity * dt / dx**2
            ab = np.zeros((3, nx))
            ab[0, 1:] = -lam
            ab[2, :-1] = -lam
            ab[1, :] = 1 + 2 * lam
            ab[1, 0] = ab[1, -1] = 1 + lam

        for _ in range(steps):
            # 1. Heat transfer coefficients from the current state.
            if sc.h_inner is not None:
                hi = np.full(nx, float(sc.h_inner))
            else:
                hi = corr.internal_htc(Tw, u, pipe.inner_diameter)
            if sc.h_outer is not None:
                ho = np.full(nx, float(sc.h_outer))
            else:
                ho = corr.external_htc(Tp[:, -1], Ta, pipe.outer_diameter, mat.emissivity)
            gi_s = hi * 2 * math.pi * ri
            Gi = gi_s / (1 + gi_s * R_in)
            go_s = ho * 2 * math.pi * ro
            Go = go_s / (1 + go_s * R_out)

            # 2. Radial exchange, implicit, with the air node eliminated.
            b[:, 0] = Cw / dt + Gi
            c[:, 0] = -Gi
            for j in range(1, n):
                g_left = Gi if j == 1 else G_shell[j - 2]
                g_right = Go if j == nr else G_shell[j - 1]
                a[:, j] = -g_left
                b[:, j] = Cp[j - 1] / dt + g_left + g_right
                c[:, j] = 0.0 if j == nr else -G_shell[j - 1]
            d[:, 0, 0] = Cw / dt * Tw
            d[:, 1:, 0] = Cp / dt * Tp
            d[:, :, 1] = 0.0
            d[:, -1, 1] = Go
            X = _thomas(a, b, c, d)
            X0, X1 = X[..., 0], X[..., 1]
            if air_fixed:
                Ta_new = Ta
            else:
                num = Ca / dt * Ta + dx * np.sum(Go * X0[:, -1]) + UA * T_env
                den = Ca / dt + dx * np.sum(Go * (1 - X1[:, -1])) + UA
                Ta_new = num / den
            sol = X0 + X1 * Ta_new
            Tw = sol[:, 0]
            Tp = sol[:, 1:]
            Q_pa += dx * np.sum(Go * (Tp[:, -1] - Ta_new)) * dt
            Q_env += UA * (Ta_new - T_env) * dt
            Ta = Ta_new

            # 3. Axial conduction along the wall.
            if sc.wall_axial_conduction and nx > 1:
                Tp = solve_banded((1, 1), ab, Tp)

            # 4. Advection by one cell.
            t_mid = t + dt / 2
            T_in = inlet(t_mid)
            if u > 0:
                T_out = Tw[-1]
                Tw = np.concatenate(([T_in], Tw[:-1]))
                E_in += Cw * dx * (T_in - T0)
                E_out += Cw * dx * (T_out - T0)
                vol += Ai * dx * 1000.0
            else:
                T_out = Tw[-1]

            t += dt
            rec["t"].append(t_mid)
            rec["dt"].append(dt)
            rec["flow"].append(q_lpm)
            rec["T_in"].append(T_in)
            rec["T_out"].append(T_out)
            rec["T_air"].append(Ta)
            rec["T_wall"].append(np.dot(Tp.mean(axis=0), shell_area) / shell_area.sum())
            rec["vol"].append(vol)
            en["in"].append(E_in)
            en["out"].append(E_out)
            en["water"].append(Cw * dx * np.sum(Tw - T0))
            en["wall"].append(dx * np.sum((Tp - T0) * Cp))
            en["air"].append(Ca * (Ta - T0))
            en["environment"].append(Q_env)
            en["pipe_to_air"].append(Q_pa)

            while pending_snaps and pending_snaps[0] <= t:
                snapshots[pending_snaps.pop(0)] = {
                    "t": np.float64(t),
                    "T_water": Tw.copy(),
                    "T_wall": Tp.copy(),
                    "T_air": np.float64(Ta),
                }

    return Result(
        scenario=sc,
        x=x,
        t=np.array(rec["t"]),
        dt=np.array(rec["dt"]),
        flow=np.array(rec["flow"]),
        T_in=np.array(rec["T_in"]),
        T_out=np.array(rec["T_out"]),
        T_air=np.array(rec["T_air"]),
        T_wall_mean=np.array(rec["T_wall"]),
        volume_out=np.array(rec["vol"]),
        energy={k_: np.array(v) for k_, v in en.items()},
        snapshots=snapshots,
        rho_cp_water=rho_cp_w,
    )
