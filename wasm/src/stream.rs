//! d3-geo's stream protocol in Rust: a chain of stages, each handing its output to the next -- the rotation in front,
//! then a clip (clip.rs), the adaptive resampling that projects, and at the end the sink that writes canvas commands.
//! Points carry d3's third argument `m`, the marker the circle clip puts on an intersection (read only by the buffers).
use crate::math::*;
use crate::projections::Transform;
use crate::rotation::Rotation;
use std::cell::RefCell;
use std::rc::Rc;

pub type Pt = [f64; 3];

pub trait Stream {
    fn point(&mut self, x: f64, y: f64, m: f64);
    fn line_start(&mut self);
    fn line_end(&mut self);
    fn polygon_start(&mut self);
    fn polygon_end(&mut self);
    fn sphere(&mut self) {}
}

/// THE SINK: canvas commands as triples (cmd, x, y) -- 0 moveTo, 1 lineTo, 2 closePath -- the same the page's own
/// canvas sink issues: a ring is closed at its end, a line is not
pub struct Sink { pub out: Rc<RefCell<Vec<f32>>>, ring: bool, first: bool }
impl Sink {
    pub fn new(out: Rc<RefCell<Vec<f32>>>) -> Sink { Sink { out, ring: false, first: false } }
}
impl Stream for Sink {
    #[inline]
    fn point(&mut self, x: f64, y: f64, _m: f64) {
        let mut o = self.out.borrow_mut();
        o.push(if self.first { 0.0 } else { 1.0 }); o.push(x as f32); o.push(y as f32);
        self.first = false;
    }
    fn line_start(&mut self) { self.first = true; }
    fn line_end(&mut self) { if self.ring { let mut o = self.out.borrow_mut(); o.push(2.0); o.push(0.0); o.push(0.0); } }
    fn polygon_start(&mut self) { self.ring = true; }
    fn polygon_end(&mut self) { self.ring = false; }
}

/// THE FRONT: degrees in, rotated radians out (d3's transformRadians then transformRotate)
pub struct Rotate { pub rot: Rotation, pub next: Box<dyn Stream> }
impl Stream for Rotate {
    #[inline]
    fn point(&mut self, x: f64, y: f64, m: f64) { let r = self.rot.apply(x * RADIANS, y * RADIANS); self.next.point(r[0], r[1], m); }
    fn line_start(&mut self) { self.next.line_start(); }
    fn line_end(&mut self) { self.next.line_end(); }
    fn polygon_start(&mut self) { self.next.polygon_start(); }
    fn polygon_end(&mut self) { self.next.polygon_end(); }
    fn sphere(&mut self) { self.next.sphere(); }
}

/// RESAMPLING (d3 resample.js): each segment projected, and subdivided on the great circle until its projection is
/// straight to within sqrt(delta2) px -- so a long edge bends as the projection bends it
const MAX_DEPTH: i32 = 16;
pub struct Resample {
    pub project: Transform, pub delta2: f64, pub next: Box<dyn Stream>,
    cos_min_distance: f64,
    in_line: bool, in_polygon: bool, ring_first: bool,
    lambda00: f64, x00: f64, y00: f64, a00: f64, b00: f64, c00: f64,
    lambda0: f64, x0: f64, y0: f64, a0: f64, b0: f64, c0: f64,
}
impl Resample {
    pub fn new(project: Transform, delta2: f64, next: Box<dyn Stream>) -> Resample {
        Resample { project, delta2, next, cos_min_distance: (30.0 * RADIANS).cos(), in_line: false, in_polygon: false, ring_first: false,
                   lambda00: 0.0, x00: 0.0, y00: 0.0, a00: 0.0, b00: 0.0, c00: 0.0, lambda0: 0.0, x0: f64::NAN, y0: 0.0, a0: 0.0, b0: 0.0, c0: 0.0 }
    }
    #[allow(clippy::too_many_arguments)]
    fn line_to(&mut self, x0: f64, y0: f64, lambda0: f64, a0: f64, b0: f64, c0: f64, x1: f64, y1: f64, lambda1: f64, a1: f64, b1: f64, c1: f64, mut depth: i32) {
        let dx = x1 - x0; let dy = y1 - y0; let d2 = dx * dx + dy * dy;
        if d2 > 4.0 * self.delta2 && depth != 0 {
            depth -= 1;
            let mut a = a0 + a1; let mut b = b0 + b1; let mut c = c0 + c1;
            let m = (a * a + b * b + c * c).sqrt();
            c /= m;
            let phi2 = asin(c);
            let lambda2 = if (c.abs() - 1.0).abs() < EPSILON || (lambda0 - lambda1).abs() < EPSILON { (lambda0 + lambda1) / 2.0 } else { b.atan2(a) };
            let p = self.project.project(lambda2, phi2);
            let (x2, y2) = (p[0], p[1]);
            let dx2 = x2 - x0; let dy2 = y2 - y0;
            let dz = dy * dx2 - dx * dy2;
            if dz * dz / d2 > self.delta2 || ((dx * dx2 + dy * dy2) / d2 - 0.5).abs() > 0.3 || a0 * a1 + b0 * b1 + c0 * c1 < self.cos_min_distance {
                a /= m; b /= m;
                self.line_to(x0, y0, lambda0, a0, b0, c0, x2, y2, lambda2, a, b, c, depth);
                self.next.point(x2, y2, 0.0);
                self.line_to(x2, y2, lambda2, a, b, c, x1, y1, lambda1, a1, b1, c1, depth);
            }
        }
    }
    #[inline]
    fn line_point(&mut self, lambda: f64, phi: f64) {
        let c = cartesian([lambda, phi]);
        let p = self.project.project(lambda, phi);
        let (x0, y0, l0, a0, b0, c0) = (self.x0, self.y0, self.lambda0, self.a0, self.b0, self.c0);
        self.x0 = p[0]; self.y0 = p[1]; self.lambda0 = lambda; self.a0 = c[0]; self.b0 = c[1]; self.c0 = c[2];
        self.line_to(x0, y0, l0, a0, b0, c0, p[0], p[1], lambda, c[0], c[1], c[2], MAX_DEPTH);
        self.next.point(self.x0, self.y0, 0.0);
    }
}
impl Stream for Resample {
    fn point(&mut self, x: f64, y: f64, _m: f64) {
        if !self.in_line { let p = self.project.project(x, y); self.next.point(p[0], p[1], 0.0); return; }
        if self.ring_first {
            self.ring_first = false;
            self.lambda00 = x;
            self.line_point(x, y);
            self.x00 = self.x0; self.y00 = self.y0; self.a00 = self.a0; self.b00 = self.b0; self.c00 = self.c0;
        } else { self.line_point(x, y); }
    }
    fn line_start(&mut self) {
        self.x0 = f64::NAN; self.in_line = true;
        self.next.line_start();
        if self.in_polygon { self.ring_first = true; }
    }
    fn line_end(&mut self) {
        if self.in_polygon {
            let (x0, y0, l0, a0, b0, c0) = (self.x0, self.y0, self.lambda0, self.a0, self.b0, self.c0);
            let (x00, y00, l00, a00, b00, c00) = (self.x00, self.y00, self.lambda00, self.a00, self.b00, self.c00);
            self.line_to(x0, y0, l0, a0, b0, c0, x00, y00, l00, a00, b00, c00, MAX_DEPTH);
        }
        self.in_line = false; self.ring_first = false;
        self.next.line_end();
    }
    fn polygon_start(&mut self) { self.next.polygon_start(); self.in_polygon = true; }
    fn polygon_end(&mut self) { self.next.polygon_end(); self.in_polygon = false; }
    fn sphere(&mut self) { self.next.sphere(); }
}

/// A BUFFER (d3 clipBuffer): lines of points kept, for a polygon's rings to be clipped as a whole
#[derive(Default)]
pub struct Buffer { pub lines: Vec<Vec<Pt>> }
impl Buffer {
    pub fn rejoin(&mut self) { if self.lines.len() > 1 { let last = self.lines.pop().unwrap(); let first = self.lines.remove(0); let mut j = last; j.extend(first); self.lines.push(j); } }
    pub fn result(&mut self) -> Vec<Vec<Pt>> { std::mem::take(&mut self.lines) }
}
impl Stream for Buffer {
    fn point(&mut self, x: f64, y: f64, m: f64) { self.lines.last_mut().unwrap().push([x, y, m]); }
    fn line_start(&mut self) { self.lines.push(Vec::new()); }
    fn line_end(&mut self) {}
    fn polygon_start(&mut self) {}
    fn polygon_end(&mut self) {}
}
