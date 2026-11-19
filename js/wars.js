// wars.js -- the wars and campaigns (data/campaigns.json: build/campaigns.py): each a group of the historical events
// (events.csv rows) and of smaller ones (the Waterloo Campaign in the Hundred Days in the Napoleonic Wars), and the
// MOVES between its battles -- lines from one battle to the next its army is taken to have fought.
// On the historical map the day's moves are drawn faintly between the day's events. A war chosen (found by name, from
// the ⚔ list, or an event's "part of") is drawn whole whatever the day: its moves in a colour per campaign, with
// arrows, its events numbered by date -- and listed in the panel, with its parts and what it was part of.
import { S, ctx } from "./state.js";
import { histOn, showYear, showDay, histDay, yearOf, yearText } from "./history.js";
import { fetchText } from "./data.js";
import { addToIndex } from "./search.js";
import { shown, visible } from "./labels.js";

S.wars = null;      // { G: the groups, kids: gi -> [gi], of: event row -> gi, moves: [[a, b, gi]] }
S.war = null;       // the war drawn whole (a group's index), or null
const COLOURS = ["#d7263d", "#1b6ca8", "#2e933c", "#e07a00", "#7b3fa0", "#00897b", "#a0522d", "#c2185b"];

export const years = (g) => g.from == null ? "" : g.to == null || g.to === g.from ? showYear(g.from) : `${showYear(g.from)}–${g.to <= 0 ? showYear(g.to) : g.to}`;
// a group and every group within it
export function within(gi) { const out = [gi]; for (let k = 0; k < out.length; k++) out.push(...(S.wars.kids.get(out[k]) || [])); return out; }
// its events, its parts' too, by date
export function eventsOf(gi) {
  const F = S.src.events.features, rows = within(gi).flatMap((g) => S.wars.G[g].events);
  return rows.sort((a, b) => dayKey(F[a].properties.date) - dayKey(F[b].properties.date));
}
// (a date cut to its year or month: the middle of it -- the Siege of Metz, "1870", among the summer's battles, not before them)
const dayKey = (d) => { const m = /^(-?\d+)(?:-(\d\d))?(?:-(\d\d))?/.exec(d || ""); return m ? +m[1] * 10000 + +(m[2] || 7) * 100 + +(m[3] || (m[2] ? 15 : 1)) : 0; };
const pointOf = (row) => S.src.events.features[row].geometry.coordinates;

export async function loadWars() {
  const t = await fetchText("campaigns.json");
  if (!t || !S.src.events) return;
  const G = JSON.parse(t).groups, kids = new Map(), of = new Map(), moves = [];
  G.forEach((g, gi) => {
    if (g.parent >= 0) { if (!kids.has(g.parent)) kids.set(g.parent, []); kids.get(g.parent).push(gi); }
    for (const r of g.events) of.set(r, gi);
    for (const [a, b] of g.moves) moves.push([a, b, gi]);
  });
  S.wars = { G, kids, of, moves };
  G.forEach((g, gi) => {
    const rows = eventsOf(gi); if (!rows.length) return;
    const coords = rows.map(pointOf), lon = coords.map((c) => c[0]), lat = coords.map((c) => c[1]);
    addToIndex({ cat: "war", war: gi, name: g.name, kind: `${g.kind} · ${years(g)}`, info: [`${rows.length} events`], weight: 5e5 + rows.length * 1e4,
      feats: [{ type: "Feature", properties: {}, geometry: { type: "MultiPoint", coordinates: coords } }],
      at: [(Math.min(...lon) + Math.max(...lon)) / 2, (Math.min(...lat) + Math.max(...lat)) / 2],
      span: [yearText(g.from ?? yearOf(S.src.events.features[rows[0]].properties.date)) + "-01-01", yearText(g.to ?? g.from ?? 0) + "-12-31"] });
  });
}

// ---- drawing (view.js, before the events' diamonds) -----------------------------------------------------------------
// a move as a line over the globe, with an arrowhead short of its end (the battle's mark stays clear)
function move(a, b, colour, width, head) {
  ctx.beginPath(); S.path({ type: "LineString", coordinates: [a, b] }); ctx.strokeStyle = colour; ctx.lineWidth = width; ctx.stroke();
  if (!visible(b)) return;
  const pb = S.proj(b), pm = S.proj(d3.geoInterpolate(a, b)(0.85));
  if (!pb || !pm) return;
  const dx = pb[0] - pm[0], dy = pb[1] - pm[1], L = Math.hypot(dx, dy);
  if (L < head * 1.5) return;                                   // (too short to show which way)
  const ux = dx / L, uy = dy / L, tx = pb[0] - ux * 6, ty = pb[1] - uy * 6;
  ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx - ux * head - uy * head * .55, ty - uy * head + ux * head * .55);
  ctx.lineTo(tx - ux * head + uy * head * .55, ty - uy * head - ux * head * .55); ctx.closePath(); ctx.fillStyle = colour; ctx.fill();
}
export function drawWars(dk) {
  if (!S.wars || !S.src.events) return;
  const { G, moves } = S.wars;
  if (S.war == null) {                                          // (the day's: between two events both shown)
    const now = histOn(), c = dk ? "#ff7a8acc" : "#b0124a99";
    for (const [a, b] of moves) if (now.events.has(a) && now.events.has(b) && shown("events", a) && shown("events", b)) move(pointOf(a), pointOf(b), c, 1.3, 6);
    return;
  }
  const gs = within(S.war), colour = new Map(gs.map((g, k) => [g, COLOURS[k % COLOURS.length]]));
  ctx.save(); ctx.setLineDash([]);
  for (const g of gs) for (const [a, b] of G[g].moves) { move(pointOf(a), pointOf(b), dk ? "#000a" : "#fffc", 4.5, 0); move(pointOf(a), pointOf(b), colour.get(g), 2.2, 8); }
  const rows = eventsOf(S.war);
  ctx.font = "600 9px system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  rows.forEach((r, k) => {
    const c = pointOf(r); if (!visible(c)) return;
    const [x, y] = S.proj(c), n = String(k + 1), R = n.length > 2 ? 8.5 : 7;
    ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fillStyle = colour.get(S.wars.of.get(r)) || "#555"; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = dk ? "#000" : "#fff"; ctx.stroke();
    ctx.fillStyle = "#fff"; ctx.fillText(n, x, y + .5);
  });
  ctx.restore();
}

// ---- the panel ------------------------------------------------------------------------------------------------------
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };
// a group's line in a list: its name, its years and events; a click chooses it
function warItem(gi, choose) {
  const g = S.wars.G[gi], n = eventsOf(gi).length;
  const li = el("li", {}, el("span", { textContent: g.name }), el("span", { textContent: `${years(g)} · ${n}` }));
  li.title = `${g.kind}: ${n} events`; li.onclick = () => choose(gi);
  return li;
}
// what a war chosen adds to the panel: the wars it was part of, its parts, its events by date (numbered as on the map)
export function warInfo(gi, info, choose, chooseEvent) {
  const { G } = S.wars, g = G[gi];
  const up = []; for (let p = g.parent; p >= 0; p = G[p].parent) up.push(p);
  if (up.length) {
    const d = el("div", { className: "kind" }, "part of ");
    up.forEach((p, k) => { if (k) d.append(" › "); d.append(el("a", { href: "#", textContent: G[p].name, onclick: (ev) => { ev.preventDefault(); choose(p); } })); });
    info.append(d);
  }
  const parts = S.wars.kids.get(gi) || [];
  if (parts.length) info.append(el("div", { className: "kind", textContent: `${parts.length} parts:` }), el("ul", {}, ...parts.map((p) => warItem(p, choose))));
  const rows = eventsOf(gi), F = S.src.events.features, of = S.wars.of;
  const colour = new Map(within(gi).map((x, k) => [x, COLOURS[k % COLOURS.length]]));
  info.append(el("div", { className: "kind", textContent: `${rows.length} events, ${within(gi).reduce((s, x) => s + G[x].moves.length, 0)} moves (a guess from places and dates):` }));
  const ol = el("ol", { className: "wars-events" });
  rows.forEach((r, k) => {
    const p = F[r].properties, li = el("li", {},
      el("span", {}, el("b", { textContent: `${k + 1}`, style: `background:${colour.get(of.get(r))}` }), " " + p.name),
      el("span", { textContent: `${showDay(p.date)}` }));
    li.title = `${p.kind}${of.get(r) !== gi ? " · " + G[of.get(r)].name : ""}`; li.onclick = () => chooseEvent(r);
    ol.append(li);
  });
  info.append(ol);
}
// an event chosen: the wars it was part of, each a link
export function eventWars(row, info, choose) {
  if (!S.wars || !S.wars.of.has(row)) return null;
  const { G } = S.wars, d = el("div", { className: "kind" }, "part of ");
  let first = true;
  for (let p = S.wars.of.get(row); p >= 0; p = G[p].parent) {
    if (!first) d.append(" › "); first = false;
    const q = p; d.append(el("a", { href: "#", textContent: `${G[p].name} (${years(G[p])})`, onclick: (ev) => { ev.preventDefault(); choose(q); } }));
  }
  info.append(d);
  return S.wars.of.get(row);
}
// the ⚔ list: the wars at the day shown first, then every war by its start; typing narrows it to the names that match
export function warList(info, choose) {
  const { G } = S.wars, y = yearOf(histDay());
  const box = el("input", { type: "search", placeholder: `filter ${G.length} wars and campaigns`, className: "wars-filter" });
  const ul = el("ul", { className: "wars-list" });
  const fill = () => {
    const q = box.value.trim().toLowerCase(); ul.innerHTML = "";
    const match = (g) => !q || g.name.toLowerCase().includes(q);
    const now = G.map((g, i) => i).filter((i) => G[i].parent < 0 && G[i].from != null && G[i].from <= y && y <= (G[i].to ?? G[i].from) && match(G[i]));
    const all = G.map((g, i) => i).filter((i) => (q ? match(G[i]) : G[i].parent < 0) && !now.includes(i));
    if (now.length) { ul.append(el("li", { className: "head", textContent: `at ${showYear(y)}` })); now.forEach((i) => ul.append(warItem(i, choose))); }
    ul.append(el("li", { className: "head", textContent: q ? "matching" : "all, by their start" }));
    all.forEach((i) => ul.append(warItem(i, choose)));
  };
  box.oninput = fill; fill();
  info.append(el("h2", { textContent: "Wars and campaigns" }), el("div", { className: "kind", textContent: "the events gathered into the wars they were part of (Wikidata); a click draws one whole" }), box, ul);
  box.focus();
}
