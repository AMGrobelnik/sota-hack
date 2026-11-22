"""System temp and toolchain paths are scrubbed down to a label and the final file name."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chipin_backend.export import build_export
from chipin_backend.scrub import Scrubber
from test_history_export import _run_folder

SCRUB = Scrubber(home="/Users/janedoe", host_names=(), user="")
SESSION = "3f2a9c1e-77b4-4d0a-9c55-0123456789ab"


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("wrote /tmp/out.csv now", "wrote [tmp]/out.csv now"),
        ("wrote /private/tmp/run7/out.csv now", "wrote [tmp]/out.csv now"),
        ("/var/folders/zz/abc123/T/plot.png", "[tmp]/plot.png"),
        ("/private/var/folders/zz/abc123/T/tool-cache", "[tmp]/tool-cache"),
        ('open "/tmp/a b"', 'open "[tmp]/a b"'),
        ("see (/tmp/x/y.log), then", "see ([tmp]/y.log), then"),
        ("[/tmp/x/y.log]", "[[tmp]/y.log]"),
        ("dir /tmp/x/y/ end", "dir [tmp] end"),
        ("cwd /tmp", "cwd [tmp]"),
        ("PATH=/tmp/a/x:/tmp/b/y", "PATH=[tmp]/x:[tmp]/y"),
        ("cc 14.0 /opt/homebrew/Cellar/llvm/18.1/bin/clang", "cc 14.0 [toolchain]/clang"),
        ("/usr/local/lib/python3.12/site.py", "[toolchain]/site.py"),
        ("/nix/store/abc-gcc-13/bin/gcc", "[toolchain]/gcc"),
        ("InstalledDir: /Applications/Xcode.app/Contents/bin", "InstalledDir: [toolchain]/bin"),
        ("/opt", "[toolchain]"),
    ],
)
def test_each_shape_is_replaced(raw: str, want: str) -> None:
    assert SCRUB.text(raw) == want


def test_a_temp_path_with_a_project_folder_and_a_long_id_keeps_neither() -> None:
    raw = f"cat /private/tmp/chipin-demo-project/{SESSION}/501/result.json done"
    out = SCRUB.text(raw)
    assert out == "cat [tmp]/result.json done"
    assert "chipin-demo" not in out and SESSION not in out and "501" not in out


@pytest.mark.parametrize(
    "text",
    [
        "https://example.org/tmp/a/b.txt",
        "http://example.org/opt/x and https://example.org/usr/local/y",
        "and/or, 1/2, 3/4 of the tmp folder, opt/in, usr/local/bin",
        "/usr/bin/env python and /bin/sh and /usr/lib/x.so",
        "~/tmp/a.txt and ~/opt/b",
        "src/tmp/a.txt and ./tmp/x and ../opt/y",
        "workspace/report.md and /tmpfoo and /optional/x",
        "Applications/Foo and the /Applicationsx path",
    ],
)
def test_urls_fractions_home_and_relative_paths_are_unchanged(text: str) -> None:
    assert SCRUB.text(text) == text


def test_the_counts_include_system_paths() -> None:
    scrubber = Scrubber(home="/Users/janedoe", host_names=(), user="")
    scrubber.text("/tmp/a/b and /opt/x/y")
    assert scrubber.counts["system_paths"] == 2


def test_export_of_a_small_fixture_has_no_absolute_path_outside_home(tmp_path: Path) -> None:
    folder = _run_folder(tmp_path / "runs")
    api = folder / "api.json"
    record = json.loads(api.read_text(encoding="utf-8"))
    record["summary"] = (
        f"log /private/var/folders/ab/cd/T/{SESSION}/x.log\nld /usr/local/bin/ld and /opt/tc/bin/cc\n"
    )
    api.write_text(json.dumps(record), encoding="utf-8")
    text = json.dumps(build_export(folder, scrubber=Scrubber(home="/Users/janedoe", host_names=(), user="")))
    assert "[tmp]/x.log" in text and "[toolchain]/ld" in text
    assert SESSION not in text
    absolute = re.findall(r"(?<![\w/.~:\-])/(?:private|tmp|var|opt|usr|nix|Applications|Users|home)\b", text)
    assert absolute == []
