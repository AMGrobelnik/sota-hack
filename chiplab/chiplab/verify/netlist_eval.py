"""Bit-parallel evaluation of a Yosys JSON gate netlist (simple gates), on numpy or on the GPU (torch).

64 input vectors are packed per machine word, so one pass of bitwise ops over the levelised gate list evaluates
64 x n_words vectors at once. Independent of the IR: it only knows gates and ports, so it checks the circuit,
not the code that generated it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

GATES = {"$_AND_", "$_NAND_", "$_OR_", "$_NOR_", "$_XOR_", "$_XNOR_", "$_ANDNOT_", "$_ORNOT_", "$_MUX_", "$_NOT_", "$_BUF_",
         "$_NMUX_", "$_AOI3_", "$_OAI3_", "$_AOI4_", "$_OAI4_"}


class Netlist:
    def __init__(self, path_or_dict, top: str | None = None):
        d = json.loads(Path(path_or_dict).read_text()) if not isinstance(path_or_dict, dict) else path_or_dict
        mods = d["modules"]
        name = top if top in mods else ("\\" + top if top and "\\" + top in mods else next(iter(mods)))
        m = mods[name]
        self.top = name.lstrip("\\")
        self.ports = {p: (v["direction"], v["bits"]) for p, v in m["ports"].items()}
        cells = []
        for c in m["cells"].values():
            if c["type"] not in GATES:
                raise ValueError(f"unsupported cell {c['type']} (synthesise to simple gates first)")
            cn = c["connections"]
            cells.append((c["type"], [cn[k][0] if k in cn else None for k in ("A", "B", "C", "D", "S")], cn["Y"][0]))
        # levelise: order cells so every input is driven before use
        driven = {}
        for p, (dirn, bits) in self.ports.items():
            if dirn == "input":
                for b in bits:
                    driven[b] = True
        order, pending = [], cells
        while pending:
            nxt = []
            for c in pending:
                if all(i is None or isinstance(i, str) or i in driven for i in c[1]):
                    order.append(c); driven[c[2]] = True
                else:
                    nxt.append(c)
            if len(nxt) == len(pending):
                raise ValueError("combinational loop or undriven net in netlist")
            pending = nxt
        self.order = order
        self.n_cells = len(cells)

    def evaluate(self, inputs: dict[str, np.ndarray], device: str = "numpy") -> dict[str, np.ndarray]:
        """inputs: {port: uint8/bool array [N, port_width]} (bit j = port bit j). Returns {output port: bool [N, width]}."""
        N = next(iter(inputs.values())).shape[0]
        nw = (N + 63) // 64
        if device == "numpy":
            xp, zeros = np, (lambda: np.zeros(nw, dtype=np.uint64))
            ones_v = np.full(nw, np.uint64(0xFFFFFFFFFFFFFFFF))
            pack = lambda col: _pack_np(col, nw)
        else:
            import torch
            xp = torch
            zeros = lambda: torch.zeros(nw, dtype=torch.int64, device=device)
            ones_v = torch.full((nw,), -1, dtype=torch.int64, device=device)
            pack = lambda col: torch.from_numpy(_pack_np(col, nw).view(np.int64)).to(device)
        V = {"0": zeros(), "1": ones_v, "x": zeros(), "z": zeros()}
        for p, (dirn, bits) in self.ports.items():
            if dirn != "input":
                continue
            a = np.asarray(inputs[p]).astype(bool)
            if a.shape[1] != len(bits):
                raise ValueError(f"port {p}: expected {len(bits)} bits, got {a.shape[1]}")
            for j, b in enumerate(bits):
                V[b] = pack(a[:, j])
        inv = (lambda v: ~v)
        for t, (A, B, C, D, S), Y in self.order:
            a = V[A] if A is not None else None
            b = V[B] if B is not None else None
            if t == "$_AND_": y = a & b
            elif t == "$_NAND_": y = inv(a & b)
            elif t == "$_OR_": y = a | b
            elif t == "$_NOR_": y = inv(a | b)
            elif t == "$_XOR_": y = a ^ b
            elif t == "$_XNOR_": y = inv(a ^ b)
            elif t == "$_ANDNOT_": y = a & inv(b)
            elif t == "$_ORNOT_": y = a | inv(b)
            elif t == "$_NOT_": y = inv(a)
            elif t == "$_BUF_": y = a
            elif t in ("$_MUX_", "$_NMUX_"):
                s = V[S]; y = (a & inv(s)) | (b & s)
                if t == "$_NMUX_": y = inv(y)
            elif t == "$_AOI3_": y = inv((a & b) | V[C])
            elif t == "$_OAI3_": y = inv((a | b) & V[C])
            elif t == "$_AOI4_": y = inv((a & b) | (V[C] & V[D]))
            elif t == "$_OAI4_": y = inv((a | b) & (V[C] | V[D]))
            V[Y] = y
        out = {}
        for p, (dirn, bits) in self.ports.items():
            if dirn != "output":
                continue
            cols = []
            for b in bits:
                w = V[b]
                w = w.cpu().numpy().view(np.uint64) if device != "numpy" else w
                cols.append(_unpack_np(w, N))
            out[p] = np.stack(cols, axis=1)
        return out


def _pack_np(col: np.ndarray, nw: int) -> np.ndarray:
    pad = np.zeros(nw * 64, dtype=np.uint8); pad[: len(col)] = col
    return np.packbits(pad.reshape(nw, 64)[:, ::-1], axis=1).view(">u8").astype(np.uint64).reshape(nw)


def _unpack_np(w: np.ndarray, N: int) -> np.ndarray:
    bits = np.unpackbits(w.astype(">u8").view(np.uint8).reshape(-1, 8), axis=1).reshape(-1, 64)[:, ::-1]
    return bits.reshape(-1)[:N].astype(bool)


# ---- integer lanes <-> port bits -------------------------------------------------------------------------------

def lanes_to_bits(x: np.ndarray, bits: int) -> np.ndarray:
    """int [N, lanes] -> uint8 [N, lanes*bits], lane i at bits [i*bits, (i+1)*bits), two's complement."""
    x = np.asarray(x, dtype=np.int64) & ((1 << bits) - 1)
    sh = np.arange(bits, dtype=np.int64)
    return ((x[:, :, None] >> sh[None, None, :]) & 1).reshape(x.shape[0], -1).astype(np.uint8)


def bits_to_lanes(b: np.ndarray, lanes: int, bits: int, signed: bool) -> np.ndarray:
    b = np.asarray(b, dtype=np.int64).reshape(b.shape[0], lanes, bits)
    v = (b << np.arange(bits, dtype=np.int64)[None, None, :]).sum(axis=2)
    if signed:
        v = np.where(v >= (1 << (bits - 1)), v - (1 << bits), v)
    return v
