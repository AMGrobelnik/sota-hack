"""Where agents run: ``local``, ``flex`` (a team Mac) or ``on_demand`` (RunPod pods).

Public surface: :class:`Runner`, :func:`runner_for` and the vocabulary in
:mod:`chipin_backend.compute.modes`. The RunPod lane lives in
:mod:`chipin_backend.compute.runpod` and is imported only when selected.
"""

from chipin_backend.compute.base import Runner
from chipin_backend.compute.factory import runner_for
from chipin_backend.compute.flex import FlexRunner, FlexUnavailableError
from chipin_backend.compute.local import LocalRunner

__all__ = ["FlexRunner", "FlexUnavailableError", "LocalRunner", "Runner", "runner_for"]
