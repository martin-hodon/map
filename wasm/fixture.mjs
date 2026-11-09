// fixture.mjs -- the page's own numbers for the Rust check: parseLite over a light file, d3's projection as geom.js setup
// makes it, rows traced into a recording sink. node fixture.mjs <file> <object> <proj index> <W> <H> <zoom> <lon,lat,gamma> <out dir> [every]
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)), root = path.join(here, "..");
const { createRequire } = await import("node:module"); const require = createRequire(import.meta.url);
const d3 = require(path.join(root, "lib/d3.min.js")); globalThis.d3 = d3;
new Function("exports", "module", "define", fs.readFileSync(path.join(root, "lib/d3-geo-projection.min.js"), "utf8"))();   // (onto the global d3)
const RING = 0x7fffffff, POLY = 0x7ffffffe;
const liteSrc = fs.readFileSync(path.join(root, "js/lite.js"), "utf8").replace(/^import .*$/m, "").replace("export function parseLite", "function parseLite");
const parseLite = new Function("RING", "POLY", "d3", liteSrc + "\nreturn parseLite;")(RING, POLY, d3);
const PROJ = [() => d3.geoOrthographic().clipAngle(90), () => d3.geoEqualEarth(), () => d3.geoNaturalEarth1(), () => d3.geoRobinson(), () => d3.geoMercator(),
              () => d3.geoEquirectangular(), () => d3.geoAzimuthalEqualArea().clipAngle(179.9), () => d3.geoWinkel3(), () => d3.geoMollweide()];
const tilt = (r) => Math.abs(r[1]) < 1e-3 ? [r[0], -1e-3, r[2]] : Math.abs(r[1]) > 90 - 1e-3 ? [r[0], Math.sign(r[1]) * (90 - 1e-3), r[2]] : r;
const [file, object, pi, W, H, zoom, rot, out, every = "1"] = process.argv.slice(2);
const full = file.replace(/(small|xsmall)\//, ""), known = full === file ? null : parseLite(fs.readFileSync(path.join(root, full), "utf8")).objects;   // (a copy's rows name their row)
const T = parseLite(fs.readFileSync(path.join(root, file), "utf8"), null, known), o = T.objects[object], g = o.g;
const proj = PROJ[+pi]().rotate(tilt(rot.split(",").map(Number))).precision(0.5);
proj.fitExtent([[10, 10], [+W - 10, +H - 10]], { type: "Sphere" });
proj.scale(proj.scale() * +zoom).translate([+W / 2, +H / 2]);
const rec = []; let ring = false, first = false;
const sink = { polygonStart() { ring = true; }, polygonEnd() { ring = false; }, lineStart() { first = true; }, lineEnd() { if (ring) rec.push(2, 0, 0); },
               point(x, y) { rec.push(first ? 0 : 1, x, y); first = false; }, sphere() {} };
function arcInto(s, a) { const xy = T.xy; if (a >= 0) for (let k = 2 * T.at[a], e = 2 * T.at[a + 1] - 2; k < e; k += 2) s.point(xy[k], xy[k + 1]); else { const r = ~a; for (let k = 2 * T.at[r + 1] - 2, e = 2 * T.at[r]; k > e; k -= 2) s.point(xy[k], xy[k + 1]); } }
const arcEnd = (s, a) => { const k = a >= 0 ? 2 * T.at[a + 1] - 2 : 2 * T.at[~a]; s.point(T.xy[k], T.xy[k + 1]); };
function trace(i) {
  const e = g.start[i + 1], refs = g.refs; let j = g.start[i]; if (j === e) return;
  const s = proj.stream(sink);
  if (o.kind === "polygon") { let open = false; while (j < e) { if (refs[j] === POLY) { s.polygonEnd(); open = false; j++; continue; } if (!open) { s.polygonStart(); open = true; } s.lineStart(); for (; refs[j] !== RING; j++) arcInto(s, refs[j]); s.lineEnd(); j++; } }
  else while (j < e) { s.lineStart(); let a; for (; refs[j] !== RING; j++) arcInto(s, a = refs[j]); arcEnd(s, a); s.lineEnd(); j++; }
}
const ids = []; for (let i = 0; i < o.n; i += +every) ids.push(i);
const t0 = performance.now(); for (const i of ids) trace(i); const ms = performance.now() - t0;
fs.mkdirSync(out, { recursive: true });
const w = (name, arr) => fs.writeFileSync(path.join(out, name), Buffer.from(arr.buffer, arr.byteOffset, arr.byteLength));
w("xy.f32", T.xy); w("at.i32", T.at); w("start.i32", g.start); w("refs.i32", g.refs); w("ids.i32", Int32Array.from(ids)); w("expected.f32", Float32Array.from(rec));
const r = proj.rotate(), t = proj.translate(), ca = proj.clipAngle ? proj.clipAngle() : null, ce = proj.clipExtent();
fs.writeFileSync(path.join(out, "params.txt"), [+pi, r[0], r[1], r[2] ?? 0, proj.scale(), t[0], t[1], ca ?? 0, ce ? 1 : 0, ...(ce ? [ce[0][0], ce[0][1], ce[1][0], ce[1][1]] : [0, 0, 0, 0]), 0.25, o.kind === "polygon" ? 1 : 0].join(" ") + "\n");
console.log(`${out}: ${object} ${ids.length} rows, ${rec.length / 3} commands, d3 ${ms.toFixed(1)} ms`);
