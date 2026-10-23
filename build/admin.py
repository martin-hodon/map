"""The world's administrative lines and units, for build/history.py's regions: Overture's land boundaries of countries,
their first-level divisions (regions: states, provinces) and second-level ones (counties: districts, departements,
Kreise) -- every country's, not only config.REGION_COUNTRIES' -- and the units' names.

    lines()   -> [coords]: each boundary simplified to KM on the sphere with every point where a boundary ends kept,
              so that two boundaries on one path (a county's along its region's, a region's along the country's) stay
              on one path -- build/bio.borders then takes each segment once. Kept in work/admin_lines.pkl.
    units()   -> {"region": [(name, country, geometry)], "county": [...]}, simplified to UNIT_DEG (to tell which unit a
              point is in). Kept in work/admin_units.pkl.
"""
import os, sys, pickle, collections
import numpy as np, shapely, duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo
from bio import log

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BOUNDARY = os.path.join(ROOT, "raw/divisions/division_boundary-*.parquet")
AREA = os.path.join(ROOT, "raw/divisions/division_area-*.parquet")
KM = 0.5                    # the boundaries' detail (the map's own: config.EPS_KM)
UNIT_DEG = 0.005            # the units' outlines, only to look a point up in


def connect():
    con = duckdb.connect()
    con.execute("LOAD spatial; SET memory_limit='800MB'; SET threads=2")
    return con


def parts(wkb):
    g = shapely.from_wkb(bytes(wkb))
    for p in shapely.get_parts(g):
        c = shapely.get_coordinates(p)
        c = c[np.r_[True, np.any(c[1:] != c[:-1], axis=1)]]   # (OSM's lines repeat a point now and then)
        if len(c) >= 2:
            yield c


def lines():
    cache = os.path.join(ROOT, "work/admin_lines.pkl")
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    con = connect()
    q = f"SELECT ST_AsWKB(geometry) FROM '{BOUNDARY}' WHERE class = 'land' AND subtype IN ('country', 'region', 'county')"
    # (1) where boundaries end: a junction of three units, or a boundary meeting the coast
    ends, n, pts = [], 0, 0
    cur = con.execute(q)
    while rows := cur.fetchmany(500):
        for (w,) in rows:
            for c in parts(w):
                ends.append(geo.key(c[[0, -1]])); n += 1; pts += len(c)
    ends = np.unique(np.concatenate(ends))
    log(n, "boundaries,", f"{pts:,} points,", len(ends), "ends")
    # (2) each simplified with those points fixed: a stretch two boundaries share is cut the same in both
    out, after = [], 0
    cur = con.execute(q)
    while rows := cur.fetchmany(500):
        for (w,) in rows:
            for c in parts(w):
                k = geo.key(c)
                fixed = np.flatnonzero(ends[np.minimum(np.searchsorted(ends, k), len(ends) - 1)] == k)
                c = c[geo.simplify(geo.to_xyz(c), KM, fixed)]
                out.append(c); after += len(c)
    log(len(out), "boundaries,", f"{after:,} points at {KM} km")
    pickle.dump(out, open(cache, "wb"))
    return out


def units():
    cache = os.path.join(ROOT, "work/admin_units.pkl")
    if os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    con = connect()
    out = collections.defaultdict(list)
    cur = con.execute(f"""SELECT subtype, country, names.primary, names.common['en'], ST_AsWKB(geometry) FROM '{AREA}'
                          WHERE class = 'land' AND subtype IN ('country', 'region', 'county')""")
    while rows := cur.fetchmany(200):
        for sub, cc, name, en, w in rows:
            if isinstance(en, list):
                en = en[0] if en else None
            g = shapely.make_valid(shapely.simplify(shapely.from_wkb(bytes(w)), UNIT_DEG))
            if not g.is_empty:
                out[sub].append((en or name, cc, g))
    log({k: len(v) for k, v in out.items()}, "units")
    out = dict(out)
    pickle.dump(out, open(cache, "wb"))
    return out


if __name__ == "__main__":
    ls = lines()
    print(len(ls), sum(len(c) for c in ls))
    us = units()
