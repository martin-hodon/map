"""TECTONIC PLATES (layer 16): Peter Bird's PB2002 model -- 52 plates and the boundaries between them, each boundary
step classed by what the plates do there -- for the map's plates layer (js/plates.js).

    build/fetch_plates.sh                     # raw/plates/: the plates' outlines and Bird's boundary steps
    .venv/bin/python build/plates.py          # -> data/plates.json (~200 kB)

data/plates.json:
  plates: [code, name, area_km2, label [lon, lat], geometry]   (a GeoJSON Polygon or MultiPolygon, the outer rings
          clockwise as d3 wants them: one plate split at the 180th meridian is one MultiPolygon)
  bounds: [id, a, b, cls, over, speed, open, slide, km, [lon, lat, lon, lat ...]]   one RUN each: Bird's steps of one
          boundary and one class in a row, joined (a ridge cut by its transforms is many runs)
    id      Bird's identifier, as "AF-AN" ("JF\\NA", "NA/PA": a subduction zone, the slash leaning over the plate
            that goes under: `A\\B` A under B, `A/B` B under A)
    a, b    the plates: a on the left of the line as it runs, b on its right
    cls     Bird's step class: OSR oceanic spreading ridge, CRB continental rift, OTF / CTF oceanic / continental
            transform fault, OCB / CCB oceanic / continental convergent boundary, SUB subduction zone
    over    which side the upper plate is on (a subduction zone's teeth): 1 left, -1 right, 0 none
    speed   a's velocity relative to b, mm a year (the run's mean, by length); open: its divergent part (closing
            negative); slide: its right-lateral part
    km      the run's length

The coordinates are rounded to 0.01° (about a kilometre): Bird's are 0.001°, more than the map shows.
Source: Bird (2003), An updated digital model of plate boundaries, G-cubed 4(3) 1027, doi:10.1029/2001GC000252, as
converted by Hugo Ahlenius (github.com/fraxen/tectonicplates), Open Data Commons Attribution License 1.0.
"""
import os, re, csv, json, math
from shapely.geometry import shape, mapping, MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.ops import polylabel

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw/plates")
OUT = os.path.join(ROOT, "data/plates.json")
Q = 2                                   # (decimals kept)

# the plates' names as said in English: "the African Plate", not "the Africa Plate"
NAMES = {"Africa": "African", "Antarctica": "Antarctic", "Arabia": "Arabian", "Australia": "Australian", "Eurasia": "Eurasian",
         "India": "Indian", "North America": "North American", "South America": "South American", "Somalia": "Somali",
         "Anatolia": "Anatolian", "Birds Head": "Bird's Head", "Burma": "Burma", "Sunda": "Sunda"}


def rnd(v):
    return round(v, Q)


def km2(g):
    """a lon/lat polygon's area, roughly (each part as flat, shrunk by the cosine of its latitude): to rank the labels"""
    parts = g.geoms if isinstance(g, MultiPolygon) else [g]
    return sum(p.area * math.cos(math.radians(p.centroid.y)) for p in parts) * 111.32 ** 2


def plates():
    by = {}
    for f in json.load(open(os.path.join(RAW, "PB2002_plates.json")))["features"]:
        p = f["properties"]
        by.setdefault(p["Code"], [p["PlateName"], []])[1].append(shape(f["geometry"]))
    out = []
    for code, (name, gs) in sorted(by.items()):
        g = unary_union(gs).buffer(0)
        parts = [orient(p, -1.0) for p in (g.geoms if isinstance(g, MultiPolygon) else [g])]   # (clockwise outer rings: d3's inside)
        big = max(parts, key=lambda p: p.area)
        at = polylabel(big, tolerance=0.05)
        geom = mapping(MultiPolygon(parts) if len(parts) > 1 else parts[0])
        geom = json.loads(json.dumps(geom), parse_float=float)
        def q(c):
            return [[rnd(x), rnd(y)] for x, y in c]
        if geom["type"] == "Polygon":
            geom["coordinates"] = [q(r) for r in geom["coordinates"]]
        else:
            geom["coordinates"] = [[q(r) for r in poly] for poly in geom["coordinates"]]
        out.append([code, f"{NAMES.get(name, name)} Plate", round(km2(g), -3), [rnd(at.x), rnd(at.y)], geom])
    return out


def bounds():
    rows = list(csv.DictReader(open(os.path.join(RAW, "PB2002_steps.csv"))))
    runs, cur = [], None
    for r in rows:
        bid, cls = r["PlateBoundIdentifer"], r["StepClass"]
        x0, y0, x1, y1 = (float(r[k]) for k in ("StartLong", "StartLat", "FinalLong", "FinalLat"))
        km = float(r["StepLength(km)"])
        joined = cur and cur["id"] == bid and cur["cls"] == cls and r["PlateBoundContinuity"] == "TRUE"
        if not joined:
            cur = {"id": bid, "cls": cls, "pts": [[x0, y0]], "km": 0.0, "v": 0.0, "d": 0.0, "s": 0.0}
            runs.append(cur)
        cur["pts"].append([x1, y1])
        cur["km"] += km
        for k, col in (("v", "VelocityLeft"), ("d", "VelocityDivergent"), ("s", "VelocityRightLateral")):
            cur[k] += km * float(r[col])
    out = []
    for u in runs:
        a, sep, b = re.match(r"(\w+)([-/\\])(\w+)", u["id"]).groups()
        over = 0 if u["cls"] != "SUB" else (-1 if sep == "\\" else 1)   # (A\B: a goes under, b on the right is the upper)
        km = u["km"] or 1
        flat = [rnd(v) for p in u["pts"] for v in p]
        out.append([u["id"], a, b, u["cls"], over, round(u["v"] / km, 1), round(u["d"] / km, 1), round(u["s"] / km, 1), round(u["km"]), flat])
    return out


def main():
    P, B = plates(), bounds()
    doc = {"source": "Bird 2003 (PB2002), via github.com/fraxen/tectonicplates, ODC-By 1.0", "plates": P, "bounds": B}
    with open(OUT, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(f"{len(P)} plates, {len(B)} boundary runs ({sum(b[8] for b in B):,} km) -> {OUT} ({os.path.getsize(OUT) // 1024} kB)")


if __name__ == "__main__":
    main()
