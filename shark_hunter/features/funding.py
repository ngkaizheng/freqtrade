"""Funding rate features (spec section 14).

Funding is a *regime* variable here, never a primary entry signal.  The
z-score is computed from a rolling window of past observations only, shifted
by one so a bar's own funding print cannot inform its own z-score.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_funding(df: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    out = df.copy()
    if "funding_rate" not in out.columns:
        return out

    # `funding_rate` is forward-filled onto the bar grid, so consecutive bars
    # repeat the same print.  Scoring it on the bar grid would give a window
    # 90 bars long == 7.5h instead of 90 real funding prints.  Collapse back to
    # the event series first.
    events = out.loc[out["funding_event"], "funding_rate"].dropna()
    if events.empty:
        out["funding_zscore"] = np.nan
        return out

    past = events.shift(1)
    mu = past.rolling(window, min_periods=max(10, window // 3)).mean()
    sd = past.rolling(window, min_periods=max(10, window // 3)).std(ddof=0)
    z = (events - mu) / sd.replace(0.0, np.nan)

    out["funding_zscore"] = z.reindex(out.index).ffill()
    out["funding_rate"] = out["funding_rate"]
    out["funding_crowded_long"] = out["funding_zscore"] > 2.0
    out["funding_crowded_short"] = out["funding_zscore"] < -2.0

    # Annualised-ish running context, purely descriptive.
    out["funding_annualised"] = out["funding_rate"] * 3 * 365
    return out
