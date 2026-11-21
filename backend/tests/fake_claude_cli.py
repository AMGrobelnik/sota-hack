"""A stand-in for the ``claude`` CLI, driven by the real PTY driver in tests.

It draws a status line with the bypass-permissions marker, reads bracketed
pastes submitted with Enter, and for each prompt journals what the real CLI
journals: the user turn, a tool call and its result, an assistant reply and
``turn_duration``, in ``$CLAUDE_CONFIG_DIR/projects/<slug>/<session>.jsonl``.
A prompt naming the structured-output file gets that file written. ``/cost``
draws a cost dialog; ``/quit`` journals a ``cost-state`` record and exits.

Run as ``python fake_claude_cli.py <claude args>``; ``--version`` prints one.
"""

from __future__ import annotations

import json
import os
import re
import sys
import termios
import tty
import uuid
from collections.abc import Callable
from pathlib import Path

PASTE_START, PASTE_END = "\x1b[200~", "\x1b[201~"


def slug(cwd: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "-", cwd)


def main() -> None:
    args = sys.argv[1:]
    if "--version" in args:
        print("2.1.400 (Claude Code)")
        return
    session = args[args.index("--session-id" if "--session-id" in args else "--resume") + 1]
    config = Path(os.environ["CLAUDE_CONFIG_DIR"])
    transcript = config / "projects" / slug(os.getcwd()) / f"{session}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)

    def journal(record: dict) -> None:
        with transcript.open("a") as f:
            f.write(json.dumps({"uuid": str(uuid.uuid4()), "isSidechain": False, **record}) + "\n")

    def draw(text: str) -> None:
        sys.stdout.write(text.replace("\n", "\r\n"))
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        draw("fake claude\n⏵⏵ bypass permissions on\n")
        buf = ""
        turn = 0
        while True:
            chunk = os.read(fd, 65536).decode("utf-8", "replace")
            if not chunk:
                return
            buf += chunk
            while "\r" in buf:
                line, buf = buf.split("\r", 1)
                if PASTE_START in line and PASTE_END in line:
                    prompt = line.split(PASTE_START, 1)[1].split(PASTE_END, 1)[0]
                    turn += 1
                    run_turn(prompt, turn, journal)
                    draw(f"\nturn {turn} done\n")
                    continue
                command = re.sub(r"[\x00-\x1f\x7f]", "", line)
                if command == "/cost":
                    draw("\nTotal cost:            $0.0123\nUsage by model:\n")
                elif command == "/quit":
                    journal({"type": "cost-state", "totalCostUSD": 0.0456, "modelUsage": {}})
                    return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def run_turn(prompt: str, turn: int, journal: Callable[[dict], None]) -> None:
    journal({"type": "user", "message": {"role": "user", "content": prompt}})
    call_id = f"toolu_{turn}"
    journal(
        {
            "type": "assistant",
            "message": {
                "id": f"msg_{turn}a",
                "content": [
                    {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": "echo"}}
                ],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            },
        }
    )
    Path("hello.txt").write_text("hello chipmonk\n")
    if ".chipmonk_struct_out.json" in prompt:
        Path(".chipmonk_struct_out.json").write_text(json.dumps({"file": "hello.txt", "ok": True}))
    journal(
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": "ok"}]},
        }
    )
    journal(
        {
            "type": "assistant",
            "message": {
                "id": f"msg_{turn}b",
                "content": [{"type": "text", "text": f"done {turn}"}],
                "usage": {"input_tokens": 120, "output_tokens": 5},
            },
        }
    )
    journal({"type": "system", "subtype": "turn_duration", "durationMs": 10})


if __name__ == "__main__":
    main()
