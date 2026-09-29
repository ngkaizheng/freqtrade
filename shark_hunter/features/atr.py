"""Average True Range (Wilder).  Drives the stop distance in spec section 25."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["true_range"] = tr
    # Wilder smoothing == exponential with alpha = 1 / period.
    out["atr"] = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    out["atr_pct"] = out["atr"] / out["close"]
    out["atr_percentile"] = out["atr_pct"].rolling(500, min_periods=100).rank(pct=True)
    return out
