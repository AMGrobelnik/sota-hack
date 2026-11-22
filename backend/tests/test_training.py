"""The optional training Python: the agent's environment and standing instructions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from chipin_backend.agents.env import build_agent_env
from chipin_backend.api.manager import standing_instructions
from chipin_backend.chiplab import CHIPLAB_BIN_ENV, chiplab_instructions
from chipin_backend.training import TRAIN_PYTHON_ENV, train_available, train_env, training_instructions


def _python(folder: Path) -> Path:
    """An executable stand-in for a training interpreter."""
    folder.mkdir(parents=True, exist_ok=True)
    python = folder / "python"
    python.write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n', encoding="utf-8")
    python.chmod(0o755)
    return python


def _lab(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    command = folder / "chiplab"
    command.write_text("#!/bin/sh\necho '{}'\n", encoding="utf-8")
    command.chmod(0o755)
    return folder


def test_training_off_by_default() -> None:
    base = {"PATH": "/usr/bin:/bin"}
    assert train_env(base) == {}
    assert not train_available(base)
    assert TRAIN_PYTHON_ENV not in build_agent_env(base=base)
    text = standing_instructions(base)
    assert "CHIPIN_TRAIN_PYTHON" not in text
    assert "synthetic" not in text.lower()


def test_train_python_reaches_the_agent_but_not_its_path(tmp_path: Path) -> None:
    python = _python(tmp_path / "train-venv" / "bin")
    base = {"PATH": "/usr/bin:/bin", TRAIN_PYTHON_ENV: str(python)}
    env = build_agent_env(base=base)
    assert env[TRAIN_PYTHON_ENV] == str(python)
    assert env["PATH"] == "/usr/bin:/bin"
    proc = subprocess.run(
        ["/bin/sh", "-c", '"$CHIPIN_TRAIN_PYTHON" -c "print(6 * 7)"'],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "42"


def test_train_python_that_is_not_executable_leaves_training_off(tmp_path: Path) -> None:
    missing = {"PATH": "/bin", TRAIN_PYTHON_ENV: str(tmp_path / "no-such-python")}
    plain = tmp_path / "python"
    plain.write_text("not a program", encoding="utf-8")
    for base in (missing, {"PATH": "/bin", TRAIN_PYTHON_ENV: str(plain)}, {TRAIN_PYTHON_ENV: "  "}):
        assert train_env(base) == {}
        assert TRAIN_PYTHON_ENV not in build_agent_env(base=base)
        assert "CHIPIN_TRAIN_PYTHON" not in standing_instructions(base)


def test_instructions_carry_the_training_paragraph_only_when_set(tmp_path: Path) -> None:
    python = _python(tmp_path / "bin")
    off = standing_instructions({"PATH": "/bin"})
    on = standing_instructions({"PATH": "/bin", TRAIN_PYTHON_ENV: str(python)})
    paragraph = training_instructions()
    assert on == f"{off.rstrip()}\n\n{paragraph}"
    flat = " ".join(paragraph.split())
    for phrase in (
        '"$CHIPIN_TRAIN_PYTHON"',
        "data/assumptions.md",
        "Split by patient",
        "before any training",
        "held-out patients only",
        "false alarms per hour",
        "per patient and pooled",
        '"synthetic data"',
        "never clinical evidence",
        "ingest-model",
        "./progress metric synthetic_sensitivity_pct",
        "./progress metric synthetic_false_alarms_per_h",
        "patients_pass",
        "patients_total",
    ):
        assert phrase in flat, phrase


def test_training_and_lab_paragraphs_together(tmp_path: Path) -> None:
    base = {
        "PATH": "/bin",
        TRAIN_PYTHON_ENV: str(_python(tmp_path / "bin")),
        CHIPLAB_BIN_ENV: str(_lab(tmp_path / "lab-bin")),
    }
    text = standing_instructions(base)
    assert text.endswith(chiplab_instructions())
    assert training_instructions() in text
    assert text.index("Training (reference and finetune)") < text.index("Chip lab")
    env = build_agent_env(base=base)
    assert env[TRAIN_PYTHON_ENV] == base[TRAIN_PYTHON_ENV]
    assert env["PATH"] == f"{tmp_path / 'lab-bin'}:/bin"
