"""Independent re-derivation of the universe factor structure.

`variance_decomp.py` first reported mean pairwise 4h correlation +0.258, top
eigen-direction 28%, 11.5 effective bets. Those numbers were WRONG: the panel
was log-transformed twice (`np.log(px / px.shift(1))` applied to a frame that
already held log returns), which turned every negative return into NaN and
compressed the rest. After the fix the same script reports +0.481 / 52% / 3.7.

A number that moved that much, in the direction that makes the project's
conclusion stronger, is exactly the kind of number to check with a second,
independently written implementation before it goes into a document.

This file shares NO code with variance_decomp.py on purpose: different loader,
different return definition (simple returns, not log), different correlation
route, and the participation ratio is computed from the eigenvalues by a
different formula.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\verify_factor_structure.py
"""

from __future__ import annotations

import sys
import zipfile
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
ZIP = ROOT / "user_data" / "sizing_out" / "full" / "n50" / \
    "backtest-result-2026-09-28_21-44-27.zip"


def universe() -> list[str]:
    with zipfile.ZipFile(ZIP) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        d = json.loads(zf.read(mj))
    (name,) = d["strategy"].keys()
    return sorted({t["pair"] for t in d["strategy"][name]["trades"]})


def main() -> int:
    pairs = universe()
    print(f"universe: {len(pairs)} symbols from the full/n50 result\n")

    # ---- simple returns, built by joining on date, not by positional diff ---
    wide = {}
    for p in pairs:
        f = DATA / f"{p.replace('/', '_').replace(':', '_')}-4h-futures.feather"
        d = pd.read_feather(f)[["date", "close"]]
        d["date"] = pd.to_datetime(d["date"], utc=True)
        wide[p] = d.set_index("date")["close"]
    px = pd.DataFrame(wide).sort_index()
    print(f"panel: {px.shape[0]} timestamps x {px.shape[1]} symbols, "
          f"{px.isna().sum().sum()} missing cells")

    simple = px.pct_change()
    bad = int(np.isinf(simple.to_numpy()).sum())
    print(f"simple returns: {bad} infinite values, "
          f"{int(np.isnan(simple.to_numpy()).sum())} NaN")

    # Correlation via pairwise-complete observations, and a second route: the
    # correlation of z-scores over the rows where BOTH symbols are present.
    C = simple.corr(min_periods=200)
    C = C.dropna(how="all").dropna(axis=1, how="all")
    iu = np.triu_indices(len(C), 1)
    vals = C.to_numpy()[iu]
    vals = vals[np.isfinite(vals)]
    print(f"\nA. pairwise-complete correlation, n={len(C)} symbols")
    print(f"   mean {vals.mean():+.4f}  median {np.median(vals):+.4f}  "
          f"min {vals.min():+.3f}  max {vals.max():+.3f}")

    # route B: complete-case only
    sub = simple.dropna()
    Cb = sub.corr()
    vb = Cb.to_numpy()[iu]
    vb = vb[np.isfinite(vb)]
    print(f"B. complete-case correlation, n={len(sub)} timestamps x {len(Cb)} "
          f"symbols")
    print(f"   mean {vb.mean():+.4f}  median {np.median(vb):+.4f}")

    # route C: log returns, for comparison with the other script
    lg = np.log(px).diff()
    Cl = lg.corr(min_periods=200)
    Cl = Cl.dropna(how="all").dropna(axis=1, how="all")
    vl = Cl.to_numpy()[iu]
    vl = vl[np.isfinite(vl)]
    print(f"C. log-return correlation (the other script's definition), "
          f"n={len(Cl)} symbols")
    print(f"   mean {vl.mean():+.4f}  median {np.median(vl):+.4f}")

    # ---- eigenvalues -------------------------------------------------------
    for tag, M in (("A", C), ("B", Cb), ("C", Cl)):
        A = M.fillna(0.0).to_numpy()
        w = np.linalg.eigvalsh(A)[::-1]
        w = np.clip(w, 0, None)
        n = len(w)
        # participation ratio: (sum w)^2 / sum w^2, the standard "effective
        # number of dimensions" for a correlation spectrum
        pr = float(w.sum() ** 2 / (w ** 2).sum())
        print(f"\n   route {tag}: top eigenvalue {w[0]/n*100:.1f}% of the mean, "
              f"top-1 share of total variance {w[0]/w.sum()*100:.1f}%, "
              f"participation ratio = {pr:.1f} of {n}")

    print("""
READING THIS
  The three routes are three different definitions of the same thing and they
  must agree to within a few points, or one of them is measuring something else.
  `variance_decomp.py`'s first answer (+0.258 / 28% / 11.5) did NOT survive:
  its panel was log-transformed twice. The correct figure is the one these
  three routes agree on.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
