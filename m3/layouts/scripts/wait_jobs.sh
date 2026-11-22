#!/bin/bash
# Wait until the three gf180 batch jobs are no longer queued or running (max 40 min).
export CHIPLAB_USER_DIR=~/projects/sota-hack/.worktrees/_m3/chiplab-home
export CHIPLAB_CONFIG=~/projects/sota-hack/.worktrees/_m3/chiplab-home/config.json
for i in $(seq 1 240); do
  n=0
  for j in j-f40e15156c8a j-0e9464c0feb0 j-e2a977a1bebd; do
    s=$(~/projects/sota-hack/.worktrees/m3-layouts/chiplab/.venv/bin/chiplab job-status --json "{\"job_id\":\"$j\"}" | grep -o '"state": "[a-z]*"')
    echo "$(date +%T) $j $s"
    case "$s" in *queued*|*running*) n=1;; esac
  done
  [ $n = 0 ] && break
  sleep 10
done
echo FINISHED
