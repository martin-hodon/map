#!/usr/bin/env python3
"""CITY DETAIL MAPS FROM A GEOFABRIK EXTRACT: build/citymaps.py's raw answers (raw/city/<wikidata>_<part>.json.gz, in
Overpass's own JSON: `out geom` ways and relations, `out body` routes, nodes) made from an .osm.pbf of the region round
a city (download.geofabrik.de, kept in raw/city/pbf/) instead of asked of Overpass -- the same elements the Overpass
queries of build/citymaps.py would give (Q_BOUNDARY ... Q_DISTRICTS), so the build does not know where they came from.

Four reads of the file (pyosmium): (1) the relations -- the city's boundary, the districts' boundaries, the train and
metro routes, the multipolygons of the areas wanted, the monuments'; (2) the boundary's ways' nodes and (3) their
places: the city's box; (4) with every node's place (an on-disk index for a big file), the ways and nodes wanted in
that box (the metros' and commuter lines' ones out to OUT_KM).
"""
import os, re, gzip, json, math, time, collections
import osmium
from osmium.filter import EntityFilter, IdFilter, KeyFilter
from osmium.osm import NODE, WAY, RELATION

STREETS = {"motorway", "trunk", "primary", "secondary"}
AREA = {"leisure": {"park", "garden"},
        "landuse": {"forest", "meadow", "recreation_ground", "cemetery", "allotments", "grass", "village_green"},
        "natural": {"wood", "heath", "grassland", "water"}, "waterway": {"riverbank"}, "aeroway": {"aerodrome"}}
REL_MARGIN_KM = 20                                        # (a multipolygon's ways kept this far beyond the box: its ring closes)


def url_of(region):
    """a Geofabrik region ("europe/united-kingdom/england") -> its latest .osm.pbf's URL, as its page links it"""
    import requests
    page = f"https://download.geofabrik.de/{region}.html"
    name = region.rsplit("/", 1)[-1]
    t = requests.get(page, timeout=60).text
    m = re.search(r'href="([^"]*/' + re.escape(name) + r'-latest\.osm\.pbf)"', t)
    if not m:
        raise SystemExit(f"no {name}-latest.osm.pbf on {page}")
    u = m.group(1)
    return u if u.startswith("http") else f"https://download.geofabrik.de/{region.rsplit('/', 1)[0]}/{u}".replace("/./", "/")


def fetch(region, pbfdir):
    """the region's extract in pbfdir (downloaded once)"""
    os.makedirs(pbfdir, exist_ok=True)
    path = os.path.join(pbfdir, region.rsplit("/", 1)[-1] + ".osm.pbf")
    if os.path.exists(path):
        return path
    u = url_of(region)
    print(f"  downloading {u}")
    t0 = time.time()
    import subprocess                                     # (curl: resumes a broken download, -C -)
    for _ in range(5):
        if subprocess.run(["curl", "-sSfL", "-C", "-", "--retry", "5", "-A", "map-citymaps-builder/0.1", "-o", path + ".part", u]).returncode == 0:
            break
    else:
        raise SystemExit(f"could not download {u}")
    os.replace(path + ".part", path)
    print(f"  {os.path.getsize(path) / 1e6:.0f} MB in {time.time() - t0:.0f} s")
    return path


def tags_of(o):
    return {t.k: t.v for t in o.tags}


def members_of(r):
    return [{"type": {"n": "node", "w": "way", "r": "relation"}[m.type], "ref": m.ref, "role": m.role} for m in r.members]


def is_area(t):
    return any(t.get(k) in v for k, v in AREA.items())


def extract(pbf, raw, *, bq, lon0, lat0, levels, monuments, airport, commuter, out_km, pad_km, streets=STREETS):
    """the raw parts (raw(part) -> path) of a city from the extract `pbf`: bq the boundary's wikidata, levels the
    districts' admin_levels, monuments the wikidata ids wanted as areas, airport (iata, lon, lat) or None, commuter(tags)
    -> a route is a metro's or commuter line's (drawn whole), out_km how far those run out, streets the highway classes"""
    t0 = time.time()
    levels = {x for lv in levels for x in str(lv).split("|")}
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.574
    # (1) the relations
    bound, admins, routes, areas, mons = [], [], [], [], []
    for r in osmium.FileProcessor(pbf, RELATION):
        t = tags_of(r)
        if t.get("boundary") == "administrative":
            if t.get("wikidata") == bq:
                bound.append((r.id, t, members_of(r)))
            elif t.get("admin_level") in levels and t.get("name"):
                admins.append((r.id, t, members_of(r)))
        elif t.get("boundary") == "place" and f"place={t.get('place')}" in levels and t.get("name"):
            admins.append((r.id, t, members_of(r)))       # (districts on no admin_level: Amsterdam's stadsdelen)
        if t.get("route") in ("subway", "light_rail", "train"):
            routes.append((r.id, t, members_of(r)))
        if t.get("type") == "multipolygon":
            if is_area(t):
                areas.append((r.id, t, members_of(r)))
            if t.get("wikidata") in monuments:
                mons.append((r.id, t, members_of(r)))
    if not bound:
        raise SystemExit(f"{bq}: no boundary relation in {os.path.basename(pbf)}")
    print(f"  pbf relations: {len(admins)} districts, {len(routes)} routes, {len(areas)} areas ({time.time() - t0:.0f} s)")
    # (2, 3) the boundary's box: its ways' nodes, their places
    bways = {m["ref"] for _, _, ms in bound for m in ms if m["type"] == "way"}
    bnodes = set()
    for w in osmium.FileProcessor(pbf, WAY).with_filter(IdFilter(bways)):
        bnodes.update(n.ref for n in w.nodes)
    xs, ys = [], []
    for n in osmium.FileProcessor(pbf, NODE).with_filter(IdFilter(bnodes)):
        xs.append(n.location.lon); ys.append(n.location.lat)
    pad = pad_km
    box = (min(xs) - pad / kx, min(ys) - pad / ky, max(xs) + pad / kx, max(ys) + pad / ky)
    reach = (lon0 - out_km / kx, lat0 - out_km / ky, lon0 + out_km / kx, lat0 + out_km / ky)
    m_ = REL_MARGIN_KM
    wide = (box[0] - m_ / kx, box[1] - m_ / ky, box[2] + m_ / kx, box[3] + m_ / ky)
    print(f"  box {tuple(round(v, 3) for v in box)}")

    # the ways wanted as members: of the boundary, the districts, the routes, the areas, the monuments
    want = {}                                             # (way id -> why: 1 a route's, 2 an area's or a boundary's)
    for bit, rels in ((2, bound), (2, admins), (1, routes), (2, areas), (2, mons)):
        for _, _, ms in rels:
            for m in ms:
                if m["type"] == "way":
                    want[m["ref"]] = want.get(m["ref"], 0) | bit
    for _, t, ms in areas:                                # (the airport's own ways kept as far as a route's: MXP, 40 km out)
        if airport and t.get("aeroway") == "aerodrome" and t.get("iata") == airport[0]:
            for m in ms:
                if m["type"] == "way":
                    want[m["ref"]] = want.get(m["ref"], 0) | 1
    stop_ids = {m["ref"] for _, _, ms in routes for m in ms if m["type"] == "node"}

    # (4) everything, with the nodes' places
    size = os.path.getsize(pbf)
    idx = "flex_mem" if size < 400e6 else "sparse_file_array," + pbf + ".nodes"
    fp = osmium.FileProcessor(pbf, NODE | WAY).with_locations(idx)
    fp.with_filter(KeyFilter("railway", "public_transport").enable_for(NODE))
    geo, wtags = {}, {}                                   # (way id -> [(lon, lat)], tags)
    stations, stops = [], {}
    lines_ways, area_ways, river_ways, mon_ways, aero_ways, coast_ways = [], [], [], [], [], []
    def inbox(pts, b):
        x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts); y0 = min(p[1] for p in pts); y1 = max(p[1] for p in pts)
        return x1 >= b[0] and x0 <= b[2] and y1 >= b[1] and y0 <= b[3]
    for o in fp:
        if o.is_node():
            if not o.location.valid():
                continue
            x, y = o.location.lon, o.location.lat
            if o.id in stop_ids and box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                stops[o.id] = (x, y)
            t = o.tags
            if t.get("railway") in ("station", "halt") and "name" in t and reach[0] <= x <= reach[2] and reach[1] <= y <= reach[3]:
                stations.append({"type": "node", "id": o.id, "lat": y, "lon": x, "tags": tags_of(o)})
            continue
        t = o.tags
        why = want.get(o.id)
        hw, rw, ww = t.get("highway"), t.get("railway"), t.get("waterway")
        area = is_area(t) or (t.get("wikidata") in monuments)
        coast = t.get("natural") == "coastline"
        if not (why or hw in streets or rw or ww in ("river", "canal") or area or coast):
            continue
        pts = [(n.lon, n.lat) for n in o.nodes if n.location.valid()]
        if len(pts) < 2 or not (inbox(pts, reach) or why and why & 2 and inbox(pts, wide)):
            continue                                      # (a boundary's way past the reach too: Istanbul's province)
        tg = tags_of(o)
        keep = False
        if why and (why & 1 or inbox(pts, wide)):
            keep = True
        if inbox(pts, box):
            if hw in streets:
                lines_ways.append(o.id); keep = True
            if rw == "rail" and tg.get("usage") in ("main", "branch") and "service" not in tg:
                lines_ways.append(o.id); keep = True
            if ww in ("river", "canal") and "name" in tg:
                river_ways.append(o.id); keep = True
            if coast:                                     # (the sea: the coastline's right, the land on its left)
                coast_ways.append(o.id); keep = True
            if area and pts[0] == pts[-1] and len(pts) >= 4:
                if is_area(tg):
                    area_ways.append(o.id)
                if tg.get("wikidata") in monuments:
                    mon_ways.append(o.id)
                keep = True
        if rw in ("station", "halt") and "name" in tg and inbox(pts, reach):
            x_ = sum(p[0] for p in pts) / len(pts); y_ = sum(p[1] for p in pts) / len(pts)
            stations.append({"type": "node", "id": -o.id, "lat": y_, "lon": x_, "tags": tg})   # (a station mapped as its area: its middle)
        if airport and tg.get("aeroway") == "aerodrome" and tg.get("iata") == airport[0]:
            aero_ways.append(o.id); keep = True
        if keep:
            geo[o.id] = pts; wtags[o.id] = tg
    del fp
    if idx.startswith("sparse_file_array"):
        os.remove(pbf + ".nodes")
    print(f"  pbf ways: {len(geo)} kept, {len(stations)} stations, {len(stops)} stops ({time.time() - t0:.0f} s)")

    G = lambda pts: [{"lat": y, "lon": x} for x, y in pts]
    def way_el(i, with_tags=True):
        el = {"type": "way", "id": i, "geometry": G(geo[i])}
        if with_tags:
            el["tags"] = wtags[i]
        return el
    def rel_geom(rid, t, ms):
        out = []
        for m in ms:
            mm = dict(m)
            if m["type"] == "way" and m["ref"] in geo:
                mm["geometry"] = G(geo[m["ref"]])
            out.append(mm)
        return {"type": "relation", "id": rid, "tags": t, "members": out}
    def touches(ms, b):
        return any(m["type"] == "way" and m["ref"] in geo and inbox(geo[m["ref"]], b) for m in ms)
    def dump(part, els):
        path = raw(part)
        with gzip.open(path + ".part", "wt", encoding="utf-8") as f:
            json.dump({"elements": els, "source": os.path.basename(pbf)}, f)
        os.replace(path + ".part", path)
        print(f"  {os.path.basename(path)}: {len(els)} elements (pbf)")

    dump("boundary", [rel_geom(*r) for r in bound])
    dump("districts", [rel_geom(*r) for r in admins if touches(r[2], box)])
    in_box_routes = [r for r in routes if touches(r[2], box)]
    rail_member = {m["ref"] for _, _, ms in in_box_routes for m in ms if m["type"] == "way"}
    lw = set(lines_ways)
    line_els = [way_el(i) for i in dict.fromkeys(lines_ways)]
    line_els += [{"type": "relation", "id": rid, "tags": t, "members": ms} for rid, t, ms in in_box_routes]
    line_els += [way_el(i) for i in rail_member if i in geo and wtags[i].get("railway") in ("rail", "subway", "light_rail")
                 and inbox(geo[i], box) and i not in lw]
    line_els += [s for s in stations if box[0] <= s["lon"] <= box[2] and box[1] <= s["lat"] <= box[3]]
    line_els += [way_el(i) for i in river_ways]
    dump("lines", line_els)
    dump("areas", [way_el(i) for i in area_ways + coast_ways] + [rel_geom(*r) for r in areas if touches(r[2], box)])
    whole = [r for r in in_box_routes if commuter(r[1])]
    tracks = {m["ref"] for _, _, ms in whole for m in ms if m["type"] == "way"}
    dump("routes", [{"type": "relation", "id": rid, "tags": t, "members": ms} for rid, t, ms in whole]
         + [way_el(i) for i in tracks if i in geo and wtags[i].get("railway") in ("rail", "subway", "light_rail")] + stations)
    dump("stops", [{"type": "node", "id": i, "lat": y, "lon": x} for i, (x, y) in stops.items()])
    dump("airport", [way_el(i) for i in aero_ways]
         + ([rel_geom(*r) for r in areas if airport and r[1].get("aeroway") == "aerodrome" and r[1].get("iata") == airport[0]]))
    dump("monuments", [way_el(i) for i in mon_ways] + [rel_geom(*r) for r in mons if touches(r[2], box)])
    print(f"  pbf: done in {time.time() - t0:.0f} s")
