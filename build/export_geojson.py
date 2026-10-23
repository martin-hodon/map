"""The TopoJSON layers as plain GeoJSON, one file per object (RFC 7946: outer rings anticlockwise -- the other way
round from the TopoJSON, which winds as d3-geo expects), for tools that read GeoJSON and not TopoJSON.

    .venv/bin/python build/export_geojson.py [decimals]     # -> data/geojson/<object>.geojson (default 3 decimals, 111 m)

The shared lines are written out once per geometry that uses them, so these files are several times bigger.
"""
import os, sys, json
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def decode(topo):
    s, t = topo["transform"]["scale"], topo["transform"]["translate"]
    return [np.cumsum(np.array(a, dtype=float), axis=0) * s + t for a in topo["arcs"]]


def ring(arcs, ids):
    out = []
    for i in ids:
        c = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.append(c if not out else c[1:])
    return np.vstack(out)


def geometry(arcs, g, nd):
    r = lambda c: np.round(c, nd).tolist()
    t = g["type"]
    if t == "LineString":
        return {"type": t, "coordinates": r(ring(arcs, g["arcs"]))}
    if t == "MultiLineString":
        return {"type": t, "coordinates": [r(ring(arcs, a)) for a in g["arcs"]]}
    if t == "Polygon":
        return {"type": t, "coordinates": [r(ring(arcs, a)[::-1]) for a in g["arcs"]]}          # (rewound for RFC 7946)
    if t == "MultiPolygon":
        return {"type": t, "coordinates": [[r(ring(arcs, a)[::-1]) for a in p] for p in g["arcs"]]}
    if t == "Point":
        return {"type": t, "coordinates": g["coordinates"]}
    raise ValueError(t)


def main():
    nd = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out_dir = os.path.join(ROOT, "data/geojson")
    os.makedirs(out_dir, exist_ok=True)
    for name in ("world.topo.json", "rivers.topo.json", "areas.topo.json"):
        topo = json.load(open(os.path.join(ROOT, "data", name)))
        arcs = decode(topo)
        for obj, coll in topo["objects"].items():
            feats = [{"type": "Feature", **({"id": g["id"]} if "id" in g else {}), "properties": g.get("properties", {}),
                      "geometry": geometry(arcs, g, nd)} for g in coll["geometries"]]
            path = os.path.join(out_dir, obj + ".geojson")
            json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
            print(f"{path}: {len(feats)} features, {os.path.getsize(path) / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
