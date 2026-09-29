"""Adversarial check on the claimed 'required IC of 0.021-0.035'.

Measures the Spearman rank IC between trailing momentum and forward return on the
project's own 47-symbol daily spot panel, at the horizons that matter, and compares
it to (a) the claimed requirement and (b) the single-test / deflated benchmarks.
Also reports the cross-sectional Fama-MacBeth style t-stat, which is the statistic
the literature actually uses for a cross-sectional signal.
"""
import os
import sys
import glob
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from ls_test import load_panel, iat, nw_tstat, maxdd  # noqa: E402


def forward(px, h):
    return px.shift(-h) / px - 1.0


def rank_ic(mom, fwd):
    """Per-date Spearman rank IC, pooled over dates where the universe is valid."""
    a = mom.rank(axis=1, pct=True)
    b = fwd.rank(axis=1, pct=True)
    ic = a.corrwith(b, axis=1)
    return ic.dropna()


def main():
    px = load_panel()
    px = px.loc["2019-01-01":]
    print(f"panel {px.shape[0]}x{px.shape[1]}  {px.index[0].date()} -> {px.index[-1].date()}\n")

    rows = []
    for lb in (14, 30, 60, 90, 180):
        mom = px / px.shift(lb) - 1.0
        for h in (1, 7, 14, 30):
            fwd = forward(px, h).clip(-3.0, 8.0)
            ic = rank_ic(mom, fwd)
            if len(ic) < 100:
                continue
            t, lags = nw_tstat(ic.values)
            ne, n = iat(ic.values)
            # effective number of cross-sectional observations (per repo trap 3.5:
            # the COUNT is still T dates; N names raise per-date precision, not the count)
            ppy = 365.0 / h
            rows.append(dict(
                lookback=lb, fwd_h=h, T=int(n), effT=round(ne, 0),
                mean_IC=round(ic.mean(), 4), t_HAC=round(t, 2),
                mean_IC_ann=round(ic.mean() * np.sqrt(ppy), 4),
            ))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print("Spearman rank IC of trailing momentum on the project's own 47-symbol panel")
    print(out.to_string(index=False))

    print("\n--- benchmarks ---")
    print("claimed 'required IC' band .............. 0.021 - 0.035")
    print("mean daily rank IC observed here ........ "
          f"{out[out.fwd_h == 1].mean_IC.mean():.4f}")
    print("mean weekly (7d) rank IC observed ....... "
          f"{out[out.fwd_h == 7].mean_IC.mean():.4f}")


if __name__ == "__main__":
    main()
