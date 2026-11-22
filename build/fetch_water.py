"""The rivers and the big lakes out of Overture's water (OSM's waterways and water areas), read straight from the
public release: only the columns and rows wanted, streamed to one local file.

    .venv/bin/python build/fetch_water.py         # -> raw/water.parquet (~ a few GB; reads ~20 GB over the network)

Kept: every river centerline (waterway=river) and every river AREA (water=river, the old riverbank) -- the areas are
how wide a river is, which OSM rarely says in a tag -- and the lakes and reservoirs whose bounding box is 30 km2 or
more (their true area is measured later, build/water.py).

And raw/water_more.parquet (more(), after a first build): the other big water areas that may be lagoons behind the
map's coast -- OSM's `natural=water` without a `water=*` Overture knows (its subtype "water": the Dniester Liman, the
Tuzly lagoons) and its bays ("physical": the Berezan Liman) --; build/water.py takes those that lie on the map's land
(OSM's coast runs across their mouth) as lakes.
"""
import os, sys, time
import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RELEASE = "2026-09-23.1"
SRC = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=base/type=water/*.parquet"
OUT = os.path.join(ROOT, "raw", "water.parquet")
MORE = os.path.join(ROOT, "raw", "water_more.parquet")
BIG = "(bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin) * cos(radians((bbox.ymin + bbox.ymax) / 2)) * 12321 >= 30"


def connect(threads=4):
    con = duckdb.connect()
    os.makedirs(os.path.join(ROOT, "work", "duck.tmp"), exist_ok=True)
    con.execute(f"""INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';
                    SET memory_limit='1500MB'; SET threads={threads}; SET preserve_insertion_order=false;
                    SET temp_directory='{os.path.join(ROOT, "work", "duck.tmp")}';""")
    return con


def more():
    """raw/water_more.parquet, in two steps, as the geometry is nearly all of the release's 28 GB: (1) the light
    columns of every big water area of the other subtypes (raw/water_more_index/, a file per part, ~6 min); (2) the
    geometry of only those that can be a lagoon behind the map's coast -- a plain water area (or a tidal channel) or a
    bay, its box mostly on the map's land (full/world.topo.json: so after a first build) and at its coast, not on a
    lake already kept (work/lakes.pkl) -- read by row number (~1,100 row groups, ~10 GB, ~40 min)."""
    if os.path.exists(MORE):
        print("have", MORE); return
    import re, pickle, json, urllib.request, collections
    import numpy as np, shapely
    from concurrent.futures import ThreadPoolExecutor
    from export_geojson import decode, ring
    t0 = time.time()
    keys = re.findall(r"<Key>([^<]*\.parquet)</Key>", urllib.request.urlopen(
        f"https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/?list-type=2&prefix=release/{RELEASE}/theme=base/type=water/").read().decode())
    idx = os.path.join(ROOT, "raw", "water_more_index")
    os.makedirs(idx, exist_ok=True)

    def light(k):
        out = os.path.join(idx, os.path.basename(k))
        if not os.path.exists(out):
            connect().execute(f"""COPY (SELECT '{k}' AS key, file_row_number AS rn, subtype, class, bbox
                FROM read_parquet('s3://overturemaps-us-west-2/{k}', file_row_number=true)
                WHERE subtype IN ('water', 'physical') AND {BIG}) TO '{out}.part' (FORMAT parquet)""")
            os.replace(out + ".part", out)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(light, keys))
    rows = duckdb.connect().execute(f"""SELECT key, rn, bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax FROM '{idx}/*.parquet'
        WHERE (subtype = 'water' AND class IN ('water', 'tidal_channel')) OR (subtype = 'physical' AND class = 'bay')""").fetchall()
    print(len(rows), "big water areas of the other subtypes", round(time.time() - t0), "s", flush=True)
    # (2) which: the box at least MIN_LAKE_KM2, mostly on the land, by the coast, not on a lake
    w = json.load(open(os.path.join(ROOT, "full/world.topo.json"))); arcs = decode(w)
    land = [shapely.Polygon(ring(arcs, p[0]), [ring(arcs, h) for h in p[1:]]) for k in ("continents", "islands")
            for g in w["objects"][k]["geometries"] for p in ([g["arcs"]] if g["type"] == "Polygon" else g["arcs"])]
    land_tree = shapely.STRtree(land)
    lakes = [shapely.Polygon(L["rings"][0], L["rings"][1:]) for L in pickle.load(open(os.path.join(ROOT, "work/lakes.pkl"), "rb")) if not L.get("lagoon")]
    lake_tree = shapely.STRtree(lakes)
    coast_tree = shapely.STRtree([shapely.LineString(arcs[i]) for i in sorted({i if i >= 0 else ~i for line in w["objects"]["coastline"]["geometries"][0]["arcs"] for i in line})])
    g = np.linspace(0.1, 0.9, 6)
    want = collections.defaultdict(list)
    for k, rn, x0, y0, x1, y1 in rows:
        if (x1 - x0) * (y1 - y0) * np.cos(np.radians((y0 + y1) / 2)) * 12321 < 45:
            continue
        if not len(coast_tree.query(shapely.box(x0 - 0.02, y0 - 0.02, x1 + 0.02, y1 + 0.02), predicate="intersects")):
            continue
        X, Y = np.meshgrid(x0 + g * (x1 - x0), y0 + g * (y1 - y0)); P = shapely.points(X.ravel(), Y.ravel())
        on, lk = np.zeros(len(P), bool), np.zeros(len(P), bool)
        on[land_tree.query(P, predicate="intersects")[0]] = True
        lk[lake_tree.query(P, predicate="intersects")[0]] = True
        if on.mean() >= 0.4 and (lk & on).sum() < 0.5 * on.sum():
            want[k].append(rn)
    print(sum(map(len, want.values())), "of them may be lagoons", flush=True)
    part = os.path.join(ROOT, "raw", "water_more_parts")
    os.makedirs(part, exist_ok=True)

    def heavy(k):
        out = os.path.join(part, os.path.basename(k))
        if not os.path.exists(out):
            connect().execute(f"""COPY (SELECT id, names.primary AS name, subtype, class, wikidata, is_salt, bbox, geometry
                FROM read_parquet('s3://overturemaps-us-west-2/{k}', file_row_number=true)
                WHERE file_row_number IN ({",".join(map(str, want[k]))})) TO '{out}.part' (FORMAT parquet)""")
            os.replace(out + ".part", out)
        print(" ", os.path.basename(k)[:10], len(want[k]), round(time.time() - t0), "s", flush=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(heavy, sorted(want)))
    duckdb.connect().execute(f"COPY (SELECT * FROM '{part}/*.parquet') TO '{MORE}' (FORMAT parquet, COMPRESSION zstd)")
    print(MORE, os.path.getsize(MORE) // 2**20, "MB in", round(time.time() - t0), "s")


def main():
    more()
    if os.path.exists(OUT):
        print("have", OUT); return
    con = connect()
    t0 = time.time()
    con.execute(f"""COPY (
      SELECT id, names.primary AS name, subtype, class, wikidata, is_intermittent, bbox, geometry
      FROM read_parquet('{SRC}')
      WHERE (subtype = 'river' AND class = 'river' AND ST_GeometryType(geometry) IN ('LINESTRING', 'MULTILINESTRING', 'POLYGON', 'MULTIPOLYGON'))
         OR (subtype IN ('lake', 'reservoir') AND ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
             AND {BIG})
    ) TO '{OUT}.part' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)""")
    os.replace(OUT + ".part", OUT)
    print(OUT, os.path.getsize(OUT) // 2**20, "MB in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
