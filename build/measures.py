"""MEASURES: what the map's own lines cannot tell -- a river's length (Wikidata P2043: the whole river, the Nile's 6,650
km, where the map traces its 50-m-wide part) and the area of a sea, a gulf, a desert, a range... (P2046: a sea's own,
where the map's has no holes for its islands) -- for the rankings (index.html's side view: js/ranks.js).

    .venv/bin/python build/measures.py        # QLever -> data/measures.json

data/measures.json: {"length_km": {wikidata: km}, "area_km2": {wikidata: km²}}, the rivers' (full/rivers.topo.json) and
the areas' (full/world.topo.json `areas`, the named islands among them) by their Wikidata ids; each the item's
preferred value (else its first), normalised to SI by Wikidata, rounded to three significant figures.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_points as fp

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data/measures.json")


def ids(path, obj):
    return sorted({g["properties"]["wikidata"] for g in json.load(open(os.path.join(ROOT, path)))["objects"][obj]["geometries"]
                   if g.get("properties", {}).get("wikidata")})


def fetch(qids, prop, scale):
    out = {}
    for k in range(0, len(qids), 400):
        vals = " ".join(f"wd:{q}" for q in qids[k:k + 400])
        q = f"""PREFIX psn: <http://www.wikidata.org/prop/statement/value-normalized/> PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
SELECT ?e ?v ?rank WHERE {{ VALUES ?e {{ {vals} }} ?e p:{prop} ?s . ?s psn:{prop} ?n . ?n wikibase:quantityAmount ?v . ?s wikibase:rank ?rank }}"""
        best = {}
        for b in fp.sparql(q, fp.QLEVER):
            e, v, pref = b["e"]["value"].rsplit("/", 1)[1], float(b["v"]["value"]) / scale, b["rank"]["value"].endswith("PreferredRank")
            if v > 0 and (e not in best or (pref and not best[e][1])): best[e] = (v, pref)
        out.update({e: float(f"{v:.3g}") for e, (v, _) in best.items()})
    return out


def main():
    rivers, areas = ids("full/rivers.topo.json", "rivers"), ids("full/world.topo.json", "areas") + ids("full/world.topo.json", "islands")
    got = {"length_km": fetch(rivers, "P2043", 1000), "area_km2": fetch(sorted(set(areas)), "P2046", 1e6)}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f'"{k}": ' + json.dumps(dict(sorted(v.items())), separators=(",", ":")) for k, v in got.items()) + "\n}\n")
    print(f"measures.json: {len(got['length_km'])} of {len(rivers)} rivers' lengths, {len(got['area_km2'])} of {len(set(areas))} areas'")


if __name__ == "__main__":
    main()
