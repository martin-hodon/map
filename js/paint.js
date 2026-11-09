// paint.js -- the frame painted in parallel: a few workers (worker.js), each with the geometry core and the lines,
// paint contiguous chunks of the frame's operations onto bitmaps, and the main thread stacks them in order, running
// between them what is drawn here (d3's sphere, a selection's GeoJSON, a clip). One frame is in flight at a time; a
// newer one asked for meanwhile waits, and only the newest of those is painted (the moving map keeps up, late frames
// are dropped). The painted pixels are the same as the one-thread draw's: source-over stacking is associative, and an
// opaque fill painted in two halves is the fill.
export class Painter {
  constructor(module, n) {
    this.n = n; this.lids = 0; this.pids = 0; this.frames = 0; this.inFlight = null; this.pending = null;
    this.workers = Array.from({ length: n }, () => { const w = new Worker("js/worker.js"); w.postMessage({ t: "init", module }); w.onmessage = (e) => this.got(e.data); return w; });
  }
  post(m) { for (const w of this.workers) w.postMessage(m); }
  lines(T) { if (T.pid) return; T.pid = ++this.lids; this.post({ t: "lines", lid: T.pid, xy: T.xy, at: T.at }); }
  rows(T, g, polygon) { if (g.pid) return; this.lines(T); g.pid = ++this.pids; g.pT = T; this.post({ t: "rows", pid: g.pid, lid: T.pid, start: g.start, refs: g.refs, polygon }); }
  free(pids, lids) { if (pids.length || lids.length) this.post({ t: "free", pids, lids }); }
  // a frame: { proj, W, H, dpr, ops, done(frame) } -- an op { main: fn } runs here, any other { pid|lid, items (rows, or arcs with lid), costs (of each), cost, fill, color, width, alpha, dash }
  paint(frame) { if (this.inFlight) this.pending = frame; else this.start(frame); }
  start(frame) {
    frame.id = ++this.frames; this.inFlight = frame;
    Object.assign(frame, partition(frame.ops, this.n));
    frame.waiting = frame.chunks.length;
    frame.chunks.forEach((c, k) => this.workers[k % this.n].postMessage({ t: "paint", frame: frame.id, chunk: k, proj: frame.proj, W: frame.W, H: frame.H, dpr: frame.dpr,
      ops: c.ops.map((o) => ({ pid: o.pid, lid: o.lid, [o.lid ? "arcs" : "rows"]: o.items, fill: o.fill, color: o.color, width: o.width, alpha: o.alpha, dash: o.dash })) }));
    if (!frame.waiting) this.finish(frame);
  }
  got(m) {
    if (m.t !== "bitmap") return;
    const f = this.inFlight;
    if (!f || m.frame !== f.id) { m.bitmap.close(); return; }
    f.chunks[m.chunk].bitmap = m.bitmap; f.chunks[m.chunk].ms = m.ms; f.chunks[m.chunk].paint = m.paint;
    if (f.waiting === 1) f.tAll = performance.now();
    if (--f.waiting === 0) this.finish(f);
  }
  finish(f) { this.inFlight = null; f.done(f); const p = this.pending; this.pending = null; if (p) this.start(p); }
}
// the operations cut into about n contiguous chunks of equal weight (points to project); a main-thread step is a cut of
// its own; an op too big for the room left is split (an opaque fill or stroke by rows, arcs always: two halves paint the
// same, but for the rows of one translucent fill, which may overlap)
export function partition(ops, n) {
  const total = ops.reduce((s, o) => s + (o.main ? 0 : o.cost), 0), target = total / n;
  const seq = [], chunks = []; let cur = null;
  const open = () => (cur ??= { ops: [], cost: 0 }), close = () => { if (cur) { seq.push({ chunk: chunks.length }); chunks.push(cur); cur = null; } };
  for (const o of ops) {
    if (o.main) { close(); seq.push({ main: o.main }); continue; }
    let op = o;
    for (;;) {
      open(); const room = target - cur.cost;
      if (op.cost <= room || chunks.length >= n - 1) { cur.ops.push(op); cur.cost += op.cost; break; }   // (the last chunk takes the rest)
      if ((op.alpha === 1 || op.lid) && op.items.length > 1 && room > target * 0.05) {
        let k = 0, c = 0; while (k < op.items.length && c + op.costs[k] <= room) c += op.costs[k++];
        if (k > 0 && k < op.items.length) { cur.ops.push({ ...op, items: op.items.slice(0, k), cost: c }); cur.cost += c; close(); op = { ...op, items: op.items.slice(k), costs: op.costs.slice(k), cost: op.cost - c }; continue; }
      }
      if (cur.ops.length) { close(); continue; }
      cur.ops.push(op); cur.cost += op.cost; close(); break;         // (bigger than a chunk: one of its own)
    }
  }
  close();
  return { seq, chunks };
}
