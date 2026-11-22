"""Load and validate a chipir/1 document (a dict, JSON text, or a path to a .json file)."""
from __future__ import annotations

import json
from pathlib import Path

from chiplab.ir.ranges import ranges
from chiplab.ir.schema import IRError, validate


def load(src) -> dict:
    if isinstance(src, dict):
        ir = src
    elif isinstance(src, (str, Path)) and str(src).lstrip().startswith("{"):
        ir = json.loads(str(src))
    else:
        ir = json.loads(Path(src).read_text())
    if not isinstance(ir, dict):
        raise IRError("chipir document must be a JSON object")
    validate(ir)
    ranges(ir)  # also checks lut inputs are 1-bit and values stay int64-safe
    ir.setdefault("meta", {})
    return ir
