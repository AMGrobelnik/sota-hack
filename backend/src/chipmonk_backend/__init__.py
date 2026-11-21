"""Chipmonk backend: run AI-scientist agents and record each run as a folder on disk.

Three subpackages with narrow seams between them:

* :mod:`chipmonk_backend.llm` - OpenRouter client and model presets.
* :mod:`chipmonk_backend.agents` - agent backends (Claude CLI, OpenRouter, stub)
  behind :class:`~chipmonk_backend.agents.base.AgentBackend`.
* :mod:`chipmonk_backend.compute` - where an agent runs (local, Flex on a Mac,
  On Demand on RunPod) behind :class:`~chipmonk_backend.compute.base.Runner`.

Shared core: :mod:`.config` (YAML schema and loader), :mod:`.log` (loguru
sinks), :mod:`.runs` (run folders and the JSONL event sink), :mod:`.orchestrate`
(one agent run end to end) and :mod:`.cli`.
"""

__version__ = "0.1.0"
