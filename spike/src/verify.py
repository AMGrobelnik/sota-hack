"""Steps 4+5: compare torch quantised model, independent numpy integer model, and the
synthesised gate netlist (Yosys write_json, evaluated bit-parallel in numpy) on ALL test windows.
usage: python -I verify.py <rr.npz> <best.json> <net.json> <torch_test_pred.npy>"""
import importlib.util as _u
import json
import sys
import numpy as np
import torch

_s = _u.spec_from_file_location("common", __file__.replace("verify.py", "common.py"))
C = _u.module_from_spec(_s); _s.loader.exec_module(C)
npz, bestp, netp, tpp = sys.argv[1:5]
data, _ = C.load_split(npz)
te = data[2]
m = json.load(open(bestp)); c = m["cfg"]; L, bits, feat = c["L"], c["bits"], c["feat"]
X = C.quantise(te["rr"], L, bits, feat).numpy().astype(np.int64)  # [N,L] integers (outside the circuit)
N = len(X)

# independent integer model (python/numpy int64)
W1 = np.array(m["W1"], dtype=np.int64); b1 = np.array(m["b1"], dtype=np.int64)
W2 = np.array(m["W2"], dtype=np.int64)
pre = X @ W1.T + b1
h = np.clip(pre >> m["shift"], 0, m["amax"])
int_pred = ((h @ W2 + m["b2"]) > 0).astype(int)

# gate netlist
net = json.load(open(netp))
mod = net["modules"]["af"]
vals = {}  # bit id -> bool array [N]
vals["0"] = np.zeros(N, bool); vals["1"] = np.ones(N, bool)
# input bits: x[i*bits+b], two's complement for drr
xu = X & ((1 << bits) - 1)
xbits = mod["ports"]["x"]["bits"]
assert len(xbits) == L * bits, (len(xbits), L, bits)
for i in range(L):
    for b in range(bits):
        vals[str(xbits[i * bits + b])] = ((xu[:, i] >> b) & 1).astype(bool)
cells = list(mod["cells"].values())
fn = {"$_AND_": lambda a, b, s: a & b, "$_NAND_": lambda a, b, s: ~(a & b),
      "$_OR_": lambda a, b, s: a | b, "$_NOR_": lambda a, b, s: ~(a | b),
      "$_XOR_": lambda a, b, s: a ^ b, "$_XNOR_": lambda a, b, s: ~(a ^ b),
      "$_ANDNOT_": lambda a, b, s: a & ~b, "$_ORNOT_": lambda a, b, s: a | ~b,
      "$_MUX_": lambda a, b, s: np.where(s, b, a), "$_NOT_": lambda a, b, s: ~a,
      "$_BUF_": lambda a, b, s: a}
types = {}
for cl in cells:
    types[cl["type"]] = types.get(cl["type"], 0) + 1
    assert cl["type"] in fn, "unknown cell " + cl["type"]
pending = cells
while pending:
    nxt = []
    for cl in pending:
        cn = cl["connections"]
        ins = [cn[p][0] if p in cn else "0" for p in ("A", "B", "S")]
        if all(str(i) in vals for i in ins):
            vals[str(cn["Y"][0])] = fn[cl["type"]](*[vals[str(i)] for i in ins])
        else:
            nxt.append(cl)
    assert len(nxt) < len(pending), "combinational loop or undriven net"
    pending = nxt
circ_pred = vals[str(mod["ports"]["pred"]["bits"][0])].astype(int)
torch_pred = np.load(tpp)

print("cell types in netlist", types, "total", len(cells))
print("test windows", N)
for nm, a, b in (("circuit vs integer model", circ_pred, int_pred),
                 ("integer model vs torch (STE-trained) forward", int_pred, torch_pred),
                 ("circuit vs torch", circ_pred, torch_pred)):
    print(f"MATCH {nm}: {int((a == b).sum())}/{N} identical, mismatches {int((a != b).sum())}")
print("circuit, test window-level", C.metrics(te["y"], circ_pred))
ry, rp = C.record_level(te["rec"], te["y"], circ_pred)
print("circuit, test record-level (majority vote)", C.metrics(ry, rp), "n_records", len(ry))
print("integer model, test window-level", C.metrics(te["y"], int_pred))
