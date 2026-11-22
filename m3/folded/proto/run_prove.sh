#!/usr/bin/env bash
# How far does a SymbiYosys BMC proof of folded == wired reach? Doubles n until the first timeout per weight type.
# Usage: LAB_HOME=<lab install dir> bash m3/folded/proto/run_prove.sh [timeout_s] [engine]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F="$(cd "$HERE/.." && pwd)"
T="${1:-300}"
ENGINE="${2:-smtbmc yices}"
TAG="${ENGINE// /-}"
mkdir -p "$F/results/prove"
for wt in ternary uniform4; do
  bash "$F/run.sh" proto/prove_proto.py --n 16 --wtype "$wt" --engine "$ENGINE" --timeout "$T" --mutate \
    --out "$F/results/prove/${wt}_n16_${TAG}_mutated.json"
  for n in 8 16 32 64 128 256; do
    out="$F/results/prove/${wt}_n${n}_${TAG}.json"
    bash "$F/run.sh" proto/prove_proto.py --n "$n" --wtype "$wt" --engine "$ENGINE" --timeout "$T" --out "$out"
    grep -q '"PASS"' "$out" || break
  done
done
echo PROVE_DONE
