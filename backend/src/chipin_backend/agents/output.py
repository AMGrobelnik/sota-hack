"""Checking what an agent produced: the structured-output file and expected files.

Shared by both agent backends. The output FILE is
the source of truth: the agent writes its result as JSON to a file named in
the last prompt, the backend validates it against ``spec.output_schema``, and
on failure re-prompts the SAME session with every validation error. The wording
names no tool, so each backend's own file tools can satisfy it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import exceptions as schema_errors
from jsonschema import validators

#: The file the agent writes its structured output to, inside its workdir.
STRUCT_OUT_FILENAME = ".chipin_struct_out.json"

#: Schema violations listed in one feedback message; the rest are counted.
MAX_REPORTED_ERRORS = 20

_SIZE_VALIDATORS: dict[str, tuple[str, str]] = {
    "maxLength": ("at most", "characters"),
    "minLength": ("at least", "characters"),
    "maxItems": ("at most", "items"),
    "minItems": ("at least", "items"),
}


def struct_out_instruction(schema: dict[str, Any], output_file: str) -> str:
    """The suffix appended to the last prompt when an output schema is set."""
    return (
        f"\n\n---\n\n"
        f"Output the result as JSON to: `{output_file}`\n\n"
        f"JSON Schema:\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```\n\n"
        f"IMPORTANT: this task is NOT complete until `{output_file}` exists and "
        f"contains JSON matching the schema above."
    )


def _size_detail(error: schema_errors.ValidationError) -> str:
    """The limit and actual size for a size violation (``" (at most 50 characters, got 56)"``)."""
    spec = _SIZE_VALIDATORS.get(str(error.validator))
    if spec is None or not hasattr(error.instance, "__len__"):
        return ""
    relation, unit = spec
    return f" ({relation} {error.validator_value} {unit}, got {len(error.instance)})"


def _format_schema_errors(errors: list[schema_errors.ValidationError]) -> str:
    """One message naming every distinct violation, capped at :data:`MAX_REPORTED_ERRORS`."""
    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    truncated = 0
    for error in errors:
        loc = ".".join(str(p) for p in error.absolute_path) or "<root>"
        key = (loc, str(error.validator), error.message)
        if key in seen:
            continue
        seen.add(key)
        if len(lines) >= MAX_REPORTED_ERRORS:
            truncated += 1
            continue
        lines.append(f"  - at `{loc}`: {error.message}{_size_detail(error)}")
    more = f"\n  - ...plus {truncated} more violation(s)." if truncated else ""
    count = "1 problem" if len(lines) == 1 else f"{len(lines)} problems"
    return (
        f"Schema validation found {count}; fix ALL of them at once:\n"
        + "\n".join(lines)
        + more
        + "\nEvery required field must be present and every field type must match the schema."
    )


def validate_struct_out(
    path: Path, schema: dict[str, Any], *, output_file: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Read and validate the output file: ``(data, None)`` when valid, else ``(data|None, why)``.

    ``output_file`` is the name the instruction used, restated in the error so
    the agent can find its way back to the right target.
    """
    if not path.exists():
        return None, (
            f"The output file `{output_file}` does not exist yet.\n\n"
            f"{struct_out_instruction(schema, output_file)}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        return None, (
            f"The file `{output_file}` does not contain valid JSON: {err}. "
            f"Rewrite the entire file with well-formed JSON."
        )
    validator = validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(data), key=schema_errors.relevance)
    if errors:
        return data if isinstance(data, dict) else None, _format_schema_errors(errors)
    if not isinstance(data, dict):
        return None, f"The file `{output_file}` must hold a JSON object, not {type(data).__name__}."
    return data, None


def validation_feedback(error: str, attempt: int, *, output_file: str) -> str:
    """The corrective prompt sent on the same session after a failed validation."""
    return (
        f"<validation-feedback>\n"
        f"Attempt {attempt} failed validation.\n\n"
        f"{error}\n\n"
        f"Produce `{output_file}` again so it contains corrected JSON that matches "
        f"the schema. Do not invent new fields.\n"
        f"</validation-feedback>"
    )


def missing_files(workdir: Path, expected: list[str]) -> list[str]:
    """The entries of ``expected`` (relative to ``workdir``) that are absent or empty."""
    missing = []
    for rel in expected:
        path = workdir / rel
        if not path.exists() or (path.is_file() and path.stat().st_size == 0):
            missing.append(rel)
    return missing


def missing_files_feedback(missing: list[str]) -> str:
    """The corrective prompt naming the required files that are still missing."""
    listed = "\n".join(f"- {m}" for m in missing)
    return (
        f"The following required files are missing:\n\n{listed}\n\n"
        "Create these files now. The task is not complete until all required files exist."
    )


def review_output(
    workdir: Path,
    schema: dict[str, Any] | None,
    expected: list[str],
    *,
    attempt: int,
    output_file: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Both checks at once: ``(structured_output, corrective_prompt_or_None)``.

    The corrective prompt answers the first failing check (schema first, then
    expected files); ``None`` means the output is complete.
    """
    data = None
    if schema is not None:
        data, error = validate_struct_out(workdir / STRUCT_OUT_FILENAME, schema, output_file=output_file)
        if error is not None:
            return None, validation_feedback(error, attempt, output_file=output_file)
    missing = missing_files(workdir, expected)
    if missing:
        return data, missing_files_feedback(missing)
    return data, None


#: Most files listed in :attr:`AgentResult.files`.
MAX_LISTED_FILES = 1000


def written_files(workdir: Path) -> list[str]:
    """Regular files under ``workdir``, relative and sorted.

    Skips the output file and anything under a dot-directory (``.venv``,
    ``.git``), and stops at :data:`MAX_LISTED_FILES`.
    """
    if not workdir.is_dir():
        return []
    found: list[str] = []
    for path in workdir.rglob("*"):
        rel = path.relative_to(workdir)
        if any(part.startswith(".") for part in rel.parts) or not path.is_file():
            continue
        found.append(str(rel))
        if len(found) >= MAX_LISTED_FILES:
            break
    return sorted(found)


__all__ = [
    "STRUCT_OUT_FILENAME",
    "missing_files",
    "missing_files_feedback",
    "review_output",
    "struct_out_instruction",
    "validate_struct_out",
    "validation_feedback",
    "written_files",
]
