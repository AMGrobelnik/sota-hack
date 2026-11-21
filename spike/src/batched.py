"""Step 2: K tiny low-precision candidates trained as ONE batched program
(stacked weights + torch.bmm). Integer model per candidate:
  h_j = clip((sum_i W1[j,i]*x_i + b1_j) >> s, 0, 15) ; score = sum_j W2[j]*h_j + b2 ; AF if score>0
W in {-1,0,+1} (ternary) or {-1,+1} (binary); b1,b2 integers; x quantised RR or dRR (see common.py).
usage: python -I batched.py <rr.npz> <outdir> <mode>   mode = select | timing"""
import importlib.util as _u
import json
import sys
import time
import numpy as np
import torch

_s = _u.spec_from_file_location("common", __file__.replace("batched.py", "common.py"))
C = _u.module_from_spec(_s); _s.loader.exec_module(C)

EPOCHS, BS, LR, AMAX = 60, 512, 0.02, 15


def make_cands(n, seed=1):
    r = np.random.default_rng(seed)
    out = []
    for _ in range(256):
        out.append(dict(L=int(r.choice([8, 16, 24])), bits=int(r.choice([4, 5, 6, 8])),
                        H=int(r.choice([4, 8, 16, 32])), feat=str(r.choice(["rr", "drr"])),
                        wtype=str(r.choice(["ternary", "binary"]))))
    return out[:n]


def build_X(rr, cands, dev):
    Lm = max(c["L"] for c in cands)
    X = torch.zeros(len(cands), len(rr), Lm)
    for k, c in enumerate(cands):
        X[k, :, :c["L"]] = C.quantise(rr, c["L"], c["bits"], c["feat"])
    return X.to(dev)


def ste(x, q):
    return x + (q - x).detach()


def qweights(w, isbin):
    t = (w > 0.5).float() - (w < -0.5).float()
    b = torch.where(w >= 0, 1.0, -1.0)
    return ste(w, torch.where(isbin, b, t))


def forward(P, X, hmask, isbin, s2):
    W1 = qweights(P["w1"], isbin)
    b1 = ste(P["b1"] * s2, torch.round(P["b1"] * s2))
    pre = torch.bmm(X, W1.transpose(1, 2)) + b1[:, None, :]
    h = ste(pre / s2[:, :, None], torch.floor(pre / s2[:, :, None]))
    h = torch.clamp(h, 0, AMAX) * hmask[:, None, :]
    W2 = qweights(P["w2"], isbin[:, :, 0])
    b2 = ste(P["b2"] * 8, torch.round(P["b2"] * 8))
    return torch.bmm(h, W2[:, :, None]).squeeze(2) + b2, W1, W2, b1, b2  # score [K,B]


def train(cands, data, dev, epochs=EPOCHS, seed=0):
    torch.manual_seed(seed)
    K = len(cands)
    Hm, Lm = max(c["H"] for c in cands), max(c["L"] for c in cands)
    Xtr = build_X(data[0]["rr"], cands, dev)
    y = torch.tensor(data[0]["y"], dtype=torch.float32, device=dev)
    N = len(y)
    P = {"w1": (torch.randn(K, Hm, Lm) * 0.6), "b1": torch.ones(K, Hm),
         "w2": torch.randn(K, Hm) * 0.6, "b2": torch.zeros(K, 1),
         "lt": torch.log(torch.tensor([[1.0 / (2 * c["H"] ** 0.5)] for c in cands]))}
    P = {k: v.to(dev).requires_grad_(True) for k, v in P.items()}
    hmask = torch.tensor([[1.0] * c["H"] + [0.0] * (Hm - c["H"]) for c in cands], device=dev)
    isbin = torch.tensor([c["wtype"] == "binary" for c in cands], device=dev)[:, None, None]
    with torch.no_grad():  # per-candidate shift so pre-activation std ~ 3 output steps
        pre = torch.bmm(Xtr[:, :1024], qweights(P["w1"], isbin).transpose(1, 2))
        sd = pre.std(dim=(1, 2)) * 1.0
        sh = torch.clamp(torch.round(torch.log2(sd / 3 + 1e-6)), 0, 12)
        s2 = (2.0 ** sh)[:, None]
    # biases are scaled per candidate: b1 int = round(P.b1 * s2) -> pass s2 as [K,1]
    pw = (y == 0).sum() / (y == 1).sum()
    opt = torch.optim.Adam(P.values(), LR)
    steps = epochs * ((N + BS - 1) // BS); step = 0
    if dev == "mps":
        torch.mps.synchronize()
    t0 = time.time()
    for ep in range(epochs):
        perm = torch.randperm(N, device=dev)
        for i in range(0, N, BS):
            for g in opt.param_groups:
                g["lr"] = LR * (1 - step / steps) + 1e-4
            step += 1
            b = perm[i:i + BS]
            score = forward(P, Xtr[:, b], hmask, isbin, s2)[0]
            logit = score * torch.exp(P["lt"])
            yb = y[b][None, :].expand_as(logit)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logit, yb, pos_weight=pw, reduction="none").mean(1).sum()
            opt.zero_grad(); loss.backward(); opt.step()
            with torch.no_grad():
                P["w1"].clamp_(-1.5, 1.5); P["w2"].clamp_(-1.5, 1.5)
    if dev == "mps":
        torch.mps.synchronize()
    dt = time.time() - t0
    return P, hmask, isbin, s2, dt


@torch.no_grad()
def predict(P, hmask, isbin, s2, cands, rr, dev):
    X = build_X(rr, cands, dev)
    return (forward(P, X, hmask, isbin, s2)[0] > 0).cpu().numpy().astype(int)  # [K,N]


def export(P, hmask, isbin, s2, cands, k):
    c = cands[k]
    with torch.no_grad():
        W1 = qweights(P["w1"], isbin)[k, :c["H"], :c["L"]].round().int().cpu().numpy()
        b1 = torch.round(P["b1"][k, :c["H"]] * s2[k]).int().cpu().numpy()
        W2 = qweights(P["w2"], isbin[:, :, 0])[k, :c["H"]].round().int().cpu().numpy()
        b2 = int(torch.round(P["b2"][k, 0] * 8).item())
    shift = int(round(float(torch.log2(s2[k, 0]))))
    return dict(cfg=c, W1=W1.tolist(), b1=b1.tolist(), shift=shift, W2=W2.tolist(), b2=b2, amax=AMAX)


if __name__ == "__main__":
    npz, outdir, mode = sys.argv[1:4]
    data, info = C.load_split(npz)
    print("split info", info, flush=True)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    if mode == "timing":
        res = []
        for d in (dev, "cpu"):
            for K in (1, 16, 64, 256):
                cands = make_cands(K)
                if d == "mps":
                    torch.mps.synchronize()
                _, _, _, _, dt = train(cands, data, d)
                res.append(dict(device=d, K=K, mode="batched", seconds=round(dt, 2),
                                cand_per_min=round(K * 60 / dt, 1)))
                print(res[-1], flush=True)
            # one at a time: same first 16 candidates, K=1 each (rate is per-candidate, constant)
            cands = make_cands(16); t = 0.0
            for c in cands:
                t += train([c], data, d)[4]
            res.append(dict(device=d, K=16, mode="one-at-a-time (measured, 16 runs)",
                            seconds=round(t, 2), cand_per_min=round(16 * 60 / t, 1)))
            print(res[-1], flush=True)
        json.dump(res, open(outdir + "/timing.json", "w"), indent=1)
    else:
        cands = make_cands(256)
        P, hm, ib, s2, dt = train(cands, data, dev)
        print("trained 256 in", round(dt, 1), "s on", dev, flush=True)
        pv = predict(P, hm, ib, s2, cands, data[1]["rr"], dev)
        yv = data[1]["y"]
        rows = []
        for k, c in enumerate(cands):
            m = C.metrics(yv, pv[k])
            ry, rp = C.record_level(data[1]["rec"], yv, pv[k])
            rows.append(dict(k=k, **c, val_win_f1=m["f1"], val_win_sens=m["sens"], val_win_spec=m["spec"],
                             val_rec_f1=C.metrics(ry, rp)["f1"]))
        json.dump(rows, open(outdir + "/val_scores.json", "w"))
        for r in rows:
            print(r)
        # best by window F1, ties -> fewer weights (smaller circuit)
        maxsz = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9  # max H*L (circuit size cap)
        best = max([r for r in rows if r["H"] * r["L"] <= maxsz], key=lambda r: (r["val_win_f1"], -r["H"] * r["L"]))
        print("BEST", best, flush=True)
        json.dump(export(P, hm, ib, s2, cands, best["k"]), open(outdir + "/best.json", "w"))
        pt = predict(P, hm, ib, s2, cands, data[2]["rr"], dev)[best["k"]]
        np.save(outdir + "/torch_test_pred.npy", pt)
        print("torch best, test window-level", C.metrics(data[2]["y"], pt))
