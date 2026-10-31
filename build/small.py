"""THE SMALL COPIES: data/small/*.txt, data/xsmall/*.txt -- every line layer again with less detail, for the map's small
scales (index.html draws from the coarsest copy still as fine as a pixel). Only the lines: a row is its place in the full
file (`row`) and its arcs -- what it is called and all the rest is read from the full file.

    .venv/bin/python build/small.py [SIZE ...]       # data/*.txt -> data/SIZE/*.txt (default: every one of SIZES)

Each size is a row of build/config.py SIZES:
  * NO SPECKS: a ring of less than `min_km2` (an island, a lake, an enclave, a hole) goes -- a polygon with its outer
    ring -- and a line with it where it was that ring's coast. A ring is the same arcs in each polygon it bounds, so an
    enclave goes from both: the hole and the land in it. A row left without a shape is not written.
  * FEWER ROWS: of a layer of lines, what the map shows from further in than the copy is used (ROW_LIMITS).
  * LONGER ARCS: where only two arcs meet and every line and ring that takes one goes on into the other (the island
    or the border whose line ended there gone), they are made one, so the point between them can go too.
  * FEWER POINTS: each arc simplified again as build/lite.py does (Visvalingam-Whyatt), a point left out when it
    stands less than `grid_km` off the line between its neighbours and makes a triangle under `grid_km` squared with
    them. An arc's ends stay, so a border still meets the coast.
  * A COARSER GRID: the points put on a grid of `decimals` decimals of a degree (`grid 0.01 -180 -90`), and a point
    that falls on the one before it, or steps back to the one before that, left out. An arc that is all on one point
    goes -- and a ring then under `min_km2` on its new points, as above, or turned the other way round (simplified
    into a figure eight: a map on the globe would fill all the rest of it). Then the arcs are merged and simplified once
    more, where that left two of them meeting alone.

TOGETHER. The world's copy is made first, and the layers on its lines go by what it kept, so a shared line stays one line
at every size. Where a line of bio.txt or history.txt runs along the world's, it has exactly the points the world's copy
kept there, and takes them as a stretch of its arcs (`uses world`, build/lite.py); a node of theirs on such a line, where
the world's copy has no point, moves to the nearest point it has -- for every arc that meets there, so they still meet.
Only their own lines are simplified. The rivers keep their own lines, but a river's end on the world's lines (its mouth)
moves the same way.

RINGS AS THE GLOBE'S CLIP WANTS THEM. A ring that comes back to a point (a narrow bay or spit closed by the grid: A B A),
a long edge along a parallel or a ring there and back up the seam, a ring of no area or turned inside out: the clip takes
such a polygon for all the sphere round it. So every ring, of the full files as well, is mended here (mend(): the rules
index.html's keepPolygons has for what it merges at run time): an arc is cut where a ring leaves it, a spike goes, a loop
is a ring of its own -- a polygon, or wound the other way a hole -- still of the file's arcs, and an edge along a parallel or
up the seam gets the points it needs. The page reads polygons as they are.
"""
import os, sys, csv, io, math, re, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SIZES, ROW_LIMITS
from lite import keep_points, KM_LAT, ROOT

ALL = ["world", "bio", "history", "rivers", "transport", "roads", "pipelines"]   # (the world first: the others go by its copy)
ON_WORLD = {"bio", "history"}                           # (run along the world's lines: only their own lines simplified)
ENDS_ON_WORLD = {"rivers"}                              # (only meet them, at their ends)
csv.field_size_limit(sys.maxsize)                       # (a continent's arcs are one long field)
ix = lambda a: a if a >= 0 else ~a                      # (an arc's index, whichever way it is followed)


def read(path, base=None):
    """a light file -> ((scale, x0, y0), its arcs as absolute grid points, its sections [(head, CSV rows)]);
    base: the arcs of the file it takes stretches of, when it does"""
    grid, arcs, sections, w = None, [], [], 0
    for line in open(path, encoding="utf-8").read().split("\n"):
        if not line or line[0] == "#":
            continue
        if line.startswith("grid "):
            grid = tuple(float(v) for v in line[5:].split())
        elif line.startswith("uses "):
            if base is None:
                raise SystemExit(f"{path} takes stretches of {line[5:]}.txt's lines: read without them")
        elif line[0] == "@":
            sections.append((line[1:].split(" "), []))
        elif sections[-1][0][0] == "arcs":
            if ":" not in line:
                arcs.append(np.cumsum(np.array(line.split(), dtype=np.int64).reshape(-1, 2), axis=0))
                continue
            n, a, i = line.split(), [], 0
            def to(p):
                if not a or a[-1] != p:
                    a.append(p)
            while i < len(n):
                if ":" in n[i]:
                    dw, k, dk = map(int, n[i].split(":"))
                    w += dw
                    for j in range(abs(dk) + 1):
                        to(tuple(base[w][k + j * (1 if dk > 0 else -1)].tolist()))
                elif not a:
                    a.append((int(n[i]), int(n[i + 1]))); i += 1
                else:
                    to((a[-1][0] + int(n[i]), a[-1][1] + int(n[i + 1]))); i += 1
                i += 1
            arcs.append(np.array(a + a[-1:] if len(a) == 1 else a, dtype=np.int64))
        else:
            sections[-1][1].append(line)
    return grid, arcs, [(h, list(csv.reader(ls))) for h, ls in sections if h[0] != "arcs" and not h[0].endswith(".fix")]


def clean(g):
    """grid points -> without repeats and steps straight back (A B A -> A), its ends kept; None when one point is left"""
    out = []
    for p in map(tuple, g.tolist()):
        if out and p[:2] == out[-1][:2]:
            continue
        if len(out) >= 2 and p[:2] == out[-2][:2]:
            out.pop()
            continue
        out.append(p)
    return np.array(out, dtype=np.int64) if len(out) >= 2 else None


def prune(shapes, kinds, pts, min_km2, turn=None):
    """the rings under min_km2 (on pts: degrees, None for an arc gone) left out -- and those turned the other way round
    from what `turn` says they were (simplified into a figure eight) -- and the lines where they were their coast; arcs
    gone left out of what is left -> (shapes, which way round each ring of them is: {(row, polygon, ring): +-1})"""
    def area_km2(ring):                                 # (signed: + counterclockwise)
        p = np.vstack([pts[a] if a >= 0 else pts[~a][::-1] for a in ring])
        x, y = p[:, 0] * KM_LAT * np.cos(np.radians(p[:, 1])), p[:, 1] * KM_LAT
        return (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2
    live = lambda a: pts[ix(a)] is not None
    kept, gone, out, way = set(), set(), {}, {}
    for key, s in shapes.items():                       # (the polygons first: their rings decide the lines')
        if kinds[key] != "polygon":
            continue
        polys = []
        for pi, poly in enumerate(s):
            rings = []
            for k, ring in enumerate(poly):
                rest = [a for a in ring if live(a)]
                a = area_km2(rest) if rest else 0.0
                if abs(a) >= min_km2 and (turn is None or np.sign(a) == turn[key, pi, k]):
                    way[key, len(polys), len(rings)] = np.sign(a)
                    rings.append(rest); kept.update(map(ix, rest))
                else:
                    gone.update(map(ix, ring))
                    if k == 0:                          # (the outer ring gone: the polygon, its holes with it)
                        gone.update(ix(a) for hole in poly[1:] for a in hole)
                        break
            else:
                polys.append(rings)
        out[key] = polys
    lost = gone - kept
    for key, s in shapes.items():                       # (a line: its arcs left, broken where a speck's coast went)
        if kinds[key] != "line":
            continue
        lines = []
        for line in s:
            cur = []
            for a in line:
                if ix(a) in lost:
                    cur and lines.append(cur); cur = []
                elif live(a):
                    cur.append(a)
            cur and lines.append(cur)
        out[key] = lines
    return out, way


def merge(shapes, kinds, arcs):
    """arcs that always run on into each other made one: at a node of two arc ends, of two arcs, crossed by every line
    and ring that takes either -> (shapes, arcs) anew"""
    end = lambda a, last: tuple(arcs[ix(a)][-1 if (a >= 0) == last else 0][:2].tolist())      # (a step's first / last point)
    def stitch(lines):                                  # (a row's lines joined where two of them, and only two, meet:
        at = collections.defaultdict(list)              #  the coast and the borders are stored an arc a line)
        for i, q in enumerate(lines):
            at[end(q[0], False)].append((i, 0)); at[end(q[-1], True)].append((i, 1))
        link = {}
        for e in at.values():
            if len(e) == 2 and e[0][0] != e[1][0]:
                link[e[0]], link[e[1]] = e[1], e[0]
        out, seen = [], set()
        def walk(i, fwd):
            q = []
            while i not in seen:
                seen.add(i); q += lines[i] if fwd else [~a for a in reversed(lines[i])]
                o = link.get((i, 1 if fwd else 0))
                if o is None:
                    break
                i, fwd = o[0], o[1] == 0
            return q
        for i in range(len(lines)):
            for e in (0, 1):
                if i not in seen and (i, e) not in link:
                    out.append(walk(i, e == 0))
        return out + [walk(i, True) for i in range(len(lines)) if i not in seen]
    shapes = {k: stitch(s) if kinds[k] == "line" else s for k, s in shapes.items()}
    seqs = [(ring, True) for k, s in shapes.items() if kinds[k] == "polygon" for poly in s for ring in poly] + \
           [(line, False) for k, s in shapes.items() if kinds[k] == "line" for line in s]
    ends, occ, cross = collections.defaultdict(list), collections.Counter(), collections.Counter()
    for a in {ix(a) for q, _ in seqs for a in q}:
        ends[tuple(arcs[a][0][:2].tolist())].append((a, 0)); ends[tuple(arcs[a][-1][:2].tolist())].append((a, 1))
    for q, ring in seqs:
        occ.update(map(ix, q))
        for i in range(len(q) if ring else len(q) - 1):
            cross[end(q[i], True)] += 1
    through = {n for n, e in ends.items() if len(e) == 2 and e[0][0] != e[1][0] and occ[e[0][0]] == occ[e[1][0]] == cross[n]}
    nxt = {}                                            # (an arc's end at such a node -> the other arc's end there)
    for n in through:
        (a, i), (b, j) = ends[n]
        nxt[a, i], nxt[b, j] = (b, j), (a, i)
    chains, seen = [], set()
    def walk(a, fwd):                                   # (from arc a, its way fwd, on through the nodes passed)
        chain = []
        while a not in seen:
            seen.add(a); chain.append((a, fwd))
            o = nxt.get((a, 1 if fwd else 0))
            if o is None:
                break
            a, fwd = o[0], o[1] == 0
        return chain
    for a in sorted(occ):                               # (the chains with ends first -- then the rings all passed)
        for i in (0, 1):
            if a not in seen and (a, i) not in nxt:
                chains.append(walk(a, i == 0))
    for a in sorted(occ):
        if a not in seen:
            chains.append(walk(a, True))
    at, new = {}, []
    for c, chain in enumerate(chains):
        for k, (a, fwd) in enumerate(chain):
            at[a] = (c, k, fwd)
        new.append(np.vstack([arcs[a] if fwd else arcs[a][::-1] for a, fwd in chain][:1] +
                             [(arcs[a] if fwd else arcs[a][::-1])[1:] for a, fwd in chain[1:]]))
    def opens(a):                                       # (the step a, its chain's first -> the chain, signed, else None)
        c, k, fwd = at[ix(a)]
        on = fwd == (a >= 0)
        return (c if on else ~c) if k == (0 if on else len(chains[c]) - 1) else None
    def redo(q, ring):
        if ring:                                        # (a ring turned to begin where a chain does)
            i = next((i for i, a in enumerate(q) if opens(a) is not None), 0)
            q = q[i:] + q[:i]
        return [c for c in map(opens, q) if c is not None]
    out = {}
    for k, s in shapes.items():
        out[k] = [[redo(r, True) for r in poly] for poly in s] if kinds[k] == "polygon" else [redo(l, False) for l in s]
    return out, new


def rows_of(sections):
    """each row's shape -> ({(section, row): polygons of rings, or lines, of signed arcs}, {(section, row): its kind})"""
    kinds_by = {h[0]: h[1] for h, _ in sections if len(h) > 1}
    shapes, kinds = {}, {}
    for si, (h, rows) in enumerate(sections):
        if "arcs" not in rows[0]:
            continue
        col, kind = rows[0].index("arcs"), kinds_by[h[0][:-7] if h[0].endswith(".pieces") else h[0]]
        for ri, r in enumerate(rows[1:]):
            text = r[col]
            shapes[si, ri] = ([[[int(a) for a in ring.split()] for ring in poly.split(";")] for poly in filter(None, text.split("|"))]
                              if kind == "polygon" else [[int(a) for a in line.split()] for line in filter(None, text.split(";"))])
            kinds[si, ri] = kind
    return shapes, kinds


def ring_area(p):
    """d3.geoArea of a ring or rings ([points in degrees]) as one polygon"""
    total = 0.0
    for q in p:
        r = np.radians(q)
        la, f = r[:, 0], r[:, 1] / 2 + math.pi / 4
        d = np.diff(la); sg, c = np.sign(d), np.abs(d)
        k = np.sin(f[:-1]) * np.sin(f[1:])
        total += np.arctan2(k * sg * np.sin(c), np.cos(f[:-1]) * np.cos(f[1:]) + k * np.cos(c)).sum()
    return 2 * (total + 2 * math.pi if total < 0 else total)


def inside(pt, ring):
    """a point in a ring, on the plate (only to find which polygon a hole of a mended ring is in)"""
    x, y, c = pt[0], pt[1], False
    a, b = ring[:-1], ring[1:]
    hit = (a[:, 1] > y) != (b[:, 1] > y)
    return bool(np.count_nonzero(x < a[hit, 0] + (y - a[hit, 1]) * (b[hit, 0] - a[hit, 0]) / (b[hit, 1] - a[hit, 1])) % 2)


def mend(shapes, kinds, arcs, scale, t0, min_km2=0.0):
    """every polygon's rings as the globe's clip wants them (see the top) -> (shapes, arcs) anew; arcs: grid points, and
    what else a point carries in further columns"""
    X = int(round(360 / scale)); Y = int(round(180 / scale))
    arcs = list(arcs)
    deg = lambda q: q[:, :2] * scale + t0
    extra = next((q.shape[1] - 2 for q in arcs if q is not None), 0)
    used = {ix(a) for k, s in shapes.items() if kinds[k] == "polygon" for poly in s for ring in poly for a in ring}
    # an edge along a parallel: its points, as far apart as a view can tell
    far = 10 / scale
    for a in used:
        q = arcs[a]
        dx = np.abs(np.diff(q[:, 0]))
        if ((np.diff(q[:, 1]) == 0) & (dx > far) & (dx < X / 2)).any():
            out = [q[:1]]
            for i in range(1, len(q)):
                d = q[i, 0] - q[i - 1, 0]
                n = int(math.ceil(abs(d) * scale / 5)) if q[i, 1] == q[i - 1, 1] and far < abs(d) < X / 2 else 1
                for j in range(1, n):
                    out.append(np.array([[q[i - 1, 0] + int(round(d * j / n)), q[i, 1], *([-1] * extra)]], dtype=np.int64))
                out.append(q[i:i + 1])
            arcs[a] = np.vstack(out)
    # a ring along the seam, there and back with different points: each stretch cut at the other's
    def points(ring):
        return np.vstack([arcs[a] if a >= 0 else arcs[~a][::-1] for a in ring])
    add = collections.defaultdict(set)
    for k, s in shapes.items():
        if kinds[k] != "polygon":
            continue
        for poly in s:
            for ring in poly:
                p = points(ring)
                on = (p[:, 0] == 0) | (p[:, 0] == X)
                if not on.any():
                    continue
                ys = np.unique(p[on, 1])
                if len(ys) < 3:
                    continue
                for a in map(ix, ring):
                    q = arcs[a]
                    for i in range(1, len(q)):
                        if q[i, 0] in (0, X) and q[i - 1, 0] in (0, X) and q[i, 1] != q[i - 1, 1]:
                            lo, hi = sorted((q[i, 1], q[i - 1, 1]))
                            add[a, i].update(int(y) for y in ys if lo < y < hi)
    for a in {a for a, _ in add}:
        q, out = arcs[a], []
        for i in range(len(q)):
            if i and add.get((a, i)):
                ys = sorted(add[a, i], reverse=q[i, 1] < q[i - 1, 1])
                out.extend([q[i, 0], y, *([-1] * extra)] for y in ys)
            out.append(q[i].tolist())
        arcs[a] = np.array(out, dtype=np.int64)
    # the loops of a ring: edges (arc, from, to), one place come back to closing a loop
    place = lambda p: (0 if p[1] in (0, Y) else 0 if p[0] == X else int(p[0]), int(p[1]))
    def loops_of(ring):
        edges = []
        for sa in ring:
            a = ix(sa); n = len(arcs[a])
            edges += [(a, k, k + 1) for k in range(n - 1)] if sa >= 0 else [(a, k, k - 1) for k in range(n - 1, 0, -1)]
        first = arcs[edges[0][0]][edges[0][1]]
        at, st, cur, out = {place(first): 0}, [place(first)], [], []
        for e in edges:
            key = place(arcs[e[0]][e[2]])
            i = at.get(key)
            if i is None:
                at[key] = len(st); st.append(key); cur.append(e)
                continue
            loop = cur[i:] + [e]
            del cur[i:]
            for u in st[i + 1:]:
                del at[u]
            del st[i + 1:]
            if len(loop) >= 3:
                out.append(loop)
        return out
    def plain(ring):
        p = points(ring)
        keys = np.where((p[:, 1] == 0) | (p[:, 1] == Y), 0, np.where(p[:, 0] == X, 0, p[:, 0])) * (Y + 1) + p[:, 1]
        return len(np.unique(keys[:-1])) == len(keys) - 1
    new, cuts = {}, collections.defaultdict(set)            # (a row's polygons: of rings of arcs, or of loops)
    of_loop = lambda loop: np.vstack([arcs[loop[0][0]][loop[0][1]][None]] + [arcs[e[0]][e[2]][None] for e in loop])[:, :2]
    for key, s in shapes.items():
        if kinds[key] != "polygon":
            continue
        polys = []
        for poly in s:
            if all(plain(r) for r in poly):
                pts = [deg(points(r)) for r in poly]
                if len(pts[0]) < 4 or ring_area(pts) > 2 * math.pi:
                    continue
                polys.append(poly)
                continue
            rings = [l for r in poly for l in loops_of(r)]
            pts = [deg(of_loop(l)) for l in rings]
            out = sorted(((ring_area([p]), i) for i, p in enumerate(pts) if ring_area([p]) <= 2 * math.pi))
            parts = [[i] for _, i in out]
            hole_of = set(range(len(rings))) - {i for _, i in out}
            for h in hole_of:
                if parts:
                    mid = pts[h][len(pts[h]) // 2]
                    next((q for q in parts if inside(mid, pts[q[0]])), parts[-1]).append(h)
            for q in parts:
                keep = [i for i in q if len(np.unique(rings_key(pts[i]), axis=0)) >= 3]
                if not keep or keep[0] != q[0]:
                    continue
                if min_km2 and ring_area([pts[q[0]]]) * 6371 ** 2 < min_km2:
                    continue
                keep = [keep[0]] + [i for i in keep[1:] if not min_km2 or (4 * math.pi - ring_area([pts[i]])) * 6371 ** 2 >= min_km2]
                if ring_area([pts[i] for i in keep]) <= 2 * math.pi:
                    polys.append([rings[i] for i in keep])
        new[key] = polys
        for poly in polys:
            for ring in poly:
                if isinstance(ring[0], tuple):              # (a loop: its arcs cut where it leaves them)
                    for j, e in enumerate(ring):
                        prev = ring[j - 1]
                        if prev[0] != e[0] or prev[2] != e[1]:
                            cuts[e[0]].add(e[1])
                            cuts[prev[0]].add(prev[2])
    pieces, out = {}, []
    for a, q in enumerate(arcs):
        if q is None:
            continue
        c = sorted(k for k in cuts.get(a, ()) if 0 < k < len(q) - 1)
        spans = list(zip([0] + c, c + [len(q) - 1]))
        pieces[a] = [(len(out) + j, u, v) for j, (u, v) in enumerate(spans)]
        out += [q[u:v + 1] for u, v in spans]
    whole = lambda sa: [p[0] for p in pieces[sa]] if sa >= 0 else [~p[0] for p in reversed(pieces[~sa])]
    def of_edges(loop):
        """a loop's edges -> its arcs (each edge in one piece; a piece's edges all there)"""
        refs = []
        for a, u, v in loop:
            for p, lo, hi in pieces[a]:
                if lo <= min(u, v) and max(u, v) <= hi:
                    r = p if v > u else ~p
                    if not refs or refs[-1] != r:
                        refs.append(r)
                    break
        if len(refs) > 1 and refs[0] == refs[-1]:
            refs.pop()
        return refs
    res = {}
    for key, s in shapes.items():
        if kinds[key] == "polygon":
            res[key] = [[of_edges(r) if isinstance(r[0], tuple) else [x for a in r for x in whole(a)] for r in poly] for poly in new[key]]
        else:
            res[key] = [[x for a in line for x in whole(a)] for line in s]
    return res, out


rings_key = lambda p: np.round(p * 1e5)


def too_far_in(sections, limits):
    """the rows of a layer of lines shown only from further in than this copy is used -> {(section, row)}"""
    out = set()
    things = {h[0]: rows for h, rows in sections if "arcs" not in rows[0]}
    for si, (h, rows) in enumerate(sections):
        name = h[0].removesuffix(".pieces")
        if "arcs" not in rows[0] or name not in limits:
            continue
        column, keep = limits[name]
        at = rows[0].index(column) if column in rows[0] else None
        by = None
        if name in things:
            T = things[name]; c = T[0].index(column) if column in T[0] else None
            by = {r[0]: (r[c] if c is not None else "") for r in T[1:]}
        for ri, r in enumerate(rows[1:]):
            v = r[at] if at is not None else ""
            if not v and by:
                v = by.get(r[0], "")
            if not keep(float(v or 0)):
                out.add((si, ri))
    return out


class Stretches:
    """the arcs of a file others take stretches of"""
    def __init__(self, arcs):
        self.arcs = [a[:, :2] for a in arcs]
        self.at = collections.defaultdict(list)             # (a point -> [(its arc, its place on it)])
        for w, a in enumerate(self.arcs):
            for k, p in enumerate(map(tuple, a.tolist())):
                self.at[p].append((w, k))

    def text(self, q, last_w):
        """an arc's line for the file, in stretches of these where it can -> (the line, the last stretch's arc)"""
        P, n, toks, i, cur = list(map(tuple, q.tolist())), len(q), [], 0, None
        A = self.arcs
        while i < n:
            best = None
            for w, k in self.at.get(P[i], ()):
                for d in (1, -1):
                    j, kk = i, k
                    while j + 1 < n and 0 <= kk + d < len(A[w]) and P[j + 1] == tuple(A[w][kk + d].tolist()):
                        j += 1; kk += d
                    if j - i >= 2 and (best is None or j > best[1]):
                        best = (w, j, k, kk)
            if best:
                w, j, k, kk = best
                toks.append(f"{w - last_w}:{k}:{kk - k}"); last_w, cur, i = w, P[j], j + 1
            else:
                toks.append(f"{P[i][0]} {P[i][1]}" if cur is None else f"{P[i][0] - cur[0]} {P[i][1] - cur[1]}")
                cur = P[i]; i += 1
        return " ".join(toks), last_w


class Followed(Stretches):
    """what the world's copy kept: for a point of data/world.txt's, where it is in the copy"""
    def __init__(self, full, arcs, step):
        super().__init__(arcs)
        self.step = step
        coords = np.vstack(full)
        self.kept = {}                                      # (a point it kept -> its place on the copy's grid)
        for q in arcs:
            for x, y, i in q.tolist():
                self.kept[tuple(coords[i].tolist())] = (x, y)
        self.moved = {}                                     # (any other point of a line it kept some of -> the nearest it kept)
        for q in full:
            P = list(map(tuple, q.tolist()))
            on = [i for i, p in enumerate(P) if p in self.kept]
            if not on:
                continue
            for a, b in zip([None] + on, on + [None]):
                for i in range((a if a is not None else -1) + 1, b if b is not None else len(P)):
                    near = [j for j in (a, b) if j is not None]
                    j = min(near, key=lambda j: (q[j, 0] - q[i, 0]) ** 2 + (q[j, 1] - q[i, 1]) ** 2)
                    self.moved.setdefault(P[i], self.kept[P[j]])

    def line(self, q, t0, scale, grid_km, ends_only):
        """an arc of a layer on the world's lines, on the copy's grid: the world's points where it runs on them"""
        P, ll, fixed = list(map(tuple, q.tolist())), [], []
        n = len(P)
        for i, p in enumerate(P):
            at = self.kept.get(p) if not ends_only or i in (0, n - 1) else None
            if at is None and i in (0, n - 1):
                at = self.moved.get(p)
            if at is None and not ends_only and p in self.moved:
                continue                                    # (the world's copy left it out)
            ll.append(np.array(at if at is not None else p) * (self.step if at is not None else scale) + t0)
            fixed.append(at is not None)
        ll = np.array(ll)
        k = keep_points(ll, grid_km, grid_km ** 2, np.array(fixed))
        return clean(np.round((ll[k] - t0) / self.step).astype(np.int64))


def shrink(name, size, decimals, grid_km, min_km2, world_full=None, follow=None):
    src = os.path.join(ROOT, "data", name + ".txt")
    if not os.path.exists(src):
        return None
    (scale, x0, y0), arcs, sections = read(src, world_full)
    t0, step = np.array([x0, y0]), 10.0 ** -decimals
    shapes, kinds = rows_of(sections)
    for key in too_far_in(sections, ROW_LIMITS.get(size, {})):
        shapes[key] = []
    n0 = sum(len(q) for q in arcs)
    deg = lambda A, k: [None if q is None else q[:, :2] * k + t0 for q in A]
    shapes, way = prune(shapes, kinds, deg(arcs, scale), min_km2)
    if name == "world":                                 # (each point says which of the file's it is: followed to the end)
        at = np.cumsum([0] + [len(q) for q in arcs])
        arcs = [np.column_stack((q, np.arange(len(q)) + at[i])) for i, q in enumerate(arcs)]
    full = [q[:, :2] for q in arcs] if name == "world" else None
    shapes, arcs = merge(shapes, kinds, arcs)
    on = name in ON_WORLD or name in ENDS_ON_WORLD
    new = []
    for q in arcs:
        ll = q[:, :2] * scale + t0
        if follow and on:
            new.append(follow.line(q[:, :2], t0, scale, grid_km, name in ENDS_ON_WORLD))
        else:
            k = keep_points(ll, grid_km, grid_km ** 2)
            new.append(clean(np.column_stack((np.round((ll[k] - t0) / step).astype(np.int64), q[k][:, 2:]))))
    shapes, way = prune(shapes, kinds, deg(new, step), min_km2, way)
    shapes, new = merge(shapes, kinds, new)             # (once more: where an arc all on one point went, or a speck's line)
    if not (follow and name in ON_WORLD):               # (the world's points stay what the world's copy made them)
        new = [clean(q[keep_points(q[:, :2] * step + t0, grid_km, grid_km ** 2)]) for q in new]
    shapes, way = prune(shapes, kinds, deg(new, step), min_km2, way)
    shapes, new = merge(shapes, kinds, new) if name in ON_WORLD else (shapes, new)
    if any(k == "polygon" for k in kinds.values()):
        shapes, new = mend(shapes, kinds, new, step, t0, min_km2)

    used = sorted({ix(a) for s in shapes.values() for x in s for y in x for a in (y if isinstance(y, list) else [y])})
    to = {a: i for i, a in enumerate(used)}
    re_ = lambda a: to[a] if a >= 0 else ~to[~a]
    cells = lambda kind, s: ("|".join(";".join(" ".join(str(re_(a)) for a in ring) for ring in poly) for poly in s) if kind == "polygon"
                             else ";".join(" ".join(str(re_(a)) for a in line) for line in s))
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    kind_of = {h[0]: h[1] for h, _ in sections if len(h) > 1}
    written = 0
    for si, (h, rows) in enumerate(sections):
        if "arcs" not in rows[0]:
            continue
        base = h[0].removesuffix(".pieces")
        out.write(f"@{base} {kind_of[base]}\nrow#,arcs\n")
        for ri in range(len(rows) - 1):
            if shapes[si, ri]:
                w.writerow([ri, cells(kinds[si, ri], shapes[si, ri])]); written += 1
    arc_lines, last_w = [], 0
    for a in used:
        if follow and name in ON_WORLD:
            t, last_w = follow.text(new[a][:, :2], last_w)
            arc_lines.append(t)
        else:
            d = np.vstack((new[a][:1, :2], np.diff(new[a][:, :2], axis=0)))
            arc_lines.append(" ".join(str(int(v)) for v in d.ravel()))
    head = [f"# {name}: a {size} copy of data/{name}.txt (points on a grid of {decimals} decimals, those off by less than "
            f"{grid_km:g} km and in triangles under {grid_km ** 2:g} km2 left out, rings under {min_km2:g} km2 too; build/small.py)",
            f"grid {step:g} {x0:g} {y0:g}", *(["uses world"] if follow and name in ON_WORLD else []), "@arcs"]
    dest = os.path.join(ROOT, "data", size, name + ".txt")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write("\n".join(head + arc_lines) + "\n" + out.getvalue())
    print(f"{os.path.relpath(dest, ROOT)}: {len(used):,} arcs, {n0:,} -> {sum(len(new[a]) for a in used):,} points, {written:,} rows, "
          f"{os.path.getsize(src) / 2**20:.2f} -> {os.path.getsize(dest) / 2**20:.2f} MB", flush=True)
    if name == "world":
        return Followed(full, [new[a] for a in used], step)


def mend_full(name, old_world, world=None):
    """data/NAME.txt with its rings mended; old_world: the world's arcs its stretches were written of, world: (Stretches)
    those they are now of -> its arcs"""
    path = os.path.join(ROOT, "data", name + ".txt")
    if not os.path.exists(path):
        return None
    (scale, x0, y0), arcs, sections = read(path, old_world)
    shapes, kinds = rows_of(sections)
    if any(k == "polygon" for k in kinds.values()):
        shapes, arcs = mend(shapes, kinds, arcs, scale, np.array([x0, y0]))
    used = sorted({ix(a) for s in shapes.values() for x in s for y in x for a in (y if isinstance(y, list) else [y])})
    to = {a: i for i, a in enumerate(used)}
    re_ = lambda a: to[a] if a >= 0 else ~to[~a]
    cells = lambda kind, s: ("|".join(";".join(" ".join(str(re_(a)) for a in ring) for ring in poly) for poly in s) if kind == "polygon"
                             else ";".join(" ".join(str(re_(a)) for a in line) for line in s))
    lines, last_w = [], 0
    for a in used:
        if world:
            t, last_w = world.text(arcs[a], last_w)
            lines.append(t)
        else:
            d = np.vstack((arcs[a][:1], np.diff(arcs[a], axis=0)))
            lines.append(" ".join(str(int(v)) for v in d.ravel()))
    text = open(path, encoding="utf-8").read()
    head = text[:text.index("@arcs\n")] + "@arcs\n"
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    for si, (h, rows) in enumerate(sections):
        out.write("@" + " ".join(h) + "\n")
        col = rows[0].index("arcs") if "arcs" in rows[0] else None
        w.writerow(rows[0])
        for ri, r in enumerate(rows[1:]):
            if col is not None:
                r = list(r); r[col] = cells(kinds[si, ri], shapes[si, ri])
            w.writerow(r)
    open(path, "w", encoding="utf-8").write(head + "\n".join(lines) + "\n" + out.getvalue())
    print(f"data/{name}.txt: {len(used):,} arcs, {sum(len(arcs[a]) for a in used):,} points, {os.path.getsize(path) / 2**20:.2f} MB", flush=True)
    return [arcs[a] for a in used]


if __name__ == "__main__":
    if sys.argv[1:] == ["roads"]:                            # (of their own: the other files are as they were)
        mend_full("roads", None)
        for size in SIZES:
            shrink("roads", size, **SIZES[size], world_full=None, follow=None)
        sys.exit()
    old_world = read(os.path.join(ROOT, "data", "world.txt"))[1]
    world_full = mend_full("world", old_world)
    lines = Stretches(world_full)
    for name in ALL[1:]:
        mend_full(name, old_world, lines if name in ON_WORLD else None)
    for size in sys.argv[1:] or list(SIZES):
        follow = None
        for name in ALL:
            r = shrink(name, size, **SIZES[size], world_full=world_full, follow=follow)
            follow = r or follow
