"""THE LIGHT FILES: smaller, readable copies of the line layers -- data/world.txt, rivers.txt, transport.txt (and
roads.txt, pipelines.txt, bio.txt, history.txt) -- for a page that needs the shapes but not every bend. The originals (full/*.topo.json) stay as they are.

    .venv/bin/python build/lite.py [HEIGHT_KM [TRI_KM2 [NAME ...]]]     # full/*.topo.json -> data/*.txt (defaults 1, 25, all); then build/small.py

FEWER POINTS. A point is left out when it adds little to the shape: where the line hardly turns, the triangle it makes
with its two neighbours is small. Visvalingam-Whyatt: the point of the smallest triangle goes first, its neighbours'
triangles are measured again, until every point left makes a triangle of TRI_KM2 or more (km2 on the ground) -- but a
point standing more than HEIGHT_KM off the line between its neighbours always stays: a sharp turn, a fjord's end, a
cape, a border's corner keep their shape (a long thin spike makes a small triangle; the height tells). Each ARC is
simplified once and its two ends always stay, so the file is still a topology: a border is the one line both countries
use, and the coast still meets it exactly. A closed arc (a lake) keeps four points or more.

THE FORMAT. Text, one thing a line, no name repeated:

    # comments
    grid 0.0025 -180 -90                 the grid: a point is (x * 0.0025 - 180, y * 0.0025 - 90)
    @arcs                                one shared line a line: x y dx dy dx dy ... (the first point, then steps)
    @countries polygon                   an object: its rows in CSV, the first one the header
    ~id,iso,name,population#,arcs        (~id: the geometry's own id) a column's suffix: # a number, [] a list ("a|b"), []# a list of numbers,
    SK,SK,Slovakia,5400000,12 -14 15;16      ? yes/no (1/0), {} JSON; an empty field: none
    @rivers line                         a GROUPED object: one row a river -- what all its pieces share --
    river,name,wikidata,...                  and @rivers.pieces: one row a piece, its arcs and only what differs
    @rivers.pieces                           from its river (empty: the river's)
    river,length_km#,arcs

The arcs of a row: polygon -- rings split by ";" (the outer one first), polygons by "|"; line -- lines split by ";";
an arc is its index in @arcs, -1 - index when it is followed backwards (TopoJSON's ~index).

A file made partly of another's lines (bio.txt, history.txt -- of world.txt's) says so: "uses world"; an arc of it may
then take a stretch of one of world.txt's: in its line "dw:k:dk" -- points k to k + dk of world's arc w (backwards when
dk < 0), w the last such stretch's (in the file, from 0) plus dw -- and the steps after it go on from its last point
(as do those of a line that starts with one).
index.html reads it into typed arrays (parseLite; the map loads only these, never full/*.topo.json).
"""
import os, sys, csv, io, json, heapq, collections
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FILES = ["world", "rivers", "transport", "roads", "bio", "history"]
APART = {"transport": ["pipelines"]}     # (objects in a file of their own, with only their arcs: the page loads it when shown)
SHARE = ["bio", "history"]               # (their lines run much of their way along the world's -- its coast, lake shores,
                                         #  borders: those stretches they take from world.txt's points, see share())
MIN_REF = 2                              # (a stretch of fewer of world.txt's points is cheaper written out)
GROUP = {"rivers": "river", "motorways": "network", "railways": "network", "pipelines": "network"}   # (pieces of one thing)
KM_LAT = 110.57


def keep_points(ll, height_km, tri_km2, fixed=None):
    """Visvalingam-Whyatt on one arc (longitude/latitude), sharp points kept (and those `fixed` says) -> the indices kept"""
    n = len(ll)
    closed = n > 3 and ll[0, 0] == ll[-1, 0] and ll[0, 1] == ll[-1, 1]
    floor = 4 if closed else 2
    if n <= floor:
        return np.arange(n)
    lat = np.radians(ll[:, 1])
    xy = np.column_stack((ll[:, 0] * KM_LAT * np.cos(lat), ll[:, 1] * KM_LAT))
    def measure(a, b, c):                                   # -> (the triangle's area, b's height over the line a-c)
        ar = abs((xy[b, 0] - xy[a, 0]) * (xy[c, 1] - xy[a, 1]) - (xy[c, 0] - xy[a, 0]) * (xy[b, 1] - xy[a, 1])) / 2
        base = float(np.hypot(*(xy[c] - xy[a])))
        return ar, (2 * ar / base if base > 1e-9 else float(np.hypot(*(xy[b] - xy[a]))))
    prev, nxt = list(range(-1, n - 1)), list(range(1, n + 1))
    alive = np.ones(n, bool)
    cur, heap = {}, []
    for i in range(1, n - 1):
        cur[i] = measure(i - 1, i, i + 1)
        if fixed is None or not fixed[i]:
            heap.append((cur[i][0], i))
    heapq.heapify(heap)
    left = n
    while heap and left > floor:
        a, i = heapq.heappop(heap)
        if not alive[i] or cur.get(i, (None,))[0] != a:
            continue
        if a >= tri_km2:
            break
        if cur[i][1] > height_km:                            # (a sharp point: stays, unless a neighbour's going changes it)
            continue
        alive[i] = False; left -= 1
        p, q = prev[i], nxt[i]
        nxt[p], prev[q] = q, p
        for j in (p, q):
            if 0 < j < n - 1 and alive[j] and (fixed is None or not fixed[j]):
                ar, h = measure(prev[j], j, nxt[j])
                cur[j] = (max(ar, a), h)                     # (never smaller than the one just dropped: the order holds)
                heapq.heappush(heap, (cur[j][0], j))
    return np.flatnonzero(alive)


def column_type(values):
    """a column's suffix from its values: # numbers, [] / []# lists, ? yes/no, {} anything else structured"""
    vs = [v for v in values if v is not None]
    if not vs:
        return ""
    if all(isinstance(v, bool) for v in vs):
        return "?"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vs):
        return "#"
    if all(isinstance(v, list) for v in vs):
        items = [x for v in vs for x in v]
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in items):
            return "[]#"
        if all(isinstance(x, str) and "|" not in x for x in items):
            return "[]"
        return "{}"
    if all(isinstance(v, str) for v in vs):
        return ""
    return "{}"


def cell(v, t):
    if v is None:
        return ""
    if t == "?":
        return "1" if v else "0"
    if t in ("[]", "[]#"):
        return "|".join(str(x) for x in v)
    if t == "{}":
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return str(v)


def arcs_text(g):
    """a geometry's arcs as text: polygon rings ';' polygons '|'; lines ';' (signed indices as in TopoJSON)"""
    t, a = g["type"], g.get("arcs")
    if a is None:
        return ""
    if t == "Polygon":
        a = [a]
    elif t == "LineString":
        a = [a]
    if t in ("Polygon", "MultiPolygon"):
        return "|".join(";".join(" ".join(str(x) for x in r) for r in p) for p in a)
    return ";".join(" ".join(str(x) for x in line) for line in a)


def table(rows, cols, types):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow([c + types[c] for c in cols])
    for r in rows:
        w.writerow([cell(r.get(c), types[c]) if c != "arcs" else r["arcs"] for c in cols])
    return out.getvalue()


def write_object(name, o):
    """an object's section(s): one table -- or, grouped (GROUP), a table of the things and one of their pieces"""
    geoms = o["geometries"]
    kind = "polygon" if any(g["type"] in ("Polygon", "MultiPolygon") for g in geoms) else "line"
    rows = []
    for g in geoms:
        r = dict(g.get("properties") or {})
        if "id" in g:
            r["~id"] = g["id"]
        r["arcs"] = arcs_text(g)
        rows.append(r)
    keys = list(dict.fromkeys(k for r in sorted(rows, key=len, reverse=True) for k in r if k != "arcs"))   # (the fullest row's order first)
    if "~id" in keys:
        keys.remove("~id"); keys.insert(0, "~id")
    gk = GROUP.get(name)
    if not gk:
        types = {k: column_type([r.get(k) for r in rows]) for k in keys}; types["arcs"] = ""
        return f"@{name} {kind}\n" + table(rows, keys + ["arcs"], types)
    groups = collections.OrderedDict()
    for r in rows:
        groups.setdefault(r.get(gk), []).append(r)
    head, pieces = [], []
    for k, rs in groups.items():                             # (a thing: each value its pieces have most)
        h = {gk: k}
        for c in keys:
            if c != gk:
                h[c] = collections.Counter(json.dumps(r.get(c), sort_keys=True) for r in rs).most_common(1)[0][0]
                h[c] = json.loads(h[c])
        head.append(h)
        for r in rs:                                         # (a piece: what differs from its thing, and its arcs)
            pieces.append({gk: k, "arcs": r["arcs"], **{c: r.get(c) for c in keys if c != gk and r.get(c) != h[c]}})
    differ = [c for c in keys if c != gk and any(c in p for p in pieces)]
    types = {k: column_type([r.get(k) for r in rows]) for k in keys}; types["arcs"] = ""
    return (f"@{name} {kind}\n" + table(head, [gk] + [c for c in keys if c != gk], types) +
            f"@{name}.pieces\n" + table(pieces, [gk] + differ + ["arcs"], types))


def renumber(objects, arc_lines):
    """the objects with only the arcs they use, numbered afresh -> (objects, arc lines)"""
    used = set()
    def walk(a):
        for x in a:
            if isinstance(x, list): walk(x)
            else: used.add(x if x >= 0 else ~x)
    for o in objects.values():
        for g in o["geometries"]:
            walk(g.get("arcs") or [])
    old = sorted(used); new = {k: i for i, k in enumerate(old)}
    def remap(a): return [remap(x) if isinstance(x, list) else (new[x] if x >= 0 else ~new[~x]) for x in a]
    objects = {k: {**o, "geometries": [{**g, "arcs": remap(g["arcs"])} if g.get("arcs") is not None else g for g in o["geometries"]]}
               for k, o in objects.items()}
    return objects, [arc_lines[k] for k in old]


def load(name):
    """full/NAME.topo.json, its arcs as absolute grid points (numpy) -> the topology, or None"""
    src = os.path.join(ROOT, "full", name + ".topo.json")
    if not os.path.exists(src):
        return None
    t = json.load(open(src))
    t["arcs"] = [np.cumsum(np.array(a, dtype=np.int64), axis=0) for a in t["arcs"]]
    return t


def share(base, kept, t):
    """THE SHARED STRETCHES: where an arc of t runs point for point along one of base's (the coast, a lake's shore, a
    border), it takes that stretch from base's light points (kept: the indices lighten() kept of each of its arcs) --
    one line, the two maps meet. -> for each arc of t its stretches (i, j, w, a0, a1): its points i to j are base's arc
    w's, of which the light ones a0 to a1"""
    BT = [list(map(tuple, a.tolist())) for a in base["arcs"]]
    at = collections.defaultdict(list)
    for w, a in enumerate(BT):
        for k, p in enumerate(a):
            at[p].append((w, k))
    out, n_runs, n_pts = [], 0, 0
    for a in t["arcs"]:
        P = list(map(tuple, a.tolist())); n = len(P); i = 0; rs = []
        while i < n - 1:
            best = None
            for w, k in at.get(P[i], ()):
                bw = BT[w]
                for d in (1, -1):
                    j, kk = i, k
                    while j + 1 < n and 0 <= kk + d < len(bw) and P[j + 1] == bw[kk + d]:
                        j += 1; kk += d
                    if j > i and (best is None or j > best[1]):
                        best = (i, j, w, k, kk)
            if best is None:
                i += 1
                continue
            i, j, w, k0, k1 = best
            K = kept[w]
            if k0 < k1:
                a0, a1 = np.searchsorted(K, k0), np.searchsorted(K, k1, "right") - 1
            else:
                a0, a1 = np.searchsorted(K, k0, "right") - 1, np.searchsorted(K, k1)
            if (int(a1) - int(a0)) * (1 if k0 < k1 else -1) + 1 >= MIN_REF:     # (how many of its light points)
                rs.append((i, j, w, int(a0), int(a1))); n_runs += 1; n_pts += j - i + 1
            i = j
        out.append(rs)
    print(f"{n_runs:,} stretches ({n_pts:,} points) along {base.get('name', 'world')}'s lines", flush=True)
    return out


def river_ends():
    """the grid points where the rivers end (full/rivers.topo.json): a mouth is also a point of the coast
    (build/rivernet.py), kept there so river and coast still meet"""
    path = os.path.join(ROOT, "full/rivers.topo.json")
    if not os.path.exists(path):
        return set()
    t, ends = json.load(open(path)), set()
    for arc in t["arcs"]:
        q = np.cumsum(np.array(arc, dtype=np.int64), axis=0)
        ends.add(tuple(q[0].tolist())); ends.add(tuple(q[-1].tolist()))
    return ends


def lighten(name, height_km, tri_km2, base=None):
    """full/NAME.topo.json -> data/NAME.txt; base: (its name, its topology, the indices kept of its arcs) when NAME
    takes stretches of it (share()) -> the indices kept of each arc"""
    src = os.path.join(ROOT, "full", name + ".topo.json")
    t = load(name)
    if t is None:
        return None
    scale, translate = t["transform"]["scale"], t["transform"]["translate"]
    sc, tr = np.array(scale), np.array(translate)
    before = after = 0
    lines = []
    mouths = river_ends() if name == "world" else set()
    stretches = share(base[1], base[2], t) if base else [[] for _ in t["arcs"]]
    kept, last_w = [], 0
    for q, rs in zip(t["arcs"], stretches):
        k = keep_points(q * sc + tr, height_km, tri_km2, np.array([tuple(p) in mouths for p in q.tolist()]) if mouths else None)
        before += len(q)
        if not rs:
            kept.append(k); after += len(k)
            q = q[k]
            d = np.vstack((q[:1], np.diff(q, axis=0)))
            lines.append(" ".join(str(int(v)) for v in d.ravel()))
            continue
        toks, last, pos = [], None, 0                     # (its own points between the stretches, lightened apart: from
        light = lambda w, a: base[1]["arcs"][w][base[2][w][a]]    #  where the last stretch left the world's light line to
        def own(seg, upto):                                       #  where the next joins it; its ends exact)
            nonlocal last, after
            pts = seg[keep_points(seg * sc + tr, height_km, tri_km2)].tolist()
            for p in pts[:len(pts) - (not upto)]:
                if last is None:
                    toks.append(f"{p[0]} {p[1]}")
                elif p != last:
                    toks.append(f"{p[0] - last[0]} {p[1] - last[1]}")
                else:
                    continue
                last = p; after += 1
        start = q[:1]
        for i, j, w, a0, a1 in rs:
            own(np.vstack((start, q[pos + 1:i], light(w, a0)[None])) if i else start, not i)
            toks.append(f"{w - last_w}:{a0}:{a1 - a0}"); last, last_w = light(w, a1).tolist(), w
            pos, start = j, light(w, a1)[None]
        own(np.vstack((start, q[pos + 1:] if pos < len(q) - 1 else q[-1:])), True)
        kept.append(None)
        lines.append(" ".join(toks))
    apart = APART.get(name, [])
    files = [(name, {k: o for k, o in t["objects"].items() if k not in apart})] + [(k, {k: t["objects"][k]}) for k in apart if k in t["objects"]]
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    for fname, objects in files:
        arcs = lines
        if apart:
            objects, arcs = renumber(objects, lines)
        what = f"a light copy of full/{name}.topo.json" + (f" ({', '.join(objects)})" if apart else "")
        out = [f"# {fname}: {what} (build/lite.py: points off by less than {height_km:g} km and in "
               f"triangles under {tri_km2:g} km2 left out; the format: build/lite.py)",
               f"grid {scale[0]:g} {translate[0]:g} {translate[1]:g}", *([f"uses {base[0]}"] if base else []),
               "@arcs", *arcs]
        text = "\n".join(out) + "\n" + "".join(write_object(k, o) for k, o in objects.items())
        dest = os.path.join(ROOT, "data", fname + ".txt")
        open(dest, "w", encoding="utf-8").write(text)
        print(f"{dest}: {len(arcs):,} arcs, {os.path.getsize(dest) / 2**20:.1f} MB", flush=True)
    print(f"{name}: {before:,} -> {after:,} points ({100 * after / before:.0f} %), {os.path.getsize(src) / 2**20:.1f} MB before", flush=True)
    return t, kept


if __name__ == "__main__":
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    a = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    world = None
    for f in sys.argv[3:] or FILES:                          # (only some: not one made of the world's lines without it)
        r = lighten(f, h, a, ("world", *world) if f in SHARE and world else None)
        if f == "world":
            world = r
