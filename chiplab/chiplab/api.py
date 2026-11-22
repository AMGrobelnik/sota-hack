"""Python API: every lab tool as a plain function returning a JSON-able dict.

    import chiplab.api as lab
    d = lab.ingest_model(format="intnn", model=params)["design_id"]
    lab.synthesize(design_id=d); lab.simulate(design_id=d, inputs="random")
"""
from __future__ import annotations

from chiplab import tools as _tools
from chiplab import tools_hw as _hw  # noqa: F401
from chiplab import tools_jobs as _jobs  # noqa: F401

TOOLS = _tools.TOOLS
__all__ = sorted(TOOLS)


def __getattr__(name: str):
    if name in TOOLS:
        return TOOLS[name]["fn"]
    raise AttributeError(name)


def __dir__():
    return __all__
