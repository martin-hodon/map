// plates.js -- THE TECTONIC PLATES (layer 16): Peter Bird's PB2002 model (data/plates.json, build/plates.py) -- the
// boundaries coloured by what the plates do there (pulled apart, sliding past, pushed together, one going under the
// other: teeth on the upper plate's side), the plates' names, a click's plate and nearby boundary, the plates found by
// name. One small file (350 kB), read once, after the rest; drawn on the main thread (6,000 points: a millisecond or two),
// not by the painters.
import { S, ctx, on, dark, fmt, make, $ } from "./state.js";
import { place, visible } from "./labels.js";
import { addToIndex } from "./search.js";

// Bird's classes, by what they do: the colour (light, dark), the width (times the zoom's), and what is said of them
export const KINDS = {
  ridge: { light: "#d2452f", dark: "#ff7a5c", w: 1.6, name: "spreading ridge", say: "pulling apart" },
  rift: { light: "#d2452f", dark: "#ff7a5c", w: 1.3, dash: [5, 3], name: "continental rift", say: "pulling apart" },
  transform: { light: "#2f8f5b", dark: "#5fd08a", w: 1.1, name: "transform fault", say: "sliding past each other" },
  collision: { light: "#8a4bc2", dark: "#b88cff", w: 1.6, name: "collision zone", say: "pushed together" },
  subduction: { light: "#1f5fbf", dark: "#6aa8ff", w: 1.6, name: "subduction zone", say: "one going under the other" },
};
const KIND_OF = { OSR: "ridge", CRB: "rift", OTF: "transform", CTF: "transform", OCB: "collision", CCB: "collision", SUB: "subduction" };
const CLASS_NAME = { OSR: "oceanic spreading ridge", CRB: "continental rift", OTF: "oceanic transform fault", CTF: "continental transform fault",
  OCB: "oceanic convergent boundary", CCB: "continental collision zone", SUB: "subduction zone" };

export const P = { plates: null, bounds: null, byCode: new Map() };
let loading = null;
// (read once, whatever the layer: the plates are found by name with it off; drawn when it comes, if it is on)
export function loadPlates(redraw) {
  return loading ??= fetch("data/plates.json").then((r) => r.ok ? r.json() : null).catch(() => null).then((d) => {
    if (!d) return null;
    P.plates = d.plates.map(([code, name, km2, label, geometry]) => ({ type: "Feature", properties: { code, name, km2, label }, geometry }));
    for (const f of P.plates) P.byCode.set(f.properties.code, f);
    P.bounds = d.bounds.map(([id, a, b, cls, over, speed, open, slide, km, flat]) => {
      const pts = []; for (let i = 0; i < flat.length; i += 2) pts.push([flat[i], flat[i + 1]]);
      return { type: "Feature", properties: { id, a, b, cls, kind: KIND_OF[cls], over, speed, open, slide, km }, geometry: { type: "LineString", coordinates: pts } };
    });
    // (each kind's lines as one MultiLineString: one path a kind a frame)
    P.byKind = {};
    for (const f of P.bounds) (P.byKind[f.properties.kind] ??= { type: "MultiLineString", coordinates: [] }).coordinates.push(f.geometry.coordinates);
    for (const f of P.plates) addToIndex(plateEntry(f));
    if (on("plates")) redraw?.();
    return P;
  });
}
const plateName = (code) => P.byCode.get(code)?.properties.name ?? code;

// ---- the drawing (a step of the frame, after the lines and before the names) ----------------------------------------
export function drawPlates() {
  if (!P.bounds) return;
  const dk = dark(), lw = Math.min(1.6, 0.8 + 0.3 * Math.log2(S.zoom + 1));
  ctx.save(); ctx.lineJoin = "round"; ctx.lineCap = "round";
  for (const k of ["transform", "rift", "ridge", "collision", "subduction"]) {
    const K = KINDS[k], g = P.byKind[k]; if (!g) continue;
    ctx.beginPath(); S.path(g);
    ctx.setLineDash(K.dash ?? []); ctx.strokeStyle = dk ? K.dark : K.light; ctx.lineWidth = K.w * lw; ctx.globalAlpha = 0.9; ctx.stroke();
  }
  ctx.setLineDash([]); ctx.globalAlpha = 0.9;
  ctx.fillStyle = dk ? KINDS.subduction.dark : KINDS.subduction.light;
  for (const f of P.bounds) if (f.properties.over) teeth(f.geometry.coordinates, f.properties.over, 4 + 2 * lw);
  ctx.restore();
}
// a subduction zone's teeth: a small triangle every `gap` pixels along the line as drawn, on the upper plate's side
// (`over` 1: left of the line as it runs -- Bird's plate a --, -1: right). Measured on the screen, so as many at
// every zoom; a piece on the globe's far side, or cut by the projection's edge, gets none.
function teeth(pts, over, size) {
  const gap = size * 3.2;
  let prev = null, carry = gap / 2;
  ctx.beginPath();
  for (const q of pts) {
    const p = visible(q) ? S.proj(q) : null;
    if (p && prev) {
      const dx = p[0] - prev[0], dy = p[1] - prev[1], len = Math.hypot(dx, dy);
      if (len > 0 && len < 200) {                                   // (a jump across the map's edge: no teeth)
        const ux = dx / len, uy = dy / len, nx = uy * over, ny = -ux * over;   // (left of travel on the screen: north of an eastward line)
        for (let t = carry; t < len; t += gap) {
          const x = prev[0] + ux * t, y = prev[1] + uy * t;
          ctx.moveTo(x - ux * size * 0.6, y - uy * size * 0.6); ctx.lineTo(x + nx * size, y + ny * size); ctx.lineTo(x + ux * size * 0.6, y + uy * size * 0.6); ctx.closePath();
        }
        carry = ((carry - len) % gap + gap) % gap;
      }
    }
    prev = p;
  }
  ctx.fill();
}
// the plates' names, the big ones from afar, the small closer in (an area to a zoom: the 13 biggest at the start)
export function plateLabels(placed) {
  if (!P.plates) return;
  const dk = dark(), min = 1.5e7 / (S.zoom * S.zoom);
  ctx.save(); ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (const f of [...P.plates].sort((a, b) => b.properties.km2 - a.properties.km2)) {
    const { name, km2, label } = f.properties;
    if (km2 < min || !visible(label) || S.sel?.feats?.includes(f)) continue;
    const big = km2 > 4e7, size = big ? 13 : 11, text = name.toUpperCase();
    ctx.font = `${big ? 700 : 600} ${size}px system-ui, sans-serif`; ctx.letterSpacing = big ? "2px" : "1px";
    const [x, y] = S.proj(label), w = ctx.measureText(text).width;
    if (!place(placed, x, y, w, size)) continue;
    ctx.lineWidth = 3; ctx.strokeStyle = dk ? "#000a" : "#fffb"; ctx.fillStyle = dk ? "#e0b9a8" : "#8c3b26";
    ctx.globalAlpha = 0.85; ctx.strokeText(text, x, y); ctx.fillText(text, x, y); ctx.globalAlpha = 1;
  }
  ctx.letterSpacing = "0px"; ctx.restore();
}

// ---- found by a click, or by name --------------------------------------------------------------------------------------
function plateEntry(f) {
  const { code, name, km2, label } = f.properties, n = new Set(P.bounds.filter((b) => b.properties.a === code || b.properties.b === code).map((b) => b.properties.a === code ? b.properties.b : b.properties.a));
  const edge = { type: "MultiLineString", coordinates: P.bounds.filter((b) => b.properties.a === code || b.properties.b === code).map((b) => b.geometry.coordinates) };
  return { cat: "plate", layer: "plates", name, kind: "tectonic plate", feats: [f], edge, at: label, weight: km2 / 100,   // (below the ocean of its name: search.js THE WEIGHTS)
           info: [`${fmt(km2)} km²`, `borders ${n.size} plates: ${[...n].map(plateName).map((s) => s.replace(/ Plate$/, "")).join(", ")}`] };
}
// a boundary: all its runs (Bird's identifier) as one, what happens at the run clicked said first
function boundaryEntry(run) {
  const p = run.properties, all = P.bounds.filter((b) => b.properties.id === p.id), km = all.reduce((s, b) => s + b.properties.km, 0);
  const A = plateName(p.a), B = plateName(p.b);
  const what = p.cls === "SUB" ? `the ${p.over > 0 ? B : A} goes under the ${p.over > 0 ? A : B}` : KINDS[p.kind].say;
  const rate = p.kind === "transform" ? Math.abs(p.slide) : p.kind === "ridge" || p.kind === "rift" ? Math.max(0, p.open) : Math.max(0, -p.open);
  return { cat: "line", layer: "plates", name: `${A.replace(/ Plate$/, "")}–${B.replace(/ Plate$/, "")} boundary`, kind: CLASS_NAME[p.cls], feats: all,
           info: [`${what}, ${rate.toFixed(rate < 10 ? 1 : 0)} mm a year here (${p.speed.toFixed(0)} mm a year in all)`, `${fmt(km)} km long`] };
}
// what a click finds: the plate under it, and the boundary within `px` pixels (the nearest)
export function platesAt(ll, at, px = 8) {
  if (!P.plates || !on("plates")) return [];
  const hits = [], plate = P.plates.find((f) => d3.geoContains(f, ll));
  let best = px, near = null;
  for (const f of P.bounds) {
    let prev = null;
    for (const q of f.geometry.coordinates) {
      const p = visible(q) ? S.proj(q) : null;
      if (p && prev) { const d = segDist(at, prev, p); if (d < best) { best = d; near = f; } }
      prev = p;
    }
  }
  if (near) hits.push(boundaryEntry(near));
  if (plate) hits.push(plateEntry(plate));
  return hits;
}
function segDist([x, y], [x0, y0], [x1, y1]) {
  const dx = x1 - x0, dy = y1 - y0, l2 = dx * dx + dy * dy, t = l2 ? Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / l2)) : 0;
  return Math.hypot(x - x0 - t * dx, y - y0 - t * dy);
}

// the key under the layer's box, while it is on
export function platesKey() {
  const el = $("plates-key"); if (!el) return;
  el.hidden = !on("plates");
  if (el.childElementCount) return;
  const dk = dark();
  for (const k of ["ridge", "transform", "collision", "subduction"]) {
    const K = KINDS[k], c = dk ? K.dark : K.light;
    el.append(make("span", { innerHTML: `<i style="background:${c}"></i>${k === "subduction" ? "subduction ▲ (teeth on the upper plate)" : K.name}` }));
  }
  el.append(make("span", { textContent: "dashed: a rift in a continent" }));
}
