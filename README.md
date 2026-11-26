# World layers at 1 km

World map data built from public sources, OpenStreetMap first, at about **1 km of detail**. Lines are simplified on
the globe to 0.5 km and stored on a 1/400° grid. Everything is longitude/latitude (WGS 84) with no projection
applied, so any projection can draw it. `index.html` shows it in nine projections (the globe, orthographic, by default).

| # | layer | file · object | what |
|---|---|---|---|
| 1 | geographical | `full/world.topo.json` · `continents`, `islands`, `coastline`, `lakes` | the five continents (`name`: Eurasia, Americas, Africa, Antarctica, Australia -- every landmass of 5 million km² or more) and every other landmass of 1 km² or more as an island (named, `name`, `rank`, `wikidata`, `label`…, where layer 7 has it as one island: its row is here, not there), the coast as lines, lakes of 45 km² or more (Ammersee and up), with the lagoons and limans of that size that OSM's coast cuts off at their mouth (`type` lagoon: the Dniester Liman, the Tuzly lagoons) |
| 2 | national borders | `full/world.topo.json` · `countries`, `country_borders` | countries and dependencies as polygons, which reuse the coast, with `population` (Wikidata's latest, by ISO 3166-1 code, two significant digits), `area_km2`, `density`, `language` (`language_code`), `color` (0-6, no two neighbours alike), `label` (a point well inside: where its name is written) and `continent` (the continent area of layer 7 its label lies in, else the nearest); the land borders as lines (`a`, `b`, `disputed`) |
| 3 | subnational | `full/world.topo.json` · `regions`, `region_borders` | states / provinces (ISO 3166-2; England has no such division in Overture: its nine regions, `STATE_PARTS` in `build/config.py`, put together from its counties, under codes of our own, `GB-ENG-LD`, and found as one, England, in the search) of the federations, of the countries whose divisions are big enough to see (8,500 km² on average -- Denmark's and Greece's are about the smallest -- two or more), of every country the size of North Macedonia (25,700 km²) or bigger whose divisions are 2,000 km² or more on average (Romania's 42 counties, Ireland's 26, Albania's 12; not Azerbaijan's 80 districts, Latvia's 42, Taiwan's 22, North Macedonia's 71 municipalities, Uganda's 135 districts), and of those of 40 million people or more (`build/config.py`; `build/topology.py` picks them), with `population` (by ISO 3166-2 code), `area_km2`, `density`, `language`, `label`, `continent` (its own: Russia's European oblasts are in Europe) |
| 4 | rivers | `full/rivers.topo.json` · `rivers` | each river that is 50 m wide somewhere, from its source down to its end, as one line (or more at forks), 50 km or longer, big or known to Wikipedia: name (English), Wikidata id, width (median and max), `river` (its id), `river_km`, `wikipedias` |
| 5 | monuments | `data/monuments.csv` | castles, palaces, cathedrals, temples, ruins, monuments, bridges, dams, national parks, waterfalls… with 100,000+ visitors a year, or well known (written about in enough Wikipedias -- 15+ for a castle, 12+ a bridge, 10+ a dam or a World Heritage Site, 15+ a national park (2026-11-23: was 25, which left out Slovak Karst, the Fatras, Black Forest), 40+ a church: `build/fetch_points.py` FAMOUS; not a name that is only a number, the Valley of the Kings' KV1 to KV63, nor a city's own item -- Wikidata's Athens is an archaeological site too -- nor a place twice: "Pompeii" and "archaeological excavations of Pompeii" are one, the village "Devín" goes for "Devín Castle"), one a line under a header: `name`, `lon`, `lat`, `kind`, `level` (1: 2 million visitors a year or more, 2: 500,000, 3: fewer -- one without a count by its Wikipedias: 80+, 40+, fewer), `visitors`, `visitors_year`, `country`, `region`, `name_local`, `wikidata`, `osm` |
| 6 | cities | `data/cities.csv` | cities of 100,000+ people (70,000+ in Europe: by the state's continent, so European Russia and Istanbul too), every capital and a few wanted all the same (`ALSO_CITIES` in `build/points.py`: Greek towns of 45-62,000; Zamora, Ávila, Segovia, Mérida; Passau), one a line under a header: `name`, `lon`, `lat`, `population` (the urban one where Wikipedia gives it -- at most 3 times the city's own, 6 for a city of 200,000+ outside China and Taiwan; where it gives none, its METRO one (population_metro), at most 3 times, 8 for a city of 200,000+: Lisbon's 3.35 million -- `METRO_FACTOR`, 2026-11-26; in China the city proper, the larger of that urban figure and its municipal districts' together, never more than its prefecture -- OSM's and Wikidata's count for a prefecture-level city is the whole prefecture, Zhoukou's 9 million for a city of 1.6: `CITY_PROPER_BY_DISTRICTS`; in Turkey a city counted as its whole province (Bursa 3.2 million, Sivas 620,000) its city proper, the largest of its urban figure, its central districts together and its article's total, the districts dropped -- `CITY_PROPER_BY_PARTS`, 2026-11-26; a metro figure reaching over a border not used -- Ciudad Juárez's with El Paso, Matamoros's, Nuevo Laredo's: `METRO_NOT`; nine GREATER areas -- São Paulo, Rio de Janeiro, Buenos Aires, Mexico City, Los Angeles, Metro Manila, Belo Horizonte, Johannesburg with Ekurhuleni and the West Rand, Tehran -- the core with the whole area's figure and the member municipalities its Wikipedia article lists (or the places lying in them) dropped, a capital among them kept (Karaj), places further out kept (São José dos Campos, Santos, Pretoria, Toluca): `GREATER`; Tokyo the same by distance, every place within 50 km dropped but Yokohama, Kawasaki, Saitama, Chiba and Sagamihara, whose counts come off its 39 million, and Madrid, every place within 35 km dropped (Móstoles, Alcalá de Henares; Guadalajara stays), and Barcelona, within 30 km (L'Hospitalet, Sabadell, Terrassa, Mataró; Manresa stays); Seoul within 50 km but Incheon and Suwon, Jakarta within 65 km (Bekasi, Tangerang, Depok, Bogor), Bangkok's Nonthaburi, Phoenix within 55 km (Mesa, Chandler, Scottsdale), Dallas within 55 km but Fort Worth (Arlington, Plano, Frisco), and so Monterrey, Salvador, Recife, Asunción, Paris (Versailles too), Brussels (its Region's communes), Stockholm and Moscow, Porto Alegre, Toronto, Mumbai, San Francisco, Kolkata (with its urban agglomeration's 14.1 million) and Manila again (Greater Manila, 26.7 million), Las Vegas, Denver, Seattle (Tacoma and Everett kept) and Vancouver: `GREATER_ROUND`; in Spain the municipality's count from Wikidata where it is larger -- OSM's is the main settlement's, Toledo's 60,505 for 87,000: `MUNICIPAL_BY_WIKIDATA`; Brussels the Region's, `CITY_POPULATION`; a city by a border on its own country's side, `CITY_PLACE` (Mexicali) -- two significant digits). `build/popcheck.py` checks the populations against one another: a country's states together against it, a state's or a country's cities together against it, `place` (city, town), `capital` (country, state), `country`, `region` (state), `name_local`, `wikidata`, `osm` -- without the districts of a bigger city (Istanbul's, Tokyo's wards, New York's boroughs, China's urban districts) and without China's towns that lie in a mapped city or its districts (Humen, Chang'an, Shishan in the Pearl River Delta: `city_towns`, 2026-11-26) |
| 7 | areas | `full/world.topo.json` · `areas` | the named parts of the world without borders of their own: oceans, seas, gulfs, bays, straits, sounds, fjords; mountain ranges, plateaus, deserts, plains, basins, peninsulas, island groups, continents — made of the map's own coast and lines across (below); a single island is a named row of `islands` (layer 1) |
| 8 | natural points | `data/natural_points.csv` | peaks (with elevation), capes, waterfalls, passes, depressions, the poles, one a line under a header: `name`, `lon`, `lat`, `kind`, `elevation_m`, `rank` (Natural Earth's: shown from what zoom), `name_en`, `wikidata` |
| 9 | airports | `data/airports.csv` | airports with scheduled flights to 3+ airports abroad (large ones: 2+), one a line under a header: `name`, `lon`, `lat`, `iata`, `icao`, `city`, `level` (1: 20 million passengers a year or more, 2: 5 million, 3: fewer or no count), `passengers`, `passengers_year`, `country`, `region` |
| 13 | biogeographic | `full/bio.topo.json` · `realms`, `biomes`, `ecoregions` | the land cut into the 847 terrestrial ecoregions (RESOLVE 2017), and those grouped into 15 biomes (with Rock and Ice) and 8 biogeographic realms: `id` (`PA`… a realm, `B0`–`B14` a biome, `E` + RESOLVE's number an ecoregion), `name`, `realm`, `biome`, `color` (RESOLVE's), `nnh`, `area_km2`, `label` -- made of the map's own coast (below) |
| 14 | historical borders | `full/history.topo.json` · `regions`, `periods` | the states, empires, dependencies (and, before them, peoples and cultures) from 3000 BC to 2019 -- from 1886 every day (CShapes 2.0), before as mapped for 3000 BC, 2000 BC … 1815, 1878, 1880 (historical-basemaps), as REGIONS of the land and their owners through time: `regions` one polygon each -- `id`, `name`, `admin`, `country`, `held` (`from:state` …), `area_km2`, `label`; `periods` one row per country-period (no geometry) -- `id` (`state:from`), `state`, `name`, `from`, `to` (days, both inclusive; years astronomical, `-0699` is 700 BC), `source`, `precision` (1 approximate, 2 partly undefined, 3 fixed by law), `status`, `owner`, `capital`, `cap`, `gwcode`, `area_km2`, `label` -- made of the map's own coast (below) |
| 15 | historical events | `data/events.csv` | battles, sieges, peace treaties and treaties, assassinations, massacres, coups, revolutions, rebellions, terror attacks, earthquakes, eruptions that enough Wikipedias write about (10+ for a battle, 8+ a peace treaty, 15+ a massacre: `build/events.py` KINDS), one a line under a header: `name`, `lon`, `lat`, `date` (cut to its precision, years astronomical), `precision` (day … century), `calendar` (julian, as historians cite a date before 1582), `kind`, `part_of` (its war or campaign), `wikipedias`, `place` (own coordinates, or its location's), `wikidata` |
| 16 | tectonic plates | `data/plates.json` | Peter Bird's PB2002 model: 52 plates (`code`, `name`, `area_km2`, `label`, outline) and their boundaries in 1,688 runs, each of one class -- spreading ridge, continental rift, transform fault, collision zone, subduction zone (with the upper plate's side, from Bird's `A\B` / `A/B`) -- and the plates' relative speed there (opening, closing, sliding, mm a year), `build/plates.py`; read once, drawn on the main thread (js/plates.js) |
| 13 | first-class roads | `full/roads.topo.json` · `roads` | what is one class below a motorway (OSM's trunk, without slip roads; beside a motorway they are that motorway; networks of 25 km+), one line per road, thinner and yellow under the motorways' orange: `ref`, `class`, `tier` (1-3: from 4x, 7x, 11x); below |
| 10–12 | main lines | `full/transport.topo.json` · `motorways`, `railways`, `pipelines` | motorways and trunk roads signed 100 km/h+ (networks of 20 km+), main-line and high-speed railways (30 km+), oil and gas pipelines that are not distribution lines (networks of 100 km+, without the fields' and terminals' short loops and dead ends), one line per road or railway (its carriageways and tracks collapsed), meeting at its junctions exactly: `ref`, `class`, `highspeed`, `network`, `network_km`, `tier` (pipelines: `name`, `substance`, `operator`) (1-3: from what zoom it is drawn) |
| 17 | city detail maps | `data/city/<wikidata>.txt`, `data/city/index.csv` | a few cities at street level, read only when the map is zoomed in on one: main streets and their bridges, districts, parks and woods, water, monuments' areas, S-Bahn, U-Bahn and main railways in their lines' colours, stations, the airport -- within the city's boundary (City detail maps, below) |
| 18 | time zones | `full/timezones.topo.json` · `zones`, `zone_borders` | the IANA time zones over land and sea (timezone-boundary-builder with the oceans: a zone's waters, the open sea in 15° strips), one polygon each: `tzid` (Europe/Berlin; at sea Etc/GMT+5, POSIX's sign), `utc` (its offset in minutes), `dst` (its daylight-saving offset, where it has one), `abbr`, `dst_abbr`, `area_km2`, `label`; the borders between them (`same`: the same time on both sides all year) -- coloured by the offset (Time zones, below) |
| 5a | parks' areas | `full/parks.topo.json` · `parks` | the outlines of layer 5's national parks and protected areas, from OSM: `name`, `wikidata` (the monument's), `kind`, `level`, `area_km2`, `osm` -- drawn with the monuments where more than a few pixels across (below) |

Layers 1–4, 7, 10–14, 18 (and the parks' areas) are **TopoJSON**: every line is stored once. The coast bounds a continent or an island, a country, a state, a
sea and a peninsula with the same arcs (a sea has no holes for its islands: the map draws the land over it), and a national border is one arc shared by both countries. Coordinates are delta-encoded integers on
the `transform` grid (1/400° = 278 m of latitude). The point layers (5, 6, 8, 9, 15) are CSV tables, one point a line under
a header (`lon`, `lat` to 3 decimals, 111 m: finer than the 1/400° grid).

`index.html` finds anything by name (the search box top middle: a country, state, city, monument, airport, river, lake, sea, range, peninsula,
peak, motorway, pipeline…; a city with its country), highlights it and flies there; a click on the map lists what is
at that spot; `#find=Alps` (with `&id=Q1286` or an iso code: that one of the namesakes) and `#at=46.5,10.5[,zoom]` link to one. Opened without
`#at=` (or `#find=`) it asks the browser for the visitor's position and, if given within 5 s, starts there, 2 km a
pixel (a step in from where the small copy ends: a country round the visitor) -- used only to turn the view, never sent
or kept; refused, failing or late, or once the map has been moved, the world view stays (`js/data.js` startHere). A scale bar bottom left (`js/scale.js`) gives a round length -- 1, 2 or 5 times a power of ten -- as measured
across the middle of the view, none while the whole world is in view. It draws only what is in view (each layer in an
R-tree), from the coarsest of the layer's three copies still about as fine as a pixel (`data/`, `data/small/`, `data/xsmall/`: below);
while the map moves from one about as fine as a few pixels, and without labels, once a frame at where it has got to (whole
again once the movement pauses -- a pinch once its fingers are lifted; a pinch is drawn anew only at steps of √2 in zoom, the picture
last drawn scaled with the fingers in between); it zooms to 300x (100 m a pixel). Points come by zoom, in tiers (`TIERS`): at the whole globe only
the cities of 10 million (a capital counts three times its people, and is drawn in blue, ringed -- the others' dots red, gold in the dark), from 2.5x those of 3 million, 5x 1 million, 8x
300,000, 14x all; the monuments of level 1 (by their visitors) from 5x (2 from 9x, 3 from 15x), the highest-ranked
peaks and capes from 4x, the airports of level 1 (by their passengers) from 4x (2 from 7x, 3 from 11x), the day's 15
best-known events from 4x (60 from 6x, 250 from 10x, all from 18x). The main lines come so too, in three tiers
(`LINE_TIERS`, `tier`: below): none at the whole globe, from 3x the first -- the motorways and railways that run on
across a country, the high-speed lines --, from 5x the second, from 8x all. The selection goes with the panel's x, or by emptying the search
box (its x, Escape). Two maps: POLITICAL (countries coloured, their borders and their states') and GEOGRAPHICAL
(the areas coloured by kind -- ocean, sea, gulf; mountains, plateau, desert, plain, delta, tundra... -- and no
political line), LANGUAGES (each country and state by its first official language: `language`, `language_code`
-- a state's own where Wikidata gives one, else its country's -- the widest-spoken in distinct colours) and
POPULATION DENSITY (`density`, people per km², from `population` and `area_km2`, the polygons' area on the sphere);
the natural lines and the other layers are on all (`#mode=geographical` links to one). Countries are coloured by a class (`color`, 0-6:
no two neighbours the same, neighbours sharing a border or within 1° -- `build/write.py props` recomputes it, with the populations) with
one of THREE COLOUR SCHEMES -- soft (the default), bold, earth; kept in the browser -- which colour every map, not the
countries' alone: the history's states, the geographical kinds, the languages, the density, the realms, biomes and
ecoregions (`tone()` in `js/style.js`: each base colour put into the scheme's lightness and chroma in HCL, light on the
light page and dark on the dark, so names read over all; density keeps its steps of lightness, turned round on the dark). With layer 3 on, each state is
filled in a shade of its country's colour (Lab lightness steps of 5, no two neighbouring states of one country alike, by
the shared arcs), so countries differ by hue and the states within one only by lightness. On the political, language and
density maps the countries' names are written at their `label` in spaced capitals (the bigger first, more the closer in)
and, with layer 3, the states' in mixed case, fading in from closer in; `build/write.py places` adds `label` and
`continent` to the file alone. On the historical map the day's states are named the same way, and with layer 3 the
provinces and dependencies within one (a period with an `owner`: the Duchy of Swabia in the Empire, a colony) get a
thin inner border and fading italic names. With layer 4 on, the rivers are named along their flow, in blue italics
on one straight line, beside a stretch of the river that runs straight under the whole name (reading left to
right; where it bends within a name, not there), again every 350 px of
a river: those of 1,000 km and more from zoom 4, 300 km from 6, 100 km from 9, the rest from 12 (`RIVER_NAMES`).
The panel opens rolled up at every start (however it was left): its title and three buttons, the political, the geographical and the biogeographical
map (a second click on it switches between the biomes and the ecoregions; the other maps are in its list). R rolls it
down (or up again), as its ▾ does. Under them two rows more, each button on or off a click: the networks over the map
-- rivers, roads (the motorways and the first-class roads, one switch), railways, pipelines -- and its points: cities, natural (peaks, capes, waterfalls) and
travel (monuments and airports). A map chosen starts with its own: the roads and the cities over the political map,
the rivers and the natural points over every other. Every other layer is on at first. A monument is drawn by its
kind -- a work of nature (a national park, a waterfall, a cave) a green tree, a building or a ruin a purple temple
front -- and, as an airport's ✈, in three sizes by its level. The monuments, peaks and airports are named from 1.6x
the zoom they show from (`LABEL_ZOOM`), the best known first, where the name overlaps none placed before (the
cities' first).

THE GAME (the button top right): a game on the cities (layer 6) of the whole world, a continent or a country -- chosen
first (World / Continent / Country, then which), the map flying there as it is chosen, a country drawn alone, without
the globe round it, its outline (or the continent's) in red. Then the game, and only what it asks besides: the
circles' size (a few, by where: 250 km to 2,000 for the world, 100 to 1,000 a continent, 25 to 200 a country) or how
many rounds. A start hides the choices: the question, the score and the box to type in are left (Again, New game).
While its panel is open the map shows no names but those of the cities named or found, and no points, roads or
railways. The LATEST guess is in a colour of its own (amber: `--last`) -- the city last named ringed and filled, the
place last clicked, the unit or ranked thing last named -- the others as before (green right, violet missed).
- **Their people:** name cities (English or local name, accents, case, punctuation and spaces aside, w as v, y and j as i, k
  as c, ou as u, no h, a doubled consonant as one, "City" optional -- Cracow is Kraków, Ho Chi Min, Talin, Kualalumpur find theirs;
  the same in every game where a name is typed, and the search's second try, as you type too -- of several of one name, the biggest there); their people add up, as a share of all the people there (a continent's: each country's, shared out by its
  states' -- so the cities of Russia's European oblasts count for Europe).
- **Outside every circle / inside a circle:** each city named gets a circle (so many km across, 500 for the world,
  300 a continent, 100 a country to start with: above); the next must lie outside every circle -- or inside one.
- **Find the city:** the game names one of the biggest cities there (300 of the world's, 150 of a continent's; of
  these, one a country, so China's do not fill the game), a click says where it is; a circle round the city out to the
  click shows how far off (0 km is best), and the kilometres add up over the rounds.

The countries' games: the countries of the world or a continent (with those that have a state in it: Russia, Turkey
and Kazakhstan are Europe's too), or a country's states (of the 141 countries the map has states for). A name is
taken in English or the local one, and for a country also as often called (UK, USA, Czech Republic, Burma...). Two
are neighbours if they share a land border; a dependency's borders count for its country (France borders Brazil),
and the countries round a disputed piece (Bir Tawil) border each other across it. Named ones are filled green, missed
or shown ones violet.
- **Name shape** (which one is this?): the map flies to one and outlines it; you name it (so many rounds; Show gives it away). **Bare shape** is the same with no map: its outline alone, in the middle of the screen, for the whole game.
- **Name all:** every one named is filled in, against the clock; Give up shows those left.
- **Neighbour chain:** from a random start, each one named must border the last, none twice; it ends when the last
  has no neighbour left (or with End, which says what was still possible).
- **Border route** (from one to another): a start and a goal 2–6 countries apart; each one named must border one named before, and
  it is done when the goal borders one; the end says how many the shortest way goes through (Show a way gives one).
- **Bare flag** is **Name flag** with no map: the flag alone, large, in the middle of the screen.
- **Name flag** (whose flag is this?): the game shows a flag (one of the world's countries and dependencies, or a country's states
  that have one: below) and you name whose it is (so many rounds; Show gives it away).
- **Name capital** (2026-11-26): the map flies to a country -- or, in a country, a state -- and you name its capital
  (so many rounds; Show gives it away). A country with more than one asks for each: Bolivia's La Paz and Sucre, South
  Africa's three. The capitals are `data/cities.csv`'s: a country's `capital` "country" (OSM's tags, checked against
  Wikidata's P36 where a country has several -- Mali's regional towns are tagged as its capitals: `build/points.py`
  national_capitals; a country with none takes Wikidata's: Vatican City, Yaren, Ngerulmud, Marigot, Philipsburg; Jerusalem's
  node has no plain `name` and was dropped until 2026-11-26), a state's "state" -- a city-state, Berlin's, takes the country's in it. Each capital named is
  shown on the map.

The rankings' games (`js/rankgame.js`) play a list of the Rankings (below), chosen as there -- what, by what, within
what -- in place of World / Continent / Country:

- **Which is bigger?** Two of the list's first 150 are shown, both on the map, and you click the one with more people,
  area, length or height (or press 1 / 2, ← / →). The answer gives both numbers. You get so many pairs, and no pair is
  asked twice.
- **Name the top** the first so many of the list (the 10 most populous countries, the longest rivers, Germany's biggest
  cities, the largest islands…), in any order and against the clock. Each one named fills its place in the list and on
  the map. One further down is told its place ("Volga is #14"). Give up shows the rest. A name counts with or without
  its kind: Amazon or Amazon River, Everest or Mount Everest. How many goes up to the list's own length, not a fixed
  1000 (`rankgame.js` roundsMax, 2026-11-26); **all** asks the whole list, so every name in it counts.

## Offline copy, updates, memory

On a real site (http/https) the map keeps itself in the browser: `sw.js` (a service worker) keeps every file
`offline.json` lists -- `index.html`, its libraries in `lib/` (d3, d3-geo-projection, topojson-client,
rbush, kept here rather than on a CDN so the map opens offline), `data/*.txt`, the CSVs and the flags (`flags.js`,
`flags.html`, `data/flags.txt`), 57 MB -- and the map
opens from that copy, with no network and nothing downloaded again. It does not update on its own: once a visit the page
compares its version with `offline.json` online, and a newer one shows a line at the foot with **update now** (the
version kept and **check for update** are also at the panel's foot). An update fetches the new files whole, into a new
copy, and drops the old one; the groups, mode and other settings (localStorage) stay.

It draws as soon as the world (`world.txt`: continents, islands, countries, states, lakes, areas) is read; the rivers, the main lines
and the points are asked for at once and drawn as each comes. The biogeographic and the historical map
(`bio.txt`, `history.txt`, 13 MB) are read only when wanted -- their mode chosen, a group of ecoregions, a link to
one -- so their names are found from then on.

**Memory.** A layer's points are one `Float32Array` and its rows numbers into it (`parseLite` in `js/lite.js`, THE LINES in `js/geom.js`): a
point is 8 bytes, not the 40+ of `[x, y]` in JS. Each row is a `Thing`, drawn straight from the numbers; GeoJSON is made
only for what asks (a click, a selection) and not kept. A layer not in use for 3 minutes is let go, and read again when
wanted (`RELEASE_MS`; its names stay, so it is still found). Every mode opened, measured in Chromium, `performance.memory` with
`gc()`: 1325 MB in the page of levels of detail, 187 MB now with the first-class roads, plus 53 MB of typed arrays; 111 MB with the optional layers let go.

After changing what the page loads (`build/lite.py`, a point layer, `index.html`, `js/`, `lib/`): `python3 build/offline.py`
writes `offline.json` (the file list and a hash of the files: the version), then commit and push.

The city detail maps (`data/city/<wikidata>.txt`, below) are NOT in the package -- only their index, `data/city/index.csv`
(`build/offline.py` LAZY): each is read only when the map is zoomed in on its city, and all of them together would be
tens of MB for the few a visitor looks at. The service worker keeps a city's file the first time it is read, in the
copy of the version in use (an update drops it, and it is read again on the next visit there).

## The code: js/ and wasm/

`index.html` is the page alone; the script is ES modules in `js/` (`main.js` loads them in order and calls each
module's `init()`; the shared mutable state is `S` in `state.js`): `style.js` the projections and colours, `geom.js`
the lines in typed arrays and how a row is traced, `view.js` the frame (which copy to draw from, the R-trees, `drawMap`),
`labels.js`, `data.js` the loading and letting go, `lite.js` the light-file reader, `history.js`, `search.js`,
`select.js`, `groups.js`, `game.js`, `ui.js`, `offline.js`, `flags.js`; `city.js` the city detail maps (below); `welle.js` the notes naming the thing selected
(../welle's data/back.json, listed in its panel as links into welle -- none without welle beside the map).

**The geometry core runs in WebAssembly** (`wasm/`, Rust, built to `js/mapgeo.wasm`, 150 KB): d3-geo's projection
pipeline ported for the nine projections -- the rotation, the antimeridian and small-circle clips, the adaptive
resampling, Mercator's extent -- the rows traced from the same typed arrays (handed to the module once a file is read)
into one buffer of canvas commands, and the R-trees. `js/wasm.js` is the seam: with the module every trace, tree and
query goes to it, without it (`?wasm=0`, or the file missing) the page runs the same JS as before -- the pixels are
the same either way (`wasm/check.sh` compares the Rust output with d3's own over `data/small/world.txt`, float for float,
in sixteen projection/rotation/zoom cases; the ten-view screenshot diff is identical). It draws in about half the time.

Building it needs Fedora's `cargo` with the wasm32 standard library (`rust-std-static-wasm32-unknown-unknown`) and
`lld`: `wasm/build.sh` (the result is committed, so the page needs none of this). `wasm/check.sh` runs the comparison
(node, for d3).

**The frame is painted in parallel** (`js/paint.js`, `js/worker.js`): `drawMap` writes down what is to be painted --
fills and strokes of rows, in order, and the few steps drawn on the main thread (the sphere, a selection, a clip) --
and a few painters (workers, one fewer than the cores, up to four; each with the module and its own copy of the lines)
paint contiguous chunks of equal weight onto bitmaps the main thread stacks in order; the labels and the points come on
top. One frame is in flight at a time, the newest asked for meanwhile is painted next (the moving map keeps up); a
moving map builds its next frame only once the painters are free (none built and thrown away meanwhile), and a whole
frame it moves on from -- or that a second finger lands on -- is dropped, never stacked, its labels never laid out
(2026-11-22: on a phone a pinch drew nothing until the fingers were lifted, every moving frame waiting behind a whole
one whose labels held the main thread for a second; the main lines' roads file is read only with the map at rest). A
moving map keeps its icons, and its names while dragged. `?workers=N` sets the number (0: the one thread paints);
a device of 4 GB or less (`navigator.deviceMemory`) gets two at most, of 2 GB none. A painter that dies or throws, or a
frame not painted within 6 s, gives the painters up: the workers are ended and the page paints on one thread for the
rest of the visit (2026-11-10: a phone pinched to a close zoom ran its painters out of memory, and the frame in flight
waited for ever -- the map froze).
Measured headless on four cores (three painters), a whole frame: the globe 100 ms (one thread 168, the JS 393),
Europe at zoom 6 96 ms (165, 360), the historical map 171 ms (374, 641).

## Light files (data/*.txt)

`build/lite.py` writes smaller, readable copies of the line layers -- `data/world.txt`, `rivers.txt`,
`transport.txt` (motorways and railways), `roads.txt`, `pipelines.txt`, `bio.txt`, `history.txt` -- from the full-detail ones in
`full/`, and leaves those as they are. The pipelines, off by default, are a file of their own with only their arcs:
the map asks for it when the layer is first switched on (or a link finds one), as it does the biogeographic and the
historical map when wanted. The map loads ONLY these (and the CSV point layers in `data/`): `data/` is what is committed and served. `full/` -- the build's
full-detail `*.topo.json` (tens of MB each), and `full/old/` the files they superseded -- is not committed
(`.gitignore`); it is what the light files are rebuilt from.

- **Fewer points.** A point goes when it adds little to the shape: where the line hardly turns, the triangle it makes
  with its neighbours is small (Visvalingam-Whyatt, the smallest first, up to 25 km²) -- but a point more than 1 km
  off the line between its neighbours always stays, so a fjord's end, a cape or a border's corner keeps its shape.
  Every shared line is simplified once with its ends fixed: borders and coast still meet exactly. About half the
  points go (world 1.56 M -> 0.77 M, rivers 0.56 M -> 0.26 M); the roads, already sparse, keep 94 %.
- **A text format, nothing repeated.** `grid` (the 1/400° grid), `@arcs` (a shared line a line: its first point and
  then its steps), then each object as CSV under its own header -- a column's type in its name (`population#` a
  number, `names_local[]` a list, `highspeed?` yes/no) -- with each geometry's arcs in its last column (rings `;`,
  polygons `|`, `-1 - i` for an arc followed backwards). A river or a road network is one row with what all its pieces
  share, and its pieces (`@rivers.pieces`) only their arcs and what differs. Sizes: world 19.5 -> 9.6 MB, rivers
  5.2 -> 1.9 MB, transport 10.6 -> 3.5 MB + pipelines 0.7 MB, bio 8.0 -> 3.9 MB, history 14.6 -> 8.1 MB.
- **The world's lines not stored twice.** The ecoregions and the historical regions are cut from the map's own land:
  much of their lines runs point for point along the world's coast, lake shores and borders. Those stretches
  `bio.txt` and `history.txt` take from `world.txt`'s light points (`uses world`; in a line `dw:k:dk` -- points k to
  k + dk of a world arc), and store only their own points between them; the page reads them with the world's already
  loaded. Their lines then lie on the coast exactly, and the two files are 1.3 MB smaller (0.5 MB gzipped).

## Small copies (data/small, data/xsmall)

`build/small.py` writes every line layer again with less detail, into `data/small/` and `data/xsmall/`, for small maps -- from
`data/*.txt`, which it first mends in place (a ring running along itself, a spike, a loop: split, as the globe's clip needs;
it is part of the build, so run it after `build/lite.py`). All are simplified together: a border is the same points in the
world, the biogeographic and the historical map, as there it is one line in the full files. A copy holds only lines: a row is its place
in the full file (`row`) and its arcs. Each size is a row of `SIZES` in `build/config.py`, each layer's rows of
`ROW_LIMITS` (the tiers and rivers the map does not draw at that copy's scales go):

| size | decimals (grid) | grid_km (detail) | min_km2 (smallest ring) | arcs | points | MB |
|---|---|---|---|---|---|---|
| (data/world.txt) | 1/400° | 1 | 1 | 136,972 | 767,424 | 9.3 |
| small | 2 (0.01°, 1.1 km) | 5 | 25 | 86,000 | 286,996 | 3.9 |
| xsmall | 1 (0.1°, 11 km) | 25 | 625 | 48,800 | 108,247 | 1.7 |

- **No specks.** A ring under `min_km2` goes: an island, a lake, an enclave (from both sides: the hole and the land in
  it), with its coast. A row left without a shape is not written (Monaco, the Vatican; the map draws it from the full copy
  where it must: a country's game).
- **Longer arcs.** Where only two arcs are left meeting, and every line and ring that takes one goes on into the other,
  they are made one (a row's lines joined first where they touch: the coast and the borders are stored an arc a line).
  The point between them can then go too.
- **Fewer points.** Visvalingam-Whyatt as in `build/lite.py`: a point goes when it is less than `grid_km` off the line
  between its neighbours and the triangle they make is under `grid_km` squared. An arc's ends stay, so the topology holds.
- **A coarser grid.** The points are put on a grid of `decimals` decimals (`grid 0.01 -180 -90`). A point on the same
  cell as the one before it goes, and so does a step straight back. A ring then under `min_km2`, or turned the other
  way round (simplified into a figure eight, which the globe would fill inside out), goes too.

`bio.txt` and `history.txt`'s copies take their stretches from the world's copy of the same size (`uses world`). The map reads them after the full file, and draws from that until they come.

## Biogeography (layer 13) and groups

`build/bio.py` cuts the land into RESOLVE's ecoregions the way the areas are made: the coast is the map's, and the
borders between ecoregions are lines across the land (the segments two RESOLVE polygons share, simplified, cut to the
map's land; a piece that only runs along the coast is RESOLVE's coast and is dropped). Each landmass is cut into faces
by those lines, and a face belongs to the ecoregion covering most of it -- an island RESOLVE leaves out, to the nearest
one. "Rock and Ice" (ice sheets, the highest ranges) is an ecoregion and a biome of its own; each of its faces is in the
realm of the nearest other ecoregion (Greenland Nearctic, the Antarctic ice Antarctica). Biomes and realms are their
ecoregions merged, so every border is one line shared by all three.

Less than RESOLVE draws: its borders are traced from a raster, so a straight border runs as a staircase of cells --
steps under 2 km are flattened (`BORDER_KM`); and an island under 10 km² is left out (`MIN_LAND_KM2`) unless it is
all its ecoregion has (Clipperton, the South China Sea Islands). 844 of the 847 ecoregions are in the file (8.2 MB;
the light copy 4.7 MB), 761 of the 775 over 2,000 km² within 25 % of RESOLVE's area. Not there: Malpelo and the St.
Peter and St. Paul Rocks (smaller than the map's land keeps) and Dronning Maud Land tundra (nunataks under the ice);
the small Antarctic tundras come out at 15-70 % of their area, and the Great Lakes' forests count the lakes, which
the map's land does not leave out.

`index.html`'s BIOGEOGRAPHICAL map shows the realms, the biomes or the ecoregions (in RESOLVE's colours), with the realms'
borders over them; every realm, biome and ecoregion is found by name, and a click lists the ecoregion, biome and realm
there. A list of them is shown by a link -- an animal's range, say: `#bio=NT,E567,B14` (realms by code, ecoregions by
`E` + number, biomes by `B` + number; the map opens at the level of the first). `#countries=SK,CZ,AT` does the same
for countries.

**My groups** (the panel): countries on the political map, or realms / biomes / ecoregions on the biogeographical one,
put into groups of one colour each -- with "a click puts it into the chosen group" on, a click puts what is under it
into the chosen group (and out of any other), a second click takes it out. Groups have a name and a colour, are kept in
the browser, and "copy link" gives the map with them (`#groups=…`). While a group holds countries, the political map
colours only the groups.

## Historical borders (layer 14) and events (layer 15)

`build/history.py` puts two sources on REGIONS of the map's land -- pieces of land that always shared one fate --, and
each region gets its owners through time:

- **from 1886**: CShapes 2.0 (ETH Zurich: every state and dependency, one polygon per country-period, a new one whenever
  its borders, status or capital change, to the day, de jure -- 710 of them);
- **3000 BC to 1885**: historical-basemaps (A. Ourednik): the world as mapped for 3000, 2000, 1500, 1000, 700, 500, 400,
  323, 300, 200, 100 BC, 1 BC, then every century to 1400, and 1279, 1500, 1530, 1600, 1650, 1700, 1715, 1783, 1800, 1815,
  1878, 1880 (its 1492 map, from another source, would cut the land into slivers: left out). Each map is taken to hold
  until the next, so a period's `from` and `to` are the maps' years, not the days things changed; maps in a row that
  draw a polity alike are one period (Assyria and Babylonia: 1500-501 BC). 3,133 periods. Where it draws a people or
  a culture rather than a state ("Lusatian culture", "Plain bison hunters") the period's `status` is `culture`.

**Uncertainty** is in `precision`: 3 a border fixed by law, 2 partly undefined (CShapes' colonies of the 1880s), 1
approximate -- historical-basemaps' rating, 1 for everything before 1650. A border takes the lower of its two sides'.
And the further back, the coarser the maps are in time: a century apart, a thousand years before 1500 BC.

**The regions** are cut by lines that stay put, not by the sources' outlines (historical-basemaps draws every map anew,
so one border is drawn a little differently in each, and their outlines laid together are slivers):

1. the administrative lines of today: Overture's countries, their first-level divisions (states, provinces) and their
   second-level ones (counties, districts, départements, Kreise) -- 94,000 boundaries, `build/admin.py`. Most old
   borders survive as some province's or district's;
2. CShapes' borders where they run more than 5 km from those and from the coast (Germany and Poland 1871-1945, India's
   partition): drawn to the day, they are kept; within 5 km they are the same border drawn twice;
3. the ecoregions' borders (layer 13: ridges, a desert's edge) where they run more than 5 km from all of these -- natural
   lines where empires ended in land of few districts (the Sahara, the steppe, Siberia);
4. a second cut: a period the first leaves with less than ¾ of its land (a people of Australia in an outback shire, a
   sultanate of the Sahel -- 434 shapes) has its own outline cut in too, where it runs apart from all the rest.

Each piece of land has an owner on each day: the country-period of that day covering most of it (where
historical-basemaps draws a vassal inside its empire, the smaller; an islet the coarser coasts miss: the nearest within
0.2°, else nobody). A sliver (under 25 km², or thinner than 1.5 km) takes its neighbour's owners. Pieces side by side
with the same owners on every day are one region, and so is an island near one (within 0.2°): 13,574 regions, of 82,000 pieces. A sliver of coast between a source's coarse coast and the map's
(under ~100 km²) that no period covers on a day is the nearest one's within 0.2° that day.

- **`regions`**: one polygon each -- `id`, `name` (its county's where that is half of it or more, else its province's:
  "Bavaria", "Landkreis Görlitz"), `admin` (the province, where the name is a county's), `country` (today's, ISO),
  `held` -- its owners through time, `from:state` each until the next (`"-2999:10012|-1499:10045|1886:255"`; an empty
  state is nobody's; a day that is 1 January written as its year) --, `area_km2`, `label`.
- **`periods`** (no geometry): one row per country-period -- `id` (`state:from`), `state`, `name`, `from`, `to` (days,
  both inclusive), `source`, `precision`, `status`, `owner` (the state ruling a dependency), `capital`, `cap`, `gwcode`,
  `area_km2`, `label`.

A state on a day is the regions whose `held` has it then, its period the one of its periods spanning the day; its
borders are the arcs between those regions and the others (two periods of one state make no border).

Of the periods over 20,000 km², 639 of CShapes' 640 are within 10 % of its own area (New Caledonia 0.77, with its atolls
under 10 km² left out) and 1,911 of historical-basemaps' 2,229 (2,180 within 25 %): its borders move to the nearest line
that lasts, a few tens of kilometres where the land has few districts -- no more than its own precision 1 says. 28
periods have no land of their own, all under 2,200 km² (Rome in 500 BC, Lübeck, Waldeck, small peoples of Australia):
their outlines run within 5 km of other lines all round. Land no state held -- much of Africa in the 1880s, Antarctica -- is in no state. CShapes' limits: changes
under 10,000 km² and wartime occupations reversed after the war are not in it, nor the small states it does not count
(Andorra, Dominica…). Dates are proleptic Gregorian, years astronomical (`-0699-01-01` is 1 January 700 BC). 14.6 MB (24 MB as one polygon per period, before the regions); the light copy
(`data/history.txt`) 8.1 MB.

**Events** (`data/events.csv`, `build/events.py`): 3,362 from Wikidata -- 2,244 battles, 424 sieges, 77 peace treaties
and 95 other treaties, 155 earthquakes, 126 massacres, 76 terror attacks, 56 assassinations, 45 coups, 39 rebellions,
21 eruptions, 4 revolutions -- each that enough Wikipedias write about, with a date and a place (1,384 more have no
place: mostly treaties, whose signing place Wikidata does not give; a revolution "in France" is no point). 257 are BC
(Kadesh 1274 BC, Megiddo 1457 BC). A date is as Wikidata cites it, cut to its precision; before 1582 mostly in the
Julian calendar, as historians cite it (Hastings on 14 October 1066), marked `julian`.

`index.html`'s HISTORICAL BORDERS map shows a day: the year slider (3000 BC to 2019), or the field (`1914-06-28`,
`1914`, `700 BC`). Each state in a colour no neighbour of that day has, a dependency paler in its ruler's colour (an
empire in one colour), a people or culture pale with its name in grey; the land borders of the day -- an approximate one
blurred, one to land no state held dashed --, the states' names, and the day's events (◆, the best known first): those
within a few years of it, more the further back (4 years in 1914, 109 in 700 BC). Every country-period and every event
is found by name ("Austria-Hungary": state 1908–1918, state 1886–1908; "Battle of Hastings"); chosen, the map goes to
its day. A state is drawn as its regions that day (no merging: all regions of one colour are one path), its borders
are the arcs between regions of different states. A click lists the state there on the day shown and the region, with
its owners through time. `#mode=history&date=-0699-01-01` links to a day.

**Wars and campaigns** (`data/campaigns.json`, `build/campaigns.py`): the events gathered into what Wikidata says they
were part of (P361, four levels up: the Battle of Waterloo in the Waterloo Campaign in the Hundred Days in the
Napoleonic Wars) -- 484 wars, campaigns, invasions, offensives (182 at the top) with two or more events, 2,430 events
in them -- and in each the MOVES between its battles and sieges: each joins the thread (an army, as far as places and
dates tell) whose last battle is within a march of it (30 km a day, plus 150 km, plus the slack of a date known only to
its month or year; at most 900 km and 550 days), so a war on two fronts gets two chains, not a zigzag. A guess, not a
record of marches. On the historical map the day's moves are drawn faintly between the day's events; a war chosen --
found by name, from the ⚔ list (beside the year: the wars at the day shown first, then all by their start, filtered by
typing), or from an event's "part of" -- is drawn whole whatever the day: its moves in a colour per campaign, with
arrows, its events numbered by date and listed in the panel, with its parts and the wars it was part of.

## Rankings

`index.html`'s **Rankings** (`js/ranks.js`; beside the map on a wide screen, in its place on a phone, where choosing a
row brings the map back): what the map has, ordered by a number -- countries by people, area or density (in the world
or a continent), a country's states so, cities by people (in the world, a continent, a country or one of its states),
rivers by length, peaks by height, oceans and seas, gulfs and bays, straits, mountain ranges, deserts, plateaus,
peninsulas and islands by area. Each row shows its share of the first as a bar; a click selects it on the map. The
numbers are the map's own but for a river's length and an area's: the map traces only where a river is wide (the
Nile's 2,863 km) and a sea without its islands, so those are Wikidata's (`data/measures.json`, `build/measures.py`:
P2043 for 3,392 of the 4,806 rivers, P2046 for 4,778 areas and islands).

While the list is open the map shows it ("colour the map", on unless unticked): what it ranks in seven shades by
its place, a seventh of the rows each, the first the darkest -- even steps of the list, not of the number, so a few
giants do not leave everything else one colour. Countries and states are filled, seas, gulfs, ranges, deserts and
islands too (the largest first: a gulf over its sea), rivers are drawn over in their shade and thicker the longer,
cities are dots by their people and peaks triangles. The country colours (and languages, density) are left out
meanwhile, so the ranking is the only colour. A key under the choices gives each shade's numbers, each row's bar is
in its shade, and a new scope (a continent, a country, a state) is flown to. On a phone a row chosen keeps the
colours on the map until the list is closed with its ×.

## Flags and coats of arms

`data/flags.txt` writes the flags and coats of arms as text, one a line, and `flags.js` (no dependencies) draws them
as SVG or on a canvas. France is `FR France: blue | white | red` -- three vertical bands of equal width. Each is the
simplest version of the flag: its fields and shapes in the right colours; the emblems many share -- the lion, the
eagles (Germany's, Albania's two-headed, Austria's, Russia's, Poland's), Berlin's bear, Lower Saxony's horse, Ireland's
harp, Wales's dragon -- traced from the arms' own drawings with their inner lines; the busier emblems (Mexico's eagle, Bhutan's dragon,
Dominica's parrot, Turkmenistan's carpet guls, Normandy's leopard, Hesse's barry lion, the Dauphiné's dolphin…) traced from the flag's own drawing, simplified, and kept as motifs
(`@druk`). Each definition stays under 5,000 characters (longer ones are reported): built of parts where it can be (a
ring of stars is `stars 12 r 0.33`, olive branches are `branch`), traced only roughly where it can't.
The file has every country and dependency of the map (by ISO 3166-1 code); the states (by ISO 3166-2 code: `DE-BY`)
of the UK, Germany, Austria, Switzerland, Belgium, Spain, Canada, Australia, the US, Brazil, Argentina, Venezuela,
Russia, Malaysia, the UAE, Ethiopia, Pakistan, Comoros and Micronesia, France's regions (not Grand Est's or
Hauts-de-France, which have only proposed ones), and some of Italy, Poland, Sweden, Nigeria and Bosnia -- only where a state has an official flag of its own (none of India's, Nepal's, Iraq's or Sudan's has;
Mexico's states use banners of their arms, not flags set by law, so Mexico is the country's flag alone); the
coats of arms of about 30 countries (`ES-arms`), of Germany's 16 states (`DE-BY-arms`, which their flags'
shields are) and of France's regions (`FR-NOR-arms`); the flags of the historical map's states (`h365` the state, by its id
there; `h365.1923-11-12` its flag from that day on; `-` none: Germany's of 1935-45 is not drawn), about 230 of them,
where a state's flag is known well (none drawn otherwise, not even for a colony); and the parts others are made of
(`castile`, `leon`; `france-ancient`, a semé of fleurs, is `checky(7, 6, blue, (+ gold fleur size 0.8))`, ermine
the same with `@ermine-spot`).
`flags.html` shows them all -- the components (the parts and motifs), the coats of arms, the
flags and the historical flags, each with how many others use it -- with an editor that draws what is typed and the
whole language, and shows the one picked under its name (and kind: flag, coat of arms, component), with what it
uses and what uses it, each drawn small and a link to it; a click on a flag in the
map's info panel opens it there. The map shows a country's or state's flag in the search results and its flag and arms
in the info panel, and plays **Name flag** with them.

- `a | b | c` vertical bands, `a / b / c` horizontal ones (`/` binds looser), `b*2` a band twice as wide, `( … )` a
  part that is a flag of its own: Spain `red / gold*2 / red`, Madagascar `white | (red / green)*2`. A part can carry
  its own charges, centred in it, sized and placed as shares of it and kept inside it: Castile-La Mancha
  `(crimson + gold castle size 0.5) | white`, Texas `(navy + white star size 0.4) | (white / red)*2`.
- `poly x,y x,y …` an outline, `line x,y x,y … w 0.02` a stroke of a pen; `smooth` draws either as a curve through its
  points (`x,y!` a corner in it), `mirror` gives one side only, and an outline from the middle to the middle
  (`x` = 0.5) is joined to its image: a crown is half a crown, Saudi Arabia's and Iraq's writing is strokes.
- `[2:3]` the ratio, height to width, first (2:3 if none); a shape for a coat of arms: `[shield]` (rounded to a
  point), `[iberian]` (round at the foot: Spain's, Portugal's), `[french]` (square, a point at the foot), each with a
  ratio of its own if given (`[iberian 1.28:1]`); `[pennant]`, `[round]` (`[round 5:4]` an oval).
- colours by name, about 60, each the usual shade on flags rather than an exact one: `red`, `scarlet`, `crimson`,
  `cherry`, `maroon`, `saffron`, `amber`, `gold`, `ochre`, `emerald`, `kelly`, `mediumgreen`, `olive`, `navy`, `cobalt`,
  `royalblue`, `sky`, `cerulean`… (all of them in `flags.html`), or `#rrggbb`.
- divisions: `quarterly(a, b, c, d)`, `up(a, b)`, `down(a, b)`, `x(a, b, c, d)`, `stripes(13, red, white)`,
  `pales(n, a, b)`, `checky(rows, cols, a, b)`, `lozengy(rows, cols, a, b)` (a fifth number turns the lozenges:
  Bavaria `lozengy(2.75, 2.2, white, cerulean, 39)`) -- each part any field, `@CODE` too.
- `+ charge` draws on the field: lines (`cross`, `nordic`, `saltire`, `band`, `pale`, `bend`, `rise`, `pall`, `border`,
  `wave`), shapes (`disc`, `ring`, `star`, `stars 50 grid 9,11`, `crescent`, `sun`, `triangle`, `trigram 101`,
  `poly x,y … / x,y …` -- outlines after `/` cut holes where they overlap…; `branch from x,y to x,y span 30 n 6`, a
  bowed stalk with pairs of leaves, all alike: Cyprus's olive branches, Eritrea's wreath), outlines
  (`eagle`, `lion`, `castle`, `fleur`, `crown`, `maple`…) and fields (`canton(…)`, `box(…)`, `shield(…)`, `circle(…)`,
  `@CODE`), each with its colour first and `at x,y`, `size s`, `w`, `rot`, `outline` (as lines: Morocco's star) after it. Spain's arms are
  `[shield] quarterly(@castile, @leon, @aragon, @navarre) + shield(@granada) size 0.24,0.2 at 0.5,0.9 + shield(@bourbon) size 0.3`.
- a motif is a definition that is only charges (it starts with `+`), reused as one charge: `southern-cross` is the
  Southern Cross's five stars, and Australia is `navy + canton(@GB) + white star points 7 size 0.3 at 0.25,0.75 +
  @southern-cross points 7 at 0.75,0.5`. Its charges that name no colour take the one it is given (`+ gold @southern-cross`,
  Cocos), its stars that name no `points` those given; `size` is 1 (the field's height) unless given; `rot` turns it (and `flip` mirrors it) about
  its centre (Hong Kong's bauhinia is one petal, `@hk-petal`, five times turned by 72°).

In code: `lib = Flags.library(text)`, then `lib.svg("FR", { height: 20 })` (a string of SVG), `lib.draw(ctx, "FR", x, y, w, h)`
(on a canvas) or `lib.image("FR", 40)` (a canvas, kept, for drawImage); `lib.codes`, `lib.gaps` (the codes defined as `-`), `lib.names`, `lib.has(code)`,
`lib.errors` (each line that could not be read). `Flags.svg("blue | white | red")` draws one definition alone;

## Names

Everything is named in English (`name`) and, where that is another, in the official language of its country
(`name_local`): Morocco's cities in Arabic, not also in Berber or French; a Swiss or Belgian city in the language its
own OSM name is in. A river gets one name in each official language of the countries it flows through, in their order
(`names_local`: the Rhine "Rhin", "Rhein"). English names are OSM's `name:en` or Wikidata's English label; local
ones are OSM's `name:<language>`, Overture's names (countries, states) or Wikidata's labels (lakes, rivers, monuments).
A country's official languages are Wikidata's with a two-letter code (`build/wdnames.py`, with a few corrections).
The seas, ranges and other areas keep Natural Earth's English names.

## The areas (layer 7)

An area is made of two kinds of line: the **coast**, which is natural and already the map's, and the lines **across**
the water or the land -- from cape to cape where a gulf opens into its sea, over the neck of a peninsula, round a
mountain range. Each line is stored once and shared (`build/areas.py`):

- an island or a group of islands is the landmasses it covers -- only coast: Iceland the island and Iceland the
  country are the same line; every other landmass Wikidata knows as an island is one too (`areas.py islands`: the
  island whose place is on it, its area agreeing); an island that is one landmass is not an area of its own in the
  file but that landmass's row of `islands`, named (`build/write.py`);
- any other area takes the part of Natural Earth's outline (1:10m) that is on its side of the coast -- in the water
  for a sea, on the land for a range -- as lines across, ending exactly where they meet the coast (the coast arc gets
  that point and is split there). A piece of outline that runs along the coast a little off it (Natural Earth's
  coast round Lesbos, along Guinea) is the coast, not a line across, and is dropped: never farther than 6 km from
  the coast (in km on the ground: at 80° N a degree of longitude is 19 km), nor than a quarter of its length (a line
  across a strait stands off by half its length), and from one point of a coast ring to another of the same ring,
  which then closes the face by itself (a piece along an atoll's chain of islets is what closes the Arabian Sea
  there, and stays), its nearest coast going on along the coast with it (a zigzag across the narrow mouth of
  Sherman Basin is near the coast all the way, but its nearest coast jumps from one shore to the other, over the
  basin's own: it stays). A piece that goes across somewhere and then along the coast for a stretch loses that
  stretch the same way (an area's outline is never a second coast a few km off the map's: the coast is the
  continent's or the island's own line), and its end there is tied to the coast; a range's outline wholly on the
  land (the Taurus) too. A line that still crosses the coast is noded there, or the polygonizer lets the sea into
  the land (the North Atlantic was lost so); two outlines along one stretch, ending at different points of it, are
  noded so too (all Florida was lost so). Natural Earth's thin slivers along a coast (Luzon Strait, La Pérouse
  Strait, St. Helena Bay) are then left with nothing. All areas' lines are joined into one set (two seas share their line) and simplified
  to 2 km where that does not take them over the coast. The coast and those lines cut the world into faces, and an
  area is the faces on its side of the coast that are mostly inside Natural Earth's outline, and the thin slivers
  between Natural Earth's coast and the map's that border it most. A sea is water only, but has no holes for the
  islands in it: they are drawn over it, as the land is (`build/write.py`);
- a sea with no water of the map's own (the Caspian, which OSM's coast leaves to the lakes) is its lakes.

Areas overlap (the Alps are in Europe); they are listed biggest first. Each has `mask` ("water" or "land"), a
`label` point (the spot deepest inside Natural Earth's shape), `kind`, `rank` (Natural Earth's scalerank: 0 the
biggest), and its Wikidata id.

## The rivers (layer 4)

Measured, not tagged: a river is in when the river area OSM maps around its centerline is 50 m wide or more
somewhere. From there it is followed downstream to its end -- along its OSM ways in their direction (the flow), from
way to way while they share a name (English, OSM's, or one part of a two-language name: "Le Rhin / Rhein" -- or one
within the other, without an article: "Rhin" in "Vieux Rhin", the Old Rhine below the weir at Kembs) or a
Wikidata item -- the same one, or one `part of` the other's: the Solimões is the Amazon's Brazilian upper course under
its own name and item -- across gaps under 10 km (30 km where the gap lies straight ahead: the Váh through the
Kráľová reservoir) and through lakes -- and then back upstream from every way reached, way to way of the same name,
to its source. So each river is one line from source to mouth (more where it forks), and a tributary stops where it
flows into another river. Rivers drawn shorter than 50 km are left out, and so are the obscure: a river stays if it
has a name and is among the 1,000 longest or the 1,000 widest, or some Wikipedia has an article on it
(`wikipedias`). A river's English name is Wikidata's (from its ways' items), or Natural Earth's where its river line
runs along it.

Then one network of single lines (`build/rivernet.py`): as tracked, a river is every channel OSM maps of it -- a
braided river hundreds of lines side by side (the Diamantina was 9,398), a river in its floodplain with its side arms.
Of each river (each connected part of it) the TRUNK is the way between its two ends farthest apart, once through its
braids. Then, the longest rivers' trunks first and the other pieces after: a stretch closer than 2.5 km to a line kept
before is the same water, dropped where that runs on for 4 km (a parallel duplicate) or at an end that does not reach
the other line (a braid's, a side arm's); of a trunk any piece of 2 km is kept, of the other pieces only one running
apart for 10 km (the Little Danube and the Moson Danube beside the Danube). A cut end is carried onto the line it ran
beside, an end within 0.6 km of a line -- or a free mouth within 5 km -- onto that line, and every line is cut into
arcs at the junctions on it, so a tributary meets its river exactly at every level of detail. A mouth in the sea is
cut where the river crosses the coast, one ending inland within 8 km of the coast (and not at a lake) is carried on to
it, and that point is put into the coast's own line (`full/world.topo.json`; `build/lite.py` keeps it). Before that, a
free end short of the map's water (on land, no lake or line near) goes on along OSM's waterways, whatever their name,
the shortest way up to 50 km to where they reach the sea, the coast or a lake (or another river, by a way of its own
name): a river renamed for its last stretch (the Liri as the Garigliano), an estuary's channels (the Xi's), a mouth
beyond a lagoon (`ONWARD_KM`).

Two rivers of ONE NAME whose lines meet, not two Wikidata items, are made one first (`merge_same` in
`build/riverlevels.py`: OSM's Ganges and its Hooghly arm to Kolkata, the Konda, the Luhit -- 6 pairs; found, chosen and
measured as one). Drawn in THREE WIDTHS by level (`lvl`, `build/riverlevels.py`, run after rivernet.py): **1** a river longer than 2,000 km
flowing into the sea itself (35: the Nile, the Amazon, the Danube, the Volga, the Ganges, the Murray ...); **2** one longer
than 500 km flowing into the sea, or into a river of level 1 -- of those only its 5 longest (the Danube's Tisza, Prut,
Sava, Drava, Olt; the Mississippi's Missouri, Arkansas, Ohio, White, Des Moines) -- 343; **3** the rest, 5,503. Levels 1
and 2 at every zoom, the rest by length as before. A river's length is Wikidata's (P2043, the preferred statement, else
the longest; the whole course -- the Nile's 6,650 km, drawn from where it is 50 m wide, 2,863 km; the Fraser's 2,657 km
corrected to 1,375), else its lines' drawn. Where it ends: the downstream end of each of its lines -- on the coast, or
within 160 km of it on no longer river (a line stopping short at a delta: the Nile at Cairo, the Rhine at the Waal, the
Euphrates at the Shatt al-Arab), the sea; on another river's line, that river. (The St. Lawrence, mapped only below Lake
Ontario's outflow and not to its estuary, is not level 1; the Brahmaputra, without a Wikidata item on its lines, is 3.)

## The main lines (layers 10-12)

`build/transport.py` takes OSM's ways (their tags: Limits, below) and joins the ways of one road number end to end --
lines as OSM has them (`full/transport.tracked.topo.json`). Then one network of single lines (`build/roadnet.py`), as
for the rivers: a motorway is two carriageways in OSM, a railway as many tracks, each its own way a few metres to a
few hundred apart, and they meet only at the road's ends if at all. So the lines go one by one, a high-speed railway
first, a motorway before a trunk road, then the longest: a stretch closer than 600 m to a line kept before is the same
road, dropped where that runs on for 2 km or at an end that does not reach the other line; the rest is kept where it
runs apart for 1 km (the carriageways parting through a mountain), its cut ends carried onto the line it ran beside.
(A line whose ways turn back on themselves -- both carriageways joined at the road's end -- is first cut there.) Two
roads side by side that close are one line too: at the map's closest they would be a pixel or two apart. A road that
meets another ends ON it -- an end within 1.5 km of another line (1 km for a railway: the slip roads between them are
not in the map) is carried onto that line, one that crosses a line and stops just beyond it ends where it crossed --
and every line is cut into arcs at the junctions on it, so the roads meet exactly at every level of detail. Before
that, two ends that face each other across a gap of up to 3 km (5 km for a railway) are joined: a line's ways in OSM
are not all tagged as it is (a station, a bridge, a tunnel named as itself), so a line is not drawn in pieces.
These lines carry no name (`build/lite.py` UNNAMED): in OSM a way is as often named after its tunnel, bridge or stretch as
after the road, and that name stood for the whole line, or for a line of its own; a line is its number, or nothing.
Pipelines side by side stay side by side; they are only joined (within 0.5 km). Of the pipelines only the long
routes are kept, not the fields and terminals: an offshore field's knot of flowlines loses its short loops first (an
arc under 20 km that is not the only way between its ends goes, one a loop at a time), then the dead ends under
20 km (from a line's end to its first junction, again and again: a star's spokes, then the platform's own line), then
whatever network is left under 100 km.

Each arc is then in one of three tiers (`tier`; the map draws the first from 3x, the second from 5x, the rest from
8x). Not by its tags -- they are too uneven across the world: India's railways have no name, number or speed -- but
by its STROKE, the way on through the junctions: at each, the two arcs that run on most nearly straight (turning less
than 45 degrees, or 75 for the same road number) are one way, and its length ranks it. A motorway's stroke of 400 km
or more is in the first tier, of 100 km the second; a railway's of 500 and 150 km; a high-speed line is in the first
whatever its length; a pipeline is ranked by its network's length (1,000 and 200 km).

## Time zones (layer 18) and the parks' areas

`build/timezones.py` reads timezone-boundary-builder's zones WITH THE OCEANS (release 2026f, 444 zones, 8.3 M points):
they cover the whole globe -- a land zone runs out over its territorial waters, the open sea is in the nautical zones,
15° each, the date line between Etc/GMT-12 and +12 -- so none follows the map's coast, and none has to: they are drawn
tinted over land and sea, with the map's lakes, coast and borders over them. A topology of their own: on the 1/400° grid
a border is the same points in both zones, so each ring is cut where its neighbours change and each piece kept once;
each arc simplified with its ends fixed (Douglas-Peucker on the sphere to 1.5 km, Visvalingam-Whyatt to 12 km², a point
3 km off kept) -- 3.1 M points on the grid -> 62,000; a ring under 4 km² goes (the Vatican's zone, and Rome's hole for
it). The north pole is moved a grid step south (the sea's strips met there: a ring through a pole is no ring to the
globe's clip, it painted all the sphere). Offsets from Python's zoneinfo (the system's tzdata) over 2026: `utc` the one
in force without daylight saving, `dst` the other (Morocco's: its Ramadan hour back). `data/timezones.txt` 0.57 MB
(0.22 MB gzipped), small 0.39 (0.15), xsmall 0.16 (0.06); read when the layer is switched on (the panel's **zones**,
off at first and with every map chosen), or a search looks like one ("UTC+5:30", "Europe/Berlin"). Each zone is
coloured by its offset (`js/zones.js`): round the colour wheel once a day, every other hour lighter, a half- or
three-quarter-hour zone darker and stronger in the hue between; the countries' own colours left out while it is on.
Where the clock changes the border is drawn dark, between zones of one time (Germany / France) faint and only closer
in. The offsets are written in the zones, the biggest first. A click lists the zone (its offset, daylight saving, the
time there now -- the browser's clock and rules) and its offset with all its zones; each is found by name.

`build/parks.py` gives the national parks and protected areas of layer 5 (1,063 rows) their outlines: the row's own OSM
object (`osm`) or the relation tagged with its Wikidata item (a boundary=national_park / protected_area first), the
shapes as QLever's OSM planet assembles them (`geo:asWKT`), 15 a request, each kept in `raw/parks/` (a failed request
tried again after 10, 20, 40… s). Kept when a polygon (a trail is not), within 25 km of the row's point, 1 km² or more;
simplified to 0.25 km (`build/lite.py` DETAIL: its own detail). 919 of 1,063 have one (856 of the 983 national parks):
113 no OSM object, 6 no shape, 4 no area, 11 too far, 10 too small -- those stay points. `data/parks.txt` 0.69 MB (0.23
gzipped), small 0.09 (0.03), xsmall 0.01 (0.006); read once the map is at 3x (`js/parks.js`), with the monuments on. A park more than
4 px across is filled green and outlined; from 30 px its tree icon goes and its name stays (written at its point when
its level would not show it yet). A click inside lists the park's area.

## City detail maps (layer 17)

Zoomed in on a city that has one (closer than 80 m a pixel, `CITY_KM` in `js/city.js`; there the map goes on down to
4 m a pixel, `CITY_MAX_KM`, where elsewhere it stops at `MAX_ZOOM`), the map draws the city's own detail map within
the city's boundary, and its own rivers, roads and railways outside it only. `build/citymaps.py` makes them from
OpenStreetMap; a city is ONE entry in its `CITIES` list, by its Wikidata id, which `admin_level`s are its districts
(`levels`; "6|8" two of OSM's as one, "place=suburb" a place boundary on no admin_level, "ward=ward" an electoral ward,
boundary=political: Manchester's), and as needed `boundary` (the
Wikidata id of the boundary to take instead; "Qa|Qb" several as one, their union: Mumbai's two districts, New York's
Manhattan and Brooklyn; "r<id>" an OSM relation with no wikidata tag, Buenos Aires, Monaco), `radius` (km: the
outline cut to a circle that far round the city's point -- a province-sized city or a county cut to its town: Kyoto's
mountains, Los Angeles County, the Gold Coast's hinterland), `names` ("en", "fr": the tags' name:en or name:fr
taken for every name that has one, where the local script would be unreadable or the city is known by them: Cairo,
Mumbai, Casablanca), `drop` (districts left out of the outline) or `keep` (only these in it), `strip` (a regex cut from the
districts' names, or a list of [regex, replacement] pairs: "Paris 18e Arrondissement" -> "18e arr.", "XI. kerület" -> "XI"),
`skip` (districts left out: a former one OSM still bounds, Turin's "Mirafiori Sud"), `airport` ([iata, lon, lat] when the
busiest within 50 km is not the city's: Rotterdam's RTM, not Schiphol), `place` ([name, lon, lat] for a city not in
data/cities.csv: Venice, Dubrovnik; for one in it, only its point moved -- the middle of `radius` and of the lanes:
the Strip for Las Vegas, Angkor for Siem Reap), `core` ([lon, lat, km], where the old town's lanes are taken from), `airport: null`
(no airport, where the nearest would stretch the window: Lucerne, Valletta),
`tertiary` (a country whose main streets OSM tags tertiary -- Denmark, Sweden -- drawn as secondary) and `pbf` (the Geofabrik extract it is read from). Each entry's comment says why its outline is the
one it is. Europe first, by international arrivals, then the world (the order: the comment over `CITIES`):

| wikidata | city | outline | districts | airport | file | gzipped |
|---|---|---|---|---|---|---|
| Q84 | London | Greater London, 1,570 km² | 6\|8 (32 boroughs, the City) | LHR | 421 KB | 146 KB (x3.4) |
| Q90 | Paris | the commune, 105 km² | 9 (arrondissements) | CDG | 163 KB | 62 KB |
| Q406 | Istanbul | the province but Çatalca, Silivri, Şile, Arnavutköy | 6 (35 ilçe) | IST | 428 KB | 146 KB (x2.8) |
| Q220 | Rome | the comune, 1,290 km² | 10 (15 municipi) | FCO | 368 KB | 130 KB |
| Q1492 | Barcelona | the municipality, 101 km² | 9 (districtes), 10 (barris) | BCN | 165 KB | 59 KB |
| Q727 | Amsterdam | the gemeente (Q9899), 219 km² | place=suburb (stadsdelen) | AMS | 148 KB | 56 KB |
| Q1085 | Prague | the capital city, 496 km² | 5 (obvody Praha 1-10) | PRG | 185 KB | 70 KB |
| Q2807 | Madrid | the municipality, 604 km² | 9 (21 distritos) | MAD | 160 KB | 57 KB |
| Q1741 | Vienna | the city and state, 415 km² | 9 (23 Bezirke) | VIE | 176 KB | 65 KB |
| Q490 | Milan | the comune, 182 km² | 10 (9 municipi) | MXP | 152 KB | 55 KB |
| Q1524 | Athens | Attica (Q758056) but East and West Attica and the islands, 412 km² | 6 (regional units), 7 (~40 demoi) | ATH | 127 KB | 47 KB |
| Q597 | Lisbon | the municipality, 100 km² | 8 (24 freguesias) | LIS | 61 KB | 23 KB |
| Q1761 | Dublin | County Dublin (Q173500), 922 km² | 7 (4 councils) | DUB | 215 KB | 78 KB |
| Q1781 | Budapest | the capital, 525 km² | 9 (23 kerület, by number) | BUD | 137 KB | 54 KB |
| Q6487 | Antalya | the province's 5 urban ilçe (Q40249, `keep`), ~1,900 km² | 6 | AYT | 152 KB | 56 KB |
| Q1748 | Copenhagen | the Capital Region's (Q26073) inner 10 kommuner, ~330 km² | 7 (kommuner) | CPH | 152 KB | 56 KB |
| Q239 | Brussels | the Capital Region (Q240), 162 km² | 8 (19 communes, French names) | BRU | 97 KB | 35 KB |
| Q1754 | Stockholm | the municipality (Q506250), 188 km² | 9 (stadsdelsområden), 10 (stadsdelar) | ARN | 121 KB | 45 KB |
| Q270 | Warsaw | the city, 517 km² | 9 (18 dzielnice) | WAW | 132 KB | 52 KB |
| Q31487 | Krakow | the city, 327 km² | 9 (18 dzielnice) | KRK | 95 KB | 37 KB |
| Q2634 | Naples | the comune, 119 km² | 10 (10 municipalità) | NAP | 68 KB | 25 KB |
| Q8717 | Seville | the municipality, 141 km² | 9 (11 distritos) | SVQ | 53 KB | 20 KB |
| Q649 | Moscow | the federal city but New Moscow (Novomoskovsky, Troitsky) and Zelenograd, ~1,100 km² | 5 (9 okrugs), 8 (raions) | SVO | 461 KB | 139 KB (x1.5) |
| Q656 | Saint Petersburg | the federal city but Kurortny and Kronshtadtsky, ~1,250 km² | 5 (16 raions), 8 (municipal okrugs) | LED | 416 KB | 145 KB |
| Q36433 | Porto | the district's (Q322792) 5 core municipalities (`keep`), ~420 km² | 7 (concelhos), 8 (freguesias) | OPO | 227 KB | 75 KB |
| Q8818 | Valencia | the municipality, 135 km² | 9 (19 districtes) | VLC | 74 KB | 28 KB |
| Q1055 | Hamburg | the city state but Neuwerk, 747 km² | 9 (7 Bezirke), 10 (Stadtteile) | HAM | 283 KB | 103 KB |
| Q1794 | Frankfurt | the city, 248 km² | 9 (16 Ortsbezirke), 10 (Stadtteile) | FRA | 96 KB | 36 KB |
| Q33959 | Nice | the commune, 72 km² | 10 (the few quartiers OSM bounds) | NCE | 40 KB | 15 KB |
| Q8810 | Granada | the municipality, 88 km² | 9 (8 distritos) | -- | 74 KB | 26 KB |
| Q116450968 | Malaga | the municipality (Q8851), 395 km² | 9 (11 distritos) | AGP | 121 KB | 42 KB |
| Q456 | Lyon | the commune, 48 km² | 9 (9 arrondissements) | LYS | 55 KB | 21 KB |
| Q23482 | Marseille | the commune, 240 km² (the calanques' massif, the Frioul islands) | 9 (16 arrondissements) | MRS | 140 KB | 47 KB |
| Q585 | Oslo | the kommune, 454 km² (Nordmarka) | 9 (15 bydeler, Sentrum, Marka) | OSL | 208 KB | 74 KB |
| Q1757 | Helsinki | the city, 214 km² of land and 500 of sea | 10 (59 kaupunginosat) | HEL | 193 KB | 68 KB |
| Q365 | Cologne | the city, 405 km² | 9 (Stadtbezirke), 10 (Stadtteile) | -- | 132 KB | 50 KB |
| Q1899 | Kyiv | the city, 839 km² | 10 (10 raions) | -- | 204 KB | 74 KB |
| Q3711 | Belgrade | the city proper (OSM's settlement), ~360 km² | 9 (10 urban opštine) | BEG | 96 KB | 34 KB |
| Q472 | Sofia | the city (OSM's settlement) | 6 (raioni), 9 (ж.к., кв.) | SOF | 191 KB | 71 KB |
| Q19660 | Bucharest | the municipality, 228 km² | 9 (6 sectors) | OTP | 74 KB | 27 KB |
| Q1773 | Riga | the city, 307 km² | 9 (apkaimes) | RIX | 107 KB | 40 KB |
| Q216 | Vilnius | the city (admin_level 8), ~400 km² | 10 (seniūnijos) | VNO | 160 KB | 60 KB |
| Q1435 | Zagreb | the city, 641 km² | 9 (17 gradske četvrti) | ZAG | 186 KB | 67 KB |
| Q495 | Turin | the comune, 130 km² | 10 (circoscrizioni) | TRN | 78 KB | 29 KB |
| Q2656 | Palermo | the comune, 159 km² (Mondello, the sea) | 10 (8 circoscrizioni) | PMO | 56 KB | 21 KB |
| Q17151 | Thessaloniki | the Dimos (Q6627746), 19 km²: the city proper | 9 (Koinotites) | SKG | 29 KB | 11 KB |
| Q1449 | Genoa | the comune, 240 km², 30 km of coast | 10 (9 municipi) | GOA | 222 KB | 74 KB |
| Q34370 | Rotterdam | the gemeente (Q2680952), out to the Maasvlakte | place=suburb (gebieden), place=quarter (wijken) | RTM | 127 KB | 48 KB |
| Q36600 | The Hague | the gemeente | place=suburb (8 stadsdelen), place=quarter (wijken) | RTM | 66 KB | 25 KB |
| Q8692 | Bilbao | the udalerria, 41 km² | 9 (8 distritos), 10 (barrios) | BIO | 52 KB | 20 KB |
| Q1731 | Dresden | the city, 328 km² | 9 (Stadtbezirke, Ortschaften) | DRS | 123 KB | 46 KB |
| Q4093 | Glasgow | the council area (Q55934339), 175 km² | place=suburb (only Kingston) | GLA | 72 KB | 27 KB |
| Q19689 | Tirana | the 11 njësi bashkiake of the Bashkia (`keep`) | 9 (njësi) | TIA | 29 KB | 12 KB |
| Q36036 | Lviv | the city, 182 km² | 10 (6 raions) | LWO | 70 KB | 25 KB |
| Q18125 | Manchester | the metropolitan borough (Q21525592), 116 km² | ward=ward (32 wards) | MAN | 83 KB | 32 KB |
| Q2256 | Birmingham | the metropolitan borough (Q20986424), 268 km² | ward=ward (wards) | BHX | 135 KB | 49 KB |
| Q641 | Venice | the comune (the lagoon, its islands, Mestre), 415 km²; the lagoon as water, no vaporetto | 10 (6 municipalità) | VCE | 334 KB | 107 KB |
| Q2044 | Florence | the comune, 102 km² | 10 (5 quartieri) | FLR | 103 KB | 35 KB |
| Q23436 | Edinburgh | the City of Edinburgh council area, 264 km² | 10 (community council areas) | EDI | 104 KB | 38 KB |
| Q34713 | Salzburg | the Statutarstadt, 66 km² | 10 (Stadtteile) | SZG | 51 KB | 19 KB |
| Q12994 | Bruges | the municipality (out to Zeebrugge), 138 km² | 9 (deelgemeenten) | none | 85 KB | 32 KB |
| Q72 | Zurich | the city, 88 km² | 9 (12 Kreise) | ZRH | 84 KB | 31 KB |
| Q71 | Geneva | the city, 16 km² | 10 (quartiers) | GVA | 21 KB | 8 KB |
| Q1891 | Bologna | the comune, 141 km² | 10 (6 quartieri) | BLQ | 80 KB | 29 KB |
| Q2028 | Verona | the comune, 199 km² | 10 (8 circoscrizioni) | VRN | 86 KB | 31 KB |
| Q13375 | Pisa | the comune (out to Marina di Pisa), 185 km² | none in OSM | PSA | 70 KB | 26 KB |
| Q1722 | Dubrovnik | the city, 143 km² | 9 (gradski kotari) | DBV | 63 KB | 24 KB |
| Q1770 | Tallinn | the city, 159 km² | 9 (8 linnaosad), 10 (asumid) | TLL | 76 KB | 30 KB |
| Q1735 | Innsbruck | the city, 105 km² | 9 (Stadtteile) | INN | 63 KB | 24 KB |
| Q4191 | Lucerne | the city, 37 km² | none in OSM | none | 45 KB | 18 KB |
| Q1764 | Reykjavik | the city (Kjalarnes with it), 273 km² | 9 (hverfi) | KEF | 118 KB | 43 KB |
| Q437 | Ljubljana | the city municipality (Q3434113), 275 km² | place=suburb (17 četrtne skupnosti) | LJU | 145 KB | 52 KB |
| Q1663 | Split | the city, 80 km² | 9 (gradski kotari) | SPU | 45 KB | 17 KB |
| Q1780 | Bratislava | the city, 367 km² | 9 (17 mestské časti) | BTS | 110 KB | 42 KB |
| Q24826 | Liverpool | the metropolitan borough (Q21665571), 112 km² | none (its wards barely mapped) | LPL | 59 KB | 22 KB |
| Q1479 | Bordeaux | the commune, 49 km² | 10 (quartiers) | BOD | 65 KB | 25 KB |
| Q6602 | Strasbourg | the commune, 78 km² | 10 (quartiers) | SXB | 98 KB | 36 KB |
| Q8826 | Palma | the municipality, 208 km² | 9 (districtes) | PMI | 102 KB | 37 KB |
| Q23800 | Valletta | the local council, 0.8 km² (the walled town) | none | none | 8 KB | 3 KB |
| Q1842 | Luxembourg | the commune, 51 km² | 9 (24 quartiers) | LUX | 64 KB | 24 KB |
| Q64 | Berlin | the Land, 890 km² | 9 (Bezirke), 10 (Ortsteile) | BER | 321 KB | 117 KB |
| Q1726 | Munich | the city, 310 km² | 9 (Stadtbezirke) | MUC | 144 KB | 53 KB |
| Q160544 | Heraklion | the municipal unit (the town, 109 km²), its 4 communities | 10 (9 names) | -- | 60 KB | 21 KB |
| Q188731 | Rhodes | the municipal unit of Rhodes (the town and its old town, 20 km²) | none | RHO | 29 KB | 11 KB |
| Q3949542 | Santorini (Fira) | the municipality of Thira (the island, Thirasia with it, 90 km²: Fira, Oia) | none | JTR | 33 KB | 12 KB |
| Q25444 | Funchal | the município (76 km²), its 10 freguesias | 8 (9 names) | FNC | 69 KB | 23 KB |
| Q11974 | Las Palmas | the municipality (101 km²), its distritos | 9 (13 names) | LPA | 62 KB | 22 KB |
| Q14328 | Santa Cruz de Tenerife | the municipality (150 km², Anaga with it) | 9 (5 names) | TFN | 65 KB | 23 KB |
| Q235 | Monaco | the principality's commune (2 km²: its level-2 relation takes in the sea), its quartiers | 10 (9 names) | -- | 17 KB | 6 KB |
| Q12892 | Antwerp | the city (204 km²), its 9 districten | 9 (10 names) | ANR | 122 KB | 45 KB |
| Q1296 | Ghent | the city (156 km²), its deelgemeenten | 9 (14 names) | -- | 113 KB | 41 KB |
| Q70 | Bern | the city (52 km²), its Stadtteile | 9 (6 names) | BRN | 68 KB | 25 KB |
| Q78 | Basel | the city (24 km²), its Wohnviertel | 9 (19 names) | -- | 46 KB | 17 KB |
| Q1792 | Gdansk | the city (262 km²), its dzielnice | 9 (35 names) | GDN | 106 KB | 41 KB |
| Q23154 | Bristol | the unitary authority 9 km round the centre (its relation runs down the Severn estuary to Steep Holm), its wards | 'ward=ward' (33 names) | -- | 93 KB | 34 KB |
| Q39121 | Leeds | the metropolitan district (552 km², Otley and Wetherby with it), its wards | 'ward=ward' (1 names) | LBA | 147 KB | 54 KB |
| Q22889 | Bath | its boundary=place (the unparished city, 29 km²: no council of its own under B&NES) | none | -- | 38 KB | 14 KB |
| Q34217 | Oxford | the city (46 km²), its wards | none | -- | 37 KB | 14 KB |
| Q350 | Cambridge | the city (41 km²), its wards | 'ward=ward' (14 names) | -- | 39 KB | 15 KB |
| Q42462 | York | the unitary authority (272 km²), its wards | none | -- | 83 KB | 31 KB |
| Q803 | Utrecht | the gemeente (99 km²), its wijken (place=suburb) | 'place=suburb' (10 names) | -- | 129 KB | 46 KB |
| Q9832 | Eindhoven | the gemeente (89 km²), its stadsdelen (place=suburb) | 'place=suburb' (7 names) | EIN | 88 KB | 31 KB |
| Q25287 | Gothenburg | the municipality (Göteborgs Stad, 450 km² with its archipelago) | 9, 10 (100 names) | GOT | 219 KB | 79 KB |
| Q2211 | Malmö | the municipality (158 km²) | 9, 10 (141 names) | -- | 90 KB | 33 KB |
| Q36647 | Cork | the city (187 km² since 2019), its electoral divisions | 9 (79 names) | ORK | 132 KB | 49 KB |
| Q10686 | Belfast | the city district (133 km²) | none | BHD | 82 KB | 30 KB |
| Q10690 | Cardiff | the county (140 km²), its communities | 10 (36 names) | -- | 102 KB | 37 KB |
| Q26793 | Bergen | the municipality (465 km²), its 8 bydeler | 9 (8 names) | BGO | 252 KB | 87 KB |
| Q25319 | Aarhus | the municipality (468 km²) | none | -- | 145 KB | 53 KB |
| Q3856 | Nicosia | both halves -- the municipality (Δήμος Λευκωσίας) and the north's Lefkoşa Türk Belediyesi, the walled city whole across the Green Line | 9 (32 names) | -- | 80 KB | 30 KB |
| Q1863 | Andorra la Vella | the parish and Escaldes-Engordany, one town along the Valira | none | -- | 32 KB | 11 KB |
| Q11194 | Sarajevo | the city (Grad Sarajevo, 141 km²), its 4 općine | 7 (4 names) | SJJ | 81 KB | 30 KB |
| Q23564 | Podgorica | the town (admin_level 8, not the 1,400 km² capital municipality) | none | TGD | 27 KB | 10 KB |
| Q171080 | Kotor | the opština 3 km round the old town (its own level-8 relation is but the walled town; the opština 335 km² of the bay's mountains) -- Dobrota, Škaljari, the fortress above | none | -- | 10 KB | 4 KB |
| Q384 | Skopje | the City of Skopje (Град Скопје, 571 km²), its 10 municipalities | 7 (10 names) | SKP | 150 KB | 52 KB |
| Q21197 | Chișinău | the city (admin_level 8, not the 563 km² municipiu) | none | RMO | 44 KB | 17 KB |
| Q2280 | Minsk | the city (409 km²), its 9 raions | 9 (9 names) | -- | 115 KB | 40 KB |
| Q14960 | Brno | the city (230 km²), its 29 městské části | 10 (4 names) | -- | 98 KB | 37 KB |
| Q188082 | Český Krumlov | the town (22 km²), its parts | none | -- | 27 KB | 10 KB |
| Q2079 | Leipzig | the city (297 km²), its 10 Stadtbezirke | 9 (10 names) | -- | 120 KB | 44 KB |
| Q2090 | Nuremberg | the city (186 km²) | 10 (10 names) | NUE | 123 KB | 44 KB |
| Q1022 | Stuttgart | the city (207 km²), its 23 Stadtbezirke | 9 (23 names) | STR | 136 KB | 49 KB |
| Q1718 | Dusseldorf | the city (217 km²), its 50 Stadtteile (the 10 Stadtbezirke are only numbered) | 10 (50 names) | DUS | 128 KB | 46 KB |
| Q1799 | Wrocław | the city (293 km²), its 48 osiedla | 9 (48 names) | WRO | 132 KB | 50 KB |
| Q268 | Poznan | the city (262 km²), its 42 osiedla | 9 (42 names) | POZ | 114 KB | 44 KB |
| Q7880 | Toulouse | the commune (118 km²) | 10 (20 names) | TLS | 113 KB | 39 KB |
| Q6441 | Montpellier | the commune (57 km²) | 10 (7 names) | MPL | 90 KB | 32 KB |
| Q648 | Lille | the commune (35 km², Lomme and Hellemmes with it) | 10 (10 names) | LIL | 68 KB | 25 KB |
| Q12191 | Nantes | the commune (65 km²) | 10 (11 names) | NTE | 101 KB | 35 KB |
| Q6397 | Avignon | the commune (65 km², its walled town and the Rhône islands) | none | -- | 55 KB | 20 KB |
| Q807 | Lausanne | the commune (41 km², its northern woods with it) | none | -- | 61 KB | 23 KB |
| Q8646 | Hong Kong | Hong Kong Island and Kowloon (the New Territories and Lantau left out), their districts | 6 (9 names) | -- | 118 KB | 40 KB |
| Q14773 | Macau | the SAR (Macau, Taipa, Cotai, Coloane: 33 km²), its parishes | 6 (8 names) | -- | 87 KB | 31 KB |
| Q612 | Dubai | the city (its relation of no admin_level), its communities | 10 (133 names) | DXB | 195 KB | 72 KB |
| Q1519 | Abu Dhabi | the city (admin_level 5) | none | -- | 90 KB | 31 KB |
| Q3861 | Doha | the municipality | 10 (54 names) | DOH | 69 KB | 25 KB |
| Q5806 | Mecca | the governorate | 10 (95 names) | -- | 101 KB | 37 KB |
| Q1861 | Bangkok | the city (1,569 km²), its 50 khet | 6 (50 names) | -- | 378 KB | 137 KB |
| Q182565 | Phuket | the province 11 km round the island's middle -- Phuket Town, Patong, Karon, Kata, Chalong -- its districts | 6 (2 names) | -- | 69 KB | 26 KB |
| Q170919 | Pattaya | the city (Bang Lamung's coast, 22 km²) | none | -- | 23 KB | 8 KB |
| Q52028 | Chiang Mai | the city municipality (40 km², the moated old town at its heart) | 8 (6 names) | CNX | 27 KB | 10 KB |
| Q334 | Singapore | the island state (735 km²), its 55 planning areas | 6 (55 names) | SIN | 238 KB | 86 KB |
| Q1865 | Kuala Lumpur | the federal territory (243 km²) | none | -- | 94 KB | 34 KB |
| Q61092 | George Town | the city (Penang Island, 306 km²) | 8 (12 names) | PEN | 97 KB | 35 KB |
| Q35765 | Osaka | the city (225 km²), its 24 wards | 8 (24 names) | -- | 141 KB | 53 KB |
| Q34600 | Kyoto | the city 9 km round its middle (828 km² whole, its northern mountains) -- Arashiyama to Fushimi Inari -- its 11 wards | 8 (6 names) | -- | 101 KB | 38 KB |
| Q169134 | Nara | the city 6 km round the park (277 km² whole, mountains east) | none | -- | 54 KB | 21 KB |
| Q1490 | Tokyo | the 23 special wards (627 km²; the Metropolis's Tama towns, mountains and islands left out) | 7 (23 names) | HND | 326 KB | 119 KB |
| Q8684 | Seoul | the city (605 km²), its 25 gu | 6 (25 names) | GMP | 261 KB | 92 KB |
| Q16520 | Busan | the city 14 km round its middle (its relation out to far islets), its 16 gu and gun | 6 (11 names) | PUS | 142 KB | 51 KB |
| Q42142 | Jeju | Jeju City 12 km round the town (978 km² whole: the island's northern half, its islets) | 8 (18 names) | CJU | 101 KB | 34 KB |
| Q1867 | Taipei | the city (272 km²), its 12 districts | none | TPE | 134 KB | 47 KB |
| Q1854 | Ho Chi Minh City | the city 9 km round District 1 (the city since 2025 is 6,800 km², Bình Dương and Vũng Tàu with it), its phường | 6 (50 names) | SGN | 108 KB | 39 KB |
| Q1858 | Hanoi | the city 8 km round Hoàn Kiếm (of its 3,359 km²), its phường | 6 (33 names) | -- | 88 KB | 33 KB |
| Q25282 | Da Nang | the city 7 km round its centre (of a province since 2025), its phường | 6 (5 names) | DAD | 37 KB | 13 KB |
| Q36160 | Hoi An | its three phường (Hội An, Hội An Đông, Hội An Tây: the old town and round it) | none | -- | 22 KB | 8 KB |
| Q8686 | Shanghai | the city 10 km round People's Square (of its 6,340 km²), its districts | 6 (7 names) | -- | 116 KB | 43 KB |
| Q956 | Beijing | the city 12 km round the Forbidden City (of its 16,410 km²: the Fifth Ring Road's), its districts | 6 (2 names) | -- | 142 KB | 54 KB |
| Q16572 | Guangzhou | the city 10 km round its centre (of 7,434 km²), its districts | 6 (3 names) | -- | 122 KB | 45 KB |
| Q15174 | Shenzhen | the city 12 km round Futian (of 1,997 km²), its districts | 6 (2 names) | -- | 149 KB | 55 KB |
| Q5826 | Xi'an | the city 8 km round the Bell Tower (the walled city and round it), its districts | 6 (3 names) | -- | 54 KB | 21 KB |
| Q30002 | Chengdu | the city 9 km round Tianfu Square, its districts | 6 (3 names) | -- | 105 KB | 40 KB |
| Q4970 | Hangzhou | the city 8 km round West Lake's east shore, its districts | 6 (1 names) | -- | 82 KB | 32 KB |
| Q189633 | Guilin | the city 7 km round its centre (the Li River's karst hills), its districts | 6 (3 names) | -- | 49 KB | 19 KB |
| Q1461 | Manila | the city and Makati, its business district | 9 (5 names) | -- | 34 KB | 13 KB |
| Q1850 | Phnom Penh | the capital (679 km²), its 14 khan | 6 (14 names) | -- | 74 KB | 28 KB |
| Q11711 | Siem Reap | the municipality 7 km round the town and Angkor Wat (its relation out over the Tonlé Sap) | none | -- | 23 KB | 9 KB |
| Q3037 | Kathmandu | the metropolitan city (50 km²; its 32 numbered wards not drawn) | none | KTM | 45 KB | 17 KB |
| Q35381 | Colombo | the municipal council (37 km²) | 9 (38 names) | -- | 45 KB | 17 KB |
| Q9347 | Malé | the city (Malé island, Hulhulé's airport and Hulhumalé, Villimalé) | none | MLE | 20 KB | 8 KB |
| Q33935 | Tel Aviv | the city (Tel Aviv-Yafo, 52 km²) | none | -- | 35 KB | 15 KB |
| Q1218 | Jerusalem | the municipality (126 km²) | none | -- | 54 KB | 22 KB |
| Q3805 | Amman | the governorate 8 km round the citadel (no relation for the Greater Amman Municipality) | none | -- | 44 KB | 16 KB |
| Q3692 | Riyadh | the governorate 12 km round the centre (Al Bathaa, Masmak) | 10 (73 names) | -- | 77 KB | 30 KB |
| Q374365 | Jeddah | the governorate 10 km round the centre | 10 (43 names) | -- | 42 KB | 16 KB |
| Q35484 | Medina | the governorate 6 km round the Prophet's Mosque | 10 (42 names) | -- | 26 KB | 10 KB |
| Q3826 | Muscat | the governorate 10 km round Muttrah and Ruwi | 10 (8 names) | -- | 20 KB | 7 KB |
| Q994 | Tbilisi | the city (504 km²), its districts | none | -- | 141 KB | 51 KB |
| Q1953 | Yerevan | the city (223 km²), its 12 districts | none | -- | 40 KB | 15 KB |
| Q9248 | Baku | the city (its relation of no wikidata, "r<id>") 9 km round the centre (of 2,140 km², Absheron's) | none | -- | 32 KB | 12 KB |
| Q269 | Tashkent | the city (335 km²), its 12 tumani | 6 (14 names) | TAS | 109 KB | 40 KB |
| Q5753 | Samarkand | the city (120 km²) | none | SKD | 28 KB | 11 KB |
| Q3820 | Beirut | the governorate (the city, 20 km²), its 12 quarters | 7 (12 names) | -- | 29 KB | 12 KB |
| Q190165 | Luang Prabang | its district 4 km round the old town (the peninsula between the Mekong and the Nam Khan) | none | LPQ | 10 KB | 4 KB |
| Q26600 | Fukuoka | the city (343 km²), its 7 wards | 8 (7 names) | FUK | 144 KB | 52 KB |
| Q181966 | Naha | the city (Okinawa's capital, 41 km²) | none | OKA | 34 KB | 12 KB |
| Q37951 | Sapporo | the city (1,121 km², its mountains with it), its 10 wards | 8 (10 names) | -- | 132 KB | 50 KB |
| Q34664 | Hiroshima | the city (907 km²), its 8 wards | 8 (8 names) | -- | 210 KB | 73 KB |
| Q11506 | Denpasar | the city and the Kuta kecamatan south of it (the beach, Legian, the airport), their kecamatan | 6 (4 names) | DPS | 76 KB | 27 KB |
| Q3274172 | Ubud | its kecamatan (the town, its rice terraces and villages) | none | -- | 18 KB | 7 KB |
| Q3630 | Jakarta | the capital region (664 km²; the Thousand Islands left out, far), its 5 kota | 5 (4 names) | HLP | 139 KB | 50 KB |
| Q7568 | Yogyakarta | the city (32 km², the kraton at its heart) | none | -- | 29 KB | 11 KB |
| Q1353 | Delhi | the Municipal Corporation's city and New Delhi | none | -- | 151 KB | 57 KB |
| Q66485 | Jaipur | the Municipal Corporation | none | -- | 30 KB | 11 KB |
| Q1156 | Mumbai | the City and the Suburban districts (603 km²), the corporation's zones | 9 (6 names) | BOM | 129 KB | 47 KB |
| Q60 | New York | Manhattan and Brooklyn (239 km²; the other three boroughs left out, residential) | 10 (13 names) | -- | 144 KB | 52 KB |
| Q61 | Washington | the District (177 km²) | 9 (8 names) | DCA | 92 KB | 31 KB |
| Q23768 | Las Vegas | Clark County 8 km round the middle of the Strip (the Strip lies in unincorporated Paradise, not the | none | LAS | 46 KB | 14 KB |
| Q18094 | Honolulu | the census place (boundary=place: the city-county takes in all of Oahu), Waikiki its core | 10 (14 names) | HNL | 48 KB | 19 KB |
| Q100 | Boston | the city (232 km² with its harbour), its neighborhoods | none | BOS | 96 KB | 34 KB |
| Q34404 | New Orleans | the parish-city 8 km round the French Quarter (the rest marsh and lake) | none | -- | 37 KB | 14 KB |
| Q1297 | Chicago | the city 10 km round the Loop (606 km² whole: its South and West sides residential) | 10 (27 names) | -- | 91 KB | 32 KB |
| Q8652 | Miami | the city and Miami Beach over Biscayne Bay (South Beach, Art Deco) | none | MIA | 52 KB | 18 KB |
| Q49233 | Orlando | Orange County 14 km round International Drive -- downtown, Universal, Walt Disney World's parks (in Bay Lake, not the city) | 8 (5 names) | -- | 159 KB | 60 KB |
| Q65 | Los Angeles | the county 14 km round Mid-Wilshire -- downtown, Hollywood, Beverly Hills, Santa Monica, LAX (the city alone 1300 km², without the last three) | 8 (7 names) | LAX | 114 KB | 38 KB |
| Q62 | San Francisco | the city-county 8 km round Twin Peaks (its relation takes in the bay, the sea, the Farallones) | none | -- | 54 KB | 20 KB |
| Q16552 | San Diego | the city 9 km round downtown (964 km² whole), Balboa Park, Old Town, Mission Bay | none | SAN | 62 KB | 22 KB |
| Q5083 | Seattle | the city (217 km² of land) | none | -- | 82 KB | 28 KB |
| Q1345 | Philadelphia | the city-county (370 km²), PHL in its south-west | 10 (36 names) | PHL | 144 KB | 52 KB |
| Q172 | Toronto | the city 10 km round downtown (630 km² whole) | 9 (10 names) | YTZ | 84 KB | 31 KB |
| Q340 | Montreal | the city (365 km² of its island), its arrondissements | 10 (19 names) | -- | 105 KB | 38 KB |
| Q2145 | Quebec | the city (485 km²), its arrondissements | 9 (6 names) | YQB | 102 KB | 38 KB |
| Q24639 | Vancouver | the city (115 km²: Stanley Park, Gastown, Granville Island) | 9 (22 names) | -- | 54 KB | 19 KB |
| Q1489 | Mexico City | the capital 10 km round the Zócalo (1485 km² whole, mostly mountain and sprawl), its alcaldías | 6 (7 names) | MEX | 94 KB | 34 KB |
| Q8969 | Cancún | the city and its Hotel Zone strip | none | CUN | 79 KB | 28 KB |
| Q989988 | Playa del Carmen | the town, Fifth Avenue its core | 10 (19 names) | -- | 43 KB | 15 KB |
| Q131429 | Oaxaca City | the municipality of Oaxaca de Juárez, the colonial centre | none | -- | 44 KB | 16 KB |
| Q1563 | Havana | the province 9 km round the centre, its municipios | 6 (7 names) | -- | 44 KB | 17 KB |
| Q3306 | Panama City | the district 8 km round the centre (2000 km² whole, forest), its corregimientos | 8 (11 names) | -- | 39 KB | 15 KB |
| Q3070 | San José | the canton (45 km²), its distritos | 8 (11 names) | -- | 42 KB | 16 KB |
| Q2467 | Nassau | New Providence (207 km², the island the city covers), Paradise Island, cut 14 km round the city (its relation reaches out over far cays) | none | NAS | 47 KB | 18 KB |
| Q34820 | Santo Domingo | the Distrito Nacional (104 km²) | none | -- | 28 KB | 11 KB |
| Q1568095 | Punta Cana | Higüey municipality 11 km round Bávaro -- the resort coast from Cap Cana to Arena Gorda | none | PUJ | 19 KB | 7 KB |
| Q41211 | San Juan | the municipio (199 km² with its lagoons), Old San Juan the core | 9 (18 names) | SJU | 44 KB | 17 KB |
| Q2868 | Lima | the province 9 km round San Isidro -- the Centro Histórico, Miraflores, Barranco -- its districts | 8 (17 names) | -- | 57 KB | 21 KB |
| Q5582862 | Cuzco | the province 5 km round the Plaza de Armas -- Sacsayhuamán above it, CUZ -- its districts | 8 (1 names) | CUZ | 33 KB | 13 KB |
| Q1486 | Buenos Aires | the city (203 km²: its level-8 relation, the level-4 one runs out into the Río de la Plata), its 48 barrios | 10 (3 names) | AEP | 66 KB | 24 KB |
| Q8678 | Rio de Janeiro | the city 10 km round the Centro (1200 km² whole) -- Copacabana, Ipanema, Corcovado, Sugarloaf | none | SDU | 90 KB | 33 KB |
| Q174 | São Paulo | the city 10 km round the Sé (1521 km² whole) | none | CGH | 122 KB | 43 KB |
| Q2887 | Santiago | the Provincia de Santiago 9 km round the Plaza de Armas, its comunas (Santiago, Providencia, Las Condes...) | 8 (15 names) | -- | 77 KB | 28 KB |
| Q2841 | Bogota | the capital 10 km round Chapinero's south (its district 1600 km² out to the páramo of Sumapaz), its localidades | 8 (15 names) | -- | 76 KB | 27 KB |
| Q48278 | Medellín | the municipality 8 km round the centre (380 km² whole, its rural corregimientos), its comunas | 9 (19 names) | EOH | 58 KB | 21 KB |
| Q657461 | Cartagena | the district 6 km round the walled city -- Getsemaní, Bocagrande, San Felipe -- (600 km² whole, its islands) | none | CTG | 30 KB | 11 KB |
| Q2900 | Quito | the canton 9 km round the Centro Histórico (4200 km² whole), its parroquias | 9 (20 names) | -- | 60 KB | 23 KB |
| Q1335 | Montevideo | the city (the department's level-8 urban part), its municipios | 10 (32 names) | -- | 62 KB | 23 KB |
| Q85 | Cairo | the Cairo and Giza governorates 12 km round the Nile -- downtown, Islamic Cairo, Giza's pyramids -- names in English | none | -- | 161 KB | 56 KB |
| Q130514 | Luxor | the governorate 6 km round the Nile -- Karnak and Luxor temples, the west bank to the Valley of the Kings | none | -- | 12 KB | 5 KB |
| Q187284 | Hurghada | the Red Sea governorate 10 km round the town (its relation the whole coast) | none | HRG | 16 KB | 6 KB |
| Q644 | Sharm El Sheikh | South Sinai 10 km round Naama Bay -- Old Sharm to the airport | none | SSH | 12 KB | 4 KB |
| Q101625 | Marrakesh | the commune (230 km²), its arrondissements | 10 (5 names) | RAK | 36 KB | 13 KB |
| Q7903 | Casablanca | the commune, its arrondissements | 9 (8 names) | -- | 47 KB | 17 KB |
| Q80985 | Fez | the commune, its arrondissements | 10 (6 names) | -- | 31 KB | 11 KB |
| Q126148 | Tangier | the commune | none | -- | 39 KB | 15 KB |
| Q3551 | Rabat | the commune | 10 (5 names) | -- | 39 KB | 15 KB |
| Q170525 | Agadir | the commune, the bay's beach and the kasbah hill | none | -- | 32 KB | 11 KB |
| Q3572 | Tunis | the governorate (346 km²: the city, La Marsa, Carthage, Sidi Bou Said, the lake), its délégations | none | TUN | 71 KB | 27 KB |
| Q3561 | Algiers | the wilaya 9 km round the centre, its communes | 8 (27 names) | -- | 78 KB | 29 KB |
| Q5465 | Cape Town | the metro 10 km round the City Bowl -- the V&A Waterfront, Table Mountain, Sea Point, Camps Bay, Kirstenbosch -- (2450 km² whole) | 10 (16 names) | -- | 57 KB | 22 KB |
| Q34647 | Johannesburg | the metro 10 km round Braamfontein -- the CBD, Maboneng, Melville, Rosebank, Sandton's edge | 10 (36 names) | -- | 70 KB | 27 KB |
| Q5468 | Durban | eThekwini 8 km round the centre -- the Golden Mile, the harbour, Berea | 10 (12 names) | -- | 53 KB | 20 KB |
| Q3870 | Nairobi | the county 9 km round the CBD -- Westlands, Kilimani, the National Park's edge -- (696 km² whole) | 9 (10 names) | -- | 63 KB | 23 KB |
| Q2222874 | Zanzibar City | the Mjini district (16 km²), Stone Town its core | none | -- | 7 KB | 2 KB |
| Q3929 | Port Louis | the district (42 km²: the harbour, the Caudan Waterfront, the Citadel) | 9 (7 names) | -- | 32 KB | 13 KB |
| Q3761 | Accra | the city, its neighbourhoods | none | ACC | 28 KB | 11 KB |
| Q8673 | Lagos | the state 10 km round Lagos Island -- Ikoyi, Victoria Island, Lekki's start, the mainland to Yaba -- its LGAs | 6 (6 names) | -- | 38 KB | 14 KB |
| Q3718 | Dakar | the département (the Cap-Vert peninsula's tip, 79 km²), its communes d'arrondissement | 8 (19 names) | -- | 31 KB | 12 KB |
| Q3624 | Addis Ababa | the chartered city (527 km²), its sub-cities | 6 (10 names) | ADD | 71 KB | 26 KB |
| Q3859 | Kigali | the city 8 km round the centre (730 km² whole) | none | -- | 27 KB | 9 KB |
| Q3935 | Windhoek | the municipality 7 km round the centre (5000 km² whole, its farmland), its suburbs | none | -- | 31 KB | 11 KB |
| Q214681 | Panaji | Tiswadi and Bardez talukas 10 km round Panaji -- the capital, Old Goa's churches, the beaches of Candolim and Calangute | none | -- | 88 KB | 32 KB |
| Q5764 | Bukhara | the city (Buxoro shahri), the old town's lanes and madrasas | none | -- | 20 KB | 7 KB |
| Q1930 | Ottawa | the city 8 km round Parliament Hill (2790 km² whole) | 9 (8 names) | -- | 57 KB | 21 KB |
| Q274120 | Niagara Falls | the Ontario city, the falls and Clifton Hill | none | -- | 40 KB | 16 KB |
| Q277408 | Tulum | the town, the ruins on the cliff | none | -- | 15 KB | 6 KB |
| Q3130 | Sydney | Greater Sydney (boundary=place, 12000 km²) 10 km round the harbour -- the CBD, the Opera House, Bondi, Manly, Taronga -- its LGAs | 6 (36 names) | SYD | 153 KB | 55 KB |
| Q3141 | Melbourne | Greater Melbourne (boundary=place) 9 km round the CBD -- Fitzroy, St Kilda, the Bay -- its LGAs | 6 (5 names) | -- | 115 KB | 41 KB |
| Q34932 | Brisbane | the City of Brisbane 9 km round the CBD (1340 km² whole), South Bank | none | -- | 103 KB | 36 KB |
| Q3183 | Perth | the City of Perth (20 km²: the CBD, Northbridge, Kings Park, the river front) | none | -- | 26 KB | 10 KB |
| Q140075 | Gold Coast | the city 10 km round Surfers Paradise (its 1300 km² out into the hinterland) | 9 (26 names) | -- | 95 KB | 34 KB |
| Q189133 | Cairns | the region 6 km round the Esplanade (its 1700 km² of rainforest), CNS | 9 (15 names) | CNS | 36 KB | 13 KB |
| Q37100 | Auckland | the region 9 km round the CBD (its 5000 km² out over the gulf's islands) | 8 (5 names) | -- | 94 KB | 33 KB |
| Q23661 | Wellington | Wellington City (290 km²), its suburbs | none | WLG | 81 KB | 29 KB |
| Q79990 | Christchurch | the city (boundary=place), its suburbs | 8 (5 names) | -- | 78 KB | 29 KB |
| Q613684 | Queenstown | the Queenstown-Lakes district 7 km round the town, Lake Wakatipu | none | ZQN | 18 KB | 7 KB |
| Q35493 | Almaty | the city 10 km round the centre (its 680 km² up into the Tian Shan) | none | -- | 60 KB | 21 KB |
| Q23430 | Ulaanbaatar | the capital 9 km round Sükhbaatar Square (its 4700 km² of steppe) | none | -- | 29 KB | 10 KB |
| Q1555 | Guatemala City | the municipio 8 km round the Zona 1 centre, La Aurora's GUA | 8 (18 names) | GUA | 57 KB | 21 KB |
| Q212773 | Antigua Guatemala | the municipio 4 km round the Parque Central (its volcano slopes cut) | none | -- | 13 KB | 5 KB |
| Q36947 | Salvador | the município 10 km round the Pelourinho (its 690 km² north to the airport cut) | none | -- | 74 KB | 27 KB |
| Q48344 | Recife | the município (218 km²), Recife Antigo, Boa Viagem | none | REC | 94 KB | 34 KB |
| Q43463 | Fortaleza | the município (314 km²), the beach front | none | FOR | 74 KB | 28 KB |
| Q132997 | Florianópolis | the município 9 km round the centre (the island's south and north beaches cut) | 9 (7 names) | -- | 55 KB | 21 KB |
| Q202316 | Foz do Iguaçu | the município (620 km²: the town, the park, the falls), IGU | none | IGU | 54 KB | 21 KB |
| Q1491 | La Paz | the municipio 7 km round the Plaza Murillo (its 470 km² down the Zongo valley cut) | 9 (5 names) | -- | 56 KB | 20 KB |
| Q637555 | Montego Bay | Saint James parish 5 km round the town, the Hip Strip | none | MBJ | 18 KB | 7 KB |
| Q2248586 | Krabi | Mueang Krabi district 9 km round between the town and Ao Nang's beach (Railay at the edge) | none | -- | 29 KB | 11 KB |
| Q13025347 | Ko Samui | the island's city municipality (230 km²), Chaweng, Lamai | none | USM | 48 KB | 18 KB |
| Q203370 | Ayutthaya | its amphoe 5 km round the island (the old capital's temples, Wat Chaiwatthanaram over the river) | 8 (17 names) | -- | 50 KB | 17 KB |
| Q131620 | Natal | the município (167 km²), Ponta Negra, the Forte dos Reis Magos | 9 (6 names) | -- | 68 KB | 25 KB |
| Q36167 | Huế | the city (5000 km² since 2025) 6 km round the Citadel, the Perfume River, the tombs south cut | none | -- | 34 KB | 13 KB |
| Q138640987 | Nha Trang | its four wards (since the 2025 reform: Nha Trang, Bắc, Nam, Tây), the beach front | none | -- | 43 KB | 16 KB |
| r19272141 | Hạ Long | the Hạ Long ward round Bãi Cháy, the bay's first islands | none | -- | 11 KB | 4 KB |
| Q1800 | Kochi | its taluk 7 km round Ernakulam -- Fort Kochi, Mattancherry over the water | none | -- | 25 KB | 10 KB |
| Q1352 | Chennai | the corporation 10 km round George Town (Marina Beach, Mylapore) | 9 (7 names) | -- | 78 KB | 29 KB |
| Q10086 | Mysuru | its taluk 6 km round the palace, Chamundi Hill | none | -- | 29 KB | 10 KB |

- **The city** is its boundary relation's area and nothing round it: everything is cut to that outline but the city's
  airport (the busiest by passengers of `data/airports.csv` within 50 km, `AIRPORT_KM`: CDG not Orly, MXP not Linate),
  drawn whole wherever it is, and the metro's and commuter lines, drawn on to their ends out of the city (within
  `OUT_KM`, 60 km) with their stations (their route relations
  whole: `Q_ROUTES`). The page cuts the map's own rivers, roads and railways out of the outline and the airport (the
  file's `@clip`), so they end where the city's begin, and draws the map round them as it was. `data/city/index.csv`
  (`wikidata`, `name`, `w`, `s`, `e`, `n`, `bytes`) gives the box of the outline and the airport: where a city's file
  applies, known without reading it, and all the page reads until it is zoomed in on one.
- **One line for one road**: the streets, and a railway's tracks of one kind and colour, go through the map's own
  `build/roadnet.py` (collapse, gaps, joins: The main lines, above) at a city's scale (`SCALE`): a stretch within 50 m
  of a street kept before (30 m for a track) is the same road -- a dual carriageway's other roadway, a canal's other
  bank (Berlin's Lützowufer) -- dropped where it runs beside it for 150 m, its cut ends and every free end within 30 m
  carried onto the line it meets. Each line is then simplified between its junctions, which stay where they are, so
  the streets meet; a street is one line over its bridges (OSM's bridge ways are not cut out of it), and `@bridges`
  are its stretches on one, drawn over it cased dark.
- **The old town's lanes** (`@lanes line`, `name`): the named pedestrian, living_street, residential, unclassified,
  footway and steps ways within `CORE_KM` (1.5 km) of the city's middle, or the spec's `core` ([lon, lat, km]: Venice
  2.4 km round Rialto for its calli, Rome 2.4 km to take in the Vatican); not a sidewalk's or crossing's footway, nor a
  square's area. Each street's ways are merged into lines by name, simplified to 3 m, cut to the outline, and
  drawn thin and white under the streets from street zoom (under 30 m a pixel), named below 12 m. They come from the
  pbf (part `lanes`) for a city read from one, else from Overpass; when Overpass is busy the city is built without
  them and asked again on the next build. This fills the centres the main classes leave empty: Florence between the
  Duomo and the Uffizi, the Stradun, Bruges inside its ring.
- **What is in it**: streets (OSM motorway, trunk, primary, secondary; `name`, `ref`, `class`); commuter lines (`s`:
  S-Bahn, RER and Transilien, Overground and the Elizabeth line, Cercanías, Rodalies, the FL and S lines, Esko,
  Marmaray, the AKN, the МЦК, the Circumvesuviana, Cumana and Circumflegrea, the Metro do Porto, HSL's trains, BG:Voz,
  Turin's SFM, Euskotren ... -- `COMMUTER_NET` on a route's network, operator or name, `COMMUTER_REF` on its ref),
  metros (`u`) and main railways (`r`: the route relations' ways -- `rail`, `subway`, `light_rail`, `narrow_gauge`
  (the Circumvesuviana), not `tram`, nor a street's `railway=razed` or `abandoned` (Dresden's old tram streets) -- and
  `usage=main/branch` tracks without `service`), with the route's `colour` and `lines`; green (parks,
  gardens, meadows, grass, cemeteries, allotments 5 ha+; woods and heath 10 ha+; merged); water (lakes, rivers' and
  canals' own areas, 0.5 ha+); the named rivers and canals as lines; the monuments of `data/monuments.csv` in the city
  that OSM maps as an area (by their `wikidata`: a closed way with an area's tag or a multipolygon, not a site relation)
  of 60 m across or more (the square root of its area; up to 300 ha) -- filled and outlined, named, without their icon;
  a gate, a column, a church stays a point; the districts' outlines (`level` 1 and 2; a district over half within the
  outline, not a neighbour's sliver; the outline's parts 40 km+ from the city's point left out: Hamburg's Neuwerk) and
  their names at a label point inside; the airport (`aeroway=aerodrome` with its IATA code) as an outline; stations
  (`railway=station/halt`, a node or a station's area; not a car train's or goods' station: "Товарный", "Kravas",
  "Preču") within 600 m of one name one point -- one name in the other ("Hbf" or not), or the same name without the
  town's and the words for a station ("Paris Austerlitz", "Gare d'Austerlitz"), or one's such words all in the other's
  ("Wien Hauptbahnhof", "Südtiroler Platz – Hauptbahnhof"), or an interchange's halves by number ("Piața Victoriei 1"
  and "2": "Piața Victoriei") -- named as the one the most trains stop at (Saint-Lazare, not its RER station next door);
  `kind` the lines there: `u`, `s`, `r`; `rank` 1 the city's busiest (its train routes, commuter lines' too, counted at
  the nearest station of each stop: at least 6 and a quarter of the busiest's, among the 10 busiest in the city; a
  long-distance route -- `service=long_distance/high_speed/international` -- counts three, so an InterCity terminus
  outranks a commuter line's halts: Dublin Heuston) or a DB category 1-2 or a Hauptbahnhof, 2 at least 3 and a tenth, or
  two kinds of line, 3 the rest; a station is kept only with a line of the map within 80 m, out of the city only an U-
  or S-Bahn's); the names of parks of 15 ha+ and lakes of 10 ha+.
- **The format** is the light text format (`build/lite.py`, Light files above): a `grid`, `@arcs`, then `@streets line`,
  `@bridges line`, `@lanes line`, `@rail line`, `@green polygon`, `@sea polygon`, `@water polygon`, `@waterways line`, `@airport polygon`,
  `@monuments polygon`, `@districts line`, `@clip polygon` (an object without rows left out: an empty one breaks the
  page's trees), and the tables `@places`, `@parks`, `@stations` (CSV with
  `lon`, `lat`). Simplified to 10 m (streets, rail), 12 m (water), 15 m (districts), 25 m (green), 20 m (airport), 5 m
  (monuments, the clip), on a grid of 1/20,000 degree (5.5 m); a polygon is a row a piece, so the page fills only
  those in view.
- **Drawn** in the map's own pipeline (`js/city.js`, called from `js/view.js`): the fills and strokes go to the
  painters like every other layer; a street is cased, widths grow with the zoom; secondary streets from 70 m a pixel;
  the second district level dashed from 50 m. While the map moves the city's casings and bridges and the map's own
  lines under it are left out, so a pinch keeps to the painters' chunks; the file is read only at rest (as
  `roads.txt`) and let go 3 minutes after the map has left the city. Names by priority: main stations, districts,
  main streets (along the line), the other stations, parks and lakes, Ortsteile, secondary streets, rivers. The
  monuments and the airport show in a city map whatever their switches say; the city map itself does not follow the
  layer switches (rivers, roads, rails).
- **The sea**: a coastal city's sea is the outline's box cut by OSM's coastlines (the land on a coastline's left),
  each face the side most of its coastline's segments say, kept within 1.5 km of the outline (`SEA_KM`, less than
  `PAD_KM`, the data's margin) as `@sea`, drawn in the map's own sea colour (`--sea`, so it does not show as a band
  over the base map's sea; the lakes, rivers and docks on it keep the city's water colour): the map's own land is coarser (Istanbul's Bosporus and Marmara shore,
  Barcelona's port, Ostia). The districts' borders and their names' label points are cut by that sea too (no
  border out in the Saronic Gulf off Piraeus). A sea over 60% of the outline is taken for a coast read the wrong way
  round and left out, unless the city's point is on land (Helsinki's outline is mostly sea, out to Ulkosaaret).
- **Sizes**: a city's file is kept to 150 KB gzipped (`BUDGET_KB`): over it, it is built again coarser -- the
  simplify tolerances times f, the smallest areas times f² (`COARSER`: 1.25 to 4; the first step guessed from the
  size, the step taken kept in `raw/city/<wikidata>_coarser.json` for the next build). London (x3.4) and Istanbul (x2.8)
  needed it; the rest are 3-145 KB at x1. Green is the largest part.
- **Where the data comes from**: a city with a `pbf` is read from Geofabrik's extract (`build/citypbf.py`, pyosmium,
  four passes: the relations; the boundary's ways and nodes for its box; the nodes and ways with their places --
  `flex_mem` under 400 MB, a node index on disk above it), downloaded once to `raw/city/pbf/` and deleted when no
  other city needs it. Overpass (three servers in turn, retries with back-off, big boxes asked in tiles) is for the
  others. Both write the same raw parts (`raw/city/<wikidata>_*.json.gz`: boundary, districts, lines, areas, routes,
  stops, airport, monuments). An extract takes 1-4 minutes (England's, 1.7 GB: about 25); built again from the raw
  parts, a city takes under a minute (London a few, with its coarser builds). One city's failure (no boundary that
  closes: Agra's district, 38 of its 53 ways without their nodes in the raw part) is printed as `<wikidata>: FAILED -- ...` and the others
  are still built; `index.csv` lists the files there are. Outside Europe every city is read from a pbf (Overpass was
  down through the build); a pbf's raw parts kept, a change of `radius`, `place` or `airport` is built again without
  it, a change of `boundary` needs the parts deleted and the extract back.

## How the detail was chosen

- **Simplified on the sphere, not in degrees** (`build/geo.py`). Douglas–Peucker with each point's distance to the
  great-circle segment, tolerance 0.5 km. Nothing dropped is more than 0.5 km from what replaces it, at every
  latitude and in every projection.
- **Straight lines keep only what they need.** A border along a meridian keeps its two ends. A border along a
  parallel (the 49th between the US and Canada) keeps a point every ~130 km: a parallel is not a great circle, and
  without those points a renderer that draws edges as great-circle arcs (d3, any globe) would bow it 90 km north.
- **Every landmass stays a valid polygon.** Where simplifying would make a coast cross itself or another ring of
  the same landmass (a spit, a lagoon, a channel narrower than the detail), OSM's own points are kept at that spot
  -- only there. (A landmass that is not valid cannot be cut into its countries.)
- **Borders meet.** A border's end on the coast is joined to the coast's own vertex (the nearest within 1 km; within
  5 km for an end that meets no other line -- a border that stops short of a river mouth). Where a border is drawn
  in pieces with a gap (Mont Blanc's disputed summit splits France–Italy), loose ends within 5 km are joined by a
  straight line. A border along the coast, or the same border from two sources, is kept once.
- **Islands under 1 km² are left out**, as are smaller lagoons (813,000 of OSM's 833,000 land polygons; they are
  dots at this scale).
- **Edges are "the shortest way over the globe"** (d3-geo's convention) and are short (≤ a few km on coasts), so a
  planar tool drawing them straight in degrees draws the same thing.
- **Winding**: outer rings clockwise, holes anticlockwise (longitude/latitude, north up), as d3-geo and TopoJSON's
  world-atlas expect. `build/export_geojson.py` writes RFC 7946 GeoJSON, wound the other way.
- **The antimeridian and the pole**: landmasses are cut at ±180° (and Antarctica closes along the pole), as OSM's land
  polygons are. Those cut edges belong to `land` and `countries`, so fills close, but not to `coastline`.

## Sources and licences

| data | source | licence |
|---|---|---|
| coast, islands | OSM land polygons, [osmdata.openstreetmap.de](https://osmdata.openstreetmap.de/data/land-polygons.html) (the OSM coastline, assembled daily) | ODbL |
| countries, dependencies, states and their borders | [Overture Maps](https://overturemaps.org) divisions, release 2026-09-23.1 (OSM boundary relations; `division_area`, `division_boundary`) | ODbL |
| rivers, lakes | Overture Maps base/water (OSM `waterway=river`, `water=river` areas, lakes and reservoirs) | ODbL |
| cities | OSM `place=city` / `place=town` nodes via Overpass; population from their tag, else Wikidata P1082; the urban population from the English Wikipedia article's infobox (`population_urban`); the classes of a place by a big city from Wikidata (P31) | ODbL / CC0 / CC BY-SA (a number) |
| monuments | Wikidata: visitors per year (P1174), coordinates (P625), kind (P31/P279), Wikipedia articles, World Heritage (P1435) (via WDQS and QLever) | CC0 |
| airports | [OurAirports](https://ourairports.com/data/) (airports, scheduled service); [OpenFlights](https://openflights.org/data) routes (2014) | public domain; ODbL |
| first-class roads | OSM's `highway=trunk` via Overture Maps' transportation theme | ODbL |
| main lines | OSM via Overpass: `highway=motorway`, `highway=trunk` + `maxspeed`, `railway=rail` + `usage=main` / `highspeed=yes`, `man_made=pipeline` + `substance` | ODbL |
| ecoregions, biomes, realms | [RESOLVE Ecoregions 2017](https://ecoregions.appspot.com/) (Dinerstein et al. 2017, *BioScience* 67:534), `build/fetch_bio.sh` | CC BY 4.0 |
| historical borders | [CShapes 2.0](https://icr.ethz.ch/data/cshapes/) (Schvitz, Girardin, Rüegger, Weidmann, Cederman, Gleditsch 2022, *Journal of Conflict Resolution* 66:144), the shapes from its shapefile, `status` and `owner` from the copy in its R package, `build/fetch_history.sh` | **CC BY-NC-SA 4.0** (non-commercial) |
| historical borders before 1886 | [historical-basemaps](https://github.com/aourednik/historical-basemaps) (A. Ourednik and contributors): the world as mapped for 3000 BC … 1880, `NAME`, `SUBJECTO`, `BORDERPRECISION` | **GPL-3.0** |
| historical events | Wikidata: what an event is (P31/P279), its date (P585, else P580, else P571, with precision and calendar), place (P625, else its location's, P276), what it is part of (P361), Wikipedia articles (via QLever), `build/events.py` | CC0 |
| wars and campaigns; rivers' lengths, areas' areas | Wikidata: part of (P361), start and end (P580, P582), what it is (P31); length (P2043), area (P2046), normalised to SI (via QLever) | CC0 |
| tectonic plates | P. Bird 2003, *An updated digital model of plate boundaries*, G³ 4(3):1027 (PB2002), as converted by H. Ahlenius ([fraxen/tectonicplates](https://github.com/fraxen/tectonicplates)), `build/fetch_plates.sh` | ODC-By 1.0 |
| time zones | [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) 2026f (E. Siroky and contributors; OSM boundaries), with the oceans; offsets from the IANA tz database (tzdata 2026f) | ODbL; public domain |
| parks' areas | OSM multipolygons via [QLever](https://qlever.dev/osm-planet) (osm2rdf) | ODbL |
| areas, natural points, river names | [Natural Earth](https://www.naturalearthdata.com) 1:10m physical: marine polygons, geographic regions, elevation points, region points, rivers | public domain |

The derived data is a database built from OSM, so it is ODbL:
"© OpenStreetMap contributors, Overture Maps Foundation". Layer 14 (`full/history.topo.json`, `data/history.txt`)
is CShapes' and historical-basemaps' as well and keeps their licences: CC BY-NC-SA 4.0 (not for commercial use, shared
alike, with "CShapes 2.0, ETH Zurich ICR (Schvitz et al. 2022)") and GPL-3.0 ("historical-basemaps, A. Ourednik").

## Building

Needs Python 3 and about 40 GB of disk for `raw/` and `work/` while building. Everything else goes into `.venv/`.

**Memory**: every step reads its big input a piece at a time (DuckDB with a memory limit, rows in small batches, the
rivers tile by tile) and peaks at 1.3–1.9 GB. Run them through `build/capped.sh`, which puts the step in a systemd
scope with a hard memory cap (`MEM=2200M` by default, no swap): past it the step is killed, not the PC. Run them one
at a time. (A running step's cap can be raised: `systemctl --user set-property --runtime run-….scope MemoryMax=…`.)

```
python3 -m venv .venv && .venv/bin/pip install shapely duckdb scipy requests ijson
build/fetch_raw.sh                           # raw/: OSM land polygons, Overture divisions (~6 GB)
.venv/bin/python build/fetch_water.py        # raw/water.parquet: rivers and big lakes (streams ~20 GB, ~1 h); raw/water_more.parquet: the other big water areas (lagoons)
.venv/bin/python build/fetch_points.py       # raw/: OSM cities and towns, Wikidata visitors and fame, airports
.venv/bin/python build/fetch_transport.py    # raw/transport/: main roads, railways, pipelines (Overpass, 10° tiles, resumes; ~6 h, 450 MB)
build/fetch_ne.sh                            # raw/ne/: Natural Earth's geography layers and rivers (~15 MB)
build/fetch_bio.sh                           # raw/ecoregions/: RESOLVE's ecoregions (150 MB zip, 240 MB shapefile)
build/fetch_plates.sh && .venv/bin/python build/plates.py   # raw/plates/ -> data/plates.json: the tectonic plates (layer 16, 1 MB in, a second)
build/capped.sh .venv/bin/python build/coast.py      # stage 1: the coast, simplified, border ends found on it (~10 min, 1.9 GB)
build/capped.sh .venv/bin/python build/topology.py   # stage 2: borders joined, simplified, faces labelled (~8 min, 1.5 GB)
MEM=1800M build/capped.sh .venv/bin/python build/water.py   # stage 4: lakes (work/) and rivers as tracked (full/rivers.tracked.topo.json) (~40 min, 1.5 GB)
MEM=2600M build/capped.sh .venv/bin/python build/water.py lagoons   # (only the lagoons, ~1 min, put after the lakes again: then write.py, rivernet.py, lite.py, small.py)
build/capped.sh .venv/bin/python build/areas.py      # stage 6: areas on the topology (work/areas.pkl), data/natural_points.csv (~18 min, 1.4 GB)
build/capped.sh .venv/bin/python build/areas.py islands   # stage 6b: + every other landmass Wikidata knows as an island (~10k; never leave it out)
build/capped.sh .venv/bin/python build/write.py      # stage 3: full/world.topo.json (with the areas)
build/capped.sh .venv/bin/python build/rivernet.py   # stage 4b: the rivers as one network (full/rivers.topo.json), their mouths into the coast
.venv/bin/python build/riverlevels.py                # stage 4c: each river's level 1-3 (its width drawn); Wikidata's lengths cached in raw/wd_river_length.json
build/capped.sh .venv/bin/python build/points.py     # stage 5: data/cities.csv, monuments.csv, airports.csv
build/capped.sh .venv/bin/python build/transport.py  # stage 7: the main lines as tracked (full/transport.tracked.topo.json) (~16 min, 1.9 GB)
build/capped.sh .venv/bin/python build/roadnet.py   # stage 7b: one network of single lines, ranked (full/transport.topo.json)
.venv/bin/python build/fetch_roads.py        # raw/roads.parquet: trunk and primary roads, of which build/roads.py takes trunk (Overture, a part at a time, resumes; ~1 h, 180 MB)
.venv/bin/python build/roads.py              # stage 7c: first-class roads, by cell, beside the motorways (full/roads.topo.json)
build/capped.sh .venv/bin/python build/bio.py        # stage 9: full/bio.topo.json (ecoregions, biomes, realms)
build/fetch_history.sh                       # raw/cshapes/: CShapes 2.0 (13 MB zip) and its R package's TopoJSON; raw/basemaps/: 38 maps (47 MB)
build/capped.sh .venv/bin/python build/admin.py      # Overture's administrative lines and units -> work/admin_*.pkl (~50 min, once)
build/capped.sh .venv/bin/python build/history.py    # stage 10: full/history.topo.json (~70 min, 1.8 GB, two cuts; ~14 min with work/history_faces.pkl)
.venv/bin/python build/events.py             # raw/wd_events.json (QLever, ~2 min) -> data/events.csv
.venv/bin/python build/campaigns.py          # raw/wd_partof.json (QLever, ~1 min) -> data/campaigns.json (wars, moves)
.venv/bin/python build/measures.py           # data/measures.json (QLever): rivers' lengths, areas' areas (rankings)
.venv/bin/python build/lite.py               # data/*.txt: light copies of the line layers (~1 min)
.venv/bin/python build/citymaps.py          # data/city/: the city detail maps (Overpass, raw/city/ caches; [Q64 ...] only those)
.venv/bin/python build/small.py              # data/*.txt mended, data/small/, data/xsmall/: every layer for small maps (~3 min)
.venv/bin/python build/timezones.py         # full/timezones.topo.json (raw/timezones/: the release's with-oceans GeoJSON, 56 MB zip; ~40 s, 0.4 GB)
.venv/bin/python build/parks.py             # full/parks.topo.json (QLever's OSM planet; raw/parks/ caches)
.venv/bin/python build/lite.py 1 25 timezones parks && .venv/bin/python build/small.py timezones parks   # their copies alone
.venv/bin/python build/export_geojson.py     # optional: data/geojson/*.geojson
```

Every number that decides the detail is in `build/config.py`.

## Limits

- **Names** of lakes and rivers are English where the feature (or another piece of the same local name) has a
  Wikidata item with an English label; else OSM's own. `name_local` keeps OSM's. A piece whose item is called as it
  is votes too (the Colorado's US ways); an item named with a qualifier in brackets ("Colorado River (Maule)") names
  only its own pieces (so Chile's Colorado items do not name Argentina's Río Colorado).
  A river with no item on any of its ways finds it by name and place -- also without its word for river ("Río Paraná":
  the Paraná River's item), or from a river of the same name within ~30 km that has one (a stretch cut off from the
  rest); a river is then called by its item's English name. Natural Earth's English names stand in where OSM's ways
  have neither item nor English name, but not for `NE_WRONG` (`build/water.py`): its one "Paraná" line runs on up the
  Paraguay. A river goes on into a way whose name holds its own as a whole word -- two letters are enough: the Po into
  "Fiume Po" and its delta's "Po di Venezia"... -- or that has its item.
- **Areas** (layer 7) are Natural Earth's at 1:10m: their lines across are rough on purpose, and they are only as
  complete as its list (1,341 named seas, gulfs, straits, ranges, deserts, peninsulas, islands…).
- **Airports**' international routes are OpenFlights' of 2014 (the newest free list); a large airport newer than
  that (Berlin's) is kept by its size. Their passengers are Wikidata's (P3872): the most of an airport's last five
  years of counts, so not a year of the pandemic; 117 of 948 have none (level 3).
- **Main lines** are what OSM tags: a railway without `usage=main`, a trunk road without `maxspeed`, a pipeline
  without `substance` is not there. A road or railway is drawn once (above): two different lines within 600 m of
  each other for 2 km (a high-speed line beside the old one) are drawn as one, the more important kept (where they part
  for less than 1 km, the other is not drawn there either).
- **Rivers** are measured, not tagged. A stretch counts where the river area OSM maps around its centerline is
  50 m wide or more (twice the distance from the centerline to the nearer bank). A wide river that OSM maps only as a
  line, without its area, is missed.
- **Visitor numbers** are only as complete as Wikidata's P1174 (and, where it has none, the English Wikipedia
  infobox's `visitation_num`), and counts are of different years (`visitors_year`); the sites without one -- most
  of them -- are there, and take their level, by how many Wikipedias write about them.
- **Disputed borders** are OSM's. Each area goes to the country whose boundary relation holds it (a dependency before
  its sovereign), and the disputed lines are flagged in `country_borders`.
- **Population** is whatever OSM's `population` tag says (the year when tagged), else Wikidata's latest -- rounded to
  two significant digits (193,456 -> 190,000; 1,215,026 -> 1,200,000), since the counts are of different years and
  kinds. It is the URBAN population where the English Wikipedia article's infobox gives one (`population_urban`, up
  to 3x the municipal count: Larnaca is a town of 52,000 in a built-up area of 130,000, so it is in; Tokyo's 39
  million); else the municipality's as OSM counts it. Only that one number is kept, not where it came from.
  A capital is always kept, with the larger of OSM's and Wikidata's counts (Muscat's OSM node is its old town).
- **Districts** of a big city that OSM maps as cities (Istanbul's, Tokyo's wards, New York's boroughs) are left out:
  a place within 2.5 km x sqrt(population / 100,000) of a city of a million (municipal counts) and under a fifth of
  its size, unless Wikidata's classes for it say it is a city or municipality of its own and not a district (Kawasaki
  and Saitama by Tokyo, Kunshan by Suzhou; the Ruhr's cities are each other's neighbours, none of them a million).
  A bigger place there goes only when Wikidata calls it a district (Harbin's Daoli, Shanghai's Pudong, Gaziantep's
  Şahinbey: 181 such dropped in October 2026). And any place Wikidata knows as a PART of a city -- a suburb, a ward,
  a city's district (China's, Turkey's), a South African township, a region of Brasília -- unless it is also a city or
  town of its own, or a capital (344 more; `build/points.py` city_parts). Places Wikidata gives as an administrative
  area named after its main town (a Chinese county, an upazila, a kecamatan, a Nigerian LGA) stay, though their
  population is the area's, not the town's alone.
