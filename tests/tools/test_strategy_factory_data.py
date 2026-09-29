from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory.data import as_utc, load_pair_bundle


def _write_ohlcv(path, dates, close):
    values = np.asarray(close, dtype=float)
    pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": values + 1,
            "low": values - 1,
            "close": values,
            "volume": np.full(len(values), 10.0),
        }
    ).to_feather(path)


def test_as_utc_handles_naive_and_aware():
    assert as_utc("2024-01-01").tzinfo is not None
    aware = pd.Timestamp("2024-01-01", tz="US/Eastern")
    assert as_utc(aware).tz_convert("UTC").hour == 5


def test_load_pair_bundle_audits_and_legacy_funding(tmp_path):
    dates = pd.date_range("2024-01-01", periods=2 * 24 * 60, freq="1min", tz="UTC")
    _write_ohlcv(tmp_path / "BTC_USDT_USDT-1m-futures.feather", dates, np.arange(len(dates)))
    five_dates = pd.date_range("2024-01-01", periods=2 * 24 * 12, freq="5min", tz="UTC")
    _write_ohlcv(tmp_path / "BTC_USDT_USDT-5m-futures.feather", five_dates, np.arange(len(five_dates)) * 5)
    funding = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01 00:00:00.002", tz="UTC")],
            "open": [0.0001],
            "high": [0],
            "low": [0],
            "close": [0],
            "volume": [0],
        }
    )
    funding.to_feather(tmp_path / "BTC_USDT_USDT-8h-funding_rate.feather")

    bundle = load_pair_bundle(tmp_path, "BTC/USDT:USDT", start="2024-01-01", end="2024-01-02")
    assert len(bundle.one_minute) == 24 * 60
    assert bundle.audit["one_minute"]["duplicates"] == 0
    assert bundle.audit["funding"]["layout"] == "legacy_8h"
    assert bundle.audit["funding"]["rows"] == 1
    assert bundle.funding.loc[0, "funding_rate"] == 0.0001
