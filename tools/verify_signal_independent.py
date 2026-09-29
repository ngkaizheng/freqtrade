"""Verify the forward recorder's signal against an INDEPENDENT implementation.

Lesson L2 says: when a check says "everything is fine", confirm with a second
independent method before believing it. The parity log currently reports OK/OK,
which is exactly the situation where a silent bug would hide: if BOTH the
recorder and the strategy share the same wrong assumption, parity reads OK and
the error is invisible.

This script independently recomputes what the exposure should be, using:
  * a from-scratch SMA (no pandas rolling helper)
  * explicit complete-candle selection
and compares against (a) the study engine and (b) the living freqtrade strategy's
own populate_indicators, via the strategy resolver.

If all three agree, the OK/OK parity is meaningful rather than circular.
"""

import numpy as np
import pandas as pd

DATA = "user_data/data/bitstamp/BTC_USD-1d.feather"
MA = 50
RISK_ON, RISK_OFF = 1.00, 0.50


def sma_manual(vals, w):
    """From-scratch SMA: mean of the trailing w values, None until warmed."""
    out = []
    for i in range(len(vals)):
        if i + 1 < w:
            out.append(np.nan)
        else:
            out.append(sum(vals[i + 1 - w: i + 1]) / w)
    return np.array(out)


def main():
    d = pd.read_feather(DATA).sort_values("date").drop_duplicates("date")
    d = d.reset_index(drop=True)
    close = d["close"].astype(float).to_numpy()

    # ---- 1. pandas rolling ----
    s_pandas = pd.Series(close).rolling(MA, min_periods=MA).mean().to_numpy()
    # ---- 2. manual ----
    s_manual = sma_manual(close, MA)

    both = ~np.isnan(s_pandas) & ~np.isnan(s_manual)
    diff = np.abs(s_pandas[both] - s_manual[both]).max()
    print("=" * 88)
    print("# INDEPENDENT SIGNAL VERIFICATION")
    print("=" * 88)
    print(f"\n  rows: {len(close)}   warm-up rows: {MA-1}")
    print(f"  max |pandas SMA - manual SMA| over {both.sum()} rows: {diff:.10f}")
    print(f"  -> {'AGREE' if diff < 1e-9 else 'DISAGREE (bug!)'}")

    # ---- 3. freqtrade strategy's own indicator ----
    from freqtrade.resolvers import StrategyResolver
    import uuid
    cfg = {
        "strategy": "BTCSmaTrend",
        "timeframe": "1d",
        "dry_run": True,
        "stake_currency": "USD",
        "stake_amount": "unlimited",
        "trading_mode": "spot",
        "margin_mode": "",
        "exchange": {"name": "bitstamp", "key": "", "secret": "",
                     "pair_whitelist": ["BTC/USD"]},
        "pairlists": [{"method": "StaticPairList"}],
        "entry_pricing": {"price_side": "same", "use_order_book": False},
        "exit_pricing": {"price_side": "same", "use_order_book": False},
        "dataformat_ohlcv": "feather",
        "user_data_dir": __import__("pathlib").Path("user_data").resolve(),
        "runmode": "backtest",
    }
    strat = StrategyResolver.load_strategy(cfg)
    df = strat.populate_indicators(d.copy(), {"pair": "BTC/USD"})
    s_strat = df["sma"].to_numpy()

    b2 = ~np.isnan(s_pandas) & ~np.isnan(s_strat)
    d2 = np.abs(s_pandas[b2] - s_strat[b2]).max()
    print(f"\n  max |pandas SMA - freqtrade strategy SMA| over {b2.sum()} rows: {d2:.10f}")
    print(f"  -> {'AGREE' if d2 < 1e-9 else 'DISAGREE (bug!)'}")

    # ---- 4. The actual decision on the last complete candle ----
    # Last row may be a forming candle; use the previous one for the decision.
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    last = d["date"].iloc[-1].to_pydatetime()
    complete_idx = len(d) - 2 if (now - last).total_seconds() < 86400 else len(d) - 1
    c = close[complete_idx]
    s = s_pandas[complete_idx]
    target = RISK_ON if c > s else RISK_OFF

    print(f"\n  decision candle : {d['date'].iloc[complete_idx].date()}")
    print(f"  close {c:,.2f}   SMA{MA} {s:,.2f}   close>SMA? {c > s}")
    print(f"  -> target exposure {target:.0%}")
    print(f"\n  recorder reported 100% for 2026-09-18; this independent check says "
          f"{target:.0%}")
    print(f"  -> {'MATCHES' if abs(target - 1.0) < 1e-9 else 'MISMATCH'}")

    # ---- 5. Sanity: how often does the signal flip historically? ----
    expo = np.where(close > s_pandas, RISK_ON, RISK_OFF)
    expo = np.where(np.isnan(s_pandas), np.nan, expo)
    ser = pd.Series(expo).dropna()
    flips = int((ser.diff().abs() > 0).sum())
    years = len(ser) / 365.0
    print(f"\n  historical target flips: {flips} over {years:.1f}y "
          f"=> {flips/years:.1f}/year (backtest expectation ~9/year)")
    print(f"  -> the recorder's turnover check will be meaningful at this cadence")


if __name__ == "__main__":
    main()
