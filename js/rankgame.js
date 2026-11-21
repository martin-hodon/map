// rankgame.js -- the RANKINGS' GAMES: a list of ranks.js (chosen as in its panel: what, by what, within what) played.
// "higher" (Which is bigger?): two of the list's first 150 (the known ones; a pair not asked twice), the question
// which has more -- people, area, length, height -- answered by a click on one (or 1 / 2, ← / →); the map flies to the
// two and shows them, the answer tells both numbers. So many pairs, the score the right ones.
// "top" (Name the top): the first so many of the list named in any order, against the clock; each named fills its
// place in the list (and the map), one named further down is told its place, and a give-up shows the rest.
import { S, $, ctx, css, fmt, make } from "./state.js";
import { game } from "./groups.js";
import { rows, choices, LISTS, loadMeasures, flyWithin, riversReady } from "./ranks.js";
import { say, gameLi, finish, unitKey, ALSO, nameKey, clock } from "./game.js";
import { fly } from "./select.js";
import { collect } from "./search.js";
import { draw } from "./view.js";
import { writeName, visible } from "./labels.js";
import { flagCode, flagSvg } from "./flags.js";

export const RANKED = new Set(["higher", "top"]);
const GR = { list: "countries", by: "population", within: "" };      // (the game's choices: kept apart from the panel's)
try { Object.assign(GR, JSON.parse(localStorage.rankgame || "{}")); } catch (e) { }
const IDS = { list: "g-rlist", by: "g-rby", within: "g-rwithin" };
export function rankSetup() { choices(GR, IDS); try { localStorage.rankgame = JSON.stringify(GR); } catch (e) { } }
export const rankWhere = () => flyWithin(GR);
const MORE = { population: "more people", area: "the larger area", density: "more people per km²" };
const question = () => GR.by === "length" ? "Which is longer?" : GR.by === "height" ? "Which is higher?" : `Which has ${MORE[GR.by]}?`;
// (a name without its kind: "Amazon" for the Amazon River, "Everest" for Mount Everest, "Baffin" for Baffin Island)
const BARE = /\b(river|rio|río|mount|mt|mountains|lake|sea|ocean|islands?|desert|gulf|bay|strait|of|the)\b/gi;
const val = (r) => LISTS[game.rk.list].by[game.rk.by](r.v);
const at = (r) => r.at ??= r.e.at || r.e.feats[0].properties?.label || d3.geoCentroid(collect(r.e.feats));

export async function startRank() {
  await loadMeasures(); await riversReady(GR.list);                 // (rivers let go meanwhile: their lines read again first)
  const all = rows(GR), L = LISTS[GR.list], wsel = $("g-rwithin"), noun = L.noun || GR.within;
  const where = wsel.hidden || L.within === "water" || L.within === "land" ? "" : wsel.selectedOptions[0]?.textContent || "";
  Object.assign(game, { where: { kind: "world", name: "the world" }, ranked: all, rk: { ...GR, noun, where }, pair: null, asked: new Set(), done: new Set(), missed: [],
                        over: false, t0: performance.now(), t1: null });
  $("g-title").textContent = `${$("g-style").selectedOptions[0].textContent} · ${noun} by ${GR.by}${where ? ` · ${where}` : ""}`;
  $("g-list").innerHTML = ""; say(""); $("g-flag").innerHTML = ""; $("g-give").hidden = true;
  if (all.length < 2) { game.over = true; $("g-ask").textContent = `Too few ${noun} with a number here to play with.`; return draw(); }
  if (game.style === "higher") {
    game.pool = all.slice(0, 150); $("g-name").hidden = true;
    rankScore(); return nextPair();
  }
  game.top = Math.min(game.rounds, all.length);
  game.keys = new Map();                                            // (each name, local name and other name -> the first row of it)
  all.forEach((r, k) => {
    const also = r.e.cat === "country" ? String(ALSO[r.e.feats[0].properties.iso] || "").split(" / ") : [];
    for (const n of [r.name, ...String(r.e.alt || "").split(" / "), ...also]) for (const key of n ? [unitKey(n), unitKey(n.replace(BARE, " "))] : [])
      if (key && !game.keys.has(key)) game.keys.set(key, k);
  });
  for (let k = 0; k < game.top; k++) $("g-list").append(make("li", { className: "gap", textContent: "?" }));
  $("g-list").start = 1;
  $("g-ask").textContent = `Name the top ${game.top} ${noun} by ${GR.by}${where ? ` in ${where}` : ""}.`;
  $("g-name").hidden = false; $("g-name").value = ""; $("g-name").placeholder = "a name, then Enter";
  $("g-give").textContent = "Give up"; $("g-give").hidden = false;
  game.clock = setInterval(rankScore, 1000);
  rankScore(); $("g-name").focus(); flyWithin(GR); draw();
}
// ---- which is bigger ----
function nextPair() {
  const P = game.pool;
  game.pair = null;
  if (game.finds.length >= game.rounds) { finish(""); $("g-ask").textContent = `All ${game.rounds} pairs. Again for more.`; return draw(); }
  let a, b;
  for (let t = 0; t < 300; t++) {                                   // (two of different numbers, the pair not asked yet)
    a = P[Math.floor(Math.random() * P.length)]; b = P[Math.floor(Math.random() * P.length)];
    if (a !== b && a.v !== b.v && !game.asked.has(a.name + "|" + b.name)) break;
  }
  game.asked.add(a.name + "|" + b.name); game.asked.add(b.name + "|" + a.name);
  game.pair = [a, b];
  const box = make("div", { id: "g-pair" });
  game.pair.forEach((r, k) => {
    const btn = document.createElement("button"); btn.title = `${r.name} (${k ? "2 or →" : "1 or ←"})`;
    btn.innerHTML = flagSvg(flagCode(r.e), 14, { cls: "fl", outline: false }); btn.append(r.name); btn.onclick = () => answer(r);
    box.append(btn);
  });
  $("g-ask").replaceChildren(question(), box);
  const part = (r) => r.e.cat === "point" ? [{ type: "Feature", geometry: { type: "Point", coordinates: at(r) } }] : r.e.feats;   // (a point's feature has no type)
  const g = collect([...part(a), ...part(b)]); fly({ cat: "area", geom: g, at: d3.geoCentroid(g) });
}
function answer(r) {
  if (!game.pair || game.over) return;
  const [a, b] = game.pair, win = a.v > b.v ? a : b, lose = win === a ? b : a, ok = r === win;
  game.finds.push({ ok });
  say(`${ok ? "✓" : "✗"} ${win.name}: ${val(win)} · ${lose.name}: ${val(lose)}`, !ok);
  gameLi(`${win.name} > ${lose.name}`, ok ? "✓" : "✗");
  rankScore(); nextPair();
}
// ---- name the top ----
function slot(k, missed) {
  const li = $("g-list").children[k], r = game.ranked[k];
  li.className = ""; li.replaceChildren(r.name + " ", make("span", { textContent: val(r) + (missed ? " · not named" : "") }));
}
export function rankGuess(text) {
  if (game.style !== "top" || game.over || !nameKey(text)) return;
  const k = game.keys.get(unitKey(text));
  if (k == null) return say(`No “${text}” among the ${fmt(game.ranked.length)} ${game.rk.noun} ranked here.`, true);
  const r = game.ranked[k];
  $("g-name").value = "";
  if (k >= game.top) return say(`${r.name} is #${k + 1} (${val(r)}): not in the top ${game.top}.`, true);
  if (game.done.has(k)) return say(`${r.name} is named already.`, true);
  game.done.add(k); slot(k, false); say(`✓ ${r.name}: #${k + 1}, ${val(r)}`);
  if (game.done.size === game.top) finish(`All ${game.top} named, in ${clock()}.`);
  rankScore(); draw();
}
export function rankGiveUp() {
  if (game.style !== "top" || game.over) return;
  game.missed = []; for (let k = 0; k < game.top; k++) if (!game.done.has(k)) { game.missed.push(k); slot(k, true); }
  finish(`${game.done.size} of ${game.top} named, in ${clock()}; the ${game.missed.length} not named are shown.`);
  rankScore(); draw();
}
export function rankScore() {
  if (!game.rk) return;
  $("g-score").textContent = game.style === "higher" ? `${game.finds.length} of ${game.rounds} · ${game.finds.filter((f) => f.ok).length} right`
    : `${game.done.size} of ${game.top} · ${clock()}`;
}
// ---- on the map: the pair asked, or those named (green) and not named (violet), with their names ----
const shownRows = () => !game.rk ? [] : game.style === "higher" ? game.pair || [] : [...game.done, ...game.missed].map((k) => game.ranked[k]);
function shape(r, fill, line) {
  const e = r.e;
  if (e.cat === "point") {
    if (!visible(at(r))) return;
    const [x, y] = S.proj(at(r)); ctx.beginPath(); ctx.arc(x, y, 6, 0, 7); ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = line; ctx.lineWidth = 2; ctx.stroke(); return;
  }
  ctx.beginPath(); S.path(collect(e.feats));                        // (made anew: a shape kept would outlive its lines let go)
  if (e.cat === "river") { ctx.strokeStyle = line; ctx.lineWidth = 3.5; ctx.stroke(); return; }
  ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = line; ctx.lineWidth = 1.5; ctx.stroke();
}
export function drawRank() {
  if (!game.rk) return;
  const hi = css("--game");
  if (game.style === "higher") { for (const r of game.pair || []) shape(r, css("--game-fill"), hi); return; }
  for (const k of game.done) shape(game.ranked[k], css("--ok-fill"), "#2e9d4a");
  for (const k of game.missed) shape(game.ranked[k], css("--miss-fill"), "#7a5cc2");
}
export function rankNames(boxes) { for (const r of shownRows()) if (visible(at(r))) writeName(boxes, r.name, at(r), 12, 600, css("--ink")); }

export function init() {
  const set = (k) => () => { GR[k] = $(IDS[k]).value; if (k === "list") GR.within = ""; rankSetup(); if (k !== "by") flyWithin(GR); };
  for (const k of Object.keys(IDS)) $(IDS[k]).onchange = set(k);
  document.addEventListener("keydown", (ev) => {                    // (which is bigger: 1 or ← the first, 2 or → the second)
    if (!game.open || game.style !== "higher" || !game.pair || game.over || ev.target.closest?.("input, select, textarea")) return;
    const k = { 1: 0, ArrowLeft: 0, 2: 1, ArrowRight: 1 }[ev.key];
    if (k != null) { ev.preventDefault(); answer(game.pair[k]); }
  });
}
