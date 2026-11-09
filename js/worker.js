// worker.js -- a painter (paint.js starts a few): its own copy of the geometry core (mapgeo.wasm) and of the lines the
// main thread has, painting the chunk of a frame's operations it is given onto an OffscreenCanvas, the bitmap sent back.
let W, scratch = { ptr: 0, bytes: 0 }, canvas, ctx, ready, projKey = "";
const lines = new Map(), rows = new Map();                          // (the main thread's ids -> the module's)
const give = (arr) => { const bytes = arr.byteLength, ptr = W.alloc(bytes); new Uint8Array(W.memory.buffer, ptr, bytes).set(new Uint8Array(arr.buffer, arr.byteOffset, bytes)); return [ptr, bytes]; };
const scratchFor = (arr) => {
  if (scratch.bytes < arr.byteLength) { if (scratch.bytes) W.dealloc(scratch.ptr, scratch.bytes); scratch = { ptr: W.alloc(arr.byteLength * 2), bytes: arr.byteLength * 2 }; }
  new Uint8Array(W.memory.buffer, scratch.ptr, arr.byteLength).set(new Uint8Array(arr.buffer, arr.byteOffset, arr.byteLength));
  return scratch.ptr;
};
function replay(n) {
  const o = new Float32Array(W.memory.buffer, W.out_ptr(), n);
  for (let k = 0; k < n; k += 3) { const c = o[k]; if (c === 1) ctx.lineTo(o[k + 1], o[k + 2]); else if (c === 0) ctx.moveTo(o[k + 1], o[k + 2]); else ctx.closePath(); }
}
function paint(m) {
  const t0 = performance.now();
  if (canvas.width !== m.W * m.dpr || canvas.height !== m.H * m.dpr) { canvas.width = m.W * m.dpr; canvas.height = m.H * m.dpr; }
  ctx.setTransform(m.dpr, 0, 0, m.dpr, 0, 0); ctx.clearRect(0, 0, m.W, m.H); ctx.lineJoin = "miter";
  const key = m.proj.join(","); if (key !== projKey) { W.proj_set(...m.proj); projKey = key; }
  for (const op of m.ops) {
    ctx.beginPath();
    if (op.arcs) replay(W.trace_arcs(lines.get(op.lid), scratchFor(op.arcs), op.arcs.length));
    else replay(W.trace_rows(rows.get(op.pid), scratchFor(op.rows), op.rows.length));
    ctx.globalAlpha = op.alpha; ctx.setLineDash(op.dash);
    if (op.fill) { ctx.fillStyle = op.color; ctx.fill(); } else { ctx.strokeStyle = op.color; ctx.lineWidth = op.width; ctx.stroke(); }
  }
  const t1 = performance.now(), bitmap = canvas.transferToImageBitmap();
  postMessage({ t: "bitmap", frame: m.frame, chunk: m.chunk, bitmap, paint: t1 - t0, ms: performance.now() - t0 }, [bitmap]);
}
onmessage = async (e) => {
  const m = e.data;
  if (m.t === "init") { ready = WebAssembly.instantiate(m.module, {}).then((inst) => { W = inst.exports; canvas = new OffscreenCanvas(1, 1); ctx = canvas.getContext("2d"); }); return; }
  await ready;                                                      // (in the order they came)
  if (m.t === "lines") lines.set(m.lid, W.lines_new(...give(m.xy), ...give(m.at)));
  else if (m.t === "rows") rows.set(m.pid, W.rows_new(lines.get(m.lid), ...give(m.start), ...give(m.refs), m.polygon));
  else if (m.t === "free") { for (const p of m.pids) if (rows.has(p)) { W.rows_free(rows.get(p)); rows.delete(p); } for (const l of m.lids) if (lines.has(l)) { W.lines_free(lines.get(l)); lines.delete(l); } }
  else if (m.t === "paint") paint(m);
};
