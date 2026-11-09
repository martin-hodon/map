// flags.js -- flags and coats of arms (flags.js, data/flags.txt) by code, and a historical state's flag on a day
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { dayNum, histDay } from "./history.js";
import { inSpan } from "./data.js";

// ---- FLAGS (flags.js, data/flags.txt): a country's or a state's flag and coat of arms, by its ISO code -- under its name
// when it is selected, small beside it in the search, and the flag game's question
S.flagLib = null;
export const flagCode = (e) => !e ? null : e.flag ? e.flag : e.layer === "countries" || e.layer === "regions" ? e.feats[0].properties.part_iso || e.feats[0].properties.iso || null
  : e.layer === "hperiods" && S.H0 ? histFlag(S.H0.periods[e.period].state, inSpan(e) ? histDay() : e.span[0]) : null;
// a state of the historical map: its flag on a day -- h<state id>, or h<state id>.<date> (1923, 1923-07-06) for the one from
// that day on: the latest not after the day
S.histFlags = null;
export function histFlag(state, day) {
  if (!S.flagLib) return null;
  if (!S.histFlags) {
    S.histFlags = new Map();
    for (const c of [...S.flagLib.codes, ...S.flagLib.gaps]) {
      const m = /^h(\d+)(?:\.(-?\d{1,4}(?:-\d\d-\d\d)?))?$/.exec(c); if (!m) continue;
      if (!S.histFlags.has(+m[1])) S.histFlags.set(+m[1], []);
      S.histFlags.get(+m[1]).push([m[2] ? dayNum(m[2]) : -Infinity, c]);
    }
    for (const l of S.histFlags.values()) l.sort((a, b) => a[0] - b[0]);
  }
  let best = null;
  for (const [t, c] of S.histFlags.get(+state) || []) if (t <= dayNum(day)) best = c;
  return best && S.flagLib.has(best) ? best : null;  // (a `-` code: no flag from that day)
}
export function flagSvg(code, h, opts = {}) {
  if (!S.flagLib || !code || !S.flagLib.has(code)) return "";
  try { return S.flagLib.svg(code, { height: h, ...opts }); } catch (err) { console.warn(code, err.message); return ""; }
}
