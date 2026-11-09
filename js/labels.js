// labels.js -- the names on the map: countries, states, areas, cities, points, rivers along their flow; the point tiers by zoom
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { bioLayer } from "./style.js";
import { ctx, css, on, dark } from "./state.js";
import { shape, Map0, B0 } from "./geom.js";
import { histOn } from "./history.js";

export function place(boxes, x, y, w, h) {
  const b = [x - w / 2 - 2, y - h / 2 - 1, x + w / 2 + 2, y + h / 2 + 1];
  if (b[0] < 0 || b[1] < 0 || b[2] > S.W || b[3] > S.H) return false;
  for (const o of boxes) if (b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]) return false;
  boxes.push(b); return true;
}
// a name centred on its place, with a halo -- unless it would overlap a name placed before. `spacing`: px between the
// letters (a country's spaced capitals); `alpha`: how far it has faded in (fadeIn)
export function writeName(boxes, text, at, size, font, fill, { spacing = 0, alpha = 1 } = {}) {
  if (alpha < 0.15) return;                                         // (too faint to read: it takes no room from another)
  ctx.font = `${font} ${size}px system-ui, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.letterSpacing = `${spacing}px`;
  const [x, y] = S.proj(at), w = ctx.measureText(text).width;
  if (place(boxes, x, y, w, size)) {
    ctx.lineWidth = 3; ctx.strokeStyle = dark() ? "#000000aa" : "#ffffffcc"; ctx.fillStyle = fill; ctx.globalAlpha = alpha;
    ctx.strokeText(text, x, y); ctx.fillText(text, x, y); ctx.globalAlpha = 1;
  }
  ctx.letterSpacing = "0px";
}
// THE NAMES' HIERARCHY: a country (or a state of its day) in SPACED CAPITALS, the states and provinces within one in
// mixed case, smaller -- and these FADE IN as you come closer (from the zoom where they first fit, full a step on: area
// over the shown minimum, 1 to 2), so they never crowd the countries' names
export const SPACED = (size) => size * 0.16, caps = (s) => s.toLocaleUpperCase();
export const fadeIn = (area, min) => Math.min(1, Math.max(0, area / min - 1));
export const STATE_KM2 = 4e6;                                              // (a state's or province's name shown from where its km² reach this over the zoom squared)
// the realms' names, or the ecoregions' (the big ones first, more of them the closer in)
export function bioLabels(boxes) {
  const bl = bioLayer(), F = B0[bl === "biomes" ? "realms" : bl];
  if (bl === "biomes") return;                                      // (a biome is everywhere in pieces: its colour says it, the legend names it)
  const min = bl === "realms" ? 0 : 4e6 / (S.zoom * S.zoom);
  for (const f of [...F].sort((a, b) => (b.properties.area_km2 || 0) - (a.properties.area_km2 || 0))) {
    const p = f.properties;
    if (!p.label || (p.area_km2 || Infinity) < min || !visible(p.label) || (S.sel && S.sel.feats.includes(f))) continue;
    if (bl === "realms") writeName(boxes, caps(p.name), p.label, 14, 600, css("--ink"), { spacing: SPACED(14) }); else writeName(boxes, p.name, p.label, 11, 400, css("--ink"));
  }
}
// the day's states' names (the biggest first, more of them the closer in): a state's in spaced capitals; then a
// culture's, grey; then -- with layer 3 -- the provinces' and dependencies' within a state (an owner's: the Duchy of
// Swabia in the Empire, a colony), smaller, in italics, fading in from closer in
export function histLabels(boxes) {
  const P = S.H0.periods, min = 3e6 / (S.zoom * S.zoom), area = (i) => P[i].area_km2 || 0;
  const all = [...histOn().countries].sort((a, b) => area(b) - area(a)), ok = (i) => P[i].label && visible(P[i].label) && !(S.sel && S.sel.period === i);
  for (const i of all) { const p = P[i];
    if (p.owner == null && p.status !== "culture" && area(i) >= min && ok(i)) writeName(boxes, caps(p.name), p.label, 11, 600, css("--ink"), { spacing: SPACED(11) }); }
  for (const i of all) { const p = P[i];
    if (p.owner == null && p.status === "culture" && area(i) >= min && ok(i)) writeName(boxes, p.name, p.label, 10, "italic 400", css("--dim")); }
  if (on("regions")) for (const i of all) { const p = P[i], m = STATE_KM2 / (S.zoom * S.zoom);
    if (p.owner != null && area(i) >= m && ok(i)) writeName(boxes, p.name, p.label, 10, "italic 400", css("--ink"), { alpha: fadeIn(area(i), m) }); }
}
// the countries' names in spaced capitals, then their states' (with layer 3) in mixed case, fading in: the biggest
// first, more of them the closer in
export function unitLabels(boxes) {
  const L = Map0, by = (a, b) => (b.properties.area_km2 || 0) - (a.properties.area_km2 || 0);
  const write = (F, min, size, font, fill, up) => { for (const f of F) { const p = f.properties;
    if (p.label && (p.area_km2 || 0) >= min && visible(p.label) && !(S.sel && S.sel.feats.includes(f)))
      writeName(boxes, up ? caps(p.name) : p.name, p.label, size, font, fill, up ? { spacing: SPACED(size) } : { alpha: fadeIn(p.area_km2 || 0, min) }); } };
  write(unitsBySize.countries ??= [...L.countries].sort(by), 6e5 / (S.zoom * S.zoom), 11, 600, css("--ink"), true);
  if (on("regions")) write(unitsBySize.regions ??= [...L.regions].sort(by), STATE_KM2 / (S.zoom * S.zoom), 11, 400, css("--ink"), false);   // (upright, full ink: a grey italic was lost on the fills)
}
export const unitsBySize = {};
// the areas' names: the biggest first, more of them the closer in
export function areaLabels(boxes) {
  const dk = dark(), maxRank = Math.log2(S.zoom) * 1.6 + 1.2, A = Map0.areas;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (const f of A) {
    const p = f.properties;
    if ((p.rank ?? 9) > maxRank || !p.label || !visible(p.label) || (S.sel && S.sel.feats.includes(f))) continue;
    const water = p.mask === "water", big = p.kind === "ocean" || p.kind === "continent";
    const size = big ? 14 : p.rank <= 1 ? 12 : 11;
    ctx.font = `italic ${big ? 600 : 400} ${size}px Georgia, serif`;
    const text = big ? p.name.toUpperCase() : p.name;
    const [x, y] = S.proj(p.label), w = ctx.measureText(text).width;
    if (!place(boxes, x, y, w, size)) continue;
    ctx.lineWidth = 3; ctx.strokeStyle = water ? css("--sea") : css("--land");
    ctx.fillStyle = water ? css("--water-label") : css("--land-label");
    ctx.globalAlpha = dk ? 0.9 : 0.85; ctx.strokeText(text, x, y); ctx.fillText(text, x, y); ctx.globalAlpha = 1;
  }
}
// the cities' dots: the bigger, the larger
export function cityDots(ids) {
  ctx.fillStyle = dark() ? "#e8c46a" : "#b03a2e";
  for (const i of ids) {
    const f = S.src.cities.features[i];
    if (!visible(f.geometry.coordinates)) continue;
    const [x, y] = S.proj(f.geometry.coordinates), r = 1 + Math.sqrt(f.properties.population / 1e6) * 0.75;   // (Tokyo's 6 px, a city of 1 million 1.75)
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
  }
}
// the cities' names: of those given, where one does not overlap another
export function cityLabels(boxes, ids) {
  ctx.font = "11px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.lineWidth = 3; ctx.strokeStyle = css("--land"); ctx.fillStyle = css("--ink");
  for (const i of ids) {                                          // (the cities are sorted biggest first)
    const f = S.src.cities.features[i], p = f.properties;
    if (!visible(f.geometry.coordinates)) continue;
    const [x, y] = S.proj(f.geometry.coordinates), t = p.name, w = ctx.measureText(t).width;
    if (!place(boxes, x + 5 + w / 2, y, w, 11)) continue;
    ctx.strokeText(t, x + 5, y); ctx.fillText(t, x + 5, y);
  }
}
// the monuments', the peaks' (capes', waterfalls') and the airports' names: from LABEL_ZOOM times the zoom a point
// shows from, the best known first (its tier's measure), beside it where they overlap no name placed before -- the
// cities' first; an airport without its "International Airport"
export const LABEL_ZOOM = 1.6;
export const pointName = (layer, p) => layer === "airports" ? p.name.replace(/\b(international\s+)?airport\b/gi, "").replace(/\s{2,}/g, " ").trim() || p.name : p.name;
export function pointLabels(boxes, layer, ids, ink) {
  const F = S.src[layer].features, by = (i) => TIERS[layer].by(F[i].properties, i);
  const ok = ids.filter((i) => S.zoom >= shownFrom(layer, i) * LABEL_ZOOM && F[i].properties.name).sort((a, b) => by(b) - by(a) || a - b);
  ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
  ctx.lineWidth = 3; ctx.strokeStyle = css("--land");
  for (const i of ok) {
    const [x, y] = S.proj(F[i].geometry.coordinates), t = pointName(layer, F[i].properties), w = ctx.measureText(t).width;
    const dx = 4 + 3 * (SIZE[F[i].properties.level] ?? 1);
    if (!place(boxes, x + dx + w / 2, y, w, 10)) continue;
    ctx.fillStyle = typeof ink === "function" ? ink(i) : ink;
    ctx.strokeText(t, x + dx, y); ctx.fillText(t, x + dx, y);
  }
}
// the rivers' names ALONG THEIR FLOW, from close in (the longer the river, the farther out): letter by letter beside a
// stretch of the line as drawn that runs nearly straight, reading left to right -- again every RIVER_GAP px of a
// river, wherever it overlaps no name placed before
export const RIVER_NAMES = [[1000, 4], [300, 6], [100, 9], [0, 12]];     // (a river's km drawn -> the zoom its name shows from)
export const RIVER_GAP = 350;
export function riverLabels(boxes, F, ids, lv) {
  const from = (km) => RIVER_NAMES.find(([min]) => km >= min)[1], size = 11, near = new Map();   // (a river -> its names on screen)
  const ok = ids.filter((i) => F[i].has(lv) && F[i].properties.name && S.zoom >= from(F[i].properties.river_km || 0))
    .sort((a, b) => (F[b].properties.river_km || 0) - (F[a].properties.river_km || 0));
  ctx.font = `italic ${size}px Georgia, serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.lineWidth = 3; ctx.strokeStyle = css("--land"); ctx.fillStyle = css("--water-label");
  for (const i of ok) {
    const p = F[i].properties, k = p.river || p.name, tw = ctx.measureText(p.name).width, w = tw + 10;
    const g = shape(F[i], lv), runs = [];
    for (const line of g.type === "LineString" ? [g.coordinates] : g.coordinates) {   // (the line on screen: its runs of visible points)
      let r = [];
      for (const c of line) { const q = visible(c) && S.proj(c); if (q) r.push(q); else { if (r.length > 1) runs.push(r); r = []; } }
      if (r.length > 1) runs.push(r);
    }
    for (const r of runs) {
      const s = [0]; for (let j = 1; j < r.length; j++) s.push(s[j - 1] + Math.hypot(r[j][0] - r[j - 1][0], r[j][1] - r[j - 1][1]));
      const at = (d) => { let lo = 0, hi = r.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (s[m] <= d) lo = m; else hi = m; }
        const t = s[hi] > s[lo] ? (d - s[lo]) / (s[hi] - s[lo]) : 0; return [r[lo][0] + (r[hi][0] - r[lo][0]) * t, r[lo][1] + (r[hi][1] - r[lo][1]) * t]; };
      for (let c = w / 2; c <= s[s.length - 1] - w / 2; c += w / 3) {
        const a = at(c - w / 2), b = at(c + w / 2), m = at(c);
        if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 0.94 * w) continue;                  // (a bend: the letters would crowd)
        if ((near.get(k) || []).some((o) => Math.hypot(o[0] - m[0], o[1] - m[1]) < RIVER_GAP)) continue;
        // (on a straight line, beside the river where it runs straight under the whole name: bent letter by letter
        //  along it, a bend in the middle of a word made it unreadable)
        const cx = b[0] - a[0], cy = b[1] - a[1], cl = Math.hypot(cx, cy), off = (q) => Math.abs((q[0] - a[0]) * cy - (q[1] - a[1]) * cx) / cl;
        let dev = off(m);
        for (let j = 0; j < r.length; j++) if (s[j] > c - w / 2 && s[j] < c + w / 2) dev = Math.max(dev, off(r[j]));
        if (dev > size * 0.3) continue;
        const dir = cx >= 0 ? 1 : -1, ang = Math.atan2(dir * cy, dir * cx);              // (left to right, whichever way it flows)
        const ux = Math.cos(ang), uy = Math.sin(ang), x = (a[0] + b[0]) / 2 + uy * size * 0.75, y = (a[1] + b[1]) / 2 - ux * size * 0.75;
        const bx = [];                                                                   // (its boxes: a letter's width apart along it)
        for (let d = -tw / 2 + size / 2; d < tw / 2; d += size) bx.push([x + ux * d - size / 2, y + uy * d - size / 2, x + ux * d + size / 2, y + uy * d + size / 2]);
        if (bx.some((q) => q[0] < 0 || q[1] < 0 || q[2] > S.W || q[3] > S.H || boxes.some((o) => q[0] < o[2] && q[2] > o[0] && q[1] < o[3] && q[3] > o[1]))) continue;
        boxes.push(...bx); (near.get(k) || near.set(k, []).get(k)).push(m);
        ctx.save(); ctx.translate(x, y); ctx.rotate(ang); ctx.strokeText(p.name, 0, 0); ctx.fillText(p.name, 0, 0); ctx.restore();
      }
    }
  }
}
// WHICH POINTS FROM WHICH ZOOM: each point layer's points in TIERS by a measure -- a city's people (a country's
// capital's counted three times, so it comes a tier sooner), a monument's level (by its visitors a year: build/points.py),
// a peak's rank, an airport's level (by its passengers), an event's fame among the day's -- and the zoom each tier shows from (1:
// the whole globe; 4 about a continent, 8 a big country). A point is shown from the zoom of the first tier its measure
// reaches; drawn, tipped and named alike. (A rank is negated: the first is the most.)
export const TIERS = {
  cities:    { by: (p) => p.population * (p.capital === "country" ? 3 : 1), tiers: [[10e6, 1], [3e6, 2.5], [1e6, 5], [300e3, 8], [0, 14]] },
  monuments: { by: (p) => -(p.level ?? 3), tiers: [[-1, 5], [-2, 9], [-Infinity, 15]] },
  nature:    { by: (p) => -(p.rank ?? 9), tiers: [[-2, 4], [-4, 6], [-6, 10], [-Infinity, 16]] },
  airports:  { by: (p) => -(p.level ?? 3), tiers: [[-1, 4], [-2, 7], [-Infinity, 11]] },
  events:    { by: (p, i) => -histOn().events.get(i), tiers: [[-15, 4], [-60, 6], [-250, 10], [-Infinity, 18]] },   // (not of the day: NaN, none)
};
export function shownFrom(layer, i) {
  const t = TIERS[layer], v = t.by(S.src[layer].features[i].properties, i);
  for (const [min, z] of t.tiers) if (v >= min) return z;
  return Infinity;
}
export const shown = (layer, i) => S.zoom >= shownFrom(layer, i);
// ...and a monument's or an airport's symbol drawn by its level: the first the largest
export const SIZE = { 1: 1.35, 2: 1.1, 3: 0.85 };
export const NATURAL = new Set(["national park", "protected area", "waterfall", "cave", "landform", "garden"]);
export const natural = (p) => NATURAL.has(p.kind);
// ...and the main lines in three tiers (build/roadnet.py: a road or railway by the length of its way on through the
// junctions -- a motorway across a continent, a ring road, a spur --, a high-speed line first, a pipeline by its
// network's length): the zoom each tier shows from; none further out than the first
export const LINE_TIERS = [3, 5, 8], ROAD_TIERS = [4, 7, 11];   // (the first-class roads: closer in than the motorways)
// (a point on the far side of the globe is not drawn)
export const visible = (p) => { const c = S.proj.clipAngle && S.proj.clipAngle(); return !c || d3.geoDistance(p, [-S.rotate[0], -S.rotate[1]]) < c * Math.PI / 180; };
