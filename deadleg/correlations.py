"""Heat transfer coefficient correlations.

Inside the pipe: forced convection, Gnielinski (turbulent) blended with the
fully developed laminar value through the transition range, as in the
VDI Heat Atlas (G1, 2010).

Outside the pipe: natural convection from a horizontal cylinder
(Churchill and Chu, 1975) plus linearised radiation to surroundings taken to
be at the bulk air temperature.
"""

from __future__ import annotations

import numpy as np

from . import properties as p

RE_LAMINAR = 2300.0
RE_TURBULENT = 1.0e4
NU_LAMINAR = 3.66  # fully developed, uniform wall temperature


def _gnielinski(re, pr):
    f = (0.790 * np.log(re) - 1.64) ** -2
    return (f / 8) * (re - 1000.0) * pr / (1.0 + 12.7 * np.sqrt(f / 8) * (pr ** (2.0 / 3.0) - 1.0))


def reynolds(T_water, velocity, inner_diameter):
    nu = p.water_viscosity(T_water) / p.water_density(T_water)
    return np.abs(velocity) * inner_diameter / nu


def internal_nusselt(re, pr):
    re = np.asarray(re, dtype=float)
    pr = np.asarray(pr, dtype=float)
    nu_turb = _gnielinski(np.maximum(re, RE_TURBULENT), pr)
    gamma = np.clip((re - RE_LAMINAR) / (RE_TURBULENT - RE_LAMINAR), 0.0, 1.0)
    nu_blend = (1 - gamma) * NU_LAMINAR + gamma * _gnielinski(np.full_like(re, RE_TURBULENT), pr)
    return np.where(re >= RE_TURBULENT, nu_turb, np.where(re <= RE_LAMINAR, NU_LAMINAR, nu_blend))


def internal_htc(T_water, velocity, inner_diameter):
    """Water-side heat transfer coefficient, W/m2K, evaluated at the local bulk
    water temperature. With no flow it falls back to the laminar conduction
    limit, which is a lower bound (it ignores natural convection in the bore)."""
    re = reynolds(T_water, velocity, inner_diameter)
    nu = internal_nusselt(re, p.water_prandtl(T_water))
    return nu * p.water_conductivity(T_water) / inner_diameter


def natural_convection_htc(T_surface, T_air, outer_diameter):
    """Churchill-Chu, horizontal cylinder, any Rayleigh number."""
    T_surface = np.asarray(T_surface, dtype=float)
    T_film = 0.5 * (T_surface + T_air)
    nu_air = p.air_kinematic_viscosity(T_film)
    k_air = p.air_conductivity(T_film)
    pr = p.air_prandtl(T_film)
    alpha = nu_air / pr
    beta = 1.0 / (T_film + p.KELVIN)
    ra = p.G * beta * np.abs(T_surface - T_air) * outer_diameter**3 / (nu_air * alpha)
    nu = (0.60 + 0.387 * ra ** (1 / 6) / (1 + (0.559 / pr) ** (9 / 16)) ** (8 / 27)) ** 2
    return nu * k_air / outer_diameter


def radiation_htc(T_surface, T_surroundings, emissivity):
    """Linearised grey-body radiation to large surroundings, W/m2K."""
    ts = np.asarray(T_surface, dtype=float) + p.KELVIN
    ta = T_surroundings + p.KELVIN
    return emissivity * p.SIGMA * (ts**2 + ta**2) * (ts + ta)


def external_htc(T_surface, T_air, outer_diameter, emissivity):
    return natural_convection_htc(T_surface, T_air, outer_diameter) + radiation_htc(T_surface, T_air, emissivity)
