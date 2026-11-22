#!/usr/bin/env bash
# Simulate (against the lab's integer model) and map (sky130, gf180) the folded neuron prototypes.
# Usage: LAB_HOME=<lab install dir> bash m3/folded/proto/run_proto.sh [wtypes] [sizes]
#   defaults: wtypes "ternary uniform4", sizes "256 64 1024" (P=1 and P=4 at 256, P=1 at the other sizes)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F="$(cd "$HERE/.." && pwd)"
WTYPES="${1:-ternary uniform4}"
SIZES="${2:-256 64 1024}"
mkdir -p "$F/results"
for n in $SIZES; do
  for wt in $WTYPES; do
    ps="1"
    if [ "$n" = "256" ]; then ps="1 4"; fi
    for p in $ps; do
      gtimeout 900 bash "$F/run.sh" proto/folded_proto.py sim --n "$n" --p "$p" --wtype "$wt" --vectors 200 \
        --out "$F/results/proto_sim_${wt}_n${n}_p${p}.json" | cut -c1-300
      gtimeout 1800 bash "$F/run.sh" proto/folded_proto.py area --n "$n" --p "$p" --wtype "$wt" \
        --out "$F/results/proto_area_${wt}_n${n}_p${p}.json" | cut -c1-200
    done
  done
done
echo PROTO_DONE
