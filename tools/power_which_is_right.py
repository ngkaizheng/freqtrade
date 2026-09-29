"""Which power estimate is trustworthy? Test the autocorrelation estimates directly.

The two methods disagree in DIRECTION:
  * analytic (autocorrelation sum +0.2783) -> inflation 1.556 -> ~18 years
  * empirical non-overlapping blocks        -> deflation 0.65-0.71x -> ~5 years

One of them is noise. The decisive question: are the individual autocorrelation
estimates statistically distinguishable from zero?

SE(rho_k) ~ 1/sqrt(n) = 1/sqrt(5312) ~ 0.0137.

If the individual rhos are mostly within ~2 SE of zero, then summing 20 noisy
values compounds noise and the "inflation" is an artifact. If they are
consistently positive and significant, the inflation is real and the blocks are
the unreliable one.

This is the check I should have run BEFORE publishing either number.
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
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x = paired(btc, r)
    n = len(x)

    print("=" * 92)
    print("# WHICH POWER ESTIMATE IS TRUSTWORTHY?")
    print("=" * 92)
    print(f"\n  n = {n}   SE(rho) ~ 1/sqrt(n) = {1/np.sqrt(n):.4f}")

    print(f"\n  {'lag':>5} {'rho':>10} {'t=rho/SE':>10}  significant?")
    rhos, tstats = [], []
    se = 1.0 / np.sqrt(n)
    for k in range(1, 21):
        rho = float(x.autocorr(k))
        t = rho / se
        rhos.append(rho)
        tstats.append(t)
        sig = "|t|>2 YES" if abs(t) > 2 else "no"
        print(f"  {k:>5} {rho:>+10.4f} {t:>+10.2f}  {sig}")

    rhos = np.array(rhos)
    tstats = np.array(tstats)
    n_sig = int((np.abs(tstats) > 2).sum())
    print(f"\n  lag-1..20: {n_sig}/20 individually significant at |t|>2")
    print(f"  sum of rhos      : {rhos.sum():+.4f}")
    print(f"  SE of the sum    : {se*np.sqrt(20):.4f}  "
          f"(if lags roughly independent)")
    print(f"  t of the sum     : {rhos.sum()/(se*np.sqrt(20)):.2f}")

    # Ljung-Box style joint test
    Q = n * (n + 2) * sum(r ** 2 / (n - k) for k, r in enumerate(rhos, 1))
    print(f"\n  Ljung-Box Q(20)  : {Q:.1f}   (chi2 critical @5% ~31.4)")
    print(f"  -> {'autocorrelation IS present' if Q > 31.4 else 'NO significant autocorrelation'}")

    print(f"""
{'=' * 92}
# VERDICT ON THE DISAGREEMENT
{'=' * 92}

  Ljung-Box says: {'significant' if Q > 31.4 else 'NOT significant'} at the 5% level.
  Individually significant lags: {n_sig}/20.""")

    if Q > 31.4:
        print(f"""
  Autocorrelation is present, so the analytic inflation is the better-supported
  estimate and the non-overlapping block figure (~5y) understates the need.
  Best estimate: ~18 years.""")
    else:
        print(f"""
  No significant autocorrelation, so the inflation factor is an artifact of
  summing noisy lag estimates, and the naive paired figure is the better one.
  Best estimate: ~12 years.""")

    print(f"""
  EITHER WAY THE DECISION IS UNCHANGED: 5, 12, or 18 years are all far beyond a
  usable forward window. The forward test still cannot settle the edge.

  I am recording the range rather than a single number, and noting that I spent
  real effort on a quantity that changes no decision -- which is its own lesson
  about diminishing returns.""")


if __name__ == "__main__":
    main()
