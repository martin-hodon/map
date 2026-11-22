// shown.js -- WHAT IS ON THE MAP: is a thing found (by a click, by name, from a list) drawn with the layers and the map
// as they are now -- and, when one that is not is chosen, the map and the layers switched so that it is. A click lists
// only what is shown (a country on the geographical map is not: its borders are not drawn); a search finds everything,
// and the choice brings its layer.
import { $, on } from "./state.js";
import { mode, bioLayer } from "./style.js";

const UNITS = new Set(["political", "language", "density"]);            // (the maps the countries and states are drawn on)
const LINE_BOX = { motorways: "motorways", roads: "motorways", railways: "railways", pipelines: "pipelines" };   // (the first-class roads come with the motorways)

// what it needs: the map (`mode`), the biogeographic level, the boxes to be ticked
function needs(e) {
  if (e.layer === "plates") return { boxes: ["plates"] };                 // (a plate, a plate boundary: plates.js)
  if (e.layer === "hperiods" || e.cat === "history" || e.span) return { mode: "history", boxes: e.src === "events" ? ["events"] : [] };
  switch (e.cat) {
    case "country": return { mode: UNITS.has(mode()) ? null : "political", boxes: ["countries"] };
    case "region": return { mode: UNITS.has(mode()) ? null : "political", boxes: ["countries", "regions"] };
    case "lake": return { boxes: ["land"] };
    case "area": return { boxes: ["areas"] };
    case "river": return { boxes: ["rivers"] };
    case "line": return { boxes: [LINE_BOX[e.layer]].filter(Boolean) };
    case "point": return { boxes: e.src ? [e.src] : [] };
    case "zone": return { boxes: ["timezones"] };                       // (a time zone, an offset: zones.js)
    case "park": return { boxes: ["monuments"] };                       // (a park's area: parks.js)
    case "bio": return { mode: "bio", level: e.layer === "realms" ? null : e.layer, boxes: [] };
    default: return { boxes: [] };                                        // (a war: shown on the historical map it chooses itself)
  }
}
export function isShown(e) {
  const n = needs(e);
  return (!n.mode || mode() === n.mode) && (!n.level || bioLayer() === n.level) && n.boxes.every(on);
}
// make it shown: its map first (a map chosen ticks its own layers), then its level and its boxes -> whether anything changed
// (the handlers' work done here, not through them: they let go of a choice no longer shown -- this one's predecessor,
//  and the search box with it)
export function showFor(e, { modeChanged, levelShown, togglesShown, wanted }) {
  if (isShown(e)) return false;
  const n = needs(e);
  if (n.level && bioLayer() !== n.level) { $("biolevel").value = n.level; try { localStorage.biolevel = n.level; } catch { } }
  if (n.mode && mode() !== n.mode) { $("mode").value = n.mode; try { localStorage.mode = n.mode; } catch { } modeChanged(false); }
  else if (n.level) levelShown();
  for (const k of n.boxes) document.querySelector(`[data-layer="${k}"]`).checked = true;
  togglesShown(); wanted();
  return true;
}
