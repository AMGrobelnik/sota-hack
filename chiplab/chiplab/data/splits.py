"""The locked subject-level split. Fixed by the lab; the AI scientist cannot change how it is computed.

Every subject (patient, baby, simulated subject) lands in exactly one part: 0 train, 1 val, 2 test.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

ALGOS = ("stratified-v1",)


class SealedTestError(PermissionError):
    """Raised when training, selection or proposal code asks for the sealed test part."""


def make_split(subjects: list[str], subject_labels: list[int], fractions=(0.7, 0.15, 0.15), seed: int = 0,
               algo: str = "stratified-v1") -> dict[str, int]:
    """Subject -> part. 'stratified-v1': per class (sorted), subjects in given order, one shared
    np.random.default_rng(seed), shuffle, cut at int(f0*n) and int((f0+f1)*n)."""
    if algo not in ALGOS:
        raise ValueError(f"unknown split algo {algo!r}; known: {ALGOS}")
    if len(subjects) != len(subject_labels):
        raise ValueError("subjects and subject_labels differ in length")
    if len(set(subjects)) != len(subjects):
        raise ValueError("duplicate subject ids")
    f0, f1, f2 = (float(f) for f in fractions)
    if min(f0, f1, f2) < 0 or abs(f0 + f1 + f2 - 1.0) > 1e-9:
        raise ValueError("fractions must be non-negative and sum to 1")
    labels = np.asarray(subject_labels)
    part = np.zeros(len(subjects), dtype=int)
    rng = np.random.default_rng(seed)
    for c in sorted(set(labels.tolist())):
        idx = np.where(labels == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        part[idx[int(f0 * n):int((f0 + f1) * n)]] = 1
        part[idx[int((f0 + f1) * n):]] = 2
    return {s: int(p) for s, p in zip(subjects, part)}


def split_hash(assign: dict, extra: str = "") -> str:
    """Stable hash of (subject, part) pairs plus anything that defines the data (loader, version, params)."""
    body = json.dumps(sorted(assign.items()), separators=(",", ":")) + "|" + extra
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def counts(assign: dict) -> list[int]:
    v = list(assign.values())
    return [v.count(p) for p in (0, 1, 2)]
