"""PhysioNet / Computing in Cardiology Challenge 2017: single-lead ECG, 30-60 s, 300 Hz.

Labels: N normal, A atrial fibrillation, O other rhythm, ~ noisy. Open access.
Assumption (stated in describe()): the dataset has no patient ids, so each recording is its own subject.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

import numpy as np

from chiplab.data.contract import Recording
from chiplab.plugins.base import DatasetLoader

URL = "https://physionet.org/files/challenge-2017/1.0.0/training2017.zip"
FS = 300


def _load_mat(zip_path: str, name: str) -> np.ndarray:
    from scipy.io import loadmat
    with zipfile.ZipFile(zip_path) as z:
        m = loadmat(io.BytesIO(z.read(f"training2017/{name}.mat")))
    return m["val"].astype(np.float32).reshape(1, -1)


class _Lazy:
    """Picklable lazy loader (multiprocessing needs it)."""

    def __init__(self, zip_path: str, name: str):
        self.zip_path, self.name = zip_path, name

    def __call__(self) -> np.ndarray:
        return _load_mat(self.zip_path, self.name)


class CinC2017(DatasetLoader):
    name = "cinc2017"
    version = "1.0.0"

    def zip_path(self, root: Path) -> Path:
        return Path(root) / "training2017.zip"

    def fetch(self, root: Path) -> None:
        p = self.zip_path(root)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(URL, p)

    def recordings(self, root: Path) -> Iterator[Recording]:
        zp = str(self.zip_path(root))
        with zipfile.ZipFile(zp) as z:
            ref = z.read("training2017/REFERENCE.csv").decode().split()
            sizes = {i.filename: i.file_size for i in z.infolist()}
        for row in ref:
            name, lab = row.split(",")
            yield Recording(rec_id=name, subject_id=name, fs=FS, channels=["lead"], label=lab,
                            load=_Lazy(zp, name), units=["adu"], duration_s=None,
                            meta={"simulated": False, "source": URL, "licence": "ODC-By 1.0 (PhysioNet open)",
                                  "mat_bytes": sizes.get(f"training2017/{name}.mat")})

    def describe(self) -> dict:
        return {"name": self.name, "version": self.version, "url": URL, "licence": "Open (PhysioNet)",
                "channels": ["lead"], "fs": FS, "labels": {"N": "normal", "A": "AF", "O": "other rhythm", "~": "noisy"},
                "assumptions": ["No patient ids are published: each recording is treated as its own subject."],
                "citation": "Clifford et al., AF Classification from a Short Single Lead ECG Recording: "
                            "the PhysioNet/Computing in Cardiology Challenge 2017"}


LOADER = CinC2017()
