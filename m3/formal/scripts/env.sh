#!/bin/bash
# usage: env.sh <command...>   run a command with the lab environment used for every measurement in FINDINGS.md.
# Default tools folder: the m3 packages' shared one next to the worktrees (<repo>/.worktrees/_m3/chiplab-home);
# set CHIPLAB_USER_DIR / CHIPLAB_CONFIG yourself to use another install.
W=$(cd "$(dirname "$0")/../../.." && pwd)
export CHIPLAB_USER_DIR=${CHIPLAB_USER_DIR:-$W/../_m3/chiplab-home}
export CHIPLAB_CONFIG=${CHIPLAB_CONFIG:-$CHIPLAB_USER_DIR/config.json}
exec "$@"
