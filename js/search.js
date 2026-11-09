// search.js -- the index of names and the search over it
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { index, fmt, fmtPop } from "./state.js";
import { Thing, lengthKm, endsOf, Map0 } from "./geom.js";
import { showDay } from "./history.js";

// (a name as typed without its marks: "lodz" finds Łódź, "kobenhavn" København -- the accents come off by decomposing, and
//  the letters that do not decompose, Polish ł, Nordic ø and æ, ß, Croatian đ, Turkish ı, are folded by hand)
export const FOLD = { "ł": "l", "ø": "o", "đ": "d", "ð": "d", "þ": "th", "æ": "ae", "œ": "oe", "ß": "ss", "ı": "i", "ħ": "h", "ŧ": "t", "ŋ": "n" };
export const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[łøđðþæœßıħŧŋ]/g, (c) => FOLD[c]);
// (what a selection draws: the shape itself, not made anew each frame)
export const frozen = (f) => f instanceof Thing ? { type: "Feature", properties: f.properties, geometry: f.geometry } : f;
export const collect = (feats) => feats.length === 1 ? frozen(feats[0]) : { type: "FeatureCollection", features: feats.map(frozen) };
export const addToIndex = (e) => { e.keys = [...new Set([e.name, ...String(e.alt || "").split(" / ")].filter(Boolean).map(norm))]; index.push(e); };
export function buildIndex() {
  const L = Map0, add = addToIndex;
  const countryName = Object.fromEntries(L.countries.map((f) => [f.properties.iso, f.properties.name]));
  L.countries.forEach((f, i) => {
    const p = f.properties;
    if (!f.has()) return;
    add({ cat: "country", name: p.name, alt: p.name_local, kind: p.subtype === "dependency" ? "dependency" : p.subtype === "continent" ? "continent" : "country",
          feats: [f], ids: [i], layer: "countries", mask: "land", weight: 1e10, info: [p.iso, p.population ? `${fmtPop(p.population)} people` : null, p.density != null ? `${Math.round(p.density)}/km²` : null, p.language, p.sovereign && p.sovereign !== p.iso ? `of ${countryName[p.sovereign] || p.sovereign}` : null] });
  });
  L.regions.forEach((f, i) => {
    const p = f.properties;
    if (!f.has()) return;
    add({ cat: "region", name: p.name, alt: p.name_local, kind: `state · ${countryName[p.country] || p.country}`, feats: [f], ids: [i], layer: "regions", mask: "land", weight: 1e5, info: [p.iso, p.population ? `${fmtPop(p.population)} people` : null, p.density != null ? `${Math.round(p.density)}/km²` : null, p.language] });   // (below a city of the same name: Istanbul)
  });
  // a state drawn in parts (England, its nine regions): found as a whole too
  for (const [name, F] of d3.group(L.regions.filter((f) => f.properties.part_of && f.has()), (f) => f.properties.part_of)) {
    const p = F[0].properties, people = d3.sum(F, (f) => f.properties.population || 0);
    add({ cat: "region", name, kind: `state · ${countryName[p.country] || p.country}`, feats: F, ids: F.map((f) => L.regions.indexOf(f)), layer: "regions", mask: "land", weight: 1e5, flag: p.part_iso, info: [p.part_iso, people ? `${fmtPop(people)} people` : null, p.language] });
  }
  // a lake: its pieces (OSM's separate features) together, by Wikidata item or name
  const lakes = new Map();
  L.lakes.forEach((f, i) => { const p = f.properties; if (!p.name || !f.has()) return; const k = p.wikidata || p.name; if (!lakes.has(k)) lakes.set(k, []); lakes.get(k).push(i); });
  for (const ids of lakes.values()) {
    const fs = ids.map((i) => L.lakes[i]), p = fs[0].properties, area = Math.max(...fs.map((f) => f.properties.area_km2 || 0));
    add({ cat: "lake", name: p.name, alt: p.name_local, kind: p.type || "lake", feats: fs, ids, layer: "lakes", mask: "water", weight: area * 1e3, info: [`${fmt(area)} km²`] });
  }
  indexAreas(L);
}
export function indexRivers(L) {                                           // a river: every line of one river (from where it is first wide to its end), together
  const add = addToIndex, rv = new Map();
  L.rivers.forEach((f, i) => { const p = f.properties; if (!p.name) return; const k = p.river || p.wikidata || p.name; if (!rv.has(k)) rv.set(k, []); rv.get(k).push(i); });
  for (const ids of rv.values()) {
    const fs = ids.map((i) => L.rivers[i]), p = fs[0].properties, wmax = Math.max(...fs.map((f) => f.properties.width_max_m || 0));
    const km = p.river_km || fs.reduce((n, f) => n + (f.properties.length_km || 0), 0);
    add({ cat: "river", name: p.name, alt: (p.names_local || []).join(" / ") || null, kind: "river", feats: fs, ids, layer: "rivers", weight: km * 1e3, info: [`${fmt(km)} km drawn`, `up to ${fmt(wmax)} m wide`] });
  }
}
export function indexAreas(L) {                                            // the areas: each by its name; the parts of one (North and South Pacific) also together, by their common name
  const add = addToIndex, byWd = new Map();
  L.areas.forEach((f, i) => {
    const p = f.properties;
    if (!f.has()) return;
    add({ cat: "area", name: p.name, alt: p.name_en || p.name_local, kind: p.kind, feats: [f], ids: [i], layer: "areas", mask: p.mask, at: p.label, weight: 1e9 / (1 + (p.rank ?? 9)) });
    if (p.wikidata) { if (!byWd.has(p.wikidata)) byWd.set(p.wikidata, []); byWd.get(p.wikidata).push(i); }
  });
  for (const ids of byWd.values()) {
    const fs = ids.map((i) => L.areas[i]), names = new Set(fs.map((f) => f.properties.name));
    if (fs.length < 2 || names.size < 2 || !fs[0].properties.name_en) continue;
    const p = fs[0].properties;
    add({ cat: "area", name: p.name_en, kind: p.kind, feats: fs, ids, layer: "areas", mask: p.mask, weight: 2e9 / (1 + (p.rank ?? 9)) });
  }
}
// the main lines: a road by its number or name -- its lines of that number that meet end to end (Germany's A1 and
// Italy's are two; a motorway's "A1" is found with its kind)
export const ROAD_MIN_FOUND_KM = 10;                                       // (a few km of a first-class road: too many to name)
export function indexLines(L, layers) {
  const add = addToIndex;
  for (const layer of layers) {
    const by = new Map();
    L[layer].forEach((f, i) => { const p = f.properties, k = p.ref || p.name; if (!k || !f.has() || (layer === "roads" && lengthKm(f) < ROAD_MIN_FOUND_KM)) return; if (!by.has(k)) by.set(k, []); by.get(k).push(i); });
    for (const all of by.values()) {
      const up = new Map(all.map((i) => [i, i])), find = (i) => { while (up.get(i) !== i) i = up.get(i); return i; }, end = new Map();
      for (const i of all) { for (const k of endsOf(L[layer][i])) { const j = end.get(k); if (j == null) end.set(k, i); else up.set(find(i), find(j)); } }
      const parts = new Map(); for (const i of all) { const r = find(i); if (!parts.has(r)) parts.set(r, []); parts.get(r).push(i); }
      for (const ids of parts.values()) {
        const fs = ids.map((i) => L[layer][i]), p = fs[0].properties, km = fs.reduce((s, f) => s + lengthKm(f), 0);
        const kind = layer === "motorways" ? p.class : layer === "roads" ? `${p.class} road` : layer === "railways" ? (p.highspeed ? "high-speed railway" : "railway") : `${p.substance} pipeline`;
        add({ cat: "line", name: p.name || p.ref, alt: p.ref, kind, feats: fs, ids, layer, weight: km * 10, info: [`${fmt(Math.round(km))} km`, p.operator] });
      }
    }
  }
}
// a point layer: each point by its name (a monument weighs less than a city of its name -- Rabat the city before Rabat
// the World Heritage Site)
export function indexPoints(k) {
  const add = addToIndex, countryName = Object.fromEntries(Map0.countries.map((f) => [f.properties.iso, f.properties.name]));
  for (const [set, kindOf, weight, info] of [
    [S.src.cities, (p) => `${p.capital === "country" ? "capital" : "city"} · ${p.country || "?"}`, (p) => p.population, (p) => [`${fmtPop(p.population)} people`, countryName[p.country]]],
    [S.src.monuments, (p) => `${p.kind} · ${p.country || "?"}`, (p) => (4 - (p.level ?? 3)) * 2e4 + (p.visitors || 0) / 1e3, (p) => [p.visitors ? `${fmt(p.visitors)} visitors/yr${p.visitors_year ? " (" + p.visitors_year + ")" : ""}` : null, countryName[p.country]]],
    [S.src.airports, (p) => `airport · ${p.country || "?"}`, (p) => (p.passengers || 0) / 10, (p) => [[p.iata, p.icao].filter(Boolean).join(" / "), p.city, p.passengers ? `${fmtPop(p.passengers)} passengers/yr${p.passengers_year ? " (" + p.passengers_year + ")" : ""}` : null]],
    [S.src.nature, (p) => p.kind, (p) => (p.elevation_m || 0) * 100, (p) => [p.elevation_m != null && `${fmt(p.elevation_m)} m`]],
    [S.src.events, (p) => `${p.kind} · ${showDay(p.date)}`, (p) => (p.wikipedias || 0) * 100, (p) => [p.part_of, p.calendar === "julian" ? "Julian calendar" : null, p.place === "location" ? "at the place it happened in" : null, `${p.wikipedias} Wikipedias`]],
  ]) {
    if (!set || set !== S.src[k]) continue;
    for (const f of set.features) {
      const p = f.properties;
      add({ cat: "point", name: p.name, alt: p.name_local || p.name_en, kind: kindOf(p), feats: [f], at: f.geometry.coordinates, weight: weight(p), info: info(p),   // (name_en: a peak's or cape's -- Cabo de Hornos, Cape Horn)
            ...(set === S.src.events ? { span: [p.date, p.date] } : {}) });   // (an event: chosen, the historical map on its day)
    }
  }
}
// TYPING NARROWS: a query that only adds letters to the last one can match nothing the last one did not, so it looks
// only among those (every match, not the 30 shown) -- the first letter scans the ~55,000 names, the rest a handful.
// (The names stay in memory: a scan of them takes milliseconds; IndexedDB would make each one slower, not faster.)
S.narrow = { n: null, size: -1, hits: null };
export function search(q) {
  const n = norm(q).trim();
  if (!n) return [];
  const pool = S.narrow.n !== null && n.startsWith(S.narrow.n) && S.narrow.size === index.length ? S.narrow.hits : index;   // (the index grows as bio and history load)
  const out = [], hits = [];
  for (const e of pool) {
    let s = 9;
    for (const k of e.keys) {
      const i = k.indexOf(n);
      if (i < 0) continue;
      s = Math.min(s, k === n ? 0 : i === 0 ? 1 : /[\s\-'(]/.test(k[i - 1]) ? 2 : 3);
    }
    if (s < 9) { out.push([s, -e.weight, e]); hits.push(e); }
  }
  S.narrow = { n, size: index.length, hits };
  out.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return out.slice(0, 30).map((r) => r[2]);
}
