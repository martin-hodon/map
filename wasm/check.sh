#!/bin/sh
# the Rust pipeline against d3's own output: fixtures from node (fixture.mjs), compared by target/release/check
set -e
cd "$(dirname "$0")"
cargo build --release 2>&1 | grep -E "^(error|warning)" || true
i=0
for cfg in "countries 0 1400 900 1 20,-30,0" "country_borders 0 1400 900 3 -60,-20,0" "countries 0 1400 900 6 -120,-45,0" "lakes 0 1400 900 2 0,0,0" \
           "countries 1 1400 900 20 10,-48,0" "regions 2 1400 900 1 -75,20,0" "countries 3 1400 900 1 0,-90,0" \
           "countries 4 1400 900 8 -10,-50,0" "regions 4 1400 900 2 150,30,0" "country_borders 4 1400 900 12 -8,-40,0" \
           "countries 5 1400 900 1 45,45,45" "countries 6 1400 900 3 60,-30,0" "areas 6 1400 900 1 -90,89,0" \
           "regions 7 1400 900 1 -179.99,0,0" "regions 8 1400 900 1 180,0,0" "coastline 0 1400 900 4 -170,-10,0"; do
  i=$((i+1)); set -- $cfg
  node fixture.mjs data/small/world.txt $1 $2 $3 $4 $5 $6 fixtures/s$i 1 >/dev/null
  ./target/release/check fixtures/s$i
done
