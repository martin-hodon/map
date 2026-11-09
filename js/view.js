// view.js -- the frame: which copy of a layer to draw from, the R-trees and what of the globe is in view, drawMap
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { PALETTES, palette, regionShades, shade, GEO, mode, densityColour, bioLayer, rankLanguages, bioColour } from "./style.js";
import { $, canvas, ctx, css, trees, points, on, HOW, dark } from "./state.js";
import { COPIES, RING, POLY, geoAt, trace, traceAll, traceArcs, Map0, coastAt, B0, syncProj, viewNow } from "./geom.js";
import { W, painter, projParams, treeOfRows, treeOfPoints, queryTree, workersWanted } from "./wasm.js";
import { rowsOf, rowCosts } from "./geom.js";
import { histOn, histLines, pxKm } from "./history.js";
import { bioLabels, histLabels, unitLabels, areaLabels, cityDots, cityLabels, pointLabels, riverLabels, shown, SIZE, natural, LINE_TIERS, ROAD_TIERS, visible } from "./labels.js";
import { loads, wanted } from "./data.js";
import { groupsOn, drawGroups, game, bareGame, drawBare } from "./groups.js";
import { SHAPES, whereGeom, outline, keepGameBase, gameLabels, drawGame } from "./game.js";

export function pick(moving = false) {
  let i = 0;
  while (i + 1 < COPIES.length && COPIES[i + 1].km <= (moving ? 2.5 : 1.25) * pxKm()) i++;
  return i;
}
// ---- the R-trees: every piece by its box (a piece over the antimeridian by two) ---------------------------------
// (from the points: an edge's bulge over a straight line is within the view's margin; a ring all the way round the
//  globe has the pole in it)
export function tree(feats) {
  if (W && feats.length) {                                          // (in the module, when it has the rows: a list of one object, in its order)
    const o = feats[0].o, g = geoAt(o, 0);
    if (g.wid && feats.length <= o.n && feats.every((f, i) => f.o === o && f.i === i)) return treeOfRows(g, feats.length);
  }
  const items = [];
  feats.forEach((f, i) => {
    const g = geoAt(f.o, 0), T = g.T, xy = T?.xy;
    let w = 999, s = 999, e = -999, n = -999;
    for (let j = g.start[f.i], end = g.start[f.i + 1]; j < end; j++) {
      const a = g.refs[j];
      if (a === RING) { if (f.o.kind !== "polygon") { items.push({ minX: w, minY: s, maxX: e, maxY: n, i }); w = s = 999; e = n = -999; } continue; }
      if (a === POLY) { if (e - w >= 359) { if (s + n > 0) n = 90; else s = -90; } items.push({ minX: w, minY: s, maxX: e, maxY: n, i }); w = s = 999; e = n = -999; continue; }
      const r = a < 0 ? ~a : a;
      for (let k = 2 * T.at[r], x = 2 * T.at[r + 1]; k < x; k += 2) { const u = xy[k], v = xy[k + 1]; if (u < w) w = u; if (u > e) e = u; if (v < s) s = v; if (v > n) n = v; }
    }
  });
  const t = new RBush(); t.load(items); return t;
}
export function pointTree(set) {
  if (W && set) return treeOfPoints(set.features.flatMap((f) => f.geometry.coordinates));
  const t = new RBush();
  if (set) t.load(set.features.map((f, i) => { const [x, y] = f.geometry.coordinates; return { minX: x, minY: y, maxX: x, maxY: y, i }; }));
  return t;
}
export function query(t, boxes) {
  if (!t) return [];                                                // (a layer still loading: nothing of it yet)
  if (t.wid) return queryTree(t, boxes);
  const s = new Set();
  for (const [w, so, e, n] of boxes) for (const it of t.search({ minX: w, minY: so, maxX: e, maxY: n })) s.add(it.i);
  return [...s].sort((a, b) => a - b);
}
// what of the globe is in view, as longitude/latitude boxes (the screen sampled on a grid and turned back)
export function viewBoxes() {
  const lon = [], lat = [], nx = 24, ny = 16;
  for (let i = 0; i <= nx; i++) for (let j = 0; j <= ny; j++) {
    const x = i * S.W / nx, y = j * S.H / ny, p = S.proj.invert([x, y]);
    if (!p || !isFinite(p[0]) || !isFinite(p[1]) || !visible(p)) continue;
    const q = S.proj(p);
    if (!q || Math.hypot(q[0] - x, q[1] - y) > 2) continue;
    lon.push(p[0]); lat.push(p[1]);
  }
  if (lon.length < 4) return [[-180, -90, 180, 90]];
  const pad = Math.max(1, 30 * pxKm() / 111);
  let s = Math.max(-90, Math.min(...lat) - pad), n = Math.min(90, Math.max(...lat) + pad);
  let full = false;
  for (const pole of [90, -90]) {                                   // (a pole in view: all longitudes)
    const q = S.proj([0, pole]);
    if (q && visible([0, pole]) && q[0] >= 0 && q[0] <= S.W && q[1] >= 0 && q[1] <= S.H) { full = true; if (pole > 0) n = 90; else s = -90; }
  }
  lon.sort((a, b) => a - b);
  let gap = lon[0] + 360 - lon[lon.length - 1], at = lon.length - 1;           // (the widest stretch of longitude not seen)
  for (let i = 1; i < lon.length; i++) if (lon[i] - lon[i - 1] > gap) { gap = lon[i] - lon[i - 1]; at = i - 1; }
  if (full || gap < 3 * pad) return [[-180, s, 180, n]];
  const w = lon[(at + 1) % lon.length] - pad, e = lon[at] + pad;
  if (w <= e && w >= -180 && e <= 180) return [[w, s, e, n]];
  const W0 = ((w + 540) % 360) - 180, E0 = ((e + 540) % 360) - 180;
  return W0 <= E0 ? [[W0, s, E0, n]] : [[W0, s, 180, n], [-180, s, E0, n]];
}
// ---- drawing -------------------------------------------------------------------------------------------------------
export const draw = (fast = false) => drawMap(fast);
// THE FRAME: drawMap writes down what is to be painted, in order -- fills and strokes of rows (ops), and steps drawn here
// (main: the sphere, a selection, a clip) -- then the painters (paint.js) paint the ops in parallel and the bitmaps are
// stacked, or, with no painters, the ops are run here one after the other; the labels and the points come on top
// (after). The one-thread way and the painted way give the same pixels.
export function drawMap(fast) {
  const t0 = performance.now();
  if (S.proj) syncProj();
  document.body.classList.toggle("bare", bareGame());
  const lv = S.src ? pick(fast) : 0;
  if (S.src && bareGame()) { ctx.clearRect(0, 0, S.W, S.H); ctx.lineJoin = "miter"; return drawBare(lv); }
  const F = { fast, lv, t0, ops: [], proj: projParams, W: S.W, H: S.H, dpr: S.dpr, done: compose };
  const main = (fn) => F.ops.push({ main: fn });
  const paint = (feats, ids, fill, color, width) => {
    if (!ids.length) return;
    F.ops.push({ feats, ids, lv, fill, color, width, alpha: ctx.globalAlpha, dash: ctx.getLineDash() });
  };
  const stroke = (feats, ids, color, width) => paint(feats, ids, false, color, width);
  const fillAll = (feats, ids, color) => paint(feats, ids, true, color, 0);
  const only = S.src && game.open && game.where?.kind === "country" ? whereGeom(lv) : null;   // (a country's game: that country alone, no globe round it)
  if (only) main(() => { ctx.save(); ctx.beginPath(); outline(only, lv); ctx.clip(); });
  main(() => { ctx.beginPath(); S.path({ type: "Sphere" }); ctx.fillStyle = css("--sea"); ctx.fill(); });
  if (!S.src) return compose(F);
  const L = Map0, boxes = viewBoxes(), dk = dark();
  const v = (k) => query(trees[k], boxes);
  const m = mode(), geo = m === "geographical", political = m === "political", themed = m === "language" || m === "density";
  const themeFill = (name) => {                                     // countries, then the states over them, by language or density
    const F = L[name], by = {};
    if (m === "language" && !Object.keys(S.langColour).length) rankLanguages();
    for (const i of v(name)) {
      const p = F[i].properties; if (!F[i].has(lv)) continue;
      const c = m === "language" ? (p.language ? (S.langColour[p.language] || "#d8d8d8") : null) : (p.density != null ? densityColour(p.density) : null);
      if (c) (by[c] ??= []).push(i);
    }
    for (const c in by) fillAll(F, by[c], c);
  };
  const geoFill = (mask) => {                                      // the areas of one side of the coast, by kind, the bigger first
    const by = {};
    for (const i of v("areas")) { const p = L.areas[i].properties; if (p.mask === mask && GEO[p.kind] && L.areas[i].has(lv)) (by[p.kind] ??= []).push(i); }
    const order = Object.keys(by).sort((a, b) => Math.min(...by[a].map((i) => L.areas[i].properties.rank ?? 9)) - Math.min(...by[b].map((i) => L.areas[i].properties.rank ?? 9)));
    if (dk) ctx.globalAlpha = 0.45;
    for (const k of order) fillAll(L.areas, by[k].sort((i, j) => (L.areas[i].properties.rank ?? 9) - (L.areas[j].properties.rank ?? 9)), GEO[k]);
    ctx.globalAlpha = 1;
  };
  if (geo && on("areas")) geoFill("water");
  if (S.sel && S.sel.cat === "area" && S.sel.mask === "water") main(() => highlight(S.sel));   // (a sea under the land: it has no holes for its islands)
  if (on("land")) fillAll(L.land, v("land"), css("--land"));
  const pal = groupsOn("countries") ? null : palette();          // (countries put into groups: only the groups coloured)
  const B = m === "bio" && S.src.bio ? B0 : null, bl = bioLayer();
  if (B) {                                                          // (the land by realm, biome or ecoregion; paler under groups)
    const by = {}; for (const i of v(bl)) { const f = B[bl][i]; if (f.has(lv)) (by[bioColour(f.properties)] ??= []).push(i); }
    ctx.globalAlpha = (dk ? 0.55 : 1) * (groupsOn(bl) ? 0.35 : 1); for (const c in by) fillAll(B[bl], by[c], c); ctx.globalAlpha = 1;
  }
  const Hl = m === "history" && S.src.hist ? histLines(lv) : null;
  if (Hl) {                                                         // (the day's country-periods; a dependency paler, in its ruler's colour)
    const now = histOn(), hp = palette() || PALETTES.pastel, by = {};
    for (const i of v("hregions")) { const pi = now.of[i]; if (pi < 0 || !S.H0.regions[i].has(lv)) continue; const p = S.H0.periods[pi];
      (by[`${now.colour.get(p.state) % hp.length}|${p.status === "culture" ? 2 : p.owner != null ? 1 : 0}`] ??= []).push(i); }
    for (const k in by) { const [c, dep] = k.split("|"); ctx.globalAlpha = (dk ? 0.8 : 1) * [1, 0.55, 0.3][dep]; fillAll(S.H0.regions, by[k], hp[c]); }
    ctx.globalAlpha = 1;
  }
  if (political && on("countries") && pal) { const by = {}; for (const i of v("countries")) { const f = L.countries[i]; if (f.has(lv)) (by[f.properties.color % pal.length] ??= []).push(i); }
    for (const c in by) fillAll(L.countries, by[c], pal[c]);
    if (on("regions")) {                                            // (the states over them, in shades of their country's colour)
      const R = L.regions, sh = regionShades(), cls = new Map(L.countries.map((f) => [f.properties.iso, f.properties.color])), rby = {};
      for (const i of v("regions")) { const f = R[i], c = cls.get(f.properties.country); if (c != null && f.has(lv)) (rby[shade(pal[c % pal.length], sh[i])] ??= []).push(i); }
      for (const c in rby) fillAll(R, rby[c], c);
    } }
  if (themed) { if (dk) ctx.globalAlpha = 0.6; themeFill("countries"); if (on("regions")) themeFill("regions"); ctx.globalAlpha = 1; }
  if (geo && on("areas")) geoFill("land");
  drawGroups(L, B, v, fillAll);
  if (S.sel && S.sel.mask === "land") main(() => highlight(S.sel));
  if (on("land")) { fillAll(L.lakes, v("lakes"), css("--sea")); const c = coastAt(lv); stroke(c.lines, query(c.tree, boxes), css("--line"), 0.6); }
  if (S.sel && S.sel.mask !== "land" && !(S.sel.cat === "area" && S.sel.mask === "water")) main(() => highlight(S.sel));
  if (B) {                                                          // (the outlines of the level shown, and the realms' over them)
    if (bl !== "realms") stroke(B[bl], v(bl), dk ? "#00000088" : "#ffffffaa", bl === "ecoregions" ? 0.5 : 0.7);
    stroke(B.realms, v("realms"), dk ? "#e8e8e8aa" : "#4a4a4aaa", 1.1);
  }
  if (Hl) {                                                         // (the day's land borders: an approximate one blurred -- wide and faint
    const ink = dk ? "#b9c2cb" : "#55606b";                   // under a thin line --, one to land no state held dashed)
    const arcs = (lists, color, width) => { const all = Int32Array.from(lists.flat()); if (all.length) F.ops.push({ T: Hl.T, arcs: all, fill: false, color, width, alpha: ctx.globalAlpha, dash: ctx.getLineDash() }); };
    ctx.globalAlpha = 0.18; arcs([Hl.rough, Hl.roughOpen], ink, 4); ctx.globalAlpha = 0.6; arcs([Hl.rough], ink, 0.6); ctx.globalAlpha = 1;
    arcs([Hl.fixed], ink, 0.8);
    ctx.globalAlpha = 0.7; arcs([Hl.partly], ink, 0.7); ctx.globalAlpha = 1;
    ctx.setLineDash([3, 3]); arcs([Hl.open], ink, 0.6); ctx.setLineDash([]);
    if (on("regions") && !fast) arcs([Hl.inner], dk ? "#6a7580" : "#a8b0b8", 0.4);   // (a province's border within its state: as a modern state's)
  }
  const gu = game.open && game.units && SHAPES.has(game.style) ? game.units.layer : null;   // (a countries' game: their borders, whatever the layers)
  if (((political || themed) && on("regions") && !fast) || gu === "regions") stroke(L.rb, v("rb"), dk ? "#6a7580" : "#a8b0b8", 0.4);
  if (((political || themed) && on("countries")) || gu) stroke(L.cb, v("cb"), dk ? "#b9c2cb" : "#55606b", 0.8);
  if (on("rivers") && L.rivers.length) {
    const min = S.zoom < 1.5 ? 600 : S.zoom < 3 ? 250 : S.zoom < 6 ? 100 : 0;    // (the long rivers first, the rest closer in)
    stroke(L.rivers, v("rivers").filter((i) => (L.rivers[i].properties.river_km || 0) >= min), dk ? "#4d86b3" : "#5b95c7", 0.7);
  }
  // the main lines by tier (LINE_TIERS): none from afar, the main roads first, the rest closer in; a railway dashed, a pipeline dotted
  const tiered = (feats, ids) => ids.filter((i) => S.zoom >= LINE_TIERS[(feats[i].properties.tier || 3) - 1]);
  const lw = Math.min(1, 0.35 + 0.2 * Math.log2(S.zoom + 1));      // (thinner the farther out: a continent's roads are many)
  const G = game.open;                                            // (the game: no names but the cities named, nothing to go by but the map)
  if (on("pipelines") && L.pipelines.length && !G) { ctx.setLineDash([1.5, 2.5]); stroke(L.pipelines, tiered(L.pipelines, v("pipelines")), dk ? "#b58b5a" : "#8a5a2b", lw); ctx.setLineDash([]); }
  if (on("railways") && L.railways.length && !G) { ctx.setLineDash([4, 2]); stroke(L.railways, tiered(L.railways, v("railways")), dk ? "#c8ccd2" : "#4a4f57", 0.9 * lw); ctx.setLineDash([]); }
  if (on("motorways") && S.zoom >= ROAD_TIERS[0] && !loads.roads) wanted();   // (their file: only once they would be drawn)
  if (on("motorways") && L.roads.length && !G) stroke(L.roads, v("roads").filter((i) => S.zoom >= ROAD_TIERS[L.roads[i].properties.tier - 1]), dk ? "#c9b45c" : "#b48c0a", 0.7 * lw);   // (under the motorways, thinner and yellow)
  if (on("motorways") && L.motorways.length && !G) stroke(L.motorways, tiered(L.motorways, v("motorways")), dk ? "#e0914a" : "#d9731f", 1.1 * lw);
  if (S.sel && (S.sel.cat === "river" || S.sel.cat === "line")) main(() => { ctx.beginPath(); S.path(S.sel.geom); ctx.strokeStyle = css("--hi"); ctx.lineWidth = 2.5; ctx.stroke(); });
  if (only) main(() => ctx.restore());
  F.after = () => {
  if (G && !fast) keepGameBase();                                // (the map under the game: a guess repaints only what lies on it)
  if (G) drawGame(fast);
  // (a moving map keeps its icons; its names too while it is dragged -- not while it zooms, where they would be laid out anew
  //  at every step; the labels cost a few ms of the frame, less than the painters leave the thread idle for)
  const names = !fast || !!S.drag;
  const placed = [];                                            // (labels placed so far: a label that would overlap one is left out)
  ctx.lineJoin = "round";                                       // (a name's halo: pointed, it runs out in spikes at an M, a W)
  if (G) { if (names) gameLabels(placed); return; }
  if (names && B) bioLabels(placed);
  if (names && Hl) histLabels(placed);
  if (names && (political || themed) && on("countries")) unitLabels(placed);
  if (names && on("areas")) areaLabels(placed);
  if (on("cities") && S.src.cities) {
    const ids = query(points.cities, boxes);
    const near = ids.filter((i) => shown("cities", i));
    cityDots(near); if (names) cityLabels(placed, near);
  }
  if (names && on("rivers") && L.rivers.length) riverLabels(placed, L.rivers, v("rivers"), lv);
  if (on("monuments") && S.src.monuments) {
    // (a work of nature -- a park, a waterfall -- a tree; a building or a ruin a temple's front; by its level the larger)
    const F = S.src.monuments.features, ink = (i) => natural(F[i].properties) ? (dk ? "#9be07a" : "#2e7d32") : (dk ? "#e0a3d8" : "#8e3a80"), seen = [];
    for (const i of query(points.monuments, boxes)) {
      const f = F[i];
      if (!shown("monuments", i) || !visible(f.geometry.coordinates)) continue;
      const [x, y] = S.proj(f.geometry.coordinates), s = SIZE[f.properties.level] ?? 1; seen.push(i);
      ctx.fillStyle = ink(i); ctx.beginPath();
      if (natural(f.properties)) { ctx.arc(x, y - 1.2 * s, 2.6 * s, 0, 2 * Math.PI); ctx.rect(x - 0.6 * s, y, 1.2 * s, 2.6 * s); }
      else { ctx.moveTo(x, y - 3.4 * s); ctx.lineTo(x + 3.2 * s, y - 1.2 * s); ctx.lineTo(x - 3.2 * s, y - 1.2 * s); ctx.closePath();
             ctx.rect(x - 2.6 * s, y - 0.6 * s, 1.3 * s, 2.4 * s); ctx.rect(x + 1.3 * s, y - 0.6 * s, 1.3 * s, 2.4 * s); ctx.rect(x - 3.2 * s, y + 2.1 * s, 6.4 * s, 1 * s); }
      ctx.fill();
    }
    if (names) pointLabels(placed, "monuments", seen, ink);
  }
  if (on("nature") && S.src.nature) {
    const ink = dk ? "#c9a27a" : "#7a4f2a", seen = [];
    ctx.fillStyle = ink;
    for (const i of query(points.nature, boxes)) {
      const f = S.src.nature.features[i];
      if (!shown("nature", i) || !visible(f.geometry.coordinates)) continue;
      const [x, y] = S.proj(f.geometry.coordinates); seen.push(i);
      ctx.beginPath();
      if (f.properties.kind === "peak") { ctx.moveTo(x, y - 3.5); ctx.lineTo(x + 3, y + 1.5); ctx.lineTo(x - 3, y + 1.5); }
      else ctx.rect(x - 1.8, y - 1.8, 3.6, 3.6);
      ctx.fill();
    }
    if (names) pointLabels(placed, "nature", seen, ink);
  }
  if (on("airports") && S.src.airports) {
    const ink = dk ? "#8fb8ff" : "#1d4f9c", seen = [];
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = ink;
    for (const i of query(points.airports, boxes)) {
      const f = S.src.airports.features[i];
      if (!shown("airports", i) || !visible(f.geometry.coordinates)) continue;
      const [x, y] = S.proj(f.geometry.coordinates); seen.push(i);
      ctx.font = `${Math.round(11 * (SIZE[f.properties.level] ?? 1))}px system-ui, sans-serif`;   // (by its passengers: three sizes)
      ctx.fillText("✈", x, y);
    }
    if (names) pointLabels(placed, "airports", seen, ink);
  }
  if (Hl && on("events") && S.src.events) {                          // (the day's events: the best known first, more the closer in)
    const F = S.src.events.features;
    ctx.fillStyle = dk ? "#ff7a8a" : "#b0124a"; ctx.strokeStyle = dk ? "#000" : "#fff"; ctx.lineWidth = 1;
    for (const i of query(points.events, boxes)) {
      if (!shown("events", i) || !visible(F[i].geometry.coordinates)) continue;
      const [x, y] = S.proj(F[i].geometry.coordinates);
      ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 3.5, y); ctx.lineTo(x, y + 4); ctx.lineTo(x - 3.5, y); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  }
  if (names && S.sel) mark(S.sel);
  };
  if (painter) { F.ops = F.ops.flatMap(forPainters); F.view = viewNow(); painter.paint(F); } else compose(F);
}
// an op as the painters take it: the rows (or arcs) of the module's copy, and the weight of each (its points) -- a list
// of several objects' Things (the land: continents and islands) an op per object when opaque; what they cannot paint is
// drawn here (the main-thread fallback)
function forPainters(o) {
  if (o.main) return [o];
  if (o.arcs) {
    if (!o.T.pid) return [{ main: () => runOp(o) }];
    const at = o.T.at, costs = Int32Array.from(o.arcs, (a) => { const r = a < 0 ? ~a : a; return at[r + 1] - at[r]; });
    return [{ ...o, lid: o.T.pid, items: o.arcs, costs, cost: costs.reduce((s, c) => s + c, 0) }];
  }
  const runs = [];                                                  // (runs of one object's Things, in order)
  for (const i of o.ids) { const f = o.feats[i], last = runs.at(-1); if (last && last.o === f.o) last.ids.push(i); else runs.push({ o: f.o, ids: [i] }); }
  if (runs.length > 1 && o.alpha !== 1) return [{ main: () => runOp(o) }];
  return runs.map((run) => {
    const r = rowsOf(o.feats, run.ids, o.lv);
    if (!r) return { main: () => runOp({ ...o, ids: run.ids }) };
    const rc = rowCosts(r.g), costs = Int32Array.from(r.rows, (i) => rc[i]);
    return { ...o, pid: r.g.pid, items: r.rows, costs, cost: costs.reduce((s, c) => s + c, 0) };
  });
}
// an op run here, through the module or d3 (the fallback)
function runOp(o) {
  ctx.globalAlpha = o.alpha; ctx.setLineDash(o.dash); ctx.beginPath();
  if (o.arcs) traceArcs(o.T, o.arcs); else traceAll(o.feats, o.ids, o.lv);
  if (o.fill) { ctx.fillStyle = o.color; ctx.fill(); } else { ctx.strokeStyle = o.color; ctx.lineWidth = o.width; ctx.stroke(); }
  ctx.globalAlpha = 1; ctx.setLineDash([]);
}
// the frame onto the canvas: the painters' bitmaps in order with the main-thread steps between them -- or every op run
// here -- then what comes on top
function compose(F) {
  const live = F.view && { proj: S.proj, path: S.path, rotate: S.rotate, zoom: S.zoom };   // (the frame's view while it is drawn: the map may have moved on)
  if (F.view) Object.assign(S, F.view);
  try { composeNow(F); } finally { if (live) Object.assign(S, live); }
}
function composeNow(F) {
  ctx.clearRect(0, 0, S.W, S.H); ctx.lineJoin = "miter";
  const t1 = performance.now(); let tm = 0, ti = 0;                  // (where the frame's time went: the drawn event tells)
  if (F.seq) for (const it of F.seq) { const t = performance.now(); if (it.main) { it.main(); tm += performance.now() - t; } else { const b = F.chunks[it.chunk].bitmap; if (b) { ctx.drawImage(b, 0, 0, S.W, S.H); b.close(); } ti += performance.now() - t; } }
  else for (const o of F.ops) { if (o.main) o.main(); else runOp(o); }
  const t2 = performance.now();
  if (F.after) F.after();
  const ms = performance.now() - F.t0;
  const detail = { ms, fast: F.fast, lv: F.lv, names: !F.fast || !!S.drag, wait: F.tAll ? F.tAll - F.t0 : t1 - F.t0, main: tm, images: ti, ops: t2 - t1, after: performance.now() - t2,
                   chunks: F.chunks?.map((c) => ({ cost: c.cost, ops: c.ops.length, ms: Math.round(c.ms), paint: Math.round(c.paint) })),
                   fallback: F.seq ? F.ops.filter((o) => o.main && !o.cost && (o.feats || o.arcs)).length : 0 };
  if (!F.fast && S.src) $("hint").textContent = `drawn in ${Math.round(ms)} ms (${["full", "small", "xsmall"][F.lv]}${painter ? `, ${painter.n} painters` : ""}) · ${HOW}`;
  canvas.dispatchEvent(new CustomEvent("drawn", { detail }));   // (a frame on the canvas: for whoever measures)
}
// the selection: an area of the map's own lines (a sea is water only, a range land only), a country, a lake -- filled
export function highlight(s) {
  if (s.cat === "river" || s.cat === "line" || s.cat === "point") return;
  ctx.beginPath(); S.path(s.geom); ctx.fillStyle = css("--hi-fill"); ctx.fill();
  ctx.strokeStyle = css("--hi"); ctx.lineWidth = 1.4; ctx.stroke();
}
// the selection's name (and a ring round a point)
export function mark(s) {
  const p = s.at && visible(s.at) ? S.proj(s.at) : null;
  if (!p) return;
  const [x, y] = p;
  if (s.cat === "point") { ctx.beginPath(); ctx.arc(x, y, 7, 0, 7); ctx.strokeStyle = css("--hi"); ctx.lineWidth = 2; ctx.stroke(); }
  ctx.font = "600 13px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.lineWidth = 3.5; ctx.strokeStyle = css("--bg"); ctx.fillStyle = css("--ink");
  const ty = s.cat === "point" ? y - 16 : y;
  ctx.strokeText(s.name, x, ty); ctx.fillText(s.name, x, ty);
}
