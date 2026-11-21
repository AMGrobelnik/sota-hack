#!/usr/bin/env bash
# Rerun the whole benchmark: designs, then RUNS runs of serial (a) and batch (b, c, d), each in a fresh lab home.
# The order of a and b alternates between runs so slow drift in machine load does not favour one mode.
# Usage: bash run_all.sh <worktree> <homes_dir> <out_dir> [runs=3] [designs.json]
# Env: CHIPLAB_USER_DIR / CHIPLAB_CONFIG as for every lab command. The batch uses the lab's own CPU lane size
# (config.lanes(): cores - 1) unless CHIPLAB_CPU_WORKERS is set.
set -euo pipefail
WT=${1:?worktree}
HOMES=${2:?homes dir}
OUT=${3:?out dir}
RUNS=${4:-3}
BENCH="$WT/m3/bench"
PY="$WT/chiplab/.venv/bin/python"
DESIGNS=${5:-$OUT/designs.json}
mkdir -p "$OUT" "$HOMES"
[ -f "$DESIGNS" ] || CHIPLAB_HOME="$HOMES/screen" "$PY" "$BENCH/gen_designs.py" "$WT/chiplab/fixtures/spike_best.json" "$DESIGNS"
{
  echo "machine: $(sysctl -n machdep.cpu.brand_string), $(sysctl -n hw.ncpu) cores" \
    "($(sysctl -n hw.perflevel0.physicalcpu) performance + $(sysctl -n hw.perflevel1.physicalcpu) efficiency)," \
    "$(($(sysctl -n hw.memsize) / 1073741824)) GB, macOS $(sw_vers -productVersion)"
  echo "python: $("$PY" -V)"
  echo "yosys: $("$CHIPLAB_USER_DIR/oss-cad-suite/bin/yosys" -V)"
  echo "lab commit: $(git -C "$WT" rev-parse --short HEAD)"
  echo "cpu workers for batch (lab lanes): $("$PY" -c "from chiplab import config; print(config.lanes()['cpu'])")"
} > "$OUT/machine.txt"
for r in $(seq 1 "$RUNS"); do
  if [ $((r % 2)) -eq 1 ]; then order="serial batch"; else order="batch serial"; fi
  for m in $order; do
    h="$HOMES/r$r-$m"
    [ ! -e "$h" ] || { echo "home $h exists; use a new homes dir" >&2; exit 2; }
    mkdir -p "$h"
    echo "run $r mode $m start $(date +%H:%M:%S)"
    CHIPLAB_HOME="$h" "$PY" "$BENCH/bench.py" --mode "$m" --run "$r" --designs "$DESIGNS" --out "$OUT"
  done
done
echo "ALL DONE $(date +%H:%M:%S)"
