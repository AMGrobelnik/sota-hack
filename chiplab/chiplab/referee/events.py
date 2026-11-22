"""Fair event-level scoring of detections (seizures, bradycardia onsets, ...) on top of timescoring 0.0.7.

Input: recordings, each {patient_id, recording_id, fs, labels (0/1 per sample), decisions (0/1) and/or scores
(float), timestamps (optional, seconds per sample)}. Output: per-recording and per-patient counts, SzCORE-style
per-patient averages and pooled figures, false alarms per hour and per 24 h, sensitivity at fixed false-alarm
rates, worst-case figures, 1 s sample-level ROC AUC, patient-level bootstrap CIs and provenance.

Guards against known timescoring 0.0.7 pitfalls:
- every Annotation is built from a validated boolean mask, never from an event list (its merge step keeps
  event[1] instead of the max end, which corrupts unsorted or overlapping event lists);
- labels, decisions, scores and timestamps must have equal lengths; empty or zero-length input is rejected;
- masks must be exactly 0/1 (timescoring casts 0.9 to 0 without a word);
- fs is passed as a Python float;
- recordings are split at timestamp gaps, so no event bridges a gap and gap time never counts as monitored time.
"""
from __future__ import annotations

import math
from importlib import metadata

import numpy as np

#: Profiles. Times in seconds; merge_s=None: never merge, split_s=None: never split.
PROFILES: dict[str, dict] = {
    # comparable with the SzCORE benchmark (timescoring defaults)
    "szcore": {"tolerance_start_s": 30.0, "tolerance_end_s": 60.0, "min_overlap": 0.0, "merge_s": 90.0,
               "split_s": 300.0, "collar_s": 0.0},
    # newborn seizure clusters must not be merged: any overlap, no merge, no split, optional collar
    "neonatal": {"tolerance_start_s": 0.0, "tolerance_end_s": 0.0, "min_overlap": 0.0, "merge_s": None,
                 "split_s": None, "collar_s": 0.0},
}
FA_TARGETS = (0.1, 0.36, 1.0)
NAN_POLICIES = {"omit": "undefined per-patient values (no reference events, or no detections) are left out of "
                        "averages and pooled figures (SzCORE convention)",
                "zero": "undefined per-patient values count as 0 in averages and pooled figures"}
MAX_THRESHOLDS = 200
INTERNAL_HZ = 10          # timescoring EventScoring works at 10 Hz
GAP_FACTOR = 1.5          # a timestamp step above 1.5 sample periods is a gap


class ScoringInputError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------ parameters

def resolve_params(profile: str = "szcore", overrides: dict | None = None) -> dict:
    """Profile defaults with caller overrides applied and checked."""
    if profile not in PROFILES:
        raise ScoringInputError(f"profile must be one of {sorted(PROFILES)}, got {profile!r}")
    p = dict(PROFILES[profile])
    for k, v in (overrides or {}).items():
        if k not in p:
            raise ScoringInputError(f"unknown scoring parameter {k!r}; known: {sorted(p)}")
        p[k] = v
    for k in ("tolerance_start_s", "tolerance_end_s", "collar_s", "min_overlap"):
        p[k] = _nonneg(p[k], k)
    if p["min_overlap"] >= 1:
        raise ScoringInputError("min_overlap is a fraction in [0, 1)")
    for k in ("merge_s", "split_s"):
        if p[k] is not None:
            p[k] = _nonneg(p[k], k)
            if p[k] == 0:
                p[k] = None          # 0 means off
    return p


def _nonneg(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ScoringInputError(f"{name} must be a finite number >= 0, got {v!r}")
    return float(v)


def _ts_params(p: dict):
    from timescoring.scoring import EventScoring
    return EventScoring.Parameters(toleranceStart=p["tolerance_start_s"] + p["collar_s"],
                                   toleranceEnd=p["tolerance_end_s"] + p["collar_s"],
                                   minOverlap=p["min_overlap"],
                                   maxEventDuration=math.inf if p["split_s"] is None else p["split_s"],
                                   minDurationBetweenEvents=0.0 if p["merge_s"] is None else p["merge_s"])


# ------------------------------------------------------------------------------------------------ input checks

def _mask(x, name: str, where: str) -> np.ndarray:
    try:
        a = np.asarray(x)
    except (ValueError, TypeError) as e:
        raise ScoringInputError(f"{where}: {name} is not a flat list ({e})") from e
    if a.ndim != 1 or a.size == 0:
        raise ScoringInputError(f"{where}: {name} must be a non-empty flat list of 0/1 per sample")
    if a.dtype == np.bool_:
        return a.copy()
    if a.dtype.kind not in "iuf":
        raise ScoringInputError(f"{where}: {name} must hold only 0/1 (got dtype {a.dtype})")
    bad = a[~np.isin(a, (0, 1))]
    if bad.size:
        raise ScoringInputError(f"{where}: {name} must be exactly 0 or 1 per sample, found {bad[0]!r} "
                                "(timescoring would silently cast it)")
    return a.astype(bool)


def _floats(x, name: str, where: str) -> np.ndarray:
    try:
        a = np.asarray(x, dtype=float)
    except (ValueError, TypeError) as e:
        raise ScoringInputError(f"{where}: {name} must be a flat list of numbers ({e})") from e
    if a.ndim != 1 or a.size == 0 or not np.isfinite(a).all():
        raise ScoringInputError(f"{where}: {name} must be a non-empty flat list of finite numbers")
    return a


def validate(recordings, score_threshold: float = 0.5) -> list[dict]:
    """Checked recordings: {patient_id, recording_id, fs, labels, decisions, scores|None, segments, ...}."""
    if isinstance(recordings, dict) and "recordings" in recordings:
        recordings = recordings["recordings"]
    if not isinstance(recordings, list) or not recordings:
        raise ScoringInputError("recordings must be a non-empty list")
    out, seen = [], set()
    for i, r in enumerate(recordings):
        if not isinstance(r, dict):
            raise ScoringInputError(f"recording {i} is not an object")
        for k in ("patient_id", "recording_id", "fs", "labels"):
            if k not in r:
                raise ScoringInputError(f"recording {i}: missing {k}")
        pid, rid = str(r["patient_id"]), str(r["recording_id"])
        where = f"recording {pid}/{rid}"
        if (pid, rid) in seen:
            raise ScoringInputError(f"{where}: duplicate patient_id/recording_id")
        seen.add((pid, rid))
        fs = r["fs"]
        if isinstance(fs, bool) or not isinstance(fs, (int, float)) or not math.isfinite(fs) or fs <= 0:
            raise ScoringInputError(f"{where}: fs must be a positive number, got {fs!r}")
        fs = float(fs)
        labels = _mask(r["labels"], "labels", where)
        n = labels.size
        scores = _floats(r["scores"], "scores", where) if r.get("scores") is not None else None
        if r.get("decisions") is not None:
            dec, dec_from = _mask(r["decisions"], "decisions", where), "decisions"
        elif scores is not None:
            dec, dec_from = scores >= score_threshold, f"scores>={score_threshold:g}"
        else:
            raise ScoringInputError(f"{where}: give decisions (0/1) and/or scores")
        ts = _floats(r["timestamps"], "timestamps", where) if r.get("timestamps") is not None else None
        for name, a in (("decisions", dec), ("scores", scores), ("timestamps", ts)):
            if a is not None and a.size != n:
                raise ScoringInputError(f"{where}: {name} has {a.size} samples, labels has {n}")
        if round(n / fs * INTERNAL_HZ) < 1:
            raise ScoringInputError(f"{where}: recording is shorter than {1 / INTERNAL_HZ:g} s")
        segs, dropped = [(0, n)], 0
        if ts is not None:
            step = np.diff(ts)
            if (step <= 0).any():
                raise ScoringInputError(f"{where}: timestamps must increase strictly")
            cuts = (np.flatnonzero(step > GAP_FACTOR / fs) + 1).tolist()
            bounds = list(zip([0] + cuts, cuts + [n], strict=True))
            segs = [(a, b) for a, b in bounds if round((b - a) / fs * INTERNAL_HZ) >= 1]
            dropped = sum(b - a for a, b in bounds) - sum(b - a for a, b in segs)
            if not segs:
                raise ScoringInputError(f"{where}: every segment between timestamp gaps is shorter than "
                                        f"{1 / INTERNAL_HZ:g} s")
        out.append({"patient_id": pid, "recording_id": rid, "fs": fs, "labels": labels, "decisions": dec,
                    "scores": scores, "segments": segs, "dropped_samples": int(dropped), "decisions_from": dec_from})
    return out


# ------------------------------------------------------------------------------------------------ scoring

def _score_mask(ref, hyp, fs: float, P) -> tuple[int, int, int]:
    from timescoring.annotations import Annotation
    from timescoring.scoring import EventScoring
    es = EventScoring(Annotation(np.asarray(ref, dtype=bool), float(fs)), Annotation(np.asarray(hyp, dtype=bool), float(fs)), P)
    return int(es.tp), int(es.fp), int(es.refTrue)


def _count(recs: list[dict], P, hyp_of=None) -> list[dict]:
    """Per-recording counts, summing the recording's segments. hyp_of(rec) overrides the decisions."""
    rows = []
    for r in recs:
        hyp = r["decisions"] if hyp_of is None else hyp_of(r)
        tp = fp = ref = ns = 0
        for a, b in r["segments"]:
            t, f, e = _score_mask(r["labels"][a:b], hyp[a:b], r["fs"], P)
            tp += t; fp += f; ref += e; ns += b - a
        rows.append({"patient_id": r["patient_id"], "recording_id": r["recording_id"], "tp": tp, "fp": fp,
                     "refTrue": ref, "numSamples": ns, "hours": ns / r["fs"] / 3600.0})
    return rows


def _div(a: float, b: float) -> float:
    return a / b if b else math.nan


def _rates(tp: int, fp: int, ref: int, hours: float) -> dict:
    sens, prec = _div(tp, ref), _div(tp, tp + fp)
    f1 = _div(2 * tp, 2 * tp + fp + (ref - tp))
    fah = _div(fp, hours)
    return {"sensitivity": sens, "precision": prec, "f1": f1, "fa_per_hour": fah, "fa_per_24h": fah * 24}


def _patients(rows: list[dict]) -> dict[str, dict]:
    pats: dict[str, dict] = {}
    for r in rows:
        p = pats.setdefault(r["patient_id"], {"patient_id": r["patient_id"], "n_recordings": 0, "tp": 0, "fp": 0,
                                              "refTrue": 0, "numSamples": 0, "hours": 0.0})
        p["n_recordings"] += 1
        for k in ("tp", "fp", "refTrue", "numSamples", "hours"):
            p[k] += r[k]
    for p in pats.values():
        p.update(_rates(p["tp"], p["fp"], p["refTrue"], p["hours"]))
    return pats


def _apply(v: float, policy: str):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0 if policy == "zero" else None
    return v


def _average(pats: dict, policy: str) -> dict:
    out = {}
    for k in ("sensitivity", "precision", "f1", "fa_per_hour", "fa_per_24h"):
        v = np.array([p[k] for p in pats.values()], dtype=float)
        if policy == "zero":
            v = np.nan_to_num(v, nan=0.0)
        v = v[~np.isnan(v)]
        out[k] = float(v.mean()) if v.size else None
        out[f"n_{k}"] = int(v.size)
    return out


def _pooled(rows: list[dict], policy: str) -> dict:
    tp, fp, ref = (sum(r[k] for r in rows) for k in ("tp", "fp", "refTrue"))
    hours = sum(r["hours"] for r in rows)
    res = {k: _apply(v, policy) for k, v in _rates(tp, fp, ref, hours).items()}
    return {**res, "tp": tp, "fp": fp, "refTrue": ref, "hours": hours}


def _clean(x):
    """JSON-safe: NaN/inf -> None, numpy scalars -> Python."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


# ------------------------------------------------------------------------------------------------ threshold sweep

def _sweep(recs: list[dict], P, policy: str, targets, thresholds: dict | None, n_thresholds: int) -> dict:
    if any(r["scores"] is None for r in recs):
        return {"skipped": "every recording needs scores for the threshold sweep"}

    def at(t: float) -> dict:
        rows = _count(recs, P, hyp_of=lambda r: r["scores"] >= t)
        pats = _patients(rows)
        po = _pooled(rows, policy)
        return {"threshold": t, "sensitivity": po["sensitivity"], "fa_per_hour": po["fa_per_hour"],
                "sensitivity_patient_avg": _average(pats, policy)["sensitivity"]}

    if thresholds:   # chosen elsewhere (e.g. on training data): apply as given
        out = []
        for tgt in targets:
            t = thresholds.get(str(tgt), thresholds.get(tgt)) if isinstance(thresholds, dict) else None
            if t is None:
                out.append({"target_fa_per_hour": tgt, "threshold": None, "note": "no threshold given for this target"})
                continue
            out.append({"target_fa_per_hour": tgt, **at(float(t)), "threshold_chosen_on_same_data": False})
        return {"points": out, "threshold_chosen_on_same_data": False}
    n = max(2, min(int(n_thresholds), MAX_THRESHOLDS))
    allsc = np.concatenate([r["scores"] for r in recs])
    cand = np.unique(np.quantile(allsc, np.linspace(0.0, 1.0, n)))
    curve = [at(float(t)) for t in cand] + [at(math.inf)]          # inf: no detections at all
    out = []
    for tgt in targets:
        ok = [c for c in curve if c["fa_per_hour"] is not None and c["fa_per_hour"] <= tgt + 1e-12]
        best = max(ok, key=lambda c: ((c["sensitivity"] if c["sensitivity"] is not None else -1.0), -c["fa_per_hour"]))
        pt = {"target_fa_per_hour": tgt, **best, "threshold_chosen_on_same_data": True}
        if math.isinf(best["threshold"]):
            pt.update(threshold=None, note="no threshold reaches this rate with any detection: alarms off")
        out.append(pt)
    return {"points": out, "n_thresholds": len(cand), "threshold_chosen_on_same_data": True,
            "note": "thresholds chosen on the scored data itself: optimistic; pass thresholds chosen on other data"}


# ------------------------------------------------------------------------------------------------ AUC

def roc_auc(y, s) -> float | None:
    """ROC AUC by the rank (Mann-Whitney) formula, ties averaged. None when only one class is present."""
    y = np.asarray(y, dtype=bool); s = np.asarray(s, dtype=float)
    npos = int(y.sum()); nneg = y.size - npos
    if npos == 0 or nneg == 0:
        return None
    order = np.argsort(s, kind="mergesort")
    _, inv, counts = np.unique(s[order], return_inverse=True, return_counts=True)
    avg = np.cumsum(counts) - (counts - 1) / 2.0
    ranks = np.empty(s.size); ranks[order] = avg[inv]
    return float((ranks[y].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def _windows_1s(labels: np.ndarray, scores: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    win = np.floor(np.arange(labels.size) / fs).astype(np.int64)
    starts = np.flatnonzero(np.r_[True, np.diff(win) != 0])
    return np.maximum.reduceat(labels.astype(np.int8), starts).astype(bool), np.maximum.reduceat(scores, starts)


def _auc(recs: list[dict]) -> dict:
    if any(r["scores"] is None for r in recs):
        return {"skipped": "every recording needs scores for ROC AUC"}
    per: dict[str, list] = {}
    ys, ss = [], []
    for r in recs:
        for a, b in r["segments"]:
            y, s = _windows_1s(r["labels"][a:b], r["scores"][a:b], r["fs"])
            ys.append(y); ss.append(s); per.setdefault(r["patient_id"], []).append((y, s))
    pooled = roc_auc(np.concatenate(ys), np.concatenate(ss))
    pp = {p: roc_auc(np.concatenate([y for y, _ in v]), np.concatenate([s for _, s in v])) for p, v in per.items()}
    vals = np.array([v for v in pp.values() if v is not None])
    q = np.percentile(vals, [25, 50, 75]) if vals.size else [None] * 3
    return {"pooled": pooled, "per_patient": pp, "per_patient_median": q[1], "per_patient_iqr": [q[0], q[2]],
            "n_patients_defined": int(vals.size),
            "window": "1 s; label = any positive sample in the second, score = max score in the second"}


# ------------------------------------------------------------------------------------------------ bootstrap

def _bootstrap(pats: dict, policy: str, n: int, seed: int) -> dict:
    P = len(pats)
    if P < 2:
        return {"skipped": "needs at least 2 patients"}
    arr = {k: np.array([p[k] for p in pats.values()], dtype=float) for k in ("tp", "fp", "refTrue", "hours", "sensitivity")}
    idx = np.random.default_rng(seed).integers(0, P, size=(int(n), P))
    tp, fp, ref, hrs = (arr[k][idx].sum(axis=1) for k in ("tp", "fp", "refTrue", "hours"))
    with np.errstate(divide="ignore", invalid="ignore"):
        stats = {"sensitivity_pooled": tp / ref, "precision_pooled": tp / (tp + fp),
                 "f1_pooled": 2 * tp / (2 * tp + fp + (ref - tp)), "fa_per_hour_pooled": fp / hrs}
        sp = arr["sensitivity"][idx]
        if policy == "zero":
            stats["sensitivity_patient_avg"] = np.nan_to_num(sp, nan=0.0).mean(axis=1)
        else:
            cnt = (~np.isnan(sp)).sum(axis=1)
            stats["sensitivity_patient_avg"] = np.where(cnt > 0, np.nansum(sp, axis=1) / np.maximum(cnt, 1), np.nan)
    out = {}
    for k, v in stats.items():
        v = np.asarray(v, dtype=float)
        if policy == "zero":
            v = np.nan_to_num(v, nan=0.0)
        v = v[np.isfinite(v)]
        out[k] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None
    return {"ci95": out, "n_resamples": int(n), "seed": int(seed), "unit": "patient (resampled with replacement)"}


# ------------------------------------------------------------------------------------------------ entry point

def score(recordings, profile: str = "szcore", params: dict | None = None, nan_policy: str = "omit",
          score_threshold: float = 0.5, fa_targets=None, thresholds: dict | None = None,
          n_thresholds: int = MAX_THRESHOLDS, n_bootstrap: int = 2000, seed: int = 0) -> dict:
    """Score recordings. See the module docstring for the input and the guards."""
    import warnings
    if nan_policy not in NAN_POLICIES:
        raise ScoringInputError(f"nan_policy must be one of {sorted(NAN_POLICIES)}")
    p = resolve_params(profile, params)
    P = _ts_params(p)
    recs = validate(recordings, score_threshold)
    targets = [float(t) for t in (fa_targets if fa_targets is not None else FA_TARGETS)]
    rows = _count(recs, P)
    for row, r in zip(rows, recs, strict=True):
        row.update(_rates(row["tp"], row["fp"], row["refTrue"], row["hours"]))
        row.update({"n_segments": len(r["segments"]), "dropped_samples": r["dropped_samples"],
                    "decisions_from": r["decisions_from"]})
    pats = _patients(rows)
    avg = _average(pats, nan_policy)
    pooled = _pooled(rows, nan_policy)
    with_ev = [q for q in pats.values() if q["refTrue"] > 0]
    free = [q for q in pats.values() if q["refTrue"] == 0]
    sens = np.array([q["sensitivity"] for q in with_ev], dtype=float)
    free_h = sum(q["hours"] for q in free)
    worst = {"min_patient_sensitivity": float(sens.min()) if sens.size else None,
             "p10_patient_sensitivity": float(np.percentile(sens, 10)) if sens.size else None,
             "patients_with_events": len(with_ev),
             "patients_zero_detections": [q["patient_id"] for q in with_ev if q["tp"] == 0],
             "event_free_patients": [{"patient_id": q["patient_id"], "fa_per_hour": q["fa_per_hour"],
                                      "fa_per_24h": q["fa_per_24h"]} for q in free],
             "event_free_fa_per_hour_pooled": _div(sum(q["fp"] for q in free), free_h) if free else None}
    auc = _auc(recs)
    try:
        ts_ver = metadata.version("timescoring")
    except metadata.PackageNotFoundError:
        ts_ver = None
    if ts_ver != "0.0.7":
        warnings.warn(f"timescoring {ts_ver} is not the pinned 0.0.7; figures may differ", stacklevel=2)
    res = {
        "per_recording": rows,
        "per_patient": list(pats.values()),
        "average": avg,
        "pooled": pooled,
        "fa_per_hour": {"pooled": pooled["fa_per_hour"], "patient_avg": avg["fa_per_hour"],
                        "per_patient": {q["patient_id"]: q["fa_per_hour"] for q in pats.values()}},
        "fa_per_24h": {"pooled": pooled["fa_per_24h"], "patient_avg": avg["fa_per_24h"],
                       "per_patient": {q["patient_id"]: q["fa_per_24h"] for q in pats.values()}},
        "sensitivity_at_fa": _sweep(recs, P, nan_policy, targets, thresholds, n_thresholds),
        "worst_case": worst,
        "auc": auc,
        "bootstrap": _bootstrap(pats, nan_policy, n_bootstrap, seed),
        "headline": {"event_sensitivity": avg["sensitivity"], "fa_per_hour": avg["fa_per_hour"],
                     "worst_patient_sensitivity": worst["min_patient_sensitivity"],
                     "auc": auc.get("pooled")},
        "provenance": {"timescoring_version": ts_ver, "profile": profile, "parameters": p,
                       "nan_policy": nan_policy, "nan_policy_meaning": NAN_POLICIES[nan_policy],
                       "per_patient_rows": "raw: undefined values are null whatever the policy",
                       "headline_basis": "event_sensitivity and fa_per_hour are SzCORE per-patient averages; "
                                         "worst_patient_sensitivity is the minimum over patients with events; "
                                         "auc is pooled 1 s ROC AUC",
                       "internal_resolution_hz": INTERNAL_HZ,
                       "gap_rule": f"timestamp step > {GAP_FACTOR} / fs splits a recording",
                       "score_threshold": score_threshold,
                       "n_recordings": len(recs), "n_patients": len(pats)},
    }
    return _clean(res)
