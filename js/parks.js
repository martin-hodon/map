// parks.js -- THE PARKS' AREAS: the national parks and protected areas of layer 5 as their OSM outlines (data/parks.txt,
// build/parks.py), drawn with the monuments, green, outlined, where a park is more than a few pixels across; smaller it
// is the monument's point alone. Drawn big, the park's tree icon goes and its name stays (written at its point when its
// tier would not show it yet). Read once the map is close enough to draw one (PARK_ZOOM), at rest.
import { S } from "./state.js";
import { dark } from "./state.js";
import { Map0 } from "./geom.js";
import { pxKm } from "./history.js";
import { writeName, visible, shown } from "./labels.js";
import { fmt } from "./state.js";

export const PARK_ZOOM = 3;           // (from here the file is read: the biggest parks, Greenland's, the Sahara's, are a few pixels at 2x)
const MIN_PX = 4, ICON_PX = 30;       // (an area drawn from this many pixels across; its icon left out from this many)
const across = (f) => Math.sqrt(f.properties.area_km2 || 0) / pxKm();
export const parkInk = () => dark() ? { fill: "#4caf5050", line: "#8fd88f" } : { fill: "#2e7d3240", line: "#2e7d32" };
// the parks in view big enough to draw, filled and outlined -> the items of the monuments drawn as areas (their wikidata)
export function drawParks(v, fillAll, stroke, lv) {
  const P = Map0.parks, ids = v("parks").filter((i) => P[i].has(lv) && across(P[i]) >= MIN_PX), ink = parkInk();
  fillAll(P, ids, ink.fill); stroke(P, ids, ink.line, 0.9);
  return new Set(ids.filter((i) => across(P[i]) >= ICON_PX).map((i) => P[i].properties.wikidata));
}
// a big park's name where its monument's tier does not show it yet (the monuments' names are placed first)
export function parkNames(placed, big) {
  if (!big.size || !S.src.monuments) return;
  const F = S.src.monuments.features, ink = parkInk().line;
  S.parkRow ??= new Map(F.map((f, i) => [f.properties.wikidata, i]));
  for (const q of big) { const i = S.parkRow.get(q); if (i == null || shown("monuments", i)) continue;
    const at = F[i].geometry.coordinates; if (visible(at)) writeName(placed, F[i].properties.name, at, 11, "italic 500", ink); }
}
// the park under a click (drawn as an area there): what the click lists
export function parksAt(ll, ids) {
  const P = Map0.parks;
  return ids.filter((i) => P[i].has() && across(P[i]) >= MIN_PX && d3.geoContains(P[i], ll)).map((i) => { const p = P[i].properties;
    return { cat: "park", name: p.name, kind: `${p.kind} · area`, feats: [P[i]], info: [`${fmt(p.area_km2)} km²`, `OSM ${p.osm}`] }; });
}
