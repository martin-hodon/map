#!/bin/sh
# The terrestrial ecoregions of the world (RESOLVE Ecoregions 2017, Dinerstein et al. 2017, CC BY 4.0): 846 ecoregions
# in 14 biomes and 8 biogeographic realms, as polygons -- for build/bio.py.
cd "$(dirname "$0")/../raw" && mkdir -p ecoregions && cd ecoregions || exit 1
[ -s Ecoregions2017.zip ] || curl -sSfL -o Ecoregions2017.zip https://storage.googleapis.com/teow2016/Ecoregions2017.zip || exit 1
[ -s Ecoregions2017.shp ] || unzip -oq Ecoregions2017.zip || exit 1
echo FETCHED
