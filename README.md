# World layers at 1 km

World map data built from public sources, OpenStreetMap first, at about **1 km of detail**. Lines are simplified on
the globe to 0.5 km and stored on a 1/400° grid. Everything is longitude/latitude (WGS 84) with no projection
applied, so any projection can draw it. `index.html` shows it in nine projections.

| # | layer | file · object | what |
|---|---|---|---|
| 1 | geographical | `full/world.topo.json` · `land`, `coastline`, `lakes` | every landmass and island of 1 km² or more, the coast as lines, lakes of 100 km² or more |
| 2 | national borders | `full/world.topo.json` · `countries`, `country_borders` | countries and dependencies as polygons, which reuse the coast, with `population` (Wikidata's latest, by ISO 3166-1 code, two significant digits), `area_km2`, `density`, `language` (`language_code`), `color` (0-6, no two neighbours alike), `label` (a point well inside: where its name is written) and `continent` (the continent area of layer 7 its label lies in, else the nearest); the land borders as lines (`a`, `b`, `disputed`) |
| 3 | subnational | `full/world.topo.json` · `regions`, `region_borders` | states / provinces (ISO 3166-2) of the big and federal countries (`build/config.py` `REGION_COUNTRIES`), with `population` (by ISO 3166-2 code), `area_km2`, `density`, `language`, `label`, `continent` (its own: Russia's European oblasts are in Europe) |
| 4 | rivers | `full/rivers.topo.json` · `rivers` | each river that is 50 m wide somewhere, from its source down to its end, as one line (or more at forks), 50 km or longer, big or known to Wikipedia: name (English), Wikidata id, width (median and max), `river` (its id), `river_km`, `wikipedias` |
| 5 | monuments | `data/monuments.csv` | castles, palaces, cathedrals, temples, ruins, monuments, bridges, dams, national parks, waterfalls… with 100,000+ visitors a year, or well known (written about in enough Wikipedias -- 15+ for a castle, 12+ a bridge, 10+ a dam or a World Heritage Site, 40+ a church: `build/fetch_points.py` FAMOUS), one a line under a header: `name`, `lon`, `lat`, `kind`, `visitors`, `visitors_year`, `wikipedias`, `country`, `region`, `name_local`, `wikidata`, `osm` |
| 6 | cities | `data/cities.csv` | cities of 100,000+ people and every capital, one a line under a header: `name`, `lon`, `lat`, `population` (the urban one where Wikipedia gives it, two significant digits), `place` (city, town), `capital` (country, state), `country`, `region` (state), `name_local`, `wikidata`, `osm` -- without the districts of a bigger city (Istanbul's, Tokyo's wards, New York's boroughs, China's urban districts) |
| 7 | areas | `full/world.topo.json` · `areas` | the named parts of the world without borders of their own: oceans, seas, gulfs, bays, straits, sounds, fjords; mountain ranges, plateaus, deserts, plains, basins, peninsulas, islands and island groups, continents — made of the map's own coast and lines across (below) |
| 8 | natural points | `data/natural_points.csv` | peaks (with elevation), capes, waterfalls, passes, depressions, the poles, one a line under a header: `name`, `lon`, `lat`, `kind`, `elevation_m`, `rank` (Natural Earth's: shown from what zoom), `name_en`, `wikidata` |
| 9 | airports | `data/airports.csv` | airports with scheduled flights to 3+ airports abroad (large ones: 2+), one a line under a header: `name`, `lon`, `lat`, `iata`, `icao`, `city`, `size` (large, medium), `destinations_abroad`, `country`, `region` |
| 13 | biogeographic | `full/bio.topo.json` · `realms`, `biomes`, `ecoregions` | the land cut into the 847 terrestrial ecoregions (RESOLVE 2017), and those grouped into 15 biomes (with Rock and Ice) and 8 biogeographic realms: `id` (`PA`… a realm, `B0`–`B14` a biome, `E` + RESOLVE's number an ecoregion), `name`, `realm`, `biome`, `color` (RESOLVE's), `nnh`, `area_km2`, `label` -- made of the map's own coast (below) |
| 14 | historical borders | `full/history.topo.json` · `regions`, `periods` | the states, empires, dependencies (and, before them, peoples and cultures) from 3000 BC to 2019 -- from 1886 every day (CShapes 2.0), before as mapped for 3000 BC, 2000 BC … 1815, 1878, 1880 (historical-basemaps), as REGIONS of the land and their owners through time: `regions` one polygon each -- `id`, `name`, `admin`, `country`, `held` (`from:state` …), `area_km2`, `label`; `periods` one row per country-period (no geometry) -- `id` (`state:from`), `state`, `name`, `from`, `to` (days, both inclusive; years astronomical, `-0699` is 700 BC), `source`, `precision` (1 approximate, 2 partly undefined, 3 fixed by law), `status`, `owner`, `capital`, `cap`, `gwcode`, `area_km2`, `label` -- made of the map's own coast (below) |
| 15 | historical events | `data/events.csv` | battles, sieges, peace treaties and treaties, assassinations, massacres, coups, revolutions, rebellions, terror attacks, earthquakes, eruptions that enough Wikipedias write about (10+ for a battle, 8+ a peace treaty, 15+ a massacre: `build/events.py` KINDS), one a line under a header: `name`, `lon`, `lat`, `date` (cut to its precision, years astronomical), `precision` (day … century), `calendar` (julian, as historians cite a date before 1582), `kind`, `part_of` (its war or campaign), `wikipedias`, `place` (own coordinates, or its location's), `wikidata` |
| 10–12 | main lines | `full/transport.topo.json` · `motorways`, `railways`, `pipelines` | motorways and trunk roads signed 100 km/h+ (networks of 20 km+), main-line and high-speed railways (30 km+), oil and gas pipelines that are not distribution lines (50 km+), one line per road or railway (its carriageways and tracks collapsed): `ref`, `name`, `network`, `network_km` |

Layers 1–4, 7, 10–14 are **TopoJSON**: every line is stored once. The coast bounds the land, a country, a state, a
sea and a peninsula with the same arcs, and a national border is one arc shared by both countries. Coordinates are delta-encoded integers on
the `transform` grid (1/400° = 278 m of latitude). The point layers (5, 6, 8, 9, 15) are CSV tables, one point a line under
a header (`lon`, `lat` to 4 decimals).

`index.html` finds anything by name (a country, state, city, monument, airport, river, lake, sea, range, peninsula,
peak, motorway, pipeline…; a city with its country), highlights it and flies there; a click on the map lists what is
at that spot; `#find=Alps` and `#at=46.5,10.5[,zoom]` link to one. It draws only what is in view (each layer in an
R-tree), in levels of detail (topojson-simplify, the coarsest still finer than a pixel), and while the wheel turns it
only scales the last picture, and while the map is dragged it only shifts it (drawn again with its labels once the
movement pauses); it zooms to 300x (100 m a pixel). Points come by zoom, in tiers (`TIERS`): at the whole globe only
the cities of 10 million (a capital counts three times its people), from 2.5x those of 3 million, 5x 1 million, 8x
300,000, 14x all; the 25 best-known monuments from 5x (150 from 8x, 800 from 12x, all from 20x), the highest-ranked
peaks and capes from 4x, the airports with 100 destinations abroad from 5x (30 from 8x, all from 14x), the day's 15
best-known events from 4x (60 from 6x, 250 from 10x, all from 18x). The selection goes with the panel's x, or by emptying the search
box (its x, Escape). Two maps: POLITICAL (countries coloured, their borders and their states') and GEOGRAPHICAL
(the areas coloured by kind -- ocean, sea, gulf; mountains, plateau, desert, plain, delta, tundra... -- and no
political line), LANGUAGES (each country and state by its first official language: `language`, `language_code`
-- a state's own where Wikidata gives one, else its country's -- the widest-spoken in distinct colours) and
POPULATION DENSITY (`density`, people per km², from `population` and `area_km2`, the polygons' area on the sphere);
the natural lines and the other layers are on all (`#mode=geographical` links to one). Countries are coloured by a class (`color`, 0-6:
no two neighbours the same, neighbours sharing a border or within 1° -- `build/write.py props` recomputes it, with the populations) with
a palette to pick (pastel, light, muted, vivid, dark, earth, greys, none; kept in the browser). With layer 3 on, each state is
filled in a shade of its country's colour (Lab lightness steps of 5, no two neighbouring states of one country alike, by
the shared arcs), so countries differ by hue and the states within one only by lightness. On the political, language and
density maps the countries' names are written at their `label` in spaced capitals (the bigger first, more the closer in)
and, with layer 3, the states' in mixed case, fading in from closer in; `build/write.py places` adds `label` and
`continent` to the file alone. On the historical map the day's states are named the same way, and with layer 3 the
provinces and dependencies within one (a period with an `owner`: the Duchy of Swabia in the Empire, a colony) get a
thin inner border and fading italic names. With layer 4 on, the rivers are named along their flow, in blue italics
beside a stretch of the line that runs nearly straight (letter by letter, reading left to right), again every 350 px of
a river: those of 1,000 km and more from zoom 4, 300 km from 6, 100 km from 9, the rest from 12 (`RIVER_NAMES`).
R rolls the panel up (or down again), as its ▴ does.

THE GAME (the button top right): a game on the cities (layer 6) of the whole world, a continent or a country. While its
panel is open the map shows no names but those of the cities named or found, and no points, roads or railways; each
start begins afresh.
- **Their people:** name cities (English or local name, accents and case aside; of several of one name, the biggest
  there); their people add up, as a share of all the people there (a continent's: each country's, shared out by its
  states' -- so the cities of Russia's European oblasts count for Europe).
- **Outside every circle / inside a circle:** each city named gets a circle (so many km across, 500 for the world,
  300 a continent, 100 a country to start with); the next must lie outside every circle -- or inside one.
- **Find the city:** the game names one of the biggest cities there (300 of the world's, 150 of a continent's; of
  these, one a country, so China's do not fill the game), a click says where it is; a circle round the city out to the
  click shows how far off (0 km is best), and the kilometres add up over the rounds.

The countries' games: the countries of the world or a continent (with those that have a state in it: Russia, Turkey
and Kazakhstan are Europe's too), or a country's states (of the 67 countries the map has states for). A name is
taken in English or the local one, and for a country also as often called (UK, USA, Czech Republic, Burma...). Two
are neighbours if they share a land border; a dependency's borders count for its country (France borders Brazil),
and the countries round a disputed piece (Bir Tawil) border each other across it. Named ones are filled green, missed
or shown ones violet.
- **Which one is this?** The map flies to one and outlines it; you name it (so many rounds; Show gives it away).
- **Name them all:** every one named is filled in, against the clock; Give up shows those left.
- **Neighbour chain:** from a random start, each one named must border the last, none twice; it ends when the last
  has no neighbour left (or with End, which says what was still possible).
- **From one to another:** a start and a goal 2–6 countries apart; each one named must border one named before, and
  it is done when the goal borders one; the end says how many the shortest way goes through (Show a way gives one).

## Offline copy, updates, prepared data

On a real site (http/https) the map keeps itself in the browser: `sw.js` (a service worker) keeps every file
`offline.json` lists -- `index.html`, its libraries in `lib/` (d3, d3-geo-projection, topojson-client, topojson-simplify,
rbush, kept here rather than on a CDN so the map opens offline), `data/lite/*.txt` and the CSVs, 34 MB -- and the map
opens from that copy, with no network and nothing downloaded again. It does not update on its own: once a visit the page
compares its version with `offline.json` online, and a newer one shows a line at the top with **update now** (the
version kept and **check for update** are also at the panel's foot). An update fetches the new files whole, into a new
copy, and drops the old one; the groups, mode and other settings (localStorage) stay.

What the page makes of the files before it can draw -- each line layer read and presimplified, the R-trees of the
layers' bounds -- is kept in IndexedDB (`map` / `prepared`) under the copy's version, so a later visit reads it back
(measured on a desktop: reading and preparing the five line layers 4.1 s -> 2.2 s, the R-trees 1.6 s -> 0.3 s).

After changing what the page loads (`build/lite.py`, a point layer, `index.html`, `lib/`): `python3 build/offline.py`
writes `offline.json` (the file list and a hash of the files: the version), then commit and push.

## Light files (data/lite/)

`build/lite.py` writes smaller, readable copies of the line layers -- `data/lite/world.txt`, `rivers.txt`,
`transport.txt`, `bio.txt`, `history.txt` -- from the full-detail ones in `full/`, and leaves those as they are. The map
loads ONLY these (and the CSV point layers in `data/`): `data/` is what is committed and served. `full/` -- the build's
full-detail `*.topo.json` (tens of MB each), and `full/old/` the files they superseded -- is not committed
(`.gitignore`); it is what the light files are rebuilt from.

- **Fewer points.** A point goes when it adds little to the shape: where the line hardly turns, the triangle it makes
  with its neighbours is small (Visvalingam-Whyatt, the smallest first, up to 25 km²) -- but a point more than 1 km
  off the line between its neighbours always stays, so a fjord's end, a cape or a border's corner keeps its shape.
  Every shared line is simplified once with its ends fixed: borders and coast still meet exactly. About half the
  points go (world 1.45 M -> 0.74 M, rivers 0.65 M -> 0.34 M); the roads, already sparse, keep 92 %.
- **A text format, nothing repeated.** `grid` (the 1/400° grid), `@arcs` (a shared line a line: its first point and
  then its steps), then each object as CSV under its own header -- a column's type in its name (`population#` a
  number, `names_local[]` a list, `highspeed?` yes/no) -- with each geometry's arcs in its last column (rings `;`,
  polygons `|`, `-1 - i` for an arc followed backwards). A river or a road network is one row with what all its pieces
  share, and its pieces (`@rivers.pieces`) only their arcs and what differs. Sizes: world 19.5 -> 9.9 MB, rivers
  13.6 -> 3.4 MB, transport 10.0 -> 4.1 MB, bio 8.2 -> 4.7 MB, history 14.4 -> 8.6 MB.

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
(Andorra, Dominica…). Dates are proleptic Gregorian, years astronomical (`-0699-01-01` is 1 January 700 BC). 14.4 MB (24 MB as one polygon per period, before the regions); the light copy
(`data/lite/history.txt`) 8.6 MB.

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
  island whose place is on it, its area agreeing);
- any other area takes the part of Natural Earth's outline (1:10m) that is on its side of the coast -- in the water
  for a sea, on the land for a range -- as lines across, ending exactly where they meet the coast (the coast arc gets
  that point and is split there). A piece of outline that runs along the coast a little off it (Natural Earth's
  coast round Lesbos, along Guinea) is the coast, not a line across, and is dropped: never farther than 3 km from
  the coast, nor than a quarter of its length (a line across a strait stands off by half its length), and from one
  point of a coast ring to another of the same ring, which then closes the face by itself (a piece along an atoll's
  chain of islets is what closes the Arabian Sea there, and stays); a line that still crosses the coast is noded
  there, or the polygonizer lets the sea into the land (the North Atlantic was lost so). Natural Earth's thin
  slivers along a coast (Yucatán Channel, Luzon Strait, La Pérouse Strait) are then left with nothing. All areas' lines are joined into one set (two seas share their line) and simplified
  to 2 km where that does not take them over the coast. The coast and those lines cut the world into faces, and an
  area is the faces on its side of the coast that are mostly inside Natural Earth's outline, and the thin slivers
  between Natural Earth's coast and the map's that border it most. A sea is water only (its islands are holes);
- a sea with no water of the map's own (the Caspian, which OSM's coast leaves to the lakes) is its lakes.

Areas overlap (the Alps are in Europe); they are listed biggest first. Each has `mask` ("water" or "land"), a
`label` point (the spot deepest inside Natural Earth's shape), `kind`, `rank` (Natural Earth's scalerank: 0 the
biggest), and its Wikidata id.

## The rivers (layer 4)

Measured, not tagged: a river is in when the river area OSM maps around its centerline is 50 m wide or more
somewhere. From there it is followed downstream to its end -- along its OSM ways in their direction (the flow), from
way to way while they share a name (English, OSM's, or one part of a two-language name: "Le Rhin / Rhein") or a
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
it, and that point is put into the coast's own line (`full/world.topo.json`; `build/lite.py` keeps it).

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
| main lines | OSM via Overpass: `highway=motorway`, `highway=trunk` + `maxspeed`, `railway=rail` + `usage=main` / `highspeed=yes`, `man_made=pipeline` + `substance` | ODbL |
| ecoregions, biomes, realms | [RESOLVE Ecoregions 2017](https://ecoregions.appspot.com/) (Dinerstein et al. 2017, *BioScience* 67:534), `build/fetch_bio.sh` | CC BY 4.0 |
| historical borders | [CShapes 2.0](https://icr.ethz.ch/data/cshapes/) (Schvitz, Girardin, Rüegger, Weidmann, Cederman, Gleditsch 2022, *Journal of Conflict Resolution* 66:144), the shapes from its shapefile, `status` and `owner` from the copy in its R package, `build/fetch_history.sh` | **CC BY-NC-SA 4.0** (non-commercial) |
| historical borders before 1886 | [historical-basemaps](https://github.com/aourednik/historical-basemaps) (A. Ourednik and contributors): the world as mapped for 3000 BC … 1880, `NAME`, `SUBJECTO`, `BORDERPRECISION` | **GPL-3.0** |
| historical events | Wikidata: what an event is (P31/P279), its date (P585, else P580, else P571, with precision and calendar), place (P625, else its location's, P276), what it is part of (P361), Wikipedia articles (via QLever), `build/events.py` | CC0 |
| areas, natural points, river names | [Natural Earth](https://www.naturalearthdata.com) 1:10m physical: marine polygons, geographic regions, elevation points, region points, rivers | public domain |

The derived data is a database built from OSM, so it is ODbL:
"© OpenStreetMap contributors, Overture Maps Foundation". Layer 14 (`full/history.topo.json`, `data/lite/history.txt`)
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
.venv/bin/python build/fetch_water.py        # raw/water.parquet: rivers and big lakes (streams ~20 GB, ~1 h)
.venv/bin/python build/fetch_points.py       # raw/: OSM cities and towns, Wikidata visitors and fame, airports
.venv/bin/python build/fetch_transport.py    # raw/transport/: main roads, railways, pipelines (Overpass, 10° tiles, resumes; ~6 h, 450 MB)
build/fetch_ne.sh                            # raw/ne/: Natural Earth's geography layers and rivers (~15 MB)
build/fetch_bio.sh                           # raw/ecoregions/: RESOLVE's ecoregions (150 MB zip, 240 MB shapefile)
build/capped.sh .venv/bin/python build/coast.py      # stage 1: the coast, simplified, border ends found on it (~10 min, 1.9 GB)
build/capped.sh .venv/bin/python build/topology.py   # stage 2: borders joined, simplified, faces labelled (~8 min, 1.5 GB)
MEM=1800M build/capped.sh .venv/bin/python build/water.py   # stage 4: lakes (work/) and rivers as tracked (full/rivers.tracked.topo.json) (~40 min, 1.5 GB)
build/capped.sh .venv/bin/python build/areas.py      # stage 6: areas on the topology (work/areas.pkl), data/natural_points.csv (~18 min, 1.4 GB)
build/capped.sh .venv/bin/python build/write.py      # stage 3: full/world.topo.json (with the areas)
build/capped.sh .venv/bin/python build/rivernet.py   # stage 4b: the rivers as one network (full/rivers.topo.json), their mouths into the coast
build/capped.sh .venv/bin/python build/points.py     # stage 5: data/cities.csv, monuments.csv, airports.csv
build/capped.sh .venv/bin/python build/transport.py  # stage 7: full/transport.topo.json (~16 min, 1.9 GB)
build/capped.sh .venv/bin/python build/bio.py        # stage 9: full/bio.topo.json (ecoregions, biomes, realms)
build/fetch_history.sh                       # raw/cshapes/: CShapes 2.0 (13 MB zip) and its R package's TopoJSON; raw/basemaps/: 38 maps (47 MB)
build/capped.sh .venv/bin/python build/admin.py      # Overture's administrative lines and units -> work/admin_*.pkl (~50 min, once)
build/capped.sh .venv/bin/python build/history.py    # stage 10: full/history.topo.json (~70 min, 1.8 GB, two cuts; ~14 min with work/history_faces.pkl)
.venv/bin/python build/events.py             # raw/wd_events.json (QLever, ~2 min) -> data/events.csv
.venv/bin/python build/lite.py               # data/lite/*.txt: light copies of the line layers (~1 min)
.venv/bin/python build/export_geojson.py     # optional: data/geojson/*.geojson
```

Every number that decides the detail is in `build/config.py`.

## Limits

- **Names** of lakes and rivers are English where the feature (or another piece of the same local name) has a
  Wikidata item with an English label; else OSM's own. `name_local` keeps OSM's. A piece whose item is called as it
  is votes too (the Colorado's US ways); an item named with a qualifier in brackets ("Colorado River (Maule)") names
  only its own pieces (so Chile's Colorado items do not name Argentina's Río Colorado).
- **Areas** (layer 7) are Natural Earth's at 1:10m: their lines across are rough on purpose, and they are only as
  complete as its list (1,341 named seas, gulfs, straits, ranges, deserts, peninsulas, islands…).
- **Airports**' international routes are OpenFlights' of 2014 (the newest free list); a large airport newer than
  that (Berlin's) is kept by its size.
- **Main lines** are what OSM tags: a railway without `usage=main`, a trunk road without `maxspeed`, a pipeline
  without `substance` is not there. A road or railway is drawn once: OSM's separate carriageways and tracks are
  collapsed -- of the lines of one road number the longest is kept, and of the others only the stretches of 1 km+
  that run more than 250 m from a kept one (`build/transport.py` TWIN_KM); two different lines side by side (a
  high-speed line beside the old one) stay two. Stubs under 1 km are dropped.
- **Rivers** are measured, not tagged. A stretch counts where the river area OSM maps around its centerline is
  50 m wide or more (twice the distance from the centerline to the nearer bank). A wide river that OSM maps only as a
  line, without its area, is missed.
- **Visitor numbers** are only as complete as Wikidata's P1174, and counts are of different years
  (`visitors_year`); the sites without one are there if enough Wikipedias write about them.
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
