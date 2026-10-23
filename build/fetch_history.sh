#!/bin/sh
# The world's states and dependencies, for build/history.py:
#  - from 1886 to 2019: CShapes 2.0 (Schvitz et al. 2022, ETH Zurich ICR, CC BY-NC-SA 4.0), one polygon per
#    country-period, with its dates. The shapes are the shapefile's; the status of each period (independent, colony,
#    protectorate, mandate, occupied) and the state ruling it are only in the copy the R package carries (a TopoJSON,
#    its periods the same).
#  - before: historical-basemaps (github.com/aourednik/historical-basemaps, GPL-3.0), the world as mapped for 3000 BC,
#    2000 BC ... 1880 (raw/basemaps/world_*.geojson).
cd "$(dirname "$0")/../raw" && mkdir -p cshapes && cd cshapes || exit 1
[ -s CShapes-2.0.zip ] || curl -sSfL -o CShapes-2.0.zip https://icr.ethz.ch/data/cshapes/CShapes-2.0.zip || exit 1
[ -s CShapes-2.0.shp ] || unzip -oqj CShapes-2.0.zip || exit 1
[ -s cshapes_2.0.tar.gz ] || curl -sSfL -o cshapes_2.0.tar.gz https://cran.r-project.org/src/contrib/cshapes_2.0.tar.gz || exit 1
[ -s cshapes_2_gw.topojson ] || tar xzOf cshapes_2.0.tar.gz cshapes/inst/extdata/cshapes_2_gw.topojson.xz | xz -d > cshapes_2_gw.topojson || exit 1
cd .. && mkdir -p basemaps && cd basemaps || exit 1
for y in bc3000 bc2000 bc1500 bc1000 bc700 bc500 bc400 bc323 bc300 bc200 bc100 bc1 100 200 300 400 500 600 700 800 900 1000 \
         1100 1200 1279 1300 1400 1500 1530 1600 1650 1700 1715 1783 1800 1815 1878 1880; do
  [ -s world_$y.geojson ] || curl -sSfL -o world_$y.geojson https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_$y.geojson || exit 1
done
[ -s LICENSE ] || curl -sSfL -o LICENSE https://raw.githubusercontent.com/aourednik/historical-basemaps/master/LICENSE || exit 1
echo FETCHED
