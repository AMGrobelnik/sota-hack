#!/bin/bash
# Re-run gf180 layouts on the lab's official fix: two docker workers, default clock, one batch.
export CHIPLAB_USER_DIR=~/projects/sota-hack/.worktrees/_m3/chiplab-home
export CHIPLAB_CONFIG=~/projects/sota-hack/.worktrees/_m3/chiplab-home/config.json
export DOCKER_HOST=unix://~/.colima/default/docker.sock
export CHIPLAB_DOCKER_WORKERS=2
cd ~/projects/sota-hack/.worktrees/m3-layouts/chiplab || exit 1
nohup ~/projects/sota-hack/.worktrees/m3-layouts/chiplab/.venv/bin/chiplab workers > ~/projects/sota-hack/.worktrees/_logs/m3-layouts-workers.log 2>&1 &
sleep 8
~/projects/sota-hack/.worktrees/m3-layouts/chiplab/.venv/bin/chiplab submit-batch --json '{"tool":"layout","args_list":[{"design_id":"765fa47586bd","pdk":"gf180","core_util":25},{"design_id":"261bd9ee3b04","pdk":"gf180","core_util":25},{"design_id":"174157d29a95","pdk":"gf180","core_util":25}]}'
