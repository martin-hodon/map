// groups.js -- my groups: countries or biogeographic regions in coloured groups, kept in the browser and in a link
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { mode, bioLayer } from "./style.js";
import { $, ctx, css, trees } from "./state.js";
import { trace, Map0, B0 } from "./geom.js";
import { query, draw } from "./view.js";
import { visible } from "./labels.js";
import { SHAPES, unitFeat } from "./game.js";

// ---- MY GROUPS: countries (on the political map) or biogeographic regions (on the biogeographical one, at the level
// shown) put into groups, each one colour. With "a click puts it into the chosen group" on, a click puts the country or
// region under it into the chosen group (out of any other), a second click takes it out. Kept in the browser
// (localStorage "map:groups"); "copy link" gives this map with them (#groups=...); a link may also show one list:
// #bio=PA,E345,B7 (realms, ecoregions, biomes), #countries=SK,CZ (ISO codes). An item is `layer:id`.
export const GROUP_COLOURS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#9a6324", "#469990", "#800000", "#000075"];
S.groups = []; S.activeGroup = 0; S.linked = false;
export const idOf = {};                                                    // (layer -> id -> its feature: countries by ISO code, the rest by id)
export const groupLayer = () => mode() === "bio" ? bioLayer() : "countries";
export const groupsOn = (layer) => S.groups.some((g) => g.items.some((k) => k.startsWith(layer + ":")));
export const featureOf = (key) => { const [layer, id] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)], i = idOf[layer]?.get(id);
  return i == null ? null : (layer === "countries" ? Map0.countries : S.src.bio ? B0[layer] : [])[i]; };
export function drawGroups(L, B, v, fillAll) {
  const m = mode(), layers = m === "bio" ? ["realms", "biomes", "ecoregions"] : m === "geographical" || m === "history" ? [] : ["countries"];
  for (const layer of layers) {                                     // (the bigger units under the smaller ones)
    const F = layer === "countries" ? L.countries : B && B[layer];
    if (!F || !idOf[layer]) continue;
    const shown = new Set(v(layer));
    for (const g of S.groups) {
      const ids = g.items.filter((k) => k.startsWith(layer + ":")).map((k) => idOf[layer].get(k.slice(layer.length + 1))).filter((i) => i != null && shown.has(i));
      if (ids.length) { ctx.globalAlpha = 0.8; fillAll(F, ids, g.color); ctx.globalAlpha = 1; }
    }
  }
}
export function saveGroups(again = true) {
  S.linked = false;
  try { localStorage["map:groups"] = JSON.stringify(S.groups); } catch (e) { }
  if (again) renderGroups();
  draw();
}
export function addGroup() {
  S.groups.push({ name: `group ${S.groups.length + 1}`, color: GROUP_COLOURS[S.groups.length % GROUP_COLOURS.length], items: [] });
  S.activeGroup = S.groups.length - 1;
}
export function groupClick(e) {                                            // (the country or region under the pointer: into the chosen group, or out)
  const ll = S.proj.invert([e.clientX, e.clientY]);
  if (!ll || !isFinite(ll[0]) || !visible(ll)) return;
  const layer = groupLayer(), F = layer === "countries" ? Map0.countries : S.src.bio ? B0[layer] : null;
  if (!F || !trees[layer]) return;
  const i = query(trees[layer], [[ll[0], ll[1], ll[0], ll[1]]]).find((i) => F[i].has() && d3.geoContains(F[i], ll));
  if (i == null) return;
  const key = `${layer}:${F[i].properties[layer === "countries" ? "iso" : "id"]}`;
  if (!S.groups.length) addGroup();
  S.activeGroup = Math.min(S.activeGroup, S.groups.length - 1);
  const g = S.groups[S.activeGroup], had = g.items.includes(key);
  for (const x of S.groups) x.items = x.items.filter((k) => k !== key);
  if (!had) g.items.push(key);
  saveGroups();
}
export function renderGroups() {
  const box = $("groups"); box.innerHTML = "";
  if (S.groups.length) $("groups-box").open = true;
  S.groups.forEach((g, n) => {
    const row = Object.assign(document.createElement("div"), { className: "row" });
    const pick = Object.assign(document.createElement("input"), { type: "radio", name: "group", checked: n === S.activeGroup, title: "A click puts things into this group" });
    pick.onchange = () => { S.activeGroup = n; };
    const col = Object.assign(document.createElement("input"), { type: "color", value: g.color, title: "Its colour" });
    col.oninput = () => { g.color = col.value; saveGroups(false); };
    const name = Object.assign(document.createElement("input"), { type: "text", value: g.name, title: "Its name" });
    name.onchange = () => { g.name = name.value; saveGroups(false); };
    const names = g.items.map((k) => featureOf(k)?.properties.name || k.split(":")[1]);
    const cnt = Object.assign(document.createElement("span"), { className: "n", textContent: g.items.length, title: names.join(", ") || "empty" });
    const del = Object.assign(document.createElement("button"), { textContent: "×", title: "Delete the group" });
    del.onclick = () => { S.groups.splice(n, 1); S.activeGroup = Math.max(0, Math.min(S.activeGroup, S.groups.length - 1)); saveGroups(); };
    row.append(pick, col, name, cnt, del); box.append(row);
  });
  const what = mode() === "bio" ? { realms: "realms", biomes: "biomes", ecoregions: "ecoregions" }[bioLayer()] : mode() === "geographical" ? null : "countries";
  $("groups-note").textContent = what ? `on this map: ${what}${S.linked ? " · from the link (not kept until changed)" : ""}` : "groups are shown on the political and biogeographical maps";
}
// ---- THE GAME (the button top right): cities of the world, a continent or a country --------------------------------
// "people": name cities -- their people add up, as a share of all the people there. "outside" / "inside": each city
// named gets a circle (so many km across); the next must lie outside every circle / inside one. "place": the game names
// a city, a click says where it is -- a circle round the city out to the click, so many km off (0 is best).
// The countries' games (UNITS, below): "which", "flag", "all", "chain", "route".
// While the game panel is open the map has no names but the cities named, and no points but theirs; a start begins
// it all afresh.
export const game = { open: false, scope: "world", style: "people", where: null, km: 500, named: [], finds: [], ask: null, pool: [], rounds: 10,
               shown() { return SHAPES.has(this.style) ? [] : this.style === "place" ? this.finds.map((f) => f.i) : this.named.slice().sort((a, b) => a - b); } };
export const bareGame = () => game.open && game.bare && game.units && game.ask != null;   // (Bare shape, Bare flag: the one asked alone, no map to go by)
export const pickedStyle = () => $("g-style").value.split(":")[0];         // ("which:bare": the game "which", played bare)
// the screen beside the game's panel (above a phone's, across the top: below it)
export function bareArea() {
  const r = $("game").getBoundingClientRect(), pad = 24, top = r.width > S.W * .6;
  return { x: pad, y: (top ? r.bottom : 0) + pad, w: (top ? S.W : r.left) - 2 * pad, h: S.H - (top ? r.bottom : 0) - 2 * pad };
}
export function drawBare(lv) {
  const A = bareArea();
  if (game.style === "flag") { Object.assign($("g-stage").style, { left: `${A.x}px`, top: `${A.y}px`, width: `${A.w}px`, height: `${A.h}px` }); return; }
  // (fitted here, not by the zoom: a shape's middle is not its label's point, and a zoom has its limits)
  const f = unitFeat(game.ask), [[x0, y0], [x1, y1]] = S.path.bounds(f), k = Math.min(A.w / (x1 - x0 || 1), A.h / (y1 - y0 || 1));
  ctx.save(); ctx.translate(A.x + A.w / 2, A.y + A.h / 2); ctx.scale(k, k); ctx.translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
  ctx.beginPath(); trace(f, lv); ctx.fillStyle = css("--game-fill"); ctx.fill(); ctx.strokeStyle = css("--ink"); ctx.lineWidth = 1.5 / k; ctx.stroke();
  ctx.restore();
}

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  try { S.groups = JSON.parse(localStorage["map:groups"] || "[]"); } catch (e) { S.groups = []; }
  $("add-group").onclick = () => { addGroup(); saveGroups(); $("grouping").checked = true; };
  $("clear-groups").onclick = () => { if (!S.groups.length || confirm("Delete all groups?")) { S.groups = []; S.activeGroup = 0; saveGroups(); } };
  $("link-groups").onclick = async () => {
    const url = `${location.origin}${location.pathname}#mode=${mode()}${mode() === "bio" ? "&level=" + bioLayer() : ""}&groups=${encodeURIComponent(JSON.stringify(S.groups))}`;
    try { await navigator.clipboard.writeText(url); $("groups-note").textContent = "link copied"; } catch (e) { prompt("The link:", url); }
  };
}
