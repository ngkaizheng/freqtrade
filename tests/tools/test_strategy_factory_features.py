from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory.data import PairBundle
from tools.strategy_factory.features import build_features


def test_features_keep_five_minute_clock_and_orb_levels():
    one_dates = pd.date_range("2024-01-01", periods=12 * 60, freq="1min", tz="UTC")
    one = pd.DataFrame(
        {
            "date": one_dates,
            "open": np.arange(len(one_dates), dtype=float),
            "high": np.arange(len(one_dates), dtype=float) + 1,
            "low": np.arange(len(one_dates), dtype=float) - 1,
            "close": np.arange(len(one_dates), dtype=float),
            "volume": np.full(len(one_dates), 10.0),
        }
    )
    five_dates = pd.date_range("2024-01-01", periods=12 * 12, freq="5min", tz="UTC")
    five = one.iloc[::5].reset_index(drop=True).copy()
    five["date"] = five_dates
    bundle = PairBundle(
        pair="BTC/USDT:USDT",
        one_minute=one,
        five_minute=five,
        funding=pd.DataFrame(columns=["date", "funding_rate"]),
        audit={},
    )
    features = build_features(bundle)
    at_0004 = features.frame[features.frame["date"] == pd.Timestamp("2024-01-01 00:04", tz="UTC")].iloc[0]
    at_0005 = features.frame[features.frame["date"] == pd.Timestamp("2024-01-01 00:05", tz="UTC")].iloc[0]
    assert pd.isna(at_0004["orb_high_5"])
    assert at_0005["orb_high_5"] == one.iloc[:5]["high"].max()
    at_0045 = features.frame[features.frame["date"] == pd.Timestamp("2024-01-01 00:45", tz="UTC")].iloc[0]
    assert pd.isna(at_0004["ema_9_5m"])
    assert not pd.isna(at_0045["ema_9_5m"])
