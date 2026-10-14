import math

import numpy as np
import pytest

from deadleg import PRESETS, Material, Pipe, Scenario, simulate
from deadleg.analytic import overall_conductance_per_m, schumann_outlet, steady_outlet
from deadleg.correlations import internal_htc

LUMPED_COPPER = Material("lumped copper", conductivity=1e6, density=8940.0, specific_heat=385.0, emissivity=0.0)


def test_no_wall_heat_capacity_gives_pure_plug_flow():
    pipe = Pipe(0.010, 0.0006, Material("weightless", 1.0, 1e-9, 1e-9, 0.0))
    sc = Scenario(pipe, 5.0, 3.0, duration=12.0, T_initial=20.0, T_inlet=55.0, h_outer=0.0, air_volume=math.inf,
                  wall_axial_conduction=False)
    r = simulate(sc)
    t_plug = sc.plug_flow_time()
    assert np.all(r.T_out[r.t < t_plug] == pytest.approx(20.0, abs=1e-6))
    assert np.all(r.T_out[r.t > t_plug] == pytest.approx(55.0, abs=1e-6))


@pytest.mark.parametrize("nx, tol", [(200, 0.01), (800, 0.0025)])
def test_matches_schumann_solution(nx, tol):
    pipe = Pipe(0.010, 0.0006, LUMPED_COPPER)
    h = 3000.0
    sc = Scenario(
        pipe, 5.0, 3.0, duration=30.0, T_initial=0.0, T_inlet=1.0, h_inner=h, h_outer=0.0,
        n_radial=1, n_axial=nx, wall_axial_conduction=False, air_volume=math.inf,
    )
    r = simulate(sc)
    u = 3.0 / 60000.0 / pipe.bore_area
    exact = schumann_outlet(
        r.t, 5.0, u, h, 2 * math.pi * pipe.inner_radius, r.rho_cp_water * pipe.bore_area, pipe.wall_heat_capacity_per_m
    )
    after_front = r.t > 5.0 / u
    assert np.max(np.abs(r.T_out - exact)[after_front]) < tol


def test_steady_state_outlet_with_heat_loss():
    pipe = PRESETS["pex_10x1.5"]
    hi, ho = 2000.0, 8.0
    sc = Scenario(
        pipe, 10.0, 1.0, duration=1500.0, T_initial=20.0, T_inlet=60.0, h_inner=hi, h_outer=ho,
        n_axial=400, wall_axial_conduction=False, air_volume=math.inf,
    )
    r = simulate(sc)
    ua = overall_conductance_per_m(hi, ho, pipe.inner_radius, pipe.outer_radius, pipe.material.conductivity)
    mdot_cp = r.rho_cp_water * 1.0 / 60000.0
    assert r.T_out[-1] == pytest.approx(steady_outlet(60.0, 20.0, 10.0, mdot_cp, ua), abs=0.02)


def test_energy_is_conserved_with_all_physics_and_a_stagnant_period():
    sc = Scenario(
        PRESETS["copper_12x0.6"], 4.0, [(20.0, 4.0), (60.0, 0.0), (15.0, 2.0)],
        T_initial=18.0, T_inlet=lambda t: 18.0 + 40.0 * min(t / 5.0, 1.0),
        air_volume=0.05, air_loss_UA=0.5, T_environment=15.0, n_axial=80,
    )
    r = simulate(sc)
    assert abs(r.energy_balance_error()) < 1e-10
    assert r.energy["environment"][-1] != 0.0


def test_air_body_warms_and_fixed_air_does_not():
    base = dict(pipe=PRESETS["copper_10x0.6"], length=3.0, flow=2.0, duration=60.0, n_axial=60)
    warm = simulate(Scenario(**base))
    fixed = simulate(Scenario(**base, air_volume=math.inf))
    assert warm.T_air[-1] > 25.0
    assert np.all(fixed.T_air == 20.0)
    # A warmer air body loses less heat, so the outlet runs (slightly) hotter.
    assert warm.T_out[-1] > fixed.T_out[-1]


def test_heavier_wall_delays_delivery():
    kw = dict(length=5.0, flow=3.0, duration=40.0, T_initial=20.0, T_inlet=55.0)
    light = simulate(Scenario(PRESETS["copper_10x0.6"], **kw)).time_to_reach(50.0)
    heavy = simulate(Scenario(Pipe(0.010, 0.0012, PRESETS["copper_10x0.6"].material), **kw)).time_to_reach(50.0)
    assert heavy > light


def test_internal_htc_regimes():
    d = 0.0088
    lam = internal_htc(50.0, 0.0, d)
    assert lam == pytest.approx(3.66 * 0.644 / d, rel=0.02)
    turb = internal_htc(50.0, 1.5, d)  # Re ~ 24 000
    assert 8000 < turb < 15000
