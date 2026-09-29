"""Causal feature construction.

Every function in this package obeys one rule: the value at bar ``t`` is a
function of bars ``<= t`` only.  That is what makes next-bar execution honest
(spec sections 5 and 35).

Two conventions worth stating explicitly:

1.  **VWAP is a running, day-anchored value.**  A bar's VWAP only includes
    bars of the same UTC day up to and including itself.  The completed daily
    VWAP is never used for an intraday decision.

2.  **Features are always computed on the full study history and only then
    sliced by split.**  CVD is a cumulative series, so computing it inside a
    validation slice would restart the accumulator and fabricate a bearish
    CVD/SMA crossover at the boundary.  Always build the whole frame, then
    slice.
"""

from __future__ import annotations

import pandas as pd

from . import atr, cvd, funding, liquidation, obv, open_interest, volume, vwap

__all__ = [
    "add_all", "add_rvol", "add_vwap", "add_obv", "add_cvd",
    "add_open_interest", "add_funding", "add_liquidation", "add_atr",
    "add_breakout", "add_forward_returns",
]

add_rvol = volume.add_rvol
add_vwap = vwap.add_vwap
add_obv = obv.add_obv
add_cvd = cvd.add_cvd
add_open_interest = open_interest.add_open_interest
add_funding = funding.add_funding
add_liquidation = liquidation.add_liquidation
add_atr = atr.add_atr
add_breakout = volume.add_breakout
add_forward_returns = volume.add_forward_returns


# Bar lags chosen so that the *time* each feature spans is comparable across
# timeframes.  Spec section 12 asks for OI change over 15m and 30m; on 5m that
# is 3 and 6 bars, on 1m it is 15 and 30.  Spec section 45 asks for forward
# returns at 5/10/15/30/60 minutes, which is a different bar count per
# timeframe and is why these cannot be one hardcoded constant.
TIMEFRAME_TUNING: dict[str, dict] = {
    "1m": {"oi_lags": (1, 3, 6, 15, 30), "cvd_delta_lags": (1, 3, 5, 10),
           "forward_horizons": (5, 10, 15, 30, 60)},
    "5m": {"oi_lags": (1, 3, 6), "cvd_delta_lags": (1, 3, 5, 10),
           "forward_horizons": (1, 2, 3, 6, 12)},
    # Higher resolutions keep the *time* each feature spans comparable, but the
    # lag sets are supersets that still contain the recipe defaults
    # (cvd_delta_5, oi_change_3).  Without that, a strategy carrying a 5-bar
    # CVD default silently finds a missing column at 1h and produces ZERO
    # trades -- indistinguishable from "no edge" unless you check the count.
    "1h": {"oi_lags": (1, 2, 3, 6), "cvd_delta_lags": (1, 2, 3, 5, 10),
           "forward_horizons": (1, 2, 4, 8, 24)},
    "4h": {"oi_lags": (1, 2, 3, 6), "cvd_delta_lags": (1, 2, 3, 5, 10),
           "forward_horizons": (1, 2, 3, 6, 12)},
}


def add_all(df: pd.DataFrame, *,
            timeframe: str = "5m",
            rvol_period: int = 20,
            breakout_period: int = 20,
            atr_period: int = 14,
            cvd_delta_lags: tuple[int, ...] | None = None,
            oi_lags: tuple[int, ...] | None = None,
            funding_window: int = 90,
            liquidation_window: int = 20,
            forward_horizons: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Attach the full feature block used across SHARK-01..SHARK-08."""
    tuning = TIMEFRAME_TUNING.get(timeframe, TIMEFRAME_TUNING["5m"])
    out = df
    out = add_rvol(out, period=rvol_period)
    out = add_breakout(out, period=breakout_period)
    out = add_atr(out, period=atr_period)
    out = add_vwap(out)
    out = add_obv(out, period=20)
    out = add_cvd(out, lags=cvd_delta_lags or tuning["cvd_delta_lags"], sma_period=20)
    out = add_open_interest(out, lags=oi_lags or tuning["oi_lags"])
    out = add_funding(out, window=funding_window)
    out = add_liquidation(out, window=liquidation_window)
    out = add_forward_returns(out, horizons=forward_horizons or tuning["forward_horizons"])
    return out
