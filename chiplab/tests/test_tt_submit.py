"""TT submission readiness: a lab TT project is checked, fixed and exported as a submission repo (no network)."""
import subprocess

import pytest
import yaml

from chiplab import config

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (config.find_bin("iverilog") and config.find_bin("verilator") and config.find_bin("yosys")),
                                 reason="OSS CAD Suite not installed"),
              pytest.mark.skipif(not (config.TT_TOOLS / "tt_tool.py").exists(), reason="tt-support-tools not installed")]

TINY = {"ir": "chipir/1", "name": "tt_tiny", "inputs": [{"name": "x", "lanes": 3, "bits": 4, "signed": False}],
        "nodes": [{"id": "s", "op": "matvec", "src": "x", "W": [[1, -1, 1]], "b": [-2]}, {"id": "y", "op": "cmp", "src": "s", "rel": "gt", "t": [0]}],
        "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def test_readiness_fix_and_export(tmp_path):
    import chiplab.api as lab
    from chiplab.hw.tt_submit import export_submission_repo, readiness
    d = lab.compile_ir(ir=TINY)["design_id"]
    t = lab.tt_package(design_id=d, harden=False, vectors=16, force=True)
    assert t["status"] == "ok" and t["user_config_ok"], t
    r = readiness(t["folder"], run_precheck_if_hardened=False)
    names = {c["check"]: c for c in r["checks"]}
    for must in ("top module ports", "verilator lint -Wall", "cocotb RTL test", "LICENSE (Apache-2.0)", "tt/ and runs/ not committed"):
        assert names[must]["ok"], names[must]
    e = export_submission_repo(t["folder"], tmp_path / "repo")
    for f in ("info.yaml", "LICENSE", "README.md", "docs/info.md", "test/test.py", "test/vectors.json", ".github/workflows/gds.yaml"):
        assert f in e["files"], (f, e["files"])
    assert not any(f.startswith("tt/") for f in e["files"])
    info = yaml.safe_load((tmp_path / "repo" / "info.yaml").read_text())
    assert all(str(info["pinout"][f"{g}[{i}]"]).strip() for g in ("ui", "uo", "uio") for i in range(8))
    assert subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=tmp_path / "repo", capture_output=True, text=True).stdout.strip() == "1"
    r2 = readiness(tmp_path / "repo", run_precheck_if_hardened=False)
    assert r2["ready"], r2["blocking"]
