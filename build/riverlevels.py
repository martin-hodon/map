"""STAGE 4c -- THE RIVERS' THREE LEVELS (how thick the map draws them): a `lvl` on every line of full/rivers.topo.json.

    .venv/bin/python build/riverlevels.py         (after build/rivernet.py; then build/lite.py 1 25 rivers, build/small.py)

  1  the great rivers: longer than LVL1_KM, flowing into the sea itself (the Nile, the Danube, the Volga -- the Caspian's
     shore is the coast here, as for rivernet.py)
  2  longer than LVL2_KM and flowing into the sea, or into a river of level 1 -- of those only its TOP longest (the
     Amazon's Madeira, Negro, Japurá ...; the rest of its tributaries stay at 3)
  3  every other river: most of them

Two lines of ONE NAME that meet, not two Wikidata items, are first made one river (merge_same: the Ganges and its
Hooghly arm). A river's LENGTH is Wikidata's (P2043, the river's whole course: the Nile's 6,650 km -- the map draws it only from where
it is 50 m wide, 2,863 km); without one, the length of its lines drawn. Where it ENDS: the downstream end of each of its
lines (rivernet.py's lines follow the flow, and a river flowing into another ends exactly on it: a junction is the end
of every arc there) -- on a point of the coast, or within SEA_KM of it and on no longer river, it is the sea; on another river's line, that river (the longest there);
else inland (a lake, a desert). Its lengths cached in raw/wd_river_length.json.
"""
import os, sys, json, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_points import sparql
import wdnames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIVERS, WORLD = os.path.join(ROOT, "full/rivers.topo.json"), os.path.join(ROOT, "full/world.topo.json")
CACHE = os.path.join(ROOT, "raw/wd_river_length.json")
LVL1_KM, LVL2_KM, TOP = 2000, 500, 5
SEA_KM = 160          # (a river's line may stop short of the coast: the Nile at Cairo, its delta's branches named apart; the
                      #  Rhine where it parts into the Waal; the Euphrates into the Shatt al-Arab -- an end this near the coast,
                      #  on no river longer than itself, is its mouth in the sea)
FIX_KM = {"Q269710": 1375}
SAME = {("r198716", "r199385")}   # (one river under two names: OSM's upper Congo, "Congo" / Lwalaba (the Lualaba), without an item, and its "River Congo")   # (Wikidata's own slips: the Fraser's 2,657 km)
GRID = 0.0025                                                           # (the topology's grid, degrees)
UNIT_KM = {"Q828224": 1, "Q11573": 0.001, "Q253276": 1.609344, "Q93318": 1.852}   # (km, m, mile, nautical mile)


def absolute(arcs):
    out = []
    for a in arcs:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x, y))
        out.append(pts)
    return out


def lengths(qids):
    """Wikidata's length of each river, km (cached; the longest where it has several)"""
    got = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = sorted(q for q in qids if q not in got)
    for i in range(0, len(todo), 300):
        vals = " ".join(f"wd:{q}" for q in todo[i:i + 300])
        rows = sparql(f"""PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
SELECT ?item ?amount ?unit ?rank WHERE {{ VALUES ?item {{ {vals} }} ?item p:P2043 ?s . ?s wikibase:rank ?rank ; psv:P2043 ?v .
  ?v wikibase:quantityAmount ?amount ; wikibase:quantityUnit ?unit . }}""")
        best = {}                                                       # (the preferred statement's, else the longest)
        for r in rows:
            q, u = r["item"]["value"].rsplit("/", 1)[1], r["unit"]["value"].rsplit("/", 1)[1]
            if u in UNIT_KM:
                km, pref = round(float(r["amount"]["value"]) * UNIT_KM[u], 1), r["rank"]["value"].endswith("PreferredRank")
                best[q] = max(best.get(q, (False, 0)), (pref, km))
        for q in todo[i:i + 300]:
            got[q] = best[q][1] if q in best else None
        print(f"  lengths: {min(i + 300, len(todo))} of {len(todo)}", flush=True)
        json.dump(got, open(CACHE, "w"))
    return got


def merge_same(by, arcs):
    """ONE RIVER OF ONE NAME: two of the same name whose lines meet, not two Wikidata items, are one (OSM's Ganges as
    two relations -- the main stream, and the Bhagirathi-Hooghly arm to Kolkata, without an item: two "Ganges" found
    and chosen apart). The one with the item -- else the longer -- takes the other's lines; its properties go on them."""
    on = collections.defaultdict(set)
    for rid, fs in by.items():
        for f in fs:
            for a in f["arcs"]:
                for q in (arcs[a][0], arcs[a][-1]):
                    on[q].add(rid)
    name, wd = (lambda r: by[r][0]["properties"].get("name")), (lambda r: by[r][0]["properties"].get("wikidata"))
    rank = lambda r: (wd(r) is not None, by[r][0]["properties"].get("river_km") or 0)
    pairs = {tuple(sorted((r, o))) for r, fs in by.items() if name(r) for f in fs for a in f["arcs"] for q in (arcs[a][0], arcs[a][-1])
             for o in on[q] if o != r and name(o) == name(r) and not (wd(o) and wd(r))} | {p for p in SAME if all(r in by for r in p)}
    head = {}
    find = lambda r: r if r not in head else find(head[r])
    for a, b in sorted(pairs):
        a, b = find(a), find(b)
        if a == b or (wd(a) and wd(b)):
            continue
        keep, gone = (a, b) if rank(a) >= rank(b) else (b, a)
        k = by[keep][0]["properties"]
        km = (k.get("river_km") or 0) + (by[gone][0]["properties"].get("river_km") or 0) if not k.get("wikidata") else k.get("river_km")
        local = list(dict.fromkeys((k.get("names_local") or []) + [n for f in by[gone][:1] for n in f["properties"].get("names_local") or []]))
        for f in by[gone]:
            f["properties"] = {**k, "length_km": f["properties"].get("length_km", 0)}
        by[keep].extend(by.pop(gone)); head[gone] = keep
        for f in by[keep]:
            f["properties"].update(river_km=km, **({"names_local": local} if local else {}))
        print(f"  one river: {name(keep)} {keep} <- {gone}")


def main():
    topo, world = json.load(open(RIVERS)), json.load(open(WORLD))
    arcs, feats = absolute(topo["arcs"]), topo["objects"]["rivers"]["geometries"]
    warcs = absolute(world["arcs"])
    coast = set()
    for g in world["objects"]["coastline"]["geometries"]:
        stack = [g["arcs"]]
        while stack:
            a = stack.pop()
            if isinstance(a, list):
                stack.extend(a)
            else:
                coast.update(warcs[a if a >= 0 else ~a])
    by = collections.defaultdict(list)
    for f in feats:
        by[f["properties"]["river"]].append(f)
    merge_same(by, arcs)
    on = collections.defaultdict(set)                                   # (a grid point -> the rivers whose lines pass it)
    ends_of = {}
    for rid, fs in by.items():
        ends = []
        for f in fs:
            for a in f["arcs"]:
                for q in arcs[a]:
                    on[q].add(rid)
            ends.append(arcs[f["arcs"][-1]][-1])
        ends_of[rid] = ends
    wd = lengths({fs[0]["properties"]["wikidata"] for fs in by.values() if fs[0]["properties"].get("wikidata")})
    km = {}
    for rid, fs in by.items():
        p = fs[0]["properties"]
        km[rid] = FIX_KM.get(p.get("wikidata")) or wd.get(p.get("wikidata")) or sum(f["properties"].get("length_km", 0) for f in fs)
    # where each river ends: the sea, another river, or inland
    from scipy.spatial import cKDTree
    import numpy as np
    pts = np.array(sorted(coast), dtype=float)
    tree = cKDTree(np.column_stack(((pts[:, 0] * GRID - 180) * np.cos(np.radians(pts[:, 1] * GRID - 90)), pts[:, 1] * GRID)))
    to_coast = lambda q: tree.query([(q[0] * GRID - 180) * np.cos(np.radians(q[1] * GRID - 90)), q[1] * GRID])[0] * 111.2   # (km, near enough)
    sea, into = set(), {}
    for rid, ends in ends_of.items():
        if any(q in coast or (to_coast(q) <= SEA_KM and all(km[r] < km[rid] for r in on[q] if r != rid)) for q in ends):
            sea.add(rid); continue
        other = [r for q in ends for r in on[q] if r != rid]
        if other:
            into[rid] = max(other, key=lambda r: km[r])
    lvl = {rid: 3 for rid in by}
    for rid in sea:
        if km[rid] > LVL1_KM:
            lvl[rid] = 1
    for rid in sea:
        if lvl[rid] == 3 and km[rid] > LVL2_KM:
            lvl[rid] = 2
    trib = collections.defaultdict(list)
    for rid, r in into.items():
        if lvl.get(r) == 1 and km[rid] > LVL2_KM:
            trib[r].append(rid)
    for r, ts in trib.items():
        for rid in sorted(ts, key=lambda t: -km[t])[:TOP]:
            lvl[rid] = 2
    for rid, fs in by.items():
        for f in fs:
            f["properties"]["lvl"] = lvl[rid]
    for o in topo["objects"].values():   # (no local name in the Arabic, Indian or Thai scripts)
        for g in o.get("geometries", []):
            wdnames.drop_unread(g.get("properties") or {})
    json.dump(topo, open(RIVERS, "w"), ensure_ascii=False, separators=(",", ":"))
    n = collections.Counter(lvl.values())
    name = lambda r: by[r][0]["properties"].get("name") or r
    print(f"{len(by):,} rivers: {len(sea):,} into the sea, {len(into):,} into another river, {len(by) - len(sea) - len(into):,} inland; "
          f"level 1: {n[1]}, 2: {n[2]}, 3: {n[3]}")
    for r in sorted((r for r in lvl if lvl[r] == 1), key=lambda r: -km[r]):
        print(f"  1 {name(r)} {km[r]:,.0f} km <- " + ", ".join(f"{name(t)} {km[t]:,.0f}" for t in sorted(trib.get(r, []), key=lambda t: -km[t])[:TOP]))


if __name__ == "__main__":
    main()
