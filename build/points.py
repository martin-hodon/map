"""STAGE 5 -- THE POINTS: cities of 100,000 people or more (70,000 in Europe: MIN_POP_BY, by the continents
full/world.topo.json gives the states and countries), and monuments with 100,000 visitors a year or more.

    .venv/bin/python build/points.py [cities] [monuments] [airports]   # -> data/cities.csv, monuments.csv, airports.csv

CITIES (layer 6): every place=city or place=town node OSM has, with its population tag -- or, where it has none (or
none that reads as a number), the latest population Wikidata gives the item the node links to (P1082, by its date).
The population shown is the URBAN one where the English Wikipedia article's infobox gives it (population_urban:
Larnaca is a town of 52,000 in a built-up area of 130,000), else the municipal count. Districts of a big city that
OSM maps as cities of their own (Istanbul's, Tokyo's wards, New York's boroughs) are left out: see districts(); and so
is any place Wikidata knows as a part of a city -- a suburb, a ward, a city district, a township: see city_parts().
A city is a point, so the file is a table: its place and its properties, no more -- the population shown and nothing
of where it came from --, grouped by country (and in GB, US, DE, IN, CN by state), the counts short (1.4M, 65k):
build/citiescsv.py writes and reads it. The monuments, the airports and the natural points (build/areas.py) are plain
tables: write_points.

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
import config, wdnames, citiescsv

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "raw")
MIN_POP = 100_000
ALSO_CITIES = {"Q3370", "Q4656", "Q27001", "Q26175", "Q145002", "Q26393", "Q200133", "Q1915327", "Q384544", "Q183111", "Q13375", "node/240088844",
               "Q167895", "Q206957", "Q210470", "Q210296", "Q188731", "Q182299", "Q207467", "Q190847",
               "node/688986898", "node/626639326", "node/29215168", "node/252217933",
               "Q4190", "Q4045", "Q33581", "Q2751", "Q155993", "Q483522", "Q178582", "Q82500", "Q29303", "Q6454", "Q157032", "Q9125", "Q7024", "Q133315", "Q183551", "Q179815", "Q209055", "Q776662", "Q204720", "Q549761", "Q180918", "Q5420", "Q3617", "Q4686", "Q205905", "Q27168", "Q190235", "Q27119", "Q27116", "Q102158", "Q194452", "Q230628", "Q235571"}   # (2026-11-27: Erdenet, 87,000, Darkhan, 75,000 -- Mongolia; Karakol, Kyrgyzstan, 84,000; Narva, 53,000; Randers, Horsens, Kolding, Vejle, 59-63,000; Lancaster, 46,000; Varaždin, 36,000; Karlovac, 42,000; Slavonski Brod, 45,000; Paphos; Canterbury, 43,000; Durham, 42,000; Hereford, 59,000; Warwick, 31,000; Torquay, 65,000; Paignton, 50,000; Calais, 67,000; Prilep, 63,000; Lugano, 67,000; Limerick, 58,000; Waterford, 60,000; Sloviansk, 40,000 by OSM now, 106,000 before the war; Siena, 54,000; Kladno, 67,000; Villach, Wels, St. Pölten -- Lower Austria's capital --, 60,000 each) (2026-11-26: Fujairah, OSM's 94,000 -- an emirate's capital; Zamora, Ávila, Segovia, Mérida -- Spanish provincial and regional capitals of 50-60,000, by OSM node: Zamora's and Ávila's items there are their towns'; Passau, 54,000)   # (2026-11-09: Kalamata, Serres, Katerini, Xanthi, Rhodes, Chania, Trikala, Alexandroupolis -- Greek cities of 45-62,000 wanted on the map)   # (under the floor, wanted all the same, by Wikidata item -- or by OSM node, where the node names none: Zadar, Pula, Martin, Trnava, Trenčín, Poprad, Chalcis, Nizwa, Karlovy Vary, Jihlava, Pisa, Fulda)
MONUMENT_NAMES = {"Q3491338": "Bohemian Switzerland National Park"}   # (the English name wanted, over Wikidata's label: České Švýcarsko)
CITY_NAMES = {"Q31026": "Yaren", "Q135617761": "Kolar", "Q956371": "Mirzapur", "Q16121944": "Jebrat El Sheikh", "Q740687": "Guéckédou", "Q16251875": "Mardin", "Q107658630": "Zamora", "Q55695431": "Ávila", "Q83069": "Sakarya", "Q200133": "Chalcis", "Q466027": "Yanbu"}   # (the English name wanted, over OSM's and Wikidata's: Chalkida; OSM's `Yanbu`` with a stray backtick)
MIN_POP_BY = {"Europe": 70_000}   # ...or this many in these continents (by the city's state's continent, else its country's)
MIN_VISITORS = 100_000
POP_STEP = 5_000
URBAN_FACTOR = 3        # a place's urban population counts when it is at most this many times its municipal one
URBAN_FACTOR_BIG = (200_000, 6)   # ...or this many, for a place of so many people or more (Paris: 2.0 million in the city, 11 in its urban area)
METRO_FACTOR = (3, 7)   # where no urban figure is given, the METRO one (population_metro) counts when at most so many times the
                        # municipal one -- the second for a place of URBAN_FACTOR_BIG[0] or more (Lisbon: 550,000 in the city,
                        # 3.35 million in its metro area; 2026-11-26) -- not in URBAN_FACTOR_BIG_NOT's countries either
METRO_KM = 60          # ...and only for a region's main city: none bigger within so many km
URBAN_FACTOR_BIG_NOT = {"CN", "TW"}   # ...but not in these countries (a county-level city's "urban" is nearly its whole county; Taoyuan's, Taipei's)
# CHINA'S CITIES (2026-11-25): OSM's and Wikidata's count for a prefecture-level city is its whole prefecture -- its
# counties and their villages too (Zhoukou 9.0 million, its city 1.6) -- and a county-level city's is its county. So
# a city of these countries shows the larger of Wikipedia's urban figure and its municipal districts' together
# (Wikidata: its P150 parts whose class is "Municipal district", each by its latest count), never more than the
# whole -- the larger of that total and every district's -- (Guangzhou's urban area, 27 million, runs on into Foshan:
# its 19); one with neither keeps the total (a county-level city: its seat and townships). The province-level
# municipalities (Beijing, Shanghai, Tianjin, Chongqing) are not cut: their districts reach far into the country.
CITY_PROPER_BY_DISTRICTS = {"CN"}
CITY_PROPER_NOT = {"Q956", "Q8686", "Q11736", "Q11725"}
# TURKEY'S CITIES (2026-11-26): OSM's count for a province's main city is often its whole province -- a metropolitan
# municipality's (Bursa 3.2 million, its city 2.0), or the province's own (Sivas 620,000, its city 370,000) -- and its
# central districts are mapped as cities of their own (Osmangazi, Yıldırım, Nilüfer). So a city of these countries
# whose count is PROVINCE_SHARE of its state's or more shows the largest of: Wikipedia's urban figure (Şanlıurfa's is
# old), its places within PARTS_KM x sqrt(its count in millions), at least PARTS_KM, together (Ankara's reach 36 km:
# Sincan), and its article's population_total -- the first and last only when under PROPER_UNDER of the count (Erzurum's "urban" is its province's;
# Sivas's, Afyonkarahisar's total is the city's), and never more than it. The places within are dropped: they are its
# districts. (proper_by_parts)
CITY_PROPER_BY_PARTS = {"TR"}
PROVINCE_SHARE = 0.6
PARTS_KM = 15
PROPER_UNDER = 0.95
# A METRO FIGURE OVER A BORDER (2026-11-26): Ciudad Juárez's (with El Paso), Matamoros's (with Brownsville), Nuevo
# Laredo's (with Laredo) -- the city keeps its own. (The US side's urban figures are the Census's: one side only.)
METRO_NOT = {"Q26590", "Q738353", "Q328846"}
# OSM places that are no towns, without a Wikidata item (hidden till 2026-11-26 by a filter's slip, view.js): a node named
# CAPITAL RIFT on Bouvet Island, Chinese development zones, Indian villages with a district's count
NOT_CITIES = {"node/14205452481", "node/6951193885", "node/6558055831", "node/7880514500", "node/13523413013", "node/367674569",
              "node/10154769796", "node/5724142117", "node/132021012", "node/132021927", "node/4476611340", "node/26487735", "node/2155586788", "node/52245055"}   # (2026-11-27: Wexford, its county's 160,000 for a town of 21,000; one place twice: a second Tenth of Ramadan, Guéckédou, Takoradi and Sekondi beside Sekondi-Takoradi, Süleymanpaşa on Tekirdağ, the Mardin node carrying the province's item on Artuklu, Kemaman district on Chukai)
# GREATER AREAS (2026-11-26): where a city's figure is its whole conurbation's, the municipalities that conurbation
# is made of are not cities of their own on the map (Guarulhos, Osasco by São Paulo; Quezon City by Manila). By the
# city's Wikidata item: (its English Wikipedia article on the area, the sections of it that list the members -- None:
# the whole page --, the area's population). A member is a place the sections link to, or one lying in such (P131:
# Buenos Aires's localities in its partidos, Tehran's cities in its counties), within GREATER_KM. A capital among them
# stays (Karaj, Alborz's), with the members in its state when that is not the core's (Fardis), and their counts come
# off the area's. Places further out stay as they were (São José dos Campos, Santos; Pretoria by Johannesburg; Toluca;
# Sete Lagoas, in Belo Horizonte's metropolitan belt). The area's other members are on the map no more.
GREATER = {
    "Q174": ("Greater São Paulo", ["Municipalities in RMSP"], 21_555_260),          # (metro, the article's infobox)
    "Q8678": ("Greater Rio de Janeiro", ["Municipalities"], 12_022_050),            # (2022)
    "Q1486": ("Greater Buenos Aires", ["List of partidos", "List of cities"], 13_985_794),   # (the city and the 24 partidos, 2022)
    "Q1489": ("Greater Mexico City", ["Mexico City", "Hidalgo", "State of Mexico"], 21_436_911),   # (2020)
    "Q65": ("Greater Los Angeles", ["Cities in Los Angeles County", "Cities in Orange County", "Cities in Riverside County",
                                    "Cities and towns in San Bernardino County", "Cities in Ventura County"], 18_316_743),   # (the CSA, 2023)
    "Q1461": ("Metro Manila", ["Local Government Units"], 14_001_751),            # (Wikidata, 2024)
    "Q42800": ("Greater Belo Horizonte", ["Cities"], 6_006_887),                   # (2020; not its metropolitan belt)
    "Q34647": ("Template:Greater Johannesburg", None, 9_167_045),                   # (Johannesburg, Ekurhuleni and the West Rand, 2016)
    "Q3616": ("Greater Tehran", None, 15_000_000),                                  # (metro, the article's infobox)
}
GREATER_KM = 150
# ...and where no article lists the members, every place within so many km, but these (2026-11-26: Tokyo's urban
# figure, 39 million, is the whole Kantō conurbation; Kawasaki, Sagamihara, Saitama, Yokohama and Chiba stay, their
# counts off its, and the rest within 50 km go -- Kawaguchi, Funabashi, Hachiōji, Fujisawa; Tsukuba, Hiratsuka stay)
# Madrid's urban figure, 6.2 million, is its whole urban area: the places within 35 km go, all of them -- Móstoles,
# Alcalá de Henares, Leganés, Getafe; Guadalajara stays)
# Barcelona's, 4.8 million, likewise: within 30 km all go -- L'Hospitalet, Badalona, Sabadell, Terrassa, Mataró;
# Vilanova i la Geltrú and Manresa stay)
# Seoul's metro figure, 26 million, is the Capital Area's: within 50 km all go but Incheon and Suwon, the two state
# capitals, their counts off it -- Goyang, Seongnam, Bucheon, Yongin; Pyeongtaek and Icheon stay. Jakarta's, 42
# million, is Jabodetabek's: within 65 km all go -- Bekasi, Tangerang, Depok, Bogor and Bogor Regency's districts;
# Rangkasbitung stays. Bangkok's, 17 million, is its metropolitan region's: Nonthaburi goes. Phoenix's urban area, 4.0
# million: within 55 km all go -- Mesa, Chandler, Scottsdale, Gilbert. Dallas's, 6.0 million, is Dallas-Fort Worth's:
# within 55 km all go but Fort Worth, its count off it -- Arlington, Plano, Irving, Frisco; Denton stays. Each the
# same, its figure kept: Monterrey (5.3 million, metro: Guadalupe, Apodaca, San Nicolás; Ramos Arizpe stays),
# Salvador (3.5: Camaçari, Lauro de Freitas), Recife (4.3, its metropolitan region: Jaboatão, Olinda, Paulista,
# Ipojuca; Vitória de Santo Antão stays), Asunción (2.5: San Lorenzo, Luque, Capiatá), Paris (11, its unité urbaine:
# Boulogne-Billancourt, Saint-Denis, Argenteuil, Versailles), Brussels (the Region's 1.25: its communes, Anderlecht,
# Schaerbeek; Leuven, Mechelen stay), Stockholm (1.6: Solna, Nacka, Huddinge), Moscow (19: Podolsk, Mytishchi,
# Zelenograd, Korolyov; Ramenskoye, Elektrostal stay), Porto Alegre (4.2, metro: Canoas, Gravataí, Novo Hamburgo),
# Toronto (5.6, urban: Mississauga, Brampton, Markham, Vaughan; Oshawa, Burlington, Hamilton stay), Mumbai (18,
# metro: Thane, Navi Mumbai, Kalyan-Dombivli, Vasai-Virar), San Francisco (4.6, metro: Oakland, Berkeley, Hayward,
# Fremont; San Jose, Sunnyvale stay). A third number is the area's figure, where the city's is its own: Kolkata (OSM's
# 4.5 million, the municipal corporation; the urban agglomeration's 14.1, 2011 census: Howrah, Bhatpara, Barasat,
# Kalyani), Manila (Metro Manila's 14; Greater Manila's 26.7, the Metro Manila article's metro figure: Antipolo,
# Bacoor, Dasmariñas, San Jose del Monte, Imus, Malolos -- three provincial capitals among them). Las Vegas (2.2,
# urban: Henderson, North Las Vegas, Paradise), Denver (2.7, urban: Aurora, Lakewood; Boulder stays), Seattle (3.5,
# the Seattle-Tacoma urban area: Bellevue, Kent, Renton; Tacoma and Everett stay, their counts off it), Vancouver
# (2.6, Metro Vancouver: Surrey, Burnaby, Richmond, Langley; Abbotsford stays).)
GREATER_ROUND = {"Q1490": (50, {"Q164234", "Q209779", "Q134635", "Q38283", "Q170616"}), "Q2807": (35, set()), "Q1492": (30, set()),
                 "Q8684": (50, {"Q20934", "Q20714"}), "Q3630": (65, set()), "Q1861": (30, set()),
                 "Q16556": (55, set()), "Q16557": (55, {"Q16558"}),
                 "Q81033": (35, set()), "Q36947": (40, set()), "Q48344": (43, set()), "Q2933": (25, set()),
                 "Q90": (30, set()), "Q239": (10, set()), "Q1754": (20, set()), "Q649": (40, set()),
                 "Q40269": (40, set()), "Q172": (40, set()), "Q1348": (46, set(), 14_112_536), "Q1156": (42, set()),
                 "Q1461": (42, set(), 26_700_000), "Q62": (46, set()),
                 "Q23768": (25, set()), "Q16554": (25, set()), "Q5083": (45, {"Q199797", "Q392599"}), "Q24639": (40, set()),
                 # (2026-11-26, the worldwide pass: every city of a million whose figure is its urban area or metro, and the
                 #  places of its country around it that figure covers; a state's capital, a famous or a big city of its own
                 #  kept, its count off the area's -- Kobe, Kyoto's Nara, Giza, Newark, Delft, Bonn, Shah Alam)
                 "Q35765": (30, {"Q193428", "Q48320", "Q169134"}), "Q11751": (30, {"Q45798", "Q201117"}), "Q55741": (23, {"Q55740"}),
                 "Q85": (30, {"Q81788"}), "Q3110": (17, {"Q723246"}), "Q4361": (27, set()), "Q60": (45, {"Q25395"}),
                 "Q10389": (30, set()), "Q33935": (11, set()), "Q34370": (14, {"Q690"}), "Q171617": (26, set()), "Q727": (16, {"Q9920"}),
                 "Q3718": (20, set()), "Q365": (20, {"Q586"}), "Q597": (17, set()), "Q1718": (10, set()), "Q490": (16, set()),
                 "Q9022": (20, set()), "Q34261": (13, set()), "Q35381": (19, {"node/3275779630"}), "Q1070": (27, {"Q11910"}),
                 "Q11462": (25, set()), "Q43463": (26, set()), "Q12439": (31, set()), "Q83189": (26, set()), "Q26600": (17, set()),
                 "Q12829733": (19, set()), "Q6106": (26, {"Q234053"}), "Q41819": (18, set()), "Q160320": (18, set()), "Q5217": (21, set()),
                 "Q3572": (12, set()), "Q3894": (20, set()), "Q5972": (21, set()), "Q16552": (22, set()), "Q11445": (20, set()),
                 "Q61092": (10, set()), "Q1022": (14, set()), "Q1794": (10, set()), "Q80484": (10, set()), "Q16553": (14, set()),
                 "Q131620": (15, set()), "Q2090": (8, set()), "Q12892": (6, set()), "Q23337": (19, set()), "Q3854": (8, set()),
                 "Q8717": (16, set()), "Q648": (13, set()), "Q1865": (40, {"Q500033", "Q182378"}), "Q36529": (12, set()),
                 "Q7903": (21, set()), "Q656": (27, set()),
                 # (and the cities of 400,000 to a million so: one or a few suburbs each -- Villeurbanne, Frederiksberg,
                 #  Metairie, Sparks; twin cities of their own kept: Valparaíso and Viña del Mar, La Paz and El Alto, Ottawa and
                 #  Gatineau, Athens and Piraeus, Khartoum's Omdurman, La Serena and Coquimbo, Kitchener and Waterloo)
                 "Q16555": (18, set()), "Q3897": (20, set()), "Q1352": (25, set()), "Q3787": (16, set()), "Q1781": (17, set()),
                 "Q191642": (17, set()), "Q18013": (23, set()), "Q3926": (11, set()), "Q456": (5, set()), "Q6346": (24, set()),
                 "Q8818": (10, set()), "Q28441": (16, set()), "Q1761": (11, set()), "Q36433": (3, set()), "Q1748": (4, set()),
                 "Q11506": (6, set()), "Q42763": (7, set()), "Q167436": (12, set()), "Q204271": (7, set()), "Q41087": (14, set()),
                 "Q170762": (7, set()), "Q1479": (6, set()), "Q34404": (10, set()), "Q40435": (13, set()), "Q273014": (14, set()),
                 "Q79848": (9, set()), "Q243766": (18, set()), "Q208669": (8, set()), "Q51111": (4, set()), "Q137271": (9, set()),
                 "Q1880": (6, set()), "Q187805": (13, set()), "Q49225": (6, set()), "Q35775": (16, set()), "Q217432": (19, set()),
                 "Q1335": (24, set()), "Q376749": (20, set()),
                 # (cities by their own count, their contiguous neighbours added: Metro Cebu, Gran Mendoza, Barranquilla's
                 #  Soledad, Barquisimeto's Cabudare, Kathmandu's Gokarneshwar (Lalitpur, Patan, kept); a place that is a part
                 #  of the city itself dropped: Ciudad Guayana's San Félix and Puerto Ordaz, Al Ahsa's Hofuf, Havana's Guanabacoa)
                 "node/259009337": (12, set(), "sum"), "Q44237": (13, set(), "sum"), "Q62823": (10, set(), "sum"),
                 "Q4709": (11, set(), "sum"), "Q3037": (7, {"Q6647"}, "sum"),
                 "Q507080": (10, set(), "own"), "Q4702167": (4, set(), "own"), "Q1563": (7, set(), "own"),
                 # (...and where the city's figure is its own: "sum" adds the suburbs' counts to it -- Gran Santo Domingo, the
                 #  Aburrá valley, Soacha, Abidjan's Anyama; "own": they are inside it already -- Algiers's communes, Sutton Coldfield)
                 "Q34820": (17, set(), "sum"), "Q48278": (12, set(), "sum"), "Q333928": (16, set(), "sum"), "Q54880": (15, set(), "sum"),
                 "Q2841": (17, set(), "sum"), "Q1515": (21, set(), "sum"), "Q3761": (16, set(), "sum"),
                 "Q2256": (14, set(), 1_600_000),   # (2026-11-27: its own 1.04 million with West Bromwich, Solihull and Dudley as the map had them; Sutton Coldfield is in it already)
                 "Q3561": (16, set(), "own"),
                 "Q10686": (14, set(), "sum"), "Q4093": (14, set(), "sum"),
                 "Q134902": (5, set(), "sum"), "Q18125": (10, set(), "sum"), "Q24826": (4, set(), "sum"), "Q1425428": (3, set(), "sum"),
                 "Q3882": (16, set())}   # (2026-11-27: Belfast with Lisburn, 12 km off; Glasgow with Paisley and East Kilbride; Stoke-on-Trent with Newcastle-under-Lyme; Manama, its urban figure, without Hamad Town, Riffa and A'ali)
STATE = re.compile(r"^(state|province) of |^region$|^first-level administrative", re.I)
# (the country and state wanted, over the map's faces', which are simplified: a city by a border can fall on the
#  wrong side -- Mexicali in California, Villa del Rosario in Venezuela -- or in the neighbour's state: 2026-11-26,
#  every city's country checked against Wikidata's P17)
CITY_PLACE = {"Q199440": ("MX", "MX-BCN"), "Q923525": ("CO", "CO-NSA"), "Q14773": ("MO", None), "Q1410": ("GI", None)}
# SPAIN'S MUNICIPALITIES (2026-11-26): OSM's count for a Spanish place is its main settlement's (the núcleo: Toledo
# 60,505, Tarragona 69,000), Wikidata's the municipality's (87,000; 144,000) -- of the same year. Here the larger.
MUNICIPAL_BY_WIKIDATA = {"ES"}
CITY_POPULATION = {"Q239": 1_250_000, "Q2088506": 104_083, "Q205905": 87_246, "Q662291": 118_632}   # (2026-11-27: Rundu, Namibia -- its 2023 census, Wikidata; OSM has 2011's 63,431; Lancaster with Morecambe, 52,660 + 34,586, both 2021 by Wikidata; Nkayi, Congo -- its 2023 count, Wikidata; OSM has 2007's 71,620) (the population wanted, over OSM's, Wikidata's and Wikipedia's: Brussels -- OSM's node is the City of Brussels, a municipality of 200,000; its article gives the Region's 1.25 million and no urban figure)
ALSO_MONUMENTS = {"Q857763": ("Caminito del Rey", "landform", -4.773, 36.916, 25, "relation/4678863")}   # (wanted all the same, though of no kind KINDS knows and with no count, by Wikidata item: its name, kind, lon, lat, Wikipedias, OSM -- a walkway in a gorge)
MIN_HERITAGE_WIKIPEDIAS = 10   # a World Heritage Site's item is kept when this many Wikipedias write about it (not each part)
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
    """a population tag as a number: '1234567', '1 234 567', '1,234,567', '1.234.567', '122’937', '~120000 (2011)' -> int | None"""
    if s is None:
        return None
    s = str(s).strip().lstrip("~≈ca. ")
    m = re.match(r"^\d{1,3}(?:[ ,.'’  ]\d{3})+(?!\d)|^\d+", s)   # (’: Swiss -- Winterthur's '122’937' was read as 122)
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


MONUMENT_COLUMNS = ["name", "lon", "lat", "kind", "level", "visitors", "visitors_year", "country", "region", "name_local", "wikidata", "osm"]
AIRPORT_COLUMNS = ["name", "lon", "lat", "iata", "icao", "city", "level", "passengers", "passengers_year", "country", "region"]


COORD_DECIMALS = 3          # a point's lon and lat: 0.001 degree, 111 m -- finer than the map's grid (config.QUANT_DEG, 278 m) needs


def write_points(rows, columns, path):
    """points (dicts with lon, lat) as a table: a header line of the columns, one point a line, an empty field for
    none (index.html pointsOf reads it back); lon and lat to COORD_DECIMALS"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow(["" if r.get(c) is None else round(r[c], COORD_DECIMALS) + 0.0 if c in ("lon", "lat") else r[c] for c in columns])


def round_pop(n):
    """a population to two significant digits, and never finer than POP_STEP: 193,456 -> 190,000; 1,215,026 ->
    1,200,000 (a count is not more accurate than that, and not of the same year everywhere)"""
    step = 10 ** max(0, len(str(int(n))) - 2)
    step = max(POP_STEP, step) if n >= POP_STEP else step   # (a town under it, a small capital -- Vatican City's 760 -- by its two digits)
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


def wd_districts(qids):
    """{qid: the population of its municipal districts together (each its latest P1082), or None} -- cached in
    raw/wd_districts.json as {qid: {district: [pop, date]}}"""
    path = os.path.join(RAW, "wd_districts.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    for i in range(0, len(need), 200):
        vals = " ".join("wd:" + q for q in need[i:i + 200])
        for b in sparql(f"""SELECT ?item ?d ?pop ?date WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P150 ?d . ?d wdt:P31 ?c .
                            ?c rdfs:label "Municipal district"@en . ?d p:P1082 ?st . ?st ps:P1082 ?pop .
                            FILTER NOT EXISTS {{ ?st wikibase:rank wikibase:DeprecatedRank }} OPTIONAL {{ ?st pq:P585 ?date }} }}"""):
            q, d = b["item"]["value"].rsplit("/", 1)[-1], b["d"]["value"].rsplit("/", 1)[-1]
            date, pop = b.get("date", {}).get("value", "")[:10], int(float(b["pop"]["value"]))
            cur = have.setdefault(q, {}).get(d)
            if cur is None or (date or "0") > (cur[1] or "0") or (date == cur[1] and pop > cur[0]):
                have[q][d] = [pop, date or None]
        for q in need[i:i + 200]:
            have.setdefault(q, {})
        json.dump(have, open(path, "w"))
        print(f"  wikidata districts {min(i + 200, len(need))}/{len(need)}", flush=True)
    return {q: sum(v[0] for v in have.get(q, {}).values()) or None for q in qids}


def wp_urban(qids):
    """{qid: the urban population its English Wikipedia article's infobox gives (population_urban), or None}"""
    def read(text):
        m = re.search(r"\|\s*population_urban\s*=([^\n]*)", text)
        return infobox_number(m.group(1)) if m else None
    return wp_infobox(qids, "wp_urban2.json", read, "urban populations")   # (2026-11-22: refetched; wp_urban.json had Paris and Lyon without one)


def national_capitals(rows, where):
    """a country with more than one capital by OSM's tags keeps those Wikidata names its capitals (P36): Mali's regional
    towns carry admin_level=2 (2026-11-26: nine capitals); Bolivia's La Paz and Sucre, South Africa's three stay.
    The others become their state's capital. (Cached in raw/wd_capitals.json: {ISO code: [items]}.)"""
    path = os.path.join(RAW, "wd_capitals.json")
    if not os.path.exists(path):
        have = collections.defaultdict(list)
        for b in sparql("""SELECT ?iso ?cap WHERE { ?c wdt:P297 ?iso . ?c p:P36 ?st . ?st ps:P36 ?cap .
                                   FILTER NOT EXISTS { ?st pq:P582 ?end } FILTER NOT EXISTS { ?st wikibase:rank wikibase:DeprecatedRank } }"""):
            have[b["iso"]["value"]].append(b["cap"]["value"].rsplit("/", 1)[-1])
        json.dump(have, open(path, "w"))
    wd = json.load(open(path))
    by = collections.defaultdict(list)
    for r in rows:
        if r["capital"] == "country":
            by[r["country"]].append(r)
    for cc, rs in by.items():
        named = [r for r in rs if r["wikidata"] in wd.get(cc, [])]
        if len(rs) > 1 and named:
            for r in rs:
                if r not in named and r["wikidata"]:   # (one without an item is not judged: Sri Jayewardenepura Kotte's node)
                    r["capital"] = "state"
                    print(f"  not a capital of {cc} (Wikidata): {r['name']}")
    # a country with none: its Wikidata capital -- a row of another code (Jerusalem, placed in the West Bank by its
    # node) made this one's, else the item itself added, from Wikidata (Vatican City, Yaren, Ngerulmud, Marigot,
    # Philipsburg: no city node of OSM, or one tagged a lesser capital and too small)
    T = json.load(open(os.path.join(ROOT, "full/world.topo.json")))["objects"]
    want = sorted(g["properties"]["iso"] for g in T["countries"]["geometries"] if g["properties"].get("subtype") == "country"
                  and g["properties"].get("iso") and not by.get(g["properties"]["iso"]) and wd.get(g["properties"]["iso"]))
    by_q = {r["wikidata"]: r for r in rows if r["wikidata"]}
    add = []
    for cc in want:
        for q in wd[cc]:
            if q in by_q:
                by_q[q]["country"], by_q[q]["capital"] = cc, "country"; print(f"  the capital of {cc}: {by_q[q]['name']}")
            else:
                add.append((cc, q))
    if not add:
        return
    path = os.path.join(RAW, "wd_capital_items.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = [q for _, q in add if q not in have]
    if need:
        vals = " ".join("wd:" + q for q in need)
        for b in sparql(f"""SELECT ?item ?name ?coord (MAX(?p) AS ?pop) WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P625 ?coord .
                            ?item rdfs:label ?name . FILTER(LANG(?name) = "en") OPTIONAL {{ ?item wdt:P1082 ?p }} }} GROUP BY ?item ?name ?coord"""):
            q = b["item"]["value"].rsplit("/", 1)[-1]
            lon, lat = map(float, re.findall(r"-?[\d.]+", b["coord"]["value"])[:2])
            have.setdefault(q, {"name": b["name"]["value"], "lon": lon, "lat": lat, "population": int(float(b.get("pop", {}).get("value", 0)))})
        json.dump(have, open(path, "w"))
    for cc, q in add:
        h = have.get(q)
        if not h:
            continue
        _, rc = where(np.array([h["lon"]]), np.array([h["lat"]]))
        rows.append({"name": CITY_NAMES.get(q) or h["name"], "lon": round(h["lon"], 3), "lat": round(h["lat"], 3), "population": h["population"], "population_municipal": h["population"],
                     "population_source": "wikidata", "population_year": None, "place": "town", "capital": "country", "country": cc,
                     "region": rc[0] if str(rc[0] or "").startswith(cc + "-") else None, "name_local": None, "wikidata": q, "osm": None})
        print(f"  the capital of {cc}, from Wikidata: {h['name']}")
    rows.sort(key=lambda r: -r["population"])


def wp_links(title, sections):
    """{qid: title} of the articles a Wikipedia page links to -- in the named sections alone (their own text, up to the
    next heading of any level), or anywhere on it (cached in raw/wp_greater.json by title and sections)"""
    path = os.path.join(RAW, "wp_greater.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    key = "|".join([title, *(sections or [])])
    if key in have:
        return have[key]
    def get(params):
        for attempt in range(6):
            r = requests.get("https://en.wikipedia.org/w/api.php", headers={"User-Agent": UA["User-Agent"]}, timeout=120,
                             params={**params, "format": "json", "formatversion": "2"})
            if r.status_code == 200:
                return r.json()
            print("wikipedia", r.status_code, "- retrying", flush=True)
            time.sleep(20 * (attempt + 1))
        raise SystemExit("wikipedia failed")
    text = get({"action": "parse", "page": title, "prop": "wikitext", "redirects": "1"})["parse"]["wikitext"]
    if sections:
        bare = lambda h: re.sub(r"'{2,}|<[^>]+>", "", h).strip()   # (a heading without its italics: List of ''partidos'')
        parts = re.split(r"^(=+)[ \t]*(.*?)[ \t]*\1[ \t]*$", text, flags=re.M)   # (text, =s, heading, text, ...)
        want = {bare(h) for h in sections}
        text = "\n".join(parts[i + 1] for i in range(2, len(parts) - 1, 3) if bare(parts[i]) in want)
    links = sorted({re.split(r"[|#]", m)[0].strip() for m in re.findall(r"\[\[([^\[\]]+)\]\]", text)} - {""})
    links = [t for t in links if ":" not in t]
    out = {}
    for i in range(0, len(links), 50):
        res = get({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": "1", "titles": "|".join(links[i:i + 50])})
        for page in res["query"]["pages"]:
            if page.get("pageprops", {}).get("wikibase_item"):
                out[page["pageprops"]["wikibase_item"]] = page["title"]
        time.sleep(0.5)
    have[key] = out
    json.dump(have, open(path, "w"), ensure_ascii=False)
    print(f"  wikipedia {title}: {len(out)} members", flush=True)
    return out


def wd_located_in(qids):
    """{qid: [the items it lies in (P131)]} (cached in raw/wd_located_in.json)"""
    path = os.path.join(RAW, "wd_located_in.json")
    have = json.load(open(path)) if os.path.exists(path) else {}
    need = sorted({q for q in qids if q and re.match(r"^Q\d+$", q) and q not in have})
    for i in range(0, len(need), 200):
        vals = " ".join("wd:" + q for q in need[i:i + 200])
        for b in sparql(f"SELECT ?item ?in WHERE {{ VALUES ?item {{ {vals} }} ?item wdt:P131 ?in }}"):
            have.setdefault(b["item"]["value"].rsplit("/", 1)[-1], []).append(b["in"]["value"].rsplit("/", 1)[-1])
        for q in need[i:i + 200]:
            have.setdefault(q, [])
        json.dump(have, open(path, "w"))
    return {q: have.get(q, []) for q in qids}


def greater(rows):
    """GREATER: the core city gets its area's figure, and the area's members go (rows sorted biggest first)"""
    def km(a, b):
        y = np.radians(a["lat"])
        return 2 * 6371 * np.arcsin(np.sqrt(np.sin((np.radians(b["lat"]) - y) / 2) ** 2 + np.cos(y) * np.cos(np.radians(b["lat"]))
                                            * np.sin(np.radians(b["lon"] - a["lon"]) / 2) ** 2))
    drop = set()
    for r in rows:
        if r["wikidata"] not in GREATER:
            continue
        title, sections, pop = GREATER[r["wikidata"]]
        mem = wp_links(title, sections)
        cl = wd_classes(list(mem))                     # (not a state the page names: Tehran province, Hidalgo)
        mem = {q: t for q, t in mem.items() if q != r["wikidata"] and not any(STATE.search(c) for c in cl.get(q) or [])}
        bare = lambda t: re.sub(r"\s*(,.*|\(.*\)|\bmunicipality|\bpartido|\bcounty)$", "", t, flags=re.I).strip()
        names = {bare(t) for t in mem.values()}
        near = [o for o in rows if o is not r and o["country"] == r["country"] and km(r, o) < GREATER_KM]
        up1 = wd_located_in([o["wikidata"] for o in near if o["wikidata"] not in mem])
        up2 = wd_located_in(sorted({q for v in up1.values() for q in v}))
        en = wdnames.english(sorted(up2))
        ucl = wd_classes(sorted({q for v in up2.values() for q in v} | set(up2)))
        def same(n):   # (a name as the page has it, or its first words: Tultitlán, Tultitlán de Mariano Escobedo)
            return n and n != bare(r["name"]) and (n in names or any(m.startswith(n + " de ") for m in names))
        named = lambda q: not any(STATE.search(c) for c in ucl.get(q) or []) and same(bare(en.get(q) or ""))
        def member(o):   # (the place, what it lies in, what that lies in -- by item, or by the English name: Tultitlán)
            if o["wikidata"] in mem or ((not o["wikidata"] or km(r, o) < GREATER_KM / 3) and same(bare(o["name"]))):   # (by its name: Cuautitlán, Chicoloapan)
                return True
            ups = [q for p in up1.get(o["wikidata"], []) for q in [p, *up2.get(p, [])]]
            return any(q in mem or named(q) for q in ups)
        inside = [o for o in near if member(o)]
        caps = [o for o in inside if o["capital"]]
        keep = [o for o in inside if o["capital"] or any(c["region"] == o["region"] != r["region"] for c in caps)]
        gone = [o for o in inside if o not in keep]
        drop |= {id(o) for o in gone}
        r["population"] = pop - sum(o["population_municipal"] for o in keep)
        r["population_source"], r["population_year"] = "greater", None
        print(f'{r["name"]}: {title} {r["population"]:,}; {len(gone)} of its places dropped ({", ".join(o["name"] for o in gone)})'
              + (f'; kept: {", ".join(o["name"] for o in keep)}' if keep else ""), flush=True)
    for r in rows:
        g = r["wikidata"] if r["wikidata"] in GREATER_ROUND else r["osm"]   # (by its OSM node, a city without an item: Cebu City)
        if g not in GREATER_ROUND:
            continue
        reach, kept, *pop = GREATER_ROUND[g]
        how = pop[0] if pop else "area"
        if isinstance(how, int):                       # (the area's figure, where the city's own is less: Kolkata's)
            r["population"] = how
        if id(r) in drop:
            continue
        near = [o for o in rows if o is not r and o["country"] == r["country"] and km(r, o) < reach and id(o) not in drop]
        keep = [o for o in near if o["wikidata"] in kept or o["osm"] in kept]
        gone = [o for o in near if o not in keep]
        drop |= {id(o) for o in gone}
        if how == "sum":                               # (the city's own count, its suburbs' added: Medellín's Bello, Itagüí)
            r["population"] += sum(o["population_municipal"] for o in gone)
        elif how != "own":                             # (own: the dropped are inside the city's own count -- Birmingham's Sutton Coldfield)
            r["population"] -= sum(o["population_municipal"] for o in keep)
        r["population_source"], r["population_year"] = "greater", None
        print(f'{r["name"]}: {r["population"]:,}; {len(gone)} places within {reach} km dropped ({", ".join(o["name"] for o in gone[:12])}...); kept: {", ".join(o["name"] for o in keep)}', flush=True)
    return sorted([r for r in rows if id(r) not in drop], key=lambda r: -r["population"])


def wp_total(qids):
    """{qid: the population its English Wikipedia article's infobox gives (population_total), or None}"""
    def read(text):
        m = re.search(r"\|\s*population_total\s*=([^\n]*)", text)
        return infobox_number(m.group(1)) if m else None
    return wp_infobox(qids, "wp_total.json", read, "total populations")


def proper_by_parts(seen, rpop, urban):
    """CITY_PROPER_BY_PARTS: a city counted as its province gets its city proper, and its districts (the places within
    PARTS_KM of it) go -- seen ({key: row}) is changed in place"""
    vs = [r for r in seen.values() if r["_cc"] in CITY_PROPER_BY_PARTS]
    big = [r for r in vs if rpop.get(r["_rg"]) and r["population_municipal"] >= PROVINCE_SHARE * rpop[r["_rg"]]]
    total = wp_total([r["wikidata"] for r in big])
    gone, done = set(), []
    for r in sorted(big, key=lambda r: -r["population_municipal"]):
        if id(r) in gone:
            continue
        m, b = r["population_municipal"], np.radians(r["lat"])
        def km(o):
            return 2 * 6371 * np.arcsin(np.sqrt(np.sin((np.radians(o["lat"]) - b) / 2) ** 2 + np.cos(b) * np.cos(np.radians(o["lat"]))
                                                * np.sin((np.radians(o["lon"] - r["lon"])) / 2) ** 2))
        reach = PARTS_KM * max(1, (m / 1e6) ** 0.5)
        parts = [o for o in vs if o is not r and id(o) not in gone and o["population_municipal"] < m and not o["capital"] and km(o) < reach]
        under = lambda v: v if v and v < PROPER_UNDER * m else 0
        proper = min(m, max(under(urban.get(r["wikidata"])), sum(o["population_municipal"] for o in parts), under(total.get(r["wikidata"]))))
        if proper:
            r["population"] = r["population_municipal"] = proper
            r["population_source"], r["population_year"] = "city-proper", None
            gone |= {id(o) for o in parts}
            done.append(f'{r["name"]} {m:,} -> {proper:,}' + (f' ({len(parts)} parts)' if parts else ''))
    for k in [k for k, o in seen.items() if id(o) in gone]:
        del seen[k]
    print(len(done), "cities counted as their province cut to the city:", "; ".join(done[:12]), "...;", len(gone), "of their districts dropped", flush=True)


def wp_metro(qids):
    """{qid: the metro population its English Wikipedia article's infobox gives (population_metro), or None}"""
    def read(text):
        m = re.search(r"\|\s*population_metro\s*=([^\n]*)", text)
        return infobox_number(m.group(1)) if m else None
    return wp_infobox(qids, "wp_metro.json", read, "metro populations")


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


# A CHINESE CITY'S TOWNS (2026-11-26): a "town of China" (a township-level town) lying in a city's municipal district,
# or straight in a city on the map (Dongguan and Zhongshan have no districts: their towns are their parts), is counted
# in that city's people already -- Humen, Chang'an, Shishan, Dali were cities of their own in the Pearl River Delta. A
# town in a county the map does not show stays (a county seat on its own). By Wikidata's P131 and its classes.
TOWN = "town of China"


def city_towns(rows):
    """the rows without the Chinese towns that are a mapped city's parts (TOWN)"""
    classes = wd_classes([r["wikidata"] for r in rows])
    towns = [r for r in rows if not r["capital"] and TOWN in (classes.get(r["wikidata"]) or [])]
    up = wd_located_in([r["wikidata"] for r in towns])
    pc = wd_classes(sorted({q for v in up.values() for q in v}))
    mapped = {r["wikidata"] for r in rows if r["wikidata"]}
    drop = {id(r) for r in towns if any(p in mapped or any("district" in c.lower() for c in pc.get(p) or []) for p in up.get(r["wikidata"], []))}
    print(len(drop), "of", len(towns), "Chinese towns dropped as a city's parts:", ", ".join(r["name"] for r in towns if id(r) in drop)[:300], "...", flush=True)
    return [r for r in rows if id(r) not in drop]


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
        if pop is None or (pop < min(MIN_POP, *MIN_POP_BY.values()) / URBAN_FACTOR and cap != "country") or not (t.get("name") or t.get("name:en") or t.get("int_name")):
            continue
        r = {"name": t.get("name") or t.get("name:en") or t.get("int_name"), "_tags": t, "population": pop, "population_municipal": pop, "population_source": src,
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
    seen = {k: r for k, r in seen.items() if r["osm"] not in NOT_CITIES}
    vs = list(seen.values())
    for r, c, g in zip(vs, *where(np.array([r["lon"] for r in vs]), np.array([r["lat"] for r in vs]))):
        r["_cc"], r["_rg"] = c, g
        r["_floor"] = 0 if r["wikidata"] in ALSO_CITIES or r["osm"] in ALSO_CITIES else MIN_POP_BY.get(cont.get(g) or cont.get(c), MIN_POP)
    mw = wd_population([r["wikidata"] for r in vs if r["_cc"] in MUNICIPAL_BY_WIKIDATA and r["wikidata"]])
    for r in vs:
        w = mw.get(r["wikidata"]) if r["_cc"] in MUNICIPAL_BY_WIKIDATA else None
        if w and w[0] > r["population"]:
            r["population"] = r["population_municipal"] = w[0]
            r["population_source"], r["population_year"] = "wikidata", w[1]
    seen = {k: r for k, r in seen.items() if r["population"] >= r["_floor"] / URBAN_FACTOR or r["capital"] == "country"}
    urban = wp_urban([r["wikidata"] for r in seen.values()])
    metro = wp_metro([r["wikidata"] for r in seen.values() if not urban.get(r["wikidata"]) and r["population_municipal"] >= 50_000
                      and r["_cc"] not in CITY_PROPER_BY_DISTRICTS | URBAN_FACTOR_BIG_NOT])
    # (a metro figure is a region's: Dallas-Fort Worth's, Rhine-Neckar's -- it goes to the region's MAIN city alone, so
    #  not to a place with a bigger one within METRO_KM: Fort Worth, Mannheim's neighbours, Secunderabad, Gdynia)
    vs = list(seen.values())
    lon, lat, mun = (np.radians([r["lon"] for r in vs]), np.radians([r["lat"] for r in vs]), np.array([r["population_municipal"] for r in vs]))
    def main_city(r):
        a, b = np.radians(r["lon"]), np.radians(r["lat"])
        d = 2 * 6371 * np.arcsin(np.sqrt(np.sin((lat - b) / 2) ** 2 + np.cos(b) * np.cos(lat) * np.sin((lon - a) / 2) ** 2))
        return not np.any((d < METRO_KM) & (mun > r["population_municipal"]))
    by_q = {r["wikidata"]: r for r in vs}
    metro = {q: v for q, v in metro.items() if v and main_city(by_q[q]) and q not in METRO_NOT}
    proper_by_parts(seen, {g["properties"]["iso"]: g["properties"].get("population") for g in T["regions"]["geometries"] if "iso" in g["properties"]}, urban)
    dsum = wd_districts([r["wikidata"] for r in seen.values() if r["_cc"] in CITY_PROPER_BY_DISTRICTS])
    for r in seen.values():                                    # the urban population where Wikipedia gives one that is
        u = urban.get(r["wikidata"])                           # bigger (and not absurdly: a district's article can carry
        m = r["population_municipal"]                          # the whole city's)
        cc, _ = r.pop("_cc", None), r.pop("_rg", None)
        if r["population_source"] == "city-proper":            # (proper_by_parts's)
            continue
        if cc in CITY_PROPER_BY_DISTRICTS and r["wikidata"] not in CITY_PROPER_NOT:
            d = dsum.get(r["wikidata"]) or 0
            proper, whole = max(u or 0, d), max(m, d)    # (the whole: OSM's tag can be an old count -- Guangzhou's 14 million)
            if proper:
                r["population"], r["population_source"], r["population_year"] = min(proper, whole), "city-proper", None
            continue
        big = m >= URBAN_FACTOR_BIG[0] and cc not in URBAN_FACTOR_BIG_NOT
        if u and m < u <= (URBAN_FACTOR_BIG[1] if big else URBAN_FACTOR) * m:
            r["population"], r["population_source"], r["population_year"] = u, "wikipedia-urban", None
        elif not u and cc not in URBAN_FACTOR_BIG_NOT and (mt := metro.get(r["wikidata"])) and m < mt <= METRO_FACTOR[big] * m:
            r["population"], r["population_source"], r["population_year"] = mt, "wikipedia-metro", None
        if r["wikidata"] in CITY_POPULATION:
            r["population"], r["population_source"], r["population_year"] = CITY_POPULATION[r["wikidata"]], "set", None
    rows = sorted([r for r in seen.values() if r.pop("_floor") <= r["population"] or r["capital"] == "country"], key=lambda r: -r["population"])
    cc, rc = where(np.array([r["lon"] for r in rows]), np.array([r["lat"] for r in rows]))
    # the names: English (OSM's name:en, else Wikidata's English label, else its name), and the one in its country's
    # official language, where that is another
    en = wdnames.english([r["wikidata"] for r in rows])
    for r, c, g in zip(rows, cc, rc):
        t = r.pop("_tags")
        local = wdnames.local_name(t, c)
        r["name"] = CITY_NAMES.get(r["wikidata"]) or t.get("name:en") or en.get(r["wikidata"]) or local or t.get("name")
        r["name_local"] = local if local and local != r["name"] else None
        r["country"], r["region"] = CITY_PLACE.get(r["wikidata"], (c, g))
    rows = city_towns(city_parts(districts(rows)))
    national_capitals(rows, where)
    rows = greater(rows)
    by = collections.Counter(r["population_source"] for r in rows)
    for r in rows:
        r["population"] = round_pop(r["population"])
    path = citiescsv.PATH
    citiescsv.write([wdnames.drop_unread(dict(r)) for r in rows], path, coord=lambda v: round(v, COORD_DECIMALS) + 0.0)   # (grouped by country, and state: citiescsv.py)
    # (where each figure came from -- osm, wikidata, wikipedia-urban, wikipedia-metro, city-proper, set -- and the
    #  municipal count it replaced: build/popcheck.py --spill reads it)
    json.dump({r["osm"] or r["wikidata"]: [r["population_source"], r["population_municipal"]] for r in rows}, open(os.path.join(RAW, "city_sources.json"), "w"))
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
    cities = citiescsv.read()
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
    # ...and the ones wanted all the same (ALSO_MONUMENTS)
    for q, (name, kind, lon, lat, n, osm) in ALSO_MONUMENTS.items():
        if q not in have and q not in fame:
            feats.append((lon, lat, {"name": name, "kind": kind, "wikipedias": n, "wikidata": q, "osm": osm}))
    for _, _, p in feats:
        p["name"] = MONUMENT_NAMES.get(p["wikidata"], p["name"])
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
    write_points([wdnames.drop_unread(dict(r)) for r in out], MONUMENT_COLUMNS, path)
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
