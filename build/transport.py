"""STAGE 7 -- TRANSPORT: the main lines of the world -- motorways (and trunk roads signed 100 km/h or more), main-line
and high-speed railways, oil and gas pipelines -- out of OSM (raw/transport/, build/fetch_transport.py).

    .venv/bin/python build/transport.py           # -> full/transport.tracked.topo.json (objects: motorways, railways, pipelines)

Only the main ones: a road by its class and its speed, a railway by OSM's `usage=main` (or `highspeed=yes`), a pipeline
by what it carries (oil, gas) and what it is for (not `distribution`, `gathering`, a penstock). And then by length:
the ways that meet end to end make one network, and a network shorter than MIN_KM of its kind (a spur in a city, a
gas main under one town) is left out. Within a network the ways of one road number (or name) are joined end to end:
lines as OSM has them, every carriageway and track, at FINE_KM. build/roadnet.py then makes them one network of single
lines (a road's carriageways one line, its junctions exact) and ranks them -> full/transport.topo.json.

Memory: each answer of Overpass is read a way at a time (ijson), every way kept simplified to FINE_KM at once.
"""
import os, sys, time, json, gzip, glob, re, collections
import numpy as np, shapely, ijson

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config
from write import quantize

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.environ.get("TRANSPORT_RAW", os.path.join(ROOT, "raw", "transport"))          # (overrides: for a test on a few tiles)
OUT = os.environ.get("TRANSPORT_OUT", os.path.join(ROOT, "full/transport.tracked.topo.json"))
MIN_KM = {"motorways": 20.0, "railways": 30.0, "pipelines": 50.0}
MIN_SPEED = 100.0
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def speed(v):
    """a maxspeed tag -> km/h (or None): '120', '70 mph', '100;80' (the first)"""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(mph)?", str(v or ""))
    return None if not m else float(m.group(1)) * (1.609 if m.group(2) else 1.0)


def classify(t):
    """-> (object, properties) or None"""
    if t.get("highway") == "motorway":
        return "motorways", {"class": "motorway", "ref": t.get("ref"), "name": t.get("int_name") or t.get("name:en") or t.get("name")}
    if t.get("highway") == "trunk" and (speed(t.get("maxspeed")) or 0) >= MIN_SPEED:
        return "motorways", {"class": "trunk", "ref": t.get("ref"), "name": t.get("int_name") or t.get("name:en") or t.get("name")}
    if t.get("railway") == "rail" and (t.get("usage") == "main" or t.get("highspeed") == "yes") and not t.get("service"):
        return "railways", {"highspeed": t.get("highspeed") == "yes" or None, "name": t.get("name:en") or t.get("name"), "ref": t.get("ref")}
    if t.get("man_made") == "pipeline" and t.get("usage") not in ("distribution", "gathering", "penstock", "facility", "industrial"):
        sub = t.get("substance", "")
        sub = "gas" if "gas" in sub or sub in ("lng", "lpg") else "oil"
        return "pipelines", {"substance": sub, "name": t.get("name:en") or t.get("name"), "operator": t.get("operator")}
    return None


def main():
    files = sorted(glob.glob(os.path.join(RAW, "*.json.gz")))
    seen = set()
    ways = {k: [] for k in MIN_KM}                           # object -> [(coords at FINE_KM, props)]
    for n, path in enumerate(files):
        with gzip.open(path, "rb") as f:
            for e in ijson.items(f, "elements.item", use_float=True):
                if e.get("type") != "way" or e["id"] in seen or not e.get("geometry"):
                    continue
                seen.add(e["id"])
                got = classify(e.get("tags", {}))
                if not got:
                    continue
                c = np.array([(p["lon"], p["lat"]) for p in e["geometry"] if p], dtype=float)
                if len(c) < 2:
                    continue
                c = c[geo.simplify(geo.to_xyz(c), config.FINE_KM)]
                ways[got[0]].append((c, got[1]))
        if n % 50 == 0:
            log(f"  {n + 1}/{len(files)} tiles, {len(seen):,} ways,", {k: len(v) for k, v in ways.items()})
    del seen
    objects, arcs = {}, []
    for obj, ws in ways.items():
        # the networks: the ways that meet end to end
        parent = list(range(len(ws)))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        at = {}
        for i, (c, _) in enumerate(ws):
            for p in (c[0], c[-1]):
                k = int(geo.key(p))
                if k in at:
                    parent[find(i)] = find(at[k])
                else:
                    at[k] = i
        del at
        nets = collections.defaultdict(list)
        for i in range(len(ws)):
            nets[find(i)].append(i)
        geoms, short = [], 0
        for ids in nets.values():
            km = sum(geo.length_km(ws[i][0]) for i in ids)
            if km < MIN_KM[obj]:
                short += 1
                continue
            # within a network, a line per road number (or name): the A1 is found as the A1, not as its country's roads
            by = collections.defaultdict(list)
            for i in ids:
                by[ws[i][1].get("ref") or ws[i][1].get("name") or ""].append(i)
            net = f"{obj[0]}{len(geoms)}"                       # (the lines of one network share it)
            for label, part in by.items():
                props = collections.defaultdict(collections.Counter)   # (each property: its most common value, by length)
                for i in part:
                    for k, v in ws[i][1].items():
                        if v:
                            props[k][v] += geo.length_km(ws[i][0])
                p = {k: c.most_common(1)[0][0] for k, c in props.items()}
                p.update(network=net, network_km=round(km))
                merged = shapely.line_merge(shapely.multilinestrings([shapely.linestrings(ws[i][0]) for i in part]))
                for g in shapely.get_parts(merged):
                    geoms.append({"type": "LineString", "arcs": [len(arcs)], "properties": p}); arcs.append(shapely.get_coordinates(g))
        objects[obj] = {"type": "GeometryCollection", "geometries": geoms}
        log(f"{obj}: {len(ws):,} ways -> {len(nets):,} networks, {short:,} under {MIN_KM[obj]:.0f} km left out;",
            f"{len(geoms):,} lines, {sum(len(arcs[g['arcs'][0]]) for g in geoms):,} points")
        ways[obj] = None
    topo = {"type": "Topology", "bbox": [-180, -90, 180, 90],
            "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
            "objects": objects, "arcs": quantize(arcs)}
    path = OUT
    json.dump(topo, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    log(f"{path}: {os.path.getsize(path) / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
