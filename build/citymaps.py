#!/usr/bin/env python3
"""CITY DETAIL MAPS: for a few cities, a small map of their own, shown when the map is zoomed in close on one --
its main streets (motorway, trunk, primary, secondary; their bridges) with names, its districts' outlines and names,
its parks and large green areas, its water, its monuments' grounds, its train and metro lines (S-Bahn, U-Bahn, main
rail; coloured by line where OSM gives `colour`) and stations, and its airport. From OpenStreetMap via Overpass.

    .venv/bin/python build/citymaps.py              # every city of CITIES -> data/city/<wikidata>.txt, data/city/index.csv
    .venv/bin/python build/citymaps.py Q64          # only these (the index is written anew from all files there)

A CITY is one entry of CITIES, keyed by its Wikidata id in data/cities.csv; nothing else is needed (its name and place
come from there, its outline from OSM's boundary relation of that id). Optional: `levels`, the admin_levels of its
districts (the first outlined and named, the second named closer in, as Berlin's Bezirke and Ortsteile; else the
first of 9, 10, 8 that cuts the city into 5 to 40).

THE CITY: its boundary relation's area, and nothing round it -- everything is cut to that outline but the city's
airport (data/airports.csv: the busiest within AIRPORT_KM; BER, MUC), drawn whole wherever it is, and the metro's and
S-Bahn's lines, drawn on to their ends out of the city with their stations (Q_ROUTES). The page cuts the map's own
rivers, roads and railways out of the outline and the airport (@clip), and draws the map as it was round them. The
index (`data/city/index.csv`: wikidata, name, w, s, e, n, bytes) gives the box of the outline and the airport: where
a city's file applies, known without reading it. (The data is asked for in the outline's box and PAD_KM more.)

THE DETAIL: lines simplified to SIMPLIFY_M (Douglas-Peucker in metres about the city's centre), points on a grid of
GRID degrees (5.6 m north-south), delta-encoded as in build/lite.py's light files -- the same format, read by the same
parseLite; tables without arcs are points (`lon#`, `lat#`). ONE LINE FOR ONE ROAD, as the map's own main lines: the
streets, and the tracks of one kind and colour, go through build/roadnet.py's collapse at a city's scale (SCALE) -- a
dual carriageway's second roadway, a canal's other bank, a line's other tracks dropped where they run beside a line
kept, their ends and every free end carried onto the line they meet. Then each line is simplified between its
junctions (an end of another line on it), which stay where they are: the streets meet. A street is one line over its
bridges; @bridges are the stretches on one, drawn over it.

    @streets line         name, ref, class (motorway trunk primary secondary), arcs -- a row a line (one_line)
    @bridges line         class -- the streets' stretches on a bridge
    @rail line            kind (u: metro, s: S-Bahn, r: main rail), colour, lines[] (refs), arcs
    @water polygon        the water areas (rivers' and canals' own, lakes), merged; a row a piece
    @waterways line       name, kind -- rivers and canals as lines (named along them; drawn where no area is mapped)
    @green polygon        kind (wood: forest, wood, heath; park: parks, meadows, cemeteries, allotments), merged; a row a piece
    @districts line       level# (1 the outlined level, 2 the finer one) -- each border once
    @airport polygon      name, iata -- whole, in the city or not
    @monuments polygon    name, wikidata -- data/monuments.csv's in the city that OSM maps as an area MONUMENT_M across or more
    @clip polygon         the outline and the airport: where the map's own lines give way
    @places               name, level#, lon#, lat# -- the districts' names, where they go (polylabel)
    @parks                name, ha#, lon#, lat# -- the large parks' and lakes' names (kind)
    @stations             name, kind (u, s, r and their mixes: "us"), rank# (1 a main station, 2 an interchange, 3 the rest), lon#, lat#

Raw answers are kept in raw/city/<wikidata>_<part>.json.gz (delete one to ask again). Overpass is asked politely: one
query at a time, a generic User-Agent, a pause between queries and a growing one when a server is busy. OSM data: ODbL.
"""
import os, sys, csv, json, gzip, time, math, itertools, collections, re
import requests, shapely
import numpy as np
from shapely.geometry import LineString, Polygon, MultiPolygon, Point, box
from shapely.ops import linemerge, polygonize, unary_union, polylabel, orient
from shapely import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lite import table, column_type                       # (the light files' tables: one format for the page to read)

ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "raw", "city")
OUT = os.path.join(ROOT, "data", "city")

# THE ORDER the cities are built in (one at a time, each looked at before the next): Europe first, the most visited by
# international tourists first (Euromonitor's Top 100 City Destinations, 2023/24, and Mastercard's Global Destination
# Cities, the European ones), of the cities of data/cities.csv with 500,000 people or more and a monument of
# data/monuments.csv in them -- then the rest of Europe's such cities by their monuments' visitors, then the world's by
# the same ranking. Done when its entry is in CITIES (a city's own choices beside it):
#   Europe:  London, Paris, Istanbul, Rome, Barcelona, Amsterdam, Prague, Madrid, Vienna, Milan, Athens, Lisbon, Dublin,
#            Budapest, Antalya, [Berlin], [Munich], Copenhagen, Brussels, Stockholm, Warsaw, Krakow, Naples, Seville,
#            Moscow, Saint Petersburg, Porto, Valencia, Hamburg, Frankfurt, Nice, Granada, Malaga, Lyon, Marseille, Oslo,
#            Helsinki, Cologne, Kyiv, Belgrade, Sofia, Bucharest, Riga, Vilnius, Zagreb, Turin, Palermo, Thessaloniki,
#            Rotterdam, The Hague, Bilbao, Dresden, Genoa, Glasgow, Manchester, Birmingham, Tirana, Lviv, Minsk, Kazan,
#            then the rest by their monuments' visitors
#   World:   Bangkok, Hong Kong, Dubai, Mecca, Macau, Kuala Lumpur, New York, Singapore, Tokyo, Seoul, Shenzhen, Osaka,
#            Taipei, Los Angeles, Las Vegas, Miami, Cancun, Phuket, Bali (Denpasar), Shanghai, Beijing, Delhi, Mumbai,
#            Cairo, Mexico City, Rio de Janeiro, Buenos Aires, Sydney, ... (Euromonitor's order)
# A city's keys: `wikidata` (data/cities.csv); `levels`, its districts' admin_levels (the first outlined and named, the
# second named closer in; else the first of 9, 10, 8 that cuts it into 5 to 40); `boundary`, the wikidata of the OSM
# boundary to take when the city's own id is on none or on the wrong one; `drop`, the districts (of `levels`[0]) left
# out of the outline -- a province's rural ones (the outline then the union of the rest); `strip`, what to cut from the (a regex, or [regex, replacement] pairs)
# districts' names (a regex: "London Borough of "); `pbf`, the Geofabrik region whose extract to read (build/citypbf.py).
CITIES = [
    {"wikidata": "Q64", "levels": [9, 10]},               # Berlin: the 12 Bezirke outlined, the 96 Ortsteile named closer in
    {"wikidata": "Q1726", "levels": [9]},                 # Munich: the 25 Stadtbezirke
    # (from here on from Geofabrik's extracts, `pbf`: Overpass was too slow for a city a day)
    {"wikidata": "Q84", "levels": ["6|8"], "strip": "^(London Borough of|Royal Borough of) ", "pbf": "europe/united-kingdom/england"},
    #   London: Greater London (1,570 km^2), its 32 boroughs and the City (admin_level 6); LHR; the Tube, the Overground,
    #   the Elizabeth line and the DLR to their ends (England's extract: Amersham, Epping, Reading, Shenfield)
    {"wikidata": "Q90", "levels": [9], "strip": [["^Paris ", ""], [" [Aa]rrondissement$", " arr."]], "pbf": "europe/france/ile-de-france"},
    #   Paris: the city proper (the commune, 105 km^2, with the Bois de Boulogne and de Vincennes), its 20 arrondissements;
    #   CDG whole; the Metro, the RER and Transilien to their ends (60 km)
    {"wikidata": "Q406", "boundary": "Q534799", "levels": [6], "drop": ["Çatalca", "Silivri", "Şile", "Arnavutköy"],
     "pbf": "europe/turkey"},
    #   Istanbul: the province (5,300 km^2, Q406 on no boundary; the metropolitan municipality is the province) without
    #   its four rural districts, Catalca, Silivri, Sile, Arnavutkoy -- the 35 urban ilceler on both shores (the
    #   Belgrad forest's in Sariyer and Eyupsultan kept); IST whole (in Arnavutkoy); the Metro and Marmaray to their ends
    {"wikidata": "Q220", "levels": [10], "strip": "^Municipio Roma ", "pbf": "europe/italy/centro"},
    #   Rome: the comune (1,290 km^2: the Agro Romano's fields too, as the city is), its 15 municipi; FCO whole (in
    #   Fiumicino); the Metro and the FL lines to their ends
    {"wikidata": "Q1492", "levels": [9, 10], "pbf": "europe/spain/cataluna"},
    #   Barcelona: the municipality (101 km^2), its 10 districts and 73 barris; BCN whole; the Metro, FGC and Rodalies
    {"wikidata": "Q727", "boundary": "Q9899", "levels": ["place=suburb"], "pbf": "europe/netherlands/noord-holland"},
    #   Amsterdam: the municipality (Q9899, 219 km^2 -- Q727 is on the woonplaats, without Weesp), its stadsdelen (on
    #   no admin_level: boundary=place, place=suburb); AMS whole; the Metro and the NS Sprinters' not (main rail)
    {"wikidata": "Q1085", "levels": [5], "strip": "^obvod ", "pbf": "europe/czech-republic"},
    #   Prague: the capital city (496 km^2, the region and the city one), its 10 obvody (Praha 1-10); PRG; the Metro,
    #   the trams' not, Esko (S) lines to their ends
    {"wikidata": "Q2807", "levels": [9], "pbf": "europe/spain/madrid"},
    #   Madrid: the municipality (604 km^2, with El Pardo's woods), its 21 distritos; MAD whole; the Metro, Metro Ligero
    #   and Cercanias (C-) to their ends
    {"wikidata": "Q1741", "levels": [9], "pbf": "europe/austria"},
    #   Vienna: the city and state (415 km^2), its 23 Bezirke; VIE (in Schwechat, 18 km out); the U-Bahn and S-Bahn to
    #   their ends
    {"wikidata": "Q490", "levels": [10], "pbf": "europe/italy/nord-ovest"},
    #   Milan: the comune (182 km^2), its 9 municipi (admin_level 10); MXP whole (the busiest, 40 km out at Ferno; not
    #   Linate, 7 km); the Metro and the S lines to their ends
    {"wikidata": "Q1524", "boundary": "Q758056", "levels": [6, 7],
     "drop": ["Περιφερειακή Ενότητα Νήσων", "Περιφερειακή Ενότητα Ανατολικής Αττικής", "Περιφερειακή Ενότητα Δυτικής Αττικής"],
     "strip": [["^Περιφερειακή Ενότητα ", ""], ["^Δήμος ", ""]], "pbf": "europe/greece"},
    #   Athens: the basin -- Attica (Q758056; Q1524 is on no boundary, the municipality of Athens, Q1224979, only 39 km^2
    #   of its 3 million) without East and West Attica and the Islands: the four Athens regional units and Piraeus
    #   (412 km^2), outlined, their ~40 demoi named; ATH whole (in East Attica); the Metro, the tram's not, Proastiakos
    {"wikidata": "Q597", "levels": [8], "pbf": "europe/portugal"},
    #   Lisbon: the municipality (100 km^2), its 24 freguesias; LIS; the Metro and CP Lisboa's and Fertagus's lines to
    #   their ends
    {"wikidata": "Q1761", "boundary": "Q173500", "levels": [7], "pbf": "europe/ireland-and-northern-ireland"},
    #   Dublin: County Dublin (Q173500, 922 km^2, its 1.5 million -- the city council's area, Q1761, is 117 km^2 with no
    #   districts but 160 electoral divisions), its four councils: Dublin City, Fingal, South Dublin, Dun Laoghaire-
    #   Rathdown; DUB; the Luas's not (tram), DART and the commuter lines
    {"wikidata": "Q1781", "levels": [9], "strip": [["^([IVXL]+)\\. kerület$", "\\1"]], "pbf": "europe/hungary"},
    #   Budapest: the capital (525 km^2), its 23 kerulets (by their numbers, "XI"); BUD; the Metro, the HEV to their ends
    {"wikidata": "Q6487", "boundary": "Q40249", "levels": [6], "keep": ["Muratpaşa", "Kepez", "Konyaaltı", "Aksu", "Döşemealtı"],
     "pbf": "europe/turkey"},
    #   Antalya: the metropolitan municipality is the province (20,700 km^2, to Alanya and Kaş); kept its five urban
    #   districts (Muratpaşa, Kepez, Konyaaltı, Aksu, Döşemealtı: the city and its airport, ~1,900 km^2); AYT
    {"wikidata": "Q1748", "boundary": "Q26073", "levels": [7], "strip": " Kommune$", "pbf": "europe/denmark", "tertiary": True,
     "keep": [x + " Kommune" for x in ["Københavns", "Frederiksberg", "Tårnby", "Dragør", "Hvidovre", "Rødovre", "Brøndby",
                                         "Herlev", "Gladsaxe", "Gentofte"]]},
    #   Copenhagen: the municipality (88 km^2) has no districts in OSM (its bydele unmapped), so the inner ten kommuner
    #   of the Capital Region (Q26073): the city, Frederiksberg within it, Amager's Tårnby and Dragør (CPH), the western
    #   and northern rings to Brøndby and Gentofte (~330 km^2, 1.1 million); the Metro, the S-tog to their ends
    {"wikidata": "Q239", "boundary": "Q240", "levels": [8], "strip": " - .*$", "pbf": "europe/belgium"},
    #   Brussels: the Capital Region (Q240, 162 km^2; the City, Q239, is one of its 19 communes), its communes by their
    #   French names ("Ixelles - Elsene" -> "Ixelles"); BRU outside it, whole; the Metro, the S trains to their ends
    {"wikidata": "Q1754", "boundary": "Q506250", "levels": [9, 10], "strip": " stadsdelsområde$", "pbf": "europe/sweden",
     "tertiary": True},
    #   Stockholm: the municipality (Q506250, 188 km^2), its stadsdelsområden (9) and stadsdelar (10); ARN (40 km out)
    #   whole; the Tunnelbana, the pendeltåg and Roslagsbanan to their ends
    {"wikidata": "Q270", "levels": [9], "pbf": "europe/poland"},
    #   Warsaw: the city (517 km^2), its 18 dzielnice; WAW; the Metro, the SKM and Koleje Mazowieckie to their ends
    {"wikidata": "Q31487", "levels": [9], "pbf": "europe/poland"},
    #   Krakow: the city (327 km^2), its 18 dzielnice; KRK; the SKA to its ends
]
PAD_KM = 2
GRID = 0.00005                                            # (degrees: 5.6 m north-south, 3.7 m east-west at 48°)
SIMPLIFY_M = {"streets": 10, "rail": 10, "water": 12, "waterways": 12, "green": 25, "districts": 15, "airport": 20,
              "monuments": 5, "clip": 5}
# ONE LINE FOR ONE ROAD at a city's scale: build/roadnet.py's own constants (km) while it collapses a city's streets and
# tracks -- carriageways, a canal's two banks (Berlin's Luetzowufer and Schoeneberger Ufer, 40-50 m apart), a line's tracks
SCALE = {
    "streets": {"SEP_KM": 0.05, "PARALLEL_KM": 0.15, "TOUCH_KM": 0.025, "MIN_RUN_KM": 0.08, "JOIN_KM": 0.03, "GAP_KM": 0.06,
                "STEP_KM": 0.01, "TURN_KM": 0.04},
    "rail": {"SEP_KM": 0.03, "PARALLEL_KM": 0.15, "TOUCH_KM": 0.02, "MIN_RUN_KM": 0.1, "JOIN_KM": 0.03, "GAP_KM": 0.1,
             "STEP_KM": 0.01, "TURN_KM": 0.05},
}
BRIDGE_M = 12                                             # (a street within this of a bridge way of its class: on the bridge)
MONUMENT_M = 60                                           # (a monument's area this across or more -- its area's square root: drawn as an area)
MONUMENT_MAX_HA = 300                                     # (...and no larger)
AREA_TAGS = {"building", "historic", "tourism", "leisure", "landuse", "place", "man_made", "amenity", "area", "boundary"}
STOP_M = 300                                              # (a route's stop this near a station: the route stops there)
MAIN_STATIONS = 10                                        # (a city's main stations by their routes: so many at most)
AIRPORT_KM = 50                                           # (the city's airport: the busiest within this of its middle)
SEA_KM = 1.5                                                # (the sea drawn this far out of the outline: its coast whole)
MIN_HA = {"park": 5, "wood": 10, "water": 0.5, "label_park": 15, "label_lake": 10}
STREETS = ["motorway", "trunk", "primary", "secondary"]

OUT_KM = 60                                               # (a metro's, a commuter line's run out of the city: to its end, within this of the middle)
BUDGET_KB = 150                                           # (a city's file gzipped at most: else built again coarser, COARSER)
COARSER = [1, 1.25, 1.5, 1.75, 2, 2.4, 2.8, 3.4, 4]      # (the steps: simplify tolerances times this, the least areas times its square)
TILE_DEG = (0.3, 0.2)                                     # (a big city's box asked for in tiles of this, lon x lat: Overpass times out on more)
# COMMUTER LINES (kind s, drawn whole as the metro's): route=light_rail, or a train route of such a network or such a
# number -- S-Bahn, S-tog, RER and Transilien, London Overground and the Elizabeth line, Cercanias, Rodalies (R1..),
# Proastiakos, Esko, HEV, Rome's FL lines, Madrid's C-1.., Milan's S lines, DART, Marmaray...; not a regional train (RE1)
COMMUTER_NET = ("S-Bahn|S-tog|RER|Transilien|Overground|Elizabeth|Cercan|Rodalies|Proastiak|Προαστιακός|Esko|HÉV|"
                "Suburban|Suburbano|Pendelt|DART|Marmaray|SKM|WKD|Szybka Kolej|CP Lisboa|Fertagus|Пригород|МЦД|Transport for London")
COMMUTER_REF = "^(S ?[0-9]|FL[0-9]|C-?[0-9]|R[0-9])"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
UA = {"User-Agent": "map-citymaps-builder/0.1 (city detail maps from OpenStreetMap)"}

Q_BOUNDARY = """[out:json][timeout:120];
rel[boundary=administrative][wikidata={qid}]({s},{w},{n},{e});
out geom;"""
Q_LINES = """[out:json][timeout:300][maxsize:536870912][bbox:{s},{w},{n},{e}];
way[highway~"^(motorway|trunk|primary|secondary)$"];
out tags geom qt;
rel[route~"^(subway|light_rail|train)$"]->.r;
.r out body qt;
(way(r.r)[railway~"^(rail|subway|light_rail)$"]; way[railway=rail][usage~"^(main|branch)$"][!service];)->.t;
.t out tags geom qt;
node[railway~"^(station|halt)$"][name];
out qt;
way[waterway~"^(river|canal)$"][name];
out tags geom qt;"""
Q_AREAS = """[out:json][timeout:300][maxsize:536870912][bbox:{s},{w},{n},{e}];
(
  wr[leisure~"^(park|garden)$"]; wr[landuse~"^(forest|meadow|recreation_ground|cemetery|allotments|grass|village_green)$"];
  wr[natural~"^(wood|heath|grassland|water)$"]; wr[waterway=riverbank]; wr[aeroway=aerodrome]; way[natural=coastline];
);
out geom qt;"""
Q_ROUTES = """[out:json][timeout:300][maxsize:536870912];
(
  rel[route~"^(subway|light_rail)$"]({s},{w},{n},{e});
  rel[route=train][ref~"{cref}"]({s},{w},{n},{e});
  rel[route=train][network~"{cnet}"]({s},{w},{n},{e});
)->.r;
.r out body qt;
way(r.r)[railway~"^(rail|subway|light_rail)$"]->.t;
.t out tags geom qt;
node(around.t:100)[railway~"^(station|halt)$"][name];
out qt;"""
Q_STOPS = """[out:json][timeout:300][bbox:{s},{w},{n},{e}];
rel[route~"^(subway|light_rail|train)$"]->.r;
node(r.r);
out skel qt;"""
Q_AIRPORT = """[out:json][timeout:120];
wr[aeroway=aerodrome][iata="{iata}"]({s},{w},{n},{e});
out geom;"""
Q_MONUMENTS = """[out:json][timeout:180][bbox:{s},{w},{n},{e}];
wr[wikidata~"^({ids})$"];
out geom;"""
Q_DISTRICTS = """[out:json][timeout:300];
rel({rid}); map_to_area->.a;
rel(area.a)[boundary=administrative][admin_level~"^({levels})$"];
out geom;"""


# ---- asking Overpass ------------------------------------------------------------------------------------------------
def ask(path, query, state={"server": 0, "last": 0.0}):
    """the answer to a query, kept at `path` (gzipped JSON): read from there when it is there"""
    if os.path.exists(path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    for attempt in itertools.count():
        wait = state["last"] + 5 - time.time()            # (a pause between queries: one at a time, politely)
        if wait > 0:
            time.sleep(wait)
        url = OVERPASS[state["server"] % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": query}, headers=UA, timeout=(30, 400))
            state["last"] = time.time()
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                d = r.json()
                if "remark" in d and ("error" in d["remark"] or "timed out" in d["remark"]):
                    raise RuntimeError(d["remark"][:200])
                os.makedirs(RAW, exist_ok=True)
                with gzip.open(path + ".part", "wt", encoding="utf-8") as f:
                    json.dump(d, f)
                os.replace(path + ".part", path)
                print(f"  {os.path.basename(path)}: {len(d['elements'])} elements ({len(r.content) / 1e6:.1f} MB)")
                return d
            why = f"HTTP {r.status_code}"
        except (requests.RequestException, RuntimeError, ValueError) as e:
            state["last"] = time.time(); why = str(e)[:120]
        if attempt >= 15:
            raise SystemExit(f"Overpass gave no answer for {os.path.basename(path)}: {why}")
        state["server"] += 1                              # (the next server; once round them all, a longer pause)
        pause = min(300, 10 * 2 ** min(attempt // len(OVERPASS), 5)) + (60 if "429" in why else 0)
        print(f"  {url.split('/')[2]}: {why}; next server in {pause} s")
        time.sleep(pause)


def ask_box(path, query, bb):
    """a query over a box (its {s} {w} {n} {e}), asked in tiles of TILE_DEG where the box is bigger -- a tile's answer kept
    while the others are asked (path_<i>), the elements put together once (each once: a way in two tiles is one)"""
    if os.path.exists(path):
        return ask(path, query)
    nx = max(1, math.ceil((bb["e"] - bb["w"]) / TILE_DEG[0])); ny = max(1, math.ceil((bb["n"] - bb["s"]) / TILE_DEG[1]))
    if nx * ny == 1:
        return ask(path, query.format(**bb))
    els, seen, tiles = [], set(), []
    for i in range(nx):
        for j in range(ny):
            t = dict(w=round(bb["w"] + (bb["e"] - bb["w"]) * i / nx, 4), e=round(bb["w"] + (bb["e"] - bb["w"]) * (i + 1) / nx, 4),
                     s=round(bb["s"] + (bb["n"] - bb["s"]) * j / ny, 4), n=round(bb["s"] + (bb["n"] - bb["s"]) * (j + 1) / ny, 4))
            tp = path.replace(".json.gz", f"_{i}{j}.json.gz"); tiles.append(tp)
            for el in ask(tp, query.format(**t))["elements"]:
                if (el["type"], el["id"]) not in seen:
                    seen.add((el["type"], el["id"])); els.append(el)
    d = {"elements": els}
    with gzip.open(path + ".part", "wt", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(path + ".part", path)
    for tp in tiles:
        os.remove(tp)
    print(f"  {os.path.basename(path)}: {len(els)} elements from {nx * ny} tiles")
    return d


# ---- geometry: metres about the centre, and back ------------------------------------------------------------------
class Local:
    def __init__(self, lon0, lat0):
        self.lon0, self.lat0, self.kx, self.ky = lon0, lat0, 111320 * math.cos(math.radians(lat0)), 110574

    def xy(self, pts):
        return [((x - self.lon0) * self.kx, (y - self.lat0) * self.ky) for x, y in pts]

    def ll(self, pts):
        return [(self.lon0 + x / self.kx, self.lat0 + y / self.ky) for x, y in pts]

    def geom(self, g):
        return shapely.transform(g, lambda a: a * [self.kx, self.ky] + [-self.lon0 * self.kx, -self.lat0 * self.ky])

    def back(self, g):
        return shapely.transform(g, lambda a: (a + [self.lon0 * self.kx, self.lat0 * self.ky]) / [self.kx, self.ky])


def way_line(el):
    g = el.get("geometry") or []
    return [(p["lon"], p["lat"]) for p in g if p]


def assemble(el, L):
    """an area way or multipolygon relation -> a polygon in metres (or None)"""
    if el["type"] == "way":
        pts = way_line(el)
        if len(pts) < 4 or pts[0] != pts[-1]:
            return None
        p = Polygon(L.xy(pts))
        return p if p.is_valid else p.buffer(0)
    outer, inner = [], []
    for m in el.get("members", []):
        if m["type"] != "way" or not m.get("geometry"):
            continue
        pts = [(p["lon"], p["lat"]) for p in m["geometry"] if p]
        if len(pts) >= 2:
            (inner if m.get("role") == "inner" else outer).append(LineString(L.xy(pts)))
    if not outer:
        return None
    try:
        o = unary_union([p.buffer(0) for p in polygonize(linemerge(outer))])
        if inner:
            o = o.difference(unary_union([p.buffer(0) for p in polygonize(linemerge(inner))]))
    except shapely.errors.GEOSException:                  # (rings that cross: OSM's broken multipolygons)
        return None
    return o if not o.is_empty else None


def parts(g):
    """a geometry's lines or polygons, one by one"""
    if g is None or g.is_empty:
        return []
    if hasattr(g, "geoms"):
        return [x for y in g.geoms for x in parts(y)]
    return [g]


def merged(ls):
    """lines joined end to end where they meet (linemerge, which takes only a MultiLineString)"""
    u = unary_union(ls)
    if u.geom_type == "MultiLineString":
        return linemerge(u)
    return u if u.geom_type == "LineString" else unary_union([p for p in parts(u) if p.geom_type == "LineString"])


# ---- writing: arcs on the grid, rows, tables -------------------------------------------------------------------------
class Writer:
    def __init__(self, L, window):
        self.L, self.arcs, self.objects, self.tables = L, [], [], []
        w, s, e, n = window
        self.x0, self.y0 = math.floor(w / GRID), math.floor(s / GRID)

    def arc(self, pts_ll, closed=False):
        """a line in lon/lat onto the grid -> its arc's index (None when it is less than a line on the grid)"""
        q = []
        for x, y in pts_ll:
            g = (round(x / GRID) - self.x0, round(y / GRID) - self.y0)
            if not q or g != q[-1]:
                q.append(g)
        if closed and len(q) > 1 and q[0] != q[-1]:
            q.append(q[0])
        if len(q) < (4 if closed else 2):
            return None
        text = [f"{q[0][0]} {q[0][1]}"] + [f"{b[0] - a[0]} {b[1] - a[1]}" for a, b in zip(q, q[1:])]
        self.arcs.append(" ".join(text))
        return len(self.arcs) - 1

    def line(self, g, tol):
        """a line in metres -> its arcs' text (simplified, on the grid)"""
        out = []
        for p in parts(g.simplify(tol)):
            a = self.arc(self.L.ll(p.coords))
            if a is not None:
                out.append(str(a))
        return ";".join(out)

    def lines_at(self, pieces, tol, clip=None):
        """a line's pieces between its junctions (lon/lat lists, end to end) -> (its arcs' text, the lines in metres):
        each piece simplified on its own, so a junction stays where it is and the lines meeting there meet; cut to
        `clip`; the pieces joined again into one arc where they still run on"""
        out, geo, cur = [], [], []
        def flush():
            if len(cur) >= 2:
                a = self.arc(self.L.ll(cur))
                if a is not None:
                    out.append(str(a)); geo.append(LineString(cur))
            cur.clear()
        for pc in pieces:
            g = LineString(self.L.xy(pc))
            gs = [g] if clip is None or clip.contains(g) else [x for x in parts(g.intersection(clip)) if x.geom_type == "LineString"]
            for x in gs:
                q = list(x.simplify(tol).coords)
                if cur and math.dist(cur[-1], q[0]) < 1e-6:
                    cur.extend(q[1:])
                else:
                    flush(); cur.extend(q)
            if len(gs) != 1 or gs[0] is not g:
                flush()                                   # (cut by the outline: a new arc after)
        flush()
        return ";".join(out), geo

    def polygon(self, g, tol, min_m2=0):
        """a polygon in metres -> its arcs' text: rings ';', polygons '|' (outer rings clockwise, holes anticlockwise in
        lon/lat, as the map's polygons: the globe would fill one the other way round as all the world but it)"""
        out = []
        for p in parts(g.simplify(tol, preserve_topology=True)):
            if p.geom_type != "Polygon" or p.area < max(min_m2, 1):
                continue
            p = orient(p, sign=-1.0)
            rings = [self.arc(self.L.ll(p.exterior.coords), True)]
            if rings[0] is None:
                continue
            for h in p.interiors:
                if Polygon(h).area >= max(min_m2, tol * tol * 4):
                    a = self.arc(self.L.ll(h.coords), True)
                    if a is not None:
                        rings.append(a)
            out.append(";".join(str(a) for a in rings))
        return "|".join(out)

    def obj(self, name, kind, rows):
        rows = [r for r in rows if r["arcs"]]
        if not rows:                                      # (none: left out -- an empty object breaks the page's trees;
            return                                        #  Lisbon has no named river but the Tagus, which is sea)
        for r in rows:                                    # (every arc a row names is one of the file's: a bad one panics
            for t in re.split(r"[;|]", r["arcs"]):        #  the page's trees)
                assert t and -len(self.arcs) <= int(t) < len(self.arcs), (name, r["arcs"][:60])
        keys = list(dict.fromkeys(k for r in rows for k in r if k != "arcs"))
        types = {k: column_type([r.get(k) for r in rows]) for k in keys}; types["arcs"] = ""
        self.objects.append(f"@{name} {kind}\n" + table(rows, keys + ["arcs"], types))

    def points(self, name, rows):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        types = {k: column_type([r.get(k) for r in rows]) for k in keys}
        self.tables.append(f"@{name}\n" + table(rows, keys, types))

    def text(self, title):
        return "\n".join([f"# {title}", f"grid {GRID:g} {self.x0 * GRID:.5f} {self.y0 * GRID:.5f}", "@arcs", *self.arcs]) + "\n" + "".join(self.objects) + "".join(self.tables)


# ---- one city ---------------------------------------------------------------------------------------------------------
def city_row(qid):
    with open(os.path.join(ROOT, "data", "cities.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["wikidata"] == qid:
                return r
    raise SystemExit(f"{qid} is not in data/cities.csv")


def sea(coast, outline):
    """the sea within SEA_KM of the outline: the box's faces cut by the coastlines (OSM: the land on a coastline's
    left), each the side most of its coastlines' segments say -- or None, no coastline near"""
    if not coast:
        return None
    reach = outline.buffer(SEA_KM * 1000)
    box_ = box(*reach.bounds)
    lines_ = [LineString(c) for c in coast]
    faces = list(polygonize(unary_union([box_.exterior] + [x.intersection(box_) for x in lines_])))
    if not faces:
        return None
    left, right = [], []                                  # (a point a metre either side of each segment's middle)
    for c in coast:
        a = np.asarray(c[:-1], float); b = np.asarray(c[1:], float)
        d = b - a; n = np.hypot(d[:, 0], d[:, 1]); ok = n > 0.5
        a, d, n = a[ok], d[ok], n[ok]
        m = a + d / 2; nx, ny = -d[:, 1] / n, d[:, 0] / n
        left.append(np.c_[m[:, 0] + nx, m[:, 1] + ny]); right.append(np.c_[m[:, 0] - nx, m[:, 1] - ny])
    tree_ = STRtree(faces)
    votes = np.zeros(len(faces))
    for pts, v in ((np.concatenate(left), 1), (np.concatenate(right), -1)):
        _, fi = tree_.query(shapely.points(pts), predicate="within")
        np.add.at(votes, fi, v)
    wet = [f for f, v in zip(faces, votes) if v < 0]
    if not wet:
        return None
    wet = unary_union(wet).intersection(reach)
    if wet.intersection(outline).area > 0.6 * outline.area:   # (a coast that cuts no face: no side to trust)
        print("  sea: left out, the coastlines cut no land off")
        return None
    return wet


def short(spec, name):
    """a district's name as drawn: `strip` (a regex, or [regex, replacement] pairs) applied -- "Paris 18e
    Arrondissement" -> "18e arr.", "Municipio Roma I" -> "I" ("Praha 1" kept whole)"""
    rules = spec.get("strip") or []
    for pat, rep_ in ([(rules, "")] if isinstance(rules, str) else rules):
        name = re.sub(pat, rep_, name)
    return name.strip()


def level_key(t):
    """a district's level as `levels` names it: its admin_level, or "place=suburb" for a place boundary (Amsterdam's
    stadsdelen, on no admin_level)"""
    return f"place={t.get('place')}" if t.get("boundary") == "place" else t.get("admin_level", "0")


def same(name):
    """a station's name to compare: "Hbf" spelt out"""
    return re.sub(r"\s*\(.*?\)", "", re.sub(r"\bHbf\b\.?", "Hauptbahnhof", name))      # (and "(tief)" gone)


AUTOZUG = r"(?i)autoreisezug|autozug|motorail|güterbahnhof|freight"      # (a car train's or goods' station: none to ride from)
STATION_WORDS = {"gare", "de", "du", "des", "d", "la", "le", "l", "station", "stazione", "di", "estación", "estació", "estacion",
                 "railway", "rail", "main", "s", "u", "rer", "metro", "bahnhof", "nádraží", "dworzec", "pályaudvar", "garı", "gari", "istasyonu", "tren"}


def core(name, town):
    """a station's name without its town's and the words for a station: "Paris Austerlitz" and "Gare d'Austerlitz" are
    "austerlitz", "London Euston" and "Euston" "euston" -- one station (within 600 m)"""
    ws = re.findall(r"\w+", same(name).lower())
    return " ".join(w for w in ws if w not in STATION_WORDS and w not in town)


def one_line(lines, scale, same=True):
    """ONE LINE FOR ONE ROAD, as the map's own main lines are made (build/roadnet.py: turns, collapse, gaps, joins,
    apply_inserts -- the same code, at a city's scale, SCALE): `lines` [(lon/lat array, properties)] most important
    first -> the lines kept [(lon/lat array, properties)], a stretch beside one kept before dropped (a dual carriageway's
    second roadway, a canal's other bank, a railway's other tracks), its cut ends and every free end carried onto the
    line it meets -- and the set of their ends (pkey), the junctions, which the simplifying keeps where they are"""
    import roadnet
    saved = {k: getattr(roadnet, k) for k in scale}
    try:
        for k, v in scale.items():
            setattr(roadnet, k, v)
        lines = [(x, p) for c, p in lines for x in roadnet.turns(c)] if same else lines
        kept, inserts, idx, attached = roadnet.collapse(lines, same, scale["JOIN_KM"])
        ext = roadnet.joins(kept, inserts, idx, attached, scale["JOIN_KM"], roadnet.gaps(kept, attached, scale["GAP_KM"]))
        kept = roadnet.apply_inserts(kept, inserts, ext)
    finally:
        for k, v in saved.items():
            setattr(roadnet, k, v)
    ends = {roadnet.pkey(q) for c, _ in kept for q in (c[0], c[-1])}
    return kept, ends


def pieces_at(c, ends):
    """a lon/lat line cut at the junctions on it -> [lon/lat lists]: each simplified on its own, its ends stay put"""
    import roadnet
    cuts = [0] + [v for v in range(1, len(c) - 1) if roadnet.pkey(c[v]) in ends] + [len(c) - 1]
    return [[tuple(map(float, q)) for q in c[a:b + 1]] for a, b in zip(cuts[:-1], cuts[1:]) if b > a]


_RAW = {}
def cached(path, f):
    """a raw answer read once a run (a city built again coarser reads it from here)"""
    if path not in _RAW:
        for k in [k for k in _RAW if os.path.basename(k).split("_")[0] != os.path.basename(path).split("_")[0]]:
            del _RAW[k]                                   # (another city's: let go)
        _RAW[path] = f()
    return _RAW[path]


def build(spec, f=1):
    """one city -> data/city/<wikidata>.txt; `f` the coarseness (COARSER): the simplify tolerances times f, the least
    areas times f squared"""
    import numpy as np
    global SIMPLIFY_M, MIN_HA
    base_s, base_h = SIMPLIFY_M, MIN_HA
    SIMPLIFY_M = {k: v * (f if k not in ("monuments", "clip") else 1) for k, v in base_s.items()}
    MIN_HA = {k: v * f * f for k, v in base_h.items()}
    try:
        return _build(spec, f, np)
    finally:
        SIMPLIFY_M, MIN_HA = base_s, base_h


PARTS = ["boundary", "districts", "lines", "areas", "routes", "stops", "airport", "monuments"]
PBF = os.path.join(RAW, "pbf")                            # (Geofabrik's extracts: a city's `pbf` region, downloaded once)


def city_airport(lon0, lat0):
    """the city's airport: of data/airports.csv the busiest (passengers) within AIRPORT_KM of its middle"""
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    near = []
    with open(os.path.join(ROOT, "data", "airports.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = math.hypot((float(r["lon"]) - lon0) * kx, (float(r["lat"]) - lat0) * ky) / 1000
            if d < AIRPORT_KM and r["iata"]:
                near.append((-int(r["passengers"] or 0), int(r["level"] or 3), d, r))
    return min(near, key=lambda t: t[:3])[3] if near else None


def is_whole(t):
    """a route drawn whole, out of the city too: a metro's, a commuter line's (COMMUTER_NET, COMMUTER_REF)"""
    return t.get("route") in ("subway", "light_rail") or (t.get("route") == "train" and commuter_train(t))


def commuter_train(t):
    """a train route that is a commuter line's: its number (COMMUTER_REF), or its network, operator or name (COMMUTER_NET)"""
    return bool(re.match(COMMUTER_REF, t.get("ref", "")) or re.search(COMMUTER_NET, " ".join(t.get(k, "") for k in ("network", "operator", "name"))))


def from_pbf(spec, bq, lon0, lat0, raw):
    """the raw parts from the Geofabrik extract of the city's region (build/citypbf.py) -- Overpass not asked"""
    import citypbf
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.574
    mons = set()
    with open(os.path.join(ROOT, "data", "monuments.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["wikidata"] and math.hypot((float(r["lon"]) - lon0) * kx, (float(r["lat"]) - lat0) * ky) < OUT_KM:
                mons.add(r["wikidata"])
    a = city_airport(lon0, lat0)
    regions = spec["pbf"] if isinstance(spec["pbf"], list) else [spec["pbf"]]
    paths = [citypbf.fetch(rg, PBF) for rg in regions]
    citypbf.extract(paths[0], raw, bq=bq, lon0=lon0, lat0=lat0, levels=spec.get("levels") or [9, 10, 8], monuments=mons,
                    airport=(a["iata"], float(a["lon"]), float(a["lat"])) if a else None, commuter=is_whole, out_km=OUT_KM, pad_km=PAD_KM,
                    streets=set(STREETS) | ({"tertiary"} if spec.get("tertiary") else set()))


def _build(spec, f, np):
    qid = spec["wikidata"]; c = city_row(qid)
    lon0, lat0 = float(c["lon"]), float(c["lat"])
    print(f"{c['name']} ({qid}){f' coarser x{f}' if f != 1 else ''}")
    raw = lambda part: os.path.join(RAW, f"{qid}_{part}.json.gz")
    # (the city's outline: its boundary relation of that wikidata id -- or of `boundary` -- the biggest if more)
    bq = spec.get("boundary", qid)
    if spec.get("pbf") and not all(os.path.exists(raw(x)) for x in PARTS):
        from_pbf(spec, bq, lon0, lat0, raw)
    b = ask(raw("boundary"), Q_BOUNDARY.format(qid=bq, s=lat0 - 0.7, w=lon0 - 1, n=lat0 + 0.7, e=lon0 + 1))
    L = Local(lon0, lat0)
    rels = [(assemble(el, L), el) for el in b["elements"] if el["type"] == "relation"]
    rels = [(g, el) for g, el in rels if g is not None]
    if not rels:
        raise SystemExit(f"{qid}: no boundary relation found")
    outline, rel = max(rels, key=lambda t: t[0].area)
    levels = spec.get("levels") or [9, 10, 8]
    dis = ask(raw("districts"), Q_DISTRICTS.format(rid=rel["id"], levels="|".join(str(x) for x in levels)))["elements"]
    # (a level may be two of OSM's, "6|8": London's City, admin_level 6, among its boroughs, 8)
    if spec.get("drop") or spec.get("keep"):              # (a province without its rural districts: the rest's union;
        drop_, keep_ = spec.get("drop") or [], spec.get("keep")  #  or only the urban ones named, "keep")
        print(f"  outline: {levels[0]} districts " + (f"{', '.join(keep_)}" if keep_ else f"but {', '.join(drop_)}"))
        keep = [assemble(el, L) for el in dis if el["type"] == "relation" and level_key(el.get("tags", {})) in str(levels[0]).split("|")
                and el["tags"].get("name") not in drop_ and (not keep_ or el["tags"].get("name") in keep_)]
        outline = unary_union([g.buffer(1) for g in keep if g is not None]).buffer(-1).intersection(outline)
        outline = unary_union([p for p in parts(outline) if p.geom_type == "Polygon" and p.area > 1e6])
    shapely.prepare(outline)
    bw, bs, be, bn = L.back(outline).bounds
    pad = PAD_KM                                          # (the box the data is asked for: the outline's, a little more)
    w, s, e, n = (round(bw - pad / L.kx * 1000, 4), round(bs - pad / L.ky * 1000, 4), round(be + pad / L.kx * 1000, 4), round(bn + pad / L.ky * 1000, 4))
    bb = dict(s=s, w=w, n=n, e=e)
    lines = cached(raw("lines"), lambda: ask_box(raw("lines"), Q_LINES, bb))["elements"]
    areas = cached(raw("areas"), lambda: ask_box(raw("areas"), Q_AREAS, bb))["elements"]
    routes = ask(raw("routes"), Q_ROUTES.format(cref=COMMUTER_REF, cnet=COMMUTER_NET, **bb))["elements"]
    stops = ask_box(raw("stops"), Q_STOPS, bb)["elements"]
    inside = lambda g: g.intersection(outline)

    # THE AIRPORT: the city's (data/airports.csv: the busiest within AIRPORT_KM of its middle), whole, wherever it is
    airport, a = None, city_airport(lon0, lat0)
    if a:
        al, aa = float(a["lon"]), float(a["lat"])
        got = ask(raw("airport"), Q_AIRPORT.format(iata=a["iata"], s=aa - 0.1, w=al - 0.15, n=aa + 0.1, e=al + 0.15))["elements"]
        gs = [(assemble(el, L), el) for el in got]
        gs = [(g, el) for g, el in gs if g is not None and not g.is_empty]
        if gs:
            g, el = max(gs, key=lambda t: t[0].area)
            airport = (g, el.get("tags", {}))
    clip = unary_union([outline] + ([airport[0]] if airport else []))
    cw, cs, ce, cn = L.back(clip).bounds
    window = (round(cw, 4), round(cs, 4), round(ce, 4), round(cn, 4))
    W = Writer(L, (min(w, cw), min(s, cs), max(e, ce), max(n, cn)))

    # STREETS: by name (or number) and class -- a bridge one with the street, drawn over it apart (@bridges) --, made one
    # line for one road (one_line), cut to the outline, simplified between the junctions (which stay where they are)
    by = collections.defaultdict(list)
    bridge_ways = collections.defaultdict(list)
    for el in lines:
        t = el.get("tags", {})
        hw = "secondary" if t.get("highway") == "tertiary" and spec.get("tertiary") else t.get("highway")
        if el["type"] != "way" or hw not in STREETS:      # ("tertiary": a country's main streets so tagged, Denmark's --
            continue                                      #  drawn as secondary)
        pts = way_line(el)
        if len(pts) < 2:
            continue
        by[(t.get("name", ""), t.get("ref", ""), hw)].append(LineString(L.xy(pts)))
        if t.get("bridge") not in (None, "no"):
            bridge_ways[hw].append(LineString(L.xy(pts)))
    todo = []
    for (name, ref, cls), ls in by.items():
        for p in parts(merged(ls)):
            if p.geom_type == "LineString" and p.length > 0:
                todo.append((np.array(L.ll(p.coords)), {"name": name or None, "ref": ref or None, "class": cls}))
    todo.sort(key=lambda t: (STREETS.index(t[1]["class"]), -LineString(L.xy(t[0])).length))
    kept, ends = one_line(todo, SCALE["streets"])
    rows, drawn = [], collections.defaultdict(list)
    for c_, p in kept:
        arcs, geo = W.lines_at(pieces_at(c_, ends), SIMPLIFY_M["streets"], outline)
        if arcs:
            rows.append({**p, "arcs": arcs}); drawn[p["class"]] += geo
    rows.sort(key=lambda r: STREETS.index(r["class"]))
    W.obj("streets", "line", rows)
    n_streets = len(rows)
    # (the bridges: the streets drawn where a bridge way of that class runs, within its half-width)
    rows = []
    for cls, ls in bridge_ways.items():
        if not drawn[cls]:
            continue
        zone = unary_union([x.buffer(BRIDGE_M, cap_style="flat") for x in ls])
        for g in drawn[cls]:
            if not g.intersects(zone):
                continue
            for x in parts(g.intersection(zone)):
                if x.geom_type == "LineString" and x.length >= 8:
                    a = W.arc(L.ll(x.coords))
                    if a is not None:
                        rows.append({"class": cls, "arcs": str(a)})
    W.obj("bridges", "line", sorted(rows, key=lambda r: STREETS.index(r["class"])))

    # RAIL: each track by the routes over it -- a metro (route=subway), an S-Bahn (light_rail, or a train route numbered
    # S1...), or main rail; coloured by its route where all its routes of that kind have one colour. A metro's and an
    # S-Bahn's lines whole (Q_ROUTES: to their ends, out of the city too); main rail cut to the outline. The tracks of
    # one kind and colour made one line (one_line: a line's two directions, a station's many tracks)
    rels_ = {el["id"]: el for el in lines + routes if el["type"] == "relation"}
    over = collections.defaultdict(list)
    for r in rels_.values():
        for m in r.get("members", []):
            if m["type"] == "way":
                over[m["ref"]].append(r)
    def kind_of(r):
        t = r.get("tags", {})
        if t.get("route") == "subway":
            return "u"
        if t.get("route") == "light_rail" or commuter_train(t):
            return "s"
        return "r"
    reach = Point(0, 0).buffer(OUT_KM * 1000, 64)         # (a metro's, a commuter line's run: to its end, but not past this)
    ways = {el["id"]: el for el in lines + routes if el["type"] == "way" and "railway" in el.get("tags", {}) and len(way_line(el)) >= 2}
    tracks = collections.defaultdict(list)
    for wid, el in ways.items():
        t = el["tags"]
        rs = over.get(wid, [])
        kinds = {kind_of(r) for r in rs} or {"u" if t["railway"] == "subway" else "r"}
        k = "u" if "u" in kinds else "s" if "s" in kinds else "r"
        mine = [r for r in rs if kind_of(r) == k]
        cols = {r["tags"].get("colour", "").lower() for r in mine} - {""}
        refs = sorted({r["tags"].get("ref", "") for r in mine} - {""}, key=lambda x: (len(x), x))
        colour = cols.pop() if len(cols) == 1 else ""
        g = LineString(L.xy(way_line(el)))
        if k == "r":
            if not outline.intersects(g):
                continue
        elif not rs:                                      # (a metro track of no route: only in the city)
            if not outline.intersects(g):
                continue
        elif not reach.contains(g):
            g = reach.intersection(g)
            if g.is_empty:
                continue
        tracks[(k, colour, "|".join(refs) if k != "r" else "")].append(g)
    groups = collections.defaultdict(list)                # (one_line by kind and colour: the refs those of the longest)
    for key, ls in tracks.items():
        for p in parts(merged(ls)):
            if p.geom_type == "LineString" and p.length > 0:
                groups[key[:2]].append((np.array(L.ll(p.coords)), {"kind": key[0], "colour": key[1] or None, "lines": key[2].split("|") if key[2] else None}))
    rows, all_rail = [], []
    for kc in sorted(groups, key=lambda kc: ("usr".index(kc[0]), kc[1])):
        todo = sorted(groups[kc], key=lambda t: -LineString(L.xy(t[0])).length)
        kept, ends = one_line(todo, SCALE["rail"])
        for c_, p in kept:
            arcs, geo = W.lines_at(pieces_at(c_, ends), SIMPLIFY_M["rail"], outline if p["kind"] == "r" else None)
            if arcs:
                rows.append({**p, "arcs": arcs}); all_rail += [(p["kind"], g) for g in geo]
    W.obj("rail", "line", rows)
    n_rail = len(rows)

    # WATER and GREEN: areas merged by kind, the small ones left out; the large parks' and lakes' names kept apart
    water, green = [], {"park": [], "wood": []}
    named = []
    coast = []
    for el in areas:
        t = el.get("tags", {})
        if t.get("natural") == "coastline":
            if el["type"] == "way" and len(way_line(el)) > 1:
                coast.append(L.xy(way_line(el)))
            continue
        if t.get("aeroway") == "aerodrome":
            continue
        g = assemble(el, L)
        if g is None or g.is_empty:
            continue
        g = inside(g)
        if g.is_empty:
            continue
        ha = g.area / 1e4
        if t.get("natural") == "water" or t.get("waterway") == "riverbank":
            if ha >= MIN_HA["water"]:
                water.append(g)
                if t.get("name") and ha >= MIN_HA["label_lake"] and t.get("water") in (None, "lake", "pond", "reservoir"):
                    named.append(("lake", t["name"], g))
            continue
        k = "wood" if t.get("landuse") == "forest" or t.get("natural") in ("wood", "heath") else "park"
        if t.get("landuse") == "grass" and ha < 5:
            continue
        if ha >= MIN_HA[k]:
            green[k].append(g)
            if t.get("leisure") == "park" and t.get("name") and ha >= MIN_HA["label_park"]:
                named.append(("park", t["name"], g))
    sea_ = wet_sea = sea(coast, outline)
    if sea_ is not None and not sea_.is_empty:
        water.append(sea_)
        print(f"  sea: {sea_.area / 1e6:.0f} km^2 within {SEA_KM} km of the outline")
    wet = unary_union(water) if water else None
    rows = []
    for k in ("wood", "park"):
        if green[k]:
            g = unary_union([x.buffer(0) for x in green[k]])
            if wet is not None:
                g = g.difference(wet)
            if k == "park" and green["wood"]:
                g = g.difference(unary_union(green["wood"]))
            for x in parts(g):                            # (a row a piece: the page draws only those in view)
                rows.append({"kind": k, "arcs": W.polygon(x, SIMPLIFY_M["green"], MIN_HA["park"] * 1e4)})
    W.obj("green", "polygon", rows)
    W.obj("water", "polygon", [{"arcs": W.polygon(x, SIMPLIFY_M["water"], MIN_HA["water"] * 1e4)} for x in parts(wet)])
    by = collections.defaultdict(list)
    for el in lines:
        t = el.get("tags", {})
        if el["type"] == "way" and t.get("waterway") in ("river", "canal") and len(way_line(el)) > 1:
            by[(t["name"], t["waterway"])].append(LineString(L.xy(way_line(el))))
    rows = []
    for (name, k), ls in sorted(by.items()):
        g = inside(merged(ls))
        for p in parts(g):
            if p.geom_type == "LineString" and p.length > 300:
                rows.append({"name": name, "kind": k, "arcs": W.line(p, SIMPLIFY_M["waterways"])})
    W.obj("waterways", "line", rows)
    if airport:
        g, t = airport
        W.obj("airport", "polygon", [{"name": t.get("name:en") or t.get("name"), "iata": t.get("iata"), "arcs": W.polygon(g, SIMPLIFY_M["airport"])}])

    # MONUMENTS as areas: each of data/monuments.csv in the city that OSM maps as an area (by its wikidata: a palace and
    # its grounds, a square, a memorial's field) of MONUMENT_M across or more (its area's square
    # root; a closed way with an area's tag, a multipolygon); a statue, a column, a gate, a church stays a point
    mons = {}
    with open(os.path.join(ROOT, "data", "monuments.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["wikidata"] and outline.contains(Point(L.xy([(float(r["lon"]), float(r["lat"]))])[0])):
                mons[r["wikidata"]] = r
    rows = []
    if mons:
        got = ask(raw("monuments"), Q_MONUMENTS.format(ids="|".join(sorted(mons)), **bb))["elements"]
        best = {}
        for el in got:
            t = el.get("tags", {}); q = t.get("wikidata")
            if q not in mons or el["type"] == "node":
                continue
            if el["type"] == "relation" and t.get("type") != "multipolygon":
                continue                                  # (a site -- the Berlin Wall's: all the city's box -- a route, a bridge's parts)
            if el["type"] == "way" and not (AREA_TAGS & set(t)) or t.get("historic") == "wall":
                continue                                  # (a closed way of no area: a piece of wall, a ring road)
            g = assemble(el, L)
            if g is None or g.is_empty:
                continue
            g = inside(g)
            if g.is_empty or g.area <= 0:
                continue
            if q not in best or g.area > best[q].area:
                best[q] = g
        for q, g in sorted(best.items(), key=lambda kv: -kv[1].area):
            if g.area < MONUMENT_M ** 2 or g.area > MONUMENT_MAX_HA * 1e4:
                continue                                  # (a gate, a column, a church: its point; a whole quarter: not an area of this map)
            arcs = W.polygon(g, SIMPLIFY_M["monuments"])
            if arcs:
                rows.append({"name": mons[q]["name"], "wikidata": q, "arcs": arcs})
    W.obj("monuments", "polygon", rows)
    n_mons = len(rows)

    # DISTRICTS: each border once (a boundary way is one arc, however many districts share it), the finer level's only
    # where the coarser has none; their names where they go best (polylabel), inside the city
    found = collections.defaultdict(list)
    for el in dis:
        if el["type"] == "relation" and el.get("tags", {}).get("name"):
            g = assemble(el, L)
            if g is not None and outline.buffer(200).contains(g.representative_point()) and \
                    g.intersection(outline).area > 0.5 * g.area:  # (most of it within: not Kraainem past Brussels's edge)
                al = level_key(el["tags"])
                found[next((lv for lv in levels if al in str(lv).split("|")), int(al) if al.isdigit() else 0)].append((el, g))
    use = [lv for lv in levels if lv in found]
    if not spec.get("levels"):
        use = [lv for lv in use if 5 <= len(found[lv]) <= 40][:1]
    use = use[:2]
    seen, rows, places = {}, [], []
    for rank, lv in enumerate(use, 1):
        for el, g in found[lv]:
            for m in el.get("members", []):
                if m["type"] == "way" and m.get("geometry") and m["ref"] not in seen:
                    seen[m["ref"]] = rank
                    p = LineString(L.xy([(q["lon"], q["lat"]) for q in m["geometry"] if q]))
                    if wet_sea is not None:                   # (no border out at sea: Piraeus's in the Saronic Gulf)
                        p = p.difference(wet_sea)
                    rows.append({"level": rank, "arcs": ";".join(a_ for x in parts(p) if x.geom_type == "LineString"
                                                                 for a_ in [W.line(x, SIMPLIFY_M["districts"])] if a_)})
            land_ = g.difference(wet_sea) if wet_sea is not None else g
            big = max(parts(land_ if not land_.is_empty else g), key=lambda x: x.area)
            at = L.ll(polylabel(big, 20).coords)[0]
            places.append({"name": short(spec, el["tags"]["name"]), "level": rank, "lon": round(at[0], 5), "lat": round(at[1], 5)})
    W.obj("districts", "line", rows)
    W.points("places", places)
    # (the outline and airport: what the page cuts out of the map's own rivers, roads and railways)
    W.obj("clip", "polygon", [{"arcs": W.polygon(clip, SIMPLIFY_M["clip"])}])

    rows = []
    for k, name, g in sorted(named, key=lambda t: -t[2].area):
        big = max(parts(g), key=lambda x: x.area)
        at = L.ll(polylabel(big, 20).coords)[0]
        if not any(r["name"] == name for r in rows):
            rows.append({"name": name, "kind": k, "ha": round(g.area / 1e4), "lon": round(at[0], 5), "lat": round(at[1], 5)})
    W.points("parks", rows)

    # STATIONS: named stations and halts, one a name within 400 m (a U-Bahn and an S-Bahn station of one name are one),
    # what stops there from the lines nearest (within 80 m of a track of that kind) -- or the station's own tags; in the
    # city, and out of it along a metro's or an S-Bahn's line
    trk = {k: [g for kk, g in all_rail if kk == k] for k in "usr"}
    trees = {k: STRtree(v) if v else None for k, v in trk.items()}
    st, nodes = [], {el["id"]: el for el in lines + routes if el["type"] == "node"}
    # (how many train routes stop there: each route=train relation's (a commuter line's too), its stops and platforms
    #  (OSM's stop positions, @stops) within STOP_M -- a city's main stations those of the most, whatever they are called)
    at_ = {el["id"]: (el["lon"], el["lat"]) for el in stops if el["type"] == "node"}
    sp, sr = [], []
    for r in rels_.values():
        if r.get("tags", {}).get("route") == "train":
            for m in r.get("members", []):
                if m["type"] == "node" and m["ref"] in at_:
                    sp.append(Point(L.xy([at_[m["ref"]]])[0])); sr.append(r["id"])
    stree = STRtree(sp) if sp else None
    n_routes = lambda pt: {sr[i] for i in stree.query(pt, predicate="dwithin", distance=STOP_M)} if stree is not None else set()
    for el in nodes.values():
        t = el.get("tags", {})
        if not t.get("name") or t.get("railway") not in ("station", "halt") or re.search(AUTOZUG, t["name"]):
            continue
        if t.get("station") in ("tram", "funicular", "monorail", "miniature"):
            continue
        pt = Point(L.xy([(el["lon"], el["lat"])])[0])
        within = outline.contains(pt)
        ks = set()
        if t.get("station") == "subway" or t.get("subway") == "yes":
            ks.add("u")
        if t.get("station") == "light_rail" or t.get("light_rail") == "yes":
            ks.add("s")
        for k in "usr":
            tr = trees[k]
            if tr is not None and len(tr.query(pt, predicate="dwithin", distance=80)):
                ks.add(k)
        if not within:
            ks &= {k for k in "us" if trees[k] is not None and len(trees[k].query(pt, predicate="dwithin", distance=80))}
        if not ks:
            continue
        cat = t.get("railway:station_category", "")
        rank = 1 if (cat in ("1", "2") or "Hauptbahnhof" in t["name"]) else 2 if (cat == "3" or len(ks) > 1) else 3
        train = ("r" in ks and t.get("station") not in ("subway", "light_rail")) or t.get("train") == "yes"
        #  (a train station on tracks drawn as an S line's -- Bruxelles-Central's, under the Nord-Midi junction -- too)
        st.append({"name": t["name"], "ks": ks, "rank": rank, "pt": pt, "ll": (el["lon"], el["lat"]), "within": within,
                   "rs": n_routes(pt) if train else set()})
    # (a route counted at the nearest station it stops by: a terminus's routes not also its metro station's next door --
    #  Paris's Chateau-Landon by the Gare de l'Est; a metro station over the main line counts none)
    counted = collections.defaultdict(set)
    for i, p_ in enumerate(sp):
        near_ = [k for k, x in enumerate(st) if sr[i] in x["rs"]]
        if near_:
            counted[min(near_, key=lambda k: st[k]["pt"].distance(p_))].add(sr[i])
    weight = {r["id"]: 3 if r.get("tags", {}).get("service") in ("long_distance", "high_speed", "international") else 1
              for r in rels_.values()}                    # (an InterCity's or ICE's stop three: Dublin Heuston over the
    for k, x in enumerate(st):                            #  Maynooth line's halts, which more commuter routes are mapped by)
        x["nr"] = sum(weight.get(r_, 1) for r_ in counted[k])
    # (by their routes: a main station those of the most -- MAIN_STATIONS at most, a third of the busiest's routes or
    #  more --, an interchange a tenth's; the DB's categories as before. Out of the city: not a main station of this map)
    most = max([x["nr"] for x in st] + [0])
    tops = sorted((x for x in st if x["within"]), key=lambda x: -x["nr"])[:MAIN_STATIONS]
    for x in st:
        if x["nr"] >= max(6, most / 4) and any(x is y for y in tops):
            x["rank"] = 1
        elif x["nr"] >= max(3, most / 10):
            x["rank"] = min(x["rank"], 2)
        if not x["within"]:
            x["rank"] = max(x["rank"], 2)
    joined, town = [], {w for n_ in (c["name"], c.get("name_local", "")) for w in re.findall(r"\w+", n_.lower())}
    for x in sorted(st, key=lambda x: x["rank"]):
        for y in joined:
            if y["pt"].distance(x["pt"]) < 600 and any(
                    a in b_ or a.split()[:2] == b_.split()[:2] and len(a.split()) == 2 or core(a, town) == core(b_, town) != ""
                    or core(a, town) and set(core(a, town).split()) <= set(core(b_, town).split())   # (Wien Hauptbahnhof,
                    #  Suedtiroler Platz - Hauptbahnhof: its U-Bahn's)
                    for n_, _ in y["all"] for a, b_ in [sorted((same(n_), same(x["name"])), key=len)]):
                # (one name in the other -- "Berlin Hauptbahnhof Tunnel (S-Bahn)", Munich's U-Bahn "Hauptbahnhof (tief)" -- or
                #  the same first two words: "München Hbf Gleis 27-36"; the name kept: the shortest of two words or more,
                #  "München Hauptbahnhof", not the U-Bahn's bare "Hauptbahnhof")
                y["all"].append((x["name"], x["nr"]))
                y["ks"] |= x["ks"]; y["rank"] = min(y["rank"], x["rank"], 2 if len(y["ks"]) > 1 else y["rank"])
                break
        else:
            joined.append(dict(x, all=[(x["name"], x["nr"])]))
    for y in joined:                                      # (the name: of the one most trains stop at -- Saint-Lazare, not its
        top = max(y["all"], key=lambda t: t[1])[0]        #  RER station's next door, Haussmann - Saint-Lazare --, the shortest
        ns = [n_ for n_, _ in y["all"] if core(n_, town) == core(top, town)] or [top]       # of two words or more of
        y["name"] = min(ns, key=lambda n_: (bool(re.match(r"[SU] ", n_)), len(same(n_).split()) < 2, len(n_)))           #  its names: Zoologischer Garten)
    W.points("stations", [{"name": x["name"], "kind": "".join(k for k in "usr" if k in x["ks"]), "rank": x["rank"],
                            "lon": round(x["ll"][0], 5), "lat": round(x["ll"][1], 5)} for x in sorted(joined, key=lambda x: (x["rank"], x["name"]))])

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, qid + ".txt")
    text = W.text(f"{c['name']}: a city detail map (build/citymaps.py; OSM, ODbL)")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    raw_b, gz_b = len(text.encode()), len(gzip.compress(text.encode(), 9))
    print(f"  -> data/city/{qid}.txt: {raw_b / 1e3:.0f} KB, {gz_b / 1e3:.0f} KB gzipped; {len(W.arcs)} arcs, {n_streets} street lines, "
          f"{n_rail} rail lines, {len(places)} district names, {len(joined)} stations, {n_mons} monument areas, "
          f"airport {airport[1].get('iata') if airport else 'none'}; levels {use}")
    return {"wikidata": qid, "name": c["name"], "w": window[0], "s": window[1], "e": window[2], "n": window[3], "bytes": raw_b, "gz": gz_b}


def write_index():
    """data/city/index.csv: every city file there, its window -- what the page reads to know where a city map applies"""
    rows = []
    for spec in CITIES:
        qid = spec["wikidata"]; path = os.path.join(OUT, qid + ".txt")
        if not os.path.exists(path):
            continue
        c = city_row(qid)
        win = json.load(open(os.path.join(RAW, f"{qid}_window.json")))
        rows.append([qid, c["name"], *win, os.path.getsize(path)])
    with open(os.path.join(OUT, "index.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["wikidata", "name", "w", "s", "e", "n", "bytes"])
        w.writerows(rows)
    print(f"data/city/index.csv: {len(rows)} cities")


def main():
    only = set(sys.argv[1:])
    for spec in CITIES:
        if only and spec["wikidata"] not in only:
            continue
        fp = os.path.join(RAW, f"{spec['wikidata']}_coarser.json")   # (the step it took last time: built again from there)
        f = json.load(open(fp)) if os.path.exists(fp) else 1  # (over BUDGET_KB gzipped: again, coarser -- from the step its size
        while True:                                       #  says, the file about as the square root of f smaller: London's)
            r = build(spec, f)
            if r["gz"] <= BUDGET_KB * 1000 or f == COARSER[-1]:
                break
            guess = 0.85 * (r["gz"] / (BUDGET_KB * 1000)) ** 2 * f
            f = next((x for x in COARSER if x > f and x >= guess), COARSER[-1]) if f == 1 else next(x for x in COARSER if x > f)
        with open(fp, "w") as fh:
            json.dump(f, fh)
        with open(os.path.join(RAW, f"{spec['wikidata']}_window.json"), "w") as fh:
            json.dump([r["w"], r["s"], r["e"], r["n"]], fh)
    write_index()


if __name__ == "__main__":
    main()
