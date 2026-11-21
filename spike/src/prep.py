"""Step 0: read AF (A) and Normal (N) recordings from the CinC 2017 zip,
detect R peaks (wfdb xqrs), store RR intervals (ms) per recording.
usage: python -I prep.py <training2017.zip> <out.npz>"""
import io
import sys
import zipfile
from multiprocessing import Pool

import numpy as np
from scipy.io import loadmat
import wfdb.processing as wp

ZIP = sys.argv[1]
OUT = sys.argv[2]
FS = 300


def work(item):
    name, lab = item
    try:
        with zipfile.ZipFile(ZIP) as z:
            m = loadmat(io.BytesIO(z.read(f"training2017/{name}.mat")))
        sig = m["val"].astype(np.float64).ravel()
        peaks = wp.xqrs_detect(sig=sig, fs=FS, verbose=False)
        rr = np.diff(np.asarray(peaks)) * 1000.0 / FS
        return name, lab, rr.astype(np.float32)
    except Exception as e:  # report, keep going
        return name, lab, str(e)


if __name__ == "__main__":
    with zipfile.ZipFile(ZIP) as z:
        ref = z.read("training2017/REFERENCE.csv").decode().split()
    items = [tuple(r.split(",")) for r in ref]
    cnt = {}
    for _, l in items:
        cnt[l] = cnt.get(l, 0) + 1
    print("all labels in zip:", cnt, flush=True)
    items = [(n, l) for n, l in items if l in ("N", "A")]
    print("kept N and A:", len(items), flush=True)
    names, labs, rrs, bad = [], [], [], []
    with Pool(8) as p:
        for i, (n, l, rr) in enumerate(p.imap(work, items, chunksize=8)):
            if isinstance(rr, str):
                bad.append((n, rr))
                continue
            names.append(n); labs.append(1 if l == "A" else 0); rrs.append(rr)
            if i % 500 == 0:
                print("done", i, flush=True)
    print("failed:", len(bad), bad[:3])
    lens = np.array([len(r) for r in rrs])
    flat = np.concatenate(rrs)
    np.savez(OUT, names=np.array(names), labels=np.array(labs), lens=lens, flat=flat)
    print("saved", OUT, "records", len(names), "median RR count", np.median(lens))
