"""Off-chip front-end: R-peak detection (wfdb xqrs) -> beat-to-beat intervals in ms, one frame per beat.

Runs on the host, not in gates (the lab reports it as off-chip). Cached on disk because peak detection is slow.
"""
from __future__ import annotations

import hashlib
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from chiplab import config
from chiplab.data.contract import FrameStream, Recording
from chiplab.plugins.base import FrontEndStage


def _peaks_to_frames(peaks: np.ndarray, fs: float) -> FrameStream:
    peaks = np.asarray(peaks, dtype=np.int64)
    rr = np.diff(peaks) * 1000.0 / fs
    t = peaks[1:] / fs if len(peaks) > 1 else np.zeros(0)
    # float32 round-trip keeps parity with the feasibility spike (it stored RR as float32)
    rr = rr.astype(np.float32).astype(np.float64)
    return FrameStream(values=rr.reshape(-1, 1), t=np.asarray(t, dtype=np.float64), names=["interval_ms"])


def _detect(rec: Recording) -> np.ndarray:
    import wfdb.processing as wp
    sig = rec.get_signals()[0].astype(np.float64)
    return np.asarray(wp.xqrs_detect(sig=sig, fs=rec.fs, verbose=False))


def _work(rec: Recording):
    try:
        peaks = _detect(rec)
        n = rec.get_signals().shape[1]
        return rec.rec_id, peaks, n / rec.fs, None
    except Exception as e:  # report, keep going
        return rec.rec_id, None, None, str(e)


class RRIntervals(FrontEndStage):
    name = "rr_intervals"
    version = "1"
    onchip = False

    def frames(self, rec: Recording, params: dict) -> FrameStream:
        return _peaks_to_frames(_detect(rec), rec.fs)

    def frames_many(self, recs: list[Recording], params: dict, cache_key: str, workers: int = 8):
        """-> (dict rec_id -> FrameStream, dict rec_id -> duration_s, failures). Cached under runs/cache."""
        h = hashlib.sha256(json.dumps({"k": cache_key, "p": params, "v": self.version,
                                       "ids": [r.rec_id for r in recs]}, sort_keys=True).encode()).hexdigest()[:16]
        path = Path(config.home("cache")) / f"{self.name}_{h}.npz"
        if path.exists():
            d = np.load(path, allow_pickle=False)
            ids, lens, flat, dur = list(d["ids"]), d["lens"], d["flat"], d["dur"]
            fs = {r.rec_id: r.fs for r in recs}
            offs = np.concatenate([[0], np.cumsum(lens)])
            out = {i: _peaks_to_frames(flat[offs[j]:offs[j + 1]], fs[i]) for j, i in enumerate(ids)}
            return out, dict(zip(ids, dur.tolist())), json.loads(str(d["fail"]))
        out, durs, fail, peaks_all = {}, {}, [], {}
        with Pool(workers) as p:
            for rid, peaks, dur, err in p.imap(_work, recs, chunksize=8):
                if err is not None:
                    fail.append([rid, err]); continue
                peaks_all[rid] = peaks; durs[rid] = dur
        fsd = {r.rec_id: r.fs for r in recs}
        ids = [r.rec_id for r in recs if r.rec_id in peaks_all]
        for i in ids:
            out[i] = _peaks_to_frames(peaks_all[i], fsd[i])
        lens = np.array([len(peaks_all[i]) for i in ids], dtype=np.int64)
        flat = np.concatenate([peaks_all[i] for i in ids]).astype(np.int64) if ids else np.zeros(0, np.int64)
        np.savez(path, ids=np.array(ids), lens=lens, flat=flat, dur=np.array([durs[i] for i in ids]),
                 fail=np.array(json.dumps(fail)))
        return out, durs, fail


STAGE = RRIntervals()
