"""Cumulative Volume Delta from Binance taker buy/sell volume (spec section 11).

delta_t = taker_buy_volume_t - taker_sell_volume_t
CVD_t   = CVD_{t-1} + delta_t

Binance defines taker buy volume as aggressive buying within the bar, so delta
is a genuine aggressive-order-flow proxy rather than an inference from OHLCV.

CVD is non-stationary by construction.  Nothing here compares the raw level
across symbols or across time; only CVD vs its own moving average and short
horizon deltas are used.
"""

from __future__ import annotations

import pandas as pd


def add_cvd(df: pd.DataFrame, lags: tuple[int, ...] = (3, 5, 10),
            sma_period: int = 20) -> pd.DataFrame:
    out = df.copy()
    delta = out["taker_buy_volume"] - out["taker_sell_volume"]
    out["cv_delta"] = delta
    out["cvd"] = delta.cumsum()
    out["cvd_sma"] = out["cvd"].rolling(sma_period, min_periods=sma_period).mean()
    out["cvd_above_sma"] = out["cvd"] > out["cvd_sma"]

    for lag in lags:
        out[f"cvd_delta_{lag}"] = out["cvd"] - out["cvd"].shift(lag)
        out[f"cvd_delta_{lag}_norm"] = out[f"cvd_delta_{lag}"] / out["volume"].rolling(
            lag, min_periods=lag).sum().replace(0.0, float("nan"))

    # Aggressive flow imbalance normalised to bar volume: in [-1, 1].
    total = (out["taker_buy_volume"] + out["taker_sell_volume"]).replace(0.0, float("nan"))
    out["taker_imbalance"] = delta / total
    return out
