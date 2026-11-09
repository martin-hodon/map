//! A native check against the page's own output: fixtures/<name>/ written by fixture.mjs (node, d3 and parseLite) --
//! the lines, an object's rows, the projection's numbers and the command stream d3 gave -- run through mapgeo and compared.
use mapgeo::pipeline::{Proj, Setup};
use mapgeo::projections::Kind;
use mapgeo::trace::{Lines, Rows};
use std::fs;

fn read_f32(p: &str) -> Vec<f32> { fs::read(p).unwrap().chunks(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect() }
fn read_i32(p: &str) -> Vec<i32> { fs::read(p).unwrap().chunks(4).map(|c| i32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect() }

fn main() {
    let dir = std::env::args().nth(1).expect("fixture dir");
    let xy = read_f32(&format!("{dir}/xy.f32")); let at = read_i32(&format!("{dir}/at.i32"));
    let start = read_i32(&format!("{dir}/start.i32")); let refs = read_i32(&format!("{dir}/refs.i32"));
    let ids = read_i32(&format!("{dir}/ids.i32")); let want = read_f32(&format!("{dir}/expected.f32"));
    // params: kind lambda phi gamma k tx ty clip has_extent x0 y0 x1 y1 delta2 polygon
    let p: Vec<f64> = fs::read_to_string(format!("{dir}/params.txt")).unwrap().split_whitespace().map(|v| v.parse().unwrap()).collect();
    let setup = Setup { kind: Kind::from_i32(p[0] as i32), rotate: [p[1], p[2], p[3]], k: p[4], tx: p[5], ty: p[6], clip_angle: p[7],
                        extent: if p[8] != 0.0 { Some([p[9], p[10], p[11], p[12]]) } else { None }, delta2: p[13] };
    let t = Lines { xy: &xy, at: &at }; let g = Rows { start: &start, refs: &refs, polygon: p[14] != 0.0 };
    let t0 = std::time::Instant::now();
    let mut proj = Proj::new(&setup);
    for &i in &ids { proj.trace(&t, &g, i as usize); }
    let ms = t0.elapsed().as_secs_f64() * 1e3;
    let got = proj.out.borrow();
    let n = got.len().min(want.len());
    let (mut bad_cmd, mut bad_xy, mut maxd) = (0usize, 0usize, 0f32);
    let mut first = None;
    for k in (0..n).step_by(3) {
        if got[k] != want[k] { bad_cmd += 1; if first.is_none() { first = Some(k); } continue; }
        if got[k] == 2.0 { continue; }
        let d = (got[k + 1] - want[k + 1]).abs().max((got[k + 2] - want[k + 2]).abs());
        if d > maxd { maxd = d; }
        if d > 0.01 { bad_xy += 1; if first.is_none() { first = Some(k); } }
    }
    println!("{dir}: {} rows, {} vs {} floats, {} cmd mismatches, {} coords off by >0.01px (max {:.4}), {ms:.1} ms",
             ids.len(), got.len(), want.len(), bad_cmd, bad_xy, maxd);
    if let Some(k) = first {
        let lo = k.saturating_sub(9);
        println!("  first mismatch at triple {}:", k / 3);
        for j in (lo..(k + 12).min(n)).step_by(3) { println!("    got {:>3} {:>10.3} {:>10.3}   want {:>3} {:>10.3} {:>10.3}", got[j], got[j+1], got[j+2], want[j], want[j+1], want[j+2]); }
    }
    if got.len() != want.len() || bad_cmd > 0 || bad_xy > 0 { std::process::exit(1); }
}
