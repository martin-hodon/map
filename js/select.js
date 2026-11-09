// select.js -- selecting: the selection, the flight to it, what is under a click
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { mode } from "./style.js";
import { $, trees, index, GAME_ZOOM, MAX_ZOOM, fmt } from "./state.js";
import { setup, eachPoint, Map0 } from "./geom.js";
import { dayText, showDay, histDay, setDay, histOn, histFeature, pxKm } from "./history.js";
import { query, draw } from "./view.js";
import { visible } from "./labels.js";
import { LAYERS, FILE_OF, layerLoad, inSpan } from "./data.js";
import { norm, collect } from "./search.js";
import { flagCode, flagSvg } from "./flags.js";
import { game, bareGame } from "./groups.js";
import { showResults, modeChanged } from "./ui.js";

// ---- selecting: highlight, fly there, say what it is ---------------------------------------------------------------
// the selection goes with the panel's x, with the search box emptied (its own x, or Escape in it), or the link cleared
export function clearSel() {
  S.sel = null; $("info").style.display = "none"; $("q").value = ""; S.found = []; showResults();
  history.replaceState(null, "", location.pathname + location.search); draw();
}
export function select(e) {
  const file = FILE_OF[e.layer];
  if (file && !LAYERS[file].ready) return void layerLoad(file).then(() => LAYERS[file].ready && select(e));   // (let go: read again first)
  if (file) LAYERS[file].last = Date.now();
  if (e.span) {                                                     // (a country-period: on the historical map, on a day of its span)
    if (mode() !== "history") { $("mode").value = "history"; modeChanged(false); }
    if (!inSpan(e)) setDay(e.span[0]);
    if (e.period != null) { e.feats = histFeature(e.period); if (!e.feats.length) e.feats = [{ type: "Feature", geometry: { type: "Point", coordinates: e.at } }]; }
  }
  S.sel = { ...e, geom: collect(e.feats), at: e.at || d3.geoCentroid(collect(e.feats)) };
  const info = $("info");
  info.style.display = "block";
  info.innerHTML = "";
  const close = Object.assign(document.createElement("button"), { textContent: "×", title: "Clear the selection" });
  close.onclick = clearSel;
  const h = Object.assign(document.createElement("h2"), { textContent: e.name });
  const k = Object.assign(document.createElement("div"), { className: "kind", textContent: [e.kind, ...(e.info || [])].filter(Boolean).join(" · ") });
  info.append(close, h, k);
  if (e.alt && norm(e.alt) !== norm(e.name)) info.append(Object.assign(document.createElement("div"), { className: "kind", textContent: e.alt }));
  const fc = flagCode(e);
  if (fc && S.flagLib?.has(fc)) info.append(Object.assign(document.createElement("a"), { className: "flags", href: "flags.html#" + fc, target: "_blank",
    title: `${e.name}: its flag${S.flagLib.has(fc + "-arms") ? " and coat of arms" : ""}${e.span ? ` on ${showDay(inSpan(e) ? histDay() : e.span[0])}` : ""} (simplified; all of them: flags.html)`, innerHTML: flagSvg(fc, 40) + flagSvg(fc + "-arms", 48) }));
  history.replaceState(null, "", "#find=" + encodeURIComponent(e.name) + ($("proj").selectedIndex ? "&proj=" + encodeURIComponent($("proj").value) : "") + (e.span ? "&date=" + encodeURIComponent(histDay()) : ""));
  fly(S.sel);
}
export function fly(s) {
  let span = 0;
  if (s.cat !== "point") {
    const [[w, so], [ea, n]] = d3.geoBounds(s.geom);
    const dlon = ((ea - w) + 360) % 360 || 360;
    span = Math.max(n - so, dlon * Math.cos(((n + so) / 2) * Math.PI / 180));
  }
  const toZoom = s.cat === "point" ? Math.max(S.zoom, 6) : bareGame() ? Math.max(1, Math.min(60, 60 / Math.max(span, 0.02))) : game.open ? Math.max(1, Math.min(GAME_ZOOM, 60 / Math.max(span, 0.5)))
                                                       : Math.max(1, Math.min(MAX_ZOOM, 110 / Math.max(span, 0.5)));
  const toRot = [-s.at[0], Math.max(-80, Math.min(80, -s.at[1])), 0];
  const r0 = S.rotate.slice(), z0 = S.zoom, t0 = performance.now(), T = 700;
  const d = ((toRot[0] - r0[0] + 540) % 360) - 180;                  // (the short way round)
  const step = (t) => {
    const k = Math.min(1, (t - t0) / T), e = d3.easeCubicInOut(k);
    S.rotate = [r0[0] + d * e, r0[1] + (toRot[1] - r0[1]) * e, 0];
    S.zoom = Math.exp(Math.log(z0) + (Math.log(toZoom) - Math.log(z0)) * e);
    setup(); draw(k < 1);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
// ---- what is here (a click) ----------------------------------------------------------------------------------------
export function identify(e) {
  const ll = S.proj.invert([e.clientX, e.clientY]);
  if (!ll || !isFinite(ll[0]) || !visible(ll)) return;
  identifyAt(ll, [e.clientX, e.clientY]);
}
export function identifyAt(ll, px) {
  const at = [[ll[0], ll[1], ll[0], ll[1]]];
  const byLayer = (layer) => { const ids = new Set(query(trees[layer], at)); return index.filter((x) => x.layer === layer && x.ids.some((i) => ids.has(i))); };
  const inside = (x) => x.feats.some((f) => f.has() && d3.geoContains(f, ll));
  const hits = [];
  const country = byLayer("countries").find(inside), region = byLayer("regions").find(inside), lake = byLayer("lakes").find(inside);
  const L0 = Map0, onLand = !lake && (!!country || query(trees.land, at).some((i) => L0.land[i].has() && d3.geoContains(L0.land[i], ll)));
  for (const x of [country, region, lake]) if (x) hits.push(x);
  if (S.src.bio && !lake) for (const l of ["ecoregions", "biomes", "realms"]) { const x = byLayer(l).find(inside); if (x) hits.push(x); }
  if (S.src.hist && mode() === "history" && !lake) {                // (the region here, and its state that day)
    const r = query(trees.hregions, at).find((r) => d3.geoContains(S.H0.regions[r], ll));
    if (r != null) {
      const p = S.H0.regions[r].properties, pi = histOn().of[r], name = (s) => { const i = S.H0.byState.get(s); return i ? S.H0.periods[i[0]].name : "nobody"; };
      const { start, from, state } = S.H0.held, owners = []; for (let k = start[r]; k < start[r + 1]; k++) owners.push(`${state[k] < 0 ? "nobody" : name(state[k])} from ${showDay(dayText(from[k]))}`);
      hits.unshift({ cat: "history", name: p.name || `region ${p.id}`, kind: "historical region", feats: [S.H0.regions[r]], at: p.label,
                     info: [p.admin, p.country, p.area_km2 ? `${fmt(p.area_km2)} km²` : null, owners.length > 12 ? `${owners.length} owners, the last: ${owners.slice(-12).join(", ")}` : owners.join(", ")] });
      const x = pi >= 0 && index.find((x) => x.period === pi);
      if (x) hits.unshift(x);
    }
  }
  const areas = byLayer("areas").filter((x) => x.feats.length === 1 && (x.mask === "water") !== onLand && inside(x));   // (a sea has no holes for its islands)
  areas.sort((a, b) => a.weight - b.weight);                        // (the smallest first: a gulf before its ocean)
  hits.push(...areas);
  // rivers passing within 8 pixels
  const r = 8 * pxKm() / 111, c = Math.max(0.1, Math.cos(ll[1] * Math.PI / 180)), near = [];
  const cand = new Set(query(trees.rivers, [[ll[0] - r / c, ll[1] - r, ll[0] + r / c, ll[1] + r]]));
  for (const x of index) {
    if (x.layer !== "rivers" || !x.ids.some((i) => cand.has(i))) continue;
    let best = Infinity;
    for (const f of x.feats) eachPoint(f, (u, w) => {
      const q = [u, w]; if (!visible(q)) return;
      const p = S.proj(q), dd = Math.hypot(p[0] - px[0], p[1] - px[1]);
      if (dd < best) best = dd;
    });
    if (best < 8) near.push([best, x]);
  }
  near.sort((a, b) => a[0] - b[0]);
  hits.push(...near.slice(0, 3).map((q) => q[1]));
  const info = $("info");
  info.style.display = "block"; info.innerHTML = "";
  const close = Object.assign(document.createElement("button"), { textContent: "×", title: "Close" });
  close.onclick = clearSel;
  info.append(close, Object.assign(document.createElement("div"), { className: "kind", textContent: `${ll[1].toFixed(2)}°, ${ll[0].toFixed(2)}°` }));
  history.replaceState(null, "", `#at=${ll[1].toFixed(3)},${ll[0].toFixed(3)}`);
  const ul = document.createElement("ul");
  for (const x of hits) {
    const li = document.createElement("li");
    li.append(Object.assign(document.createElement("span"), { textContent: x.name }), Object.assign(document.createElement("span"), { textContent: x.kind }));
    li.onclick = () => select(x);
    ul.append(li);
  }
  if (!hits.length) ul.append(Object.assign(document.createElement("li"), { textContent: onLand ? "(nothing named here)" : "(open water)" }));
  info.append(ul);
}
