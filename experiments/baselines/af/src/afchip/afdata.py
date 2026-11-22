"""RR intervals and rhythm labels from PhysioNet AFDB and LTAFDB annotation files.

Off-chip front end (stated plainly): R-peak times come from the database's beat annotations;
the interval between consecutive beats is converted to milliseconds and quantised to 8 ms units,
saturated at 255 (2.04 s). That 8-bit unsigned integer per interval is the chip's only input.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

RR_UNIT_MS = 8
RR_MAX = 255
AF_LABEL = "(AFIB"
# Beat symbols counted as heartbeats (WFDB beat codes); everything else is a non-beat annotation.
BEAT_SYMBOLS = set("NLRBAaJSVrFejnE/fQ?")


@dataclass(frozen=True)
class Record:
    name: str
    rr: np.ndarray  # uint8-range ints, quantised RR in 8 ms units
    af: np.ndarray  # 1 = interval inside an AFIB episode, 0 = other rhythm, -1 = unlabelled
    rhythm: np.ndarray  # rhythm string index per interval (for reporting)


def _rhythm_per_sample(atr: wfdb.Annotation) -> tuple[np.ndarray, list[str]]:
    """Return (change samples, rhythm labels) from the rhythm annotations ('+' with aux_note)."""
    samples, labels = [], []
    for s, sym, aux in zip(atr.sample, atr.symbol, atr.aux_note):
        if sym == "+" and aux:
            samples.append(int(s))
            labels.append(aux.strip().rstrip("\x00"))
    return np.asarray(samples, dtype=np.int64), labels


def load_record(db_dir: Path, name: str, *, beat_ext: str) -> Record:
    """Load one record. beat_ext: 'qrs' for AFDB (database beat file), 'atr' for LTAFDB."""
    atr = wfdb.rdann(str(db_dir / name), "atr")
    fs = float(atr.fs) if atr.fs else float(wfdb.rdheader(str(db_dir / name)).fs)
    beats = wfdb.rdann(str(db_dir / name), beat_ext)
    bs = np.asarray([s for s, sym in zip(beats.sample, beats.symbol) if sym in BEAT_SYMBOLS], dtype=np.int64)
    bs = np.unique(bs)
    rr_ms = np.diff(bs) * 1000.0 / fs
    rr = np.clip(np.rint(rr_ms / RR_UNIT_MS), 0, RR_MAX).astype(np.int64)
    ch_s, ch_l = _rhythm_per_sample(atr)
    names = sorted(set(ch_l))
    end = bs[1:]  # an interval belongs to the rhythm active at the beat that ends it
    idx = np.searchsorted(ch_s, end, side="right") - 1
    af = np.full(len(rr), -1, dtype=np.int64)
    rh = np.full(len(rr), -1, dtype=np.int64)
    ok = idx >= 0
    lab = np.asarray(ch_l, dtype=object)
    af[ok] = (lab[idx[ok]] == AF_LABEL).astype(np.int64)
    rh[ok] = np.asarray([names.index(x) for x in lab[idx[ok]]], dtype=np.int64)
    return Record(name=name, rr=rr, af=af, rhythm=rh)


def segments(rec: Record, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Contiguous non-overlapping segments of n intervals from the record start (as Dash 2009 and
    Andersson 2015). A segment is AF if more than 50% of its intervals are AFIB (PercThresh 50%).
    Segments touching unlabelled intervals are dropped. Returns (X [m, n], y [m], n_af_intervals [m])."""
    m = len(rec.rr) // n
    x = rec.rr[: m * n].reshape(m, n)
    a = rec.af[: m * n].reshape(m, n)
    keep = (a >= 0).all(axis=1)
    naf = a.sum(axis=1)
    y = (2 * naf > n).astype(np.int64)
    return x[keep], y[keep], naf[keep]


def list_records(db_dir: Path) -> list[str]:
    return [r.strip() for r in (db_dir / "RECORDS").read_text().split() if r.strip()]
