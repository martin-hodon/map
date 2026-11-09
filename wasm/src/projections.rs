//! The nine projections the map offers (index.html PROJ), as d3-geo and d3-geo-projection compute them: a raw
//! projection takes rotated radians and gives unit coordinates; the transform then scales and translates them.
use crate::math::*;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind { Orthographic = 0, EqualEarth = 1, NaturalEarth1 = 2, Robinson = 3, Mercator = 4, Equirectangular = 5, AzimuthalEqualArea = 6, Winkel3 = 7, Mollweide = 8 }

impl Kind {
    pub fn from_i32(k: i32) -> Kind {
        match k { 0 => Kind::Orthographic, 1 => Kind::EqualEarth, 2 => Kind::NaturalEarth1, 3 => Kind::Robinson, 4 => Kind::Mercator,
                  5 => Kind::Equirectangular, 6 => Kind::AzimuthalEqualArea, 7 => Kind::Winkel3, _ => Kind::Mollweide }
    }
}

// Robinson's table (d3-geo-projection robinson.js), the y column scaled as there
const ROBINSON: [[f64; 2]; 20] = {
    const K: [[f64; 2]; 20] = [[0.9986, -0.062], [1.0000, 0.0000], [0.9986, 0.0620], [0.9954, 0.1240], [0.9900, 0.1860], [0.9822, 0.2480], [0.9730, 0.3100], [0.9600, 0.3720], [0.9427, 0.4340], [0.9216, 0.4958],
                                [0.8962, 0.5571], [0.8679, 0.6176], [0.8350, 0.6769], [0.7986, 0.7346], [0.7597, 0.7903], [0.7186, 0.8435], [0.6732, 0.8936], [0.6213, 0.9394], [0.5722, 0.9761], [0.5322, 1.0000]];
    let mut out = K; let mut i = 0;
    while i < 20 { out[i][1] = K[i][1] * 1.593415793900743; i += 1; }
    out
};

const A1: f64 = 1.340264; const A2: f64 = -0.081106; const A3: f64 = 0.000893; const A4: f64 = 0.003796;

#[inline]
fn aitoff(x: f64, y: f64) -> P2 {
    let cosy = y.cos(); let x = x / 2.0;
    let sincia = sinci(acos(cosy * x.cos()));
    [2.0 * cosy * x.sin() * sincia, y.sin() * sincia]
}

#[inline]
fn mollweide_theta(cp: f64, mut phi: f64) -> f64 {
    let cpsin = cp * phi.sin(); let mut i = 30;
    loop {
        let delta = (phi + phi.sin() - cpsin) / (1.0 + phi.cos());
        phi -= delta;
        i -= 1;
        if !(delta.abs() > EPSILON && i > 0) { break; }
    }
    phi / 2.0
}

/// the raw projection: rotated (lambda, phi) in radians -> unit coordinates
#[inline]
pub fn raw(kind: Kind, lambda: f64, phi: f64) -> P2 {
    match kind {
        Kind::Orthographic => [phi.cos() * lambda.sin(), phi.sin()],
        Kind::EqualEarth => {
            let m = 3f64.sqrt() / 2.0;
            let l = asin(m * phi.sin()); let l2 = l * l; let l6 = l2 * l2 * l2;
            [lambda * l.cos() / (m * (A1 + 3.0 * A2 * l2 + l6 * (7.0 * A3 + 9.0 * A4 * l2))), l * (A1 + A2 * l2 + l6 * (A3 + A4 * l2))]
        }
        Kind::NaturalEarth1 => {
            let phi2 = phi * phi; let phi4 = phi2 * phi2;
            [lambda * (0.8707 - 0.131979 * phi2 + phi4 * (-0.013791 + phi4 * (0.003971 * phi2 - 0.001529 * phi4))),
             phi * (1.007226 + phi2 * (0.015085 + phi4 * (-0.044475 + 0.028874 * phi2 - 0.005916 * phi4)))]
        }
        Kind::Robinson => {
            let i = (phi.abs() * 36.0 / PI).min(18.0);
            let i0 = i.floor(); let di = i - i0; let i0 = i0 as usize;
            let (ax, ay) = (ROBINSON[i0][0], ROBINSON[i0][1]);
            let (bx, by) = (ROBINSON[i0 + 1][0], ROBINSON[i0 + 1][1]);
            let c = (i0 + 2).min(19); let (cx, cy) = (ROBINSON[c][0], ROBINSON[c][1]);
            [lambda * (bx + di * (cx - ax) / 2.0 + di * di * (cx - 2.0 * bx + ax) / 2.0), sign(phi) * (by + di * (cy - ay) / 2.0 + di * di * (cy - 2.0 * by + ay) / 2.0)]
        }
        Kind::Mercator => [lambda, ((HALF_PI + phi) / 2.0).tan().ln()],
        Kind::Equirectangular => [lambda, phi],
        Kind::AzimuthalEqualArea => {
            let cx = lambda.cos(); let cy = phi.cos();
            let k = sqrt(2.0 / (1.0 + cx * cy));
            if k == f64::INFINITY { return [2.0, 0.0]; }
            [k * cy * lambda.sin(), k * phi.sin()]
        }
        Kind::Winkel3 => { let c = aitoff(lambda, phi); [(c[0] + lambda / HALF_PI) / 2.0, (c[1] + phi) / 2.0] }
        Kind::Mollweide => {
            let sqrt2 = 2f64.sqrt(); let (cx, cy, cp) = (sqrt2 / HALF_PI, sqrt2, PI);
            let t = mollweide_theta(cp, phi);
            [cx * lambda * t.cos(), cy * t.sin()]
        }
    }
}

/// d3's scaleTranslate after recenter: unit coordinates -> the screen (k the scale, dx/dy the translation that puts
/// project(0, 0) at the translate point)
#[derive(Clone, Copy, Debug)]
pub struct Transform { pub kind: Kind, pub k: f64, pub dx: f64, pub dy: f64 }

impl Transform {
    pub fn new(kind: Kind, k: f64, tx: f64, ty: f64) -> Transform {
        let c = raw(kind, 0.0, 0.0);   // (recenter: the centre [0, 0] projected, scaled, and the translation set off by it)
        let center = [k * c[0], -k * c[1]];
        Transform { kind, k, dx: tx - center[0], dy: ty - center[1] }
    }
    /// projectTransform: rotated radians -> screen
    #[inline]
    pub fn project(&self, lambda: f64, phi: f64) -> P2 {
        let p = raw(self.kind, lambda, phi);
        [self.dx + self.k * p[0], self.dy - self.k * p[1]]
    }
}
