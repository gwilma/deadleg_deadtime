# waterhammer

Screens a domestic hot water pipe for water hammer: given the pipe, run length, flow, rest pressure,
temperature and how fast the valve closes, it calculates the surge and says whether mitigation (an
arrester, a slower valve, lower velocity) is required against a 2 bar limit. Standard library only.
Method, limits and sources: [`docs/water_hammer.md`](../docs/water_hammer.md).

```bash
python -m waterhammer --pipe copper_10x0.6 --length 8 --flow 6 --valve solenoid
python -m waterhammer --od 12 --wall 2 --material pex --length 10 --flow 4 --closure-time 0.05 --json
```

```python
from waterhammer import assess_simple, Inputs, Limits, PRESETS, assess

r = assess_simple("pex_12x2.0", length_m=8, flow_l_min=6, valve="single_lever_mixer")
r.mitigation_required, r.design_surge_bar, r.recommendations

r = assess(Inputs(PRESETS["copper_12x0.6"], 5, 4, static_pressure_bar=3.5, temperature_c=60,
                  closure_time_s=0.05, limits=Limits(pressure_rating_bar=6)))
```

Valve types: `solenoid` (0.02 s), `single_lever_mixer` (0.1 s), `quarter_turn` (0.15 s),
`thermostatic_shower` (0.3 s), `screw_down` (1.0 s), or any closure time in seconds.
Length is measured from the valve to the nearest reflection point (manifold, larger main, cylinder,
expansion vessel).

Tests: `python -m pytest tests/test_waterhammer.py`. Screening table: `python examples/waterhammer_sweep.py`.

## Excel version

[`excel/waterhammer.xlsx`](../excel/waterhammer.xlsx) implements the same model as live formulas
(no macros): inputs and results on the `Model` sheet, intermediate values on `Calc`, the
method-of-characteristics simulation on `MOC` (10 reaches, up to 6000 time steps) and property
tables on `Data`. Rebuild it with `python excel/build_workbook.py` (needs openpyxl; LibreOffice, if
installed, stores calculated values in the file). `python excel/check_workbook.py` recalculates it
with LibreOffice for five cases and compares every quantity with the Python model; they agree to
about 1e-13. Two differences from the Python defaults: the workbook's simulation uses 10 reaches
(Python uses 20, which moves the MOC surge by a few per cent), and its "closure time meeting the
limit" is the Michaud estimate rather than the bisection against the simulation.

## Physics note

[`docs/physics/water_hammer_physics.pdf`](../docs/physics/water_hammer_physics.pdf) (Tufte-LaTeX)
derives every equation the model uses and works an example. Rebuild the figures with
`python docs/physics/figures.py` (Altair + vl-convert) and the PDF with `latexmk -pdf` in `docs/physics`.
