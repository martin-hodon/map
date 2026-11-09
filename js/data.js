// data.js -- loading: the light files and the point tables, the layers and their copies, releasing a layer not in use, load()
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { PROJ, mode, legend } from "./style.js";
import { $, trees, points, on, MAX_ZOOM, fmt } from "./state.js";
import { setup, COPIES, Map0, thingsOf, B0 } from "./geom.js";
import { dayNum, yearOf, showYear, histDay, setDay } from "./history.js";
import { tree, pointTree, draw } from "./view.js";
import { loadWasm, attachRows, releaseRows, freeTree } from "./wasm.js";
import { ROAD_TIERS } from "./labels.js";
import { startOffline, showVersion } from "./offline.js";
import { parseLite } from "./lite.js";
import { addToIndex, buildIndex, indexRivers, indexLines, indexPoints, search } from "./search.js";
import { select, identifyAt } from "./select.js";
import { GROUP_COLOURS, idOf, groupsOn, renderGroups } from "./groups.js";
import { showResults, modeChanged } from "./ui.js";

// THE DATA: the light files of the line layers (data/*.txt, build/lite.py) and the point layers' CSV -- the only data
// the map loads (the full-detail layers, full/*.topo.json, are what the light files are made from: not served)
// THE ORDER: the world first (land, countries, states, lakes, areas) -- the map is drawn as soon as it is read -- and the
// rest as each comes (rivers, the main lines, the points: asked for at once, read after the world, each drawn when
// ready); the biogeographic and the historical map, and the pipelines, only when wanted (wanted(): their mode, a group
// of theirs, their layer switched on, a link)
export const fetched = {};
export const fetchText = (f) => fetched[f] ??= fetch("data/" + f).then((r) => r.ok ? r.text() : null).catch(() => null);
export const getData = async (f, base) => { const t = await fetchText(f); delete fetched[f]; return t == null ? null : f.endsWith(".csv") ? pointsOf(d3.csvParse(t)) : parseLite(t, base); };
export const POINT_FILES = { cities: "cities.csv", monuments: "monuments.csv", nature: "natural_points.csv", airports: "airports.csv", events: "events.csv" };
S.redrawing = false;
export const redraw = () => { if (S.redrawing) return; S.redrawing = true;                // (a layer come: drawn once, not while the map is moved)
  requestAnimationFrame(() => { S.redrawing = false; if (!S.drag && !S.moving) draw(); }); };
export function showStats() {
  const n = (k, t) => S.src[k] ? ` · ${S.src[k].features.length} ${t}` : "";
  let t = `${Map0.countries.length} countries · ${Map0.regions.length} states · ${Map0.lakes.length} lakes · ${Map0.areas.length} areas · ` +
    `${(S.src.world.xy.length / 2).toLocaleString("en")} points` +
    (Map0.rivers.length ? ` · ${new Set(Map0.rivers.map((f) => f.properties.river)).size} rivers` : "") +
    n("cities", "cities") + n("monuments", "monuments") + n("nature", "peaks, capes…") + n("airports", "airports") + n("events", "historical events");
  if (B0.realms.length) t += ` · ${B0.ecoregions.length} ecoregions in ${B0.biomes.length} biomes, ${B0.realms.length} realms`;
  if (S.H0) t += ` · ${S.H0.periods.length} country-periods ${showYear(Math.min(...S.H0.periods.map((p) => yearOf(p.from))))}–2019 in ${S.H0.regions.length} regions`;
  $("stats").textContent = t;
}
// a copy of a line layer, read when asked for: `objectsOf[name]`, what its Things point at, gets the copy's numbers. Stays
// when the layer is let go (RELEASE), as its names stay to be found: read again, it only gets the numbers again.
export const BASE = { bio: "world", history: "world" }, lineFiles = {}, objectsOf = {};
export function readCopy(name, lv) {
  const c = lineFiles[name] ??= [];
  return c[lv] ??= (async () => {
    const f = `${COPIES[lv].dir}${name}.txt`, t = await fetchText(f);
    delete fetched[f];
    const full = lv ? await readCopy(name, 0) : true, base = BASE[name] ? await readCopy(BASE[name], lv) : null;
    if (t == null || !full || lineFiles[name] !== c || (BASE[name] && !base)) return null;   // (let go meanwhile: not wanted any more)
    const T = parseLite(t, base, objectsOf[name]), O = objectsOf[name] ??= {};
    for (const k in T.objects) { const o = O[k] ??= { kind: T.objects[k].kind, n: T.objects[k].n, rows: T.objects[k].rows, geos: [] }; o.geos[lv] = T.objects[k].g; attachRows(T, o.geos[lv], o.kind); }
    delete T.objects;
    if (lv) redraw();
    return T;
  })();
}
// a layer of its own file: its full copy, its rows (and, the first time, their names in the index), its trees; the coarser copies after it
// (`used`: what keeps it from being let go: RELEASE)
export async function addLayer(name) {
  const L = LAYERS[name], T = await readCopy(name, 0);
  if (!T) return null;
  if (!L.known) { for (const k of L.keys) Map0[k] = thingsOf(objectsOf[name], k); L.indexIt(Map0); L.known = true; }
  for (const k of L.keys) trees[k] = tree(Map0[k]);
  L.ready = true; L.last = Date.now();
  readCopy(name, 1); readCopy(name, 2);
  showStats(); redraw();
  return T;
}
export const LAYERS = {
  rivers: { keys: ["rivers"], used: () => on("rivers"), indexIt: (L) => indexRivers(L) },
  transport: { keys: ["motorways", "railways"], used: () => on("motorways") || on("railways"), indexIt: (L) => indexLines(L, ["motorways", "railways"]) },
  roads: { keys: ["roads"], used: () => on("motorways") && S.zoom >= ROAD_TIERS[0], indexIt: (L) => indexLines(L, ["roads"]) },
  pipelines: { keys: ["pipelines"], used: () => on("pipelines"), indexIt: (L) => indexLines(L, ["pipelines"]) },
  bio: { keys: ["realms", "biomes", "ecoregions"], read: () => loadBio(), used: () => mode() === "bio" || ["realms", "biomes", "ecoregions"].some(groupsOn) },
  history: { keys: ["hregions"], read: () => loadHistory(), used: () => mode() === "history" },
};
export const FILE_OF = { hperiods: "history", ...Object.fromEntries(Object.entries(LAYERS).flatMap(([name, L]) => L.keys.map((k) => [k, name]))) };
export const loads = {}, layerLoad = (name) => loads[name] ??= (LAYERS[name].read ?? (() => addLayer(name)))();
S.restLoaded = false;
export function foundWhenCome() {                                          // (#find=...: what the link names, once a layer of it has come)
  if (!S.pendingFind) return;
  const r = search(S.pendingFind), e = r.find(inSpan) || r[0];
  if (e) { S.pendingFind = null; $("q").value = e.name; select(e); }
}
export function wanted() {
  if (!S.src || !S.restLoaded) return;
  for (const name in LAYERS) if (LAYERS[name].used() || S.pendingFind) layerLoad(name).then(foundWhenCome);
}
// RELEASE: a layer not in use for a few minutes is let go -- its points (tens of MB, the historical map's more) -- and read
// again when wanted (from the browser's cache, in a moment). Its names stay in the index, so it is still found: chosen, it comes back first.
export const RELEASE_MS = 3 * 60 * 1000;
export function letGo(name) {
  const L = LAYERS[name];
  if (name === "history") { for (const k in objectsOf.history ?? {}) for (const g of objectsOf.history[k].geos) if (g) releaseRows(g); S.H0 = null; S.histNow = null; delete objectsOf.history; L.known = false; }
  else for (const k in objectsOf[name]) { for (const g of objectsOf[name][k].geos) if (g) releaseRows(g); objectsOf[name][k].geos = []; }
  for (const k of L.keys) { freeTree(trees[k]); delete trees[k]; }
  delete lineFiles[name]; delete loads[name];
  L.ready = false;
  if (name === "bio") S.src.bio = null;
  if (name === "history") S.src.hist = null;
}
export function releaseUnused() {
  const now = Date.now();
  for (const name in LAYERS) { const L = LAYERS[name];
    if (L.used() || !L.ready) L.last = now;
    else if (now - L.last > RELEASE_MS) letGo(name);
  }
}
export async function load() {
  const kept = await startOffline();
  await loadWasm();
  showVersion(kept);
  for (const f of ["rivers.txt", "transport.txt", ...Object.values(POINT_FILES), "flags.txt"]) fetchText(f);
  const world = await readCopy("world", 0);
  if (!world) { $("stats").textContent = "no data/world.txt yet (README.md)"; return; }
  S.src = { world };
  const L = Map0, O = objectsOf.world, islands = thingsOf(O, "islands");
  // (the land is the continents and the islands; a named island is an area too -- one row in the file, its name on it)
  Object.assign(L, { land: [...thingsOf(O, "continents"), ...islands], countries: thingsOf(O, "countries"), regions: thingsOf(O, "regions"), lakes: thingsOf(O, "lakes"), cb: thingsOf(O, "country_borders"), rb: thingsOf(O, "region_borders"),
    areas: [...thingsOf(O, "areas"), ...islands.filter((f) => f.properties.name).map((f) => f.named({ kind: "island", mask: "land", ...f.properties }))] });
  for (const k of ["land", "countries", "lakes", "cb", "rb", "areas", "regions"]) trees[k] = tree(L[k]);
  buildIndex();
  idOf.countries = new Map(L.countries.map((f, i) => [f.properties.iso, i]));
  legend(); showStats();
  const h = new URLSearchParams(location.hash.slice(1));      // (#find=Alps&proj=Mollweide: a link to one thing)
  if (h.get("proj") && PROJ[h.get("proj")]) $("proj").value = h.get("proj");
  // (#groups=[...]: a map of groups; #bio=PA,E345,B7 or #countries=SK,CZ: one list shown -- a range, say)
  if (h.get("groups")) { try { S.groups = JSON.parse(h.get("groups")); S.linked = true; } catch (e) { } }
  const list = (s, layerOf) => s.split(",").map((x) => x.trim()).filter(Boolean).map((x) => `${layerOf(x)}:${x}`);
  if (h.get("bio")) { const items = list(h.get("bio"), bioLayerOf); S.groups.push({ name: "shown", color: GROUP_COLOURS[S.groups.length % GROUP_COLOURS.length], items }); S.linked = true;
    if (!h.get("mode")) h.set("mode", "bio"); if (!h.get("level") && items.length) h.set("level", items[0].split(":")[0]); }
  if (h.get("countries")) { S.groups.push({ name: "shown", color: GROUP_COLOURS[S.groups.length % GROUP_COLOURS.length], items: list(h.get("countries"), () => "countries") }); S.linked = true;
    if (!h.get("mode")) h.set("mode", "political"); }
  if (h.get("level") && $("biolevel").querySelector(`[value="${h.get("level")}"]`)) $("biolevel").value = h.get("level");
  if (h.get("date")) setDay(h.get("date"));
  if (h.get("mode") && $("mode").querySelector(`[value="${h.get("mode")}"]`)) { $("mode").value = h.get("mode"); modeChanged(false); }
  renderGroups();
  setup(); draw();
  if (h.get("at") && !h.get("find")) {                          // (#at=lat,lon[,zoom]: what is at that spot)
    const [lat, lon, z] = h.get("at").split(",").map(Number);
    S.rotate = [-lon, -lat, 0]; S.zoom = Math.min(MAX_ZOOM, z || 4); setup(); draw(); identifyAt([lon, lat], S.proj([lon, lat]));
  }
  readCopy("world", 1); readCopy("world", 2);                     // (not waited for: the full file draws till then)
  await Promise.all([
    layerLoad("rivers"), layerLoad("transport"),
    ...Object.entries(POINT_FILES).map(([k, f]) => getData(f).then((d) => { if (!d) return; S.src[k] = d; points[k] = pointTree(d); indexPoints(k); showStats(); redraw(); })),
    fetchText("flags.txt").then((t) => { if (!t) return; S.flagLib = Flags.library(t); if (S.flagLib.errors.length) console.warn("data/flags.txt:", S.flagLib.errors);
      showResults(); }),
  ]);
  S.restLoaded = true;
  // (#find=Alps: once all but the two maps of their own are in -- the Rhine is no state's name, Berlin the city before the state)
  if (h.get("find")) { const e = search(h.get("find"))[0]; if (e) { $("q").value = e.name; select(e); } else S.pendingFind = h.get("find"); }
  wanted();
}
// a table of points (data/cities.csv, monuments.csv, natural_points.csv, airports.csv, events.csv: a header line, one a line,
// `lon` and `lat` its place) read into one shape, so all of them are drawn, found and named alike
export function pointsOf(rows) {
  const NUM = new Set(["population", "visitors", "visitors_year", "wikipedias", "level", "passengers", "passengers_year", "elevation_m", "rank"]);
  return { features: rows.map((r) => {
    const p = {};
    for (const k of rows.columns) if (k !== "lon" && k !== "lat" && r[k] !== "") p[k] = NUM.has(k) ? +r[k] : r[k];
    return { geometry: { coordinates: [+r.lon, +r.lat] }, properties: p };
  }) };
}
// the biogeographic layer (data/bio.txt): only when wanted (its map, a group of its, a link), as it is only for its
// own map, its names and the ecoregion under a click
S.pendingFind = null;
export const bioLayerOf = (id) => /^E\d+$/.test(id) ? "ecoregions" : /^B\d+$/.test(id) ? "biomes" : "realms";
export async function loadBio() {
  const L = LAYERS.bio, first = !L.known, bio = await readCopy("bio", 0);
  if (!bio) { $("mode").querySelector('[value="bio"]').disabled = true; return; }
  if (first) { const O = objectsOf.bio; for (const k of L.keys) B0[k] = thingsOf(O, k); }
  const B = B0;
  for (const k of L.keys) trees[k] = tree(B[k]);
  S.src.bio = bio; L.known = true; L.ready = true; L.last = Date.now();
  readCopy("bio", 1); readCopy("bio", 2);
  if (first) {
    for (const k of ["realms", "biomes", "ecoregions"]) idOf[k] = new Map(B[k].map((f, i) => [f.properties.id, i]));
    const realm = Object.fromEntries(B.realms.map((f) => [f.properties.id, f.properties.name])), biome = Object.fromEntries(B.biomes.map((f) => [f.properties.id, f.properties.name]));
    const count = (k, v) => B.ecoregions.filter((f) => f.properties[k] === v).length;
    B.realms.forEach((f, i) => addToIndex({ cat: "bio", name: f.properties.name, alt: f.properties.id, kind: "biogeographic realm", feats: [f], ids: [i], layer: "realms", mask: "land", at: f.properties.label, weight: 5e9, info: [`${count("realm", f.properties.id)} ecoregions`] }));
    B.biomes.forEach((f, i) => addToIndex({ cat: "bio", name: f.properties.name, alt: f.properties.id, kind: "biome", feats: [f], ids: [i], layer: "biomes", mask: "land", weight: 4e9, info: [`${count("biome", f.properties.id)} ecoregions`] }));
    B.ecoregions.forEach((f, i) => { const p = f.properties;
      addToIndex({ cat: "bio", name: p.name, alt: p.id, kind: `ecoregion · ${realm[p.realm] || "no realm"}`, feats: [f], ids: [i], layer: "ecoregions", mask: "land", at: p.label, weight: 1e6 + (p.area_km2 || 0),
                   info: [biome[p.biome], p.area_km2 ? `${fmt(p.area_km2)} km²` : null, p.id] }); });
  }
  showStats();
  legend(); renderGroups();
  if (mode() === "bio" || S.groups.length) draw();
}
// the historical map (data/history.txt): only when wanted (its map, a link), as it is only for its own map; each country-period
// is found by name (chosen, the map shows a day in its span), a region under a click
S.historyIndexed = false;
export async function loadHistory() {
  const L = LAYERS.history, hist = await readCopy("history", 0);
  if (!hist || !objectsOf.history?.regions) { $("mode").querySelector('[value="history"]').disabled = true; return; }
  S.histNow = null;
  const O = objectsOf.history, P = O.periods.rows, regions = thingsOf(O, "regions"), byState = new Map();
  P.forEach((p, i) => { p._f = dayNum(p.from); p._t = dayNum(p.to); if (!byState.has(p.state)) byState.set(p.state, []); byState.get(p.state).push(i); });
  // (each region's owners as numbers, all in one array: the text it comes as was a third of what this map took)
  const start = new Int32Array(regions.length + 1), from = [], state = [];
  regions.forEach((f, r) => { start[r] = from.length; for (const x of f.properties.held || []) { const k = x.lastIndexOf(":"), s = x.slice(k + 1); from.push(dayNum(x.slice(0, k))); state.push(s === "" ? -1 : +s); } delete f.properties.held; });
  start[regions.length] = from.length;
  S.H0 = { periods: P, byState, held: { start, from: Int32Array.from(from), state: Int32Array.from(state) }, pairs: new Map(), regions };
  trees.hregions = tree(regions);
  S.src.hist = hist; L.ready = true; L.last = Date.now();
  readCopy("history", 1); readCopy("history", 2);
  if (!S.historyIndexed) {
    S.historyIndexed = true;
    const name = new Map(P.map((p) => [p.state, p.name]));
    const years = (p) => `${showYear(yearOf(p.from))}–${showYear(yearOf(p.to))}`;
    P.forEach((p, i) => {
      addToIndex({ cat: "history", name: p.name, kind: `${p.status === "independent" || !p.status ? "state" : p.status} ${years(p)}`, feats: [], ids: [], layer: "hperiods", period: i,
                   mask: "land", at: p.label, weight: 1e5 + (p.area_km2 || 0) / 1e3, span: [p.from, p.to],
                   info: [p.owner != null ? `of ${name.get(p.owner) || p.owner}` : null, p.capital ? `capital ${p.capital}` : null, p.area_km2 ? `${fmt(p.area_km2)} km²` : null,
                          p.source === "basemaps" ? `as mapped for ${showYear(yearOf(p.from))}, until the next map` : `${p.from} to ${p.to}`, p.precision === 1 ? "borders approximate" : null] }); });
  }
  showStats();
  if (mode() === "history") draw();
}
export const inSpan = (e) => e.span && dayNum(e.span[0]) <= dayNum(histDay()) && dayNum(histDay()) <= dayNum(e.span[1]);

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  setInterval(releaseUnused, 30000);
}
