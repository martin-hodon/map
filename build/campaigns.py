"""WARS AND CAMPAIGNS: the historical events (data/events.csv) gathered into the wars, campaigns, invasions, offensives
... they were part of, those into the bigger ones (Wikidata's "part of", P361, up to four levels), and in each the
MOVES between its battles and sieges -- lines that go roughly as the armies did.

    .venv/bin/python build/campaigns.py       # QLever -> raw/wd_partof.json (kept) -> data/campaigns.json

data/campaigns.json: {"groups": [...]}, one per war or campaign with at least two events in it (its own and its parts'):
    id      the Wikidata id
    name    English
    kind    what Wikidata says it is (war, military campaign, invasion, ...: the first that is one of MILITARY)
    from, to   its years (astronomical: -217 is 218 BC): Wikidata's start and end, else its events' first and last
    parent  the index of the war it was part of, or -1
    events  its own events, as rows of data/events.csv (0 the first under the header), by date
    moves   pairs of those rows: from a battle to the next one its army is taken to have fought

A move: the events of one group are taken by date; each battle or siege joins the THREAD (an army, as far as one can
tell) whose last battle is nearest -- within a march of it (MARCH_KM a day, and BASE_KM, plus the slack of a date known
only to its month or year: SLACK), never more than MOVE_KM or MOVE_DAYS -- and is linked from that one; with none near
enough it starts a thread of its own. So a war on two fronts gets two chains, not a zigzag between them. Where most
of a group's events are known to the day or month, one known only to its year (or coarser) is left out of the moves:
where it falls among them is not known. It is a guess from places and dates alone, not a record of marches.

An event in several groups goes to the most specific (the one the others contain, else the smallest). A group that
is no war (a "historical period", a list, a treaty series) is passed over: its events go to the next one up, if any.
"""
import os, re, sys, csv, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_points as fp

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw/wd_partof.json")
EVENTS = os.path.join(ROOT, "data/events.csv")
OUT = os.path.join(ROOT, "data/campaigns.json")
LEVELS = 4
# what a war or a campaign is (Wikidata's classes, by word): a group of no such class is none
MILITARY = re.compile(r"\b(war|wars|warfare|campaign|operation|invasion|battle|siege|conquest|rebellion|revolt|uprising|"
                      r"insurgency|theat(er|re) of war|front|conflict|offensive|revolution|expedition|intervention|crusade|"
                      r"war phase|raid|occupation)\b", re.I)
MOVED = {"battle", "siege"}         # the kinds of event an army moves between
MOVE_KM, MOVE_DAYS, MARCH_KM, BASE_KM = 900, 550, 30, 150
SLACK = {"day": 0, "month": 30, "year": 365, "decade": 3650, "century": 36500}   # (days a date may be off by)


def fetch():
    if os.path.exists(RAW):
        return json.load(open(RAW))
    ev = [r["wikidata"] for r in csv.DictReader(open(EVENTS)) if r["wikidata"]]
    seen, frontier, edges, info = set(), set(ev), set(), {}
    for level in range(LEVELS):
        todo = sorted(frontier - seen); seen |= frontier; frontier = set()
        for k in range(0, len(todo), 400):
            vals = " ".join(f"wd:{q}" for q in todo[k:k + 400])
            q = f"""PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?e ?p ?pl ?s ?t ?cl WHERE {{ VALUES ?e {{ {vals} }} ?e wdt:P361 ?p .
 OPTIONAL {{ ?p rdfs:label ?pl FILTER(LANG(?pl)="en") }} OPTIONAL {{ ?p wdt:P580 ?s }} OPTIONAL {{ ?p wdt:P582 ?t }}
 OPTIONAL {{ ?p wdt:P31 ?c . ?c rdfs:label ?cl FILTER(LANG(?cl)="en") }} }}"""
            for b in fp.sparql(q, fp.QLEVER):
                e, p = (b[k]["value"].rsplit("/", 1)[1] for k in ("e", "p"))
                edges.add((e, p))
                d = info.setdefault(p, {"label": None, "start": None, "end": None, "classes": []})
                d["label"] = d["label"] or b.get("pl", {}).get("value")
                d["start"] = d["start"] or b.get("s", {}).get("value")
                d["end"] = d["end"] or b.get("t", {}).get("value")
                if "cl" in b and b["cl"]["value"] not in d["classes"]: d["classes"].append(b["cl"]["value"])
                frontier.add(p)
        print(f"  level {level}: {len(todo)} asked, {len(edges)} links", flush=True)
    got = {"edges": sorted(edges), "info": info}
    json.dump(got, open(RAW, "w"))
    return got


def year(t):
    m = re.match(r"(-?\d+)", t or "")
    return int(m.group(1)) if m else None


def day(s):     # "1815-06-18", "-0217", "1415-06": a number to compare (a date cut to its year or month: the middle of it)
    m = re.match(r"(-?\d+)(?:-(\d\d))?(?:-(\d\d))?", s)
    return int(m.group(1)) * 372 + (int(m.group(2) or 7) - 1) * 31 + int(m.group(3) or (15 if m.group(2) else 1))


def km(a, b):
    la1, la2, dl = math.radians(a[1]), math.radians(b[1]), math.radians(b[0] - a[0])
    return 6371 * math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(dl))))


def main():
    got = fetch()
    rows = list(csv.DictReader(open(EVENTS)))
    row_of = {r["wikidata"]: i for i, r in enumerate(rows) if r["wikidata"]}
    info = got["info"]
    war = {q for q, d in info.items() if d["label"] and any(MILITARY.search(c) for c in d["classes"])}
    up = {}
    for e, p in got["edges"]:
        if e != p: up.setdefault(e, []).append(p)

    def ancestors(q, seen=None):          # every war q is part of, however far up
        seen = set() if seen is None else seen
        for p in up.get(q, []):
            if p not in seen: seen.add(p); ancestors(p, seen)
        return seen

    def wars_over(q):                     # the nearest wars above q (through groups that are none)
        out, todo, seen = set(), list(up.get(q, [])), set()
        while todo:
            p = todo.pop()
            if p in seen: continue
            seen.add(p)
            if p in war: out.add(p)
            else: todo += up.get(p, [])
        return out

    # each event's group, each group's parent: the most specific of those over it
    size = {}
    for q in row_of:
        for a in ancestors(q):
            size[a] = size.get(a, 0) + 1

    def pick(cands):
        cands = [c for c in cands if c in war]
        if not cands: return None
        inner = [c for c in cands if not any(c in ancestors(o) for o in cands if o != c)]   # (none of the others inside it)
        return min(inner or cands, key=lambda c: (size.get(c, 0), c))

    group_of = {q: pick(wars_over(q)) for q in row_of}
    parent_of, todo = {}, {g for g in group_of.values() if g}
    while todo:
        g = todo.pop()
        if g in parent_of: continue
        p = pick(wars_over(g))
        if p and g in ancestors(p): p = None          # (a loop in the data)
        parent_of[g] = p
        if p: todo.add(p)

    members = {}
    for q, g in group_of.items():
        if g: members.setdefault(g, []).append(row_of[q])
    total = {}                            # (events in a group and its parts)
    for g in parent_of:
        n, h, seen = len(members.get(g, [])), g, set()
        total[g] = total.get(g, 0) + n
        while parent_of.get(h) and h not in seen:
            seen.add(h); h = parent_of[h]; total[h] = total.get(h, 0) + n
    keep = {g for g in parent_of if total.get(g, 0) >= 2}

    # a dropped group's events go up to the next kept one
    def kept_up(g):
        while g and g not in keep: g = parent_of.get(g)
        return g
    final = {}
    for g, evs in members.items():
        k = kept_up(g)
        if k: final.setdefault(k, []).extend(evs)

    order = sorted(keep, key=lambda g: (year(info[g]["start"]) if info[g]["start"] else 9999, info[g]["label"]))
    index = {g: i for i, g in enumerate(order)}
    pt = lambda i: (float(rows[i]["lon"]), float(rows[i]["lat"]))
    groups = []
    for g in order:
        evs = sorted(final.get(g, []), key=lambda i: (day(rows[i]["date"]), -int(rows[i]["wikipedias"] or 0)))
        moves, threads = [], []          # threads: the last battle of each
        fine = sum(rows[i]["precision"] in ("day", "month") for i in evs) * 2 >= max(3, len(evs))
        for i in evs:
            if rows[i]["kind"] not in MOVED or (fine and rows[i]["precision"] not in ("day", "month")): continue
            best, bd = None, MOVE_KM
            for t, last in enumerate(threads):
                dt = day(rows[i]["date"]) - day(rows[last]["date"])
                if dt > MOVE_DAYS: continue
                d, reach = km(pt(last), pt(i)), BASE_KM + MARCH_KM * (dt + SLACK.get(rows[i]["precision"], 0) + SLACK.get(rows[last]["precision"], 0))
                if 1 < d < bd and d <= reach: best, bd = t, d
            if best is None: threads.append(i)
            else: moves.append([threads[best], i]); threads[best] = i
        yrs = [year(rows[i]["date"]) for i in evs]
        d = info[g]
        groups.append({"id": g, "name": d["label"], "kind": next(c for c in d["classes"] if MILITARY.search(c)),
                       "from": year(d["start"]) if d["start"] else (min(yrs) if yrs else None),
                       "to": year(d["end"]) if d["end"] else (max(yrs) if yrs else None),
                       "parent": index.get(kept_up(parent_of.get(g)), -1), "events": evs, "moves": moves})
    # a group's years without its own: its parts'
    for gi in reversed(range(len(groups))):
        G, p = groups[gi], groups[gi]["parent"]
        if p >= 0:
            P = groups[p]
            if G["from"] is not None and (P["from"] is None or G["from"] < P["from"]) and not info[P["id"]]["start"]: P["from"] = G["from"]
            if G["to"] is not None and (P["to"] is None or G["to"] > P["to"]) and not info[P["id"]]["end"]: P["to"] = G["to"]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write('{"groups": [\n' + ",\n".join(json.dumps(g, ensure_ascii=False, separators=(",", ":")) for g in groups) + "\n]}\n")
    n_ev = sum(len(g["events"]) for g in groups); n_mv = sum(len(g["moves"]) for g in groups)
    print(f"campaigns.json: {len(groups)} wars and campaigns ({sum(g['parent'] < 0 for g in groups)} at the top), {n_ev} events in them, {n_mv} moves")


if __name__ == "__main__":
    main()
