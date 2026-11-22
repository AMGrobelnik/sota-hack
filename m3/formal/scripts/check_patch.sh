#!/bin/bash
# usage: check_patch.sh <patched_pkg_parent>   (a folder holding a patched copy of the chiplab package)
# 1. writes ../proposed/formal.patch from runs/patchwork/{a,b}; 2. runs the lab's formal tests against the patched copy;
# 3. runs the patched prove(golden=True) on the spike design. Lab environment as in env.sh.
W=$(cd "$(dirname "$0")/../../.." && pwd)
PW=$W/m3/formal/runs/patchwork
export PYTHONPATH=$1
export CHIPLAB_HOME=$W/chiplab/runs   # the stored designs, not <patched copy>/runs
(cd "$PW" && diff -ruN a b > "$W/m3/formal/proposed/formal.patch")
echo "[check] patch lines: $(wc -l < "$W/m3/formal/proposed/formal.patch")"
E="bash $W/m3/formal/scripts/env.sh $W/chiplab/.venv/bin/python"
$E -c 'import chiplab.verify.formal as f; print("[check] using", f.__file__)'
(cd "$W/chiplab" && $E -m pytest -q -p no:cacheprovider tests/test_formal_golden.py 2>&1 | tail -5)
$E "$W/m3/formal/scripts/lab_golden.py" 765fa47586bd "$PW/lab_golden_spike"
