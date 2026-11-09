//! The whole projection as the page sets it up (geom.js setup): rotation, pre-clip (the antimeridian, or a circle for
//! the globe and the azimuthal), resampling with the projection, the Mercator extent, the sink -- built once, rows run
//! through it, the canvas commands collected in one buffer.
use crate::clip::{Antimeridian, Circle, Clip, Rectangle};
use crate::math::*;
use crate::projections::{Kind, Transform};
use crate::rotation::Rotation;
use crate::stream::{Resample, Rotate, Sink, Stream};
use crate::trace::{self, Lines, Rows};
use std::cell::RefCell;
use std::rc::Rc;

pub struct Setup {
    pub kind: Kind, pub rotate: [f64; 3], pub k: f64, pub tx: f64, pub ty: f64,
    pub clip_angle: f64,                    // (degrees; 0: the antimeridian cut)
    pub extent: Option<[f64; 4]>,           // (Mercator's: given, or None for its own from k and translate)
    pub delta2: f64,                        // (precision squared: 0.25)
}

pub struct Proj { pub chain: Box<dyn Stream>, pub out: Rc<RefCell<Vec<f32>>> }

impl Proj {
    pub fn new(s: &Setup) -> Proj {
        let out = Rc::new(RefCell::new(Vec::new()));
        let mut sink: Box<dyn Stream> = Box::new(Sink::new(out.clone()));
        if s.kind == Kind::Mercator {
            let [x0, y0, x1, y1] = s.extent.unwrap_or_else(|| { let k = PI * s.k; [s.tx - k, s.ty - k, s.tx + k, s.ty + k] });
            sink = Box::new(Rectangle::new(x0, y0, x1, y1, sink));
        }
        let resample: Box<dyn Stream> = Box::new(Resample::new(Transform::new(s.kind, s.k, s.tx, s.ty), s.delta2, sink));
        let clipped: Box<dyn Stream> = if s.clip_angle > 0.0 { Box::new(Clip::new(Circle::new(s.clip_angle * RADIANS), resample)) }
                                       else { Box::new(Clip::new(Antimeridian, resample)) };
        let rot = Rotation::new(s.rotate[0] * RADIANS, s.rotate[1] * RADIANS, s.rotate[2] * RADIANS);
        Proj { chain: Box::new(Rotate { rot, next: clipped }), out }
    }
    pub fn clear(&self) { self.out.borrow_mut().clear(); }
    pub fn trace(&mut self, t: &Lines, g: &Rows, row: usize) { trace::trace(&mut *self.chain, t, g, row); }
    pub fn trace_arcs(&mut self, t: &Lines, arcs: &[i32]) { trace::trace_arcs(&mut *self.chain, t, arcs); }
}
