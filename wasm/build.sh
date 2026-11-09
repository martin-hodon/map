#!/bin/sh
# the geometry core built for the page: wasm/ -> js/mapgeo.wasm (the wasm32 target: dnf install rust-std-static-wasm32-unknown-unknown)
set -e
cd "$(dirname "$0")"
cargo build --release --target wasm32-unknown-unknown
cp target/wasm32-unknown-unknown/release/mapgeo.wasm ../js/mapgeo.wasm
command -v wasm-opt >/dev/null && wasm-opt -O3 ../js/mapgeo.wasm -o ../js/mapgeo.wasm || true
ls -l ../js/mapgeo.wasm
