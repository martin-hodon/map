"""STAGE 4b -- THE RIVER NETWORK: the rivers as tracked (water.py: each river's pieces, full/rivers.tracked.topo.json)
made into one network of single lines -> full/rivers.topo.json; and their mouths into the coast (full/world.topo.json).

    .venv/bin/python build/rivernet.py            (after water.py and write.py; then build/lite.py)

A river as tracked is every channel OSM maps of it: a braided river is hundreds of lines side by side (the Diamantina
was 9,398), a river through its floodplain has its side arms, and two rivers sharing a valley run for kilometres a
stone's throw apart. Drawn, that is a band of lines where there is one river. So:

TRUNK. A river's pieces are a graph (their ends the nodes). Of its biggest connected part, the trunk is the way between
its two ends farthest apart (Dijkstra twice) -- the river once through its braids -- one line, following the flow. (Of
a smaller part, cut off from the rest, that way is just another piece.)

ONE LINE FOR ONE WATER. The trunks go first, the longest rivers first, then the rest of the pieces (the longest
first). A stretch of a line closer than SEP_KM to a line kept before is the same water: dropped where that runs on for
PARALLEL_KM, or at an end of the line that does not reach the other (a braid's or a side arm's end). The rest is kept
-- of a trunk any piece of PIECE_KM or more, of the other pieces only one that runs apart for BRANCH_KM (the Little
Danube and the Moson Danube beside the Danube; not a braid). A side arm's end that then meets nothing goes on along
its river's own channels, the shortest way (up to CLOSE_KM) back to a line kept: the rest of that arm. Where a line was cut, its end is carried onto the line it
ran beside: a side arm leaves its river and comes back to it.

JOINS. A river flowing into another ends ON it: an end within TOUCH_KM of another line -- or a free mouth, or a side
arm's end, within JOIN_KM -- is carried onto that line, and that line is cut there (a junction is the end of every arc that meets it), so the
join stays exact however far the map simplifies (an arc's ends are always kept).

MOUTHS. A river that ends in the sea is cut where it crosses the coast; one that ends inland within MOUTH_KM of the coast
(and not at a lake) is carried on to it. The point on the coast is put into the coast's own line (full/world.topo.json,
on the shared grid), so river and coast meet exactly; build/lite.py keeps those points.
"""
import os, sys, json, time, heapq, collections
import numpy as np
import shapely, shapely.ops
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from write import quantize
from export_geojson import decode, ring

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TRACKED = os.path.join(ROOT, "full/rivers.tracked.topo.json")
OUT = os.path.join(ROOT, "full/rivers.topo.json")
WORLD = os.path.join(ROOT, "full/world.topo.json")
R = 6371.0
SEP_KM = 2.5         # a stretch closer than this to a line kept before is the same water
PARALLEL_KM = 4.0    # ...dropped where it runs so this long (or at an end that does not reach that line)
TOUCH_KM = 0.6       # an end this near another line meets it
JOIN_KM = 5.0        # a free downstream end this near another line flows into it
BRANCH_KM = 25.0     # a piece not of a trunk: kept only where it runs apart this long (a braid in a wide floodplain runs apart 10-20 km)
PIECE_KM = 10.0      # a trunk's piece left shorter than this: dropped
CLOSE_KM = 40.0      # a side arm's end that meets nothing: joined back along its own channels this far
MOUTH_KM = 8.0       # a free downstream end this near the coast (and not at a lake): carried on into the sea
LAKE_KM = 1.0        # ...unless a lake is this near, and nearer than the coast (not one whose shore is the coast: the Caspian)
STEP_KM = 0.5        # the samples along a line, for the distances
CELL = SEP_KM / R    # the index's cells (on the unit sphere)
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


def xyz(ll):
    lon, lat = np.radians(ll[:, 0]), np.radians(ll[:, 1])
    return np.column_stack((np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)))


def lonlat(p):
    p = np.atleast_2d(p)
    return np.column_stack((np.degrees(np.arctan2(p[:, 1], p[:, 0])), np.degrees(np.arcsin(np.clip(p[:, 2] / np.linalg.norm(p, axis=1), -1, 1)))))


def km(ll):
    return float(np.linalg.norm(np.diff(xyz(ll), axis=0), axis=1).sum() * R) if len(ll) > 1 else 0.0


def samples(ll, step=STEP_KM):
    """points every ~step km along a line -> (xyz, the segment each lies on, how far along it 0..1, km from the start)"""
    P = xyz(ll)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1) * R
    n = np.maximum(1, np.ceil(seg / step).astype(int))
    j = np.repeat(np.arange(len(seg)), n)
    t = np.concatenate([np.arange(k) / k for k in n])
    j = np.append(j, len(seg) - 1); t = np.append(t, 1.0)
    S = P[j] * (1 - t)[:, None] + P[j + 1] * t[:, None]
    along = np.concatenate(([0], np.cumsum(seg)))[j] + seg[j] * t
    return S, j, t, along


class Index:
    """the samples of the lines kept so far, by cell: which line, which of its segments"""
    def __init__(self, cell=CELL):
        self.cell = cell
        self.xyz = np.zeros((1 << 20, 3)); self.line = np.zeros(1 << 20, np.int32); self.seg = np.zeros(1 << 20, np.int32)
        self.n = 0; self.cells = collections.defaultdict(list)

    def add(self, line, S, j):
        m = len(S)
        while self.n + m > len(self.xyz):
            self.xyz = np.vstack((self.xyz, np.zeros_like(self.xyz))); self.line = np.concatenate((self.line, np.zeros_like(self.line))); self.seg = np.concatenate((self.seg, np.zeros_like(self.seg)))
        self.xyz[self.n:self.n + m] = S; self.line[self.n:self.n + m] = line; self.seg[self.n:self.n + m] = j
        for k, c in zip(range(self.n, self.n + m), map(tuple, np.floor(S / self.cell).astype(np.int64))):
            self.cells[c].append(k)
        self.n += m

    def near(self, S, reach=1, skip=-1):
        """each point's nearest kept sample within `reach` cells (not of line `skip`) -> (km, sample id; inf, -1 if none)"""
        cs = np.unique(np.floor(S / self.cell).astype(np.int64), axis=0)
        off = np.array([(a, b, c) for a in range(-reach, reach + 1) for b in range(-reach, reach + 1) for c in range(-reach, reach + 1)])
        ids = {k for c in cs for o in off for k in self.cells.get(tuple(c + o), ())}
        d, i = np.full(len(S), np.inf), np.full(len(S), -1)
        if not ids:
            return d, i
        ids = np.fromiter(ids, np.int64)
        if skip >= 0:
            ids = ids[self.line[ids] != skip]
            if not len(ids):
                return d, i
        dd, ii = cKDTree(self.xyz[ids]).query(S, distance_upper_bound=(reach * self.cell))
        ok = np.isfinite(dd)
        d[ok], i[ok] = dd[ok] * R, ids[ii[ok]]
        return d, i


def onto(ll, j, p):
    """the point of line `ll` nearest to xyz `p`, about its segment j -> (segment, how far along, lon/lat)"""
    P, best = xyz(ll), None
    for s in range(max(0, j - 2), min(len(ll) - 1, j + 3)):
        a, b = P[s], P[s + 1]; ab = b - a; L = ab @ ab
        t = 0.0 if L == 0 else float(np.clip((p - a) @ ab / L, 0, 1))
        q = a + ab * t; dist = np.linalg.norm(p - q)
        if best is None or dist < best[0]:
            best = (dist, s, t, q)
    return best[1], best[2], lonlat(best[3])[0]


def trunks(lines):
    """each river's pieces as a graph: of each connected part, the way between its two ends farthest apart, as one line
    following the flow -> [(river, trunk line, its pieces, [the other pieces])]"""
    by = collections.defaultdict(list)
    for k, (c, p) in enumerate(lines):
        by[p.get("river")].append(k)
    out = []
    for rid, ks in by.items():
        key = lambda q: (int(round(q[0] / config.QUANT_DEG)), int(round(q[1] / config.QUANT_DEG)))
        adj = collections.defaultdict(list)                  # node -> [(node, piece, forward?, km)]
        for k in ks:
            c = lines[k][0]; a, b, L = key(c[0]), key(c[-1]), km(c)
            adj[a].append((b, k, True, L)); adj[b].append((a, k, False, L))
        seen = set()
        for start in list(adj):
            if start in seen:
                continue
            def far(src):                                    # Dijkstra: the farthest node, and how each was reached
                dist, back, h = {src: 0.0}, {}, [(0.0, src)]
                while h:
                    d, u = heapq.heappop(h)
                    if d > dist[u]:
                        continue
                    for v, k, fw, L in adj[u]:
                        if d + L < dist.get(v, np.inf):
                            dist[v] = d + L; back[v] = (u, k, fw); heapq.heappush(h, (d + L, v))
                return max(dist, key=dist.get), back, dist
            a, _, dist = far(start)
            seen |= set(dist)
            b, back, _ = far(a)
            steps, v = [], b
            while v != a:
                u, k, fw = back[v]; steps.append((k, fw)); v = u
            steps.reverse()                                  # a -> b
            with_flow = sum(km(lines[k][0]) * (1 if fw else -1) for k, fw in steps)
            if with_flow < 0:                                # (the flow is b -> a)
                steps = [(k, not fw) for k, fw in reversed(steps)]
            parts = [lines[k][0] if fw else lines[k][0][::-1] for k, fw in steps]
            c = np.vstack([parts[0]] + [q[1:] for q in parts[1:]]) if parts else None
            used = {k for k, _ in steps}
            comp = {k for u in dist for _, k, _, _ in adj[u]}
            out.append((rid, c, used, sorted(comp - used, key=lambda k: -km(lines[k][0]))))
    return out


def network(lines):
    """-> the kept lines [(lon/lat, river, trunk?)], the points to put into each {line: [(segment, along, point)]}, the
    index of their samples, each river's properties, the ends carried onto a line"""
    tr = trunks(lines)
    river_km = {p.get("river"): p.get("river_km", 0) for _, p in lines}
    props = {p.get("river"): p for _, p in lines}
    # (a river's trunk: of its biggest part; another part's -- a braid's cluster cut off from the rest -- is a piece
    #  like any other, kept only where it runs apart)
    main = {}
    for rid, c, ks, _ in tr:
        if c is not None and km(c) > main.get(rid, (0,))[0]:
            main[rid] = (km(c), id(c))
    todo = [(c, rid, True, ks) for rid, c, ks, _ in sorted(tr, key=lambda x: (-river_km.get(x[0], 0), -km(x[1]) if x[1] is not None else 0))
            if c is not None and main[rid][1] == id(c)]
    todo += sorted([(c, rid, False, ks) for rid, c, ks, _ in tr if c is not None and main[rid][1] != id(c)] +
                   [(lines[k][0], rid, False, {k}) for rid, _, _, rest in tr for k in rest], key=lambda x: -km(x[0]))
    log(f"{len(lines):,} pieces of {len(props):,} rivers: {len(main):,} trunks, {len(todo) - len(main):,} other pieces (and trunks of the smaller parts)")
    idx, kept, inserts, attached, used = Index(), [], collections.defaultdict(list), set(), set()
    stats = collections.Counter()

    def snap(k_sample, from_p):                              # the point on the kept line nearest, put into it
        L = int(idx.line[k_sample]); s, t, q = onto(kept[L][0], int(idx.seg[k_sample]), from_p)
        inserts[L].append((s, t, q)); attached.add(pkey(q)); return q

    def consider(c, rid, trunk, need):
        """a line against those kept: its pieces kept that run apart `need` km -> how many"""
        S, j, t, along = samples(c)
        d, near = idx.near(S)
        cov = d < SEP_KM
        if cov.all():
            stats["covered"] += 1; return 0
        # the runs: covered or not; a covered one dropped where it is long, or at an end that does not reach the line
        edges = np.flatnonzero(np.diff(cov.astype(np.int8))) + 1
        runs = [(a, b - 1) for a, b in zip(np.r_[0, edges], np.r_[edges, len(S)])]
        n = len(S)
        def drop(a, b):
            if not cov[a]:
                return False
            if along[b] - along[a] >= PARALLEL_KM:
                return True
            return (a == 0 and d[0] >= TOUCH_KM) or (b == n - 1 and d[-1] >= TOUCH_KM)
        group, groups = [], []
        for a, b in runs:
            if drop(a, b):
                if group: groups.append(group); group = []
            else:
                group.append((a, b))
        if group: groups.append(group)
        got = 0
        for g in groups:
            a, b = g[0][0], g[-1][1]
            if sum(along[y] - along[x] for x, y in g if not cov[x]) < need:
                stats["short"] += 1; continue
            # the piece from sample a to sample b (a cut end begins on the sample before it, carried onto that line)
            lo, hi = (a - 1 if a > 0 else a), (b + 1 if b < n - 1 else b)
            pts = np.array([lonlat(S[lo])[0]] + [c[v] for v in range(j[lo] + 1, j[hi] + 1)] + [lonlat(S[hi])[0]])
            if lo == 0: pts[0] = c[0]                            # (a line's own end exactly: a node of its river's channels)
            if hi == n - 1: pts[-1] = c[-1]
            if lo == 0 and cov[0]:                           # (an end that reaches a line: onto it)
                pts = np.vstack((snap(near[0], S[0]), pts))
            elif lo > 0:
                pts = np.vstack((snap(near[lo], S[lo]), pts)); stats["cut"] += 1
            if hi == n - 1 and cov[-1]:
                pts = np.vstack((pts, snap(near[-1], S[-1])))
            elif hi < n - 1:
                pts = np.vstack((pts, snap(near[hi], S[hi]))); stats["cut"] += 1
            pts = pts[np.r_[True, np.any(np.abs(np.diff(pts, axis=0)) > 1e-9, axis=1)]]
            if len(pts) < 2:
                continue
            L = len(kept); kept.append((pts, rid, trunk)); got += 1
            S2, j2, _, _ = samples(pts); idx.add(L, S2, j2)
        return got

    for c, rid, trunk, ks in todo:
        if len(c) >= 2 and consider(c, rid, trunk, PIECE_KM if trunk else BRANCH_KM):
            used.update(ks)
    log(f"kept {len(kept):,} lines ({stats['covered']:,} pieces the same water as a line kept, {stats['short']:,} pieces too short, {stats['cut']:,} ends carried onto a line)")
    # SIDE ARMS BACK: a side arm kept with an end that meets nothing goes on along its own river's channels (those not
    # kept), the shortest way up to CLOSE_KM, to a point within JOIN_KM of a line kept -- the rest of that arm, kept
    # whatever its length (and carried onto that line)
    gkey = lambda q: (int(round(q[0] / config.QUANT_DEG)), int(round(q[1] / config.QUANT_DEG)))
    adj = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, (c, p) in enumerate(lines):
        if k not in used:
            a, b, L = gkey(c[0]), gkey(c[-1]), km(c)
            adj[p.get("river")][a].append((b, k, True, L, c[-1])); adj[p.get("river")][b].append((a, k, False, L, c[0]))
    free, closed = free_ends(kept, attached), 0
    for L in range(len(kept)):
        c, rid, trunk = kept[L]
        if trunk:
            continue
        for last in (False, True):
            q = c[-1] if last else c[0]
            G = adj.get(rid, {})
            if not free(q) or gkey(q) not in G:
                continue
            dist, back, h, goal = {gkey(q): 0.0}, {}, [(0.0, gkey(q))], None
            while h and goal is None:
                dd, u = heapq.heappop(h)
                if dd > dist[u]:
                    continue
                for v, k, fw, w, at in G[u]:
                    if dd + w < dist.get(v, np.inf) and dd + w <= CLOSE_KM:
                        dist[v] = dd + w; back[v] = (u, k, fw); heapq.heappush(h, (dd + w, v))
                        if idx.near(xyz(at[None]), reach=int(np.ceil(JOIN_KM / SEP_KM)), skip=L)[0][0] < JOIN_KM:
                            goal = v; break
            if goal is None:
                continue
            steps, v = [], goal
            while v != gkey(q):
                u, k, fw = back[v]; steps.append(lines[k][0] if fw else lines[k][0][::-1]); used.add(k); v = u
            path = np.vstack([p if i == 0 else p[1:] for i, p in enumerate(reversed(steps))])   # (from q on)
            if not last:
                path = path[::-1]                            # (into the arm's start)
            closed += consider(path, rid, False, 0) > 0
    log(f"{closed:,} side arms joined back along their own channels")
    return kept, inserts, idx, props, attached


pkey = lambda q: (round(float(q[0]), 7), round(float(q[1]), 7))


def free_ends(kept, attached):
    """the ends that meet nothing: not on another line, not another line's end"""
    n = collections.Counter(pkey(q) for c, _, _ in kept for q in (c[0], c[-1]))
    return lambda q: n[pkey(q)] == 1 and pkey(q) not in attached


def joins(kept, inserts, idx, attached):
    """free ends onto the line they are at: an end within TOUCH_KM, a downstream end (or a side arm's) within JOIN_KM -> {line: (point
    before its start, point after its end)} (kept apart: the points put into a line are counted on it as it was)"""
    free, ext, n = free_ends(kept, attached), {}, 0
    for L, (c, rid, trunk) in enumerate(kept):
        for last in (False, True):
            q = c[-1] if last else c[0]
            if not free(q):
                continue
            p, most = xyz(q[None]), JOIN_KM if last or not trunk else TOUCH_KM   # (a source stays where it is; a side arm's start is on its river)
            d, i = idx.near(p, reach=int(np.ceil((JOIN_KM + STEP_KM) / SEP_KM)), skip=L)
            if not np.isfinite(d[0]) or d[0] >= most + STEP_KM or d[0] < 1e-6:   # (the samples: STEP_KM apart -- the line itself measured next)
                continue
            M = int(idx.line[i[0]]); s, t, r = onto(kept[M][0], int(idx.seg[i[0]]), p[0])
            if km(np.array([q, r])) >= most:
                continue
            inserts[M].append((s, t, r)); attached.add(pkey(r))
            h, e = ext.get(L, (None, None)); ext[L] = (h, r) if last else (r, e); n += 1
    log(f"{n:,} free ends carried onto the line they are at")
    return ext


def apply_inserts(kept, inserts, ext):
    out = []
    for L, (c, rid, trunk) in enumerate(kept):
        ins = sorted(inserts.get(L, []), key=lambda x: (x[0], x[1]))
        if ins:
            parts, last = [], 0
            for s, t, q in ins:
                parts.append(c[last:s + 1]); parts.append(q[None]); last = s + 1
            parts.append(c[last:])
            c = np.vstack(parts)
        h, e = ext.get(L, (None, None))
        c = np.vstack([x for x in (None if h is None else h[None], c, None if e is None else e[None]) if x is not None])
        out.append((c, rid, trunk))
    return out


def mouths(kept, world, attached):
    """the free downstream ends: cut at the coast if in the sea, carried on to it if near -> (kept, the points into the coast)"""
    arcs = decode(world)
    land = [shapely.Polygon(ring(arcs, g["arcs"][0]), [ring(arcs, h) for h in g["arcs"][1:]]) for g in world["objects"]["land"]["geometries"] if g["type"] == "Polygon"]
    land += [shapely.Polygon(ring(arcs, p[0]), [ring(arcs, h) for h in p[1:]]) for g in world["objects"]["land"]["geometries"] if g["type"] == "MultiPolygon" for p in g["arcs"]]
    land_tree = shapely.STRtree(land)
    lakes = [shapely.Polygon(ring(arcs, a[0])) for g in world["objects"]["lakes"]["geometries"] for a in ([g["arcs"]] if g["type"] == "Polygon" else g["arcs"])]
    lake_tree = shapely.STRtree(lakes)
    coast_ids = sorted({i if i >= 0 else ~i for line in world["objects"]["coastline"]["geometries"][0]["arcs"] for i in line})
    coast = [shapely.LineString(arcs[i]) for i in coast_ids]; coast_tree = shapely.STRtree(coast)
    free = free_ends(kept, attached)
    on_land = lambda q: len(land_tree.query(shapely.Point(q), predicate="intersects")) > 0
    into, cut, carried = [], 0, 0
    for L, (c, rid, trunk) in enumerate(kept):
        q = c[-1]
        if not free(q):
            continue
        deg = lambda k: k / 111.2 / max(0.2, np.cos(np.radians(q[1])))
        if not on_land(q):                                   # in the sea: cut where it last crosses the coast
            v = len(c) - 1
            while v > 0 and not on_land(c[v]):
                v -= 1
            if v == 0 and not on_land(c[0]):
                continue
            seg = shapely.LineString(c[v:v + 2])
            hits = [(h, i) for i in coast_tree.query(seg, predicate="intersects") for h in shapely.get_parts(shapely.intersection(seg, coast[i])) if h.geom_type == "Point"]
            if not hits:
                continue
            h, i = min(hits, key=lambda x: seg.project(x[0]))
            c = np.vstack((c[:v + 1], [[h.x, h.y]])); cut += 1
        else:                                                # near the coast, not at a lake: on to it
            P = shapely.Point(q)
            near = coast_tree.query(P, predicate="dwithin", distance=deg(MOUTH_KM))
            if not len(near):
                continue
            i = min(near, key=lambda i: coast[i].distance(P))
            lake = lake_tree.query(P, predicate="dwithin", distance=deg(LAKE_KM))
            if len(lake):                                    # (a lake whose shore there is the coast -- the Caspian -- is the sea)
                k = min(lake, key=lambda k: lakes[k].distance(P))
                shore = shapely.ops.nearest_points(lakes[k].boundary, P)[0]
                if lakes[k].distance(P) < coast[i].distance(P) and coast[i].distance(shore) >= deg(TOUCH_KM):
                    continue
            h = shapely.ops.nearest_points(coast[i], P)[0]
            if km(np.array([q, [h.x, h.y]])) >= MOUTH_KM:
                continue
            c = np.vstack((c, [[h.x, h.y]])); carried += 1
        kept[L] = (c, rid, trunk)
        into.append((coast_ids[i], c[-1]))
    log(f"mouths: {cut:,} cut at the coast, {carried:,} carried on to it")
    return kept, into


def coast_points(world, into):
    """the mouths put into the coast's arcs (on the grid; already there: nothing)"""
    q = config.QUANT_DEG
    by = collections.defaultdict(list)
    for a, p in into:
        by[a].append((int(round((p[0] + 180) / q)), int(round((p[1] + 90) / q))))
    n = 0
    for a, pts in by.items():
        P = np.cumsum(np.array(world["arcs"][a], dtype=np.int64), axis=0)
        for g in pts:
            if np.any(np.all(P == g, axis=1)):
                continue
            f = P.astype(float); x = np.array(g, float)
            ab = f[1:] - f[:-1]; L = (ab ** 2).sum(1); L[L == 0] = 1
            t = np.clip(((x - f[:-1]) * ab).sum(1) / L, 0, 1)
            s = int(np.argmin(((f[:-1] + ab * t[:, None] - x) ** 2).sum(1)))
            P = np.vstack((P[:s + 1], [g], P[s + 1:])); n += 1
        world["arcs"][a] = np.vstack((P[:1], np.diff(P, axis=0))).tolist()
    log(f"{n:,} mouths put into the coast")


def main():
    if not os.path.exists(TRACKED):
        raise SystemExit(f"{TRACKED}: missing -- build/water.py writes it")
    topo = json.load(open(TRACKED))
    arcs = decode(topo)
    lines = [(ring(arcs, g["arcs"]), g["properties"]) for g in topo["objects"]["rivers"]["geometries"]]
    km0 = sum(km(c) for c, _ in lines)
    kept, inserts, idx, props, attached = network(lines)
    ext = joins(kept, inserts, idx, attached)
    kept = apply_inserts(kept, inserts, ext)
    world = json.load(open(WORLD))
    kept, into = mouths(kept, world, attached)
    coast_points(world, into)
    # the arcs: every line cut at every junction (an end of another line on it), so a join is an arc's end
    q = config.QUANT_DEG
    grid = [np.column_stack((np.round((c[:, 0] + 180) / q), np.round((c[:, 1] + 90) / q))).astype(np.int64) for c, _, _ in kept]
    grid = [g[np.r_[True, np.any(g[1:] != g[:-1], axis=1)]] for g in grid]
    junction = set()
    for g in grid:
        if len(g) > 1:
            junction.add(tuple(g[0])); junction.add(tuple(g[-1]))
    feats, arcs_out = [], []
    for g, (c, rid, trunk) in zip(grid, kept):
        if len(g) < 2:
            continue
        cuts = [0] + [v for v in range(1, len(g) - 1) if tuple(g[v]) in junction] + [len(g) - 1]
        ids = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            ids.append(len(arcs_out)); arcs_out.append(g[a:b + 1])
        p = {k: v for k, v in props[rid].items() if k != "length_km"}
        feats.append({"type": "LineString", "arcs": ids, "properties": {**p, "length_km": round(km(g * q - [180, 90]), 1)}})
    topo_out = {"type": "Topology", "bbox": [-180, -90, 180, 90], "transform": {"scale": [q, q], "translate": [-180, -90]},
                "objects": {"rivers": {"type": "GeometryCollection", "geometries": feats}},
                "arcs": [np.vstack((a[:1], np.diff(a, axis=0))).tolist() for a in arcs_out]}
    json.dump(topo_out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(world, open(WORLD, "w"), ensure_ascii=False, separators=(",", ":"))
    km1 = sum(f["properties"]["length_km"] for f in feats)
    log(f"{OUT}: {len(feats):,} lines ({len(lines):,} before), {len(arcs_out):,} arcs, {km1:,.0f} km ({km0:,.0f} before), {os.path.getsize(OUT) / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
