// city.js -- THE CITY DETAIL MAPS (build/citymaps.py: data/city/<wikidata>.txt, listed in data/city/index.csv with
// each one's window): zoomed in close on such a city (CITY_KM a pixel or less, the middle of the map in its window), its
// file is read -- only then, and only with the map at rest, as the roads' -- and drawn in the frame as the other line
// layers are (its rows handed to the module and the painters, its fills and strokes ops of the frame): its parks and
// woods, its water, its districts' borders, its main streets and their bridges, its S-Bahn, U-Bahn and main rail
// coloured by line, its airport; on top, with the names, its stations and the names of its districts, streets, parks,
// lakes and rivers. Within its window the map's own rivers, roads and railways (0.5 km of detail: a street's width
// off and more) give way to the city's (clipped out); everywhere else the map is as it was. Inside a window the map
// zooms in further than elsewhere (CITY_MAX_KM a pixel, not MAX_ZOOM's ~50 m). A city not looked at for RELEASE_MS
// is let go, as a layer is. A city map is one whole, whatever the network switches (the political map starts with
// the railways off, the geographical with the roads off: a city map without its trains or streets is no city map), and
// it shows the monuments and airports in it with the travel switch off too (view.js iconLayers).
import { S } from "./state.js";
import { ctx, css, dark, MAX_ZOOM, R_KM } from "./state.js";
import { parseLite } from "./lite.js";
import { thingsOf } from "./geom.js";
import { attachRows, releaseRows, freeTree } from "./wasm.js";
import { tree, query } from "./view.js";
import { place, writeName, nameAlong, SPACED, caps } from "./labels.js";
import { pxKm } from "./history.js";

export const CITY_KM = 0.08, CITY_MAX_KM = 0.004, RELEASE_MS = 3 * 60 * 1000;
let index = null;                                                    // (the cities with a detail map: wikidata, name, window)
const loaded = new Map();                                            // (wikidata -> a promise, then the city read: { T, L, trees, last })
fetch("data/city/index.csv").then((r) => r.ok ? r.text() : null).then((t) => {
  if (!t) return;
  index = d3.csvParse(t, (r) => ({ id: r.wikidata, name: r.name, win: [+r.w, +r.s, +r.e, +r.n] }));
}).catch(() => { });
// the city whose window holds the middle of the map (whatever the zoom), or null
export function cityAt(c = S.proj && S.proj.invert([S.W / 2, S.H / 2])) {
  if (!index || !S.proj) return null;
  if (!c || !isFinite(c[0])) return null;
  return index.find(({ win: [w, s, e, n] }) => c[0] >= w && c[0] <= e && c[1] >= s && c[1] <= n) ?? null;
}
// HOW CLOSE: in a city's window down to CITY_MAX_KM a pixel; elsewhere MAX_ZOOM -- or as close as the map already is (one
// that leaves a window zoomed in is not thrown back out by the next turn of the wheel)
export function zoomCap(at) {
  const base = S.proj.scale() / S.zoom;
  return cityAt(at) ? Math.max(MAX_ZOOM, R_KM / (CITY_MAX_KM * base)) : Math.max(MAX_ZOOM, at ? 0 : S.zoom);
}
// the city to draw in this frame: close enough, its file read (else asked for, at rest only, and drawn when it comes)
export function cityShown(fast, redraw) {
  if (pxKm() > CITY_KM) return null;
  const c = cityAt();
  if (!c) return null;
  const got = loaded.get(c.id);
  if (got?.L) { got.last = Date.now(); return { ...c, ...got }; }
  if (!got && !fast) loaded.set(c.id, read(c).then((r) => { if (r) { loaded.set(c.id, r); redraw(); } else loaded.delete(c.id); }));
  return null;
}
async function read(c) {
  const t = await fetch(`data/city/${c.id}.txt`).then((r) => r.ok ? r.text() : null).catch(() => null);
  if (!t) return null;
  while (S.moving || S.pinch || S.drag) await new Promise((ok) => setTimeout(ok, 150));   // (read with the map at rest: not into a pinch's frames)
  const T = parseLite(t), O = {}, L = {}, trees = {};
  for (const k in T.objects) { const o = T.objects[k]; O[k] = { kind: o.kind, n: o.n, rows: o.rows, geos: [o.g] }; attachRows(T, o.g, o.kind); L[k] = thingsOf(O, k); }
  for (const k of ["streets", "bridges", "rail", "waterways", "districts", "green", "water", "monuments"]) if (L[k]?.length) trees[k] = tree(L[k]);
  const pts = (name) => (T.tables[name] || []).map((p) => ({ ...p, at: [p.lon, p.lat] }));
  const clip = L.clip?.[0]?.geometry ?? null;                       // (the city's outline and its airport: GeoJSON, made once)
  const areas = new Set((L.monuments || []).map((f) => f.properties.wikidata));   // (the monuments drawn as areas: no icon of their own)
  return { T, O, L, trees, clip, areas, places: pts("places"), parks: pts("parks"), stations: pts("stations"), last: Date.now() };
}
export function releaseCities() {
  const now = Date.now();
  for (const [id, c] of loaded) if (c.L && now - c.last > RELEASE_MS) {
    for (const k in c.O) for (const g of c.O[k].geos) releaseRows(g);
    for (const k in c.trees) freeTree(c.trees[k]);
    loaded.delete(id);
  }
}
setInterval(releaseCities, 30000);

// ---- the frame -----------------------------------------------------------------------------------------------------
const STREETS = ["secondary", "primary", "trunk", "motorway"];      // (drawn in this order: the bigger over the smaller)
const INK = {
  light: { wood: "#9cc58a", park: "#b9dca4", water: "#a9cbe3", waterway: "#7fb0d6", airport: "#d6d3cc", district: "#8a6f8f", district2: "#a99aab",
           motorway: ["#c0601a", "#f0a050"], trunk: ["#b07f12", "#f6c85f"], primary: ["#bba04a", "#fbe7a6"], secondary: ["#b0aca2", "#ffffff"], bridge: "#4a4f57",
           u: "#1f5ba8", s: "#2e8b3e", r: "#4a4f57", monument: "#e3c6dc", monumentLine: "#a0558f", ink: "#2a3440", street: "#3a3f46", halo: "#ffffffd9", stationRing: "#2a3440", station: "#ffffff" },
  dark: { wood: "#2f4a2c", park: "#3a5634", water: "#24465f", waterway: "#3f78a3", airport: "#45474a", district: "#b79bbd", district2: "#7d6f80",
          motorway: ["#000000", "#c8762e"], trunk: ["#000000", "#a8892f"], primary: ["#111111", "#857a52"], secondary: ["#111111", "#6c7177"], bridge: "#000000",
          u: "#5b8fe0", s: "#55b865", r: "#c8ccd2", monument: "#4d3549", monumentLine: "#c784b8", ink: "#d9dee3", street: "#d0d4d8", halo: "#000000b3", stationRing: "#e8e8e8", station: "#22272c" },
};
const ink = () => INK[dark() ? "dark" : "light"];
// (how thick, by how close: 1 at CITY_KM a pixel, 2.4 at 10 m)
const thick = () => Math.min(2.6, Math.max(0.7, 0.7 + 0.45 * Math.log2(CITY_KM / pxKm())));
// (the rows in view: by the screen's own box -- the frame's boxes are padded by a degree at least, all of a city)
const screenBox = () => {
  const ll = [[0, 0], [S.W / 2, 0], [S.W, 0], [S.W, S.H / 2], [S.W, S.H], [S.W / 2, S.H], [0, S.H], [0, S.H / 2]].map((p) => S.proj.invert(p));
  if (ll.some((p) => !p || !isFinite(p[0]) || !isFinite(p[1]))) return null;
  const pad = 0.002, xs = ll.map((p) => p[0]), ys = ll.map((p) => p[1]);
  return [[Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad]];
};
const ids = (c, k, boxes) => c.trees[k] ? query(c.trees[k], screenBox() ?? boxes) : (c.L[k] || []).map((_, i) => i);
const secondaryShown = () => pxKm() < 0.07;
// the clip that keeps the map's own lines out of the city -- its outline and its airport, the file's @clip, so the map's
// roads and railways end where the city's begin (main thread, round the ops between it and the restore)
export function clipOut(c) {
  if (c.clip) { ctx.save(); ctx.beginPath(); ctx.rect(-10, -10, S.W + 20, S.H + 20); S.path(c.clip); ctx.clip("evenodd"); return; }
  const [w, s, e, n] = c.win, ring = [];
  for (let k = 0; k <= 8; k++) ring.push([w + (e - w) * k / 8, s]);
  for (let k = 0; k <= 8; k++) ring.push([e, s + (n - s) * k / 8]);
  for (let k = 0; k <= 8; k++) ring.push([e - (e - w) * k / 8, n]);
  for (let k = 0; k <= 8; k++) ring.push([w, n - (n - s) * k / 8]);
  ctx.save(); ctx.beginPath(); ctx.rect(-10, -10, S.W + 20, S.H + 20);
  ring.forEach((p, k) => { const q = S.proj(p); if (q) k ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
  ctx.closePath(); ctx.clip("evenodd");
}
// the areas, under the borders and lines: woods and parks, the airport, the water, the rivers and canals as lines, the districts' borders
export function cityAreas(c, boxes, fillAll, stroke, fast) {
  const I = ink(), L = c.L, t = thick();
  const by = (k, f) => ids(c, k, boxes).filter((i) => f(L[k][i].properties));
  if (L.green) { fillAll(L.green, by("green", (p) => p.kind === "wood"), I.wood); fillAll(L.green, by("green", (p) => p.kind === "park"), I.park); }
  if (L.airport) fillAll(L.airport, [0], I.airport);
  if (L.waterways) stroke(L.waterways, ids(c, "waterways", boxes), I.waterway, 1.2 * t);   // (a moving frame too: a river gone while the map moves -- the user, 2026-11-22)
  if (L.water) fillAll(L.water, ids(c, "water", boxes), I.water);
  if (L.monuments) { const m = ids(c, "monuments", boxes); fillAll(L.monuments, m, I.monument); if (!fast) stroke(L.monuments, m, I.monumentLine, 1); }
  if (L.districts) {
    const d = ids(c, "districts", boxes), F = L.districts;
    if (pxKm() < 0.05 && !fast) { ctx.setLineDash([2, 3]); stroke(F, d.filter((i) => F[i].properties.level === 2), I.district2, 0.7); ctx.setLineDash([]); }
    ctx.globalAlpha = 0.8; stroke(F, d.filter((i) => F[i].properties.level === 1), I.district, 1.3); ctx.globalAlpha = 1;
  }
}
// the lines, over the map's: the streets (casings, then fills, a class over the one below it -- each street one line; its
// bridges, @bridges, over all, cased dark), the railways
// (a moving frame: no casings -- half the strokes, and the pinch keeps up)
export function cityLines(c, boxes, stroke, fast) {
  const I = ink(), L = c.L, t = thick();
  if (L.streets) {
    const F = L.streets, all = ids(c, "streets", boxes);
    const shown = STREETS.filter((k) => k !== "secondary" || secondaryShown());
    const W = { motorway: 2.6, trunk: 2.3, primary: 1.9, secondary: 1.3 };
    const of = (F, all, k) => all.filter((i) => F[i].properties.class === k);
    if (!fast) for (const k of shown) stroke(F, of(F, all, k), I[k][0], W[k] * t + 1.4);
    for (const k of shown) stroke(F, of(F, all, k), I[k][1], W[k] * t);
    const B = L.bridges, bs = B ? ids(c, "bridges", boxes) : [];
    if (B && !fast) for (const k of shown) { stroke(B, of(B, bs, k), I.bridge, W[k] * t + 2.4); stroke(B, of(B, bs, k), I[k][1], W[k] * t); }
  }
  if (L.rail) {
    const F = L.rail, all = ids(c, "rail", boxes), by = {};
    ctx.setLineDash([5, 3]); stroke(F, all.filter((i) => F[i].properties.kind === "r"), I.r, 1.1 * t); ctx.setLineDash([]);
    for (const i of all) { const p = F[i].properties; if (p.kind !== "r") (by[`${p.kind}|${p.colour || I[p.kind]}`] ??= []).push(i); }
    for (const k of Object.keys(by).sort()) { const [kind, colour] = k.split("|"); stroke(F, by[k], colour, (kind === "s" ? 1.6 : 1.5) * t); }
  }
}
// ---- on top: the stations and the names ---------------------------------------------------------------------------
const visibleHere = (at) => { const q = S.proj(at); return q && q[0] > -20 && q[1] > -20 && q[0] < S.W + 20 && q[1] < S.H + 20 ? q : null; };
export function cityStations(c) {
  const I = ink(), km = pxKm(), t = thick();
  ctx.strokeStyle = I.stationRing; ctx.fillStyle = I.station;
  for (const s of c.stations) {
    if (s.rank === 3 && km > 0.05) continue;
    const q = visibleHere(s.at); if (!q) continue;
    const r = (s.rank === 1 ? 3.6 : s.rank === 2 ? 2.8 : 2.2) * Math.min(1.5, t);
    ctx.lineWidth = s.rank === 1 ? 1.6 : 1.2; ctx.beginPath(); ctx.arc(q[0], q[1], r, 0, 7); ctx.fill(); ctx.stroke();
  }
}
// the names, by importance: the main stations, the districts, the big streets, the other stations, the parks and lakes,
// the finer districts, the smaller streets, the rivers and canals
export function cityNames(c, placed, boxes) {
  const I = ink(), km = pxKm(), L = c.L;
  const station = (s) => {
    const q = visibleHere(s.at); if (!q) return;
    const size = s.rank === 1 ? 12 : 11, font = s.rank === 1 ? "600" : "500", text = s.name;
    ctx.font = `${font} ${size}px system-ui, sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    const w = ctx.measureText(text).width, dx = s.rank === 1 ? 7 : 5;
    const x = place(placed, q[0] + dx + w / 2, q[1], w, size) ? q[0] + dx         // (right of it, or else left)
      : place(placed, q[0] - dx - w / 2, q[1], w, size) ? q[0] - dx - w : null;
    if (x === null) return;
    ctx.lineWidth = 3; ctx.strokeStyle = I.halo; ctx.fillStyle = I.ink; ctx.strokeText(text, x, q[1]); ctx.fillText(text, x, q[1]);
  };
  const stations = c.stations;
  for (const s of stations) if (s.rank === 1 && km < 0.12) station(s);
  for (const p of c.places) if (p.level === 1 && km < 0.12 && visibleHere(p.at)) writeName(placed, caps(p.name), p.at, 11, 600, I.district, { spacing: SPACED(11), alpha: 0.9 });
  const streets = (classes) => {
    if (!L.streets) return;
    const F = L.streets, sel = ids(c, "streets", boxes).filter((i) => classes.includes(F[i].properties.class) && (F[i].properties.name || F[i].properties.ref));
    const text = (p) => p.class === "motorway" && p.ref ? p.ref : p.name || p.ref;
    ctx.font = `500 ${km < 0.015 ? 11 : 10}px system-ui, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.lineWidth = 3; ctx.strokeStyle = I.halo; ctx.fillStyle = I.street;
    nameAlong(placed, F, sel, 0, { text, key: text, size: km < 0.015 ? 11 : 10, gap: 400, offset: 0 });
  };
  if (km < 0.06) streets(["motorway", "trunk", "primary"]);
  for (const s of stations) if (s.rank === 2 && km < 0.05) station(s);
  for (const p of c.parks) if (visibleHere(p.at) && km < (p.ha > 150 ? 0.08 : p.ha > 50 ? 0.04 : 0.02))
    writeName(placed, p.name, p.at, 11, "italic 500", p.kind === "lake" ? css("--water-label") : (dark() ? "#9bd08a" : "#2f6b2a"));
  for (const p of c.places) if (p.level === 2 && km < 0.035 && visibleHere(p.at)) writeName(placed, p.name, p.at, 10, "italic 400", I.district2 === "#7d6f80" ? "#b5a8b8" : "#6f5a74");
  for (const s of stations) if (s.rank === 3 && km < 0.022) station(s);
  if (km < 0.025) streets(["secondary"]);
  if (L.waterways && km < 0.08) {
    ctx.font = "italic 11px Georgia, serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.lineWidth = 3; ctx.strokeStyle = I.halo; ctx.fillStyle = css("--water-label");
    nameAlong(placed, L.waterways, ids(c, "waterways", boxes), 0, { text: (p) => p.name, key: (p) => p.name, size: 11, gap: 450 });
  }
}
