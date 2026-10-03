"""Closed-form limiting cases, used to verify the numerical model."""

from __future__ import annotations

import math

import numpy as np
from scipy.integrate import quad
from scipy.special import i0e


def schumann_fluid(xi: float, eta: float) -> float:
    """Dimensionless fluid temperature for the Anzelius-Schumann problem.

    Plug flow over a wall with no radial or axial conduction resistance,
    constant film coefficient, no external losses; the inlet steps from 0 to 1
    at t = 0 into a pipe at 0.

        xi  = h P x / (m_dot c_w)              (number of transfer units to x)
        eta = h P (t - x/u) / C_wall           (time since the plug front passed x)

    theta_f = e^-xi [ e^-eta I0(2 sqrt(xi eta)) + int_0^eta e^-s I0(2 sqrt(xi s)) ds ]
    for eta >= 0, and 0 before the front arrives.
    """
    if eta < 0:
        return 0.0

    def g(s):
        z = 2.0 * math.sqrt(xi * s)
        return i0e(z) * math.exp(z - xi - s)

    integral, _ = quad(g, 0.0, eta, limit=200)
    return g(eta) + integral


def schumann_outlet(t, length, velocity, h, perimeter, C_water, C_wall):
    """Outlet temperature (0..1) of the Schumann problem at times t.

    C_water and C_wall are heat capacities per metre (J/mK);
    m_dot c_w = C_water * velocity.
    """
    xi = h * perimeter * length / (C_water * velocity)
    tau = np.asarray(t, dtype=float) - length / velocity
    return np.array([schumann_fluid(xi, h * perimeter * s / C_wall) for s in np.atleast_1d(tau)])


def steady_outlet(T_in, T_air, length, mdot_cp, UA_per_m):
    """Steady-state outlet temperature with the surroundings at a fixed T_air."""
    return T_air + (T_in - T_air) * math.exp(-UA_per_m * length / mdot_cp)


def overall_conductance_per_m(h_in, h_out, r_in, r_out, k):
    """Water-to-air UA per metre, W/mK."""
    return 1.0 / (
        1.0 / (h_in * 2 * math.pi * r_in) + math.log(r_out / r_in) / (2 * math.pi * k) + 1.0 / (h_out * 2 * math.pi * r_out)
    )
