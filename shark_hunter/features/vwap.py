"""UTC-day anchored VWAP, computed causally (spec section 9)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Running VWAP that resets at 00:00 UTC.

    ``vwap`` at bar ``t`` is sum(typical_price * volume) / sum(volume) over the
    bars of ``t``'s UTC day up to and including ``t``.  The completed daily
    total is never used, so there is no lookahead (spec section 35).
    """
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex) or out.index.tz is None:
        raise ValueError("add_vwap requires a tz-aware DatetimeIndex")

    tp = (out["high"] + out["low"] + out["close"]) / 3.0
    vol = out["volume"].clip(lower=0.0)
    day = out.index.floor("D")

    pv = (tp * vol).groupby(day).cumsum()
    cv = vol.groupby(day).cumsum()
    out["vwap"] = pv / cv.replace(0.0, np.nan)

    # Distance from VWAP in relative terms; used for reporting and the
    # SHARK-08 regime filter, never as a hidden normaliser.
    out["vwap_distance"] = out["close"] / out["vwap"] - 1.0
    out["above_vwap"] = out["close"] > out["vwap"]
    return out
