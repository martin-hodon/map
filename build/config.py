"""What the map keeps: every number that decides the detail, and which countries are split into their states."""

EPS_KM = 0.5            # the simplification: no dropped point is more than this from the line that replaces it
FINE_KM = 0.1           # the intermediate simplification kept on disk (re-simplified finer where lines would cross)
MIN_ISLAND_KM2 = 1.0    # land smaller than this is left out (at 1 km detail it would be a dot)
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
#     about the smallest; not Slovenia's 212 municipalities nor North Macedonia's 71) -- and at least MIN_STATES (one
#     would be the country again);
#   * or a country of MIN_STATES_PEOPLE or more (Japan's 47 prefectures, Thailand's 77 provinces, South Korea's 16);
#   * never one of NO_STATES.
MIN_STATES = 2
MIN_STATE_KM2 = 8500.0
MIN_STATES_PEOPLE = 40e6
FEDERAL = [                 # (by ISO 3166-1 alpha-2)
    "US", "CA", "MX", "BR", "AR", "VE",                         # the Americas
    "KN",
    "RU", "DE", "AT", "CH", "BE", "BA", "GB",                   # Europe (the United Kingdom devolved)
    "IN", "PK", "MY", "NP", "IQ", "AE",                         # Asia
    "ET", "NG", "SO", "SS", "SD", "KM",                         # Africa
    "AU", "FM",                                                 # Oceania
]
NO_STATES = ["GL"]          # (Greenland: five municipalities, all ice)

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
