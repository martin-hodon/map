"""The rivers and the big lakes out of Overture's water (OSM's waterways and water areas), read straight from the
public release: only the columns and rows wanted, streamed to one local file.

    .venv/bin/python build/fetch_water.py         # -> raw/water.parquet (~ a few GB; reads ~20 GB over the network)

Kept: every river centerline (waterway=river) and every river AREA (water=river, the old riverbank) -- the areas are
how wide a river is, which OSM rarely says in a tag -- and the lakes and reservoirs whose bounding box is 30 km2 or
more (their true area is measured later, build/water.py).
"""
import os, time
import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RELEASE = "2026-09-23.1"
SRC = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=base/type=water/*.parquet"
OUT = os.path.join(ROOT, "raw", "water.parquet")


def main():
    if os.path.exists(OUT):
        print("have", OUT); return
    con = duckdb.connect()
    os.makedirs(os.path.join(ROOT, "work", "duck.tmp"), exist_ok=True)
    con.execute(f"""INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';
                    SET memory_limit='1500MB'; SET threads=4; SET preserve_insertion_order=false;
                    SET temp_directory='{os.path.join(ROOT, "work", "duck.tmp")}';""")
    t0 = time.time()
    con.execute(f"""COPY (
      SELECT id, names.primary AS name, subtype, class, wikidata, is_intermittent, bbox, geometry
      FROM read_parquet('{SRC}')
      WHERE (subtype = 'river' AND class = 'river' AND ST_GeometryType(geometry) IN ('LINESTRING', 'MULTILINESTRING', 'POLYGON', 'MULTIPOLYGON'))
         OR (subtype IN ('lake', 'reservoir') AND ST_GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
             AND (bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin) * cos(radians((bbox.ymin + bbox.ymax) / 2)) * 12321 >= 30)
    ) TO '{OUT}.part' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)""")
    os.replace(OUT + ".part", OUT)
    print(OUT, os.path.getsize(OUT) // 2**20, "MB in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
