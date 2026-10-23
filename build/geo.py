"""Geometry on the sphere, shared by every stage: points as unit vectors, lines simplified by their distance on the
globe (not in degrees), areas in square kilometres.

Why the sphere: the output is meant for any projection. Simplifying in degrees keeps three times too many points
in the Arctic (a degree of longitude is a third of its length there) and, worse, lets a border that follows a
parallel -- the 49th between the US and Canada -- lose every point between its ends: straight in degrees, but a
renderer that draws edges as great-circle arcs (d3, any globe) would bow it 90 km north. Measured on the sphere,
a line keeps exactly the points it needs to stay within the tolerance in every projection.
"""
import numpy as np

R_KM = 6371.0088          # mean Earth radius
DEG = np.pi / 180
CHUNK = 1 << 20           # simplify's distances are computed this many points at a time (bounded memory)


def to_xyz(lonlat, dtype=np.float64):
    """(n, 2) degrees -> (n, 3) unit vectors. float32 is plenty to simplify with (0.4 m on the globe) and half the
    memory: a continent's coast is tens of millions of points"""
    lon, lat = lonlat[:, 0] * DEG, lonlat[:, 1] * DEG
    c = np.cos(lat)
    return np.column_stack((c * np.cos(lon), c * np.sin(lon), np.sin(lat))).astype(dtype, copy=False)


def _seg_dist(P, A, B):
    """chord distance (unit sphere) of each point in P to the great-circle segment A-B"""
    A, B = A.astype(np.float64), B.astype(np.float64)
    n = np.cross(A, B)
    nn = np.linalg.norm(n)
    dA = np.linalg.norm(P - A, axis=1)
    if nn < 1e-14:                         # A and B coincide (a closed ring's ends): the distance to that point
        return dA
    n = n / nn
    d = np.abs(P @ n)                      # to the whole great circle
    # outside the segment's span (the point's foot beyond A or beyond B): to the nearer end instead
    beyond = ((P @ np.cross(n, A)) < 0) | ((P @ np.cross(B, n)) < 0)
    if beyond.any():
        d = np.where(beyond, np.minimum(dA, np.linalg.norm(P - B, axis=1)), d)
    return d


def simplify(xyz, eps_km, fixed=None):
    """Douglas-Peucker on the sphere: the indices to keep so that no dropped point is more than eps_km from the
    simplified line. `fixed`: indices that must stay (junctions with other lines, the antimeridian cut). The ends
    always stay; a closed ring (first == last) is split at its fixed points, or at its first point."""
    n = len(xyz)
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    if fixed is not None and len(fixed):
        keep[np.asarray(fixed)] = True
    eps = 2 * np.sin(eps_km / R_KM / 2)    # the chord of that arc
    idx = np.flatnonzero(keep)
    stack = [(int(a), int(b)) for a, b in zip(idx[:-1], idx[1:])]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        # (the farthest point from the chord, a chunk at a time: the first chord of a continent spans all of it)
        dmax, m = -1.0, -1
        for s in range(a + 1, b, CHUNK):
            d = _seg_dist(xyz[s:min(b, s + CHUNK)], xyz[a], xyz[b])
            i = int(np.argmax(d))
            if d[i] > dmax:
                dmax, m = float(d[i]), s + i
        if dmax > eps:
            keep[m] = True
            stack.append((a, m))
            stack.append((m, b))
    return np.flatnonzero(keep)


def ring_area_km2(lonlat):
    """a ring's area on the sphere (signed: positive for counter-clockwise in lon/lat). Good for every ring that does
    not wrap a pole -- the Antarctic one is flagged by its caller."""
    lon, lat = lonlat[:, 0] * DEG, lonlat[:, 1] * DEG
    s = np.sum((lon[1:] - lon[:-1]) * (2 + np.sin(lat[:-1]) + np.sin(lat[1:])))
    return s * R_KM * R_KM / 2


def d3_area(rings):
    """a polygon's area as d3.geoArea reads it (steradians; d3-geo's area.js): its rings' spherical excess, summed,
    wrapped by 2 pi when negative. More than 2 pi -- over half the globe -- means d3 sees it inside out (a tiny ring
    whose points flipped when snapped to the grid) and would paint the whole globe but it."""
    s = 0.0
    for c in rings:
        lam, phi = c[:, 0] * DEG, c[:, 1] * DEG / 2 + np.pi / 4
        d = lam[1:] - lam[:-1]
        sd = np.sign(d); ad = sd * d
        k = np.sin(phi[:-1]) * np.sin(phi[1:])
        s += float(np.sum(np.arctan2(k * sd * np.sin(ad), np.cos(phi[:-1]) * np.cos(phi[1:]) + k * np.cos(ad))))
    return 2 * (2 * np.pi + s if s < 0 else s)


def length_km(lonlat):
    xyz = to_xyz(lonlat)
    c = np.linalg.norm(xyz[1:] - xyz[:-1], axis=1)
    return float(np.sum(2 * np.arcsin(np.clip(c / 2, 0, 1))) * R_KM)


def key(lonlat, q=1e7):
    """exact-coordinate keys (int64 pairs packed) for matching vertices shared between sources"""
    x = np.round(np.asarray(lonlat)[..., 0] * q).astype(np.int64) + 1800000000
    y = np.round(np.asarray(lonlat)[..., 1] * q).astype(np.int64) + 900000000
    return x * 1800000001 + y             # (x < 3.6e9, y < 1.8e9: fits in int64)
