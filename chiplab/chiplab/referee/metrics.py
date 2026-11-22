"""How every result is scored. Fixed by the lab; the AI scientist cannot redefine a metric.

Binary tasks: the positive class is class index 1. Multiclass: per-class one-vs-rest plus accuracy.
"""
from __future__ import annotations

import numpy as np


def _r(x: float) -> float:
    return round(float(x), 4)


def binary(y, p) -> dict:
    y = np.asarray(y).astype(int); p = np.asarray(p).astype(int)
    tp = int(((y == 1) & (p == 1)).sum()); fn = int(((y == 1) & (p != 1)).sum())
    tn = int(((y != 1) & (p != 1)).sum()); fp = int(((y != 1) & (p == 1)).sum())
    sens = tp / max(tp + fn, 1); spec = tn / max(tn + fp, 1)
    ppv = tp / max(tp + fp, 1); f1 = 2 * tp / max(2 * tp + fp + fn, 1)
    return dict(sens=_r(sens), spec=_r(spec), f1=_r(f1), ppv=_r(ppv), tp=tp, fn=fn, tn=tn, fp=fp, n=int(len(y)))


def multiclass(y, p, n_classes: int) -> dict:
    y = np.asarray(y).astype(int); p = np.asarray(p).astype(int)
    per = {}
    for c in range(n_classes):
        per[c] = binary((y == c).astype(int), (p == c).astype(int))
    return {"acc": _r((y == p).mean() if len(y) else 0.0), "per_class": per, "n": int(len(y))}


def by_record(rec, y, p) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Majority vote of window decisions per recording (>= 0.5 -> positive). Returns (rec ids, y, p)."""
    rec = np.asarray(rec); y = np.asarray(y); p = np.asarray(p)
    ids = np.unique(rec)
    ry = np.array([y[rec == i][0] for i in ids])
    rp = np.array([int(p[rec == i].mean() >= 0.5) for i in ids])
    return ids, ry, rp


def per_subject(subj, y, p, names: list[str] | None = None) -> dict:
    """Per-subject sensitivity/specificity and the worst subject (only subjects with that class count)."""
    subj = np.asarray(subj); y = np.asarray(y).astype(int); p = np.asarray(p).astype(int)
    rows = []
    for s in np.unique(subj):
        m = subj == s
        b = binary(y[m], p[m])
        rows.append({"subject": names[s] if names else int(s), "n": b["n"], "positives": b["tp"] + b["fn"],
                     "sens": b["sens"] if b["tp"] + b["fn"] else None,
                     "spec": b["spec"] if b["tn"] + b["fp"] else None})
    sens = [r for r in rows if r["sens"] is not None]
    spec = [r for r in rows if r["spec"] is not None]
    worst_sens = min(sens, key=lambda r: r["sens"]) if sens else None
    worst_spec = min(spec, key=lambda r: r["spec"]) if spec else None
    return {"rows": rows, "n_subjects": len(rows),
            "worst_sens": worst_sens["sens"] if worst_sens else None,
            "worst_sens_subject": worst_sens["subject"] if worst_sens else None,
            "worst_spec": worst_spec["spec"] if worst_spec else None,
            "worst_spec_subject": worst_spec["subject"] if worst_spec else None}


def summary(view_part, p, with_rows: bool = False) -> dict:
    """Window, recording (majority vote) and subject level scores for one split part of a View."""
    p = np.asarray(p).astype(int)
    y = view_part.y
    if len(view_part.classes) > 2:
        return {"window": multiclass(y, p, len(view_part.classes))}
    ids, ry, rp = by_record(view_part.rec, y, p)
    subj_of_rec = np.array([view_part.subjects.index(view_part.recs[i]["subject_id"]) for i in ids]) if len(ids) else ids
    ps = per_subject(subj_of_rec, ry, rp, view_part.subjects)
    out = {"window": binary(y, p), "record": binary(ry, rp), "n_records": int(len(ids)),
           "subject": {k: v for k, v in ps.items() if k != "rows"}}
    if with_rows:
        out["subject"]["rows"] = ps["rows"]
    return out


def events(recordings, **kwargs) -> dict:
    """Event-level scoring (timescoring 0.0.7, SzCORE or neonatal profile): see chiplab.referee.events.score."""
    from chiplab.referee.events import score
    return score(recordings, **kwargs)
