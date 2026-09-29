"""Reconcile turnover vs flip count — correcting a reporting error.

I previously reported the strategy's expected trade frequency as "~9/year". The
independent verification found 18.8 target flips per year.

These are two DIFFERENT quantities and I conflated them:

  turnover  = sum |exposure_t - exposure_{t-1}|  per year, in exposure units.
              Each flip moves exposure by 0.5 (1.00 <-> 0.50), so
              turnover = 0.5 x flips.

  9.2x/year turnover therefore implies 9.2 / 0.5 = 18.4 flips/year.

So ~9/year was the turnover figure mis-stated as a trade count. The correct
expectation for the forward parity check is ~18-19 rebalances per year, i.e.
roughly one every 2-3 weeks.

This script confirms the reconciliation on both the BTC series and the pool.
"""

import numpy as np
import pandas as pd

MA = 50
RISK_ON, RISK_OFF = 1.00, 0.50


def analyse(label, close, ppy=365):
    s = close.rolling(MA, min_periods=MA).mean()
    expo = pd.Series(np.where(close > s, RISK_ON, RISK_OFF), index=close.index)
    expo = expo[s.notna()]
    flips = int((expo.diff().abs() > 0).sum())
    turnover = float(expo.diff().abs().sum())
    years = len(expo) / ppy
    print(f"\n  {label}")
    print(f"    span            : {len(expo)} bars = {years:.1f}y")
    print(f"    target flips    : {flips}  -> {flips/years:.1f}/year")
    print(f"    turnover        : {turnover:.1f} exposure-units "
          f"-> {turnover/years:.2f}x/year")
    print(f"    check: turnover/0.5 = {turnover/0.5:.1f}  vs flips {flips}  "
          f"-> {'consistent' if abs(turnover/0.5 - flips) < 1 else 'INCONSISTENT'}")
    return flips / years, turnover / years


def main():
    print("=" * 88)
    print("# TURNOVER vs FLIP COUNT — reconciling the ~9/year claim")
    print("=" * 88)

    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float)
    f_btc, t_btc = analyse("BTC/USD (Bitstamp, 15.1y)", btc)

    closes = {}
    for m in ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
              "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
              "NEO", "TRX"]:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        try:
            dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        except FileNotFoundError:
            continue
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    idx = panel.ffill().mean(axis=1)
    f_pool, t_pool = analyse("20-major pool index (Binance, 7.7y)", idx)

    print(f"\n{'=' * 88}")
    print("# CORRECTED EXPECTATION FOR FORWARD VALIDATION")
    print(f"{'=' * 88}")
    print(f"""
  WRONG (what I reported earlier): "~9 trades/year"
  RIGHT:                           ~{f_btc:.0f} rebalances/year on BTC
                                   ({t_btc:.1f}x/year turnover)
                                   ~{f_pool:.0f} rebalances/year on the pool

  The error was conflating turnover (a magnitude in exposure units) with the
  number of rebalance events. They differ by a factor of 1/0.5 = 2 because each
  flip moves exposure by half the book.

  Practical implication for forward validation: expect a rebalance roughly every
  2-3 weeks, NOT every ~6 weeks. If the live bot fires far fewer than
  ~{f_btc:.0f}/year, that is a signal of a parity problem, and the old (wrong)
  benchmark of 9 would have hidden it.

  This matters because the turnover check is one of the few forward-validation
  metrics that resolves quickly. A wrong benchmark would have made a broken
  implementation look acceptable.""")


if __name__ == "__main__":
    main()
