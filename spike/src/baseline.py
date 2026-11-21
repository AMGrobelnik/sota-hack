"""Step 1: full-precision MLP on RR window (L=24 RR + 24 diffs, float ms).
usage: python -I baseline.py <rr.npz>"""
import sys
import numpy as np
import torch
import torch.nn as nn
import importlib.util as _u
_s = _u.spec_from_file_location("common", __file__.replace("baseline.py", "common.py"))
_c = _u.module_from_spec(_s); _s.loader.exec_module(_c)  # -I drops script dir from path
load_split, metrics, record_level, LMAX = _c.load_split, _c.metrics, _c.record_level, _c.LMAX

torch.manual_seed(0)
data, info = load_split(sys.argv[1])
print("split info", info)


def feats(rr):
    rr = torch.as_tensor(rr)
    d = rr[:, 1:] - rr[:, :-1]
    return torch.cat([(rr[:, 1:] - 800) / 300, d / 150], 1)


dev = "mps" if torch.backends.mps.is_available() else "cpu"
Xtr, ytr = feats(data[0]["rr"]).to(dev), torch.tensor(data[0]["y"], dtype=torch.float32, device=dev)
net = nn.Sequential(nn.Linear(Xtr.shape[1], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 1)).to(dev)
opt = torch.optim.Adam(net.parameters(), 2e-3)
pw = torch.tensor((ytr == 0).sum().item() / (ytr == 1).sum().item(), device=dev)
for ep in range(30):
    perm = torch.randperm(len(ytr), device=dev)
    for i in range(0, len(perm), 256):
        b = perm[i:i + 256]
        loss = nn.functional.binary_cross_entropy_with_logits(net(Xtr[b]).squeeze(1), ytr[b], pos_weight=pw)
        opt.zero_grad(); loss.backward(); opt.step()
for name, s in (("val", 1), ("test", 2)):
    with torch.no_grad():
        p = (net(feats(data[s]["rr"]).to(dev)).squeeze(1) > 0).cpu().numpy().astype(int)
    print(name, "window-level", metrics(data[s]["y"], p))
    ry, rp = record_level(data[s]["rec"], data[s]["y"], p)
    print(name, "record-level (majority vote of windows)", metrics(ry, rp), "n_records", len(ry))
n = sum(p.numel() for p in net.parameters())
print("baseline params", n, "device", dev)
