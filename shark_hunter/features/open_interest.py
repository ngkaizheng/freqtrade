"""Open interest features (spec sections 12 and 13).

Source: Binance `daily/metrics` archives, the only free source of historical
5-minute open interest.  The value stamped at time ``t`` is a point-in-time
snapshot, so using it for a decision taken at bar ``t``'s close introduces no
lookahead.

The price x OI regime grid is a *classification*, not a causal claim.  The
report is required to test the 2x2 rather than assume quadrant A is bullish.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_open_interest(df: pd.DataFrame, lags: tuple[int, ...] = (3, 6)) -> pd.DataFrame:
    out = df.copy()
    if "open_interest" not in out.columns:
        return out

    oi = out["open_interest"]
    out["oi_change_abs"] = oi.diff()
    for lag in lags:
        past = oi.shift(lag)
        # A near-zero prior OI makes the ratio explode; those bars carry no
        # information and an inf here silently poisons every z-score and
        # quantisation downstream.
        out[f"oi_change_{lag}"] = (oi / past - 1.0).replace([np.inf, -np.inf], np.nan)
        out[f"oi_change_{lag}_abs"] = oi - past

    # Value-denominated change is the cross-symbol comparable quantity.
    if "open_interest_value" in out.columns:
        oiv = out["open_interest_value"]
        for lag in lags:
            out[f"oi_value_change_{lag}"] = (oiv / oiv.shift(lag) - 1.0).replace(
                [np.inf, -np.inf], np.nan)

    if "taker_long_short_vol_ratio" in out.columns:
        out["taker_ls_vol_ratio"] = out["taker_long_short_vol_ratio"]
    if "top_trader_long_short_ratio" in out.columns:
        out["top_trader_ls_ratio"] = out["top_trader_long_short_ratio"]

    out = add_price_oi_regime(out)
    return out


def add_price_oi_regime(df: pd.DataFrame, price_lag: int = 3) -> pd.DataFrame:
    """Label each bar with quadrant A/B/C/D of price change x OI change."""
    out = df
    price_chg = out["close"].pct_change(price_lag)
    oi_col = f"oi_change_{price_lag}"
    if oi_col not in out.columns:
        return out

    price_up = price_chg > 0
    oi_up = out[oi_col] > 0
    out["price_oi_regime"] = np.select(
        [price_up & oi_up, price_up & ~oi_up, ~price_up & oi_up, ~price_up & ~oi_up],
        ["A", "B", "C", "D"],
        default="?",
    )
    out["price_change_n"] = price_chg
    return out
