import math

import pytest

from waterhammer import PRESETS, Inputs, Limits, arrester_volume, assess, assess_simple, simulate_moc, wave_speed
from waterhammer.model import friction_factor
from waterhammer.properties import G, water_bulk_modulus, water_density, water_viscosity

T = 55.0


def test_water_properties():
    assert water_density(20) == pytest.approx(998.2)
    assert water_bulk_modulus(20) == pytest.approx(2.19e9, rel=0.01)
    assert water_viscosity(20) == pytest.approx(1.002e-3, rel=0.01)


def test_wave_speed_ranges():
    # Copper ~1300 m/s, PE-X a few hundred m/s, rigid pipe limit = speed of sound in water
    assert 1200 < wave_speed(PRESETS["copper_15x0.7"], T) < 1450
    assert 200 < wave_speed(PRESETS["pex_12x2.0"], T) < 450
    mlcp, pex = wave_speed(PRESETS["mlcp_16x2.0"], T), wave_speed(PRESETS["pex_16x2.2"], T)
    assert mlcp > pex  # aluminium layer stiffens the wall
    assert wave_speed(PRESETS["pex_12x2.0"], 20) > wave_speed(PRESETS["pex_12x2.0"], 70)


def test_moc_instant_closure_matches_joukowsky():
    p = PRESETS["copper_12x0.6"]
    q = 4 / 60000
    r = simulate_moc(p, 5, q, 3e5, T, 0.0)
    jk = water_density(T) * wave_speed(p, T) * q / p.bore_area
    assert (r.peak_gauge_pa - 3e5) == pytest.approx(jk, rel=0.03)


@pytest.mark.parametrize("tc", [0.3, 0.5, 1.0])
def test_moc_slow_closure_matches_rigid_column(tc):
    """For t_c >> 2L/a the elastic result tends to rigid-column theory."""
    p, L, T_ = PRESETS["pex_12x2.0"], 8.0, T
    rho, A, D = water_density(T_), p.bore_area, p.inner_diameter
    q0 = 6 / 60000
    v0 = q0 / A
    f = friction_factor(rho * v0 * D / water_viscosity(T_), p.material.roughness / D)
    hr = 3e5 / (rho * G)
    h0 = hr - f * L / D * v0**2 / (2 * G)
    q, t, dt, hmax = q0, 0.0, 2e-6, h0
    while t < tc * 0.999:
        tau = 1 - t / tc
        hv = h0 * (q / (tau * q0)) ** 2
        q = max(q + (hr - f * L / D * (q / A) ** 2 / (2 * G) - hv) * G * A / L * dt, 0.0)
        hmax = max(hmax, hv)
        t += dt
    rigid = hmax * rho * G - 3e5
    moc = simulate_moc(p, L, q0, 3e5, T_, tc).peak_gauge_pa - 3e5
    assert moc == pytest.approx(rigid, rel=0.05)


def test_short_copper_screw_down_tap_is_fine():
    r = assess_simple("copper_15x0.7", 3, 4, "screw_down")
    assert not r.mitigation_required
    assert r.design_surge_bar < 0.5


def test_solenoid_on_long_copper_needs_mitigation():
    r = assess_simple("copper_10x0.6", 8, 6, "solenoid")
    assert r.mitigation_required
    assert r.regime == "slow"  # 2L/a ~ 12 ms < 20 ms closure
    assert r.min_closure_time_s > 0.02
    # closing that slowly should then pass
    r2 = assess_simple("copper_10x0.6", 8, 6, r.min_closure_time_s * 1.01)
    assert r2.design_surge_bar <= 2.0 + 1e-6


def test_recommended_flow_passes_even_instant_closure():
    r = assess_simple("pex_12x2.0", 10, 6, "solenoid")
    r2 = assess_simple("pex_12x2.0", 10, r.max_flow_for_instant_closure_l_min * 0.99, 0.0)
    assert r2.design_surge_bar <= 2.0


def test_limits_are_configurable():
    base = assess_simple("pex_12x2.0", 8, 6, "single_lever_mixer")
    loose = assess_simple("pex_12x2.0", 8, 6, "single_lever_mixer", limits=Limits(max_surge_bar=5.0))
    assert base.mitigation_required and not loose.mitigation_required


def test_closed_form_only():
    r = assess(Inputs(PRESETS["pex_12x2.0"], 8, 6, closure_time_s=0.1, simulate=False))
    assert r.moc_surge_bar is None
    assert r.design_surge_bar == pytest.approx(r.closed_form_surge_bar)


def test_arrester_volume():
    # isothermal closed form check
    v = arrester_volume(1000, 1e-4, 10, 2.0, 3e5, 2e5, n=1.0)
    ke = 0.5 * 1000 * 1e-4 * 10 * 4
    p0 = 3e5 + 101325
    assert v == pytest.approx(ke / (p0 * math.log((p0 + 2e5) / p0)))
    assert arrester_volume(1000, 1e-4, 10, 2.0, 3e5, 2e5, n=1.4) > v


def test_bad_inputs():
    with pytest.raises(ValueError):
        Inputs(PRESETS["pex_12x2.0"], 0, 6)
    with pytest.raises(ValueError):
        simulate_moc(PRESETS["pex_10x1.5"], 50, 12 / 60000, 1e5, T, 0.1)  # friction > supply pressure


def test_arrester_volume_reported_in_ml():
    r = assess_simple("copper_10x0.6", 8, 6, "solenoid")
    assert 1 < r.arrester_precharge_volume_ml < 50
    assert f"{r.arrester_precharge_volume_ml:.0f} ml" in r.recommendations[0]
