"""STAGE 7 -- TRANSPORT: the main lines of the world -- motorways (and trunk roads signed 100 km/h or more), main-line
and high-speed railways, oil and gas pipelines -- out of OSM (raw/transport/, build/fetch_transport.py).

    .venv/bin/python build/transport.py           # -> data/transport.topo.json (objects: motorways, railways, pipelines)

Only the main ones: a road by its class and its speed, a railway by OSM's `usage=main` (or `highspeed=yes`), a pipeline
by what it carries (oil, gas) and what it is for (not `distribution`, `gathering`, a penstock). And then by length:
the ways that meet end to end make one network, and a network shorter than MIN_KM of its kind (a spur in a city, a
gas main under one town) is left out. Each network's lines are joined end to end and simplified on the sphere. A
road or railway is one line: the two carriageways of a motorway, the tracks of a railway, are separate ways in OSM
(parallel, a few metres to a few hundred apart) -- of the lines of one road number the longest is kept, and of each
other one only the stretches that do not run within TWIN_KM of a kept one (an arm that is really elsewhere).

Memory: each answer of Overpass is read a way at a time (ijson), every way kept simplified to FINE_KM at once.
"""
import os, sys, time, json, gzip, glob, re, collections
import numpy as np, shapely, ijson

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo, config
from write import quantize

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.environ.get("TRANSPORT_RAW", os.path.join(ROOT, "raw", "transport"))          # (overrides: for a test on a few tiles)
OUT = os.environ.get("TRANSPORT_OUT", os.path.join(ROOT, "data/transport.topo.json"))
MIN_KM = {"motorways": 20.0, "railways": 30.0, "pipelines": 50.0}
EPS_KM = {"motorways": 1.0, "railways": 1.0, "pipelines": 1.0}      # (their detail: coarser than the coast's)
MIN_SPEED = 100.0
TWIN_KM = {"motorways": 0.25, "railways": 0.25}                   # (pipelines side by side are pipelines side by side)
MIN_RUN_KM = 1.0                                                  # a stretch of a line beside a kept one, kept if this long
MIN_LINE_KM = 1.0                                                 # (a stub shorter than this vanishes on the 1/400 degree grid anyway)
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


def collapse(lines, d_km):
    """the lines of one road (shapely linestrings at FINE_KM), longest first: each one without its stretches within
    d_km of the ones before it -> coordinate arrays. The kept lines' points (densified to ~0.3 km) are the yardstick."""
    from scipy.spatial import cKDTree
    chord = 2 * np.sin(d_km / geo.R_KM / 2)
    cloud, tree, out, dirty = [], None, [], False
    for g in sorted(lines, key=lambda g: -g.length):
        c = shapely.get_coordinates(shapely.segmentize(g, 0.003))
        xyz = geo.to_xyz(c)
        if dirty:
            tree, dirty = cKDTree(np.concatenate(cloud)), False
        free = np.ones(len(c), bool) if tree is None else tree.query(xyz, distance_upper_bound=chord)[0] == np.inf
        if free.all():
            runs = [(0, len(c))]
        else:                                                  # the runs of points not beside a kept line (with a point over at each end)
            runs, i = [], 0
            while i < len(c):
                if not free[i]:
                    i += 1; continue
                j = i
                while j < len(c) and free[j]:
                    j += 1
                runs.append((max(0, i - 1), min(len(c), j + 1))); i = j
        for a, b in runs:
            if b - a >= 2 and (b - a == len(c) or geo.length_km(c[a:b]) >= MIN_RUN_KM):
                out.append(c[a:b]); cloud.append(xyz[a:b]); dirty = True
    return out


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
        geoms, short, twins = [], 0, 0
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
                parts = list(shapely.get_parts(merged))
                if obj in TWIN_KM and len(parts) > 1:
                    twins += len(parts); parts = collapse(parts, TWIN_KM[obj]); twins -= len(parts)
                for c in (shapely.get_coordinates(g) if not isinstance(g, np.ndarray) else g for g in parts):
                    c = c[geo.simplify(geo.to_xyz(c), EPS_KM[obj])]
                    if len(c) >= 2 and geo.length_km(c) >= MIN_LINE_KM:
                        geoms.append({"type": "LineString", "arcs": [len(arcs)], "properties": p}); arcs.append(c)
        objects[obj] = {"type": "GeometryCollection", "geometries": geoms}
        log(f"{obj}: {len(ws):,} ways -> {len(nets):,} networks, {short:,} under {MIN_KM[obj]:.0f} km left out;",
            f"{twins:,} twin lines collapsed; {len(geoms):,} lines, {sum(len(arcs[g['arcs'][0]]) for g in geoms):,} points")
        ways[obj] = None
    topo = {"type": "Topology", "bbox": [-180, -90, 180, 90],
            "transform": {"scale": [config.QUANT_DEG, config.QUANT_DEG], "translate": [-180, -90]},
            "objects": objects, "arcs": quantize(arcs)}
    path = OUT
    json.dump(topo, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    log(f"{path}: {os.path.getsize(path) / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
