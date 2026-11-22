"""intnn: integer neural networks with weights wired into gates (binary, ternary or k-bit weights).

Per hidden layer:  h = clip( (W h_prev + b) >> s, 0, 2^abits - 1 )
Output:            score = W_out h + b_out ;  binary: decision = score > 0 ; multiclass: argmax(score)

Population training: K candidates are stacked (zero-padded weights, masks) and trained as one batched program
with torch.bmm and straight-through estimators. Candidates of different depth or training settings train as
separate populations inside the same call. predict() is the exact integer math (float64, integers only), and
lower() writes the same math as chipir/1, so the chip equals the model bit for bit.
"""
from __future__ import annotations

import math
import os
import time

import numpy as np
import torch

from chiplab.plugins.base import BatchInputs, ModelFamily

WCODE = {"ternary": 0, "binary": 1, "kbit": 2}
DEFAULTS = {"hidden": [16], "wtype": "ternary", "wbits": 4, "abits": 4,
            "epochs": 60, "lr": 0.02, "batch_size": 512, "class_weight": "auto", "seed": 0}
TRAIN_KEYS = ("epochs", "lr", "batch_size", "class_weight", "seed")


def _determinism():
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def _dev(dev: str | None) -> str:
    if dev:
        return dev
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _sync(dev):
    if dev == "cuda":
        torch.cuda.synchronize()
    elif dev == "mps":
        torch.mps.synchronize()


def _ste(x, q):
    return x + (q - x).detach()


def _qw(w, code, qmax):
    """Quantise weights: ternary {-1,0,1} (|w|>0.5), binary {-1,1}, kbit round+clip to [-qmax, qmax]."""
    t = (w > 0.5).to(w.dtype) - (w < -0.5).to(w.dtype)
    b = torch.where(w >= 0, torch.ones_like(w), -torch.ones_like(w))
    kq = torch.maximum(torch.minimum(torch.round(w), qmax), -qmax)
    return torch.where(code == 0, t, torch.where(code == 1, b, kq))


class IntNN(ModelFamily):
    name = "intnn"
    version = "1"

    # ---------------------------------------------------------------- settings
    def space(self) -> dict:
        return {"hidden": {"type": "list[int]", "each": [1, 256], "max_layers": 4, "default": [16]},
                "wtype": {"values": list(WCODE), "default": "ternary"},
                "wbits": {"range": [2, 8], "default": 4, "note": "kbit only: weights in [-(2^(wbits-1)-1), 2^(wbits-1)-1]"},
                "abits": {"range": [1, 8], "default": 4, "note": "activations clipped to [0, 2^abits-1]"},
                "epochs": {"range": [1, 2000], "default": 60}, "lr": {"range": [1e-4, 0.5], "default": 0.02},
                "batch_size": {"range": [16, 65536], "default": 512},
                "class_weight": {"values": ["auto", "none"], "default": "auto"}, "seed": {"default": 0}}

    def validate_cfg(self, cfg: dict) -> dict:
        c = dict(DEFAULTS)
        c.update({k: v for k, v in cfg.items() if k != "H"})
        if "H" in cfg and "hidden" not in cfg:
            c["hidden"] = [int(cfg["H"])]
        c["hidden"] = [int(h) for h in c["hidden"]]
        if not (1 <= len(c["hidden"]) <= 4) or any(h < 1 or h > 256 for h in c["hidden"]):
            raise ValueError(f"hidden must be 1-4 layers of width 1-256, got {c['hidden']}")
        if c["wtype"] not in WCODE:
            raise ValueError(f"wtype must be one of {list(WCODE)}")
        c["wbits"], c["abits"] = int(c["wbits"]), int(c["abits"])
        if not 2 <= c["wbits"] <= 8 or not 1 <= c["abits"] <= 8:
            raise ValueError("wbits in 2..8, abits in 1..8")
        if c["class_weight"] not in ("auto", "none"):
            raise ValueError("class_weight must be auto or none")
        c["epochs"], c["batch_size"], c["seed"] = int(c["epochs"]), int(c["batch_size"]), int(c["seed"])
        c["lr"] = float(c["lr"])
        return c

    def est_cost(self, cfg: dict, in_spec: dict) -> dict:
        c = self.validate_cfg(cfg)
        dims = [in_spec["lanes"]] + c["hidden"] + [1]
        w = sum(a * b for a, b in zip(dims[:-1], dims[1:]))
        # every weight is at most one add/sub of a narrow operand; ternary leaves ~1/3 zero on average
        dens = {"ternary": 0.67, "binary": 1.0, "kbit": 1.0 + 0.5 * (c["wbits"] - 2)}[c["wtype"]]
        return {"weights": int(w), "adds": int(round(w * dens)), "layers": len(c["hidden"]) + 1,
                "max_width": max(dims)}

    # ---------------------------------------------------------------- training
    def train(self, cfgs: list[dict], data: BatchInputs, dev: str | None = None, opts: dict | None = None):
        _determinism()
        dev = _dev(dev)
        opts = opts or {}
        cfgs = [self.validate_cfg(c) for c in cfgs]
        y = data.y.to(dev).long()
        n_classes = int(opts.get("n_classes") or int(y.max().item()) + 1)
        n_classes = max(n_classes, 2)
        groups = {}
        for k, c in enumerate(cfgs):
            gk = (len(c["hidden"]),) + tuple(c[t] for t in TRAIN_KEYS)
            groups.setdefault(gk, []).append(k)
        state = {"family": self.name, "version": self.version, "cfgs": cfgs, "n_classes": n_classes,
                 "keys": list(data.keys), "in_specs": data.in_specs, "groups": [], "train_seconds": 0.0}
        t_total = 0.0
        for gk, members in groups.items():
            g, dt = self._train_group(cfgs, members, data, y, n_classes, dev)
            state["groups"].append(g); t_total += dt
        state["train_seconds"] = t_total
        state["device"] = dev
        return state

    def _inputs(self, members, data, dev):
        keys = [data.keys[k] for k in members]
        uniq = sorted(set(keys))
        Inmax = max(data.in_specs[u]["lanes"] for u in uniq)
        N = next(iter(data.tensors.values())).shape[0]
        Xu = torch.zeros(len(uniq), N, Inmax, device=dev)
        for i, u in enumerate(uniq):
            t = data.tensors[u].to(dev).float()
            Xu[i, :, :t.shape[1]] = t
        kidx = torch.tensor([uniq.index(kk) for kk in keys], device=dev)
        in_lanes = [data.in_specs[kk]["lanes"] for kk in keys]
        return Xu, kidx, in_lanes, Inmax

    def _train_group(self, cfgs, members, data, y, n_classes, dev):
        c0 = cfgs[members[0]]
        torch.manual_seed(c0["seed"])
        Kg, D = len(members), len(c0["hidden"])
        Xu, kidx, in_lanes, Inmax = self._inputs(members, data, dev)
        N = Xu.shape[1]
        out_dim = 1 if n_classes == 2 else n_classes
        Hmax = [max(cfgs[k]["hidden"][l] for k in members) for l in range(D)]
        dims = [Inmax] + Hmax
        code = torch.tensor([WCODE[cfgs[k]["wtype"]] for k in members], device=dev).float()[:, None, None]
        qmax = torch.tensor([1.0 if cfgs[k]["wtype"] != "kbit" else float(2 ** (cfgs[k]["wbits"] - 1) - 1)
                             for k in members], device=dev)[:, None, None]
        amax = torch.tensor([float(2 ** cfgs[k]["abits"] - 1) for k in members], device=dev)[:, None, None]
        hmask = [torch.tensor([[1.0] * cfgs[k]["hidden"][l] + [0.0] * (Hmax[l] - cfgs[k]["hidden"][l]) for k in members],
                              device=dev) for l in range(D)]
        P = {}
        for l in range(D):
            P[f"W{l}"] = torch.randn(Kg, dims[l + 1], dims[l]) * 0.6
            P[f"b{l}"] = torch.ones(Kg, dims[l + 1])
        P["Wo"] = torch.randn(Kg, out_dim, Hmax[-1]) * 0.6
        P["bo"] = torch.zeros(Kg, out_dim)
        P["lt"] = torch.log(torch.tensor([[1.0 / (2 * cfgs[k]["hidden"][-1] ** 0.5)] for k in members]))
        P = {k: v.to(dev) for k, v in P.items()}
        sc = qmax.cpu().clone()  # kbit: spread init over the integer range
        P = {k: (v * sc.to(dev) if k.startswith("W") else v) for k, v in P.items()}
        P = {k: v.requires_grad_(True) for k, v in P.items()}
        # per-candidate, per-layer shift so pre-activation std ~ 3 output steps (as in the feasibility spike)
        shifts = []
        with torch.no_grad():
            h = Xu[:, :1024][kidx]
            for l in range(D):
                pre = torch.bmm(h, _qw(P[f"W{l}"], code, qmax).transpose(1, 2))
                m = hmask[l][:, None, :].expand_as(pre)
                sd = torch.stack([pre[i][m[i] > 0].std() if (m[i] > 0).any() else torch.tensor(1.0, device=dev)
                                  for i in range(Kg)])
                sh = torch.clamp(torch.round(torch.log2(sd / 3 + 1e-6)), 0, 12)
                shifts.append(sh)
                s = (2.0 ** sh)[:, None, None]
                h = torch.minimum(torch.maximum(torch.floor((pre + torch.round(P[f"b{l}"] * s[:, :, 0])[:, None, :]) / s),
                                                torch.zeros_like(pre)), amax) * hmask[l][:, None, :]
        if c0["class_weight"] == "auto":
            cnt = torch.bincount(y, minlength=n_classes).float().clamp(min=1)
            cw = (cnt.sum() / (n_classes * cnt))
        else:
            cw = torch.ones(n_classes, device=dev)
        pos_w = (cw[1] / cw[0]) if n_classes == 2 else None
        opt = torch.optim.Adam(P.values(), c0["lr"])
        bs, epochs, lr = c0["batch_size"], c0["epochs"], c0["lr"]
        steps = epochs * ((N + bs - 1) // bs); step = 0
        _sync(dev); t0 = time.time()
        for ep in range(epochs):
            perm = torch.randperm(N, device=dev)
            for i in range(0, N, bs):
                for gr in opt.param_groups:
                    gr["lr"] = lr * (1 - step / steps) + 1e-4
                step += 1
                b = perm[i:i + bs]
                score = self._forward(P, Xu[:, b][kidx], shifts, code, qmax, amax, hmask, D, train=True)
                logit = score * torch.exp(P["lt"])[:, :, None] if out_dim > 1 else score[:, :, 0] * torch.exp(P["lt"])
                yb = y[b]
                if out_dim == 1:
                    yy = yb[None, :].float().expand_as(logit)
                    loss = torch.nn.functional.binary_cross_entropy_with_logits(
                        logit, yy, pos_weight=pos_w, reduction="none").mean(1).sum()
                else:
                    loss = torch.nn.functional.cross_entropy(
                        logit.reshape(-1, out_dim), yb.repeat(Kg), weight=cw, reduction="none").view(Kg, -1).mean(1).sum()
                opt.zero_grad(); loss.backward(); opt.step()
                with torch.no_grad():
                    for k in P:
                        if k.startswith("W"):
                            P[k].copy_(torch.maximum(torch.minimum(P[k], qmax + 0.5), -qmax - 0.5))
        _sync(dev); dt = time.time() - t0
        g = {"members": members, "depth": D, "dims": dims, "out_dim": out_dim,
             "params": {k: v.detach().cpu() for k, v in P.items()},
             "shifts": [s.detach().cpu() for s in shifts], "code": code.cpu(), "qmax": qmax.cpu(), "amax": amax.cpu(),
             "hidden": [[cfgs[k]["hidden"][l] for l in range(D)] for k in members], "in_lanes": in_lanes,
             "train_seconds": dt}
        return g, dt

    def _forward(self, P, X, shifts, code, qmax, amax, hmask, D, train: bool):
        h = X
        for l in range(D):
            s = (2.0 ** shifts[l]).to(X.dtype)[:, None, None]
            W = _qw(P[f"W{l}"], code, qmax)
            braw = P[f"b{l}"] * s[:, :, 0]
            bint = torch.round(braw)
            if train:
                W = _ste(P[f"W{l}"], W); bint = _ste(braw, bint)
            pre = torch.bmm(h, W.transpose(1, 2)) + bint[:, None, :]
            hq = torch.floor(pre / s)
            if train:
                hq = _ste(pre / s, hq)
            h = torch.minimum(torch.maximum(hq, torch.zeros_like(hq)), amax) * hmask[l][:, None, :]
        Wo = _qw(P["Wo"], code, qmax)
        braw = P["bo"] * 8
        bo = torch.round(braw)
        if train:
            Wo = _ste(P["Wo"], Wo); bo = _ste(braw, bo)
        return torch.bmm(h, Wo.transpose(1, 2)) + bo[:, None, :]          # [K, B, out_dim]

    # ---------------------------------------------------------------- exact inference
    @torch.no_grad()
    def predict(self, state, data: BatchInputs, dev: str | None = None, return_scores: bool = False):
        dev = _dev(dev)
        K = len(state["cfgs"])
        N = next(iter(data.tensors.values())).shape[0]
        out = np.zeros((K, N), dtype=np.int64)
        scores = {}
        for g in state["groups"]:
            members = g["members"]
            Xu, kidx, _, Inmax = self._inputs(members, data, dev)
            if Inmax < g["dims"][0]:
                Xu = torch.nn.functional.pad(Xu, (0, g["dims"][0] - Inmax))
            Xu = Xu.double()
            P = {k: v.to(dev).double() for k, v in g["params"].items()}
            shifts = [s.to(dev).double() for s in g["shifts"]]
            code, qmax, amax = g["code"].to(dev).double(), g["qmax"].to(dev).double(), g["amax"].to(dev).double()
            D = g["depth"]
            hmask = [torch.tensor([[1.0] * h[l] + [0.0] * (g["dims"][l + 1] - h[l]) for h in g["hidden"]],
                                  device=dev, dtype=torch.float64) for l in range(D)]
            for i in range(0, N, 65536):
                sc = self._forward(P, Xu[:, i:i + 65536][kidx], shifts, code, qmax, amax, hmask, D, train=False)
                dec = (sc[:, :, 0] > 0).long() if g["out_dim"] == 1 else torch.argmax(sc, dim=2)
                out[members, i:i + 65536] = dec.cpu().numpy()
                if return_scores:
                    for j, k in enumerate(members):
                        scores.setdefault(k, []).append(sc[j].cpu().numpy())
        if return_scores:
            return out, {k: np.concatenate(v) for k, v in scores.items()}
        return out

    # ---------------------------------------------------------------- lowering to chipir/1
    def int_params(self, state, k: int) -> dict:
        for g in state["groups"]:
            if k in g["members"]:
                j = g["members"].index(k); break
        else:
            raise KeyError(f"candidate {k} not in state")
        P, code, qmax = g["params"], g["code"][j:j + 1].double(), g["qmax"][j:j + 1].double()
        hid, inl = g["hidden"][j], g["in_lanes"][j]
        layers, prev = [], inl
        for l in range(g["depth"]):
            W = _qw(P[f"W{l}"][j:j + 1].double(), code, qmax)[0, :hid[l], :prev].round().long().tolist()
            s = int(g["shifts"][l][j].item())
            b = torch.round(P[f"b{l}"][j, :hid[l]].double() * (2.0 ** s)).long().tolist()
            layers.append({"W": W, "b": b, "shift": s, "amax": int(g["amax"][j].item())})
            prev = hid[l]
        Wo = _qw(P["Wo"][j:j + 1].double(), code, qmax)[0, :, :prev].round().long().tolist()
        bo = torch.round(P["bo"][j].double() * 8).long().tolist()
        return {"layers": layers, "Wo": Wo, "bo": bo, "out_dim": g["out_dim"]}

    def lower(self, state, k: int, in_spec: dict) -> dict:
        ip = self.int_params(state, k)
        nodes, prev = [], "x"
        for l, L in enumerate(ip["layers"]):
            nodes.append({"id": f"l{l}_mv", "op": "matvec", "src": prev, "W": L["W"], "b": L["b"]})
            nodes.append({"id": f"l{l}_sh", "op": "shift", "src": f"l{l}_mv", "k": L["shift"]})
            nodes.append({"id": f"l{l}", "op": "clip", "src": f"l{l}_sh", "lo": 0, "hi": L["amax"]})
            prev = f"l{l}"
        nodes.append({"id": "score", "op": "matvec", "src": prev, "W": ip["Wo"], "b": ip["bo"]})
        if ip["out_dim"] == 1:
            nodes.append({"id": "dec", "op": "cmp", "src": "score", "rel": "gt", "t": [0]})
        else:
            nodes.append({"id": "dec", "op": "argmax", "src": "score"})
        return {"ir": "chipir/1", "name": f"intnn_c{k}",
                "inputs": [{"name": "x", "lanes": int(in_spec["lanes"]), "bits": int(in_spec["bits"]),
                            "signed": bool(in_spec["signed"])}],
                "nodes": nodes, "outputs": [{"name": "y", "src": "dec"}],
                "meta": {"family": self.name, "family_version": self.version, "cfg": state["cfgs"][k], "candidate": k}}


FAMILY = IntNN()


def numpy_reference(ip: dict, X: np.ndarray) -> np.ndarray:
    """Independent int64 numpy implementation of the lowered math (used by tests)."""
    h = np.asarray(X, dtype=np.int64)
    for L in ip["layers"]:
        pre = h @ np.asarray(L["W"], dtype=np.int64).T + np.asarray(L["b"], dtype=np.int64)
        h = np.clip(pre >> L["shift"], 0, L["amax"])
    sc = h @ np.asarray(ip["Wo"], dtype=np.int64).T + np.asarray(ip["bo"], dtype=np.int64)
    return (sc[:, 0] > 0).astype(np.int64) if ip["out_dim"] == 1 else np.argmax(sc, axis=1)
