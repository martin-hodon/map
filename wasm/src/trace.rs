//! A row traced through the stream, as the page's geom.js trace/arcInto/arcEnd/traceArcs do: the row's arcs read from the
//! shared point arrays (an arc's last point left out, it is the next arc's first), rings and polygons opened and closed.
use crate::stream::Stream;

pub const RING: i32 = 0x7fff_ffff;
pub const POLY: i32 = 0x7fff_fffe;

/// the shared lines of one file: `xy` longitude and latitude in turn (f32, as the page keeps them), `at` where each arc starts
pub struct Lines<'a> { pub xy: &'a [f32], pub at: &'a [i32] }

/// an object's rows: `start[row]`..`start[row + 1]` in `refs`
pub struct Rows<'a> { pub start: &'a [i32], pub refs: &'a [i32], pub polygon: bool }

#[inline]
fn arc_into(s: &mut dyn Stream, t: &Lines, a: i32) {
    let xy = t.xy;
    if a >= 0 {
        let a = a as usize;
        let (mut k, e) = (2 * t.at[a] as usize, 2 * t.at[a + 1] as usize - 2);
        while k < e { s.point(xy[k] as f64, xy[k + 1] as f64, 0.0); k += 2; }
    } else {
        let r = !a as usize;
        let (mut k, e) = (2 * t.at[r + 1] as isize - 2, 2 * t.at[r] as isize);
        while k > e { s.point(xy[k as usize] as f64, xy[k as usize + 1] as f64, 0.0); k -= 2; }
    }
}
#[inline]
fn arc_end(s: &mut dyn Stream, t: &Lines, a: i32) {
    let k = if a >= 0 { 2 * t.at[a as usize + 1] as usize - 2 } else { 2 * t.at[!a as usize] as usize };
    s.point(t.xy[k] as f64, t.xy[k + 1] as f64, 0.0);
}

/// one row into the stream (geom.js trace)
pub fn trace(s: &mut dyn Stream, t: &Lines, g: &Rows, row: usize) {
    let refs = g.refs;
    let (mut j, e) = (g.start[row] as usize, g.start[row + 1] as usize);
    if j == e { return; }
    if g.polygon {
        let mut open = false;
        while j < e {
            if refs[j] == POLY { s.polygon_end(); open = false; j += 1; continue; }
            if !open { s.polygon_start(); open = true; }
            s.line_start();
            while refs[j] != RING { arc_into(s, t, refs[j]); j += 1; }
            s.line_end(); j += 1;
        }
    } else {
        while j < e {
            s.line_start();
            let mut a = 0;
            while refs[j] != RING { a = refs[j]; arc_into(s, t, a); j += 1; }
            arc_end(s, t, a); s.line_end(); j += 1;
        }
    }
}

/// arcs, each a line of its own (geom.js traceArcs)
pub fn trace_arcs(s: &mut dyn Stream, t: &Lines, arcs: &[i32]) {
    for &a in arcs { s.line_start(); arc_into(s, t, a); arc_end(s, t, a); s.line_end(); }
}
