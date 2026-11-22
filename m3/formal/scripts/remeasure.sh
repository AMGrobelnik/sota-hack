#!/bin/bash
# usage: remeasure.sh <out_dir>   three timed runs of the final recipe per chip and engine set, one at a time,
# each preceded by the machine's load average (other jobs share this Mac; the load is part of the measurement)
W=$(cd "$(dirname "$0")/../../.." && pwd)
for d in 765fa47586bd 0246527da711; do
  for e in cec bitwuzla cec,bitwuzla; do
    for i in 1 2 3; do
      echo "[remeasure] design=$d engines=$e run=$i loadavg=$(sysctl -n vm.loadavg)"
      bash "$W/m3/formal/scripts/env.sh" "$W/chiplab/.venv/bin/python" "$W/m3/formal/scripts/golden_proof.py" "$d" \
        --timeout 600 --out "$1" --engines "$e" --split | grep -E '"golden_proved"|"wall_s": [0-9.]+,$' | head -2
    done
  done
done
echo "[remeasure] done"
