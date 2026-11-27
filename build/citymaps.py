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
# out of the outline -- a province's rural ones (the outline then the union of the rest), or `keep`, only these in it;
# `strip`, what to cut from the districts' names (a regex: "London Borough of "; or [regex, replacement] pairs);
# `skip`, districts left out (a former one OSM still bounds: Turin's "Mirafiori Sud");
# `tertiary`, OSM's tertiary roads drawn as secondary (where a country's main streets are so tagged: Denmark, Sweden);
# `place`, [name, lon, lat] for a city not in data/cities.csv (Venice, Dubrovnik);
# `airport`, [iata, lon, lat] when the busiest within AIRPORT_KM is not the city's (Rotterdam's RTM, not Schiphol);
# `pbf`, the Geofabrik region whose extract to read (build/citypbf.py).
CITIES = [
    {"wikidata": "Q64", "levels": [9, 10]},               # Berlin: the 12 Bezirke outlined, the 96 Ortsteile named closer in
    {"wikidata": "Q1726", "levels": [9]},                 # Munich: the 25 Stadtbezirke
    # (from here on from Geofabrik's extracts, `pbf`: Overpass was too slow for a city a day)
    {"wikidata": "Q84", "core": [-0.1250, 51.5070, 1.2], "levels": ["6|8"], "strip": "^(London Borough of|Royal Borough of) ", "pbf": "europe/united-kingdom/england"},
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
    {"wikidata": "Q220", "core": [12.475, 41.899, 2.4], "levels": [10], "strip": "^Municipio Roma ", "pbf": "europe/italy/centro"},
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
    {"wikidata": "Q2634", "levels": [10], "pbf": "europe/italy/sud"},
    #   Naples: the comune (119 km^2), its 10 municipalità (admin_level 10, "Municipalità 1"); NAP; the Metro, the
    #   Circumvesuviana, Cumana and Circumflegrea to their ends
    {"wikidata": "Q8717", "levels": [9], "strip": "^Distrito ", "tertiary": True, "pbf": "europe/spain/andalucia"},
    #   Seville: the municipality (141 km^2), its 11 distritos; SVQ; the Metro, the Cercanías to their ends
    {"wikidata": "Q649", "levels": [5, 8], "pbf": "russia/central-fed-district",
     "drop": ["Новомосковский административный округ", "Троицкий административный округ", "Зеленоградский административный округ"],
     "strip": " административный округ$"},
    #   Moscow: the federal city without New Moscow (Novomoskovsky, Troitsky) and the Zelenograd exclave -- the old city
    #   within and round the MKAD (~1,000 km^2); its 9 okrugs outlined, raions (8) named closer in; SVO; the Metro, the
    #   MCC and the MCD to their ends
    {"wikidata": "Q656", "levels": [5, 8], "pbf": "russia/northwestern-fed-district",
     "drop": ["Курортный район", "Кронштадтский район"], "strip": " район$"},
    #   Saint Petersburg: the federal city without the Kurortny district up the coast and Kronstadt in the gulf
    #   (~1,150 km^2: Peterhof and Pushkin kept, for their palaces); its 16 raions outlined, the municipal okrugs (8)
    #   named closer in; LED; the Metro and the suburban trains to their ends
    {"wikidata": "Q36433", "boundary": "Q322792", "levels": [7, 8], "pbf": "europe/portugal",
     "keep": ["Porto", "Vila Nova de Gaia", "Matosinhos", "Maia", "Gondomar"],
     "strip": [["^União das [Ff]reguesias de ", ""], [",.*$", ""], [" e .*$", ""]]},
    #   Porto: the municipality is 41 km^2, so the district's (Q322792) core five -- Porto, Gaia across the Douro (the
    #   port lodges), Matosinhos, Maia (OPO), Gondomar (~430 km^2); their freguesias named closer in, a union's by its
    #   first ("Cedofeita, Santo Ildefonso, Sé, ..." -> "Cedofeita"); the Metro do Porto, the CP Porto lines
    {"wikidata": "Q8818", "levels": [9], "pbf": "europe/spain/valencia"},
    #   Valencia: the municipality (135 km^2, with the Albufera's rice fields to the south), its 19 districtes; VLC;
    #   Metrovalencia and the Rodalia (Cercanías) to their ends
    {"wikidata": "Q1055", "levels": [9, 10], "pbf": "europe/germany/hamburg"},
    #   Hamburg: the city state (755 km^2), its 7 Bezirke outlined, the 104 Stadtteile named closer in; HAM; the U-Bahn,
    #   the S-Bahn and the AKN to their ends
    {"wikidata": "Q1794", "levels": [9, 10], "pbf": "europe/germany/hessen"},
    #   Frankfurt: the city (248 km^2), its 16 Ortsbezirke outlined, the 46 Stadtteile named closer in; FRA; the U-Bahn,
    #   the S-Bahn to their ends
    {"wikidata": "Q33959", "levels": [10], "pbf": "europe/france/provence-alpes-cote-d-azur"},
    #   Nice: the commune (72 km^2) and the quartiers OSM bounds (admin_level 10); NCE; the tram, the TER and the
    #   Chemins de fer de Provence to their ends
    {"wikidata": "Q8810", "levels": [9], "strip": "^Distrito ", "tertiary": True, "pbf": "europe/spain/andalucia"},
    #   Granada: the municipality (88 km^2), its 8 distritos; GRX; the Metro de Granada, the trains to their ends
    {"wikidata": "Q116450968", "boundary": "Q8851", "levels": [9], "strip": "^Distrito ", "tertiary": True, "pbf": "europe/spain/andalucia"},
    #   Malaga: the municipality (395 km^2: Montes de Málaga to the north), its 11 distritos; AGP; the Metro de Málaga,
    #   the Cercanías to their ends
    {"wikidata": "Q456", "levels": [9], "strip": [["^Lyon ", ""], [" [Aa]rrondissement$", " arr."]], "tertiary": True, "pbf": "europe/france/rhone-alpes"},
    #   Lyon: the commune (48 km^2), its 9 arrondissements; LYS out of town; the Métro, the funiculars and the TER to
    #   their ends
    {"wikidata": "Q23482", "levels": [9], "strip": [["^Marseille ", ""], [" [Aa]rrondissement$", " arr."]], "tertiary": True,
     "pbf": "europe/france/provence-alpes-cote-d-azur"},
    #   Marseille: the commune (240 km^2, the calanques' massif to the south-east), its 16 arrondissements; MRS out of
    #   town; the Métro, the TER to their ends
    {"wikidata": "Q585", "levels": [9], "tertiary": True, "pbf": "europe/norway"},
    #   Oslo: the kommune (454 km^2, Nordmarka's forest to the north), its 15 bydeler, Sentrum, Marka; OSL out of town;
    #   the T-bane, the trains to their ends
    {"wikidata": "Q1757", "levels": [10], "tertiary": True, "pbf": "europe/finland"},
    #   Helsinki: the city (214 km^2 of land, 500 of sea to Ulkosaaret), its 59 kaupunginosat; HEL out of town; the metro,
    #   the HSL commuter trains to their ends
    {"wikidata": "Q365", "levels": [9, 10], "pbf": "europe/germany/nordrhein-westfalen/koeln-regbez"},
    #   Cologne: the city (405 km^2), its 9 Stadtbezirke outlined, the 86 Stadtteile named closer in; CGN; the
    #   Stadtbahn, the S-Bahn to their ends
    {"wikidata": "Q1899", "levels": [10], "strip": " район$", "pbf": "europe/ukraine"},
    #   Kyiv: the city (839 km^2), its 10 raions; KBP out of town; the Metro, the city electric trains to their ends
    {"wikidata": "Q3711", "levels": [9], "strip": [["^Београд \\((.*)\\)$", "\\1"]], "pbf": "europe/serbia"},
    #   Belgrade: the city proper (OSM's settlement, ~360 km^2: the 10 urban gradske opštine, not the rural ones of the
    #   City of Belgrade), named as "Врачар" (not "Београд (Врачар)"); BEG; BG voz and the trains to their ends
    {"wikidata": "Q472", "levels": [6, 9], "strip": "^(Район|ж\\.к\\.|кв\\.) ", "tertiary": True, "pbf": "europe/bulgaria"},
    #   Sofia: the city (OSM's settlement, ~190 km^2), its raioni (admin_level 6; those mostly out of town left out),
    #   the ж.к. and кв. named closer in; SOF; the Metro and the trains to their ends
    {"wikidata": "Q19660", "levels": [9], "pbf": "europe/romania"},
    #   Bucharest: the municipality (228 km^2), its 6 sectors; OTP out of town; the Metro, the trains to their ends
    {"wikidata": "Q1773", "levels": [9, 10], "strip": " apkaime$", "tertiary": True, "pbf": "europe/latvia"},
    #   Riga: the city (307 km^2), its 58 apkaimes (neighbourhoods); RIX; the trains to their ends
    {"wikidata": "Q216", "levels": [10], "strip": " seniūnija$", "tertiary": True, "pbf": "europe/lithuania"},
    #   Vilnius: the city (OSM's, admin_level 8, ~400 km^2), its 21 seniūnijos (admin_level 10); VNO; the trains to
    #   their ends
    {"wikidata": "Q1435", "levels": [9], "strip": "^Gradska četvrt ", "tertiary": True, "pbf": "europe/croatia"},
    #   Zagreb: the city (641 km^2: Medvednica to the north), its 17 gradske četvrti; ZAG; the trains to their ends
    {"wikidata": "Q495", "levels": [10], "skip": ["Mirafiori Sud"], "pbf": "europe/italy/nord-ovest"},
    #   Turin: the comune (130 km^2), its circoscrizioni (as "Circoscrizione N", as Naples's); TRN out of town; the
    #   Metro, the SFM to their ends
    {"wikidata": "Q2656", "levels": [10], "tertiary": True, "pbf": "europe/italy/isole"},
    #   Palermo: the comune (159 km^2, out to Mondello and the sea), its 8 circoscrizioni (as "I Circoscrizione"); PMO
    #   out of town
    {"wikidata": "Q17151", "boundary": "Q6627746", "levels": [9], "strip": [["^(\\d)η Κοινότητα Θεσσαλονίκης$", "\\1η Κοινότητα"]],
     "tertiary": True, "pbf": "europe/greece"},
    #   Thessaloniki: the Dimos (Q6627746, 19 km^2: the city proper; Kalamaria etc. their own municipalities), its 5
    #   Koinotites; SKG out of town
    {"wikidata": "Q1449", "levels": [10], "tertiary": True, "pbf": "europe/italy/nord-ovest"},
    #   Genoa: the comune (240 km^2, 30 km along the coast), its 9 municipi; GOA
    {"wikidata": "Q34370", "boundary": "Q2680952", "levels": ["place=suburb", "place=quarter"], "airport": ["RTM", 4.437, 51.957],
     "pbf": "europe/netherlands/zuid-holland"},
    #   Rotterdam: the gemeente (Q2680952; Q34370 is the woonplaats), out to the Maasvlakte; its gebieden (place=suburb,
    #   as Amsterdam's), the wijken named closer in; RTM; the Metro, NS Sprinters as main rail
    {"wikidata": "Q36600", "levels": ["place=suburb", "place=quarter"], "airport": ["RTM", 4.437, 51.957], "tertiary": True,
     "pbf": "europe/netherlands/zuid-holland"},
    #   The Hague: the gemeente (Den Haag, Scheveningen on the sea), its 8 stadsdelen (place=suburb), the wijken closer in
    {"wikidata": "Q8692", "levels": [9, 10], "tertiary": True, "pbf": "europe/spain/pais-vasco"},
    #   Bilbao: the udalerria (41 km^2), its 8 distritos, the barrios closer in; BIO out of town; Metro Bilbao, Euskotren
    #   and Renfe Cercanías
    {"wikidata": "Q1731", "levels": [9, 10], "tertiary": True, "pbf": "europe/germany/sachsen"},
    #   Dresden: the city (328 km^2), its Stadtbezirke and Ortschaften; DRS; the S-Bahn; tertiary (the Altstadt ring)
    {"wikidata": "Q4093", "boundary": "Q55934339", "levels": ["place=suburb"], "pbf": "europe/united-kingdom/scotland"},
    #   Glasgow: the Glasgow City council area (Q55934339, 175 km^2), its suburbs as OSM bounds them (place=suburb: no
    #   admin_level under the council); GLA out of town; the Subway; ScotRail as main rail
    {"wikidata": "Q19689", "levels": [9], "keep": [f"Njësia Bashkiake Nr. {k}" for k in range(1, 12)],
     "strip": [["^Njësia Bashkiake Nr\\. (\\d+)$", "Njësia \\1"]], "tertiary": True, "pbf": "europe/albania"},
    #   Tirana: the city proper, the 11 njësi bashkiake of the Bashkia (the rest of its 1,100 km^2 its rural units); TIA
    #   out of town; no metro or suburban rail
    {"wikidata": "Q36036", "levels": [10], "strip": " район$", "tertiary": True, "airport": ["LWO", 23.956, 49.813], "pbf": "europe/ukraine"},
    #   Lviv: the city (182 km^2), its 6 raions; LWO (not in data/airports.csv: closed to flights since 2022)
    {"wikidata": "Q18125", "boundary": "Q21525592", "levels": ["ward=ward"], "pbf": "europe/united-kingdom/england"},
    #   Manchester: the metropolitan borough (Q21525592, 116 km^2, out to Wythenshawe and the airport), its electoral
    #   wards (boundary=political: no admin_level under the borough); MAN; Metrolink is tram (not drawn)
    {"wikidata": "Q2256", "boundary": "Q20986424", "levels": ["ward=ward"], "strip": " [Ww]ard$", "pbf": "europe/united-kingdom/england"},
    #   Birmingham: the metropolitan borough (Q20986424, 268 km^2), its electoral wards; BHX out of town; the West
    #   Midlands Metro tram (not drawn)
    {"wikidata": "Q641", "place": ["Venice", 12.3358, 45.4386], "core": [12.3330, 45.4380, 2.4], "levels": [10], "tertiary": True, "pbf": "europe/italy/nord-est"},
    #   Venice: the comune (415 km^2: the city, the lagoon and its islands, Mestre on the mainland), its 6 municipalità;
    #   the lagoon is OSM's sea (its coastline runs round the lagoon's shores); VCE; no vaporetto (ferries: not drawn);
    #   not in data/cities.csv (`place`)
    {"wikidata": "Q2044", "levels": [10], "tertiary": True, "pbf": "europe/italy/centro"},
    #   Florence: the comune (102 km^2), its 5 quartieri; FLR
    {"wikidata": "Q23436", "tertiary": True, "pbf": "europe/united-kingdom/scotland"},
    #   Edinburgh: the City of Edinburgh council area; EDI
    {"wikidata": "Q34713", "tertiary": True, "pbf": "europe/austria"},
    #   Salzburg: the Statutarstadt (66 km^2); SZG; the S-Bahn
    {"wikidata": "Q12994", "tertiary": True, "pbf": "europe/belgium"},
    #   Bruges: the municipality (138 km^2, out to Zeebrugge on the sea), its deelgemeenten
    {"wikidata": "Q72", "tertiary": True, "pbf": "europe/switzerland"},
    #   Zurich: the city (88 km^2), its 12 Kreise; ZRH; the S-Bahn
    {"wikidata": "Q71", "tertiary": True, "pbf": "europe/switzerland"},
    #   Geneva: the city (16 km^2); GVA; the Léman Express
    {"wikidata": "Q1891", "levels": [10], "strip": "^Quartiere ", "tertiary": True, "pbf": "europe/italy/nord-est"},
    #   Bologna: the comune (141 km^2), its 6 quartieri; BLQ
    {"wikidata": "Q2028", "levels": [10], "tertiary": True, "pbf": "europe/italy/nord-est"},
    #   Verona: the comune (199 km^2), its circoscrizioni; VRN
    {"wikidata": "Q13375", "tertiary": True, "pbf": "europe/italy/centro"},
    #   Pisa: the comune (185 km^2, out to the sea at Marina di Pisa); PSA
    {"wikidata": "Q1722", "place": ["Dubrovnik", 18.1100, 42.6410], "strip": "^Gradski kotar ", "tertiary": True, "pbf": "europe/croatia"},
    #   Dubrovnik: the city (143 km^2 along the coast); DBV out of town; not in data/cities.csv (`place`)
    {"wikidata": "Q1770", "levels": [9, 10], "tertiary": True, "pbf": "europe/estonia"},
    #   Tallinn: the city (159 km^2), its 8 linnaosad, the asumid closer in; TLL; Elron's trains
    {"wikidata": "Q1735", "tertiary": True, "pbf": "europe/austria"},
    #   Innsbruck: the city (105 km^2); INN; the S-Bahn
    {"wikidata": "Q4191", "airport": None, "tertiary": True, "pbf": "europe/switzerland"},
    #   Lucerne: the city (37 km^2, Littau with it), no districts in OSM; no airport (ZRH, 45 km off, would stretch the window); the S-Bahn
    {"wikidata": "Q1764", "tertiary": True, "pbf": "europe/iceland"},
    #   Reykjavik: the city (273 km^2, Kjalarnes with it); KEF (40 km out); no railways
    {"wikidata": "Q437", "boundary": "Q3434113", "levels": ["place=suburb"], "strip": "^Četrtna skupnost ", "tertiary": True, "pbf": "europe/slovenia"},
    #   Ljubljana: the city municipality (Q3434113, 275 km^2), its četrtne skupnosti; LJU
    {"wikidata": "Q1663", "strip": "^Gradski kotar ", "tertiary": True, "pbf": "europe/croatia"},
    #   Split: the city (80 km^2); SPU
    {"wikidata": "Q1780", "airport": ["BTS", 17.2127, 48.1702], "strip": "^Bratislava-", "tertiary": True, "pbf": "europe/slovakia"},
    #   Bratislava: the city (367 km^2), its 17 boroughs (mestské časti); BTS (not in data/airports.csv)
    {"wikidata": "Q24826", "boundary": "Q21665571", "airport": ["LPL", -2.8497, 53.3336], "levels": ["ward=ward"], "strip": " [Ww]ard$", "pbf": "europe/united-kingdom/england"},
    #   Liverpool: the metropolitan borough (112 km^2), its wards; LPL; Merseyrail
    {"wikidata": "Q1479", "tertiary": True, "pbf": "europe/france/aquitaine"},
    #   Bordeaux: the commune (49 km^2), its quartiers; BOD
    {"wikidata": "Q6602", "airport": ["SXB", 7.6282, 48.5383], "tertiary": True, "pbf": "europe/france/alsace"},
    #   Strasbourg: the commune (78 km^2), its quartiers; SXB
    {"wikidata": "Q8826", "tertiary": True, "pbf": "europe/spain/islas-baleares"},
    #   Palma: the municipality (208 km^2), its districts; PMI
    {"wikidata": "Q23800", "airport": None, "tertiary": True, "pbf": "europe/malta"},
    #   Valletta: the local council (0.8 km^2: the walled old town alone, all of it core); no airport (MLA would stretch the window)
    {"wikidata": "Q1842", "tertiary": True, "pbf": "europe/luxembourg"},
    #   Luxembourg: the commune (51 km^2), its 24 quartiers; LUX
    {"wikidata": "Q160544", "boundary": "Q12875667", "levels": [9], "strip": [["^\\d+η Κοινότητα Ηρακλείου - ", ""], ["^Κοινότητα ", ""]], "tertiary": True, "pbf": "europe/greece"},
    #   Heraklion: the municipal unit (the town, 109 km^2), its 4 communities; HER
    {"wikidata": "Q188731", "boundary": "Q21695272", "tertiary": True, "pbf": "europe/greece"},
    #   Rhodes: the municipal unit of Rhodes (the town and its old town, 20 km^2); RHO
    {"wikidata": "Q3949542", "place": ["Santorini (Fira)", 25.4316, 36.4166], "core": [25.4316, 36.4166, 1.5], "tertiary": True, "pbf": "europe/greece"},
    #   Santorini (Fira): the municipality of Thira (the island, Thirasia with it, 90 km^2: Fira, Oia); JTR; the lanes round
    #   Fira; not in data/cities.csv (`place`)
    {"wikidata": "Q25444", "levels": [8], "tertiary": True, "pbf": "europe/portugal"},
    #   Funchal: the município (76 km^2), its 10 freguesias; FNC
    {"wikidata": "Q11974", "tertiary": True, "pbf": "africa/canary-islands"},
    #   Las Palmas de Gran Canaria: the municipality (101 km^2), its distritos; LPA
    {"wikidata": "Q14328", "tertiary": True, "pbf": "africa/canary-islands"},
    #   Santa Cruz de Tenerife: the municipality (150 km^2, Anaga with it); TFN
    {"wikidata": "Q235", "boundary": "r2220322", "levels": [10], "airport": None, "tertiary": True, "pbf": "europe/monaco"},
    #   Monaco: the principality's commune (2 km^2: its level-2 relation takes in the sea), its quartiers; no airport (NCE, in France, would stretch the window)
    {"wikidata": "Q12892", "airport": ["ANR", 4.4603, 51.1894], "tertiary": True, "pbf": "europe/belgium"},
    #   Antwerp: the city (204 km^2), its 9 districten; ANR (BRU, 45 km off, would stretch the window)
    {"wikidata": "Q1296", "tertiary": True, "pbf": "europe/belgium"},
    #   Ghent: the city (156 km^2), its deelgemeenten
    {"wikidata": "Q70", "tertiary": True, "pbf": "europe/switzerland"},
    #   Bern: the city (52 km^2), its Stadtteile; BRN; the S-Bahn
    {"wikidata": "Q78", "tertiary": True, "pbf": "europe/switzerland"},
    #   Basel: the city (24 km^2), its Wohnviertel; BSL (EuroAirport, in France); the S-Bahn
    {"wikidata": "Q1792", "tertiary": True, "pbf": "europe/poland/pomorskie"},
    #   Gdańsk: the city (262 km^2), its dzielnice; GDN; the SKM
    {"wikidata": "Q23154", "boundary": "Q21693433", "levels": ["ward=ward"], "strip": " [Ww]ard$", "radius": 9,
     "airport": None, "pbf": "europe/united-kingdom/england"},
    #   Bristol: the unitary authority 9 km round the centre (its relation runs down the Severn estuary to Steep Holm),
    #   its wards; no airport (BRS, 11 km south-west, would stretch the window)
    {"wikidata": "Q39121", "boundary": "Q774015", "levels": ["ward=ward"], "strip": " [Ww]ard$", "pbf": "europe/united-kingdom/england"},
    #   Leeds: the metropolitan district (552 km^2, Otley and Wetherby with it), its wards; LBA
    {"wikidata": "Q22889", "airport": None, "tertiary": True, "pbf": "europe/united-kingdom/england"},
    #   Bath: its boundary=place (the unparished city, 29 km^2: no council of its own under B&NES); no airport (BRS
    #   would stretch the window)
    {"wikidata": "Q34217", "airport": None, "levels": ["ward=ward"], "strip": " [Ww]ard$", "tertiary": True, "pbf": "europe/united-kingdom/england"},
    #   Oxford: the city (46 km^2), its wards; no airport
    {"wikidata": "Q350", "boundary": "Q21713103", "airport": None, "levels": ["ward=ward"], "strip": " [Ww]ard$", "tertiary": True, "pbf": "europe/united-kingdom/england"},
    #   Cambridge: the city (41 km^2), its wards; no airport
    {"wikidata": "Q42462", "boundary": "Q20986421", "airport": None, "levels": ["ward=ward"], "strip": " [Ww]ard$", "tertiary": True, "pbf": "europe/united-kingdom/england"},
    #   York: the unitary authority (272 km^2), its wards; no airport (LBA, 35 km)
    {"wikidata": "Q803", "levels": ["place=suburb"], "airport": None, "tertiary": True, "pbf": "europe/netherlands/utrecht"},
    #   Utrecht: the gemeente (99 km^2), its wijken (place=suburb); no airport (AMS, 35 km)
    {"wikidata": "Q9832", "levels": ["place=suburb"], "tertiary": True, "pbf": "europe/netherlands/noord-brabant"},
    #   Eindhoven: the gemeente (89 km^2), its stadsdelen (place=suburb); EIN
    {"wikidata": "Q25287", "boundary": "Q52502", "levels": [9, 10], "pbf": "europe/sweden"},
    #   Gothenburg: the municipality (Göteborgs Stad, 450 km^2 with its archipelago); GOT; the pendeltåg
    {"wikidata": "Q2211", "boundary": "Q503361", "levels": [9, 10], "airport": None, "tertiary": True, "pbf": "europe/sweden"},
    #   Malmö: the municipality (158 km^2); no airport (MMX 28 km out, CPH over the Sound)
    {"wikidata": "Q36647", "levels": [9], "strip": " ED$", "tertiary": True, "pbf": "europe/ireland-and-northern-ireland"},
    #   Cork: the city (187 km^2 since 2019), its electoral divisions; ORK
    {"wikidata": "Q10686", "airport": ["BHD", -5.8725, 54.6181], "levels": ["ward=ward"], "strip": " [Ww]ard$", "tertiary": True,
     "pbf": "europe/ireland-and-northern-ireland"},
    #   Belfast: the city district (133 km^2); BHD (George Best City; BFS, 20 km out, would stretch the window)
    {"wikidata": "Q10690", "boundary": "Q24342199", "levels": [10], "airport": None, "tertiary": True, "pbf": "europe/united-kingdom/wales"},
    #   Cardiff: the county (140 km^2), its communities; no airport (CWL, 16 km west, would stretch the window)
    {"wikidata": "Q26793", "boundary": "Q10428388", "levels": [9], "tertiary": True, "pbf": "europe/norway"},
    #   Bergen: the municipality (465 km^2), its 8 bydeler; BGO (in Ytrebygda); the Bybanen is tram (not drawn)
    {"wikidata": "Q25319", "boundary": "Q240262", "levels": ["place=suburb"], "airport": None, "tertiary": True, "pbf": "europe/denmark"},
    #   Aarhus: the municipality (468 km^2); no airport (AAR, 40 km out); the Letbanen is tram-train (light_rail)
    {"wikidata": "Q3856", "boundary": "Q56037497|Q7030537", "airport": None, "tertiary": True, "pbf": "europe/cyprus"},
    #   Nicosia: both halves -- the municipality (Δήμος Λευκωσίας) and the north's Lefkoşa Türk Belediyesi, the walled
    #   city whole across the Green Line; no airport (LCA 40 km, ECN 20 km)
    {"wikidata": "Q1863", "boundary": "Q2522163|Q24286", "airport": None, "tertiary": True, "pbf": "europe/andorra"},
    #   Andorra la Vella: the parish and Escaldes-Engordany, one town along the Valira; no airport
    {"wikidata": "Q11194", "levels": [7], "strip": "^Općina ", "tertiary": True, "pbf": "europe/bosnia-herzegovina"},
    #   Sarajevo: the city (Grad Sarajevo, 141 km^2), its 4 općine; SJJ
    {"wikidata": "Q23564", "tertiary": True, "pbf": "europe/montenegro"},
    #   Podgorica: the town (admin_level 8, not the 1,400 km^2 capital municipality); TGD
    {"wikidata": "Q171080", "boundary": "Q4856305", "place": ["Kotor", 18.7713, 42.4249], "radius": 3, "airport": None, "tertiary": True, "pbf": "europe/montenegro"},
    #   Kotor: the opština 3 km round the old town (its own level-8 relation is but the walled town; the opština 335
    #   km^2 of the bay's mountains) -- Dobrota, Škaljari, the fortress above; no airport (TIV, 8 km)
    {"wikidata": "Q384", "boundary": "Q2575820", "levels": [7], "strip": "^Општина ", "tertiary": True, "pbf": "europe/macedonia"},
    #   Skopje: the City of Skopje (Град Скопје, 571 km^2), its 10 municipalities; SKP
    {"wikidata": "Q21197", "tertiary": True, "pbf": "europe/moldova"},
    #   Chișinău: the city (admin_level 8, not the 563 km^2 municipiu); RMO
    {"wikidata": "Q2280", "levels": [9], "strip": " раён$", "airport": None, "pbf": "europe/belarus"},
    #   Minsk: the city (409 km^2), its 9 raions; no airport (MSQ, 40 km out); the Metro
    {"wikidata": "Q14960", "levels": [10], "strip": "^Brno-", "tertiary": True, "pbf": "europe/czech-republic"},
    #   Brno: the city (230 km^2), its 29 městské části; BRQ
    {"wikidata": "Q188082", "place": ["Český Krumlov", 14.3152, 48.8109], "levels": [10], "airport": None, "tertiary": True, "pbf": "europe/czech-republic"},
    #   Český Krumlov: the town (22 km^2), its parts; no airport
    {"wikidata": "Q2079", "levels": [9], "airport": None, "pbf": "europe/germany/sachsen"},
    #   Leipzig: the city (297 km^2), its 10 Stadtbezirke; no airport (LEJ, 15 km out toward Halle); the S-Bahn
    {"wikidata": "Q2090", "levels": [9, 10], "tertiary": True, "pbf": "europe/germany/bayern/mittelfranken"},
    #   Nuremberg: the city (186 km^2); NUE; the S-Bahn, the U-Bahn
    {"wikidata": "Q1022", "levels": [9], "strip": "^Stuttgart-", "pbf": "europe/germany/baden-wuerttemberg/stuttgart-regbez"},
    #   Stuttgart: the city (207 km^2), its 23 Stadtbezirke; STR (on the edge); the S-Bahn
    {"wikidata": "Q1718", "levels": [10], "pbf": "europe/germany/nordrhein-westfalen/duesseldorf-regbez"},
    #   Düsseldorf: the city (217 km^2), its 50 Stadtteile (the 10 Stadtbezirke are only numbered); DUS; the S-Bahn
    {"wikidata": "Q1799", "levels": [9], "tertiary": True, "pbf": "europe/poland/dolnoslaskie"},
    #   Wrocław: the city (293 km^2), its 48 osiedla; WRO
    {"wikidata": "Q268", "levels": [9], "tertiary": True, "pbf": "europe/poland/wielkopolskie"},
    #   Poznań: the city (262 km^2), its 42 osiedla; POZ
    {"wikidata": "Q7880", "tertiary": True, "pbf": "europe/france/midi-pyrenees"},
    #   Toulouse: the commune (118 km^2); TLS (Blagnac, next door); the Métro
    {"wikidata": "Q6441", "tertiary": True, "pbf": "europe/france/languedoc-roussillon"},
    #   Montpellier: the commune (57 km^2); MPL
    {"wikidata": "Q648", "tertiary": True, "pbf": "europe/france/nord-pas-de-calais"},
    #   Lille: the commune (35 km^2, Lomme and Hellemmes with it); LIL
    {"wikidata": "Q12191", "tertiary": True, "pbf": "europe/france/pays-de-la-loire"},
    #   Nantes: the commune (65 km^2); NTE
    {"wikidata": "Q6397", "airport": None, "tertiary": True, "pbf": "europe/france/provence-alpes-cote-d-azur"},
    #   Avignon: the commune (65 km^2, its walled town and the Rhône islands); no airport
    {"wikidata": "Q807", "airport": None, "tertiary": True, "pbf": "europe/switzerland"},
    #   Lausanne: the commune (41 km^2, its northern woods with it); no airport (GVA, 50 km); the Métro
    # -- beyond Europe: the most visited (Euromonitor's, Mastercard's top city destinations), a few capitals with them
    {"wikidata": "Q8646", "boundary": "Q19483|Q239143", "levels": [6], "strip": " District$", "names": "en", "airport": None,
     "core": [114.165, 22.290, 1.8], "pbf": "asia/china/hong-kong"},
    #   Hong Kong: Hong Kong Island and Kowloon (the New Territories and Lantau left out), their districts; names in
    #   English (name:en); no airport (HKG, on Lantau, would stretch the window); the MTR
    {"wikidata": "Q14773", "levels": [6], "names": "en", "tertiary": True, "pbf": "asia/china/macau"},
    #   Macau: the SAR (Macau, Taipa, Cotai, Coloane: 33 km^2), its parishes; MFM; the Light Rapid Transit
    {"wikidata": "Q612", "levels": [10], "names": "en", "core": [55.296, 25.262, 1.5], "pbf": "asia/gcc-states"},
    #   Dubai: the city (its relation of no admin_level), its communities; names in English; DXB; the Metro;
    #   lanes round Deira and Bur Dubai, the old town on the Creek
    {"wikidata": "Q1519", "levels": [10], "names": "en", "airport": None, "pbf": "asia/gcc-states"},
    #   Abu Dhabi: the city (admin_level 5); names in English; no airport (AUH, 30 km out)
    {"wikidata": "Q3861", "levels": [10], "names": "en", "pbf": "asia/gcc-states"},
    #   Doha: the municipality; its zones; names in English; DOH; the Metro
    {"wikidata": "Q5806", "levels": [10], "names": "en", "core": [39.8262, 21.4225, 1.5], "airport": None, "pbf": "asia/gcc-states"},
    #   Mecca: the governorate; names in English; no airport (JED, 80 km); the lanes round the Masjid al-Haram
    {"wikidata": "Q1861", "levels": [6], "strip": " District$", "names": "en", "airport": None, "core": [100.4977, 13.7525, 2.0],
     "pbf": "asia/thailand"},
    #   Bangkok: the city (1,569 km^2), its 50 khet; names in English; no airport (BKK and DMK would stretch the window); the BTS, the MRT, the Airport Rail Link, the
    #   SRT Red Lines; the lanes of Rattanakosin and the Khao San Road
    {"wikidata": "Q182565", "place": ["Phuket", 98.3400, 7.8700], "radius": 11, "airport": None, "levels": [6], "strip": " District$", "names": "en",
     "core": [98.2970, 7.8960, 1.5], "tertiary": True, "pbf": "asia/thailand"},
    #   Phuket: the province 11 km round the island's middle -- Phuket Town, Patong, Karon, Kata, Chalong -- its
    #   districts; names in English; no airport (HKT, 25 km north); the lanes of Patong
    {"wikidata": "Q170919", "names": "en", "airport": None, "tertiary": True, "pbf": "asia/thailand"},
    #   Pattaya: the city (Bang Lamung's coast, 22 km^2); names in English; no airport (UTP, 30 km)
    {"wikidata": "Q52028", "names": "en", "tertiary": True, "pbf": "asia/thailand"},
    #   Chiang Mai: the city municipality (40 km^2, the moated old town at its heart); names in English; CNX
    {"wikidata": "Q334", "levels": [6], "names": "en", "core": [103.850, 1.284, 1.8], "pbf": "asia/malaysia-singapore-brunei"},
    #   Singapore: the island state (735 km^2), its 55 planning areas; SIN; the MRT; lanes round Chinatown and the river
    {"wikidata": "Q1865", "names": "en", "airport": None, "pbf": "asia/malaysia-singapore-brunei"},
    #   Kuala Lumpur: the federal territory (243 km^2); no airport (KUL, 50 km out); the LRT, the MRT, the KTM Komuter
    {"wikidata": "Q61092", "names": "en", "core": [100.3370, 5.4170, 1.2], "tertiary": True, "pbf": "asia/malaysia-singapore-brunei"},
    #   George Town (Penang): the city (Penang Island, 306 km^2); PEN; the lanes of its UNESCO core
    {"wikidata": "Q35765", "levels": [8], "strip": "( [Ww]ard|-ku)$", "names": "en", "airport": None, "pbf": "asia/japan/kansai"},
    #   Osaka: the city (225 km^2), its 24 wards; names in English; no airport (ITM, KIX out of town); JR, the Metro, the
    #   private lines
    {"wikidata": "Q34600", "levels": [8], "strip": "( [Ww]ard|-ku)$", "names": "en", "airport": None, "core": [135.7750, 35.0000, 2.0], "radius": 9,
     "pbf": "asia/japan/kansai"},
    #   Kyoto: the city 9 km round its middle (828 km^2 whole, its northern mountains) -- Arashiyama to Fushimi Inari -- its 11 wards; names in English; no airport; the lanes
    #   of Gion and Higashiyama
    {"wikidata": "Q169134", "names": "en", "airport": None, "core": [135.8300, 34.6850, 1.5], "radius": 6, "tertiary": True,
     "pbf": "asia/japan/kansai"},
    #   Nara: the city 6 km round the park (277 km^2 whole, mountains east); names in English; no airport; the lanes of Naramachi and the park's temples
    {"wikidata": "Q1490", "levels": [7], "names": "en", "airport": ["HND", 139.7811, 35.5494], "core": [139.7745, 35.7120, 1.5],
     "keep": ["Suginami", "Nakano", "Shinjuku", "Bunkyō", "Taito", "Sumida", "Chuo", "Meguro", "Ota", "Setagaya", "Shibuya", "Toshima", "Kita", "Arakawa", "Itabashi", "Nerima", "Adachi", "Minato", "Katsushika", "Chiyoda", "Edogawa", "Koto", "Shinagawa"],
     "pbf": "asia/japan/kanto"},
    #   Tokyo: the 23 special wards (627 km^2; the Metropolis's Tama towns, mountains and islands left out); names in
    #   English; HND (in Ota); JR, the Metro, Toei, the private lines; the lanes of Asakusa and Ueno
    {"wikidata": "Q8684", "levels": [6], "strip": "-gu$", "names": "en", "airport": ["GMP", 126.7906, 37.5583], "core": [126.9850, 37.5740, 1.8],
     "pbf": "asia/south-korea"},
    #   Seoul: the city (605 km^2), its 25 gu; names in English; GMP (ICN, 50 km out on its island, would stretch the
    #   window); the Subway, Korail's lines; the lanes of Jongno, Bukchon and Insadong
    {"wikidata": "Q16520", "radius": 14, "levels": [6], "strip": "-(gu|gun)$", "names": "en", "pbf": "asia/south-korea"},
    #   Busan: the city 14 km round its middle (its relation out to far islets), its 16 gu and gun; names in English; PUS
    {"wikidata": "Q42142", "radius": 12, "names": "en", "tertiary": True, "pbf": "asia/south-korea"},
    #   Jeju: Jeju City 12 km round the town (978 km^2 whole: the island's northern half, its islets); names in English; CJU
    {"wikidata": "Q1867", "levels": [6], "strip": " District$", "names": "en", "core": [121.5090, 25.0400, 1.5], "pbf": "asia/taiwan"},
    #   Taipei: the city (272 km^2), its 12 districts; names in English; TSA; the MRT, TRA
    {"wikidata": "Q1854", "levels": [6], "strip": "^(Phường|Xã|Đặc khu) ", "radius": 9, "core": [106.7010, 10.7740, 1.5], "pbf": "asia/vietnam"},
    #   Ho Chi Minh City: the city 9 km round District 1 (the city since 2025 is 6,800 km^2, Bình Dương and Vũng Tàu with
    #   it), its phường; SGN; the Metro
    {"wikidata": "Q1858", "levels": [6], "strip": "^(Phường|Xã|Đặc khu) ", "radius": 8, "core": [105.8520, 21.0330, 1.5], "airport": None, "pbf": "asia/vietnam"},
    #   Hanoi: the city 8 km round Hoàn Kiếm (of its 3,359 km^2), its phường; no airport (HAN, 25 km out); the Metro;
    #   the lanes of the Old Quarter
    {"wikidata": "Q25282", "levels": [6], "strip": "^(Phường|Xã|Đặc khu) ", "radius": 7, "pbf": "asia/vietnam"},
    #   Da Nang: the city 7 km round its centre (of a province since 2025), its phường; DAD
    {"wikidata": "Q36160", "boundary": "Q961738|Q139986873|Q2314804", "levels": [6], "strip": "^(Phường|Xã|Đặc khu) ", "airport": None, "tertiary": True, "pbf": "asia/vietnam"},
    #   Hội An: its three phường (Hội An, Hội An Đông, Hội An Tây: the old town and round it); no airport (DAD, 30 km)
    {"wikidata": "Q8686", "levels": [6], "strip": " District$", "names": "en", "radius": 10, "airport": None,
     "core": [121.4880, 31.2300, 1.5], "pbf": "asia/china/shanghai"},
    #   Shanghai: the city 10 km round People's Square (of its 6,340 km^2), its districts; names in English; no airport
    #   (SHA, PVG out of the circle); the Metro; the lanes of the old town and the Bund
    {"wikidata": "Q956", "levels": [6], "strip": " District$", "names": "en", "radius": 12, "airport": None,
     "core": [116.3975, 39.9300, 2.0], "pbf": "asia/china/beijing"},
    #   Beijing: the city 12 km round the Forbidden City (of its 16,410 km^2: the Fifth Ring Road's), its districts; names
    #   in English; no airport (PEK, PKX out of the circle); the Subway; the hutongs round the Forbidden City
    {"wikidata": "Q16572", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 10, "pbf": "asia/china/guangdong"},
    #   Guangzhou: the city 10 km round its centre (of 7,434 km^2), its districts; names in English; no airport (CAN, 28 km)
    {"wikidata": "Q15174", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 12, "pbf": "asia/china/guangdong"},
    #   Shenzhen: the city 12 km round Futian (of 1,997 km^2), its districts; names in English; no airport (SZX, 30 km)
    {"wikidata": "Q5826", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 8, "core": [108.9450, 34.2600, 2.0], "pbf": "asia/china/shaanxi"},
    #   Xi'an: the city 8 km round the Bell Tower (the walled city and round it), its districts; names in English; no
    #   airport (XIY, 30 km); the Metro; the lanes inside the walls
    {"wikidata": "Q30002", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 9, "pbf": "asia/china/sichuan"},
    #   Chengdu: the city 9 km round Tianfu Square, its districts; names in English; no airport; the Metro
    {"wikidata": "Q4970", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 8, "pbf": "asia/china/zhejiang"},
    #   Hangzhou: the city 8 km round West Lake's east shore, its districts; names in English; no airport; the Metro
    {"wikidata": "Q189633", "levels": [6], "strip": " District$", "names": "en", "airport": None, "radius": 7, "tertiary": True, "pbf": "asia/china/guangxi"},
    #   Guilin: the city 7 km round its centre (the Li River's karst hills), its districts; names in English; no airport
    {"wikidata": "Q1461", "boundary": "Q1461|Q1508", "airport": None, "core": [120.9750, 14.5900, 1.2], "pbf": "asia/philippines"},
    #   Manila: the city and Makati, its business district; no airport (MNL, in Pasay and Parañaque); the LRT, the MRT,
    #   the PNR; the lanes of Intramuros
        {"wikidata": "Q1850", "levels": [6], "strip": "^Khan ", "names": "en", "airport": None, "pbf": "asia/cambodia"},
    #   Phnom Penh: the capital (679 km^2), its 14 khan; names in English; no airport (KTI, 30 km out)
    {"wikidata": "Q11711", "boundary": "Q4929292", "core": [103.8590, 13.3620, 1.5], "place": ["Siem Reap", 103.8600, 13.4000], "radius": 7, "names": "en", "airport": None, "tertiary": True, "pbf": "asia/cambodia"},
    #   Siem Reap: the municipality 7 km round the town and Angkor Wat (its relation out over the Tonlé Sap); names in English; no airport (SAI, 40 km)
    {"wikidata": "Q3037", "levels": [8], "names": "en", "core": [85.3100, 27.7100, 1.5], "tertiary": True, "pbf": "asia/nepal"},
    #   Kathmandu: the metropolitan city (50 km^2; its 32 numbered wards not drawn); names in English; KTM; the lanes of
    #   Thamel and Durbar Square
    {"wikidata": "Q35381", "names": "en", "airport": None, "tertiary": True, "pbf": "asia/sri-lanka"},
    #   Colombo: the municipal council (37 km^2); names in English; no airport (CMB, 30 km)
    {"wikidata": "Q9347", "names": "en", "tertiary": True, "pbf": "asia/maldives"},
    #   Malé: the city (Malé island, Hulhulé's airport and Hulhumalé, Villimalé); names in English; MLE
    {"wikidata": "Q33935", "names": "en", "airport": None, "core": [34.7550, 32.0540, 1.2], "pbf": "asia/israel-and-palestine"},
    #   Tel Aviv: the city (Tel Aviv-Yafo, 52 km^2); names in English; no airport (TLV, 15 km); Israel Railways, the
    #   Red Line; the lanes of Old Jaffa and Neve Tzedek
    {"wikidata": "Q1218", "place": ["Jerusalem", 35.2137, 31.7683], "names": "en", "airport": None, "core": [35.2310, 31.7770, 1.2],
     "pbf": "asia/israel-and-palestine"},
    #   Jerusalem: the municipality (126 km^2); names in English; no airport; the lanes of the Old City; not in
    #   data/cities.csv (`place`)
    {"wikidata": "Q3805", "boundary": "Q472788", "names": "en", "radius": 8, "airport": None, "levels": [8], "pbf": "asia/jordan"},
    #   Amman: the governorate 8 km round the citadel (no relation for the Greater Amman Municipality); names in English;
    #   no airport (AMM, 30 km)
    {"wikidata": "Q3692", "boundary": "Q97302281", "radius": 12, "airport": None, "names": "en", "levels": [10], "pbf": "asia/gcc-states"},
    #   Riyadh: the governorate 12 km round the centre (Al Bathaa, Masmak); names in English; no airport (RUH, 30 km);
    #   the Metro
    {"wikidata": "Q374365", "boundary": "Q97016466", "radius": 10, "airport": None, "core": [39.1860, 21.4850, 1.2], "names": "en", "levels": [10], "pbf": "asia/gcc-states"},
    #   Jeddah: the governorate 10 km round the centre; names in English; no airport (JED, 20 km north); the lanes
    #   of Al-Balad
    {"wikidata": "Q35484", "boundary": "Q97307705", "radius": 6, "airport": None, "core": [39.6110, 24.4680, 1.2], "names": "en", "levels": [10], "pbf": "asia/gcc-states"},
    #   Medina: the governorate 6 km round the Prophet's Mosque; names in English; no airport (MED, 15 km)
    {"wikidata": "Q3826", "boundary": "Q544762", "radius": 10, "airport": None, "core": [58.5930, 23.6150, 1.0], "names": "en", "levels": [10], "pbf": "asia/gcc-states"},
    #   Muscat: the governorate 10 km round Muttrah and Ruwi; names in English; no airport (MCT, 25 km west); the lanes of
    #   old Muscat and Muttrah
    {"wikidata": "Q994", "levels": [6], "names": "en", "airport": None, "core": [44.8070, 41.6905, 1.2], "pbf": "europe/georgia"},
    #   Tbilisi: the city (504 km^2), its districts; names in English; no airport (TBS, 17 km); the Metro; the lanes of
    #   the old town
    {"wikidata": "Q1953", "levels": [6], "names": "en", "airport": None, "pbf": "asia/armenia"},
    #   Yerevan: the city (223 km^2), its 12 districts; names in English; no airport (EVN, 12 km)
    {"wikidata": "Q9248", "boundary": "r2415335", "radius": 9, "names": "en", "airport": None, "core": [49.8370, 40.3660, 1.0],
     "pbf": "asia/azerbaijan"},
    #   Baku: the city (its relation of no wikidata, "r<id>") 9 km round the centre (of 2,140 km^2, Absheron's); no
    #   airport (GYD, 20 km); the Metro; the lanes of the walled Icherisheher
    {"wikidata": "Q269", "levels": [6], "names": "en", "pbf": "asia/uzbekistan"},
    #   Tashkent: the city (335 km^2), its 12 tumani; names in English; TAS; the Metro
    {"wikidata": "Q5753", "names": "en", "tertiary": True, "pbf": "asia/uzbekistan"},
    #   Samarkand: the city (120 km^2); names in English; SKD
    {"wikidata": "Q3820", "boundary": "Q651688", "levels": [7], "names": "en", "airport": None, "pbf": "asia/lebanon"},
    #   Beirut: the governorate (the city, 20 km^2), its 12 quarters; names in English; no airport (BEY, just south)
    {"wikidata": "Q190165", "place": ["Luang Prabang", 102.1359, 19.8887], "boundary": "Q6695010", "radius": 4, "names": "en",
     "tertiary": True, "pbf": "asia/laos"},
    #   Luang Prabang: its district 4 km round the old town (the peninsula between the Mekong and the Nam Khan); names in
    #   English; LPQ; not in data/cities.csv (`place`)
    {"wikidata": "Q26600", "levels": [8], "strip": "( [Ww]ard|-ku)$", "names": "en", "pbf": "asia/japan/kyushu"},
    #   Fukuoka: the city (343 km^2), its 7 wards; names in English; FUK (in Hakata, by the centre); JR, the Subway
    {"wikidata": "Q181966", "names": "en", "tertiary": True, "pbf": "asia/japan/kyushu"},
    #   Naha: the city (Okinawa's capital, 41 km^2); names in English; OKA
    {"wikidata": "Q37951", "levels": [8], "strip": "( [Ww]ard|-ku)$", "names": "en", "airport": None, "pbf": "asia/japan/hokkaido"},
    #   Sapporo: the city (1,121 km^2, its mountains with it), its 10 wards; names in English; no airport (CTS, 40 km)
    {"wikidata": "Q34664", "levels": [8], "strip": "( [Ww]ard|-ku)$", "names": "en", "airport": None, "pbf": "asia/japan/chugoku"},
    #   Hiroshima: the city (907 km^2), its 8 wards; names in English; no airport (HIJ, 40 km)
    {"wikidata": "Q11506", "boundary": "Q11506|Q994499", "levels": [6], "tertiary": True, "pbf": "asia/indonesia/nusa-tenggara"},
    #   Denpasar and Kuta (Bali): the city and the Kuta kecamatan south of it (the beach, Legian, the airport), their
    #   kecamatan; DPS
    {"wikidata": "Q3274172", "place": ["Ubud", 115.2625, -8.5069], "airport": None, "tertiary": True, "pbf": "asia/indonesia/nusa-tenggara"},
    #   Ubud (Bali): its kecamatan (the town, its rice terraces and villages); no airport; not in data/cities.csv
    {"wikidata": "Q3630", "levels": [5], "core": [106.8270, -6.1750, 1.5], "place": ["Jakarta", 106.8270, -6.1900], "radius": 12, "airport": ["HLP", 106.8908, -6.2666], "pbf": "asia/indonesia/java"},
    #   Jakarta: the capital region (664 km^2; the Thousand Islands left out, far), its 5 kota; HLP (CGK, 20 km out,
    #   would stretch the window); the KRL Commuterline, the MRT
    {"wikidata": "Q7568", "airport": None, "tertiary": True, "pbf": "asia/indonesia/java"},
    #   Yogyakarta: the city (32 km^2, the kraton at its heart); no airport (YIA, 40 km)
    {"wikidata": "Q1353", "boundary": "Q1353|Q987", "airport": None, "core": [77.2300, 28.6560, 1.5], "pbf": "asia/india/northern-zone"},
    #   Delhi: the Municipal Corporation's city and New Delhi; no airport (DEL, south of them); the Metro; the lanes of
    #   Old Delhi (Chandni Chowk)
    {"wikidata": "Q66485", "boundary": "Q6124132", "airport": None, "core": [75.8240, 26.9240, 1.5], "pbf": "asia/india/northern-zone"},
    #   Jaipur: the Municipal Corporation; no airport (JAI, south of it); the Metro; the lanes of the walled Pink City
    {"wikidata": "Q1156", "boundary": "Q2341660|Q2085374", "levels": [9], "names": "en", "core": [72.8330, 18.9300, 1.5],
     "pbf": "asia/india/western-zone"},
    #   Mumbai: the City and the Suburban districts (603 km^2), the corporation's zones; names in English; BOM; the
    #   Suburban Railway, the Metro; the lanes of the Fort and Colaba
    # -- the Americas
    {"wikidata": "Q60", "boundary": "Q11299|Q18419", "airport": None, "core": [-74.0060, 40.7100, 2], "pbf": "north-america/us/new-york"},
    #   New York: Manhattan and Brooklyn (239 km^2; the other three boroughs left out, residential); no airport (LGA
    #   and JFK in Queens); the Subway, PATH, the LIRR and Metro-North
    {"wikidata": "Q61", "airport": ["DCA", -77.0377, 38.8512], "pbf": "north-america/us/district-of-columbia"},
    #   Washington: the District (177 km^2); DCA just over the Potomac; the Metro, MARC and VRE
    {"wikidata": "Q23768", "boundary": "Q108403", "core": [-115.1480, 36.1670, 1.5], "place": ["Las Vegas", -115.1600, 36.1300], "radius": 8,
     "airport": ["LAS", -115.1523, 36.0801], "core": [-115.1430, 36.1700, 1.2], "pbf": "north-america/us/nevada"},
    #   Las Vegas: Clark County 8 km round the middle of the Strip (the Strip lies in unincorporated Paradise, not the
    #   city): downtown and Fremont Street to the airport
    {"wikidata": "Q18094", "airport": ["HNL", -157.9225, 21.3187], "core": [-157.8290, 21.2780, 1.2], "pbf": "north-america/us/hawaii"},
    #   Honolulu: the census place (boundary=place: the city-county takes in all of Oahu), Waikiki its core; HNL
    {"wikidata": "Q100", "pbf": "north-america/us/massachusetts"},
    #   Boston: the city (232 km^2 with its harbour), its neighborhoods; BOS in East Boston; the T, the Commuter Rail
    {"wikidata": "Q34404", "radius": 8, "airport": None, "core": [-90.0650, 29.9580, 1], "tertiary": True,
     "pbf": "north-america/us/louisiana"},
    #   New Orleans: the parish-city 8 km round the French Quarter (the rest marsh and lake); no airport (MSY, 18 km)
    {"wikidata": "Q1297", "radius": 10, "airport": None, "core": [-87.6290, 41.8820, 1.5], "pbf": "north-america/us/illinois"},
    #   Chicago: the city 10 km round the Loop (606 km^2 whole: its South and West sides residential); no airport (MDW
    #   12 km, ORD 25 km); the L, Metra
    {"wikidata": "Q8652", "boundary": "Q8652|Q201516", "airport": ["MIA", -80.2906, 25.7959], "pbf": "north-america/us/florida"},
    #   Miami: the city and Miami Beach over Biscayne Bay (South Beach, Art Deco); MIA just west of the city; Metrorail
    {"wikidata": "Q49233", "boundary": "Q488543", "core": [-81.3790, 28.5420, 1.5], "place": ["Orlando", -81.4700, 28.4700], "radius": 14, "airport": None,
     "core": [-81.3790, 28.5410, 1], "pbf": "north-america/us/florida"},
    #   Orlando: Orange County 14 km round International Drive -- downtown, Universal, Walt Disney World's parks (in
    #   Bay Lake, not the city); no airport (MCO, 16 km east); SunRail
    {"wikidata": "Q65", "boundary": "Q104994", "core": [-118.2430, 34.0520, 1.5], "place": ["Los Angeles", -118.3600, 34.0400], "radius": 14,
     "airport": ["LAX", -118.4085, 33.9416], "core": [-118.2468, 34.0500, 1.2], "pbf": "north-america/us/california"},
    #   Los Angeles: the county 14 km round Mid-Wilshire -- downtown, Hollywood, Beverly Hills, Santa Monica, LAX (the
    #   city alone 1300 km^2, without the last three); Metro Rail, Metrolink
    {"wikidata": "Q62", "core": [-122.4080, 37.7880, 1.5], "place": ["San Francisco", -122.4450, 37.7650], "radius": 8, "airport": None,
     "pbf": "north-america/us/california"},
    #   San Francisco: the city-county 8 km round Twin Peaks (its relation takes in the bay, the sea, the Farallones);
    #   no airport (SFO in San Mateo County); BART, Muni Metro, the cable cars, Caltrain
    {"wikidata": "Q16552", "radius": 9, "pbf": "north-america/us/california"},
    #   San Diego: the city 9 km round downtown (964 km^2 whole), Balboa Park, Old Town, Mission Bay; SAN; the Trolley
    {"wikidata": "Q5083", "airport": None, "pbf": "north-america/us/washington"},
    #   Seattle: the city (217 km^2 of land); no airport (SEA, 20 km south); Link light rail, Sounder
    {"wikidata": "Q1345", "pbf": "north-america/us/pennsylvania"},
    #   Philadelphia: the city-county (370 km^2), PHL in its south-west; SEPTA's subway and Regional Rail
    {"wikidata": "Q172", "radius": 10, "airport": ["YTZ", -79.3962, 43.6275], "pbf": "north-america/canada/ontario"},
    #   Toronto: the city 10 km round downtown (630 km^2 whole); YTZ on the Island (YYZ, 22 km, would stretch the
    #   window); the subway, the streetcars' city, GO Transit
    {"wikidata": "Q340", "airport": None, "core": [-73.5540, 45.5070, 1.2], "pbf": "north-america/canada/quebec"},
    #   Montreal: the city (365 km^2 of its island), its arrondissements; no airport (YUL in Dorval); the Métro, the
    #   REM, exo; Vieux-Montréal the core
    {"wikidata": "Q2145", "core": [-71.2080, 46.8130, 1], "pbf": "north-america/canada/quebec"},
    #   Quebec City: the city (485 km^2), its arrondissements; YQB in its west; the walled Vieux-Québec
    {"wikidata": "Q24639", "airport": None, "pbf": "north-america/canada/british-columbia"},
    #   Vancouver: the city (115 km^2: Stanley Park, Gastown, Granville Island); no airport (YVR on Sea Island, in
    #   Richmond); the SkyTrain
    {"wikidata": "Q1489", "radius": 10, "levels": [6], "airport": ["MEX", -99.0721, 19.4363], "pbf": "north-america/mexico"},
    #   Mexico City: the capital 10 km round the Zócalo (1485 km^2 whole, mostly mountain and sprawl), its alcaldías;
    #   MEX; the Metro, the Tren Suburbano
    {"wikidata": "Q8969", "airport": ["CUN", -86.8771, 21.0365], "tertiary": True, "pbf": "north-america/mexico"},
    #   Cancún: the city and its Hotel Zone strip; CUN
    {"wikidata": "Q989988", "airport": None, "tertiary": True, "pbf": "north-america/mexico"},
    #   Playa del Carmen: the town, Fifth Avenue its core; no airport (CUN, 50 km)
    {"wikidata": "Q131429", "boundary": "Q2000066", "airport": None, "tertiary": True, "pbf": "north-america/mexico"},
    #   Oaxaca: the municipality of Oaxaca de Juárez, the colonial centre; no airport
    {"wikidata": "Q1563", "boundary": "Q12588", "radius": 9, "levels": [6], "airport": None, "core": [-82.3500, 23.1380, 1.2],
     "pbf": "central-america/cuba"},
    #   Havana: the province 9 km round the centre, its municipios; no airport (HAV, 15 km); Habana Vieja the core
    {"wikidata": "Q3306", "boundary": "Q2216411", "radius": 8, "levels": [8], "airport": None,
     "core": [-79.5350, 8.9530, 1], "pbf": "central-america/panama"},
    #   Panama City: the district 8 km round the centre (2000 km^2 whole, forest), its corregimientos; no airport
    #   (PTY, 20 km); Casco Viejo the core; the Metro
    {"wikidata": "Q3070", "boundary": "Q2536213", "place": ["San José", -84.0800, 9.9330], "airport": None,
     "pbf": "central-america/costa-rica"},
    #   San José: the canton (45 km^2), its distritos; no airport (SJO, in Alajuela)
    {"wikidata": "Q2467", "boundary": "Q3339000", "radius": 14, "tertiary": True, "pbf": "central-america/bahamas"},
    #   Nassau: New Providence (207 km^2, the island the city covers), Paradise Island, cut 14 km round the city (its
    #   relation reaches out over far cays); NAS
    {"wikidata": "Q34820", "airport": None, "core": [-69.8850, 18.4740, 1], "pbf": "central-america/haiti-and-domrep"},
    #   Santo Domingo: the Distrito Nacional (104 km^2); no airport (SDQ, 25 km east); the Zona Colonial; the Metro
    {"wikidata": "Q1568095", "boundary": "Q1020261", "core": [-68.3690, 18.5570, 1.5], "place": ["Punta Cana", -68.4200, 18.6400], "radius": 11,
     "airport": ["PUJ", -68.3634, 18.5674], "tertiary": True, "pbf": "central-america/haiti-and-domrep"},
    #   Punta Cana: Higüey municipality 11 km round Bávaro -- the resort coast from Cap Cana to Arena Gorda; PUJ
    {"wikidata": "Q41211", "place": ["San Juan", -66.1170, 18.4650], "core": [-66.1150, 18.4650, 1],
     "pbf": "north-america/us/puerto-rico"},
    #   San Juan: the municipio (199 km^2 with its lagoons), Old San Juan the core; SJU; the Tren Urbano
    {"wikidata": "Q2868", "boundary": "Q579240", "place": ["Lima", -77.0300, -12.0900], "radius": 9, "levels": [8],
     "airport": None, "core": [-77.0300, -12.0470, 1.2], "pbf": "south-america/peru"},
    #   Lima: the province 9 km round San Isidro -- the Centro Histórico, Miraflores, Barranco -- its districts; no
    #   airport (LIM in Callao, 12 km); the Metro, the Metropolitano
    {"wikidata": "Q5582862", "boundary": "Q1132101", "place": ["Cusco", -71.9780, -13.5170], "radius": 5, "levels": [8],
     "airport": ["CUZ", -71.9388, -13.5357], "tertiary": True, "pbf": "south-america/peru"},
    #   Cusco: the province 5 km round the Plaza de Armas -- Sacsayhuamán above it, CUZ -- its districts
    {"wikidata": "Q1486", "boundary": "r1224652", "levels": [10], "airport": ["AEP", -58.4156, -34.5592],
     "pbf": "south-america/argentina"},
    #   Buenos Aires: the city (203 km^2: its level-8 relation, the level-4 one runs out into the Río de la Plata), its
    #   48 barrios; AEP on the river (EZE, 22 km, would stretch the window); the Subte
    {"wikidata": "Q8678", "radius": 10, "airport": ["SDU", -43.1634, -22.9105], "pbf": "south-america/brazil/sudeste"},
    #   Rio de Janeiro: the city 10 km round the Centro (1200 km^2 whole) -- Copacabana, Ipanema, Corcovado, Sugarloaf;
    #   SDU on the bay (GIG, 15 km, would stretch the window); the Metrô, SuperVia
    {"wikidata": "Q174", "radius": 10, "airport": ["CGH", -46.6553, -23.6261], "pbf": "south-america/brazil/sudeste"},
    #   São Paulo: the city 10 km round the Sé (1521 km^2 whole); CGH (GRU, 25 km); the Metrô, the CPTM
    {"wikidata": "Q2887", "boundary": "Q45632", "radius": 9, "levels": [8], "airport": None, "core": [-70.6500, -33.4390, 1.2],
     "pbf": "south-america/chile"},
    #   Santiago: the Provincia de Santiago 9 km round the Plaza de Armas, its comunas (Santiago, Providencia, Las
    #   Condes...); no airport (SCL, 15 km); the Metro
    {"wikidata": "Q2841", "boundary": "r1387968", "place": ["Bogotá", -74.0700, 4.6300], "radius": 10, "airport": None,
     "core": [-74.0730, 4.5970, 1], "pbf": "south-america/colombia"},
    #   Bogotá: the capital 10 km round Chapinero's south (its district 1600 km^2 out to the páramo of Sumapaz), its
    #   localidades; no airport (BOG, 12 km); La Candelaria the core
    {"wikidata": "Q48278", "radius": 8, "airport": ["EOH", -75.5906, 6.2199], "pbf": "south-america/colombia"},
    #   Medellín: the municipality 8 km round the centre (380 km^2 whole, its rural corregimientos), its comunas; EOH
    #   (MDE, 20 km over the mountains); the Metro, the Metrocable
    {"wikidata": "Q657461", "radius": 6, "place": ["Cartagena", -75.5480, 10.4230], "airport": ["CTG", -75.5130, 10.4424],
     "tertiary": True, "pbf": "south-america/colombia"},
    #   Cartagena: the district 6 km round the walled city -- Getsemaní, Bocagrande, San Felipe -- (600 km^2 whole, its
    #   islands); CTG
    {"wikidata": "Q2900", "boundary": "Q2466472", "radius": 9, "airport": None, "core": [-78.5130, -0.2200, 1.2],
     "pbf": "south-america/ecuador"},
    #   Quito: the canton 9 km round the Centro Histórico (4200 km^2 whole), its parroquias; no airport (UIO, 18 km);
    #   the Metro
    {"wikidata": "Q1335", "airport": None, "core": [-56.2050, -34.9070, 1], "pbf": "south-america/uruguay"},
    #   Montevideo: the city (the department's level-8 urban part), its municipios; no airport (MVD, in Canelones);
    #   the Ciudad Vieja the core
    # -- Africa
    {"wikidata": "Q85", "boundary": "Q30805|Q30832", "place": ["Cairo", 31.2000, 30.0300], "radius": 12, "airport": None,
     "core": [31.2560, 30.0470, 1.5], "names": "en", "pbf": "africa/egypt"},
    #   Cairo: the Cairo and Giza governorates 12 km round the Nile -- downtown, Islamic Cairo, Giza's pyramids --
    #   names in English; no airport (CAI, 20 km); the Metro; the lanes of Islamic Cairo
    {"wikidata": "Q130514", "boundary": "Q30797", "place": ["Luxor", 32.6200, 25.7100], "radius": 6, "airport": None,
     "tertiary": True, "names": "en", "pbf": "africa/egypt"},
    #   Luxor: the governorate 6 km round the Nile -- Karnak and Luxor temples, the west bank to the Valley of the Kings
    {"wikidata": "Q187284", "boundary": "Q30831", "radius": 10, "airport": ["HRG", 33.7994, 27.1783], "tertiary": True, "names": "en", "pbf": "africa/egypt"},
    #   Hurghada: the Red Sea governorate 10 km round the town (its relation the whole coast); HRG
    {"wikidata": "Q644", "boundary": "Q30815", "place": ["Sharm El Sheikh", 34.3300, 27.9200], "radius": 10,
     "airport": ["SSH", 34.3950, 27.9773], "tertiary": True, "names": "en", "pbf": "africa/egypt"},
    #   Sharm El Sheikh: South Sinai 10 km round Naama Bay -- Old Sharm to the airport; SSH; not in data/cities.csv
    {"wikidata": "Q101625", "airport": ["RAK", -8.0363, 31.6069], "core": [-7.9890, 31.6295, 1.5], "names": "fr", "pbf": "africa/morocco"},
    #   Marrakech: the commune (230 km^2), its arrondissements; names in French (OSM's carry Tifinagh and Arabic too);
    #   RAK; the medina's lanes (Jemaa el-Fnaa, the souks)
    {"wikidata": "Q7903", "airport": None, "core": [-7.6180, 33.6000, 1.2], "names": "fr", "pbf": "africa/morocco"},
    #   Casablanca: the commune, its arrondissements; no airport (CMN, 25 km); the tramway; the old medina
    {"wikidata": "Q80985", "airport": None, "core": [-4.9770, 34.0640, 1.5], "names": "fr", "pbf": "africa/morocco"},
    #   Fez: the commune, its arrondissements; no airport (FEZ, 12 km); Fès el-Bali, the walled medina, its lanes
    {"wikidata": "Q126148", "airport": None, "core": [-5.8120, 35.7860, 1.2], "names": "fr", "pbf": "africa/morocco"},
    #   Tangier: the commune; no airport (TNG, 12 km); the medina and the kasbah over the strait
    {"wikidata": "Q3551", "airport": None, "core": [-6.8350, 34.0240, 1.2], "names": "fr", "pbf": "africa/morocco"},
    #   Rabat: the commune; no airport (RBA, in Salé); the medina, the Kasbah of the Udayas, the tramway
    {"wikidata": "Q170525", "airport": None, "tertiary": True, "names": "fr", "pbf": "africa/morocco"},
    #   Agadir: the commune, the bay's beach and the kasbah hill; no airport (AGA, 20 km)
    {"wikidata": "Q3572", "boundary": "Q328109", "airport": ["TUN", 10.2272, 36.8510], "core": [10.1700, 36.7990, 1.2],
     "names": "fr", "pbf": "africa/tunisia"},
    #   Tunis: the governorate (346 km^2: the city, La Marsa, Carthage, Sidi Bou Said, the lake), its délégations;
    #   names in French; TUN; the medina's lanes; the TGM
    {"wikidata": "Q3561", "boundary": "Q141026", "radius": 9, "levels": [8], "airport": None, "core": [3.0600, 36.7850, 1],
     "names": "fr", "pbf": "africa/algeria"},
    #   Algiers: the wilaya 9 km round the centre, its communes; names in French; no airport (ALG, 16 km); the Casbah
    {"wikidata": "Q5465", "boundary": "Q1185115", "place": ["Cape Town", 18.4300, -33.9500], "radius": 10, "airport": None,
     "pbf": "africa/south-africa"},
    #   Cape Town: the metro 10 km round the City Bowl -- the V&A Waterfront, Table Mountain, Sea Point, Camps Bay,
    #   Kirstenbosch -- (2450 km^2 whole); no airport (CPT, 18 km)
    {"wikidata": "Q34647", "boundary": "Q2346838", "place": ["Johannesburg", 28.0400, -26.1700], "radius": 10, "airport": None,
     "pbf": "africa/south-africa"},
    #   Johannesburg: the metro 10 km round Braamfontein -- the CBD, Maboneng, Melville, Rosebank, Sandton's edge;
    #   no airport (JNB, 20 km); the Gautrain
    {"wikidata": "Q5468", "boundary": "Q311544", "radius": 8, "airport": None, "pbf": "africa/south-africa"},
    #   Durban: eThekwini 8 km round the centre -- the Golden Mile, the harbour, Berea; no airport (DUR, 30 km)
    {"wikidata": "Q3870", "boundary": "Q3335223", "radius": 9, "airport": None, "pbf": "africa/kenya"},
    #   Nairobi: the county 9 km round the CBD -- Westlands, Kilimani, the National Park's edge -- (696 km^2 whole); no
    #   airport (NBO, 15 km)
    {"wikidata": "Q2222874", "boundary": "Q65127655", "airport": None, "core": [39.1890, -6.1620, 1], "tertiary": True,
     "pbf": "africa/tanzania"},
    #   Zanzibar City: the Mjini district (16 km^2), Stone Town its core; no airport (ZNZ, just south of it)
    {"wikidata": "Q3929", "boundary": "Q960645", "airport": None, "tertiary": True, "pbf": "africa/mauritius"},
    #   Port Louis: the district (42 km^2: the harbour, the Caudan Waterfront, the Citadel); no airport (MRU, 40 km)
    {"wikidata": "Q3761", "pbf": "africa/ghana"},
    #   Accra: the city, its neighbourhoods; ACC
    {"wikidata": "Q8673", "boundary": "Q815913", "place": ["Lagos", 3.4200, 6.4600], "radius": 10, "levels": [6],
     "airport": None, "pbf": "africa/nigeria"},
    #   Lagos: the state 10 km round Lagos Island -- Ikoyi, Victoria Island, Lekki's start, the mainland to Yaba -- its
    #   LGAs; no airport (LOS, 15 km)
    {"wikidata": "Q3718", "boundary": "Q2066372", "levels": [8], "strip": "^Commune de ", "airport": None,
     "pbf": "africa/senegal-and-gambia"},
    #   Dakar: the département (the Cap-Vert peninsula's tip, 79 km^2), its communes d'arrondissement; no airport
    #   (DSS, 40 km)
    {"wikidata": "Q3624", "levels": [6], "names": "en", "pbf": "africa/ethiopia"},
    #   Addis Ababa: the chartered city (527 km^2), its sub-cities; names in English; ADD at Bole; the light rail
    {"wikidata": "Q3859", "radius": 8, "airport": None, "pbf": "africa/rwanda"},
    #   Kigali: the city 8 km round the centre (730 km^2 whole); no airport (KGL, 10 km)
    {"wikidata": "Q3935", "radius": 7, "airport": None, "tertiary": True, "pbf": "africa/namibia"},
    #   Windhoek: the municipality 7 km round the centre (5000 km^2 whole, its farmland), its suburbs; no airport
    #   (WDH, 40 km)
    # -- the rest of the ~300 (pbfs kept back from the batches above: .keep)
    {"wikidata": "Q214681", "boundary": "Q3291873|Q3632943", "place": ["Panaji", 73.8280, 15.4990], "radius": 10,
     "airport": None, "tertiary": True, "pbf": "asia/india/western-zone"},
    #   Goa: Tiswadi and Bardez talukas 10 km round Panaji -- the capital, Old Goa's churches, the beaches of Candolim
    #   and Calangute; no airport (GOI, 25 km)
    {"wikidata": "Q5764", "airport": None, "tertiary": True, "pbf": "asia/uzbekistan"},
    #   Bukhara: the city (Buxoro shahri), the old town's lanes and madrasas; no airport
    {"wikidata": "Q1930", "radius": 8, "airport": None, "pbf": "north-america/canada/ontario"},
    #   Ottawa: the city 8 km round Parliament Hill (2790 km^2 whole); no airport (YOW, 11 km); the O-Train
    {"wikidata": "Q274120", "place": ["Niagara Falls", -79.0750, 43.0900], "airport": None, "tertiary": True, "pbf": "north-america/canada/ontario"},
    #   Niagara Falls: the Ontario city, the falls and Clifton Hill; no airport; not in data/cities.csv
    {"wikidata": "Q277408", "place": ["Tulum", -87.4650, 20.2110], "airport": None, "tertiary": True, "pbf": "north-america/mexico"},
    #   Tulum: the town, the ruins on the cliff; no airport; not in data/cities.csv
    # -- Oceania
    {"wikidata": "Q3130", "place": ["Sydney", 151.2200, -33.8700], "radius": 10, "levels": [6],
     "airport": ["SYD", 151.1772, -33.9461], "pbf": "australia-oceania/australia"},
    #   Sydney: Greater Sydney (boundary=place, 12000 km^2) 10 km round the harbour -- the CBD, the Opera House, Bondi,
    #   Manly, Taronga -- its LGAs; SYD; Sydney Trains, the Metro, the light rail
    {"wikidata": "Q3141", "radius": 9, "levels": [6], "airport": None, "pbf": "australia-oceania/australia"},
    #   Melbourne: Greater Melbourne (boundary=place) 9 km round the CBD -- Fitzroy, St Kilda, the Bay -- its LGAs; no
    #   airport (MEL, 20 km); the trams' city, Metro Trains
    {"wikidata": "Q34932", "boundary": "Q917682", "radius": 9, "airport": None, "pbf": "australia-oceania/australia"},
    #   Brisbane: the City of Brisbane 9 km round the CBD (1340 km^2 whole), South Bank; no airport (BNE, 12 km);
    #   Queensland Rail's City network
    {"wikidata": "Q3183", "boundary": "Q1855330", "airport": None, "tertiary": True, "pbf": "australia-oceania/australia"},
    #   Perth: the City of Perth (20 km^2: the CBD, Northbridge, Kings Park, the river front); no airport (PER, 10 km);
    #   Transperth's trains
    {"wikidata": "Q140075", "boundary": "Q1069385", "place": ["Gold Coast", 153.4200, -28.0000], "radius": 10,
     "airport": None, "tertiary": True, "pbf": "australia-oceania/australia"},
    #   Gold Coast: the city 10 km round Surfers Paradise (its 1300 km^2 out into the hinterland); no airport (OOL,
    #   25 km); the G:link tram
    {"wikidata": "Q189133", "boundary": "Q1025962", "radius": 6, "airport": ["CNS", 145.7553, -16.8758], "tertiary": True,
     "pbf": "australia-oceania/australia"},
    #   Cairns: the region 6 km round the Esplanade (its 1700 km^2 of rainforest), CNS
    {"wikidata": "Q37100", "boundary": "Q726917", "radius": 9, "airport": None, "pbf": "australia-oceania/new-zealand"},
    #   Auckland: the region 9 km round the CBD (its 5000 km^2 out over the gulf's islands); no airport (AKL, 17 km)
    {"wikidata": "Q23661", "boundary": "Q47037646", "pbf": "australia-oceania/new-zealand"},
    #   Wellington: Wellington City (290 km^2), its suburbs; WLG at Rongotai; the Metlink trains, the cable car
    {"wikidata": "Q79990", "airport": None, "pbf": "australia-oceania/new-zealand"},
    #   Christchurch: the city (boundary=place), its suburbs; no airport (CHC, 10 km)
    {"wikidata": "Q613684", "place": ["Queenstown", 168.6620, -45.0310], "radius": 7, "airport": ["ZQN", 168.7392, -45.0211],
     "tertiary": True, "pbf": "australia-oceania/new-zealand"},
    #   Queenstown: the Queenstown-Lakes district 7 km round the town, Lake Wakatipu; ZQN; not in data/cities.csv
    # -- the last of the ~300
    {"wikidata": "Q35493", "radius": 10, "airport": None, "pbf": "asia/kazakhstan"},
    #   Almaty: the city 10 km round the centre (its 680 km^2 up into the Tian Shan); no airport (ALA, 15 km); the metro
    {"wikidata": "Q23430", "radius": 9, "airport": None, "pbf": "asia/mongolia"},
    #   Ulaanbaatar: the capital 9 km round Sükhbaatar Square (its 4700 km^2 of steppe); no airport
    {"wikidata": "Q1555", "radius": 8, "airport": ["GUA", -90.5275, 14.5833], "pbf": "central-america/guatemala"},
    #   Guatemala City: the municipio 8 km round the Zona 1 centre, La Aurora's GUA
    {"wikidata": "Q212773", "place": ["Antigua Guatemala", -90.7343, 14.5586], "radius": 4, "airport": None, "tertiary": True,
     "pbf": "central-america/guatemala"},
    #   Antigua Guatemala: the municipio 4 km round the Parque Central (its volcano slopes cut); not in data/cities.csv
    {"wikidata": "Q36947", "radius": 10, "airport": None, "pbf": "south-america/brazil/nordeste"},
    #   Salvador: the município 10 km round the Pelourinho (its 690 km^2 north to the airport cut); no airport; the metro
    {"wikidata": "Q48344", "airport": ["REC", -34.9236, -8.1265], "pbf": "south-america/brazil/nordeste"},
    #   Recife: the município (218 km^2), Recife Antigo, Boa Viagem; REC
    {"wikidata": "Q43463", "airport": ["FOR", -38.5326, -3.7763], "pbf": "south-america/brazil/nordeste"},
    #   Fortaleza: the município (314 km^2), the beach front; FOR
    {"wikidata": "Q132997", "radius": 9, "airport": None, "pbf": "south-america/brazil/sul"},
    #   Florianópolis: the município 9 km round the centre (the island's south and north beaches cut); no airport
    {"wikidata": "Q202316", "airport": ["IGU", -54.4850, -25.6003], "tertiary": True, "pbf": "south-america/brazil/sul"},
    #   Foz do Iguaçu: the município (620 km^2: the town, the park, the falls), IGU
    {"wikidata": "Q1491", "radius": 7, "airport": None, "pbf": "south-america/bolivia"},
    #   La Paz: the municipio 7 km round the Plaza Murillo (its 470 km^2 down the Zongo valley cut); no airport (LPB,
    #   up in El Alto)
    {"wikidata": "Q637555", "boundary": "Q1421939", "radius": 5, "airport": ["MBJ", -77.9134, 18.5037], "tertiary": True,
     "pbf": "central-america/jamaica"},
    #   Montego Bay: Saint James parish 5 km round the town, the Hip Strip; MBJ
    {"wikidata": "Q2248586", "place": ["Krabi", 98.8650, 8.0500], "radius": 9, "airport": None, "tertiary": True, "pbf": "asia/thailand"},
    #   Krabi: Mueang Krabi district 9 km round between the town and Ao Nang's beach (Railay at the edge); not in
    #   data/cities.csv
    {"wikidata": "Q13025347", "place": ["Ko Samui", 100.0600, 9.5000], "airport": ["USM", 100.0623, 9.5478], "tertiary": True,
     "pbf": "asia/thailand"},
    #   Ko Samui: the island's city municipality (230 km^2), Chaweng, Lamai; USM; not in data/cities.csv
    {"wikidata": "Q203370", "boundary": "Q476434", "place": ["Ayutthaya", 100.5680, 14.3560], "radius": 5, "airport": None,
     "tertiary": True, "pbf": "asia/thailand"},
    #   Ayutthaya: its amphoe 5 km round the island (the old capital's temples, Wat Chaiwatthanaram over the river)
    {"wikidata": "Q131620", "airport": None, "pbf": "south-america/brazil/nordeste"},
    #   Natal: the município (167 km^2), Ponta Negra, the Forte dos Reis Magos; no airport (NAT, 25 km)
    {"wikidata": "Q36167", "boundary": "Q36399", "place": ["Huế", 107.5800, 16.4650], "radius": 6, "airport": None,
     "tertiary": True, "pbf": "asia/vietnam"},
    #   Huế: the city (5000 km^2 since 2025) 6 km round the Citadel, the Perfume River, the tombs south cut
    {"wikidata": "Q138640987", "boundary": "Q138640987|Q138636916|Q138643826|Q138642399", "place": ["Nha Trang", 109.1930, 12.2450],
     "radius": 8, "airport": None, "tertiary": True, "pbf": "asia/vietnam"},
    #   Nha Trang: its four wards (since the 2025 reform: Nha Trang, Bắc, Nam, Tây), the beach front; not in data/cities.csv
    {"wikidata": "r19272141", "place": ["Hạ Long", 107.0800, 20.9550], "radius": 6, "airport": None,
     "tertiary": True, "pbf": "asia/vietnam"},
    #   Hạ Long: the Hạ Long ward round Bãi Cháy, the bay's first islands; not in data/cities.csv, its relation (no
    #   wikidata tag) for an id
    {"wikidata": "Q1800", "boundary": "Q16134795", "radius": 7, "airport": None, "tertiary": True, "pbf": "asia/india/southern-zone"},
    #   Kochi: its taluk 7 km round Ernakulam -- Fort Kochi, Mattancherry over the water; no airport (COK, 25 km)
    {"wikidata": "Q1352", "radius": 10, "airport": None, "pbf": "asia/india/southern-zone"},
    #   Chennai: the corporation 10 km round George Town (Marina Beach, Mylapore); no airport (MAA, 14 km)
    {"wikidata": "Q10086", "boundary": "Q25566589", "radius": 6, "airport": None, "tertiary": True, "pbf": "asia/india/southern-zone"},
    #   Mysuru: its taluk 6 km round the palace, Chamundi Hill
]
PAD_KM = 2
OUTLINE_KM = 40                                           # (an outline's parts farther from the city's point: left out)
GRID = 0.00005                                            # (degrees: 5.6 m north-south, 3.7 m east-west at 48°)
SIMPLIFY_M = {"streets": 10, "lanes": 3, "rail": 10, "water": 12, "waterways": 12, "green": 25, "districts": 15, "airport": 20,
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

CORE_KM = 1.5                                             # (the old town's lanes: within this of the middle -- or the spec's `core`)
LANES = "pedestrian|living_street|residential|unclassified|footway|steps"
OUT_KM = 60                                               # (a metro's, a commuter line's run out of the city: to its end, within this of the middle)
BUDGET_KB = 150                                           # (a city's file gzipped at most: else built again coarser, COARSER)
COARSER = [1, 1.25, 1.5, 1.75, 2, 2.4, 2.8, 3.4, 4]      # (the steps: simplify tolerances times this, the least areas times its square)
TILE_DEG = (0.3, 0.2)                                     # (a big city's box asked for in tiles of this, lon x lat: Overpass times out on more)
# COMMUTER LINES (kind s, drawn whole as the metro's): route=light_rail, or a train route of such a network or such a
# number -- S-Bahn, S-tog, RER and Transilien, London Overground and the Elizabeth line, Cercanias, Rodalies (R1..),
# Proastiakos, Esko, HEV, Rome's FL lines, Madrid's C-1.., Milan's S lines, Turin's SFM, DART, Marmaray...; not a regional train (RE1)
COMMUTER_NET = ("S-Bahn|S-tog|RER|AKN|Transilien|Overground|Elizabeth|Cercan|Rodalies|Proastiak|Προαστιακός|Esko|HÉV|"
                "Suburban|Suburbano|Pendelt|DART|Marmaray|SKM|WKD|Szybka Kolej|CP Lisboa|Fertagus|Пригород|МЦД|МЦК|Transport for London|"
                "Circumvesuviana|Cumana|Circumflegrea|EAV|Rodalia|Metro do Porto|HSL|БГ:Воз|Euskotren|FGC|Ferrocarrils de la Generalitat|"
                "\\bJR\\b|旅客鉄道|Keikyu|京急|Keio|京王|Odakyu|小田急|Tokyu|東急|Seibu|西武|Tobu|東武|Keisei|京成|Hankyu|阪急|Hanshin|阪神|"
                "Keihan|京阪|Kintetsu|近鉄|Nankai|南海|SRT Red|Airport Rail Link|KTM Komuter|\\bMTR\\b|Korail|코레일|臺鐵|台鐵|Taiwan Railway|Israel Railways|רכבת ישראל|KRL|Commuter Line|Commuterline|Mumbai Suburban|Long Island Rail Road|LIRR|Metro-North|NJ Transit|MBTA Commuter|Commuter Rail|MARC|VRE|Virginia Railway Express|Metra|Caltrain|Metrolink|COASTER|Sounder|SEPTA Regional|Regional Rail|Tri-Rail|SunRail|GO Transit|\bexo\b|Trem Metropolitano|CPTM|SuperVia|Tren Suburbano|Metrotrén|Tren Urbano|Gautrain|Metrorail|Sydney Trains|NSW TrainLink|Metro Trains|V/Line|Queensland Rail|Transperth|Translink")
COMMUTER_REF = "^(S ?[0-9]|FL[0-9]|C-?[0-9]|R[0-9]|SFM ?[0-9A-Z])"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
UA = {"User-Agent": "map-citymaps-builder/0.1 (city detail maps from OpenStreetMap)"}

Q_BOUNDARY = """[out:json][timeout:120];
rel[boundary=administrative][wikidata={qid}]({s},{w},{n},{e});
out geom;"""
Q_LANES = """[out:json][timeout:180];
way[highway~"^({lanes})$"][name](around:{r},{lat},{lon});
out tags geom;"""
Q_LINES = """[out:json][timeout:300][maxsize:536870912][bbox:{s},{w},{n},{e}];
way[highway~"^(motorway|trunk|primary|secondary)$"];
out tags geom qt;
rel[route~"^(subway|light_rail|train)$"]->.r;
.r out body qt;
(way(r.r)[railway~"^(rail|subway|light_rail|narrow_gauge)$"]; way[railway=rail][usage~"^(main|branch)$"][!service];)->.t;
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
way(r.r)[railway~"^(rail|subway|light_rail|narrow_gauge)$"]->.t;
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
NAMES = {"lang": None}                                    # (the city's `names`: "en" -- its tags' name:en for name where
                                                          #  there is one, a city whose own names the page cannot read)


def named(d):
    """the answer `d` with each element's name in the city's `names` language, where it has one"""
    if NAMES["lang"]:
        k = "name:" + NAMES["lang"]
        for el in d.get("elements", []):
            t = el.get("tags")
            if t and t.get(k):
                t["name"] = t[k]
    return d


def ask(path, query, state={"server": 0, "last": 0.0}, tries=16):
    """the answer to a query, kept at `path` (gzipped JSON): read from there when it is there"""
    if os.path.exists(path):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return named(json.load(f))
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
        if attempt >= tries - 1:
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
def city_row(qid, spec=None):
    """the city's row of data/cities.csv -- or the spec's `place`, [name, lon, lat], for one not in it (Venice: the
    list's cities are those of 500,000 people or more, or so tagged); for one in it, `place` moves only its centre
    (the window's middle: Las Vegas's Strip, not downtown)"""
    import citiescsv                                       # (grouped by country: citiescsv.py)
    for r in citiescsv.read():
        if r["wikidata"] == qid:
            if spec and spec.get("place"):
                r = dict(r, lon=str(spec["place"][1]), lat=str(spec["place"][2]))
            return r
    if spec and spec.get("place"):
        name, lon, lat = spec["place"]
        return {"name": name, "lon": str(lon), "lat": str(lat), "wikidata": qid}
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
    if wet.intersection(outline).area > 0.6 * outline.area and wet.contains(Point(0, 0)):   # (a coast that cuts no
        #  face: no side to trust; but a city mostly sea with its point on land kept: Helsinki's outer islands)
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
    """a district's level as `levels` names it: its admin_level, "place=suburb" for a place boundary (Amsterdam's
    stadsdelen, on no admin_level), "ward=ward" for an electoral ward (boundary=political: Manchester's)"""
    if t.get("boundary") == "political":
        return f"ward={t.get('political_division')}"
    return f"place={t.get('place')}" if t.get("boundary") == "place" else t.get("admin_level", "0")


def same(name):
    """a station's name to compare: "Hbf" spelt out"""
    return re.sub(r"\s*\(.*?\)", "", re.sub(r"\bHbf\b\.?", "Hauptbahnhof", name))      # (and "(tief)" gone)


AUTOZUG = r"(?i)autoreisezug|autozug|motorail|güterbahnhof|freight|товарн|kravas|preču"      # (a car train's or goods' station: none to ride from)
STATION_WORDS = {"gare", "de", "du", "des", "d", "la", "le", "l", "station", "stazione", "di", "estación", "estació", "estacion",
                 "railway", "rail", "main", "s", "u", "rer", "metro", "bahnhof", "nádraží", "dworzec", "pályaudvar", "garı", "gari", "istasyonu", "tren", "жп", "гара"}


def core(name, town):
    """a station's name without its town's and the words for a station: "Paris Austerlitz" and "Gare d'Austerlitz" are
    "austerlitz", "London Euston" and "Euston" "euston" -- one station (within 600 m)"""
    ws = re.findall(r"\w+", same(name).lower())
    if len(ws) > 1 and re.fullmatch(r"\d{1,2}", ws[-1]):  # (an interchange's halves by number: Bucharest's "Piața Victoriei 1"
        ws = ws[:-1]                                      #  and "2", St Petersburg's "Технологический институт 1" and "2")
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


def city_airport(lon0, lat0, spec=None):
    """the city's airport: of data/airports.csv the busiest (passengers) within AIRPORT_KM of its middle; or the spec's
    `airport`, [iata, lon, lat] (one not in the list, or nearer than the busiest: Rotterdam's RTM, not Schiphol)"""
    if spec and "airport" in spec:                        # (null: none drawn -- Lucerne's nearest, ZRH, 45 km off)
        if not spec["airport"]:
            return None
        iata, lon, lat = spec["airport"]
        return {"iata": iata, "lon": lon, "lat": lat}
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
    a = city_airport(lon0, lat0, spec)
    regions = spec["pbf"] if isinstance(spec["pbf"], list) else [spec["pbf"]]
    paths = [citypbf.fetch(rg, PBF) for rg in regions]
    citypbf.extract(paths[0], raw, bq=bq, lon0=lon0, lat0=lat0, levels=spec.get("levels") or [9, 10, 8], monuments=mons,
                    airport=(a["iata"], float(a["lon"]), float(a["lat"])) if a else None, commuter=is_whole, out_km=OUT_KM, pad_km=PAD_KM,
                    streets=set(STREETS) | ({"tertiary"} if spec.get("tertiary") else set()),
                    core=(*(spec.get("core") or [lon0, lat0, CORE_KM]), set(LANES.split("|"))))


def _build(spec, f, np):
    qid = spec["wikidata"]; c = city_row(qid, spec)
    lon0, lat0 = float(c["lon"]), float(c["lat"])
    NAMES["lang"] = spec.get("names")
    print(f"{c['name']} ({qid}){f' coarser x{f}' if f != 1 else ''}")
    raw = lambda part: os.path.join(RAW, f"{qid}_{part}.json.gz")
    # (the city's outline: its boundary relation of that wikidata id -- or of `boundary` -- the biggest if more)
    bq = spec.get("boundary", qid)
    if spec.get("pbf") and not all(os.path.exists(raw(x)) for x in PARTS):
        from_pbf(spec, bq, lon0, lat0, raw)
    elif spec.get("pbf") and not os.path.exists(raw("lanes")) and os.path.exists(os.path.join(PBF, spec["pbf"].rsplit("/", 1)[-1] + ".osm.pbf")):
        import citypbf                                    # (a city built before the lanes: they alone, from its extract there)
        citypbf.lanes_only(os.path.join(PBF, spec["pbf"].rsplit("/", 1)[-1] + ".osm.pbf"), raw,
                           (*(spec.get("core") or [lon0, lat0, CORE_KM]), set(LANES.split("|"))))
    b = ask(raw("boundary"), Q_BOUNDARY.format(qid=bq, s=lat0 - 0.7, w=lon0 - 1, n=lat0 + 0.7, e=lon0 + 1))
    L = Local(lon0, lat0)
    rels = [(assemble(el, L), el) for el in b["elements"] if el["type"] == "relation"]
    rels = [(g, el) for g, el in rels if g is not None]
    if not rels:
        raise SystemExit(f"{qid}: no boundary relation found")
    outline, rel = max(rels, key=lambda t: t[0].area)
    if "|" in bq:                                         # (a city of two councils, "Qa|Qb": divided Nicosia's two halves --
        by_q = {}                                         #  each one's largest relation, their union)
        for g, el in rels:
            q = el.get("tags", {}).get("wikidata")
            if q not in by_q or g.area > by_q[q].area:
                by_q[q] = g
        outline = unary_union([g.buffer(1) for g in by_q.values()]).buffer(-1)
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
    if spec.get("radius"):                                # (a province-sized city cut to its town: so many km round its
        outline = outline.intersection(Point(0, 0).buffer(spec["radius"] * 1000, 64))   #  centre -- Hanoi, Saigon)
    far = [p for p in parts(outline) if p.distance(Point(0, 0)) > OUTLINE_KM * 1000]
    if far:                                               # (an exclave far out of town left out: Hamburg's Neuwerk in the
        print(f"  outline: {len(far)} part(s) {OUTLINE_KM}+ km out left out")   #  North Sea, 100 km off)
        outline = unary_union([p for p in parts(outline) if p.distance(Point(0, 0)) <= OUTLINE_KM * 1000])
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
    airport, a = None, city_airport(lon0, lat0, spec)
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

    # LANES: the old town's own streets -- the named lanes, alleys, steps and squares' ways within the core (CORE_KM of the
    # middle, or the spec's `core`, [lon, lat, km]): Florence's between the Duomo and the Uffizi, Venice's calli, the
    # Stradun; thin, under the streets, at street zoom only. Asked of Overpass apart (a part of their own: the others kept)
    ck = spec.get("core") or [lon0, lat0, CORE_KM]
    kx_, ky_ = 111.32 * math.cos(math.radians(ck[1])), 110.574
    q = Q_LANES.format(lanes=LANES, r=round(ck[2] * 1000), lat=ck[1], lon=ck[0])
    by = collections.defaultdict(list)
    try:                                                  # (Overpass busy: the map without them, asked again next build)
        lane_els = ask(raw("lanes"), q, tries=4)["elements"]
    except SystemExit as e:
        print(f"  no lanes: {e}"); lane_els = []
    for el in lane_els:
        t = el.get("tags", {})
        if el["type"] != "way" or t.get("area") == "yes" or t.get("footway") in ("sidewalk", "crossing") or not t.get("name"):
            continue
        pts = way_line(el)                                # (within the core: a part asked of a wider one cut to it)
        if len(pts) >= 2 and any(math.hypot((x - ck[0]) * kx_, (y - ck[1]) * ky_) <= ck[2] for x, y in pts):
            by[t["name"]].append(LineString(L.xy(pts)))
    rows = []
    for name, ls in by.items():
        for p in parts(merged(ls)):
            if p.geom_type == "LineString" and p.length > 0:
                arcs, _ = W.lines_at([L.ll(p.coords)], SIMPLIFY_M["lanes"], outline)
                if arcs:
                    rows.append({"name": name, "arcs": arcs})
    W.obj("lanes", "line", rows)
    n_lanes = len(rows)

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
    ways = {el["id"]: el for el in lines + routes if el["type"] == "way" and len(way_line(el)) >= 2   # (a street's
            and el.get("tags", {}).get("railway") in ("rail", "subway", "light_rail", "narrow_gauge")}  #  railway=razed: no line)
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
    if sea_ is not None and not sea_.is_empty:            # (the sea its own object, in the map's own sea colour: no darker
        W.obj("sea", "polygon", [{"arcs": W.polygon(x, SIMPLIFY_M["water"], MIN_HA["water"] * 1e4)} for x in parts(sea_)])
        wet = wet.difference(sea_)                        #  band over the base map's sea; lakes, rivers, docks on it)
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
        if el["type"] == "relation" and el.get("tags", {}).get("name") and el["tags"]["name"] not in spec.get("skip", ()):
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
        y["name"] = min(ns, key=lambda n_: (bool(re.match(r"[SU] ", n_)), len(same(n_).split()) < 2,           #  its names: Zoologischer Garten;
                                            bool(re.search(r"(?i)\b(station|bahnhof|gare|stazione)\b", n_)), len(n_)))   #  not one
        #  that says "station": "Den Haag Centraal", not HTM's "Centraal Station")
        bare = re.sub(r"\s+\d{1,2}$", "", y["name"])      # (an interchange's numbered halves joined: "Piața Victoriei",
        if bare != y["name"] and sum(re.sub(r"\s+\d{1,2}$", "", n_) == bare for n_, _ in y["all"]) > 1:   #  not "... 2")
            y["name"] = bare
    W.points("stations", [{"name": x["name"], "kind": "".join(k for k in "usr" if k in x["ks"]), "rank": x["rank"],
                            "lon": round(x["ll"][0], 5), "lat": round(x["ll"][1], 5)} for x in sorted(joined, key=lambda x: (x["rank"], x["name"]))])

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, qid + ".txt")
    text = W.text(f"{c['name']}: a city detail map (build/citymaps.py; OSM, ODbL)")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    raw_b, gz_b = len(text.encode()), len(gzip.compress(text.encode(), 9))
    print(f"  -> data/city/{qid}.txt: {raw_b / 1e3:.0f} KB, {gz_b / 1e3:.0f} KB gzipped; {len(W.arcs)} arcs, {n_streets} street lines, {n_lanes} lanes, "
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
        c = city_row(qid, spec)
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
            try:
                r = build(spec, f)
            except (Exception, SystemExit) as e:          # (one city's failure is reported, the others still built)
                print(f"{spec['wikidata']}: FAILED -- {type(e).__name__}: {e}"); r = None; break
            if r["gz"] <= BUDGET_KB * 1000 or f == COARSER[-1]:
                break
            guess = 0.85 * (r["gz"] / (BUDGET_KB * 1000)) ** 2 * f
            f = next((x for x in COARSER if x > f and x >= guess), COARSER[-1]) if f == 1 else next(x for x in COARSER if x > f)
        if r is None:
            continue
        with open(fp, "w") as fh:
            json.dump(f, fh)
        with open(os.path.join(RAW, f"{spec['wikidata']}_window.json"), "w") as fh:
            json.dump([r["w"], r["s"], r["e"], r["n"]], fh)
    write_index()


if __name__ == "__main__":
    main()
