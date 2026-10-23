"""STAGE 2 -- THE TOPOLOGY: the coast (stage 1) and the land borders of countries and of states (Overture's division
boundaries, OSM's boundary relations) joined into one planar map, simplified to EPS_KM, cut into faces, and every face
told which country (or dependency) and which state it belongs to.

    .venv/bin/python build/topology.py            # -> work/topology.pkl (build/write.py makes the TopoJSON of it)

How the lines are made to fit:
  * a border's end on the coast is the coastline's own vertex (matched exactly, else the nearest within SNAP_KM),
    and that vertex is kept when the coast is simplified; a line ending ON another (a state border meeting the
    national one) splits it there -- so every line meets the others at its ends, and only there;
  * everything is simplified on the sphere (geo.simplify) with those junctions fixed; where two simplified lines
    would cross (a border hugging a coast, two islands across a narrow strait), the segments at the crossing get
    back the points of their finest version (the fine coast, the border as OSM has it) -- only there;
  * a border piece of no length, and a border arc on the same path as another line with the same ends (a border
    drawn along the coast, one border from two sources), are dropped: two lines on one path leave no face between;
  * each landmass is cut by the borders inside it into FACES (shapely.polygonize: the lines are already noded), and
    a face belongs to the country or dependency whose area (Overture's, land and territorial sea) holds a point
    inside it, and to the state likewise.
"""
import os, sys, time, pickle, collections
import duckdb, numpy as np, shapely
from shapely import STRtree
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BOUNDARY = os.path.join(ROOT, "raw/divisions/division_boundary-*.parquet")
AREA = os.path.join(ROOT, "raw/divisions/division_area-*.parquet")
OUT = os.path.join(ROOT, "work/topology.pkl")
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ---- the divisions: who is who, and their areas (to label the faces) ---------------------------------------------
def divisions(con):
    rel = con.execute(f"""SELECT division_id, subtype, class, country, region, names.primary, names.common['en'], ST_AsWKB(geometry)
                          FROM '{AREA}' WHERE subtype IN ('country', 'dependency') OR (subtype = 'region' AND country IN ({",".join(f"'{c}'" for c in config.REGION_COUNTRIES)}))""")
    info, geoms, cls_of = {}, {}, {}
    while True:
        rows = rel.fetchmany(20)
        if not rows:
            break
        for did, sub, cls, cc, reg, name, name_en, w in rows:
            if isinstance(name_en, list):
                name_en = name_en[0] if name_en else None
            info.setdefault(did, {"id": did, "subtype": sub, "country": cc, "region": reg, "name": name, "name_en": name_en or name,
                                  "sovereign": config.SOVEREIGN.get(cc) if sub == "dependency" else cc})
            # the maritime area is the whole territory (land and its territorial sea): prefer it, else the land
            if cls == "maritime" or did not in geoms:
                geoms[did] = shapely.simplify(shapely.from_wkb(w), 0.001)   # (100 m: plenty to tell which unit a face is in)
                cls_of[did] = cls
    log(len(info), "divisions:", dict(collections.Counter(v["subtype"] for v in info.values())), dict(collections.Counter(cls_of.values())))
    return info, geoms


# ---- the border lines ---------------------------------------------------------------------------------------------
def border_lines(con, info, ends):
    """the land borders, read a few at a time: each split where another line's end lies on one of its inner vertices
    (`ends`: every border end, found by stage 1), exact duplicates dropped. They are kept as OSM has them (a few
    million points): simplified, they are their own finest version, which does not cross (0.1 km would)."""
    rel = con.execute(f"""SELECT id, subtype, division_ids, is_disputed, ST_AsWKB(geometry) FROM '{BOUNDARY}'
                          WHERE class = 'land' AND subtype IN ('country', 'region')""")
    ends = np.unique(geo.key(ends))
    lines, seen, n_in, pts_in = [], set(), 0, 0
    skipped = collections.Counter()
    while True:
        rows = rel.fetchmany(100)
        if not rows:
            break
        for bid, sub, ids, disputed, w in rows:
            if sub == "region":
                a, b = (info.get(i) for i in ids) if ids and len(ids) == 2 else (None, None)
                if not a or not b or a["subtype"] != "region" or b["subtype"] != "region" or a["country"] != b["country"]:
                    skipped["region (not two states of one listed country)"] += 1
                    continue
            g = shapely.from_wkb(w)
            for p in (g.geoms if g.geom_type == "MultiLineString" else [g]):
                c = shapely.get_coordinates(p)
                c = c[np.r_[True, np.any(c[1:] != c[:-1], axis=1)]]   # (OSM's lines repeat a point now and then)
                if len(c) < 2:
                    continue
                n_in += 1; pts_in += len(c)
                k = geo.key(c)
                cut = np.flatnonzero(np.isin(k[1:-1], ends)) + 1
                bounds = [0, *cut.tolist(), len(k) - 1]
                for a, b in zip(bounds[:-1], bounds[1:]):
                    piece = c[a:b + 1]
                    sig = (min(k[a], k[b]), max(k[a], k[b]), len(piece), int(geo.key(piece[len(piece) // 2])))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    piece = piece.copy()
                    lines.append({"kind": sub, "ids": list(ids or []), "disputed": bool(disputed), "src": bid, "c": piece})
    log(n_in, "border lines,", f"{pts_in:,} points", "skipped", dict(skipped))
    log(len(lines), "lines after splitting at junctions", dict(collections.Counter(l["kind"] for l in lines)),
        f"{sum(len(l['c']) for l in lines):,} points")
    return lines


# ---- the coast ----------------------------------------------------------------------------------------------------
def load_coast():
    z = np.load(os.path.join(ROOT, "work/coast_fine.npz"))
    off, coords = z["offsets"], z["coords"]                 # (read once: z["coords"] decompresses the whole array anew)
    rings = [coords[off[i]:off[i + 1]] for i in range(len(off) - 1)]
    return rings, z["poly"], z["hole"], z["area"], z["ends"], z["cand"]


def attach(lines, rings, E, cand):
    """each line end on the coast: which ring and which vertex of it (the best candidate stage 1 found) -- within
    SNAP_KM, or LOOSE_KM for an end that meets no other line (a border that stops short of a river mouth)"""
    Ek = geo.key(E)
    best = {}
    for e, r, v, d in cand:
        k = int(Ek[int(e)])
        if k not in best or d < best[k][2]:
            best[k] = (int(r), int(v), d)
    deg = collections.Counter(int(k) for l in lines for k in geo.key(np.array([l["c"][0], l["c"][-1]])))
    att, far = 0, []
    for l in lines:
        l["at"] = [None, None]
        for j, pos in ((0, 0), (1, -1)):
            k = int(geo.key(l["c"][pos]))
            b = best.get(k)
            if b and (b[2] <= config.SNAP_KM or (deg[k] == 1 and b[2] <= config.LOOSE_KM)):
                l["at"][j] = b[:2]
                l["c"][pos] = rings[b[0]][b[1]]          # (the coast's own vertex: exactly equal from here on)
                att += 1
                if b[2] > 0.001:
                    far.append(b[2])
    log(att, "line ends joined to the coast;", len(far), "of them moved to the nearest coast vertex (max", round(max(far, default=0), 3), "km)")


def connect(lines):
    """the ends that still meet nothing (a border drawn in pieces, with a gap where a summit is disputed): each joined
    to the nearest other such end within LOOSE_KM by a straight line"""
    ends = [(i, j) for i, l in enumerate(lines) for j in (0, 1) if l["at"][j] is None]
    deg = collections.Counter(int(k) for l in lines for k in geo.key(np.array([l["c"][0], l["c"][-1]])))
    ends = [(i, j) for i, j in ends if deg[int(geo.key(lines[i]["c"][-j]))] == 1]
    if len(ends) < 2:
        return lines
    P = np.array([lines[i]["c"][-j] for i, j in ends])
    tree = cKDTree(geo.to_xyz(P))
    pairs = sorted((d, a, b) for a, b in tree.query_pairs(2 * np.sin(config.LOOSE_KM / geo.R_KM / 2), output_type="ndarray")
                   for d in [float(np.linalg.norm(geo.to_xyz(P[[a]]) - geo.to_xyz(P[[b]])))])
    used, n = set(), 0
    for d, a, b in pairs:
        if a in used or b in used:
            continue
        used.update((a, b))
        (i, _), (k, _) = ends[a], ends[b]
        la, lb = lines[i], lines[k]
        lines.append({"kind": "country" if la["kind"] == lb["kind"] == "country" else "region", "ids": la["ids"],
                      "disputed": la["disputed"] or lb["disputed"], "src": f"gap:{la['src']}:{lb['src']}",
                      "c": np.array([P[a], P[b]]), "at": [None, None]})
        n += 1
    log(n, "gaps between loose border ends closed;", len(ends) - 2 * n, "ends still loose")
    return lines


def prune(lines):
    """lines that neither reach the coast nor meet another line at either end (a border on an island too small to
    keep) are dropped, repeatedly"""
    while True:
        deg = collections.Counter(int(k) for l in lines for k in geo.key(np.array([l["c"][0], l["c"][-1]])))
        keep = []
        for l in lines:
            k0, k1 = int(geo.key(l["c"][0])), int(geo.key(l["c"][-1]))
            free0 = l["at"][0] is None and deg[k0] < 2
            free1 = l["at"][1] is None and deg[k1] < 2
            if free0 and free1 and k0 != k1:
                continue
            keep.append(l)
        if len(keep) == len(lines):
            break
        log("pruned", len(lines) - len(keep), "loose lines")
        lines = keep
    # (a piece whose ends were both moved onto the same coast vertex, and has nothing between: a point, not a line)
    keep = [l for l in lines if not np.all(l["c"] == l["c"][0])]
    log("dropped", len(lines) - len(keep), "border pieces of no length")
    return keep


# ---- simplification to arcs ---------------------------------------------------------------------------------------
class Arc:
    """a line of the map: `c` its simplified points, `keep` their indices in its finest version (fine() -- the fine
    coast between two nodes, or the border as OSM has it)"""
    __slots__ = ("c", "kind", "src", "lo", "hi", "keep", "line", "ring", "cut")

    def __init__(self, c, kind, src, lo, hi, keep, line=None, ring=None, cut=False):
        self.c, self.kind, self.src, self.lo, self.hi, self.keep, self.line, self.ring, self.cut = c, kind, src, lo, hi, keep, line, ring, cut


def fine(arc, rings, lines):
    return arc.c if arc.cut else lines[arc.line]["c"] if arc.line is not None else span(rings[arc.ring], arc.lo, arc.hi)


def span(src, lo, hi):
    """src from vertex lo forward to vertex hi; on a closed ring (src[0] == src[-1]) through its closing vertex when
    hi <= lo, all the way round when hi == lo"""
    if hi > lo:
        return src[lo:hi + 1]
    n = len(src) - 1
    return np.vstack((src[lo:n], src[:hi + 1]))


def coast_arcs(rings, lines):
    """every ring cut at its nodes (the vertices where borders join it, and the antimeridian's), each piece an arc"""
    nodes = collections.defaultdict(set)
    for l in lines:
        for a in l["at"]:
            if a:
                nodes[a[0]].add(a[1])
    arcs, ring_arcs = [], []
    for r, c in enumerate(rings):
        cut = (np.abs(c[:-1, 0]) == 180) | (c[:-1, 1] <= -89.9999)
        ns = sorted(nodes[r] | set(np.flatnonzero(cut).tolist()))
        ids = []
        for i, a in enumerate(ns or [0]):                  # (a ring without nodes: one closed arc from its first vertex)
            b = ns[(i + 1) % len(ns)] if ns else 0
            sp = span(c, a, b)
            is_cut = len(sp) == 2 and all(abs(p[0]) == 180 or p[1] <= -89.9999 for p in sp) and (
                sp[0][0] == sp[1][0] or (sp[0][1] <= -89.9999 and sp[1][1] <= -89.9999))
            keep = np.arange(len(sp)) if is_cut else geo.simplify(geo.to_xyz(sp), config.EPS_KM)
            ids.append(len(arcs))
            arcs.append(Arc(sp[keep].copy(), "coast", r, a, b, keep, ring=r, cut=is_cut))
        ring_arcs.append(ids)
    log(len(arcs), "coast arcs,", sum(a.cut for a in arcs), "of them along the antimeridian or the pole")
    return arcs, ring_arcs


def line_arcs(lines):
    arcs = []
    for i, l in enumerate(lines):
        keep = geo.simplify(geo.to_xyz(l["c"]), config.EPS_KM)
        arcs.append(Arc(l["c"][keep], l["kind"], l["src"], 0, len(l["c"]) - 1, keep, line=i))
    return arcs


def crossings(cs):
    """lines (coordinate arrays) -> (the pairs (i < j) that cross or overlap, the lines that cross themselves).
    Touching at shared ends is how lines meet: anything else is a crossing."""
    geoms = [shapely.linestrings(c) for c in cs]
    pa, pb = STRtree(geoms).query(geoms, predicate="intersects")
    m = pa < pb
    pairs = set()
    for i, j in zip(pa[m].tolist(), pb[m].tolist()):
        x = shapely.intersection(geoms[i], geoms[j])
        if x.is_empty:
            continue
        ends = {tuple(cs[i][0]), tuple(cs[i][-1])} & {tuple(cs[j][0]), tuple(cs[j][-1])}
        if x.geom_type in ("Point", "MultiPoint") and all(tuple(p) in ends for p in shapely.get_coordinates(x)):
            continue
        pairs.add((i, j))
    return pairs, {i for i, g in enumerate(geoms) if not shapely.is_simple(g)}


def fix_crossings(arcs, rings, lines):
    """simplified arcs must not cross each other, nor themselves: where they would, the segments at the crossing get
    back all the points of their finest version between their ends -- only those. Crossings the finest lines have
    already (two islands across a strait narrower than the fine coast's detail) are left as they are."""
    given_pairs, given_self = crossings([fine(a, rings, lines) for a in arcs])
    log(f"{len(given_pairs)} crossings and {len(given_self)} self-crossings in the finest lines themselves (left as they are)")
    for rnd in range(12):
        pairs, selfx = crossings([a.c for a in arcs])
        pairs, selfx = pairs - given_pairs, selfx - given_self
        log(f"round {rnd}: {len(pairs)} crossings, {len(selfx)} arcs crossing themselves")
        if not pairs and not selfx:
            return
        spots = collections.defaultdict(list)                # arc -> the points where it crosses
        for i, j in pairs:
            x = shapely.get_coordinates(shapely.intersection(shapely.linestrings(arcs[i].c), shapely.linestrings(arcs[j].c)))
            spots[i].append(x); spots[j].append(x)
        for i in selfx:
            g = shapely.linestrings(arcs[i].c)
            nd = shapely.get_parts(shapely.node(g))
            spots[i].append(np.vstack([shapely.get_coordinates(shapely.get_point(nd, 0)), shapely.get_coordinates(shapely.get_point(nd, -1))]))
        grew = 0
        for i, sp in spots.items():
            a = arcs[i]
            if a.cut:
                continue
            c = a.c
            segs = shapely.linestrings(np.stack((c[:-1], c[1:]), axis=1))
            _, hit = STRtree(segs).query(shapely.buffer(shapely.points(np.vstack(sp)), 1e-7), predicate="intersects")
            back = [np.arange(int(a.keep[j]) + 1, int(a.keep[j + 1])) for j in np.unique(hit).tolist() if a.keep[j + 1] - a.keep[j] > 1]
            if back:
                a.keep = np.union1d(a.keep, np.concatenate(back))
                a.c = fine(a, rings, lines)[a.keep]
                grew += 1
        if not grew:
            break
    log("(crossings left)")


def dedupe(arcs):
    """a border arc that runs along another line with the same ends -- a border drawn along the coast, one border
    twice from two sources -- is dropped (kind "dup"): two lines on one path would make the faces between them
    nothing. The coast is kept over a border, a national border over a state's."""
    pairs, _ = crossings([a.c for a in arcs])
    rank = {"coast": 0, "country": 1, "region": 2}
    n = 0
    for i, j in sorted(pairs):
        a, b = arcs[i], arcs[j]
        if "dup" in (a.kind, b.kind) or {tuple(a.c[0]), tuple(a.c[-1])} != {tuple(b.c[0]), tuple(b.c[-1])}:
            continue
        ga, gb = shapely.linestrings(a.c), shapely.linestrings(b.c)
        if shapely.hausdorff_distance(ga, gb) > 0.01:        # (1 km: the same path, as two sources drew it)
            continue
        drop = b if rank[b.kind] >= rank[a.kind] else a
        if drop.kind == "coast":
            continue
        drop.kind = "dup"; n += 1
    log(n, "border arcs dropped as the same path as another line")


def node_crossings(arcs, points=None):
    """lines that cross even as OSM draws them (the lines round Cyprus's buffer zone; two coasts across a channel
    narrower than the fine detail, a delta's islands): the crossing point is put into both, so split_junctions cuts
    them there and they meet at their ends -- else a sea cut out between them (stage 6) would not close."""
    pairs, _ = crossings([a.c for a in arcs])
    add, keys = collections.defaultdict(list), []
    for i, j in pairs:
        if "dup" in (arcs[i].kind, arcs[j].kind):
            continue
        x = shapely.intersection(shapely.linestrings(arcs[i].c), shapely.linestrings(arcs[j].c))
        if x.geom_type not in ("Point", "MultiPoint"):
            continue
        for p in shapely.get_coordinates(x):
            add[i].append(p); add[j].append(p); keys.append(int(geo.key(p)))
            if points is not None:
                points.append(p)
    for i, pts in add.items():
        c = arcs[i].c
        for p in pts:
            if (np.all(c == p, axis=1)).any():
                continue
            segs = shapely.linestrings(np.stack((c[:-1], c[1:]), axis=1))
            k = int(np.argmin(shapely.distance(segs, shapely.points(p))))
            c = np.vstack((c[:k + 1], [p], c[k + 1:]))
        arcs[i].c = c
    log(len(add), "arcs given the points where they cross another line")
    return np.array(keys, dtype=np.int64)


def split_junctions(arcs, ring_arcs, also=()):
    """an arc that another one ends on, at one of its inner vertices, is split there (and at `also`: the crossings
    node_crossings put in): every line must meet the others at its ends only, or a face's outline would leave it
    midway and could not be told as whole arcs"""
    live = [a for a in arcs if a.kind != "dup"]
    ends = np.unique(np.concatenate((geo.key(np.array([p for a in live for p in (a.c[0], a.c[-1])])), np.asarray(also, np.int64))))
    n, replace = 0, collections.defaultdict(dict)          # (a ring's arcs: rebuilt once, at the end)
    for i in range(len(arcs)):
        a = arcs[i]
        if a.kind == "dup" or len(a.c) < 3:
            continue
        k = geo.key(a.c[1:-1])
        pos = np.minimum(np.searchsorted(ends, k), len(ends) - 1)
        cut = np.flatnonzero(ends[pos] == k) + 1
        if not len(cut):
            continue
        bounds = [0, *cut.tolist(), len(a.c) - 1]
        pieces = [a.c[x:y + 1] for x, y in zip(bounds[:-1], bounds[1:])]
        a.c = pieces[0]
        ids = [i]
        for c in pieces[1:]:
            ids.append(len(arcs))
            arcs.append(Arc(c, a.kind, a.src, 0, 0, None, line=a.line, ring=a.ring))
        if a.kind == "coast":                                # (in its ring's list, the pieces in order)
            replace[a.ring][i] = ids
        n += 1
    for r, rep in replace.items():
        ring_arcs[r] = [j for i in ring_arcs[r] for j in rep.get(i, (i,))]
    log(n, "arcs split where another line ends on them")


# ---- faces --------------------------------------------------------------------------------------------------------
def polygonize(lines):
    """the faces noded lines enclose. (A face whose outline touches itself at a node -- an enclave's border meeting
    its host's at one point, as in Cyprus's Dhekelia -- comes back from GEOS as an "invalid ring": made valid, it is
    the face, on the same vertices.)"""
    polys, _, _, invalid = shapely.polygonize_full(lines)
    fixed = [q for r in shapely.get_parts(invalid) for q in shapely.get_parts(shapely.make_valid(shapely.Polygon(shapely.get_coordinates(r))))
             if q.geom_type == "Polygon"]
    return list(shapely.get_parts(polys)) + fixed


def land_polygons(arcs, ring_arcs, poly, hole):
    """the land polygons back out of their rings' arcs: one shapely Polygon per landmass"""
    by = collections.defaultdict(list)
    for r, ids in enumerate(ring_arcs):
        by[int(poly[r])].append(r)
    polys, pids = [], []
    for pid, rs in by.items():
        ringc = []
        for r in rs:
            cs = [arcs[i].c for i in ring_arcs[r]]
            c = np.vstack([cs[0]] + [x[1:] for x in cs[1:]])
            ringc.append(c)
        outer = [c for r, c in zip(rs, ringc) if not hole[r]]
        holes = [c for r, c in zip(rs, ringc) if hole[r]]
        if outer:
            polys.append(shapely.Polygon(outer[0], holes)); pids.append(pid)
    return polys, pids


def faces(arcs, ring_arcs, poly, hole, kinds):
    """each landmass cut by the border arcs (of the given kinds) inside it -> [(face polygon, landmass id)]"""
    polys, pids = land_polygons(arcs, ring_arcs, poly, hole)
    tree = STRtree(polys)
    border = [i for i, a in enumerate(arcs) if a.kind in kinds]
    # which landmass each border arc is in: the one holding a point of it (its middle vertex, or its middle)
    mids = [shapely.points(a.c[len(a.c) // 2]) if len(a.c) > 2 else shapely.line_interpolate_point(shapely.linestrings(a.c), .5, normalized=True) for a in (arcs[i] for i in border)]
    hit_a, hit_p = tree.query(mids, predicate="within")
    hits = collections.defaultdict(list)
    for a, p in zip(hit_a.tolist(), hit_p.tolist()):
        hits[border[a]].append(p)
    owner = {}
    for a_i, m in zip(border, mids):
        ps = hits.get(a_i, [])
        if len(ps) == 1:
            owner[a_i] = ps[0]
            continue
        # (in two landmasses -- an islet in an estuary, overlapping the mainland's outline -- or on the coast itself: the
        # one most of its points are in, the bigger if even; one end of a border left to the islet would hang open on the
        # mainland, and the two countries it parts be one face: Ecuador and Peru at Zarumilla)
        line = shapely.linestrings(arcs[a_i].c)
        pts = shapely.line_interpolate_point(line, np.linspace(0, 1, 5), normalized=True)
        cand = ps or tree.query(line).tolist() or [int(tree.query_nearest(m)[0])]
        owner[a_i] = max(cand, key=lambda p: (int(shapely.covers(polys[p], pts).sum()), -round(shapely.distance(polys[p], m), 7), polys[p].area))
    per = collections.defaultdict(list)
    for a, p in owner.items():
        per[p].append(a)
    out, short = [], []
    ring_of_poly = collections.defaultdict(list)
    for r in range(len(ring_arcs)):
        ring_of_poly[int(poly[r])].append(r)
    for k, (P, pid) in enumerate(zip(polys, pids)):
        if k not in per:                                    # (no border inside: the landmass is one face)
            out.append((P, pid))
            continue
        lines = [shapely.linestrings(arcs[i].c) for r in ring_of_poly[pid] for i in ring_arcs[r]] + [shapely.linestrings(arcs[i].c) for i in per[k]]
        got = polygonize(lines)
        V = P if shapely.is_valid(P) else shapely.make_valid(P)
        shapely.prepare(V)
        n0, cover = len(out), 0.0
        for f in got:
            if shapely.contains(V, shapely.point_on_surface(f)):
                out.append((f, pid)); cover += f.area
        if cover < 0.99 * V.area:                           # (lines that do not meet cleanly leave land in no face)
            short.append((pid, len(out) - n0, round(100 * cover / V.area, 1)))
    if short:
        log(f"  {len(short)} landmasses not fully cut into faces (landmass, faces, % covered):", sorted(short, key=lambda s: s[2])[:12])
    log(len(out), "faces cut by", "+".join(kinds))
    return out


def label(faces_, info, geoms, subtypes, within=None):
    """the division each face is in: the one whose area holds a point inside it (dependencies before countries);
    else the nearest within 20 km. `within`: per face, the country it must be a state of"""
    ids = [d for d in geoms if info[d]["subtype"] in subtypes]
    areas = [geoms[d] for d in ids]
    tree = STRtree(areas)
    rank = {"dependency": 0, "region": 0, "country": 1}
    pts = [shapely.point_on_surface(f) for f, _ in faces_]
    fi, ai = tree.query(pts, predicate="within")
    hits = collections.defaultdict(list)
    for f, a in zip(fi.tolist(), ai.tolist()):
        if within is None or info[ids[a]]["country"] == within[f]:
            hits[f].append(ids[a])
    out, claims, near, none = [], {}, 0, 0
    for f in range(len(faces_)):
        h = sorted(hits.get(f, []), key=lambda d: (rank[info[d]["subtype"]], shapely.area(geoms[d])))
        if not h:
            ni, dist = tree.query_nearest(pts[f], return_distance=True, all_matches=False)
            cands = [ids[a] for a in np.atleast_1d(ni) if within is None or info[ids[a]]["country"] == within[f]]
            if cands and float(np.atleast_1d(dist)[0]) < 0.2:
                h = cands[:1]; near += 1
        if not h:
            out.append(None); none += 1
            continue
        out.append(h[0])
        same_rank = [d for d in h if rank[info[d]["subtype"]] == rank[info[h[0]]["subtype"]] and info[d]["country"] != info[h[0]]["country"]]
        if same_rank:
            claims[f] = [h[0]] + same_rank
    log(f"labelled {len(faces_)} faces as {'/'.join(subtypes)}: {near} by the nearest, {none} in none, {len(claims)} claimed by two")
    return out, claims


def main():
    con = duckdb.connect()
    con.execute("LOAD spatial; SET memory_limit='800MB'; SET threads=2")
    info, geoms = divisions(con)
    rings, poly, hole, area, E, cand = load_coast()
    lines = border_lines(con, info, E)
    log(len(rings), "coast rings,", sum(len(r) for r in rings), "fine points")
    attach(lines, rings, E, cand)
    lines = prune(connect(lines))
    arcs, ring_arcs = coast_arcs(rings, lines)
    first_line = len(arcs)
    arcs += line_arcs(lines)
    log(len(arcs), "arcs,", sum(len(a.c) for a in arcs), "points")
    fix_crossings(arcs, rings, lines)
    dedupe(arcs)
    split_junctions(arcs, ring_arcs, node_crossings(arcs))
    log(len(arcs), "arcs,", sum(len(a.c) for a in arcs), "points after the crossings")
    cf = faces(arcs, ring_arcs, poly, hole, ("country",))
    c_lab, c_claims = label(cf, info, geoms, ("country", "dependency"))
    rf = faces(arcs, ring_arcs, poly, hole, ("country", "region"))
    rc_lab, _ = label(rf, info, geoms, ("country", "dependency"))
    within = [info[d]["country"] if d else None for d in rc_lab]
    r_lab, _ = label(rf, info, geoms, ("region",), within=within)
    pickle.dump({"arcs": [(a.c, a.kind, a.src, a.cut) for a in arcs], "ring_arcs": ring_arcs, "poly": poly, "hole": hole, "area": area,
                 "lines": [{k: v for k, v in l.items() if k != "c"} for l in lines], "first_line": first_line,
                 "country_faces": [(shapely.to_wkb(f), p) for f, p in cf], "country_labels": c_lab, "claims": c_claims,
                 "region_faces": [(shapely.to_wkb(f), p) for f, p in rf], "region_country": rc_lab, "region_labels": r_lab,
                 "info": info}, open(OUT, "wb"))
    log("topology written", OUT)


if __name__ == "__main__":
    main()
