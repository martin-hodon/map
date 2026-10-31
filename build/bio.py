"""STAGE 9 -- THE BIOGEOGRAPHIC LAYER: the land cut into the terrestrial ecoregions of the world (RESOLVE Ecoregions 2017,
Dinerstein et al. 2017, CC BY 4.0: raw/ecoregions/, build/fetch_bio.sh), and those grouped into their biomes and their
biogeographic realms -- for showing where something lives (an animal's range as a list of regions to highlight).

    build/capped.sh .venv/bin/python build/bio.py     # work/topology.pkl + raw/ecoregions -> full/bio.topo.json

Made of the map's own lines, as the areas are (build/areas.py): the COAST is the map's, and the borders between
ecoregions are lines across the land. RESOLVE's polygons share their vertices along a border, so a border is the
segments two of them have both; it is taken once, cut into edges where three regions meet, simplified, cut to the
map's land (a piece that only runs along the coast is RESOLVE's coast, not a border: dropped) and put into the coast
(areas.into_coast). Each landmass is cut by those lines into faces (topology.faces), and a face belongs to the ecoregion
covering most of it -- an island RESOLVE has not, to the nearest one. "Rock and Ice" (ice sheets, the highest
mountains) has no realm in RESOLVE: each of its faces takes the realm of the nearest ecoregion.

Objects (one file, every line stored once; loaded by index.html only when the map shows it):
    realms      the 8 biogeographic realms: id (PA NA NT AT IM AA OC AN), name
    biomes      the 14 biomes and Rock and Ice: id (B0-B14), name, color (RESOLVE's)
    ecoregions  the 847 ecoregions: id (E + RESOLVE's ECO_ID), eco (that number), name, biome, realm, nnh (Nature
                Needs Half: 1 half protected, 2 could recover, 3 could reach half, 4 imperilled), color (RESOLVE's),
                area_km2, label (a point well inside)
A list of ids (`PA`, `B7`, `E345`, mixed) is what index.html highlights: `#bio=PA,E345`.
"""
import os, sys, time, json, pickle, collections
import numpy as np, shapely, duckdb
from shapely import STRtree
from shapely.ops import polylabel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config, topology, areas, write

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "raw/ecoregions/Ecoregions2017.shp")
REALMS = {"Palearctic": "PA", "Nearctic": "NA", "Neotropic": "NT", "Afrotropic": "AT", "Indomalayan": "IM",
          "Australasia": "AA", "Oceania": "OC", "Antarctica": "AN"}
ICE = 0                     # RESOLVE's "Rock and Ice": no realm, no biome of the fourteen
FACES_VERSION = 12          # (work/bio_faces.pkl is made again when the way of cutting changes: 2 the lake shores too, 4 TIE_KM,
                            # 5 BORDER_KM and no islet rings, 6 a tie's point put into the line it meets, 10 the inland ends merged
                            # before the lines are joined, 11 lines cut again at the coast, hugs in km on the ground, 12 a
                            # border's nearest coast may jump)
BORDER_KM = 2.0             # a border's simplification: RESOLVE's borders are traced from a raster, a straight line runs as a
                            # staircase of its cells -- steps under this are flattened (the map's own lines: config.EPS_KM)
MIN_LAND_KM2 = 10.0         # an island (with all its faces) smaller than this is left out of the file: a rock -- unless it is
                            # all its ecoregion has (Clipperton, Malpelo: an animal living only there still has a place)
TIE_KM = 1.0                # a border end left meeting nothing (simplified, two ends of one junction drift apart: west of the
                            # Great Slave Lake by 60 m) is tied to the nearest line within this -- else a face left open
                            # there merges two ecoregions
NO_AREA_DEG2 = 1e-9         # a face smaller than this (~12 m2) is no face: a sliver between two lines on one path
SMALL_DEG2 = 0.01           # a face smaller than this (~100 km2) is in the ecoregion its inner point is in
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


def ecoregions():
    """RESOLVE's ecoregions -> (records, the rings of their polygons as [(record index, coords)]); kept in
    work/ecoregions.pkl (reading the shapefile takes minutes)"""
    cache = os.path.join(ROOT, "work/ecoregions.pkl")
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(SRC):
        return pickle.load(open(cache, "rb"))
    con = duckdb.connect()
    con.execute("LOAD spatial; SET memory_limit='600MB'; SET threads=1")
    cur = con.execute(f"SELECT ECO_ID, ECO_NAME, BIOME_NUM, BIOME_NAME, REALM, NNH, COLOR, COLOR_BIO, ST_AsWKB(geom) FROM ST_Read('{SRC}') ORDER BY ECO_ID")
    recs, rings = [], []
    while batch := cur.fetchmany(20):
        for eco, name, biome, bname, realm, nnh, color, cbio, wkb in batch:
            g = shapely.make_valid(shapely.from_wkb(bytes(wkb)))
            n = len(recs)
            for p in shapely.get_parts(g):
                if p.geom_type != "Polygon":
                    continue
                for r in (p.exterior, *p.interiors):
                    rings.append((n, shapely.get_coordinates(r)))
            ice = int(eco) == ICE
            recs.append({"eco": int(eco), "name": name, "biome": 0 if ice else int(biome), "biome_name": "Rock and Ice" if ice else bname,
                         "realm": REALMS.get(realm), "nnh": int(nnh) if nnh else None, "color": color, "color_bio": cbio,
                         "G": shapely.make_valid(shapely.simplify(g, 0.01))})   # (to tell which ecoregion a face is in: roughly is enough)
    log(len(recs), "ecoregions,", len(rings), "rings,", sum(len(c) for _, c in rings), "points")
    pickle.dump((recs, rings), open(cache, "wb"))
    return recs, rings


def borders(rings, km=BORDER_KM, islets=True):
    """the ecoregions' outlines, every segment once (a border two rings have both; RESOLVE's coast and lake shores,
    which one ring has -- a border running to a lake RESOLVE leaves out, the Great Lakes, must end on its shore or the
    faces around it do not close), as edges from one meeting of lines to the next, simplified on the sphere to km ->
    [coords]. (Their coast is dropped where it only runs along the map's: areas.on_side.) build/history.py's
    country-periods so too. islets: leave out a ring that borders nothing (False: some polygons' outlines, without their
    neighbours -- each borders nothing, and is no island)."""
    ks = [geo.key(c) for _, c in rings]
    a = np.concatenate([k[:-1] for k in ks]); b = np.concatenate([k[1:] for k in ks])
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    del a, b
    order = np.lexsort((hi, lo))
    same = (lo[order][1:] == lo[order][:-1]) & (hi[order][1:] == hi[order][:-1])
    shared = np.zeros(len(lo), bool); first = np.zeros(len(lo), bool)   # (shared: only to tell a ring that borders nothing)
    shared[order[1:][same]] = True; shared[order[:-1][same]] = True
    first[order[np.r_[True, ~same]]] = True                  # (each segment once: where it comes first)
    # (a segment along the antimeridian is where the data is cut, as the map's land is: no border -- laid over the
    # land's own cut it would open the landmass's ring there, and Russia's faces would fall out with the sea's)
    x0 = np.concatenate([np.abs(c[:-1, 0]) for _, c in rings]); x1 = np.concatenate([np.abs(c[1:, 0]) for _, c in rings])
    keep = first & ~((x0 >= 180 - 1e-9) & (x1 >= 180 - 1e-9))
    del x0, x1
    del order, same
    # (the vertices where the borders meet: on more than two of the kept segments, or where a border ends)
    ends = np.concatenate([lo[keep], hi[keep]])
    uk, cnt = np.unique(ends, return_counts=True)
    node = uk[cnt != 2]                                      # (sorted: a vertex is looked up in it, is_node)
    is_node = lambda k: node[np.minimum(np.searchsorted(node, k), max(len(node) - 1, 0))] == k if len(node) else np.zeros(len(k), bool)
    log(int(shared.sum()), "segments on a border between two,", int(keep.sum()), "segments once,", len(node), "nodes")
    del lo, hi, first, ends, uk, cnt
    # (a ring that shares no segment and no meeting point with another, and touches or crosses none, is an island's
    # coast: nothing to cut. One drawn without shared points -- historical-basemaps' peoples of Australia, each on its
    # own -- crosses its neighbours: cut)
    at, islet = 0, set()
    for r, ((_, c), k) in enumerate(zip(rings, ks)):
        m = len(c) - 1
        if not shared[at:at + m].any() and not is_node(k).any():
            islet.add(r)
        at += m
    if not islets:
        islet = set()
    if islet:
        lines = np.array([shapely.linestrings(c) for _, c in rings])
        cand = sorted(islet)
        hit_a, hit_b = shapely.STRtree(lines).query(lines[cand], predicate="intersects")
        islet -= {cand[a] for a, b in zip(hit_a.tolist(), hit_b.tolist()) if cand[a] != b}
    out, at = [], 0
    for r, ((_, c), k) in enumerate(zip(rings, ks)):
        m = len(c) - 1
        kp = keep[at:at + m]; at += m
        if not kp.any() or r in islet:
            continue
        isn = is_node(k)                               # (a run of kept segments stops at a node: a border edge)
        starts = np.flatnonzero(kp & np.r_[True, ~kp[:-1] | isn[1:m]])
        ends_ = np.flatnonzero(kp & np.r_[~kp[1:] | isn[1:m], True])
        for i, j in zip(starts.tolist(), ends_.tolist()):
            run = c[i:j + 2]
            out.append(run[geo.simplify(geo.to_xyz(run), km)])
    log(len(out), "border edges,", sum(len(c) for c in out), "points;", len(islet), "rings of islands left out")
    return out


def land_faces(edges, cache, version, source, tie_km=TIE_KM):
    """the map's land cut by lines (edges(S): [coords] -- the outlines of polygons, borders(); S: the map, areas.setup --
    cut to the land, put into the coast: areas.into_coast) -> (arcs as coords, [(face, landmass id)]); kept in cache while it is newer than source
    and of this version (the cutting takes ~15 min). A line end meeting nothing is tied to the nearest line within tie_km."""
    got = cached_faces(cache, version, source)
    if got:
        return got
    S = areas.setup()
    edges = edges(S)
    pieces = []
    for n, c in enumerate(edges):
        line = shapely.linestrings(c)
        pieces += [shapely.linestrings(p) for p in areas.on_side(line, line, "land", S)]
        if n % 2000 == 0:
            log(f"  {n}/{len(edges)} edges cut to the land, {len(pieces)} pieces")
    del edges
    areas.into_coast(pieces, S, tie_km)
    T = S["T"]
    faces = topology.faces(S["arcs"], S["ring_arcs"], T["poly"], T["hole"], ("area",))
    # (not the map's own borders, not the lines dropped as twins: a face's ring would be walked along them)
    arcs = [a.c for a in S["arcs"] if a.kind in ("coast", "area")]
    pickle.dump((version, arcs, [(shapely.to_wkb(f), pid) for f, pid in faces]), open(cache, "wb"))
    return arcs, real_faces(faces)


def cached_faces(cache, version, source):
    """land_faces' faces from its cache, if it is newer than source and of this version -> (arcs, faces) or None"""
    got = pickle.load(open(cache, "rb")) if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(source) else None
    if not (got and len(got) == 3 and got[0] == version):
        return None
    _, arcs, faces = got
    faces = [(shapely.from_wkb(w), pid) for w, pid in faces]
    log(len(faces), "faces from", cache)
    return arcs, real_faces(faces)


def real_faces(faces):
    """without the faces of no area: a sliver between two lines on one path (the polygonizer's, from a ring made valid)
    runs along them both ways at once, and a country merged of the faces next to it loses its outline there"""
    out = [(f, pid) for f, pid in faces if f.area > NO_AREA_DEG2]
    if len(out) < len(faces):
        log(len(faces) - len(out), "faces of no area left out")
    return out


def land_km2(faces):
    """each landmass's size (its faces') -> {landmass id: km2}"""
    land = collections.Counter()
    for f, pid in faces:
        land[pid] += sum(abs(geo.ring_area_km2(shapely.get_coordinates(p.exterior))) for p in shapely.get_parts(f) if p.geom_type == "Polygon")
    return land


def label(faces, ks):
    """a point well inside the biggest of the faces ks -> [lon, lat]"""
    big = max(ks, key=lambda k: faces[k][0].area)
    try:
        p = polylabel(faces[big][0], 0.01)
    except Exception:                                        # (an invalid face: a point on it)
        p = shapely.point_on_surface(faces[big][0])
    return [round(p.x, 3), round(p.y, 3)]


def main():
    recs, rings = ecoregions()
    for r in recs:                                           # (a simplified outline can cross itself: made valid)
        r["G"] = shapely.make_valid(r["G"])
    arcs, faces = land_faces(lambda S: borders(rings), os.path.join(ROOT, "work/bio_faces.pkl"), FACES_VERSION, os.path.join(ROOT, "work/ecoregions.pkl"))
    del rings
    land = land_km2(faces)

    # ---- each face: the ecoregion covering most of it (none: the nearest); Rock and Ice's: the realm of the nearest other
    gtree = STRtree([r["G"] for r in recs])
    others = [i for i, r in enumerate(recs) if r["eco"] != ICE]
    otree = STRtree([recs[i]["G"] for i in others])
    for r in recs:
        shapely.prepare(r["G"])
    owner, realm_of, far = [], [], 0
    for f, _ in faces:
        p = shapely.point_on_surface(f)
        best, bi = 0.0, None
        if f.area < SMALL_DEG2:                              # (a small face -- most are islets: the ecoregion its point is in)
            hit = gtree.query(p, predicate="within").tolist()
            if len(hit) == 1:
                bi = hit[0]
        if bi is None:
            for i in gtree.query(f).tolist():
                try:
                    s = shapely.intersection(recs[i]["G"], f).area
                except shapely.errors.GEOSException:          # (a face of a thin ring, crossing itself on the grid)
                    s = shapely.intersection(recs[i]["G"], shapely.make_valid(f)).area
                if s > best:
                    best, bi = s, i
        if bi is None:
            bi = int(gtree.query_nearest(p)[0]); far += 1
        owner.append(bi)
        realm_of.append(recs[bi]["realm"] or recs[others[int(otree.query_nearest(p)[0])]]["realm"])
    log(len(faces), "faces,", far, "in no ecoregion (given the nearest)")
    rock = [land[pid] < MIN_LAND_KM2 for _, pid in faces]   # (an island under MIN_LAND_KM2 goes, unless all its ecoregion has)
    has = {o for o, r in zip(owner, rock) if not r}
    keep = [not r or o not in has for o, r in zip(owner, rock)]
    faces, owner, realm_of = ([x for x, k in zip(xs, keep) if k] for xs in (faces, owner, realm_of))
    log(len(keep) - sum(keep), "faces of islands under", MIN_LAND_KM2, "km2 left out,", sum(r and k for r, k in zip(rock, keep)), "kept: their ecoregion's only land")

    # ---- the file: the faces as arcs, merged per ecoregion, biome, realm
    topo = write.Topo(arcs)
    rings_of, bad = [], 0
    for f, _ in faces:
        try:
            rings_of.append(topo.polygon(f))
        except ValueError:
            rings_of.append(None); bad += 1
    if bad:
        log(bad, "faces could not be read back as arcs")
    def grouped(key):
        g = collections.defaultdict(list)
        for k, (rr, o, rl) in enumerate(zip(rings_of, owner, realm_of)):
            if rr is not None:
                g[key(o, rl)].append(k)
        return g
    objects = {}
    eco = grouped(lambda o, rl: o)
    objects["ecoregions"] = {"type": "GeometryCollection", "geometries": [write.geometry(write.merge(topo, [rings_of[k] for k in ks]), {
        "id": f"E{recs[o]['eco']}", "eco": recs[o]["eco"], "name": recs[o]["name"], "biome": f"B{recs[o]['biome']}",
        "realm": recs[o]["realm"], "nnh": recs[o]["nnh"], "color": recs[o]["color"], "label": label(faces, ks)}) for o, ks in sorted(eco.items())]}
    bio = grouped(lambda o, rl: recs[o]["biome"])
    bname = {r["biome"]: (r["biome_name"], r["color_bio"]) for r in recs}
    objects["biomes"] = {"type": "GeometryCollection", "geometries": [write.geometry(write.merge(topo, [rings_of[k] for k in ks]), {
        "id": f"B{b}", "name": bname[b][0], "color": bname[b][1]}) for b, ks in sorted(bio.items())]}
    rl = grouped(lambda o, rl: rl)
    rname = {v: k for k, v in REALMS.items()}
    objects["realms"] = {"type": "GeometryCollection", "geometries": [write.geometry(write.merge(topo, [rings_of[k] for k in ks]), {
        "id": r, "name": rname[r], "label": label(faces, ks)}) for r, ks in sorted(rl.items()) if r]}
    log(len(objects["ecoregions"]["geometries"]), "ecoregions,", len(objects["biomes"]["geometries"]), "biomes,", len(objects["realms"]["geometries"]), "realms")
    qarcs = write.quantize(arcs)
    write.drop_inside_out(objects, qarcs, list(objects))
    qarcs = write.drop_unused(objects, qarcs)
    write.area_km2(objects, qarcs, ["ecoregions"])
    out = {"type": "Topology", "bbox": [-180, -90, 180, 90],
           "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
           "objects": objects, "arcs": qarcs}
    path = os.path.join(ROOT, "full/bio.topo.json")
    json.dump(out, open(path, "w"), separators=(",", ":"))
    log(f"{path}: {os.path.getsize(path) / 2**20:.1f} MB, {len(qarcs)} arcs")


if __name__ == "__main__":
    main()
