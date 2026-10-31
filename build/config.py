"""What the map keeps: every number that decides the detail, and which countries are split into their states."""

EPS_KM = 0.5            # the simplification: no dropped point is more than this from the line that replaces it
FINE_KM = 0.1           # the intermediate simplification kept on disk (re-simplified finer where lines would cross)
MIN_ISLAND_KM2 = 1.0    # land smaller than this is left out (at 1 km detail it would be a dot)
MIN_CONTINENT_KM2 = 5e6  # a landmass this big is a continent (Australia's 7.6 million km2 the smallest; Greenland, 2.1, an island)
MIN_HOLE_KM2 = 1.0      # ...and so are smaller inland seas and lagoons cut out of the land
SNAP_KM = 1.0           # a border's end this close to the coast is joined to it
LOOSE_KM = 5.0          # ...and one that meets no other line, this close -- or, off the coast, to another such end
MIN_LAKE_KM2 = 45.0     # lakes this big are drawn (Ammersee, 46 km2, the smallest wanted)
QUANT_DEG = 0.0025      # the output grid: 1/400 degree, 278 m of latitude -- a quarter of the detail

# THE STATES AND PROVINCES (layer 3): which countries are drawn with their first-level divisions (Overture's regions)
# -- decided by build/topology.py (region_countries()) by this rule:
#   * a federation (or a devolved state) always;
#   * any other country when its divisions are big enough to see: on average MIN_STATE_KM2 or more -- the fewer the
#     better (Malawi's 3 regions, Serbia's 2 are kept; Denmark's 5 regions, 8,600 km2, and Greece's 14, 9,400, are
#     about the smallest) -- and at least MIN_STATES (one would be the country again);
#   * any country of MIN_COUNTRY_KM2 or more (the size of North Macedonia, 25,700 km2, and up) whose divisions are on
#     average MIN_SMALL_STATE_KM2 or more (Romania's 42 counties, Ireland's 26, Albania's 12) -- not Azerbaijan's 80
#     districts (1,100 km2), Latvia's 42, Taiwan's 22, North Macedonia's own 71 municipalities;
#   * or a country of MIN_STATES_PEOPLE or more (Japan's 47 prefectures, Thailand's 77 provinces, South Korea's 16);
#   * never one of NO_STATES.
MIN_STATES = 2
MIN_STATE_KM2 = 8500.0
MIN_COUNTRY_KM2 = 25000.0
MIN_SMALL_STATE_KM2 = 2000.0
MIN_STATES_PEOPLE = 40e6
FEDERAL = [                 # (by ISO 3166-1 alpha-2)
    "US", "CA", "MX", "BR", "AR", "VE",                         # the Americas
    "KN",
    "RU", "DE", "AT", "CH", "BE", "BA", "GB",                   # Europe (the United Kingdom devolved)
    "IN", "PK", "MY", "NP", "IQ", "AE",                         # Asia
    "ET", "NG", "SO", "SS", "SD", "KM",                         # Africa
    "AU", "FM",                                                 # Oceania
]
# A STATE DRAWN IN PARTS (build/topology.py): England has no first-level division in Overture, only its 152 counties and
# unitary districts -- its nine regions (ONS) are the counties put together: {state: (its name, {part: (name, Wikidata
# item, the counties)})}. A part's code is ours (ISO 3166-2 has none), its people and the like are its item's.
STATE_PARTS = {"GB-ENG": ("England", {
    "GB-ENG-NE": ("North East England", "Q47983", [
        "Northumberland", "Newcastle upon Tyne", "North Tyneside", "South Tyneside", "Gateshead", "Sunderland", "County Durham",
        "Darlington", "Hartlepool", "Stockton-on-Tees", "Middlesbrough", "Redcar and Cleveland"]),
    "GB-ENG-NW": ("North West England", "Q47967", [
        "Cumbria", "Lancashire", "Blackpool", "Blackburn with Darwen", "Bolton", "Bury", "Manchester", "Oldham", "Rochdale", "Salford",
        "Stockport", "Tameside", "Trafford", "Wigan", "Knowsley", "Liverpool", "St. Helens", "Sefton", "Wirral", "Halton", "Warrington",
        "Cheshire East", "Cheshire West and Chester"]),
    "GB-ENG-YH": ("Yorkshire and the Humber", "Q48063", [
        "North Yorkshire", "York", "East Riding of Yorkshire", "Kingston upon Hull, City of", "North Lincolnshire", "North East Lincolnshire",
        "Barnsley", "Doncaster", "Rotherham", "Sheffield", "Bradford", "Calderdale", "Kirklees", "Leeds", "Wakefield"]),
    "GB-ENG-EM": ("East Midlands", "Q47994", [
        "Derby", "Derbyshire", "Nottingham", "Nottinghamshire", "Leicester", "Leicestershire", "Rutland", "Lincolnshire", "Northamptonshire"]),
    "GB-ENG-WM": ("West Midlands", "Q48038", [
        "Herefordshire, County of", "Shropshire", "Telford and Wrekin", "Staffordshire", "Stoke-on-Trent", "Warwickshire", "Worcestershire",
        "Birmingham", "Coventry", "Dudley", "Sandwell", "Solihull", "Walsall", "Wolverhampton"]),
    "GB-ENG-EE": ("East of England", "Q48006", [
        "Bedford", "Central Bedfordshire", "Luton", "Cambridgeshire", "Peterborough", "Essex", "Southend-on-Sea", "Thurrock", "Hertfordshire",
        "Norfolk", "Suffolk"]),
    "GB-ENG-LD": ("London", "Q23306", [
        "Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden", "City of London", "Croydon", "Ealing", "Enfield", "Greenwich",
        "Hackney", "Hammersmith and Fulham", "Haringey", "Harrow", "Havering", "Hillingdon", "Hounslow", "Islington", "Kensington and Chelsea",
        "Kingston upon Thames", "Lambeth", "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames", "Southwark", "Sutton",
        "Tower Hamlets", "Waltham Forest", "Wandsworth", "Westminster"]),
    "GB-ENG-SE": ("South East England", "Q48015", [
        "Bracknell Forest", "Reading", "Slough", "West Berkshire", "Windsor and Maidenhead", "Wokingham", "Buckinghamshire", "Milton Keynes",
        "East Sussex", "Brighton and Hove", "Hampshire", "Southampton", "Portsmouth", "Isle of Wight", "Kent", "Medway", "Oxfordshire", "Surrey",
        "West Sussex"]),
    "GB-ENG-SW": ("South West England", "Q48026", [
        "Bath and North East Somerset", "Bournemouth, Christchurch and Poole", "Bristol, City of", "Cornwall", "Isles of Scilly", "Devon", "Plymouth",
        "Torbay", "Dorset", "Gloucestershire", "North Somerset", "Somerset", "South Gloucestershire", "Swindon", "Wiltshire"]),
})}
# ...and the lines between parts that no county boundary gives: {state: [((part, part), [lon, lat...])]} -- the Thames below
# London, land on the coast's maps as far as Tilbury, and with no line in Overture between Thurrock and Kent
PART_LINES = {"GB-ENG": [
    (("GB-ENG-LD", "GB-ENG-SE"), [(.211, 51.49), (.218, 51.48)]),
    (("GB-ENG-EE", "GB-ENG-SE"), [(.218, 51.48), (.245, 51.472), (.275, 51.459), (.305, 51.4675), (.335, 51.4535), (.365, 51.449), (.395, 51.449),
                                  (.425, 51.453), (.455, 51.483), (.485, 51.4945), (.503, 51.4994)]),
]}
PART_CODES = {p for _, parts in STATE_PARTS.values() for p in parts}

NO_STATES = ["GL", "UG"]    # (Greenland: five municipalities, all ice; Uganda: its ISO 3166-2 divisions are its 135
                            #  districts, 1,800 km2 on average -- Overture has only the four regions above them)

OVERTURE_RELEASE = "2026-09-23.1"

# a dependency's sovereign (Overture's areas give only the dependency's own code)
SOVEREIGN = {
    "PF": "FR", "WF": "FR", "CP": "FR", "BL": "FR", "GP": "FR", "MQ": "FR", "GF": "FR", "PM": "FR", "YT": "FR", "RE": "FR", "TF": "FR", "NC": "FR", "MF": "FR",
    "CK": "NZ", "NU": "NZ", "TK": "NZ",
    "AS": "US", "PR": "US", "VI": "US", "UM": "US", "GU": "US", "MP": "US",
    "PN": "GB", "KY": "GB", "TC": "GB", "BM": "GB", "VG": "GB", "FK": "GB", "GS": "GB", "SH": "GB", "AI": "GB", "MS": "GB", "GI": "GB",
    "JE": "GB", "GG": "GB", "IM": "GB", "IO": "GB",
    "AW": "NL", "CW": "NL", "BQ": "NL", "XE": "NL", "XS": "NL", "SX": "NL",
    "GL": "DK", "FO": "DK",
    "XJ": "NO", "BV": "NO", "SJ": "NO",
    "AX": "FI",
    "HM": "AU", "CC": "AU", "CX": "AU", "NF": "AU",
    "MO": "CN", "HK": "CN",
}

# THE SMALL COPIES (build/small.py): data/<size>/*.txt -- every line layer for small maps, from data/*.txt:
#   decimals -- the coordinates kept to so many decimals of a degree (the grid: 2 -> 0.01 degree, 1.1 km of latitude);
#   grid_km  -- the detail: a point closer than this to the line between its neighbours, in a triangle with them
#               under grid_km squared, is left out (build/lite.py's Visvalingam-Whyatt);
#   min_km2  -- a ring smaller than this (an island, a lake, a hole, an enclave) is left out, and its coast with it.
SIZES = {
    "small":  {"decimals": 2, "grid_km": 5.0, "min_km2": 25.0},
    "xsmall": {"decimals": 1, "grid_km": 25.0, "min_km2": 625.0},
}
# ...and of the lines only what the map shows at that copy's scales (index.html: LINE_TIERS, the rivers' lengths): {object: (column, keep it?)}
ROW_LIMITS = {
    "small":  {"motorways": ("tier#", lambda t: t <= 2), "roads": ("tier#", lambda t: t <= 2), "railways": ("tier#", lambda t: t <= 2), "pipelines": ("tier#", lambda t: t <= 2)},
    "xsmall": {"motorways": ("tier#", lambda t: t <= 1), "roads": ("tier#", lambda t: t <= 1), "railways": ("tier#", lambda t: t <= 1), "pipelines": ("tier#", lambda t: t <= 1),
               "rivers": ("river_km#", lambda km: km >= 250)},
}
