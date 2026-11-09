//! mapgeo: the map's geometry core for WebAssembly -- the lines a file read (lite.rs or the page's parseLite) kept here,
//! rows traced through the projection into canvas commands, pieces found by their boxes. A plain C-style interface, no
//! bindgen: the page allocates with `alloc`, writes the typed arrays, hands them over (owned here from then on), and reads
//! results from `out_ptr()`/`ids_ptr()` as views on the module's memory.
pub mod math;
pub mod rotation;
pub mod projections;
pub mod stream;
pub mod clip;
pub mod trace;
pub mod rtree;
pub mod pipeline;

use pipeline::{Proj, Setup};
use projections::Kind;
use rtree::{Bx, Tree};
use std::alloc::{alloc as sys_alloc, dealloc as sys_dealloc, Layout};
use std::cell::RefCell;
use std::collections::HashMap;
use trace::{Lines, Rows};

/// a buffer the page filled: ours now
struct Buf { ptr: *mut u8, bytes: usize }
impl Buf {
    fn slice<T>(&self) -> &[T] { if self.bytes == 0 { &[] } else { unsafe { std::slice::from_raw_parts(self.ptr as *const T, self.bytes / std::mem::size_of::<T>()) } } }
}
impl Drop for Buf { fn drop(&mut self) { if self.bytes > 0 { unsafe { sys_dealloc(self.ptr, Layout::from_size_align_unchecked(self.bytes, 8)) } } } }

struct LinesBuf { xy: Buf, at: Buf }
struct RowsBuf { lines: i32, start: Buf, refs: Buf, polygon: bool }

#[derive(Default)]
struct State {
    next: i32,
    lines: HashMap<i32, LinesBuf>, rows: HashMap<i32, RowsBuf>, trees: HashMap<i32, Tree>,
    proj: Option<Proj>, ids: Vec<i32>,
}
thread_local! { static ST: RefCell<State> = RefCell::new(State::default()); }

#[no_mangle]
pub extern "C" fn alloc(bytes: usize) -> *mut u8 { if bytes == 0 { return 8 as *mut u8; } unsafe { sys_alloc(Layout::from_size_align_unchecked(bytes, 8)) } }
#[no_mangle]
pub extern "C" fn dealloc(ptr: *mut u8, bytes: usize) { if bytes > 0 { unsafe { sys_dealloc(ptr, Layout::from_size_align_unchecked(bytes, 8)) } } }

fn fresh(st: &mut State) -> i32 { st.next += 1; st.next }

/// the lines of a file: xy (f32 pairs), at (i32): both buffers from `alloc`, owned from here on
#[no_mangle]
pub extern "C" fn lines_new(xy: *mut u8, xy_bytes: usize, at: *mut u8, at_bytes: usize) -> i32 {
    ST.with(|s| { let mut st = s.borrow_mut(); let id = fresh(&mut st); st.lines.insert(id, LinesBuf { xy: Buf { ptr: xy, bytes: xy_bytes }, at: Buf { ptr: at, bytes: at_bytes } }); id })
}
#[no_mangle]
pub extern "C" fn lines_free(id: i32) { ST.with(|s| { s.borrow_mut().lines.remove(&id); }) }

/// an object's rows over some lines: start and refs (i32) from `alloc`, owned from here on
#[no_mangle]
pub extern "C" fn rows_new(lines: i32, start: *mut u8, start_bytes: usize, refs: *mut u8, refs_bytes: usize, polygon: i32) -> i32 {
    ST.with(|s| { let mut st = s.borrow_mut(); let id = fresh(&mut st);
        st.rows.insert(id, RowsBuf { lines, start: Buf { ptr: start, bytes: start_bytes }, refs: Buf { ptr: refs, bytes: refs_bytes }, polygon: polygon != 0 }); id })
}
#[no_mangle]
pub extern "C" fn rows_free(id: i32) { ST.with(|s| { s.borrow_mut().rows.remove(&id); }) }

/// the projection as the page has it: kind (projections::Kind), rotate (degrees), scale, translate, clip angle (degrees,
/// 0 for the antimeridian cut), an extent (has_extent != 0) for Mercator, precision squared
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn proj_set(kind: i32, lambda: f64, phi: f64, gamma: f64, k: f64, tx: f64, ty: f64, clip_angle: f64, has_extent: i32, x0: f64, y0: f64, x1: f64, y1: f64, delta2: f64) {
    let setup = Setup { kind: Kind::from_i32(kind), rotate: [lambda, phi, gamma], k, tx, ty, clip_angle,
                        extent: if has_extent != 0 { Some([x0, y0, x1, y1]) } else { None }, delta2 };
    ST.with(|s| { s.borrow_mut().proj = Some(Proj::new(&setup)); })
}

fn with_rows<R>(st: &State, rows: i32, f: impl FnOnce(&Lines, &Rows) -> R) -> Option<R> {
    let g = st.rows.get(&rows)?; let l = st.lines.get(&g.lines)?;
    Some(f(&Lines { xy: l.xy.slice(), at: l.at.slice() }, &Rows { start: g.start.slice(), refs: g.refs.slice(), polygon: g.polygon }))
}

/// the rows `ids` (i32, n of them) of `rows` traced: the number of floats written -- (cmd, x, y) triples at `out_ptr()`
#[no_mangle]
pub extern "C" fn trace_rows(rows: i32, ids: *const i32, n: usize) -> usize {
    let ids = unsafe { std::slice::from_raw_parts(ids, n) };
    ST.with(|s| {
        let mut st = s.borrow_mut();
        let Some(mut proj) = st.proj.take() else { return 0 };
        proj.clear();
        with_rows(&st, rows, |t, g| for &i in ids { proj.trace(t, g, i as usize); });
        let n = proj.out.borrow().len();
        st.proj = Some(proj); n
    })
}
/// arcs of `lines`, each a line of its own
#[no_mangle]
pub extern "C" fn trace_arcs(lines: i32, arcs: *const i32, n: usize) -> usize {
    let arcs = unsafe { std::slice::from_raw_parts(arcs, n) };
    ST.with(|s| {
        let mut st = s.borrow_mut();
        let Some(mut proj) = st.proj.take() else { return 0 };
        proj.clear();
        if let Some(l) = st.lines.get(&lines) { proj.trace_arcs(&Lines { xy: l.xy.slice(), at: l.at.slice() }, arcs); }
        let n = proj.out.borrow().len();
        st.proj = Some(proj); n
    })
}
#[no_mangle]
pub extern "C" fn out_ptr() -> *const f32 { ST.with(|s| s.borrow().proj.as_ref().map_or(std::ptr::null(), |p| p.out.borrow().as_ptr())) }

/// a tree of the rows' boxes (n_rows rows)
#[no_mangle]
pub extern "C" fn tree_new(rows: i32, n_rows: usize) -> i32 {
    ST.with(|s| { let mut st = s.borrow_mut();
        let Some(t) = with_rows(&st, rows, |t, g| Tree::of_rows(t, g, n_rows)) else { return 0 };
        let id = fresh(&mut st); st.trees.insert(id, t); id })
}
/// a tree of points (f64 pairs at xy, n of them; the buffer stays the caller's)
#[no_mangle]
pub extern "C" fn ptree_new(xy: *const f64, n: usize) -> i32 {
    let xy = unsafe { std::slice::from_raw_parts(xy, 2 * n) };
    ST.with(|s| { let mut st = s.borrow_mut(); let t = Tree::of_points(xy); let id = fresh(&mut st); st.trees.insert(id, t); id })
}
#[no_mangle]
pub extern "C" fn tree_free(id: i32) { ST.with(|s| { s.borrow_mut().trees.remove(&id); }) }
/// the pieces in any of n boxes (f64: w, s, e, n each): how many ids, at `ids_ptr()`, sorted
#[no_mangle]
pub extern "C" fn tree_query(tree: i32, boxes: *const f64, n: usize) -> usize {
    let b = unsafe { std::slice::from_raw_parts(boxes, 4 * n) };
    let boxes: Vec<Bx> = b.chunks(4).map(|c| Bx { w: c[0], s: c[1], e: c[2], n: c[3] }).collect();
    ST.with(|s| { let mut st = s.borrow_mut(); let State { trees, ids, .. } = &mut *st;
        match trees.get(&tree) { Some(t) => { t.query(&boxes, ids); ids.len() } None => { ids.clear(); 0 } } })
}
#[no_mangle]
pub extern "C" fn ids_ptr() -> *const i32 { ST.with(|s| s.borrow().ids.as_ptr()) }
