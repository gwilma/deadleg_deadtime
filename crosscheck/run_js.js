// node crosscheck/run_js.js cases.json out.json [nx nr axial]
const D = require("../web/deadleg.js");
const fs = require("fs");
const [cases, outPath, nx, nr, axial] = process.argv.slice(2);
const res = {};
for (const c of JSON.parse(fs.readFileSync(cases))) {
  const s = { ...c, airArea: c.airArea === "inf" ? Infinity : c.airArea };
  if (nx) s.nx = +nx; if (nr) s.nr = +nr; if (axial) s.axial = axial === "1";
  const r = D.simulate(s);
  res[c.id] = { t: r.t, Tout: r.Tout, Tair: r.Tair, t40: r.timeToReach(40), t45: r.timeToReach(45), t50: r.timeToReach(50), ebal: r.energyBalanceError() };
}
fs.writeFileSync(outPath, JSON.stringify(res));
