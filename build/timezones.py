"""LAYER 18 -- THE TIME ZONES: the world cut into the IANA time zones (timezone-boundary-builder, E. Siroky and
contributors, ODbL: its "with oceans" release, raw/timezones/), each with its offset from UTC -- for a map coloured by
the offset, and the zone's id (Europe/Berlin) under a click.

    .venv/bin/python build/timezones.py      # raw/timezones/timezones-with-oceans.geojson.zip -> full/timezones.topo.json
    .venv/bin/python build/lite.py 1 25 timezones && .venv/bin/python build/small.py timezones

WITH THE OCEANS: the zones cover the whole globe -- a land zone runs out over its territorial waters, the open sea is in
the nautical zones (Etc/GMT+5: 15° of longitude each, the date line between Etc/GMT-12 and Etc/GMT+12) -- so no zone
follows the map's coast, and none needs to: the zones are drawn over the land and the sea alike, tinted, and the map's
own coast over them. (The land-only release follows OSM's coast at full detail: cut to the map's coast it would be
another bio.py, for lines the map draws anyway.)

A TOPOLOGY OF ITS OWN: the source's polygons share their points along a border, so on the 1/400° grid (config.QUANT_DEG)
a border is the same points in both zones: each ring is cut where its neighbours change (a point with other neighbours
in another ring: three zones meet, or two part), and each piece is kept once, as an arc both zones use. Then each arc
is simplified on its own (its ends stay, so the zones still meet): Douglas-Peucker on the sphere to EPS_KM, then
Visvalingam-Whyatt (build/lite.py) to TRI_KM2 -- a time zone's border is a country's or a state's, drawn under the map's
own; the layer is for the colours, and its file is a few hundred kB.

Objects:
    zones         one row a zone: tzid (IANA's: Europe/Berlin; at sea Etc/GMT+5 -- its sign the POSIX one, the other
                  way round), utc (its offset now, minutes: 60), dst (the offset for part of the year, when it has one:
                  120 -- summer time; Morocco's is its Ramadan hour back), abbr / dst_abbr (CET / CEST: where tzdata
                  gives letters), area_km2, label (a point well inside; a sea zone's near the equator)
    zone_borders  one row a border, its arcs: same (1: both sides keep the same time all year -- Germany / France --,
                  drawn faint; not between a zone's waters and the sea of the same time), and the date line in the open sea (the ±180° meridian between Etc/GMT-12 and +12)
The offsets are Python's zoneinfo (the system's tzdata) over the year YEAR: utc the one in force when no daylight saving
is (the smaller of two; but a shift back for under DST_MIN_DAYS -- Morocco's Ramadan -- is the exception), dst the other.
"""
import os, sys, json, zipfile, datetime, zoneinfo, collections, time
import numpy as np, ijson, shapely
from shapely.ops import polylabel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config
from lite import keep_points

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "raw/timezones/timezones-with-oceans.geojson.zip")   # (release 2026f: github.com/evansiroky/timezone-boundary-builder)
OUT = os.path.join(ROOT, "full/timezones.topo.json")
Q = config.QUANT_DEG
EPS_KM = 1.5               # Douglas-Peucker on the sphere: nothing dropped farther than this off its line...
HEIGHT_KM, TRI_KM2 = 3.0, 12.0     # ...then Visvalingam-Whyatt: a point in a triangle under TRI_KM2 goes, unless it stands HEIGHT_KM off
MIN_KM2 = 4.0              # a ring smaller than this goes (an islet's own zone, and the hole for it in the sea round it: one arc)
YEAR = 2026
DST_MIN_DAYS = 60          # (an offset in force for fewer days than this a year is the exception, not the zone's own)
X180, Y90 = round(360 / Q), round(180 / Q)   # (the +180° meridian, the north pole on the grid)
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def clean(p):
    """grid points (a ring, open) -> without repeats and spikes (A B A -> A), as a ring: None when under three points"""
    out = []
    for q in map(tuple, p.tolist()):
        if out and q == out[-1]:
            continue
        if len(out) >= 2 and q == out[-2]:
            out.pop(); continue
        out.append(q)
    while len(out) >= 3:                                # (round the ring's seam too: a repeat, a spike either side of it)
        if out[0] == out[-1]:
            out.pop()
        elif out[-2] == out[0]:
            out.pop()
        elif out[1] == out[-1]:
            out = out[1:]
        else:
            break
    return np.array(out, dtype=np.int64) if len(out) >= 3 else None


def read_zones():
    """the source's zones -> [(tzid, [polygon: [ring: open grid points, outer ring clockwise as d3 wants it]])]"""
    z = zipfile.ZipFile(SRC)
    out = []
    for ft in ijson.items(z.open(z.namelist()[0]), "features.item", use_float=True):
        g = ft["geometry"]
        polys = []
        for p in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            rings = []
            for r in p:
                a = np.asarray(r, dtype=np.float64)               # (wound as d3 wants it: an outer ring clockwise, a hole the other way --
                ccw = np.dot(a[:-1, 0], a[1:, 1]) - np.dot(a[1:, 0], a[:-1, 1]) > 0   #  on the plane; the source's are either way)
                if ccw == (not rings):
                    a = a[::-1]
                q = np.column_stack((np.round((a[:, 0] + 180) / Q), np.round((a[:, 1] + 90) / Q))).astype(np.int64)
                q[:, 1] = np.minimum(q[:, 1], Y90 - 1)             # (the sea's strips meet at the north pole: a ring through a pole
                q = clean(q)                                       #  is no ring to the globe's clip -- it painted all the sphere)
                if q is not None:
                    rings.append(q)
                elif not rings:
                    break                                          # (the outer ring gone: its holes with it)
            if rings:
                polys.append(rings)
        out.append((ft["properties"]["tzid"], polys))
    return out


def topology(zones):
    """the rings cut into arcs where their neighbours change, each arc once -> (arcs: grid points, rings as
    [(zone, polygon, ring, [signed arc])], the zones using each arc)"""
    key = lambda p: (p[:, 0] << 18) | p[:, 1]
    rings = [(zi, pi, ri, r) for zi, (_, polys) in enumerate(zones) for pi, p in enumerate(polys) for ri, r in enumerate(p)]
    k = np.concatenate([key(r) for *_, r in rings])
    prev = np.concatenate([np.roll(key(r), 1) for *_, r in rings])
    nxt = np.concatenate([np.roll(key(r), -1) for *_, r in rings])
    pairs = np.unique(np.column_stack((k, np.minimum(prev, nxt), np.maximum(prev, nxt))), axis=0)
    ks, n = np.unique(pairs[:, 0], return_counts=True)
    junction = set(ks[n > 1].tolist())
    del k, prev, nxt, pairs, ks, n
    log(f"{len(rings):,} rings, {len(junction):,} points where neighbours change")
    arcs, by_key, users, out = [], {}, collections.defaultdict(set), []
    def arc_id(seg):
        kk = key(seg)
        fwd = kk[0] < kk[-1] or (kk[0] == kk[-1] and (len(kk) < 3 or kk[1] <= kk[-2]))
        c = seg if fwd else seg[::-1]
        b = c.tobytes()
        if b not in by_key:
            by_key[b] = len(arcs); arcs.append(c)
        return by_key[b] if fwd else ~by_key[b]
    for zi, pi, ri, r in rings:
        kk = key(r)
        j = np.flatnonzero(np.fromiter((x in junction for x in kk.tolist()), bool, len(kk)))
        if not len(j):                                     # (a ring touching no other: one closed arc, from its least point)
            c = np.roll(r, -int(np.argmin(kk)), axis=0)
            ids = [arc_id(np.vstack((c, c[:1])))]
        else:
            c = np.roll(r, -int(j[0]), axis=0); c = np.vstack((c, c[:1]))
            cut = list(j - j[0]) + [len(r)]
            ids = [arc_id(c[a:b + 1]) for a, b in zip(cut[:-1], cut[1:])]
        for a in ids:
            users[a if a >= 0 else ~a].add(zi)
        out.append((zi, pi, ri, ids))
    log(f"{len(arcs):,} arcs, {sum(len(a) for a in arcs):,} points")
    return arcs, out, users


def simplified(arcs):
    """each arc simplified, its ends kept -> grid points"""
    out, before, after = [], 0, 0
    for a in arcs:
        ll = a * Q - [180, 90]
        closed = len(a) > 3 and (a[0] == a[-1]).all()
        if closed:                                         # (a closed arc: its far point held too, so that it stays a ring)
            far = int(np.argmax(np.hypot(*(ll - ll[0]).T)))
            k = np.unique(np.concatenate([geo.simplify(geo.to_xyz(ll[:far + 1]), EPS_KM), far + geo.simplify(geo.to_xyz(ll[far:]), EPS_KM)]))
            k = k[keep_points(ll[k], HEIGHT_KM, TRI_KM2, k == far)]
        else:
            k = geo.simplify(geo.to_xyz(ll), EPS_KM)
            k = k[keep_points(ll[k], HEIGHT_KM, TRI_KM2)]
        before += len(a); after += len(k)
        out.append(a[k])
    log(f"simplified: {before:,} -> {after:,} points")
    return out


def offsets(tzid):
    """the zone's offsets over YEAR -> (utc, dst or None, abbr, dst_abbr) in minutes"""
    tz = zoneinfo.ZoneInfo(tzid)
    seen = collections.Counter(); names = {}
    for d in range(0, 366):
        t = (datetime.datetime(YEAR, 1, 1, 12, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=d)).astimezone(tz)
        m = round(t.utcoffset().total_seconds() / 60)
        seen[m] += 1; names.setdefault(m, t.tzname())
    if len(seen) == 1:
        utc, dst = next(iter(seen)), None
    else:
        lo, hi = sorted(seen)[:1][0], sorted(seen)[-1]
        utc, dst = (hi, lo) if seen[lo] < DST_MIN_DAYS else (lo, hi)
    letters = lambda s: s if s and s[0].isalpha() and not s.startswith(("GMT", "UTC")) else None
    return utc, dst, letters(names[utc]), letters(names[dst]) if dst is not None else None


def largest(g):
    """a shape made valid (simplified, a ring may touch itself) -> its largest polygon"""
    ps = [q for p in shapely.get_parts(shapely.make_valid(g)) for q in shapely.get_parts(p) if q.geom_type == "Polygon"]
    return max(ps, key=lambda p: p.area) if ps else g.buffer(0)


def main():
    zones = read_zones()
    log(f"{len(zones)} zones, {sum(len(r) for _, ps in zones for p in ps for r in p):,} points on the grid")
    arcs, rings, users = topology(zones)
    arcs = simplified(arcs)
    ll = lambda a: arcs[a] * Q - [180, 90] if a >= 0 else (arcs[~a] * Q - [180, 90])[::-1]
    pts = lambda ids: np.vstack([ll(a)[:-1] for a in ids] + [ll(ids[0])[:1]])
    polys = collections.defaultdict(lambda: collections.defaultdict(list))
    dropped = 0
    gone = {i for i, a in enumerate(arcs) if len(a) < 4 and (a[0] == a[-1]).all()}   # (a loop simplified to a spike: no area)
    for zi, pi, ri, ids in rings:
        ids = [a for a in ids if (a if a >= 0 else ~a) not in gone]
        if not ids:
            if ri == 0:
                polys[zi][pi] = None
            continue
        p = pts(ids)
        if len(np.unique(p, axis=0)) < 3 or abs(geo.ring_area_km2(p)) < MIN_KM2 and not (p[:, 1] <= -89.9).any():
            dropped += 1
            if ri == 0:
                polys[zi][pi] = None                       # (its outer ring gone: the polygon with it)
            continue
        if polys[zi].get(pi, []) is not None:
            polys[zi][pi].append((ri, ids))
    log(f"{dropped:,} rings under {MIN_KM2:g} km2 left out")
    used = set()
    geoms = []
    for zi, (tzid, _) in enumerate(zones):
        P = [[ids for _, ids in sorted(rs)] for rs in polys[zi].values() if rs and rs[0][0] == 0]
        if not P:
            log(f"  {tzid}: nothing left"); continue
        for p in P:
            for r in p:
                used.update(a if a >= 0 else ~a for a in r)
        shp = [shapely.Polygon(pts(p[0]), [pts(h) for h in p[1:]]) for p in P]
        area = sum(abs(geo.ring_area_km2(pts(p[0]))) - sum(abs(geo.ring_area_km2(pts(h))) for h in p[1:]) for p in P)
        big = largest(max(shp, key=lambda s: s.area))
        if tzid.startswith("Etc/"):                        # (a sea zone: named near the equator, where its strip is widest)
            band = big.intersection(shapely.box(-180, -25, 180, 25))
            big = largest(band) if not band.is_empty else big
        lab = polylabel(big, 0.05)
        utc, dst, abbr, dabbr = offsets(tzid)
        geoms.append({"type": "Polygon" if len(P) == 1 else "MultiPolygon", "arcs": P[0] if len(P) == 1 else P,
                      "properties": {k: v for k, v in {"tzid": tzid, "utc": utc, "dst": dst, "abbr": abbr, "dst_abbr": dabbr,
                                     "area_km2": round(area), "label": [round(lab.x, 2), round(lab.y, 2)]}.items() if v is not None},
                      "_zi": zi})
    # the borders: an arc between two zones -- the same time on both sides all year, or not -- and the date line at sea
    of = {g["_zi"]: g["properties"] for g in geoms}
    key = lambda p: (p["utc"], p.get("dst"))
    borders = []
    for a in sorted(used):
        u = [z for z in users[a] if z in of]
        if len(u) == 2:
            if key(of[u[0]]) == key(of[u[1]]) and any(of[z]["tzid"].startswith("Etc/") for z in u):
                continue                                   # (a land zone's waters and the sea's of the same time: no border at all)
            borders.append({"type": "LineString", "arcs": [a], "properties": {"same": key(of[u[0]]) == key(of[u[1]])}})
        elif len(u) == 1 and (arcs[a][:, 0] == X180).all() and len(np.unique(arcs[a][:, 1])) > 1:
            borders.append({"type": "LineString", "arcs": [a], "properties": {"same": False}})
    for g in geoms:
        del g["_zi"]
    old = sorted(used); new = {k: i for i, k in enumerate(old)}
    remap = lambda x: [remap(y) for y in x] if isinstance(x, list) else (new[x] if x >= 0 else ~new[~x])
    for g in geoms + borders:
        g["arcs"] = remap(g["arcs"])
    topo = {"type": "Topology", "transform": {"scale": [Q, Q], "translate": [-180, -90]},
            "arcs": [np.vstack((arcs[k][:1], np.diff(arcs[k], axis=0))).tolist() for k in old],
            "objects": {"zones": {"type": "GeometryCollection", "geometries": geoms},
                        "zone_borders": {"type": "GeometryCollection", "geometries": borders}}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(topo, open(OUT, "w"), separators=(",", ":"))
    log(f"{OUT}: {len(geoms)} zones, {len(borders):,} borders, {len(old):,} arcs, "
        f"{sum(len(arcs[k]) for k in old):,} points, {os.path.getsize(OUT) / 2**20:.1f} MB")
    by = collections.Counter(g["properties"]["utc"] for g in geoms)
    log("zones by offset: " + ", ".join(f"{m / 60:+g}h {n}" for m, n in sorted(by.items())))


if __name__ == "__main__":
    main()
