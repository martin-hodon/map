"""STAGE 5 -- THE POINTS: cities of 100,000 people or more (70,000 in Europe: MIN_POP_BY, by the continents
full/world.topo.json gives the states and countries), and monuments with 100,000 visitors a year or more.

    .venv/bin/python build/points.py [cities] [monuments] [airports]   # -> data/cities.csv, monuments.csv, airports.csv

CITIES (layer 6): every place=city or place=town node OSM has, with its population tag -- or, where it has none (or
none that reads as a number), the latest population Wikidata gives the item the node links to (P1082, by its date).
The population shown is the URBAN one where the English Wikipedia article's infobox gives it (population_urban:
Larnaca is a town of 52,000 in a built-up area of 130,000), else the municipal count. Districts of a big city that
OSM maps as cities of their own (Istanbul's, Tokyo's wards, New York's boroughs) are left out: see districts(); and so
is any place Wikidata knows as a part of a city -- a suburb, a ward, a city district, a township: see city_parts().
A city is a point, so the file is a table (CITY_COLUMNS, a header line, one city a line): its place and its
properties, no more -- the population shown and nothing of where it came from. So are the monuments, the airports and
the natural points (build/areas.py): write_points.

MONUMENTS (layer 5): OSM knows no visitor numbers; Wikidata does (P1174, visitors per year). Every item with one, a
place (P625) and a latest yearly count of 100,000 or more, whose kind (P31, read up through its classes, P279) is a
building or a work of architecture -- a castle, a palace, a church, a temple, a tower, a bridge, a monument, a ruin, an
archaeological site -- or a work of nature -- a national park, a protected area, a waterfall, a cave, a mountain, a
canyon. Not museums as such, zoos, theme parks, stadiums, theatres, shops or stations -- unless they are also one of
the former (the Louvre is a palace).

...and the WELL KNOWN ones whatever their count: castles, palaces, cathedrals, temples, forts, ancient sites... that
enough Wikipedias write about (build/fetch_points.py FAMOUS: 15 or more for a castle, 40 for a church), and the World
Heritage Sites that 10 or more do. A count Wikidata lacks is taken from the English Wikipedia's infobox
(visitation_num...). Each monument has a LEVEL, 1 to 3, by its visitors (MONUMENT_LEVELS) -- or, with no count, by
its Wikipedias (FAME_LEVELS) -- which the map shows it by; the Wikipedias themselves are not written.

AIRPORTS: OurAirports' airports with scheduled service -- the large ones, and the medium ones with routes (OpenFlights)
to MIN_INTL_DESTINATIONS or more airports abroad -- with their passengers a year (Wikidata, P3872) and a LEVEL by
them (AIRPORT_LEVELS).

All get the country and state they are in from the map's own faces (work/topology.pkl), so a point and the polygon it
is drawn on always agree.
"""
import os, sys, re, csv, json, time, pickle, collections
import numpy as np, requests, shapely
from shapely import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, wdnames

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw")
MIN_POP = 100_000
MIN_POP_BY = {"Europe": 70_000}   # ...or this many in these continents (by the city's state's continent, else its country's)
MIN_VISITORS = 100_000
POP_STEP = 5_000
URBAN_FACTOR = 3        # a place's urban population counts when it is at most this many times its municipal one
MIN_HERITAGE_WIKIPEDIAS = 10    # a World Heritage Site's item is kept when this many Wikipedias write about it (not each part)
CATALOGUE = re.compile(r"[A-Z]{1,4} ?\d+[A-Za-z]?")     # a name that is only a number in a list: the Valley of the
                                # Kings' tombs, KV1 to KV63 (the valley itself kept) -- left out, they crowd round Luxor
MONUMENT_LEVELS = (2_000_000, 500_000)   # visitors a year: a monument of level 1 has the first, of 2 the second, of 3 fewer
FAME_LEVELS = (80, 40)          # ...and one with no count, as many Wikipedias (how well known: in its place)
AIRPORT_LEVELS = (20_000_000, 5_000_000)   # passengers a year: an airport of level 1, of 2 (of 3 fewer, or no count)
MIN_INTL_DESTINATIONS = 3       # an airport is international when its routes reach this many airports abroad (or it is large)
UA = {"User-Agent": "welle-map-builder/0.1 (world map layers from OSM + Wikidata)", "Accept": "application/sparql-results+json"}

# the kinds of monument (Wikidata classes: an item is of a kind if one of its classes is, or is under, one of these)
KINDS = [   # (first match wins: the more telling kinds first)
    ("castle", ["Q23413", "Q57821", "Q1785071", "Q88291"]),                      # castle, fortification, fort, citadel
    ("palace", ["Q16560", "Q53536964", "Q1802963"]),                             # palace, royal palace, mansion
    ("religious", ["Q24398318", "Q1370598", "Q16970", "Q44539", "Q32815", "Q44613", "Q160742", "Q2977"]),   # religious building, place of worship, church, temple, mosque, monastery, abbey, cathedral
    ("archaeological", ["Q839954", "Q109607", "Q15661340", "Q3950"]),            # archaeological site, ruins, ancient city, (villa)
    ("tomb", ["Q381885", "Q162875", "Q12516"]),                                  # tomb, mausoleum, pyramid
    ("monument", ["Q4989906", "Q5003624", "Q179700", "Q575759", "Q1368898"]),    # monument, memorial, statue, war memorial, (national memorial)
    ("tower", ["Q12518", "Q11303", "Q1440300"]),                                 # tower, skyscraper, observation tower
    ("bridge", ["Q12280"]),
    ("dam", ["Q12323"]),
    ("garden", ["Q1107656", "Q167346"]),                                         # garden, botanical garden
    ("national park", ["Q46169"]),
    ("protected area", ["Q473972", "Q179049", "Q23790", "Q1377575"]),            # protected area, nature reserve, natural monument, wildlife refuge
    ("waterfall", ["Q34038"]),
    ("cave", ["Q35509"]),
    ("landform", ["Q271669", "Q8502", "Q150784", "Q39816", "Q8072", "Q40080", "Q23397"]),  # landform, mountain, canyon, valley, volcano, beach, lake
    ("heritage", ["Q358", "Q1081138", "Q2319498", "Q9259"]),                     # heritage site, historic site, landmark, World Heritage Site
]   # (not "building" or "structure" as such: that is streets, rail lines, chairlifts and libraries too)
# ...and what is not a monument by itself (an item that is only one of these is left out)
NOT = ["Q33506", "Q207694", "Q43501", "Q2416723", "Q194195", "Q483110", "Q641226", "Q24354", "Q7075", "Q11315", "Q55488", "Q1248784",
       "Q3918", "Q16917", "Q1076486", "Q5773747", "Q27686", "Q41253", "Q22698", "Q1059478", "Q132510", "Q2154459",
       "Q472577", "Q44782", "Q79007", "Q34442", "Q54114", "Q728937", "Q15079663"]
       # museum, art museum, zoo, theme park, amusement park, stadium, arena, theatre, library, shopping centre, railway
       # station, airport, university, hospital, sports venue, historic house museum?, hotel, cinema, park,
       # (garden) centre, market, (convention) centre, retail park, port, street, road, boulevard, railway line,
       # (rapid transit line)
STRONG = {"castle", "palace", "religious", "archaeological", "tomb", "monument", "national park", "waterfall", "cave", "dam"}
       # (a kind that is a monument whatever else the item is; the others -- a landform, a protected area, a tower, a
       # bridge, a garden, a heritage site -- count only if the item is not also one of NOT)


def num(s):
    """a population tag as a number: '1234567', '1 234 567', '1,234,567', '1.234.567', '~120000 (2011)' -> int | None"""
    if s is None:
        return None
    s = str(s).strip().lstrip("~≈ca. ")
    m = re.match(r"^\d{1,3}(?:[ ,.'  ]\d{3})+(?!\d)|^\d+", s)
    if not m:
        return None
    return int(re.sub(r"\D", "", m.group(0)))


def sparql(q):
    for attempt in range(6):
        r = requests.post("https://query.wikidata.org/sparql", data={"query": q, "format": "json"}, headers=UA, timeout=600)
        if r.status_code == 200:
            return r.json()["results"]["bindings"]
        print("wdqs", r.status_code, "- retrying", flush=True); time.sleep(30 * (attempt + 1))
    raise SystemExit("wikidata failed")


def wd_population(qids):
    """the latest population Wikidata gives each item (cached in raw/wd_population.json)"""
    path = os.path.join(RAW, "wd_population.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = [q for q in qids if q not in have]
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in sparql(f"""SELECT ?item ?pop ?date WHERE {{ VALUES ?item {{ {vals} }} ?item p:P1082 ?st . ?st ps:P1082 ?pop .
                            FILTER NOT EXISTS {{ ?st wikibase:rank wikibase:DeprecatedRank }} OPTIONAL {{ ?st pq:P585 ?date }} }}"""):
            q = b["item"]["value"].rsplit("/", 1)[-1]
            d = b.get("date", {}).get("value", "")[:4]
            cur = have.get(q)
            if cur is None or (d or "0") > (cur[1] or "0"):
                have[q] = [int(float(b["pop"]["value"])), d or None]
        for q in need[i:i + 400]:
            have.setdefault(q, None)
        json.dump(have, open(path, "w"))
        print(f"  wikidata populations {min(i + 400, len(need))}/{len(need)}", flush=True)
    return have


class Where:
    """the country (and state) at a point, from the map's own faces"""
    def __init__(self):
        T = pickle.load(open(os.path.join(ROOT, "work/topology.pkl"), "rb"))
        info = T["info"]
        code = lambda d, k: ("AQ" if d == "AQ" else info[d][k]) if d else None
        cf = [(shapely.from_wkb(w), code(l, "country")) for (w, _), l in zip(T["country_faces"], T["country_labels"])]
        rf = [(shapely.from_wkb(w), code(l, "region")) for (w, _), l in zip(T["region_faces"], T["region_labels"]) if l]
        self.cg, self.cc = [g for g, _ in cf], [c for _, c in cf]
        self.rg, self.rc = [g for g, _ in rf], [c for _, c in rf]
        self.ct, self.rt = STRtree(self.cg), STRtree(self.rg)

    def __call__(self, x, y):
        pts = shapely.points(x, y)
        out_c, out_r = [None] * len(pts), [None] * len(pts)
        for tree, codes, out in ((self.ct, self.cc, out_c), (self.rt, self.rc, out_r)):
            pi, gi = tree.query(pts, predicate="within")
            for p, g in zip(pi.tolist(), gi.tolist()):
                out[p] = codes[g]
            miss = [i for i in range(len(pts)) if out[i] is None]
            if miss:                                         # (on the coast, or a city on its islet: the nearest face within 5 km)
                ni, d = tree.query_nearest(pts[miss], return_distance=True, all_matches=False)
                for (p, g), dd in zip(zip(ni[0].tolist(), ni[1].tolist()), d.tolist()):
                    if dd < 0.05:
                        out[miss[p]] = codes[g]
        return out_c, out_r


CITY_COLUMNS = ["name", "lon", "lat", "population", "place", "capital", "country", "region", "name_local", "wikidata", "osm"]
MONUMENT_COLUMNS = ["name", "lon", "lat", "kind", "level", "visitors", "visitors_year", "country", "region", "name_local", "wikidata", "osm"]
AIRPORT_COLUMNS = ["name", "lon", "lat", "iata", "icao", "city", "level", "passengers", "passengers_year", "country", "region"]


def write_points(rows, columns, path):
    """points (dicts with lon, lat) as a table: a header line of the columns, one point a line, an empty field for
    none (index.html pointsOf reads it back)"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow(["" if r.get(c) is None else round(r[c], 4) if c in ("lon", "lat") else r[c] for c in columns])


def round_pop(n):
    """a population to two significant digits, and never finer than POP_STEP: 193,456 -> 190,000; 1,215,026 ->
    1,200,000 (a count is not more accurate than that, and not of the same year everywhere)"""
    step = max(POP_STEP, 10 ** max(0, len(str(int(n))) - 2))
    return int(round(n / step) * step)


def wd_classes(qids):
    """{qid: the English names of its classes (P31)} (cached in raw/wd_place_classes.json)"""
    path = os.path.join(RAW, "wd_place_classes.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in wdnames.sparql(f'SELECT ?item ?l WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P31 ?c . ?c rdfs:label ?l . FILTER(LANG(?l) = "en") }}'):
            have.setdefault(b["item"]["value"].rsplit("/", 1)[-1], []).append(b["l"]["value"])
        for q in need[i:i + 400]:
            have.setdefault(q, [])
        json.dump(have, open(path, "w"), ensure_ascii=False)
    return {q: have.get(q, []) for q in qids}


def wp_urban(qids):
    """{qid: the urban population its English Wikipedia article's infobox gives (population_urban), or None}"""
    def read(text):
        m = re.search(r"\|\s*population_urban\s*=([^\n]*)", text)
        return infobox_number(m.group(1)) if m else None
    return wp_infobox(qids, "wp_urban.json", read, "urban populations")


def wp_infobox(qids, cache, read, what):
    """{qid: read(the lead section's wikitext of its English Wikipedia article), or None} -- 50 articles a request
    (cached in raw/<cache>)"""
    path = os.path.join(RAW, cache)
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    titles = {}
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in wdnames.sparql(f"""PREFIX schema: <http://schema.org/> SELECT ?item ?t WHERE {{ VALUES ?item {{ {vals} }}
            ?a schema:about ?item . ?a schema:isPartOf <https://en.wikipedia.org/> . ?a schema:name ?t . }}"""):
            titles[b["t"]["value"]] = b["item"]["value"].rsplit("/", 1)[-1]
    todo = sorted(titles)
    for i in range(0, len(todo), 50):
        for attempt in range(6):
            try:
                r = requests.get("https://en.wikipedia.org/w/api.php", headers={"User-Agent": UA["User-Agent"]}, timeout=120, params={
                    "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "rvsection": "0",
                    "format": "json", "formatversion": "2", "titles": "|".join(todo[i:i + 50])})
                if r.status_code == 200:
                    break
                print("wikipedia", r.status_code, "- retrying", flush=True)
            except requests.RequestException as e:
                print("wikipedia", type(e).__name__, "- retrying", flush=True)
            time.sleep(20 * (attempt + 1))
        else:
            raise SystemExit("wikipedia failed")
        res = r.json()["query"]
        back = {n["to"]: n["from"] for n in res.get("normalized", [])}
        for page in res["pages"]:
            q = titles.get(page["title"]) or titles.get(back.get(page["title"], ""))
            text = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
            if q:
                have[q] = read(text) if text else None
        for t in todo[i:i + 50]:
            have.setdefault(titles[t], None)
        json.dump(have, open(path, "w"))
        print(f"  wikipedia {what} {min(i + 50, len(todo))}/{len(todo)}", flush=True)
        time.sleep(0.5)
    for q in need:
        have.setdefault(q, None)
    json.dump(have, open(path, "w"))
    return {q: have.get(q) for q in qids}


def wp_visitors(qids):
    """{qid: [visitors a year, the year or None] its English Wikipedia article's infobox gives (visitation_num,
    visitors...), or None}"""
    def read(text):
        m = re.search(r"\|\s*(?:visitation_num|visitation|visitors_num|annual_visitors|visitors|annual_visitation)\s*=([^\n|]*)", text)
        if not m:
            return None
        v = re.sub(r"^\s*(?:over|more than|about|around|approx(?:imately|\.)?|c(?:a)?\.|est(?:imated|\.)?)\s*", "", m.group(1), flags=re.I)
        n = infobox_number(v)
        y = re.search(r"\|\s*(?:visitation_year|visitors_year|visitation_date)\s*=\D*((?:19|20)\d\d)", text) or re.search(r"\b((?:19|20)\d\d)\b", m.group(1))
        return [n, int(y.group(1)) if y else None] if n and n >= 1000 else None
    return wp_infobox(qids, "wp_visitors.json", read, "visitors")


def level(n, steps):
    """1, 2 or 3: n reaches steps[0], steps[1] or neither (None: 3)"""
    return 1 if n is not None and n >= steps[0] else 2 if n is not None and n >= steps[1] else 3


def wd_passengers(codes):
    """{IATA code: [passengers a year, the year]} -- Wikidata's (P3872, the airport's item by its code, P238): the
    most of its last five years' counts (so not a year of the pandemic), cached in raw/wd_passengers.json"""
    path = os.path.join(RAW, "wd_passengers.json")
    if os.path.exists(path):
        return json.load(open(path))
    P = ("PREFIX p: <http://www.wikidata.org/prop/> PREFIX ps: <http://www.wikidata.org/prop/statement/> "
         "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>\n")
    years = collections.defaultdict(dict)
    for i in range(0, len(codes), 300):
        vals = " ".join(f'"{c}"' for c in codes[i:i + 300])
        for b in wdnames.sparql(P + f"""SELECT ?iata ?n ?date WHERE {{ VALUES ?iata {{ {vals} }} ?item wdt:P238 ?iata .
                ?item p:P3872 ?s . ?s ps:P3872 ?n . ?s pq:P585 ?date }}"""):
            y, n = int(b["date"]["value"][:4]), float(b["n"]["value"])
            c = years[b["iata"]["value"]]
            c[y] = max(c.get(y, 0), n)
    out = {}
    for c, ys in years.items():
        last = max(ys)
        y = max((y for y in ys if y > last - 5), key=lambda y: ys[y])
        out[c] = [int(ys[y]), y]
    json.dump(out, open(path, "w"))
    return out


def infobox_number(v):
    """an infobox value as a number: '130.000', '39,105,000<ref>...</ref>', '{{formatnum:1234}}', '1.2 million' -> int | None"""
    v = re.sub(r"<!--.*?-->|<ref[^>]*/>|<ref[^>]*>.*?</ref>", " ", v)
    v = re.sub(r"\{\{\s*formatnum:\s*([^}|]+)[^}]*\}\}", r"\1", v)
    v = re.sub(r"\{\{[^}]*\}\}|&nbsp;", " ", v).strip()
    m = re.match(r"^~?\s*(\d+(?:\.\d+)?)\s*million\b", v, re.I)
    if m:
        return int(float(m.group(1)) * 1e6)
    return num(v)


DISTRICT = re.compile(r"(?<!urban )(?<!rural )\b(district|ward|borough|neighbou?rhood|quarter|arrondissement|subdistrict|suburb|mahalle|kecamatan|kelurahan|barangay|locality of India)\b", re.I)
CITY = re.compile(r"\b(city of|big city|large city|million city|prefecture-level city|county-level city|sub-provincial city|highly urbanized city|"
                  r"city designated|independent city|urban municipality|municipal corporation|municipality of|commune of|commune in|"
                  r"city in the|locality of Mexico|charter city|metropolitan city|special city|core city|satellite city|"
                  r"provincial capital|prefectural capital|state capital|national capital|county seat|town of|town in)\b", re.I)


def districts(rows):
    """a place that is a district of a much bigger city (Istanbul's, Tokyo's wards, New York's boroughs: OSM maps
    them as cities of their own) is dropped: one within 2.5 km x sqrt(population / 100,000) of a city of a million or
    more (by the municipal counts), under a fifth of its size, and not a capital -- unless Wikidata's classes for it
    say it is a city or municipality of its own and not a district (Kawasaki, Saitama and Chiba by Tokyo; Kunshan by
    Suzhou; the Ruhr's cities are each other's neighbours, none a district). A bigger one there (Harbin's Daoli, a
    million people) only when Wikidata calls it a district. rows are sorted biggest first."""
    from scipy.spatial import cKDTree
    import geo
    xyz = geo.to_xyz(np.array([[r["lon"], r["lat"]] for r in rows]))
    tree, cand = cKDTree(xyz), {}
    for r, p in zip(rows, xyz):
        if r["population_municipal"] < 1_000_000:
            continue
        km = 2.5 * (r["population_municipal"] / 1e5) ** 0.5
        for j in tree.query_ball_point(p, 2 * np.sin(km / geo.R_KM / 2)):
            o = rows[j]
            if o is not r and o["population_municipal"] < r["population_municipal"] and o["capital"] != "country":
                cand.setdefault(j, (r["name"], o["population_municipal"] < 0.2 * r["population_municipal"]))
    classes = wd_classes([rows[j]["wikidata"] for j in cand])
    drop = set()
    for j, (core, small) in cand.items():
        cl = classes.get(rows[j]["wikidata"]) or []
        if any(DISTRICT.search(c) for c in cl) or (small and not any(CITY.search(c) for c in cl)):
            drop.add(j)
    print(len(drop), "of", len(cand), "places by a bigger city dropped as its districts:",
          ", ".join(f'{rows[j]["name"]} ({cand[j][0]})' for j in sorted(drop)[:40]), "...", flush=True)
    return [r for j, r in enumerate(rows) if j not in drop]


# a PART of a city, whatever its distance to the centre: a suburb, a ward, a city's district (China's urban districts,
# Turkey's), a South African township, a region of Brasília -- by Wikidata's classes, when none of them is a settlement
# of its own (Üsküdar is "municipality of Turkey, town, city": kept). Its population is a part's, not a city's.
PART = re.compile(r"\b(suburb|neighbou?rhood|quarter|ward|barangay|mahalle|South African township|township of China|district of Turkey|"
                  r"district of China|subdistrict in China|sub-provincial district|administrative region of the Federal District|district of Taiwan)\b", re.I)
SETTLEMENT = re.compile(r"\b(city|town|human settlement|village|metropolis|urban|settlement)\b", re.I)


def city_parts(rows):
    """the rows without the parts of a city (PART); a capital stays (a country's or a state's: Dong Hoi's item is a ward)"""
    classes = wd_classes([r["wikidata"] for r in rows])
    def part(r):
        cl = classes.get(r["wikidata"]) or []
        return not r["capital"] and any(PART.search(c) for c in cl) and not any(SETTLEMENT.search(c) and not PART.search(c) for c in cl)
    drop = [r for r in rows if part(r)]
    print(len(drop), "places dropped as parts of a city:", ", ".join(r["name"] for r in drop[:30]), "...", flush=True)
    return [r for r in rows if not part(r)]


def cities(where):
    els = json.load(open(os.path.join(RAW, "osm_places.json")))["elements"]
    need = sorted({e["tags"]["wikidata"] for e in els if num(e["tags"].get("population")) is None and re.match(r"^Q\d+$", e["tags"].get("wikidata", ""))})
    print(len(els), "OSM cities and towns;", len(need), "without a population tag but with a Wikidata item", flush=True)
    wdp = wd_population(need)
    caps = sorted({e["tags"]["wikidata"] for e in els if (e["tags"].get("capital") in ("yes", "2") or e["tags"].get("admin_level") == "2")
                   and re.match(r"^Q\d+$", e["tags"].get("wikidata", ""))})
    wdcap = wd_population(caps)                            # (a capital: the larger of OSM's count and Wikidata's)
    rows, seen = [], {}
    for e in els:
        t = e["tags"]
        pop, src, year = num(t.get("population")), "osm", (t.get("population:date") or t.get("source:population") or "")[:4] or None
        if pop is None and wdp.get(t.get("wikidata")):
            pop, year = wdp[t["wikidata"]]; src = "wikidata"
        cap = "country" if t.get("capital") in ("yes", "2") or t.get("admin_level") == "2" else "state" if t.get("capital") == "4" else None
        if cap == "country" and wdcap.get(t.get("wikidata")) and wdcap[t["wikidata"]][0] > (pop or 0):
            pop, year = wdcap[t["wikidata"]]; src = "wikidata"   # (a capital's node can be its old town: Muscat's)
        if pop is None or (pop < min(MIN_POP, *MIN_POP_BY.values()) / URBAN_FACTOR and cap != "country") or not t.get("name"):
            continue
        r = {"name": t.get("name"), "_tags": t, "population": pop, "population_municipal": pop, "population_source": src,
             "population_year": year if year and year.isdigit() else None, "place": t.get("place"), "capital": cap,
             "wikidata": t.get("wikidata"), "osm": f"node/{e['id']}", "lon": e["lon"], "lat": e["lat"]}
        k = t.get("wikidata") or f"{t.get('name')}|{round(e['lat'], 1)}|{round(e['lon'], 1)}"
        if k in seen:                                      # (the same city twice: keep the city over the town, then the bigger)
            o = seen[k]
            if (o["place"] == "city", o["population"]) >= (r["place"] == "city", r["population"]):
                continue
        seen[k] = r
    # each city's floor: its continent's (a state's own: Russia's European oblasts, Istanbul's; else its country's)
    T = json.load(open(os.path.join(ROOT, "full/world.topo.json")))["objects"]
    cont = {g["properties"]["iso"]: g["properties"].get("continent") for o in ("countries", "regions") for g in T[o]["geometries"] if "iso" in g["properties"]}
    vs = list(seen.values())
    for r, c, g in zip(vs, *where(np.array([r["lon"] for r in vs]), np.array([r["lat"] for r in vs]))):
        r["_floor"] = MIN_POP_BY.get(cont.get(g) or cont.get(c), MIN_POP)
    seen = {k: r for k, r in seen.items() if r["population"] >= r["_floor"] / URBAN_FACTOR or r["capital"] == "country"}
    urban = wp_urban([r["wikidata"] for r in seen.values()])
    for r in seen.values():                                    # the urban population where Wikipedia gives one that is
        u = urban.get(r["wikidata"])                           # bigger (and not absurdly: a district's article can carry
        if u and r["population_municipal"] < u <= URBAN_FACTOR * r["population_municipal"]:   # the whole city's)
            r["population"], r["population_source"], r["population_year"] = u, "wikipedia-urban", None
    rows = sorted([r for r in seen.values() if r.pop("_floor") <= r["population"] or r["capital"] == "country"], key=lambda r: -r["population"])
    cc, rc = where(np.array([r["lon"] for r in rows]), np.array([r["lat"] for r in rows]))
    # the names: English (OSM's name:en, else Wikidata's English label, else its name), and the one in its country's
    # official language, where that is another
    en = wdnames.english([r["wikidata"] for r in rows])
    for r, c, g in zip(rows, cc, rc):
        t = r.pop("_tags")
        local = wdnames.local_name(t, c)
        r["name"] = t.get("name:en") or en.get(r["wikidata"]) or local or t.get("name")
        r["name_local"] = local if local and local != r["name"] else None
        r["country"], r["region"] = c, g
    rows = city_parts(districts(rows))
    by = collections.Counter(r["population_source"] for r in rows)
    for r in rows:
        r["population"] = round_pop(r["population"])
    path = os.path.join(ROOT, "data/cities.csv")
    write_points(rows, CITY_COLUMNS, path)
    print(f"{path}: {len(rows)} cities of {MIN_POP:,}+ ({', '.join(f'{v:,}+ in {k}' for k, v in MIN_POP_BY.items())}; population from {dict(by)}), {os.path.getsize(path) // 1024} KB", flush=True)


# the same place twice (twice()): words that only wrap a name ("archaeological excavations of Pompeii", "Castle Clinton
# National Monument", "wreck of the RMS Titanic") -- and a kind, the building of a place named as itself ("Devín
# Castle" and the village Devín, "Karnak Temple Complex" and Karnak)
WRAP = {"the", "of", "and", "in", "at", "complex", "compounds", "national", "monument", "monuments", "park", "memorial",
        "archaeological", "excavations", "site", "sites", "ruins", "area", "associated", "wreck", "rms", "historic",
        "historical", "ancient", "city", "kingdom", "unesco", "world", "heritage"}
BUILDING = {"castle", "citadel", "fortress", "fort", "palace", "temple", "cathedral", "abbey", "church", "mosque",
            "monastery", "pyramid"}
TWICE_KM = 3.0      # (two such names this near: one place)
CITY_KM = 10.0      # a monument named as a city this near is the city (Wikidata's Athens is an archaeological site too)


def twice(out, why):
    """the monuments without the cities (named as a city of data/cities.csv near) and without the second of a place
    named twice (WRAP, BUILDING): of a name and its wrapping the better known kept (its visitors the larger of the two),
    of a place and its building the building -- unless the place is twice as well known"""
    import unicodedata
    from scipy.spatial import cKDTree
    fold = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()
    words = lambda s: frozenset(re.findall(r"[a-z0-9]+", fold(s)))
    xy = lambda r: (r["lon"] * np.cos(np.radians(r["lat"])), r["lat"])
    cities = list(csv.DictReader(open(os.path.join(ROOT, "data/cities.csv"), encoding="utf-8")))
    ct = cKDTree([xy({"lon": float(c["lon"]), "lat": float(c["lat"])}) for c in cities])
    drop, gone = set(), []
    for i, r in enumerate(out):
        if any(fold(r["name"]) in (fold(cities[j]["name"]), fold(cities[j]["name_local"])) for j in ct.query_ball_point(xy(r), CITY_KM / 111)):
            drop.add(i); why["a city's own item"] += 1
    t = cKDTree([xy(r) for r in out])
    fame = lambda r: r.get("wikipedias") or 0
    for i, j in sorted(t.query_pairs(TWICE_KM / 111)):
        if i in drop or j in drop:
            continue
        a, b = out[i], out[j]
        wa, wb = words(a["name"]), words(b["name"])
        if not wa or not wb or not (wa <= wb or wb <= wa):
            continue
        short, long_ = (i, j) if len(wa) < len(wb) or (len(wa) == len(wb) and fame(a) >= fame(b)) else (j, i)
        extra = words(out[long_]["name"]) - words(out[short]["name"])
        if extra <= WRAP:                                      # (the same, wrapped: the better known, with the count)
            keep, lose = (short, long_) if fame(out[short]) >= fame(out[long_]) else (long_, short)
            if (out[lose].get("visitors") or 0) > (out[keep].get("visitors") or 0):
                out[keep]["visitors"], out[keep]["visitors_year"] = out[lose]["visitors"], out[lose].get("visitors_year")
        elif len(extra - WRAP) == 1 and extra - WRAP <= BUILDING:   # (a place and its building)
            keep, lose = (short, long_) if fame(out[short]) > 2 * fame(out[long_]) else (long_, short)
        else:
            continue
        drop.add(lose); gone.append(f"{out[lose]['name']} ({out[keep]['name']})"); why["the same place twice"] += 1
    print(len(gone), "monuments the same as another:", ", ".join(gone[:40]), "...", flush=True)
    return [r for i, r in enumerate(out) if i not in drop]


def monuments(where):
    rows = json.load(open(os.path.join(RAW, "wd_visitors.json")))
    classes = json.load(open(os.path.join(RAW, "wd_classes.json")))
    kinds = [(k, set(qs)) for k, qs in KINDS]
    NOTS = set(NOT)
    items = collections.defaultdict(list)
    for b in rows:
        items[b["item"]["value"].rsplit("/", 1)[-1]].append(b)
    feats, why = [], collections.Counter()
    for q, bs in items.items():
        # the count: the preferred statements if any, else all; the latest year among them (then the largest)
        pref = [b for b in bs if b["rank"]["value"].endswith("PreferredRank")] or bs
        best = max(pref, key=lambda b: (int(b.get("year", {}).get("value", 0) or 0), float(b["visitors"]["value"])))
        v = float(best["visitors"]["value"])
        if v < MIN_VISITORS:
            why["under 100,000 a year"] += 1
            continue
        types = {t.rsplit("/", 1)[-1] for b in bs for t in b.get("types", {}).get("value", "").split() if t}
        up = set().union(*(set(classes.get(t, {})) | {t} for t in types)) if types else set()
        kind = next((k for k, qs in kinds if up & qs), None)
        if kind is None:
            why["not a monument (by its classes)"] += 1
            continue
        if (up & NOTS) and kind not in STRONG:
            why["a museum, park, venue... first"] += 1
            continue
        if re.match(r"^Q\d+$", best["itemLabel"]["value"]):
            why["no name"] += 1
            continue
        if CATALOGUE.fullmatch(best["itemLabel"]["value"]):
            why["only a number (KV62)"] += 1
            continue
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", best["coord"]["value"], re.I)     # (WDQS: Point, QLever: POINT)
        if not m:
            continue
        lon, lat = float(m.group(1)), float(m.group(2))
        osm = ("way/" + best["osmway"]["value"]) if "osmway" in best else ("relation/" + best["osmrel"]["value"]) if "osmrel" in best else None
        feats.append((lon, lat, {"name": best["itemLabel"]["value"], "kind": kind, "visitors": int(v),
                                 "visitors_year": int(best["year"]["value"]) if best.get("year") else None, "wikidata": q, "osm": osm}))
    # ...and the well-known ones, counted or not: by how many Wikipedias write about them (raw/wd_famous.json)
    have, fame = {p["wikidata"] for _, _, p in feats}, {}
    famous = json.load(open(os.path.join(RAW, "wd_famous.json")))
    for r in famous:
        if r["kind"] == "heritage" and r["n"] < MIN_HERITAGE_WIKIPEDIAS:   # (a World Heritage Site's lesser parts)
            continue
        if r["item"] in have or not r.get("label") or re.match(r"^Q\d+$", r["label"]):
            continue
        if CATALOGUE.fullmatch(r["label"]):
            why["only a number (KV62)"] += 1
            continue
        o = fame.get(r["item"])
        if o is None or (o["kind"] == "heritage" and r["kind"] != "heritage"):   # (the telling kind over "heritage")
            fame[r["item"]] = r
    for q, r in fame.items():
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", r["coord"], re.I)
        if m:
            feats.append((float(m.group(1)), float(m.group(2)), {"name": r["label"], "kind": r["kind"], "wikipedias": r["n"], "wikidata": q}))
    langs = {}
    for r in famous:
        langs[r["item"]] = max(langs.get(r["item"], 0), r["n"])
    for _, _, p in feats:
        p.setdefault("wikipedias", langs.get(p["wikidata"]))
    # (a count where Wikidata has none: the English Wikipedia's infobox)
    wp = wp_visitors([p["wikidata"] for _, _, p in feats if not p.get("visitors")])
    for _, _, p in feats:
        if not p.get("visitors") and wp.get(p["wikidata"]):
            p["visitors"], p["visitors_year"] = wp[p["wikidata"]]
            why["(a count from Wikipedia)"] += 1
    why["well known (Wikipedias), no visitor count"] = sum(not p.get("visitors") for _, _, p in feats)
    feats.sort(key=lambda f: (-(f[2].get("visitors") or 0), -(f[2].get("wikipedias") or 0)))
    cc, rc = where(np.array([f[0] for f in feats]), np.array([f[1] for f in feats]))
    local = wdnames.local_labels([(p["wikidata"], c) for (_, _, p), c in zip(feats, cc)])   # (its name in its country's language)
    for (_, _, p), l in zip(feats, local):
        p["name_local"] = l if l and l != p["name"] else None
    out = [{**p, "lon": lon, "lat": lat, "country": c, "region": g} for (lon, lat, p), c, g in zip(feats, cc, rc)]
    out = twice(out, why)
    # (its level: by its visitors -- or, with no count, by how many Wikipedias write about it; the first first)
    for r in out:
        r["level"] = level(r["visitors"], MONUMENT_LEVELS) if r.get("visitors") else level(r.get("wikipedias"), FAME_LEVELS)
    out.sort(key=lambda r: (r["level"], -(r.get("visitors") or 0), -(r.get("wikipedias") or 0)))
    path = os.path.join(ROOT, "data/monuments.csv")
    write_points(out, MONUMENT_COLUMNS, path)
    print(f"{path}: {len(out)} monuments ({dict(collections.Counter(r['kind'] for r in out).most_common())};",
          f"by level {dict(sorted(collections.Counter(r['level'] for r in out).items()))}); left out: {dict(why)}", flush=True)


def airports(where):
    """the airports with scheduled flights abroad: OurAirports' airports with scheduled service whose routes
    (OpenFlights') reach MIN_INTL_DESTINATIONS airports in other countries or more; a large one 2 or more (or any,
    if it is newer than the routes)"""
    import csv
    ap = {}
    with open(os.path.join(RAW, "ourairports.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["type"] in ("large_airport", "medium_airport") and r["scheduled_service"] == "yes" and r["iata_code"]:
                ap[r["iata_code"]] = r
    abroad, routed = collections.defaultdict(set), set()
    with open(os.path.join(RAW, "openflights_routes.dat"), encoding="utf-8", errors="replace") as f:
        for line in f:
            x = line.rstrip("\n").split(",")
            if len(x) >= 5:
                routed.update((x[2], x[4]))
                if x[2] in ap and x[4] in ap and ap[x[2]]["iso_country"] != ap[x[4]]["iso_country"]:
                    abroad[x[2]].add(x[4]); abroad[x[4]].add(x[2])
    # (a large airport with flights to 2 or more airports abroad -- or newer than the routes (2014), like Berlin's)
    keep = [r for c, r in ap.items() if len(abroad[c]) >= MIN_INTL_DESTINATIONS
            or (r["type"] == "large_airport" and (len(abroad[c]) >= 2 or c not in routed))]
    pax = wd_passengers(sorted(r["iata_code"] for r in keep))
    keep.sort(key=lambda r: -pax.get(r["iata_code"], [0])[0])
    lon, lat = np.array([float(r["longitude_deg"]) for r in keep]), np.array([float(r["latitude_deg"]) for r in keep])
    cc, rc = where(lon, lat)
    out = [{"name": r["name"], "lon": x, "lat": y, "iata": r["iata_code"], "icao": r["icao_code"] or r["gps_code"] or None,
            "city": r["municipality"] or None, "level": level(pax.get(r["iata_code"], [None])[0], AIRPORT_LEVELS),
            "passengers": pax.get(r["iata_code"], [None])[0], "passengers_year": pax.get(r["iata_code"], [None, None])[1],
            "country": c or r["iso_country"], "region": g}
           for r, x, y, c, g in zip(keep, lon.tolist(), lat.tolist(), cc, rc)]
    path = os.path.join(ROOT, "data/airports.csv")
    write_points(out, AIRPORT_COLUMNS, path)
    print(f"{path}: {len(out)} international airports ({sum(r['passengers'] is not None for r in out)} with a passenger count;",
          f"by level {dict(sorted(collections.Counter(r['level'] for r in out).items()))})", flush=True)


def main():
    where = Where()
    parts = sys.argv[1:] or ["cities", "monuments", "airports"]
    if "cities" in parts:
        cities(where)
    if "monuments" in parts:
        monuments(where)
    if "airports" in parts:
        airports(where)


if __name__ == "__main__":
    main()
