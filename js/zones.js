// zones.js -- THE TIME ZONES (layer 18): data/timezones.txt (build/timezones.py: timezone-boundary-builder's zones with
// the oceans) -- each zone tinted by its offset from UTC, the borders where the clock changes over them (faint where it
// does not: Germany / France), the offsets written in the zones; a click's zone (Europe/Berlin, its offset, its daylight
// saving, the time there now: the browser's own clock and time zone rules, Intl), the zones and the offsets found by name
// ("Europe/Berlin", "UTC+5:30"). Read when the layer is switched on, or a search looks like one (ui.js).
import { S } from "./state.js";
import { css, dark } from "./state.js";
import { Map0 } from "./geom.js";
import { writeName, visible } from "./labels.js";
import { addToIndex } from "./search.js";

// "UTC+5:30", "UTC-3", "UTC+0" (minutes east of Greenwich)
export const offText = (m) => `UTC${m < 0 ? "-" : "+"}${Math.floor(Math.abs(m) / 60)}${Math.abs(m) % 60 ? ":" + String(Math.abs(m) % 60).padStart(2, "0") : ""}`;
// THE COLOURS: round the colour wheel once a day (an hour 15° on), every other hour lighter -- so two zones side by side
// always differ, and the order still shows; a zone of a half or three quarters (India's +5:30, Nepal's +5:45) the hue
// between its two hours, darker and stronger: it stands out of both
export function zoneColour(m) {
  const h = m / 60, whole = Math.floor(h), part = h !== whole, hue = (((h + 12) * 15) % 360 + 360) % 360, dk = dark();
  const odd = ((whole % 2) + 2) % 2;
  return part ? `hsl(${hue} 85% ${dk ? 42 : 48}%)` : `hsl(${hue} ${dk ? 45 : 65}% ${dk ? (odd ? 26 : 40) : (odd ? 62 : 84)}%)`;
}
// the zones in view by colour, and their borders: the clock's changes, then (closer in, at rest) the faint ones
export function drawZones(v, fillAll, stroke, lv, fast) {
  const Z = Map0.zones, by = {};
  for (const i of v("zones")) { const f = Z[i]; if (f.has(lv)) (by[zoneColour(f.properties.utc)] ??= []).push(i); }
  return { fill: () => { for (const c in by) fillAll(Z, by[c], c); },
    lines: () => {
      const B = Map0.zone_borders, ids = v("zone_borders"), dk = dark();
      if (S.zoom >= 3 && !fast) stroke(B, ids.filter((i) => B[i].properties.same), dk ? "#ffffff30" : "#00000024", 0.5);
      stroke(B, ids.filter((i) => !B[i].properties.same), dk ? "#e8e8e8b0" : "#3a3a3aa0", 0.9);
    } };
}
// the offsets written in the zones: the biggest first (the sea's strips, whole continents' zones), more the closer in
let bySize = null;
export function zoneLabels(boxes) {
  bySize ??= [...Map0.zones].sort((a, b) => (b.properties.area_km2 || 0) - (a.properties.area_km2 || 0));
  const min = 3e6 / (S.zoom * S.zoom), ink = css("--ink");
  for (const f of bySize) { const p = f.properties;
    if ((p.area_km2 || 0) < min) break;
    if (p.label && visible(p.label) && !(S.sel && S.sel.feats?.includes(f))) writeName(boxes, offText(p.utc), p.label, 11, 600, ink); }
}
// what is said of a zone: its offset, its daylight saving, and the time there as the clock reads now (the browser's rules
// for that id: a sea zone's Etc/GMT+5 is UTC-5, POSIX's sign; a land zone's the browser may know newer than the file)
const clock = (tz) => { try { return new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", weekday: "short" }).format(new Date()); } catch (e) { return null; } };
export function zoneInfo(p) {
  const dst = p.dst == null ? "no daylight saving" : p.dst > p.utc ? `daylight saving ${offText(p.dst)}${p.dst_abbr ? " (" + p.dst_abbr + ")" : ""}` : `${offText(p.dst)} for part of the year${p.dst_abbr ? " (" + p.dst_abbr + ")" : ""}`;
  const now = clock(p.tzid);
  return [`${offText(p.utc)}${p.abbr ? " (" + p.abbr + ")" : ""}`, dst, now ? `now ${now}` : null, p.tzid.startsWith("Etc/") ? "nautical time at sea" : null];
}
// found by name: each zone by its id (and its city: "Berlin" -- below the city itself), each offset with all its zones
export function indexZones(L) {
  const by = new Map();
  L.zones.forEach((f, i) => { const p = f.properties; if (!f.has()) return;
    if (!by.has(p.utc)) by.set(p.utc, []); by.get(p.utc).push(i);
    addToIndex({ cat: "zone", name: p.tzid, alt: [p.tzid.split("/").pop().replace(/_/g, " "), p.abbr, p.dst_abbr].filter(Boolean).join(" / "), kind: `time zone · ${offText(p.utc)}`,
                 feats: [f], ids: [i], layer: "zones", at: p.label, weight: 10 + (p.area_km2 || 0) / 1e6, get info() { return zoneInfo(p).slice(1); } }); });
  for (const [m, ids] of by) {
    const n = ids.filter((i) => !L.zones[i].properties.tzid.startsWith("Etc/")).length;
    addToIndex({ cat: "zone", name: offText(m), alt: m ? null : "GMT", kind: `time offset · ${n} zone${n === 1 ? "" : "s"}`, feats: ids.map((i) => L.zones[i]), ids, layer: "zones",
                 at: L.zones[ids[0]].properties.label, weight: 1e8, offset: m });
  }
}
