"""STAGE 4 -- WATER: the big lakes, and the rivers where they are 50 m wide or more.

    .venv/bin/python build/water.py               # -> work/lakes.pkl (for build/write.py), full/rivers.tracked.topo.json (for build/rivernet.py)

LAKES: every lake or reservoir polygon (OSM's water areas, via raw/water.parquet) of MIN_LAKE_KM2 or more, simplified
on the sphere like the coast; islands in them under MIN_ISLAND_KM2 left out.

RIVERS: OSM rarely says how wide a river is, but it maps every river of any size as an AREA (water=river) around its
centerline (waterway=river). So the width is measured: the centerline is sampled every ~250 m, and where a sample
lies inside the river's water -- the river areas merged, so the joins between their pieces are not banks -- the
width there is twice its distance to the nearest bank. A river is kept where that is RIVER_MIN_M or more:
  * the widths are smoothed (a running median over ~1 km), so an island or a bridge does not cut it;
  * a stretch across a lake or reservoir is kept when the river is wide on both sides of it;
  * narrow gaps under GAP_KM between wide stretches are bridged, and wide stretches under MIN_RUN_KM are dropped.
The kept stretches of each river are joined end to end, simplified to EPS_KM and written as TopoJSON lines with
their name (English, from Wikidata, where it has one; `name_local` OSM's), Wikidata id and width (median and max, m).

MEMORY: the water file is ~5 GB of geometry and 2.5 million rivers, so nothing is read whole. It is cut once into
TILE-degree tiles on disk (work/water_tiles/, read a few rows at a time), and the rivers are measured tile by tile:
all that is kept of a tile is the samples that lie in water.

    .venv/bin/python build/water.py names         # (only: full/rivers.tracked.topo.json's rivers named -- English, and local)
"""
import os, sys, time, json, pickle, collections
import duckdb, numpy as np, shapely
import shapely.ops
from shapely import STRtree
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config, wdnames
from write import quantize

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WATER = os.path.join(ROOT, "raw/water.parquet")
TILES = os.path.join(ROOT, "work/water_tiles")
RIVER_MIN_M = 50.0
STEP_DEG = 0.0025          # the samples along a centerline (~250 m)
GAP_KM = 2.0
MIN_RUN_KM = 3.0
MIN_RIVER_KM = 50.0        # a river drawn shorter than this (from where it is first wide to its end) is left out
BIG = 1000                 # a river among the BIG longest or widest is kept whatever Wikipedia knows
BRIDGE_KM = 10.0           # a gap between two ways of one river (a lake without a centerline) is bridged up to this
FAR_BRIDGE_KM = 30.0       # ...and up to this where the gap lies ahead, the way the river was going (a long reservoir)
TILE = 2.0                 # degrees: the rivers are measured tile by tile
MARGIN = 0.1               # ...with the water this far round each tile (so the banks just outside it count)
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ---- lakes --------------------------------------------------------------------------------------------------------
def lakes(con):
    out = []
    rel = con.execute(f"SELECT id, name, subtype, wikidata, ST_AsWKB(geometry) FROM '{WATER}' WHERE subtype IN ('lake', 'reservoir')")
    from write import signed_area
    seen = 0
    while True:
        rows = rel.fetchmany(100)
        if not rows:
            break
        for oid, name, sub, wd, w in rows:
            seen += 1
            g = shapely.from_wkb(w)
            for p in shapely.get_parts(g):
                ext = shapely.get_coordinates(p.exterior)
                a = abs(geo.ring_area_km2(ext))
                if a < config.MIN_LAKE_KM2:
                    continue
                rings = [ext]
                for h in p.interiors:
                    c = shapely.get_coordinates(h)
                    if abs(geo.ring_area_km2(c)) >= config.MIN_ISLAND_KM2:
                        rings.append(c)
                rings = [c[geo.simplify(geo.to_xyz(c), config.EPS_KM)] for c in rings]
                # (wound for d3: outer clockwise, islands anticlockwise)
                rings = [c if (i == 0) == (signed_area(c) < 0) else c[::-1] for i, c in enumerate(rings)]
                out.append({"rings": rings, "name": name, "type": sub, "wikidata": wd, "area_km2": round(a, 1)})
    log(f"lakes: {len(out)} of {config.MIN_LAKE_KM2} km2 or more (of {seen} big-box candidates)")
    pickle.dump(out, open(os.path.join(ROOT, "work/lakes.pkl"), "wb"))


# ---- rivers -------------------------------------------------------------------------------------------------------
def split_water(con):
    """raw/water.parquet cut into TILE-degree tiles on disk (work/water_tiles/<i>_<j>.pkl: a stream of pickled row
    lists): read once, a few rows at a time; a feature goes to every tile its box reaches (+ MARGIN), a polygon over
    several tiles clipped to each. Each tile is then small enough to measure on its own."""
    done = os.path.join(TILES, "done")
    if os.path.exists(done):
        return
    os.makedirs(TILES, exist_ok=True)
    for f in os.listdir(TILES):                              # (a pass cut short: start over)
        os.remove(os.path.join(TILES, f))
    rel = con.execute(f"""SELECT subtype, CASE WHEN ST_GeometryType(geometry) IN ('LINESTRING', 'MULTILINESTRING') THEN 'line' ELSE 'poly' END,
                                 id, name, wikidata, bbox.xmin, bbox.xmax, bbox.ymin, bbox.ymax, ST_AsWKB(geometry) FROM '{WATER}'""")
    buf, size, n = collections.defaultdict(list), 0, 0

    def flush():
        for (i, j), rows in buf.items():
            with open(os.path.join(TILES, f"{i}_{j}.pkl"), "ab") as fh:
                pickle.dump(rows, fh)
        buf.clear()

    m = MARGIN
    while True:
        rows = rel.fetchmany(100)
        if not rows:
            break
        for s, g, oid, name, wd, x0, x1, y0, y1, w in rows:
            n += 1
            cells = [(i, j) for i in range(int(np.floor((x0 - m) / TILE)), int(np.floor((x1 + m) / TILE)) + 1)
                            for j in range(int(np.floor((y0 - m) / TILE)), int(np.floor((y1 + m) / TILE)) + 1)]
            if len(cells) == 1 or g == "line":               # (a line whole: it is sampled along its full length)
                for c in cells:
                    buf[c].append((s, g, oid, name, wd, w)); size += len(w)
                continue
            geom = shapely.from_wkb(w)
            for i, j in cells:
                part = shapely.clip_by_rect(geom, i * TILE - m, j * TILE - m, (i + 1) * TILE + m, (j + 1) * TILE + m)
                if not part.is_empty:
                    pw = shapely.to_wkb(part)
                    buf[(i, j)].append((s, g, oid, name, wd, pw)); size += len(pw)
        if size > 64 * 2**20:
            flush(); size = 0
        if n % 200000 < 100:
            log(f"  {n:,} water features into tiles")
    flush()
    open(done, "w").write(str(n))
    log(f"water: {n:,} features in {len(os.listdir(TILES)) - 1} tiles")


def read_tile(i, j):
    rows = []
    with open(os.path.join(TILES, f"{i}_{j}.pkl"), "rb") as fh:
        while True:
            try:
                rows += pickle.load(fh)
            except EOFError:
                return rows


def tile_widths(rows, x0, y0, lines):
    """one tile: every centerline crossing it sampled every STEP_DEG; the samples inside the tile measured against the
    river water around them (width in metres; -1 in a lake or reservoir). Only lines with a measured sample are kept
    in `lines`: key -> {"name", "wikidata", "c": all its samples (float32), "i", "w": its measured samples and their
    widths, in chunks (numpy: a few bytes a sample)}"""
    river = [shapely.from_wkb(w) for s, g, *_ , w in rows if s == "river" and g == "poly" and w]
    still = [shapely.from_wkb(w) for s, g, *_ , w in rows if s != "river" and w]
    if not river and not still:
        return
    water = lake = None
    if river:
        water = shapely.union_all([shapely.make_valid(g) for g in river])
        shapely.prepare(water)
    if still:
        lake = shapely.union_all([shapely.make_valid(g) for g in still])
        shapely.prepare(lake)
    k = np.cos(np.radians(y0 + TILE / 2))                    # (local metres: longitude shrunk by the latitude)
    tree = None
    for s, g, oid, name, wd, w in rows:
        if s != "river" or g != "line":
            continue
        for part, p in enumerate(shapely.get_parts(shapely.from_wkb(w))):
            c = shapely.get_coordinates(shapely.segmentize(p, STEP_DEG))
            if len(c) < 2:
                continue
            here = np.flatnonzero((c[:, 0] >= x0) & (c[:, 0] < x0 + TILE) & (c[:, 1] >= y0) & (c[:, 1] < y0 + TILE))
            if not len(here):
                continue
            W = np.zeros(len(here), np.float32)
            px, py = c[here, 0], c[here, 1]
            if water is not None:
                inside = shapely.contains_xy(water, px, py)
                if inside.any():
                    if tree is None:                         # the banks: the merged water's rings, as segments in local metres
                        segs = []
                        for q in shapely.get_parts(water):
                            for ring in (shapely.get_rings(q) if q.geom_type == "Polygon" else []):
                                rc = shapely.get_coordinates(ring)
                                rc = np.column_stack((rc[:, 0] * k, rc[:, 1]))
                                segs.append(np.stack((rc[:-1], rc[1:]), axis=1))
                        tree = STRtree(shapely.linestrings(np.concatenate(segs))) if segs else False
                    if tree is not False:
                        _, d = tree.query_nearest(shapely.points(px[inside] * k, py[inside]), return_distance=True, all_matches=False)
                        W[inside] = 2 * d * 111320.0          # (degrees of latitude -> metres; the width is twice the half)
            if lake is not None:
                W[shapely.contains_xy(lake, px, py) & (W == 0)] = -1
            got = np.flatnonzero(W != 0)
            if not len(got):
                continue
            key = (oid, part)
            L = lines.get(key)
            if L is None:
                L = lines[key] = {"name": name, "wikidata": wd, "c": None, "i": [], "w": []}
            if L["c"] is None and (W >= RIVER_MIN_M).any():   # (its samples only once it is wide somewhere: most never are)
                L["c"] = c.astype(np.float32)
            L["i"].append(here[got].astype(np.int32)); L["w"].append(W[got])


def widths(con):
    split_water(con)
    lines = {}
    tiles = sorted(tuple(int(v) for v in f[:-4].split("_")) for f in os.listdir(TILES) if f.endswith(".pkl"))
    for n, (i, j) in enumerate(tiles):
        rows = read_tile(i, j)
        if any(r[0] == "river" and r[1] == "line" for r in rows):
            tile_widths(rows, i * TILE, j * TILE, lines)
        del rows
        if n % 200 == 0:
            log(f"  {n}/{len(tiles)} tiles, {len(lines)} lines with measured water, {sum(len(x) for L in lines.values() for x in L['w']):,} samples")
    return lines


def runs(L):
    """one line's stretches that are wide enough: [(start sample, end sample, median width, max)]"""
    if L["c"] is None:
        return []
    n = len(L["c"])
    w = np.zeros(n)
    w[np.concatenate(L["i"])] = np.concatenate(L["w"])
    if not (w >= RIVER_MIN_M).any():
        return []
    step_km = STEP_DEG * 111.32
    # smoothed: the running median over ~1 km (lakes as unknown)
    h = 2
    pad = np.pad(np.where(w < 0, np.nan, w), h, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * h + 1)
    with np.errstate(all="ignore"):
        med = np.nanmedian(win, axis=1)
    # a lake between wide stretches is part of the river; so is a narrow gap under GAP_KM
    state = np.where(med >= RIVER_MIN_M, 1, np.where(w < 0, 2, 0))
    k = 0
    while k < n:
        if state[k] != 1:
            j = k
            while j < n and state[j] != 1:
                j += 1
            if k > 0 and j < n and (np.all(state[k:j] == 2) or (j - k) * step_km < GAP_KM):
                state[k:j] = 1
            k = j
        else:
            k += 1
    edges = np.flatnonzero(np.diff(np.concatenate(([0], (state == 1).astype(int), [0]))))
    out = []
    for a, b in zip(edges[::2], edges[1::2]):
        if (b - a) * step_km < MIN_RUN_KM:
            continue
        ws = w[a:b][w[a:b] > 0]
        out.append((a, b, float(np.median(ws)) if len(ws) else 0.0, float(ws.max()) if len(ws) else 0.0))
    return out


def collect_ways(by):
    """every centerline way of the rivers that are wide somewhere: the ways of their names or their Wikidata items
    (a stretch of the Amazon along the Peru-Colombia border has the item and no name), and the unnamed wide ones by
    their id, read from the tiles once and kept at FINE_KM (their ends as they are)"""
    path = os.path.join(ROOT, "work/river_ways.pkl")
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    names = {k[0] for k in by if k[0]}
    items = {k[1] for k in by if k[0] and k[1]}
    loose = {k[1].rsplit("/", 1)[0] for k in by if not k[0]}
    ways, seen = [], set()
    tiles = sorted(tuple(int(v) for v in f[:-4].split("_")) for f in os.listdir(TILES) if f.endswith(".pkl"))
    for n, (i, j) in enumerate(tiles):
        for s, g, oid, name, wd, w in read_tile(i, j):
            if s != "river" or g != "line" or oid in seen or not (name in names or wd in items or oid in loose):
                continue
            seen.add(oid)
            for part, p in enumerate(shapely.get_parts(shapely.from_wkb(w))):
                c = shapely.get_coordinates(p)
                c = c[np.r_[True, np.any(c[1:] != c[:-1], axis=1)]]
                if len(c) < 2:
                    continue
                c = c[geo.simplify(geo.to_xyz(c), config.FINE_KM)]
                ways.append({"oid": oid, "part": part, "name": name, "wikidata": wd, "c": c, "length_km": geo.length_km(c)})
        if n % 500 == 0:
            log(f"  {n}/{len(tiles)} tiles, {len(ways):,} ways, {sum(len(w['c']) for w in ways):,} points")
    pickle.dump(ways, open(path, "wb"))
    return ways


def track(by, ways):
    """each river that is wide somewhere, from its source to its end: from the wide stretch down along its ways in
    the direction OSM draws them (the flow), way to way of the same name, over gaps under BRIDGE_KM (a lake without a
    centerline; under FAR_BRIDGE_KM where the gap lies straight ahead) by a straight line, at a fork down every arm;
    then back up from every way reached, to the source, way to way of the same name. -> [(river id, pieces, widths)]"""
    for w in ways:
        w["osm_name"] = w["name"]
    wdnames.rename(ways)                                    # (the same river by one name: "Rhein" and "Le Rhin / Rhein" are the Rhine)
    group = collections.defaultdict(list)                   # the English name (an unnamed way alone) -> its ways
    by_osm = collections.defaultdict(list)                  # OSM's name (or the way id) -> its ways, to find the wide stretches on
    for k, w in enumerate(ways):
        group[w["name"] or ("", w["oid"])].append(k)
        by_osm[w["osm_name"] or w["oid"]].append(k)
    lines = [shapely.linestrings(w["c"]) for w in ways]
    key = lambda p: int(geo.key(p))
    # the wide stretches' first samples, on their ways
    starts, trees = [], {}
    for (name, wd), parts in by.items():
        g = name or wd.rsplit("/", 1)[0]
        ks = by_osm.get(g)
        if not ks:
            continue
        if g not in trees:
            trees[g] = STRtree([lines[k] for k in ks])
        for arr, wmed, wmax in parts:
            p0 = shapely.points(arr[:1].astype(float))
            (_, j), d = trees[g].query_nearest(p0, return_distance=True, all_matches=False)
            if float(d[0]) < 0.003:
                k = ks[int(j[0])]
                starts.append((k, float(shapely.line_locate_point(lines[k], p0[0])), wmed, wmax))
    log(len(starts), "wide stretches found on their ways")
    # downstream, way by way: on to a way that starts where this one ends and shares a name with it -- English, OSM's,
    # one part of a name in two languages ("Le Rhin / Rhein"), or one within the other ("Große Isar", the arm of the
    # Isar through Landshut) -- so a river goes on through its sections (High
    # Rhine, Upper Rhine...) and across a border, and a tributary stops where it flows into another river
    import re as _re
    def names(w):
        t = {x.strip().lower() for n in (w["name"], w["osm_name"]) if n for x in _re.split(r"\s*[/;,]\s*|\s+-\s+", n) if x.strip()}
        return t
    tok = [names(w) for w in ways]
    heads = collections.defaultdict(list)
    for k, w in enumerate(ways):
        heads[key(w["c"][0])].append(k)
    hx = cKDTree(geo.to_xyz(np.array([w["c"][0] for w in ways])))
    ring = [key(w["c"][0]) == key(w["c"][-1]) for w in ways]   # (a way round an island in the river, or a reservoir's shore: no way on)
    bridge_chord = 2 * np.sin(BRIDGE_KM / geo.R_KM / 2)
    far_chord = 2 * np.sin(FAR_BRIDGE_KM / geo.R_KM / 2)
    def ahead(k, p):                                        # is p on, roughly, where way k was heading at its end?
        c = ways[k]["c"]
        i = max(0, len(c) - 2)
        while i > 0 and geo.length_km(c[i:]) < 2.0:
            i -= 1
        u, v = c[-1] - c[i], p - c[-1]
        u[0] *= np.cos(np.radians(c[-1][1])); v[0] *= np.cos(np.radians(c[-1][1]))
        return float(u @ v) > 0.3 * float(np.linalg.norm(u) * np.linalg.norm(v))
    def within(x, y):                                       # (one name in the other, as whole words: "Isar" in "Große Isar")
        return len(x) >= 3 and _re.search(r"(?<!\w)" + _re.escape(x) + r"(?!\w)", y) is not None
    # ...or by Wikidata: the same item, or one a part (P361) of the other's -- the Solimões is the Amazon's Brazilian
    # upper course, under its own name and item, part of the Amazon's
    part = wdnames.part_of(sorted({w["wikidata"] for w in ways if w["wikidata"]}))
    def same(a, b):
        wa, wb = ways[a]["wikidata"], ways[b]["wikidata"]
        if wa and wb and (wa == wb or part.get(wa) == wb or part.get(wb) == wa or (part.get(wa) is not None and part.get(wa) == part.get(wb))):
            return True
        if not tok[a]:
            return not tok[b] and ways[a]["oid"] == ways[b]["oid"]
        return bool(tok[a] & tok[b]) or any(within(x, y) or within(y, x) for x in tok[a] for y in tok[b])
    lakes_ = pickle.load(open(os.path.join(ROOT, "work/lakes.pkl"), "rb")) if os.path.exists(os.path.join(ROOT, "work/lakes.pkl")) else []
    lake_geoms = [shapely.make_valid(shapely.Polygon(L["rings"][0], L["rings"][1:])) for L in lakes_]
    lake_tree = STRtree(lake_geoms) if lake_geoms else None
    head_tree = STRtree(shapely.points(np.array([w["c"][0] for w in ways])))
    begin, bridges, steps = {}, [], []
    widths = collections.defaultdict(list)
    for k, d, wmed, wmax in starts:
        widths[k].append((wmed, wmax))
        todo = [(k, d)]
        while todo:
            k, d = todo.pop()
            if k in begin and begin[k] <= d:
                continue
            begin[k] = d
            end = ways[k]["c"][-1]
            nxt = [j for j in heads.get(key(end), []) if j != k and same(k, j) and not ring[j]]
            if not nxt:                                     # (a gap: a head of the same river within BRIDGE_KM -- or FAR_BRIDGE_KM straight ahead)
                near = hx.query_ball_point(geo.to_xyz(end[None])[0], far_chord)
                cand = [j for j in near if j != k and j not in begin and same(k, j) and not ring[j]
                        and (np.linalg.norm(geo.to_xyz(ways[j]["c"][:1])[0] - geo.to_xyz(end[None])[0]) <= bridge_chord or ahead(k, ways[j]["c"][0]))]
                if cand:
                    j = min(cand, key=lambda j: np.linalg.norm(ways[j]["c"][0] - end))
                    nxt = [j]; bridges.append((k, j))
            if not nxt and lake_tree is not None:           # (into a lake: on from the head of the same river on its shore)
                for li in lake_tree.query(shapely.points(end), predicate="dwithin", distance=0.02).tolist():
                    cand = [j for j in head_tree.query(lake_geoms[li], predicate="dwithin", distance=0.02).tolist()
                            if j != k and same(k, j) and j not in begin]
                    if cand:
                        j = max(cand, key=lambda j: np.linalg.norm(ways[j]["c"][0] - end))   # (the outflow: the far end)
                        nxt.append(j); break
            todo += [(j, 0.0) for j in nxt]
            steps += [(k, j) for j in nxt]
    # and up to the source: the whole of every way reached, then the ways that end where one begins under the same
    # name (or over a gap under BRIDGE_KM), and theirs
    tails = collections.defaultdict(list)
    for k, w in enumerate(ways):
        tails[key(w["c"][-1])].append(k)
    tx = cKDTree(geo.to_xyz(np.array([w["c"][-1] for w in ways])))
    up, above = list(begin), 0
    for k in begin:
        begin[k] = 0.0
    while up:
        k = up.pop()
        head = ways[k]["c"][0]
        prev = [j for j in tails.get(key(head), []) if j != k and j not in begin and same(k, j) and not ring[j]]
        if not prev:
            cand = [j for j in tx.query_ball_point(geo.to_xyz(head[None])[0], bridge_chord) if j != k and j not in begin and same(k, j) and not ring[j]]
            if cand:
                j = min(cand, key=lambda j: np.linalg.norm(ways[j]["c"][-1] - head))
                prev = [j]; bridges.append((j, k))
        for j in prev:
            begin[j] = 0.0; steps.append((j, k)); up.append(j); above += 1
    log(above, "ways added above the wide stretches, up to the sources")
    # the pieces, and which belong together
    pieces = {k: (shapely.get_coordinates(shapely.ops.substring(lines[k], d, lines[k].length)) if d > 0 else ways[k]["c"]) for k, d in begin.items()}
    pieces = {k: c for k, c in pieces.items() if len(c) >= 2}   # (a stretch that begins at its way's very end)
    bridges = [(a, b) for a, b in bridges if a in pieces and b in pieces]
    parent = {k: k for k in pieces}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in steps:                                      # (one river: the ways the walk went through -- not every way
        if a in pieces and b in pieces:                     # that touches it: a tributary ends on its river)
            parent[find(b)] = find(a)
    rivers = collections.defaultdict(list)
    for k in pieces:
        rivers[find(k)].append(k)
    out = []
    for r, ks in rivers.items():
        segs = [pieces[k] for k in ks] + [np.array([ways[a]["c"][-1], ways[b]["c"][0]]) for a, b in bridges if find(a) == r]
        out.append((r, ks, segs, [w for k in ks for w in widths.get(k, [])]))
    return out


def natural_earth_names():
    """a river's English name from Natural Earth's river centerlines (1:10m, raw/ne/), for the rivers OSM has no
    Wikidata item on (the Nile, the Yangtze): the name of the one of its lines that most of the river's points lie
    within 5 km of -- if that is most of them"""
    fs = [f for f in json.load(open(os.path.join(ROOT, "raw/ne/ne_10m_rivers_lake_centerlines.geojson")))["features"]
          if (f["properties"].get("name_en") or f["properties"].get("name")) and f["geometry"]]
    geoms = [shapely.from_geojson(json.dumps(f["geometry"])) for f in fs]
    names = [f["properties"].get("name_en") or f["properties"]["name"] for f in fs]
    tree = STRtree(geoms)

    def name_of(segs):
        pts = np.vstack([shapely.get_coordinates(shapely.segmentize(shapely.linestrings(c), 0.05)) for c in segs if len(c) >= 2])
        pts = pts[:: max(1, len(pts) // 200)]
        (_, j), d = tree.query_nearest(shapely.points(pts), return_distance=True, all_matches=False)
        votes = collections.Counter(names[i] for i, dd in zip(j.tolist(), d.tolist()) if dd < 0.05)
        best = votes.most_common(1)
        return best[0][0] if best and best[0][1] >= 0.5 * len(pts) else None
    return name_of


def rivers(con):
    path = os.path.join(ROOT, "work/river_runs.pkl")          # (the measured stretches: the long part, kept)
    if os.path.exists(path):
        by = pickle.load(open(path, "rb"))
    else:
        lines = widths(con)
        # each river's wide stretches (by name and Wikidata id: the same river's OSM ways)
        by = collections.defaultdict(list)
        for (oid, part), L in lines.items():
            for a, b, wmed, wmax in runs(L):
                by[(L["name"], L["wikidata"]) if (L["name"] or L["wikidata"]) else ("", f"{oid}/{part}")].append((L["c"][a:b].copy(), wmed, wmax))
        del lines
        by = dict(by)
        pickle.dump(by, open(path, "wb"))
    log(sum(len(v) for v in by.values()), "wide stretches of", len(by), "rivers")
    ways = collect_ways(by)
    log(f"{len(ways):,} ways of those rivers")
    ne_name = natural_earth_names()
    def weigh(ks, f):                                       # (a property's most common value, by length)
        c = collections.Counter()
        for k in ks:
            if f(ways[k]):
                c[f(ways[k])] += ways[k]["length_km"]
        return c.most_common(1)
    def weigh_all(ks, f):
        c = collections.Counter()
        for k in ks:
            if f(ways[k]):
                c[f(ways[k])] += ways[k]["length_km"]
        return c.most_common()
    def english(ks, segs):
        """the English name that covers most of it -- one from Wikidata before OSM's own; else Natural Earth's, if its
        river runs along this one -> ([(name, weight)], from Natural Earth?)"""
        name = weigh(ks, lambda w: w["name"] if w.get("name_local") or w.get("wikidata") else None)   # (an item's own name too)
        if name:
            return name, False
        ne, own = ne_name(segs), weigh(ks, lambda w: w["name"])
        if ne and own and _re.search(r"(?<!\w)" + _re.escape(ne.lower()) + r"(?!\w)", own[0][0].lower()):
            return own, False                               # (OSM's own name says it in full: "Peace River", not Natural Earth's "Peace")
        return ([(ne, 0)], True) if ne else (own, False)
    rivs = [(rid, ks, segs, ws, *english(ks, segs)) for rid, ks, segs, ws in track(by, ways)]
    # pieces that meet end to end under the same English name are one river: a border where the ways share no name
    # (the Danube's Hungarian "Duna" and Serbian "Дунав", with no Wikidata item on either). A tributary's name is not
    # its river's. (The walk itself goes on through a name change where the items say it is one river.)
    parent = list(range(len(rivs)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    at = collections.defaultdict(list)
    for i, r in enumerate(rivs):
        if r[4]:
            for c in r[2]:
                for p in (c[0], c[-1]):
                    at[(int(geo.key(p)), r[4][0][0])].append(i)
    for ids in at.values():
        for i in ids[1:]:
            parent[find(i)] = find(ids[0])
    groups = collections.defaultdict(list)
    for i in range(len(rivs)):
        groups[find(i)].append(i)
    joined = len(rivs) - len(groups)
    feats, short, from_ne = [], 0, 0
    for g in groups.values():
        rid = rivs[g[0]][0]
        ks = [k for i in g for k in rivs[i][1]]; segs = [c for i in g for c in rivs[i][2]]; ws = [w for i in g for w in rivs[i][3]]
        name, ne = max(((rivs[i][4], rivs[i][5]) for i in g), key=lambda x: sum(v for _, v in x[0]) if x[0] else -1)
        total = sum(geo.length_km(c) for c in segs)
        if total < MIN_RIVER_KM:
            short += 1
            continue
        from_ne += ne
        local = weigh(ks, lambda w: w["osm_name"])
        # (its item: the one of its ways' items whose English label is its name -- a river's, not a section's)
        wds = weigh_all(ks, lambda w: w["wikidata"])
        en_of = wdnames.english([q for q, _ in wds])
        wd = [x for x in wds if name and en_of.get(x[0]) == name[0][0]][:1]   # (else found by its name: name_rivers)
        wm = float(np.median([w for w, _ in ws])) if ws else 0.0
        wx = float(max(w for _, w in ws)) if ws else 0.0
        props = {"name": name[0][0] if name else None, "name_local": local[0][0] if local and name and local[0][0] != name[0][0] else None,
                 "wikidata": wd[0][0] if wd and str(wd[0][0]).startswith("Q") else None, "river": f"r{rid}",
                 "width_m": round(wm), "width_max_m": round(wx), "river_km": round(total)}
        merged = shapely.line_merge(shapely.multilinestrings([shapely.linestrings(c) for c in segs]), directed=True)
        for g in shapely.get_parts(merged):
            c = shapely.get_coordinates(g)
            c = c[geo.simplify(geo.to_xyz(c), config.EPS_KM)]
            feats.append({"c": c, **props, "length_km": round(geo.length_km(c), 1)})
    log(f"{len(set(f['river'] for f in feats))} rivers of {MIN_RIVER_KM:.0f} km or more ({short} shorter left out; {from_ne} named by Natural Earth;",
        f"{joined} pieces joined to their river by name)")
    arcs = [f["c"] for f in feats]
    topo = {"type": "Topology", "bbox": [-180, -90, 180, 90],
            "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
            "objects": {"rivers": {"type": "GeometryCollection", "geometries": [
                {"type": "LineString", "arcs": [i], "properties": {k: v for k, v in f.items() if k != "c" and v is not None}} for i, f in enumerate(feats)]}},
            "arcs": quantize(arcs)}
    path = os.path.join(ROOT, "full/rivers.tracked.topo.json")
    json.dump(topo, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    log(f"{path}: {len(feats)} river lines, {sum(len(a) for a in arcs):,} points, {sum(f['length_km'] for f in feats):,.0f} km, {os.path.getsize(path) / 2**20:.1f} MB")


import re as _re


def name_rivers():
    """full/rivers.tracked.topo.json's rivers by their English names, and by their names in the official language of each country
    they flow through (in that order; its Wikidata item's labels -- else OSM's own name): `names_local`"""
    from points import Where
    from export_geojson import decode
    path = os.path.join(ROOT, "full/rivers.tracked.topo.json")
    topo = json.load(open(path))
    geoms = topo["objects"]["rivers"]["geometries"]
    props = [g["properties"] for g in geoms]
    arcs = decode(topo)
    samples = [arcs[g["arcs"][0]][np.linspace(0, len(arcs[g["arcs"][0]]) - 1, min(20, len(arcs[g["arcs"][0]]))).astype(int)] for g in geoms]
    wdnames.rename([p for p in props if "name_local" not in p])
    langs = wdnames.official_languages()
    first = {}
    for p in props:
        first.setdefault(p.get("river"), p)
    # a river without an item (none of its ways has one): the Wikidata river of its English name that has its place
    # within ~200 km of it (the best known, if several), or a famous one of that name that has no place
    pts = collections.defaultdict(list)
    for g, smp in zip(geoms, samples):
        pts[g["properties"].get("river")].append(smp)
    lost = [rid for rid, p in first.items() if not p.get("wikidata") and p.get("name")]
    variants = lambda n: {n, n + " River", n[:-6] if n.endswith(" River") else n}   # (Wikidata's "Mekong River")
    found = wdnames.items_named(sorted({v for r in lost for v in variants(first[r]["name"])}), "Q4022")
    got_items = 0
    for rid in lost:
        P = np.vstack(pts[rid])
        cands = [c for v in variants(first[rid]["name"]) for c in found.get(v, [])]
        near = [(n, q) for q, x, y, n in cands if x is not None and float(np.hypot(*(P - (x, y)).T).min()) < 2.0]
        # (of those near it, the one most Wikipedias write about; with none near, a famous one with no place given --
        # the Mekong's and the Yangtze's items have none)
        # (a long river's item may have its source as its place, far above where the river is wide: the Mekong's,
        # in Tibet -- a famous one within 15 degrees)
        far = [(n, q) for q, x, y, n in cands if x is not None and n >= 50 and (first[rid].get("river_km") or 0) >= 500
               and float(np.hypot(*(P - (x, y)).T).min()) < 15.0]
        best = max(near, default=None) or max(far, default=None) or max(((n, q) for q, x, y, n in cands if x is None and n >= 30), default=(None, None))
        if best[1]:
            for p in props:
                if p.get("river") == rid:
                    p["wikidata"] = best[1]
            got_items += 1
    log(got_items, "of", len(lost), "rivers without an item found theirs by name and place")
    # one river per Wikidata item: its pieces the walk could not connect (a gap over 10 km, a side arm from its own
    # wide stretch) go by the id of its longest, with their lengths added up
    by_item = collections.defaultdict(dict)
    for p in props:
        if p.get("wikidata"):
            by_item[p["wikidata"]][p["river"]] = p.get("river_km") or 0
    merged = 0
    for q, rs in by_item.items():
        if len(rs) > 1:
            rid, total = max(rs, key=rs.get), sum(rs.values())
            for p in props:
                if p.get("wikidata") == q:
                    p["river"], p["river_km"] = rid, round(total)
            merged += len(rs) - 1
    log(merged, "rivers joined to their item's")
    # a river with an item is called by the item's English name where its own is only part of it: "St. Lawrence River",
    # "Peace River", not Natural Earth's "St. Lawrence", "Peace"
    en = wdnames.english(sorted({p["wikidata"] for p in props if p.get("wikidata")}))
    full = 0
    for p in props:
        e = en.get(p.get("wikidata"))
        if e and p.get("name") and e != p["name"] and _re.search(r"(?<!\w)" + _re.escape(p["name"].lower()) + r"(?!\w)", e.lower()):
            p["name"] = e; full += 1
    log(full, "river lines named in full by their item")
    where = Where()
    allp = np.vstack(samples)
    cc, _ = where(allp[:, 0], allp[:, 1])
    del where
    countries, at = collections.defaultdict(list), 0                   # river -> its countries, in the order met
    for g, smp in zip(geoms, samples):
        rid = g["properties"].get("river")
        for c in cc[at:at + len(smp)]:
            if c and c not in countries[rid]:
                countries[rid].append(c)
        at += len(smp)
    first = {}
    for p in props:
        first.setdefault(p.get("river"), p)
    want = collections.defaultdict(set)
    for rid, p in first.items():
        for c in countries.get(rid, []):
            if p.get("wikidata") and langs.get(c):
                want[langs[c][0]].add(p["wikidata"])
    got = {l: wdnames.labels(sorted(q), l) for l, q in want.items()}
    names = {}
    for rid, p in first.items():
        ns = []
        for c in countries.get(rid, []):
            n = got.get(langs.get(c, [None])[0], {}).get(p.get("wikidata")) if p.get("wikidata") and langs.get(c) else None
            if n and n != p.get("name") and n not in ns:
                ns.append(n)
        if not ns and p.get("name_local") and p["name_local"] != p.get("name"):
            # (no item: OSM's own name -- on a border river often in both languages, "Dunărea - Дунав": each)
            ns = [x for x in _re.split(r"\s*[/;]\s*|\s+-\s+", p["name_local"]) if x and x != p.get("name")]
        names[rid] = ns
    for p in props:
        p.pop("name_local", None)
        if names.get(p.get("river")):
            p["names_local"] = names[p.get("river")]
    # and which to keep: a river with a name, that is big -- among the BIG longest, or the BIG widest -- or that some
    # Wikipedia has an article on (out go the obscure named flows that are wide somewhere)
    wp = wdnames.wikipedias(sorted({p["wikidata"] for p in first.values() if p.get("wikidata")}))
    by_len = sorted(first, key=lambda r: -(first[r].get("river_km") or 0))[:BIG]
    by_width = sorted(first, key=lambda r: -(first[r].get("width_max_m") or 0))[:BIG]
    keep = {r for r, p in first.items() if p.get("name") and (r in by_len or r in by_width or wp.get(p.get("wikidata"), 0) > 0)}
    for p in props:
        p["wikipedias"] = wp.get(p.get("wikidata")) or None
    gone = [g for g in geoms if g["properties"].get("river") not in keep]
    topo["objects"]["rivers"]["geometries"] = [g for g in geoms if g["properties"].get("river") in keep]
    used = sorted({g["arcs"][0] for g in topo["objects"]["rivers"]["geometries"]})
    renum = {a: i for i, a in enumerate(used)}
    topo["arcs"] = [topo["arcs"][a] for a in used]
    for g in topo["objects"]["rivers"]["geometries"]:
        g["arcs"] = [renum[g["arcs"][0]]]
    json.dump(topo, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    log(path, "named:", sum(1 for v in names.values() if v), "rivers with local names;", len(keep), "of", len(first), "rivers kept",
        f"({len(first) - len(keep)} unnamed, small and unknown to Wikipedia: {len(gone)} lines), {os.path.getsize(path) / 2**20:.1f} MB")


def main():
    if "names" in sys.argv[1:]:
        return name_rivers()
    con = duckdb.connect()
    con.execute(f"""LOAD spatial; SET memory_limit='900MB'; SET threads=1; SET preserve_insertion_order=false;
                    SET temp_directory='{os.path.join(ROOT, "work", "duck.tmp")}'""")
    os.makedirs(os.path.join(ROOT, "full"), exist_ok=True)   # (the full-detail layers: not committed -- the map loads data/lite/)
    if "rivers" not in sys.argv[1:]:
        lakes(con)
    if "lakes" not in sys.argv[1:]:
        rivers(con)
        name_rivers()


if __name__ == "__main__":
    main()
