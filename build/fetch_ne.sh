#!/bin/sh
# Natural Earth's physical geography at 1:10m (public domain): named seas and gulfs, mountain ranges, peninsulas...
# as polygons, and peaks, capes and waterfalls as points -- for build/areas.py.
cd "$(dirname "$0")/../raw" && mkdir -p ne && cd ne || exit 1
for f in geography_marine_polys geography_regions_polys geography_regions_points geography_regions_elevation_points rivers_lake_centerlines populated_places; do
  [ -s ne_10m_$f.geojson ] || curl -sSfL -o ne_10m_$f.geojson \
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_$f.geojson || exit 1
done
echo FETCHED
