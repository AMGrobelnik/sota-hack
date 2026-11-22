"""Default streaming output is bit-identical to the base branch (origin/ant/chip-lab at 3a49ed5).

tests/fixtures/stream_golden.json holds SHA-256 digests of the wrapper Verilog and of the info JSON that
compile-stream writes, produced by the base branch's emit/stream.py for every existing fixture. Any change to the
default (no postproc, no channel_serial) output fails here, byte for byte.
"""
import hashlib
import json
from pathlib import Path

import pytest

from chiplab.emit.stream import emit_stream
from chiplab.ingest.intnn import to_ir
from chiplab.ir.schema import validate

HERE = Path(__file__).parent
GOLDEN = HERE / "fixtures" / "stream_golden.json"


def fixture_irs() -> dict:
    from test_fpga import tiny_ir
    from test_stream import wide_ir
    irs = {"spike_best": to_ir(json.loads((HERE.parent / "fixtures" / "spike_best.json").read_text())),
           "wide": wide_ir(), "tiny": validate(tiny_ir()),
           "one": validate({"ir": "chipir/1", "name": "one", "inputs": [{"name": "x", "lanes": 1, "bits": 5, "signed": True}],
                            "nodes": [{"id": "a", "op": "abs", "src": "x"}], "outputs": [{"name": "y", "src": "a"}]})}
    for f in sorted((HERE / "fixtures" / "m3_run").glob("*.json")):
        irs[f"m3_{f.stem}"] = validate(json.loads(f.read_text()))
    return irs


def _digests(ir: dict, tt: bool, **kw) -> dict:
    text, sinfo = emit_stream(ir, tt=tt, **kw)
    return {"verilog_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "info_sha256": hashlib.sha256(json.dumps(sinfo, default=str).encode()).hexdigest(),
            "verilog_bytes": len(text.encode())}


CASES = [(n, tt) for n in fixture_irs() for tt in (True, False)]


@pytest.mark.parametrize("name,tt", CASES, ids=[f"{n}-{'tt' if t else 'generic'}" for n, t in CASES])
def test_default_stream_is_byte_identical(name, tt):
    gold = json.loads(GOLDEN.read_text())
    ir = fixture_irs()[name]
    key = f"{name}_{'tt' if tt else 'generic'}"
    assert _digests(ir, tt) == gold[key]
    # explicit "off" options are the default too
    assert _digests(ir, tt, postproc=None, channel_serial=None) == gold[key]


def test_golden_covers_every_fixture():
    assert set(json.loads(GOLDEN.read_text())) == {f"{n}_{'tt' if t else 'generic'}" for n, t in CASES}
