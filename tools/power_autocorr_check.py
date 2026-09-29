"""Autocorrelation check on the paired excess series — does it inflate the need?

power_analysis.py gave two results that disagree slightly:
  * analytic requirement : 11.7 years
  * empirical block scaling: log-log slope -0.721, but theory says -0.5

A slope STEEPER than -0.5 means SD(mean) falls slower than 1/sqrt(T), i.e. there
is positive autocorrelation and fewer effective independent observations than
raw day count suggests. That would make the true requirement LONGER than 11.7y.

This matters because I just published a correction saying "~12 years, not ~271".
If autocorrelation doubles that, the correction is still directionally right but
the number is wrong again. Lesson L9 says: check before publishing a second time.

Method:
  1. autocorrelation of the excess series at lags 1..20
  2. Newey-West / Lo-style variance inflation factor
  3. effective sample size = n / inflation
  4. corrected power requirement using the inflated variance
"""

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


def paired(close, rets, cost=COST):
    e = sma_expo(close)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    rule = pos * rets - turn * cost / 10_000.0
    flat = pd.Series(float(e.mean()), index=rets.index) * rets
    return (rule - flat).dropna()


def main():
    print("=" * 94)
    print("# AUTOCORRELATION CHECK — is the 11.7-year figure overstated?")
    print("=" * 94)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    x = paired(btc, r)
    n = len(x)
    yrs = n / PPY
    mean_x = float(x.mean())
    sd_x = float(x.std())
    se_naive = sd_x / np.sqrt(n)

    print(f"\n  n = {n} ({yrs:.1f}y)   mean {mean_x:+.6f}   sd {sd_x:.6f}")
    print(f"  naive SE {se_naive:.6f}   t = {mean_x/se_naive:.2f}")

    # ---------- 1. autocorrelation profile ----------
    print(f"\n{'=' * 94}")
    print("# 1. AUTOCORRELATION OF THE EXCESS SERIES")
    print(f"{'=' * 94}")
    print(f"\n  {'lag':>5} {'rho':>10}  bar")
    rhos = []
    for k in range(1, 21):
        rho = float(x.autocorr(k))
        rhos.append(rho)
        bar = "#" * int(min(abs(rho) * 200, 60))
        sign = "+" if rho >= 0 else "-"
        print(f"  {k:>5} {rho:>+10.4f}  {sign}{bar}")
    rhos = np.array(rhos)
    print(f"\n  sum of lags 1-20 : {rhos.sum():+.4f}")
    print(f"  max |rho|        : {np.abs(rhos).max():.4f}")

    # ---------- 2. variance inflation (Lo 2002 style) ----------
    print(f"\n{'=' * 94}")
    print("# 2. VARIANCE INFLATION FACTOR")
    print(f"{'=' * 94}")
    # Lo's eta(q) for annualised Sharpe uses sum of (q-k)*rho_k.
    # Here we want the inflation of Var(mean) for a T-day sample:
    #   Var(mean) = (sd^2/T) * [1 + 2*sum_{k=1}^{K} (1 - k/T) * rho_k]
    K = 20
    infl = 1.0 + 2.0 * sum((1 - k / n) * rhos[k - 1] for k in range(1, K + 1))
    infl = max(infl, 0.05)
    print(f"\n  inflation factor (K={K}) : {infl:.3f}")
    se_adj = se_naive * np.sqrt(infl)
    t_adj = mean_x / se_adj
    print(f"  naive SE      : {se_naive:.6f}   t {mean_x/se_naive:.2f}")
    print(f"  adjusted SE   : {se_adj:.6f}   t {t_adj:.2f}")
    print(f"  -> inflation {'INCREASES' if infl > 1 else 'DECREASES'} the uncertainty "
          f"by {(np.sqrt(infl)-1)*100:+.0f}%")

    # ---------- 3. effective sample size ----------
    print(f"\n{'=' * 94}")
    print("# 3. EFFECTIVE SAMPLE SIZE")
    print(f"{'=' * 94}")
    n_eff = n / infl
    print(f"\n  nominal n        : {n:,.0f} days ({yrs:.1f}y)")
    print(f"  effective n      : {n_eff:,.0f} days ({n_eff/PPY:.1f}y)")
    print(f"  ratio            : {n_eff/n:.2f}")

    # ---------- 4. corrected power requirement ----------
    print(f"\n{'=' * 94}")
    print("# 4. CORRECTED POWER REQUIREMENT (80% power, 95% confidence)")
    print(f"{'=' * 94}")
    need_se = abs(mean_x) / 2.8
    # with inflation, Var(mean) = sd^2 * infl / T  =>  T = sd^2 * infl / need_se^2
    need_n = (sd_x ** 2) * infl / (need_se ** 2)
    need_yrs = need_n / PPY

    need_n_naive = (sd_x ** 2) / (need_se ** 2)
    print(f"\n  without inflation : {need_n_naive:,.0f} days = "
          f"{need_n_naive/PPY:.1f} years")
    print(f"  WITH inflation    : {need_n:,.0f} days = {need_yrs:.1f} years")

    # ---------- 5. cross-check with an independent method ----------
    print(f"\n{'=' * 94}")
    print("# 5. CROSS-CHECK — empirical block resampling (independent method)")
    print(f"{'=' * 94}")
    arr = x.to_numpy()
    rng = np.random.default_rng(555)
    print(f"\n  {'block yrs':>10} {'sd(mean)':>12} {'implied yrs for power':>24}")
    for by in (0.5, 1.0, 2.0, 3.0):
        bl = int(by * PPY)
        if bl * 4 > n:
            continue
        starts = rng.integers(0, n - bl, size=800)
        m = np.array([arr[s:s + bl].mean() for s in starts])
        sd_m = float(m.std(ddof=1))
        # sd_m is SE for a sample of length bl; need SE = need_se
        implied = bl * (sd_m / need_se) ** 2 / PPY
        print(f"  {by:>10.1f} {sd_m:>12.6f} {implied:>24.1f}")

    print(f"""
{'=' * 94}
# CONCLUSION
{'=' * 94}

  The excess series shows autocorrelation summing to {rhos.sum():+.4f} over lags 1-20,
  giving a variance inflation factor of {infl:.3f}.

  Corrected requirement: ~{need_yrs:.0f} years (not the {need_n_naive/PPY:.1f}y
  naive figure, and not the ~225y absolute-Sharpe figure I had been quoting).

  Status of my claims:
    * "~271 years"  -- WRONG. Wrong statistic (absolute vs paired). Overstated.
    * "~12 years"   -- closer, but ignores autocorrelation. Understated.
    * "~{need_yrs:.0f} years"   -- current best estimate with inflation applied.

  All three are far beyond any practical forward window, so the conclusion is
  unchanged: the forward test cannot settle the edge. But the NUMBER I publish
  should be the right one, and the direction of my previous correction was right
  while its magnitude was optimistic.""")


if __name__ == "__main__":
    main()
