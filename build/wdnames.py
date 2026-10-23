"""NAMES: everything is called by its English name, and by one local name -- in the official language of its country
(Arabic in Morocco, not also Berber or French; for a river, one in each official language of the countries it flows
through). The English and local labels come from Wikidata, fetched a few hundred at a time from QLever and cached in
raw/ (wd_labels.json for English, wd_labels_local.json for the rest, wd_official_languages.json).

A country's official languages are Wikidata's (P37) that have a two-letter code (P218, ISO 639-1): the languages of
the state, not every recognized one -- with OVERRIDE where Wikidata has none or would put a minor one first."""
import os, json, re, time, collections
import requests

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
QLEVER = "https://qlever.dev/api/wikidata"
UA = {"User-Agent": "welle-map-builder/0.1 (world map layers from OSM + Wikidata)", "Accept": "application/sparql-results+json"}
PREFIX = """PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
_cache = {}
# where Wikidata has none, or lists them in an order that would pick a minor one first (the first is the one used)
OVERRIDE = {
    "US": ["en"], "CN": ["zh-hans", "zh"], "TW": ["zh-hant", "zh"], "HK": ["zh-hant", "zh", "en"], "MO": ["zh-hant", "pt"],
    "SG": ["en", "ms", "zh-hans", "ta"], "GR": ["el"], "ME": ["sr"],
    "UY": ["es"], "BF": ["fr"], "GP": ["fr"], "MQ": ["fr"], "CP": ["fr"], "FK": ["en"], "GI": ["en"], "BV": ["no"],
    "AU": ["en"], "CH": ["de", "fr", "it"], "BE": ["nl", "fr", "de"], "CA": ["en", "fr"], "KZ": ["kk", "ru"],
    "BY": ["be", "ru"], "CY": ["el", "tr"], "AF": ["ps", "fa"], "LU": ["lb", "fr", "de"], "NO": ["nb", "nn"],
    "ZA": ["en", "af", "zu", "xh"], "ZW": ["en"], "IM": ["en", "gv"],
    "MT": ["mt", "en"], "FI": ["fi", "sv"], "VA": ["it", "la"], "MK": ["mk", "sq"], "XK": ["sq", "sr"],
    "BA": ["bs", "hr", "sr"], "ML": ["fr"], "RW": ["rw", "en", "fr"], "MG": ["mg", "fr"], "SN": ["fr"],
    "ER": ["ti", "ar", "en"], "MU": ["en", "fr"], "SC": ["en", "fr"], "VU": ["bi", "en", "fr"], "BI": ["rn", "fr", "en"],
    "DJ": ["fr", "ar"], "TD": ["fr", "ar"], "KM": ["fr", "ar"], "MR": ["ar"], "TZ": ["sw", "en"], "KE": ["sw", "en"],
    "PE": ["es"], "BO": ["es"], "PR": ["es", "en"], "CM": ["fr", "en"], "GG": ["en", "fr"], "IE": ["ga", "en"],
}


def sparql(q):
    for attempt in range(6):
        try:
            r = requests.post(QLEVER, data={"query": PREFIX + q}, headers=UA, timeout=300)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            print("wikidata", r.status_code, "- retrying", flush=True)
        except requests.RequestException as e:
            print("wikidata", type(e).__name__, "- retrying", flush=True)
        time.sleep(20 * (attempt + 1))
    raise SystemExit("wikidata failed")


def official_languages():
    """{ISO 3166-1 alpha-2: [ISO 639-1 codes]} (cached)"""
    path = os.path.join(RAW, "wd_official_languages.json")
    if not os.path.exists(path):
        out = collections.defaultdict(list)
        for b in sparql("SELECT ?iso ?code WHERE { ?c wdt:P297 ?iso . ?c wdt:P37 ?l . ?l wdt:P218 ?code . }"):
            iso, code = b["iso"]["value"].upper(), b["code"]["value"].lower()
            if code not in out[iso]:
                out[iso].append(code)
        json.dump(out, open(path, "w"), indent=0, sort_keys=True)
    if "langs" not in _cache:
        _cache["langs"] = {**json.load(open(path)), **OVERRIDE}
    return _cache["langs"]


def labels(qids, lang):
    """{qid: its label in lang, or None} (cached)"""
    path = os.path.join(RAW, "wd_labels.json" if lang == "en" else "wd_labels_local.json")
    if path not in _cache:
        _cache[path] = json.load(open(path)) if os.path.exists(path) else {}
    store = _cache[path] if lang == "en" else _cache[path].setdefault(lang, {})
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in store})
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in sparql(f'SELECT ?item ?l WHERE {{ VALUES ?item {{ {vals} }} ?item rdfs:label ?l . FILTER(LANG(?l) = "{lang}") }}'):
            store[b["item"]["value"].rsplit("/", 1)[-1]] = b["l"]["value"]
        for x in need[i:i + 400]:
            store.setdefault(x, None)
    if need:
        json.dump(_cache[path], open(path, "w"), ensure_ascii=False)
    return {q: store.get(q) for q in qids}


def items_named(names, cls):
    """{English label: [(qid, lon, lat, Wikipedias)]} -- the Wikidata items of class cls (or under it) with that English
    label, and their place if they have one (cached in raw/wd_items_<cls>.json)"""
    path = os.path.join(RAW, f"wd_items_{cls}.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({n for n in names if n and n not in have})
    for i in range(0, len(need), 150):
        vals = " ".join(json.dumps(n, ensure_ascii=False) + "@en" for n in need[i:i + 150])
        for b in sparql(f"""PREFIX schema: <http://schema.org/> PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?item ?l (SAMPLE(?c) AS ?cc) (COUNT(DISTINCT ?a) AS ?n) WHERE {{ VALUES ?l {{ {vals} }} ?item rdfs:label ?l .
  ?item wdt:P31/wdt:P279* wd:{cls} . OPTIONAL {{ ?item wdt:P625 ?c . }}
  OPTIONAL {{ ?a schema:about ?item . ?a schema:isPartOf ?w . ?w wikibase:wikiGroup "wikipedia" . }} }} GROUP BY ?item ?l"""):
            m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", b.get("cc", {}).get("value", ""), re.I)
            have.setdefault(b["l"]["value"], []).append((b["item"]["value"].rsplit("/", 1)[-1], float(m.group(1)) if m else None,
                                                         float(m.group(2)) if m else None, int(b["n"]["value"])))
        for n in need[i:i + 150]:
            have.setdefault(n, [])
        json.dump(have, open(path, "w"), ensure_ascii=False)
    return {n: have.get(n, []) for n in names}


def part_of(qids):
    """{qid: the item it is part of (P361), for those that are part of one of the given items} (cached in
    raw/wd_part_of.json: every P361 target, filtered here)"""
    path = os.path.join(RAW, "wd_part_of.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in sparql(f"SELECT ?item ?p WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P361 ?p . }}"):
            have.setdefault(b["item"]["value"].rsplit("/", 1)[-1], []).append(b["p"]["value"].rsplit("/", 1)[-1])
        for q in need[i:i + 400]:
            have.setdefault(q, [])
    if need:
        json.dump(have, open(path, "w"))
    given = set(qids)
    return {q: next((p for p in have.get(q, []) if p in given), None) for q in qids if have.get(q)}


def wikipedias(qids):
    """{qid: how many Wikipedias have an article on it} (cached in raw/wd_wikipedias.json)"""
    path = os.path.join(RAW, "wd_wikipedias.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    for i in range(0, len(need), 400):
        vals = " ".join("wd:" + q for q in need[i:i + 400])
        for b in sparql(f"""PREFIX schema: <http://schema.org/> PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?item (COUNT(DISTINCT ?a) AS ?n) WHERE {{ VALUES ?item {{ {vals} }} ?a schema:about ?item . ?a schema:isPartOf ?w . ?w wikibase:wikiGroup "wikipedia" . }} GROUP BY ?item"""):
            have[b["item"]["value"].rsplit("/", 1)[-1]] = int(b["n"]["value"])
        for q in need[i:i + 400]:
            have.setdefault(q, 0)
    if need:
        json.dump(have, open(path, "w"))
    return {q: have.get(q, 0) for q in qids}


def language_names():
    """{ISO 639-1 code: the language's English name} (cached in raw/wd_language_names.json)"""
    path = os.path.join(RAW, "wd_language_names.json")
    if not os.path.exists(path):
        out = {}
        for b in sparql('SELECT ?code ?n WHERE { ?l wdt:P218 ?code . ?l rdfs:label ?n . FILTER(LANG(?n) = "en") }'):
            out.setdefault(b["code"]["value"].lower(), b["n"]["value"])
        json.dump(out, open(path, "w"), ensure_ascii=False, sort_keys=True)
    return json.load(open(path))


def english(qids):
    return labels(qids, "en")


def local_labels(items):
    """[(qid, country)] -> [the item's label in its country's first official language that has one, or None]"""
    langs = official_languages()
    want = collections.defaultdict(set)
    for q, cc in items:
        if q:
            for lang in langs.get(cc or "", []):
                want[lang].add(q)
    got = {lang: labels(sorted(qs), lang) for lang, qs in want.items()}
    return [next((got[l].get(q) for l in langs.get(cc or "", []) if q and got[l].get(q)), None) for q, cc in items]


def local_name(tags, country):
    """an OSM feature's name in its country's official language: its name:<lang> for one of them -- the one that its
    own `name` is, or holds, if several (Geneva is "Genève", not "Genf") -- else its `name`"""
    name = tags.get("name")
    low = {k.lower(): v for k, v in tags.items()}                 # (OSM writes name:zh-Hans)
    names = [low.get(f"name:{lang}") for lang in official_languages().get(country or "", [])]
    names = [n for n in names if n]
    for n in names:
        if name and n in name:
            return n
    return names[0] if names else name


def rename(props):
    """props with "name" and "wikidata" (a list of them, changed in place): the English name first, the own one kept.
    A piece without an item (most of a river's OSM ways have none) is named like the pieces of the same local name
    that have one: by the English name that most of their length (or area) has -- 60% or more. A piece whose item's
    name is its own votes too, for that name (the Colorado's US ways); an item named with a qualifier in brackets
    ("Colorado River (Maule)") is one river of several of that name, so it names its own pieces only (not Argentina's
    Río Colorado)."""
    en = english([p.get("wikidata") for p in props])
    local = {}
    for p in props:
        e = en.get(p.get("wikidata"))
        if e and e != p.get("name"):
            p["name_local"] = p.get("name")
            p["name"] = e
        own = p.get("name_local") or (p.get("name") if e else None)
        if own and not re.search(r"\(.+\)$", p["name"]):
            c = local.setdefault(own, {})
            c[p["name"]] = c.get(p["name"], 0) + (p.get("length_km") or p.get("area_km2") or 1)
    best = {}
    for k, c in local.items():
        name, w = max(c.items(), key=lambda kv: kv[1])
        if w >= 0.6 * sum(c.values()):
            best[k] = name
    for p in props:
        if not p.get("wikidata") and not p.get("name_local") and p.get("name") in best:
            p["name_local"] = p["name"]
            p["name"] = best[p["name_local"]]
    return props
