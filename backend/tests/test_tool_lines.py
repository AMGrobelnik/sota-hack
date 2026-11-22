"""The one-line gist a collapsed tool row shows, built from the call itself."""

from __future__ import annotations

from pathlib import Path

import pytest

from chipin_backend.api.translate import (
    LINE_MAX,
    command_line,
    line_from_summary,
    tool_line,
)

RUN = "/home/u/proj/backend/runs/20261122-131313-ebd95a/workspace"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("cd /a/b/c && python train.py --epochs 3", "python train.py --epochs 3"),
        ("cd ../..; ls . data", "ls . data"),
        (f"cd {RUN}/agents/a1\npython3 fit.py", "python3 fit.py"),
        ("FOO=1 BAR='x y' python run.py", "python run.py"),
        ("timeout 60 ./subagent wait --stage propose", "./subagent wait --stage propose"),
    ],
)
def test_setup_hops_and_prefixes_are_dropped(command: str, expected: str) -> None:
    assert command_line(command) == expected


def test_a_lone_cd_keeps_its_folder_short() -> None:
    assert command_line(f"cd {RUN}/agents/a1") == "cd agents/a1"


def test_long_paths_keep_their_last_two_parts() -> None:
    line = command_line("cat ../../.claude/plugins/chipin/skills/chiplab/references/tools.md")
    assert line == "cat references/tools.md"
    assert command_line(f"python {RUN}/agents/a2/rf.py") == "python a2/rf.py"
    assert command_line("cat data/val.json") == "cat data/val.json"  # two parts stay
    assert "https://example.org/a/b/c" in command_line("curl -s https://example.org/a/b/c")


def test_the_workspace_is_shown_relative() -> None:
    assert command_line(f"python {RUN}/train.py", Path(RUN)) == "python train.py"


def test_a_heredoc_shows_its_command_not_its_body() -> None:
    command = "cat > spec.md <<'EOF'\n# Spec\n- a; b && c\nEOF"
    assert command_line(command) == "cat > spec.md"
    assert command_line("mkdir -p data && cat > data/gen.py <<EOF\nimport x\nEOF") == (
        "mkdir -p data (+1 more)"
    )


def test_a_pipeline_keeps_its_first_command() -> None:
    assert command_line("cat result.json | head -c 400 2>&1") == "cat result.json"
    assert command_line("grep -n 'a|b' notes.md | wc -l") == "grep -n 'a|b' notes.md"


def test_several_commands_show_the_first_meaningful_one_and_a_count() -> None:
    command = "ls -la; cat spec.json; ./progress stage spec started; ./subagent --help 2>&1 | head -30"
    assert command_line(command) == "ls -la (+2 more)"
    assert command_line('C="--chip ref"\n./progress metric auc 0.9 $C\npython eval.py') == "python eval.py"
    assert command_line("for i in 1 2 3; do ./subagent wait; done") == "./subagent wait"


def test_quoted_separators_do_not_split() -> None:
    assert command_line('echo "a; b" && python x.py "c && d"') == 'python x.py "c && d"'
    assert command_line('C="note {\\"x\\": 1} now"\n./subagent start "go"') == './subagent start "go"'
    assert command_line('./subagent wait | grep -q "a\\|b" || break') == "./subagent wait"


def test_long_lines_end_on_a_word_with_an_ellipsis() -> None:
    line = command_line("python train.py " + " ".join(f"--flag{i} value{i}" for i in range(40)))
    assert len(line) <= LINE_MAX
    assert line.endswith("…")
    assert line[:-1].split()[-1].startswith(("--flag", "value"))
    assert not line[:-1].endswith(" ")


@pytest.mark.parametrize("command", ["", "   ", "\n\n"])
def test_an_empty_command_has_no_line(command: str) -> None:
    assert command_line(command) == ""


def test_the_agents_own_description_wins() -> None:
    args = {"command": "cd /x/y/z && make all", "description": "Build the firmware"}
    assert tool_line("Bash", args) == "Build the firmware"
    assert tool_line("terminal", {"command": "ls"}, description="List the workspace") == "List the workspace"
    assert tool_line("Bash", {"command": "cd /x/y/z && make all"}) == "Ran make all"
    assert tool_line("terminal", {"command": ""}) == "terminal"
    assert tool_line("Read", {"file_path": "brief.md"}) == "Read brief.md"


def test_an_old_summary_is_reshaped() -> None:
    old = f"Ran cd {RUN}; ls . dat…"
    assert line_from_summary(old) == "Ran ls ."  # the cut word goes
    assert line_from_summary("Read brief.md") == "Read brief.md"
    assert line_from_summary(f"Ran cd {RUN}/agents/a1") == "Ran cd agents/a1"
