"""Pipe geometry and a few common domestic hot water sizes."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .properties import COPPER, MATERIALS, MLCP, PEX, Material


@dataclass(frozen=True)
class Pipe:
    """A circular pipe with a homogeneous, axially symmetric wall."""

    outer_diameter: float  # m
    wall_thickness: float  # m
    material: Material
    name: str = ""

    def __post_init__(self):
        if not 0 < 2 * self.wall_thickness < self.outer_diameter:
            raise ValueError("wall thickness must be positive and less than the outer radius")

    @property
    def inner_diameter(self) -> float:
        return self.outer_diameter - 2 * self.wall_thickness

    @property
    def inner_radius(self) -> float:
        return self.inner_diameter / 2

    @property
    def outer_radius(self) -> float:
        return self.outer_diameter / 2

    @property
    def bore_area(self) -> float:
        return math.pi * self.inner_radius**2

    @property
    def wall_area(self) -> float:
        return math.pi * (self.outer_radius**2 - self.inner_radius**2)

    @property
    def water_volume_per_m(self) -> float:
        """m3 of water per metre of pipe."""
        return self.bore_area

    @property
    def wall_mass_per_m(self) -> float:
        return self.wall_area * self.material.density

    @property
    def wall_heat_capacity_per_m(self) -> float:
        """J/K per metre of pipe wall."""
        return self.wall_area * self.material.volumetric_heat_capacity

    def describe(self) -> str:
        return (
            f"{self.name or self.material.name}: OD {self.outer_diameter * 1e3:.1f} mm, "
            f"wall {self.wall_thickness * 1e3:.2f} mm, ID {self.inner_diameter * 1e3:.2f} mm"
        )


def make_pipe(outer_diameter_mm: float, wall_mm: float, material: str | Material, name: str = "") -> Pipe:
    mat = MATERIALS[material.lower()] if isinstance(material, str) else material
    return Pipe(outer_diameter_mm / 1e3, wall_mm / 1e3, mat, name)


# Copper: EN 1057 / BS 2871 Table X sizes. PE-X: typical 10 and 12 mm
# barrier pipe; check the manufacturer's data sheet for the exact wall.
PRESETS: dict[str, Pipe] = {
    "copper_10x0.6": Pipe(0.010, 0.0006, COPPER, "Copper 10 x 0.6"),
    "copper_12x0.6": Pipe(0.012, 0.0006, COPPER, "Copper 12 x 0.6"),
    "pex_10x1.5": Pipe(0.010, 0.0015, PEX, "PE-X 10 x 1.5"),
    "pex_12x2.0": Pipe(0.012, 0.0020, PEX, "PE-X 12 x 2.0"),
    "mlcp_12x1.6": Pipe(0.012, 0.0016, MLCP, "MLCP 12 x 1.6"),
}
