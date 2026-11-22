#!/usr/bin/env bash
# Run a folded-package script with the chip lab's environment.
# Usage: LAB_HOME=<lab install dir> bash m3/folded/run.sh <script.py> [args...]
# LAB_HOME holds the existing lab install (config.json, oss-cad-suite, pdk). Results cache goes in work/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WT="$(cd "$HERE/../.." && pwd)"
: "${LAB_HOME:?set LAB_HOME to the lab install folder}"
export CHIPLAB_USER_DIR="$LAB_HOME"
export CHIPLAB_CONFIG="$LAB_HOME/config.json"
export CHIPLAB_HOME="$HERE/work/lab-home"
export CHIPLAB_CPU_WORKERS="${CHIPLAB_CPU_WORKERS:-4}"
export CHIPLAB_DOCKER_WORKERS=0
export PATH="$LAB_HOME/oss-cad-suite/bin:$PATH"
# Yosys 0.71 overflows the default 8 MB stack (SIGSEGV, exit 139) parsing the lab's one-line sum for a wide
# 4-bit matvec row (1024 terms); 64 MB is enough. See feasibility.md.
ulimit -s 65520 2>/dev/null || true
script="$1"; shift
if [ "$script" = "pytest" ]; then
  exec "$WT/chiplab/.venv/bin/python" -m pytest -p no:cacheprovider "$@"
fi
exec "$WT/chiplab/.venv/bin/python" "$HERE/$script" "$@"
