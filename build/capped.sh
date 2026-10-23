#!/bin/sh
# Run a build step inside a hard memory cap (a systemd user scope): past it the step is killed, instead of the whole
# PC swapping itself to a standstill. MEM overrides the cap.   build/capped.sh .venv/bin/python build/topology.py
exec systemd-run --user --scope -q -p MemoryMax="${MEM:-2200M}" -p MemorySwapMax=0 /usr/bin/time -f "peak %M KB, %e s" "$@"
