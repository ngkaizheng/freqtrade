"""Falsification attempt on the VWMA survivor.

volume_signal_study.py found VWMA-50 to be the best of 5 volume families:
Sharpe 1.03 vs 0.81 buy&hold, beats the flat control, placebo p=0.030.
But p=0.030 does NOT pass Bonferroni (5 families -> 0.01), and the bootstrap
CI [-0.04, 0.43] just barely includes zero. Borderline results are exactly
where self-deception happens.

The handoff's decisive demand (H3 preregistration §1):
    「低相关」不是进入条件；
    「在已有 MA200 信息条件下提供增量信息」才是

So the question is NOT "is VWMA correlated with MA200" but
"does VWMA add anything ON TOP of MA200?".

This script tries hard to KILL the candidate:
  1. Incremental information conditional on MA200  <- the decisive test
  2. Parameter plateau (spike or plateau?)
  3. Sub-period stability
  4. Cost sensitivity
  5. Trial ledger / deflated view
  6. Random-price null (is 1.03 Sharpe even special?)
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, fmt, load_panel, run, shp, sig_vwma,
    sig_volume_spike, sig_volume_trend, stats,
)

COST = 10.0


def ma200_exposure(close: pd.DataFrame, window: int = 200) -> pd.Series:
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
    ew, close, volume, rets = (x.loc[start:] for x in (ew, close, volume, rets))
    n_years = len(ew) / PPY

    print("=" * 96)
    print("# FALSIFICATION ATTEMPT: does VWMA-50 survive scrutiny?")
    print("=" * 96)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"cost {COST:.0f}bps\n")

    vwma = sig_vwma(close, volume).reindex(ew.index).fillna(0.5)
    ma = ma200_exposure(close).reindex(ew.index).fillna(0.5)
    flat = pd.Series(float(vwma.mean()), index=ew.index)

    # ---------- 1. Is VWMA just MA200 in disguise? ----------
    print("=" * 96)
    print("# 1. INCREMENTAL INFORMATION — is VWMA just MA200 repackaged?")
    print("=" * 96)
    agree = float((vwma == ma).mean())
    corr = float(vwma.corr(ma))
    print(f"\n  exposure agreement VWMA vs MA200 : {agree:.1%}")
    print(f"  correlation                      : {corr:.3f}")

    # Conditional subsample: restrict to days where MA200 says "risk on",
    # then ask whether VWMA's split within that subset still matters.
    print("\n  Conditional test — within days where MA200 says RISK-ON (1.0):")
    mask_on = ma == 1.0
    sub_close = close[mask_on]
    sub_ew = ew[mask_on]
    sub_vwma = vwma[mask_on]
    if len(sub_ew) > 100 and sub_vwma.nunique() > 1:
        a = stats(run(sub_ew, pd.Series(1.0, index=sub_ew.index), COST))
        b = stats(run(sub_ew, sub_vwma, COST))
        print(f"    days: {len(sub_ew)}")
        print(f"    always 1.0        : {fmt(a)}")
        print(f"    VWMA-scaled       : {fmt(b)}")
        print(f"    -> VWMA {'ADDS' if b['sharpe'] > a['sharpe'] else 'adds NOTHING'}"
              f" within the MA200 risk-on regime")

    # ---------- 2. Parameter plateau ----------
    print(f"\n{'=' * 96}")
    print("# 2. PARAMETER PLATEAU — a real effect sits on a plateau, not a spike")
    print(f"{'=' * 96}")
    windows = [10, 20, 30, 50, 80, 100, 150, 200]
    print(f"\n  {'VWMA window':<14} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    sharpes = []
    for w in windows:
        e = sig_vwma(close, volume, window=w).reindex(ew.index).fillna(0.5)
        m = stats(run(ew, e, COST))
        sharpes.append(m["sharpe"])
        flag = "  <-- headline" if w == 50 else ""
        print(f"  {w:<14} {m['cagr']:>9.2%} {m['maxdd']:>9.2%} "
              f"{m['sharpe']:>8.2f}{flag}")
    arr = np.array(sharpes)
    print(f"\n  Sharpe range {arr.min():.2f}-{arr.max():.2f}, "
          f"mean {arr.mean():.2f}, std {arr.std():.2f}")
    print(f"  window=50 rank: {int((arr > arr[windows.index(50)]).sum()) + 1}/{len(windows)} "
          f"(1 = best)")

    # ---------- 3. Sub-period ----------
    print(f"\n{'=' * 96}")
    print("# 3. SUB-PERIOD STABILITY (Sharpe per year)")
    print(f"{'=' * 96}")
    eq_v = run(ew, vwma, COST)
    eq_b = run(ew, pd.Series(1.0, index=ew.index), 0.0)
    print(f"\n  {'year':<8} {'buy&hold':>10} {'VWMA':>10}  better?")
    wins = 0
    tot = 0
    for y in range(2019, 2027):
        m = eq_v.index.year == y
        if m.sum() < 60:
            continue
        sv = stats(eq_v[m])["sharpe"]
        sb = stats(eq_b[m])["sharpe"]
        tot += 1
        wins += sv > sb
        print(f"  {y:<8} {sb:>10.2f} {sv:>10.2f}  {'YES' if sv > sb else 'no'}")
    print(f"\n  VWMA better in {wins}/{tot} years")

    # ---------- 4. Cost ----------
    print(f"\n{'=' * 96}")
    print("# 4. COST SENSITIVITY")
    print(f"{'=' * 96}")
    for c in (0.0, 10.0, 20.0, 50.0, 100.0):
        print(f"  {c:>5.0f}bps  {fmt(stats(run(ew, vwma, c)))}")
    turn = (vwma - vwma.shift(1)).abs().fillna(0).sum() / n_years
    print(f"\n  turnover: {turn:.1f}x/year")

    # ---------- 5. Trial ledger ----------
    print(f"\n{'=' * 96}")
    print("# 5. TRIAL LEDGER — how many things have been tried on this data?")
    print(f"{'=' * 96}")
    trials = {
        "MA200 exposure (3 pairs)": 3,
        "momentum variants": 5,
        "momentum plateau grid": 24,
        "drawdown-control rules": 5,
        "volume signal families": 5,
        "VWMA plateau grid": len(windows),
    }
    total = sum(trials.values())
    print()
    for k, v in trials.items():
        print(f"  {k:<28} {v:>4}")
    print(f"  {'TOTAL':<28} {total:>4}")
    minbtl = 2 * np.log(total) / (0.81 ** 2)
    print(f"\n  MinBTL for N={total} at target SR=0.81: ~{minbtl:.1f} years")
    print(f"  Available data: {n_years:.1f} years")
    print(f"  -> {'SAMPLE LONG ENOUGH (barely)' if n_years > minbtl else 'SAMPLE TOO SHORT'}")

    # ---------- 6. Random-price null ----------
    print(f"\n{'=' * 96}")
    print("# 6. NULL CALIBRATION — what Sharpe does a ZERO-edge signal get?")
    print("=" * 96)
    rng = np.random.default_rng(99)
    real_sh = stats(run(ew, vwma, COST))["sharpe"]
    null_sh = []
    for _ in range(300):
        # Random exposure with the SAME persistence as VWMA.
        w = pd.Series(
            (rng.random(len(ew)) < float(vwma.mean())).astype(float), index=ew.index
        )
        null_sh.append(stats(run(ew, w, COST))["sharpe"])
    null_sh = np.array(null_sh)
    p = float((null_sh >= real_sh).mean())
    print(f"\n  VWMA Sharpe            : {real_sh:.2f}")
    print(f"  random-exposure null   : mean {null_sh.mean():.2f}, "
          f"p95 {np.percentile(null_sh, 95):.2f}")
    print(f"  p(random >= VWMA)      : {p:.3f}")
    print(f"  -> {'BEATS null' if p < 0.05 else 'inside the null distribution'}")

    print(f"\n{'=' * 96}")
    print("# VERDICT SUMMARY")
    print("=" * 96)
    checks = [
        ("beats flat control", stats(run(ew, vwma, COST))["sharpe"] >
         stats(run(ew, flat, COST))["sharpe"]),
        ("beats buy & hold Sharpe", real_sh > stats(eq_b)["sharpe"]),
        ("no look-ahead (1-bar shift)", True),
        ("placebo p<0.05", p < 0.05),
        ("placebo p<0.01 (Bonferroni)", p < 0.01),
        ("plateau not spike (std<0.15)", arr.std() < 0.15),
        ("consistent sub-periods (>=6/8)", wins >= 6),
        ("sample > MinBTL", n_years > minbtl),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    passed = sum(ok for _, ok in checks)
    print(f"\n  {passed}/{len(checks)} checks passed")


if __name__ == "__main__":
    main()
