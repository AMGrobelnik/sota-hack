"""Step 3a: best.json -> af.v (integer arithmetic, weights as constants).
usage: python -I export_verilog.py <best.json> <af.v>"""
import json
import math
import sys

m = json.load(open(sys.argv[1]))
c = m["cfg"]; L, H, bits, feat = c["L"], c["H"], c["bits"], c["feat"]
W1, b1, W2, b2, sh, amax = m["W1"], m["b1"], m["W2"], m["b2"], m["shift"], m["amax"]
signed_in = feat == "drr"
xmax = 2 ** (bits - 1) if signed_in else 2 ** bits - 1
bw = lambda v: max(1, math.ceil(math.log2(v + 1))) + 2
WP = bw(max(sum(abs(w) for w in row) * xmax + abs(b) for row, b in zip(W1, b1)))
WS = bw(H * amax + abs(b2))
lines = [f"module af(input [{L * bits - 1}:0] x, output pred);"]
for i in range(L):
    sl = f"x[{i * bits + bits - 1}:{i * bits}]"
    ext = f"$signed({sl})" if signed_in else f"$signed({{1'b0,{sl}}})"
    lines.append(f"  wire signed [{WP - 1}:0] xs{i} = {ext};")
for j in range(H):
    terms = "".join(f" {'+' if w > 0 else '-'} xs{i}" for i, w in enumerate(W1[j]) if w)
    bc = f"{'-' if b1[j] < 0 else ''}{WP}'sd{abs(b1[j])}"
    lines.append(f"  wire signed [{WP - 1}:0] p{j} = {bc}{terms};")
    lines.append(f"  wire signed [{WP - 1}:0] q{j} = p{j} >>> {sh};")
    lines.append(f"  wire [3:0] h{j} = (q{j} < 0) ? 4'd0 : (q{j} > {amax}) ? 4'd{amax} : q{j}[3:0];")
terms = "".join(f" {'+' if w > 0 else '-'} $signed({{{WS - 4}'b0,h{j}}})" for j, w in enumerate(W2) if w)
bc = f"{'-' if b2 < 0 else ''}{WS}'sd{abs(b2)}"
lines.append(f"  wire signed [{WS - 1}:0] score = {bc}{terms};")
lines.append("  assign pred = (score > 0);")
lines.append("endmodule")
open(sys.argv[2], "w").write("\n".join(lines) + "\n")
print("wrote", sys.argv[2], "cfg", c, "WP", WP, "WS", WS)
