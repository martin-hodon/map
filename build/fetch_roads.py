"""The raw lines of the first-class roads -- what is one class below a motorway: OSM's `highway=trunk`; `primary`, a level lower, is fetched and left out by build/roads.py
-- from Overture's transportation theme (its roads are OSM's;
ODbL). Overpass would take a day for these, a tile at a time.

    .venv/bin/python build/fetch_roads.py        # -> raw/roads.parquet (resumes: raw/roads/<part>.parquet)

A part of Overture's at a time, so a stop costs one part; only what build/roads.py reads, no slip roads, each line already at 200 m
(ST_Simplify: 0.002 degrees), so the file is small and no answer is ever all in memory.
"""
import os, sys, time, glob
import duckdb
from multiprocessing.pool import ThreadPool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
from config import OVERTURE_RELEASE
SRC = f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme=transportation/type=segment/*.parquet"
PARTS = os.path.join(ROOT, "raw", "roads")
OUT = os.path.join(ROOT, "raw", "roads.parquet")
PARALLEL = 4


def main():
    if os.path.exists(OUT):
        print("have", OUT); return
    os.makedirs(PARTS, exist_ok=True)
    con = duckdb.connect()
    con.execute("""INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';
                   SET memory_limit='1800MB'; SET threads=6; SET preserve_insertion_order=false;""")
    files = [r[0] for r in con.execute(f"SELECT file FROM glob('{SRC}') ORDER BY 1").fetchall()]
    t0 = time.time()
    done = [0]
    def fetch(job):                                          # (the time goes on the network: a few parts at once)
        n, f = job
        part = os.path.join(PARTS, f"{n:03d}.parquet")
        if not os.path.exists(part):
            con.cursor().execute(f"""COPY (
              SELECT class, names.primary AS name, routes[1].ref AS ref,
                     speed_limits[1].max_speed.value * CASE WHEN speed_limits[1].max_speed.unit = 'mph' THEN 1.609 ELSE 1 END AS speed,
                     ST_AsWKB(ST_Simplify(geometry, 0.002)) AS wkb
              FROM read_parquet('{f}') WHERE subtype = 'road' AND class IN ('trunk', 'primary') AND subclass IS DISTINCT FROM 'link'
            ) TO '{part}.tmp' (FORMAT parquet, COMPRESSION zstd)""")
            os.replace(part + ".tmp", part)
        done[0] += 1
        print(f"{done[0]}/{len(files)} parts, {time.time() - t0:.0f} s", flush=True)
    with ThreadPool(PARALLEL) as pool:
        for _ in pool.imap_unordered(fetch, list(enumerate(files))):
            pass
    con.execute(f"COPY (SELECT * FROM read_parquet('{PARTS}/*.parquet')) TO '{OUT}.part' (FORMAT parquet, COMPRESSION zstd)")
    os.replace(OUT + ".part", OUT)
    print(OUT, os.path.getsize(OUT) // 2**20, "MB in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
