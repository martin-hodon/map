"""The raw lines of transport: motorways (and trunk roads signed 100 km/h or more), main-line and high-speed
railways, and oil and gas pipelines -- from OpenStreetMap through Overpass, one TILE-degree tile at a time.

    .venv/bin/python build/fetch_transport.py       # -> raw/transport/<i>_<j>.json.gz (resumes where it stopped)

Only the tiles that hold land, or lie next to it (pipelines run under the sea), are asked for. Each answer is kept
as it came (gzipped): build/transport.py chooses from it, a tile at a time, so no answer is ever all in memory
with another. OSM data: ODbL.
"""
import os, sys, time, gzip, itertools
import numpy as np, requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "raw", "transport")
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
# (modest limits -- 300 s, 256 MB: a server queues a query that asks for more until it gives up with 504; a tile
# that needs more comes back with an error remark and is asked for in quarters)
UA = {"User-Agent": "welle-map-builder/0.1 (world map layers from OSM)"}
TILE = 10
QUERY = """[out:json][timeout:300][maxsize:268435456][bbox:{s},{w},{n},{e}];
(
  way[highway=motorway];
  way[highway=trunk][maxspeed];
  way[railway=rail][usage=main];
  way[railway=rail][highspeed=yes];
  way[man_made=pipeline][substance~"^(gas|natural_gas|oil|crude_oil|petroleum|fuel|lng|lpg|condensate|oil;gas|gas;oil)$"];
);
out tags geom qt;"""


def tiles():
    """the tiles with land in them or next to them (from stage 1's coast: every landmass's box, grown by a tile)"""
    z = np.load(os.path.join(ROOT, "work/coast_fine.npz"))
    off, coords = z["offsets"], z["coords"]
    t = set()
    for r in range(len(off) - 1):
        c = coords[off[r]:off[r + 1]]
        i0, j0 = np.floor(c.min(0) / TILE).astype(int) - 1
        i1, j1 = np.floor(c.max(0) / TILE).astype(int) + 1
        for i in range(max(i0, -180 // TILE), min(i1, 180 // TILE - 1) + 1):
            for j in range(max(j0, -60 // TILE), min(j1, 90 // TILE - 1) + 1):    # (nothing of this south of 60)
                t.add((i, j))
    return sorted(t)


def check(path):
    """"ok"; "big" (the query ran out of time or memory: ask in quarters); "busy" (an error page, the server busy)"""
    with gzip.open(path, "rb") as f:
        head = f.read(64)
        tail = head
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            tail = (tail + chunk)[-4096:]
    if not head.lstrip().startswith(b"{"):
        return "busy"
    if b'"remark"' in tail and (b"timed out" in tail or b"out of memory" in tail):
        return "big"
    return "busy" if b'"remark"' in tail and b"error" in tail else "ok"


def fetch(name, s, w, n, e, state={"server": 0}):
    """one box -> raw/transport/<name>.json.gz; a box Overpass cannot answer whole is asked for in quarters. The
    public servers are busy at times: then the next one, after a pause that grows."""
    path = os.path.join(OUT, name + ".json.gz")
    if os.path.exists(path) or os.path.exists(os.path.join(OUT, name + ".split")):
        return
    q = QUERY.format(s=s, w=w, n=n, e=e)
    for attempt in itertools.count():                        # (the public servers are down at times: wait it out)
        url = OVERPASS[state["server"] % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=(30, 400), stream=True)   # (the query stops at 300 s)
            if r.status_code == 200:
                tmp = os.path.join(OUT, name + ".part")
                with gzip.open(tmp, "wb") as f:                  # (streamed to disk: an answer is never held whole)
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                verdict = check(tmp)
                if verdict == "ok":
                    os.replace(tmp, path)
                    time.sleep(2)                                # (the servers are shared: one query at a time, a pause between)
                    return
                os.remove(tmp)
                if verdict == "big":
                    print(f"  {name}: too big, in quarters", flush=True)
                    ms, mw = (s + n) / 2, (w + e) / 2
                    for k, box in enumerate(((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e))):
                        fetch(f"{name}_{k}", *box)
                    open(os.path.join(OUT, name + ".split"), "w").close()
                    return
            print(f"  {name}: {url.split('/')[2]} {r.status_code} busy", flush=True)
            if r.status_code == 429:                         # (too many queries: the same server, after a wait)
                time.sleep(60)
                continue
        except requests.RequestException as ex:
            print(f"  {name}: {url.split('/')[2]} {type(ex).__name__} - next server", flush=True)
        state["server"] += 1
        time.sleep(min(900, 20 * (attempt + 1)))


def main():
    os.makedirs(OUT, exist_ok=True)
    todo = tiles()
    print(len(todo), "tiles", flush=True)
    t0 = time.time()
    for n, (i, j) in enumerate(todo):
        fetch(f"{i}_{j}", j * TILE, i * TILE, (j + 1) * TILE, (i + 1) * TILE)
        if n % 25 == 0:
            print(f"  {n + 1}/{len(todo)} tiles, {time.time() - t0:.0f} s", flush=True)
    print("FETCHED")


if __name__ == "__main__":
    main()
