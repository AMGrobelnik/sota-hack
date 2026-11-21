#!/bin/bash
# usage: sweep.sh <jobs.txt> <out_dir> <timeout_s> <parallel>
# Each line of jobs.txt: "<design_id> <scope>:<method>"; every line is one fastgolden.py process, <parallel> at once.
# FG_MUTANT=1 in the environment: golden of a mutated IR (soundness check, every method must then FAIL).
W=$(cd "$(dirname "$0")/../../.." && pwd)
JOBS=$1; OUT=$2; T=$3; P=$4
grep -v '^#' "$JOBS" | xargs -P "$P" -L 1 gtimeout $((T + 120)) bash "$W/m3/formal/scripts/env.sh" \
  "$W/chiplab/.venv/bin/python" "$W/m3/formal/scripts/fastgolden.py" --timeout "$T" --out "$OUT"
echo "[sweep] done"
