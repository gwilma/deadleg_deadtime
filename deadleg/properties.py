"""Thermophysical properties of water, air and pipe materials.

Temperatures are in degrees Celsius unless stated otherwise. The water and air
fits are standard engineering correlations, accurate to about 1 % over
5-95 degC, which is ample given the uncertainty in the heat transfer
coefficients they feed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

G = 9.81  # m/s2
SIGMA = 5.670374419e-8  # Stefan-Boltzmann, W/m2K4
KELVIN = 273.15


# --------------------------------------------------------------------------
# Water (liquid, ~1-3 bar)
# --------------------------------------------------------------------------

def water_density(T):
    """Density, kg/m3 (Thiesen/Tilton fit)."""
    T = np.asarray(T, dtype=float)
    return 1000.0 * (1.0 - (T + 288.9414) / (508929.2 * (T + 68.12963)) * (T - 3.9863) ** 2)


def water_cp(T):
    """Specific heat capacity, J/kgK."""
    T = np.asarray(T, dtype=float)
    return 4217.4 - 3.720283 * T + 0.1412855 * T**2 - 2.654387e-3 * T**3 + 2.093236e-5 * T**4


def water_viscosity(T):
    """Dynamic viscosity, Pa s (Vogel-type fit)."""
    T = np.asarray(T, dtype=float)
    return 2.414e-5 * 10.0 ** (247.8 / (T + KELVIN - 140.0))


def water_conductivity(T):
    """Thermal conductivity, W/mK."""
    T = np.asarray(T, dtype=float)
    return 0.5706 + 1.756e-3 * T - 6.46e-6 * T**2


def water_prandtl(T):
    return water_viscosity(T) * water_cp(T) / water_conductivity(T)


# --------------------------------------------------------------------------
# Air (1 atm)
# --------------------------------------------------------------------------

def air_density(T):
    T = np.asarray(T, dtype=float)
    return 101325.0 / (287.05 * (T + KELVIN))


def air_cp(T):
    return 1006.0 + 0.0 * np.asarray(T, dtype=float)


def air_conductivity(T):
    T = np.asarray(T, dtype=float)
    return 0.02414 + 7.7e-5 * T


def air_kinematic_viscosity(T):
    T = np.asarray(T, dtype=float)
    return 1.327e-5 + 9.2e-8 * T


def air_prandtl(T):
    return 0.71 + 0.0 * np.asarray(T, dtype=float)


# --------------------------------------------------------------------------
# Pipe materials
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Material:
    """A homogeneous, isotropic pipe wall material."""

    name: str
    conductivity: float  # W/mK
    density: float  # kg/m3
    specific_heat: float  # J/kgK
    emissivity: float  # outer surface, for radiation to the surroundings

    @property
    def volumetric_heat_capacity(self) -> float:
        return self.density * self.specific_heat

    @property
    def diffusivity(self) -> float:
        return self.conductivity / self.volumetric_heat_capacity


# Phosphorus-deoxidised copper (Cu-DHP, EN 1057). Emissivity of a lightly
# tarnished tube; bright new copper is ~0.03-0.05, heavily oxidised ~0.6-0.8.
COPPER = Material("copper", conductivity=340.0, density=8940.0, specific_heat=385.0, emissivity=0.1)

# Cross-linked polyethylene. Published values: k 0.35-0.41 W/mK,
# rho 930-950 kg/m3, cp 1.9-2.3 kJ/kgK.
PEX = Material("PE-X", conductivity=0.38, density=940.0, specific_heat=2100.0, emissivity=0.9)

# Multilayer composite pipe (PE-RT / Al / PE-RT) represented as one
# homogeneous material, as the user's brief asks. Assumes ~12 % of the wall
# is aluminium by volume: rho and rho*cp are volume-weighted; k is close to
# the plastic's because the aluminium layer is thin and radial heat flow
# passes through the plastic layers in series.
MLCP = Material("MLCP (homogenised)", conductivity=0.45, density=1150.0, specific_heat=1750.0, emissivity=0.9)

MATERIALS = {"copper": COPPER, "pex": PEX, "mlcp": MLCP}
