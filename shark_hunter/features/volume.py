"""Relative volume and price breakout -- the SHARK-01 signal pair."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_rvol(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """RVOL_N = current volume / SMA(volume, N)   (spec section 6.1).

    The average intentionally includes the current bar: at bar close the
    current bar's volume is fully known, so this stays causal, and it is the
    convention the spec states literally.  Volume is clipped at zero before
    the mean so a zero-volume bar cannot manufacture an infinite ratio.
    """
    out = df.copy()
    vol = out["volume"].clip(lower=0.0)
    avg = vol.rolling(period, min_periods=period).mean()
    out["volume_sma"] = avg
    out["rvol"] = vol / avg.replace(0.0, np.nan)
    return out


def add_breakout(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Donchian breakout that strictly excludes the current bar (spec 8).

    ``prev_high_N`` is the highest high of the N bars *ending one bar ago*.
    Including the current bar would make a breakout almost impossible to
    exceed and, worse, would leak the bar's own high into its own decision.
    """
    out = df.copy()
    out["prev_high"] = out["high"].rolling(period, min_periods=period).max().shift(1)
    out["prev_low"] = out["low"].rolling(period, min_periods=period).min().shift(1)
    out["breakout_long"] = out["close"] > out["prev_high"]
    out["breakout_short"] = out["close"] < out["prev_low"]
    return out


def add_forward_returns(df: pd.DataFrame,
                        horizons: tuple[int, ...] = (1, 2, 3, 6, 12)) -> pd.DataFrame:
    """Forward close-to-close returns, for signal-quality work only.

    These columns are *never* consumed by a strategy or by the execution
    engine.  They exist so the signal can be judged before a stop and target
    are attached to it (spec section 45).  Every consumer is downstream of
    :func:`features.add_all` but upstream of the trade loop, which is where
    the separation is enforced.
    """
    out = df.copy()
    close = out["close"]
    for h in horizons:
        out[f"fwd_ret_{h}"] = close.shift(-h) / close - 1.0
    return out
