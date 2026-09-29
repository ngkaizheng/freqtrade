"""Critical check: is the cross-asset result 16 independent wins, or ~1 repeated?

sma_cross_asset_wf.py found 16/20 assets beat buy & hold out-of-sample, sign test
p=0.0059. But these are all crypto majors — they are HIGHLY correlated (often
0.7-0.9). A sign test assumes independent trials. If the assets all move
together, "16/20" carries far less information than it appears: it may reflect
one market regime, counted 20 times.

This script measures the effective number of independent assets and re-tests
significance with a block bootstrap that preserves cross-asset correlation.
"""

import numpy as np
import pandas as pd

from volume_signal_study import MAJORS, PPY, load_panel, run, stats
from volume_vs_speed import sma_exposure
from sma_cross_asset_wf import walk_forward_oos

COST = 10.0


def main() -> None:
    close, volume = load_panel(MAJORS)
    rets = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    start = "2019-01-01"
    close, rets = close.loc[start:], rets.loc[start:]

    print("=" * 96)
    print("# IS '16/20' REALLY 16 INDEPENDENT WINS?")
    print("=" * 96)

    # ---- Cross-asset correlation ----
    corr = rets.corr()
    off = corr.where(~np.eye(len(corr), dtype=bool))
    mean_corr = float(off.stack().mean())
    print(f"\n  mean pairwise return correlation: {mean_corr:.3f}")
    print(f"  median: {float(off.stack().median()):.3f}   "
          f"max: {float(off.stack().max()):.3f}")

    # Effective number of independent assets (eigenvalue / participation ratio)
    c = corr.fillna(0).to_numpy()
    ev = np.linalg.eigvalsh(c)
    ev = ev[ev > 0]
    n_eff_pr = float((ev.sum() ** 2) / (ev ** 2).sum())      # participation ratio
    n_eff_kaiser = float((ev > 1.0).sum())                    # Kaiser criterion
    print(f"\n  nominal assets                    : {len(corr)}")
    print(f"  effective N (participation ratio) : {n_eff_pr:.1f}")
    print(f"  effective N (eigenvalues > 1)     : {n_eff_kaiser:.1f}")
    print(f"  -> 20 assets behave like roughly {n_eff_pr:.0f} independent bets")

    # ---- Re-run the per-asset walk-forward ----
    rows = []
    for p in close.columns:
        res = walk_forward_oos(close, rets, p)
        if res:
            rows.append(res)
    deltas = np.array([r["rule"] - r["bh"] for r in rows])
    wins = int((deltas > 0).sum())
    n = len(deltas)
    mean_d = float(deltas.mean())

    print(f"\n  observed: {wins}/{n} assets better, mean dSharpe {mean_d:+.3f}")

    # ---- Naive sign test (assumes independence) ----
    from math import comb
    p_naive = sum(comb(n, k) for k in range(wins, n + 1)) / (2 ** n)
    print(f"\n  naive sign test (assumes independence): p = {p_naive:.4f}")

    # ---- Correlation-aware test ----
    # Build a null in which all assets share ONE common driver, so they are as
    # correlated as the real data, and the rule has no skill.
    print(f"\n{'=' * 96}")
    print("# CORRELATION-AWARE NULL — one common factor, zero skill")
    print(f"{'=' * 96}")
    rng = np.random.default_rng(83)

    # Use the real correlation structure via its Cholesky factor, then replace
    # the per-asset return series with factor-driven noise.
    L = np.linalg.cholesky(c + np.eye(len(c)) * 1e-8)
    n_obs = len(rets)
    n_assets = len(c)

    null_means = []
    null_wins = []
    for _ in range(400):
        z = rng.standard_normal((n_obs, n_assets))
        sim = z @ L.T
        # Scale to roughly match the real return volatility.
        sim = sim * rets.std().to_numpy()
        sim_df = pd.DataFrame(sim, index=rets.index, columns=rets.columns)
        # Rule applied to the SIMULATED prices (index of cumulated returns).
        sim_close = 100 * (1 + sim_df).cumprod()
        d = []
        for p in sim_df.columns:
            r = sim_df[p].fillna(0.0)
            c1 = sim_close[[p]]
            # Fixed SMA-50 (no per-asset tuning) to isolate the effect.
            e = sma_exposure(c1, 50).reindex(r.index).fillna(0.5)
            sr_r = stats(run(r, e, COST))["sharpe"]
            sr_b = stats(run(r, pd.Series(1.0, index=r.index), 0.0))["sharpe"]
            d.append(sr_r - sr_b)
        d = np.array(d)
        null_means.append(d.mean())
        null_wins.append(int((d > 0).sum()))

    null_means = np.array(null_means)
    null_wins = np.array(null_wins)
    p_mean = float((null_means >= mean_d).mean())
    p_wins = float((null_wins >= wins).mean())

    print(f"\n  {'statistic':<34} {'observed':>10} {'null mean':>11} {'null p95':>10} "
          f"{'p-value':>9}")
    print(f"  {'mean dSharpe across assets':<34} {mean_d:>+10.3f} "
          f"{null_means.mean():>+11.3f} {np.percentile(null_means, 95):>+10.3f} "
          f"{p_mean:>9.3f}")
    print(f"  {'assets better than buy & hold':<34} {wins:>10} "
          f"{null_wins.mean():>11.1f} {np.percentile(null_wins, 95):>10.1f} "
          f"{p_wins:>9.3f}")

    # ---- Deflated Sharpe, accounting for the real trial count ----
    print(f"\n{'=' * 96}")
    print("# DEFLATED VIEW — the trial ledger")
    print(f"{'=' * 96}")
    trials = {
        "MA200 exposure": 3, "momentum variants": 5, "momentum grid": 24,
        "drawdown rules": 5, "volume families": 5, "VWMA grid": 8,
        "funding families": 4, "funding sign test": 8,
        "SMA window grid": 8, "cross-asset WF": 20,
    }
    total = sum(trials.values())
    print()
    for k, v in trials.items():
        print(f"  {k:<28} {v:>4}")
    print(f"  {'TOTAL':<28} {total:>4}")
    n_years = len(rets) / PPY
    minbtl = 2 * np.log(total) / (0.84 ** 2)
    print(f"\n  MinBTL for N={total}, target SR=0.84: ~{minbtl:.1f} years")
    print(f"  available data                    : {n_years:.1f} years")
    print(f"  -> {'OK' if n_years > minbtl else 'SAMPLE TOO SHORT for this many trials'}")

    # ---- Verdict ----
    print(f"\n{'=' * 96}")
    print("# VERDICT")
    print("=" * 96)
    print(f"\n  Naive sign test p          : {p_naive:.4f}  (assumes independence)")
    print(f"  Correlation-aware p (mean) : {p_mean:.3f}")
    print(f"  Correlation-aware p (wins) : {p_wins:.3f}")
    print(f"\n  Effective independent bets : ~{n_eff_pr:.0f} (not 20)")
    if p_mean < 0.05:
        print("\n  => The effect SURVIVES the correlation-aware null.")
    else:
        print("\n  => The effect does NOT survive the correlation-aware null.")
        print("     '16/20' was largely ONE market regime counted many times.")


if __name__ == "__main__":
    main()
