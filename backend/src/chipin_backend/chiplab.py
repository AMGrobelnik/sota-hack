"""The optional chip lab: how an agent finds the ``chiplab`` command and its install.

The chip lab (``chiplab/`` in the sota-hack repository) turns a trained model
into a verified, measured chip. When a lab tool runs in an agent's working
folder it reports through the ``./progress`` helper by itself, so the backend
only has to let the agent reach the lab:

- ``CHIPIN_CHIPLAB_BIN``: a folder holding the ``chiplab`` command (the
  launcher the lab's ``scripts/install.sh`` writes, or the lab's
  ``.venv/bin``). It goes first on the agent's ``PATH``.
- ``CHIPLAB_CONFIG`` and ``CHIPLAB_USER_DIR``: the lab's own settings for an
  install outside ``~/.chiplab`` and ``~/.config/chiplab``. They are paths,
  not secrets, and pass to the agent unchanged when set.

When the lab is on, the agent also gets ``CHIPIN_PROGRESS_CHIP=1``: the
``./progress`` helper takes ``metric ... --chip <design_id>`` and
``chosen <design_id>``, so the lab tags each number with its chip.

With none of these set, the lab counts as present only when ``chiplab`` is
already on the agent's ``PATH`` (the lab's default install puts it in
``~/.local/bin``). Otherwise it is off: the agent's environment and
instructions stay exactly as without a lab.

When the lab is on, each run also gets the chip-lab skill
(``skills/chiplab`` in this package, see :func:`install_skill`): written into
the run's working folder where the agent's harness discovers skills, with the
installed lab's own tool reference copied in as ``references/tools.md``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from collections.abc import Mapping
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from loguru import logger

#: Folder holding the ``chiplab`` command; put first on the agent's PATH.
CHIPLAB_BIN_ENV = "CHIPIN_CHIPLAB_BIN"
#: The lab's own variables, passed to the agent when set.
CHIPLAB_PASSED_NAMES: tuple[str, ...] = ("CHIPLAB_CONFIG", "CHIPLAB_USER_DIR")
CHIPLAB_COMMAND = "chiplab"
#: Set to ``1`` for the agent when the lab is on: this backend's ``./progress``
#: takes ``metric ... --chip <design_id>`` and ``chosen <design_id>``.
PROGRESS_CHIP_ENV = "CHIPIN_PROGRESS_CHIP"
#: The paragraph added to the agent's standing instructions when the lab is on.
CHIPLAB_INSTRUCTIONS_PATH = Path(__file__).parent / "api" / "chiplab.md"


def chiplab_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Agent environment entries that let it call the lab; ``{}`` when the lab is off.

    ``source`` (default ``os.environ``) is the launcher's environment. A
    ``CHIPIN_CHIPLAB_BIN`` without an executable ``chiplab`` in it is a
    misconfiguration: logged, and the lab stays off.
    """
    src = os.environ if source is None else source
    path = src.get("PATH", "")
    bin_dir = src.get(CHIPLAB_BIN_ENV, "").strip()
    if bin_dir:
        command = Path(bin_dir).expanduser() / CHIPLAB_COMMAND
        if not (command.is_file() and os.access(command, os.X_OK)):
            logger.warning(
                "{} is set but {} is not an executable chiplab command; chip lab off",
                CHIPLAB_BIN_ENV,
                command,
            )
            return {}
        path = os.pathsep.join(p for p in (str(command.parent), path) if p)
    elif not path or shutil.which(CHIPLAB_COMMAND, path=path) is None:
        return {}
    env = {"PATH": path, PROGRESS_CHIP_ENV: "1"}
    env.update({name: src[name] for name in CHIPLAB_PASSED_NAMES if src.get(name)})
    return env


def chiplab_available(source: Mapping[str, str] | None = None) -> bool:
    """Whether an agent started from ``source`` can call the chip lab."""
    return bool(chiplab_env(source))


def chiplab_instructions() -> str:
    """The chip-lab paragraph of the standing instructions."""
    return CHIPLAB_INSTRUCTIONS_PATH.read_text(encoding="utf-8")


# ---- the chip-lab skill ----

#: The skill's name: its folder name and the ``name`` in its front matter.
SKILL_NAME = "chiplab"
#: The claude CLI gets the skill as a session-only plugin (``--plugin-dir``, see
#: ``agents/claude_cli.py``): this folder under its working folder is the plugin's
#: root, with the manifest and a ``skills/`` folder. The project setting source
#: would also find ``.claude/skills/``, but it loads every CLAUDE.md above the
#: working folder and the user's own, so it stays off.
CLAUDE_PLUGIN_NAME = "chipin"
CLAUDE_PLUGIN_DIR = Path(".claude") / "plugins" / CLAUDE_PLUGIN_NAME
CLAUDE_PLUGIN_MANIFEST = Path(".claude-plugin") / "plugin.json"
#: Where each agent harness discovers skills, relative to its working folder:
#: the claude CLI reads ``skills/<name>/SKILL.md`` in the plugin above; OpenHands
#: reads AgentSkills folders from ``.agents/skills/`` (see ``agents/openrouter_agent.py``).
SKILL_DIRS: dict[str, Path] = {
    "claude_cli": CLAUDE_PLUGIN_DIR / "skills",
    "openrouter": Path(".agents") / "skills",
}
#: The dashboard's agent names for the same harnesses.
HARNESS_ALIASES = {"claude": "claude_cli"}
#: The lab's reference inside an installed skill, copied from the lab at install time.
TOOLS_REFERENCE = Path("references") / "tools.md"
#: How long the lab may take to print its reference.
REFERENCE_TIMEOUT_S = 60
#: The launcher the lab's ``scripts/install.sh`` writes: ``exec "<lab>/.venv/bin/chiplab" "$@"``.
_LAUNCHER_TARGET = re.compile(r'exec\s+"([^"]+)"')


def skill_files() -> Traversable:
    """The skill as shipped in this package (``chipin_backend/skills/chiplab``)."""
    return resources.files("chipin_backend") / "skills" / SKILL_NAME


def install_skill(workspace: Path, harness: str, source: Mapping[str, str] | None = None) -> Path | None:
    """Install the chip-lab skill where ``harness`` discovers skills in ``workspace``.

    Only when the lab is on for an agent started from ``source`` (the same
    test as :func:`chiplab_env`) and only for a harness that loads skills
    (``claude_cli``/``claude`` or ``openrouter``); otherwise nothing is written
    and ``None`` is returned. Idempotent: a second call rewrites the same files.
    For the claude CLI the skill sits in a plugin folder
    (:data:`CLAUDE_PLUGIN_DIR`) whose manifest is written too. Returns the
    skill's folder.
    """
    name = HARNESS_ALIASES.get(harness, harness)
    folder = SKILL_DIRS.get(name)
    if folder is None or not chiplab_env(source):
        return None
    if name == "claude_cli":
        manifest = workspace / CLAUDE_PLUGIN_DIR / CLAUDE_PLUGIN_MANIFEST
        manifest.parent.mkdir(parents=True, exist_ok=True)
        body = {"name": CLAUDE_PLUGIN_NAME, "description": "ChipIn run tools: the chip-lab skill"}
        manifest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    dest = write_skill(workspace / folder / SKILL_NAME, source)
    logger.info("chip-lab skill installed for {} at {}", harness, folder / SKILL_NAME)
    return dest


def write_skill(dest: Path, source: Mapping[str, str] | None = None) -> Path:
    """Write the skill folder to ``dest``: the packaged files plus the lab's own reference.

    ``references/tools.md`` is the installed lab's generated reference
    (``chiplab agent-doc``) under a one-line header naming the lab version;
    when the lab is off or its reference cannot be read, the file is left out
    (SKILL.md then points the agent at the lab's own help) and a warning is
    logged.
    """
    dest.mkdir(parents=True, exist_ok=True)
    _copy_tree(skill_files(), dest)
    tools = dest / TOOLS_REFERENCE
    reference = lab_reference(source)
    if reference is None:
        tools.unlink(missing_ok=True)
        logger.warning("chip-lab skill at {} has no {}: the lab's reference was not found", dest, tools.name)
    else:
        tools.parent.mkdir(parents=True, exist_ok=True)
        tools.write_text(reference, encoding="utf-8")
    return dest


def lab_reference(source: Mapping[str, str] | None = None) -> str | None:
    """The installed lab's tool reference with a header line naming its version; ``None`` if unavailable.

    The text is what the lab itself prints for ``chiplab agent-doc`` (its
    ``AGENT.md``, generated from the live tool registry), so it cannot drift
    from the lab the agent calls. The lab's files are only read.
    """
    src = os.environ if source is None else source
    env = chiplab_env(src)
    command = shutil.which(CHIPLAB_COMMAND, path=env.get("PATH")) if env else None
    if command is None:
        return None
    run_env = {name: src[name] for name in ("HOME", "LANG", "TMPDIR") if src.get(name)}
    run_env.update(env)
    try:
        proc = subprocess.run(
            [command, "agent-doc"],
            env=run_env,
            capture_output=True,
            text=True,
            timeout=REFERENCE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("chiplab agent-doc did not run: {}", exc)
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        logger.warning("chiplab agent-doc failed (exit {}): {}", proc.returncode, proc.stderr.strip()[-300:])
        return None
    header = (
        f"> Copied from the installed chip lab ({lab_version(Path(command))}) by `chiplab agent-doc` "
        "when this skill was installed; do not edit."
    )
    return f"{header}\n\n{proc.stdout.strip()}\n"


def lab_version(command: Path) -> str:
    """``chiplab <version>, commit <sha>`` for the lab behind ``command``, as far as it can be read.

    Follows the lab's launcher to its ``.venv/bin/chiplab``, then reads the
    version from the nearest ``pyproject.toml`` and the last commit touching
    the lab's folder from git. Unknown parts are left out.
    """
    target = _launcher_target(command)
    project = next((p for p in target.parents if (p / "pyproject.toml").is_file()), None)
    if project is None:
        return "chiplab, version unknown"
    parts = [f"chiplab {_pyproject_version(project / 'pyproject.toml') or 'version unknown'}"]
    if commit := _git_commit(project):
        parts.append(f"commit {commit}")
    return ", ".join(parts)


def _launcher_target(command: Path) -> Path:
    real = command.resolve()
    try:
        head = real.read_text(encoding="utf-8", errors="ignore")[:2000]
    except OSError:
        return real
    match = _LAUNCHER_TARGET.search(head) if head.startswith("#!/bin/sh") else None
    return Path(match.group(1)).resolve() if match else real


def _pyproject_version(path: Path) -> str | None:
    try:
        version = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {}).get("version")
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return str(version) if version else None


def _git_commit(folder: Path) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        proc = subprocess.run(
            [git, "-C", str(folder), "log", "-1", "--format=%h", "--", "."],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _copy_tree(src: Traversable, dest: Path) -> None:
    """Copy a package resource folder to ``dest``, overwriting files of the same name."""
    for item in src.iterdir():
        if item.name.startswith(("__", ".")):
            continue
        target = dest / item.name
        if item.is_dir():
            target.mkdir(exist_ok=True)
            _copy_tree(item, target)
        else:
            target.write_bytes(item.read_bytes())


__all__ = [
    "CHIPLAB_BIN_ENV",
    "CHIPLAB_COMMAND",
    "CHIPLAB_INSTRUCTIONS_PATH",
    "CHIPLAB_PASSED_NAMES",
    "CLAUDE_PLUGIN_DIR",
    "CLAUDE_PLUGIN_MANIFEST",
    "CLAUDE_PLUGIN_NAME",
    "PROGRESS_CHIP_ENV",
    "SKILL_DIRS",
    "SKILL_NAME",
    "TOOLS_REFERENCE",
    "chiplab_available",
    "chiplab_env",
    "chiplab_instructions",
    "install_skill",
    "lab_reference",
    "lab_version",
    "skill_files",
    "write_skill",
]
