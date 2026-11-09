// wasmcheck.mjs -- the built module's interface (lib.rs) from node, over the check's fixtures: node wasmcheck.mjs fixtures/s1 ...
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url));
const { instance } = await WebAssembly.instantiate(fs.readFileSync(path.join(here, "../js/mapgeo.wasm")), {});
const W = instance.exports;
const give = (arr) => { const bytes = arr.byteLength, ptr = W.alloc(bytes); new Uint8Array(W.memory.buffer, ptr, bytes).set(new Uint8Array(arr.buffer, arr.byteOffset, bytes)); return [ptr, bytes]; };
let fail = 0;
for (const dir of process.argv.slice(2)) {
  const rd = (n, C) => { const b = fs.readFileSync(path.join(dir, n)); return new C(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
  const xy = rd("xy.f32", Float32Array), at = rd("at.i32", Int32Array), start = rd("start.i32", Int32Array), refs = rd("refs.i32", Int32Array), ids = rd("ids.i32", Int32Array), want = rd("expected.f32", Float32Array);
  const p = fs.readFileSync(path.join(dir, "params.txt"), "utf8").trim().split(" ").map(Number);
  const lines = W.lines_new(...give(xy), ...give(at)), rows = W.rows_new(lines, ...give(start), ...give(refs), p[14]);
  W.proj_set(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12], p[13]);
  const [ip] = give(ids);
  const t0 = performance.now(); const n = W.trace_rows(rows, ip, ids.length); const ms = performance.now() - t0;
  const got = new Float32Array(W.memory.buffer, W.out_ptr(), n);
  let bad = 0; for (let k = 0; k < Math.min(n, want.length); k++) if (got[k] !== want[k]) bad++;
  const tree = W.tree_new(rows, start.length - 1), [bp] = give(Float64Array.from([-10, 35, 30, 60, 170, -50, 180, -40]));
  const nq = W.tree_query(tree, bp, 2), hits = Array.from(new Int32Array(W.memory.buffer, W.ids_ptr(), nq));
  console.log(`${dir}: ${n} vs ${want.length} floats, ${bad} differ, wasm ${ms.toFixed(1)} ms; tree: ${nq} rows in two boxes (${hits.slice(0, 6)}...)`);
  if (n !== want.length || bad) fail = 1;
  W.tree_free(tree); W.rows_free(rows); W.lines_free(lines);
}

// the tree against the boxes view.js tree() makes, brute force
{
  const dir = process.argv[2], RING = 0x7fffffff, POLY = 0x7ffffffe;
  const rd = (n, C) => { const b = fs.readFileSync(path.join(dir, n)); return new C(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); };
  const xy = rd("xy.f32", Float32Array), at = rd("at.i32", Int32Array), start = rd("start.i32", Int32Array), refs = rd("refs.i32", Int32Array);
  const polygon = fs.readFileSync(path.join(dir, "params.txt"), "utf8").trim().split(" ").map(Number)[14];
  const items = [];
  for (let i = 0; i < start.length - 1; i++) { let w = 999, s = 999, e = -999, n = -999;
    for (let j = start[i]; j < start[i + 1]; j++) { const a = refs[j];
      if (a === RING) { if (!polygon) { items.push([w, s, e, n, i]); w = s = 999; e = n = -999; } continue; }
      if (a === POLY) { if (e - w >= 359) { if (s + n > 0) n = 90; else s = -90; } items.push([w, s, e, n, i]); w = s = 999; e = n = -999; continue; }
      const r = a < 0 ? ~a : a; for (let k = 2 * at[r], x = 2 * at[r + 1]; k < x; k += 2) { const u = xy[k], v = xy[k + 1]; if (u < w) w = u; if (u > e) e = u; if (v < s) s = v; if (v > n) n = v; } } }
  const lines = W.lines_new(...give(xy), ...give(at)), rows = W.rows_new(lines, ...give(start), ...give(refs), polygon), tree = W.tree_new(rows, start.length - 1);
  let bad = 0, total = 0;
  for (let t = 0; t < 200; t++) {
    const boxes = Array.from({ length: 1 + (t % 3) }, () => { const w = -180 + Math.random() * 300, s = -90 + Math.random() * 150; return [w, s, w + Math.random() * 60, s + Math.random() * 40]; });
    const want = [...new Set(items.filter(([w, s, e, n]) => boxes.some(([bw, bs, be, bn]) => bw <= e && be >= w && bs <= n && bn >= s)).map((it) => it[4]))].sort((a, b) => a - b);
    const [bp] = give(Float64Array.from(boxes.flat())), nq = W.tree_query(tree, bp, boxes.length), got = Array.from(new Int32Array(W.memory.buffer, W.ids_ptr(), nq));
    total += want.length; if (got.join() !== want.join()) bad++;
  }
  console.log(`tree queries: ${bad} of 200 differ from brute force (${total} rows found)`); if (bad) process.exit(1);
}
process.exit(fail);
