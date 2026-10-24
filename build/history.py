"""STAGE 10 -- HISTORICAL BORDERS: the world's states, empires and dependencies from 3000 BC to 2019, as REGIONS -- pieces
of land that always shared one fate -- and each region's owners through time. Two sources (build/fetch_history.sh):
  - from 1886: CShapes 2.0 (Schvitz et al. 2022, ETH Zurich ICR, CC BY-NC-SA 4.0: raw/cshapes/) -- every change to
    the day, de jure;
  - before: historical-basemaps (A. Ourednik et al., GPL-3.0: raw/basemaps/) -- the world as it was in 3000 BC,
    2000 BC ... 1800, 1815, 1878, 1880 (SNAPSHOTS), each map taken to hold until the next: a period's `from` and `to` are
    the snapshots', not the days things changed. Its borders are approximate (BORDERPRECISION 1) before 1650.

    build/capped.sh .venv/bin/python build/history.py     # work/topology.pkl, Overture's divisions (build/admin.py),
                                                          # full/bio.topo.json, raw/cshapes, raw/basemaps -> full/history.topo.json

THE REGIONS are cut by lines that stay put, not by the sources' own outlines (historical-basemaps draws each map anew:
one border is drawn a little differently in every map, and their outlines laid together are slivers):
  - the administrative lines of today (Overture: countries, their regions, their counties -- build/admin.py): most
    historical borders survive as some province's or district's;
  - CShapes' borders where they run apart from those (Germany's and Poland's of 1871-1945, India's partition): drawn
    to the day, they are kept -- but not where they run within CSHAPES_KM of an administrative line, the same border
    drawn twice;
  - the ecoregions' borders (full/bio.topo.json: mountain ridges, a desert's edge) where they run apart from both by
    ECO_KM: natural lines, where empires ended in land of few districts (the Sahara, the steppe, Siberia).
They cut the map's land into faces (build/bio.land_faces). Each face has an owner on each day: the country-period valid
then that covers most of it (the smaller of two covering it alike: historical-basemaps draws a vassal inside its empire;
an islet no period covers takes the nearest within NEAR_DEG). A sliver (under MIN_FACE_KM2, or thinner than THIN_KM) takes
the owners of the neighbour it shares most border with. Faces side by side with the same owners on every day are one
region -- and an island near one with them (within NEAR_DEG). A state on a day is the regions it holds; a border, the
lines between regions of different states.

Objects (one file, every line stored once; a day is "YYYY-MM-DD" -- a year before 1 astronomical, written as ISO 8601
does: "-0699-01-01" is 1 January 700 BC --, proleptic Gregorian; a day that is 1 January written as its year: "-0699";
from and to both inclusive; 2019-12-31 is where the data ends, not the state):
    regions     one polygon per region: id (a number), name (its county's, where it is less than half of its region --
                state, province -- else the region's), admin (that region, where the name is a county's), country (ISO,
                today's), held (its owners through time: "from:state", each until the next -- an empty state: nobody's),
                area_km2, label
    periods     no geometry: one row per country-period -- id (state:from), state (the state's number: CShapes' gwcode --
                Gleditsch & Ward's, CShapes' own for a dependency --, or 10000 and up for historical-basemaps' names), name,
                from, to, source (cshapes, basemaps), precision (of its borders: 1 approximate, 2 partly undefined, 3 fixed
                by law), status (CShapes': independent, colony, protectorate, mandate, occupied; historical-basemaps': a
                dependency where it names a ruler, culture where it draws a people or culture, not a polity), owner (the
                state ruling a dependency), capital, cap ([lon, lat]), gwcode, area_km2, label
A state's land on a day: the regions whose `held` has it then (its period that day: the one of its periods spanning it);
its borders: the arcs between those regions and the others.
"""
import os, re, sys, json, collections
import numpy as np, shapely, duckdb
from shapely import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config, write, areas, bio, admin
from bio import log
from dates import days as day_of, iso

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "raw/cshapes/CShapes-2.0.shp")
META = os.path.join(ROOT, "raw/cshapes/cshapes_2_gw.topojson")   # (the R package's copy: status, owner, b_def)
BASEMAPS = os.path.join(ROOT, "raw/basemaps")
# historical-basemaps' maps taken (astronomical years: 3000 BC is -2999); 1492 is left out -- drawn from another source,
# 1946 shapes sharing a quarter of their points with the maps around it, it would cut the land into slivers --, and
# from 1886 CShapes has every day
SNAPSHOTS = [("bc3000", -2999), ("bc2000", -1999), ("bc1500", -1499), ("bc1000", -999), ("bc700", -699), ("bc500", -499),
             ("bc400", -399), ("bc323", -322), ("bc300", -299), ("bc200", -199), ("bc100", -99), ("bc1", 0)] + \
            [(str(y), y) for y in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1279, 1300, 1400, 1500,
                                   1530, 1600, 1650, 1700, 1715, 1783, 1800, 1815, 1878, 1880)]
BASE_ID = 10000             # (historical-basemaps' states: numbered from here, by name)
# historical-basemaps draws peoples and cultures where no state was (its TYPE mostly empty): told by the name -- status
# "culture", a cultural area, not a polity
CULTURE = re.compile(r"\b(cultures?|hunters?|gatherers?|hunter-gatherers|farmers|nomads|pastoral(ists)?|peoples|foragers|fishers|fichers|"
                     r"herders|neolithic|bronze age|aboriginal)\b", re.I)
FACES_VERSION = 11          # (work/history_faces.pkl is made again when the way of cutting changes: 2 no antimeridian, no loops,
                            # 4 an arc in two landmasses given to the one holding most of it, 5 historical-basemaps too, 6 an
                            # islet ring only if it touches no other, 7 regions: administrative lines, CShapes', ecoregions',
                            # 8 twin lines dropped, the second cut, 9 only the coast's and the cut's arcs, 10 the outlines
                            # of the second cut all, none taken for an island's coast, 11 periods from 100 km2)
FIRST_CUT = 8               # (work/history_faces1.pkl, the first cut: only to tell which periods it leaves short)
BIO = os.path.join(ROOT, "full/bio.topo.json")
BORDER_KM = config.EPS_KM   # CShapes' borders are drawn lines, not a raster's steps: simplified as the map's own
CSHAPES_KM = 5.0            # a CShapes border this close to an administrative line is that line (CShapes draws coarser)
ECO_KM = 5.0                # an ecoregion border this close to any of them is that line (a stretch's end is tied to the line
                            # it comes near, the coast within 6 km: areas.tie_loose_ends)
MIN_FACE_KM2 = 25.0         # a face smaller than this -- or thinner than THIN_KM (twice its area over its outline) -- is a
THIN_KM = 1.5               # sliver between two versions of one line: its neighbour's
ISLE_KM2 = 5000.0           # an island under this joins a region with its owners within NEAR_DEG (the Cyclades with Greece)
SHORT = 0.75                # a country-period the first cut leaves less than this of its land (its own shape's, over SHORT_KM2)
SHORT_KM2 = 100.0           # has its outline cut in too: a people of Australia in an outback shire, a sultanate of the Sahel,
                            # Rome in 500 BC, Hamburg
NEAR_DEG = 0.2              # an islet no period covers belongs to the nearest one within this (else to nobody: Dominica,
                            # St Lucia, which CShapes leaves out, are not Guadeloupe's and Martinique's)
FILL_DEG2 = 0.01            # a face smaller than this (~100 km2) that no period covers on a day -- land between a source's
                            # coarse coast and the map's -- is the nearest's within NEAR_DEG that day (not a gap on the coast)
COVER = 0.5                 # a period holds a face when it covers this much of what the best cover of it ever does (a face
                            # on the coast CShapes draws coarser may be a third in any)
DAY = 1                     # (days are numbers: build/dates.py)


class Shapes:
    """the distinct shapes of all periods: the rings of their polygons, each ring once (an island that changed hands is
    one ring), and each shape made valid and simplified to tell which faces it covers"""
    def __init__(self):
        self.index, self.rings, self.seen, self.ug = {}, [], set(), []

    def add(self, wkb, rec):
        u = self.index.setdefault(wkb, len(self.index))
        if u == len(self.ug):
            g = shapely.make_valid(shapely.from_wkb(wkb))
            for p in shapely.get_parts(g):
                if p.geom_type != "Polygon":
                    continue
                for r in (p.exterior, *p.interiors):
                    c = shapely.get_coordinates(r)
                    k = np.unique(geo.key(c)).tobytes()
                    if k not in self.seen:
                        self.seen.add(k); self.rings.append((rec, c))
            self.ug.append(shapely.make_valid(shapely.simplify(g, 0.01)))
        return u


def cshapes(S, recs):
    """CShapes' country-periods, from 1886 (the names from the R package's copy: the shapefile's are not UTF-8)"""
    meta = {(g["properties"]["gwcode"], g["properties"]["start"]): g["properties"]
            for g in json.load(open(META))["objects"]["cshapes_2_gw"]["geometries"]}
    con = duckdb.connect()
    con.execute("LOAD spatial; SET memory_limit='600MB'; SET threads=1")
    rows = con.execute(f"SELECT gwcode, gwsyear, gwsmonth, gwsday, gweyear, gwemonth, gweday, ST_AsWKB(geom) "
                       f"FROM ST_Read('{SRC}') ORDER BY gwcode, gwsyear, gwsmonth, gwsday").fetchall()
    for gw, sy, sm, sd, ey, em, ed, wkb in rows:
        m = meta[(gw, f"{sy:04d}-{sm:02d}-{sd:02d}")]
        status = m["status"] if m["status"] != "N/A" else None
        clon, clat = m["caplong"], m["caplat"]
        defined = int(m["b_def"]) if m["b_def"] is not None else 1
        recs.append({"state": gw, "gwcode": gw, "name": m["country_name"], "from": day_of(sy, sm, sd), "to": day_of(ey, em, ed),
                     "source": "cshapes", "precision": 3 if defined else 2, "status": status,
                     "owner": int(m["owner"]) if status and status != "independent" and str(m["owner"]).isdigit() else None,
                     "capital": m["capname"], "cap": [round(clon, 3), round(clat, 3)] if clon is not None else None,
                     "u": S.add(bytes(wkb), len(recs))})


def basemaps(S, recs, until):
    """historical-basemaps' polities, one period for the snapshots in a row that draw one the same: from the first
    snapshot to the day before the one after the last (the last map, 1880, to the day before `until`). A feature
    without a NAME is land no state held; two features of one name in a map are one polity."""
    maps = []
    for f, y in SNAPSHOTS:
        by = collections.defaultdict(list)
        for ft in json.load(open(os.path.join(BASEMAPS, f"world_{f}.geojson")))["features"]:
            p, g = ft["properties"], ft["geometry"]
            n = (p.get("NAME") or "").strip()
            if n and n != "?" and g:
                by[n].append((p, shapely.geometry.shape(g)))
        maps.append((y, {n: (ps[0][0], shapely.to_wkb(shapely.multipolygons([q for _, g in ps for q in shapely.get_parts(g) if q.geom_type == "Polygon"])))
                         for n, ps in by.items()}))
    ids = {n: BASE_ID + i for i, n in enumerate(sorted({n for _, m in maps for n in m}))}
    starts = [day_of(y) for y, _ in maps] + [until]
    open_ = {}                                               # (name -> the record it continues while the shape stays)
    for k, (y, m) in enumerate(maps):
        for n, (p, wkb) in m.items():
            r = open_.get(n)
            if r is not None and r["wkb"] == wkb and r["to"] == starts[k] - DAY:
                r["to"] = starts[k + 1] - DAY
                continue
            ruler = (p.get("SUBJECTO") or "").strip()
            owner = ids.get(ruler) if ruler and ruler != n and ruler in m else None
            r = {"state": ids[n], "gwcode": None, "name": n, "from": starts[k], "to": starts[k + 1] - DAY, "source": "basemaps",
                 "precision": max(1, int(p.get("BORDERPRECISION") or 1)), "status": "culture" if CULTURE.search(n) else "dependency" if owner else None,
                 "owner": owner, "capital": None, "cap": None, "wkb": wkb, "u": S.add(wkb, len(recs))}
            recs.append(r); open_[n] = r
    for r in recs:
        r.pop("wkb", None)


def periods():
    """both sources' country-periods -> (records, the rings of their shapes as [(record, coords)], each once, the
    distinct shapes)"""
    S, recs = Shapes(), []
    cshapes(S, recs)
    basemaps(S, recs, min(r["from"] for r in recs))
    log(len(recs), "country-periods,", len(S.ug), "shapes,", len(S.rings), "rings,", sum(len(c) for _, c in S.rings), "points")
    return recs, S.rings, S.ug


def owners(faces, recs, ug):
    """each face's country-period on each day -> (the days a change starts on, [face][epoch] record or -1; epoch e:
    days[e] to days[e + 1] - 1)"""
    days = sorted({r["from"] for r in recs} | {r["to"] + DAY for r in recs})
    at = {d: i for i, d in enumerate(days)}
    E = len(days) - 1
    valid = np.full((len(ug), E), -1, np.int32)              # (each shape's period on each epoch: one at most)
    twice = 0
    for i, r in enumerate(recs):
        span = valid[r["u"], at[r["from"]]:at[r["to"] + DAY]]
        twice += int((span >= 0).any())                      # (two names drawn the same at once: the first kept)
        span[span < 0] = i
    if twice:
        log(twice, "periods drawn as another one is at the same time (the first kept)")
    size = [G.area for G in ug]
    tree = STRtree(ug)
    for G in ug:
        shapely.prepare(G)
    own = np.full((len(faces), E), -1, np.int32)
    near = filled = 0
    for k, (f, _) in enumerate(faces):
        cand = []
        for u in tree.query(f).tolist():
            s = 1.0 if shapely.contains(ug[u], f) else areas.share(f, ug[u])
            if s > 0:
                cand.append((s, u))
        if cand:                                             # (a shape a sliver of it is in -- the shapes are simplified, a face by
            top = max(s for s, _ in cand)                    # a border overlaps its neighbour -- does not hold it on a day no other
            cand = [(s, u) for s, u in cand if s >= COVER * top]   # does: land no state held in 1886 stays so)
        else:                                                # (an islet off CShapes' coast: the nearest shapes)
            p = shapely.point_on_surface(f)
            cand = [(-shapely.distance(p, ug[u]), u) for u in tree.query(p, predicate="dwithin", distance=NEAR_DEG).tolist()]
            near += bool(cand)
        o = own[k]
        for _, u in sorted(cand, key=lambda c: (-c[0], size[c[1]])):   # (the one covering most of it of those valid on the day; the smaller if alike)
            m = o < 0
            o[m] = valid[u][m]
        if (o < 0).any() and f.area < FILL_DEG2:                # (a sliver of coast some days' shapes leave out: theirs)
            for u in sorted(tree.query(f, predicate="dwithin", distance=NEAR_DEG).tolist(), key=lambda u: shapely.distance(f, ug[u])):
                m = o < 0
                o[m] = valid[u][m]
            filled += 1
        if k % 5000 == 0:
            log(f"  {k}/{len(faces)} faces given their owners")
    log(len(faces), "faces,", E, "spans of days,", near, "islets given the nearest country-period,", filled, "slivers of coast filled")
    return days, own


def even(own, recs, days):
    """a country-period has the same faces on all its days, so that its polygon is what the border lines of any of its
    days enclose: a face it has on some only (an islet nearer another shape then, a coast face covered differently) it
    has on all if on most of them (by days), else on none -> how many were made so"""
    at = {d: i for i, d in enumerate(days)}
    n = 0
    for _ in range(5):                                       # (one made even can make another uneven: until none is)
        changed = 0
        for i, r in enumerate(recs):
            e0, e1 = at[r["from"]], at[r["to"] + DAY]
            span = own[:, e0:e1] == i
            part = np.flatnonzero(span.any(axis=1) & ~span.all(axis=1)).tolist()
            if not part:
                continue
            w = np.array([days[e + 1] - days[e] for e in range(e0, e1)])
            for f in part:
                o = own[f, e0:e1]                            # (a view: written into own)
                if 2 * w[o == i].sum() >= w.sum():
                    o[:] = i
                else:
                    o[o == i] = -1
                changed += 1
        n += changed
        if not changed:
            break
    return n


def eco_lines():
    """the ecoregions' borders: the arcs of full/bio.topo.json two ecoregions share -> [coords]"""
    t = json.load(open(BIO))
    sc, tr = np.array(t["transform"]["scale"]), np.array(t["transform"]["translate"])
    use = collections.Counter()
    def walk(x):
        for y in x:
            if isinstance(y, list):
                walk(y)
            else:
                use[y if y >= 0 else ~y] += 1
    for g in t["objects"]["ecoregions"]["geometries"]:
        walk(g.get("arcs", []))
    out = []
    for a, n in use.items():
        q = np.cumsum(np.array(t["arcs"][a], dtype=np.int64), axis=0)
        q = q[np.r_[True, np.any(q[1:] != q[:-1], axis=1)]]      # (on the grid a short arc can be one point)
        if n >= 2 and len(q) >= 2:
            out.append(q * sc + tr)
    return out


def line_tree(lines):
    """lines -> an STRtree of them in pieces of 32 segments (to measure how far a point is from the nearest)"""
    return STRtree([shapely.linestrings(c[i:i + 33]) for c in lines for i in range(0, len(c) - 1, 32)])


def apart(lines, km, *trees):
    """the stretches of lines farther than km from every line of the trees (a source's version of a line the map has
    already -- an administrative line, the coast -- would leave slivers between the two) -> [coords]. A stretch runs on
    to its first point within km, where areas.tie_to_lines ties it to the line it came near; one shorter than 2 km is a
    wobble, dropped."""
    deg, out = km / 111.0, []
    for c in lines:
        c = c[np.r_[True, np.any(c[1:] != c[:-1], axis=1)]]     # (a source's point twice in a row: once)
        if len(c) < 2:
            continue
        p = shapely.get_coordinates(shapely.segmentize(shapely.linestrings(c), deg / 2))
        far = np.ones(len(p), bool)
        for tree in trees:
            (i, _), d = tree.query_nearest(shapely.points(p), return_distance=True, all_matches=False)
            near = np.zeros(len(p), bool)
            near[i] = d <= deg
            far &= ~near
        edge = np.diff(np.r_[0, far.astype(np.int8), 0])
        for a, b in zip(np.flatnonzero(edge == 1).tolist(), np.flatnonzero(edge == -1).tolist()):
            run = p[max(0, a - 1):min(len(p), b + 1)]
            if geo.length_km(run) >= 2 * km:
                out.append(run[geo.simplify(geo.to_xyz(run), BORDER_KM)])
    return out


def cut_lines(rings, recs, S, short=()):
    """the lines the land is cut into faces by: the administrative ones, CShapes' apart from them and from the coast
    (S: the map), the ecoregions' apart from all three; and the outlines of the shapes `short` apart from all four
    -> [coords]"""
    adm = bio.borders([(None, c) for c in admin.lines()], admin.KM)
    log(len(adm), "administrative lines")
    A = line_tree(adm)
    cs = apart(bio.borders([(r, c) for r, c in rings if recs[r]["source"] == "cshapes"], BORDER_KM), CSHAPES_KM, A, S["ctree"])
    log(len(cs), "stretches of CShapes' borders apart from them,", round(sum(geo.length_km(c) for c in cs)), "km")
    eco = apart(eco_lines(), ECO_KM, A, S["ctree"], line_tree(cs))
    log(len(eco), "stretches of ecoregion borders apart from both,", round(sum(geo.length_km(c) for c in eco)), "km")
    more = []
    if short:
        more = apart(bio.borders([(r, c) for r, c in rings if recs[r]["u"] in short], BORDER_KM, islets=False), CSHAPES_KM, A, S["ctree"], line_tree(cs), line_tree(eco))
        log(len(more), "stretches of the outlines of", len(short), "shapes the first cut left short,", round(sum(geo.length_km(c) for c in more)), "km")
    return adm + cs + eco + more


def face_km(faces):
    """each face's area and outline -> (km2, km)"""
    a, l = np.zeros(len(faces)), np.zeros(len(faces))
    for k, (f, _) in enumerate(faces):
        for p in shapely.get_parts(f):
            if p.geom_type != "Polygon":
                continue
            rs = [shapely.get_coordinates(r) for r in (p.exterior, *p.interiors)]
            a[k] += abs(geo.ring_area_km2(rs[0])) - sum(abs(geo.ring_area_km2(r)) for r in rs[1:])
            l[k] += sum(geo.length_km(r) for r in rs)
    return a, l


def regions(faces, own, side, arcs, keep):
    """faces -> regions: a sliver takes its neighbour's owners (in own), then the faces side by side with the same owners
    on every day are one region, and so is an island near one -> [region of each face, or -1: left out]"""
    km2, km = face_km(faces)
    nb = collections.defaultdict(collections.Counter)        # (face -> neighbour -> km of border shared)
    for a, ks in side.items():
        if len(ks) == 2 and ks[0] != ks[1]:
            L = geo.length_km(arcs[a])
            nb[ks[0]][ks[1]] += L; nb[ks[1]][ks[0]] += L
    thin = np.flatnonzero(keep & ((km2 < MIN_FACE_KM2) | (2 * km2 / np.maximum(km, 1e-9) < THIN_KM))).tolist()
    n = 0
    for k in sorted(thin, key=lambda k: km2[k]):              # (the smallest first: one beside another takes its new owners)
        best = [j for j, _ in nb[k].most_common() if keep[j]]
        if best:
            own[k] = own[best[0]]; n += 1
    log(len(thin), "slivers,", n, "given their neighbour's owners")
    hist = np.unique(own, axis=0, return_inverse=True)[1].ravel()   # (the faces' histories: one number for each different)
    parent = list(range(len(faces)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for k, js in nb.items():
        for j in js:
            if keep[k] and keep[j] and hist[k] == hist[j]:
                parent[find(j)] = find(k)
    land = bio.land_km2(faces)                               # (an island near land of its owners: with them)
    big = [k for k, (f, pid) in enumerate(faces) if keep[k] and land[pid] >= ISLE_KM2]
    tree = STRtree([faces[k][0] for k in big])
    isles = 0
    for k, (f, pid) in enumerate(faces):
        if not keep[k] or land[pid] >= ISLE_KM2:
            continue
        cand = [big[j] for j in tree.query(f, predicate="dwithin", distance=NEAR_DEG).tolist() if hist[big[j]] == hist[k]]
        if cand:
            parent[find(k)] = find(min(cand, key=lambda j: shapely.distance(f, faces[j][0]))); isles += 1
    roots = {}
    out = [roots.setdefault(find(k), len(roots)) if keep[k] else -1 for k in range(len(faces))]
    log(len(roots), "regions of", int(keep.sum()), "faces;", isles, "islands with a region near them")
    return out


def names(faces, region, R):
    """each region's name: its county's where that county is half of it or more (the county its faces are most in),
    else its region's (the first-level division -- state, province -- it is most in) -> [{name, admin, country}]"""
    U = admin.units()
    trees = {k: STRtree([g for _, _, g in v]) for k, v in U.items()}
    most = [{k: collections.Counter() for k in trees} for _ in range(R)]
    size = np.zeros(R)
    for k, (f, _) in enumerate(faces):
        if region[k] < 0:
            continue
        p = shapely.point_on_surface(f)
        size[region[k]] += f.area
        for kind, t in trees.items():
            hit = t.query(p, predicate="within").tolist()
            if hit:
                most[region[k]][kind][hit[0]] += f.area
    def top(m, kind):
        u = m[kind].most_common(1)
        return (U[kind][u[0][0]], u[0][1]) if u else (None, 0)
    out = []
    for r, m in enumerate(most):
        (reg, _), (cty, ca), (cc, _) = top(m, "region"), top(m, "county"), top(m, "country")
        name = cty[0] if cty and (ca >= 0.5 * size[r] or not reg) else reg[0] if reg else cc[0] if cc else None
        out.append({"name": name, "admin": reg[0] if reg and name != reg[0] else None, "country": (cc or reg or cty or (None, None))[1]})
    return out


def short(n):
    """a day's number -> its text, a 1 January as its year"""
    t = iso(n)
    return t[:-6] if t.endswith("-01-01") else t


def short_shapes(faces, own, recs, ug, days):
    """the shapes of the country-periods the cut leaves less than SHORT of their land -> {shape}"""
    km2, _ = face_km(faces)
    at = {d: e for e, d in enumerate(days)}
    out = set()
    for i, r in enumerate(recs):
        G = ug[r["u"]]
        src = sum(abs(geo.ring_area_km2(shapely.get_coordinates(p.exterior))) - sum(abs(geo.ring_area_km2(shapely.get_coordinates(h))) for h in p.interiors)
                  for p in shapely.get_parts(G) if p.geom_type == "Polygon")
        if src >= SHORT_KM2 and km2[own[:, at[r["from"]]] == i].sum() < SHORT * src:
            out.add(r["u"])
    log(len(out), "shapes left short of", SHORT, "of their land by the first cut")
    return out


def main():
    recs, rings, ug = periods()
    cache, tie = os.path.join(ROOT, "work/history_faces.pkl"), max(CSHAPES_KM, ECO_KM)
    got = bio.cached_faces(cache, FACES_VERSION, SRC)
    if not got:                                              # (cut twice: the second time with the outlines of the
        arcs, faces = bio.land_faces(lambda S: cut_lines(rings, recs, S), os.path.join(ROOT, "work/history_faces1.pkl"), FIRST_CUT, SRC, tie)
        days, own = owners(faces, recs, ug)                  # periods the first cut leaves short)
        even(own, recs, days)
        lacking = short_shapes(faces, own, recs, ug, days)
        del arcs, faces, own
        got = bio.land_faces(lambda S: cut_lines(rings, recs, S, lacking), cache, FACES_VERSION, SRC, tie)
    arcs, faces = got
    del rings, got
    days, own = owners(faces, recs, ug)
    log(even(own, recs, days), "times a face a country-period had on some of its days only made all or none")
    E = len(days) - 1
    # ---- an island under MIN_LAND_KM2 goes, unless it is all a country-period has
    land = bio.land_km2(faces)
    rock = np.array([land[pid] < bio.MIN_LAND_KM2 for _, pid in faces])
    has = set(np.unique(own[~rock]).tolist())
    keep = ~rock | np.array([any(p >= 0 and p not in has for p in np.unique(o).tolist()) for o in own])
    log(int(rock.sum()), "faces of islands under", bio.MIN_LAND_KM2, "km2,", int((rock & keep).sum()), "kept (a country-period's only land)")

    # ---- the faces as arcs; which faces each arc bounds
    topo = write.Topo(arcs)
    rings_of, bad = [None] * len(faces), 0
    for k, (f, _) in enumerate(faces):
        if keep[k]:
            try:
                rings_of[k] = topo.polygon(f)
            except ValueError:
                bad += 1
    if bad:
        log(bad, "faces could not be read back as arcs")
    keep &= np.array([r is not None for r in rings_of])
    side = collections.defaultdict(list)
    for k, rr in enumerate(rings_of):
        if rr is not None:
            for r in rr:
                for a in r:
                    side[a if a >= 0 else ~a].append(k)
    region = regions(faces, own, side, arcs, keep)
    R = max(region) + 1
    members = collections.defaultdict(list)
    for k, r in enumerate(region):
        if r >= 0:
            members[r].append(k)
    first = [members[r][0] for r in range(R)]
    gw = np.array([r["state"] for r in recs] + [-1], np.int64)
    G = gw[own[first]]                                       # (each region's state on each epoch; nobody's: -1)

    # ---- regions: their faces merged, their owners as runs of days
    named = names(faces, region, R)
    geoms = []
    for r in range(R):
        g = G[r]
        cut = np.r_[0, np.flatnonzero(g[1:] != g[:-1]) + 1]
        held = [f"{short(days[e])}:{'' if g[e] < 0 else int(g[e])}" for e in cut.tolist()]
        if g[0] < 0:
            held = held[1:]
        geoms.append(write.geometry(write.merge(topo, [rings_of[k] for k in members[r]]), {
            "id": r + 1, **named[r], "held": held, "label": bio.label(faces, members[r])}))
    objects = {"regions": {"type": "GeometryCollection", "geometries": geoms}}
    log(R, "regions,", sum(len(g["properties"]["held"]) for g in geoms), "owners in their histories")

    qarcs = write.quantize(arcs)
    write.drop_inside_out(objects, qarcs, ["regions"])
    qarcs = write.drop_unused(objects, qarcs)
    write.area_km2(objects, qarcs, ["regions"])

    # ---- periods: each country-period's regions on its first day -- its area, and its label: the label of its region
    # nearest the middle of them all (weighed by area)
    area = np.array([g["properties"].get("area_km2") or 0 for g in geoms], float)
    lab = np.array([g["properties"]["label"] for g in geoms], float)
    xyz = geo.to_xyz(lab)
    at = {d: e for e, d in enumerate(days)}
    rows, nothing = [], 0
    for i, r in enumerate(recs):
        e = at[r["from"]]
        rs = np.flatnonzero(own[first, e] == i)
        if not len(rs):
            nothing += 1
            continue
        mid = (xyz[rs] * area[rs, None]).sum(axis=0)
        best = int(rs[np.argmax(xyz[rs] @ mid)])
        rows.append({"type": None, "id": f"{r['state']}:{iso(r['from'])}", "properties": {k: v for k, v in (
            ("state", r["state"]), ("name", r["name"]), ("from", iso(r["from"])), ("to", iso(r["to"])), ("source", r["source"]),
            ("precision", r["precision"]), ("status", r["status"]), ("owner", r["owner"]), ("capital", r["capital"]),
            ("cap", r["cap"]), ("gwcode", r["gwcode"]), ("area_km2", int(round(area[rs].sum()))),
            ("label", geoms[best]["properties"]["label"])) if v is not None}})
    if nothing:
        log(nothing, "country-periods with no land of their own (under another drawn alike, or off the map's land)")
    objects["periods"] = {"type": "GeometryCollection", "geometries": rows}
    log(len(rows), "country-periods")

    out = {"type": "Topology", "bbox": [-180, -90, 180, 90],
           "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
           "objects": objects, "arcs": qarcs}
    path = os.path.join(ROOT, "full/history.topo.json")
    json.dump(out, open(path, "w"), separators=(",", ":"))
    log(f"{path}: {os.path.getsize(path) / 2**20:.1f} MB, {len(qarcs)} arcs")


if __name__ == "__main__":
    main()
