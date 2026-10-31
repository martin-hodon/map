"""THE FIRST-CLASS ROADS: what is one class below a motorway (OSM's trunk: raw/roads/, build/fetch_roads.py) as
single lines, as build/roadnet.py makes the motorways -> full/roads.topo.json (object: roads). build/lite.py and
build/small.py then make data/roads.txt and its copies.

    .venv/bin/python build/roads.py

Three times the motorways' lines would not fit into memory at once, so it goes by CELL (CELL_DEG degrees square, each line in the cell of
its first point; the cells side by side only by the ends they share: a road along a cell's edge may stay two carriageways for a stretch):

  * the ways of one road number (or name), joined end to end;
  * a road's carriageways one line, as roadnet.collapse does: the most important first -- the motorways there are, which
    are not written again, so a trunk road beside a motorway is the motorway, then the trunk roads, each the longest first;
  * ends carried onto what they meet (roadnet.gaps, joins), every line cut where another ends, each arc at EPS_KM.

Then, of all the cells' arcs: what is connected to under MIN_NET_KM goes (a town's main street), each arc's rank by the stroke it is on
(roadnet.strokes), and a row for each connected run of one road's arcs of one tier: to be found as one, and few enough to name them all.
"""
import os, sys, json, time, glob, pickle, shutil, collections, multiprocessing
import numpy as np, shapely, duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, geo
from export_geojson import decode, ring
from roadnet import turns, collapse, gaps, joins, apply_inserts, strokes, refs, km

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw", "roads")
CELLS = os.path.join(ROOT, "raw", "roads_cells")
DONE = os.path.join(ROOT, "raw", "roads_done")
OUT = os.environ.get("ROADS_OUT", os.path.join(ROOT, "full", "roads.topo.json"))
MOTORWAYS = os.path.join(ROOT, "full", "transport.topo.json")
CELL_DEG = 15
JOIN_KM, GAP_KM = 1.0, 3.0
EPS_KM = 1.0
MIN_LINE_KM = 0.5    # (a line of no name this short, on its own: what is left of a junction)
MIN_NET_KM = 25.0
TIERS = (300, 80)    # a stroke's km for the first and the second tier
WORKERS = 2
T0 = time.time()
Q = config.QUANT_DEG


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def partition():
    """the raw lines, a parquet file a cell"""
    if os.path.exists(CELLS):
        return
    con = duckdb.connect()
    con.execute(f"LOAD spatial; SET memory_limit='2GB'; SET threads=4; SET preserve_insertion_order=false;")
    con.execute(f"""COPY (
      WITH r AS (SELECT class, name, ref, ST_GeomFromWKB(wkb) AS g, wkb FROM read_parquet('{RAW}/*.parquet') WHERE class = 'trunk')
      SELECT floor((ST_X(ST_StartPoint(g)) + 180) / {CELL_DEG})::INT AS cx, floor((ST_Y(ST_StartPoint(g)) + 90) / {CELL_DEG})::INT AS cy, class, name, ref, wkb FROM r
    ) TO '{CELLS}.tmp' (FORMAT parquet, COMPRESSION zstd, PARTITION_BY (cx, cy))""")
    os.replace(CELLS + ".tmp", CELLS)
    log("cells:", len(glob.glob(CELLS + "/*/*")))


def context():
    """the motorways, each arc and its box"""
    t = json.load(open(MOTORWAYS))
    arcs = decode(t)
    lines = [ring(arcs, g["arcs"]) for g in t["objects"]["motorways"]["geometries"]]
    box = np.array([(c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()) for c in lines])
    return lines, box


def merged_lines(rows):
    """the ways of one label joined -> [(lon/lat, properties)]"""
    by = collections.defaultdict(list)
    for cl, name, ref, g in rows:
        by[ref or name or ""].append((cl, name, ref, g))
    out = []
    for label, part in by.items():
        lens = shapely.length(np.array([x[3] for x in part], dtype=object))
        cls, names, rf = collections.Counter(), collections.Counter(), collections.Counter()
        for (cl, name, ref, _), l in zip(part, lens):
            cls[cl] += l
            if name: names[name] += l
            if ref: rf[ref] += l
        p = {"class": cls.most_common(1)[0][0]}
        if rf: p["ref"] = rf.most_common(1)[0][0]
        if names: p["name"] = names.most_common(1)[0][0]
        m = shapely.line_merge(shapely.multilinestrings([x[3] for x in part]))
        for g in shapely.get_parts(m):
            c = shapely.get_coordinates(g)
            if len(c) >= 2 and (label or km(c) >= MIN_LINE_KM):
                out.append((c, p))
    return out


LINES, BOX = None, None


def do_cell(path):
    name = os.path.basename(path) + "_" + os.path.basename(os.path.dirname(path))
    done = os.path.join(DONE, name + ".pkl")
    if os.path.exists(done):
        return
    con = duckdb.connect()
    rows = con.execute(f"SELECT class, name, ref, wkb FROM read_parquet('{path}/*.parquet')").fetchall()
    con.close()
    cx = int(os.path.basename(os.path.dirname(path)).split("=")[1]); cy = int(os.path.basename(path).split("=")[1])
    w, s = cx * CELL_DEG - 180, cy * CELL_DEG - 90
    geoms = shapely.from_wkb([bytes(r[3]) for r in rows])
    lines = merged_lines([(r[0], r[1], r[2], g) for r, g in zip(rows, geoms)])
    del rows, geoms
    m = 2.0
    near = np.flatnonzero((BOX[:, 0] <= w + CELL_DEG + m) & (BOX[:, 2] >= w - m) & (BOX[:, 1] <= s + CELL_DEG + m) & (BOX[:, 3] >= s - m))
    ctx = [(LINES[i], {"_ctx": 1}) for i in near]
    roads = [(x, p) for c, p in lines for x in turns(c)]
    roads.sort(key=lambda x: (x[1]["class"] != "trunk", -km(x[0])))
    kept, inserts, idx, attached = collapse(ctx + roads, True, JOIN_KM)
    ext = joins(kept, inserts, idx, attached, JOIN_KM, gaps(kept, attached, GAP_KM))
    kept = apply_inserts(kept, inserts, ext)
    del idx
    grid = [np.column_stack((np.round((c[:, 0] + 180) / Q), np.round((c[:, 1] + 90) / Q))).astype(np.int32) for c, _ in kept]
    grid = [g[np.r_[True, np.any(g[1:] != g[:-1], axis=1)]] for g in grid]
    junction = {tuple(x) for g in grid if len(g) > 1 for x in (g[0], g[-1])}
    arcs, pieces = [], []
    for g, (c, p) in zip(grid, kept):
        if len(g) < 2 or p.get("_ctx"):
            continue
        cuts = [0] + [v for v in range(1, len(g) - 1) if tuple(g[v]) in junction] + [len(g) - 1]
        ids = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            f = g[a:b + 1]
            ids.append(len(arcs)); arcs.append(f[geo.simplify(geo.to_xyz(f * Q - [180, 90]), EPS_KM)])
        pieces.append((ids, p))
    pickle.dump((arcs, pieces), open(done + ".tmp", "wb"), protocol=4)
    os.replace(done + ".tmp", done)
    print(f"[{time.time() - T0:6.0f}s] {name}: {len(lines):,} lines -> {len(pieces):,}, {len(arcs):,} arcs, {sum(map(len, arcs)):,} points", flush=True)


def chained(ids, arcs):
    """a row's arcs {arc: its number in the file} as few lines as go end to end (each line a box in the page's R-tree) -> [[signed numbers]]"""
    at = collections.defaultdict(list)
    for a in ids:
        at[tuple(arcs[a][0])].append((a, False)); at[tuple(arcs[a][-1])].append((a, True))
    used, lines = set(), []
    def walk(a, back):
        line = []
        while True:
            used.add(a); line.append(~ids[a] if back else ids[a])
            node = tuple(arcs[a][0] if back else arcs[a][-1])
            on = [x for x in at[node] if x[0] not in used]
            if len(at[node]) != 2 or not on:
                return line
            a, back = on[0]
    for node, here in at.items():                            # (from the ends and the forks first, then what is left: rings)
        if len(here) != 2:
            for a, back in here:
                if a not in used:
                    lines.append(walk(a, back))
    for a in ids:
        if a not in used:
            lines.append(walk(a, False))
    return lines


def main():
    global LINES, BOX
    partition()
    os.makedirs(DONE, exist_ok=True)
    LINES, BOX = context()
    log(f"{len(LINES):,} motorway lines")
    # (a cell is a folder: DuckDB may write it as several files)
    cells = sorted(glob.glob(CELLS + "/*/*"), key=lambda d: sum(map(os.path.getsize, glob.glob(d + "/*.parquet"))))
    with multiprocessing.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool:
        for _ in pool.imap_unordered(do_cell, cells):
            pass
    LINES = BOX = None
    arcs, pieces = [], []
    for f in sorted(glob.glob(DONE + "/*.pkl")):
        a, ps = pickle.load(open(f, "rb"))
        n = len(arcs); arcs += a
        pieces += [([x + n for x in ids], p) for ids, p in ps]
    log(f"{len(pieces):,} lines, {len(arcs):,} arcs, {sum(map(len, arcs)):,} points")
    # the networks: what is connected, however little of it is one road
    parent = list(range(len(arcs)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    node = {}
    for a, g in enumerate(arcs):
        for x in (tuple(g[0]), tuple(g[-1])):
            if x in node:
                parent[find(a)] = find(node[x])
            else:
                node[x] = a
    ref = [None] * len(arcs)
    for ids, p in pieces:
        for a in ids:
            ref[a] = refs(p)
    stroke, length = strokes(arcs, ref)
    net = collections.Counter()
    for a in range(len(arcs)):
        net[find(a)] += length[a]
    dead = {a for a in range(len(arcs)) if net[find(a)] < MIN_NET_KM}
    log(f"{sum(length[a] for a in dead):,.0f} km in networks under {MIN_NET_KM} km left out, {sum(length) - sum(length[a] for a in dead):,.0f} km kept")
    tier = [1 if s >= TIERS[0] else 2 if s >= TIERS[1] else 3 for s in stroke]
    # a row: a road's arcs of one tier that are connected (a road of no name: a tier's that are)
    rows = collections.defaultdict(list)
    for ids, p in pieces:
        for a in ids:
            if a not in dead:
                rows[(p.get("ref") or p.get("name") or "", p["class"], tier[a])].append((a, p))
    geoms, out, tiers = [], [], collections.Counter()
    for (label, cl, t), got in rows.items():
        up = {a: a for a, _ in got}
        def root(x):
            while up[x] != x:
                up[x] = up[up[x]]; x = up[x]
            return x
        ends = {}
        for a, _ in got:
            for x in (tuple(arcs[a][0]), tuple(arcs[a][-1])):
                if x in ends:
                    up[root(a)] = root(ends[x])
                else:
                    ends[x] = a
        parts = collections.defaultdict(list)
        for a, p in got:
            parts[root(a)].append((a, p))
        for part in parts.values():
            p = part[0][1]
            ids = {}
            for a, _ in part:
                ids[a] = len(out); out.append(arcs[a]); tiers[t] += length[a]
            geoms.append({"type": "MultiLineString", "arcs": chained(ids, arcs), "properties": {k: p[k] for k in ("class", "ref", "name") if k in p} | {"tier": t}})
    log(f"{len(geoms):,} rows, {len(out):,} arcs, {sum(map(len, out)):,} points; by tier:", {k: round(tiers[k]) for k in sorted(tiers)})
    topo = {"type": "Topology", "bbox": [-180, -90, 180, 90], "transform": {"scale": [Q, Q], "translate": [-180, -90]},
            "objects": {"roads": {"type": "GeometryCollection", "geometries": geoms}},
            "arcs": [np.vstack((a[:1], np.diff(a, axis=0))).tolist() for a in out]}
    json.dump(topo, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    log(f"{OUT}: {os.path.getsize(OUT) / 2**20:.1f} MB")
    shutil.rmtree(CELLS); shutil.rmtree(DONE)


if __name__ == "__main__":
    main()
