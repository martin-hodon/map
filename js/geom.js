// geom.js -- the lines in typed arrays: a row's arcs, its GeoJSON when asked, tracing a row through the projection into the canvas path, neighbours, merging, lengths; the rings mended for the globe's clip
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { PROJ } from "./style.js";
import { $, canvas, ctx, R_KM, tilt } from "./state.js";
import { tree, query } from "./view.js";
import { objectsOf } from "./data.js";
import { W, setProj, attachRows, traceRows, traceArcsOf } from "./wasm.js";

export function setup() {
  S.dpr = window.devicePixelRatio || 1; S.W = canvas.clientWidth || innerWidth; S.H = canvas.clientHeight || innerHeight;   // (its size as laid out: the picture never stretched)
  if (canvas.width !== S.W * S.dpr || canvas.height !== S.H * S.dpr) { canvas.width = S.W * S.dpr; canvas.height = S.H * S.dpr; }
  ctx.setTransform(S.dpr, 0, 0, S.dpr, 0, 0);
  S.proj = PROJ[$("proj").value]().rotate(tilt(S.rotate)).precision(0.5);
  S.proj.fitExtent([[10, 10], [S.W - 10, S.H - 10]], { type: "Sphere" });
  S.proj.scale(S.proj.scale() * S.zoom).translate([S.W / 2, S.H / 2]);
  S.path = d3.geoPath(S.proj, ctx).pointRadius(2);
  syncProj();
}
// the view as it is now, for a frame painted meanwhile: the projection copied (a drag turns S.proj in place), the path on
// it, the rotation and zoom -- compose draws the main-thread steps and the labels under it, in step with the bitmaps
export function viewNow() {
  const p = PROJ[$("proj").value]().rotate(S.proj.rotate()).scale(S.proj.scale()).translate(S.proj.translate()).precision(S.proj.precision());
  return { proj: p, path: d3.geoPath(p, ctx).pointRadius(2), rotate: S.rotate.slice(), zoom: S.zoom };
}
// the projection's numbers to the wasm pipeline: at setup, and before every frame (a drag or a pinch turns S.proj directly)
export const syncProj = () => setProj(S.proj, Object.keys(PROJ).indexOf($("proj").value));
// ---- what is merged at run time (a continent, a state of its day): rings the globe's clip can read ----------------
// (the files' polygons are mended already, by these same rules: build/small.py)
// a ring of fewer than three distinct points (one point over and over: some coast cut to nothing) -- the globe's clip takes
// it for one round the whole sphere
export const flat = (r) => { const [x, y] = r[0]; let a = null; for (const [u, w] of r) if (u !== x || w !== y) { if (!a) a = [u, w]; else if (u !== a[0] || w !== a[1]) return false; } return true; };
// a ring that runs along itself (a narrow bay or spit that a coarser grid or the simplification closed to no width: A B A):
// where the globe's edge crosses such a stretch the two crossings are one point, the clip cannot tell which way is in, and
// it paints the globe but the polygon -- at those rotations only. So a ring is cut at each point it comes back to: a
// spike goes, a loop is a ring of its own -- wound as the polygon is, a polygon of its own; the other way, a hole
// (the same place: read from sums of grid steps, not always the same float; -180° and 180° one meridian, a pole one point --
//  a ring round Antarctica is cut along the seam, the Southern Ocean's runs up it and back)
export const placeKey = ([x, y]) => Math.round(Math.abs(y) === 90 ? 0 : (x === 180 ? -180 : x) * 1e5 + 18e6) * 4e7 + Math.round((y + 90) * 1e5);
export const loopsOf = (r) => {
  const at = new Map(), st = [], out = [];
  for (const q of r) {
    const key = placeKey(q), i = at.get(key);
    if (i === undefined) { at.set(key, st.length); st.push(q); continue; }
    const loop = st.splice(i + 1);
    for (const u of loop) at.delete(placeKey(u));
    if (loop.length >= 2) out.push([st[i], ...loop, q]);
  }
  return out.length === 1 && out[0].length === r.length ? [r] : out;
};
// a long edge along a parallel (where the IHO's Southern Ocean meets the oceans north of it: -60.5°, 146° in one step) is meant
// along it: as the great circle between its ends it would dip across Antarctica and through the ring's own hole
export const alongParallel = (r) => {
  if (!r.some((q, j) => j && q[1] === r[j - 1][1] && Math.abs(q[0] - r[j - 1][0]) > 10 && Math.abs(q[0] - r[j - 1][0]) < 180)) return r;
  return r.flatMap((q, j) => {
    const o = r[j - 1], d = j && q[1] === o[1] ? q[0] - o[0] : 0, n = Math.abs(d) > 10 && Math.abs(d) < 180 ? Math.ceil(Math.abs(d) / 5) : 1;
    return Array.from({ length: n }, (_, k) => k === n - 1 ? q : [o[0] + d * (k + 1) / n, q[1]]);
  });
};
// a ring along the ±180° seam, there and back with different points (cut there in the source): each stretch cut at the
// other's points, so that untangle sees the two as the same line
export const alongSeam = (r) => {
  const on = (q) => Math.abs(q[0]) === 180, ys = [...new Set(r.filter(on).map((q) => q[1]))];
  if (ys.length < 3) return r;
  return r.flatMap((q, j) => {
    const o = r[j - 1];
    if (!j || !on(o) || !on(q) || o[1] === q[1]) return [q];
    const between = ys.filter((y) => (y - o[1]) * (y - q[1]) < 0).sort((u, w) => (u - o[1]) * (o[1] < q[1] ? 1 : -1) - (w - o[1]) * (o[1] < q[1] ? 1 : -1));
    return [...between.map((y) => [q[0], y]), q];
  });
};
export const wound = (r) => d3.geoArea({ type: "Polygon", coordinates: [r] }) <= 2 * Math.PI;
export function untangle(p) {
  const loops = p.map(loopsOf);
  if (loops.every((l, k) => l.length === 1 && l[0] === p[k])) return [p];
  const rings = loops.flat(), polys = rings.filter(wound).map((r) => [r]).sort((a, b) => d3.geoArea({ type: "Polygon", coordinates: a }) - d3.geoArea({ type: "Polygon", coordinates: b }));
  for (const h of rings) if (!wound(h) && polys.length) {             // (a hole: in the smallest polygon round it)
    const mid = h[h.length >> 1];
    (polys.find((q) => d3.geoContains({ type: "Polygon", coordinates: [q[0]] }, mid)) ?? polys.at(-1)).push(h);
  }
  return polys;
}
export function keepPolygons(f) {
  const g = f.geometry;
  if (!g || (g.type !== "Polygon" && g.type !== "MultiPolygon")) return f;
  const parts = (g.type === "Polygon" ? [g.coordinates] : g.coordinates).map((p) => p.map((r) => alongSeam(alongParallel(r)))).flatMap(untangle)
    .map((p) => p.filter((r) => r.length >= 4 && !flat(r))).filter((p) => p.length && p[0].length >= 4)
    .filter((p) => d3.geoArea({ type: "Polygon", coordinates: p }) <= 2 * Math.PI);
  return { ...f, geometry: parts.length ? { type: "MultiPolygon", coordinates: parts } : null };
}
// ---- THE LINES -----------------------------------------------------------------------------------------------------
// A file read (parseLite) is its points -- one Float32Array, longitude and latitude in turn; `at`: where each arc starts --
// and its objects, each row's arcs as numbers in one Int32Array (`refs`, from `start[row]`: signed as in TopoJSON, RING at
// a ring's or a line's end, POLY at a polygon's). A point is 8 bytes, as an array in JS 40 or more (the page once took 1.4 GB for
// 37 MB of text). A row is a Thing: what it is called, and its place: it is drawn straight from the numbers (trace), and
// GeoJSON is made of it only when something asks for its `geometry` (a click, a selection): not kept.
// COPIES: every file comes in three (build/small.py), its rows the same rows: a row of the full file by its number in each.
export const COPIES = [{ dir: "", km: 1 }, { dir: "small/", km: 5 }, { dir: "xsmall/", km: 25 }];
export const RING = 0x7fffffff, POLY = 0x7ffffffe, NOTHING = { start: [], refs: [] };
export const geoAt = (o, lv) => { for (; lv >= 0; lv--) if (o.geos[lv]) return o.geos[lv]; return NOTHING; };   // (a copy not come yet: the next finer)
export class Thing {
  constructor(o, i, properties) { this.o = o; this.i = i; this.properties = properties; }
  get type() { return "Feature"; }
  has(lv = 0) { const g = geoAt(this.o, lv); return g.start[this.i + 1] > g.start[this.i]; }
  get geometry() { return shape(this, 0); }
  named(properties) { return new Thing(this.o, this.i, properties); }
}
// the row's arcs as TopoJSON has them: polygons of rings, or lines, of signed arcs
export function arcsOf(f, lv = 0) {
  const g = geoAt(f.o, lv), out = []; let cur = [], poly = [];
  for (let j = g.start[f.i], e = g.start[f.i + 1]; j < e; j++) { const a = g.refs[j];
    if (a === RING) { poly.push(cur); cur = []; } else if (a === POLY) { out.push(poly); poly = []; } else cur.push(a); }
  return f.o.kind === "polygon" ? out : poly;
}
export const arcPoints = (T, a) => { const r = a < 0 ? ~a : a, q = []; for (let k = T.at[r]; k < T.at[r + 1]; k++) q.push([T.xy[2 * k], T.xy[2 * k + 1]]); return a < 0 ? q.reverse() : q; };
export const joined = (T, arcs) => { const q = []; for (const a of arcs) { const p = arcPoints(T, a); for (let k = q.length ? 1 : 0; k < p.length; k++) q.push(p[k]); } return q; };
export function shape(f, lv = 0) {                                         // (GeoJSON, made anew)
  if (!f.has(lv)) return null;
  const T = geoAt(f.o, lv).T, A = arcsOf(f, lv);
  if (f.o.kind === "polygon") return { type: "MultiPolygon", coordinates: A.map((p) => p.map((r) => joined(T, r))) };
  return A.length === 1 ? { type: "LineString", coordinates: joined(T, A[0]) } : { type: "MultiLineString", coordinates: A.map((l) => joined(T, l)) };
}
// what the canvas gets from the projection (d3.geoPath's own, for a canvas)
export const sink = { ring: false, first: false,
  polygonStart() { this.ring = true; }, polygonEnd() { this.ring = false; }, lineStart() { this.first = true; },
  lineEnd() { if (this.ring) ctx.closePath(); },
  point(x, y) { if (this.first) { ctx.moveTo(x, y); this.first = false; } else ctx.lineTo(x, y); } };
// an arc's points through the stream, but its last (the next arc's first; a ring's first again)
export function arcInto(s, T, a) {
  const xy = T.xy;
  if (a >= 0) for (let k = 2 * T.at[a], e = 2 * T.at[a + 1] - 2; k < e; k += 2) s.point(xy[k], xy[k + 1]);
  else { const r = ~a; for (let k = 2 * T.at[r + 1] - 2, e = 2 * T.at[r]; k > e; k -= 2) s.point(xy[k], xy[k + 1]); }
}
export const arcEnd = (s, T, a) => { const k = a >= 0 ? 2 * T.at[a + 1] - 2 : 2 * T.at[~a]; s.point(T.xy[k], T.xy[k + 1]); };
// a row into the path being built
export function trace(f, lv) {
  const g = geoAt(f.o, lv), e = g.start[f.i + 1], refs = g.refs, T = g.T;
  let j = g.start[f.i];
  if (j === e) return;
  if (g.wid) return traceRows(g, [f.i]);
  const s = S.proj.stream(sink);
  if (f.o.kind === "polygon") {
    let open = false;
    while (j < e) {
      if (refs[j] === POLY) { s.polygonEnd(); open = false; j++; continue; }
      if (!open) { s.polygonStart(); open = true; }
      s.lineStart();
      for (; refs[j] !== RING; j++) arcInto(s, T, refs[j]);
      s.lineEnd(); j++;
    }
  } else while (j < e) {
    s.lineStart();
    let a;
    for (; refs[j] !== RING; j++) arcInto(s, T, a = refs[j]);
    arcEnd(s, T, a); s.lineEnd(); j++;
  }
}
// the rows of one list's Things (a layer's: one object's) at a level: the copy and the row numbers, or null when the list
// mixes objects or the module has no copy of it
export function rowsOf(feats, ids, lv) {
  if (!W || !feats.length || !ids.length) return null;
  const o = feats[ids[0]].o, g = geoAt(o, lv);
  if (!g.wid) return null;
  const rows = new Int32Array(ids.length); let k = 0;
  for (const i of ids) { const f = feats[i]; if (f.o !== o) return null; rows[k++] = f.i; }
  return { g, rows };
}
export function rowCosts(g) {                                             // (points per row: the weight of painting it, once)
  if (g.costs) return g.costs;
  const c = new Int32Array(g.start.length - 1), T = g.T;
  for (let i = 0; i < c.length; i++) { let n = 0;
    for (let j = g.start[i], e = g.start[i + 1]; j < e; j++) { const a = g.refs[j]; if (a === RING || a === POLY) continue; const r = a < 0 ? ~a : a; n += T.at[r + 1] - T.at[r]; }
    c[i] = n; }
  return g.costs = c;
}
// rows of one list into the path: all at once when the module has them
export function traceAll(feats, ids, lv) {
  const r = rowsOf(feats, ids, lv);
  if (r) return traceRows(r.g, r.rows);
  for (const i of ids) trace(feats[i], lv);
}
export function traceArcs(T, arcs) {                                       // (arcs, each a line of its own)
  if (T.wid) return traceArcsOf(T, arcs);
  const s = S.proj.stream(sink);
  for (const a of arcs) { s.lineStart(); arcInto(s, T, a); arcEnd(s, T, a); s.lineEnd(); }
}
// the rows' neighbours (topojson.neighbors): those with an arc in common
export function neighbors(F) {
  const by = new Map(), nb = F.map(() => new Set());
  F.forEach((f, i) => { const g = geoAt(f.o, 0); for (let j = g.start[f.i]; j < g.start[f.i + 1]; j++) { const a = g.refs[j]; if (a === RING || a === POLY) continue;
    const r = a < 0 ? ~a : a, o = by.get(r); if (o === undefined) by.set(r, [i]); else { for (const x of o) if (x !== i) { nb[i].add(x); nb[x].add(i); } o.push(i); } } });
  return nb.map((n) => [...n].sort((a, b) => a - b));
}
// rows merged into one outline (topojson.merge, given only the arcs it needs)
export function merged(F, lv = 0) {
  const parts = F.filter((f) => f.has(lv)), arcs = [], T = parts.length ? geoAt(parts[0].o, lv).T : null;
  const geoms = parts.map((f) => { const A = arcsOf(f, lv); for (const p of A) for (const r of p) for (const a of r) { const x = a < 0 ? ~a : a; arcs[x] ??= arcPoints(T, x); } return { type: "MultiPolygon", arcs: A }; });
  return keepPolygons({ type: "Feature", properties: {}, geometry: topojson.merge({ type: "Topology", arcs }, geoms) });
}
export const lengthKm = (f) => {                                           // (near enough: the search's "1,200 km")
  const g = geoAt(f.o, 0), T = g.T, rad = Math.PI / 180; let km = 0;
  for (let j = g.start[f.i]; j < g.start[f.i + 1]; j++) { const a = g.refs[j]; if (a === RING || a === POLY) continue; const r = a < 0 ? ~a : a;
    for (let k = T.at[r] + 1; k < T.at[r + 1]; k++) { const y = T.xy[2 * k + 1], y0 = T.xy[2 * k - 1]; km += Math.hypot((T.xy[2 * k] - T.xy[2 * k - 2]) * Math.cos((y + y0) / 2 * rad), y - y0); } }
  return km * rad * R_KM;
};
export const endsOf = (f) => {                                             // (a line's two ends, as text)
  const g = geoAt(f.o, 0), T = g.T, first = g.refs[g.start[f.i]], last = g.refs[g.start[f.i + 1] - 2], p = (a, end) => { const r = a < 0 ? ~a : a, k = (a >= 0) === end ? T.at[r + 1] - 1 : T.at[r]; return `${T.xy[2 * k]},${T.xy[2 * k + 1]}`; };
  return [p(first, false), p(last, true)];
};
export const eachPoint = (f, go) => { const g = geoAt(f.o, 0), T = g.T;     // (a row's points, the shared ends twice)
  for (let j = g.start[f.i]; j < g.start[f.i + 1]; j++) { const a = g.refs[j]; if (a === RING || a === POLY) continue; const r = a < 0 ? ~a : a;
    for (let k = T.at[r]; k < T.at[r + 1]; k++) go(T.xy[2 * k], T.xy[2 * k + 1]); } };
// the map's rows: the world's objects, and the rest as they come; a layer of one file's objects has one list of Things
export let Map0 = { land: [], countries: [], regions: [], lakes: [], areas: [], cb: [], rb: [], rivers: [], motorways: [], roads: [], railways: [], pipelines: [] };
export const thingsOf = (O, name) => { const o = O[name]; if (!o) return []; const R = o.rows; o.rows = null; return Array.from({ length: o.n }, (_, i) => new Thing(o, i, R ? R[i] : {})); };
// the coast is one row of many lines: in each copy a Thing a line (a copy's lines are longer: a tree of its own)
export const coasts = [];
export function coastAt(lv) {
  const o = objectsOf.world.coastline;
  for (; lv > 0 && !o.geos[lv]; lv--);
  if (coasts[lv]) return coasts[lv];
  const g = o.geos[lv], ends = [g.start[0]];
  for (let j = g.start[0]; j < g.start[1]; j++) if (g.refs[j] === RING) ends.push(j + 1);
  const own = { kind: "line", geos: [{ T: g.T, refs: g.refs, start: Int32Array.from(ends) }] }, lines = Array.from({ length: ends.length - 1 }, (_, i) => new Thing(own, i));
  attachRows(g.T, own.geos[0], "line");
  return coasts[lv] = { lines, tree: tree(lines) };
}
// the biogeographic layer's rows (its own file, loaded when wanted: loadBio)
export let B0 = { realms: [], biomes: [], ecoregions: [] };
