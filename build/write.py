"""STAGE 3 -- THE FILE: the topology (stage 2) and the lakes written as one TopoJSON, every shared line stored once.

    .venv/bin/python build/write.py               # -> full/world.topo.json

Objects (every geometry refers to the same arcs -- a coast is stored once whether it bounds the land, a country or
a state):
    land             the land, one polygon per landmass (islands of MIN_ISLAND_KM2 and more)
    coastline        the coast as lines -- the land's outline without the cuts along the antimeridian and the pole
    lakes            the lakes of MIN_LAKE_KM2 and more (their own arcs: a lake is drawn over the land): name (English,
                     from Wikidata, where it has one), name_local, type (lake, reservoir), area_km2, wikidata
    countries        countries and dependencies (Greenland, Puerto Rico, Hong Kong...): iso, name, name_en,
                     subtype, sovereign, label (where its name is written), continent
    country_borders  the land borders between them as lines (a, b: the two sides; disputed)
    regions          the states / provinces of the countries build/topology.py picks (config): iso (ISO 3166-2), name, name_en, country,
                     label, continent
    region_borders   the borders between them as lines
Coordinates are longitude/latitude (WGS 84) on a grid of QUANT_DEG, delta-encoded (the TopoJSON `transform`).
Rings wind as d3-geo expects (outer clockwise, holes anticlockwise, in longitude/latitude with north up);
build/export_geojson.py writes RFC 7946 GeoJSON (the other way round) for tools that want that.
"""
import os, sys, json, pickle, collections, time
import numpy as np, shapely
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config, wdnames

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GAP_DEG = 1e-4             # merge: a ring of faces read back with a gap under this (11 m; the grid is 278 m) is closed over it
STITCH_DEG = 0.05          # ...and a ring chained to the next one starting this near its end, when it stopped short (5 km)
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def signed_area(c):
    """planar, in degrees: > 0 anticlockwise"""
    return 0.5 * float(np.sum(c[:-1, 0] * c[1:, 1] - c[1:, 0] * c[:-1, 1]))


def on_segment(q, a, b, tol=1e-9):
    """is point q on the segment a-b (planar, in degrees)?"""
    d = b - a
    L = float(d @ d)
    t = 0.0 if L == 0 else min(1.0, max(0.0, float((q - a) @ d) / L))
    return float(np.hypot(*(a + t * d - q))) <= tol


class Topo:
    def __init__(self, arcs):
        self.arcs = arcs                                    # float coordinate arrays
        self.keys = [geo.key(c) for c in arcs]
        self.by_start = collections.defaultdict(list)       # an end's key -> [(arc, forward)] (an arc starts at either end)
        for i, k in enumerate(self.keys):
            self.by_start[int(k[0])].append((i, True))
            self.by_start[int(k[-1])].append((i, False))
        self.nodes = set(self.by_start)
        self.verts = np.concatenate(arcs) if arcs else np.zeros((0, 2))
        self.vtree = cKDTree(self.verts)                    # (to put a face's vertex exactly on the arcs' own)

    def coords(self, ring):
        """a ring of signed arc indices (TopoJSON's ~i for reversed) -> its coordinates"""
        out = []
        for a in ring:
            c = self.arcs[a] if a >= 0 else self.arcs[~a][::-1]
            out.append(c if not out else c[1:])
        return np.vstack(out)

    def follow(self, a, fwd, c, k, p):
        """how far arc a (this way round) follows the ring from its vertex p -> the ring index its end is at, or None.
        The arc may have vertices the ring has not, and the ring vertices the arc has not, where they lie on the other's
        segment (points put into the coast after the ring was made: the lines across of stage 6)."""
        n = len(k)
        ac, kk = (self.arcs[a], self.keys[a]) if fwd else (self.arcs[a][::-1], self.keys[a][::-1])
        q = p
        for j in range(1, len(kk)):
            # (a vertex of the ring the arc has not, on the arc's segment: passed)
            while int(kk[j]) != k[(q + 1) % n] and q - p < n and on_segment(c[(q + 1) % n], ac[j - 1], ac[j]):
                q += 1
            if int(kk[j]) == k[(q + 1) % n]:
                q += 1
            elif not on_segment(ac[j], c[q % n], c[(q + 1) % n]):
                return None
            if q - p > n:
                return None
        return q if q > p else None

    def ring_arcs(self, c):
        """a ring's coordinates (made of whole arcs) -> its arcs, following them from node to node"""
        d, i = self.vtree.query(c)                          # (the arcs' own coordinates, where a vertex is one of theirs to 1e-9:
        c = np.where((d <= 1e-9)[:, None], self.verts[i], c)  # a point computed twice can differ in its last bit)
        kc = geo.key(c[:-1])                                # (a point twice in a row is once -- also two a float's last bit
        c = c[:-1][np.r_[True, kc[1:] != kc[:-1]]]          # apart, computed twice: one key)
        if len(c) > 1 and geo.key(c[0]) == geo.key(c[-1]):
            c = c[:-1]
        k = [int(x) for x in geo.key(c)]
        n = len(k)
        starts = [i for i, x in enumerate(k) if x in self.nodes]
        if not starts:
            raise ValueError("a ring with no node on it")
        p0 = starts[0]
        p, out, guard = p0, [], 0
        while True:
            best = None
            for a, fwd in self.by_start.get(k[p % n], []):
                q = self.follow(a, fwd, c, k, p)
                if q is not None:
                    best = (a, fwd, q); break
            if best is None:
                raise ValueError(f"no arc follows the ring at vertex {p}")
            a, fwd, q = best
            out.append(a if fwd else ~a)
            p = q
            guard += 1
            if p % n == p0 % n and p >= p0 + n:
                return out
            if guard > n + 5:
                raise ValueError("ring walk did not close")

    def polygon(self, poly):
        """a shapely polygon made of arcs -> [exterior arcs, hole arcs...] wound for d3"""
        rings = []
        for i, r in enumerate([poly.exterior, *poly.interiors]):
            c = shapely.get_coordinates(r)
            arcs = self.ring_arcs(c)
            cw = signed_area(c) < 0
            if (i == 0) != cw:                              # (outer clockwise, holes anticlockwise)
                arcs = [~a for a in reversed(arcs)]
            rings.append(arcs)
        return rings


def merge(topo, polys):
    """faces (lists of d3-wound rings of arcs) dissolved into one multipolygon: an arc used by two of them (once
    each way) is inside and goes; what is left is chained back into rings, holes put in their outer rings"""
    use = collections.Counter()
    for rings in polys:
        for r in rings:
            for a in r:
                use[a] += 1
    left = [a for a in use for _ in range(use[a]) if use.get(~a, 0) == 0]
    if len(left) == sum(len(r) for rs in polys for r in rs):
        return polys                                        # (nothing shared: as they are)
    start = collections.defaultdict(list)
    for a in left:
        c = topo.arcs[a] if a >= 0 else topo.arcs[~a][::-1]
        start[int(geo.key(c[:1])[0])].append(a)
    endk = lambda a: int(geo.key((topo.arcs[a] if a >= 0 else topo.arcs[~a][::-1])[-1:])[0])
    startk = lambda a: int(geo.key((topo.arcs[a] if a >= 0 else topo.arcs[~a][::-1])[:1])[0])
    end = lambda a: (topo.arcs[a] if a >= 0 else topo.arcs[~a][::-1])[-1]
    begin = lambda a: (topo.arcs[a] if a >= 0 else topo.arcs[~a][::-1])[0]
    near = lambda p, q: abs(p[0] - q[0]) + abs(p[1] - q[1]) < GAP_DEG
    used, rings = set(), []
    for a0 in left:
        if a0 in used:
            continue
        ring, a = [], a0
        while a is not None and a not in used:
            used.add(a); ring.append(a)
            nxt = [b for b in start[endk(a)] if b not in used]
            if not nxt and not near(end(a), begin(ring[0])):  # (a face read back past a 1 m arc -- the ring walk took its end as
                nxt = [b for b in left if b not in used and near(end(a), begin(b))]   # on the segment before: the one starting there)
            a = nxt[0] if nxt else None
            if endk(ring[-1]) == startk(ring[0]) or (a is None and near(end(ring[-1]), begin(ring[0]))):
                break
        rings.append(ring)
    # (a chain that stopped short -- its next arc a few hundred metres off, past more than GAP_DEG: the North
    # Atlantic's at Cape Farewell -- goes on with the chain that starts nearest its end, so a ring never jumps across
    # its area from where it stopped back to where it began: d3 would draw that as a great circle, the area inside out)
    shut = lambda r: near(end(r[-1]), begin(r[0]))
    open_ = [r for r in rings if not shut(r)]
    while open_:
        r = open_.pop()
        d, s = min(((abs(end(r[-1]) - begin(o[0])).sum(), k) for k, o in enumerate(open_)), default=(None, None))
        if s is None or d >= STITCH_DEG or abs(end(r[-1]) - begin(r[0])).sum() <= d:
            continue                                         # (none near, or itself the nearest: as it is)
        o = open_.pop(s); rings = [x for x in rings if x is not o]; r.extend(o)
        if not shut(r):
            open_.append(r)
    rings = [r for r in rings if len(topo.coords(r)) >= 4]   # (an arc there and back, left of a thin sliver: no ring)
    outers = [r for r in rings if signed_area(topo.coords(r)) < 0]
    holes = [r for r in rings if signed_area(topo.coords(r)) >= 0]
    if not outers and holes:                                # (a ring round a pole reads the wrong way on the plane: the biggest is the outer)
        big = max(holes, key=lambda r: abs(signed_area(topo.coords(r))))
        holes.remove(big)
        outers = [[~a for a in reversed(big)]]
    out = [[r] for r in outers]
    shapes = [shapely.Polygon(topo.coords(r)) for r in outers]
    for h in holes:
        p = shapely.Point(topo.coords(h)[0])
        inside = [i for i, s in enumerate(shapes) if s.covers(p)]
        (out[min(inside, key=lambda i: shapes[i].area)] if inside else out[0]).append(h)
    return out


def geometry(rings_list, props, gid=None):
    g = {"type": "Polygon", "arcs": rings_list[0]} if len(rings_list) == 1 else {"type": "MultiPolygon", "arcs": rings_list}
    if gid is not None:
        g["id"] = gid
    g["properties"] = {k: v for k, v in props.items() if v is not None}
    return g


def quantize(arcs):
    q = config.QUANT_DEG
    out = []
    for c in arcs:
        p = np.column_stack((np.round((c[:, 0] + 180) / q), np.round((c[:, 1] + 90) / q))).astype(np.int64)
        keep = np.ones(len(p), bool)
        keep[1:] = np.any(p[1:] != p[:-1], axis=1)
        p = p[keep]
        if len(p) == 1:
            p = np.vstack((p, p))
        d = np.vstack((p[:1], np.diff(p, axis=0)))
        out.append(d.tolist())
    return out


def drop_inside_out(objects, qarcs, names=("land", "lakes", "countries", "regions")):
    """the polygons as they are on the grid: a tiny island whose three points flip over when snapped to it would be
    read inside out (the whole globe but it) -- such a part is left out"""
    q = config.QUANT_DEG
    dec = [np.cumsum(np.array(a, dtype=float), axis=0) * q + (-180, -90) for a in qarcs]
    ring = lambda ids: np.vstack([(dec[i] if i >= 0 else dec[~i][::-1])[(1 if k else 0):] for k, i in enumerate(ids)])
    for name in names:
        geoms, dropped = [], 0
        for g in objects[name]["geometries"]:
            polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
            keep = [p for p in polys if geo.d3_area([ring(r) for r in p]) <= 2 * np.pi]
            dropped += len(polys) - len(keep)
            if keep:
                g["type"], g["arcs"] = ("Polygon", keep[0]) if len(keep) == 1 else ("MultiPolygon", keep)
                geoms.append(g)
        objects[name]["geometries"] = geoms
        if dropped:
            log(f"  {name}: {dropped} parts left out, inside out on the grid")


def division_names(ids):
    """{Overture division id: {language: name}} -- its names.common, read without the geometry"""
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit='400MB'; SET threads=1")
    area = os.path.join(ROOT, "raw/divisions/division_area-*.parquet")
    con.execute("CREATE TEMP TABLE want(id VARCHAR)")
    con.executemany("INSERT INTO want VALUES (?)", [(i,) for i in ids])
    out = {}
    for did, m in con.execute(f"SELECT DISTINCT a.division_id, a.names.common FROM '{area}' a JOIN want w ON a.division_id = w.id").fetchall():
        if m:
            out[did] = dict(m) if not isinstance(m, dict) or "key" not in m else dict(zip(m["key"], m["value"]))
    return out


def colour(objects, qarcs):
    """each country's `color`: a class 0..n, no two neighbours the same -- neighbours share an arc, or come within
    NEAR_DEG of each other (Iceland and Greenland, Spain and Morocco, the Channel). Greedy, the most constrained
    (highest degree) first; a planar map needs 4, the near-neighbour edges a few more."""
    NEAR_DEG = 1.0
    geoms = objects["countries"]["geometries"]
    def arc_ids(g):
        rings = g["arcs"] if g["type"] == "Polygon" else [r for poly in g["arcs"] for r in poly]
        return {(~a if a < 0 else a) for r in rings for a in r}
    def points(g):
        rings = g["arcs"] if g["type"] == "Polygon" else [r for poly in g["arcs"] for r in poly]
        out = []
        for r in rings:
            for a in r:
                x = np.cumsum(np.array(qarcs[~a if a < 0 else a], dtype=float), axis=0)
                out.append(x[::max(1, len(x) // 50)])   # (a sample: the distance test is coarse anyway)
        return np.concatenate(out) if out else np.zeros((0, 2))
    ids = [arc_ids(g) for g in geoms]
    by_arc = collections.defaultdict(set)
    for i, s in enumerate(ids):
        for a in s:
            by_arc[a].add(i)
    adj = [set() for _ in geoms]
    for members in by_arc.values():
        for i in members:
            adj[i] |= members - {i}
    from scipy.spatial import cKDTree
    pts = [points(g) for g in geoms]
    scale = np.array([1 / config.QUANT_DEG, 1 / config.QUANT_DEG])   # (quantized units)
    for i in range(len(geoms)):
        if not len(pts[i]):
            continue
        ti = cKDTree(pts[i])
        for j in range(i + 1, len(geoms)):
            if not len(pts[j]) or j in adj[i]:
                continue
            lo, hi = np.maximum(pts[i].min(0), pts[j].min(0)), np.minimum(pts[i].max(0), pts[j].max(0))
            if np.any(hi - lo < -NEAR_DEG * scale):
                continue
            d, _ = ti.query(pts[j], distance_upper_bound=NEAR_DEG * scale[0])
            if np.isfinite(d).any():
                adj[i].add(j); adj[j].add(i)
    order = sorted(range(len(geoms)), key=lambda i: -len(adj[i]))
    col = [None] * len(geoms)
    for i in order:
        used = {col[j] for j in adj[i]}
        col[i] = next(c for c in range(99) if c not in used)
    for g, c in zip(geoms, col):
        g["properties"]["color"] = c
    log(max(col) + 1 if col else 0, "colours for the countries; most neighbours:",
        ", ".join(f'{geoms[i]["properties"]["iso"]} {len(adj[i])}' for i in order[:5]))


def drop_unused(objects, qarcs):
    """the arcs no object refers to (lines across left inside an area once its faces are one) are left out, and the
    references renumbered"""
    def walk(x, f):
        return [walk(y, f) for y in x] if isinstance(x, list) else f(x)
    used = set()
    for o in objects.values():
        for g in o["geometries"]:
            walk(g["arcs"], lambda a: used.add(a if a >= 0 else ~a))
    new = {a: i for i, a in enumerate(sorted(used))}
    for o in objects.values():
        for g in o["geometries"]:
            g["arcs"] = walk(g["arcs"], lambda a: new[a] if a >= 0 else ~new[~a])
    log(f"  {len(qarcs) - len(used)} arcs no object uses left out")
    return [qarcs[a] for a in sorted(used)]


def main():
    T = pickle.load(open(os.path.join(ROOT, "work/topology.pkl"), "rb"))
    A = pickle.load(open(os.path.join(ROOT, "work/areas.pkl"), "rb")) if os.path.exists(os.path.join(ROOT, "work/areas.pkl")) else None
    if A:                                                   # (stage 6's arcs: the same, the coast split where lines across meet it, and those lines)
        T["arcs"], T["ring_arcs"] = A["arcs"], A["ring_arcs"]
        T["country_faces"], T["region_faces"] = A.get("country_faces", T["country_faces"]), A.get("region_faces", T["region_faces"])
    info = T["info"]
    arcs = [a[0] for a in T["arcs"]]
    kinds = [a[1] for a in T["arcs"]]
    cut = [a[3] for a in T["arcs"]]
    lakes = pickle.load(open(os.path.join(ROOT, "work/lakes.pkl"), "rb")) if os.path.exists(os.path.join(ROOT, "work/lakes.pkl")) else []
    wdnames.rename(lakes)                                   # (by their English names: OSM's are the local ones)
    lake_first = len(arcs)
    for L in lakes:
        for r in L["rings"]:
            arcs.append(r)
    topo = Topo(arcs[:lake_first])
    objects = {}

    # ---- land and coastline
    by = collections.defaultdict(list)
    for r, ids in enumerate(T["ring_arcs"]):
        by[int(T["poly"][r])].append(r)
    land = []
    for pid, rs in by.items():
        outer = [r for r in rs if not T["hole"][r]]
        if not outer:
            continue
        rings = []
        for r in outer + [r for r in rs if T["hole"][r]]:
            ra = list(T["ring_arcs"][r])
            c = topo.coords(ra)
            if (r in outer) != (signed_area(c) < 0):
                ra = [~a for a in reversed(ra)]
            rings.append(ra)
        land.append({"type": "Polygon", "arcs": rings})
    objects["land"] = {"type": "GeometryCollection", "geometries": land}
    objects["coastline"] = {"type": "GeometryCollection", "geometries": [{"type": "MultiLineString", "arcs": [[i] for i, k in enumerate(kinds) if k == "coast" and not cut[i]]}]}
    log(len(land), "land polygons")

    # ---- lakes (their own arcs): named in English and in the language of the country they are in (its face's)
    faces_cc = [(shapely.from_wkb(w), info[l]["country"] if l in info else None) for (w, _), l in zip(T["country_faces"], T["country_labels"])]
    ftree = shapely.STRtree([f for f, _ in faces_cc])
    pts = shapely.points([L["rings"][0][len(L["rings"][0]) // 2] for L in lakes]) if lakes else []
    at = {}
    if len(pts):
        (li, fi), d = ftree.query_nearest(pts, return_distance=True, all_matches=False)
        at = {int(i): faces_cc[int(j)][1] for i, j in zip(li, fi)}
    loc = wdnames.local_labels([(L.get("wikidata"), at.get(i)) for i, L in enumerate(lakes)])
    for L, l in zip(lakes, loc):
        if l:                                               # (the official language's name; none if it is the English one)
            L["name_local"] = l if l != L.get("name") else None
        elif L.get("name_local") == L.get("name"):
            L["name_local"] = None

    # ---- lakes (their own arcs)
    lk, a = [], lake_first
    for L in lakes:
        rings = []
        for r in L["rings"]:
            rings.append([a]); a += 1
        lk.append({"type": "Polygon", "arcs": rings, "properties": {k: v for k, v in L.items() if k != "rings" and v is not None}})
    objects["lakes"] = {"type": "GeometryCollection", "geometries": lk}

    # ---- the areas (stage 6): faces of the coast and the lines across -- or, for a sea of no water of the map's own, lakes
    if A:
        geoms, bad = [], 0
        for rec in A["areas"]:
            polys = []
            for w in rec["faces"]:
                try:
                    polys.append(topo.polygon(shapely.from_wkb(w)))
                except ValueError:
                    bad += 1
            polys = merge(topo, polys) if polys else []
            polys += [lk[i]["arcs"] for i in rec["lakes"]]
            if polys:
                geoms.append(geometry(polys, rec["props"]))
        objects["areas"] = {"type": "GeometryCollection", "geometries": geoms}
        log(len(geoms), "areas" + (f" ({bad} faces could not be read back as arcs)" if bad else ""))

    # ---- the names: English, and in the official language of the country (Overture's names, OSM's)
    common = division_names(list(info))
    langs = wdnames.official_languages()
    def local_of(d, cc):
        en = info[d]["name_en"] or info[d]["name"]
        n = next((common.get(d, {}).get(l) for l in langs.get(cc or "", []) if common.get(d, {}).get(l)), None) or info[d]["name"]
        return n if n != en else None

    # ---- countries
    def units(faces_, labels, props_of, skip_unlabelled=True):
        groups = collections.defaultdict(list)
        bad = []
        for (w, pid), lab in zip(faces_, labels):
            if lab is None and skip_unlabelled:
                continue
            f = shapely.from_wkb(w)
            try:
                groups[lab].append(topo.polygon(f))
            except ValueError as e:
                bad.append((props_of(lab).get("iso"), round(f.area, 4), str(e)[:30]))
        if bad:
            log(f"  ({len(bad)} faces could not be read back as arcs: {bad})")
        return [geometry(merge(topo, polys), props_of(lab), gid) for lab, polys in groups.items() for gid in [props_of(lab).get("iso")]]

    def cprops(d):
        if d == "AQ":
            return {"iso": "AQ", "name": "Antarctica", "subtype": "continent"}
        v = info[d]
        return {"iso": v["country"], "name": v["name_en"] or v["name"], "name_local": local_of(d, v["country"]), "subtype": v["subtype"],
                "sovereign": v.get("sovereign"), "overture": v["id"]}
    cf, cl = T["country_faces"], list(T["country_labels"])
    for i, ((w, pid), lab) in enumerate(zip(cf, cl)):         # (the land no country has: Antarctica, if south of 60)
        if lab is None and shapely.get_coordinates(shapely.from_wkb(w))[:, 1].max() < -60:
            cl[i] = "AQ"
    objects["countries"] = {"type": "GeometryCollection", "geometries": units(cf, cl, cprops)}
    log(len(objects["countries"]["geometries"]), "countries and dependencies")

    # ---- regions
    def rprops(d):
        v = info[d]
        return {"iso": v["region"], "name": v["name_en"] or v["name"], "name_local": local_of(d, v["country"]), "country": v["country"], "overture": v["id"]}
    objects["regions"] = {"type": "GeometryCollection", "geometries": units(T["region_faces"], T["region_labels"], rprops)}
    log(len(objects["regions"]["geometries"]), "regions")

    # ---- the borders as lines (one geometry per source line: its arcs)
    for kind, name in (("country", "country_borders"), ("region", "region_borders")):
        per = collections.defaultdict(list)
        for i in range(T["first_line"], lake_first):
            if kinds[i] == kind:
                per[T["arcs"][i][2]].append(i)
        src_of = {}
        for l in T["lines"]:
            src_of.setdefault(l["src"], l)
        geoms = []
        for src, ids in per.items():
            l = src_of[src]
            sides = [info[d]["region" if kind == "region" else "country"] if d in info else None for d in l["ids"]]
            p = {"a": sides[0] if sides else None, "b": sides[1] if len(sides) > 1 else None}
            if kind == "country" and l["disputed"]:
                p["disputed"] = True
            if kind == "region":
                p["country"] = info[l["ids"][0]]["country"] if l["ids"] and l["ids"][0] in info else None
            geoms.append({"type": "MultiLineString", "arcs": [[i] for i in ids], "properties": {k: v for k, v in p.items() if v is not None}})
        objects[name] = {"type": "GeometryCollection", "geometries": geoms}
        log(len(geoms), name)

    qarcs = quantize(arcs)
    drop_inside_out(objects, qarcs, [k for k in ("land", "lakes", "countries", "regions", "areas") if k in objects])
    qarcs = drop_unused(objects, qarcs)
    colour(objects, qarcs)
    items = iso_items(objects)
    area_km2(objects, qarcs)
    places(objects, qarcs)
    languages(objects, items)
    populations(objects, items)
    out = {"type": "Topology",
           "bbox": [-180, -90, 180, 90],
           "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
           "objects": objects, "arcs": qarcs}
    os.makedirs(os.path.join(ROOT, "full"), exist_ok=True)   # (the full-detail layers: not committed -- the map loads data/lite/)
    path = os.path.join(ROOT, "full/world.topo.json")
    json.dump(out, open(path, "w"), separators=(",", ":"))
    log(f"{path}: {os.path.getsize(path) / 2**20:.1f} MB, {len(arcs)} arcs, {sum(len(c) for c in arcs):,} points")


def iso_items(objects):
    """{(object, ISO code): [Wikidata items with that code]} -- 3166-1 alpha-2 (P297) for a country, 3166-2 (P300)
    for a state"""
    items = collections.defaultdict(list)
    for name, prop in (("countries", "P297"), ("regions", "P300")):
        codes = sorted({g["properties"]["iso"] for g in objects[name]["geometries"] if g["properties"].get("iso")})
        for i in range(0, len(codes), 300):
            vals = " ".join(json.dumps(c) for c in codes[i:i + 300])
            for b in wdnames.sparql(f"SELECT ?item ?code WHERE {{ VALUES ?code {{ {vals} }} ?item wdt:{prop} ?code . }}"):
                items[(name, b["code"]["value"])].append(b["item"]["value"].rsplit("/", 1)[-1])
    return items


def ring_reader(qarcs):
    """-> ring(arc ids): a ring's longitude/latitude points, from the quantized arcs"""
    q = config.QUANT_DEG
    dec = [np.cumsum(np.array(a, dtype=float), axis=0) * q + (-180, -90) for a in qarcs]
    return lambda ids: np.vstack([(dec[i] if i >= 0 else dec[~i][::-1])[(1 if k else 0):] for k, i in enumerate(ids)])


def area_km2(objects, qarcs, names=("countries", "regions")):
    """each country's and state's `area_km2` (the objects named): the area of its polygons on the sphere (outer rings
    less holes)"""
    ring = ring_reader(qarcs)
    for name in names:
        for g in objects[name]["geometries"]:
            polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
            km2 = sum(abs(geo.ring_area_km2(ring(p[0]))) - sum(abs(geo.ring_area_km2(ring(h))) for h in p[1:]) for p in polys)
            g["properties"]["area_km2"] = int(round(km2))


# the continents, by their Wikidata items (P30 of a country's): Natural Earth's "Australia" area is Oceania's land
CONTINENTS = {"Q15": "Africa", "Q51": "Antarctica", "Q48": "Asia", "Q46": "Europe", "Q49": "North America",
              "Q18": "South America", "Q55643": "Oceania", "Q538": "Oceania", "Q3960": "Oceania"}


def continents_of():
    """{ISO 3166-1 alpha-2: [its continents]} -- Wikidata's (P30 of the items with that code; cached in
    raw/wd_continents.json)"""
    path = os.path.join(ROOT, "raw/wd_continents.json")
    if not os.path.exists(path):
        out = collections.defaultdict(list)
        for b in wdnames.sparql("SELECT ?iso ?c WHERE { ?item wdt:P297 ?iso . ?item wdt:P30 ?c . }"):
            c = CONTINENTS.get(b["c"]["value"].rsplit("/", 1)[-1])
            if c and c not in out[b["iso"]["value"].upper()]:
                out[b["iso"]["value"].upper()].append(c)
        json.dump(out, open(path, "w"), indent=0, sort_keys=True)
    return json.load(open(path))


def places(objects, qarcs):
    """each country's and state's `label` (a point well inside its biggest polygon: where its name is written) and
    `continent`: its country's (Wikidata's); of a country on several, the one whose land -- the continent areas of
    layer 7 -- its label lies in, or is nearest to. A state's own: Russia's European oblasts are in Europe, the
    country in Asia."""
    from shapely.ops import polylabel
    ring = ring_reader(qarcs)
    poly = lambda p: shapely.make_valid(shapely.Polygon(ring(p[0]), [ring(h) for h in p[1:]]))
    parts = lambda g: [g["arcs"]] if g["type"] == "Polygon" else g["arcs"] if g["type"] == "MultiPolygon" else []
    land = {CONTINENTS[g["properties"]["wikidata"]]: shapely.union_all([poly(p) for p in parts(g)]) for g in objects.get("areas", {"geometries": []})["geometries"]
            if g["properties"].get("kind") == "continent" and g["properties"].get("wikidata") in CONTINENTS}
    of = continents_of()
    n = collections.Counter()
    for name in ("countries", "regions"):
        for g in objects[name]["geometries"]:
            ps = [poly(p) for p in parts(g)]
            if not ps:
                continue
            big = max((y for p in ps for x in shapely.get_parts(p) for y in shapely.get_parts(x) if y.geom_type == "Polygon"), key=lambda x: x.area, default=None)
            if big is None:                                     # (a sliver: no polygon left once made valid)
                continue
            lab = polylabel(big, tolerance=max(0.001, (big.area ** 0.5) / 100))
            g["properties"]["label"] = [round(lab.x, 3), round(lab.y, 3)]
            cs = of.get(g["properties"]["iso"] if name == "countries" else g["properties"].get("country"), [])
            cs = [c for c in cs if c in land] if len(cs) > 1 else cs or list(land)
            if len(cs) > 1:                                     # (several: where its label is)
                cs = sorted(cs, key=lambda c: land[c].distance(lab))
                n["by place"] += 1
            if cs:
                g["properties"]["continent"] = cs[0]
            n["without Wikidata's"] += not of.get(g["properties"]["iso"] if name == "countries" else g["properties"].get("country"))
    log(len(land), "continent areas;", dict(n), "countries and states")


def languages(objects, items):
    """each country's and state's `language` (its English name) and `language_code`: the first official language
    (wdnames.official_languages: Wikidata P37 with its ISO 639-1 code, with the overrides; a territory's sovereign's),
    for a state its own (P37 of its item) where it has one -- the one that is not its country's first, if it has
    several: Tamil Nadu's Tamil, Catalonia's Catalan -- else its country's"""
    langs = wdnames.official_languages()
    names = wdnames.language_names()
    by_item, speakers = {}, collections.Counter()
    qids = sorted({q for (name, _), qs in items.items() if name == "regions" for q in qs})
    for i in range(0, len(qids), 400):
        vals = " ".join("wd:" + q for q in qids[i:i + 400])
        for b in wdnames.sparql(f"SELECT ?item ?code ?sp WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P37 ?l . ?l wdt:P218 ?code . OPTIONAL {{ ?l wdt:P1098 ?sp }} }}"):
            code = b["code"]["value"].lower().split("-")[0]
            by_item.setdefault(b["item"]["value"].rsplit("/", 1)[-1], set()).add(code)
            speakers[code] = max(speakers[code], float(b.get("sp", {}).get("value") or 0))
    n = 0
    first = {}
    for g in objects["countries"]["geometries"]:
        p = g["properties"]
        code = next(iter(langs.get(p.get("iso") or "", []) or langs.get(p.get("sovereign") or "", [])), None)   # (Svalbard: Norway's)
        first[p.get("iso")] = code
        if code:
            code = code.split("-")[0]                          # (zh-hans: Chinese)
            p["language"], p["language_code"] = names.get(code, code), code; n += 1
    for g in objects["regions"]["geometries"]:
        p = g["properties"]
        own = {c for q in items.get(("regions", p.get("iso")), []) for c in by_item.get(q, set())}
        # (of a state's own official languages, the ones that are not its country's, and of those the most spoken:
        # Tamil Nadu's Tamil, not its English; Catalonia's Catalan over its Occitan; Quebec's French)
        national = {c.split("-")[0] for c in langs.get(p.get("country") or "", [])}
        pick = own - national or own
        code = max(pick, key=lambda c: speakers[c]) if pick else first.get(p.get("country"))
        if code:
            code = code.split("-")[0]
            p["language"], p["language_code"] = names.get(code, code), code; n += 1
    log(n, "countries and states with a language")


def populations(objects, items):
    """each country's and state's `population`: Wikidata's latest (P1082) for the item of its ISO code -- rounded
    like a city's (two significant digits) -- and `density` (people per km2, from `area_km2`)"""
    from points import wd_population, round_pop
    pops = wd_population(sorted({q for qs in items.values() for q in qs}))
    n = 0
    for name in ("countries", "regions"):
        for g in objects[name]["geometries"]:
            got = [pops[q] for q in items.get((name, g["properties"].get("iso")), []) if pops.get(q) and pops[q][0] > 0]   # (the Vatican: a count of 0 on record)
            if got:                                            # (several items for one code: the latest count, then the biggest)
                pop, year = max(got, key=lambda x: (x[1] or "", x[0]))
                g["properties"]["population"] = round_pop(pop)
                g["properties"]["population_year"] = int(year) if year and year.isdigit() else None
                if g["properties"].get("area_km2"):
                    g["properties"]["density"] = round(pop / g["properties"]["area_km2"], 1)
                n += 1
            else:
                for k in ("population", "population_year", "density"):
                    g["properties"].pop(k, None)
    log(n, "countries and states with a population")


def props_only():
    """`write.py props`: only the countries' and states' colour classes, areas, languages and populations of
    full/world.topo.json, in place"""
    path = os.path.join(ROOT, "full/world.topo.json")
    out = json.load(open(path))
    colour(out["objects"], out["arcs"])
    items = iso_items(out["objects"])
    area_km2(out["objects"], out["arcs"])
    places(out["objects"], out["arcs"])
    languages(out["objects"], items)
    populations(out["objects"], items)
    json.dump(out, open(path, "w"), separators=(",", ":"))


if __name__ == "__main__":
    if sys.argv[1:] == ["props"]:
        props_only(); raise SystemExit
    if sys.argv[1:] == ["places"]:                          # (only the labels and continents: no Wikidata)
        path = os.path.join(ROOT, "full/world.topo.json")
        out = json.load(open(path))
        places(out["objects"], out["arcs"])
        json.dump(out, open(path, "w"), separators=(",", ":"))
        raise SystemExit
    main()
