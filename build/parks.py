"""THE PARKS' AREAS (layer 5's national parks and protected areas, as areas): the outline of each national park and
protected area of data/monuments.csv, from OpenStreetMap -- drawn, tinted, where the park is more than a few pixels
across; smaller, it stays the monument's point.

    .venv/bin/python build/parks.py      # data/monuments.csv + OSM (QLever, raw/parks/ caches) -> full/parks.topo.json
    .venv/bin/python build/lite.py 1 25 parks && .venv/bin/python build/small.py parks

WHICH OSM OBJECT: the row's own (`osm`: relation/2131838, from build/points.py), else the relation (or way) whose
`wikidata` tag is the row's item -- of several, a boundary=national_park / protected_area or leisure=nature_reserve
first, a relation before a way. The shapes are OSM's multipolygons as QLever's OSM planet (osm2rdf: qlever.dev/api/osm-planet)
assembles them (geo:asWKT), asked for BATCH at a time, each answer kept under raw/parks/ (a park's outline,
relation_<id>.wkt; the ids looked up, ids.json): a second run asks for nothing. A request that fails is tried again
after 10, 20, 40... s.

KEPT: a polygon (a park mapped as a route -- the Appalachian Trail -- is no area), that the row's point lies in or within
NEAR_KM of (a wrong match: another object of the item, far off), and of MIN_KM2 or more; each ring simplified on the
sphere (EPS_KM) and put on the 1/400° grid, an outer ring clockwise. The parks overlap, and share no lines: each ring is an
arc of its own. A row with no shape found stays the monument's point.

Object:
    parks   one row a park: name, wikidata (the monument's: how the map ties the area to its point), kind, level, area_km2, osm
"""
import os, sys, csv, json, time, hashlib
import numpy as np, requests, shapely
from shapely.geometry.polygon import orient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw/parks")
OUT = os.path.join(ROOT, "full/parks.topo.json")
QLEVER = "https://qlever.dev/api/osm-planet"
KINDS = {"national park", "protected area"}
BATCH = 15
EPS_KM = 0.25              # (the map's own lines are kept to 0.5 km: a park's outline as fine, on the 278 m grid)
MIN_KM2 = 1.0
NEAR_KM = 25.0
Q = config.QUANT_DEG
PREFIX = """PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
"""


def ask(query, accept):
    """QLever, tried again with a growing wait -> the answer's text"""
    for k in range(7):
        try:
            r = requests.post(QLEVER, data={"query": PREFIX + query}, headers={"Accept": accept}, timeout=300)
            if r.ok:
                return r.text
            print(f"  QLever {r.status_code}: {r.text[:200]}", flush=True)
        except requests.RequestException as e:
            print(f"  QLever: {e}", flush=True)
        time.sleep(10 * 2 ** k)
    raise SystemExit("QLever does not answer")


def lookup(items):
    """the OSM objects tagged with these Wikidata items -> {item: 'relation/123'} (raw/parks/ids.json)"""
    path = os.path.join(RAW, "ids.json")
    known = json.load(open(path)) if os.path.exists(path) else {}
    todo = [q for q in items if q not in known]
    for i in range(0, len(todo), 200):
        part = todo[i:i + 200]
        vals = " ".join(f'"{q}"' for q in part)
        text = ask(f"SELECT ?o ?wd ?b ?l WHERE {{ VALUES ?wd {{ {vals} }} ?o osmkey:wikidata ?wd . "
                   f"OPTIONAL {{ ?o osmkey:boundary ?b }} OPTIONAL {{ ?o osmkey:leisure ?l }} }}", "application/sparql-results+json")
        best = {}
        for b in json.loads(text)["results"]["bindings"]:
            o = b["o"]["value"].split("openstreetmap.org/")[-1]
            if not o.startswith(("relation/", "way/")):
                continue
            rank = (b.get("b", {}).get("value") in ("national_park", "protected_area") or b.get("l", {}).get("value") == "nature_reserve",
                    o.startswith("relation/"))
            q = b["wd"]["value"]
            if q not in best or rank > best[q][0]:
                best[q] = (rank, o)
        for q in part:
            known[q] = best[q][1] if q in best else None
        json.dump(known, open(path, "w"), indent=0)
    return known


def shapes(objs):
    """their outlines as WKT -> {'relation/123': wkt or ''} (raw/parks/<kind>_<id>.wkt; '' none)"""
    file = lambda o: os.path.join(RAW, o.replace("/", "_") + ".wkt")
    todo = sorted({o for o in objs if not os.path.exists(file(o))})
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        vals = " ".join(f"<https://www.openstreetmap.org/{o}>" for o in part)
        text = ask(f"SELECT ?o ?wkt WHERE {{ VALUES ?o {{ {vals} }} ?o geo:hasGeometry/geo:asWKT ?wkt }}", "text/tab-separated-values")
        got = {}
        for line in text.split("\n")[1:]:
            if "\t" in line:
                o, w = line.split("\t", 1)
                got[o.strip("<>").split("openstreetmap.org/")[-1]] = w.strip().strip('"').split('"^^')[0]
        for o in part:
            open(file(o), "w").write(got.get(o, ""))
        print(f"  {i + len(part)}/{len(todo)} outlines", flush=True)
    return {o: open(file(o)).read() for o in objs}


def rings_of(g):
    """a (multi)polygon -> [polygon: [ring: grid points, closed]] simplified, the outer ring clockwise; specks left out"""
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon":
            continue
        p = orient(p, sign=-1.0)
        rings = []
        for k, r in enumerate([p.exterior, *p.interiors]):
            ll = np.asarray(r.coords)[:, :2]
            if abs(geo.ring_area_km2(ll)) < MIN_KM2:
                if k == 0:
                    break
                continue
            ll = ll[geo.simplify(geo.to_xyz(ll), EPS_KM)]
            q = np.column_stack((np.round((ll[:, 0] + 180) / Q), np.round((ll[:, 1] + 90) / Q))).astype(np.int64)
            q = q[np.r_[True, np.any(q[1:] != q[:-1], axis=1)]]
            if len(q) >= 4 and len(np.unique(q, axis=0)) >= 3:
                rings.append(q)
            elif k == 0:
                break
        if rings:
            out.append(rings)
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data/monuments.csv"), encoding="utf-8")) if r["kind"] in KINDS]
    ids = lookup([r["wikidata"] for r in rows if not r["osm"].startswith(("relation/", "way/")) and r["wikidata"]])
    obj = {r["wikidata"]: r["osm"] if r["osm"].startswith(("relation/", "way/")) else ids.get(r["wikidata"]) for r in rows}
    wkt = shapes([o for o in obj.values() if o])
    arcs, geoms, why = [], [], {"no OSM object": 0, "no outline": 0, "not an area": 0, "far from its point": 0, "too small": 0}
    for r in rows:
        o = obj[r["wikidata"]]
        if not o:
            why["no OSM object"] += 1; continue
        if not wkt[o]:
            why["no outline"] += 1; continue
        g = shapely.make_valid(shapely.from_wkt(wkt[o]))
        g = shapely.union_all([p for p in shapely.get_parts(g) for p in shapely.get_parts(p) if p.geom_type == "Polygon"] or [shapely.Polygon()])
        if g.is_empty:
            why["not an area"] += 1; continue
        pt = shapely.Point(float(r["lon"]), float(r["lat"]))
        if g.distance(pt) * 111 > NEAR_KM:
            why["far from its point"] += 1; continue
        P = rings_of(g)
        if not P:
            why["too small"] += 1; continue
        area = sum(abs(geo.ring_area_km2(q[:, :2] * Q - [180, 90])) * (1 if k == 0 else -1) for p in P for k, q in enumerate(p))
        refs = []
        for p in P:
            refs.append([])
            for q in p:
                refs[-1].append([len(arcs)]); arcs.append(q)
        geoms.append({"type": "MultiPolygon", "arcs": refs,
                      "properties": {"name": r["name"], "wikidata": r["wikidata"], "kind": r["kind"], "level": int(r["level"]),
                                     "area_km2": round(area), "osm": o}})
    topo = {"type": "Topology", "transform": {"scale": [Q, Q], "translate": [-180, -90]},
            "arcs": [np.vstack((a[:1], np.diff(a, axis=0))).tolist() for a in arcs],
            "objects": {"parks": {"type": "GeometryCollection", "geometries": geoms}}}
    json.dump(topo, open(OUT, "w"), separators=(",", ":"))
    print(f"{OUT}: {len(geoms)} of {len(rows)} parks as areas ({sum(1 for g in geoms if g['properties']['kind'] == 'national park')} national parks), "
          f"{sum(len(a) for a in arcs):,} points, {os.path.getsize(OUT) / 2**20:.1f} MB; points only: {why}")


if __name__ == "__main__":
    main()
