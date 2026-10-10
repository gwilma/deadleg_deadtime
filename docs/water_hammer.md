# Water hammer in domestic hot water pipes: method, limits and sources

This note goes with the `waterhammer` package, its Excel twin `excel/waterhammer.xlsx`, and the full derivation in `docs/physics/water_hammer_physics.pdf`. It explains what water hammer is, when a domestic hot
water (DHW) installation needs protection against it, how the model decides, and where each threshold
comes from. The default context is a dwelling DHW branch: 1 to 6 l/min, 10 to 15 mm OD copper, PE-X,
PB or multilayer (MLCP) pipe, 2.5 to 4 bar rest pressure, 50 to 60 °C water.

## 1. The physics

When a valve stops a moving column of water, the water's momentum is converted into a pressure wave
that travels back up the pipe at the wave speed *a*, reflects at the nearest point of near-constant
pressure (a larger main, a manifold, a cylinder, an expansion vessel or accumulator) and returns as a
pressure drop. The round trip takes the **critical time** *T*<sub>c</sub> = 2*L*/*a*.

**Wave speed** (Korteweg; thick-wall form from Wylie & Streeter 1993, eq. 2.21):

    a = sqrt( (K/ρ) / (1 + ψ K D / (E e)) )

*K* and ρ are the water's bulk modulus and density, *D* the bore, *e* the wall thickness, *E* the
wall's Young's modulus and ψ a restraint factor (≈1; the model uses the thick-wall expressions for a
pipe anchored throughout, free to move axially, or anchored upstream only). Typical results at 55 °C:

| Pipe | a (m/s) |
|---|---|
| Copper 10 x 0.6 / 15 x 0.7 | ≈ 1350 / 1310 |
| MLCP 12 x 1.6 (0.2 mm Al, assumed) | ≈ 935 |
| PE-X 12 x 2.0 | ≈ 285 |

Plastic pipe has a much lower wave speed, so a lower instantaneous surge, but its critical time is
four to five times longer, so a given valve is more likely to count as "rapid".

**Surge magnitude.**

* Closure faster than 2*L*/*a* (Joukowsky 1898): Δ*p* = ρ *a* Δ*v*. In copper, roughly **13 bar per
  m/s**; in PE-X roughly 3 bar per m/s.
* Slower closure (Michaud): Δ*p* ≈ 2ρ*L*Δ*v* / *t*<sub>close</sub>. This no longer depends on the
  pipe material, only on run length, velocity and closure time.

Real valves choke most of the flow in the last part of their stroke, so the model also runs a
method-of-characteristics (MOC) simulation (Wylie & Streeter ch. 3) of a constant-pressure source,
the pipe with steady friction, and an orifice valve whose open area falls linearly to zero. The
**design surge** is the larger of the closed form and the MOC result. The tests check the MOC against
Joukowsky for instant closure (within 3 %) and against rigid-column theory for slow closure (within 5 %).

**Column separation.** If the pressure drop that follows the surge takes the pipe below vapour pressure,
the column breaks and its collapse can exceed the Joukowsky value. At 3 bar rest pressure this happens
once the surge exceeds roughly 4 bar, so it is flagged as a failure.

## 2. When mitigation is needed: the limits used

| Check | Default | Governs? | Source |
|---|---|---|---|
| Pressure rise above rest pressure caused by valve operation | **≤ 2 bar (0.2 MPa)** | Yes | Technical rules for drinking water installations (TRWI): DIN EN 806-2 together with DIN 1988-200; quoted in VDI 6006:2017 §4.3 "Normative requirements" ("must not exceed 0.2 MPa (2 bar)"). The same 2 bar rise was already required by DIN 1988 (1988). |
| Peak pressure (rest + surge) | ≤ pressure rating of pipe and fittings at the DHW temperature (default 10 bar; set yours) | Yes | Water Supply (Water Fittings) Regulations 1999, Sch. 2 para 3(b) (fittings must resist "pressure surges"), para 5 and para 12 (fittings and systems to withstand 1.5 × the maximum design operating pressure). |
| Minimum pressure | > vapour pressure | Yes | Physics (column separation); Wylie & Streeter ch. 8. |
| Flow velocity | ≤ 1.5 m/s for hot water | Advisory only | Uniform Plumbing Code 610.12 and US copper-tube guidance: 8 ft/s (2.4 m/s) cold, 5 ft/s (1.5 m/s) hot below 60 °C, 2 ft/s above 60 °C. DIN 1988-300 allows up to 2 m/s in single connection pipes. |

If any governing check fails the model returns **mitigation required**. Every limit can be changed via
`Limits(...)` or the CLI flags (`--max-surge`, `--rating`).

**US practice for comparison.** The International Plumbing Code (604.9) and Uniform Plumbing Code
(609.10) require a water hammer arrester wherever quick-closing valves are used, regardless of a
calculation, with arresters to ASSE 1010 and sized and placed per PDI-WH 201. UK and European
practice (EN 806, BS 8558, VDI 6006) is performance-based: keep the rise within 2 bar by velocity,
closure time or a surge damper. This model implements the performance test, and the US rule is the
safe fallback where no calculation is done.

## 3. Valve closure times

VDI 6006 identifies the valves that cause surges in dwellings as fast-closing shut-off and draw-off
valves: **solenoid valves, ball valves and single-lever mixer taps**. The defaults below are
engineering estimates of the *effective* closure time (the period over which the valve actually
throttles the flow, usually the last fraction of the stroke). They are not taken from a standard, so
measure or ask the manufacturer when a result is marginal.

| Valve | Default (s) | Typical sources in a dwelling |
|---|---|---|
| `solenoid` | 0.02 | Washing machine, dishwasher, sensor tap, electric/digital shower, some WC valves |
| `single_lever_mixer` | 0.10 | Kitchen/basin mixer lever pushed shut |
| `quarter_turn` | 0.15 | Ceramic-disc quarter-turn tap, ball valve |
| `thermostatic_shower` | 0.30 | Bar/thermostatic mixer |
| `screw_down` | 1.0 | Traditional washer (compression) tap |

## 4. Which length to use

*L* is the distance from the closing valve back to the **nearest reflection point**: a point where the
pressure is held nearly constant. For a dwelling that is usually the HIU or combi DHW outlet manifold,
the branch tee on a much larger pipe (bore area at least about four times larger), an unvented cylinder,
or an expansion vessel / accumulator on the hot side. When in doubt use the whole run from the hot water
source, which is conservative.

## 5. Screening results for the project defaults

Longest *L* (m) that needs **no** mitigation at 3 bar rest pressure, 55 °C, 2 bar limit (grid 1, 2, 3, 5, 8,
10, 15, 20, 25, 30 m; "0" means even 1 m fails). Full table: `results/waterhammer/screening.csv`;
regenerate with `python examples/waterhammer_sweep.py`.

| pipe | valve | 1 l/min | 2 l/min | 3 l/min | 4 l/min | 5 l/min | 6 l/min |
|---|---|---|---|---|---|---|---|
| copper_10x0.6 | solenoid | 5 | 3 | 2 | 1 | 1 | 1 |
| copper_10x0.6 | single_lever_mixer | >=30 | 15 | 10 | 8 | 5 | 5 |
| copper_10x0.6 | quarter_turn | >=30 | 25 | 15 | 10 | 10 | 8 |
| copper_10x0.6 | screw_down | >=30 | >=30 | >=30 | >=30 | >=30 | >=30 |
| copper_12x0.6 | solenoid | 10 | 5 | 3 | 2 | 2 | 1 |
| copper_12x0.6 | single_lever_mixer | >=30 | 25 | 15 | 10 | 10 | 8 |
| copper_12x0.6 | quarter_turn | >=30 | >=30 | 25 | 20 | 15 | 10 |
| copper_12x0.6 | screw_down | >=30 | >=30 | >=30 | >=30 | >=30 | >=30 |
| copper_15x0.7 | solenoid | >=30 | 8 | 5 | 3 | 3 | 2 |
| copper_15x0.7 | single_lever_mixer | >=30 | >=30 | 25 | 20 | 15 | 10 |
| copper_15x0.7 | quarter_turn | >=30 | >=30 | >=30 | >=30 | 25 | 20 |
| copper_15x0.7 | screw_down | >=30 | >=30 | >=30 | >=30 | >=30 | >=30 |
| pex_10x1.5 | solenoid | >=30 | 2 | 1 | 1 | 0 | 0 |
| pex_10x1.5 | single_lever_mixer | >=30 | 10 | 5 | 5 | 3 | 3 |
| pex_10x1.5 | quarter_turn | >=30 | 15 | 10 | 8 | 5 | 5 |
| pex_10x1.5 | screw_down | >=30 | >=30 | >=30 | >=30 | 25 | 20 |
| pex_12x2.0 | solenoid | >=30 | >=30 | 2 | 1 | 1 | 1 |
| pex_12x2.0 | single_lever_mixer | >=30 | >=30 | 10 | 5 | 5 | 5 |
| pex_12x2.0 | quarter_turn | >=30 | >=30 | 15 | 10 | 8 | 5 |
| pex_12x2.0 | screw_down | >=30 | >=30 | >=30 | >=30 | >=30 | >=30 |
| mlcp_12x1.6 | solenoid | 5 | 3 | 2 | 1 | 1 | 1 |
| mlcp_12x1.6 | single_lever_mixer | >=30 | 15 | 10 | 8 | 5 | 5 |
| mlcp_12x1.6 | quarter_turn | >=30 | 25 | 15 | 10 | 10 | 8 |
| mlcp_12x1.6 | screw_down | >=30 | >=30 | >=30 | >=30 | >=30 | >=30 |

What the table says:

* **Solenoid valves on small-bore pipe almost always exceed 2 bar** above about 2 to 3 l/min, at any
  practical length. Appliances on a DHW feed (dishwashers, some washing machines, digital showers)
  are the main case for an arrester, fitted at the appliance valve.
* **Lever mixers and quarter-turn taps** are fine on short runs but fail on the long, small-bore runs that
  the dead-leg work encourages (for example 10 mm copper at 6 l/min fails beyond about 5 m).
* **Reducing the bore to cut dead-leg volume raises velocity and therefore surge.** The two goals pull
  against each other, and this model is the check on the trade-off.
* In the slow-closure regime the result depends only on *L*, velocity and closure time, not on the
  pipe material, which is why MLCP 12 x 1.6 matches copper 10 x 0.6 (both 8.8 mm bore).
* PE-X's low wave speed caps the surge: when ρ*a**v* ≤ 2 bar (for example PE-X 12 x 2.0 at
  2 l/min) no valve and no length can exceed the limit.

## 6. Mitigation options the model reports

When mitigation is required the model gives four options, in this order:

1. **Water hammer arrester / surge damper** at the quick-closing valve. It reports an indicative gas
   precharge volume from the classic air-chamber energy balance: ½ρ*AL**v*² = *p*₀*V*₀[(*p*₁/*p*₀)^((n−1)/n) − 1]/(n−1),
   with *p*₁ = rest pressure + allowed rise, absolute pressures, and n = 1.4 by default (adiabatic,
   which is conservative). Use the manufacturer's sizing (PDI-WH 201 sizes A to F in US practice) for selection.
2. **A slower-closing valve**: the shortest effective closure time that meets the limit, worked out
   with the same "larger of closed form and MOC" rule.
3. **Lower velocity**: the flow (or larger bore) at which even instantaneous closure stays within the
   limit, Δ*v* ≤ Δ*p*<sub>allow</sub>/(ρ*a*).
4. **A shorter run to a reflection point, or lower rest pressure** (a PRV) when the peak-pressure check fails.

## 7. Limitations

* Single pipe, single valve; no branches, no fittings' local losses, no unsteady friction. Branched
  networks need a full transient analysis.
* Plastic moduli are indicative short-term values that fall steeply with temperature
  (`waterhammer/properties.py`); MLCP is treated as a thickness-weighted PE-RT/aluminium wall with an
  assumed 0.2 mm Al layer. Use data-sheet values where available.
* Column separation is detected but not simulated.
* Air trapped in the pipe, flexible hoses and appliance hose connections all soften real surges, so
  results lean conservative.

## 8. Sources

Checked online for this work (October 2026):

* Water Supply (Water Fittings) Regulations 1999 (SI 1999/1148), Schedule 2, paras 3, 5, 12.
  <https://www.legislation.gov.uk/uksi/1999/1148/schedule/2>
* VDI 6006:2017-11, *Pressure surges in drinking-water installations: causes, noise emission and
  prevention*. Scope: <https://www.vdi.de/en/home/vdi-standards/details/vdi-6006-pressure-surges-in-drinking-water-installations-causes-noise-emission-and-prevention>;
  contents and the 0.2 MPa limit: <https://m.vdi.de/fileadmin/pages/vdi_de/redakteure/richtlinien/inhaltsverzeichnisse/2681896.pdf>
* SBZ Monteur training sheet citing DIN 1988's 2 bar maximum pressure rise and 2.5 m/s for some fittings:
  <https://www.sbz-monteur.de/sites/default/files/sbzm_pdf/file_162310.pdf>
* Water Regs UK on EN 806 test pressure (MDP = 1.5 × maximum operating pressure):
  <https://www.waterregsuk.co.uk/topics/all-faqs/is-the-pressure-testing-specified-in-bs-en-806-acceptable/>
* Engineering ToolBox, velocities in copper pipe (2.4 / 1.5 / 0.6 m/s):
  <https://engineeringtoolbox.com/copper-pipes-water-velocities-d_1081.html>

Cited from standard texts and references without re-reading the clause here (check before quoting):

* BS EN 806-2:2005, *Specifications for installations inside buildings conveying water for human
  consumption. Design*, and BS 8558:2015 (UK complementary guidance). The exact clause number of the
  2 bar requirement in EN 806-2 was not checked against the standard.
* DIN 1988-200 and DIN 1988-300 (velocity limits, 2 m/s for connection pipes).
* International Plumbing Code 604.9; Uniform Plumbing Code 609.10 and 610.12; ASSE 1010; PDI-WH 201.
* Wylie, E.B. & Streeter, V.L. (1993) *Fluid Transients in Systems*, Prentice Hall (wave speed, MOC,
  column separation).
* Thorley, A.R.D. (2004) *Fluid Transients in Pipeline Systems*, 2nd ed., Professional Engineering Publishing.
* Joukowsky, N. (1898/1904) *On the hydraulic hammer in water supply pipes*, Proc. AWWA 24 (1904 translation).
* Water properties: IAPWS-95 (density, speed of sound, vapour pressure) via the CRC Handbook.
