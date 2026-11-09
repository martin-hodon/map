//! d3-geo's math.js: the guarded inverse trig and the constants, so that every edge case comes out as d3's does.
pub const EPSILON: f64 = 1e-6;
pub const EPSILON2: f64 = 1e-12;
pub const PI: f64 = std::f64::consts::PI;
pub const HALF_PI: f64 = PI / 2.0;
pub const QUARTER_PI: f64 = PI / 4.0;
pub const TAU: f64 = PI * 2.0;
pub const DEGREES: f64 = 180.0 / PI;
pub const RADIANS: f64 = PI / 180.0;

#[inline]
pub fn acos(x: f64) -> f64 { if x > 1.0 { 0.0 } else if x < -1.0 { PI } else { x.acos() } }
#[inline]
pub fn asin(x: f64) -> f64 { if x > 1.0 { HALF_PI } else if x < -1.0 { -HALF_PI } else { x.asin() } }
#[inline]
pub fn sqrt(x: f64) -> f64 { if x > 0.0 { x.sqrt() } else { 0.0 } }   // (d3-geo-projection's: never NaN)
#[inline]
pub fn sinci(x: f64) -> f64 { if x != 0.0 { x / x.sin() } else { 1.0 } }
#[inline]
pub fn sign(x: f64) -> f64 { if x > 0.0 { 1.0 } else if x < 0.0 { -1.0 } else { 0.0 } }
/// JavaScript's Math.round: half up (Rust's rounds half away from zero)
#[inline]
pub fn js_round(x: f64) -> f64 { (x + 0.5).floor() }

pub type P2 = [f64; 2];
pub type P3 = [f64; 3];

#[inline]
pub fn spherical(c: P3) -> P2 { [c[1].atan2(c[0]), asin(c[2])] }
#[inline]
pub fn cartesian(s: P2) -> P3 { let (lambda, phi) = (s[0], s[1]); let cos_phi = phi.cos(); [cos_phi * lambda.cos(), cos_phi * lambda.sin(), phi.sin()] }
#[inline]
pub fn dot(a: P3, b: P3) -> f64 { a[0] * b[0] + a[1] * b[1] + a[2] * b[2] }
#[inline]
pub fn cross(a: P3, b: P3) -> P3 { [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]] }
#[inline]
pub fn add(a: P3, b: P3) -> P3 { [a[0] + b[0], a[1] + b[1], a[2] + b[2]] }
#[inline]
pub fn scale(v: P3, k: f64) -> P3 { [v[0] * k, v[1] * k, v[2] * k] }
#[inline]
pub fn normalize(d: P3) -> P3 { let l = (d[0] * d[0] + d[1] * d[1] + d[2] * d[2]).sqrt(); [d[0] / l, d[1] / l, d[2] / l] }
#[inline]
pub fn point_equal(a: P2, b: P2) -> bool { (a[0] - b[0]).abs() < EPSILON && (a[1] - b[1]).abs() < EPSILON }
