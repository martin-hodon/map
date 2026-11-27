"""THE POPULATIONS CHECKED AGAINST ONE ANOTHER (2026-11-25): a country's states together against the country, and a
state's or a country's cities together against it -- what a wrong figure looks like (a Chinese city carrying its whole
prefecture, a state's count from another decade, a city's urban area spilling over its state's border).

    python3 build/popcheck.py [--all] [--spill]   # reads full/world.topo.json and data/cities.csv; prints what is off
                                                 # (--spill: which states' excess is urban / metro figures, and whose)

  states     a country whose states (layer 3) add up to more than STATES_TOL off its own count (both ways), or where
             some of its states have no count
  cities     a state, or a country, whose cities (layer 6) add up to more than CITIES_MAX of its own count -- a city is
             counted in the state its `region` names (its urban figure can reach over the border: Brussels's)
Exits 1 when anything is off and lists the worst first (--all: every one, not the first 25 of each).
"""
import collections, csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import citiescsv

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATES_TOL = 0.10      # a country's states together within 10% of its count
CITIES_MAX = 1.0       # its cities together at most its count
OWN_TOL = 1.05         # (--spill: by their own counts within 5% of it -- Buenos Aires's 101%, a count a year apart -- is "only by the figures")
SHOW = 25


def main():
    every = "--all" in sys.argv
    T = json.load(open(os.path.join(ROOT, "full/world.topo.json")))["objects"]
    countries = {g["properties"]["iso"]: g["properties"] for g in T["countries"]["geometries"] if g["properties"].get("iso")}
    regions = {g["properties"]["iso"]: g["properties"] for g in T["regions"]["geometries"] if g["properties"].get("iso")}
    cities = citiescsv.read()
    bad = 0

    def report(title, rows):
        nonlocal bad
        bad += len(rows)
        print(f"{title}: {len(rows)}")
        for line in rows[: None if every else SHOW]:
            print("  " + line)
        if not every and len(rows) > SHOW:
            print(f"  ... and {len(rows) - SHOW} more (--all)")

    # a country's states together
    by_country = collections.defaultdict(list)
    for r in regions.values():
        by_country[r.get("country")].append(r)
    off = []
    for cc, rs in by_country.items():
        c = countries.get(cc)
        if not c or not c.get("population"):
            continue
        missing = [r["name"] for r in rs if not r.get("population")]
        s = sum(r.get("population") or 0 for r in rs)
        dev = s / c["population"] - 1
        if missing or abs(dev) > STATES_TOL:
            off.append((abs(dev), f"{cc} {c['name']}: states {s:,} against {c['population']:,} ({dev:+.0%})"
                                  + (f", {len(missing)} of {len(rs)} without a count ({', '.join(missing[:5])})" if missing else "")))
    report(f"countries whose states are more than {STATES_TOL:.0%} off", [t for _, t in sorted(off, reverse=True)])

    # a state's, a country's cities together
    for key, units, what in (("region", regions, "states"), ("country", countries, "countries")):
        tot, n, big = collections.Counter(), collections.Counter(), {}
        for c in cities:
            k, p = c.get(key), int(c["population"] or 0)
            tot[k] += p; n[k] += 1
            if p > big.get(k, (0, ""))[0]:
                big[k] = (p, c["name"])
        off = []
        for k, s in tot.items():
            u = units.get(k)
            if not u or not u.get("population"):
                continue
            if s > CITIES_MAX * u["population"]:
                off.append((s / u["population"], f"{k} {u['name']}: {n[k]} cities {s:,} against {u['population']:,} "
                                                 f"({s / u['population']:.0%}; the biggest {big[k][1]} {big[k][0]:,})"))
        report(f"{what} whose cities add up to more than {CITIES_MAX:.0%} of it", [t for _, t in sorted(off, reverse=True)])
    if "--spill" in sys.argv:
        spill(cities, regions)
    print("PASS" if not bad else f"{bad} off")
    sys.exit(1 if bad else 0)


def spill(cities, regions):
    """--spill: of the states whose cities add up to more than them, those that would NOT with each city's own
    (municipal) count -- the excess is an urban or metro figure reaching over the suburbs (raw/city_sources.json,
    written by build/points.py) -- each with the cities whose figure does it, the biggest excess first; and the rest,
    over even by the municipal counts (a state's count old or wrong, districts counted as cities)"""
    src = json.load(open(os.path.join(ROOT, "raw/city_sources.json")))
    tot, mun, wide = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for c in cities:
        k, p = c["region"], int(c["population"] or 0)
        s, m = src.get(c["osm"] or c["wikidata"], [None, p])
        m = min(p, m or p)
        tot[k] += p; mun[k] += m
        if p > m:
            wide[k].append((p - m, c["name"], s, p, m))
    by_city, other = [], []
    for k, t in tot.items():
        u = regions.get(k)
        if not u or not u.get("population") or t <= CITIES_MAX * u["population"]:
            continue
        line = f"{k} {u['name']}: {t:,} against {u['population']:,} ({t / u['population']:.0%}; own counts {mun[k]:,}, {mun[k] / u['population']:.0%})"
        (by_city if mun[k] <= OWN_TOL * u["population"] else other).append((t / u["population"], line, sorted(wide[k], reverse=True)))
    print(f"\nstates over only by urban / metro figures (by the cities' own counts within {OWN_TOL - 1:.0%}): {len(by_city)}")
    for _, line, w in sorted(by_city, reverse=True):
        print("  " + line)
        for ex, n, s, p, m in w[:4]:
            print(f"      {n}: {p:,} ({s}) for {m:,} of its own, +{ex:,}")
    print(f"states over even by the cities' own counts: {len(other)}")
    for _, line, w in sorted(other, reverse=True):
        print("  " + line + (f" -- widest: {w[0][1]} {w[0][3]:,} ({w[0][2]})" if w else ""))


if __name__ == "__main__":
    main()
