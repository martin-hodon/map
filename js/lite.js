// lite.js -- parseLite: a light file (data/*.txt) read into typed arrays -- the shared arcs and each object's rows
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { RING, POLY } from "./geom.js";

// a light file read (the format: build/lite.py; build/small.py its copies): @arcs (a line each: x y dx dy ...; "dw:k:dk",
// a stretch of base's), then each object's rows (a header, a row each, its arcs last -- or, grouped, a row a thing and
// @name.pieces a row a piece, with what differs). The points and the rows' arcs go straight into typed arrays: the text
// is never split into lines or numbers. `known`: the objects known already -- a copy's rows name their row, a layer read again
// has its names already.
export function parseLite(text, base, known) {
  const len = text.length, objects = {};
  let pos = 0, sc = 1, tx = 0, ty = 0, xy = new Float32Array(1 << 16), np = 0, at = new Int32Array(1 << 12), na = 0;
  const lineEnd = () => { const e = text.indexOf("\n", pos); return e < 0 ? len : e; };
  const value = (v, t) => v === "" ? undefined : t === "#" ? +v : t === "[]" ? v.split("|") : t === "[]#" ? v.split("|").map(Number) : t === "?" ? v === "1" : t === "{}" ? JSON.parse(v) : v;
  const readArcs = () => {
    for (; pos < len && text.charCodeAt(pos) !== 64; pos++) {       // (to the next @)
      const e = lineEnd();
      if (na + 2 > at.length) { const b = new Int32Array(at.length * 2); b.set(at); at = b; }
      at[na++] = np;
      let x = 0, y = 0, first = true, have = 0, pair = 0;
      const put = (px, py) => {
        if (!first && px === x && py === y) return;
        if (2 * np + 4 > xy.length) { const b = new Float32Array(xy.length * 2); b.set(xy); xy = b; }
        xy[2 * np] = px * sc + tx; xy[2 * np + 1] = py * sc + ty; np++; x = px; y = py; first = false;
      };
      for (let i = pos; i < e;) {
        let c = text.charCodeAt(i);
        if (c === 32) { i++; continue; }
        let neg = false, n = 0;
        if (c === 45) { neg = true; c = text.charCodeAt(++i); }
        while (c >= 48 && c <= 57) { n = n * 10 + c - 48; c = i + 1 < e ? text.charCodeAt(++i) : (i++, 32); }
        if (neg) n = -n;
        if (c === 58) {                                             // (dw:k:dk: base's arc, from its point k, |dk| steps on, back on the grid)
          let k = 0, dk = 0, sign = 1;
          for (c = text.charCodeAt(++i); c >= 48 && c <= 57; c = text.charCodeAt(++i)) k = k * 10 + c - 48;
          c = text.charCodeAt(++i); if (c === 45) { sign = -1; c = text.charCodeAt(++i); }
          while (c >= 48 && c <= 57) { dk = dk * 10 + c - 48; c = i + 1 < e ? text.charCodeAt(++i) : (i++, 32); }
          lastW += n;
          for (let j = 0, q = 2 * (base.at[lastW] + k); j <= dk; j++, q += 2 * sign) put(Math.round((base.xy[q] - tx) / sc), Math.round((base.xy[q + 1] - ty) / sc));
          have = 0; continue;
        }
        if (!have) { pair = n; have = 1; continue; }
        have = 0;
        if (first) put(pair, n); else put(x + pair, y + n);
      }
      if (np - at[na - 1] === 1) { if (2 * np + 4 > xy.length) { const b = new Float32Array(xy.length * 2); b.set(xy); xy = b; } xy[2 * np] = xy[2 * np - 2]; xy[2 * np + 1] = xy[2 * np - 1]; np++; }   // (all on one point of the grid: two still, as a line must have)
      pos = e;
    }
    at[na] = np;
  };
  let lastW = 0;
  const spec = (line) => line.split(",").map((c) => { const m = c.match(/^(.*?)(\[\]#|\[\]|#|\?|\{\})?$/); return [m[1], m[2] || ""]; });
  const things = {};
  const readObject = (head) => {
    const piecesOf = head[0].endsWith(".pieces") ? head[0].slice(0, -7) : null, name = piecesOf ?? head[0];
    let e = lineEnd();
    const cols = spec(text.slice(pos, e)), hasArcs = cols.at(-1)[0] === "arcs", byRow = cols[0][0] === "row", was = known?.[name];
    pos = e + 1;
    const wantProps = !byRow && !was && cols.length > (hasArcs ? 1 : 0), lines = [];
    let refs = new Int32Array(hasArcs ? 1 << 12 : 0), nr = 0, idx = 0, rows = 0;
    const n0 = byRow ? was.n : 0;
    let start = new Int32Array(byRow ? n0 + 1 : 1 << 10);
    const open = () => { if (nr + 2 >= refs.length) { const b = new Int32Array(refs.length * 2); b.set(refs); refs = b; } };
    for (; pos < len && text.charCodeAt(pos) !== 64; pos = e + 1) {
      e = lineEnd();
      if (e === pos) continue;
      if (!hasArcs) { if (wantProps) lines.push(text.slice(pos, e)); rows++; continue; }
      let cut = text.lastIndexOf(",", e - 1); if (cut < pos) cut = pos - 1;
      if (byRow) { const r = +text.slice(pos, cut); while (idx <= r) start[idx++] = nr; }
      else { if (idx + 2 > start.length) { const b = new Int32Array(start.length * 2); b.set(start); start = b; } start[idx++] = nr; if (wantProps) lines.push(text.slice(pos, Math.max(cut, pos))); }
      rows++;
      let c, v = 0, neg = false, inNum = false;
      const any = cut + 1 < e;
      for (let i = cut + 1; i <= e; i++) {
        c = i < e ? text.charCodeAt(i) : 0;
        if (c >= 48 && c <= 57) { v = v * 10 + c - 48; inNum = true; continue; }
        if (c === 45) { neg = true; continue; }
        if (inNum) { open(); refs[nr++] = neg ? -v : v; v = 0; neg = false; inNum = false; }
        if (c === 59) { open(); refs[nr++] = RING; }
        else if (c === 124) { open(); refs[nr++] = RING; refs[nr++] = POLY; }
      }
      if (any) { open(); refs[nr++] = RING; if ((was?.kind ?? kindOf[name]) === "polygon") refs[nr++] = POLY; }
    }
    if (!hasArcs) {                                                 // (a grouped object's things: the key first)
      if (wantProps) things[name] = readRows(cols, lines);
      kindOf[name] = head[1] ?? kindOf[name];
      return;
    }
    if (byRow) while (idx <= n0) start[idx++] = nr;
    else start[idx] = nr;
    const n = byRow ? n0 : idx;
    let props = null;
    if (wantProps) {
      props = readRows(cols, lines, name);
      if (piecesOf && things[name]) { const key = Object.keys(things[name][0] || {})[0], by = new Map(things[name].map((t) => [t[key], t]));
        props = props.map((own) => Object.assign(Object.create(by.get(own[key]) ?? null), own)); }
    }
    objects[name] = { kind: was?.kind ?? kindOf[name], n, rows: props, g: { start: byRow ? start : start.slice(0, n + 1), refs: refs.slice(0, nr) } };
  };
  const kindOf = {};
  const readRows = (cols, lines) => {
    const keep = cols.filter(([k]) => k !== "arcs"), out = [], one = new Map();   // (a text only once: "primary", "Asia")
    for (const r of d3.csvParseRows(lines.join("\n"))) { const o = {}; keep.forEach(([k, t], i) => { if (k === "~id") return; let v = value(r[i] ?? "", t); if (typeof v === "string") { const w = one.get(v); if (w) v = w; else one.set(v, v); } if (v !== undefined) o[k] = v; }); out.push(o); }
    return out;
  };
  while (pos < len) {
    const c = text.charCodeAt(pos), e = lineEnd();
    if (e === pos || c === 35) { pos = e + 1; continue; }
    if (c === 103) { const [a, x, y] = text.slice(pos + 5, e).split(" ").map(Number); sc = a; tx = x; ty = y; pos = e + 1; continue; }   // (grid ...)
    if (c === 64) {
      const head = text.slice(pos + 1, e).split(" ");
      pos = e + 1;
      if (head[0] === "arcs") { readArcs(); continue; }
      if (head[1]) kindOf[head[0]] = head[1];
      readObject(head);
      continue;
    }
    pos = e + 1;                                                    // (uses ...)
  }
  const T = { xy: xy.slice(0, 2 * np), at: at.slice(0, na + 1), objects };
  for (const k in objects) objects[k].g.T = T;
  return T;
}
