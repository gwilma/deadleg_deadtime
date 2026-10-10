// Water hammer screening model: a line-for-line port of waterhammer/model.py.
// DATA (property tables, presets, valve times) is injected by web/build_page.py
// from waterhammer/properties.py, so Python, Excel and this page share one data set.
"use strict";
(function (root) {
  const DATA = /*DATA*/null;
  const G = 9.81, P_ATM = 101325;

  function interp(table, x) {
    if (x <= table[0][0]) return table[0][1];
    const n = table.length;
    if (x >= table[n - 1][0]) return table[n - 1][1];
    let i = 1;
    while (table[i][0] < x) i++;
    const [x0, y0] = table[i - 1], [x1, y1] = table[i];
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
  }
  const waterDensity = t => interp(DATA.water.density, t);
  const waterBulkModulus = t => { const c = interp(DATA.water.sound, t); return waterDensity(t) * c * c; };
  const waterVapourPressure = t => interp(DATA.water.vapour, t);
  const waterViscosity = t => 2.414e-5 * Math.pow(10, 247.8 / (t + 273.15 - 140.0));

  function makePipe(od, wall, material, al = 0, name = "") {
    if (!(wall > 0 && 2 * wall < od)) throw new Error("Wall thickness must be positive and less than the outside radius.");
    if (!(al >= 0 && al < wall)) throw new Error("The aluminium layer must be thinner than the wall.");
    const mat = DATA.materials[material];
    if (!mat) throw new Error("Unknown material " + material);
    const D = (od - 2 * wall) / 1e3;
    return { od, wall_mm: wall, al, material, mat, name, D, e: wall / 1e3, area: Math.PI * D * D / 4 };
  }
  function hoopModulus(p, t) {
    const base = interp(p.mat.modulus, t);
    if (p.al === 0) return base;
    const f = p.al / p.wall_mm;
    return f * interp(DATA.aluminium.modulus, t) + (1 - f) * base;
  }
  function restraintFactor(p, restraint) {
    const d = p.D, e = p.e, nu = p.mat.poisson;
    const thick = 2 * (e / d) * (1 + nu);
    if (restraint === "anchored") return thick + d * (1 - nu * nu) / (d + e);
    if (restraint === "expansion_joints") return thick + d / (d + e);
    if (restraint === "upstream_anchor") return thick + d * (1 - nu / 2) / (d + e);
    throw new Error("Unknown restraint " + restraint);
  }
  function waveSpeed(p, t, restraint = "anchored") {
    const k = waterBulkModulus(t), rho = waterDensity(t), E = hoopModulus(p, t);
    const psi = restraintFactor(p, restraint);
    return Math.sqrt((k / rho) / (1 + psi * k * p.D / (E * p.e)));
  }
  function frictionFactor(re, relRough) {
    if (re < 2300) return 64 / Math.max(re, 1e-9);
    return 0.25 / Math.pow(Math.log10(relRough / 3.7 + 5.74 / Math.pow(re, 0.9)), 2);
  }

  function simulateMoc(p, length, q0, pStatic, t, tClose, restraint = "anchored", reaches = 20, periodsAfter = 6, keepTrace = false) {
    const rho = waterDensity(t), a = waveSpeed(p, t, restraint);
    const area = p.area, d = p.D, v0 = q0 / area;
    const re = rho * v0 * d / waterViscosity(t);
    const f = frictionFactor(re, p.mat.roughness / d);
    const n = Math.max(reaches, 4), dx = length / n, dt = dx / a;
    const b = a / (G * area), r = f * dx / (2 * G * d * area * area);
    const hRes = pStatic / (rho * G);
    const hf = f * length / d * v0 * v0 / (2 * G);
    const hV0 = hRes - hf;
    if (hV0 <= 0) throw new Error("Friction uses up all the rest pressure: the pipe cannot deliver this flow.");
    let h = Array.from({ length: n + 1 }, (_, i) => hRes - hf * i / n);
    let qq = new Array(n + 1).fill(q0);
    const tEnd = tClose + periodsAfter * 2 * length / a;
    const steps = Math.ceil(tEnd / dt);
    let peak = hV0, minH = hV0;
    const times = keepTrace ? [0] : null, valveP = keepTrace ? [hV0 * rho * G] : null;
    for (let k = 1; k <= steps; k++) {
      const tt = k * dt;
      const tau = (tt >= tClose || tClose === 0) ? 0 : 1 - tt / tClose;
      const hn = h.slice(), qn = qq.slice();
      for (let i = 1; i < n; i++) {
        const cp = h[i - 1] + b * qq[i - 1] - r * qq[i - 1] * Math.abs(qq[i - 1]);
        const cm = h[i + 1] - b * qq[i + 1] + r * qq[i + 1] * Math.abs(qq[i + 1]);
        hn[i] = (cp + cm) / 2;
        qn[i] = (cp - cm) / (2 * b);
      }
      const cm0 = h[1] - b * qq[1] + r * qq[1] * Math.abs(qq[1]);
      hn[0] = hRes;
      qn[0] = (hRes - cm0) / b;
      const cp = h[n - 1] + b * qq[n - 1] - r * qq[n - 1] * Math.abs(qq[n - 1]);
      const kv = (tau * q0) * (tau * q0) / hV0;
      qn[n] = (kv === 0 || cp <= 0) ? 0 : (-kv * b + Math.sqrt((kv * b) * (kv * b) + 4 * kv * cp)) / 2;
      hn[n] = cp - b * qn[n];
      h = hn; qq = qn;
      if (h[n] > peak) peak = h[n];
      for (const x of h) if (x < minH) minH = x;
      if (keepTrace) { times.push(tt); valveP.push(h[n] * rho * G); }
    }
    return { peakGaugePa: peak * rho * G, minGaugePa: minH * rho * G, times, valveP };
  }

  function arresterVolume(rho, area, length, v, pStaticGauge, dpAllow, n = 1.4) {
    if (dpAllow <= 0) return Infinity;
    const ke = 0.5 * rho * area * length * v * v;
    const p0 = pStaticGauge + P_ATM, ratio = (p0 + dpAllow) / p0;
    const w = Math.abs(n - 1) < 1e-9 ? p0 * Math.log(ratio) : p0 * (Math.pow(ratio, (n - 1) / n) - 1) / (n - 1);
    return ke / w;
  }

  function closureTimeForLimit(inp, q, pStatic, dpAllow, guess) {
    const surge = tc => simulateMoc(inp.pipe, inp.length, q, pStatic, inp.temperature, tc, inp.restraint).peakGaugePa - pStatic;
    let lo = guess, hi = guess;
    while (surge(lo) <= dpAllow && lo > 1e-3) lo /= 2;
    while (surge(hi) > dpAllow) { hi *= 2; if (hi > 60) return Infinity; }
    for (let i = 0; i < 12; i++) {
      const mid = (lo + hi) / 2;
      if (surge(mid) > dpAllow) lo = mid; else hi = mid;
    }
    return hi;
  }

  // inp: {pipe, length (m), flow (l/min), pressure (bar g), temperature (C), closure (s),
  //       restraint, maxSurge (bar), rating (bar g), advisoryVelocity (m/s), gasIndex}
  function assess(inp) {
    const t = inp.temperature, rho = waterDensity(t), a = waveSpeed(inp.pipe, t, inp.restraint);
    const q = inp.flow / 60000, v = q / inp.pipe.area, L = inp.length;
    if (!(L > 0) || !(inp.flow > 0) || !(inp.closure >= 0)) throw new Error("Length and flow must be positive and the closure time zero or more.");
    const tCrit = 2 * L / a, pStatic = inp.pressure * 1e5, dpAllow = inp.maxSurge * 1e5;
    const dpJk = rho * a * v;
    const regime = inp.closure <= tCrit ? "rapid" : "slow";
    const dpCf = regime === "rapid" ? dpJk : 2 * rho * L * v / inp.closure;
    const sim = simulateMoc(inp.pipe, L, q, pStatic, t, inp.closure, inp.restraint, 20, 6, true);
    const mocSurge = sim.peakGaugePa - pStatic;
    const dpDesign = Math.max(dpCf, mocSurge);
    const peak = pStatic + dpDesign, minGauge = sim.minGaugePa;
    const pVapGauge = waterVapourPressure(t) - P_ATM;
    const checks = [
      { key: "surge", name: "Surge above rest pressure", value: dpDesign / 1e5, limit: inp.maxSurge, unit: "bar", passed: dpDesign <= dpAllow, governs: true },
      { key: "peak", name: "Peak pressure", value: peak / 1e5, limit: inp.rating, unit: "bar g", passed: peak <= inp.rating * 1e5, governs: true },
      { key: "min", name: "Lowest pressure", value: minGauge / 1e5, limit: pVapGauge / 1e5, unit: "bar g", passed: minGauge > pVapGauge, governs: true },
      { key: "vel", name: "Flow velocity", value: v, limit: inp.advisoryVelocity, unit: "m/s", passed: v <= inp.advisoryVelocity, governs: false },
    ];
    const required = checks.some(c => c.governs && !c.passed);
    let tNeed;
    if (dpJk <= dpAllow) tNeed = 0;
    else tNeed = Math.max(2 * rho * L * v / dpAllow, closureTimeForLimit(inp, q, pStatic, dpAllow, 2 * rho * L * v / dpAllow));
    const vAllow = dpAllow / (rho * a), qAllow = vAllow * inp.pipe.area * 60000;
    const vol = required ? arresterVolume(rho, inp.pipe.area, L, v, pStatic, Math.min(dpAllow, inp.rating * 1e5 - pStatic), inp.gasIndex) : null;
    return {
      velocity: v, waveSpeed: a, criticalTime: tCrit, regime, joukowskyBar: dpJk / 1e5, closedFormBar: dpCf / 1e5,
      mocSurgeBar: mocSurge / 1e5, designSurgeBar: dpDesign / 1e5, peakBar: peak / 1e5, minBar: minGauge / 1e5,
      vapourGaugeBar: pVapGauge / 1e5, checks, required, minClosureTime: tNeed, maxFlowInstant: qAllow,
      maxVelocityInstant: vAllow, arresterMl: vol === null ? null : vol * 1e6, trace: { t: sim.times, p: sim.valveP },
    };
  }

  const api = { DATA, makePipe, waveSpeed, simulateMoc, arresterVolume, assess, waterDensity };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.WaterHammer = api;
})(typeof window !== "undefined" ? window : globalThis);
