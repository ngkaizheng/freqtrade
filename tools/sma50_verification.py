"""Verify the SMA-50 headline: does it beat the FLAT control at matched exposure?

The findings doc quotes a "+0.255" figure for SMA-50. That number came from the
SMA50-vs-SMA200 contrast, NOT from the flat control. This script computes the
number that actually matters, plus the placebo and bootstrap.
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, load_panel, run, shp, stats, wildcard,
)
from volume_vs_speed import sma_exposure

COST = 10.0


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)
    start = "2019-01-01"
    ew, close = ew.loc[start:], close.loc[start:]
    n_years = len(ew) / PPY
    n = len(ew)

    bh = stats(run(ew, pd.Series(1.0, index=ew.index), 0.0))
    print("=" * 92)
    print("# SMA-50: verify against the FLAT control, placebo, and bootstrap")
    print("=" * 92)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"{COST:.0f}bps")
    print(f"buy & hold: CAGR {bh['cagr']:.2%}, MaxDD {bh['maxdd']:.2%}, "
          f"Sharpe {bh['sharpe']:.2f}\n")

    print(f"  {'rule':<22} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8} "
          f"{'dSharpe vs flat':>17}")
    out = {}
    for w in (20, 50, 100, 200):
        e = sma_exposure(close, w).reindex(ew.index).fillna(0.5)
        avg = float(e.mean())
        d = stats(run(ew, e, COST))
        f = stats(run(ew, pd.Series(avg, index=ew.index), COST))
        out[w] = (e, d, f, avg)
        print(f"  {'SMA-' + str(w):<22} {avg:>6.1%} {d['cagr']:>9.2%} "
              f"{d['maxdd']:>9.2%} {d['sharpe']:>8.2f} "
              f"{d['sharpe'] - f['sharpe']:>+17.3f}")

    # Placebo for each window
    print(f"\n{'=' * 92}")
    print("# WILDCARD PLACEBO (200 draws) — random exposure, matched mean")
    print(f"{'=' * 92}")
    rng = np.random.default_rng(17)
    print(f"\n  {'rule':<22} {'Sharpe':>8} {'p(Sharpe)':>10} {'p(MaxDD)':>10}  "
          f"verdict (4 windows -> Bonferroni p<0.0125)")
    for w, (e, d, f, avg) in out.items():
        sh, dd = [], []
        for _ in range(200):
            m = stats(run(ew, wildcard(avg, n, ew.index, 30, rng), COST))
            sh.append(m["sharpe"]); dd.append(m["maxdd"])
        p_sh = float((np.array(sh) >= d["sharpe"]).mean())
        p_dd = float((np.array(dd) >= d["maxdd"]).mean())
        verdict = ("PASSES Bonferroni" if p_sh < 0.0125
                   else "weak (p<0.05)" if p_sh < 0.05
                   else "indistinguishable")
        print(f"  {'SMA-' + str(w):<22} {d['sharpe']:>8.2f} {p_sh:>10.3f} "
              f"{p_dd:>10.3f}  {verdict}")

    # Paired bootstrap vs flat
    print(f"\n{'=' * 92}")
    print("# PAIRED BOOTSTRAP — Sharpe(SMA) - Sharpe(flat), 5000 draws")
    print(f"{'=' * 92}")
    rng2 = np.random.default_rng(23)
    print(f"\n  {'rule':<22} {'dSharpe':>9} {'95% CI':>20} {'p(<=0)':>8}  verdict")
    for w, (e, d, f, avg) in out.items():
        p_ = e.shift(1).fillna(0.0)
        t_ = p_.diff().abs().fillna(p_.abs())
        rr = (p_ * ew - t_ * COST / 10_000).to_numpy()
        rf = (avg * ew).to_numpy()
        point = shp(rr) - shp(rf)
        b = np.array([shp(rr[i]) - shp(rf[i])
                      for i in (block_idx(n, 20, rng2) for _ in range(5000))])
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"  {'SMA-' + str(w):<22} {point:>+9.3f} "
              f"{f'[{lo:+.2f}, {hi:+.2f}]':>20} "
              f"{float((b <= 0).mean()):>8.3f}  "
              f"{'SIGNIFICANT' if lo > 0 else 'not significant'}")

    print(f"\n{'=' * 92}")
    print("# HONEST SUMMARY")
    print("=" * 92)
    d50 = out[50][1]
    f50 = out[50][2]
    print(f"\n  SMA-50 Sharpe {d50['sharpe']:.2f} vs flat control {f50['sharpe']:.2f} "
          f"-> dSharpe {d50['sharpe'] - f50['sharpe']:+.3f}")
    print(f"  vs buy & hold Sharpe {bh['sharpe']:.2f} "
          f"-> dSharpe {d50['sharpe'] - bh['sharpe']:+.3f}")
    print(f"\n  SE(Sharpe) at {n_years:.1f}y = {1/np.sqrt(n_years):.2f}")


if __name__ == "__main__":
    main()
