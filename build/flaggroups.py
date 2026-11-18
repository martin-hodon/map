#!/usr/bin/env python3
"""flaggroups.py -- data/flag_groups.json: for each country's, dependency's and state's flag in data/flags.txt, what it
is and where, from the map's own layers (full/world.topo.json) -- so flags.html can show them by continent, countries
apart from dependencies and states, and those by their country:

  { "FR": ["Europe", "country"], "PR": ["North America", "dependency", "US"], "ES-AN": ["Europe", "state", "ES"], ... }

The continent is the map's (`continent`: where the label lies -- Russia's European oblasts in Europe, its Asian ones in
Asia; Greenland in North America). A code the map has not (a flag for a state below its divisions) is left out: the
page takes a state's country from its code and its continent from the country's. Run it again after adding flags:

  python3 build/flaggroups.py
"""
import json, os, re

# the flags the map has no polygon for (the map draws Western Sahara and Palestine by other codes, England as its nine
# regions), placed here; the EU is none of the three
EXTRA = {"EH": ["Africa", "country"], "PS": ["Asia", "country"], "GB-ENG": ["Europe", "state", "GB"], "EU": ["Europe", "union"]}

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def main():
    codes = set()
    for line in open(os.path.join(ROOT, "data", "flags.txt"), encoding="utf-8"):
        m = re.match(r"([A-Z]{2}(?:-[A-Z0-9]+)*)[ :]", line)
        if m and not m.group(1).endswith("-arms"): codes.add(m.group(1))
    topo = json.load(open(os.path.join(ROOT, "full", "world.topo.json"), encoding="utf-8"))["objects"]
    out = {k: v for k, v in EXTRA.items() if k in codes}
    for g in topo["countries"]["geometries"]:
        p = g["properties"]
        if p.get("iso") in codes:
            out[p["iso"]] = [p["continent"], p["subtype"]] + ([p["sovereign"]] if p["subtype"] == "dependency" else [])
    for g in topo["regions"]["geometries"]:
        p = g["properties"]
        if p.get("iso") in codes: out[p["iso"]] = [p["continent"], "state", p["country"]]
    with open(os.path.join(ROOT, "data", "flag_groups.json"), "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(out.items())) + "\n}\n")
    print(f"flag_groups.json: {len(out)} of {len(codes)} flags placed; not on the map: {' '.join(sorted(codes - set(out))) or 'none'}")

if __name__ == "__main__":
    main()
