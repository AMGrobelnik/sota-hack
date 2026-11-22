"""A family of tiny quantised seizure detectors, trained with the integer arithmetic in the loop, exported to
the chip lab's chipir/1 format, and evaluated from that very document.

Every design applies one small network to each channel's 5 integer features (shared weights) and takes the
maximum score over channels: score > t raises the alarm. t is chosen on validation babies only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch

IN_BITS = 6
QMAX = (1 << IN_BITS) - 1
AMAX = 15              # hidden activations are 4-bit unsigned


@dataclass(frozen=True)
class Spec:
    channels: int
    hidden: int        # 0 = a single linear unit per channel
    wmax: int          # weight range -wmax..wmax (1 = ternary, 7 = 4-bit)
    seed: int

    @property
    def id(self) -> str:
        wb = "t" if self.wmax == 1 else f"w{int(math.log2(self.wmax + 1)) + 1}"
        return f"c{self.channels}-h{self.hidden}-{wb}-s{self.seed}"


def shift_for(wmax: int, n_feat: int) -> int:
    return max(0, round(math.log2(wmax * QMAX * n_feat / (2 * AMAX))))


# ---------------- feature quantiser (fitted on training babies only) ----------------

def fit_quantiser(f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """f: [..., F] positive floats -> per-feature (lo, hi) of log2 at the 1st and 99th percentiles."""
    lg = np.log2(np.maximum(f.reshape(-1, f.shape[-1]), 1e-6))
    return np.percentile(lg, 1, axis=0), np.percentile(lg, 99, axis=0)


def quantise(f: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    lg = np.log2(np.maximum(f, 1e-6))
    q = np.rint((lg - lo) / (hi - lo) * QMAX)
    return np.clip(q, 0, QMAX).astype(np.int64)


# ---------------- quantisation-aware model ----------------

def ste_round(x: torch.Tensor) -> torch.Tensor:
    return x + (torch.round(x) - x).detach()


def ste_floor(x: torch.Tensor) -> torch.Tensor:
    return x + (torch.floor(x) - x).detach()


def leaky_clip(a: torch.Tensor) -> torch.Tensor:
    """Forward: clip to 0..AMAX exactly. Backward: slope 0.1 outside the range, so clipped units can recover."""
    c = torch.clamp(a, 0, AMAX)
    return c + 0.1 * (a - c) - (0.1 * (a - c)).detach()


class TinyNet(torch.nn.Module):
    def __init__(self, n_feat: int, spec: Spec):
        super().__init__()
        self.spec = spec
        self.k = shift_for(spec.wmax, n_feat)
        h = spec.hidden
        a = 1.0 if spec.wmax == 1 else 0.6
        if h == 0:
            self.w = torch.nn.Parameter(torch.empty(n_feat).uniform_(-a, a))
        else:
            self.w1 = torch.nn.Parameter(torch.empty(h, n_feat).uniform_(-a, a))
            self.b1 = torch.nn.Parameter(torch.zeros(h))
            self.wo = torch.nn.Parameter(torch.empty(h).uniform_(-a, a))
        self.log_scale = torch.nn.Parameter(torch.tensor(0.0))
        self.center = torch.nn.Parameter(torch.tensor(0.0))
        self.norm = 1.0          # fixed score scale set at initialisation (training only)
        self.hard = False        # False: unrounded warm-up phase; True: exact integer arithmetic (STE)

    def qw(self, p: torch.Tensor) -> torch.Tensor:
        m = self.spec.wmax
        if not self.hard:
            return torch.clamp(p * m, -m, m)
        return torch.clamp(ste_round(p * m), -m, m)

    def ints(self) -> dict:
        with torch.no_grad():
            if self.spec.hidden == 0:
                return {"w": self.qw(self.w).long().tolist()}
            b1 = torch.round(self.b1 * (2 ** self.k) * 8).long().tolist()
            return {"w1": self.qw(self.w1).long().tolist(), "b1": b1, "wo": self.qw(self.wo).long().tolist(),
                    "k": self.k}

    def score(self, x: torch.Tensor) -> torch.Tensor:
        """x: [N, C, F] integer-valued floats -> integer-valued score [N] (max over channels)."""
        if self.spec.hidden == 0:
            s = x @ self.qw(self.w)
        else:
            b1 = self.b1 * (2 ** self.k) * 8
            z = x @ self.qw(self.w1).T + (ste_round(b1) if self.hard else b1)
            a = z / (2 ** self.k)
            a = leaky_clip(ste_floor(a) if self.hard else a)
            s = a @ self.qw(self.wo)
        return s.amax(dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.exp(self.log_scale) * self.score(x) / self.norm - self.center


def train(spec: Spec, x: np.ndarray, y: np.ndarray, groups: np.ndarray, *, steps: int = 3000, batch: int = 512,
          warm: float = 0.4) -> dict:
    """Adam, linear learning-rate decay; the first `warm` share of steps unrounded, the rest exact integer.
    Minibatches draw every training baby equally often (groups = baby index per window)."""
    torch.manual_seed(spec.seed)
    rng = np.random.default_rng(spec.seed)
    xt = torch.tensor(x, dtype=torch.float32)
    yt = torch.tensor(y, dtype=torch.float32)
    net = TinyNet(x.shape[2], spec)
    with torch.no_grad():
        s0 = net.score(xt[torch.tensor(rng.choice(len(xt), min(4096, len(xt)), replace=False))])
        net.norm = float(s0.std()) + 1e-3
        net.center.fill_(float(s0.mean()) / net.norm)
    cnt = np.bincount(groups)
    prob = 1.0 / cnt[groups]
    prob = prob / prob.sum()
    cdf = np.cumsum(prob)
    npos = float((prob * y).sum())
    pw = torch.tensor(min(20.0, (1.0 - npos) / max(npos, 1e-6)))
    loss_f = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
    opt = torch.optim.Adam(net.parameters(), lr=0.02)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: 1.0 - 0.9 * i / steps)
    for i in range(steps):
        net.hard = i >= warm * steps
        idx = torch.tensor(np.minimum(np.searchsorted(cdf, rng.random(batch)), len(yt) - 1))
        opt.zero_grad()
        loss = loss_f(net(xt[idx]), yt[idx])
        loss.backward()
        opt.step()
        sched.step()
    net.hard = True
    return net.ints()


# ---------------- chipir/1 export and evaluation of that document ----------------

def to_ir(spec: Spec, p: dict, n_feat: int, t: int, name: str) -> dict:
    c = spec.channels
    nodes: list[dict] = []
    if spec.hidden == 0:
        W = [[0] * (c * n_feat) for _ in range(c)]
        for ch in range(c):
            W[ch][ch * n_feat:(ch + 1) * n_feat] = p["w"]
        nodes.append({"id": "s", "op": "matvec", "src": "x", "W": W})
    else:
        h = spec.hidden
        W1 = [[0] * (c * n_feat) for _ in range(c * h)]
        for ch in range(c):
            for j in range(h):
                W1[ch * h + j][ch * n_feat:(ch + 1) * n_feat] = p["w1"][j]
        Wo = [[0] * (c * h) for _ in range(c)]
        for ch in range(c):
            Wo[ch][ch * h:(ch + 1) * h] = p["wo"]
        nodes += [
            {"id": "l1", "op": "matvec", "src": "x", "W": W1, "b": p["b1"] * c},
            {"id": "l1s", "op": "shift", "src": "l1", "k": p["k"]},
            {"id": "a1", "op": "clip", "src": "l1s", "lo": 0, "hi": AMAX},
            {"id": "s", "op": "matvec", "src": "a1", "W": Wo},
        ]
    last = "s"
    if c > 1:
        nodes.append({"id": "smax", "op": "max", "src": "s", "groups": [list(range(c))]})
        last = "smax"
    nodes.append({"id": "dec", "op": "cmp", "src": last, "rel": "gt", "t": [int(t)]})
    return {"ir": "chipir/1", "name": name,
            "inputs": [{"name": "x", "lanes": c * n_feat, "bits": IN_BITS, "signed": False}],
            "nodes": nodes, "outputs": [{"name": "y", "src": "dec"}],
            "meta": {"features_per_channel": n_feat, "channels": c, "hidden": spec.hidden, "wmax": spec.wmax}}


def eval_ir(ir: dict, x: np.ndarray, upto: str | None = None) -> np.ndarray:
    """Integer evaluation of the document (semantics of the lab's reference interpreter) for the ops used here.
    x: int64 [N, lanes]. Returns the first lane of node `upto` (default: the output)."""
    v = {"x": np.asarray(x, dtype=np.int64)}
    for nd in ir["nodes"]:
        op = nd["op"]
        if op == "matvec":
            y = v[nd["src"]] @ np.asarray(nd["W"], dtype=np.int64).T
            if nd.get("b") is not None:
                y = y + np.asarray(nd["b"], dtype=np.int64)[None, :]
        elif op == "shift":
            y = v[nd["src"]] >> nd["k"]
        elif op == "clip":
            y = np.clip(v[nd["src"]], nd["lo"], nd["hi"])
        elif op == "max":
            y = np.stack([v[nd["src"]][:, g].max(axis=1) for g in nd["groups"]], axis=1)
        elif op == "cmp":
            y = (v[nd["src"]] > np.asarray(nd["t"], dtype=np.int64)[None, :]).astype(np.int64)
        else:
            raise ValueError(op)
        v[nd["id"]] = y
        if upto == nd["id"]:
            return y[:, 0]
    return v[ir["outputs"][0]["src"]][:, 0]


def score_node(ir: dict) -> str:
    return ir["nodes"][-2]["id"]
