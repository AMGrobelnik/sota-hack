#!/bin/bash
# usage: iprove.sh <out_dir>   the chain recipe with the ABC iprove engine on both chips: one run with --mutants
# (soundness: every mutated golden model must FAIL), then three timed runs per chip, whole miter (no --split).
# Each run is preceded by the load average (other packages share this Mac; the load is part of the measurement).
W=$(cd "$(dirname "$0")/../../.." && pwd)
E="bash $W/m3/formal/scripts/env.sh $W/chiplab/.venv/bin/python $W/m3/formal/scripts/golden_proof.py"
for d in 765fa47586bd 0246527da711; do
  echo "[iprove] design=$d mutants loadavg=$(sysctl -n vm.loadavg)"
  $E "$d" --timeout 600 --out "${1}_mutants" --engines iprove --mutants | grep -E '"golden_proved"|"mutants_all_caught"|"wall_s": [0-9.]+,$'
  for i in 1 2 3; do
    echo "[iprove] design=$d run=$i loadavg=$(sysctl -n vm.loadavg)"
    $E "$d" --timeout 600 --out "$1" --engines iprove | grep -E '"golden_proved"|"wall_s": [0-9.]+,$' | head -2
  done
done
echo "[iprove] done"
