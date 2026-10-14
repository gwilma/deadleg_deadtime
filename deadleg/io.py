"""Scenario files, result export and comparison with measured outlet traces.

A scenario file is JSON, for example::

    {
      "pipe": {"preset": "copper_10x0.6"},
      "length_m": 5,
      "flow_l_per_min": 3,
      "duration_s": 60,
      "T_initial_C": 20,
      "T_inlet_C": 55
    }

``pipe`` may instead be ``{"outer_diameter_mm": 12, "wall_mm": 1.6, "material": "mlcp"}``,
optionally with a ``"material_properties"`` object (conductivity, density,
specific_heat, emissivity) to define a new material.
``flow_schedule`` (a list of ``[duration_s, l_per_min]``) replaces
``flow_l_per_min`` and ``duration_s``. ``T_inlet_C`` may be a number or
``{"times_s": [...], "temps_C": [...]}``, e.g. a measured heater outlet trace.
``air_volume_m3`` may be a number or ``"fixed"`` for an air body held at
``T_initial_C``.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

from .model import Result, Scenario
from .pipes import PRESETS, Pipe, make_pipe
from .properties import Material


def pipe_from_dict(d: dict) -> Pipe:
    if "preset" in d:
        return PRESETS[d["preset"]]
    material = d.get("material", "copper")
    if "material_properties" in d:
        mp = d["material_properties"]
        material = Material(
            name=mp.get("name", str(material)),
            conductivity=mp["conductivity"],
            density=mp["density"],
            specific_heat=mp["specific_heat"],
            emissivity=mp.get("emissivity", 0.9),
        )
    return make_pipe(d["outer_diameter_mm"], d["wall_mm"], material, d.get("name", ""))


def scenario_from_dict(d: dict) -> Scenario:
    if "flow_schedule" in d:
        flow, duration = [tuple(seg) for seg in d["flow_schedule"]], None
    else:
        flow, duration = d["flow_l_per_min"], d["duration_s"]
    t_in = d.get("T_inlet_C", 55.0)
    if isinstance(t_in, dict):
        t_in = (t_in["times_s"], t_in["temps_C"])
    air = d.get("air_volume_m3")
    if air == "fixed":
        air = math.inf
    numerics = d.get("numerics", {})
    return Scenario(
        pipe=pipe_from_dict(d["pipe"]),
        length=d["length_m"],
        flow=flow,
        duration=duration,
        T_initial=d.get("T_initial_C", 20.0),
        T_inlet=t_in,
        air_volume=air,
        air_loss_UA=d.get("air_loss_UA_W_per_K", 0.0),
        T_environment=d.get("T_environment_C"),
        h_inner=d.get("h_inner_W_per_m2K"),
        h_outer=d.get("h_outer_W_per_m2K"),
        n_axial=numerics.get("n_axial", 200),
        n_radial=numerics.get("n_radial", 6),
        wall_axial_conduction=numerics.get("wall_axial_conduction", True),
        dt_stagnant=numerics.get("dt_stagnant_s", 1.0),
    )


def load_scenario(path) -> Scenario:
    return scenario_from_dict(json.loads(Path(path).read_text()))


def write_result_csv(result: Result, path) -> None:
    cols = {
        "time_s": result.t,
        "flow_l_per_min": result.flow,
        "T_inlet_C": result.T_in,
        "T_outlet_C": result.T_out,
        "T_air_C": result.T_air,
        "T_wall_mean_C": result.T_wall_mean,
        "volume_delivered_l": result.volume_out,
        "energy_in_J": result.energy["in"],
        "energy_out_J": result.energy["out"],
        "energy_in_wall_J": result.energy["wall"],
        "energy_in_air_J": result.energy["air"],
    }
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in zip(*cols.values()):
            w.writerow([f"{v:.6g}" for v in row])


def summary(result: Result, thresholds=(40.0, 45.0, 50.0)) -> dict:
    sc = result.scenario
    out = {
        "pipe": sc.pipe.describe(),
        "length_m": sc.length,
        "water_volume_l": sc.water_volume * 1000,
        "wall_heat_capacity_J_per_K": sc.pipe.wall_heat_capacity_per_m * sc.length,
        "plug_flow_time_s": sc.plug_flow_time(),
        "final_outlet_C": float(result.T_out[-1]),
        "final_air_C": float(result.T_air[-1]),
        "energy_balance_error": result.energy_balance_error(),
    }
    for T in thresholds:
        out[f"time_to_{T:g}C_s"] = result.time_to_reach(T)
        out[f"volume_to_{T:g}C_l"] = result.volume_to_reach(T)
    return out


def load_trace(path, time_col: str = "time_s", temp_col: str | None = None):
    """Read a measured outlet trace (time, temperature) from CSV. With no
    ``temp_col`` the first column whose name starts with ``T`` or contains
    ``temp`` is used."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if temp_col is None:
        temp_col = next(c for c in rows[0] if c != time_col and (c.lower().startswith("t") or "temp" in c.lower()))
    t = np.array([float(r[time_col]) for r in rows])
    T = np.array([float(r[temp_col]) for r in rows])
    return t, T


def compare(result: Result, t_meas, T_meas, thresholds=(45.0,), sample_interval: float | None = None) -> dict:
    """Error statistics between the modelled and a measured outlet trace.

    With ``sample_interval`` set, threshold crossing times are also given as
    the first reading at or after the crossing on that sampling grid, which is
    how a manually read probe reports them.
    """
    t_meas = np.asarray(t_meas, dtype=float)
    T_meas = np.asarray(T_meas, dtype=float)
    model = result.outlet_at(t_meas)
    err = model - T_meas
    out = {"rmse_C": float(np.sqrt(np.mean(err**2))), "bias_C": float(np.mean(err)), "max_abs_C": float(np.max(np.abs(err)))}
    for T in thresholds:
        tm = result.time_to_reach(T)
        above = np.nonzero(T_meas >= T)[0]
        out[f"model_time_to_{T:g}C_s"] = tm
        out[f"measured_time_to_{T:g}C_s"] = float(t_meas[above[0]]) if above.size else math.nan
        if sample_interval:
            out[f"model_reading_to_{T:g}C_s"] = sample_interval * math.ceil(tm / sample_interval - 1e-9)
    return out
