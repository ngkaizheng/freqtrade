"""Head-to-head: is the VWMA signal anything more than an MA200 price trend?

vwma_falsification.py showed that WITHIN MA200 risk-on days, VWMA-scaled
exposure (Sharpe 2.28) is WORSE than simply holding 1.0 (Sharpe 2.44).
That suggests the volume signal contributes nothing on top of price trend.

This script settles it cleanly by comparing, at MATCHED average exposure:
  * MA200 alone        (pure price trend)
  * VWMA-50 alone      (price trend + volume weighting)
  * combination        (both must agree)
and by direct comparison VWMA vs MA200 on the days they DISAGREE.
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, fmt, load_panel, run, shp, sig_vwma, stats,
)

COST = 10.0


def ma200_exposure(close, window=200):
    c = close.mean(axis=1, skipna=True)
    ma = c.rolling(window, min_periods=window).mean()
    valid = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[valid] = np.where(c[valid] > ma[valid], 1.0, 0.5)
    return out


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)
    start = "2019-01-01"
    ew, close, volume = ew.loc[start:], close.loc[start:], volume.loc[start:]
    n_years = len(ew) / PPY

    vwma = sig_vwma(close, volume).reindex(ew.index).fillna(0.5)
    ma = ma200_exposure(close).reindex(ew.index).fillna(0.5)
    combo = pd.concat([vwma, ma], axis=1).min(axis=1)

    print("=" * 96)
    print("# HEAD-TO-HEAD: MA200 (price) vs VWMA (volume-weighted price)")
    print("=" * 96)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"{COST:.0f}bps\n")

    cands = {"MA200 alone": ma, "VWMA-50 alone": vwma,
             "min(MA200, VWMA)": combo}

    print(f"  {'rule':<20} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}  "
          f"{'vs flat':>9}")
    for name, e in cands.items():
        avg = float(e.mean())
        d = stats(run(ew, e, COST))
        f = stats(run(ew, pd.Series(avg, index=ew.index), COST))
        print(f"  {name:<20} {avg:>6.1%} {d['cagr']:>9.2%} {d['maxdd']:>9.2%} "
              f"{d['sharpe']:>8.2f}  {d['sharpe']-f['sharpe']:>+9.3f}")

    # --- The decisive question: on days they DISAGREE, who is right? ---
    print(f"\n{'=' * 96}")
    print("# DISAGREEMENT ANALYSIS — where MA200 and VWMA differ, who wins?")
    print(f"{'=' * 96}")
    disagree = ma != vwma
    n_dis = int(disagree.sum())
    ma_bull_vwma_bear = (ma == 1.0) & (vwma == 0.5)
    ma_bear_vwma_bull = (ma == 0.5) & (vwma == 1.0)
    print(f"\n  days in agreement   : {int((~disagree).sum())} "
          f"({float((~disagree).mean()):.1%})")
    print(f"  days in disagreement: {n_dis} ({float(disagree.mean()):.1%})")
    print(f"    MA200 bull, VWMA bear : {int(ma_bull_vwma_bear.sum())}")
    print(f"    MA200 bear, VWMA bull : {int(ma_bear_vwma_bull.sum())}")

    fwd = ew.shift(-1)  # next-day return
    for label, mask in (("MA200 bull / VWMA bear", ma_bull_vwma_bear),
                        ("MA200 bear / VWMA bull", ma_bear_vwma_bull)):
        if mask.sum() == 0:
            continue
        r = fwd[mask].dropna()
        print(f"\n  {label}: n={len(r)}  mean next-day ret {r.mean():+.4%}  "
              f"annualised {r.mean()*PPY:+.1%}")
    print("\n  (If VWMA had real information, the side it favours should")
    print("   show a systematically better forward return.)")

    # --- Paired bootstrap: VWMA vs MA200 ---
    print(f"\n{'=' * 96}")
    print("# PAIRED BOOTSTRAP — Sharpe(VWMA) - Sharpe(MA200), 5000 draws")
    print(f"{'=' * 96}")
    pv = vwma.shift(1).fillna(0.0)
    pm = ma.shift(1).fillna(0.0)
    tv = pv.diff().abs().fillna(pv.abs())
    tm = pm.diff().abs().fillna(pm.abs())
    rv = (pv * ew - tv * COST / 10_000).to_numpy()
    rm = (pm * ew - tm * COST / 10_000).to_numpy()
    n = len(rv)
    point = shp(rv) - shp(rm)
    rng = np.random.default_rng(21)
    boots = np.array([shp(rv[i]) - shp(rm[i])
                      for i in (block_idx(n, 20, rng) for _ in range(5000))])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"\n  dSharpe {point:+.3f}   95% CI [{lo:+.2f}, {hi:+.2f}]   "
          f"p(<=0) {float((boots <= 0).mean()):.3f}")
    print(f"  -> VWMA is {'significantly better' if lo > 0 else 'NOT distinguishable from'} MA200")

    # --- Same test for the flat control, to calibrate ---
    print(f"\n{'=' * 96}")
    print("# CALIBRATION — same bootstrap vs the FLAT control at matched exposure")
    print(f"{'=' * 96}")
    for name, e in cands.items():
        p_ = e.shift(1).fillna(0.0)
        t_ = p_.diff().abs().fillna(p_.abs())
        r_ = (p_ * ew - t_ * COST / 10_000).to_numpy()
        r_f = (float(e.mean()) * ew).to_numpy()
        b = np.array([shp(r_[i]) - shp(r_f[i])
                      for i in (block_idx(n, 20, rng) for _ in range(3000))])
        l, h = np.percentile(b, [2.5, 97.5])
        print(f"  {name:<20} dSharpe {shp(r_)-shp(r_f):+.3f}  "
              f"CI [{l:+.2f}, {h:+.2f}]  "
              f"{'SIGNIFICANT' if l > 0 else 'not significant'}")

    # --- Conclusion ---
    print(f"\n{'=' * 96}")
    print("# CONCLUSION")
    print("=" * 96)
    ma_sh = stats(run(ew, ma, COST))["sharpe"]
    vw_sh = stats(run(ew, vwma, COST))["sharpe"]
    if abs(ma_sh - vw_sh) < 0.15:
        print(f"\n  MA200 ({ma_sh:.2f}) and VWMA ({vw_sh:.2f}) perform comparably.")
        print("  The volume weighting is NOT adding independent information —")
        print("  both are price-trend rules, and the headline Sharpe came from")
        print("  trend-following, not from volume.")
    else:
        print(f"\n  VWMA {vw_sh:.2f} vs MA200 {ma_sh:.2f} — see CI above for whether"
              " this difference is real.")


if __name__ == "__main__":
    main()
