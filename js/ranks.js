// ranks.js -- the RANKINGS: a side view (beside the map on a wide screen, in its place on a phone) that orders what the
// map has by a number: countries by their people, area or density (in the world or a continent), a country's states
// so, cities by their people (in the world, a continent, a country or a state), rivers by their length, peaks by their
// height, seas, gulfs and bays by their area. A row chosen is selected on the map (flown to, named); on a phone the
// map comes back for it, and the button returns to the list as it was.
// The numbers are the map's own (population, area_km2, density, elevation_m) but for a river's length and a sea's
// area: Wikidata's (data/measures.json: build/measures.py) -- the map traces only a river's wide part and a sea without
// holes for its islands. Its rows are the search's (one a country, a river of many lines, England whole).
// THE MAP COLOURED BY IT: while the list is open (and "colour the map" ticked) the map shows the list -- what it ranks
// in seven shades by its place (a seventh of the rows a shade, the first the darkest), with everything else of its kind
// plain (the country colours left out): countries and states filled, seas and gulfs, ranges, deserts and islands
// filled, rivers drawn over in their shade, cities as dots (by their people) and peaks as triangles. Each row's bar is in its
// shade, and a key under the choices gives each shade's numbers. On a phone a row chosen hides the list but not its
// colours: they stay on the map until the list is closed with its ×. A new scope (a continent, a country, a state) is
// flown to.
import { S, $, index, fmt, fmtPop, dark } from "./state.js";
import { Map0 } from "./geom.js";
import { fetchText, LAYERS, layerLoad } from "./data.js";
import { game } from "./groups.js";
import { flagCode, flagSvg } from "./flags.js";
import { select, fly } from "./select.js";
import { collect } from "./search.js";
import { draw } from "./view.js";

S.measures = null;
const WATER = { "oceans and seas": ["ocean", "sea"], "gulfs and bays": ["gulf", "bay", "inlet", "fjord", "sound", "lagoon", "estuary"], "straits and channels": ["strait", "channel"] };
const LAND = { "mountain ranges": ["mountains"], "deserts": ["desert"], "plateaus": ["plateau"], "peninsulas": ["peninsula"], "islands": ["island"] };
const km2 = (v) => `${fmt(v)} km²`;
// each list: what it orders (rows), by which numbers, within what
export const LISTS = {
  countries: { noun: "countries", label: "countries", by: { population: fmtPop, area: km2, density: (v) => `${fmt(v)} /km²` }, within: "continent" },
  states: { noun: "states", label: "states of a country", by: { population: fmtPop, area: km2, density: (v) => `${fmt(v)} /km²` }, within: "country" },
  cities: { noun: "cities", label: "cities", by: { population: fmtPop }, within: "place" },
  rivers: { noun: "rivers", label: "rivers", by: { length: (v) => `${fmt(v)} km` } },
  peaks: { noun: "peaks", label: "mountains (peaks)", by: { height: (v) => `${fmt(v)} m` } },
  water: { noun: "", label: "seas, gulfs, straits", by: { area: km2 }, within: "water" },
  land: { noun: "", label: "ranges, deserts, islands…", by: { area: km2 }, within: "land" },
};
const R = { list: "countries", by: "population", within: "", open: false, paint: true }, RS = R;
try { Object.assign(R, JSON.parse(localStorage.ranks || "{}"), { open: false }); } catch (e) { }
const save = () => { try { localStorage.ranks = JSON.stringify(R); } catch (e) { } };
const PANEL = { list: "rk-list", by: "rk-by", within: "rk-within" };

const countryOf = () => Object.fromEntries(Map0.countries.map((f) => [f.properties.iso, f.properties]));
const regionOf = () => Object.fromEntries(Map0.regions.map((f) => [f.properties.iso, f.properties]));
// the rows of a list: { e (the search's entry), name, sub, v } -- of the list's choices R (the panel's), or a game's
export function rows(R = RS) {
  const C = countryOf(), out = [], p0 = (e) => e.feats[0].properties;
  if (R.list === "countries") for (const e of index) {
    if (e.cat !== "country" || e.kind === "continent") continue;
    const p = p0(e); if (R.within && p.continent !== R.within) continue;
    out.push({ e, name: e.name, sub: p.subtype === "dependency" ? `dependency of ${C[p.sovereign]?.name || p.sovereign}` : p.continent, v: { population: p.population, area: p.area_km2, density: p.density }[R.by] });
  }
  if (R.list === "states") for (const e of index) {
    if (e.cat !== "region") continue;
    const p = p0(e), whole = e.feats.length > 1;           // (England: its nine regions together)
    if (!whole && p.part_of) continue;
    if (p.country !== R.within) continue;
    const pop = whole ? e.feats.reduce((s, f) => s + (f.properties.population || 0), 0) : p.population, area = whole ? e.feats.reduce((s, f) => s + (f.properties.area_km2 || 0), 0) : p.area_km2;
    out.push({ e, name: e.name, sub: p.iso, v: { population: pop, area, density: area ? pop / area : null }[R.by] });
  }
  if (R.list === "cities" && S.src.cities) {
    const Rg = regionOf(), F = new Set(S.src.cities.features), [scope, code] = (R.within || "world:").split(":");
    for (const e of index) {
      if (e.cat !== "point" || !F.has(e.feats[0])) continue;
      const p = p0(e), cont = (p.region && Rg[p.region]?.continent) || C[p.country]?.continent;
      if ((scope === "continent" && cont !== code) || (scope === "country" && p.country !== code) || (scope === "state" && p.region !== code)) continue;
      out.push({ e, name: e.name, sub: [p.capital === "country" ? "capital" : null, Rg[p.region]?.name, C[p.country]?.name].filter(Boolean).join(", "), v: p.population });
    }
  }
  if (R.list === "rivers") for (const e of index) {
    if (e.cat !== "river") continue;
    const wd = e.feats.map((f) => f.properties.wikidata).find(Boolean), v = S.measures?.length_km[wd];
    if (v) out.push({ e, name: e.name, sub: e.alt || "", v });
  }
  if (R.list === "peaks" && S.src.nature) {
    const F = new Set(S.src.nature.features.filter((f) => f.properties.kind === "peak"));
    for (const e of index) if (e.cat === "point" && F.has(e.feats[0]) && p0(e).elevation_m != null) out.push({ e, name: e.name, sub: p0(e).name_en && p0(e).name_en !== e.name ? p0(e).name_en : "", v: p0(e).elevation_m });
  }
  if (R.list === "water" || R.list === "land") {
    const kinds = (R.list === "water" ? WATER : LAND)[R.within] || [], best = new Map();
    for (const e of index) {                                // (a sea in parts -- the North and South Pacific -- once, whole)
      if (e.cat !== "area" || !kinds.includes(e.kind)) continue;
      const wd = p0(e).wikidata, v = S.measures?.area_km2[wd];
      if (v && (!best.has(wd) || e.feats.length > best.get(wd).e.feats.length)) best.set(wd, { e, name: e.name, sub: e.kind, v });
    }
    out.push(...best.values());
  }
  return out.filter((r) => r.v > 0).sort((a, b) => b.v - a.v);
}

// the choices: what, by what, within what (each list its own) -- into the panel's selects, or a game's (ids: PANEL's)
export function choices(R, ids) {
  const L = LISTS[R.list];
  $(ids.list).value = R.list;
  const by = $(ids.by); by.innerHTML = ""; for (const k of Object.keys(L.by)) by.append(new Option(k, k));
  if (!L.by[R.by]) R.by = Object.keys(L.by)[0];
  by.value = R.by; by.hidden = Object.keys(L.by).length < 2;
  within(R, $(ids.within));
}
function within(R, sel) {
  const L = LISTS[R.list], C = Map0.countries.map((f) => f.properties);
  sel.innerHTML = ""; sel.hidden = !L.within;
  const add = (v, t) => sel.append(new Option(t, v));
  const conts = [...new Set(C.map((p) => p.continent).filter(Boolean))].sort();
  const countries = C.filter((p) => p.subtype !== "continent").sort((a, b) => a.name.localeCompare(b.name));
  if (L.within === "continent") { add("", "the world"); conts.forEach((c) => add(c, c)); }
  if (L.within === "country") { const has = new Set(Map0.regions.map((f) => f.properties.country)); countries.filter((p) => has.has(p.iso)).forEach((p) => add(p.iso, p.name)); }
  if (L.within === "place") {
    add("world:", "the world");
    const g1 = Object.assign(document.createElement("optgroup"), { label: "a continent" }); conts.forEach((c) => g1.append(new Option(c, "continent:" + c)));
    const g2 = Object.assign(document.createElement("optgroup"), { label: "a country" }); countries.forEach((p) => g2.append(new Option(p.name, "country:" + p.iso)));
    sel.append(g1, g2);
    const [scope, code] = (R.within || "").split(":"), cc = scope === "state" ? code.split("-")[0] : scope === "country" ? code : null;
    const st = Map0.regions.map((f) => f.properties).filter((p) => p.country === cc && !p.part_of).sort((a, b) => a.name.localeCompare(b.name));
    if (st.length) { const g3 = Object.assign(document.createElement("optgroup"), { label: `a state of ${C.find((p) => p.iso === cc)?.name}` }); st.forEach((p) => g3.append(new Option(p.name, "state:" + p.iso))); sel.append(g3); }
  }
  if (L.within === "water" || L.within === "land") Object.keys(L.within === "water" ? WATER : LAND).forEach((k) => add(k, k));
  if (![...sel.options].some((o) => o.value === R.within)) R.within = sel.options[0]?.value ?? "";
  sel.value = R.within;
}
// the shades, palest to darkest (on the dark scheme from dim to bright: the darkest there is the land)
const RAMP = ["#fbecb4", "#f8d08a", "#f3ab66", "#e8824f", "#d45a4a", "#ad3a50", "#74234f"];
const RAMP_DARK = ["#3f3d33", "#5b4c33", "#7c5a35", "#9f6638", "#c06a40", "#dc6552", "#f2707a"];
export const rampColour = (k) => (dark() ? RAMP_DARK : RAMP)[k];
const shadeOf = (k, n) => 6 - Math.min(6, Math.floor(7 * k / n));     // (k: the place in the list, from 0)
// what the map draws for the list shown (view.js), or null: { layer, mask, unit (countries, states: the country colours
// left out), lines (rivers), by: [ids of each shade], dots: [{ at, shade, r }] the last first }
let painted = null;
let kept = false;                                                   // (the list hidden for a row on a phone: its colours kept)
// RIVERS KEPT: the rivers' lines are let go a few minutes after their layer is switched off (data.js: RELEASE), and with
// them every river's shape -- so while the list or a game (rankgame.js) ranks rivers they are kept, and read again first
S.keepLayer = (name) => name === "rivers" && (((R.open || kept) && R.list === "rivers") || (game.open && game.rk?.list === "rivers"));
export const riversReady = async (list) => { if (list === "rivers" && !LAYERS.rivers.ready) await layerLoad("rivers"); };
export const rankMap = () => (R.open || kept) && R.paint ? painted : null;
function paintOf() {
  if (!shown.length) return null;
  const e0 = shown[0].e, n = shown.length;
  if (e0.cat === "point") {
    const top = shown[0].v;
    return { peaks: R.list === "peaks", dots: shown.map((r, k) => ({ at: r.e.feats[0].geometry.coordinates, shade: shadeOf(k, n), r: R.list === "cities" ? 2 + 7 * Math.sqrt(r.v / top) : 2.5 + 0.6 * shadeOf(k, n) })).reverse() };
  }
  const by = Array.from({ length: 7 }, () => []);
  shown.forEach((r, k) => by[shadeOf(k, n)].push(...r.e.ids));
  const P = { layer: e0.layer, by };
  if (e0.layer === "countries" || e0.layer === "regions") P.unit = true;
  else if (e0.layer === "rivers") P.lines = true;
  else P.mask = e0.mask;
  return P;
}
// the key: each shade with the numbers of its rows (from its last to its first)
function key() {
  const k = $("rk-key"), L = LISTS[R.list], n = shown.length; k.innerHTML = "";
  k.hidden = !R.paint || !n;
  if (k.hidden) return;
  const short = (v) => R.by === "population" ? fmtPop(v) : L.by[R.by](v).replace(/ (km²|km|m|\/km²)$/, "");
  for (let s = 0; s < 7; s++) {
    const rows = shown.filter((_, j) => shadeOf(j, n) === s); if (!rows.length) continue;
    const lo = rows.at(-1).v, hi = rows[0].v;
    k.append(Object.assign(document.createElement("span"), { innerHTML: `<i style="background:${rampColour(s)}"></i>`, title: `${fmt(rows.length)} ${L.noun || "of them"}: ${L.by[R.by](lo)} – ${L.by[R.by](hi)}` }));
    k.lastChild.append(lo === hi ? short(lo) : `${short(lo)}–${short(hi)}`);
  }
}
// a new scope flown to: a continent, a country, a state
export function flyWithin(R = RS) {
  const [scope, code] = R.list === "cities" ? (R.within || "world:").split(":") : [LISTS[R.list].within, R.within];
  const e = scope === "continent" ? index.find((x) => x.kind === "continent" && x.name === code)
    : scope === "country" ? index.find((x) => x.cat === "country" && x.feats[0].properties.iso === code)
    : scope === "state" ? index.find((x) => x.cat === "region" && x.feats[0].properties.iso === code) : null;
  if (e) { const geom = collect(e.feats); fly({ cat: "area", geom, at: d3.geoCentroid(geom) }); }
}
let shown = [], limit = 100;
export function render() {
  const L = LISTS[R.list];
  choices(R, PANEL); save();
  shown = rows(); limit = 100;
  const sum = shown.reduce((s, r) => s + r.v, 0), add = R.by === "population" || (R.list !== "water" && R.list !== "land" && R.by === "area");
  $("rk-sum").textContent = `${fmt(shown.length)} ${L.noun || R.within}` + (add && shown.length ? ` · ${L.by[R.by](sum)} in all` : "")
    + (R.list === "rivers" ? " · the whole river's length (Wikidata)" : R.list === "water" || R.list === "land" ? " · area (Wikidata)" : "");
  painted = paintOf(); key(); $("rk-paint").checked = R.paint;
  fill(); draw();
}
function fill() {
  const ol = $("rk-rows"), L = LISTS[R.list], top = shown[0]?.v || 1, sum = shown.reduce((s, r) => s + r.v, 0);
  ol.innerHTML = "";
  shown.slice(0, limit).forEach((r, k) => {
    const li = document.createElement("li");
    const share = R.by === "population" && sum ? ` · ${(100 * r.v / sum).toFixed(r.v / sum >= .1 ? 0 : 1)}%` : "";
    li.innerHTML = `<span class="n">${k + 1}</span><span class="nm">${flagSvg(flagCode(r.e), 11, { cls: "fl", outline: false })}</span><span class="v"></span><i style="width:${(100 * r.v / top).toFixed(1)}%${R.paint ? `;background:${rampColour(shadeOf(k, shown.length))};opacity:1` : ""}"></i>`;
    li.querySelector(".nm").append(r.name, Object.assign(document.createElement("small"), { textContent: r.sub ? " " + r.sub : "" }));
    li.querySelector(".v").textContent = L.by[R.by](r.v); li.title = L.by[R.by](r.v) + share;
    li.onclick = () => { for (const x of ol.children) x.classList.remove("on"); li.classList.add("on"); $("q").value = r.e.name; select(r.e); if (matchMedia("(max-width: 700px)").matches) openRanks(false, true); };
    ol.append(li);
  });
  if (shown.length > limit) {
    const more = Object.assign(document.createElement("li"), { className: "more", textContent: `${fmt(shown.length - limit)} more…` });
    more.onclick = () => { limit += 200; fill(); }; ol.append(more);
  }
}
export async function openRanks(open, keep = false) {
  R.open = open; kept = keep; $("ranks").hidden = !open; $("ranks-btn").hidden = open; document.body.classList.toggle("ranking", open);
  if (!open) return void draw();
  await loadMeasures(); await riversReady(R.list); render();
}
export async function loadMeasures() { if (!S.measures) { const t = await fetchText("measures.json"); S.measures = t ? JSON.parse(t) : { length_km: {}, area_km2: {} }; } }
export function init() {
  for (const id of ["rk-list", "g-rlist"]) { $(id).innerHTML = ""; for (const [k, L] of Object.entries(LISTS)) $(id).append(new Option(L.label, k)); }
  $("ranks-btn").onclick = () => { if (S.src) openRanks(true); };
  $("rk-close").onclick = () => openRanks(false);
  $("rk-list").onchange = async () => { R.list = $("rk-list").value; R.within = ""; await riversReady(R.list); render(); };
  $("rk-by").onchange = () => { R.by = $("rk-by").value; render(); };
  $("rk-within").onchange = () => { R.within = $("rk-within").value; render(); flyWithin(); };
  $("rk-paint").onchange = () => { R.paint = $("rk-paint").checked; render(); };
}
