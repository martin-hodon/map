// history.js -- the historical map: the day, which country-period holds each region on it, the day's borders by kind
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { $, R_KM } from "./state.js";
import { RING, POLY, geoAt, merged } from "./geom.js";

// the historical map's rows (its own file, loaded when wanted: loadHistory) -- regions, each with its owners through
// time; H0: what does not change with the day (each region's owners as numbers, the periods, the arcs between regions)
S.histNow = null; S.H0 = null;
// a day as the data writes it: "1914-06-28", "-0699-01-01" (years astronomical: 0 is 1 BC, -699 700 BC); a number to
// compare (strings will not: "-0699" < "-0700"); a date cut to its year or month ("-0479", "1415-06") is its first day
export const dayNum = (s) => { const m = /^(-?\d+)(?:-(\d\d))?(?:-(\d\d))?$/.exec(s || ""); return m ? +m[1] * 10000 + +(m[2] || 1) * 100 + +(m[3] || 1) : NaN; };
export const dayText = (n) => { const y = Math.floor(n / 10000), r = n - y * 10000, md = String(r).padStart(4, "0"); return yearText(y) + (r === 101 ? "" : `-${md.slice(0, 2)}-${md.slice(2)}`); };
export const yearOf = (s) => parseInt(s, 10);
export const yearText = (y) => (y < 0 ? "-" : "") + String(Math.abs(y)).padStart(4, "0");
export const showYear = (y) => y <= 0 ? `${1 - y} BC` : String(y);
export const showDay = (s) => { const y = yearOf(s), md = s.replace(/^-?\d+/, ""); return y <= 0 ? showYear(y) + (md && md !== "-01-01" ? md : "") : s; };
S.curDay = "1914-06-28";
export const histDay = () => S.curDay;
export function setDay(t) {                                                // ("1914-06-28", "1914", "-699", "700 BC", "700 BC-08-10")
  let m = /^\s*(\d+)\s*(?:BC|BCE|v\.?\s*Chr\.?)\s*(-\d\d-\d\d)?\s*$/i.exec(String(t)), d;
  if (m) d = yearText(1 - +m[1]) + (m[2] || "-01-01");
  else if ((m = /^\s*(-?\d{1,4})(-\d\d)?(-\d\d)?\s*$/.exec(String(t)))) d = yearText(+m[1]) + (m[2] || "-01") + (m[3] || "-01");
  else return;
  const lo = "-2999-01-01", hi = "2019-12-31", y = yearOf(d);
  if (dayNum(d) < dayNum(lo)) d = lo; else if (dayNum(d) > dayNum(hi)) d = hi;
  else if (d.endsWith("02-29") && !((y % 4 === 0 && y % 100 !== 0) || y % 400 === 0)) d = d.slice(0, -2) + "28";
  S.curDay = d; $("day").value = showDay(d); $("year").value = yearOf(d); S.histNow = null;
  try { localStorage.histday = d; } catch (e) { }
}
// what is on the day shown: its country-periods, its borders, and a colour class for each state -- no two neighbours
// alike, a dependency in its ruler's where its neighbours let it (an empire in one colour); and its events
export const eventYears = (y) => Math.max(1, Math.round((2020 - y) / 25));   // (the events shown: within this many years of the day -- 4 in 1914, 109 in 700 BC)
export function histOn() {
  const d = histDay();
  if (S.histNow && S.histNow.day === d) return S.histNow;
  const n = dayNum(d), P = S.H0.periods, { start, from, state } = S.H0.held, R = start.length - 1, of = new Int32Array(R).fill(-1), members = new Map();
  for (let r = 0; r < R; r++) {                                     // (each region's country-period that day: its state's period spanning it)
    let k = start[r] - 1; while (k + 1 < start[r + 1] && from[k + 1] <= n) k++;
    if (k < start[r] || state[k] < 0) continue;
    const pi = (S.H0.byState.get(state[k]) || []).find((i) => P[i]._f <= n && n <= P[i]._t);
    if (pi === undefined) continue;
    of[r] = pi; if (!members.has(pi)) members.set(pi, []); members.get(pi).push(r);
  }
  const countries = [...members.keys()];
  const near = new Map(), owner = new Map(), colour = new Map(), N = 8;
  for (const pi of countries) { const p = P[pi]; near.set(p.state, new Set()); if (p.owner != null) owner.set(p.state, p.owner); }
  for (const { s1, s2, open } of bordersOf(of, 0)) if (!open) { near.get(s1).add(s2); near.get(s2).add(s1); }
  const free = (g, c) => ![...near.get(g)].some((x) => colour.get(x) === c);
  for (const g of [...near.keys()].sort((a, b) => owner.has(a) - owner.has(b) || near.get(b).size - near.get(a).size)) {   // (the states first, the most neighbours first)
    const want = colour.get(owner.get(g));
    let c = 0;
    if (want !== undefined && free(g, want)) c = want; else while (!free(g, c) && c < N - 1) c++;
    colour.set(g, c);
  }
  const y = yearOf(d), w = eventYears(y), events = [];
  if (S.src.events) S.src.events.features.forEach((f, i) => { if (Math.abs((f.properties._y ??= yearOf(f.properties.date)) - y) <= w) events.push(i); });
  return S.histNow = { day: d, of, members, countries, colour, lv: [], events: new Map(events.map((i, r) => [i, r])) };   // (event -> its rank that day: the file is the best known first)
}
// the arcs between two regions of different states that day (of a copy: its arcs)
export function* bordersOf(of, lv) {
  const P = S.H0.periods, pairs = regionPairs(lv);
  for (let n = 0; n < pairs.length; n += 3) {
    const a = pairs[n], r1 = pairs[n + 1], r2 = pairs[n + 2], p1 = of[r1], p2 = r2 < 0 ? -2 : of[r2];
    if (p2 === -2 || p1 === p2 || (p1 < 0 && p2 < 0)) continue;
    const s1 = p1 < 0 ? null : P[p1].state, s2 = p2 < 0 ? null : P[p2].state;
    if (s1 === s2) continue;
    yield { a, p1, p2, s1, s2, open: s1 == null || s2 == null };
  }
}
// an arc and the regions on its two sides (-1: one side only, the coast), three numbers each
export function regionPairs(lv) {
  const g = geoAt(S.H0.regions[0].o, lv), R = S.H0.pairs;
  if (R.has(g)) return R.get(g);
  const n = g.T.at.length - 1, one = new Int32Array(n).fill(-1), two = new Int32Array(n).fill(-1);
  for (let r = 0; r < S.H0.regions.length; r++) for (let j = g.start[r]; j < g.start[r + 1]; j++) { const a = g.refs[j]; if (a === RING || a === POLY) continue;
    const x = a < 0 ? ~a : a; if (one[x] < 0) one[x] = r; else if (two[x] < 0) two[x] = r; }
  const out = []; for (let x = 0; x < n; x++) if (one[x] >= 0) out.push(x, one[x], two[x]);
  const pairs = Int32Array.from(out); R.set(g, pairs); return pairs;
}
// from a copy: the day's borders, a list of arcs for each way of drawing one: an approximate border blurred, one to land no
// state held dashed
export function histLines(lv) {
  const now = histOn(), g = geoAt(S.H0.regions[0].o, lv), P = S.H0.periods;
  return now.lv[lv]?.g === g ? now.lv[lv] : now.lv[lv] = (() => {
    const lines = { g, T: g.T, rough: [], roughOpen: [], fixed: [], partly: [], open: [], inner: [] };
    for (const { a, p1, p2, s1, s2, open } of bordersOf(now.of, lv)) {
      const pr = Math.min(p1 < 0 ? 9 : P[p1].precision, p2 < 0 ? 9 : P[p2].precision);
      const o1 = p1 < 0 ? null : P[p1].owner, o2 = p2 < 0 ? null : P[p2].owner;   // (within one state: a province and its ruler, two of one ruler's)
      lines[!open && (o1 === s2 || o2 === s1 || (o1 != null && o1 === o2)) ? "inner" : pr === 1 ? (open ? "roughOpen" : "rough") : open ? "open" : pr === 2 ? "partly" : "fixed"].push(a);
    }
    return lines;
  })();
}
// a country-period's land on the day shown, merged of its regions (none if it has none then)
export function histFeature(pi) {
  const rs = histOn().members.get(pi);
  return rs ? [{ ...merged(rs.map((r) => S.H0.regions[r])), properties: S.H0.periods[pi] }] : [];
}
// the coarsest copy still about as fine as a pixel; while the map moves, as fine as a few
export const pxKm = () => R_KM / S.proj.scale();
