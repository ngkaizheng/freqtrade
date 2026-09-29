"""The four pre-registered signal families.

Every function receives a completed-candle feature frame and returns a signal at
that bar's close. The execution engine is responsible for shifting the signal to
the next bar open; no strategy may use the current bar's future path as an entry.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.strategy_factory.features import FeatureBundle
from tools.strategy_factory.models import StrategySpec


def _false_if_nan(series: pd.Series) -> pd.Series:
    return series.notna() & np.isfinite(series.to_numpy(dtype=float))


def _up_5m(frame: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    return (
        _false_if_nan(frame[f"ema_{fast}_5m"])
        & _false_if_nan(frame[f"ema_{slow}_5m"])
        & (frame[f"ema_{fast}_5m"] > frame[f"ema_{slow}_5m"])
        & (frame["close"] > frame[f"ema_{fast}_5m"])
    )


def _down_5m(frame: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    return (
        _false_if_nan(frame[f"ema_{fast}_5m"])
        & _false_if_nan(frame[f"ema_{slow}_5m"])
        & (frame[f"ema_{fast}_5m"] < frame[f"ema_{slow}_5m"])
        & (frame["close"] < frame[f"ema_{fast}_5m"])
    )


def _signals_h1(frame: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    fast = int(params["trend_fast"])
    slow = int(params["trend_slow"])
    tolerance = float(params["pullback_bps"]) / 10_000
    vwap = frame["session_vwap"]
    volume_ratio = frame["volume_ratio_20_1m"]
    pullback_volume_ratio = frame["previous_volume_ratio_20_1m"]
    valid_vwap = _false_if_nan(vwap) & _false_if_nan(volume_ratio) & _false_if_nan(pullback_volume_ratio)
    touch_long = valid_vwap & (frame["low"] <= vwap * (1 + tolerance))
    touch_short = valid_vwap & (frame["high"] >= vwap * (1 - tolerance))
    common_long = (
        touch_long
        & (frame["close"] > vwap)
        & (frame["close"] > frame["open"])
        & (pullback_volume_ratio <= float(params["contraction_max"]))
        & (volume_ratio >= float(params["confirmation_min"]))
    )
    common_short = (
        touch_short
        & (frame["close"] < vwap)
        & (frame["close"] < frame["open"])
        & (pullback_volume_ratio <= float(params["contraction_max"]))
        & (volume_ratio >= float(params["confirmation_min"]))
    )
    return common_long & _up_5m(frame, fast, slow), common_short & _down_5m(frame, fast, slow)


def _signals_h2(frame: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    fast = int(params["ema_fast"])
    slow = int(params["ema_slow"])
    ema_fast = frame[f"ema_{fast}_1m"]
    ema_slow = frame[f"ema_{slow}_1m"]
    previous_open = frame["open"].shift(1)
    previous_close = frame["close"].shift(1)
    previous_high = frame["high"].shift(1)
    previous_low = frame["low"].shift(1)
    valid = _false_if_nan(ema_fast) & _false_if_nan(ema_slow)
    touch_long = valid & (frame["low"] <= ema_fast)
    touch_short = valid & (frame["high"] >= ema_fast)
    engulfing_long = (
        (previous_close < previous_open)
        & (frame["close"] > frame["open"])
        & (frame["open"] <= previous_close)
        & (frame["close"] >= previous_open)
        & (frame["close"] > previous_high)
    )
    engulfing_short = (
        (previous_close > previous_open)
        & (frame["close"] < frame["open"])
        & (frame["open"] >= previous_close)
        & (frame["close"] <= previous_open)
        & (frame["close"] < previous_low)
    )
    long = (
        touch_long
        & (ema_fast > ema_slow)
        & (frame["close"] > ema_fast)
        & engulfing_long
        & _up_5m(frame, 20, 50)
    )
    short = (
        touch_short
        & (ema_fast < ema_slow)
        & (frame["close"] < ema_fast)
        & engulfing_short
        & _down_5m(frame, 20, 50)
    )
    return long.fillna(False), short.fillna(False)


def _signals_h3(frame: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    range_minutes = int(params["range_minutes"])
    window_hours = int(params["trade_window_hours"])
    high = frame[f"orb_high_{range_minutes}"]
    low = frame[f"orb_low_{range_minutes}"]
    minute = frame["minute_in_day"]
    valid = _false_if_nan(high) & _false_if_nan(low) & _false_if_nan(frame["volume_ratio_20_1m"])
    active = (minute >= range_minutes) & (minute <= range_minutes + window_hours * 60)
    volume = frame["volume_ratio_20_1m"] >= float(params["volume_min"])
    long = valid & active & volume & (frame["close"] > high)
    short = valid & active & volume & (frame["close"] < low)
    return long.fillna(False), short.fillna(False)


def _signals_h4(frame: pd.DataFrame, params: dict[str, Any]) -> tuple[pd.Series, pd.Series]:
    lookback = int(params["lookback"])
    atr_median = frame[f"atr_median_{lookback}_1m"]
    compression = frame["atr14_1m"] <= atr_median * float(params["compression_max"])
    high = frame[f"breakout_high_{lookback}_1m"]
    low = frame[f"breakout_low_{lookback}_1m"]
    volume = frame["volume_ratio_20_1m"] >= float(params["volume_min"])
    valid = _false_if_nan(atr_median) & _false_if_nan(high) & _false_if_nan(low)
    long = valid & compression & volume & (frame["close"] > high) & _up_5m(frame, 20, 50)
    short = valid & compression & volume & (frame["close"] < low) & _down_5m(frame, 20, 50)
    return long.fillna(False), short.fillna(False)


def signals_for_spec(features: FeatureBundle, spec: StrategySpec) -> tuple[np.ndarray, np.ndarray]:
    """Return long/short signal arrays aligned to completed 1m candles."""

    frame = features.frame
    handlers = {
        "H1_VWAP_PULLBACK": _signals_h1,
        "H2_EMA_RETEST": _signals_h2,
        "H3_UTC_ORB": _signals_h3,
        "H4_ATR_COMPRESSION": _signals_h4,
    }
    handler = handlers[spec.hypothesis_id]
    long, short = handler(frame, spec.params)
    # A signal cannot be both directions; conflicting rows are discarded.
    conflict = long & short
    return (
        (long & ~conflict).to_numpy(dtype=bool),
        (short & ~conflict).to_numpy(dtype=bool),
    )
