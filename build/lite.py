"""THE LIGHT FILES: smaller, readable copies of the line layers -- data/lite/world.txt, rivers.txt, transport.txt (and
bio.txt, history.txt) -- for a page that needs the shapes but not every bend. The originals (data/*.topo.json) stay as they are.

    .venv/bin/python build/lite.py [HEIGHT_KM [TRI_KM2]]     # data/*.topo.json -> data/lite/*.txt (defaults 1 and 25)

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
index.html?lite reads it back into the topology the page draws.
"""
import os, sys, csv, io, json, heapq, collections
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FILES = ["world", "rivers", "transport", "bio", "history"]
GROUP = {"rivers": "river", "motorways": "network", "railways": "network", "pipelines": "network"}   # (pieces of one thing)
KM_LAT = 110.57


def keep_points(ll, height_km, tri_km2):
    """Visvalingam-Whyatt on one arc (longitude/latitude), sharp points kept -> the indices kept"""
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
        cur[i] = measure(i - 1, i, i + 1); heap.append((cur[i][0], i))
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
            if 0 < j < n - 1 and alive[j]:
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


def lighten(name, height_km, tri_km2):
    src = os.path.join(ROOT, "data", name + ".topo.json")
    if not os.path.exists(src):
        return
    t = json.load(open(src))
    scale, translate = t["transform"]["scale"], t["transform"]["translate"]
    sc, tr = np.array(scale), np.array(translate)
    before = after = 0
    lines = []
    for arc in t["arcs"]:
        q = np.cumsum(np.array(arc, dtype=np.int64), axis=0)
        k = keep_points(q * sc + tr, height_km, tri_km2)
        q = q[k]
        d = np.vstack((q[:1], np.diff(q, axis=0)))
        lines.append(" ".join(str(int(v)) for v in d.ravel()))
        before += len(arc); after += len(k)
    out = [f"# {name}: a light copy of data/{name}.topo.json (build/lite.py: points off by less than {height_km:g} km and in "
           f"triangles under {tri_km2:g} km2 left out; the format: build/lite.py)",
           f"grid {scale[0]:g} {translate[0]:g} {translate[1]:g}", "@arcs", *lines]
    text = "\n".join(out) + "\n" + "".join(write_object(k, o) for k, o in t["objects"].items())
    os.makedirs(os.path.join(ROOT, "data/lite"), exist_ok=True)
    dest = os.path.join(ROOT, "data/lite", name + ".txt")
    open(dest, "w", encoding="utf-8").write(text)
    print(f"{dest}: {before:,} -> {after:,} points ({100 * after / before:.0f} %), "
          f"{os.path.getsize(src) / 2**20:.1f} -> {os.path.getsize(dest) / 2**20:.1f} MB", flush=True)


if __name__ == "__main__":
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    a = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    for f in FILES:
        lighten(f, h, a)
