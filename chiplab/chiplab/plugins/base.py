"""Plugin interfaces. Everything task-specific in the lab is a plugin; the core never names a sensor or disease.

The AI scientist extends the lab by writing a plugin, running `chiplab plugin test <path>` (conformance, in a
subprocess) and `chiplab plugin register <path>` (stores the file's sha256; a changed file is refused).

Kinds:
    DatasetLoader    real recordings in   (must not define splits: the lab does that)
    SensorSimulator  simulated recordings in (meta.simulated=True, plus a list of stated assumptions)
    FrontEndStage    recording -> frames (off-chip, float), optionally lowerable to IR (on-chip)
    ModelFamily      population training of K candidates at once + lowering one candidate to chipir/1
                     (lower() MUST equal predict() bit for bit; conformance checks it)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from chiplab.data.contract import FrameStream, Recording


class DatasetLoader(ABC):
    name: str = ""
    version: str = "1"

    @abstractmethod
    def fetch(self, root: Path) -> None:
        """Download into root if missing (idempotent)."""

    @abstractmethod
    def recordings(self, root: Path) -> Iterator[Recording]:
        """Yield every recording, in a stable order."""

    def describe(self) -> dict:
        return {"name": self.name, "version": self.version}


class SensorSimulator(ABC):
    name: str = ""
    version: str = "1"

    @abstractmethod
    def simulate(self, n_subjects: int, params: dict, seed: int) -> Iterator[Recording]:
        """Yield simulated recordings; every one has meta['simulated'] = True."""

    @abstractmethod
    def assumptions(self, params: dict) -> list[str]:
        """Plain-language assumptions behind the simulation, shown to the clinician."""


class FrontEndStage(ABC):
    name: str = ""
    version: str = "1"
    onchip: bool = False

    @abstractmethod
    def frames(self, rec: Recording, params: dict) -> FrameStream:
        """Turn a recording into frames (float). Off-chip stages run on the host, not in gates."""

    def lower(self, params: dict, in_spec: dict) -> dict:
        """On-chip stages only: return a chipir/1 fragment computing the same thing in integers."""
        raise NotImplementedError(f"{self.name} is off-chip only")


@dataclass
class BatchInputs:
    """Integer chip inputs for a population. Candidates that share an encoding share one tensor.

    keys[k]        which encoded input candidate k reads
    tensors[key]   float32 tensor [N, lanes] holding exact integers, on the training device
    in_specs[key]  {"lanes": int, "bits": int, "signed": bool}  (becomes the IR input port)
    """
    keys: list[str]
    tensors: dict[str, Any]
    in_specs: dict[str, dict]
    y: Any = None                 # long tensor [N] (class index), None at inference
    meta: dict = field(default_factory=dict)


class ModelFamily(ABC):
    name: str = ""
    version: str = "1"

    @abstractmethod
    def space(self) -> dict:
        """The settings the AI scientist may vary, with allowed values or ranges and defaults."""

    @abstractmethod
    def validate_cfg(self, cfg: dict) -> dict:
        """Return the cfg with defaults filled, or raise ValueError."""

    @abstractmethod
    def est_cost(self, cfg: dict, in_spec: dict) -> dict:
        """Cheap pre-synthesis estimate, e.g. {"weights": n, "adds": m}; used for budgets before training."""

    @abstractmethod
    def train(self, cfgs: list[dict], data: BatchInputs, dev: str, opts: dict) -> Any:
        """Train all candidates at once (population training). Return an opaque state."""

    @abstractmethod
    def predict(self, state: Any, data: BatchInputs) -> Any:
        """Integer decisions [K, N] (class index) exactly as the chip will compute them."""

    @abstractmethod
    def lower(self, state: Any, k: int, in_spec: dict) -> dict:
        """chipir/1 document for candidate k. Input port named 'x' with in_spec; one output named 'y'."""


class Target(ABC):
    name: str = ""
    kind: str = "logic"          # logic | fpga | asic

    @abstractmethod
    def synthesize(self, rtl: Path, top: str, workdir: Path, opts: dict) -> dict:
        """Synthesise and return metrics."""
