"""THE POPULATIONS CHECKED AGAINST ONE ANOTHER (2026-11-25): a country's states together against the country, and a
state's or a country's cities together against it -- what a wrong figure looks like (a Chinese city carrying its whole
prefecture, a state's count from another decade, a city's urban area spilling over its state's border).

    python3 build/popcheck.py [--all]        # reads full/world.topo.json and data/cities.csv; prints what is off

  states     a country whose states (layer 3) add up to more than STATES_TOL off its own count (both ways), or where
             some of its states have no count
  cities     a state, or a country, whose cities (layer 6) add up to more than CITIES_MAX of its own count -- a city is
             counted in the state its `region` names (its urban figure can reach over the border: Brussels's)
Exits 1 when anything is off and lists the worst first (--all: every one, not the first 25 of each).
"""
import collections, csv, json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATES_TOL = 0.10      # a country's states together within 10% of its count
CITIES_MAX = 1.0       # its cities together at most its count
SHOW = 25


def main():
    every = "--all" in sys.argv
    T = json.load(open(os.path.join(ROOT, "full/world.topo.json")))["objects"]
    countries = {g["properties"]["iso"]: g["properties"] for g in T["countries"]["geometries"] if g["properties"].get("iso")}
    regions = {g["properties"]["iso"]: g["properties"] for g in T["regions"]["geometries"] if g["properties"].get("iso")}
    cities = list(csv.DictReader(open(os.path.join(ROOT, "data/cities.csv"), encoding="utf-8")))
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
    print("PASS" if not bad else f"{bad} off")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
