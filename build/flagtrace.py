#!/usr/bin/env python3
"""flagtrace.py -- an SVG path as a `poly` of data/flags.txt: its corners as shares of a box, curves flattened, the
corners thinned (Douglas-Peucker) to what still shows -- for tracing an emblem from a flag's own drawing.

  build/flagtrace.py FILE.svg                     every <path> of the file: its index, fill, size, first numbers
  build/flagtrace.py FILE.svg 3 5 [--tol 0.002]   paths 3 and 5 as one poly (outlines joined by /), in the shares of
                                                  the file's viewBox (a whole flag's: x of the width, y of the height)
      --box x0,y0,x1,y1   in the shares of this box instead (a motif's own 1:1 box: an emblem drawn as `@name`)
      --tol t             how far (in shares) a thinned outline may stray from the drawn one (default 0.0015)
      --flipx             mirrored left to right (the other of a pair)

Paths only (no <use>, no transforms but a plain translate on the path itself): enough for the flags' emblems, which
are drawn as paths. Arcs (A) are taken as straight lines.
"""
import re, sys, math, xml.etree.ElementTree as ET

def tokens(d):
    for m in re.finditer(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d):
        yield m.group(0)

def outlines(d, steps=12):
    """the path's subpaths as lists of (x, y), curves flattened into `steps` pieces"""
    out, cur, x, y, sx, sy, cmd, last_c = [], [], 0.0, 0.0, 0.0, 0.0, None, None
    toks, i = list(tokens(d)), 0
    def num():
        nonlocal i
        i += 1
        return float(toks[i - 1])
    def bez(p0, p1, p2, p3):
        for k in range(1, steps + 1):
            t = k / steps; u = 1 - t
            cur.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                        u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                if cur: out.append(cur); cur = []
                x, y = sx, sy; last_c = None
                continue
        rel = cmd.islower(); C = cmd.upper(); ox, oy = (x, y) if rel else (0, 0)
        if C == "M":
            if cur: out.append(cur)
            x, y = num() + ox, num() + oy; sx, sy = x, y; cur = [(x, y)]
            cmd = "l" if rel else "L"; last_c = None
        elif C == "L": x, y = num() + ox, num() + oy; cur.append((x, y)); last_c = None
        elif C == "H": x = num() + (x if rel else 0); cur.append((x, y)); last_c = None
        elif C == "V": y = num() + (y if rel else 0); cur.append((x, y)); last_c = None
        elif C == "C":
            p1 = (num() + ox, num() + oy); p2 = (num() + ox, num() + oy); p3 = (num() + ox, num() + oy)
            bez((x, y), p1, p2, p3); x, y = p3; last_c = p2
        elif C == "S":
            p1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            p2 = (num() + ox, num() + oy); p3 = (num() + ox, num() + oy)
            bez((x, y), p1, p2, p3); x, y = p3; last_c = p2
        elif C == "Q":
            q = (num() + ox, num() + oy); p3 = (num() + ox, num() + oy)
            bez((x, y), (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y)), (p3[0] + 2 / 3 * (q[0] - p3[0]), p3[1] + 2 / 3 * (q[1] - p3[1])), p3)
            x, y = p3; last_c = None
        elif C == "A":
            for _ in range(5): num()
            x, y = num() + ox, num() + oy; cur.append((x, y)); last_c = None
        else: raise SystemExit(f"flagtrace: no command {cmd!r}")
    if cur: out.append(cur)
    return out

def thin(pts, tol):
    """Douglas-Peucker: the fewest corners within `tol` of the outline"""
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]; n = math.hypot(dx, dy) or 1e-12
    far, at = -1, 0
    for k in range(1, len(pts) - 1):
        d = abs((pts[k][0] - a[0]) * dy - (pts[k][1] - a[1]) * dx) / n if n > 1e-12 else math.hypot(pts[k][0] - a[0], pts[k][1] - a[1])
        if d > far: far, at = d, k
    if far <= tol: return [a, b]
    return thin(pts[:at + 1], tol)[:-1] + thin(pts[at:], tol)

def short(v):
    """a share in three decimals, without the leading 0: .125, -.04, 1"""
    t = f"{v:.3f}".rstrip("0").rstrip(".")
    return re.sub(r"^(-?)0\.", r"\1.", t) if t not in ("", "-0") else "0"

def main():
    args = sys.argv[1:]
    if not args: raise SystemExit(__doc__)
    tol, box, flipx = 0.0015, None, False
    if "--tol" in args: k = args.index("--tol"); tol = float(args[k + 1]); del args[k:k + 2]
    if "--box" in args: k = args.index("--box"); box = [float(v) for v in args[k + 1].split(",")]; del args[k:k + 2]
    if "--flipx" in args: args.remove("--flipx"); flipx = True
    root = ET.parse(args[0]).getroot()
    vb = [float(v) for v in re.split(r"[ ,]+", root.get("viewBox").strip())] if root.get("viewBox") else [0, 0, float(re.sub(r"[a-z]+$", "", root.get("width"))), float(re.sub(r"[a-z]+$", "", root.get("height")))]
    paths = [p for p in root.iter() if p.tag.endswith("path")]
    if len(args) == 1:
        for k, p in enumerate(paths):
            pts = [q for o in outlines(p.get("d")) for q in o]
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            print(k, p.get("fill") or p.get("style", "")[:30], f"x {min(xs):.0f}..{max(xs):.0f} y {min(ys):.0f}..{max(ys):.0f}", (p.get("transform") or ""), p.get("d")[:50])
        return
    x0, y0, x1, y1 = box or [vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]]
    parts = []
    for k in map(int, args[1:]):
        p = paths[k]; tx = ty = 0.0
        m = re.match(r"\s*translate\(\s*([-\d.e]+)[ ,]*([-\d.e]*)\)\s*$", p.get("transform") or "")
        if m: tx, ty = float(m.group(1)), float(m.group(2) or 0)
        elif p.get("transform"): print(f"# path {k}: transform {p.get('transform')} ignored", file=sys.stderr)
        for o in outlines(p.get("d")):
            o = [((px + tx - x0) / (x1 - x0), (py + ty - y0) / (y1 - y0)) for px, py in o]
            if flipx: o = [(1 - px, py) for px, py in o]
            if len(o) > 2 and o[0] == o[-1]: o = o[:-1]
            o = thin(o + [o[0]], tol)[:-1]
            if len(o) >= 3: parts.append(" ".join(f"{short(px)},{short(py)}" for px, py in o))
    print("poly " + " / ".join(parts))

if __name__ == "__main__":
    main()
