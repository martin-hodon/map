// wasm.js -- the geometry core in WebAssembly (wasm/: Rust, built to js/mapgeo.wasm): the lines and rows a file read are
// handed to the module too, rows are traced into canvas commands there (d3's projection pipeline ported: rotate, clip,
// resample, the Mercator extent) and the R-trees live there. Loaded unless ?wasm=0 or the file is missing: then the page
// runs in JS as before (geom.js trace, view.js tree) -- one interface either way, the same pixels (wasm/check compares).
import { ctx } from "./state.js";
import { Painter } from "./paint.js";

export let W = null;                                                // (the module's exports, when it runs)
export let painter = null;                                          // (the workers painting frames in parallel: paint.js)
export let projParams = null;                                       // (the projection's numbers, as handed to the module and the workers)
let scratch = { ptr: 0, bytes: 0 };
export const wasmWanted = () => new URLSearchParams(location.search).get("wasm") !== "0";
// how many painters: ?workers=N, or one fewer than the cores, up to four (fewer than two: the one thread paints)
export const workersWanted = () => { const q = new URLSearchParams(location.search).get("workers"); return q != null ? +q : Math.min(4, (navigator.hardwareConcurrency || 2) - 1); };
export async function loadWasm() {
  if (!wasmWanted() || typeof WebAssembly === "undefined") return false;
  try {
    const r = await fetch("js/mapgeo.wasm", { cache: "no-cache" });
    if (!r.ok) throw new Error(`${r.status}`);
    const module = await WebAssembly.compile(await r.arrayBuffer()), instance = await WebAssembly.instantiate(module, {});
    W = instance.exports;
    const n = workersWanted();
    if (n >= 2 && typeof Worker !== "undefined" && typeof OffscreenCanvas !== "undefined") painter = new Painter(module, n);
    return true;
  } catch (e) { console.warn("mapgeo.wasm not loaded, the JS geometry is used:", e.message); W = null; return false; }
}
// a buffer of the module's, filled from a typed array (a view is taken after the alloc: the memory may have grown)
const give = (arr) => { const bytes = arr.byteLength, ptr = W.alloc(bytes); new Uint8Array(W.memory.buffer, ptr, bytes).set(new Uint8Array(arr.buffer, arr.byteOffset, bytes)); return [ptr, bytes]; };
const scratchFor = (arr) => {                                       // (one buffer reused for the ids and boxes handed in)
  if (scratch.bytes < arr.byteLength) { if (scratch.bytes) W.dealloc(scratch.ptr, scratch.bytes); scratch = { ptr: W.alloc(arr.byteLength * 2), bytes: arr.byteLength * 2 }; }
  new Uint8Array(W.memory.buffer, scratch.ptr, arr.byteLength).set(new Uint8Array(arr.buffer, arr.byteOffset, arr.byteLength));
  return scratch.ptr;
};
// ---- the data: a file's lines (T) and each object's rows (g) ------------------------------------------------------
export function attachLines(T) { if (!W || T.wid) return; T.wid = W.lines_new(...give(T.xy), ...give(T.at)); T.wrefs = 0; }
export function attachRows(T, g, kind) {
  if (!W || g.wid) return;
  attachLines(T);
  g.wid = W.rows_new(T.wid, ...give(g.start), ...give(g.refs), kind === "polygon" ? 1 : 0); g.wT = T; T.wrefs++;
  painter?.rows(T, g, kind === "polygon" ? 1 : 0);
}
export function releaseRows(g) {                                    // (the lines go with the last of their objects)
  if (!W || !g.wid) return;
  W.rows_free(g.wid); g.wid = 0;
  const last = --g.wT.wrefs === 0;
  if (last) { W.lines_free(g.wT.wid); g.wT.wid = 0; }
  painter?.free([g.pid], last ? [g.wT.pid] : []); g.pid = 0; if (last) g.wT.pid = 0;
  g.wT = null;
}
// ---- the projection, as geom.js setup made it --------------------------------------------------------------------
export function setProj(proj, kind) {
  if (!W) return;
  const r = proj.rotate(), t = proj.translate(), ca = proj.clipAngle ? proj.clipAngle() : null, ce = proj.clipExtent();
  projParams = [kind, r[0], r[1], r[2] ?? 0, proj.scale(), t[0], t[1], ca ?? 0, ce ? 1 : 0, ...(ce ? [ce[0][0], ce[0][1], ce[1][0], ce[1][1]] : [0, 0, 0, 0]), 0.25];
  W.proj_set(...projParams);
}
// ---- rows traced into the canvas path ------------------------------------------------------------------------------
function replay(n) {
  const o = new Float32Array(W.memory.buffer, W.out_ptr(), n);
  for (let k = 0; k < n; k += 3) { const c = o[k]; if (c === 1) ctx.lineTo(o[k + 1], o[k + 2]); else if (c === 0) ctx.moveTo(o[k + 1], o[k + 2]); else ctx.closePath(); }
}
export function traceRows(g, ids) { const a = ids instanceof Int32Array ? ids : Int32Array.from(ids); replay(W.trace_rows(g.wid, scratchFor(a), a.length)); }
export function traceArcsOf(T, arcs) { const a = Int32Array.from(arcs); replay(W.trace_arcs(T.wid, scratchFor(a), a.length)); }
// ---- the R-trees ---------------------------------------------------------------------------------------------------
export const treeOfRows = (g, n) => ({ wid: W.tree_new(g.wid, n) });
export function treeOfPoints(xy) { const a = Float64Array.from(xy), ptr = scratchFor(a), t = { wid: W.ptree_new(ptr, a.length / 2) }; return t; }
export function freeTree(t) { if (W && t?.wid) { W.tree_free(t.wid); t.wid = 0; } }
export function queryTree(t, boxes) {
  const b = new Float64Array(boxes.length * 4); boxes.forEach((q, i) => b.set(q, 4 * i));
  const n = W.tree_query(t.wid, scratchFor(b), boxes.length);
  return Array.from(new Int32Array(W.memory.buffer, W.ids_ptr(), n));
}
