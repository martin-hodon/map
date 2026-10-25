// FLAGS AND COATS OF ARMS FROM TEXT: a flag written as a line -- France `blue | white | red`, Germany `[3:5] black /
// red / gold`, Japan `white + red disc size 0.6` -- drawn to SVG or onto a canvas, the same shapes either way. A coat of
// arms is the same language in a shield (`[shield] ...`), and a part of one can be another flag or arms (`@castile`).
// The whole language is in flags.html (the gallery and an editor); the definitions are data/flags.txt.
//
//   const lib = Flags.library(text)                 the definitions file: `CODE: definition` a line (# a comment)
//   lib.svg("FR", { height: 20 })                    an <svg> string;  Flags.svg("blue | white | red", ...) one alone
//   lib.draw(ctx, "FR", x, y, w, h)                  onto a canvas (w or h null: from the flag's own ratio)
//   lib.image("FR", 20)                              a canvas of it, kept: for drawImage on a map
//   lib.has("FR"), lib.ratio("FR"), lib.codes, lib.errors
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
//   def      := [shape] expr                  [2:3] (height:width, the default), [1:1], [shield], [pennant]
//   expr     := field ('+' charge)*           charges drawn over the field, in order
//             | ('+' charge)+                a motif: charges alone, no field (a constellation), used as + @name
//   field    := cols ('/' cols)*              bands top to bottom
//   cols     := part ('|' part)*              bands hoist to fly
//   part     := atom ['*' weight]             a band's share (1 by default): red / yellow*2 / red
//   atom     := colour | '(' expr ')' | @name | division '(' args ')'
//   charge   := [colour [colour]] shape {modifier}    or   canton|box|shield|circle '(' expr ')' {modifier}   or  @name {modifier}
//   modifier := at x,y | size s | size w,h | w s | n k | rot deg | points k | r s | span deg | t s | from x,y | to x,y
//             | ring | row | arc | grid r,c | flip | flipv | outline (a shape as lines, w wide: a star as its line star)
//   poly x,y x,y … [/ x,y x,y …]               outlines, filled even-odd (a / starts the next: a hole, or another piece)
const SHAPES = ["rect", "shield", "pennant", "round"];
const DIVISIONS = new Set(["quarterly", "up", "down", "x", "stripes", "pales", "checky", "lozengy"]);
const BOXES = new Set(["canton", "box", "shield", "circle"]);
const MODS_NUM = new Set(["size", "w", "n", "rot", "points", "r", "span", "t", "inner", "k", "d"]);
const MODS_PAIR = new Set(["at", "from", "to", "grid"]);
const MODS_FLAG = new Set(["ring", "row", "arc", "flip", "flipv", "outline"]);

function tokenize(s) {
  const out = [], re = /\s*(?:(#[0-9a-fA-F]{3,6}\b)|(-?\d*\.?\d+)|(@?[A-Za-z_][\w.-]*)|([|/+*(),\[\]:]))/y;
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
           ratio = { shield: 1.2, pennant: 1.22, round: 1, rect: ratio }[shape];
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
    for (;;) {
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
    }
    if (ch.shape === "poly") {                                                // poly x,y x,y x,y ... (fractions of the field)
      ch.rings = [];
      do {
        const ring = [];
        while (peek().t === "num") { const a = num(); want(","); ring.push([a, num()]); }
        if (ring.length < 3) throw new FlagError("poly wants three points or more", x.at);
        ch.rings.push(ring);
      } while (peek().t === "/" && peek(1).t === "num" && next());
    }
    return ch;
  }
}

// ---- drawing: a definition becomes OPS -- fills, strokes and clipped groups of them, with SVG path data in the
// flag's own units -- which svg() writes as elements and draw() paints with Path2D ---------------------------------
const f2 = (v) => Math.round(v * 100) / 100;
const rectD = (x, y, w, h) => `M${f2(x)} ${f2(y)}H${f2(x + w)}V${f2(y + h)}H${f2(x)}Z`;
const polyD = (pts) => "M" + pts.map((q) => `${f2(q[0])} ${f2(q[1])}`).join("L") + "Z";
const lineD = (pts) => "M" + pts.map((q) => `${f2(q[0])} ${f2(q[1])}`).join("L");
function outlineD(shape, x, y, w, h) {
  if (shape === "shield") return `M${f2(x)} ${f2(y)}H${f2(x + w)}V${f2(y + h * 0.5)}C${f2(x + w)} ${f2(y + h * 0.78)} ${f2(x + w * 0.62)} ${f2(y + h * 0.9)} ${f2(x + w / 2)} ${f2(y + h)}` +
                                 `C${f2(x + w * 0.38)} ${f2(y + h * 0.9)} ${f2(x)} ${f2(y + h * 0.78)} ${f2(x)} ${f2(y + h * 0.5)}Z`;
  if (shape === "round") return polyD(arc(x + w / 2, y + h / 2, w / 2, h / 2, 0, 2 * Math.PI, 48));
  if (shape === "pennant") return polyD([[x, y], [x + w, y + h * 0.45], [x + w * 0.38, y + h * 0.45], [x + w, y + h], [x, y + h]]);
  return rectD(x, y, w, h);
}
const arc = (cx, cy, rx, ry, a0, a1, n) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + (a1 - a0) * i / n; return [cx + rx * Math.cos(a), cy + ry * Math.sin(a)]; });
// a line from a to b carried on past both ends (so a wide stroke's square ends lie outside the field)
const longLine = (a, b, k = 3) => { const dx = b[0] - a[0], dy = b[1] - a[1]; return [[a[0] - dx * k, a[1] - dy * k], [b[0] + dx * k, b[1] + dy * k]]; };

// the silhouettes (heraldry's common charges, simplified): polygons in a 100 x 100 box, `sym` the right half only (from
// the top of the middle round to its foot: mirrored for the left), `eo` drawn even-odd (the castle's door a hole; the lion, traced from Scotland's Royal Banner,
// its inner lines)
const SIL = {
  eagle: { sym: [50,10, 54,9, 57,12, 57,17, 54,21, 55,25, 60,26, 66,20, 73,12, 82,7, 95,5, 93,11, 99,14, 91,18, 97,23, 88,26, 94,32, 84,34, 89,40, 78,41, 82,47, 70,46, 63,48, 64,56, 72,60, 76,68, 69,66, 66,70, 61,64, 58,70, 64,80, 70,88, 60,86, 56,92, 50,88] },
  eagle2: { sym: [50,24, 53,17, 55,10, 59,6, 64,6, 68,9, 64,11, 61,13, 60,19, 61,26, 66,20, 73,12, 82,7, 95,5, 93,11, 99,14, 91,18, 97,23, 88,26, 94,32, 84,34, 89,40, 78,41, 82,47, 70,46, 63,48, 64,56, 72,60, 76,68, 69,66, 66,70, 61,64, 58,70, 64,80, 70,88, 60,86, 56,92, 50,88] },
  fleur: { sym: [50,3, 55,10, 58,20, 57,31, 54,44, 58,44, 60,34, 66,24, 75,20, 85,22, 91,30, 89,40, 83,45, 84,37, 80,31, 73,31, 67,36, 64,44, 72,44, 72,53, 58,53, 62,62, 70,70, 77,72, 68,77, 59,74, 54,66, 50,72] },
  castle: { sym: [50,12, 52.5,12, 52.5,18, 57,18, 57,12, 62,12, 62,40, 68,40, 68,26, 72,26, 72,31, 75,31, 75,26, 79,26, 79,31, 82,31, 82,26, 86,26, 86,92, 50,92],
            more: [[44,92, 44,76, 50,70, 56,76, 56,92], [47,24, 53,24, 53,34, 47,34]], eo: true },
  tower: { sym: [50,8, 54,8, 54,16, 62,16, 62,8, 70,8, 70,92, 50,92], more: [[44,92, 44,74, 50,68, 56,74, 56,92]], eo: true },
  crown: { sym: [50,18, 57,46, 68,26, 72,50, 86,32, 82,66, 82,80, 50,80] },
  tree: { sym: [50,4, 64,26, 57,26, 72,46, 62,46, 80,68, 56,68, 56,94, 50,94] },
  maple: { sym: [50,4, 57,17, 64,14, 61,38, 72,27, 75,33, 87,30, 83,43, 89,46, 70,61, 73,68, 53,65, 54,92, 50,92] },
  bird: { sym: [50,34, 54,38, 70,30, 92,24, 80,40, 62,50, 56,54, 54,66, 50,70] },
  trident: { sym: [50,8, 56,22, 53,22, 53,58, 63,58, 64,22, 71,30, 70,60, 64,66, 53,66, 53,92, 50,92] },
  horse: { polys: [[18,24, 25,15, 31,11, 35,5, 38,12, 45,17, 53,27, 61,35, 75,36, 85,41, 91,49, 95,63, 89,59, 85,53, 82,61, 80,72, 84,86, 88,94, 80,94, 76,84, 70,72, 66,67, 58,70, 52,78, 54,90, 48,94, 46,84, 44,72, 42,61, 39,53, 34,47, 29,41, 21,41, 14,45, 10,41, 18,35, 26,33, 22,29, 15,29]] },
  shieldform: { sym: [50,4, 92,4, 92,50, 88,70, 70,88, 50,96] },
  lion: { polys: [[80.9,2, 82.4,3.7, 81.6,6.6, 85.2,11.2, 88.3,11.1, 90,9.6, 88.8,12.8, 86.9,13.7, 85.9,16.9, 87.1,19, 88.7,19.6, 86.3,20.8, 83.6,18.9, 82.3,21.7, 82.9,25.1, 78.6,24.3, 76.9,21.2, 77.5,17.9, 76.8,13.7, 78,9.5, 76.7,8.2, 74.4,8.9, 71.7,12, 70.4,15.2, 70.3,19.4, 72.1,24.4, 84.2,38.3, 85.7,42.7, 85.7,49.2, 83.4,55.9, 79.7,59.7, 74.9,61.1, 66.4,59.9, 66.4,64.8, 67.2,65.8, 68.8,66.5, 71.2,66.3, 75.3,63.1, 75.8,66, 78.5,66.8, 77.1,68.2, 77.2,69.5, 78.5,70.6, 80.5,71.1, 79.6,72.3, 77,72.9, 79.3,73.8, 78.6,75, 76.4,76.1, 79.2,77.8, 75.9,79.6, 77.8,80.9, 73.5,82.6, 76.6,84.3, 74.2,85.5, 71.8,85.7, 72,87.9, 74,89.7, 73.2,93.7, 71.2,95.4, 71.4,92.8, 69.4,91.9, 69.3,89.2, 68.5,88.8, 66.9,90.9, 66.7,94, 65.1,94.9, 65,97.9, 63.3,96.4, 62.6,93.4, 61.7,93.9, 61.2,95.8, 60,94.3, 60.2,91.3, 61.1,89.2, 59.7,89.5, 58.2,91.1, 58.1,89.2, 61.3,85.1, 64.9,85.4, 66.1,84.6, 68.5,80.7, 68.3,77.7, 67.6,75.7, 63.8,78.3, 60.3,76.9, 60.5,79.1, 62.9,80.8, 60.9,81.6, 58.5,80.4, 58.5,83.4, 57.3,82.6, 56,79.4, 55.1,82.5, 54.4,80.8, 54.6,78.2, 55.9,76.3, 58.2,74.9, 55.3,67.1, 52.9,67, 50.6,68, 48.3,71.9, 48.7,75.1, 50.5,76.4, 54,75.9, 53.3,77.8, 52,78.7, 49.2,78.6, 47,81.1, 45.4,78.7, 44.3,82.2, 41.2,78.5, 40.1,81, 37,77.4, 36.2,77.8, 35.9,79.5, 35.2,79.3, 33.3,75.9, 32.2,75.4, 31.1,78.5, 28.6,80.1, 28,82.7, 26.7,80.8, 26.6,77.1, 27.7,75.8, 29.5,75.3, 29.8,74.5, 25.2,75.8, 24.2,75.5, 24,74.5, 23.1,74.5, 20.7,75.9, 21.7,73, 24.1,71.7, 23.2,71.1, 21.7,71.7, 22.2,70.1, 25,67.9, 22.8,67.3, 25,65.8, 29.2,66.2, 30.2,69.1, 33.4,71.4, 42.7,71.7, 41.1,65.6, 37.6,66.1, 38.1,64.4, 35.6,65.8, 32.4,65, 35.2,64, 36.6,62.3, 33,60.7, 31.5,56.9, 36.3,59.6, 36.1,56.6, 38.5,54.2, 39,54.5, 38.3,57.6, 40.7,59.1, 47.6,55.4, 50,55.6, 52,56.8, 56.1,56.9, 56.2,56.3, 55.1,53.8, 49.8,52.9, 44.9,48.4, 42.1,51.3, 41.9,49.1, 41,49.8, 41.2,50.7, 38.1,49.7, 39.2,51.1, 35.6,50.1, 35.7,52.3, 33.4,51, 34.5,53.3, 30.8,51.3, 30.8,53.2, 28.9,52.1, 28,54, 27.5,52.7, 26.8,54.5, 25.9,53.7, 23.1,57.6, 22.9,52.8, 22,52.3, 20.8,53.8, 20.1,58.4, 18.5,59.3, 18.4,62.2, 16.6,60.5, 16.3,56.6, 18.3,54.1, 18.5,52.8, 16.6,53.5, 14,56, 12.7,56, 10.8,58.7, 10.2,55.7, 11,52.9, 15.7,51.1, 13.4,50.4, 12.8,49.5, 9.9,50.4, 11.5,47.7, 14.4,46.2, 18.2,48.5, 21.7,48, 34.9,39.1, 32.6,34.4, 31.3,36.4, 31,32.3, 29.7,34, 30.2,29.2, 28.7,31.2, 28.3,30.5, 28.6,26.5, 27.9,27.3, 27.6,26.9, 27.7,22.2, 27,24, 24.9,18.2, 22.6,17.1, 20.2,19, 16.9,18.3, 15.5,17, 15.1,15.9, 18.5,16.3, 19.4,14.8, 21.4,14.5, 21.7,13.2, 20.8,12.4, 18.7,12.6, 17.6,11.2, 14.2,11.6, 15.8,9.3, 19.7,8.1, 17,6.8, 18,5.8, 20.4,5.3, 24,6.9, 23.8,5.2, 22.5,3.6, 24.9,3.9, 27.4,7.5, 27.2,12.3, 33.7,18.4, 38.2,26.7, 43.4,30.5, 47.4,28.9, 51,28.5, 51.7,26.8, 43.7,27.3, 44.2,23.3, 45.4,24, 46.1,22.3, 40.5,21.5, 39.1,18.5, 39.6,16.1, 41.1,15.2, 41.4,18.5, 42.9,19.6, 45.8,20.2, 45.3,18.8, 43.4,18.2, 43.1,13.2, 50.2,10.6, 53.1,10.4, 55.2,7.6, 56,8, 56.3,10.3, 59.2,12.3, 59.9,14.3, 62.8,13.2, 63.1,14.5, 61.7,16.1, 63.3,20.9, 64.3,21.8, 65.8,21.7, 63.3,23.9, 63.4,26.1, 64.8,28, 66.8,28.2, 65.2,29.7, 63.2,30, 63.2,34.1, 65.8,34.7, 62.1,36.3, 62.7,38.1, 64.4,39.2, 61.7,40.6, 59.3,38.5, 59.4,40.3, 67.7,54.3, 70.6,56.8, 74.3,57.6, 77.9,56.3, 80.4,53.8, 81.7,50.6, 81.3,47.8, 78.3,44.9, 75.3,44.9, 74.6,46.5, 76.6,48.7, 73.7,49.6, 71.3,47.7, 70.4,49.3, 71.1,53.8, 68.1,50.4, 68.2,47.8, 69.4,45.3, 67.5,43.7, 67.4,40.7, 69.1,42.6, 71.3,43.3, 73.2,41.3, 72.6,39.3, 72.9,36.9, 75.7,35.1, 74.8,37.6, 75.3,39.8, 81,43, 81.3,42.4, 78.1,35.6, 69.1,26.3, 67.1,21.2, 66.9,16.4, 67.7,12.8, 69.8,9.2, 72.9,6.8, 79.2,5.2, 80.6,3.8],
                  [19.7,8.9, 23.8,12.1, 20.9,9.2],
                  [49.6,12.5, 48,14, 50.5,14.8, 51.4,13.2],
                  [81,12.9, 77.8,16.3, 78.3,18.1, 81.6,13.3],
                  [48.3,18.5, 46.4,18.8, 46.4,20.3, 50.3,20.4, 50.4,18.5],
                  [79.5,19.3, 79.2,23.4, 80.4,23.5, 80,19.4],
                  [46.5,22.3, 46.8,24.4, 49.3,24.2, 50.8,22.8, 50.7,22.3],
                  [48.8,30.3, 45.3,31.2, 40.5,34.3, 38.5,33.9, 36.9,32.7, 42.8,31.2, 35.7,31.8, 37.2,33.9, 39.5,34.8, 35.7,38.2, 35.4,40, 42.1,36.3, 39,39.4, 39.7,39.6, 41.9,39.2, 45.8,36.8, 43.7,41, 45.5,41.8, 47.5,40.6, 45.3,44.3, 48.3,43.8, 51,39.7, 50.1,44.2, 52.2,43.7, 54,40.4, 54.9,43.3, 56.3,44.5, 57.6,44.2, 56.6,41.5, 58.5,43.4, 60.5,43.6, 57.4,41.6, 55.5,37.7, 55,38, 56.7,43.7, 55.6,43.3, 54.3,37, 53.6,36.6, 52.5,42.5, 50.9,43.4, 51.7,39.2, 51.2,37.2, 48.9,42.4, 46.4,43.8, 49,38.9, 48.4,38.5, 46.2,40.8, 44.5,41, 46,38.8, 46.5,35.4, 40.8,38.8, 43.7,35.3, 43.6,34.4, 35.9,39.3, 38,36.7, 44.3,32.4, 49.9,30.9, 49.9,30.3],
                  [58.8,34.1, 58.5,37.7, 59.7,37.8],
                  [56.3,57.6, 54.9,64.2, 55.2,66.4, 55.7,66.4, 55.5,64.3, 56.8,58.8],
                  [27.9,67, 27.3,68.1, 25.8,67.5, 25.8,68.6, 30.3,72.3, 30.5,71.8, 27.2,68.8, 28.3,67.8],
                  [72.5,67.7, 69.1,69.6, 71.9,69.1, 72,71.5, 72.5,71.6],
                  [58.9,67.9, 58.5,68.2, 59.6,69.8, 62.6,70.9],
                  [25.2,68.9, 25,71.4, 29.8,73.1, 25.3,70.8],
                  [66.6,87.8, 62.4,92.2, 61.5,91.3, 61,91.7, 63,92.6, 67,88.3]], eo: true },
  dragon: { polys: [[6,40, 14,33, 22,31, 26,24, 31,30, 36,38, 44,45, 56,45, 62,41, 63,30, 58,18, 69,23, 77,12, 80,25, 89,22, 84,35, 93,37, 82,46, 70,50, 75,54, 86,51, 95,44, 97,51, 88,58, 76,62, 72,66, 75,76, 82,80, 70,83, 65,72, 58,68, 53,70, 51,80, 57,85, 45,87, 43,72, 37,65, 31,58, 29,51, 22,46, 15,47, 7,45]] },
  bear: { polys: [[30,10, 38,8, 42,12, 46,18, 54,22, 62,30, 66,42, 66,56, 70,64, 72,78, 76,90, 66,92, 62,80, 58,72, 52,74, 48,86, 52,92, 40,92, 42,78, 40,64, 38,54, 32,50, 26,52, 20,48, 26,44, 32,40, 28,34, 22,32, 18,26, 22,22, 26,16]] },
  harp: { polys: [[22,8, 34,5, 50,12, 66,10, 80,3, 85,12, 72,24, 62,41, 52,59, 42,77, 35,95, 21,95, 25,60, 24,30], [33,21, 35,82, 43,65, 53,47, 63,29, 49,23]], eo: true },
};
for (const s of Object.values(SIL)) if (s.sym) {
  const h = s.sym, pts = [];
  for (let i = 0; i < h.length; i += 2) pts.push(h[i], h[i + 1]);
  for (let i = h.length - 4; i >= 2; i -= 2) pts.push(100 - h[i], h[i + 1]);
  s.polys = [pts, ...(s.more || [])];
}

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
  triangle: { size: 0.5 }, poly: {}, script: { size: [0.55, 0.22] }, triskele: { size: 0.7 }, trigram: { size: 0.25 }, ...Object.fromEntries(Object.keys(SIL).map((k) => [k, { size: 0.6 }])),
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
      case "lozengy": {                                           // (diamonds of b on a, r rows and c columns: Bavaria)
        want(4, 2); const r = Math.round(A[0]), c = Math.round(A[1]), o = node(A[2], R), dw = w / c, dh = h / r, ps = [];
        for (let i = 0; i < r; i++) for (let j = 0; j < c; j++) { const px = x + (j + 0.5) * dw, py = y + (i + 0.5) * dh;   // (tip to tip: a shows between)
          ps.push([[px, py - dh / 2], [px + dw / 2, py], [px, py + dh / 2], [px - dw / 2, py]]); }
        return [...o, ...piece(A[3], R, null, ps)];
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
    const o = shapeOps(ch, R);
    if (!ch.mods.outline) return o;
    const w = (ch.mods.w ?? 0.03) * R.h;
    return o.map((q) => q.fill ? { stroke: q.fill, width: w, d: q.d, join: "miter" } : q);
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
      case "ref": {                                                  // (a motif: its charges in a box of its ratio, size 1 -- the field's height -- unless given)
        const d = resolve(ch.sub.name, ch.sub.at);
        if (!d.motif) break;
        const z = m.size ?? 1, [w, h] = Array.isArray(z) ? [z[0] * R.w, z[1] * R.h] : [z * R.h / d.ratio, z * R.h];
        const was = given; given = { colors: ch.colors.length ? ch.colors : given.colors, points: m.points || given.points };
        try { return node(ch.sub, sub(R, cx - w / 2, cy - h / 2, w, h)); } finally { given = was; }
      }
    }
    switch (ch.shape) {
      case "box": case "shield": case "circle": case "ref": {
        let shape = ch.shape === "box" ? "rect" : ch.shape === "circle" ? "round" : ch.shape, w = sw, h = sh;
        if (ch.shape === "ref") { const d = resolve(ch.sub.name, ch.sub.at); shape = d.shape; if (!Array.isArray(size)) w = sh / d.ratio; }
        else if (ch.shape === "shield" && !Array.isArray(size)) w = sh / 1.2;
        const S = sub(R, cx - w / 2, cy - h / 2, w, h, shape);
        const o = [{ clip: S.outline, ops: node(ch.sub, S) }];      // (a shield or arms gets a fine line round it)
        if (shape === "shield") o.push({ stroke: "#00000033", width: Math.max(0.3, h * 0.012), d: S.outline });
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
      case "poly": return [fillP(ch.rings.map((q) => q.map(([u, v]) => [R.x + u * R.w, R.y + v * R.h])), c0, true)];
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
    const S = SIL[ch.shape];
    if (S) return [fillP(S.polys.map((p) => { const q = []; for (let i = 0; i < p.length; i += 2) q.push([p[i] / 100 - 0.5, p[i + 1] / 100 - 0.5]); return place(q); }), c0, S.eo)];
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
    if (o.fill) return `<path d="${o.d}" fill="${o.fill}"${o.eo ? ' fill-rule="evenodd"' : ""}/>`;
    return `<path d="${o.d}" fill="none" stroke="${o.stroke}" stroke-width="${f2(o.width)}"${o.join ? ` stroke-linejoin="${o.join}"` : ""}/>`;
  }).join("");
  body.push(walk(ops));
  const w = opts.width ?? (opts.height ? opts.height * W / H : W), h = opts.height ?? (opts.width ? opts.width * H / W : H);
  const title = opts.title ? `<title>${String(opts.title).replace(/[<&]/g, (c) => c === "<" ? "&lt;" : "&amp;")}</title>` : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f2(W)} ${f2(H)}" width="${f2(w)}" height="${f2(h)}"${opts.cls ? ` class="${opts.cls}"` : ""}>${title}<defs>${defs.join("")}</defs>${body.join("")}</svg>`;
}
function toCanvas(ctx, ops) {
  for (const o of ops) {
    if (o.clip) { ctx.save(); ctx.clip(new Path2D(o.clip)); toCanvas(ctx, o.ops); ctx.restore(); }
    else if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(new Path2D(o.d), o.eo ? "evenodd" : "nonzero"); }
    else { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.width; ctx.lineJoin = o.join || "miter"; ctx.lineCap = "butt"; ctx.stroke(new Path2D(o.d)); }
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
function library(text = "") {
  const defs = new Map(), src = new Map(), names = new Map(), errors = [], cache = new Map();
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
    try { defs.set(m[1], parse(m[3])); } catch (e) { errors.push({ line: r.line, code: m[1], msg: e.message }); }
  }
  const lib = {
    codes: [...defs.keys()], errors, names,
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
  COLORS, FlagError, parse, library,
  charges: Object.keys(CHARGES), divisions: [...DIVISIONS],
  svg: (text, opts = {}, lib = library()) => lib.render(parse(text), opts),
  draw: (ctx, text, x, y, w, h, opts = {}, lib = library()) => lib.paint(ctx, parse(text), x, y, w, h, opts),
};
root.Flags = Flags;
if (typeof module === "object" && module.exports) module.exports = Flags;
})(typeof self !== "undefined" ? self : this);
