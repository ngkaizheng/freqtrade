"""Per-asset walk-forward for SMA-N — the strongest test available on this data.

Status of the one surviving candidate
-------------------------------------
SMA-50 on the equal-weight majors portfolio:
  in-sample Sharpe 1.07 vs 0.84 buy & hold, placebo p=0.005,
  paired bootstrap CI [+0.02, +0.48]  <- only CI in the project excluding zero
BUT the two out-of-sample methods disagreed:
  walk-forward (stitched OOS) 0.94 vs 0.75  -> passed
  anchored split              0.53 vs 0.57  -> failed

A single portfolio-level OOS test has almost no power (6.7 years, SE ~0.39).
Cross-sectional replication is far stronger: run the SAME walk-forward protocol
independently on each of 20 assets and count how often the frozen rule beats
buy & hold out-of-sample. If the edge is real it should appear across assets.

This is the handoff's "跨市场/跨资产复制 —— 最强的防过拟合证据之一".
"""

import numpy as np
import pandas as pd

from volume_signal_study import MAJORS, PPY, load_panel, run, stats
from volume_vs_speed import sma_exposure

COST = 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]


def walk_forward_oos(close: pd.DataFrame, rets: pd.DataFrame, pair: str,
                     n_folds: int = 6) -> dict:
    """Run anchored walk-forward for one asset. Returns stitched OOS metrics."""
    r = rets[pair].fillna(0.0)
    c = close[[pair]]
    n = len(r)
    fold = n // (n_folds + 1)

    oos_rule, oos_bh = [], []
    chosen = []
    for k in range(n_folds):
        tr_end = fold * (k + 1)
        te_end = min(tr_end + fold, n)
        if te_end - tr_end < 20:
            continue
        tr_mask = np.zeros(n, dtype=bool)
        tr_mask[:tr_end] = True

        # Choose the window using ONLY training data.
        best_w, best_sr = None, -np.inf
        for w in WINDOWS:
            e = sma_exposure(c, w).reindex(r.index).fillna(0.5)
            sr = stats(run(r[tr_mask], e[tr_mask], COST))["sharpe"]
            if sr > best_sr:
                best_w, best_sr = w, sr
        best_w = best_w or 50
        chosen.append(best_w)

        e = sma_exposure(c, best_w).reindex(r.index).fillna(0.5)
        te_slice = slice(tr_end, te_end)
        seg = run(r[te_slice], e[te_slice], COST)
        oos_rule.append(seg.pct_change().dropna())
        oos_bh.append(r[te_slice])

    if not oos_rule:
        return {}
    rr = pd.concat(oos_rule)
    rb = pd.concat(oos_bh)
    sr_rule = float(rr.mean() / rr.std() * np.sqrt(PPY)) if rr.std() > 0 else 0.0
    sr_bh = float(rb.mean() / rb.std() * np.sqrt(PPY)) if rb.std() > 0 else 0.0
    return {"pair": pair, "rule": sr_rule, "bh": sr_bh,
            "chosen": chosen, "n": len(rr)}


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    start = "2019-01-01"
    close, rets = close.loc[start:], rets.loc[start:]

    print("=" * 96)
    print("# PER-ASSET WALK-FORWARD — the strongest anti-overfit test available")
    print("=" * 96)
    print(f"window {close.index[0].date()} -> {close.index[-1].date()} "
          f"({len(close)/PPY:.1f}y), {COST:.0f}bps")
    print("Protocol: pick the SMA window in-sample, freeze it, trade it "
          "out-of-sample, roll forward.\n")

    rows = []
    for p in close.columns:
        res = walk_forward_oos(close, rets, p)
        if res:
            rows.append(res)

    print(f"  {'pair':<12} {'OOS rule':>9} {'OOS BH':>8} {'delta':>8}  {'windows chosen':<24}")
    wins = 0
    for r in rows:
        better = r["rule"] > r["bh"]
        wins += better
        ch = ",".join(str(w) for w in r["chosen"])
        print(f"  {r['pair']:<12} {r['rule']:>9.2f} {r['bh']:>8.2f} "
              f"{r['rule'] - r['bh']:>+8.2f}  {ch:<24}")

    deltas = np.array([r["rule"] - r["bh"] for r in rows])
    print(f"\n  beats buy & hold out-of-sample: {wins}/{len(rows)} assets")
    print(f"  mean dSharpe {deltas.mean():+.3f}   median {np.median(deltas):+.3f}   "
          f"std {deltas.std():.3f}")

    # Sign test: is the win rate better than a coin flip?
    from math import comb
    n = len(rows)
    p_one_sided = sum(comb(n, k) for k in range(wins, n + 1)) / (2 ** n)
    print(f"\n  sign test: {wins}/{n} wins -> p = {p_one_sided:.4f} "
          f"({'SIGNIFICANT' if p_one_sided < 0.05 else 'not significant'})")

    # Bootstrap CI on the mean delta across assets
    rng = np.random.default_rng(71)
    boot = np.array([deltas[rng.integers(0, n, n)].mean() for _ in range(10000)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"  bootstrap 95% CI on mean dSharpe across assets: "
          f"[{lo:+.3f}, {hi:+.3f}]")
    print(f"  -> {'edge replicates across assets' if lo > 0 else 'does NOT replicate (CI includes 0)'}")

    # How stable is the chosen window?
    all_chosen = [w for r in rows for w in r["chosen"]]
    print(f"\n  chosen windows: {pd.Series(all_chosen).value_counts().sort_index().to_dict()}")
    print("  (A stable edge should pick similar windows across assets;")
    print("   wild variation means the in-sample choice is noise.)")

    # Regime analysis on the portfolio rule
    print(f"\n{'=' * 96}")
    print("# REGIME DEPENDENCE — portfolio SMA-50 vs buy & hold by year")
    print(f"{'=' * 96}")
    ew = rets.mean(axis=1, skipna=True).fillna(0.0)
    sma50 = sma_exposure(close, 50).reindex(ew.index).fillna(0.5)
    eq_r = run(ew, sma50, COST)
    eq_b = run(ew, pd.Series(1.0, index=ew.index), 0.0)
    print(f"\n  {'year':<8} {'BH Sharpe':>10} {'rule Sharpe':>12} {'BH CAGR':>10} "
          f"{'rule CAGR':>11}  better?")
    yw = 0
    yt = 0
    for y in range(2019, 2027):
        m = eq_r.index.year == y
        if m.sum() < 60:
            continue
        sr_b = stats(eq_b[m])["sharpe"]
        sr_r = stats(eq_r[m])["sharpe"]
        yt += 1
        yw += sr_r > sr_b
        print(f"  {y:<8} {sr_b:>10.2f} {sr_r:>12.2f} "
              f"{stats(eq_b[m])['cagr']:>10.2%} {stats(eq_r[m])['cagr']:>11.2%}  "
              f"{'YES' if sr_r > sr_b else 'no'}")
    print(f"\n  rule better in {yw}/{yt} years")

    # Final verdict
    print(f"\n{'=' * 96}")
    print("# VERDICT ON SMA-N")
    print(f"{'=' * 96}")
    checks = [
        ("replicates across assets (>13/20, p<0.05)", p_one_sided < 0.05),
        ("mean dSharpe CI excludes zero", lo > 0),
        ("consistent across years (>=5/8)", yw >= 5),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\n  {sum(ok for _, ok in checks)}/{len(checks)} passed")


if __name__ == "__main__":
    main()
