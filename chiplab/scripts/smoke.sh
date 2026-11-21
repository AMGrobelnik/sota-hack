#!/usr/bin/env bash
# Smoke test of the chip lab through the CLI only: model in -> verified, measured chip out.
#   scripts/smoke.sh          core flow (no Docker needed)
#   scripts/smoke.sh --full   also layout / timing-power (LibreLane), iCE40 bitstream, Tiny Tapeout package
set -euo pipefail
cd "$(dirname "$0")/.."
C=.venv/bin/chiplab
FULL=0; [ "${1:-}" = "--full" ] && FULL=1
RUN="smoke-$(date +%s)"
pyget() { .venv/bin/python -c "import json,sys; r=json.load(sys.stdin); print(r$1)"; }
step() { printf '\n== %s\n' "$*"; }
call() { local tool=$1 args=$2; local out; out=$($C "$tool" --json "$args") || { echo "$out"; echo "FAILED: $tool"; exit 1; }; echo "$out"; }
show() { .venv/bin/python -c "import json,sys; r=json.load(sys.stdin); print({k: r[k] for k in r if k in ($1)})"; }

step "ingest the feasibility-spike model (intnn)"
D=$($C ingest-model --json "{\"format\": \"intnn\", \"model\": $(cat fixtures/spike_best.json), \"name\": \"spike\"}" | pyget '["design_id"]')
echo "design_id=$D"
step "synthesize";          call synthesize "{\"design_id\":\"$D\",\"run_id\":\"$RUN\"}" | show "'metrics','cached'"
step "bit-exact (random)";  call simulate "{\"design_id\":\"$D\",\"inputs\":\"random\",\"n\":100000,\"run_id\":\"$RUN\"}" | show "'bit_exact','n','device'"
step "formal";              call prove-equivalence "{\"design_id\":\"$D\",\"timeout\":300,\"run_id\":\"$RUN\"}" | show "'proved','against','method','verification_level'"
step "sky130 area";         call map-to-process "{\"design_id\":\"$D\",\"pdk\":\"sky130\",\"run_id\":\"$RUN\"}" | show "'metrics'"
step "iCE40 LUTs";          call count-luts "{\"design_id\":\"$D\",\"family\":\"ice40\"}" | show "'metrics'"
step "streaming wrapper";   call compile-stream "{\"design_id\":\"$D\",\"tt\":true}" | show "'top','transfers_per_frame'"
step "RTL sim (level 3)";   call rtl-simulate "{\"design_id\":\"$D\",\"n\":200}" | show "'passed','vectors','mismatches','verification_level'"
if [ "$FULL" = 1 ]; then
  step "LibreLane timing/power/layout (sky130A)"; call layout "{\"design_id\":\"$D\",\"pdk\":\"sky130A\",\"run_id\":\"$RUN\"}" | show "'status','area_um2','timing_ws_ns','power_uw','png'"
  step "iCE40 bitstream";   call bitstream "{\"design_id\":\"$D\",\"run_id\":\"$RUN\"}" | show "'status','metrics','bin'"
  step "Tiny Tapeout package"; call tt-package "{\"design_id\":\"$D\",\"run_id\":\"$RUN\"}" | show "'status','folder','tiles'"
fi
step "cost";                call estimate-cost "{\"design_id\":\"$D\"}" | .venv/bin/python -c "import json,sys; [print(' ', r['route'], r.get('fits'), r.get('cost'), r['currency']) for r in json.load(sys.stdin)['routes']]"
step "report";              call chip-report "{\"design_id\":\"$D\",\"run_id\":\"$RUN\"}" | pyget '["report_md"]' | head -12
step "events"; wc -l < "runs/events/$RUN.jsonl" 2>/dev/null || ls runs/events | tail -1
echo; echo "SMOKE OK ($D)"
