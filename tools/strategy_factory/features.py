"""Feature construction with explicit candle-availability semantics."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from tools.strategy_factory.data import PairBundle


@dataclass
class FeatureBundle:
    """Point-in-time 1m features plus the event stream used for funding."""

    frame: pd.DataFrame
    funding: pd.DataFrame
    five_minute_features: pd.DataFrame


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _rolling_orb_levels(frame: pd.DataFrame, minutes: int) -> tuple[pd.Series, pd.Series]:
    """Return the fixed first-N-minute UTC range, available only after N bars."""

    day = frame["date"].dt.floor("D")
    # A candle stamped 00:00 is complete at 00:01, so the first N-minute
    # range becomes available at the N-minute timestamp, not at row N-1.
    minute_number = frame["date"].dt.hour * 60 + frame["date"].dt.minute
    running_high = frame.groupby(day, sort=False)["high"].cummax()
    running_low = frame.groupby(day, sort=False)["low"].cummin()
    # Shift within each UTC day so the candle that completes the range is not
    # itself included in the level it is about to break.
    running_high = running_high.groupby(day, sort=False).shift(1)
    running_low = running_low.groupby(day, sort=False).shift(1)
    ready = minute_number >= minutes
    high = running_high.where(ready).groupby(day, sort=False).ffill()
    low = running_low.where(ready).groupby(day, sort=False).ffill()
    return high, low


def _five_minute_features(five: pd.DataFrame) -> pd.DataFrame:
    result = five.copy().sort_values("date")
    for span in (9, 20, 50, 200):
        result[f"ema_{span}_5m"] = _ema(result["close"], span)
    result["atr14_5m"] = _atr(result, 14)
    result["volume_median_5m"] = (
        result["volume"].rolling(20, min_periods=20).median().shift(1)
    )
    # A 5m candle labelled 00:00 is complete at 00:05, not 00:00.
    result["available_at"] = result["date"] + pd.Timedelta(minutes=5)
    return result


def build_features(bundle: PairBundle) -> FeatureBundle:
    """Build all features once per pair before enumerating strategy parameters."""

    frame = bundle.one_minute.copy().sort_values("date").reset_index(drop=True)
    frame.attrs["pair"] = bundle.pair
    five = _five_minute_features(bundle.five_minute)

    for span in (5, 9, 12, 20, 21, 34, 50, 200):
        frame[f"ema_{span}_1m"] = _ema(frame["close"], span)
    frame["atr14_1m"] = _atr(frame, 14)
    frame["volume_median_20_1m"] = (
        frame["volume"].rolling(20, min_periods=20).median().shift(1)
    )
    frame["volume_ratio_20_1m"] = frame["volume"] / frame["volume_median_20_1m"].replace(
        0, np.nan
    )
    # Pullback volume is measured on the prior completed candle; the current
    # candle is reserved for expansion/confirmation. This avoids requiring one
    # candle to be both contraction and expansion.
    frame["previous_volume_ratio_20_1m"] = frame["volume_ratio_20_1m"].shift(1)
    for lookback in (20, 60):
        frame[f"atr_median_{lookback}_1m"] = (
            frame["atr14_1m"].rolling(lookback, min_periods=lookback).median().shift(1)
        )
        frame[f"breakout_high_{lookback}_1m"] = (
            frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)
        )
        frame[f"breakout_low_{lookback}_1m"] = (
            frame["low"].rolling(lookback, min_periods=lookback).min().shift(1)
        )

    day = frame["date"].dt.floor("D")
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    weighted_volume = typical * frame["volume"]
    frame["session_vwap"] = (
        weighted_volume.groupby(day, sort=False).cumsum()
        / frame["volume"].groupby(day, sort=False).cumsum().replace(0, np.nan)
    )
    frame["session_day"] = day
    frame["minute_in_day"] = (
        frame["date"].dt.hour * 60
        + frame["date"].dt.minute
        + frame["date"].dt.second / 60
    )
    frame["hour_utc"] = frame["date"].dt.hour

    frame["sweep_high_20_1m"] = frame["high"].rolling(20, min_periods=20).max().shift(1)
    frame["sweep_low_20_1m"] = frame["low"].rolling(20, min_periods=20).min().shift(1)
    frame["sweep_volume_ratio_20_1m"] = frame["volume_ratio_20_1m"]

    for minutes in (5, 15, 30):
        high, low = _rolling_orb_levels(frame, minutes)
        frame[f"orb_high_{minutes}"] = high
        frame[f"orb_low_{minutes}"] = low

    # Merge only completed 5m features. At 00:05 the 00:00-00:05 candle is
    # available; at 00:04 the previous 5m candle remains in force.
    five_columns = [
        "available_at",
        "ema_9_5m",
        "ema_20_5m",
        "ema_50_5m",
        "ema_200_5m",
        "atr14_5m",
        "volume_median_5m",
    ]
    frame = pd.merge_asof(
        frame.sort_values("date"),
        five[five_columns].sort_values("available_at"),
        left_on="date",
        right_on="available_at",
        direction="backward",
    ).drop(columns=["available_at"])

    funding = bundle.funding.copy().sort_values("date")
    # Keep the exact event stream; the engine sums only events while a position
    # is open. This avoids a forward-filled funding feature being mistaken for a
    # fee known before the event.
    return FeatureBundle(frame=frame.reset_index(drop=True), funding=funding, five_minute_features=five)
