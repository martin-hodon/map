// style.js -- colours and legends: the projections, the palettes, the states' shades, the geographical kinds, languages, density, the biogeographic colours, the legend, the panel's roll
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { $ } from "./state.js";
import { neighbors, Map0, B0 } from "./geom.js";

export const PROJ = {   // (the first is the default)
  "Orthographic (globe)": () => d3.geoOrthographic().clipAngle(90),
  "Equal Earth": () => d3.geoEqualEarth(), "Natural Earth": () => d3.geoNaturalEarth1(), "Robinson": () => d3.geoRobinson(),
  "Mercator": () => d3.geoMercator(),
  "Equirectangular": () => d3.geoEquirectangular(), "Azimuthal equal-area": () => d3.geoAzimuthalEqualArea().clipAngle(179.9),
  "Winkel tripel": () => d3.geoWinkel3(), "Mollweide": () => d3.geoMollweide(),
};
// the countries' colours: each has a class (`color`, 0-6, no two neighbours the same -- build/write.py), and a
// palette gives each class its colour. Light ones for the light scheme, dark ones for the dark; "none" is the plain land.
export const PALETTES = {
  "pastel": ["#f3d9c4", "#d6e6c3", "#cfdcec", "#f4e3a8", "#e6d3e8", "#c9e5e0", "#f0cfd2", "#e2dcc8"],
  "light": ["#f7e8dc", "#e8f0dd", "#e3ebf4", "#f8f0d0", "#f0e6f1", "#e0f0ed", "#f6e3e5", "#eeeae0"],
  "muted": ["#d9b99b", "#b5c9a0", "#a9bfd3", "#ddca8a", "#c8b3cc", "#a4cdc5", "#d6afb3", "#c6bfa8"],
  "vivid": ["#f5a66a", "#9bcf6e", "#7cb0e6", "#f2d75c", "#c99be0", "#6fcfc0", "#f08c9a", "#c2b56f"],
  "dark muted": ["#5a4634", "#3e4d32", "#33424f", "#5a5230", "#4b3a4f", "#2f4a45", "#553a3e", "#45423a"],
  "dark vivid": ["#7d4a1e", "#3f5f1f", "#1f4a73", "#736318", "#5b2f6e", "#1a5f58", "#742c39", "#5b5320"],
  "earth": ["#c9a97a", "#a3ad7c", "#9fb3a8", "#d1b98c", "#b39b84", "#8fa98f", "#c5a08e", "#b7b08f"],
  "greys": ["#e8e8e8", "#d4d4d4", "#dedad4", "#cfd3d6", "#e0dcd8", "#d8dcd2", "#e3e0e6", "#cdcdcd"],
  "none": null,
};
export const palette = () => PALETTES[$("palette").value];
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
// the two maps: POLITICAL -- countries coloured, their borders and their states' -- and GEOGRAPHICAL -- the seas,
// gulfs, mountains, deserts, plateaus, plains... coloured by their kind (the bigger under the smaller). The natural
// lines -- coast, islands, lakes -- and everything else are on both.
export const GEO = {
  ocean: "#c4d9e9", sea: "#bcd3e5", gulf: "#b3cde1", bay: "#b3cde1", sound: "#b3cde1", channel: "#b3cde1", strait: "#b3cde1", fjord: "#b3cde1",
  inlet: "#b3cde1", lagoon: "#aed0d8", estuary: "#b3cde1", reef: "#a9d3cf", lake: "#bcd3e5",
  mountains: "#c9b199", foothills: "#d7c6b0", plateau: "#dbcaa5", desert: "#f0dba8", plain: "#dbe6c0", lowland: "#dbe6c0", basin: "#e0e4c6",
  valley: "#cfdcb8", gorge: "#cfdcb8", delta: "#bfdac4", wetlands: "#bfdac4", tundra: "#e0e7dc", depression: "#e7d8be",
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
  order.forEach((l, i) => { S.langColour[l] = i < LANG_COLOURS.length ? LANG_COLOURS[i] : "#d8d8d8"; });
  return order;
}
export function legend() {
  const el = $("legend"), m = mode();
  el.style.display = (m === "language" || m === "density" || m === "history" || (m === "bio" && bioLayer() !== "ecoregions" && S.src && S.src.bio)) ? "block" : "none";
  el.innerHTML = "";
  if (m === "language") {
    const order = rankLanguages();
    for (const l of order.slice(0, LANG_COLOURS.length)) el.append(Object.assign(document.createElement("span"), { innerHTML: `<i style="background:${S.langColour[l]}"></i>${l}` }));
    el.append(Object.assign(document.createElement("span"), { innerHTML: `<i style="background:#d8d8d8"></i>other` }));
  } else if (m === "density") {
    let lo = 0;
    for (const [lim, c] of DENSITY) { el.append(Object.assign(document.createElement("span"), { innerHTML: `<i style="background:${c}"></i>${lim === Infinity ? lo + "+" : lo + "–" + lim}` })); lo = lim; }
    el.append(Object.assign(document.createElement("span"), { textContent: "people per km²" }));
  } else if (m === "bio" && S.src && S.src.bio) {
    for (const f of B0[bioLayer()]) { const p = f.properties; el.append(Object.assign(document.createElement("span"), { innerHTML: `<i style="background:${bioColour(p)}"></i>${p.name}` })); }
  } else if (m === "history") {
    el.append(Object.assign(document.createElement("div"), { textContent: "a dependency: paler, in its ruler's colour · a people or culture (no state): pale, its name grey · a blurred border: approximate (all before 1650) · dashed: to land no state held · ◆ events within a few years (the further back, the more)" }));
  }
}
export const bioColour = (p) => REALM_COLOURS[p.id] || p.color || "#d8d8d8";
// the panel rolled up or down (up at every start: the buttons only)
export const roll = (up) => { $("panel").classList.toggle("rolled", up); $("roll").textContent = up ? "▾" : "▴"; $("roll").setAttribute("aria-expanded", String(!up)); };

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  for (const k of Object.keys(PROJ)) $("proj").add(new Option(k, k));
  for (const k of Object.keys(PALETTES)) $("palette").add(new Option(k === "none" ? "no country colours" : k + " colours", k));
  $("roll").onclick = () => roll(!$("panel").classList.contains("rolled"));
  // R rolls it too -- anywhere but in a field you type or choose in
  document.addEventListener("keydown", (ev) => {
    if (ev.key.toLowerCase() !== "r" || ev.ctrlKey || ev.metaKey || ev.altKey || ev.target.closest?.("input, select, textarea, [contenteditable]")) return;
    roll(!$("panel").classList.contains("rolled")); ev.preventDefault();
  });
  roll(true);
  try { if ($("mode").querySelector(`[value="${localStorage.mode}"]`)) $("mode").value = localStorage.mode; } catch (e) { }
}
