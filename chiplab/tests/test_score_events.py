"""score-events: golden edges of timescoring 0.0.7 through the lab's guards, policies, sweep, AUC, bootstrap,
the tool and the ./progress metrics. All data synthetic, 1 Hz unless stated."""
import json
import math
import stat

import numpy as np
import pytest

from chiplab.referee import events as E
from chiplab.referee.metrics import events as metrics_events


def mask(n, *spans):
    m = np.zeros(n, dtype=int)
    for a, b in spans:
        m[a:b] = 1
    return m.tolist()


def rec(pid, rid, labels, decisions=None, scores=None, fs=1.0, **kw):
    r = {"patient_id": pid, "recording_id": rid, "fs": fs, "labels": labels, **kw}
    if decisions is not None:
        r["decisions"] = decisions
    if scores is not None:
        r["scores"] = scores
    return r


def one(labels, decisions, profile="szcore", params=None, **kw):
    out = E.score([rec("p", "r", labels, decisions, **kw)], profile=profile, params=params, n_bootstrap=10)
    return out["per_recording"][0]


# ---------------------------------------------------------------- golden edges

@pytest.mark.parametrize("gap,tp,fp", [(29, 1, 0), (31, 0, 1)])
def test_tolerance_start_edge(gap, tp, fp):
    """A detection ending 29 s before onset is inside the 30 s start tolerance; 31 s is a false alarm."""
    r = one(mask(1000, (500, 510)), mask(1000, (480 - gap, 500 - gap)))
    assert (r["tp"], r["fp"], r["refTrue"]) == (tp, fp, 1)


@pytest.mark.parametrize("gap,tp,fp", [(59, 1, 0), (61, 0, 1)])
def test_tolerance_end_edge(gap, tp, fp):
    r = one(mask(1000, (500, 510)), mask(1000, (510 + gap, 520 + gap)))
    assert (r["tp"], r["fp"]) == (tp, fp)


@pytest.mark.parametrize("gap,events", [(89, 1), (90, 2)])
def test_merge_edge(gap, events):
    r = one(mask(2000, (100, 110), (110 + gap, 120 + gap)), mask(2000))
    assert r["refTrue"] == events


@pytest.mark.parametrize("dur,events", [(300, 1), (301, 2)])
def test_split_edge(dur, events):
    r = one(mask(2000, (100, 100 + dur)), mask(2000))
    assert r["refTrue"] == events


def test_neonatal_never_merges_or_splits_and_needs_overlap():
    lab = mask(3000, (100, 110), (115, 125), (500, 1400))
    r = one(lab, mask(3000), profile="neonatal")
    assert r["refTrue"] == 3                               # 5 s apart: still 2 events; 900 s: not split
    near = one(mask(1000, (500, 510)), mask(1000, (511, 520)), profile="neonatal")
    assert (near["tp"], near["fp"]) == (0, 1)              # adjacent but no overlap
    coll = one(mask(1000, (500, 510)), mask(1000, (511, 520)), profile="neonatal", params={"collar_s": 2})
    assert (coll["tp"], coll["fp"]) == (1, 0)


def test_overrides_bradycardia_style():
    lab = mask(4000, (100, 110), (279, 289), (1000, 1500))
    r = one(lab, mask(4000), params={"merge_s": 180, "split_s": None, "tolerance_start_s": 5, "tolerance_end_s": 5})
    assert r["refTrue"] == 2      # 169 s gap merged at 180 s; 500 s event not split
    assert one(lab, mask(4000))["refTrue"] == 4                         # szcore: no merge, 500 s split in two
    assert E.resolve_params("szcore", {"merge_s": 0})["merge_s"] is None


def test_events_at_file_edges():
    r = one(mask(600, (0, 10), (590, 600)), mask(600, (0, 3), (595, 600)), params={"merge_s": None})
    assert (r["tp"], r["fp"], r["refTrue"]) == (2, 0, 2)
    whole = one([1] * 50, [1] * 50)
    assert (whole["tp"], whole["fp"], whole["refTrue"]) == (1, 0, 1)


def test_event_free_and_fa_rates():
    out = E.score([rec("p", "r", mask(7200), mask(7200, (100, 110), (3000, 3010)))], n_bootstrap=10)
    r = out["per_recording"][0]
    assert (r["tp"], r["fp"], r["refTrue"], r["numSamples"]) == (0, 2, 0, 7200)
    assert r["fa_per_hour"] == pytest.approx(1.0) and r["fa_per_24h"] == pytest.approx(24.0)
    assert r["sensitivity"] is None                                     # raw row: undefined
    assert out["worst_case"]["event_free_patients"][0]["fa_per_hour"] == pytest.approx(1.0)
    assert out["worst_case"]["event_free_fa_per_hour_pooled"] == pytest.approx(1.0)


def test_higher_fs_matches_1hz():
    a = one(mask(1000, (500, 510)), mask(1000, (452, 472)))
    b = one(np.repeat(mask(1000, (500, 510)), 4).tolist(), np.repeat(mask(1000, (452, 472)), 4).tolist(), fs=4)
    assert (a["tp"], a["fp"], a["refTrue"]) == (b["tp"], b["fp"], b["refTrue"]) and b["numSamples"] == 4000


# ---------------------------------------------------------------- patients and NaN policies

def _two_patients():
    return [rec("A", "a1", mask(3600, (100, 110)), mask(3600, (100, 105))),
            rec("A", "a2", mask(3600, (100, 110)), mask(3600)),
            rec("B", "b1", mask(3600), mask(3600, (2000, 2010)))]


def test_multi_recording_patient_sums():
    out = E.score(_two_patients(), n_bootstrap=10)
    pa = {p["patient_id"]: p for p in out["per_patient"]}
    assert (pa["A"]["tp"], pa["A"]["refTrue"], pa["A"]["n_recordings"], pa["A"]["numSamples"]) == (1, 2, 2, 7200)
    assert pa["A"]["sensitivity"] == pytest.approx(0.5)
    assert out["pooled"]["sensitivity"] == pytest.approx(0.5) and out["pooled"]["fa_per_hour"] == pytest.approx(1 / 3)
    assert out["worst_case"]["patients_with_events"] == 1


def test_nan_policy_omit_vs_zero():
    omit = E.score(_two_patients(), nan_policy="omit", n_bootstrap=10)
    zero = E.score(_two_patients(), nan_policy="zero", n_bootstrap=10)
    assert omit["average"]["sensitivity"] == pytest.approx(0.5) and omit["average"]["n_sensitivity"] == 1
    assert zero["average"]["sensitivity"] == pytest.approx(0.25) and zero["average"]["n_sensitivity"] == 2
    assert omit["provenance"]["nan_policy"] == "omit" and "SzCORE" in omit["provenance"]["nan_policy_meaning"]
    allfree = [rec("B", "b1", mask(100), mask(100))]
    assert E.score(allfree, nan_policy="omit", n_bootstrap=10)["pooled"]["sensitivity"] is None
    assert E.score(allfree, nan_policy="zero", n_bootstrap=10)["pooled"]["sensitivity"] == 0.0


def test_worst_case_zero_detection_patients():
    recs = [rec(f"P{i}", "r", mask(600, (100, 110)), mask(600, (100, 110)) if i else mask(600)) for i in range(5)]
    w = E.score(recs, n_bootstrap=10)["worst_case"]
    assert w["min_patient_sensitivity"] == 0.0 and w["patients_zero_detections"] == ["P0"]
    assert w["p10_patient_sensitivity"] == pytest.approx(0.4)


# ---------------------------------------------------------------- guards

@pytest.mark.parametrize("bad,msg", [
    ([], "non-empty"),
    ([rec("p", "r", [], [])], "non-empty"),
    ([rec("p", "r", [0, 0.9, 1], [0, 0, 1])], "exactly 0 or 1"),
    ([rec("p", "r", [0, 1, 1], [0, 2, 1])], "exactly 0 or 1"),
    ([rec("p", "r", [0, 1, 1], [0, 1])], "has 2 samples"),
    ([rec("p", "r", [0, 1, 1], [0, 1, 1], scores=[0.1, 0.2])], "has 2 samples"),
    ([rec("p", "r", [0, 1], [0, 1], fs=0)], "fs must be"),
    ([rec("p", "r", [0, 1], [0, 1], fs=True)], "fs must be"),
    ([rec("p", "r", [0, 1])], "decisions"),
    ([rec("p", "r", [0, 1], [0, 1]), rec("p", "r", [0, 1], [0, 1])], "duplicate"),
    ([rec("p", "r", [0], [0], fs=100)], "shorter"),
    ([rec("p", "r", [0, 1, 0], [0, 1, 0], timestamps=[0, 2, 1])], "increase"),
])
def test_rejects_bad_input(bad, msg):
    with pytest.raises(E.ScoringInputError, match=msg):
        E.score(bad, n_bootstrap=10)


def test_rejects_bad_params():
    for prof, par in (("adult", None), ("szcore", {"merge": 3}), ("szcore", {"tolerance_start_s": -1}),
                      ("szcore", {"min_overlap": 1.0})):
        with pytest.raises(E.ScoringInputError):
            E.resolve_params(prof, par)
    with pytest.raises(E.ScoringInputError):
        E.score([rec("p", "r", [0, 1], [0, 1])], nan_policy="ignore")


def test_unsorted_events_cannot_reach_timescoring():
    """Masks only: the same events in any order give one mask, so timescoring's merge bug cannot bite."""
    r = one(mask(2000, (500, 600), (100, 150), (520, 540)), mask(2000))
    assert r["refTrue"] == 2


def test_timestamp_gap_splits_recording():
    lab = mask(200, (95, 105))
    ts = list(range(100)) + [t + 10000.0 for t in range(100, 200)]
    out = E.score([rec("p", "r", lab, lab, timestamps=ts)], n_bootstrap=10)["per_recording"][0]
    assert out["n_segments"] == 2 and out["refTrue"] == 2 and out["hours"] == pytest.approx(200 / 3600)
    nogap = E.score([rec("p", "r", lab, lab, timestamps=list(range(200)))], n_bootstrap=10)["per_recording"][0]
    assert nogap["n_segments"] == 1 and nogap["refTrue"] == 1


# ---------------------------------------------------------------- sweep, AUC, bootstrap, provenance

def _scored(n_pat=4, seed=1):
    rng = np.random.default_rng(seed)
    recs = []
    for p in range(n_pat):
        lab = np.array(mask(3600, (1000, 1060), (2500, 2530)))
        sc = rng.random(3600) * 0.6 + lab * 0.5
        recs.append(rec(f"P{p}", "r", lab.tolist(), scores=sc.round(4).tolist()))
    return recs


def test_sweep_auc_bootstrap_provenance():
    out = E.score(_scored(), n_bootstrap=200)
    sw = out["sensitivity_at_fa"]
    assert sw["threshold_chosen_on_same_data"] is True and 2 <= sw["n_thresholds"] <= 200
    pts = {p["target_fa_per_hour"]: p for p in sw["points"]}
    assert set(pts) == {0.1, 0.36, 1.0}
    for t, p in pts.items():
        assert p["fa_per_hour"] <= t + 1e-9
    assert pts[1.0]["sensitivity"] >= pts[0.1]["sensitivity"]
    assert out["auc"]["pooled"] > 0.8 and out["auc"]["n_patients_defined"] == 4
    lo, hi = out["auc"]["per_patient_iqr"]
    assert lo <= out["auc"]["per_patient_median"] <= hi
    ci = out["bootstrap"]["ci95"]["sensitivity_pooled"]
    assert ci[0] <= ci[1] and out["bootstrap"]["n_resamples"] == 200
    again = E.score(_scored(), n_bootstrap=200, n_thresholds=10)
    assert again["bootstrap"] == out["bootstrap"]                        # fixed seed
    pv = out["provenance"]
    assert pv["timescoring_version"] == "0.0.7" and pv["parameters"]["merge_s"] == 90.0
    assert set(out["headline"]) == {"event_sensitivity", "fa_per_hour", "worst_patient_sensitivity", "auc"}
    json.dumps(out, allow_nan=False)                                     # strict JSON


def test_fixed_thresholds_flag_not_same_data():
    sw = E.score(_scored(), thresholds={"0.1": 0.9, "1.0": 0.7}, n_bootstrap=10)["sensitivity_at_fa"]
    assert sw["threshold_chosen_on_same_data"] is False
    pts = {p["target_fa_per_hour"]: p for p in sw["points"]}
    assert pts[0.1]["threshold"] == 0.9 and pts[0.36]["threshold"] is None


def test_roc_auc_numpy():
    assert E.roc_auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert E.roc_auc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)
    assert E.roc_auc([1, 1], [0.1, 0.2]) is None


def test_decisions_from_scores_and_metrics_alias():
    lab = mask(600, (100, 110))
    sc = (np.array(lab) * 0.9).tolist()
    r = metrics_events([rec("p", "r", lab, scores=sc)], n_bootstrap=10)["per_recording"][0]
    assert r["tp"] == 1 and r["decisions_from"] == "scores>=0.5"


# ---------------------------------------------------------------- tool and ./progress

def test_tool_and_progress(tmp_path, monkeypatch):
    from chiplab import tools
    from chiplab.progress import METRIC_KEYS
    log = tmp_path / "calls.txt"
    helper = tmp_path / "progress"
    helper.write_text(f"#!/bin/sh\n# ChipIn progress helper\necho \"$@\" >> {log}\n")
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "in.json"
    f.write_text(json.dumps({"recordings": _scored(3)}))
    res = tools.TOOLS["score_events"]["fn"](path=str(f), n_bootstrap=50, n_thresholds=20)
    assert res["status"] == "ok" and res["per_recording"][0]["numSamples"] == 3600
    assert not log.exists() or "event_sensitivity" not in log.read_text()   # off by default
    res = tools.TOOLS["score_events"]["fn"](recordings=_scored(3), n_bootstrap=50, n_thresholds=20,
                                            progress_metrics=True)
    lines = [ln.split() for ln in log.read_text().splitlines() if ln.startswith("metric")]
    sent = {ln[1]: ln for ln in lines}
    for k in ("event_sensitivity", "fa_per_hour", "worst_patient_sensitivity", "auc"):
        assert k in sent and sent[k][3] == METRIC_KEYS[k] and math.isfinite(float(sent[k][2]))
    bad = tools.TOOLS["score_events"]["fn"](recordings=[rec("p", "r", [0, 0.5], [0, 1])])
    assert bad["status"] == "error" and "exactly 0 or 1" in bad["error"]
    assert tools.TOOLS["score_events"]["fn"]()["status"] == "error"


def test_design_id_ties_metrics_to_a_chip(tmp_path, monkeypatch):
    from chiplab import tools
    from chiplab.progress import CHIP_FLAG_ENV, EVENT_KEYS
    log = tmp_path / "calls.txt"
    helper = tmp_path / "progress"
    helper.write_text(f"#!/bin/sh\n# ChipIn progress helper\necho \"$@\" >> {log}\n")
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(CHIP_FLAG_ENV, "1")
    fn = tools.TOOLS["score_events"]["fn"]
    kw = dict(recordings=_scored(3), n_bootstrap=50, n_thresholds=20, progress_metrics=True, force=True)

    def run(**extra):
        log.unlink(missing_ok=True)
        res = fn(**kw, **extra)
        lines = [ln.split() for ln in log.read_text().splitlines() if ln.startswith("metric")]
        return {k: v for k, v in res.items() if k not in ("cost", "cached")}, lines
    plain, plain_lines = run()
    tied, tied_lines = run(design_id="abc123def456")
    assert plain == tied                                            # the answer itself does not change
    assert plain_lines and all("--chip" not in ln for ln in plain_lines)
    scored = [ln for ln in tied_lines if ln[1] in EVENT_KEYS]       # run counters (candidates) never carry a chip
    assert {ln[1] for ln in scored} == set(EVENT_KEYS)
    assert all(ln[-2:] == ["--chip", "abc123def456"] for ln in scored)


def test_engine_load_batch_weights_only(tmp_path):
    """A real intnn training state round-trips through torch.load(weights_only=True) in load_batch."""
    torch = pytest.importorskip("torch")
    from chiplab.plugins.base import BatchInputs
    from chiplab.plugins.families.intnn import FAMILY
    from chiplab.train.engine import load_batch
    r = np.random.default_rng(0)
    a = r.integers(0, 16, size=(256, 6)); y = (a[:, :3].sum(1) > a[:, 3:].sum(1)).astype(int)
    ins = {"u": {"lanes": 6, "bits": 4, "signed": False}}
    t = {"u": torch.tensor(a, dtype=torch.float32)}
    cfgs = [{"hidden": [4], "wtype": "ternary", "epochs": 1, "batch_size": 64}]
    state = FAMILY.train(cfgs, BatchInputs(keys=["u"], tensors=t, in_specs=ins, y=torch.tensor(y)), "cpu", {"n_classes": 2})
    torch.save(state, tmp_path / "state.pt")
    for name, obj in (("cands.json", []), ("val_scores.json", []), ("batch.json", {}),
                      ("encodings.json", {"keys": ["u"], "fitted": {}, "in_specs": ins})):
        (tmp_path / name).write_text(json.dumps(obj))
    back = load_batch(tmp_path)["state"]
    assert FAMILY.int_params(back, 0) == FAMILY.int_params(state, 0)
