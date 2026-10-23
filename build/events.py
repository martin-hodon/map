"""HISTORICAL EVENTS: battles, sieges, peace treaties and other treaties, assassinations, massacres, coups, revolutions
and rebellions, terror attacks, earthquakes and eruptions that enough Wikipedias write about -- each where and when it
happened, from Wikidata (CC0).

    .venv/bin/python build/events.py          # QLever -> raw/wd_events.json (kept) -> data/events.csv

One a line under a header (as the other point layers, build/points.write_points):
    name, lon, lat, date, precision, calendar, kind, part_of, wikipedias, place, wikidata
date: as Wikidata gives it, cut to its precision ("1066-10-14", "1415-06", "-0479", a year before 1 AD astronomical:
0 is 1 BC, -479 is 480 BC); precision: day, month, year, decade, century; calendar: julian where the date is Julian
(as historians cite one before 1582 -- Hastings on 14 October), else empty (Gregorian). place: own (the event's own
coordinates) or location (those of the place it happened in -- a city, a palace: one that is a country or a region
is no place). An event with no date or no place is left out; one in several classes is the first kind of KINDS.
"""
import os, re, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_points as fp
from points import write_points
from dates import days, julian, year_text

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw/wd_events.json")
OUT = os.path.join(ROOT, "data/events.csv")
# (kind, Wikidata class -- with every class under it --, the Wikipedias that must write about one): the more specific first
KINDS = [("siege", "Q188055", 10), ("battle", "Q178561", 10), ("peace treaty", "Q625298", 8), ("treaty", "Q131569", 12),
         ("assassination", "Q3882219", 10), ("massacre", "Q3199915", 15), ("coup", "Q45382", 12), ("revolution", "Q10931", 15),
         ("rebellion", "Q124734", 15), ("terror attack", "Q2223653", 25), ("earthquake", "Q7944", 15), ("eruption", "Q7692360", 10)]
COLUMNS = ["name", "lon", "lat", "date", "precision", "calendar", "kind", "part_of", "wikipedias", "place", "wikidata"]
PRECISION = {7: "century", 8: "decade", 9: "year", 10: "month", 11: "day"}
JULIAN = "http://www.wikidata.org/entity/Q1985786"
# a location that is a whole country, a historical one, a region or a first-level division is no place for a point
NOPLACE = ["Q6256", "Q3624078", "Q3024240", "Q82794", "Q10864048", "Q5107"]


def query(root, least):
    nope = " ".join(f"wd:{q}" for q in NOPLACE)
    return f"""PREFIX schema: <http://schema.org/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
SELECT ?item (SAMPLE(?l) AS ?label) (SAMPLE(?c) AS ?coord) (SAMPLE(?c2) AS ?coord2)
       (SAMPLE(?t) AS ?time) (SAMPLE(?pr) AS ?prec) (SAMPLE(?cal) AS ?calendar) (SAMPLE(?t2) AS ?start) (SAMPLE(?pr2) AS ?prec2) (SAMPLE(?cal2) AS ?calendar2)
       (SAMPLE(?t3) AS ?inception) (SAMPLE(?pr3) AS ?prec3) (SAMPLE(?cal3) AS ?calendar3) (SAMPLE(?pl) AS ?partof) (COUNT(DISTINCT ?a) AS ?n) WHERE {{
  ?item wdt:P31/wdt:P279* wd:{root} .
  ?a schema:about ?item . ?a schema:isPartOf ?w . ?w wikibase:wikiGroup "wikipedia" .
  OPTIONAL {{ ?item wdt:P625 ?c }}
  OPTIONAL {{ ?item wdt:P276 ?loc . ?loc wdt:P625 ?c2 . FILTER NOT EXISTS {{ ?loc wdt:P31/wdt:P279* ?k . VALUES ?k {{ {nope} }} }} }}
  OPTIONAL {{ ?item p:P585/psv:P585 ?v . ?v wikibase:timeValue ?t ; wikibase:timePrecision ?pr ; wikibase:timeCalendarModel ?cal }}
  OPTIONAL {{ ?item p:P580/psv:P580 ?v2 . ?v2 wikibase:timeValue ?t2 ; wikibase:timePrecision ?pr2 ; wikibase:timeCalendarModel ?cal2 }}
  OPTIONAL {{ ?item p:P571/psv:P571 ?v3 . ?v3 wikibase:timeValue ?t3 ; wikibase:timePrecision ?pr3 ; wikibase:timeCalendarModel ?cal3 }}
  OPTIONAL {{ ?item wdt:P361 ?p . ?p rdfs:label ?pl . FILTER(LANG(?pl) = "en") }}
  OPTIONAL {{ ?item rdfs:label ?l . FILTER(LANG(?l) = "en") }}
}} GROUP BY ?item HAVING (COUNT(DISTINCT ?a) >= {least})"""


def fetch():
    got = json.load(open(RAW)) if os.path.exists(RAW) else {}
    for kind, root, least in KINDS:
        key = f"{root}:{least}"
        if key in got:
            continue
        got[key] = [{k: v["value"] for k, v in b.items()} for b in fp.sparql(query(root, least), fp.QLEVER)]
        print(f"  {kind} ({root}, {least}+ Wikipedias): {len(got[key])}", flush=True)
        json.dump(got, open(RAW, "w"))
    return got


def when(b):
    """the event's date as Wikidata cites it -> (text cut to its precision, precision, "julian" or "") or None"""
    for t, p, c in (("time", "prec", "calendar"), ("start", "prec2", "calendar2"), ("inception", "prec3", "calendar3")):
        if t not in b:
            continue
        s, prec = b[t], int(b.get(p, 9))
        if prec < 7:
            return None
        neg = s.startswith("-")
        y, m, d = (int(x) for x in s.lstrip("-").split("T")[0].split("-"))
        y = -y if neg else y
        cal = ""
        if b.get(c) == JULIAN and prec >= 11:                # (the RDF value is turned Gregorian: back to the day it is cited by)
            y, m, d = julian(days(y, m, d)); cal = "julian"
        elif b.get(c) == JULIAN:
            cal = "julian"
        ys = year_text(y)
        text = ys if prec <= 9 else f"{ys}-{m:02d}" if prec == 10 else f"{ys}-{m:02d}-{d:02d}"
        return text, PRECISION[min(prec, 11)], cal
    return None


def point(s):
    """"POINT(lon lat)" -> (lon, lat); an unknown value (a blank node) -> None"""
    m = re.fullmatch(r"POINT\(([-\d.eE]+) ([-\d.eE]+)\)", s or "")
    return (float(m[1]), float(m[2])) if m else None


def main():
    got = fetch()
    rows, seen, dropped = [], set(), {"no date": 0, "no place": 0}
    for kind, root, least in KINDS:
        for b in got[f"{root}:{least}"]:
            q = b["item"].rsplit("/", 1)[-1]
            if q in seen:
                continue
            seen.add(q)
            w = when(b)
            own = point(b.get("coord")); pt = own or point(b.get("coord2"))
            if not w or not pt:
                dropped["no date" if not w else "no place"] += 1
                continue
            lon, lat = pt
            rows.append({"name": b.get("label") or q, "lon": lon, "lat": lat, "date": w[0], "precision": w[1], "calendar": w[2],
                         "kind": kind, "part_of": b.get("partof"), "wikipedias": int(b["n"]), "place": "own" if own else "location",
                         "wikidata": q})
    rows.sort(key=lambda r: -r["wikipedias"])                 # (the best known first, as the monuments)
    write_points(rows, COLUMNS, OUT)
    print(f"{OUT}: {len(rows)} events; left out: {dropped}")
    print(collections.Counter(r["kind"] for r in rows).most_common())


if __name__ == "__main__":
    main()
