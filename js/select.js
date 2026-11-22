// select.js -- selecting: the selection, the flight to it, what is under a click
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { mode } from "./style.js";
import { $, trees, index, GAME_ZOOM, MAX_ZOOM, fmt, make } from "./state.js";
import { setup, eachPoint, Map0 } from "./geom.js";
import { dayText, showDay, histDay, setDay, histOn, histFeature, pxKm } from "./history.js";
import { query, draw } from "./view.js";
import { visible } from "./labels.js";
import { LAYERS, FILE_OF, layerLoad, inSpan, wanted } from "./data.js";
import { norm, collect, entriesAt } from "./search.js";
import { flagCode, flagSvg } from "./flags.js";
import { game, bareGame } from "./groups.js";
import { showResults, modeChanged, levelShown, togglesShown } from "./ui.js";
import { warInfo, eventWars, warList } from "./wars.js";
import { welleLines } from "./welle.js";
import { platesAt } from "./plates.js";
import { isShown, showFor } from "./shown.js";
import { parksAt } from "./parks.js";

// ---- selecting: highlight, fly there, say what it is ---------------------------------------------------------------
// the selection goes with the panel's x, with the search box emptied (its own x, or Escape in it), or the link cleared
export function clearSel() {
  S.sel = null; S.war = null; $("info").style.display = "none"; $("q").value = ""; S.found = []; showResults();
  history.replaceState(null, "", location.pathname + location.search); draw();
}
// (`fly`: the map turned and zoomed to it -- not for a click on the map, which chooses what is under the pointer where it is)
export function select(e, { fly: flyTo = true } = {}) {
  showFor(e, { modeChanged, levelShown, togglesShown, wanted });                 // (not on the map as it is: its map and layer switched on -- shown.js)
  const file = FILE_OF[e.layer];
  if (file && !LAYERS[file].ready) return void layerLoad(file).then(() => LAYERS[file].ready && select(e, { fly: flyTo }));   // (let go: read again first)
  if (file) LAYERS[file].last = Date.now();
  if (e.span) {                                                     // (a country-period: on the historical map, on a day of its span)
    if (mode() !== "history") { $("mode").value = "history"; modeChanged(false); }
    if (!inSpan(e)) setDay(e.span[0]);
    if (e.period != null) { e.feats = histFeature(e.period); if (!e.feats.length) e.feats = [{ type: "Feature", geometry: { type: "Point", coordinates: e.at } }]; }
  }
  S.sel = { ...e, geom: collect(e.feats), at: e.at || d3.geoCentroid(collect(e.feats)) };
  const info = openInfo("Clear the selection");
  const h = make("h2", { textContent: e.name });
  const k = make("div", { className: "kind", textContent: [e.kind, ...(e.info || [])].filter(Boolean).join(" · ") });
  info.append(h, k);
  S.war = e.war ?? null;
  if (e.war != null) warInfo(e.war, info, chooseWar, chooseEvent);
  else if (e.layer === "events" || (e.cat === "point" && e.span)) S.war = eventWars(S.src.events.features.indexOf(e.feats[0]), info, chooseWar);
  if (e.alt && norm(e.alt) !== norm(e.name)) info.append(make("div", { className: "kind", textContent: e.alt }));
  const fc = flagCode(e);
  if (fc && S.flagLib?.has(fc)) info.append(make("a", { className: "flags", href: "flags.html#" + fc, target: "_blank",
    title: `${e.name}: its flag${S.flagLib.has(fc + "-arms") ? " and coat of arms" : ""}${e.span ? ` on ${showDay(inSpan(e) ? histDay() : e.span[0])}` : ""} (simplified; all of them: flags.html)`, innerHTML: flagSvg(fc, 40) + flagSvg(fc + "-arms", 48) }));
  const me = S.sel;                                                    // (a later choice made while back.json comes: not this one's box)
  const p = e.feats?.[0]?.properties ?? {};                             // (its ids first: the name is not one -- many a Battle of Smolensk)
  welleLines("place", [p.wikidata, (e.cat === "country" || e.cat === "region") && p.iso, `${e.name}|${e.cat}`].filter(Boolean)).then((w) => { if (w.total && S.sel === me) info.append(welleBox(w)); });
  history.replaceState(null, "", "#find=" + encodeURIComponent(e.name) + ($("proj").selectedIndex ? "&proj=" + encodeURIComponent($("proj").value) : "") + (e.span ? "&date=" + encodeURIComponent(histDay()) : ""));
  if (flyTo) fly(S.sel); else draw();
}
// the notes' lines naming it (../welle), under the panel's other facts: a link each into welle at that line
function welleBox({ lines: ls, total }) {
  const box = make("div", { className: "welle" }), ul = document.createElement("ul");
  box.append(make("div", { className: "kind", textContent: `in the notes (welle) · ${total}` + (total > ls.length ? `, the first ${ls.length}` : "") }), ul);
  for (const l of ls) {
    const item = document.createElement("li");
    item.append(make("a", { href: l.href, textContent: l.text }), make("span", { textContent: l.file }));
    ul.append(item);
  }
  return box;
}
// a war (a group of campaigns.json) or an event (a row of events.csv) chosen from the panel: as if found by name
export const chooseWar = (gi) => { const e = index.find((x) => x.war === gi); if (e) { $("q").value = e.name; select(e); } };
export const chooseEvent = (row) => { const f = S.src.events.features[row], e = index.find((x) => x.cat === "point" && x.feats[0] === f); if (e) { $("q").value = e.name; select(e); } };
// the ⚔ list of wars, in the panel
// the info panel opened empty but for its × (which clears the selection)
function openInfo(title = "Close") {
  const info = $("info"), close = make("button", { textContent: "×", title });
  close.onclick = clearSel; info.style.display = "block"; info.replaceChildren(close);
  return info;
}
export function showWars() {
  if (!S.wars) return;
  warList(openInfo(), chooseWar);
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
  identifyAt(ll, [e.clientX, e.clientY], { cycle: true });
}
export function identifyAt(ll, px, { cycle = false } = {}) {
  const at = [[ll[0], ll[1], ll[0], ll[1]]];
  const byLayer = (layer) => entriesAt(layer, query(trees[layer], at));
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
  for (const x of entriesAt("rivers", cand)) {
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
  hits.push(...parksAt(ll, query(trees.parks, at)));                // (a park drawn as its area: monuments on)
  const zone = byLayer("zones").find((x) => x.feats.length === 1 && inside(x));   // (the time zone here, and its offset with all its zones: layer 18)
  if (zone) hits.push(zone, ...byLayer("zones").filter((x) => x.offset === zone.feats[0].properties.utc));
  hits.push(...platesAt(ll, px));                                   // (the plate under it and a boundary near: their layer on)
  // A CLICK CHOOSES (`cycle`): the first thing here, or, the chosen one among them, the next -- after the last, nothing
  // (a country, again its state, its sea, a river near...: click on till it is the one); the list of all of them under
  // it. A link to a place (#at=) only lists them.
  hits.splice(0, hits.length, ...hits.filter(isShown));             // (only what the map shows: its layers on, its map chosen)
  if (cycle && hits.length) {
    const at = S.sel ? hits.findIndex((x) => sameThing(x, S.sel)) : -1, next = hits[at + 1];
    if (!next) return clearSel();
    select(next, { fly: false });
    $("info").append(hereList(hits, next, ll));
    return;
  }
  if (cycle && S.sel) clearSel();                                   // (nothing here: the choice let go, the place told)
  const info = openInfo();
  info.append(make("div", { className: "kind", textContent: `${ll[1].toFixed(2)}°, ${ll[0].toFixed(2)}°` }));
  history.replaceState(null, "", `#at=${ll[1].toFixed(3)},${ll[0].toFixed(3)}`);
  const ul = hereList(hits, null).lastChild;
  if (!hits.length) ul.append(make("li", { textContent: onLand ? "(nothing named here)" : "(open water)" }));
  info.append(ul);
}
// (one thing found twice: a click's plate, boundary or historical region is made anew each time -- the same by its shape)
const sameThing = (a, b) => a === b || (a.name === b.name && a.cat === b.cat && !!a.feats?.length && a.feats[0] === b.feats?.[0]);
// what is here, the chosen one marked (`on`): a click on one chooses it (and goes there)
function hereList(hits, on, ll) {
  const box = make("div", { className: "here" }), ul = document.createElement("ul");
  if (on) box.append(make("div", { className: "kind", textContent: `here (${ll[1].toFixed(2)}°, ${ll[0].toFixed(2)}°): ${hits.indexOf(on) + 1} of ${hits.length} · click again for the next` }));
  for (const x of hits) {
    const li = make("li", { className: x === on ? "on" : "" });
    li.append(make("span", { textContent: x.name }), make("span", { textContent: x.kind }));
    li.onclick = () => select(x);
    ul.append(li);
  }
  box.append(ul);
  return box;
}
