"""POWER ANALYSIS — how long must the forward test run?

I have repeatedly quoted "detecting a +0.17 Sharpe edge needs ~271 years". That
number comes from the absolute-Sharpe formula:

    n_years ~ (2.8 / SR)^2      (80% power, 95% confidence)

But that formula is for testing an ABSOLUTE Sharpe against ZERO. The claim here is
different: the RULE beats a MATCHED FLAT control. That is a PAIRED comparison of
two return series driven by the same underlying returns, and paired comparisons
have far lower variance than absolute ones.

If so, my 271-year figure is wrong -- too pessimistic -- and I have been
overstating the power problem. I need to check this rather than keep quoting it.

Method (empirical, no distributional assumptions):
  1. Build the paired series: rule_net - flat_net (already net of costs).
  2. Measure how the standard error of its MEAN scales with sample length, by
     subsampling independent blocks of the real 15-year history.
  3. Convert to the sample length needed for 80% power to detect the observed
     effect at 95% confidence.
  4. Compare against the naive absolute-Sharpe formula.

Also reports the required length for the small "forward evaluation" question:
how long until the forward test can distinguish "rule >= flat" from "rule < flat"
at the observed effect size.
"""

import os
import numpy as np
import pandas as pd

PPY = 365
COST = 10.0
MA = 50
RISK_ON, RISK_OFF = 1.00, 0.50


def sma_expo(close, w=MA):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(RISK_OFF, index=close.index)
    out[v] = np.where(close[v] > ma[v], RISK_ON, RISK_OFF)
    return out


def paired_series(close, rets, cost=COST):
    e = sma_expo(close)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    rule = pos * rets - turn * cost / 10_000.0
    flat = pd.Series(float(e.mean()), index=rets.index) * rets
    return (rule - flat).dropna()


def sharpe(r, ppy=PPY):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def main():
    print("=" * 94)
    print("# POWER ANALYSIS — how long must the forward test actually run?")
    print("=" * 94)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    diff = paired_series(btc, r_btc)
    n = len(diff)
    yrs = n / PPY

    mean_d = float(diff.mean())
    sd_d = float(diff.std())
    se_mean = sd_d / np.sqrt(n)

    print(f"\n  paired series (rule_net - flat_net), BTC 15y:")
    print(f"    n = {n} days ({yrs:.1f}y)")
    print(f"    mean excess daily return : {mean_d:+.6f}  "
          f"({mean_d*PPY:+.2%} annualised)")
    print(f"    sd   excess daily return : {sd_d:.6f}")
    print(f"    SE of the mean           : {se_mean:.6f}")
    t_stat = mean_d / se_mean if se_mean > 0 else np.nan
    print(f"    t-stat on the mean       : {t_stat:.2f}")

    # ---------- Requirement A: is the mean excess != 0? ----------
    print(f"\n{'=' * 94}")
    print("# A. TESTING THE MEAN EXCESS RETURN != 0 (paired t-style)")
    print(f"{'=' * 94}")
    # Needed SE for 80% power at alpha=0.05: |mean| / SE >= 2.8
    need_se = abs(mean_d) / 2.8
    # SE scales as 1/sqrt(T)
    need_n = n * (se_mean / need_se) ** 2
    need_yrs = need_n / PPY
    print(f"\n    current SE {se_mean:.6f} at {yrs:.1f}y")
    print(f"    need SE {need_se:.6f} for 80% power on the observed mean")
    print(f"    -> required sample: {need_n:,.0f} days = {need_yrs:.1f} years")

    # ---------- Requirement B: the Sharpe-difference claim ----------
    print(f"\n{'=' * 94}")
    print("# B. THE CLAIM I HAVE BEEN QUOTING (absolute Sharpe vs 0)")
    print(f"{'=' * 94}")
    obs_edge = sharpe(paired_series(btc, r_btc))  # not the right stat, kept for contrast
    rule_sh = sharpe((sma_expo(btc).shift(1).fillna(0) * r_btc -
                      sma_expo(btc).shift(1).fillna(0).diff().abs().fillna(0) * COST / 1e4))
    flat_sh = sharpe(pd.Series(float(sma_expo(btc).mean()), index=r_btc.index) * r_btc)
    edge_sh = rule_sh - flat_sh
    print(f"\n    observed Sharpe(rule) {rule_sh:.3f}  Sharpe(flat) {flat_sh:.3f}  "
          f"edge {edge_sh:.3f}")
    naive = (2.8 / edge_sh) ** 2
    print(f"    naive formula (2.8/edge)^2 = {naive:.1f} years")
    print(f"    -- this is the figure I kept quoting, and it is for an ABSOLUTE")
    print(f"       Sharpe vs zero, not for the paired difference.")

    # ---------- Empirical scaling of the paired statistic ----------
    print(f"\n{'=' * 94}")
    print("# C. EMPIRICAL SCALING — subsample independent blocks")
    print(f"{'=' * 94}")
    rng = np.random.default_rng(77)
    arr = diff.to_numpy()
    print(f"\n    {'block yrs':>10} {'blocks':>8} {'mean':>12} {'sd(mean)':>12} "
          f"{'t':>8}")
    rows = []
    for block_yrs in (0.5, 1, 2, 3, 5):
        bl = int(block_yrs * PPY)
        if bl * 5 > n:
            continue
        nb = n // bl
        starts = rng.integers(0, n - bl, size=600)
        means = np.array([arr[s:s + bl].mean() for s in starts])
        sd_m = float(means.std(ddof=1))
        t = mean_d / sd_m if sd_m > 0 else np.nan
        rows.append((block_yrs, len(means), float(means.mean()), sd_m, t))
        print(f"    {block_yrs:>10.1f} {len(means):>8} {means.mean():>+12.6f} "
              f"{sd_m:>12.6f} {t:>8.2f}")

    if len(rows) >= 2:
        # fit sd(mean) ~ c / sqrt(T)
        Ts = np.array([r[0] for r in rows])
        SDs = np.array([r[3] for r in rows])
        k = np.polyfit(np.log(Ts), np.log(SDs), 1)
        print(f"\n    log-log slope = {k[0]:.3f}  (theory: -0.5)")
        print(f"    -> SE scaling {'consistent with 1/sqrt(T)' if abs(k[0] + 0.5) < 0.25 else 'NOT 1/sqrt(T)'}")

    # ---------- Conclusion ----------
    print(f"\n{'=' * 94}")
    print("# CONCLUSION")
    print(f"{'=' * 94}")
    print(f"""
    The paired comparison (rule vs matched flat) needs roughly
        {need_yrs:.1f} years   for 80% power on the OBSERVED effect,
    versus the
        {naive:.1f} years   figure I had been quoting from the absolute-Sharpe
                          formula.

    These differ because the two series are highly correlated (same underlying
    returns), so the DIFFERENCE is much less noisy than either level. My repeated
    "~271 years" claim was therefore overstated -- it answered the wrong question.

    Practical read for the forward test:
      * ~{need_yrs:.0f} years is still far beyond a normal validation window, so the
        forward test CANNOT settle the edge on any practical horizon either -- but
        the honest number is ~{need_yrs:.0f}y, not ~{naive:.0f}y.
      * The forward test's real value remains Question A (implementation fidelity),
        which resolves in weeks and needs no power argument at all.
""")


if __name__ == "__main__":
    main()
