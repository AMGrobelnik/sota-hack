"""Compute device for the batched netlist evaluator and training: CUDA, else Apple MPS, else numpy/CPU."""
from __future__ import annotations


def resolve(requested: str | None = "auto") -> str:
    """'auto' | 'cuda' | 'mps' | 'cpu' | 'numpy' -> a device that exists here ('numpy' means plain CPU numpy)."""
    req = (requested or "auto").lower()
    if req in ("numpy", "cpu"):
        return "numpy"
    try:
        import torch
    except Exception:
        return "numpy"
    if req in ("auto", "cuda", "gpu") and torch.cuda.is_available():
        return "cuda"
    if req in ("auto", "mps", "gpu", "cuda") and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "numpy"


def describe() -> dict:
    out = {"selected": resolve("auto")}
    try:
        import torch
        out.update(torch=torch.__version__, cuda=torch.cuda.is_available(),
                   mps=bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()))
        if torch.cuda.is_available():
            out["gpu"] = torch.cuda.get_device_name(0)
    except Exception as e:
        out["torch"] = f"not importable: {e}"
    return out
