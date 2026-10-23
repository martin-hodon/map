"""The raw points: every city and town OpenStreetMap knows (Overpass), and every item Wikidata gives a yearly visitor
count (P1174) with a place on the globe (P625), with what it is (P31) and the classes above those (P279).

    .venv/bin/python build/fetch_points.py        # -> raw/osm_places.json, raw/wd_visitors.json, raw/wd_classes.json
    .venv/bin/python build/fetch_points.py wikidata   # (only the Wikidata part)

Both are public: OSM under ODbL, Wikidata CC0. The numbers are chosen later (build/points.py): this keeps all of it.
"""
import json, os, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
UA = {"User-Agent": "welle-map-builder/0.1 (world map layers from OSM + Wikidata)"}
OVERPASS = "https://overpass-api.de/api/interpreter"
WDQS = "https://query.wikidata.org/sparql"
QLEVER = "https://qlever.dev/api/wikidata"     # (for the one big query: WDQS stops every query at 60 s)
PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/> PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/> PREFIX wikibase: <http://wikiba.se/ontology#>
"""
MIN_VISITORS = 100_000      # (build/points.py's: only these items are looked up further)
# the well-known kinds: (kind, Wikidata class, the Wikipedias that must write about one) -- fewer for a castle than for
# a church or a tower, of which there are far more
FAMOUS = [("castle", "Q23413", 15), ("palace", "Q16560", 15), ("palace", "Q751876", 20), ("religious", "Q2977", 15), ("religious", "Q16970", 40),
          ("religious", "Q32815", 25), ("religious", "Q44539", 20), ("religious", "Q44613", 20), ("castle", "Q57821", 20),
          ("archaeological", "Q839954", 20), ("archaeological", "Q15661340", 20), ("tomb", "Q381885", 20),
          ("tomb", "Q162875", 20), ("tomb", "Q12516", 20), ("monument", "Q4989906", 25), ("monument", "Q179700", 25),
          ("tower", "Q12518", 30), ("bridge", "Q12280", 12), ("dam", "Q12323", 10), ("national park", "Q46169", 25), ("waterfall", "Q34038", 20)]


def overpass(q, out):
    if os.path.exists(out):
        return
    for attempt in range(5):
        r = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=1200)
        if r.status_code == 200:
            open(out, "wb").write(r.content)
            print(out, len(r.content) // 1024, "KB")
            return
        print("overpass", r.status_code, r.text[:200], "- retrying"); time.sleep(60 * (attempt + 1))
    sys.exit("overpass failed")


def sparql(q, endpoint=WDQS):
    for attempt in range(6):
        try:
            r = requests.post(endpoint, data={"query": PREFIXES + q, "format": "json"}, headers={**UA, "Accept": "application/sparql-results+json"}, timeout=600)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            print("sparql", r.status_code, r.text[:200], "- retrying")
        except requests.RequestException as e:
            print("sparql", type(e).__name__, "- retrying")
        time.sleep(30 * (attempt + 1))
    sys.exit("wikidata failed")


def main():
    os.makedirs(RAW, exist_ok=True)
    # ---- every city and town (their population is read later: its tag, or Wikidata's for the ones without)
    if "wikidata" not in sys.argv[1:]:
        overpass('[out:json][timeout:1200];node["place"~"^(city|town)$"];out body qt;', os.path.join(RAW, "osm_places.json"))

    # ---- Wikidata: everything with a yearly visitor count and a place; each count with its year. (In small queries:
    # the statements alone first, then what they are, their OSM ids and names only for the items with a count of
    # MIN_VISITORS or more, a few hundred at a time -- one query for all of it runs past the service's time limit.)
    out = os.path.join(RAW, "wd_visitors.json")
    if not os.path.exists(out):
        stm = sparql("""
SELECT ?item ?coord ?visitors ?year ?rank WHERE {
  ?item p:P1174 ?st . ?st ps:P1174 ?visitors ; wikibase:rank ?rank .
  OPTIONAL { ?st pq:P585 ?date . BIND(YEAR(?date) AS ?year) }
  ?item wdt:P625 ?coord .
}""", QLEVER)
        stm = [b for b in stm if not b["rank"]["value"].endswith("DeprecatedRank")     # (in QLever a FILTER on it drops most rows)
               and b["visitors"]["type"] == "literal"]                            # (not "unknown value")
        print(len(stm), "visitor counts")
        big = sorted({b["item"]["value"].rsplit("/", 1)[-1] for b in stm if float(b["visitors"]["value"]) >= MIN_VISITORS})
        extra = {}
        for i in range(0, len(big), 300):
            vals = " ".join("wd:" + q for q in big[i:i + 300])
            for b in sparql(f"""SELECT ?item ?itemLabel (GROUP_CONCAT(DISTINCT STR(?type); separator=" ") AS ?types) (SAMPLE(?w) AS ?osmway) (SAMPLE(?r) AS ?osmrel) WHERE {{
  VALUES ?item {{ {vals} }}
  OPTIONAL {{ ?item wdt:P31 ?type . }} OPTIONAL {{ ?item wdt:P10689 ?w . }} OPTIONAL {{ ?item wdt:P402 ?r . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul,de,fr,es,it,ru,zh,ja" . }}
}} GROUP BY ?item ?itemLabel"""):
                extra[b["item"]["value"].rsplit("/", 1)[-1]] = {k: v for k, v in b.items() if k != "item"}
            print(" items", min(i + 300, len(big)), "/", len(big), flush=True); time.sleep(2)
        rows = [{**b, **extra[q]} for b in stm for q in [b["item"]["value"].rsplit("/", 1)[-1]] if q in extra]
        json.dump(rows, open(out, "w"))
        print(out, len(rows), "rows")
    rows = json.load(open(out))

    # ---- the classes those items are instances of, with every class above them (to tell a castle from a museum)
    out = os.path.join(RAW, "wd_classes.json")
    if not os.path.exists(out):
        types = sorted({t.rsplit("/", 1)[-1] for r in rows for t in r.get("types", {}).get("value", "").split() if t})
        print(len(types), "classes")
        found = {}
        for i in range(0, len(types), 100):
            vals = " ".join("wd:" + t for t in types[i:i + 100])
            for b in sparql(f"SELECT ?c ?super WHERE {{ VALUES ?c {{ {vals} }} ?c wdt:P279* ?super . }}"):   # (WDQS: QLever gets this path wrong)
                c = b["c"]["value"].rsplit("/", 1)[-1]
                found.setdefault(c, {})[b["super"]["value"].rsplit("/", 1)[-1]] = ""
            print(" classes", min(i + 100, len(types)), "/", len(types), flush=True); time.sleep(2)
        json.dump(found, open(out, "w"))

    # ---- the well-known ones, whether Wikidata counts their visitors or not: castles, palaces, cathedrals... that
    # FAMOUS_MIN or more Wikipedias write about (each kind with every class under it), and every World Heritage Site
    out = os.path.join(RAW, "wd_famous.json")
    done_path = os.path.join(RAW, "wd_famous_done.json")          # (which classes, at which count, are in the file)
    rows = json.load(open(out)) if os.path.exists(out) else []
    done = json.load(open(done_path)) if os.path.exists(done_path) else ([[k, r, 30 if r == "Q12280" else l] for k, r, l in FAMOUS if r != "Q12323"] + [["heritage", "Q9259", 0]] if rows else [])
    todo = [(k, r, l) for k, r, l in FAMOUS if [k, r, l] not in done]
    if todo or ["heritage", "Q9259", 0] not in done:
        for kind, root, least in todo:
            rows = [x for x in rows if x.get("root") != root and not (x["kind"] == kind and "root" not in x)]   # (fetched anew: a class at another count)
            got = sparql(f"""PREFIX schema: <http://schema.org/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?item (SAMPLE(?c) AS ?coord) (SAMPLE(?l) AS ?label) (COUNT(DISTINCT ?a) AS ?n) WHERE {{
  ?item wdt:P31/wdt:P279* wd:{root} . ?item wdt:P625 ?c .
  ?a schema:about ?item . ?a schema:isPartOf ?w . ?w wikibase:wikiGroup "wikipedia" .
  OPTIONAL {{ ?item rdfs:label ?l . FILTER(LANG(?l) = "en") }}
}} GROUP BY ?item HAVING (COUNT(DISTINCT ?a) >= {least})""", QLEVER)
            rows += [{"item": b["item"]["value"].rsplit("/", 1)[-1], "kind": kind, "root": root, "n": int(b["n"]["value"]),
                      "coord": b["coord"]["value"], "label": b.get("label", {}).get("value")} for b in got]
            done = [d for d in done if not (d[0] == kind and d[1] == root)] + [[kind, root, least]]
            print(f"  famous {kind} ({root}, {least}+ Wikipedias): {len(got)}", flush=True)
            json.dump(rows, open(out, "w")); json.dump(done, open(done_path, "w"))
    if ["heritage", "Q9259", 0] not in done:
        got = sparql("""PREFIX schema: <http://schema.org/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?item (SAMPLE(?c) AS ?coord) (SAMPLE(?l) AS ?label) (COUNT(DISTINCT ?a) AS ?n) WHERE {
  ?item wdt:P1435 wd:Q9259 . ?item wdt:P625 ?c .
  OPTIONAL { ?a schema:about ?item . ?a schema:isPartOf ?w . ?w wikibase:wikiGroup "wikipedia" . }
  OPTIONAL { ?item rdfs:label ?l . FILTER(LANG(?l) = "en") }
} GROUP BY ?item""", QLEVER)
        rows += [{"item": b["item"]["value"].rsplit("/", 1)[-1], "kind": "heritage", "root": "Q9259", "n": int(b["n"]["value"]),
                  "coord": b["coord"]["value"], "label": b.get("label", {}).get("value")} for b in got]
        print(f"  World Heritage Sites: {len(got)}", flush=True)
        json.dump(rows, open(out, "w")); json.dump(done + [["heritage", "Q9259", 0]], open(done_path, "w"))

    # ---- airports: OurAirports' list (public domain), and OpenFlights' routes (ODbL) to tell the international ones
    for name, url in (("ourairports.csv", "https://davidmegginson.github.io/ourairports-data/airports.csv"),
                      ("openflights_routes.dat", "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat")):
        out = os.path.join(RAW, name)
        if not os.path.exists(out):
            r = requests.get(url, headers=UA, timeout=300)
            r.raise_for_status()
            open(out, "wb").write(r.content)
            print(out, len(r.content) // 1024, "KB")
    print("points fetched")


if __name__ == "__main__":
    main()
