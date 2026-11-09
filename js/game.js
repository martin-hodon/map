// game.js -- the games: cities to find, countries to name, chains and routes
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { $, canvas, ctx, css, R_KM, fmt, fmtPop } from "./state.js";
import { setup, COPIES, geoAt, Thing, trace, neighbors, merged, Map0 } from "./geom.js";
import { pxKm } from "./history.js";
import { pick, draw } from "./view.js";
import { writeName, cityDots, cityLabels, visible } from "./labels.js";
import { norm, collect } from "./search.js";
import { flagSvg } from "./flags.js";
import { clearSel, fly } from "./select.js";
import { idOf, game, bareGame, pickedStyle } from "./groups.js";

export const SHAPES = new Set(["which", "flag", "all", "chain", "route"]);          // (the games of countries, or of a country's states)
// (a name as typed: no accents, case or punctuation -- and w as v, y as i, k as c: "Cracow" for Kraków, "Kioto" for Kyoto)
export const nameKey = (s) => norm(s).replace(/[^\p{L}\p{N}]+/gu, " ").trim().replace(/w/g, "v").replace(/y/g, "i").replace(/k/g, "c");
S.gameData = null;                                                // (cities by name, each one's continent; built once)
export function gameIndex() {
  if (S.gameData) return S.gameData;
  const L = Map0, key = nameKey;
  // (only what has a code: a state without one -- Aksai Chin, the Ilemi Triangle -- was filed under `undefined`, and every
  //  city without a state of its own (Prague) took that one's continent: "Prague (Czechia) is not in Europe")
  const contOf = new Map([...L.countries, ...L.regions].filter((f) => f.properties.iso).map((f) => [f.properties.iso, f.properties.continent]));
  const byName = new Map(), cont = [];
  S.src.cities.features.forEach((f, i) => {
    const p = f.properties;
    cont[i] = contOf.get(p.region) || contOf.get(p.country);
    for (const k of new Set([p.name, p.name_local].filter(Boolean).map(key))) { if (!byName.has(k)) byName.set(k, []); byName.get(k).push(i); }
  });
  // a continent's people: each country's, shared out among the continents by its states' people (Russia's European
  // oblasts' to Europe)
  const people = {}, states = d3.group(L.regions.filter((f) => f.properties.population), (f) => f.properties.country);
  for (const f of L.countries) {
    const p = f.properties; if (!p.population) continue;
    const rs = states.get(p.iso) || [], all = d3.sum(rs, (r) => r.properties.population);
    if (!all) { people[p.continent] = (people[p.continent] || 0) + p.population; continue; }
    for (const r of rs) people[r.properties.continent] = (people[r.properties.continent] || 0) + p.population * r.properties.population / all;
  }
  const names = new Map(L.countries.map((f) => [f.properties.iso, f.properties.name]));
  return S.gameData = { key, byName, cont, people, names };
}
// THE SETUP: where first -- the world, a continent, a country (the second list: which) --, then the game, and only what
// that game asks besides (the circles' size, how many rounds). A start hides it all: the question, the score, the box
// to type in; "New game" brings it back. Where is shown as it is chosen: the map flies there (a country alone).
export function gameWhere() {                                              // the second list: the continents, or the countries (with cities,
  const L = Map0, box = $("g-where"), d = gameIndex(), was = box.value;                     // or for the countries' games: with states)
  const flagged = (c) => S.flagLib && Map0.regions.filter((g) => g.properties.country === c && S.flagLib.has(g.properties.iso)).length > 1;
  const has = pickedStyle() === "flag" ? new Set(Map0.countries.map((g) => g.properties.iso).filter(flagged))
    : SHAPES.has(pickedStyle()) ? new Set(d3.rollups(Map0.regions, (v) => v.length, (g) => g.properties.country).filter(([, n]) => n > 1).map(([c]) => c))
    : new Set(S.src.cities.features.map((f) => f.properties.country));
  box.innerHTML = ""; box.hidden = game.scope === "world";
  if (game.scope === "continent") for (const c of Object.keys(d.people).sort()) { if (d.cont.includes(c)) box.add(new Option(c, "continent:" + c)); }
  if (game.scope === "country") for (const f of [...L.countries].sort((a, b) => a.properties.name.localeCompare(b.properties.name))) if (has.has(f.properties.iso)) box.add(new Option(f.properties.name, "country:" + f.properties.iso));
  if ([...box.options].some((o) => o.value === was)) box.value = was;
}
export const whereValue = () => game.scope === "world" ? "world" : $("g-where").value;
// the outline of where in a copy: a continent merged of that copy's own arcs (merged of the full detail, its coast was
// drawn at 1.5 px from afar -- Norway's fjords, the Aegean's islands -- and looked hairy)
export function continentGeom(lv, id) {
  const split = new Set(Map0.regions.map((f) => f.properties.country));   // (its land: its states, and its countries without states)
  return merged([...Map0.countries.filter((f) => !split.has(f.properties.iso)), ...Map0.regions].filter((f) => f.properties.continent === id), lv);
}
export function whereGeom(lv) {                                            // (a Thing, or GeoJSON)
  const w = game.where;
  if (!w || w.kind === "world") return null;
  if (w.kind === "country") { const f = Map0.countries[idOf.countries.get(w.id)]; return f.has(lv) ? f : w.geom; }
  w.lv ??= [];
  const g = geoAt(Map0.regions[0].o, lv);
  if (w.lv[lv]?.g !== g) { const f = continentGeom(lv, w.id); w.lv[lv] = { g, f: f.geometry ? f : w.geom }; }
  return w.lv[lv].f;
}
export const outline = (f, lv) => { if (f instanceof Thing) trace(f, f.has(lv) ? lv : 0); else S.path(f); };
export function gameRegion(v) {
  const L = Map0, d = gameIndex(), [kind, id] = v.split(":");
  if (kind === "continent") {
    const f = continentGeom(0, id);
    return { kind, id, name: id, geom: f, at: d3.geoCentroid(f), people: d.people[id], has: (i) => d.cont[i] === id };
  }
  if (kind === "country") {
    const f = L.countries[idOf.countries.get(id)];
    return { kind, id, name: f.properties.name, geom: f, at: f.properties.label, people: f.properties.population, has: (i) => S.src.cities.features[i].properties.country === id };
  }
  return { kind: "world", name: "the world", people: d3.sum(L.countries, (f) => f.properties.population || 0), has: () => true };
}
export function flyWhere() {
  const w = game.where;
  if (w.geom) fly({ cat: "area", geom: w.geom, at: w.at || d3.geoCentroid(w.geom) });
  else { S.rotate = [-10, 0, 0]; S.zoom = 1; setup(); draw(); }
}
export function resetGame() {                                              // (nothing played: the map shows only where)
  clearInterval(game.clock);
  Object.assign(game, { named: [], finds: [], ask: null, units: null, over: false, start: null, goal: null, way: null });
  $("g-flag").innerHTML = ""; $("g-stage").innerHTML = "";
}
export function previewGame() { resetGame(); game.where = gameRegion(whereValue()); flyWhere(); }
export function setupGame(on) { $("g-setup").hidden = !on; $("g-play").hidden = on; if (on) { resetGame(); draw(); } }
export function openGame(open) {
  game.open = open; $("game").hidden = !open; $("game-btn").hidden = open; document.body.classList.toggle("gaming", open);
  $("tip").style.display = "none"; resetGame();
  if (open) { if (S.sel) clearSel(); setupGame(true); gameStyle(); gameKm(); previewGame(); } else draw();
}
export function gameStyle() {                                              // (what the chosen game asks for)
  const s = pickedStyle();
  $("g-kmbox").hidden = s !== "outside" && s !== "inside"; $("g-roundsbox").hidden = s !== "place" && s !== "which" && s !== "flag";
  $("g-roundsof").textContent = s === "place" ? "cities to find" : "to name";
  const was = whereValue(); gameWhere();                           // (the countries offered: with cities, or with states)
  if (whereValue() !== was) previewGame(); else draw();
}
// the circles' sizes offered, by where: the world's cities lie far apart, a country's close
export const KM = { world: [250, 500, 1000, 2000], continent: [100, 200, 300, 500, 1000], country: [25, 50, 100, 200] }, KM0 = { world: 500, continent: 300, country: 100 };
export function gameKm() { $("g-km").replaceChildren(...KM[game.scope].map((km) => new Option(`${fmt(km)} km`, km))); $("g-km").value = KM0[game.scope]; }
export function startGame() {
  const d = gameIndex(), C = S.src.cities.features;
  resetGame();
  Object.assign(game, { style: pickedStyle(), bare: $("g-style").value.endsWith(":bare"), where: gameRegion(whereValue()), km: +$("g-km").value || KM0[game.scope],
                        rounds: Math.max(1, Math.min(100, +$("g-rounds").value || 10)) });
  $("g-setup").hidden = true; $("g-play").hidden = false;
  $("g-title").textContent = `${$("g-style").selectedOptions[0].textContent.split(":")[0]} · ${game.where.kind === "world" ? "the world" : game.where.name}` +
    (game.style === "outside" || game.style === "inside" ? ` · circles ${fmt(game.km)} km` : "");
  $("g-give").hidden = true;
  if (SHAPES.has(game.style)) return startUnits();
  const ids = C.map((_, i) => i).filter(game.where.has);
  // (to find: the biggest cities there -- the file is biggest first -- in a random order; of the world or a continent,
  // one a country: China's many big cities would fill the game)
  game.pool = d3.shuffle(ids.slice(0, game.where.kind === "world" ? 300 : game.where.kind === "continent" ? 150 : Math.max(20, game.rounds * 2)));
  if (game.where.kind !== "country") {   // (one a country first; a continent of few countries -- Oceania -- then fills up with the rest)
    const seen = new Set(), first = game.pool.filter((i) => { const c = C[i].properties.country; return !seen.has(c) && seen.add(c); });
    game.pool = [...first, ...game.pool.filter((i) => !first.includes(i))];
  }
  game.rounds = Math.min(game.rounds, game.pool.length);
  $("g-list").innerHTML = ""; say("");
  $("g-name").hidden = game.style === "place"; $("g-name").value = ""; $("g-name").placeholder = "a city, then Enter";
  if (game.style === "place") nextFind(); else { $("g-ask").textContent = ""; $("g-name").focus(); }
  gameScore(); flyWhere();
}
export const say = (text, no = false) => { $("g-msg").textContent = text; $("g-msg").className = no ? "no" : ""; };
export const kmApart = (i, j) => d3.geoDistance(S.src.cities.features[i].geometry.coordinates, S.src.cities.features[j].geometry.coordinates) * R_KM;
export const cityText = (i) => { const p = S.src.cities.features[i].properties; return `${p.name} (${gameIndex().names.get(p.country) || p.country})`; };
export function guess(text) {                                              // a city named: taken, or why not
  const d = gameIndex(), k = d.key(text);
  if (!k || !game.where) return;
  const all = d.byName.get(k) || [], here = all.filter(game.where.has), fresh = here.filter((i) => !game.named.includes(i));
  if (!all.length) return say(`No city “${text}” (of 100,000 people or more -- 70,000 in Europe -- or a capital).`, true);
  if (!here.length) return say(`${cityText(all[0])} is not in ${game.where.name}.`, true);
  if (!fresh.length) return say(`${cityText(here[0])} is named already.`, true);
  const r = game.km / 2, near = (i) => game.named.reduce((b, j) => { const km = kmApart(i, j); return km < b[0] ? [km, j] : b; }, [Infinity, -1]);
  const fits = (i) => game.style === "outside" ? near(i)[0] > r : game.style === "inside" ? !game.named.length || near(i)[0] <= r : true;
  const ok = fresh.filter(fits);
  if (!ok.length) { const [km, j] = near(fresh[0]);
    return say(game.style === "outside" ? `${cityText(fresh[0])} is in the circle of ${S.src.cities.features[j].properties.name} (${fmt(km)} km from it).`
                                        : `${cityText(fresh[0])} is in no circle: the nearest is ${S.src.cities.features[j].properties.name}'s, ${fmt(km)} km away.`, true); }
  const i = ok[0], p = S.src.cities.features[i].properties;                // (of several of that name, the biggest)
  game.named.push(i); $("g-name").value = "";
  say(`✓ ${cityText(i)} · ${fmtPop(p.population)}`);
  const li = document.createElement("li"); li.append(p.name + " ", Object.assign(document.createElement("span"), { textContent: fmtPop(p.population) }));
  $("g-list").prepend(li);
  gameScore(); drawGameOver();
}
export function nextFind() {
  game.ask = game.finds.length < game.rounds ? game.pool[game.finds.length] : null;
  $("g-ask").innerHTML = "";
  if (game.ask != null) $("g-ask").append("Where is ", Object.assign(document.createElement("b"), { textContent: game.where.kind === "country" ? S.src.cities.features[game.ask].properties.name : cityText(game.ask) }), "?");
  else $("g-ask").textContent = "All found. Again for more.";
}
export function gameClick(e) {                                             // (find the city: the click is the answer)
  if (game.style !== "place" || game.ask == null) return;
  const ll = S.proj.invert([e.clientX, e.clientY]);
  if (!ll || !isFinite(ll[0]) || !visible(ll)) return;
  const i = game.ask, km = d3.geoDistance(ll, S.src.cities.features[i].geometry.coordinates) * R_KM;
  game.finds.push({ i, at: ll, km });
  say(`${cityText(i)}: ${fmt(km)} km off`);
  const li = document.createElement("li"); li.append(S.src.cities.features[i].properties.name + " ", Object.assign(document.createElement("span"), { textContent: `${fmt(km)} km` }));
  $("g-list").prepend(li);
  nextFind(); gameScore(); drawGameOver();
}
export function gameScore() {
  const C = S.src.cities.features, w = game.where;
  if (!w) return;
  if (SHAPES.has(game.style)) return unitScore();
  if (game.style === "place") {
    const n = game.finds.length, km = d3.sum(game.finds, (f) => f.km);
    $("g-score").textContent = `${n} of ${game.rounds} · ${fmt(km)} km off in all` + (n ? ` · ${fmt(km / n)} km a city` : "");
    return;
  }
  const people = d3.sum(game.named, (i) => C[i].properties.population);
  $("g-score").textContent = `${game.named.length} cities · ${fmtPop(people || 0)} people` +
    (game.style === "people" && w.people ? ` · ${(100 * people / w.people).toFixed(1)} % of ${w.name}'s ${fmtPop(w.people)}` : "");
}
// ---- THE COUNTRIES' GAMES: the UNITS -- the countries of the world or a continent, or a country's states -- each with
// its names (the map's, the local one, and for a country those it is often called: ALSO) and its NEIGHBOURS, a land
// border (the arcs two share: topojson.neighbors). A dependency's borders are its country's (French Guiana: France and
// Brazil); a disputed piece (Bir Tawil, the Golan) is no unit, and the ones round it border each other across it.
// "which": one is shown (the map flies to it), its name asked -- so many of them; "flag": its flag is shown (the map
// stays where it is), its name asked -- of those with a flag in data/flags.txt; "all": every one named is filled in,
// against the clock; "chain": each one named borders the last, none twice, as long as it goes; "route": from one to
// another, each one named bordering one named before, in as few as can be (the shortest way said at the end).
export const ALSO = { US: "USA / United States of America / America", GB: "UK / Great Britain / Britain", CZ: "Czech Republic", CI: "Côte d'Ivoire",
  CD: "DR Congo / DRC / Congo-Kinshasa / Democratic Republic of Congo", CG: "Congo / Congo-Brazzaville / Republic of Congo", CV: "Cabo Verde",
  FM: "Micronesia", MM: "Burma", MK: "Macedonia", SZ: "Swaziland", TL: "Timor-Leste", VA: "Vatican / Holy See", BA: "Bosnia", AE: "UAE / Emirates",
  TR: "Türkiye", ST: "São Tomé", NL: "Holland", RU: "Russian Federation", LA: "Lao", CF: "CAR", AG: "Antigua", TT: "Trinidad", KN: "Saint Kitts",
  VC: "Saint Vincent", PG: "Papua", IR: "Persia" };
export const unitKey = (s) => nameKey(s).replace(/^the /, "").replace(/\bst\b/g, "saint");   // (The Gambia: Gambia; St Lucia: Saint Lucia)
export function gameUnits(w) {
  const states = w.kind === "country", layer = states ? "regions" : "countries", G = Map0[layer], nb = neighbors(G);
  // (a continent's: those of it, and those with a state in it -- Russia, Turkey and Kazakhstan are Europe's too)
  const part = new Set(w.kind === "continent" ? Map0.regions.filter((g) => g.properties.continent === w.id).map((g) => g.properties.country) : []);
  const isUnit = (p) => states ? p.country === w.id
    : p.subtype === "country" && p.continent !== "Antarctica" && (!/^X/.test(p.iso) || p.iso === "XK") && (w.kind === "world" || p.continent === w.id || part.has(p.iso));
  const at = new Map(states ? [] : G.map((g, k) => [g.properties.iso, k]));
  const owner = G.map((g, k) => { const p = g.properties; if (isUnit(p)) return k;
    const s = states || p.subtype !== "dependency" ? undefined : at.get(p.sovereign); return s !== undefined && isUnit(G[s].properties) ? s : null; });
  const units = [], of = new Map(), F = Map0[layer];
  G.forEach((g, k) => { if (owner[k] !== k) return; const p = g.properties;
    of.set(k, units.length);
    units.push({ k, iso: p.iso, name: p.name, label: p.label || d3.geoCentroid(F[k]), area: p.area_km2 || 0, nb: new Set(),
                 keys: [p.name, p.name_local, ...(states ? [] : String(ALSO[p.iso] || "").split(" / "))].filter(Boolean).map(unitKey) }); });
  const link = (a, b) => { const x = of.get(owner[a]), y = of.get(owner[b]); if (x != null && y != null && x !== y) { units[x].nb.add(y); units[y].nb.add(x); } };
  const across = (p) => !states && /^X/.test(p.iso) && p.iso !== "XK";
  G.forEach((g, a) => { for (const b of nb[a]) link(a, b); if (across(g.properties)) for (const b of nb[a]) for (const c of nb[a]) link(b, c); });
  const byKey = new Map(); units.forEach((u, i) => { for (const k of u.keys) if (!byKey.has(k)) byKey.set(k, i); });
  return { layer, word: states ? "state" : "country", words: states ? "states" : "countries", units, byKey };
}
export const unitFeat = (u) => Map0[game.units.layer][game.units.units[u].k];
export function reach(from) {                                              // every unit reachable across borders: [its steps from `from`, the one before]
  const U = game.units.units, got = new Map([[from, [0, -1]]]), q = [from];
  for (let h = 0; h < q.length; h++) { const a = q[h], d = got.get(a)[0]; for (const b of U[a].nb) if (!got.has(b)) { got.set(b, [d + 1, a]); q.push(b); } }
  return got;
}
export const bold = (t) => Object.assign(document.createElement("b"), { textContent: t });
export const gameLi = (t, note = "") => { const e = document.createElement("li"); e.append(t + " ", Object.assign(document.createElement("span"), { textContent: note })); $("g-list").prepend(e); };
export const into = () => game.where.kind === "world" ? "the world" : game.where.name;
export const clock = () => { const s = Math.round(((game.t1 ?? performance.now()) - game.t0) / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
export function startUnits() {
  const w = game.where, U = gameUnits(w), n = U.units.length, all = U.units.map((_, i) => i), linked = all.filter((i) => U.units[i].nb.size);
  Object.assign(game, { units: U, done: new Set(), order: [], missed: [], way: null, over: false, start: null, goal: null, t0: performance.now(), t1: null });
  $("g-list").innerHTML = ""; say(""); $("g-name").hidden = false; $("g-name").value = ""; $("g-name").placeholder = `a ${U.word}, then Enter`;
  const fail = (t) => { game.over = true; $("g-ask").textContent = t; unitScore(); draw(); };
  if (game.style === "which" || game.style === "flag") {
    game.pool = d3.shuffle(game.style === "flag" ? all.filter((i) => S.flagLib?.has(U.units[i].iso)) : all); game.rounds = Math.min(game.rounds, game.pool.length);
    if (!game.pool.length) return fail(`No flags of the ${U.words} of ${into()} yet.`);
  }
  else if (game.style === "all") { $("g-ask").textContent = `Name every ${U.word} of ${into()}: ${n}.`; game.clock = setInterval(unitScore, 1000); }
  else if (game.style === "chain") {
    if (!linked.length) return fail(`No two ${U.words} of ${into()} share a border.`);
    game.start = linked[Math.floor(Math.random() * linked.length)]; game.order = [game.start]; askChain();
  } else {                                                          // (two far enough apart: 2 to 6 between, else any 1 or more)
    const far = (a, lo, hi) => [...reach(a)].filter(([, [d]]) => d >= lo && d <= hi).map(([b]) => b);
    let pair = null;
    for (const a of d3.shuffle(linked.slice()).slice(0, 30)) { const f = far(a, 3, 7); if (f.length) { pair = [a, f[Math.floor(Math.random() * f.length)]]; break; } }
    for (const a of pair ? [] : linked) { const f = far(a, 2, Infinity); if (f.length) { pair = [a, f[0]]; break; } }
    if (!pair) return fail(`No two ${U.words} of ${into()} have one between them across borders.`);
    [game.start, game.goal] = pair; game.order = [game.start]; game.done = new Set([game.start]);
    $("g-ask").replaceChildren("From ", bold(U.units[game.start].name), " to ", bold(U.units[game.goal].name), `: name ${U.words} across the borders, each next to one named.`);
  }
  $("g-give").textContent = { which: "Show", flag: "Show", all: "Give up", chain: "End", route: "Show a way" }[game.style]; $("g-give").hidden = false;
  unitScore(); $("g-name").focus();
  if (game.style === "which") return nextUnit();
  if (game.style === "flag") { if (!game.bare) flyWhere(); return nextUnit(); }
  const show = game.style === "chain" ? [game.start, ...U.units[game.start].nb] : game.style === "route" ? [game.start, game.goal] : null;
  if (show) { const g = collect(show.map((u) => unitFeat(u))); fly({ cat: "area", geom: g, at: d3.geoCentroid(g) }); }
  else flyWhere();
}
export function nextUnit() {                                               // ("which": the next one shown, the map flown to it)
  const U = game.units;
  game.ask = game.finds.length < game.rounds ? game.pool[game.finds.length] : null;
  $("g-flag").innerHTML = ""; $("g-stage").innerHTML = "";
  if (game.ask == null) { finish(""); $("g-ask").textContent = `All ${game.rounds} shown. Again for more.`; if (game.bare) return flyWhere(); return draw(); }
  if (game.style === "flag") {
    $("g-ask").textContent = `Whose flag is this? Name the ${U.word}.`;
    if (game.bare) $("g-stage").innerHTML = flagSvg(U.units[game.ask].iso, 600); else $("g-flag").innerHTML = flagSvg(U.units[game.ask].iso, 110);
    return draw();
  }
  $("g-ask").textContent = `Which ${U.word} is this?`;
  if (game.bare) {                                                  // (no flight: nothing to fly over, and it would show the way)
    const g = unitFeat(game.ask), [[w, so], [ea, n]] = d3.geoBounds(g), dlon = ((ea - w) + 360) % 360 || 360;
    S.rotate = [-(w + dlon / 2), -(n + so) / 2, 0]; S.zoom = Math.max(1, Math.min(60, 60 / Math.max(n - so, dlon * Math.cos((n + so) / 2 * Math.PI / 180), .02)));
    setup(); return draw();
  }
  fly({ cat: "area", geom: unitFeat(game.ask), at: U.units[game.ask].label });
}
export function askChain() {
  const U = game.units, first = game.order.length === 1;
  $("g-ask").replaceChildren(first ? "Start: " : "Next to ", bold(U.units[game.order.at(-1)].name), first ? `. Name a ${U.word} next to it, then one next to that…` : "?");
}
export function finish(text) { game.over = true; game.t1 = performance.now(); clearInterval(game.clock); $("g-give").hidden = true; if (text) say(text); }
export function unitGuess(text) {                                          // a name typed: right, or why not
  const U = game.units;
  if (!U || game.over || !nameKey(text)) return;
  const u = U.byKey.get(unitKey(text));
  if (u == null) return say(`No ${U.word} “${text}” in ${into()}.`, true);
  const n = U.units[u].name;
  $("g-name").value = "";
  if (game.style === "which" || game.style === "flag") {
    const a = game.ask, ok = u === a;
    game.finds.push({ u: a, ok });
    say(ok ? `✓ ${n}` : `✗ That is ${U.units[a].name}, not ${n}.`, !ok); gameLi(U.units[a].name, ok ? "✓" : `✗ ${n}`);
    unitScore(); return nextUnit();
  }
  if (game.style === "all") {
    if (game.done.has(u)) return say(`${n} is named already.`, true);
    game.done.add(u); say(`✓ ${n}`); gameLi(n);
    if (game.done.size === U.units.length) finish(`All ${U.units.length} named, in ${clock()}.`);
  } else if (game.style === "chain") {
    const last = game.order.at(-1);
    if (game.order.includes(u)) return say(`${n} is in the chain already.`, true);
    if (!U.units[last].nb.has(u)) return say(`${n} does not border ${U.units[last].name}.`, true);
    game.order.push(u); say(`✓ ${n}`); gameLi(n, String(game.order.length - 1));
    if (![...U.units[u].nb].some((b) => !game.order.includes(b))) finish(`No neighbour of ${n} is left: a chain of ${game.order.length - 1}.`); else askChain();
  } else {
    if (game.done.has(u)) return say(`${n} is named already.`, true);
    if (![...game.done].some((b) => U.units[b].nb.has(u))) return say(`${n} borders none of those named yet.`, true);
    game.done.add(u); game.order.push(u); gameLi(n);
    if (u === game.goal || U.units[u].nb.has(game.goal)) {
      if (u !== game.goal) { game.done.add(game.goal); game.order.push(game.goal); }
      const named = game.order.length - 2, best = reach(game.start).get(game.goal)[0] - 1;
      finish(`✓ There, with ${named} named: the shortest way goes through ${best}.`);
    } else say(`✓ ${n}`);
  }
  unitScore(); drawGameOver();
}
export function giveUp() {                                                 // (Show / Give up / End / Show a way)
  const U = game.units;
  if (!U || game.over) return;
  if (game.style === "which" || game.style === "flag") { const a = game.ask; game.finds.push({ u: a, ok: false }); say(`That is ${U.units[a].name}.`); gameLi(U.units[a].name, "shown"); unitScore(); return nextUnit(); }
  if (game.style === "all") { game.missed = U.units.map((_, i) => i).filter((i) => !game.done.has(i));
    finish(`${game.done.size} of ${U.units.length} named, in ${clock()}; the ${game.missed.length} not named are shown.`); }
  else if (game.style === "chain") { const last = game.order.at(-1), left = [...U.units[last].nb].filter((b) => !game.order.includes(b));
    finish(`A chain of ${game.order.length - 1}. Next to ${U.units[last].name} there was still ${left.map((b) => U.units[b].name).join(", ")}.`); }
  else { const r = reach(game.start), way = [];
    for (let a = r.get(game.goal)[1]; a !== game.start; a = r.get(a)[1]) way.unshift(a);
    game.way = way; finish(`A shortest way: ${[game.start, ...way, game.goal].map((u) => U.units[u].name).join(" → ")}.`); }
  unitScore(); drawGameOver();
}
export function unitScore() {
  const U = game.units;
  if (!U) return;
  $("g-score").textContent = game.style === "which" || game.style === "flag" ? `${game.finds.length} of ${game.rounds} · ${game.finds.filter((f) => f.ok).length} right`
    : game.style === "all" ? `${game.done.size} of ${U.units.length} · ${clock()}`
    : game.style === "chain" ? `a chain of ${Math.max(0, game.order.length - 1)}`
    : `${Math.max(0, game.order.length - 1 - (game.done.has(game.goal) ? 1 : 0))} named`;
}
// the units on the map: named (or right) green, missed or shown violet, the one asked (the chain's last, the route's
// two ends) in the highlight; one too small to see at this zoom a dot round its middle
export function drawUnits() {
  const U = game.units;
  if (!U) return;
  const lv = pick(), hi = css("--game"), km2 = pxKm() * pxKm();
  const paint = (us, fill, line = 0) => {
    if (!us.length) return;
    ctx.beginPath();
    for (const u of us) { const c = U.units[u].label;
      if (U.units[u].area / km2 < 12) { if (visible(c)) { const [x, y] = S.proj(c); ctx.moveTo(x + 4, y); ctx.arc(x, y, 4, 0, 7); } } else outline(unitFeat(u), lv); }
    ctx.fillStyle = fill; ctx.fill();
    if (line) { ctx.strokeStyle = hi; ctx.lineWidth = line; ctx.stroke(); }
  };
  const ok = css("--ok-fill"), miss = css("--miss-fill"), cur = css("--game-fill");
  if (game.style === "which" || game.style === "flag") {
    paint(game.finds.filter((f) => f.ok).map((f) => f.u), ok); paint(game.finds.filter((f) => !f.ok).map((f) => f.u), miss);
    if (game.ask != null && game.style === "which") paint([game.ask], cur, 2);   // (the flag game: the map does not give it away)
  } else if (game.style === "all") { paint([...game.done], ok); paint(game.missed, miss); }
  else if (game.style === "chain") {
    paint(game.order.slice(0, -1), ok); paint(game.order.slice(-1), cur, 2);
    if (game.order.length > 1) { ctx.beginPath(); S.path({ type: "LineString", coordinates: game.order.map((u) => U.units[u].label) });
      ctx.setLineDash([4, 3]); ctx.strokeStyle = hi; ctx.lineWidth = 1.2; ctx.stroke(); ctx.setLineDash([]); }
  } else if (game.start != null) {
    paint([...game.done].filter((u) => u !== game.start && u !== game.goal), ok); paint(game.way || [], miss);
    paint([game.start], cur, 1.5); paint([game.goal], cur, 2.5);
  }
}
export function gameUnitNames(boxes) {                                     // (the names of those named, shown or given -- never the one asked)
  const U = game.units;
  if (!U) return;
  const ids = game.style === "which" || game.style === "flag" ? game.finds.map((f) => f.u) : game.style === "all" ? [...game.done, ...game.missed]
    : game.style === "chain" ? game.order.slice().reverse() : game.start == null ? [] : [game.start, game.goal, ...game.done, ...(game.way || [])];
  for (const u of new Set(ids)) { const c = U.units[u].label; if (visible(c)) writeName(boxes, U.units[u].name, c, 11, 600, css("--ink")); }
}
// the game on the map: its region's outline, the circles, the cities named or found (their names: drawMap)
// THE MAP UNDER THE GAME, as last drawn whole: between two guesses (or two clicks) only the game changes -- its circles,
// the cities named and their names -- so a guess paints those over this picture instead of drawing the map again
// (a full draw is what took a guess its time). Kept for the view it was drawn at; any other view draws the map afresh.
export const gameBase = document.createElement("canvas");
export const viewKey = () => `${S.rotate}|${S.zoom}|${S.W}|${S.H}|${$("proj").value}`;
export function keepGameBase() {
  gameBase.width = canvas.width; gameBase.height = canvas.height;
  gameBase.getContext("2d").drawImage(canvas, 0, 0); gameBase.view = viewKey();
}
export function drawGameOver() {
  if (gameBase.view !== viewKey() || S.moving || S.drag || bareGame()) return draw();
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(gameBase, 0, 0); ctx.restore();
  drawGame(false);
  gameLabels([]);
}
export const gameLabels = (boxes) => SHAPES.has(game.style) ? gameUnitNames(boxes) : cityLabels(boxes, game.shown());
export function drawGame(fast) {
  const C = S.src.cities.features, hi = css("--game"), deg = (km) => km / R_KM * 180 / Math.PI;
  const lv = Math.min(COPIES.length - 1, pick(fast) + 1), where = whereGeom(lv);   // (a copy coarser than the map's: a 2 px line)
  if (where) { ctx.beginPath(); outline(where, lv); ctx.strokeStyle = hi; ctx.lineWidth = 2; ctx.stroke(); }
  if (SHAPES.has(game.style)) return drawUnits();
  const ring = (center, km, fill) => { ctx.beginPath(); S.path(d3.geoCircle().center(center).radius(deg(km)).precision(km > 300 ? 2 : 0.5)());
    if (fill) { ctx.fillStyle = css("--game-fill"); ctx.fill(); } ctx.strokeStyle = hi; ctx.lineWidth = 2; ctx.stroke(); };
  if (game.style === "outside" || game.style === "inside") for (const i of game.named) ring(C[i].geometry.coordinates, game.km / 2, true);
  if (game.style === "place") game.finds.forEach((f, n) => {
    const last = n === game.finds.length - 1, c = C[f.i].geometry.coordinates;
    ctx.globalAlpha = last ? 1 : 0.35;
    if (f.km > 1) ring(c, f.km, false);
    ctx.beginPath(); S.path({ type: "LineString", coordinates: [f.at, c] }); ctx.setLineDash([3, 3]); ctx.stroke(); ctx.setLineDash([]);
    if (visible(f.at)) { const [x, y] = S.proj(f.at); ctx.beginPath(); ctx.moveTo(x - 4, y - 4); ctx.lineTo(x + 4, y + 4); ctx.moveTo(x + 4, y - 4); ctx.lineTo(x - 4, y + 4); ctx.lineWidth = 2; ctx.stroke(); }
    ctx.globalAlpha = 1;
  });
  cityDots(game.shown());
  if (!fast && game.style !== "place" && game.named.length) {          // (the last one named: ringed)
    const c = C[game.named[game.named.length - 1]].geometry.coordinates;
    if (visible(c)) { const [x, y] = S.proj(c); ctx.beginPath(); ctx.arc(x, y, 7, 0, 7); ctx.strokeStyle = hi; ctx.lineWidth = 2.5; ctx.stroke(); }
  }
}

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  $("game-btn").onclick = () => { if (S.src && S.src.cities) openGame(true); };
  $("game-close").onclick = () => openGame(false);
  $("g-style").onchange = gameStyle;
  for (const b of $("g-scope").children) b.onclick = () => {
    game.scope = b.dataset.k; for (const o of $("g-scope").children) o.classList.toggle("on", o === b);
    gameWhere(); gameKm(); previewGame();
  };
  $("g-where").onchange = previewGame;
  $("g-start").onclick = startGame;
  $("g-again").onclick = startGame;
  $("g-new").onclick = () => setupGame(true);
  $("g-give").onclick = giveUp;
  $("g-name").addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); (SHAPES.has(game.style) ? unitGuess : guess)($("g-name").value); } });
  $("g-name").addEventListener("input", (ev) => { if (/\n/.test(ev.target.value)) ev.target.value = ev.target.value.replace(/\s*\n\s*/g, " "); });   // (pasted lines)
}
