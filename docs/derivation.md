# Derivation of the governing equations

## 1. Problem

A pipe of length $L$, bore radius $r_i$ and outer radius $r_o$ runs through a body
of air. At $t<0$ the water in the pipe, the pipe wall and the air are all at the
same temperature $T_0$. At $t=0$ a tap opens and water enters at temperature
$T_{in}(t)$ (a constant, a step, or any measured inlet trace) and volume flow
$Q(t)$. We want the outlet temperature $T_{out}(t)$, and from it the time and
volume run off before the outlet reaches a usable temperature.

Four bodies exchange heat:

```
 water (flows, axial x)  --h_i-->  pipe wall (r, x)  --h_o-->  air body (one node)  --UA-->  environment (optional)
```

## 2. Assumptions

1. **Water**: one-dimensional plug flow with uniform velocity $u=Q/(\pi r_i^2)$
   over the cross-section, and a bulk (mixing-cup) temperature $T_w(x,t)$.
   Axial conduction and dispersion in the water are neglected (the Péclet number
   $uL/\alpha_w$ is of order $10^6$). The water is incompressible, so a change of
   flow is felt along the whole pipe at once.
2. **Water properties**: $\rho_w c_w$ is held constant (evaluated at the mean of
   $T_0$ and the inlet temperature) so that enthalpy is transported exactly.
   Viscosity, conductivity and Prandtl number vary with temperature inside the
   heat transfer correlation, where they matter (viscosity halves between 20
   and 55 °C).
3. **Pipe wall**: homogeneous and axially symmetric, with constant $k_p$, $\rho_p$,
   $c_p$. Temperature $T_p(r,x,t)$ varies radially and axially; conduction in both
   directions is included.
4. **Water to wall**: a film coefficient $h_i$ from a steady forced-convection
   correlation evaluated with the local water temperature (Section 4).
5. **Wall to air**: natural convection plus linearised radiation, $h_o$, with
   the radiating surroundings taken to be at the air temperature.
6. **Air**: one well mixed body of volume $V_a$ at a single temperature $T_a(t)$
   that rises as heat arrives from the pipe. Optionally it loses heat to a fixed
   environment at $T_{env}$ through a conductance $UA_{env}$ (zero by default).
   With $V_a\to\infty$ the air stays at $T_0$.

## 3. Governing equations

**Water** (energy balance on a slice $dx$ moving with the flow):

$$
\rho_w c_w A_i\left(\frac{\partial T_w}{\partial t}+u\frac{\partial T_w}{\partial x}\right)
= h_i\,2\pi r_i\,\big(T_p(r_i,x,t)-T_w\big)
$$

with $A_i=\pi r_i^2$, $T_w(0,t)=T_{in}(t)$ and $T_w(x,0)=T_0$.

**Wall** (transient conduction in an axisymmetric annulus):

$$
\rho_p c_p\frac{\partial T_p}{\partial t}
=\frac{1}{r}\frac{\partial}{\partial r}\left(k_p r\frac{\partial T_p}{\partial r}\right)
+k_p\frac{\partial^2 T_p}{\partial x^2},\qquad r_i<r<r_o
$$

with convective boundary conditions on both faces

$$
-k_p\frac{\partial T_p}{\partial r}\Big|_{r_i}=h_i\big(T_w-T_p(r_i)\big),\qquad
-k_p\frac{\partial T_p}{\partial r}\Big|_{r_o}=h_o\big(T_p(r_o)-T_a\big),
$$

insulated ends ($\partial T_p/\partial x=0$ at $x=0,L$) and $T_p(r,x,0)=T_0$.

**Air** (lumped):

$$
\rho_a c_a V_a\frac{dT_a}{dt}=\int_0^L h_o\,2\pi r_o\big(T_p(r_o,x,t)-T_a\big)\,dx-UA_{env}\big(T_a-T_{env}\big),
\qquad T_a(0)=T_0 .
$$

**Energy conservation.** Adding the three equations and integrating over time,

$$
\int_0^t \rho_w c_w Q\,(T_{in}-T_{out})\,dt' = \Delta E_{water}+\Delta E_{wall}+\Delta E_{air}+\int_0^t UA_{env}(T_a-T_{env})\,dt' ,
$$

which the numerical scheme satisfies to round-off (checked in the tests).

### What controls the answer

Non-dimensionalising shows three groups do most of the work:

* **Heat capacity ratio** $\sigma = \rho_p c_p A_p / (\rho_w c_w A_i)$, the wall's
  heat capacity per metre relative to the water's. If the wall were heated
  instantly and with no losses, the hot front would travel at $u/(1+\sigma)$ and
  arrive at $(1+\sigma)L/u$. For 10 mm copper $\sigma\approx0.24$; for PE-X
  10 × 1.5 $\sigma\approx0.5$.
* **Number of transfer units** $NTU = h_i\,2\pi r_i L/(\rho_w c_w Q)$: how
  completely the water gives its heat to the wall in one pass. It is large (tens)
  for these pipes, so the front is not delayed by lack of contact.
* **Wall Biot number** $Bi = h_i (r_o-r_i)/k_p$ and the wall Fourier number
  $k_p t/(\rho_p c_p (r_o-r_i)^2)$. For copper $Bi\sim0.02$: the wall is
  isothermal through its thickness and behaves as a lumped heat capacity, so the
  outlet climbs steadily once the front arrives. For PE-X $Bi\sim10$–$40$ and the
  wall conducts slowly: only a thin inner skin heats while the water passes, so
  warm water arrives soon after plug-flow time but the last few degrees take much
  longer. That is why PE-X beats copper to 40 °C but loses at 50 °C at low flow.

External losses ($h_o\approx 6$–$10$ W/m²K) are small during a draw lasting
seconds; they set the steady outlet temperature and the cooling between draws.

## 4. Heat transfer coefficients

**Inside** (`deadleg/correlations.py`): $Re=uD_i/\nu$, $Nu=h_iD_i/k_w$.

* $Re\ge10^4$: Gnielinski,
  $Nu=\dfrac{(f/8)(Re-1000)Pr}{1+12.7\sqrt{f/8}\,(Pr^{2/3}-1)}$,
  $f=(0.790\ln Re-1.64)^{-2}$.
* $Re\le2300$: $Nu=3.66$ (fully developed laminar, uniform wall temperature).
* In between: linear interpolation in $Re$ between the two (VDI Heat Atlas G1).

At 1–6 l/min in 7–9 mm bores, $Re$ is roughly 2500–35000, so the flow is
transitional at the low end and turbulent above about 2 l/min.

**Outside**: Churchill and Chu for a horizontal cylinder,
$Nu_D=\left\{0.60+\dfrac{0.387\,Ra_D^{1/6}}{[1+(0.559/Pr)^{9/16}]^{8/27}}\right\}^2$,
with air properties at the film temperature, plus radiation
$h_{rad}=\varepsilon\sigma(T_s^2+T_a^2)(T_s+T_a)$ (kelvin). Emissivity is 0.1 for
tarnished copper and 0.9 for plastics. Either coefficient can be overridden with a
fixed value (`h_inner`, `h_outer`) for sensitivity studies.

## 5. Numerical method (`deadleg/model.py`)

Finite volumes: $N_x$ axial cells of length $\Delta x$; in each, one water node
and $N_r$ wall shells of equal thickness; plus one air node. Each time step is
split into three operators (Lie splitting):

1. **Radial exchange**, backward Euler. Per axial cell the water node and
   the wall shells form a tridiagonal system. The conductances between nodes are
   series resistances, e.g. water to first shell
   $G=\big[1/(h_i2\pi r_i)+\ln(r_1/r_i)/(2\pi k_p)\big]^{-1}$, shell to shell
   $2\pi k_p/\ln(r_{j+1}/r_j)$. The outermost shell is coupled to the air node,
   which couples every cell. The solution is linear in the new air temperature,
   $T=X_0+X_1T_a^{n+1}$, so two tridiagonal solves per cell followed by the scalar
   air balance give the fully implicit answer without iteration.
2. **Axial wall conduction**, backward Euler (one banded solve per step).
3. **Advection**: while water flows the time step is $\Delta t=\Delta x/u$ (Courant
   number exactly 1), so advection is an exact shift by one cell and the inlet
   value enters cell 1. There is no numerical diffusion of the front; any
   smearing in the results is physical. Zero-flow periods use a fixed $\Delta t$.

The scheme conserves energy exactly (the fluxes between nodes cancel pairwise and
advection moves whole cells of water). It is first-order accurate in
$\Delta x$; with the default 200 cells the outlet temperature is within about 1 %
of the analytical solution below.

## 6. Verification (`tests/test_model.py`)

* **No wall heat capacity** → the outlet is a pure step at the plug-flow time
  $V/Q$.
* **Anzelius–Schumann solution.** With a thin, perfectly conducting wall, no axial
  conduction and no external losses, the problem has the classical closed form
  ($\xi=h_iPx/(\dot m c_w)$, $\eta=h_iP(t-x/u)/C_{wall}$):
  $\theta_w=e^{-\xi}\left[e^{-\eta}I_0(2\sqrt{\xi\eta})+\int_0^\eta e^{-s}I_0(2\sqrt{\xi s})\,ds\right]$.
  The model converges to it at first order (maximum error 0.7 % at 200 cells,
  0.18 % at 800).
* **Steady state with losses** to air at fixed temperature matches
  $T_{out}=T_a+(T_{in}-T_a)\exp(-UA'L/\dot mc_w)$ to 0.02 K.
* **Energy balance** closes to $10^{-10}$ with every term active, including a
  stagnant period and a time-varying inlet.

## 7. Limitations and possible extensions

* Plug flow. Below $Re\approx2300$ (well under 1 l/min in these bores, or cold
  water at around 1 l/min) the parabolic velocity profile brings the first
  warm water out at about half the plug-flow time and smears the front.
* Steady-state $h_i$ applied to a strongly transient wall; the entrance region
  and the moving thermal front both raise the true coefficient a little.
* A homogeneous wall. Multilayer pipe (PE-RT/Al/PE-RT) is represented by
  volume-averaged properties; the code's shell structure would accept per-layer
  properties if that becomes worth doing.
* Radiation to surroundings at the air temperature; fittings, clips and
  thermal mass of the surrounding structure are not modelled.
