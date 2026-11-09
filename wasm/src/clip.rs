//! d3-geo's clipping: the antimeridian cut (every flat projection), the small-circle clip (the globe, the azimuthal
//! equal-area) and the rectangle post-clip (Mercator's extent) -- with the polygon rejoining that walks the cut
//! segments and the clip edge alternately, and polygonContains that tells whether the clip's start point is inside.
//! Ported from d3-geo 3.1.2 clip/*.js, polygonContains.js, circle.js: the same branches in the same order.
use crate::math::*;
use crate::stream::{Buffer, Pt, Stream};

// ---- polygonContains ----------------------------------------------------------------------------------------------
#[inline]
fn longitude(p: P2) -> f64 { if p[0].abs() <= PI { p[0] } else { sign(p[0]) * ((p[0].abs() + PI) % TAU - PI) } }

/// d3-array's Adder stands in for this: a compensated sum (Neumaier), exact enough for the near-zero test it feeds
struct Adder { s: f64, c: f64 }
impl Adder {
    fn new() -> Adder { Adder { s: 0.0, c: 0.0 } }
    fn add(&mut self, x: f64) { let t = self.s + x; if self.s.abs() >= x.abs() { self.c += (self.s - t) + x; } else { self.c += (x - t) + self.s; } self.s = t; }
    fn value(&self) -> f64 { self.s + self.c }
}

pub fn polygon_contains(polygon: &[Vec<P2>], point: P2) -> bool {
    let lambda = longitude(point);
    let mut phi = point[1];
    let sin_phi = phi.sin();
    let normal = [lambda.sin(), -lambda.cos(), 0.0];
    let mut angle = 0.0;
    let mut winding: i64 = 0;
    let mut sum = Adder::new();
    if sin_phi == 1.0 { phi = HALF_PI + EPSILON; } else if sin_phi == -1.0 { phi = -HALF_PI - EPSILON; }
    for ring in polygon {
        let m = ring.len();
        if m == 0 { continue; }
        let mut point0 = ring[m - 1];
        let mut lambda0 = longitude(point0);
        let phi0 = point0[1] / 2.0 + QUARTER_PI;
        let mut sin_phi0 = phi0.sin();
        let mut cos_phi0 = phi0.cos();
        for &point1 in ring.iter() {
            let lambda1 = longitude(point1);
            let phi1 = point1[1] / 2.0 + QUARTER_PI;
            let sin_phi1 = phi1.sin();
            let cos_phi1 = phi1.cos();
            let delta = lambda1 - lambda0;
            let sgn = if delta >= 0.0 { 1.0 } else { -1.0 };
            let abs_delta = sgn * delta;
            let antimeridian = abs_delta > PI;
            let k = sin_phi0 * sin_phi1;
            sum.add((k * sgn * abs_delta.sin()).atan2(cos_phi0 * cos_phi1 + k * abs_delta.cos()));
            angle += if antimeridian { delta + sgn * TAU } else { delta };
            if antimeridian ^ (lambda0 >= lambda) ^ (lambda1 >= lambda) {
                let arc = normalize(cross(cartesian(point0), cartesian(point1)));
                let intersection = normalize(cross(normal, arc));
                let phi_arc = (if antimeridian ^ (delta >= 0.0) { -1.0 } else { 1.0 }) * asin(intersection[2]);
                if phi > phi_arc || (phi == phi_arc && (arc[0] != 0.0 || arc[1] != 0.0)) {
                    winding += if antimeridian ^ (delta >= 0.0) { 1 } else { -1 };
                }
            }
            lambda0 = lambda1; sin_phi0 = sin_phi1; cos_phi0 = cos_phi1; point0 = point1;
        }
    }
    (angle < -EPSILON || (angle < EPSILON && sum.value() < -EPSILON2)) ^ ((winding & 1) != 0)
}

// ---- clipRejoin ----------------------------------------------------------------------------------------------------
struct Node { x: Pt, z: Option<usize>, o: usize, e: bool, v: bool, n: usize, p: usize }

fn link(nodes: &mut [Node], list: &[usize]) {
    let n = list.len();
    if n == 0 { return; }
    for i in 0..n { let a = list[i]; let b = list[(i + 1) % n]; nodes[a].n = b; nodes[b].p = a; }
}

/// the cut segments rejoined along the clip edge (d3 clipRejoin): `compare` orders the intersections along the edge,
/// `interpolate` draws the edge between two of them (or all round it, from None to None)
pub fn rejoin(mut segments: Vec<Vec<Pt>>, compare: &dyn Fn(Pt, Pt) -> f64, mut start_inside: bool,
              interpolate: &mut dyn FnMut(Option<Pt>, Option<Pt>, f64, &mut dyn Stream), stream: &mut dyn Stream) {
    let mut nodes: Vec<Node> = Vec::new();
    let mut subject: Vec<usize> = Vec::new();
    let mut clip: Vec<usize> = Vec::new();
    for (si, segment) in segments.iter_mut().enumerate() {
        if segment.len() < 2 { continue; }
        let n = segment.len() - 1;
        let p0 = segment[0];
        let mut p1 = segment[n];
        if point_equal([p0[0], p0[1]], [p1[0], p1[1]]) {
            if p0[2] == 0.0 && p1[2] == 0.0 {
                stream.line_start();
                for q in segment.iter().take(n) { stream.point(q[0], q[1], 0.0); }
                stream.line_end();
                continue;
            }
            p1[0] += 2.0 * EPSILON;   // (a degenerate case: the point moved)
            segment[n] = p1;
        }
        let a = nodes.len(); nodes.push(Node { x: p0, z: Some(si), o: a + 1, e: true, v: false, n: 0, p: 0 });
        nodes.push(Node { x: p0, z: None, o: a, e: false, v: false, n: 0, p: 0 });
        subject.push(a); clip.push(a + 1);
        let b = nodes.len(); nodes.push(Node { x: p1, z: Some(si), o: b + 1, e: false, v: false, n: 0, p: 0 });
        nodes.push(Node { x: p1, z: None, o: b, e: true, v: false, n: 0, p: 0 });
        subject.push(b); clip.push(b + 1);
    }
    if subject.is_empty() { return; }
    clip.sort_by(|&a, &b| compare(nodes[a].x, nodes[b].x).partial_cmp(&0.0).unwrap_or(std::cmp::Ordering::Equal));
    link(&mut nodes, &subject);
    link(&mut nodes, &clip);
    for &i in &clip { start_inside = !start_inside; nodes[i].e = start_inside; }
    let start = subject[0];
    loop {
        let mut current = start;
        let mut is_subject = true;
        while nodes[current].v { current = nodes[current].n; if current == start { return; } }
        let mut points = nodes[current].z;
        stream.line_start();
        loop {
            nodes[current].v = true; let o = nodes[current].o; nodes[o].v = true;
            if nodes[current].e {
                if is_subject {
                    if let Some(si) = points { for q in &segments[si] { stream.point(q[0], q[1], 0.0); } }
                } else {
                    let nx = nodes[nodes[current].n].x;
                    interpolate(Some(nodes[current].x), Some(nx), 1.0, stream);
                }
                current = nodes[current].n;
            } else {
                if is_subject {
                    points = nodes[nodes[current].p].z;
                    if let Some(si) = points { for q in segments[si].iter().rev() { stream.point(q[0], q[1], 0.0); } }
                } else {
                    let px = nodes[nodes[current].p].x;
                    interpolate(Some(nodes[current].x), Some(px), -1.0, stream);
                }
                current = nodes[current].p;
            }
            current = nodes[current].o;
            points = nodes[current].z;
            is_subject = !is_subject;
            if nodes[current].v { break; }
        }
        stream.line_end();
    }
}

/// the order of intersections along the antimeridian and along a circle alike (d3 compareIntersection)
pub fn compare_intersection(a: Pt, b: Pt) -> f64 {
    (if a[0] < 0.0 { a[1] - HALF_PI - EPSILON } else { HALF_PI - a[1] })
        - (if b[0] < 0.0 { b[1] - HALF_PI - EPSILON } else { HALF_PI - b[1] })
}

// ---- the clip framework (d3 clip/index.js) --------------------------------------------------------------------------
/// a line clipper: takes a line's points and writes its visible pieces to `out` (d3's clipLine(stream))
pub trait ClipLine {
    fn line_start(&mut self, out: &mut dyn Stream);
    fn point(&mut self, lambda: f64, phi: f64, out: &mut dyn Stream);
    fn line_end(&mut self, out: &mut dyn Stream);
    /// 0: intersections or empty; 1: none; 2: intersections, and the first and last segments should be rejoined
    fn clean(&self) -> i32;
}

pub trait ClipKind {
    fn point_visible(&self, lambda: f64, phi: f64) -> bool;
    fn interpolate(&self, from: Option<Pt>, to: Option<Pt>, direction: f64, stream: &mut dyn Stream);
    fn start(&self) -> P2;
    fn clip_line(&self) -> Box<dyn ClipLine>;
}

pub struct Clip<K: ClipKind> {
    kind: K, line: Box<dyn ClipLine>, ring_line: Box<dyn ClipLine>, ring_buffer: Buffer,
    polygon_started: bool, in_polygon: bool, in_line: bool,
    polygon: Vec<Vec<P2>>, segments: Vec<Vec<Pt>>, ring: Vec<P2>,
    pub sink: Box<dyn Stream>,
}

impl<K: ClipKind> Clip<K> {
    pub fn new(kind: K, sink: Box<dyn Stream>) -> Clip<K> {
        let line = kind.clip_line(); let ring_line = kind.clip_line();
        Clip { kind, line, ring_line, ring_buffer: Buffer::default(), polygon_started: false, in_polygon: false, in_line: false,
               polygon: Vec::new(), segments: Vec::new(), ring: Vec::new(), sink }
    }
    fn point_ring(&mut self, lambda: f64, phi: f64) {
        self.ring.push([lambda, phi]);
        self.ring_line.point(lambda, phi, &mut self.ring_buffer);
    }
    fn ring_end(&mut self) {
        let first = self.ring[0];
        self.point_ring(first[0], first[1]);
        self.ring_line.line_end(&mut self.ring_buffer);
        let clean = self.ring_line.clean();
        let mut ring_segments = self.ring_buffer.result();
        let n = ring_segments.len();
        self.ring.pop();
        let ring = std::mem::take(&mut self.ring);
        self.polygon.push(ring);
        if n == 0 { return; }
        if clean & 1 != 0 {   // no intersections
            let segment = &ring_segments[0];
            if segment.len() > 1 {
                let m = segment.len() - 1;
                if !self.polygon_started { self.sink.polygon_start(); self.polygon_started = true; }
                self.sink.line_start();
                for q in segment.iter().take(m) { self.sink.point(q[0], q[1], 0.0); }
                self.sink.line_end();
            }
            return;
        }
        if n > 1 && clean & 2 != 0 { let last = ring_segments.pop().unwrap(); let first = ring_segments.remove(0); let mut j = last; j.extend(first); ring_segments.push(j); }
        self.segments.extend(ring_segments.into_iter().filter(|s| s.len() > 1));
    }
}

impl<K: ClipKind> Stream for Clip<K> {
    fn point(&mut self, lambda: f64, phi: f64, _m: f64) {
        if self.in_polygon { self.point_ring(lambda, phi); }
        else if self.in_line { self.line.point(lambda, phi, &mut *self.sink); }
        else if self.kind.point_visible(lambda, phi) { self.sink.point(lambda, phi, 0.0); }
    }
    fn line_start(&mut self) {
        if self.in_polygon { self.ring_line.line_start(&mut self.ring_buffer); self.ring.clear(); }
        else { self.in_line = true; self.line.line_start(&mut *self.sink); }
    }
    fn line_end(&mut self) {
        if self.in_polygon { self.ring_end(); }
        else { self.in_line = false; self.line.line_end(&mut *self.sink); }
    }
    fn polygon_start(&mut self) { self.in_polygon = true; self.segments.clear(); self.polygon.clear(); }
    fn polygon_end(&mut self) {
        self.in_polygon = false;
        let segments = std::mem::take(&mut self.segments);
        let polygon = std::mem::take(&mut self.polygon);
        let start_inside = polygon_contains(&polygon, self.kind.start());
        if !segments.is_empty() {
            if !self.polygon_started { self.sink.polygon_start(); self.polygon_started = true; }
            let kind = &self.kind;
            let mut interp = |a: Option<Pt>, b: Option<Pt>, d: f64, s: &mut dyn Stream| kind.interpolate(a, b, d, s);
            rejoin(segments, &compare_intersection, start_inside, &mut interp, &mut *self.sink);
        } else if start_inside {
            if !self.polygon_started { self.sink.polygon_start(); self.polygon_started = true; }
            self.sink.line_start();
            self.kind.interpolate(None, None, 1.0, &mut *self.sink);
            self.sink.line_end();
        }
        if self.polygon_started { self.sink.polygon_end(); self.polygon_started = false; }
    }
    fn sphere(&mut self) {
        self.sink.polygon_start(); self.sink.line_start();
        self.kind.interpolate(None, None, 1.0, &mut *self.sink);
        self.sink.line_end(); self.sink.polygon_end();
    }
}

// ---- the antimeridian (d3 clip/antimeridian.js) ------------------------------------------------------------------
pub struct Antimeridian;
struct AntimeridianLine { lambda0: f64, phi0: f64, sign0: f64, clean: i32 }

fn antimeridian_intersect(lambda0: f64, phi0: f64, lambda1: f64, phi1: f64) -> f64 {
    let s = (lambda0 - lambda1).sin();
    if s.abs() > EPSILON {
        let cos_phi1 = phi1.cos(); let cos_phi0 = phi0.cos();
        ((phi0.sin() * cos_phi1 * lambda1.sin() - phi1.sin() * cos_phi0 * lambda0.sin()) / (cos_phi0 * cos_phi1 * s)).atan()
    } else { (phi0 + phi1) / 2.0 }
}

impl ClipLine for AntimeridianLine {
    fn line_start(&mut self, out: &mut dyn Stream) { out.line_start(); self.clean = 1; }
    fn point(&mut self, mut lambda1: f64, phi1: f64, out: &mut dyn Stream) {
        let sign1 = if lambda1 > 0.0 { PI } else { -PI };
        let delta = (lambda1 - self.lambda0).abs();
        if (delta - PI).abs() < EPSILON {   // the line crosses a pole
            self.phi0 = if (self.phi0 + phi1) / 2.0 > 0.0 { HALF_PI } else { -HALF_PI };
            out.point(self.lambda0, self.phi0, 0.0);
            out.point(self.sign0, self.phi0, 0.0);
            out.line_end(); out.line_start();
            out.point(sign1, self.phi0, 0.0);
            out.point(lambda1, self.phi0, 0.0);
            self.clean = 0;
        } else if self.sign0 != sign1 && delta >= PI {   // the line crosses the antimeridian
            if (self.lambda0 - self.sign0).abs() < EPSILON { self.lambda0 -= self.sign0 * EPSILON; }
            if (lambda1 - sign1).abs() < EPSILON { lambda1 -= sign1 * EPSILON; }
            self.phi0 = antimeridian_intersect(self.lambda0, self.phi0, lambda1, phi1);
            out.point(self.sign0, self.phi0, 0.0);
            out.line_end(); out.line_start();
            out.point(sign1, self.phi0, 0.0);
            self.clean = 0;
        }
        self.lambda0 = lambda1; self.phi0 = phi1;
        out.point(lambda1, phi1, 0.0);
        self.sign0 = sign1;
    }
    fn line_end(&mut self, out: &mut dyn Stream) { out.line_end(); self.lambda0 = f64::NAN; self.phi0 = f64::NAN; }
    fn clean(&self) -> i32 { 2 - self.clean }
}

impl ClipKind for Antimeridian {
    fn point_visible(&self, _l: f64, _p: f64) -> bool { true }
    fn interpolate(&self, from: Option<Pt>, to: Option<Pt>, direction: f64, s: &mut dyn Stream) {
        match (from, to) {
            (None, _) => {
                let phi = direction * HALF_PI;
                s.point(-PI, phi, 0.0); s.point(0.0, phi, 0.0); s.point(PI, phi, 0.0); s.point(PI, 0.0, 0.0);
                s.point(PI, -phi, 0.0); s.point(0.0, -phi, 0.0); s.point(-PI, -phi, 0.0); s.point(-PI, 0.0, 0.0); s.point(-PI, phi, 0.0);
            }
            (Some(f), Some(t)) if (f[0] - t[0]).abs() > EPSILON => {
                let lambda = if f[0] < t[0] { PI } else { -PI };
                let phi = direction * lambda / 2.0;
                s.point(-lambda, phi, 0.0); s.point(0.0, phi, 0.0); s.point(lambda, phi, 0.0);
            }
            (Some(_), Some(t)) => s.point(t[0], t[1], 0.0),
            (Some(_), None) => {}
        }
    }
    fn start(&self) -> P2 { [-PI, -HALF_PI] }
    fn clip_line(&self) -> Box<dyn ClipLine> { Box::new(AntimeridianLine { lambda0: f64::NAN, phi0: f64::NAN, sign0: f64::NAN, clean: 1 }) }
}

// ---- the small circle (d3 clip/circle.js) -------------------------------------------------------------------------
#[derive(Clone, Copy)]
pub struct Circle { radius: f64, cr: f64, delta: f64, small_radius: bool, not_hemisphere: bool }

impl Circle {
    pub fn new(radius: f64) -> Circle { let cr = radius.cos(); Circle { radius, cr, delta: 2.0 * RADIANS, small_radius: cr > 0.0, not_hemisphere: cr.abs() > EPSILON } }
    #[inline]
    fn visible(&self, lambda: f64, phi: f64) -> bool { lambda.cos() * phi.cos() > self.cr }
    fn code(&self, lambda: f64, phi: f64) -> i32 {
        let r = if self.small_radius { self.radius } else { PI - self.radius };
        let mut code = 0;
        if lambda < -r { code |= 1; } else if lambda > r { code |= 2; }
        if phi < -r { code |= 4; } else if phi > r { code |= 8; }
        code
    }
    /// the great circle a-b meets the clip circle: one point (two = false), or both (two = true) when the first lies between a and b
    fn intersect(&self, a: P2, b: P2, two: bool) -> Intersect {
        let pa = cartesian(a); let pb = cartesian(b);
        let n1 = [1.0, 0.0, 0.0];
        let n2 = cross(pa, pb);
        let n2n2 = dot(n2, n2);
        let n1n2 = n2[0];
        let determinant = n2n2 - n1n2 * n1n2;
        if determinant == 0.0 { return if two { Intersect::None } else { Intersect::One(a) }; }   // two polar points
        let c1 = self.cr * n2n2 / determinant;
        let c2 = -self.cr * n1n2 / determinant;
        let n1xn2 = cross(n1, n2);
        let aa = add(scale(n1, c1), scale(n2, c2));
        let u = n1xn2;
        let w = dot(aa, u);
        let uu = dot(u, u);
        let t2 = w * w - uu * (dot(aa, aa) - 1.0);
        if t2 < 0.0 { return Intersect::None; }
        let t = t2.sqrt();
        let q = spherical(add(scale(u, (-w - t) / uu), aa));
        if !two { return Intersect::One(q); }
        let (mut lambda0, mut lambda1, mut phi0, mut phi1) = (a[0], b[0], a[1], b[1]);
        if lambda1 < lambda0 { std::mem::swap(&mut lambda0, &mut lambda1); }
        let delta = lambda1 - lambda0;
        let polar = (delta - PI).abs() < EPSILON;
        let meridian = polar || delta < EPSILON;
        if !polar && phi1 < phi0 { std::mem::swap(&mut phi0, &mut phi1); }
        let between = if meridian {
            if polar { (phi0 + phi1 > 0.0) ^ (q[1] < (if (q[0] - lambda0).abs() < EPSILON { phi0 } else { phi1 })) }
            else { phi0 <= q[1] && q[1] <= phi1 }
        } else { (delta > PI) ^ (lambda0 <= q[0] && q[0] <= lambda1) };
        if between {
            let q1 = spherical(add(scale(u, (-w + t) / uu), aa));
            Intersect::Two(q, q1)
        } else { Intersect::None }
    }
}

enum Intersect { None, One(P2), Two(P2, P2) }

struct CircleLine { c: Circle, point0: Option<Pt>, c0: i32, v0: bool, v00: bool, clean: i32 }

impl ClipLine for CircleLine {
    fn line_start(&mut self, _out: &mut dyn Stream) { self.v00 = false; self.v0 = false; self.clean = 1; }
    fn point(&mut self, lambda: f64, phi: f64, out: &mut dyn Stream) {
        let c = &self.c;
        let mut point1: Pt = [lambda, phi, 0.0];
        let v = c.visible(lambda, phi);
        let code = if c.small_radius { if v { 0 } else { c.code(lambda, phi) } }
                   else if v { c.code(lambda + if lambda < 0.0 { PI } else { -PI }, phi) } else { 0 };
        if self.point0.is_none() { self.v00 = v; self.v0 = v; if v { out.line_start(); } }
        if v != self.v0 {
            let p0 = self.point0.unwrap_or([f64::NAN, f64::NAN, 0.0]);
            let p0_2 = [p0[0], p0[1]];
            let point2 = c.intersect(p0_2, [lambda, phi], false);
            match point2 {
                Intersect::One(q) if !point_equal(p0_2, q) && !point_equal([lambda, phi], q) => {}
                _ => point1[2] = 1.0,
            }
        }
        if v != self.v0 {
            self.clean = 0;
            let p0 = self.point0.unwrap_or([f64::NAN, f64::NAN, 0.0]);
            let p0_2 = [p0[0], p0[1]];
            if v {   // outside going in
                out.line_start();
                if let Intersect::One(q) = c.intersect([lambda, phi], p0_2, false) { out.point(q[0], q[1], 0.0); self.point0 = Some([q[0], q[1], 0.0]); }
            } else {   // inside going out
                if let Intersect::One(q) = c.intersect(p0_2, [lambda, phi], false) { out.point(q[0], q[1], 2.0); self.point0 = Some([q[0], q[1], 0.0]); }
                out.line_end();
            }
        } else if c.not_hemisphere && self.point0.is_some() && (c.small_radius ^ v) {
            // (the codes differ, or are both zero, and the segment meets the small circle)
            if code & self.c0 == 0 {
                let p0 = self.point0.unwrap();
                if let Intersect::Two(t0, t1) = c.intersect([lambda, phi], [p0[0], p0[1]], true) {
                    self.clean = 0;
                    if c.small_radius {
                        out.line_start(); out.point(t0[0], t0[1], 0.0); out.point(t1[0], t1[1], 0.0); out.line_end();
                    } else {
                        out.point(t1[0], t1[1], 0.0); out.line_end(); out.line_start(); out.point(t0[0], t0[1], 3.0);
                    }
                }
            }
        }
        if v && (self.point0.is_none() || !point_equal([self.point0.unwrap()[0], self.point0.unwrap()[1]], [point1[0], point1[1]])) {
            out.point(point1[0], point1[1], 0.0);
        }
        self.point0 = Some(point1); self.v0 = v; self.c0 = code;
    }
    fn line_end(&mut self, out: &mut dyn Stream) { if self.v0 { out.line_end(); } self.point0 = None; }
    fn clean(&self) -> i32 { self.clean | (((self.v00 && self.v0) as i32) << 1) }
}

/// d3 circleStream: the circle round [0, 0] of `radius`, every `delta` radians, from t0 to t1 (or all round)
pub fn circle_stream(stream: &mut dyn Stream, radius: f64, delta: f64, direction: f64, t0: Option<P2>, t1: Option<P2>) {
    if delta == 0.0 { return; }
    let cos_radius = radius.cos(); let sin_radius = radius.sin();
    let step = direction * delta;
    let (t0, t1) = match (t0, t1) {
        (None, _) | (_, None) => (radius + direction * TAU, radius - step / 2.0),
        (Some(a), Some(b)) => {
            let mut t0 = circle_radius(cos_radius, a); let t1 = circle_radius(cos_radius, b);
            if if direction > 0.0 { t0 < t1 } else { t0 > t1 } { t0 += direction * TAU; }
            (t0, t1)
        }
    };
    let mut t = t0;
    while if direction > 0.0 { t > t1 } else { t < t1 } {
        let p = spherical([cos_radius, -sin_radius * t.cos(), -sin_radius * t.sin()]);
        stream.point(p[0], p[1], 0.0);
        t -= step;
    }
}
fn circle_radius(cos_radius: f64, point: P2) -> f64 {
    let mut p = cartesian(point); p[0] -= cos_radius;
    let p = normalize(p);
    let radius = acos(-p[1]);
    ((if -p[2] < 0.0 { -radius } else { radius }) + TAU - EPSILON) % TAU
}

impl ClipKind for Circle {
    fn point_visible(&self, lambda: f64, phi: f64) -> bool { self.visible(lambda, phi) }
    fn interpolate(&self, from: Option<Pt>, to: Option<Pt>, direction: f64, s: &mut dyn Stream) {
        circle_stream(s, self.radius, self.delta, direction, from.map(|p| [p[0], p[1]]), to.map(|p| [p[0], p[1]]));
    }
    fn start(&self) -> P2 { if self.small_radius { [0.0, -self.radius] } else { [-PI, self.radius - PI] } }
    fn clip_line(&self) -> Box<dyn ClipLine> { Box::new(CircleLine { c: *self, point0: None, c0: 0, v0: false, v00: false, clean: 1 }) }
}

// ---- the rectangle (d3 clip/rectangle.js): Mercator's post-clip, in screen coordinates --------------------------
const CLIP_MAX: f64 = 1e9;
const CLIP_MIN: f64 = -CLIP_MAX;

pub struct Rectangle {
    x0: f64, y0: f64, x1: f64, y1: f64,
    pub sink: Box<dyn Stream>, buffer: Buffer, buffering: bool,
    segments: Option<Vec<Vec<Pt>>>, polygon: Option<Vec<Vec<P2>>>,
    x__: f64, y__: f64, v__: bool, x_: f64, y_: f64, v_: bool, first: bool, clean: bool, in_line: bool,
}

/// Liang-Barsky: the segment a-b cut to the box, true when something is left (d3 clip/line.js)
fn clip_segment(a: &mut P2, b: &mut P2, x0: f64, y0: f64, x1: f64, y1: f64) -> bool {
    let (ax, ay, bx, by) = (a[0], a[1], b[0], b[1]);
    let (mut t0, mut t1) = (0.0, 1.0);
    let dx = bx - ax; let dy = by - ay;
    let mut r = x0 - ax;
    if dx == 0.0 && r > 0.0 { return false; }
    r /= dx;
    if dx < 0.0 { if r < t0 { return false; } if r < t1 { t1 = r; } } else if dx > 0.0 { if r > t1 { return false; } if r > t0 { t0 = r; } }
    r = x1 - ax;
    if dx == 0.0 && r < 0.0 { return false; }
    r /= dx;
    if dx < 0.0 { if r > t1 { return false; } if r > t0 { t0 = r; } } else if dx > 0.0 { if r < t0 { return false; } if r < t1 { t1 = r; } }
    r = y0 - ay;
    if dy == 0.0 && r > 0.0 { return false; }
    r /= dy;
    if dy < 0.0 { if r < t0 { return false; } if r < t1 { t1 = r; } } else if dy > 0.0 { if r > t1 { return false; } if r > t0 { t0 = r; } }
    r = y1 - ay;
    if dy == 0.0 && r < 0.0 { return false; }
    r /= dy;
    if dy < 0.0 { if r > t1 { return false; } if r > t0 { t0 = r; } } else if dy > 0.0 { if r < t0 { return false; } if r < t1 { t1 = r; } }
    if t0 > 0.0 { a[0] = ax + t0 * dx; a[1] = ay + t0 * dy; }
    if t1 < 1.0 { b[0] = ax + t1 * dx; b[1] = ay + t1 * dy; }
    true
}

impl Rectangle {
    pub fn new(x0: f64, y0: f64, x1: f64, y1: f64, sink: Box<dyn Stream>) -> Rectangle {
        Rectangle { x0, y0, x1, y1, sink, buffer: Buffer::default(), buffering: false, segments: None, polygon: None,
                    x__: 0.0, y__: 0.0, v__: false, x_: f64::NAN, y_: f64::NAN, v_: false, first: true, clean: true, in_line: false }
    }
    #[inline]
    fn visible(&self, x: f64, y: f64) -> bool { self.x0 <= x && x <= self.x1 && self.y0 <= y && y <= self.y1 }
    fn corner(&self, p: Pt, direction: f64) -> i32 {
        if (p[0] - self.x0).abs() < EPSILON { if direction > 0.0 { 0 } else { 3 } }
        else if (p[0] - self.x1).abs() < EPSILON { if direction > 0.0 { 2 } else { 1 } }
        else if (p[1] - self.y0).abs() < EPSILON { if direction > 0.0 { 1 } else { 0 } }
        else if direction > 0.0 { 3 } else { 2 }
    }
    fn compare_point(&self, a: Pt, b: Pt) -> f64 {
        let ca = self.corner(a, 1.0); let cb = self.corner(b, 1.0);
        if ca != cb { (ca - cb) as f64 } else if ca == 0 { b[1] - a[1] } else if ca == 1 { a[0] - b[0] } else if ca == 2 { a[1] - b[1] } else { b[0] - a[0] }
    }
    fn interpolate(&self, from: Option<Pt>, to: Option<Pt>, direction: f64, stream: &mut dyn Stream) {
        let (mut a, mut a1) = (0, 0);
        let along = match (from, to) {
            (None, _) | (_, None) => true,
            (Some(f), Some(t)) => { a = self.corner(f, direction); a1 = self.corner(t, direction); a != a1 || ((self.compare_point(f, t) < 0.0) ^ (direction > 0.0)) }
        };
        if along {
            let d = direction as i32;
            loop {
                stream.point(if a == 0 || a == 3 { self.x0 } else { self.x1 }, if a > 1 { self.y1 } else { self.y0 }, 0.0);
                a = (a + d + 4) % 4;
                if a == a1 { break; }
            }
        } else if let Some(t) = to { stream.point(t[0], t[1], 0.0); }
    }
    fn polygon_inside(&self) -> i32 {
        let mut winding = 0;
        if let Some(polygon) = &self.polygon {
            for ring in polygon {
                if ring.is_empty() { continue; }
                let (mut b0, mut b1) = (ring[0][0], ring[0][1]);
                for q in ring.iter().skip(1) {
                    let (a0, a1) = (b0, b1); b0 = q[0]; b1 = q[1];
                    if a1 <= self.y1 { if b1 > self.y1 && (b0 - a0) * (self.y1 - a1) > (b1 - a1) * (self.x0 - a0) { winding += 1; } }
                    else if b1 <= self.y1 && (b0 - a0) * (self.y1 - a1) < (b1 - a1) * (self.x0 - a0) { winding -= 1; }
                }
            }
        }
        winding
    }
    fn active(&mut self) -> &mut dyn Stream { if self.buffering { &mut self.buffer } else { &mut *self.sink } }
    fn line_point(&mut self, mut x: f64, mut y: f64) {
        let v = self.visible(x, y);
        if let Some(polygon) = &mut self.polygon { polygon.last_mut().unwrap().push([x, y]); }
        if self.first {
            self.x__ = x; self.y__ = y; self.v__ = v;
            self.first = false;
            if v { self.active().line_start(); self.active().point(x, y, 0.0); }
        } else if v && self.v_ { self.active().point(x, y, 0.0); }
        else {
            self.x_ = self.x_.clamp(CLIP_MIN, CLIP_MAX); self.y_ = self.y_.clamp(CLIP_MIN, CLIP_MAX);
            x = x.clamp(CLIP_MIN, CLIP_MAX); y = y.clamp(CLIP_MIN, CLIP_MAX);
            let mut a = [self.x_, self.y_]; let mut b = [x, y];
            let (x0, y0, x1, y1) = (self.x0, self.y0, self.x1, self.y1);
            if clip_segment(&mut a, &mut b, x0, y0, x1, y1) {
                if !self.v_ { self.active().line_start(); self.active().point(a[0], a[1], 0.0); }
                self.active().point(b[0], b[1], 0.0);
                if !v { self.active().line_end(); }
                self.clean = false;
            } else if v {
                self.active().line_start(); self.active().point(x, y, 0.0);
                self.clean = false;
            }
        }
        self.x_ = x; self.y_ = y; self.v_ = v;
    }
}

impl Stream for Rectangle {
    fn point(&mut self, x: f64, y: f64, _m: f64) {
        if self.in_line { self.line_point(x, y); }
        else if self.visible(x, y) { self.active().point(x, y, 0.0); }
    }
    fn polygon_start(&mut self) { self.buffering = true; self.segments = Some(Vec::new()); self.polygon = Some(Vec::new()); self.clean = true; }
    fn polygon_end(&mut self) {
        let start_inside = self.polygon_inside() != 0;
        let clean_inside = self.clean && start_inside;
        let segments = self.segments.take().unwrap_or_default();
        let visible = !segments.is_empty();
        if clean_inside || visible {
            self.sink.polygon_start();
            if clean_inside {
                self.sink.line_start();
                let (x0, y0, x1, y1) = (self.x0, self.y0, self.x1, self.y1);
                let me = Rectangle::new(x0, y0, x1, y1, Box::new(Buffer::default()));   // (a stateless copy for its interpolate)
                me.interpolate(None, None, 1.0, &mut *self.sink);
                self.sink.line_end();
            }
            if visible {
                let (x0, y0, x1, y1) = (self.x0, self.y0, self.x1, self.y1);
                let me = Rectangle::new(x0, y0, x1, y1, Box::new(Buffer::default()));
                let compare = |a: Pt, b: Pt| me.compare_point(a, b);
                let mut interp = |a: Option<Pt>, b: Option<Pt>, d: f64, s: &mut dyn Stream| me.interpolate(a, b, d, s);
                rejoin(segments, &compare, start_inside, &mut interp, &mut *self.sink);
            }
            self.sink.polygon_end();
        }
        self.buffering = false; self.polygon = None;
    }
    fn line_start(&mut self) {
        self.in_line = true;
        if let Some(polygon) = &mut self.polygon { polygon.push(Vec::new()); }
        self.first = true; self.v_ = false; self.x_ = f64::NAN; self.y_ = f64::NAN;
    }
    fn line_end(&mut self) {
        if self.segments.is_some() {
            let (x, y) = (self.x__, self.y__);
            self.line_point(x, y);
            if self.v__ && self.v_ { self.buffer.rejoin(); }
            let r = self.buffer.result();
            self.segments.as_mut().unwrap().extend(r);
        }
        self.in_line = false;
        if self.v_ { self.active().line_end(); }
    }
    fn sphere(&mut self) { self.sink.sphere(); }
}
