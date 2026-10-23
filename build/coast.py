"""STAGE 1 -- THE COAST: OSM's land polygons (osmdata.openstreetmap.de, the coastline assembled daily) read one at a
time, the islands under MIN_ISLAND_KM2 left out, every ring simplified on the sphere to FINE_KM -- with the vertices
where a border meets the coast kept exactly, so the borders can be joined to it later -- and every landmass kept a
valid polygon (OSM's own points kept round the spots where FINE_KM would make its rings cross), so it can be
cut into its countries.

    .venv/bin/python build/coast.py               # -> work/coast_fine.npz (~ 2 min per pass over 79M points)

A border's end (Overture's division boundaries, from OSM) is almost always one of the coastline's own nodes: those
are found by their exact coordinates. The few that are not are matched to the nearest coast vertex within SNAP_KM.
Every such candidate is kept in the fine rings; build/topology.py picks the one each border end joins.
"""
import os, re, sys, time
import duckdb, numpy as np, shapely
from scipy.spatial import cKDTree
from shapely import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LAND = "/vsizip/" + os.path.join(ROOT, "raw/land-polygons-complete-4326.zip") + "/land-polygons-complete-4326/land_polygons.shp"
BOUNDARY = os.path.join(ROOT, "raw/divisions/division_boundary-*.parquet")
OUT = os.path.join(ROOT, "work/coast_fine.npz")


def border_ends(con):
    """every end of every land boundary line (countries and regions), unique"""
    ends = []
    for (w,) in con.execute(f"SELECT ST_AsWKB(geometry) FROM '{BOUNDARY}' WHERE subtype IN ('country', 'region') AND class = 'land'").fetchall():
        g = shapely.from_wkb(w)
        for p in (g.geoms if g.geom_type == "MultiLineString" else [g]):
            c = shapely.get_coordinates(p)
            ends += [c[0], c[-1]]
    ends = np.array(ends)
    _, first = np.unique(geo.key(ends), return_index=True)
    return ends[np.sort(first)]


def crossing_spots(P, rc):
    """where a polygon's rings cross or touch: the new nodes when its rings are noded, and the spot GEOS reports"""
    spots = []
    m = re.search(r"\[([-\d.eE+]+) ([-\d.eE+]+)\]", shapely.is_valid_reason(P))
    if m:
        spots.append((float(m.group(1)), float(m.group(2))))
    noded = shapely.get_parts(shapely.node(shapely.multilinestrings([shapely.linestrings(c) for c in rc])))
    if len(noded):
        ends = np.vstack([shapely.get_coordinates(shapely.get_point(noded, 0)), shapely.get_coordinates(shapely.get_point(noded, -1))])
        new = ~np.isin(geo.key(ends), geo.key(np.vstack(rc)))
        spots += [tuple(p) for p in ends[new]]
    return np.array(spots).reshape(-1, 2)


def valid_keeps(rings):
    """[(ring coords, fixed vertices)] of one landmass -> the vertices each keeps at FINE_KM such that the polygon stays
    valid. Where simplifying would make its rings cross (a spit, a lagoon, a strait narrower than FINE_KM), the
    simplified segments at the crossing get back all of OSM's vertices between their ends -- only those, so a
    landmass of millions of points does not go back to all of them for one narrow spit. (Restoring a segment whole
    leaves the rest as simplified as it was: no need to simplify again.) -> (keeps, the tries it took)"""
    keeps = [geo.simplify(geo.to_xyz(c, np.float32), config.FINE_KM, fixed) for c, fixed in rings]
    for tries in range(20):
        rc = [c[k] for (c, _), k in zip(rings, keeps)]
        P = shapely.Polygon(rc[0], rc[1:])
        if shapely.is_valid(P):
            return keeps, tries
        spots = crossing_spots(P, rc)
        if not len(spots):
            break
        pts = shapely.buffer(shapely.points(spots), 1e-7)
        grew = False
        for i, (k, c) in enumerate(zip(keeps, rc)):
            segs = shapely.linestrings(np.stack((c[:-1], c[1:]), axis=1))
            _, hit = STRtree(segs).query(pts, predicate="intersects")
            back = [np.arange(int(k[j]) + 1, int(k[j + 1])) for j in np.unique(hit).tolist() if k[j + 1] - k[j] > 1]
            if back:
                keeps[i] = np.union1d(k, np.concatenate(back)); grew = True
        if not grew:
            break
    return [np.arange(len(c)) for c, _ in rings], 99       # (the last resort: all of OSM's points)


def main():
    t0 = time.time()
    con = duckdb.connect()
    con.execute("LOAD spatial; SET memory_limit='500MB'; SET threads=1")
    E = border_ends(con)
    Ek, Exyz = geo.key(E), geo.to_xyz(E)
    snap_chord = 2 * np.sin(max(config.SNAP_KM, config.LOOSE_KM) / geo.R_KM / 2)   # (topology.py chooses among them)
    print(len(E), "border ends", round(time.time() - t0), "s")

    coords, offsets, poly, hole, area = [], [0], [], [], []
    cand = []            # (end index, ring index, vertex index in the fine ring, km)
    kept = dropped = pts_in = finer = 0
    rel = con.execute(f"SELECT ST_AsWKB(geom) FROM ST_Read('{LAND}')")
    pid = -1
    while True:
        batch = rel.fetchmany(200)
        if not batch:
            break
        for bi in range(len(batch)):
            (w,), batch[bi] = batch[bi], None            # (each one let go of once read: a continent is 110 MB)
            pid += 1
            g = shapely.from_wkb(w)
            rings = []                                  # (coords, fixed vertices, border-end hits, area, is hole)
            coords_of = [shapely.get_coordinates(r) for r in [g.exterior, *g.interiors]]
            del g, w                                    # (a continent: its geometry is gone once its rings are read)
            for ri, c in enumerate(coords_of):
                pts_in += len(c)
                polar = c[:, 1].min() < -85             # the Antarctic ring wraps the pole: no area formula for it
                a = abs(geo.ring_area_km2(c)) if not polar else 1e7
                if a < (config.MIN_ISLAND_KM2 if ri == 0 else config.MIN_HOLE_KM2):
                    if ri == 0:
                        dropped += 1
                        break                           # (its holes go with it)
                    continue
                fixed = set(np.flatnonzero((np.abs(c[:, 0]) == 180) | (c[:, 1] <= -89.9999)).tolist())   # the antimeridian cut, the pole
                # the border ends on this ring: exactly on a vertex, or the nearest vertex within SNAP_KM
                x0, y0 = c.min(0) - .1; x1, y1 = c.max(0) + .1
                near = np.flatnonzero((E[:, 0] >= x0) & (E[:, 0] <= x1) & (E[:, 1] >= y0) & (E[:, 1] <= y1))
                hits = []
                if len(near):
                    # (only the vertices in the 0.1-degree cells round those ends are searched: a continent has millions)
                    cells = lambda p: (np.floor(p[:, 0] * 10).astype(np.int32) + 1810) * 2000 + np.floor(p[:, 1] * 10).astype(np.int32) + 910
                    ec = cells(E[near])
                    ec = np.unique((ec[:, None] + np.array([dx * 2000 + dy for dx in (-1, 0, 1) for dy in (-1, 0, 1)], np.int32)[None, :]).ravel())
                    cand_v = np.flatnonzero(np.isin(cells(c), ec))
                    if len(cand_v):
                        tree = cKDTree(geo.to_xyz(c[cand_v]))
                        d, j = tree.query(Exyz[near])
                        for e, dd, jj in zip(near.tolist(), d.tolist(), j.tolist()):
                            if dd <= snap_chord:
                                i = int(cand_v[jj])
                                i = i if i != len(c) - 1 else 0         # (the closing vertex is the first)
                                hits.append((e, i, float(dd * geo.R_KM)))
                                fixed.add(i)
                        del tree
                rings.append((c, sorted(fixed), hits, a, ri > 0))
            if not rings or rings[0][4]:
                continue
            # simplified -- and still a valid polygon (every later stage builds on these rings: a landmass that is not
            # valid cannot be cut into its countries)
            keeps, tries = valid_keeps([(c, fixed) for c, fixed, *_ in rings])
            finer += tries > 0
            for (c, fixed, hits, a, is_hole), keep in zip(rings, keeps):
                pos = {int(v): k for k, v in enumerate(keep)}
                r = len(poly)
                for e, i, d in hits:
                    cand.append((e, r, pos[i], d))
                coords.append(c[keep]); offsets.append(offsets[-1] + len(keep))
                poly.append(pid); hole.append(is_hole); area.append(a)
            kept += 1
        if pid % 100000 < 200:
            print(f"  {pid} polygons, {kept} kept, {dropped} dropped, {pts_in / 1e6:.1f}M points in, {offsets[-1] / 1e6:.2f}M out, {time.time() - t0:.0f} s", flush=True)
    np.savez_compressed(OUT, coords=np.concatenate(coords), offsets=np.array(offsets), poly=np.array(poly), hole=np.array(hole),
                        area=np.array(area), ends=E, cand=np.array(cand, dtype=float).reshape(-1, 4))
    print(f"coast: {kept} land polygons kept ({dropped} under {config.MIN_ISLAND_KM2} km2 left out), {len(poly)} rings, "
          f"{offsets[-1]:,} points at {config.FINE_KM} km (from {pts_in:,}); {len(cand)} border-end candidates; {finer} landmasses kept OSM's own points round a narrow spot to stay valid; {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
