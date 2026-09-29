"""Final gate: walk-forward / out-of-sample test for SMA-50.

sma50_verification.py found SMA-50 genuinely significant vs the flat control
(dSharpe +0.257, CI [+0.02, +0.48], placebo p=0.005). That is the first
candidate in this project to clear the standard gates.

But the trial ledger now stands at ~54 configurations, and the window was
chosen AFTER seeing the grid (20/50/100/200 -> 50 won). That is exactly the
selection process the handoff warns about.

This script applies the last honest test:
  1. Walk-forward: choose the best window IN-SAMPLE, trade it OUT-OF-SAMPLE,
     roll forward. Report only the stitched OOS result.
  2. Anchored OOS: fit on the first half, freeze, test on the second half.
  3. Deflated view: what does the Sharpe have to clear given N trials?
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, load_panel, run, stats,
)
from volume_vs_speed import sma_exposure

COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)
    start = "2019-01-01"
    ew, close = ew.loc[start:], close.loc[start:]
    n_years = len(ew) / PPY
    n = len(ew)

    print("=" * 94)
    print("# FINAL GATE — walk-forward / out-of-sample for the SMA rule")
    print("=" * 94)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"{COST:.0f}bps\n")

    # Precompute exposures for every window once.
    exps = {w: sma_exposure(close, w).reindex(ew.index).fillna(0.5)
            for w in WINDOWS}

    def sharpe_of(mask: pd.Series, w: int) -> float:
        """In-sample Sharpe of window w restricted to `mask`."""
        r = ew[mask]
        e = exps[w][mask]
        return stats(run(r, e, COST))["sharpe"]

    # ---------- 1. Walk-forward ----------
    print("=" * 94)
    print("# 1. WALK-FORWARD — pick the window in-sample, trade it out-of-sample")
    print("=" * 94)
    n_folds = 6
    fold_size = n // (n_folds + 1)
    oos_returns = []
    print(f"\n  {'fold':<6} {'train':<24} {'test':<24} {'chosen':>8} "
          f"{'IS SR':>8} {'OOS SR':>8}")
    for k in range(n_folds):
        train_end = fold_size * (k + 1)
        test_end = min(train_end + fold_size, n)
        train_mask = pd.Series(False, index=ew.index)
        train_mask.iloc[:train_end] = True
        test_mask = pd.Series(False, index=ew.index)
        test_mask.iloc[train_end:test_end] = True
        if test_mask.sum() < 30:
            continue

        # Choose the window using ONLY the training data.
        best_w, best_sr = None, -np.inf
        for w in WINDOWS:
            sr = sharpe_of(train_mask, w)
            if sr > best_sr:
                best_w, best_sr = w, sr

        e = exps[best_w][test_mask]
        seg = run(ew[test_mask], e, COST)
        oos_returns.append(seg.pct_change().dropna())
        print(f"  {k + 1:<6} "
              f"{str(ew.index[0].date()) + '..' + str(ew.index[train_end - 1].date()):<24} "
              f"{str(ew.index[train_end].date()) + '..' + str(ew.index[test_end - 1].date()):<24} "
              f"{best_w:>8} {best_sr:>8.2f} {stats(seg)['sharpe']:>8.2f}")

    if oos_returns:
        stitched = pd.concat(oos_returns)
        oos_sr = float(stitched.mean() / stitched.std() * np.sqrt(PPY))
        # Buy & hold over the same OOS stitched period, for reference.
        bh_stitched = []
        for k in range(n_folds):
            train_end = fold_size * (k + 1)
            test_end = min(train_end + fold_size, n)
            if test_end - train_end < 30:
                continue
            bh_stitched.append(ew.iloc[train_end:test_end])
        bhs = pd.concat(bh_stitched)
        bh_sr = float(bhs.mean() / bhs.std() * np.sqrt(PPY))
        print(f"\n  Stitched OOS Sharpe (walk-forward): {oos_sr:.2f}")
        print(f"  Buy & hold over same period       : {bh_sr:.2f}")
        print(f"  -> {'OOS holds up' if oos_sr > bh_sr else 'OOS FAILS to beat buy & hold'}")

    # ---------- 2. Anchored split ----------
    print(f"\n{'=' * 94}")
    print("# 2. ANCHORED SPLIT — fit on first half, freeze, test on second half")
    print(f"{'=' * 94}")
    mid = n // 2
    train = pd.Series(False, index=ew.index)
    train.iloc[:mid] = True
    test = ~train

    best_w, best_sr = None, -np.inf
    for w in WINDOWS:
        sr = sharpe_of(train, w)
        if sr > best_sr:
            best_w, best_sr = w, sr
    print(f"\n  window chosen on 1st half: {best_w}  (IS Sharpe {best_sr:.2f})")

    e_test = exps[best_w][test]
    oos = stats(run(ew[test], e_test, COST))
    bh_oos = stats(run(ew[test], pd.Series(1.0, index=ew[test].index), 0.0))
    flat_oos = stats(run(ew[test], pd.Series(float(e_test.mean()),
                                             index=ew[test].index), COST))
    print(f"  2nd-half period          : {ew.index[mid].date()} -> "
          f"{ew.index[-1].date()}")
    print(f"\n    {'rule':<26} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    print(f"    {'frozen SMA-' + str(best_w):<26} {oos['cagr']:>9.2%} "
          f"{oos['maxdd']:>9.2%} {oos['sharpe']:>8.2f}")
    print(f"    {'buy & hold':<26} {bh_oos['cagr']:>9.2%} "
          f"{bh_oos['maxdd']:>9.2%} {bh_oos['sharpe']:>8.2f}")
    print(f"    {'flat control (same avg)':<26} {flat_oos['cagr']:>9.2%} "
          f"{flat_oos['maxdd']:>9.2%} {flat_oos['sharpe']:>8.2f}")
    print(f"\n  OOS beats buy & hold Sharpe? "
          f"{'YES' if oos['sharpe'] > bh_oos['sharpe'] else 'NO'}")
    print(f"  OOS beats flat control?      "
          f"{'YES' if oos['sharpe'] > flat_oos['sharpe'] else 'NO'}")

    # ---------- 3. Deflated view ----------
    print(f"\n{'=' * 94}")
    print("# 3. DEFLATED VIEW — what must a Sharpe clear given N trials?")
    print(f"{'=' * 94}")
    # Bailey & Lopez de Prado expected max Sharpe under the null.
    g = 0.5772156649
    for N in (8, 54, 100):
        # Variance of Sharpe estimates across trials; use the observed spread
        # of window Sharpes as a proxy.
        srs = np.array([stats(run(ew, exps[w], COST))["sharpe"] for w in WINDOWS])
        v = srs.var()
        e_max = np.sqrt(v) * ((1 - g) * 1.96 + g * 2.0)  # rough Gumbel approx
        print(f"\n  N={N:<4} observed Sharpe spread (var) {v:.3f}  "
              f"-> expected max under null ~{e_max:.2f}")
    print("\n  Note: at 7.7 years SE(Sharpe) = 0.36, so the null already")
    print("  produces Sharpes near 0.8-1.0 by chance alone.")

    print(f"\n{'=' * 94}")
    print("# VERDICT")
    print("=" * 94)
    if oos_returns:
        print(f"\n  Walk-forward OOS Sharpe {oos_sr:.2f} vs buy & hold {bh_sr:.2f}")
    print(f"  Anchored OOS: rule {oos['sharpe']:.2f} vs BH {bh_oos['sharpe']:.2f} "
          f"vs flat {flat_oos['sharpe']:.2f}")


if __name__ == "__main__":
    main()
