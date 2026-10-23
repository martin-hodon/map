"""What the map keeps: every number that decides the detail, and which countries are split into their states."""

EPS_KM = 0.5            # the simplification: no dropped point is more than this from the line that replaces it
FINE_KM = 0.1           # the intermediate simplification kept on disk (re-simplified finer where lines would cross)
MIN_ISLAND_KM2 = 1.0    # land smaller than this is left out (at 1 km detail it would be a dot)
MIN_HOLE_KM2 = 1.0      # ...and so are smaller inland seas and lagoons cut out of the land
SNAP_KM = 1.0           # a border's end this close to the coast is joined to it
LOOSE_KM = 5.0          # ...and one that meets no other line, this close -- or, off the coast, to another such end
MIN_LAKE_KM2 = 100.0    # lakes this big are drawn
QUANT_DEG = 0.0025      # the output grid: 1/400 degree, 278 m of latitude -- a quarter of the detail

# THE STATES AND PROVINCES (layer 3): for the countries that are big, many, or federal -- by ISO 3166-1 alpha-2.
# (Every country over ~500,000 km2 or ~40 million people, and the federations and devolved states among the rest.)
REGION_COUNTRIES = [
    # the Americas
    "US", "CA", "MX", "BR", "AR", "CO", "PE", "VE", "BO", "CL",
    # Europe
    "RU", "UA", "DE", "FR", "ES", "IT", "PL", "GB", "AT", "CH", "BE", "SE", "NO", "FI", "RO", "BA",
    # Asia
    "CN", "IN", "ID", "PK", "BD", "JP", "PH", "VN", "TH", "MM", "MY", "KR", "IR", "IQ", "SA", "TR", "KZ", "MN", "AF", "UZ", "AE",
    # Africa
    "NG", "ET", "EG", "CD", "ZA", "TZ", "KE", "SD", "SS", "DZ", "LY", "MA", "AO", "ML", "NE", "TD", "SO",
    # Oceania
    "AU", "NZ", "PG",
]

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
