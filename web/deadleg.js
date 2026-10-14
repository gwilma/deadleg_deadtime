/* deadleg.js: JavaScript port of the deadleg transient model (deadleg/model.py).
 *
 * Same physics and numerics as the Python package: plug-flow water advected
 * exactly one cell per step (dt = dx/u), implicit radial exchange water -> wall
 * shells -> air with the air node eliminated exactly, implicit axial conduction
 * along the wall, temperature-dependent water-side and air-side coefficients.
 * One constant flow and a constant inlet temperature per run.
 *
 * Works in the browser (window.Deadleg) and in Node (module.exports).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Deadleg = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const G = 9.81, SIGMA = 5.670374419e-8, KELVIN = 273.15;
  const DEFAULT_AIR_AREA = 0.01; // m2 of air cross-section per metre of pipe

  // ---- properties (deadleg/properties.py) -------------------------------
  const water = {
    density: T => 1000 * (1 - (T + 288.9414) / (508929.2 * (T + 68.12963)) * (T - 3.9863) ** 2),
    cp: T => 4217.4 - 3.720283 * T + 0.1412855 * T ** 2 - 2.654387e-3 * T ** 3 + 2.093236e-5 * T ** 4,
    viscosity: T => 2.414e-5 * Math.pow(10, 247.8 / (T + KELVIN - 140)),
    conductivity: T => 0.5706 + 1.756e-3 * T - 6.46e-6 * T ** 2,
  };
  water.prandtl = T => water.viscosity(T) * water.cp(T) / water.conductivity(T);
  const air = {
    density: T => 101325 / (287.05 * (T + KELVIN)),
    cp: () => 1006,
    conductivity: T => 0.02414 + 7.7e-5 * T,
    nu: T => 1.327e-5 + 9.2e-8 * T,
    prandtl: () => 0.71,
  };

  const MATERIALS = {
    copper: { name: "copper", k: 340, rho: 8940, cp: 385, eps: 0.1 },
    pex: { name: "PE-X", k: 0.38, rho: 940, cp: 2100, eps: 0.9 },
    mlcp: { name: "MLCP (homogenised)", k: 0.45, rho: 1150, cp: 1750, eps: 0.9 },
  };
  const PRESETS = {
    "copper_10x0.6": { name: "Copper 10 × 0.6", od: 0.010, wall: 0.0006, material: "copper" },
    "copper_12x0.6": { name: "Copper 12 × 0.6", od: 0.012, wall: 0.0006, material: "copper" },
    "pex_10x1.5": { name: "PE-X 10 × 1.5", od: 0.010, wall: 0.0015, material: "pex" },
    "pex_12x2.0": { name: "PE-X 12 × 2.0", od: 0.012, wall: 0.0020, material: "pex" },
    "mlcp_12x1.6": { name: "MLCP 12 × 1.6", od: 0.012, wall: 0.0016, material: "mlcp" },
  };

  // ---- correlations (deadleg/correlations.py) ---------------------------
  const RE_LAM = 2300, RE_TURB = 1e4, NU_LAM = 3.66;
  function gnielinski(re, pr) {
    const f = Math.pow(0.79 * Math.log(re) - 1.64, -2);
    return (f / 8) * (re - 1000) * pr / (1 + 12.7 * Math.sqrt(f / 8) * (Math.pow(pr, 2 / 3) - 1));
  }
  function internalHtc(Tw, u, D) {
    const re = Math.abs(u) * D / (water.viscosity(Tw) / water.density(Tw));
    const pr = water.prandtl(Tw);
    let nu;
    if (re >= RE_TURB) nu = gnielinski(re, pr);
    else if (re <= RE_LAM) nu = NU_LAM;
    else {
      const g = (re - RE_LAM) / (RE_TURB - RE_LAM);
      nu = (1 - g) * NU_LAM + g * gnielinski(RE_TURB, pr);
    }
    return nu * water.conductivity(Tw) / D;
  }
  function externalHtc(Ts, Ta, Do, eps) {
    const Tf = 0.5 * (Ts + Ta);
    const nu = air.nu(Tf), k = air.conductivity(Tf), pr = air.prandtl(Tf);
    const alpha = nu / pr, beta = 1 / (Tf + KELVIN);
    const ra = G * beta * Math.abs(Ts - Ta) * Do ** 3 / (nu * alpha);
    const nuD = Math.pow(0.6 + 0.387 * Math.pow(ra, 1 / 6) / Math.pow(1 + Math.pow(0.559 / pr, 9 / 16), 8 / 27), 2);
    const ts = Ts + KELVIN, ta = Ta + KELVIN;
    return nuD * k / Do + eps * SIGMA * (ts * ts + ta * ta) * (ts + ta);
  }

  function pipeGeometry(p) {
    const mat = typeof p.material === "string" ? MATERIALS[p.material] : p.material;
    const ro = p.od / 2, ri = ro - p.wall;
    return { ...p, mat, ri, ro, Ai: Math.PI * ri * ri, Ap: Math.PI * (ro * ro - ri * ri) };
  }

  /**
   * simulate(s): s = {pipe: preset key or {od, wall, material}, length, flow (l/min),
   *   duration (s), T0, Tin, airArea (m2 per m; Infinity = fixed air), airUA (W/K),
   *   Tenv, nx, nr, axial (bool), hInner, hOuter (optional overrides), maxSteps}
   */
  function simulate(s) {
    const P = pipeGeometry(typeof s.pipe === "string" ? PRESETS[s.pipe] : s.pipe);
    const mat = P.mat;
    const nx = s.nx ?? 200, nr = s.nr ?? 6, L = s.length;
    const T0 = s.T0 ?? 20, Tin = s.Tin ?? 55, Tenv = s.Tenv ?? T0;
    const dx = L / nx;
    const rhoCpW = water.density(0.5 * (T0 + Tin)) * water.cp(0.5 * (T0 + Tin));
    const Cw = rhoCpW * P.Ai;
    const u = s.flow / 60000 / P.Ai;
    const dt = dx / u;
    const steps = Math.min(s.maxSteps ?? 1e6, Math.max(1, Math.round(s.duration / dt)));

    // wall shells
    const rf = Array.from({ length: nr + 1 }, (_, j) => P.ri + (P.ro - P.ri) * j / nr);
    const rc = Array.from({ length: nr }, (_, j) => 0.5 * (rf[j] + rf[j + 1]));
    const shellArea = rc.map((_, j) => Math.PI * (rf[j + 1] ** 2 - rf[j] ** 2));
    const rhoCpP = mat.rho * mat.cp;
    const Cp = shellArea.map(a => rhoCpP * a);
    const k = mat.k;
    const Rin = Math.log(rc[0] / P.ri) / (2 * Math.PI * k);
    const Rout = Math.log(P.ro / rc[nr - 1]) / (2 * Math.PI * k);
    const Gs = [];
    for (let j = 0; j < nr - 1; j++) Gs.push(2 * Math.PI * k / Math.log(rc[j + 1] / rc[j]));

    const airArea = s.airArea ?? DEFAULT_AIR_AREA;
    const airFixed = !isFinite(airArea);
    const Ca = airFixed ? 0 : air.density(T0) * air.cp(T0) * airArea * L;
    const UA = s.airUA ?? 0;

    let Tw = new Float64Array(nx).fill(T0);
    const Tp = Array.from({ length: nr }, () => new Float64Array(nx).fill(T0)); // Tp[j][i]
    let Ta = T0;

    // axial conduction: constant matrix, pre-factorised (Thomas)
    const axial = (s.axial ?? true) && nx > 1;
    let axC = null, axM = null;
    if (axial) {
      const lam = (k / rhoCpP) * dt / (dx * dx);
      const bb = new Float64Array(nx).fill(1 + 2 * lam);
      bb[0] = bb[nx - 1] = 1 + lam;
      axC = new Float64Array(nx); axM = new Float64Array(nx);
      axM[0] = bb[0]; axC[0] = -lam / axM[0];
      for (let i = 1; i < nx; i++) { axM[i] = bb[i] + lam * axC[i - 1]; axC[i] = -lam / axM[i]; }
      axM.lam = lam;
    }

    const n = nr + 1;
    const a = new Float64Array(n), b = new Float64Array(n), c = new Float64Array(n);
    const cpr = new Float64Array(n), d0 = new Float64Array(n), d1 = new Float64Array(n);
    const X0 = Array.from({ length: n }, () => new Float64Array(nx));
    const X1 = Array.from({ length: n }, () => new Float64Array(nx));
    const GoArr = new Float64Array(nx);

    const out = { t: [], Tout: [], Tair: [], Twall: [], vol: [], Ein: [], Eout: [], Ewater: [], Ewall: [], Eair: [], Eenv: [] };
    let Ein = 0, Eout = 0, Qenv = 0, vol = 0, t = 0;
    const totalShell = shellArea.reduce((p, q) => p + q, 0);

    for (let step = 0; step < steps; step++) {
      let num = Ca / dt * Ta + UA * Tenv, den = Ca / dt + UA;
      for (let i = 0; i < nx; i++) {
        const hi = s.hInner ?? internalHtc(Tw[i], u, 2 * P.ri);
        const ho = s.hOuter ?? externalHtc(Tp[nr - 1][i], Ta, 2 * P.ro, mat.eps);
        const gi = hi * 2 * Math.PI * P.ri, Gi = gi / (1 + gi * Rin);
        const go = ho * 2 * Math.PI * P.ro, Go = go / (1 + go * Rout);
        GoArr[i] = Go;
        b[0] = Cw / dt + Gi; c[0] = -Gi;
        for (let j = 1; j < n; j++) {
          const gl = j === 1 ? Gi : Gs[j - 2];
          const gr = j === nr ? Go : Gs[j - 1];
          a[j] = -gl; b[j] = Cp[j - 1] / dt + gl + gr; c[j] = j === nr ? 0 : -Gs[j - 1];
        }
        d0[0] = Cw / dt * Tw[i]; d1[0] = 0;
        for (let j = 1; j < n; j++) { d0[j] = Cp[j - 1] / dt * Tp[j - 1][i]; d1[j] = 0; }
        d1[n - 1] = Go;
        // Thomas, two right-hand sides
        cpr[0] = c[0] / b[0]; d0[0] /= b[0]; d1[0] /= b[0];
        for (let j = 1; j < n; j++) {
          const m = b[j] - a[j] * cpr[j - 1];
          cpr[j] = c[j] / m;
          d0[j] = (d0[j] - a[j] * d0[j - 1]) / m;
          d1[j] = (d1[j] - a[j] * d1[j - 1]) / m;
        }
        X0[n - 1][i] = d0[n - 1]; X1[n - 1][i] = d1[n - 1];
        for (let j = n - 2; j >= 0; j--) {
          X0[j][i] = d0[j] - cpr[j] * X0[j + 1][i];
          X1[j][i] = d1[j] - cpr[j] * X1[j + 1][i];
        }
        num += dx * Go * X0[n - 1][i];
        den += dx * Go * (1 - X1[n - 1][i]);
      }
      const TaNew = airFixed ? Ta : num / den;
      for (let i = 0; i < nx; i++) {
        Tw[i] = X0[0][i] + X1[0][i] * TaNew;
        for (let j = 0; j < nr; j++) Tp[j][i] = X0[j + 1][i] + X1[j + 1][i] * TaNew;
      }
      if (airFixed) {
        // heat to a fixed-temperature air body leaves the system for good
        for (let i = 0; i < nx; i++) Qenv += dx * GoArr[i] * (Tp[nr - 1][i] - TaNew) * dt;
      } else Qenv += UA * (TaNew - Tenv) * dt;
      Ta = TaNew;

      if (axial) {
        const lam = axM.lam;
        for (let j = 0; j < nr; j++) {
          const T = Tp[j];
          T[0] = T[0] / axM[0];
          for (let i = 1; i < nx; i++) T[i] = (T[i] + lam * T[i - 1]) / axM[i];
          for (let i = nx - 2; i >= 0; i--) T[i] = T[i] - axC[i] * T[i + 1];
        }
      }

      const Tout = Tw[nx - 1];
      for (let i = nx - 1; i > 0; i--) Tw[i] = Tw[i - 1];
      Tw[0] = Tin;
      Ein += Cw * dx * (Tin - T0);
      Eout += Cw * dx * (Tout - T0);
      vol += P.Ai * dx * 1000;

      out.t.push(t + dt / 2);
      t += dt;
      out.Tout.push(Tout);
      out.Tair.push(Ta);
      let wsum = 0, ewall = 0;
      for (let j = 0; j < nr; j++) {
        let m = 0;
        for (let i = 0; i < nx; i++) { m += Tp[j][i]; ewall += (Tp[j][i] - T0) * Cp[j]; }
        wsum += (m / nx) * shellArea[j];
      }
      out.Twall.push(wsum / totalShell);
      out.vol.push(vol);
      let ew = 0;
      for (let i = 0; i < nx; i++) ew += Tw[i] - T0;
      out.Ein.push(Ein); out.Eout.push(Eout);
      out.Ewater.push(Cw * dx * ew); out.Ewall.push(dx * ewall); out.Eair.push(Ca * (Ta - T0)); out.Eenv.push(Qenv);
    }

    const plug = P.Ai * L / (s.flow / 60000);
    const result = {
      ...out, dt, steps, u, plugTime: plug, pipe: P, rhoCpW,
      sigma: rhoCpP * P.Ap / (rhoCpW * P.Ai),
      waterVolumeL: P.Ai * L * 1000,
      wallProfile: rc.map((r, j) => ({ depth: r - P.ri, T: Array.from(Tp[j]) })),
      energyBalanceError() {
        const last = this.t.length - 1;
        const stored = this.Ewater[last] + this.Ewall[last] + this.Eair[last];
        return (this.Ein[last] - this.Eout[last] - stored - this.Eenv[last]) / Math.max(Math.abs(this.Ein[last]), 1e-12);
      },
      timeToReach(T) { return firstCrossing(this.t, this.Tout, T); },
      volumeToReach(T) {
        const tt = this.timeToReach(T);
        return isNaN(tt) ? NaN : (tt * s.flow / 60);
      },
    };
    return result;
  }

  function firstCrossing(t, y, level) {
    for (let k = 0; k < y.length; k++) {
      if (y[k] >= level) {
        if (k === 0) return t[0];
        return t[k - 1] + (level - y[k - 1]) * (t[k] - t[k - 1]) / (y[k] - y[k - 1]);
      }
    }
    return NaN;
  }

  return { simulate, PRESETS, MATERIALS, water, air, internalHtc, externalHtc, pipeGeometry, DEFAULT_AIR_AREA };
});
