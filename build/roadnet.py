"""STAGE 7b -- THE ROAD NETWORK: the main lines as tracked (build/transport.py: every carriageway and track OSM maps,
full/transport.tracked.topo.json) made into one network of single lines, and ranked -> full/transport.topo.json.

    .venv/bin/python build/roadnet.py            (after transport.py; then build/lite.py)

ONE LINE FOR ONE ROAD. A motorway is two carriageways in OSM, a railway as many tracks: each its own way, parallel, a
few metres to a few hundred apart, and they meet only at the road's ends if at all (they are not even of one network).
Drawn, that is two lines where there is one road. So the lines go one by one, the most important first (a high-speed
railway; a motorway before a trunk road), then the longest: a stretch closer than SEP_KM to a line kept before is the
same road -- dropped where that runs on for PARALLEL_KM, or at an end that does not reach the other line. The rest is
kept (a stretch of MIN_RUN_KM or more: the carriageways part through a mountain), its cut ends carried onto the line
it ran beside. Two roads side by side that close (a high-speed line beside the old one, a motorway along a trunk road)
are one line too: at the map's closest, 100 m a pixel, they would be a pixel or two apart. (A line whose way turns
back on itself -- the two carriageways joined where they meet at a road's end -- is first cut at that turn.)
Pipelines side by side are pipelines side by side: they are only joined.

ROUTES, NOT FIELDS. Of the pipelines only the long routes are kept: an offshore field is a star of lines a few km
long from its wells to a platform (the Persian Gulf's are dozens), a terminal a tangle of short branches to its
tanks. So a dead end -- the arcs from a line's end to the first junction -- shorter than SPUR_KM goes, again and again
(the star's spokes, then the platform's own line if that is short too); a network then under MIN_NET_KM goes whole.
A field's flowlines also run into each other, a knot of short loops no dead end undoes: first a short arc of a loop
(one that is not the only way between its ends) goes, one a loop at a time and the shortest first, until no short
arc is left on a loop -- what was connected stays connected, and the knot is a star whose spokes then go.

JOINS. A road that meets another ends ON it: an end within JOIN_KM of another line (the slip roads between them are
not in the map) is carried onto that line, and that line is cut there -- a junction is the end of every arc that
meets it, so the join stays exact however far the map simplifies (an arc's ends are always kept). Before that, two
ends that face each other across a gap of up to GAP_KM -- a line's ways in OSM are not all tagged as it is, at a
station, on a bridge -- are joined end to end, so a line is not drawn in pieces.

RANK. Each arc is in one of three tiers (the map draws the first from afar, the last only close in), by the road it is
part of: not by its tags -- they are too uneven across the world (India's railways have no name, no number, no speed)
-- but by its STROKE, the way a driver goes on through the junctions: at each, the two arcs that run on most nearly
straight (turning less than TURN_DEG; an arc of the same road number, less than REF_TURN_DEG) are one way through,
and a stroke's length ranks it: TIERS km for the first and the second tier. A high-speed railway is in the first tier
whatever its length; a pipeline is ranked by its network's length.
"""
import os, sys, json, time, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, geo
from export_geojson import decode, ring
from rivernet import R, xyz, km, samples, Index, onto

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TRACKED = os.path.join(ROOT, "full/transport.tracked.topo.json")
OUT = os.path.join(ROOT, "full/transport.topo.json")
SEP_KM = 0.6         # a stretch closer than this to a line kept before is the same road
PARALLEL_KM = 2.0    # ...dropped where it runs so this long (a road crossing at 30 degrees is that near for 2.4 km)
TOUCH_KM = 0.3       # an end this near the line it ran beside reaches it
MIN_RUN_KM = 1.0     # a stretch of a line not beside one kept: kept if this long
JOIN_KM = {"motorways": 1.5, "railways": 1.0, "pipelines": 0.5}   # a free end this near another line meets it
GAP_KM = {"motorways": 3.0, "railways": 5.0, "pipelines": 5.0}    # two free ends facing each other this near: one line
GAP_DEG = 35.0       # ...each running on towards the other within this
STEP_KM = 0.2        # the samples along a line, for the distances
TURN_KM = 0.3        # a way that turns back (120 degrees or more between this far before and after a point): cut there
EPS_KM = 1.0         # the arcs' detail (coarser than the coast's)
DIR_KM = 1.5         # an arc's direction at a junction: towards its point this far along
TURN_DEG = 45.0      # a stroke goes on through a junction along an arc that turns less than this...
REF_TURN_DEG = 75.0  # ...or, of the same road number, this
TIERS = {"motorways": (400, 100), "railways": (500, 150), "pipelines": (1000, 200)}   # km for the first, the second tier
SPUR_KM = 20.0       # a pipeline's dead end shorter than this (from its end to a junction) goes
MIN_NET_KM = 100.0   # ...and a pipeline network then shorter than this
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


pkey = lambda q: (round(float(q[0]), 7), round(float(q[1]), 7))


def turns(c):
    """a line cut where it turns back on itself (a road's two carriageways joined at its end) -> [lines]"""
    if len(c) < 3:
        return [c]
    P = xyz(c)
    along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] * R
    b = np.clip(np.searchsorted(along, along - TURN_KM, side="right") - 1, 0, len(c) - 1)
    f = np.clip(np.searchsorted(along, along + TURN_KM), 0, len(c) - 1)
    u, v = P - P[b], P[f] - P
    nu, nv = np.linalg.norm(u, axis=1), np.linalg.norm(v, axis=1)
    ok = (nu > 0) & (nv > 0)
    cos = np.ones(len(c))
    cos[ok] = (u[ok] * v[ok]).sum(1) / (nu[ok] * nv[ok])
    sharp = (cos < -0.5) & ok
    sharp[0] = sharp[-1] = False
    if not sharp.any():
        return [c]
    cuts, i = [], 1                                          # (of each run of sharp points, the sharpest)
    while i < len(c) - 1:
        if not sharp[i]:
            i += 1; continue
        j = i
        while j < len(c) - 1 and sharp[j]:
            j += 1
        cuts.append(i + int(np.argmin(cos[i:j]))); i = j
    return [c[a:b + 1] for a, b in zip([0] + cuts, cuts + [len(c) - 1]) if b > a]


def collapse(lines, same, stub):
    """the lines (most important first) against those kept before them: the stretches beside one dropped (`same`:
    roads side by side are one road), the cut ends carried onto it -> kept [(lon/lat, properties)], the points to
    put into each {line: [(segment, along, point)]}, the index of their samples, the points carried onto a line"""
    idx, kept, inserts, attached, stats = Index(SEP_KM / R), [], collections.defaultdict(list), set(), collections.Counter()

    def snap(k, p):                                          # the point on the kept line nearest, put into it
        L = int(idx.line[k]); s, t, q = onto(kept[L][0], int(idx.seg[k]), p)
        inserts[L].append((s, t, q)); attached.add(pkey(q)); return q

    def keep(pts, p):
        pts = pts[np.r_[True, np.any(np.abs(np.diff(pts, axis=0)) > 1e-9, axis=1)]]
        if len(pts) < 2:
            return
        L = len(kept); kept.append((pts, p))
        S, j, _, _ = samples(pts, STEP_KM); idx.add(L, S, j)

    for c, p in lines:
        if not same:
            keep(c, p); continue
        S, j, t, along = samples(c, STEP_KM)
        d, near = idx.near(S)
        for e in (0, len(S) - 1):                            # (an end ON a kept line -- a way on from its end, a branch
            if d[e] < 1e-3:                                  #  off it --: near that point it is not beside the line)
                at = (near >= 0) & (np.linalg.norm(idx.xyz[np.maximum(near, 0)] - S[e], axis=1) * R < 1.5 * STEP_KM)
                d[at] = np.inf
        cov, n = d < SEP_KM, len(S)
        if cov.all():
            stats["covered"] += 1; continue
        if not cov.any():                                    # (however short: a tunnel, a bridge, a station named as
            keep(c, p); continue                             #  itself is a piece of its line, and its gap if left out)
        # the runs, beside a kept line or not; one beside it dropped where it is long, or at an end that does not reach it
        edges = np.flatnonzero(np.diff(cov.astype(np.int8))) + 1
        runs = [(a, b - 1) for a, b in zip(np.r_[0, edges], np.r_[edges, n])]
        # (an end that crosses a line and stops less than `stub` km beyond it: it ends ON that line, where it crossed)
        crossed = lambda r: cov[r[0]] and d[r[0]:r[1] + 1].min() < TOUCH_KM
        lead = int(len(runs) > 2 and not cov[0] and along[runs[0][1]] < stub and crossed(runs[1]))
        trail = int(len(runs) > 2 + lead and not cov[-1] and along[-1] - along[runs[-1][0]] < stub and crossed(runs[-2]))
        runs = runs[lead:len(runs) - trail]
        first, last = runs[0][0], runs[-1][1]
        def drop(a, b):
            if not cov[a]:
                return False
            return (along[b] - along[a] >= PARALLEL_KM or (a == first and not lead and d[a] >= TOUCH_KM) or
                    (b == last and not trail and d[b] >= TOUCH_KM))
        group, groups = [], []
        for a, b in runs:
            if drop(a, b):
                if group: groups.append(group); group = []
            else:
                group.append((a, b))
        if group: groups.append(group)
        for g in groups:
            a, b = g[0][0], g[-1][1]
            if sum(along[y] - along[x] for x, y in g if not cov[x]) < MIN_RUN_KM:
                stats["short"] += 1; continue
            # the piece from sample lo to sample hi: a cut end begins on the sample before it, an end that reaches a
            # line on its sample nearest that line (not beyond it, where it crossed over); either carried onto the line
            lo, hi = (a - 1 if a > first else a), (b + 1 if b < last else b)
            if a == first and cov[a]:
                lo = a + int(np.argmin(d[a:g[0][1] + 1]))
            if b == last and cov[b]:
                hi = g[-1][0] + int(np.argmin(d[g[-1][0]:b + 1]))
            pts = np.array([snap(near[lo], S[lo]) if cov[lo] else c[0]] + [c[v] for v in range(j[lo] + 1, j[hi] + 1)] +
                           [snap(near[hi], S[hi]) if cov[hi] else c[-1]])
            stats["cut"] += (a > first) + (b < last); stats["crossed"] += (lead and a == first) + (trail and b == last)
            keep(pts, p)
    if same:
        log(f"  kept {len(kept):,} lines ({stats['covered']:,} the same road as a line kept, {stats['short']:,} pieces too short, {stats['cut']:,} ends carried onto a line, {stats['crossed']:,} cut where they crossed one)")
    return kept, inserts, idx, attached


def heading(c, last):
    """a line's direction out of its end (from its point DIR_KM back), in the tangent plane there"""
    P = xyz(c[::-1] if last else c)
    along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] * R
    v = P[0] - P[min(np.searchsorted(along, DIR_KM), len(P) - 1)]
    v = v - P[0] * (v @ P[0]); nv = np.linalg.norm(v)
    return v / nv if nv > 0 else None


def gaps(kept, attached, most):
    """two free ends that face each other across a gap of up to `most` km (OSM's ways of a line not all tagged as it:
    a station, a bridge), each running on towards the other within GAP_DEG: joined end to end -> {line: (point before
    its start, point after its end)}"""
    from scipy.spatial import cKDTree
    n = collections.Counter(pkey(q) for c, _ in kept for q in (c[0], c[-1]))
    ends = [(L, last) for L, (c, _) in enumerate(kept) for last in (False, True)
            if n[pkey(c[-1] if last else c[0])] == 1 and pkey(c[-1] if last else c[0]) not in attached]
    if len(ends) < 2:
        return {}
    pt = lambda e: kept[e[0]][0][-1 if e[1] else 0]
    P = xyz(np.array([pt(e) for e in ends]))
    H = [heading(kept[L][0], last) for L, last in ends]
    cos = np.cos(np.radians(GAP_DEG))
    pairs = []
    for a, b in cKDTree(P).query_pairs(most / R):
        if ends[a][0] == ends[b][0] or H[a] is None or H[b] is None:
            continue
        g = P[b] - P[a]; dist = np.linalg.norm(g)
        if dist == 0:
            continue
        g /= dist
        if H[a] @ g >= cos and H[b] @ -g >= cos:
            pairs.append((dist, a, b))
    ext, done, got = {}, set(), 0
    for _, a, b in sorted(pairs):
        if a in done or b in done:
            continue
        done |= {a, b}
        (L, last), r = ends[a], pt(ends[b])
        h, e = ext.get(L, (None, None)); ext[L] = (h, r) if last else (r, e)
        attached.add(pkey(r)); attached.add(pkey(pt(ends[a]))); got += 1
    log(f"  {got:,} gaps between two ends joined")
    return ext


def joins(kept, inserts, idx, attached, most, ext):
    """each free end (meeting nothing) onto the line nearest within `most` km -> {line: (point before its start,
    point after its end)}, added to `ext`; an end that comes to another's end, joined end to end"""
    n = collections.Counter(pkey(q) for c, _ in kept for q in (c[0], c[-1]))
    free = lambda q: n[pkey(q)] == 1 and pkey(q) not in attached
    got = 0
    for L, (c, _) in enumerate(kept):
        for last in (False, True):
            q = c[-1] if last else c[0]
            if not free(q):
                continue
            P = xyz(q[None])
            d, i = idx.near(P, reach=int(np.ceil((most + STEP_KM) / (SEP_KM))), skip=L)
            if not np.isfinite(d[0]) or d[0] >= most + STEP_KM:
                continue
            M = int(idx.line[i[0]]); m = kept[M][0]; s, t, r = onto(m, int(idx.seg[i[0]]), P[0])
            if km(np.array([q, r])) >= most:
                continue
            if (s == 0 and t == 0) or (s == len(m) - 2 and t == 1):
                r = m[0] if s == 0 and t == 0 else m[-1]    # (another's end: end to end, and that end no longer free)
            elif km(np.array([q, r])) > 1e-6:
                inserts[M].append((s, t, r))
            attached.add(pkey(r)); attached.add(pkey(q))
            if km(np.array([q, r])) <= 1e-6:
                continue                                     # (already on it: a point of that line)
            h, e = ext.get(L, (None, None)); ext[L] = (h, r) if last else (r, e); got += 1
    log(f"  {got:,} free ends carried onto the line they are at")
    return ext


def apply_inserts(kept, inserts, ext):
    out = []
    for L, (c, p) in enumerate(kept):
        ins = sorted(inserts.get(L, []), key=lambda x: (x[0], x[1]))
        if ins:
            parts, last = [], 0
            for s, t, q in ins:
                parts.append(c[last:s + 1]); parts.append(q[None]); last = s + 1
            parts.append(c[last:])
            c = np.vstack(parts)
        h, e = ext.get(L, (None, None))
        c = np.vstack([x for x in (None if h is None else h[None], c, None if e is None else e[None]) if x is not None])
        out.append((c, p))
    return out


def bridges(ends, live):
    """the arcs that are the only way between their ends (Tarjan's, without recursion), of the arcs live"""
    at = collections.defaultdict(list)
    for a in live:
        x, y = ends[a]; at[x].append(a); at[y].append(a)
    order, low, out = {}, {}, set()
    for root in at:
        if root in order:
            continue
        order[root] = low[root] = len(order)
        stack = [(root, None, iter(at[root]))]
        while stack:
            x, via, it = stack[-1]
            for a in it:
                if a == via:
                    continue
                y = ends[a][1] if ends[a][0] == x else ends[a][0]
                if y in order:
                    low[x] = min(low[x], order[y])
                else:
                    order[y] = low[y] = len(order); stack.append((y, a, iter(at[y]))); break
            else:
                stack.pop()
                if stack:
                    up = stack[-1][0]; low[up] = min(low[up], low[x])
                    if low[x] > order[up]:
                        out.add(via)
    return out


def knots(fine, length):
    """the short arcs of the pipelines' loops (ROUTES, NOT FIELDS) -> the arcs that go: of each set of arcs that are
    each on a loop with the others (what is left when the bridges are taken out, apart), the shortest short one, round
    after round"""
    ends = [(tuple(g[0]), tuple(g[-1])) for g in fine]
    live, dead = set(range(len(fine))), set()
    while True:
        br = bridges(ends, live)
        parent = {}
        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for a in live - br:
            x, y = ends[a]; parent[find(x)] = find(y)
        best = {}
        for a in live - br:
            if length[a] < SPUR_KM:
                c = find(ends[a][0])
                if c not in best or length[a] < length[best[c]]:
                    best[c] = a
        if not best:
            return dead
        dead |= set(best.values()); live -= set(best.values())


def spurs(fine, length, dead=()):
    """the pipelines' short dead ends (ROUTES, NOT FIELDS), the arcs dead already left out -> the arcs that go"""
    at = collections.defaultdict(set)                   # a node (an arc's end) -> the arcs at it
    ends = [(tuple(g[0]), tuple(g[-1])) for g in fine]
    for a, (x, y) in enumerate(ends):
        if a not in dead:
            at[x].add(a); at[y].add(a)
    dead, again = set(dead), True
    while again:
        again = False
        for x in list(at):
            if len(at[x]) != 1:
                continue
            chain, run, y, a = [], 0.0, x, next(iter(at[x]))
            while True:                                     # (from the end along the arcs through the nodes of two)
                chain.append(a); run += length[a]
                y = ends[a][1] if ends[a][0] == y else ends[a][0]
                if len(at[y]) != 2 or run >= SPUR_KM or y == x:
                    break
                a = next(b for b in at[y] if b != a)
            if run < SPUR_KM and len(at[y]) >= 3:
                for b in chain:
                    dead.add(b); at[ends[b][0]].discard(b); at[ends[b][1]].discard(b)
                again = True
    return dead


def refs(p):
    return frozenset(r.strip() for r in str(p.get("ref") or "").split(";") if r.strip())


def strokes(arcs, ref):
    """each arc's stroke length (km): at every junction the two arcs that go on most nearly straight are one way on"""
    q = config.QUANT_DEG
    length, at = [], collections.defaultdict(list)          # node -> [(arc, its end, its direction away from the node)]
    for a, g in enumerate(arcs):
        P = xyz(g * q - [180, 90])
        along = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))] * R
        length.append(along[-1])
        for end in (0, 1):
            node = P[0] if end == 0 else P[-1]
            far = P[min(np.searchsorted(along, DIR_KM), len(P) - 1)] if end == 0 else P[max(np.searchsorted(along, along[-1] - DIR_KM, side="right") - 1, 0)]
            v = far - node; v = v - node * (v @ node); nv = np.linalg.norm(v)
            at[tuple(g[0] if end == 0 else g[-1])].append((a, end, v / nv if nv > 0 else None))
    partner = {}
    for inc in at.values():
        if len(inc) < 2:
            continue
        cands = []
        for x in range(len(inc)):
            for y in range(x + 1, len(inc)):
                (a, ea, va), (b, eb, vb) = inc[x], inc[y]
                if a == b or va is None or vb is None:
                    continue
                turn = np.degrees(np.arccos(np.clip(-(va @ vb), -1, 1)))     # (0: straight on)
                same = bool(ref[a] & ref[b])
                if turn < (REF_TURN_DEG if same else TURN_DEG):
                    cands.append((turn - (30 if same else 0), x, y))
        used = set()
        for _, x, y in sorted(cands):
            if x in used or y in used:
                continue
            used |= {x, y}
            partner[inc[x][:2]] = inc[y][:2]; partner[inc[y][:2]] = inc[x][:2]
    of, total = [-1] * len(arcs), []
    for a in range(len(arcs)):
        if of[a] >= 0:
            continue
        sid, members = len(total), [a]; of[a] = sid
        for end in (0, 1):
            cur, ce = a, end
            while (cur, ce) in partner:
                b, eb = partner[(cur, ce)]
                if of[b] >= 0:
                    break
                of[b] = sid; members.append(b); cur, ce = b, 1 - eb
        total.append(sum(length[m] for m in members))
    return [total[of[a]] for a in range(len(arcs))], length


def main():
    if not os.path.exists(TRACKED):
        raise SystemExit(f"{TRACKED}: missing -- build/transport.py writes it")
    topo = json.load(open(TRACKED))
    arcs = decode(topo)
    q = config.QUANT_DEG
    objects, arcs_out = {}, []
    for obj, o in topo["objects"].items():
        lines = [(ring(arcs, g["arcs"]), {k: v for k, v in g["properties"].items() if k not in ("network", "network_km")})
                 for g in o["geometries"]]
        km0 = sum(km(c) for c, _ in lines)
        same = obj != "pipelines"
        if same:
            lines = [(x, p) for c, p in lines for x in turns(c)]
            first = lambda p: -2 if p.get("highspeed") else -1 if p.get("class") == "motorway" else 0
            lines.sort(key=lambda x: (first(x[1]), -km(x[0])))
        log(f"{obj}: {len(lines):,} lines, {km0:,.0f} km")
        kept, inserts, idx, attached = collapse(lines, same, JOIN_KM[obj])
        ext = joins(kept, inserts, idx, attached, JOIN_KM[obj], gaps(kept, attached, GAP_KM[obj]))
        kept = apply_inserts(kept, inserts, ext)
        del idx
        # the arcs: every line cut at every junction (an end of another line on it), so a join is an arc's end
        grid = [np.column_stack((np.round((c[:, 0] + 180) / q), np.round((c[:, 1] + 90) / q))).astype(np.int64) for c, _ in kept]
        grid = [g[np.r_[True, np.any(g[1:] != g[:-1], axis=1)]] for g in grid]
        junction = {tuple(x) for g in grid if len(g) > 1 for x in (g[0], g[-1])}
        pieces, fine = [], []                                # (each line's arcs, at the grid's detail)
        for g, (c, p) in zip(grid, kept):
            if len(g) < 2:
                continue
            cuts = [0] + [v for v in range(1, len(g) - 1) if tuple(g[v]) in junction] + [len(g) - 1]
            ids = []
            for a, b in zip(cuts[:-1], cuts[1:]):
                ids.append(len(fine)); fine.append(g[a:b + 1])
            pieces.append((ids, p))
        length = [km(g * q - [180, 90]) for g in fine]
        knot = knots(fine, length) if obj == "pipelines" else set()
        dead = spurs(fine, length, knot) if obj == "pipelines" else set()
        # the networks (the lines that meet), and each arc's rank
        parent = list(range(len(fine)))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        node = {}
        for a, g in enumerate(fine):
            if a in dead:
                continue
            for x in (tuple(g[0]), tuple(g[-1])):
                if x in node:
                    parent[find(a)] = find(node[x])
                else:
                    node[x] = a
        ref = [None] * len(fine)
        for ids, p in pieces:
            for a in ids:
                ref[a] = refs(p)
        stroke, length = strokes(fine, ref)
        net_km = collections.Counter()
        for a in range(len(fine)):
            if a not in dead:
                net_km[find(a)] += length[a]
        if obj == "pipelines":
            spur = len(dead)
            dead |= {a for a in range(len(fine)) if a not in dead and net_km[find(a)] < MIN_NET_KM}
            log(f"  {sum(length[a] for a in dead):,.0f} km of pipelines' loops, dead ends and small networks left out ({len(knot):,} arcs of loops, {spur - len(knot):,} of dead ends, {len(dead) - spur:,} of small networks)")
        t1, t2 = TIERS[obj]
        def tier(a, p):
            v = net_km[find(a)] if obj == "pipelines" else stroke[a]
            return 1 if v >= t1 or p.get("highspeed") else 2 if v >= t2 else 3
        nets, geoms = {}, []
        for ids, p in pieces:                                # (a line: one feature for each run of arcs of one tier)
            run = []
            for k, a in enumerate(ids):
                if a in dead:
                    continue
                run.append(a)
                if k == len(ids) - 1 or ids[k + 1] in dead or tier(ids[k + 1], p) != tier(a, p):
                    r = find(a); nets.setdefault(r, f"{obj[0]}{len(nets)}")
                    geoms.append({"type": "LineString", "arcs": [len(arcs_out) + x for x in range(len(run))],
                                  "properties": {**p, "network": nets[r], "network_km": round(net_km[r]), "tier": tier(a, p)}})
                    for x in run:
                        g = fine[x]
                        arcs_out.append(g[geo.simplify(geo.to_xyz(g * q - [180, 90]), EPS_KM)])
                    run = []
        objects[obj] = {"type": "GeometryCollection", "geometries": geoms}
        tiers = collections.Counter()
        for ids, p in pieces:
            for a in ids:
                if a not in dead:
                    tiers[tier(a, p)] += length[a]
        log(f"  {len(geoms):,} lines, {len(fine) - len(dead):,} arcs, {sum(tiers.values()):,.0f} km ({km0:,.0f} before), {len(nets):,} networks;",
            "by tier: " + ", ".join(f"{k}: {tiers[k]:,.0f} km" for k in sorted(tiers)))
    out = {"type": "Topology", "bbox": [-180, -90, 180, 90], "transform": {"scale": [q, q], "translate": [-180, -90]},
           "objects": objects, "arcs": [np.vstack((a[:1], np.diff(a, axis=0))).tolist() for a in arcs_out]}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    log(f"{OUT}: {os.path.getsize(OUT) / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
