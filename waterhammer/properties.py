"""Water and pipe-wall properties used by the water hammer model.

Everything here is indicative engineering data. Where a manufacturer's data
sheet gives a modulus for the actual pipe, pass it in instead.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

G = 9.81  # m/s2
P_ATM = 101_325.0  # Pa


def _interp(table: list[tuple[float, float]], x: float) -> float:
    """Linear interpolation in a sorted (x, y) table, clamped at the ends."""
    xs = [p[0] for p in table]
    if x <= xs[0]:
        return table[0][1]
    if x >= xs[-1]:
        return table[-1][1]
    i = bisect_left(xs, x)
    (x0, y0), (x1, y1) = table[i - 1], table[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# Pure water at about 1 atm. Density and vapour pressure: IAPWS-95 values as
# tabulated in the CRC Handbook. Isentropic bulk modulus derived from the IAPWS
# speed of sound (K = rho c^2); it peaks near 50 C, so hot water gives slightly
# *higher* surge than cold for the same velocity in a rigid pipe.
_WATER_DENSITY = [(0, 999.8), (10, 999.7), (20, 998.2), (30, 995.7), (40, 992.2), (50, 988.0),
                  (60, 983.2), (70, 977.8), (80, 971.8), (90, 965.3), (100, 958.4)]
_WATER_SOUND_SPEED = [(0, 1402.4), (10, 1447.3), (20, 1482.3), (30, 1509.2), (40, 1528.9), (50, 1542.6),
                      (60, 1551.0), (70, 1554.7), (80, 1554.4), (90, 1550.5), (100, 1543.4)]
_WATER_VAPOUR_PRESSURE = [(0, 611), (10, 1228), (20, 2339), (30, 4247), (40, 7384), (50, 12352),
                          (60, 19946), (70, 31201), (80, 47414), (90, 70182), (100, 101418)]


def water_density(t_c: float) -> float:
    """kg/m3."""
    return _interp(_WATER_DENSITY, t_c)


def water_bulk_modulus(t_c: float) -> float:
    """Isentropic bulk modulus, Pa."""
    c = _interp(_WATER_SOUND_SPEED, t_c)
    return water_density(t_c) * c * c


def water_vapour_pressure(t_c: float) -> float:
    """Absolute, Pa."""
    return _interp(_WATER_VAPOUR_PRESSURE, t_c)


def water_viscosity(t_c: float) -> float:
    """Dynamic viscosity, Pa s (Vogel equation fit, good to ~1% over 0-100 C)."""
    return 2.414e-5 * 10 ** (247.8 / (t_c + 273.15 - 140.0))


@dataclass(frozen=True)
class WallMaterial:
    """Elastic properties of a pipe wall for the wave speed calculation.

    `modulus` is a table of (temperature C, Young's modulus Pa). For plastics
    use the short-term (dynamic) modulus: a surge lasts milliseconds, so the
    creep modulus used for pressure rating is far too low.
    """

    name: str
    modulus: list[tuple[float, float]] = field(hash=False)
    poisson: float
    roughness: float  # m, for steady friction

    def young_modulus(self, t_c: float) -> float:
        return _interp(self.modulus, t_c)


# Copper: EN 1057 R250 (half-hard) tube; E ~ 110-130 GPa, little change below 100 C.
COPPER = WallMaterial("copper", [(0, 117e9), (100, 115e9)], 0.34, 1.5e-6)
STAINLESS = WallMaterial("stainless steel", [(0, 195e9), (100, 190e9)], 0.30, 1.5e-6)
# PE-X: short-term flexural/tensile modulus falls steeply with temperature.
# Values are mid-range of manufacturer data (roughly 0.6-0.9 GPa at 20 C).
# Treat as indicative; a lower modulus gives a lower wave speed, so a lower
# Joukowsky surge but a longer critical time 2L/a.
PEX = WallMaterial("PE-X", [(20, 0.70e9), (40, 0.55e9), (60, 0.42e9), (80, 0.32e9)], 0.46, 7e-6)
# Polybutylene (PB-1), common UK push-fit plastic pipe.
PB = WallMaterial("PB", [(20, 0.45e9), (40, 0.38e9), (60, 0.30e9), (80, 0.24e9)], 0.45, 7e-6)
# PE-RT (the liner and cover of multilayer composite pipe).
PERT = WallMaterial("PE-RT", [(20, 0.60e9), (40, 0.47e9), (60, 0.36e9), (80, 0.28e9)], 0.46, 7e-6)
ALUMINIUM = WallMaterial("aluminium", [(0, 70e9), (100, 68e9)], 0.33, 1.5e-6)

MATERIALS: dict[str, WallMaterial] = {
    "copper": COPPER,
    "stainless": STAINLESS,
    "pex": PEX,
    "pb": PB,
    "pert": PERT,
}


@dataclass(frozen=True)
class Pipe:
    """Circular pipe. `aluminium_mm` > 0 makes it a multilayer composite (MLCP)
    whose wall is `material` (PE-RT) with an aluminium layer of that thickness.
    """

    outer_diameter_mm: float
    wall_mm: float
    material: WallMaterial
    aluminium_mm: float = 0.0
    name: str = ""

    def __post_init__(self):
        if not 0 < 2 * self.wall_mm < self.outer_diameter_mm:
            raise ValueError("wall thickness must be positive and less than the outer radius")
        if not 0 <= self.aluminium_mm < self.wall_mm:
            raise ValueError("aluminium layer must be thinner than the wall")

    @property
    def inner_diameter(self) -> float:
        """m."""
        return (self.outer_diameter_mm - 2 * self.wall_mm) / 1e3

    @property
    def wall(self) -> float:
        """m."""
        return self.wall_mm / 1e3

    @property
    def bore_area(self) -> float:
        return math.pi * self.inner_diameter**2 / 4

    def hoop_modulus(self, t_c: float) -> float:
        """Effective Young's modulus of the wall in hoop (thickness-weighted
        for a composite; the hoop strain is common to all layers)."""
        e_base = self.material.young_modulus(t_c)
        if self.aluminium_mm == 0:
            return e_base
        frac = self.aluminium_mm / self.wall_mm
        return frac * ALUMINIUM.young_modulus(t_c) + (1 - frac) * e_base

    @property
    def poisson(self) -> float:
        return self.material.poisson

    def describe(self) -> str:
        kind = f"MLCP ({self.material.name}/Al {self.aluminium_mm:g} mm)" if self.aluminium_mm else self.material.name
        return (f"{self.name or kind}: OD {self.outer_diameter_mm:g} mm, wall {self.wall_mm:g} mm, "
                f"ID {self.inner_diameter * 1e3:.2f} mm")


# Same keys as the thermal model's presets where they overlap. Copper sizes
# from EN 1057; plastic walls are typical, check the data sheet.
PRESETS: dict[str, Pipe] = {
    "copper_10x0.6": Pipe(10, 0.6, COPPER, name="Copper 10 x 0.6"),
    "copper_12x0.6": Pipe(12, 0.6, COPPER, name="Copper 12 x 0.6"),
    "copper_15x0.7": Pipe(15, 0.7, COPPER, name="Copper 15 x 0.7"),
    "copper_22x0.9": Pipe(22, 0.9, COPPER, name="Copper 22 x 0.9"),
    "pex_10x1.5": Pipe(10, 1.5, PEX, name="PE-X 10 x 1.5"),
    "pex_12x2.0": Pipe(12, 2.0, PEX, name="PE-X 12 x 2.0"),
    "pex_16x2.2": Pipe(16, 2.2, PEX, name="PE-X 16 x 2.2"),
    "pb_10x1.7": Pipe(10, 1.7, PB, name="PB 10 x 1.7"),
    "pb_15x1.9": Pipe(15, 1.9, PB, name="PB 15 x 1.9"),
    # Ref 29 (FairHeat) Manufacturer A sizes; Al layer thickness assumed.
    "mlcp_12x1.6": Pipe(12, 1.6, PERT, aluminium_mm=0.2, name="MLCP 12 x 1.6"),
    "mlcp_16x2.0": Pipe(16, 2.0, PERT, aluminium_mm=0.2, name="MLCP 16 x 2.0"),
}
