// FLAGS AND COATS OF ARMS FROM TEXT: a flag written as a line -- France `blue | white | red`, Germany `[3:5] black /
// red / gold`, Japan `white + red disc size 0.6` -- drawn to SVG or onto a canvas, the same shapes either way. A coat of
// arms is the same language in a shield (`[shield] ...`), and a part of one can be another flag or arms (`@castile`).
// The whole language is in flags.html (the gallery and an editor); the definitions are data/flags.txt.
//
//   const lib = Flags.library(text)                 the definitions file: `CODE: definition` a line (# a comment)
//   lib.svg("FR", { height: 20 })                    an <svg> string;  Flags.svg("blue | white | red", ...) one alone
//   lib.draw(ctx, "FR", x, y, w, h)                  onto a canvas (w or h null: from the flag's own ratio)
//   lib.image("FR", 20)                              a canvas of it, kept: for drawImage on a map
//   lib.has("FR"), lib.ratio("FR"), lib.codes, lib.gaps (the codes defined as `-`: no flag), lib.errors
(function (root) {
"use strict";

// ---- colours: a few names for the usual flag colours (and the heraldic tinctures), or #rgb / #rrggbb --------------
const COLORS = {                                                     // (names for the flags' usual shades: near enough, not exact)
  // reds
  red: "#d52b1e", scarlet: "#ed1c24", brightred: "#ff0000", crimson: "#c8102e", cherry: "#ce1126",
  cardinal: "#bf0a30", darkred: "#a51931", maroon: "#8d1b3d",
  // oranges, yellows
  orange: "#ff8200", saffron: "#ff9933", amber: "#ffb612", rust: "#e05206", ochre: "#c65d1f", yellow: "#fcd116",
  lemon: "#ffef00", lightyellow: "#fcdc50", gold: "#f6b40e", darkgold: "#c09300",
  // browns
  brown: "#7b4a2a", chestnut: "#a0522d", copper: "#d57800", bronze: "#b07e3c", tan: "#c4a35a", sand: "#e8c98c",
  // greens
  green: "#009a44", emerald: "#00a651", kelly: "#1eb53a", grass: "#138808", jade: "#009e60", lightgreen: "#6aa84f",
  lime: "#7ac143", moss: "#4a7c2c", olive: "#4e5b31", seagreen: "#2e8b57", viridian: "#00785e", teal: "#00868b",
  mediumgreen: "#00843d", darkgreen: "#006233", deepgreen: "#006400", forest: "#00533e", pine: "#01411c",
  // blues
  blue: "#0055a4", royalblue: "#0038a8", cobalt: "#0047ab", azure: "#0072ce", brightblue: "#0066ff",
  dodgerblue: "#1e90ff", steelblue: "#3d8fd6", sky: "#75aadb", lightblue: "#41b6e6", cornflower: "#6fb7e9", cerulean: "#0098d4",
  aqua: "#00abc9", cyan: "#00bce4", navy: "#012169", darkblue: "#002868", deepblue: "#0010a0",
  ultramarine: "#0c1c8c", midnight: "#0f204b",
  // the rest
  purple: "#6c2d82", violet: "#3c3b6e", pink: "#f4a6c4", white: "#ffffff", black: "#000000", grey: "#8d8d8d",
  gray: "#8d8d8d", silver: "#c0c0c0", darkgrey: "#555555",
  // the tinctures
  argent: "#ffffff", or: "#f6b40e", gules: "#d52b1e", azure_: "#0072ce", vert: "#009a44", sable: "#000000", purpure: "#6c2d82",
};
const color = (name) => /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(name) ? name : COLORS[name];
const isColor = (name) => !!color(name);

class FlagError extends Error { constructor(msg, at) { super(at == null ? msg : `${msg} (at ${at + 1})`); this.at = at; } }

// ---- the language ----------------------------------------------------------------------------------------------
//   def      := [shape] expr                  [2:3] (height:width, the default), [1:1], [shield] (iberian, french: other
//                                             shields; any with its own h:w: [iberian 6:5]), [pennant], [round]
//   expr     := field ('+' charge)*           charges drawn over the field, in order
//             | ('+' charge)+                a motif: charges alone, no field (a constellation), used as + @name
//   field    := cols ('/' cols)*              bands top to bottom
//   cols     := part ('|' part)*              bands hoist to fly
//   part     := atom ['*' weight]             a band's share (1 by default): red / yellow*2 / red
//   atom     := colour | '(' expr ')' | @name | division '(' args ')'
//   charge   := [colour [colour]] shape {modifier}    or   canton|box|shield|circle '(' expr ')' {modifier}   or  @name {modifier}
//   modifier := at x,y | size s | size w,h | w s | n k | rot deg | points k | r s | span deg | t s | from x,y | to x,y
//             | ring | row | arc | grid r,c | flip | flipv | outline (a shape as lines, w wide: a star as its line star)
//             | smooth (a poly's or line's points joined by a curve through them; x,y! a corner in it)
//             | mirror (the charge again, mirrored about its middle: for a poly or line give one side, and an outline
//                       that starts and ends on the middle, x = 0.5, is joined to its mirror image as one)
//   poly x,y x,y … [/ x,y x,y …]               outlines, filled even-odd (a / starts the next: a hole, or another piece)
//   line x,y x,y … [/ x,y x,y …]               lines w wide, with round ends: a stroke of a pen
const SHAPES = ["rect", "shield", "iberian", "french", "pennant", "round"];
const ARMS = new Set(["shield", "iberian", "french"]);    // (the shields: a coat of arms' shapes)
const DIVISIONS = new Set(["quarterly", "up", "down", "x", "stripes", "pales", "checky", "lozengy"]);
const BOXES = new Set(["canton", "box", "shield", "circle"]);
const MODS_NUM = new Set(["size", "w", "n", "rot", "points", "r", "span", "t", "inner", "k", "d"]);
const MODS_PAIR = new Set(["at", "from", "to", "grid"]);
const MODS_FLAG = new Set(["ring", "row", "arc", "flip", "flipv", "outline", "smooth", "mirror"]);

function tokenize(s) {
  const out = [], re = /\s*(?:(#[0-9a-fA-F]{3,6}\b)|(-?\d*\.?\d+)|(@?[A-Za-z_][\w.-]*)|([|/+*(),\[\]:!]))/y;
  let m, i = 0;
  while (i < s.length) {
    re.lastIndex = i;
    if (/^\s*$/.test(s.slice(i))) break;
    if (!(m = re.exec(s))) throw new FlagError(`can't read "${s.slice(i).trim().slice(0, 12)}"`, i);
    const at = m.index + m[0].length - (m[1] || m[2] || m[3] || m[4]).length;
    if (m[1]) out.push({ t: "word", v: m[1].toLowerCase(), at });
    else if (m[2]) out.push({ t: "num", v: parseFloat(m[2]), at });
    else if (m[3]) out.push(m[3][0] === "@" ? { t: "ref", v: m[3].slice(1), at } : { t: "word", v: m[3].toLowerCase(), at });
    else out.push({ t: m[4], at });
    i = re.lastIndex;
  }
  out.push({ t: "end", at: s.length });
  return out;
}

function parse(text) {
  const T = tokenize(text);
  let p = 0;
  const peek = (k = 0) => T[p + k], next = () => T[p++];
  const want = (t) => { const x = next(); if (x.t !== t) throw new FlagError(`expected "${t}" but found ${show(x)}`, x.at); return x; };
  const show = (x) => x.t === "end" ? "the end" : x.t === "word" || x.t === "ref" ? `"${x.v}"` : x.t === "num" ? x.v : `"${x.t}"`;
  const num = () => { const x = next(); if (x.t !== "num") throw new FlagError(`expected a number but found ${show(x)}`, x.at); return x.v; };

  let shape = "rect", ratio = 2 / 3;
  if (peek().t === "[") {
    next();
    if (peek().t === "num") { const h = num(); want(":"); const w = num(); ratio = h / w; }
    else { const x = next(); if (x.t !== "word" || !SHAPES.includes(x.v)) throw new FlagError(`unknown shape ${show(x)}`, x.at); shape = x.v;
           ratio = { shield: 1.2, iberian: 1.15, french: 1.12, pennant: 1.22, round: 1, rect: ratio }[shape];
           if (peek().t === "num") { const h = num(); want(":"); const w = num(); ratio = h / w; } }
    want("]");
  }
  const body = expr();
  if (peek().t !== "end") throw new FlagError(`unexpected ${show(peek())}`, peek().at);
  return { shape, ratio, body, motif: body.k === "layer" && !body.base };

  function expr() {
    const base = peek().t === "+" ? null : field(), charges = [];
    while (peek().t === "+") { next(); charges.push(charge()); }
    return charges.length ? { k: "layer", base, charges } : base;
  }
  // (each level gives {node, wt}: a lone band keeps its weight for the level above -- the yellow*2 of red / yellow*2 / red)
  function field() { return split("/", "h", () => split("|", "v", part)).node; }
  function split(op, dir, sub) {
    const items = [sub()];
    while (peek().t === op) { next(); items.push(sub()); }
    return items.length === 1 ? items[0] : { node: { k: "split", dir, parts: items.map((q) => ({ node: q.node, wt: q.wt ?? 1 })) } };
  }
  function part() {
    const node = atom();
    if (peek().t === "*") { next(); return { node, wt: num() }; }
    return { node, wt: undefined };
  }
  function atom() {
    const x = next();
    if (x.t === "(") { const e = expr(); want(")"); return e; }
    if (x.t === "ref") return { k: "ref", name: x.v, at: x.at };
    if (x.t === "word" && isColor(x.v)) return { k: "color", c: color(x.v) };
    if (x.t === "word" && DIVISIONS.has(x.v) && peek().t === "(") {
      next(); const args = [];
      do { args.push(peek().t === "num" ? next().v : expr()); } while (peek().t === "," && next());
      want(")");
      return { k: "div", name: x.v, args, at: x.at };
    }
    throw new FlagError(`expected a colour, "(", @name or a division but found ${show(x)}`, x.at);
  }
  function charge() {
    const colors = [];
    while (peek().t === "word" && isColor(peek().v)) colors.push(color(next().v));
    const x = next(), ch = { colors, mods: {}, at: x.at };
    if (x.t === "ref") { ch.shape = "ref"; ch.sub = { k: "ref", name: x.v, at: x.at }; }
    else if (x.t === "word" && BOXES.has(x.v) && peek().t === "(") { next(); ch.shape = x.v; ch.sub = expr(); want(")"); }
    else if (x.t === "word" && CHARGES[x.v]) ch.shape = x.v;
    else throw new FlagError(`unknown charge ${show(x)}`, x.at);
    if (x.t === "word" && peek().t === "num" && (x.v === "stars" || x.v === "trigram")) ch.mods.n = next().v;   // (stars 12, trigram 101)
    modifiers();
    if (ch.shape === "poly" || ch.shape === "line") {                         // poly x,y x,y x,y ... (fractions of the field; x,y! a corner)
      ch.rings = [];
      do {
        const ring = [];
        while (peek().t === "num") { const a = num(); want(","); const q = [a, num()]; if (peek().t === "!") { next(); q.push(true); } ring.push(q); }
        if (ring.length < (ch.shape === "poly" ? 3 : 2)) throw new FlagError(`${ch.shape} wants ${ch.shape === "poly" ? "three" : "two"} points or more`, x.at);
        ch.rings.push(ring);
      } while (peek().t === "/" && peek(1).t === "num" && next());
      modifiers();
    }
    return ch;

    function modifiers() { for (;;) {
      const m = peek();
      if (m.t !== "word") break;
      if (MODS_FLAG.has(m.v)) { next(); ch.mods[m.v] = true; continue; }
      if (MODS_NUM.has(m.v) || MODS_PAIR.has(m.v)) {
        next(); const a = num();
        if (peek().t === "," && peek(1).t === "num") { next(); ch.mods[m.v] = [a, num()]; }
        else if (MODS_PAIR.has(m.v)) throw new FlagError(`"${m.v}" wants two numbers: x,y`, m.at);
        else ch.mods[m.v] = a;
        continue;
      }
      break;
    } }
  }
}

// ---- drawing: a definition becomes OPS -- fills, strokes and clipped groups of them, with SVG path data in the
// flag's own units -- which svg() writes as elements and draw() paints with Path2D ---------------------------------
const f2 = (v) => Math.round(v * 100) / 100;
const rectD = (x, y, w, h) => `M${f2(x)} ${f2(y)}H${f2(x + w)}V${f2(y + h)}H${f2(x)}Z`;
const polyD = (pts) => "M" + pts.map((q) => `${f2(q[0])} ${f2(q[1])}`).join("L") + "Z";
const lineD = (pts) => "M" + pts.map((q) => `${f2(q[0])} ${f2(q[1])}`).join("L");
// a curve through the points, each one's tangent along the way from the point before it to the one after; at a corner
// (q[2]) or an open end none, so the curve comes straight at it
function curveD(pts, closed) {
  const n = pts.length, at = (i) => pts[(i + n) % n];
  const along = (i) => { if (at(i)[2] || (!closed && (i === 0 || i === n - 1))) return null;
    const a = at(i - 1), b = at(i + 1), l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1; return [(b[0] - a[0]) / l, (b[1] - a[1]) / l]; };
  let d = `M${f2(pts[0][0])} ${f2(pts[0][1])}`;
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const p = at(i), q = at(i + 1), dx = q[0] - p[0], dy = q[1] - p[1], l = Math.hypot(dx, dy) / 3, s = along(i), e = along(i + 1);
    d += `C${f2(s ? p[0] + s[0] * l : p[0] + dx / 3)} ${f2(s ? p[1] + s[1] * l : p[1] + dy / 3)} ${f2(e ? q[0] - e[0] * l : q[0] - dx / 3)} ${f2(e ? q[1] - e[1] * l : q[1] - dy / 3)} ${f2(q[0])} ${f2(q[1])}`;
  }
  return closed ? d + "Z" : d;
}
// a poly's or line's outline and its mirror image about the middle: one outline if it ends on the middle, else two
function mirrored(q, closed) {
  const onIt = (p) => Math.abs(p[0] - 0.5) < 0.002, back = q.map(([x, y, c]) => [1 - x, y, c]).reverse();
  if (onIt(q[0]) && onIt(q[q.length - 1])) return closed ? [[...q, ...back.slice(1, -1)]] : [q, back];
  if (!closed && onIt(q[q.length - 1])) return [[...q, ...back.slice(1)]];
  if (!closed && onIt(q[0])) return [[...back.slice(0, -1), ...q]];
  return [q, back];
}
function outlineD(shape, x, y, w, h) {
  if (shape === "shield") return `M${f2(x)} ${f2(y)}H${f2(x + w)}V${f2(y + h * 0.5)}C${f2(x + w)} ${f2(y + h * 0.78)} ${f2(x + w * 0.62)} ${f2(y + h * 0.9)} ${f2(x + w / 2)} ${f2(y + h)}` +
                                 `C${f2(x + w * 0.38)} ${f2(y + h * 0.9)} ${f2(x)} ${f2(y + h * 0.78)} ${f2(x)} ${f2(y + h * 0.5)}Z`;
  if (shape === "iberian") { const r = Math.min(w / 2, h / 2);             // (round at the foot: Spain's, Portugal's)
    return polyD([[x, y], [x + w, y], ...arc(x + w / 2, y + h - r, w / 2, r, 0, Math.PI, 32), [x, y]]); }
  if (shape === "french") return `M${f2(x)} ${f2(y)}H${f2(x + w)}V${f2(y + h * 0.8)}Q${f2(x + w)} ${f2(y + h * 0.9)} ${f2(x + w * 0.64)} ${f2(y + h * 0.91)}` +   // (square, a point at the foot)
                                 `Q${f2(x + w * 0.54)} ${f2(y + h * 0.92)} ${f2(x + w / 2)} ${f2(y + h)}Q${f2(x + w * 0.46)} ${f2(y + h * 0.92)} ${f2(x + w * 0.36)} ${f2(y + h * 0.91)}` +
                                 `Q${f2(x)} ${f2(y + h * 0.9)} ${f2(x)} ${f2(y + h * 0.8)}Z`;
  if (shape === "round") return polyD(arc(x + w / 2, y + h / 2, w / 2, h / 2, 0, 2 * Math.PI, 48));
  if (shape === "pennant") return polyD([[x, y], [x + w, y + h * 0.45], [x + w * 0.38, y + h * 0.45], [x + w, y + h], [x, y + h]]);
  return rectD(x, y, w, h);
}
const arc = (cx, cy, rx, ry, a0, a1, n) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + (a1 - a0) * i / n; return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)]; });
// a line from a to b carried on past both ends (so a wide stroke's square ends lie outside the field)
const longLine = (a, b, k = 3) => { const dx = b[0] - a[0], dy = b[1] - a[1]; return [[a[0] - dx * k, a[1] - dy * k], [b[0] + dx * k, b[1] + dy * k]]; };

// the charges: each a default size and place (fractions of the field; size of its height), and how it is drawn
const CHARGES = {
  // lines across the field (w: their width, of the field's height)
  cross:   { w: 0.2, line: (R, c, m) => [longLine([R.x, c[1]], [R.x + R.w, c[1]], 0.1), longLine([c[0], R.y], [c[0], R.y + R.h], 0.1)] },
  nordic:  { w: 0.2, at: [0.37, 0.5], line: (R, c) => CHARGES.cross.line(R, c) },
  saltire: { w: 0.2, line: (R) => [longLine([R.x, R.y], [R.x + R.w, R.y + R.h], 0.1), longLine([R.x + R.w, R.y], [R.x, R.y + R.h], 0.1)] },
  band:    { w: 0.2, line: (R, c) => [longLine([R.x, c[1]], [R.x + R.w, c[1]], 0.1)] },
  pale:    { w: 0.2, line: (R, c) => [longLine([c[0], R.y], [c[0], R.y + R.h], 0.1)] },
  // a wave across: n waves over the width, r high (of the height)
  wave:    { w: 0.06, line: (R, c, m) => { const n = m.n ?? 4, a = (m.r ?? 0.03) * R.h, q = [];
    for (let i = -2; i <= n * 24 + 2; i++) { const x = R.x + i / (n * 24) * R.w; q.push([x, c[1] - a * Math.cos(2 * Math.PI * i / 24)]); } return [q]; } },   // (a crest at the hoist)
  // (the diagonals, through `at`: the middle unless moved)
  bend:    { w: 0.25, line: (R, c) => [longLine([c[0] - R.w / 2, c[1] - R.h / 2], [c[0] + R.w / 2, c[1] + R.h / 2], 0.2)] },
  rise:    { w: 0.25, line: (R, c) => [longLine([c[0] - R.w / 2, c[1] + R.h / 2], [c[0] + R.w / 2, c[1] - R.h / 2], 0.2)] },
  // a Y on its side: from the hoist's two corners to `at`, and on to the fly
  pall:    { w: 0.2, at: [0.33, 0.5], line: (R, c) => [[R.x, R.y], [R.x, R.y + R.h]].map((k) => [[k[0] - (c[0] - k[0]) * 0.3, k[1] - (c[1] - k[1]) * 0.3], c, [R.x + R.w * 1.1, c[1]]]), join: "miter" },
  border:  { w: 0.1, outline: true },
  // shapes at a place (at: their middle) of a size
  disc: { size: 0.5 }, ring: { size: 0.5 }, star: { size: 0.3 }, stars: { size: 0.12 }, crescent: { size: 0.5 }, plus: { size: 0.6 },
  square: { size: 0.5 }, diamond: { size: [0.86, 0.8] }, sun: { size: 0.5 }, wheel: { size: 0.5 }, taegeuk: { size: 0.5 },
  triangle: { size: 0.5 }, poly: {}, line: { w: 0.02 }, branch: { size: 0.08, w: 0.012 }, script: { size: [0.55, 0.22] }, triskele: { size: 0.7 }, trigram: { size: 0.25 },
  // a field within the field: canton (from the top left: size its width and height), box, shield, circle (at their middle)
  canton: { size: [0.5, 0.5] }, box: { size: [0.5, 0.5] }, shield: { size: 0.5 }, circle: { size: 0.5 }, ref: { size: 0.5 },
};

function compile(def, lib, x, y, w, h) {
  const out = [], seen = [];
  let given = { colors: [], points: null };                        // (what a motif's charges take when they say none)
  const R0 = { x, y, w, h, outline: outlineD(def.shape, x, y, w, h) };
  out.push({ clip: R0.outline, ops: node(def.body, R0) });
  return out;

  function resolve(name, at) {
    const d = lib && lib.def(name);
    if (!d) throw new FlagError(`no flag "@${name}"`, at);
    if (seen.includes(name)) throw new FlagError(`"@${name}" refers to itself`, at);
    return d;
  }
  function node(n, R) {
    if (n.k === "color") return [{ fill: n.c, d: rectD(R.x, R.y, R.w, R.h) }];
    if (n.k === "ref") { const d = resolve(n.name, n.at); seen.push(n.name); const o = node(d.body, R); seen.pop(); return o; }
    if (n.k === "split") return split(n.dir, n.parts, R);
    if (n.k === "div") return division(n, R);
    if (n.k === "layer") {
      const o = n.base ? node(n.base, R) : [];
      for (const ch of n.charges) o.push(...charge(ch, R));
      return [{ clip: R.outline, ops: o }];
    }
    throw new FlagError("?");
  }
  // bands: a plain colour is filled on to the field's far edge, the next band over it (no seam between two)
  function split(dir, parts, R) {
    const total = parts.reduce((a, q) => a + q.wt, 0), o = [];
    let at = 0;
    for (const q of parts) {
      const a = at / total, b = (at + q.wt) / total; at += q.wt;
      const S = dir === "v" ? sub(R, R.x + a * R.w, R.y, (b - a) * R.w, R.h) : sub(R, R.x, R.y + a * R.h, R.w, (b - a) * R.h);
      const n = q.node, base = n.k === "layer" ? n.base : n;       // (a band with charges of its own: its colour so too, the charges over it)
      if (!base || base.k !== "color") { o.push(...node(n, S)); continue; }
      o.push({ fill: base.c, d: dir === "v" ? rectD(S.x, S.y, R.x + R.w - S.x, S.h) : rectD(S.x, S.y, S.w, R.y + R.h - S.y) });
      if (n !== base) o.push({ clip: S.outline, ops: n.charges.flatMap((ch) => charge(ch, S)) });
    }
    return o;
  }
  function piece(n, R, pts, many) {                               // (a part cut out of the field: a triangle, or many diamonds)
    const d = many ? many.map(polyD).join("") : polyD(pts);
    if (n.k === "color") return [{ fill: n.c, d }];
    return [{ clip: d, ops: node(n, R) }];
  }
  function division(n, R) {
    const A = n.args, want = (k, nums = 0) => { if (A.length !== k) throw new FlagError(`${n.name}() wants ${k} parts`, n.at);
      for (let i = 0; i < k; i++) if ((i < nums) !== (typeof A[i] === "number")) throw new FlagError(`${n.name}(): ${i < nums ? "a number" : "a colour or field"} as part ${i + 1}`, n.at); };
    const { x, y, w, h } = R, TL = [x, y], TR = [x + w, y], BL = [x, y + h], BR = [x + w, y + h], C = [x + w / 2, y + h / 2];
    switch (n.name) {
      case "quarterly": want(4); return split("h", [{ node: { k: "split", dir: "v", parts: [{ node: A[0], wt: 1 }, { node: A[1], wt: 1 }] }, wt: 1 },
                                                    { node: { k: "split", dir: "v", parts: [{ node: A[2], wt: 1 }, { node: A[3], wt: 1 }] }, wt: 1 }], R);
      case "up": want(2); return [...node(A[1], R), ...piece(A[0], R, [TL, TR, BL])];       // (a above the line rising to the fly's top)
      case "down": want(2); return [...node(A[1], R), ...piece(A[0], R, [TL, TR, BR])];     // (a above the line falling to the fly's foot)
      case "x": want(4); return [...node(A[0], R), ...piece(A[1], R, [TR, BR, C]), ...piece(A[2], R, [BL, BR, C]), ...piece(A[3], R, [TL, BL, C])];
      case "stripes": case "pales": {
        want(3, 1); const k = Math.max(1, Math.round(A[0]));
        return split(n.name === "stripes" ? "h" : "v", Array.from({ length: k }, (_, i) => ({ node: A[1 + i % 2], wt: 1 })), R);
      }
      case "lozengy": {                                           // (diamonds of b on a, r rows and c columns; a fifth number turns them by
        // that many degrees about the top of the hoist, r and c then any numbers: Bavaria's lozenges, bendwise)
        const turn = A.length === 5 && typeof A[4] === "number" ? A[4] : 0;
        if (A.length !== (turn ? 5 : 4) || typeof A[0] !== "number" || typeof A[1] !== "number" || typeof A[2] === "number" || typeof A[3] === "number")
          throw new FlagError("lozengy() wants rows, columns, two colours or fields, and a turn (degrees) if any", n.at);
        const r = turn ? A[0] : Math.round(A[0]), c = turn ? A[1] : Math.round(A[1]), o = node(A[2], R), dw = w / c, dh = h / r, ps = [];
        const t = turn * Math.PI / 180, cs = Math.cos(t), sn = Math.sin(t), to = ([u, v]) => [x + u * cs - v * sn, y + u * sn + v * cs];
        let i0 = 0, i1 = r, j0 = 0, j1 = c;
        if (turn) {                                               // (every cell the turned grid needs to cover the field)
          const uv = [[0, 0], [w, 0], [0, h], [w, h]].map(([a, b]) => [a * cs + b * sn, -a * sn + b * cs]);
          j0 = Math.floor(Math.min(...uv.map((q) => q[0])) / dw) - 1; j1 = Math.ceil(Math.max(...uv.map((q) => q[0])) / dw) + 1;
          i0 = Math.floor(Math.min(...uv.map((q) => q[1])) / dh) - 1; i1 = Math.ceil(Math.max(...uv.map((q) => q[1])) / dh) + 1;
        }
        for (let i = i0; i < i1; i++) for (let j = j0; j < j1; j++) { const pu = (j + 0.5) * dw, pv = (i + 0.5) * dh;   // (tip to tip: a shows between)
          ps.push([[pu, pv - dh / 2], [pu + dw / 2, pv], [pu, pv + dh / 2], [pu - dw / 2, pv]].map(to)); }
        return [...o, { clip: R.outline, ops: piece(A[3], R, null, ps) }];
      }
      case "checky": {
        want(4, 2); const r = Math.round(A[0]), c = Math.round(A[1]), o = node(A[2], R);
        for (let i = 0; i < r; i++) for (let j = 0; j < c; j++) if ((i + j) % 2) o.push(...node(A[3], sub(R, x + j * w / c, y + i * h / r, w / c, h / r)));
        return o;
      }
    }
    throw new FlagError(`unknown division ${n.name}`, n.at);
  }
  function sub(R, x, y, w, h, shape = "rect") { return { x, y, w, h, outline: outlineD(shape, x, y, w, h) }; }

  function charge(ch, R) {                                       // (outline: the shape's fills drawn as lines instead)
    const o = shapeOps(ch, R), m = ch.mods;
    if (m.mirror && !ch.rings) o.push({ turn: true, rot: 0, sx: -1, sy: 1, cx: R.x + (m.at ? m.at[0] : 0.5) * R.w, cy: R.y, ops: o.slice() });
    if (!m.outline) return o;
    const w = (m.w ?? 0.03) * R.h;
    const lined = (l) => l.map((q) => q.ops ? { ...q, ops: lined(q.ops) } : q.fill ? { stroke: q.fill, width: w, d: q.d, join: "miter" } : q);
    return lined(o);
  }
  function shapeOps(ch, R) {
    const D = CHARGES[ch.shape], m = ch.mods, c0 = ch.colors[0] || given.colors[0] || "#ffffff", c1 = ch.colors[1] || given.colors[1] || "#000000";
    const points = m.points || given.points || 5;
    const at = m.at || D.at || [0.5, 0.5], cx = R.x + at[0] * R.w, cy = R.y + at[1] * R.h;
    const size = m.size ?? D.size ?? 0.5;
    const [sw, sh] = Array.isArray(size) ? [size[0] * R.w, size[1] * R.h] : [size * R.h, size * R.h];
    const lw = (m.w ?? D.w ?? 0.1) * R.h;
    const rot = (m.rot || 0) * Math.PI / 180, fx = m.flip ? -1 : 1, fy = m.flipv ? -1 : 1;
    // local (x right, y down, both -0.5..0.5 of the charge's box) to the field
    const place = (pts, bx = cx, by = cy, w = sw, h = sh) => pts.map(([u, v]) => { u *= w * fx; v *= h * fy;
      return [bx + u * Math.cos(rot) - v * Math.sin(rot), by + u * Math.sin(rot) + v * Math.cos(rot)]; });
    const fillP = (polys, col = c0, eo = false) => ({ fill: col, d: polys.map(polyD).join(""), eo });

    if (D.line) return [{ stroke: c0, width: lw, d: D.line(R, [cx, cy], m).map(lineD).join(""), join: D.join }];
    if (D.outline) return [{ stroke: c0, width: lw * 2, d: R.outline }];
    switch (ch.shape) {
      case "canton": {
        const S = Array.isArray(size) ? sub(R, R.x, R.y, sw, sh) : sub(R, R.x, R.y, R.w * size, R.h * size);
        return node(ch.sub, S);
      }
      case "ref": {                                                  // (a motif: its charges in a box of its ratio, size 1 -- the field's height -- unless given; rot turns it about its centre, flip flipv mirror it)
        const d = resolve(ch.sub.name, ch.sub.at);
        if (!d.motif) break;
        const z = m.size ?? 1, [w, h] = Array.isArray(z) ? [z[0] * R.w, z[1] * R.h] : [z * R.h / d.ratio, z * R.h];
        const was = given; given = { colors: ch.colors.length ? ch.colors : given.colors, points: m.points || given.points };
        try { const o = node(ch.sub, sub(R, cx - w / 2, cy - h / 2, w, h));
          return m.rot || m.flip || m.flipv ? [{ turn: true, rot: m.rot || 0, sx: m.flip ? -1 : 1, sy: m.flipv ? -1 : 1, cx, cy, ops: o }] : o; } finally { given = was; }
      }
    }
    switch (ch.shape) {
      case "box": case "shield": case "circle": case "ref": {
        let shape = ch.shape === "box" ? "rect" : ch.shape === "circle" ? "round" : ch.shape, w = sw, h = sh;
        if (ch.shape === "ref") { const d = resolve(ch.sub.name, ch.sub.at); shape = d.shape; if (!Array.isArray(size)) w = sh / d.ratio; }
        else if (ch.shape === "shield" && !Array.isArray(size)) w = sh / 1.2;
        const S = sub(R, cx - w / 2, cy - h / 2, w, h, shape);
        const o = [{ clip: S.outline, ops: node(ch.sub, S) }];      // (a shield or arms gets a fine line round it)
        if (ARMS.has(shape)) o.push({ stroke: "#00000033", width: Math.max(0.3, h * 0.012), d: S.outline });
        return o;
      }
      case "disc": return [fillP([arc(cx, cy, sw / 2, sh / 2, 0, 2 * Math.PI, 64)])];
      case "ring": return [{ stroke: c0, width: m.w != null ? lw : sh * 0.12, d: polyD(arc(cx, cy, sw / 2, sh / 2, 0, 2 * Math.PI, 64)) }];
      case "square": return [fillP([place([[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]])])];
      case "diamond": return [fillP([place([[0, -0.5], [0.5, 0], [0, 0.5], [-0.5, 0]])])];
      case "triangle": {                                            // from the hoist (flip: from the fly) to a point size of the width in
        const d = (Array.isArray(m.size) ? m.size[0] : m.size ?? 0.5) * R.w, x0 = m.flip ? R.x + R.w : R.x, s = m.flip ? -1 : 1;
        const ty = m.at ? cy : R.y + R.h / 2, half = (m.size && Array.isArray(m.size) ? m.size[1] : 1) * R.h / 2;
        return [fillP([[[x0, ty - half], [x0 + s * d, ty], [x0, ty + half]]])];
      }
      case "poly": case "line": {
        const closed = ch.shape === "poly", rings = (m.mirror ? ch.rings.flatMap((q) => mirrored(q, closed)) : ch.rings).map((q) => q.map(([u, v, c]) => [R.x + u * R.w, R.y + v * R.h, c]));
        const d = rings.map((q) => m.smooth ? curveD(q, closed) : closed ? polyD(q) : lineD(q)).join("");
        return closed ? [{ fill: c0, d, eo: true }] : [{ stroke: c0, width: lw, d, join: "round", cap: "round" }];
      }
      case "plus": { const t = (m.t ?? 0.3) / 2;
        return [fillP([place([[-t, -0.5], [t, -0.5], [t, -t], [0.5, -t], [0.5, t], [t, t], [t, 0.5], [-t, 0.5], [-t, t], [-0.5, t], [-0.5, -t], [-t, -t]])])]; }
      case "star": {
        if (!m.outline) return [fillP([place(star(points, m.inner))])];
        const o = star(points, m.inner).filter((_, i) => i % 2 === 0), lines = [];   // (the line star: each point to the next but one)
        for (let s0 = 0; s0 < (points % 2 ? 1 : 2); s0++) { const q = []; for (let i = s0; q.length < (points % 2 ? points : points / 2); i += 2) q.push(o[i % points]); lines.push(place(q)); }
        return [fillP(lines)];
      }
      case "trigram": {                                             // three bars (n: 1 whole, 0 broken, top to bottom), size their length
        const bits = String(Math.round(m.n ?? 111)).padStart(3, "0").slice(-3), [L, T] = Array.isArray(size) ? [sw, sh] : [sh, sh * 2 / 3], q = [];
        for (let i = 0; i < 3; i++) { const v0 = -0.5 + i * 0.375, v1 = v0 + 0.25;
          for (const [u0, u1] of bits[i] === "1" ? [[-0.5, 0.5]] : [[-0.5, -1 / 24], [1 / 24, 0.5]]) q.push(place([[u0, v0], [u1, v0], [u1, v1], [u0, v1]], cx, cy, L, T)); }
        return [fillP(q)];
      }
      case "branch": {                                              // a stalk from `from` to `to` (bowed by span degrees), n pairs of
        // leaves along it and one at its tip, all alike: size a leaf's length, k its width (of the length), rot its angle off the stalk
        const P = (q) => [R.x + q[0] * R.w, R.y + q[1] * R.h], a = m.from ? P(m.from) : [cx, cy + R.h / 4], b = m.to ? P(m.to) : [cx, cy - R.h / 4];
        const th = (m.span || 0) * Math.PI / 180, c = Math.hypot(b[0] - a[0], b[1] - a[1]);
        let at_ = (t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], dir = () => Math.atan2(b[1] - a[1], b[0] - a[0]);
        if (Math.abs(th) > 1e-3) {                                  // (an arc: bowed to the right of the way from `from` to `to`; minus, the left)
          const nx = -(b[1] - a[1]) / c, ny = (b[0] - a[0]) / c, d = c / 2 / Math.tan(th / 2);
          const C = [(a[0] + b[0]) / 2 - nx * d, (a[1] + b[1]) / 2 - ny * d], rr = Math.hypot(a[0] - C[0], a[1] - C[1]);
          const a0 = Math.atan2(a[1] - C[1], a[0] - C[0]), s1 = ((Math.atan2(b[1] - C[1], b[0] - C[0]) - a0) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
          const sweep = Math.abs(s1 - Math.abs(th)) < 1e-6 ? s1 : s1 - 2 * Math.PI;
          at_ = (t) => [C[0] + rr * Math.cos(a0 + sweep * t), C[1] + rr * Math.sin(a0 + sweep * t)];
          dir = (t) => a0 + sweep * t + Math.sign(sweep) * Math.PI / 2;
        }
        const L = sh, W = L * (m.k ?? 0.36), off = (m.rot ?? 40) * Math.PI / 180, n = Math.round(m.n ?? 5), leaves = [];
        const leaf = ([x0, y0], g) => { const o = [];                // (pointed at both ends, its base on the stalk)
          for (let i = 0; i <= 16; i++) { const s = i <= 8 ? i / 8 : (16 - i) / 8, e = (i <= 8 ? 1 : -1) * W / 2 * Math.sin(Math.PI * s);
            o.push([x0 + s * L * Math.cos(g) - e * Math.sin(g), y0 + s * L * Math.sin(g) + e * Math.cos(g)]); }
          return o; };
        for (let i = 0; i < n; i++) { const t = n > 1 ? 0.12 + 0.76 * i / (n - 1) : 0.5, p = at_(t), g = dir(t);
          leaves.push(leaf(p, g - off), leaf(p, g + off)); }
        leaves.push(leaf(b, dir(1)));
        return [{ stroke: c0, width: lw, d: lineD(Array.from({ length: 49 }, (_, i) => at_(i / 48))) }, fillP(leaves)];
      }
      case "stars": {
        const n = Math.max(1, Math.round(m.n || 5)), pts = starPlaces(n, m, R, cx, cy, sh);
        return [fillP(pts.map(([px, py]) => place(star(points, m.inner), px, py)))];
      }
      case "crescent": {
        // a disc less a smaller one (k: its size, of the first) moved toward the fly by d (of the size); rot turns it
        const k = m.k ?? 0.8, r = 0.5, ri = r * k, dd = m.d ?? 0.2;
        const xi = (r * r - ri * ri + dd * dd) / (2 * dd), yi = Math.sqrt(Math.max(0, r * r - xi * xi));
        const t0 = Math.atan2(yi, xi), p0 = Math.atan2(yi, xi - dd);
        const pts = [...arc(0, 0, r, r, t0, 2 * Math.PI - t0, 40), ...arc(dd, 0, ri, ri, 2 * Math.PI - p0, p0, 40)];
        return [fillP([place(pts)])];
      }
      case "sun": {                                                 // a disc and n rays (r: their reach, of the size)
        const n = Math.round(m.n || 16), r = 0.5, rin = (m.inner ?? 0.62) * r, ray = [], o = [];
        for (let i = 0; i < 2 * n; i++) { const a = -Math.PI / 2 + i * Math.PI / n; ray.push([(i % 2 ? rin * 0.92 : r) * Math.cos(a), (i % 2 ? rin * 0.92 : r) * Math.sin(a)]); }
        o.push(fillP([place(ray)]), fillP([place(arc(0, 0, rin * 0.82, rin * 0.82, 0, 2 * Math.PI, 40))], ch.colors[1] || c0));
        return o;
      }
      case "wheel": {                                               // a ring with n spokes
        const n = Math.round(m.n || 24), d = [];
        for (let i = 0; i < n; i++) { const a = i * 2 * Math.PI / n; d.push(place([[0, 0], [0.5 * Math.cos(a), 0.5 * Math.sin(a)]])); }
        return [{ stroke: c0, width: sh * 0.07, d: polyD(place(arc(0, 0, 0.47, 0.47, 0, 2 * Math.PI, 48))) },
                { stroke: c0, width: sh * 0.025, d: d.map(lineD).join("") }, fillP([place(arc(0, 0, 0.08, 0.08, 0, 2 * Math.PI, 16))])];
      }
      case "script": {                                              // writing, as a mere impression: a line and strokes up from it
        const n = Math.round(m.n || 14), d = [lineD(place([[-0.5, 0.42], [0.5, 0.42]]))];
        for (let i = 0; i < n; i++) { const u = -0.47 + 0.94 * (i + 0.5) / n, f = Math.abs(Math.sin(i * 12.9898 + 4.1) * 43758.5453) % 1;
          d.push(lineD(place([[u, 0.42], [u + (f > 0.7 ? 0.03 : 0), 0.42 - (0.25 + 0.6 * f)]]))); if (f < 0.25) d.push(lineD(place([[u + 0.02, -0.4], [u + 0.04, -0.46]]))); }
        return [{ stroke: c0, width: sh * 0.1, d: d.join(""), join: "round" }];
      }
      case "triskele": {                                            // three running legs (Man, Sicily)
        const d = [];
        for (let i = 0; i < 3; i++) { const a = -Math.PI / 2 + i * 2 * Math.PI / 3, b = a + Math.PI * 0.55;
          const k = [0.26 * Math.cos(a), 0.26 * Math.sin(a)], f = [k[0] + 0.24 * Math.cos(b), k[1] + 0.24 * Math.sin(b)], t = [f[0] + 0.1 * Math.cos(b + Math.PI / 2), f[1] + 0.1 * Math.sin(b + Math.PI / 2)];
          d.push(lineD(place([[0, 0], k, f, t]))); }
        return [{ stroke: c0, width: sh * 0.1, d: d.join(""), join: "round" }, fillP([place(arc(0, 0, 0.08, 0.08, 0, 2 * Math.PI, 16))])];
      }
      case "taegeuk": {                                             // the first colour above, the second below, an S between
        const top = [...arc(0, 0, 0.5, 0.5, Math.PI, 2 * Math.PI, 40), ...arc(0.25, 0, 0.25, 0.25, 0, Math.PI, 20), ...arc(-0.25, 0, 0.25, 0.25, 0, -Math.PI, 20)];
        return [fillP([place(arc(0, 0, 0.5, 0.5, 0, 2 * Math.PI, 64))], c1), fillP([place(top)], c0)];
      }
    }
    throw new FlagError(`can't draw ${ch.shape}`, ch.at);
  }
}
function star(p, inner) {
  const k = inner ?? (p <= 6 ? Math.cos(2 * Math.PI / p) / Math.cos(Math.PI / p) : 0.5), out = [];
  for (let i = 0; i < 2 * p; i++) { const a = -Math.PI / 2 + i * Math.PI / p, r = i % 2 ? 0.5 * k : 0.5; out.push([r * Math.cos(a), r * Math.sin(a)]); }
  return out;
}
// where n stars go: a ring (r: its radius, of the height), a row or line (from x,y to x,y, else spread round `at`), an
// arc (r, span degrees, over the top), or a grid r,c (every other place of r rows and c columns: the US 9,11)
function starPlaces(n, m, R, cx, cy, sh) {
  const out = [];
  if (m.grid) {
    const [rows, cols] = m.grid, mx = sh * 0.9, my = sh * 0.75;
    for (let i = 0; i < rows && out.length < n; i++) for (let j = 0; j < cols && out.length < n; j++)
      if ((i + j) % 2 === 0) out.push([R.x + mx + j * (R.w - 2 * mx) / Math.max(1, cols - 1), R.y + my + i * (R.h - 2 * my) / Math.max(1, rows - 1)]);
    return out;
  }
  if (m.from || m.to || m.row) {
    const a = m.from ? [R.x + m.from[0] * R.w, R.y + m.from[1] * R.h] : [cx - (n - 1) * sh * 0.75, cy];
    const b = m.to ? [R.x + m.to[0] * R.w, R.y + m.to[1] * R.h] : [cx + (n - 1) * sh * 0.75, cy];
    for (let i = 0; i < n; i++) { const t = n === 1 ? 0.5 : i / (n - 1); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
    return out;
  }
  const r = (m.r ?? 0.33) * R.h;
  if (m.arc) {
    const span = (m.span ?? 180) * Math.PI / 180;
    for (let i = 0; i < n; i++) { const a = -Math.PI / 2 - span / 2 + span * (n === 1 ? 0.5 : i / (n - 1)); out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    return out;
  }
  for (let i = 0; i < n; i++) { const a = -Math.PI / 2 + i * 2 * Math.PI / n; out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  return out;
}

// ---- output ------------------------------------------------------------------------------------------------------
let clipN = 0;
function toSvg(ops, W, H, opts = {}) {
  const defs = [], body = [];
  const walk = (list) => list.map((o) => {
    if (o.clip) { const id = `fc${++clipN}`; defs.push(`<clipPath id="${id}"><path d="${o.clip}"/></clipPath>`); return `<g clip-path="url(#${id})">${walk(o.ops)}</g>`; }
    if (o.turn) return `<g transform="translate(${f2(o.cx)} ${f2(o.cy)}) rotate(${f2(o.rot)}) scale(${o.sx} ${o.sy}) translate(${f2(-o.cx)} ${f2(-o.cy)})">${walk(o.ops)}</g>`;
    if (o.fill) return `<path d="${o.d}" fill="${o.fill}"${o.eo ? ' fill-rule="evenodd"' : ""}/>`;
    return `<path d="${o.d}" fill="none" stroke="${o.stroke}" stroke-width="${f2(o.width)}"${o.join ? ` stroke-linejoin="${o.join}"` : ""}${o.cap ? ` stroke-linecap="${o.cap}"` : ""}/>`;
  }).join("");
  body.push(walk(ops));
  const w = opts.width ?? (opts.height ? opts.height * W / H : W), h = opts.height ?? (opts.width ? opts.width * H / W : H);
  const title = opts.title ? `<title>${String(opts.title).replace(/[<&]/g, (c) => c === "<" ? "&lt;" : "&amp;")}</title>` : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f2(W)} ${f2(H)}" width="${f2(w)}" height="${f2(h)}"${opts.cls ? ` class="${opts.cls}"` : ""}>${title}<defs>${defs.join("")}</defs>${body.join("")}</svg>`;
}
function toCanvas(ctx, ops) {
  for (const o of ops) {
    if (o.clip) { ctx.save(); ctx.clip(new Path2D(o.clip)); toCanvas(ctx, o.ops); ctx.restore(); }
    else if (o.turn) { ctx.save(); ctx.translate(o.cx, o.cy); ctx.rotate(o.rot * Math.PI / 180); ctx.scale(o.sx, o.sy); ctx.translate(-o.cx, -o.cy); toCanvas(ctx, o.ops); ctx.restore(); }
    else if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(new Path2D(o.d), o.eo ? "evenodd" : "nonzero"); }
    else { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.width; ctx.lineJoin = o.join || "miter"; ctx.lineCap = o.cap || "butt"; ctx.stroke(new Path2D(o.d)); }
  }
}
const UNIT = 100;                                                   // (a flag is drawn 100 units high; svg scales it)
function frame(def, opts) {                                         // (its outline: a thin line round a flag, so white shows on white)
  if (opts.outline === false || def.motif) return [];
  return [{ stroke: opts.outline || "#00000040", width: UNIT * 0.012, d: outlineD(def.shape, 0, 0, UNIT / def.ratio, UNIT) }];
}

// ---- a library: the definitions file -----------------------------------------------------------------------------
// `CODE Name: definition` a line (the name optional: `FR France: blue | white | red`); a line starting with a space goes
// on with the one before; # and a space start a comment
const MAX_DEF = 5000;                                              // (a definition longer than this is reported: traced emblems kept rough)
function library(text = "") {
  const defs = new Map(), src = new Map(), names = new Map(), errors = [], gaps = [], cache = new Map();
  const lines = text.split("\n"), rows = [];
  lines.forEach((l, i) => {
    const s = l.replace(/^\s*#.*$|\s#(\s.*)?$/, "").trimEnd();      // (# and a space: a comment; #ff0000 a colour)
    if (!s.trim()) return;
    if (/^\s/.test(s) && rows.length) rows[rows.length - 1].text += " " + s.trim();
    else rows.push({ text: s, line: i + 1 });
  });
  for (const r of rows) {
    const m = /^\s*([\w.-]+)(?:\s+([^:]*?))?\s*:\s*(.*)$/.exec(r.text);
    if (!m) { errors.push({ line: r.line, msg: "not `CODE Name: definition`" }); continue; }
    if (defs.has(m[1]) || src.has(m[1])) errors.push({ line: r.line, code: m[1], msg: "defined twice (the last counts)" });
    if (m[2]) names.set(m[1], m[2]);
    src.set(m[1], m[3]);
    if (m[3] === "-") { gaps.push(m[1]); continue; }                // (`-`: no flag shown, e.g. a gap in a state's history)
    if (m[3].length > MAX_DEF) errors.push({ line: r.line, code: m[1], msg: `${m[3].length} characters: more than ${MAX_DEF} (simplify it, or build it of parts)` });
    try { defs.set(m[1], parse(m[3])); } catch (e) { errors.push({ line: r.line, code: m[1], msg: e.message }); }
  }
  const lib = {
    codes: [...defs.keys()], gaps, errors, names,
    def: (code) => defs.get(code),
    source: (code) => src.get(code),
    has: (code) => defs.has(code),
    ratio: (code) => { const d = get(code); return d.ratio; },
    shape: (code) => get(code).shape,
    motif: (code) => !!get(code).motif,                           // (charges alone: drawn on nothing)
    svg: (code, opts = {}) => render(get(code), opts),
    draw: (ctx, code, x, y, w, h, opts = {}) => paint(ctx, get(code), x, y, w, h, opts),
    image(code, height, opts = {}) {                                // a canvas of it, for drawImage (kept by code and size)
      const key = `${code}|${height}|${opts.outline}`;
      if (cache.has(key)) return cache.get(key);
      const d = get(code), dpr = opts.dpr || (typeof devicePixelRatio === "number" ? devicePixelRatio : 1);
      const cv = document.createElement("canvas"), w = height / d.ratio;
      cv.width = Math.ceil(w * dpr); cv.height = Math.ceil(height * dpr);
      const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr); paint(ctx, d, 0, 0, w, height, opts);
      cv.cssWidth = w; cv.cssHeight = height;
      cache.set(key, cv); return cv;
    },
  };
  function get(code) {
    if (typeof code !== "string") return code;
    const d = defs.get(code); if (!d) throw new FlagError(`no flag "${code}"`); return d;
  }
  function render(d, opts) { const W = UNIT / d.ratio; return toSvg([...compile(d, lib, 0, 0, W, UNIT), ...frame(d, opts)], W, UNIT, opts); }
  function paint(ctx, d, x, y, w, h, opts) {
    if (w == null) w = h / d.ratio; if (h == null) h = w * d.ratio;
    ctx.save(); ctx.translate(x, y); ctx.scale(w / (UNIT / d.ratio), h / UNIT);
    toCanvas(ctx, [...compile(d, lib, 0, 0, UNIT / d.ratio, UNIT), ...frame(d, opts)]);
    ctx.restore();
  }
  lib.render = render; lib.paint = paint;
  return lib;
}

// one definition alone (it may name others of `lib`)
const Flags = {
  COLORS, FlagError, parse, library, isArms: (shape) => ARMS.has(shape),
  charges: Object.keys(CHARGES), divisions: [...DIVISIONS],
  svg: (text, opts = {}, lib = library()) => lib.render(parse(text), opts),
  draw: (ctx, text, x, y, w, h, opts = {}, lib = library()) => lib.paint(ctx, parse(text), x, y, w, h, opts),
};
root.Flags = Flags;
if (typeof module === "object" && module.exports) module.exports = Flags;
})(typeof self !== "undefined" ? self : this);
