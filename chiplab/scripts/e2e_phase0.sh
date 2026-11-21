#!/usr/bin/env bash
# Phase 0 end-to-end through the CLI: task -> data -> propose -> train -> compile -> synth -> simulate -> evaluate.
set -euo pipefail
cd "$(dirname "$0")/.."
C=".venv/bin/chiplab"
j() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }
T=$($C define-task --json '{"name":"af_rr","dataset":"cinc2017","classes":{"neg":["N"],"pos":["A"]},"split":{"fractions":[0.7,0.15,0.15],"seed":0,"algo":"stratified-v1"},"clinical_floor":{"worst_subject_sensitivity":0.9},"budgets":{"max_gates":5000}}' | tee /dev/stderr | j '["task_id"]')
V=$($C load-data --json "{\"task_id\":\"$T\",\"frontend\":{\"name\":\"rr_intervals\"},\"window\":{\"L\":25,\"stride\":4,\"max_per_rec\":40}}" | tee /dev/stderr | j '["view_id"]')
P=$($C propose-designs --json "{\"view_id\":\"$V\",\"family\":\"intnn\",\"sampler\":\"random\",\"n\":256,\"seed\":1,\"space\":{\"L\":[8,16,24],\"bits\":[4,5,6,8],\"hidden\":[[4],[8],[16],[32]],\"encoder\":[\"uniform\",\"delta\"],\"lo\":[0],\"hi\":[2048],\"wtype\":[\"ternary\",\"binary\"]}}" | tee /dev/stderr | j '["proposal_id"]')
B=$($C train-batch --json "{\"proposal_id\":\"$P\",\"epochs\":60}" | python3 -c "
import json,sys; r=json.load(sys.stdin); print(json.dumps({k:r[k] for k in ('status','batch_id','timing') if k in r}), file=sys.stderr)
rows=[x for x in r['rows'] if x.get('cfg.hidden',[99])[0]*x.get('enc.L',99)<=128] or r['rows']
b=max(rows,key=lambda x:x['val_win_f1']); print(json.dumps(b),file=sys.stderr); print(r['batch_id'], b['k'])")
read BID K <<<"$B"
D=$($C compile-verilog --json "{\"batch_id\":\"$BID\",\"k\":$K}" | tee /dev/stderr | j '["design_id"]')
$C synthesize --json "{\"design_id\":\"$D\"}"
$C simulate --json "{\"design_id\":\"$D\",\"inputs\":\"val\"}"
$C simulate --json "{\"design_id\":\"$D\",\"inputs\":\"random\",\"n\":200000,\"device\":\"cuda\"}"
$C evaluate-clinical --json "{\"design_id\":\"$D\",\"split\":\"val\"}"
$C count-luts --json "{\"design_id\":\"$D\",\"family\":\"xc7\"}"
$C leaderboard
