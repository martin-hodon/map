#!/bin/sh
# raw/plates/: Peter Bird's PB2002 plate model (as converted by Hugo Ahlenius, ODC-By 1.0) -- the plates' outlines
# (GeoJSON) and the boundary steps with their classes and velocities (CSV) -- for build/plates.py
set -e
cd "$(dirname "$0")/../raw" && mkdir -p plates && cd plates
U=https://raw.githubusercontent.com/fraxen/tectonicplates/master
for f in GeoJSON/PB2002_plates.json GeoJSON/PB2002_boundaries.json original/PB2002_steps.csv original/PB2002_steps_desc.txt README.md LICENSE.md; do
  curl -sSfL -o "$(basename "$f")" "$U/$f"
done
ls -l
