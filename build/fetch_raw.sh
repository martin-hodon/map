#!/bin/bash
# the raw downloads (raw/, ~6 GB): OSM land polygons (osmdata.openstreetmap.de) and Overture's divisions (OSM
# boundaries, areas); raw/divisions/files.txt lists the release's files (build/README: how to refresh it)
set -e
cd "$(dirname "$0")/.."
get() {   # url file: once, resumable by rerunning
  if [ ! -f "$2" ]; then curl -sS -A "welle-map-builder/0.1" --retry 5 -o "$2.part" "$1"; mv "$2.part" "$2"; fi
}
get https://osmdata.openstreetmap.de/download/land-polygons-complete-4326.zip raw/land-polygons-complete-4326.zip
while read -r key; do
  t=$(echo "$key" | grep -o "type=[a-z_]*" | cut -d= -f2)
  get "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/$key" "raw/divisions/$t-$(basename "$key")"
done < raw/divisions/files.txt
echo FETCHED
