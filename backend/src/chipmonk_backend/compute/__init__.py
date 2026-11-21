"""Where agents run: ``local``, ``flex`` (a team Mac) or ``on_demand`` (RunPod pods).

Public surface: :class:`Runner`, :func:`runner_for` and the vocabulary in
:mod:`chipmonk_backend.compute.modes`. The RunPod lane lives in
:mod:`chipmonk_backend.compute.runpod` and is imported only when selected.
"""

from chipmonk_backend.compute.base import Runner
from chipmonk_backend.compute.factory import runner_for
from chipmonk_backend.compute.flex import FlexRunner, FlexUnavailableError
from chipmonk_backend.compute.local import LocalRunner

__all__ = ["FlexRunner", "FlexUnavailableError", "LocalRunner", "Runner", "runner_for"]
