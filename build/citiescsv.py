"""data/cities.csv, ITS LAYOUT (2026-11-27): the cities grouped by country -- and in the five big federations or
unions, GB, US, DE, IN, CN, by state too --, the biggest first in each group, the counts short (1.2M, 65k). Written by
build/points.py; read by build/popcheck.py, build/citymaps.py, ../sky/build/sky.py, ../welle/build/links.py, and the
page (js/data.js citiesRows, the same rules).

    # ...                       a comment (the lines at the top: what the file is)
    name,lon,lat,...            the header: the columns of a city -- without `country` (its group says it)
    [CZ] Czechia                a country: its ISO code in brackets, then its name (only for the reader's eyes)
    [US-CA] California          a state of GB, US, DE, IN, CN: its code has the country's before a dash; the rows under
                                it leave `region` empty (the header says it)
    Prague,14.42,50.088,1.4M,…  a city: population 1.4M = 1,400,000, 65k = 65,000, 4.2k = 4,200, 950 = 950

read() gives every city as before the layout -- a dict of all of COLUMNS, strings, the population in digits -- the
biggest first (of the same count, as the file has them: by country and state)."""
import csv, io, json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PATH = os.path.join(ROOT, "data", "cities.csv")
COLUMNS = ["name", "lon", "lat", "population", "place", "capital", "country", "region", "name_local", "wikidata", "osm"]
STATES = ("GB", "US", "DE", "IN", "CN")          # (grouped by state too)
HEAD = """# data/cities.csv -- the map's cities: 100,000 people or more (70,000 in Europe), every capital, and the exceptions
# (build/points.py writes it; build/citiescsv.py says how it reads)
# [XX] Name: a country, its cities under it, the biggest first; in GB, US, DE, IN and CN [XX-YY] Name: a state of it
# population: 1.4M = 1,400,000; 65k = 65,000; 4.2k = 4,200
"""


def short(n):
    """a count as written: 1400000 -> 1.4M, 65000 -> 65k, 4200 -> 4.2k, 950 -> 950 (exact: no digit lost)"""
    n = int(n)
    for div, unit in ((1_000_000, "M"), (1000, "k")):
        if n >= div and (n * 100) % div == 0:
            return f"{n / div:.2f}".rstrip("0").rstrip(".") + unit
    return str(n)


def long(s):
    """back: '1.4M' -> 1400000"""
    s = s.strip()
    mult = {"M": 1_000_000, "k": 1000}.get(s[-1:], 1)
    return round(float(s[:-1] if mult > 1 else s) * mult) if s else 0


def names():
    """the countries' and states' names, by code (full/world.topo.json)"""
    T = json.load(open(os.path.join(ROOT, "full", "world.topo.json")))["objects"]
    return {g["properties"]["iso"]: g["properties"]["name"] for k in ("countries", "regions") for g in T[k]["geometries"] if g["properties"].get("iso")}


def write(rows, path=PATH, coord=lambda v: v):
    """rows: dicts of COLUMNS (population an int); coord rounds lon and lat"""
    N, cols = names(), [c for c in COLUMNS if c != "country"]
    groups = {}
    for r in rows:   # (in the order given: the biggest first)
        key = (r["country"], r["region"] if r["country"] in STATES else None)
        groups.setdefault(key, []).append(r)
    order = sorted(groups, key=lambda k: (N.get(k[0], k[0]).lower(), k[0], "" if k[1] is None else N.get(k[1], k[1]).lower()))
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    out.write(HEAD)
    w.writerow(cols)
    last = None
    for c, g in order:
        if c != last:
            out.write(f"[{c}] {N.get(c, c)}\n"); last = c
        if g is not None:
            out.write(f"[{g}] {N.get(g, g)}\n")
        for r in groups[(c, g)]:
            w.writerow(["" if g is not None and k == "region" else short(r[k]) if k == "population" else
                        "" if r.get(k) is None else coord(r[k]) if k in ("lon", "lat") else r[k] for k in cols])
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out.getvalue())


def read(path=PATH):
    rows, cols, country, state = [], None, None, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            if cols is None:
                cols = next(csv.reader([line])); continue
            if line.startswith("["):
                code = line[1:line.index("]")]
                if "-" in code: state = code
                else: country, state = code, None
                continue
            r = dict(zip(cols, next(csv.reader([line]))))
            r["country"] = country
            if state: r["region"] = state
            r["population"] = str(long(r["population"]))
            rows.append({k: r.get(k, "") for k in COLUMNS})
    rows.sort(key=lambda r: -int(r["population"]))
    return rows
