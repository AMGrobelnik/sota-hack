"""Agent backends behind one small interface.

Public surface: :class:`AgentSpec`, :class:`AgentEvent`, :class:`AgentResult`,
:class:`EventSink`, :class:`AgentBackend` and :func:`backend_for`. Backend
modules (``claude_cli``, ``openrouter_agent``, ``stub``) are imported lazily
by name through :data:`BACKENDS`.
"""

from chipin_backend.agents.base import BACKENDS, AgentBackend, backend_class, backend_for
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventKind, EventSink

__all__ = [
    "BACKENDS",
    "AgentBackend",
    "AgentEvent",
    "AgentResult",
    "AgentSpec",
    "EventKind",
    "EventSink",
    "backend_class",
    "backend_for",
]
