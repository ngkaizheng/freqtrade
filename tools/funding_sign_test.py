"""Sign test: is funding CONTRARIAN or MOMENTUM?

funding_signal_study.py tested the contrarian direction (crowded long -> de-risk)
and it failed: negative dSharpe vs the flat control, only 6/20 pairs better than
buy & hold.

That is a useful signal in itself. Funding may work the OTHER way: high funding
means the market is in a strong leveraged uptrend, and trend-following says keep
holding. That is a MOMENTUM reading, not a contrarian one.

This script tests both directions explicitly, and is honest about the fact that
testing both doubles the multiple-comparison burden.
"""

import numpy as np
import pandas as pd

from volume_signal_study import (
    MAJORS, PPY, block_idx, load_panel, run, shp, stats, wildcard,
)
from volume_vs_speed import sma_exposure
from funding_signal_study import load_funding, to_daily_index

COST = 10.0


def signals_both_directions(fund: pd.DataFrame) -> dict:
    """Return {name: exposure} for contrarian AND momentum readings."""
    pooled = fund.mean(axis=1, skipna=True).rolling(3, min_periods=1).mean()
    out = {}

    # --- Level, both signs ---
    # contrarian: high funding -> low exposure
    out["level: contrarian"] = (1.0 - pooled / 0.001).clip(0.0, 1.0)
    # momentum: high funding -> high exposure
    out["level: momentum"] = (pooled / 0.001).clip(0.0, 1.0)

    # --- Percentile, both signs ---
    rank = pooled.rolling(90, min_periods=90).rank(pct=True)
    out["pct90: contrarian"] = (1.0 - rank).clip(0.0, 1.0)
    out["pct90: momentum"] = rank.clip(0.0, 1.0)

    # --- Trend of funding, both signs ---
    fast = pooled.rolling(7, min_periods=7).mean()
    slow = pooled.rolling(30, min_periods=30).mean()
    valid = fast.notna() & slow.notna()
    rising = pd.Series(np.nan, index=fund.index)
    rising[valid] = (fast[valid] > slow[valid]).astype(float)
    out["trend: momentum (funding rising -> hold)"] = rising
    out["trend: contrarian (funding rising -> cut)"] = 1.0 - rising

    # --- Extreme, both signs ---
    hi = pooled.rolling(90, min_periods=90).quantile(0.9)
    lo = pooled.rolling(90, min_periods=90).quantile(0.1)
    v = hi.notna() & lo.notna()
    con = pd.Series(1.0, index=fund.index)
    con[v & (pooled > hi)] = 0.25
    con[v & (pooled < lo)] = 1.0
    con[~v] = 0.5
    out["extreme: contrarian"] = con
    mom = pd.Series(1.0, index=fund.index)
    mom[v & (pooled > hi)] = 1.0
    mom[v & (pooled < lo)] = 0.25
    mom[~v] = 0.5
    out["extreme: momentum"] = mom

    return out


def main() -> None:
    close, volume = load_panel(MAJORS)
    fund_raw = load_funding(MAJORS)
    fund = to_daily_index(fund_raw, close.index)

    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)

    start = "2020-01-01"
    ew, close, volume, fund = (x.loc[start:] for x in (ew, close, volume, fund))
    n = len(ew)
    n_years = n / PPY

    print("=" * 96)
    print("# SIGN TEST — is funding contrarian or momentum?")
    print("=" * 96)
    print(f"window {ew.index[0].date()} -> {ew.index[-1].date()} ({n_years:.1f}y), "
          f"{COST:.0f}bps, coverage {float(fund.notna().mean().mean()):.0%}")
    print(f"SE(Sharpe) ~ {1/np.sqrt(n_years):.2f}\n")

    bh = stats(run(ew, pd.Series(1.0, index=ew.index), 0.0))
    print(f"buy & hold: CAGR {bh['cagr']:.2%}  MaxDD {bh['maxdd']:.2%}  "
          f"Sharpe {bh['sharpe']:.2f}")

    sigs = signals_both_directions(fund)

    print(f"\n{'=' * 96}")
    print("# ALL DIRECTIONS vs FLAT CONTROL (flat = constant at same avg exposure)")
    print(f"{'=' * 96}")
    print(f"\n  {'signal':<42} {'avgExp':>7} {'CAGR':>9} {'Sharpe':>8} {'vs flat':>9}")
    stored = {}
    for name, e in sigs.items():
        e = e.reindex(ew.index).ffill().fillna(0.5)
        if e.nunique() <= 1:
            continue
        avg = float(e.mean())
        d = stats(run(ew, e, COST))
        fl = stats(run(ew, pd.Series(avg, index=ew.index), COST))
        stored[name] = (e, d, fl, avg)
        print(f"  {name:<42} {avg:>6.1%} {d['cagr']:>9.2%} {d['sharpe']:>8.2f} "
              f"{d['sharpe'] - fl['sharpe']:>+9.3f}")

    # Which direction wins overall?
    print(f"\n{'=' * 96}")
    print("# DIRECTION SUMMARY")
    print(f"{'=' * 96}")
    con = [(k, v) for k, v in stored.items() if "contrarian" in k]
    mom = [(k, v) for k, v in stored.items() if "momentum" in k]
    for label, grp in (("CONTRARIAN", con), ("MOMENTUM", mom)):
        if not grp:
            continue
        ds = [v[1]["sharpe"] - v[2]["sharpe"] for _, v in grp]
        print(f"\n  {label}: mean dSharpe vs flat {np.mean(ds):+.3f}  "
              f"(best {max(ds):+.3f}, worst {min(ds):+.3f})")
    print(f"\n  -> {'MOMENTUM' if np.mean([v[1]['sharpe']-v[2]['sharpe'] for _,v in mom]) > np.mean([v[1]['sharpe']-v[2]['sharpe'] for _,v in con]) else 'CONTRARIAN'}"
          f" direction is the better reading")

    # Placebo + bootstrap on the BEST signal overall
    best = max(stored.items(), key=lambda kv: kv[1][1]["sharpe"])[0]
    e, d, fl, avg = stored[best]
    print(f"\n{'=' * 96}")
    print(f"# FULL GATES on the best signal: '{best}'")
    print("#   8 signals tested -> Bonferroni p < 0.00625")
    print(f"{'=' * 96}")
    print(f"\n  Sharpe {d['sharpe']:.2f}  (buy & hold {bh['sharpe']:.2f}, "
          f"flat {fl['sharpe']:.2f})")

    rng = np.random.default_rng(53)
    sh = [stats(run(ew, wildcard(avg, n, ew.index, 30, rng), COST))["sharpe"]
          for _ in range(200)]
    p_sh = float((np.array(sh) >= d["sharpe"]).mean())
    print(f"  placebo p(Sharpe) = {p_sh:.3f}  "
          f"({'PASSES Bonferroni' if p_sh < 0.00625 else 'weak' if p_sh < 0.05 else 'indistinguishable'})")

    rng2 = np.random.default_rng(59)
    p_ = e.shift(1).fillna(0.0)
    t_ = p_.diff().abs().fillna(p_.abs())
    rr = (p_ * ew - t_ * COST / 10_000).to_numpy()
    rf = (avg * ew).to_numpy()
    point = shp(rr) - shp(rf)
    b = np.array([shp(rr[i]) - shp(rf[i])
                  for i in (block_idx(n, 20, rng2) for _ in range(5000))])
    lo, hi = np.percentile(b, [2.5, 97.5])
    print(f"  bootstrap dSharpe {point:+.3f}  CI [{lo:+.2f}, {hi:+.2f}]  "
          f"({'SIGNIFICANT' if lo > 0 else 'not significant'})")

    # Negative controls: random funding (should fail)
    print(f"\n{'=' * 96}")
    print("# NEGATIVE CONTROL — shuffle the funding series (destroys information)")
    print(f"{'=' * 96}")
    rng3 = np.random.default_rng(61)
    null_sh = []
    for _ in range(100):
        shuf = fund.copy()
        for c in shuf.columns:
            vals = np.array(shuf[c].to_numpy(), dtype=float, copy=True)
            rng3.shuffle(vals)
            shuf[c] = vals
        s2 = signals_both_directions(shuf).get(best)
        if s2 is None:
            continue
        s2 = s2.reindex(ew.index).ffill().fillna(0.5)
        null_sh.append(stats(run(ew, s2, COST))["sharpe"])
    null_sh = np.array(null_sh)
    print(f"\n  real Sharpe      : {d['sharpe']:.2f}")
    print(f"  shuffled funding : mean {null_sh.mean():.2f}, "
          f"p95 {np.percentile(null_sh, 95):.2f}")
    print(f"  p(shuffled >= real): {float((null_sh >= d['sharpe']).mean()):.3f}")
    print("  (If shuffled does as well, the apparent edge is not from funding.)")

    # Incremental vs SMA-50
    print(f"\n{'=' * 96}")
    print("# INCREMENTAL OVER SMA-50 (the handoff's real demand)")
    print(f"{'=' * 96}")
    sma50 = sma_exposure(close, 50).reindex(ew.index).fillna(0.5)
    target = float(sma50.mean())
    e_sc = (e * (target / max(float(e.mean()), 1e-9))).clip(0.0, 1.0)
    combo = pd.concat([sma50, e_sc], axis=1).min(axis=1)
    print(f"\n  {'rule':<34} {'avgExp':>7} {'CAGR':>9} {'MaxDD':>9} {'Sharpe':>8}")
    for label, ee in (("SMA-50 alone", sma50),
                      (f"{best} (rescaled)", e_sc),
                      ("min(SMA-50, funding)", combo)):
        m = stats(run(ew, ee, COST))
        print(f"  {label:<34} {float(ee.mean()):>6.1%} {m['cagr']:>9.2%} "
              f"{m['maxdd']:>9.2%} {m['sharpe']:>8.2f}")
    mask_on = sma50 >= 1.0
    if mask_on.sum() > 100:
        sub = ew[mask_on]
        a = stats(run(sub, pd.Series(1.0, index=sub.index), COST))
        b2 = stats(run(sub, e_sc[mask_on], COST))
        print(f"\n  Within SMA-50 risk-ON days (n={int(mask_on.sum())}):")
        print(f"    always 1.0     : Sharpe {a['sharpe']:.2f}")
        print(f"    funding-scaled : Sharpe {b2['sharpe']:.2f}")
        print(f"    -> funding {'ADDS' if b2['sharpe'] > a['sharpe'] else 'adds NOTHING'}")


if __name__ == "__main__":
    main()
