#!/bin/bash
# usage: check_iprove.sh <patched_pkg_parent>   (a folder holding a copy of the chiplab package with formal.patch AND
# formal-iprove.patch applied). Runs the lab's golden-proof tests against that copy, then the lab's own
# prove(golden=True) on the spike and the 3-head chip, three times each. Lab environment as in env.sh.
W=$(cd "$(dirname "$0")/../../.." && pwd)
export PYTHONPATH=$1
export CHIPLAB_HOME=$W/chiplab/runs   # the stored designs
E="bash $W/m3/formal/scripts/env.sh $W/chiplab/.venv/bin/python"
$E -c 'import chiplab.verify.formal as f; print("[check] using", f.__file__)'
$E -m pytest -q -p no:cacheprovider --rootdir "$W/chiplab" "$W/chiplab/tests/test_formal_golden.py" 2>&1 | tail -3
for d in 765fa47586bd 0246527da711; do
  for i in 1 2 3; do
    echo "[check] design=$d run=$i loadavg=$(sysctl -n vm.loadavg)"
    $E "$W/m3/formal/scripts/lab_golden.py" "$d" "$W/m3/formal/runs/patchwork/lab_iprove_${d}_$i" 600
  done
done
echo "[check] done"
