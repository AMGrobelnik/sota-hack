"""Recordings -> frames (front-end) -> windows (View), each window tagged with its locked split part."""
from __future__ import annotations

import numpy as np

from chiplab.data.contract import FrameStream, Recording, View
from chiplab.plugins.base import FrontEndStage


def _class_lookup(classes: dict) -> tuple[list[str], dict[str, int], int | None]:
    names = list(classes.keys())
    lut, default = {}, None
    for ci, (cname, labels) in enumerate(classes.items()):
        for lab in labels:
            if lab in ("*", "__background__"):
                default = ci
            else:
                lut[lab] = ci
    return names, lut, default


def recording_class(rec: Recording, classes: dict) -> int | None:
    """Class index of a recording-level label, or None if it maps to no class."""
    _, lut, _ = _class_lookup(classes)
    return lut.get(rec.label) if rec.label is not None else None


def build_view(recordings: list[Recording], frontend: FrontEndStage, fe_params: dict, window: dict, classes: dict,
               assign: dict, frames: dict | None = None, durations: dict | None = None,
               exclude_unmapped: bool = True) -> View:
    """window = {"L": frames per window, "stride": int, "max_per_rec": int | None}.

    Labels: the recording label when it maps to a class; otherwise per window from events (the event covering
    the window's last frame; windows outside every event get the class listing "*" / "__background__", else 0).
    `frames` / `durations` may be precomputed (rec_id -> FrameStream / seconds) to skip the front-end.
    """
    names, lut, default = _class_lookup(classes)
    L, stride = int(window["L"]), int(window.get("stride", 1))
    mx = window.get("max_per_rec")
    Xs, ys, recs_i, subj_i, tend, parts = [], [], [], [], [], []
    recs_meta, subjects, subj_idx = [], [], {}
    F, fnames = None, None
    for rec in recordings:
        rlab = lut.get(rec.label) if rec.label is not None else None
        if rec.label is not None and rlab is None and not rec.events and exclude_unmapped:
            continue
        if rec.subject_id not in assign:
            raise KeyError(f"subject {rec.subject_id} has no split part")
        fs: FrameStream = frames[rec.rec_id] if frames is not None and rec.rec_id in frames else frontend.frames(rec, fe_params)
        if fnames is None:
            fnames, F = list(fs.names), fs.values.shape[1]
        dur = (durations or {}).get(rec.rec_id, rec.duration_s)
        ri = len(recs_meta)
        recs_meta.append({"rec_id": rec.rec_id, "subject_id": rec.subject_id, "duration_s": dur, "label": rec.label,
                          "events": [{"onset_s": e.onset_s, "offset_s": e.offset_s, "label": e.label} for e in rec.events],
                          "simulated": bool(rec.meta.get("simulated", False))})
        if rec.subject_id not in subj_idx:
            subj_idx[rec.subject_id] = len(subjects); subjects.append(rec.subject_id)
        T = fs.values.shape[0]
        starts = list(range(0, T - L + 1, stride))
        if mx is not None:
            starts = starts[:int(mx)]
        part = assign[rec.subject_id]
        for st in starts:
            te = float(fs.t[st + L - 1]) if len(fs.t) else 0.0
            if rlab is not None:
                y = rlab
            else:
                y = default if default is not None else 0
                for e in rec.events:
                    if e.onset_s <= te <= e.offset_s and e.label in lut:
                        y = lut[e.label]; break
            Xs.append(fs.values[st:st + L]); ys.append(y); recs_i.append(ri)
            subj_i.append(subj_idx[rec.subject_id]); tend.append(te); parts.append(part)
    if not Xs:
        raise ValueError("no windows: recordings too short for L or no recording maps to a class")
    return View(X=np.stack(Xs).astype(np.float64), y=np.array(ys, dtype=np.int64), rec=np.array(recs_i, dtype=np.int64),
                subj=np.array(subj_i, dtype=np.int64), t_end=np.array(tend, dtype=np.float64),
                part=np.array(parts, dtype=np.int64), classes=names, frame_names=fnames, recs=recs_meta,
                subjects=subjects, meta={"window": dict(window), "frontend": frontend.name, "fe_params": fe_params})
