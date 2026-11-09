//! d3-geo's rotation.js: the three-angle rotation of the sphere (radians in, radians out), composed exactly as d3
//! composes it -- lambda alone, phi-gamma alone, both, or none -- so that the same inputs give the same floats.
use crate::math::*;

#[derive(Clone, Copy, Debug)]
pub enum Rotation {
    Identity,
    Lambda(f64),
    PhiGamma { cp: f64, sp: f64, cg: f64, sg: f64 },
    Both { dl: f64, cp: f64, sp: f64, cg: f64, sg: f64 },
}

impl Rotation {
    /// rotateRadians(deltaLambda, deltaPhi, deltaGamma)
    pub fn new(delta_lambda: f64, delta_phi: f64, delta_gamma: f64) -> Rotation {
        let dl = delta_lambda % TAU;
        let pg = delta_phi != 0.0 || delta_gamma != 0.0;
        let (cp, sp, cg, sg) = (delta_phi.cos(), delta_phi.sin(), delta_gamma.cos(), delta_gamma.sin());
        if dl != 0.0 {
            if pg { Rotation::Both { dl, cp, sp, cg, sg } } else { Rotation::Lambda(dl) }
        } else if pg { Rotation::PhiGamma { cp, sp, cg, sg } } else { Rotation::Identity }
    }
    #[inline]
    fn lambda(dl: f64, lambda: f64) -> f64 {
        let l = lambda + dl;
        if l.abs() > PI { l - js_round(l / TAU) * TAU } else { l }
    }
    #[inline]
    fn phi_gamma(cp: f64, sp: f64, cg: f64, sg: f64, lambda: f64, phi: f64) -> P2 {
        let cos_phi = phi.cos();
        let x = lambda.cos() * cos_phi;
        let y = lambda.sin() * cos_phi;
        let z = phi.sin();
        let k = z * cp + x * sp;
        [(y * cg - k * sg).atan2(x * cp - z * sp), asin(k * cg + y * sg)]
    }
    #[inline]
    pub fn apply(&self, lambda: f64, phi: f64) -> P2 {
        match *self {
            Rotation::Identity => [if lambda.abs() > PI { lambda - js_round(lambda / TAU) * TAU } else { lambda }, phi],
            Rotation::Lambda(dl) => [Rotation::lambda(dl, lambda), phi],
            Rotation::PhiGamma { cp, sp, cg, sg } => Rotation::phi_gamma(cp, sp, cg, sg, lambda, phi),
            Rotation::Both { dl, cp, sp, cg, sg } => { let l = Rotation::lambda(dl, lambda); Rotation::phi_gamma(cp, sp, cg, sg, l, phi) }
        }
    }
}
