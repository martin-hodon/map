"""STAGE 6 -- THE AREAS: the named parts of the world that have no border of their own in OSM -- oceans, seas, gulfs,
bays, straits; mountain ranges, deserts, plateaus, plains, basins, peninsulas, islands and island groups, continents --
made of the map's own lines. Also their named points: peaks, capes, waterfalls, passes.

    .venv/bin/python build/areas.py     # work/topology.pkl -> work/areas.pkl (for build/write.py), data/natural_points.csv
    .venv/bin/python build/areas.py islands   # + every other landmass Wikidata knows as an island, named (into work/areas.pkl)

The areas are Natural Earth's (public domain, 1:10m, raw/ne/): its marine polygons and its geographic regions. An area
is two kinds of line: the COAST, which is natural and already the map's, and the lines ACROSS -- from cape to cape
where a gulf opens into its sea, over the neck of a peninsula, round a range. Every line is drawn once, and the areas
(and the land, and the countries) share it:
  * an island, or a group of them, is the landmasses it covers (most of each inside Natural Earth's outline): only
    coast -- Iceland the island and Iceland the country are the same line;
  * any other area is cut out of the world by the coast and its outline: the part of Natural Earth's outline that
    is on its side of the coast (in the water for a sea, on the land for a range) becomes lines, ending exactly where
    they meet the coast (the point goes into the coast arc, which is split there). All areas' lines are joined into
    one set (a line two seas share is one line) and simplified to AREA_KM where that does not take them over the
    coast. Then the coast and those lines cut the world into faces; an area is the faces on its side of the coast
    that lie mostly inside Natural Earth's outline -- a sea is water only (build/write.py leaves it no holes for its
    islands: they are drawn over it), a range land only --
    and the SLIVERS: where Natural Earth's coast runs a little off the map's, the thin faces between the two go to
    the area they border most. (Lines left inside an area are dropped from the file: build/write.py.)
  * a sea that has no water of the map's own (the Caspian: OSM's coast leaves it to the lakes) is its lakes.
`mask` in the properties says which side it is on: "water" or "land".
"""
import os, sys, re, json, time, pickle, collections
import numpy as np, shapely
from shapely import STRtree
import shapely.ops
from shapely.ops import polylabel
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config, topology, wdnames
from topology import Arc

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NE = os.path.join(ROOT, "raw/ne")
AREA_KM = 2.0               # the lines across: their detail
T0 = time.time()

# Natural Earth's classes -> kind; not listed: left out
MARINE = {"ocean": "ocean", "sea": "sea", "gulf": "gulf", "bay": "bay", "strait": "strait", "sound": "sound", "channel": "channel",
          "lagoon": "lagoon", "fjord": "fjord", "inlet": "inlet", "river": "estuary", "reef": "reef"}
REGIONS = {"Range/mtn": "mountains", "Pen/cape": "peninsula", "Peninsula": "peninsula", "Island": "island", "Island group": "islands",
           "Plateau": "plateau", "Desert": "desert", "Geoarea": "region", "Coast": "coast", "Plain": "plain", "Delta": "delta",
           "Basin": "basin", "Continent": "continent", "Valley": "valley", "Lowland": "lowland", "Tundra": "tundra",
           "Isthmus": "isthmus", "Wetlands": "wetlands", "Gorge": "gorge", "Foothills": "foothills", "Depression": "depression",
           "Lake": "lake"}
POINTS = {"mountain": "peak", "spot elevation": "peak", "depression": "depression", "plateau": "plateau", "pass": "pass",
          "cape": "cape", "waterfall": "waterfall", "pole": "pole", "island": "island", "plain": "plain", "island group": "islands"}
WHOLE = ("island", "islands")   # (made of whole landmasses)


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def name_of(name, name_en):
    """Natural Earth writes the big ones in capitals (ALPS): those by their English name"""
    if name and name.isupper():
        return name_en or name.title()
    return name or name_en


def share(f, G):
    """how much of f lies in G (a face polygonize made can touch itself: then as made valid)"""
    try:
        return shapely.intersection(f, G).area / f.area
    except shapely.errors.GEOSException:
        return shapely.intersection(shapely.make_valid(f), G).area / f.area


def ne_areas():
    out = []
    src = [(f, "marine") for f in json.load(open(os.path.join(NE, "ne_10m_geography_marine_polys.geojson")))["features"]] + \
          [(f, "regions") for f in json.load(open(os.path.join(NE, "ne_10m_geography_regions_polys.geojson")))["features"]]
    for f, layer in src:
        p = {k.lower(): v for k, v in f["properties"].items()}
        kind = (MARINE if layer == "marine" else REGIONS).get(p["featurecla"])
        name = name_of(p.get("name"), p.get("name_en"))
        if not kind or not name:
            continue
        g = shapely.make_valid(shapely.from_geojson(json.dumps(f["geometry"])))
        g = shapely.union_all([q for q in shapely.get_parts(g) if q.geom_type in ("Polygon", "MultiPolygon")])
        if g.is_empty:
            continue
        # where its name goes: the point deepest inside its biggest part (as Natural Earth drew it)
        big = max(shapely.get_parts(g), key=lambda q: q.area)
        lab = polylabel(big, tolerance=max(0.01, (big.area ** 0.5) / 100))
        out.append({"G": g, "mask": "water" if layer == "marine" or kind == "lake" else "land",
                    "props": {"name": name, "name_en": p.get("name_en") if p.get("name_en") != name else None, "kind": kind,
                              "mask": "water" if layer == "marine" or kind == "lake" else "land", "rank": p.get("scalerank"),
                              "wikidata": p.get("wikidataid") or None, "label": [round(lab.x, 3), round(lab.y, 3)]}})
    return out


def seg_km(c):
    """the lengths of a line's segments in km (flat, each round its middle)"""
    dx = (np.diff(c[:, 0]) + 180.0) % 360.0 - 180.0
    return 111.0 * np.hypot(dx * np.cos(np.radians((c[1:, 1] + c[:-1, 1]) / 2)), np.diff(c[:, 1]))


def setup():
    """the map as stage 2 left it: its arcs (coast arcs knowing their ring), the landmasses, the coast as segments"""
    T = pickle.load(open(os.path.join(ROOT, "work/topology.pkl"), "rb"))
    ring_arcs = T["ring_arcs"]
    ring_of = {i: r for r, ids in enumerate(ring_arcs) for i in ids}
    arcs = [Arc(c, kind, src, 0, 0, None, ring=ring_of.get(i), cut=cut) for i, (c, kind, src, cut) in enumerate(T["arcs"])]
    polys, pids = topology.land_polygons(arcs, ring_arcs, T["poly"], T["hole"])
    land = [p if shapely.is_valid(p) else shapely.make_valid(p) for p in polys]
    seg_arc, seg_j, segs = [], [], []
    for i, a in enumerate(arcs):
        if a.kind == "coast" and not a.cut and len(a.c) > 1:
            segs.append(np.stack((a.c[:-1], a.c[1:]), axis=1)); seg_arc.append(np.full(len(a.c) - 1, i)); seg_j.append(np.arange(len(a.c) - 1))
    arc_pos, ring_km = np.zeros(len(arcs)), np.zeros(len(ring_arcs))   # (where each arc starts on its ring, in km)
    for r, ids in enumerate(ring_arcs):
        for i in ids:
            arc_pos[i] = ring_km[r]; ring_km[r] += seg_km(arcs[i].c).sum()
    seg_pos = np.concatenate([arc_pos[i] + np.r_[0.0, np.cumsum(seg_km(arcs[i].c))[:-1]] for i in (a[0] for a in seg_arc)])
    S = {"T": T, "arcs": arcs, "ring_arcs": ring_arcs, "polys": polys, "land": land, "ltree": STRtree(land),
         "seg_pos": seg_pos, "seg_len": np.concatenate([seg_km(arcs[a[0]].c) for a in seg_arc]), "ring_km": ring_km,
         "seg_arc": np.concatenate(seg_arc), "seg_j": np.concatenate(seg_j), "segs": np.concatenate(segs),
         "seg_ring": np.array([-1 if a.ring is None else a.ring for a in arcs])[np.concatenate(seg_arc)],
         "ctree": STRtree(shapely.linestrings(np.concatenate(segs)))}
    log(len(land), "landmasses,", len(S["seg_arc"]), "coast segments")
    return S


def across(A, S):
    """an area's lines across: all of its outline that is on its side of the coast (a sea's in the water, a range's on
    the land). Each piece ends exactly on the coast (it was cut there). -> [coords]"""
    return on_side(shapely.boundary(A["G"]), A["G"], A["mask"], S, ALONG_KM)


def on_side(B, G, mask, S, near_km=None):
    """the part of the lines B on one side of the coast ("water" or "land"; G: what to look for land near), cut where
    they meet it, without the pieces that only run along it (hugs) -> [coords]. build/bio.py cuts the ecoregions'
    borders so."""
    near = S["ltree"].query(shapely.buffer(G, 0.05))
    if mask == "land" and len(near) == 1 and B.geom_type == "LineString":   # (a line well inside one landmass -- most
        P = S["land"][near[0]]                                                # of a country's inner borders: as it is)
        shapely.prepare(P)
        if shapely.contains_properly(P, B):
            c = shapely.get_coordinates(B)
            return [c] if geo.length_km(c) >= 0.05 else []
    L = shapely.multipolygons([q for i in near for q in shapely.get_parts(S["land"][i]) if q.geom_type == "Polygon"]) if len(near) else None
    op = shapely.difference if mask == "water" else shapely.intersection
    try:
        part = B if L is None else op(B, L)
    except shapely.errors.GEOSException:                     # (two landmasses overlapping across a strait of 100 m)
        part = op(B, shapely.union_all(shapely.get_parts(L)))
    out = []
    for p in shapely.get_parts(shapely.line_merge(part)):
        if p.geom_type != "LineString" or p.is_empty:
            continue
        for c in (along(shapely.get_coordinates(p), S, near_km, G) if near_km else [shapely.get_coordinates(p)]):
            if geo.length_km(c) >= 0.05 and not hugs(c, S, near_km or NEAR_KM, G):
                out.append(c)
    return out


def coast_km(pts, S, r_km, segs=False):
    """for each point its distance to the coast in km (as on the ground, not in degrees: at 80 N a degree of
    longitude is 19 km) and the ring of the nearest coast -- np.inf and -1 where none is within r_km (segs: and
    the nearest coast segment's index, -1 so, and where on its ring that nearest point is, in km)"""
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    d, ring, near, pos = np.full(len(pts), np.inf), np.full(len(pts), -1), np.full(len(pts), -1), np.zeros(len(pts))
    if not len(pts):
        return (d, ring, near, pos) if segs else (d, ring)
    cos = np.maximum(np.cos(np.radians(pts[:, 1])), 0.01)
    r = r_km / 111.0
    boxes = shapely.box(pts[:, 0] - r / cos, pts[:, 1] - r, pts[:, 0] + r / cos, pts[:, 1] + r)
    pi, si = S["ctree"].query(boxes)
    if not len(pi):
        return (d, ring, near, pos) if segs else (d, ring)
    P, seg = pts[pi], S["segs"][si]                         # (each pair in km, flat round its point)
    k = cos[pi][:, None]
    def flat(q):
        return np.column_stack((((q[:, 0] - P[:, 0] + 180.0) % 360.0 - 180.0) * k[:, 0], q[:, 1] - P[:, 1])) * 111.0
    a, b = flat(seg[:, 0]), flat(seg[:, 1])
    ab = b - a
    t = np.clip(-(a * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0.0, 1.0)
    dist = np.hypot(*(a + t[:, None] * ab).T)
    order = np.lexsort((dist, pi))                          # (per point its nearest: the first of its pairs by distance)
    first = order[np.r_[True, pi[order][1:] != pi[order][:-1]]]
    d[pi[first]] = dist[first]
    ring[pi[first]] = S["seg_ring"][si[first]]
    near[pi[first]] = si[first]
    pos[pi[first]] = S["seg_pos"][si[first]] + t[first] * S["seg_len"][si[first]]
    ring[d > r_km] = near[d > r_km] = -1
    d[d > r_km] = np.inf
    return (d, ring, near, pos) if segs else (d, ring)


def jumps(pts, ring, pos, S, near_km, G=None):
    """between each point and the next: does the nearest coast jump -- from one shore of a bay's mouth to the
    other, its whole shore away, rather than going on along the coast as a line along it does? -> bool per step.
    No G (the arcs into_coast drops: any area's): every jump. G an area's outline (a polygon): only where the
    shore jumped over is the area's own (Sherman Basin, behind
    the zigzag across its mouth) -- a sea's outline past a fjord's mouth jumps over the fjord, which is not the
    sea's, and the fjord may be the sea's face's too. G a line (build/bio.py's borders, cut by themselves): none --
    a border is no outline of a basin, and the coast it runs along is RESOLVE's or CShapes' own"""
    step = seg_km(pts)
    same = (ring[1:] == ring[:-1]) & (ring[1:] >= 0)
    L = S["ring_km"][np.maximum(ring[1:], 0)]
    a, b = pos[:-1], pos[1:]
    gone = np.abs(b - a)
    out = same & (np.minimum(gone, L - gone) > 2 * step + near_km)
    if G is not None and G.geom_type not in ("Polygon", "MultiPolygon"):
        return np.zeros_like(out)                            # (lines, not an area's outline -- bio's, history's: no test)
    if G is None or not out.any():
        return out
    shapely.prepare(G)
    for k in np.flatnonzero(out):                            # (the shore jumped over: the shorter way round its ring)
        lo, hi = min(a[k], b[k]), max(a[k], b[k])
        x = lo + (hi - lo) * np.linspace(0.1, 0.9, 9) if hi - lo <= L[k] / 2 else (hi + (L[k] - hi + lo) * np.linspace(0.1, 0.9, 9)) % L[k]
        q = ring_point(int(ring[k + 1]), x, S)
        out[k] = shapely.dwithin(G, shapely.points(q), 0.02).sum() > len(q) / 2
    return out


def ring_point(r, x, S):
    """the points of coast ring r at x km along it -> [[lon, lat]]"""
    if "ring_order" not in S:
        o = np.lexsort((S["seg_pos"], S["seg_ring"]))
        S["ring_order"], S["ring_from"] = o, np.searchsorted(S["seg_ring"][o], np.arange(len(S["ring_km"]) + 1))
    o = S["ring_order"][S["ring_from"][r]:S["ring_from"][r + 1]]
    j = o[np.clip(np.searchsorted(S["seg_pos"][o], x, side="right") - 1, 0, len(o) - 1)]
    t = np.clip((x - S["seg_pos"][j]) / np.maximum(S["seg_len"][j], 1e-12), 0.0, 1.0)[:, None]
    return S["segs"][j, 0] + t * (S["segs"][j, 1] - S["segs"][j, 0])


def along(c, S, near_km, G=None):
    """a piece without its stretches ALONG the coast: where it keeps within near_km of one coast ring for a stretch
    at least near_km long and four times as long as it ever stands off (a line across a bay's mouth stands off by half
    its length: it stays), its nearest coast going on along the coast with it (across a mouth it jumps: jumps) -- Natural Earth's coast beside the map's, in a piece that also goes across somewhere, which
    hugs, taking the piece whole, keeps. What is left of it ends off the coast and is tied to it (tie_loose_ends), so
    the area follows the map's coast there. A closed piece (the outline of a range wholly on land, along the coast
    for a stretch: the Taurus) is read from its point farthest off the coast; one never as far as near_km from it
    (a loop of the outline in the water: all of Maputo Bay the map has) stays whole. -> [coords]"""
    if np.array_equal(c[0], c[-1]):                          # (a ring: from its vertex farthest off the coast)
        d = coast_km(c[:-1], S, near_km)[0]
        if d.max() < near_km:
            return [c]
        k = int(np.argmax(d))
        c = np.vstack((c[k:-1], c[:k + 1]))
    pts = shapely.get_coordinates(shapely.segmentize(shapely.linestrings(c), 0.01))
    own = np.zeros(len(pts), bool)                         # (the piece's own vertices: only they and the cuts are kept --
    j = 0                                                  #  the points segmentize put in are for the measure)
    for k in range(len(pts)):
        if j < len(c) and np.array_equal(pts[k], c[j]):
            own[k] = True; j += 1
    d, ring, _, pos = coast_km(pts, S, near_km, segs=True)
    jump = np.r_[jumps(pts, ring, pos, S, near_km, G), False]
    step = np.r_[0.0, [geo.length_km(pts[k - 1:k + 1]) for k in range(1, len(pts))]]
    cut = np.zeros(len(pts), bool)
    i = 0
    while i < len(pts):
        if d[i] >= near_km or ring[i] < 0:
            i += 1; continue
        j = i
        while j + 1 < len(pts) and d[j + 1] < near_km and ring[j + 1] == ring[i] and not jump[j]:
            j += 1
        km = step[i + 1:j + 1].sum()
        if km >= near_km and km >= 4 * d[i:j + 1].max():
            cut[i + 1:j] = True                              # (its ends stay: the pieces either side end there)
            if i == 0: cut[0] = True
            if j == len(pts) - 1: cut[j] = True
        i = j + 1
    if not cut.any():
        return [c]
    out, run = [], []
    for k in range(len(pts)):
        if cut[k]:
            if len(run) > 1: out.append(np.array(run))
            run = []
        elif own[k] or not run or k + 1 == len(pts) or cut[k + 1]:
            run.append(pts[k])
    if len(run) > 1:
        out.append(np.array(run))
    return out


def tie_loose_ends(lines, S, near_km=None):
    """a line whose end meets no other line and is not on the coast, but is near it (where a piece along the coast
    was dropped as hugging -- one area's outline shares it with another's, which went on across from there):
    a connector from that end to the nearest coast point within twice near_km (what hugs drops), so the face closes
    there -> lines + connectors"""
    ends = collections.Counter()
    for c in lines:
        ends[(float(c[0][0]), float(c[0][1]))] += 1; ends[(float(c[-1][0]), float(c[-1][1]))] += 1
    add = []
    for c in lines:
        for p in (c[0], c[-1]):
            if ends[(float(p[0]), float(p[1]))] == 1:
                q = to_coast(p, S)
                km = geo.length_km(np.array([p, q]))
                if 1e-6 < km <= 2 * (near_km or NEAR_KM):
                    add.append(np.array([p, q]))
    log(len(add), "loose ends near the coast tied to it")
    return lines + add


def tie_to_lines(lines, S, km):
    """a line end that meets no other line and is not on the coast (two lines of one junction simplified a few metres
    apart): a connector from it to the nearest point of another line within km -> lines + connectors (the point on
    that line becomes a junction: topology.split_junctions)"""
    ends = collections.Counter()
    for c in lines:
        ends[(float(c[0][0]), float(c[0][1]))] += 1; ends[(float(c[-1][0]), float(c[-1][1]))] += 1
    geoms = [shapely.linestrings(c) for c in lines]
    tree = STRtree(geoms)
    add = []
    for n, c in enumerate(lines):
        for p in (c[0], c[-1]):
            if ends[(float(p[0]), float(p[1]))] != 1:
                continue
            pt = shapely.points(np.asarray(p, dtype=float))
            _, d = S["ctree"].query_nearest(pt, return_distance=True, all_matches=False)
            if len(d) and d[0] <= 1e-7:                          # (on the coast: insert_ends takes it)
                continue
            near = [j for j in tree.query(shapely.buffer(pt, km / 111.0)).tolist() if j != n]
            if not near:
                continue
            j = min(near, key=lambda j: shapely.distance(geoms[j], pt))
            q = shapely.get_coordinates(shapely.ops.nearest_points(geoms[j], pt)[0])[0]
            if 1e-9 < geo.length_km(np.array([p, q])) <= km:
                add.append(np.array([p, q]))
                c = lines[j]                                     # (q a vertex of that line too: split_junctions cuts at vertices)
                if not np.all(c == q, axis=1).any():
                    segs = shapely.linestrings(np.stack((c[:-1], c[1:]), axis=1))
                    s = int(np.argmin(shapely.distance(segs, shapely.points(q))))
                    lines[j] = np.vstack((c[:s + 1], [q], c[s + 1:]))
    log(len(add), "loose ends tied to the nearest line within", km, "km")
    return lines + add


def to_coast(p, S, r_km=50.0):
    """the point of the coast nearest p (on the ground, within r_km; else in degrees), on its segment exactly (as
    insert_ends wants it)"""
    si = coast_km(np.asarray(p, dtype=float)[None], S, r_km, segs=True)[2]
    if si[0] < 0:
        si = S["ctree"].query_nearest(shapely.points(np.asarray(p, dtype=float)[None]), all_matches=False)[1]
    a, b = S["segs"][int(si[0])]
    k = np.cos(np.radians(p[1]))                             # (the foot of the perpendicular, flat round p)
    ab, ap = (b - a) * (k, 1.0), (np.asarray(p) - a) * (k, 1.0)
    t = float(np.clip(np.dot(ap, ab) / max(np.dot(ab, ab), 1e-18), 0.0, 1.0))
    return a + t * (b - a)


NEAR_KM = 3.0               # an outline piece never farther than this from the coast, and flat along it, is the coast, not a line across
ALONG_KM = 6.0              # ...for an area's outline (Natural Earth's coast at 1:10m strays that far): a sea follows the map's
                            # coast, never a line of its own a few km off it


def hugs(c, S, near_km=NEAR_KM, G=None):
    """does the piece run along the coast (Natural Earth's coast, a little off the map's: round Lesbos, along
    Guinea) rather than across the water? Never farther from the coast than near_km, and than a quarter of its
    length -- a line across a strait stands off the coast by half its length at its middle -- and from one point
    of a coast ring to another of the same ring, which then closes the face by itself (a piece along a chain of
    islets, an atoll's rim, is what closes the face there, and stays). Its nearest coast never jumps: a zigzag across
    the narrow mouth of a basin (Sherman Basin's) is near the coast all the way, and stays."""
    km = geo.length_km(c)
    pts = shapely.get_coordinates(shapely.segmentize(shapely.linestrings(c), 0.01))
    d, ring, _, pos = coast_km(pts, S, near_km, segs=True)
    far = float(d.max()) if len(pts) else 0.0
    if not (far < near_km and far < 0.25 * km) or jumps(pts, ring, pos, S, near_km, G).any():
        return False
    (_, si), de = S["ctree"].query_nearest(shapely.points(c[[0, -1]]), return_distance=True, all_matches=False)
    if len(si) < 2 or de.max() > 1e-7:
        return False
    rings = [S["arcs"][int(S["seg_arc"][int(x)])].ring for x in si]
    return rings[0] is not None and rings[0] == rings[1]


def simplified(c, S):
    """a line across at AREA_KM -- or finer, where that would take it over an island or a cape"""
    for eps in (AREA_KM, config.EPS_KM):
        simple = c[geo.simplify(geo.to_xyz(c), eps)]
        if len(simple) == len(c) or not over_coast(simple, S):
            return simple
    return c


def merge_ends(lines, S, tol=1e-5, inland=False):
    """line ends closer than tol (~1 m) are one point -- the one on the coast, if one is: several lines meeting the coast
    a centimetre apart would cut it into arcs of a centimetre, finer than a coordinate can tell. `inland`: only the
    ends off the coast (before the lines are joined: two ends made one ON the coast would be joined into one line
    through it, which then no longer ends there)"""
    ends = np.array([p for c in lines for p in (c[0], c[-1])])
    parent = np.arange(len(ends))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    (_, si), d = S["ctree"].query_nearest(shapely.points(ends), return_distance=True, all_matches=False)
    for i, j in cKDTree(ends).query_pairs(tol, output_type="ndarray").tolist():
        if not inland or min(d[i], d[j]) > 1e-9:
            parent[find(j)] = find(i)
    best = {}
    for i in range(len(ends)):
        r = find(i)
        if r not in best or d[i] < d[best[r]]:
            best[r] = i
    moved = 0
    for n, c in enumerate(lines):
        for e, i in ((0, 2 * n), (-1, 2 * n + 1)):
            b = best[find(i)]
            if b != i:
                c[e] = ends[b]; moved += 1
    log(moved, "line ends merged into another within", tol, "degrees")
    return [c for c in lines if not np.all(c == c[0])]


def insert_ends(S, pts):
    """the points where lines across meet the coast, put into the coast arcs (each lies on a coast segment already:
    the coast does not move) -> (their keys, for split_junctions; the points that are new vertices)"""
    arcs, add = S["arcs"], collections.defaultdict(list)
    P = np.array(pts)
    (_, si), d = S["ctree"].query_nearest(shapely.points(P), return_distance=True, all_matches=False)
    keys, added = [], []
    for p, s_, dd in zip(P, si.tolist(), d.tolist()):
        if dd > 1e-7:                                        # (not on the coast: a line that ends in the open)
            continue
        a, j = int(S["seg_arc"][s_]), int(S["seg_j"][s_])
        c = arcs[a].c
        keys.append(int(geo.key(p)))
        if np.all(c[j] == p) or np.all(c[j + 1] == p):
            continue
        add[a].append((j, float(np.hypot(*(p - c[j]))), p)); added.append(p)
    for a, ins in add.items():
        c = arcs[a].c
        ins = sorted({(j, t): p for j, t, p in ins}.items())
        rows, last = [], 0
        for (j, t), p in ins:
            rows.append(c[last:j + 1]); rows.append(p[None]); last = j + 1
        rows.append(c[last:])
        arcs[a].c = np.vstack(rows)
    log(len(keys), "ends of lines across on the coast,", sum(len(v) for v in add.values()), "of them new coast vertices")
    return np.array(keys, dtype=np.int64), added


def twin_lines(lines, tol=0.005):
    """lines -> without one of two with the same two ends on one path (within tol): ends merged (merge_ends) can make
    two lines that were apart one -- the Saskatchewan-Manitoba border, from two sources, straight from corner to
    corner --, and a line end tied to one of them only (tie_to_lines) leaves the faces beside them unreadable"""
    by, out = collections.defaultdict(list), []
    for c in lines:
        k0, k1 = int(geo.key(c[0])), int(geo.key(c[-1]))
        same = by[(min(k0, k1), max(k0, k1))]
        if k0 != k1 and any(shapely.hausdorff_distance(shapely.linestrings(c), shapely.linestrings(d)) <= tol for d in same):
            continue
        same.append(c); out.append(c)
    log(len(lines) - len(out), "lines dropped as the same path as another")
    return out


def drop_twins(arcs, tol=0.005):
    """a line across with the same two ends as another line, and on its path (within tol, ~500 m): dropped -- a
    coast that Natural Earth's outline follows for a stretch; two lines on one path make a loop of no area, and a
    face cannot close through it"""
    by = collections.defaultdict(list)
    for i, a in enumerate(arcs):
        if a.kind in ("coast", "area"):
            k0, k1 = int(geo.key(a.c[0])), int(geo.key(a.c[-1]))
            by[(min(k0, k1), max(k0, k1))].append(i)
    n = 0
    for ids in by.values():
        if len(ids) < 2:
            continue
        for i in ids:
            a = arcs[i]
            if a.kind != "area":
                continue
            for j in ids:
                if j != i and arcs[j].kind in ("coast", "area") and shapely.hausdorff_distance(shapely.linestrings(a.c), shapely.linestrings(arcs[j].c)) <= tol:
                    a.kind = "dup"; n += 1
                    break
    log(n, "lines across dropped as the same path as another line")


def drop_hugging(arcs, S, near_km):
    """a line across cut into arcs -- where it crosses the coast (simplified over a headland), where another line meets
    it -- can leave arcs that only run along the coast, from a point of a coast ring to another of the same ring
    (hugs), though the line as a whole stood off it somewhere: dropped, as such a line would have been; the sliver
    between it and the coast is then part of the face beside it, and the area follows the coast there"""
    n = pts = 0
    for a in arcs:
        if a.kind == "area" and len(a.c) > 1 and hugs(a.c, S, near_km):
            a.kind = "dup"; n += 1; pts += len(a.c)
    log(n, "arcs of lines across dropped as running along the coast,", pts, "points")


def refit_faces(T, pts):
    """the country and state faces of stage 2, given the points insert_ends put into the coast (each on a segment of
    theirs already): so they still follow the arcs vertex by vertex. -> (country faces, region faces)"""
    pts = np.asarray(pts, dtype=float).reshape(-1, 2)
    tree = STRtree(shapely.points(pts)) if len(pts) else None
    out = []
    for key in ("country_faces", "region_faces"):
        faces, n = [], 0
        for w, pid in T[key]:
            if tree is not None:
                f = shapely.from_wkb(w)
                near = tree.query(f, predicate="dwithin", distance=1e-7)
                if len(near):
                    w = shapely.to_wkb(shapely.snap(f, shapely.multipoints(pts[near]), 1e-9)); n += 1
            faces.append((w, pid))
        out.append(faces)
        log(f"  {key}: {n} given coast points of lines across")
    return out


def over_coast(c, S):
    """does the line cross the coast anywhere but at its ends?"""
    line = shapely.linestrings(c)
    hit = S["ctree"].query(line, predicate="intersects")
    if not len(hit):
        return False
    x = shapely.get_coordinates(shapely.intersection(line, shapely.union_all(S["ctree"].geometries[hit])))
    return bool(len(x) and np.any(np.min(np.stack([np.abs(x - c[0]).sum(1), np.abs(x - c[-1]).sum(1)]), axis=0) > 1e-9))


SLIVER_DEG = 0.03           # a face thinner than this (~3 km: twice its area over its outline) is a sliver between two coasts


def complete(sel, S):
    """the lines near an area (positions in S["use"]), completed: every coast ring one of them is on or ends on, whole,
    and the lines across that meet them at an end -- else a line whose far end is just outside would dangle and the
    face it closes would not close"""
    arcs, use, pos = S["arcs"], S["use"], S["pos"]
    need, rings = set(sel), set()
    for i in sel:
        a = arcs[use[i]]
        for k in (int(geo.key(a.c[0])), int(geo.key(a.c[-1]))):
            for j in S["coast_at"].get(k, ()):
                rings.add(arcs[j].ring)
            if a.kind == "area":
                need.update(pos[j] for j in S["area_at"].get(k, ()))
        if a.kind == "coast":
            rings.add(a.ring)
    for r in rings:
        need.update(pos[j] for j in S["ring_arcs"][r])
    return sorted(need)


def faces_of(n, A, S, atree, ageoms, gtree, areas):
    """the faces of the coast and the lines across on the area's side of the coast that are mostly inside it -- and
    the slivers (between Natural Earth's coast and the map's) that border it more than any other area"""
    G, kind, out = A["G"], A["props"]["kind"], []
    if kind in WHOLE:                                        # (an island: its landmasses whole)
        for i in S["ltree"].query(G).tolist():
            if share(S["land"][i], G) >= 0.5:
                out.append(S["polys"][i])
        return out
    lines = [ageoms[k] for k in complete(atree.query(shapely.box(*shapely.bounds(shapely.buffer(G, 0.3)))).tolist(), S)]
    for f in topology.polygonize(lines):
        on_land = len(S["ltree"].query(shapely.point_on_surface(f), predicate="within")) > 0
        if on_land != (A["mask"] == "land"):
            continue
        if share(f, G) >= 0.5:
            out.append(f)
        elif 2 * f.area / max(f.length, 1e-12) < SLIVER_DEG:
            around = shapely.buffer(f, SLIVER_DEG)
            best = max(((shapely.intersection(areas[i]["G"], around).area, i) for i in gtree.query(around).tolist()
                        if areas[i]["mask"] == A["mask"] and areas[i]["props"]["kind"] not in WHOLE), default=(0, None))
            if best[1] == n and best[0] > 0 and share(f, G) >= max(share(f, areas[i]["G"]) for i in gtree.query(f).tolist()):
                out.append(f)
    return out


def ends_onto_lines(lines, tol=1e-5):
    """a line end on another line, between two of its vertices (within tol, ~1 m): made a vertex of that one too -- two
    areas' outlines along one coast, each cut where it leaves the coast (along), end at different points of one
    segment; one then lies on the other, a hair off it, and they overlap unnoded (no face closes there: all Florida)"""
    geoms = [shapely.linestrings(c) for c in lines]
    tree = STRtree(geoms)
    ends = np.array([p for c in lines for p in (c[0], c[-1])])
    pi, li = tree.query(shapely.points(ends), predicate="dwithin", distance=tol)
    add = collections.defaultdict(list)
    for e, j in zip(pi.tolist(), li.tolist()):
        if j == e // 2:
            continue
        c, p = lines[j], ends[e]
        if np.abs(c - p).sum(1).min() <= tol:                 # (at a vertex of it already, or near enough: merge_ends')
            continue
        segs = shapely.linestrings(np.stack((c[:-1], c[1:]), axis=1))
        add[j].append((int(np.argmin(shapely.distance(segs, shapely.points(p)))), p))
    out = list(lines)
    for j, got in add.items():
        c = lines[j]
        by = collections.defaultdict(list)
        for k, p in got:
            by[k].append(p)
        rows = []
        for k in range(len(c) - 1):
            rows.append(c[k])
            ps = sorted(by.get(k, ()), key=lambda p: float(np.hypot(*(p - c[k]))))
            rows += ps
        rows.append(c[-1])
        out[j] = np.array(rows)
    log(sum(len(v) for v in add.values()), "line ends made vertices of the line they are on")
    return out


def split_on_coast(lines, S):
    """lines cut again at their inner vertices on the coast: line_merge joins two lines that end at one coast point
    (a gulf's mouth and the sea's outline beside it, both from one cape) into one through it, which then no longer
    ends there -- and where the two run off nearly together, the polygonizer gets a loop there and back, and the
    gulf no face"""
    out = []
    for c in lines:
        if len(c) < 3:
            out.append(c); continue
        on = S["ctree"].query(shapely.points(c[1:-1]), predicate="dwithin", distance=1e-9)[0] + 1
        bounds = [0, *np.unique(on).tolist(), len(c) - 1]
        out += [c[x:y + 1] for x, y in zip(bounds[:-1], bounds[1:])]
    return out


def into_coast(pieces, S, tie_km=0.0, near_km=NEAR_KM, hug_arcs=False):
    """the pieces of the lines across (linestrings) made the map's: joined into one set (a line two areas share once),
    simplified to AREA_KM, noded, their ends merged and tied to the coast and put into it (the coast arcs split there),
    and added to S["arcs"] as kind "area"; S["polys"] read again with the new coast points -> (lines, the new coast
    vertices: the country faces get them too). build/bio.py makes the ecoregions' borders so as well, with tie_km: a
    line end that meets nothing, off the coast, is tied to the nearest line within that (tie_to_lines). hug_arcs: the
    arcs they are cut into dropped where they only run along the coast (drop_hugging)"""
    arcs, ring_arcs = S["arcs"], S["ring_arcs"]
    # (ends a hair apart -- one junction, each line cut to the coast on its own -- made one first: joined, a line would
    # run on through it, and the third line ending there would hang)
    pieces = [shapely.linestrings(c) for c in ends_onto_lines(merge_ends([shapely.get_coordinates(g) for g in pieces], S, inland=True))]
    lines = [simplified(c, S) for c in split_on_coast([shapely.get_coordinates(g) for g in shapely.get_parts(shapely.line_merge(shapely.unary_union(shapely.multilinestrings(pieces))))], S)]
    # (simplified, two lines can cross where they did not meet: noded once more, or no face would close there)
    lines = split_on_coast([shapely.get_coordinates(g) for g in shapely.get_parts(shapely.line_merge(shapely.unary_union(shapely.multilinestrings([shapely.linestrings(c) for c in lines]))))], S)
    lines = twin_lines(merge_ends(lines, S))
    lines = tie_loose_ends(lines, S, near_km)
    if tie_km:
        lines = tie_to_lines(lines, S, tie_km)
    keys, added = insert_ends(S, [p for c in lines for p in (c[0], c[-1])])
    # (none of no length, and no loop there and back -- A to B to A, two ends merged: one edge twice, and GEOS's
    # polygonizer then loses the face around it, all of Thailand)
    arcs += [Arc(c, "area", "area", 0, 0, None) for c in lines if len(c) > 1 and not np.all(c == c[0])
             and not (np.array_equal(c[0], c[-1]) and len(np.unique(c[:-1], axis=0)) < 3)]
    # (a line across that still crosses the coast -- simplified, or Natural Earth's outline through a headland the
    # map has: noded there, or the polygonizer would let the sea into the land)
    xpts = []
    keys = np.concatenate([np.asarray(keys, dtype=np.int64), topology.node_crossings(arcs, xpts)])
    added += [np.asarray(p, dtype=float) for p in xpts]
    topology.split_junctions(arcs, ring_arcs, keys)
    drop_twins(arcs)
    if hug_arcs:
        drop_hugging(arcs, S, near_km)
    S["polys"], _ = topology.land_polygons(arcs, ring_arcs, S["T"]["poly"], S["T"]["hole"])   # (with the new coast points: an island whole is read back by them)
    log(len(lines), "lines across,", sum(len(c) for c in lines), "points")
    return lines, added


def main():
    S = setup()
    arcs, ring_arcs = S["arcs"], S["ring_arcs"]
    areas = ne_areas()
    log(len(areas), "areas from Natural Earth")

    # ---- the lines across, all areas' together: shared pieces once, crossings noded; their ends into the coast
    pieces = []
    for n, A in enumerate(areas):
        if A["props"]["kind"] in WHOLE or A["props"]["kind"] == "lake":
            continue
        pieces += [shapely.linestrings(c) for c in across(A, S)]
        if n % 200 == 0:
            log(f"  {n}/{len(areas)} areas, {len(pieces)} lines across")
    lines, added = into_coast(pieces, S, near_km=ALONG_KM, hug_arcs=True)

    # ---- the faces of each area
    use = [i for i, a in enumerate(arcs) if a.kind in ("coast", "area")]
    ageoms = [shapely.linestrings(arcs[i].c) for i in use]
    S["use"], S["pos"] = use, {j: i for i, j in enumerate(use)}
    S["coast_at"], S["area_at"] = collections.defaultdict(list), collections.defaultdict(list)
    for j in use:
        a = arcs[j]
        for k in (int(geo.key(a.c[0])), int(geo.key(a.c[-1]))):
            (S["coast_at"] if a.kind == "coast" else S["area_at"])[k].append(j)
    atree = STRtree(ageoms)
    lake_list = pickle.load(open(os.path.join(ROOT, "work/lakes.pkl"), "rb")) if os.path.exists(os.path.join(ROOT, "work/lakes.pkl")) else []
    lake_geoms = [shapely.make_valid(shapely.Polygon(L["rings"][0], L["rings"][1:])) for L in lake_list]
    lake_tree = STRtree(lake_geoms) if lake_geoms else None
    gtree = STRtree([A["G"] for A in areas])
    out, empty = [], []
    for n, A in enumerate(areas):
        rec = {"props": A["props"], "faces": [], "lakes": []}
        if A["props"]["kind"] != "lake":
            rec["faces"] = [shapely.to_wkb(f) for f in faces_of(n, A, S, atree, ageoms, gtree, areas)]
        if not rec["faces"] and A["mask"] == "water" and lake_tree is not None:    # (the Caspian: its lakes)
            rec["lakes"] = [i for i in lake_tree.query(A["G"]).tolist() if share(lake_geoms[i], A["G"]) >= 0.5]
        if rec["faces"] or rec["lakes"]:
            out.append(rec)
        else:
            empty.append(A["props"]["name"])
        if n % 100 == 0:
            log(f"  {n}/{len(areas)} areas cut into faces")
    log(len(out), "areas:", dict(collections.Counter(r["props"]["kind"] for r in out).most_common()), f"; {len(empty)} with nothing of the map's own:", empty[:40])
    cf, rf = refit_faces(S["T"], added)
    pickle.dump({"arcs": [(a.c, a.kind, a.src, a.cut) for a in arcs], "ring_arcs": ring_arcs, "areas": out,
                 "country_faces": cf, "region_faces": rf},
                open(os.path.join(ROOT, "work/areas.pkl"), "wb"))
    log("work/areas.pkl written")
    natural_points()


NATURE_COLUMNS = ["name", "lon", "lat", "kind", "elevation_m", "rank", "name_en", "wikidata"]


def natural_points():
    from points import write_points                          # (a table of points, as the cities')
    pts, why = [], collections.Counter()
    for fn in ("ne_10m_geography_regions_elevation_points", "ne_10m_geography_regions_points"):
        for f in json.load(open(os.path.join(NE, fn + ".geojson")))["features"]:
            p = f["properties"]
            kind = POINTS.get(p["featurecla"])
            name = name_of(p.get("name"), p.get("name_en"))
            if not kind or not name or kind in ("island", "islands", "plain"):     # (those are areas already)
                why[p["featurecla"]] += 1
                continue
            lon, lat = f["geometry"]["coordinates"][:2]
            el = p.get("elevation")
            pts.append({"name": name, "lon": lon, "lat": lat, "name_en": p.get("name_en") if p.get("name_en") != name else None,
                        "kind": kind, "elevation_m": int(el) if el not in (None, "", -99, -9999) else None,
                        "rank": p.get("scalerank"), "wikidata": p.get("wikidataid") or None})
    pts.sort(key=lambda r: (99 if r["rank"] is None else r["rank"], -(r["elevation_m"] or 0)))
    path = os.path.join(ROOT, "data/natural_points.csv")
    write_points(pts, NATURE_COLUMNS, path)
    log(f"{path}: {len(pts)} points ({dict(collections.Counter(r['kind'] for r in pts))}); left out {dict(why)}")


ISLAND_RANK = [(10000, 5), (2000, 6), (500, 7), (100, 8), (20, 9), (5, 10)]   # (km2, rank: shown from what zoom -- Natural Earth's islands have 1-7)


def wd_islands():
    """Wikidata's islands (Q23442 and under) with a place: [(qid, English label, lon, lat, area km2 or None)] (cached
    in raw/wd_islands.json)"""
    path = os.path.join(ROOT, "raw/wd_islands.json")
    if not os.path.exists(path):
        rows = wdnames.sparql("""SELECT ?item ?l ?c ?a WHERE { ?item wdt:P31/wdt:P279* wd:Q23442 . ?item wdt:P625 ?c .
            OPTIONAL { ?item rdfs:label ?l FILTER(LANG(?l) = "en") } OPTIONAL { ?item wdt:P2046 ?a } }""")
        out = {}
        for b in rows:
            m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", b["c"]["value"], re.I)
            q = b["item"]["value"].rsplit("/", 1)[-1]
            if m and b.get("l") and q not in out:
                a = b.get("a", {}).get("value")
                out[q] = [b["l"]["value"], float(m.group(1)), float(m.group(2)), float(a) if a else None]
        json.dump(out, open(path, "w"), ensure_ascii=False)
    return [(q, *v) for q, v in json.load(open(path)).items()]


def islands():
    """the landmasses that are no island area yet, named by Wikidata's islands: the island whose place is on the
    landmass (of several, the one most Wikipedias write about), when its area (P2046), if it has one, is that of the
    landmass within a factor of 5 -- else only a small landmass (an islet's item on a continent names nothing)"""
    from types import SimpleNamespace
    from points import Where
    A = pickle.load(open(os.path.join(ROOT, "work/areas.pkl"), "rb"))
    T = pickle.load(open(os.path.join(ROOT, "work/topology.pkl"), "rb"))
    polys, _ = topology.land_polygons([SimpleNamespace(c=a[0]) for a in A["arcs"]], A["ring_arcs"], T["poly"], T["hole"])
    del T
    km2 = [geo.ring_area_km2(np.asarray(p.exterior.coords)) for p in polys]
    tree = STRtree(polys)
    A["areas"] = [r for r in A["areas"] if r["props"].get("src") != "wikidata"]      # (from an earlier run)
    named = set()
    for rec in A["areas"]:
        if rec["props"]["kind"] == "island":                    # (a landmass in a named group -- the Cyclades -- still wants its own name)
            for w in rec["faces"]:
                named.update(tree.query(shapely.point_on_surface(shapely.from_wkb(w)), predicate="within").tolist())
    isl = wd_islands()
    pts = shapely.points(np.array([[x, y] for _, _, x, y, _ in isl]))
    pi, gi = tree.query(pts, predicate="within")
    cands = collections.defaultdict(list)
    for i, g in zip(pi.tolist(), gi.tolist()):
        q, name, x, y, a = isl[i]
        if g in named or abs(km2[g]) < config.MIN_ISLAND_KM2:
            continue
        if (a and 0.2 <= abs(km2[g]) / a <= 5) or (not a and abs(km2[g]) < 200):
            cands[g].append(i)
    wp = wdnames.wikipedias(sorted({isl[i][0] for c in cands.values() for i in c}))
    picks = {g: max(c, key=lambda i: (wp.get(isl[i][0], 0), isl[i][4] is not None)) for g, c in cands.items()}
    where = Where()
    cc, _ = where(np.array([isl[i][2] for i in picks.values()]), np.array([isl[i][3] for i in picks.values()]))
    del where
    local = wdnames.local_labels([(isl[i][0], c) for i, c in zip(picks.values(), cc)])
    for (g, i), c, loc in zip(picks.items(), cc, local):
        q, name, x, y, a = isl[i]
        rank = next((r for lim, r in ISLAND_RANK if abs(km2[g]) >= lim), 11)
        lab = polylabel(polys[g], tolerance=max(0.001, (polys[g].area ** 0.5) / 100))
        A["areas"].append({"props": {"name": name, "name_local": loc if loc and loc != name else None, "kind": "island", "mask": "land",
                                     "rank": rank, "wikidata": q, "wikipedias": wp.get(q) or None, "label": [round(lab.x, 3), round(lab.y, 3)],
                                     "src": "wikidata"},
                           "faces": [shapely.to_wkb(polys[g])], "lakes": []})
    log(len(picks), "landmasses named as islands by Wikidata (of", len(polys), "landmasses,", len(named), "islands named already);",
        sum(1 for i in picks.values() if wp.get(isl[i][0], 0) == 0), "in no Wikipedia; e.g.",
        ", ".join(isl[i][1] for i in list(picks.values())[:15]))
    pickle.dump(A, open(os.path.join(ROOT, "work/areas.pkl"), "wb"))
    log("work/areas.pkl written")


if __name__ == "__main__":
    islands() if sys.argv[1:] == ["islands"] else main()
