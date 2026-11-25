// style.js -- colours and legends: the projections, the palettes, the states' shades, the geographical kinds, languages, density, the biogeographic colours, the legend, the panel's roll
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { $, make, dark } from "./state.js";
import { neighbors, Map0, B0 } from "./geom.js";

export const PROJ = {   // (the first is the default)
  "Orthographic (globe)": () => d3.geoOrthographic().clipAngle(90),
  "Equal Earth": () => d3.geoEqualEarth(), "Natural Earth": () => d3.geoNaturalEarth1(), "Robinson": () => d3.geoRobinson(),
  "Mercator": () => d3.geoMercator(),
  "Equirectangular": () => d3.geoEquirectangular(), "Azimuthal equal-area": () => d3.geoAzimuthalEqualArea().clipAngle(179.9),
  "Winkel tripel": () => d3.geoWinkel3(), "Mollweide": () => d3.geoMollweide(),
};
// THE COLOURS, three ways (the select beside the map mode -- every map's, not the countries' alone): SOFT, light and
// gentle with every hue its own; BOLD, stronger (a projector, a phone in the sun); EARTH, muted and warm, an atlas's. Each
// colour drawn is a BASE colour (the lists below) put into the scheme's lightness and strength in HCL -- light on the light
// scheme, dark on the dark, so the names over them read on both, and the bases' differences in lightness kept in part
// (k) so neighbours still differ. (Was 8 palettes for the countries alone, 2026-11-24: most too faint or too loud.)
export const SCHEMES = {
  soft:  { light: { L: 86, k: 0.4, c: 0.6, cap: 24 }, dark: { L: 34, k: 0.4, c: 0.42, cap: 17 } },
  bold:  { light: { L: 79, k: 0.55, c: 1.0, cap: 42 }, dark: { L: 40, k: 0.5, c: 0.7, cap: 30 } },
  earth: { light: { L: 81, k: 0.45, c: 0.45, cap: 19, warm: 0.45 }, dark: { L: 33, k: 0.4, c: 0.36, cap: 14, warm: 0.45 } },
};
export const scheme = () => SCHEMES[$("palette").value] ? $("palette").value : "soft";
const TONED = new Map();
// a base colour in the scheme (seq: one of a SEQUENCE, density's -- its lightness kept as it is, on the dark scheme turned
// round: the fewest people dim, the most bright)
export function tone(hex, seq = false) {
  const dk = dark(), key = scheme() + dk + hex + seq;
  let out = TONED.get(key);
  if (out === undefined) {
    const s = SCHEMES[scheme()][dk ? "dark" : "light"], c = d3.hcl(hex);
    let h = c.h;
    if (s.warm && !isNaN(h)) h += Math.max(-40, Math.min(40, ((70 - h) % 360 + 540) % 360 - 180)) * s.warm;   // (earth: every hue a little toward ochre -- at most 18°, a blue still a blue)
    const L = seq ? (dk ? 20 + (96 - c.l) * 0.6 : c.l) : s.L + (c.l - 80) * s.k;
    out = d3.hcl(h, Math.min(s.cap * (seq ? 1.5 : 1), (c.c || 0) * s.c), L).formatHex(); TONED.set(key, out);
  }
  return out;
}
// the countries' colours: each has a class (`color`, 0-6, no two neighbours the same -- build/write.py), each class a hue
const COUNTRY_BASE = ["#f5a66a", "#9bcf6e", "#7cb0e6", "#f2d75c", "#c99be0", "#6fcfc0", "#f08c9a", "#c2b56f"];
export const PALETTES = { soft: "soft colours", bold: "bold colours", earth: "earth colours" };
export const palette = () => COUNTRY_BASE.map((c) => tone(c));
// the states on the political map: each in its country's colour made a little lighter or darker (no two neighbouring
// states of one country alike), so countries differ by hue and the states within one only by shade
export const SHADES = [0, -5, 5, -10, 10, -15];                        // (steps of Lab lightness; 0: the country's own colour)
export let shadeCache = new Map();
S.regionShade = null;
export function regionShades() {                                       // each state's shade: greedy, the most neighbours first
  if (S.regionShade) return S.regionShade;
  const R = Map0.regions, nb = neighbors(R), cc = (i) => R[i].properties.country;
  S.regionShade = new Int8Array(R.length).fill(-1);
  for (const i of R.map((_, i) => i).sort((a, b) => nb[b].length - nb[a].length)) {
    const used = new Set(nb[i].filter((j) => cc(j) === cc(i)).map((j) => S.regionShade[j]));
    let k = 0; while (used.has(k) && k < SHADES.length - 1) k++;
    S.regionShade[i] = k;
  }
  return S.regionShade;
}
export function shade(color, k) {                                      // (a colour near white or black: all the steps moved in)
  const key = color + k;
  if (!shadeCache.has(key)) {
    const c = d3.lab(color), shift = Math.min(0, 97 - c.l - Math.max(...SHADES)) + Math.max(0, 12 - c.l - Math.min(...SHADES));
    c.l += SHADES[k] + shift; shadeCache.set(key, c.formatHex());
  }
  return shadeCache.get(key);
}
export const geoColour = (kind) => tone(GEO[kind]);
// the two maps: POLITICAL -- countries coloured, their borders and their states' -- and GEOGRAPHICAL -- the seas,
// gulfs, mountains, deserts, plateaus, plains... coloured by their kind (the bigger under the smaller). The natural
// lines -- coast, islands, lakes -- and everything else are on both.
export const GEO = {   // (the bases: as strong as the countries', the scheme makes them soft; water blues, the land by how it lies)
  ocean: "#8fbfe6", sea: "#86b8e2", gulf: "#74aede", bay: "#74aede", sound: "#74aede", channel: "#74aede", strait: "#74aede", fjord: "#74aede",
  inlet: "#74aede", lagoon: "#6cc4cf", estuary: "#74aede", reef: "#5fcfc0", lake: "#86b8e2",
  mountains: "#c08a5a", foothills: "#d6ae80", plateau: "#d9b46a", desert: "#f2cf6e", plain: "#a9d27a", lowland: "#a9d27a", basin: "#c7d47a",
  valley: "#8fcf8a", gorge: "#8fcf8a", delta: "#6fc9a0", wetlands: "#6fc9a0", tundra: "#b9cbc0", depression: "#e8a88a",
};  // (not: a peninsula, an isthmus, an island, a continent, a coast, a region -- land of no one colour)
export const geographical = () => $("mode").value === "geographical";
export const mode = () => $("mode").value;
// LANGUAGES: each country and state by its (first official) language -- the widest-spoken ones (by the people of
// the places that have them) in distinct colours, the rest in one grey. DENSITY: people per km2, a sequential scale.
export const LANG_COLOURS = ["#e8a06a", "#8fc27a", "#7fb0e6", "#f2d264", "#c69be0", "#6fcfc0", "#f0919c", "#c9b96f", "#a4d47a", "#d9a8d0",
                      "#8ed3e8", "#f5b98a", "#b4b4e8", "#e0c89a", "#9ad6a8", "#e6a5b8", "#c7d47a", "#a8c8e0"];
export const DENSITY = [[1, "#f5f1e6"], [5, "#f0e3c0"], [20, "#ecd19c"], [50, "#e6b87c"], [100, "#dd9a62"], [250, "#cf7a4e"], [500, "#b95a3f"], [1000, "#963f34"], [Infinity, "#6b2a2a"]];
export const densityColour = (d) => (DENSITY.find(([lim]) => d < lim) || DENSITY[DENSITY.length - 1])[1];
// BIOGEOGRAPHICAL: the land by realm, biome or ecoregion (data/bio.txt, build/bio.py: RESOLVE Ecoregions 2017) --
// a biome and an ecoregion in RESOLVE's own colours, a realm in one of these
export const REALM_COLOURS = { PA: "#e9c77b", NA: "#9cc5a1", NT: "#8fd18a", AT: "#f2a65e", IM: "#e58f8f", AA: "#d8a0d6", OC: "#7fc4e0", AN: "#d9e2ea" };
export const bioLayer = () => $("biolevel").value;
S.langColour = {};
export function rankLanguages() {                                         // (the language colours: by the people speaking them, from the data)
  const people = {};
  for (const f of Map0.countries) { const p = f.properties; if (p.language) people[p.language] = (people[p.language] || 0) + (p.population || 1e5); }
  const order = Object.keys(people).sort((a, b) => people[b] - people[a]);
  S.langColour = {};
  order.forEach((l, i) => { S.langColour[l] = i < LANG_COLOURS.length ? LANG_COLOURS[i] : "#d8d8d8"; });   // (the bases: tone() when drawn)
  return order;
}
export function legend() {
  const el = $("legend"), m = mode();
  el.style.display = (m === "language" || m === "density" || m === "history" || (m === "bio" && bioLayer() !== "ecoregions" && S.src && S.src.bio)) ? "block" : "none";
  el.innerHTML = "";
  if (m === "language") {
    const order = rankLanguages();
    for (const l of order.slice(0, LANG_COLOURS.length)) el.append(make("span", { innerHTML: `<i style="background:${tone(S.langColour[l])}"></i>${l}` }));
    el.append(make("span", { innerHTML: `<i style="background:${tone("#d8d8d8")}"></i>other` }));
  } else if (m === "density") {
    let lo = 0;
    for (const [lim, c] of DENSITY) { el.append(make("span", { innerHTML: `<i style="background:${tone(c, true)}"></i>${lim === Infinity ? lo + "+" : lo + "–" + lim}` })); lo = lim; }
    el.append(make("span", { textContent: "people per km²" }));
  } else if (m === "bio" && S.src && S.src.bio) {
    for (const f of B0[bioLayer()]) { const p = f.properties; el.append(make("span", { innerHTML: `<i style="background:${bioColour(p)}"></i>${p.name}` })); }
  } else if (m === "history") {
    el.append(make("div", { textContent: "a dependency: paler, in its ruler's colour · a people or culture (no state): pale, its name grey · a blurred border: approximate (all before 1650) · dashed: to land no state held · ◆ events within a few years (the further back, the more)" }));
  }
}
export const bioColour = (p) => tone(REALM_COLOURS[p.id] || p.color || "#d8d8d8");
// the panel rolled up or down (up at every start: the buttons only)
export const roll = (up) => { $("panel").classList.toggle("rolled", up); $("roll").textContent = up ? "▾" : "▴"; $("roll").setAttribute("aria-expanded", String(!up)); };

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  for (const k of Object.keys(PROJ)) $("proj").add(new Option(k, k));
  for (const k of Object.keys(PALETTES)) $("palette").add(new Option(PALETTES[k], k));
  $("roll").onclick = () => roll(!$("panel").classList.contains("rolled"));
  // R rolls it too -- anywhere but in a field you type or choose in
  document.addEventListener("keydown", (ev) => {
    if (ev.key.toLowerCase() !== "r" || ev.ctrlKey || ev.metaKey || ev.altKey || ev.target.closest?.("input, select, textarea, [contenteditable]")) return;
    roll(!$("panel").classList.contains("rolled")); ev.preventDefault();
  });
  roll(true);
  try { if ($("mode").querySelector(`[value="${localStorage.mode}"]`)) $("mode").value = localStorage.mode; } catch (e) { }
}
