import numpy as np
import pytest

from chiplab.data.splits import counts, make_split, split_hash


def _spike_split(labels, seed=0):
    """The feasibility spike's split, copied verbatim (spike/src/common.py)."""
    rng = np.random.default_rng(seed)
    split = np.zeros(len(labels), dtype=int)
    for c in (0, 1):
        idx = np.where(labels == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        split[idx[int(0.70 * n):int(0.85 * n)]] = 1
        split[idx[int(0.85 * n):]] = 2
    return split


def test_matches_spike_exactly():
    r = np.random.default_rng(5)
    labels = (r.random(997) < 0.13).astype(int)
    subs = [f"s{i}" for i in range(len(labels))]
    a = make_split(subs, labels.tolist(), seed=0)
    assert [a[s] for s in subs] == _spike_split(labels).tolist()


def test_no_subject_in_two_parts_and_hash_stable():
    subs = [f"p{i}" for i in range(40)]
    a = make_split(subs, [i % 3 for i in range(40)], seed=3)
    assert set(a) == set(subs) and set(a.values()) <= {0, 1, 2}
    assert sum(counts(a)) == 40
    assert split_hash(a, "x") == split_hash(dict(reversed(list(a.items()))), "x")
    assert split_hash(a, "x") != split_hash(a, "y")
    b = dict(a); b["p0"] = (b["p0"] + 1) % 3
    assert split_hash(a, "x") != split_hash(b, "x")


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        make_split(["a", "a"], [0, 1])
    with pytest.raises(ValueError):
        make_split(["a", "b"], [0, 1], fractions=(0.5, 0.6, 0.1))
