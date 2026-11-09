//! The pieces' boxes (view.js tree: a polygon's ring set a box, a line each its own; a ring round the globe takes the pole
//! in) in a packed R-tree -- sorted into tiles, then nodes of up to 16 -- answering the view's boxes with the rows hit,
//! sorted and unique, as view.js query gives them.
use crate::trace::{Lines, Rows, POLY, RING};

#[derive(Clone, Copy)]
pub struct Bx { pub w: f64, pub s: f64, pub e: f64, pub n: f64 }
impl Bx {
    pub const EMPTY: Bx = Bx { w: 999.0, s: 999.0, e: -999.0, n: -999.0 };
    #[inline] fn hits(&self, o: &Bx) -> bool { o.w <= self.e && o.e >= self.w && o.s <= self.n && o.n >= self.s }
    #[inline] fn grow(&mut self, o: &Bx) { if o.w < self.w { self.w = o.w; } if o.e > self.e { self.e = o.e; } if o.s < self.s { self.s = o.s; } if o.n > self.n { self.n = o.n; } }
}

const NODE: usize = 16;
struct Node { bx: Bx, first: usize, count: usize, leaf: bool }   // (children: the next level's nodes, or the items)

pub struct Tree { items: Vec<(Bx, i32)>, levels: Vec<Vec<Node>> }

impl Tree {
    /// the boxes of an object's rows (view.js tree)
    pub fn of_rows(t: &Lines, g: &Rows, n_rows: usize) -> Tree {
        let mut items = Vec::new();
        for i in 0..n_rows {
            let mut b = Bx::EMPTY;
            for j in g.start[i] as usize..g.start[i + 1] as usize {
                let a = g.refs[j];
                if a == RING { if !g.polygon { items.push((b, i as i32)); b = Bx::EMPTY; } continue; }
                if a == POLY { if b.e - b.w >= 359.0 { if b.s + b.n > 0.0 { b.n = 90.0; } else { b.s = -90.0; } } items.push((b, i as i32)); b = Bx::EMPTY; continue; }
                let r = if a < 0 { !a } else { a } as usize;
                for k in t.at[r] as usize..t.at[r + 1] as usize {
                    let (u, v) = (t.xy[2 * k] as f64, t.xy[2 * k + 1] as f64);
                    if u < b.w { b.w = u; } if u > b.e { b.e = u; } if v < b.s { b.s = v; } if v > b.n { b.n = v; }
                }
            }
        }
        Tree::build(items)
    }
    /// points, each its own box (view.js pointTree)
    pub fn of_points(xy: &[f64]) -> Tree {
        Tree::build((0..xy.len() / 2).map(|i| (Bx { w: xy[2 * i], s: xy[2 * i + 1], e: xy[2 * i], n: xy[2 * i + 1] }, i as i32)).collect())
    }
    fn build(mut items: Vec<(Bx, i32)>) -> Tree {
        // sort-tile-recursive: by the centre's x into vertical strips, each strip by y
        let n = items.len();
        if n == 0 { return Tree { items, levels: vec![] }; }
        let leaves = n.div_ceil(NODE);
        let strips = (leaves as f64).sqrt().ceil() as usize;
        let per_strip = n.div_ceil(strips);
        items.sort_by(|a, b| (a.0.w + a.0.e).partial_cmp(&(b.0.w + b.0.e)).unwrap());
        for c in items.chunks_mut(per_strip) { c.sort_by(|a, b| (a.0.s + a.0.n).partial_cmp(&(b.0.s + b.0.n)).unwrap()); }
        let mut level: Vec<Node> = items.chunks(NODE).enumerate().map(|(i, c)| {
            let mut bx = Bx::EMPTY; for (b, _) in c { bx.grow(b); }
            Node { bx, first: i * NODE, count: c.len(), leaf: true }
        }).collect();
        let mut levels = vec![];
        while level.len() > 1 {
            let up: Vec<Node> = level.chunks(NODE).enumerate().map(|(i, c)| {
                let mut bx = Bx::EMPTY; for nd in c { bx.grow(&nd.bx); }
                Node { bx, first: i * NODE, count: c.len(), leaf: false }
            }).collect();
            levels.push(level); level = up;
        }
        levels.push(level);
        levels.reverse();   // (the root first)
        Tree { items, levels }
    }
    /// the rows any of the boxes hit: sorted, each once
    pub fn query(&self, boxes: &[Bx], out: &mut Vec<i32>) {
        out.clear();
        if self.levels.is_empty() { return; }
        for q in boxes {
            let mut stack: Vec<(usize, usize)> = vec![(0, 0)];
            while let Some((lv, i)) = stack.pop() {
                let nd = &self.levels[lv][i];
                if !nd.bx.hits(q) { continue; }
                if nd.leaf { for (b, id) in &self.items[nd.first..nd.first + nd.count] { if b.hits(q) { out.push(*id); } } }
                else { for c in nd.first..nd.first + nd.count { stack.push((lv + 1, c)); } }
            }
        }
        out.sort_unstable(); out.dedup();
    }
}
