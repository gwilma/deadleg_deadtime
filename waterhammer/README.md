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
