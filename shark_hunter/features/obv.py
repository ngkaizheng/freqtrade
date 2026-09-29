"""On-Balance Volume (spec section 10).

OBV is a volume-price proxy.  It is not institutional accumulation and is
never described as such in the report.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_obv(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    vol = out["volume"].clip(lower=0.0)

    direction = np.sign(close.diff().fillna(0.0))
    out["obv"] = (direction * vol).cumsum()
    out["obv_sma"] = out["obv"].rolling(period, min_periods=period).mean()
    out["obv_above_sma"] = out["obv"] > out["obv_sma"]
    out["obv_high"] = out["obv"].rolling(period, min_periods=period).max().shift(1)
    out["obv_breakout"] = out["obv"] > out["obv_high"]
    return out
