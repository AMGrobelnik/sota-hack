"""The generic data contract. Any sensor, any dataset, real or simulated, enters the lab as Recordings.

Recording   one continuous recording from one subject (patient, baby, volunteer, simulated subject).
FrameStream what an off-chip front-end turns a recording into: one row per frame (a beat, an epoch, a sample).
View        windows of frames ready for training: float frame values (pre-encoding), labels, and the
            locked split part of every window. Encoding to integers (the chip boundary) happens per design,
            in data/encode.py, because the AI scientist varies bits and encoders per candidate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

PARTS = {"train": 0, "val": 1, "test": 2}
PART_NAMES = {v: k for k, v in PARTS.items()}


@dataclass
class Event:
    onset_s: float
    offset_s: float
    label: str


@dataclass
class Recording:
    rec_id: str
    subject_id: str
    fs: float                                   # samples per second of `signals`
    channels: list[str]
    label: Optional[str] = None                 # recording-level label, if the dataset has one
    events: list[Event] = field(default_factory=list)   # labelled intervals (the events the chip must detect)
    signals: Optional[np.ndarray] = None        # float32 [C, T]; may be None if `load` is given
    load: Optional[Callable[[], np.ndarray]] = None      # lazy loader returning [C, T]
    units: Optional[list[str]] = None
    duration_s: Optional[float] = None
    meta: dict = field(default_factory=dict)    # must include simulated: bool, source, licence when known

    def get_signals(self) -> np.ndarray:
        if self.signals is None:
            if self.load is None:
                raise ValueError(f"recording {self.rec_id} has no signals")
            self.signals = np.asarray(self.load(), dtype=np.float32)
        return self.signals


@dataclass
class FrameStream:
    values: np.ndarray          # float64 [T_f, F]
    t: np.ndarray               # float64 [T_f], time of each frame in seconds from recording start
    names: list[str]            # F feature names


@dataclass
class View:
    """Windows of frames. X holds float frame values; the integer chip inputs are made per design."""
    X: np.ndarray               # float64 [N, Lw, F]   last frame of the window = decision time
    y: np.ndarray               # int64 [N]            class index (task's class order)
    rec: np.ndarray             # int64 [N]            index into recs
    subj: np.ndarray            # int64 [N]            index into subjects
    t_end: np.ndarray           # float64 [N]          seconds from recording start
    part: np.ndarray            # int64 [N]            0 train, 1 val, 2 test (from the locked split)
    classes: list[str]
    frame_names: list[str]
    recs: list[dict]            # per recording: rec_id, subject_id, duration_s, label, events, simulated
    subjects: list[str]
    meta: dict = field(default_factory=dict)

    def select(self, part: int) -> "View":
        m = self.part == part
        return View(self.X[m], self.y[m], self.rec[m], self.subj[m], self.t_end[m], self.part[m],
                    self.classes, self.frame_names, self.recs, self.subjects, dict(self.meta))

    def __len__(self) -> int:
        return len(self.y)

    def save(self, path) -> None:
        import json
        np.savez_compressed(path, X=self.X, y=self.y, rec=self.rec, subj=self.subj, t_end=self.t_end, part=self.part,
                            info=np.array(json.dumps({"classes": self.classes, "frame_names": self.frame_names,
                                                      "recs": self.recs, "subjects": self.subjects, "meta": self.meta})))

    @classmethod
    def load(cls, path) -> "View":
        import json
        d = np.load(path, allow_pickle=False)
        info = json.loads(str(d["info"]))
        return cls(d["X"], d["y"], d["rec"], d["subj"], d["t_end"], d["part"], info["classes"], info["frame_names"],
                   info["recs"], info["subjects"], info["meta"])
