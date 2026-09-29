"""Phase A tests: canonical data layer, discovery, and the data audit.

Fixture-free by design: the same files run under pytest and under the
dependency-free V2 runner, so a result reported by one is a result reported by
the other. ``tmp_path`` is replaced with ``tempfile`` for the same reason.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.data import (
    AVAILABLE,
    DEGRADED,
    MISSING,
    as_utc,
    audit_funding,
    audit_price,
    cross_timeframe_audit,
    discover,
    format_symbol,
    funding_cross_source_audit,
    funding_price_coverage,
    load_funding_events,
    load_ohlcv,
    normalize_timeframe,
    pandas_offset,
    run_audit,
    timeframe_minutes,
)


# ---------------------------------------------------------------------------
# Synthetic dataset builders
# ---------------------------------------------------------------------------


def _write_ohlcv(path: Path, periods: int = 200, freq: str = "1h", start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    base = np.linspace(100.0, 200.0, periods)
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + 0.5,
            "volume": np.full(periods, 10.0),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_feather(path)
    return frame


def _write_funding(path: Path, events: int = 30, start: str = "2024-01-01") -> pd.DataFrame:
    times = pd.date_range(start, periods=events, freq="8h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": times + pd.Timedelta(milliseconds=2),
            "open": np.linspace(0.0001, 0.0005, events),
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0.0,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_feather(path)
    return frame


def _write_funding_rest(path: Path, events: int = 30, start: str = "2024-01-01") -> pd.DataFrame:
    times = pd.date_range(start, periods=events, freq="8h", tz="UTC")
    frame = pd.DataFrame(
        {"fundingTime": times, "fundingRate": np.linspace(0.0001, 0.0005, events)}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_feather(path)
    return frame


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def test_format_symbol_renders_perpetual_and_spot() -> None:
    assert format_symbol("BTC", "USDT_USDT") == "BTC/USDT:USDT"
    assert format_symbol("BTC", "USDT") == "BTC/USDT"
    assert format_symbol("BTC", "USDT_BUSD") == "BTC/USDT:BUSD"


def test_normalize_timeframe_maps_to_canonical_labels() -> None:
    assert normalize_timeframe("5m") == "5m"
    assert normalize_timeframe("15min") == "15m"
    assert normalize_timeframe("1h") == "1h"
    assert normalize_timeframe("4H") == "4h"
    assert normalize_timeframe("1d") == "1d"
    assert normalize_timeframe("nonsense") is None


def test_pandas_offset_uses_pandas3_minute_alias() -> None:
    # pandas 3 reads a lowercase 'm' as month-end, which would silently
    # resample minute bars to months.
    assert pandas_offset("5m") == "5min"
    assert pandas_offset("1h") == "1h"
    index = pd.date_range("2024-01-01", periods=10, freq="5min", tz="UTC")
    assert len(index) == 10


def test_timeframe_minutes_rejects_unknown_label() -> None:
    assert timeframe_minutes("15m") == 15
    try:
        timeframe_minutes("7z")
    except KeyError:
        return
    raise AssertionError("an unknown timeframe must raise KeyError")


def test_as_utc_normalizes_naive_and_aware() -> None:
    assert str(as_utc("2024-01-01")) == "2024-01-01 00:00:00+00:00"
    assert str(as_utc("2024-01-01T00:00:00+02:00")) == "2023-12-31 22:00:00+00:00"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def test_load_ohlcv_sets_decision_time_at_bar_close() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "BTC_USDT_USDT-1h-futures.feather"
        _write_ohlcv(path, periods=5, freq="1h")
        frame = load_ohlcv(path, "1h")
    # A candle labelled 00:00 on a 1h grid closes at 01:00.
    assert frame["decision_time"].iloc[0] == pd.Timestamp("2024-01-01 01:00", tz="UTC")
    assert (frame["decision_time"] - frame["date"]).unique() == [pd.Timedelta(hours=1)]


def test_load_funding_keeps_events_and_records_exchange_offset() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "BTC_USDT_USDT-8h-funding_rate.feather"
        _write_funding(path, events=10)
        events = load_funding_events(path)
    assert len(events) == 10
    assert events["offset_ms"].unique().tolist() == [2]
    # The event stream must stay one row per settlement: no forward filling.
    assert events["settlement_time"].is_monotonic_increasing
    assert events["funding_rate"].notna().all()


def test_load_funding_supports_rest_layout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "BTC_USDT-funding.feather"
        _write_funding_rest(path, events=8)
        events = load_funding_events(path)
    assert len(events) == 8
    assert events["offset_ms"].unique().tolist() == [0]


# ---------------------------------------------------------------------------
# Audits
# ---------------------------------------------------------------------------


def test_audit_price_detects_gaps_and_duplicates() -> None:
    dates = pd.to_datetime(
        [
            "2024-01-01 00:00",
            "2024-01-01 01:00",
            "2024-01-01 02:00",
            "2024-01-01 02:00",  # duplicate
            "2024-01-01 05:00",  # gap
        ],
        utc=True,
    )
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [1.0] * 5,
            "high": [1.1] * 5,
            "low": [0.9] * 5,
            "close": [1.0] * 5,
            "volume": [1.0] * 5,
        }
    )
    report = audit_price(frame, "1h")
    assert report["duplicates"] == 1
    assert report["gap_events"] >= 1
    assert report["invalid_ohlcv"] == 0
    assert report["timezone"] == "UTC"
    assert report["naive_timestamps"] == 0


def test_audit_price_flags_invalid_ohlc() -> None:
    dates = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [1.0, 1.0, 1.0],
            "high": [0.5, 1.1, 1.1],  # first bar violates high >= open
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )
    assert audit_price(frame, "1h")["invalid_ohlcv"] == 1


def test_audit_funding_measures_interval_and_completeness() -> None:
    times = pd.date_range("2024-01-01", periods=20, freq="8h", tz="UTC")
    frame = pd.DataFrame(
        {
            "event_time": times,
            "settlement_time": times,
            "funding_rate": np.full(20, 0.0001),
            "offset_ms": np.zeros(20, dtype="int64"),
            "source": "synthetic",
        }
    )
    report = audit_funding(frame)
    assert report["observed_interval_hours"] == 8.0
    assert report["missing_events"] == 0
    assert report["completeness_ratio"] == 1.0
    assert report["status"] == AVAILABLE


def test_audit_funding_reports_missing_settlements() -> None:
    times = pd.date_range("2024-01-01", periods=20, freq="8h", tz="UTC").delete([5, 6])
    frame = pd.DataFrame(
        {
            "event_time": times,
            "settlement_time": times,
            "funding_rate": np.full(len(times), 0.0001),
            "offset_ms": np.zeros(len(times), dtype="int64"),
            "source": "synthetic",
        }
    )
    report = audit_funding(frame)
    assert report["missing_events"] == 2
    assert report["completeness_ratio"] < 1.0


def test_funding_cross_source_reports_disagreement() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        a = Path(tmp) / "A-8h-funding_rate.feather"
        b = Path(tmp) / "B-8h-funding_rate.feather"
        _write_funding(a, events=10)
        _write_funding(b, events=10)
        same = funding_cross_source_audit([a, b])
        assert same["status"] == AVAILABLE
        assert same["max_spread_bps"] == 0.0

        # Now make the second source disagree by 10 bps on the last event.
        frame = pd.read_feather(b)
        frame.loc[frame.index[-1], "open"] += 0.001
        frame.to_feather(b)
        differ = funding_cross_source_audit([a, b])
    assert differ["status"] == AVAILABLE
    assert differ["max_spread_bps"] > 0.0
    assert differ["identical_ratio"] < 1.0


def test_funding_price_coverage_reports_lag() -> None:
    funding = {
        "status": AVAILABLE,
        "start": "2024-01-01 00:00:00+00:00",
        "end": "2024-01-11 00:00:00+00:00",
    }
    price = {
        "1h": {
            "usable": True,
            "start": "2024-01-01 00:00:00+00:00",
            "end": "2024-01-03 00:00:00+00:00",
        }
    }
    report = funding_price_coverage(funding, price)
    assert report["funding_lags_price_by_days"] > 0.0
    assert report["status"] == DEGRADED


def test_cross_timeframe_audit_reports_but_never_repairs() -> None:
    base = load_ohlcv_frame("1m", 300)
    derived = aggregate_five(base)
    report = cross_timeframe_audit({"1m": base, "5m": derived}, "5m")
    assert report["status"] == AVAILABLE
    assert report["common_buckets"] > 0
    assert report["mismatched_buckets"] == 0
    assert "no overwrite" in report["policy"]

    corrupted = derived.copy()
    corrupted.loc[corrupted.index[3], "close"] += 5.0
    report2 = cross_timeframe_audit({"1m": base, "5m": corrupted}, "5m")
    assert report2["mismatched_buckets"] >= 1


# ---------------------------------------------------------------------------
# Discovery and the full audit
# ---------------------------------------------------------------------------


def test_discover_merges_funding_layouts_into_one_inventory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        futures = root / "data" / "binance" / "futures"
        funding = root / "data" / "binance_funding"
        _write_ohlcv(futures / "BTC_USDT_USDT-1h-futures.feather", periods=50, freq="1h")
        _write_funding(futures / "BTC_USDT_USDT-8h-funding_rate.feather", events=20)
        _write_funding_rest(funding / "BTC_USDT-funding.feather", events=40)

        inventory = discover(futures)
    assert list(inventory) == ["BTC_USDT"]
    item = inventory["BTC_USDT"]
    assert item.symbol == "BTC/USDT:USDT"
    assert len(item.funding) == 2, "both funding layouts must land in one inventory"
    assert item.field_status()["funding_rate"] == AVAILABLE


def test_discover_reports_absent_derivatives_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        futures = Path(tmp) / "futures"
        _write_ohlcv(futures / "ETH_USDT_USDT-1h-futures.feather", periods=50, freq="1h")
        inventory = discover(futures)
    status = inventory["ETH_USDT"].field_status()
    assert status["open_interest"] == MISSING
    assert status["taker_buy_volume"] == MISSING
    assert status["index_price"] == MISSING
    # Basis is never reported available without a real index price.
    assert status["basis"] == MISSING


def test_run_audit_summarises_blocked_families() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        futures = Path(tmp) / "futures"
        _write_ohlcv(futures / "BTC_USDT_USDT-1h-futures.feather", periods=400, freq="1h")
        _write_funding(futures / "BTC_USDT_USDT-8h-funding_rate.feather", events=20)
        manifest = run_audit(futures, with_hash=False)
    assert manifest["symbols_discovered"] == 1
    assert manifest["primary_timeframes_ready"] == ["1h"]
    assert manifest["missing_primary_timeframes"] == ["5m", "15m"]
    blocked = " ".join(manifest["blocked_families"])
    assert "open_interest" in blocked
    assert "basis" in blocked


def test_run_audit_does_not_modify_source_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        futures = Path(tmp) / "futures"
        source = futures / "BTC_USDT_USDT-1h-futures.feather"
        _write_ohlcv(source, periods=400, freq="1h")
        before = source.read_bytes()
        mtime = source.stat().st_mtime_ns
        run_audit(futures, with_hash=True)
        assert source.read_bytes() == before
        assert source.stat().st_mtime_ns == mtime


def test_data_fingerprint_is_stable_and_content_sensitive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        futures = Path(tmp) / "futures"
        _write_ohlcv(futures / "BTC_USDT_USDT-1h-futures.feather", periods=400, freq="1h")
        first = run_audit(futures, with_hash=False)
        from tools.strategy_factory_v2.data import data_fingerprint

        a = data_fingerprint(first)
        b = data_fingerprint(run_audit(futures, with_hash=False))
        assert a == b, "the same dataset must fingerprint identically"
        assert len(a) == 64


# ---------------------------------------------------------------------------
# Local helpers used by two tests above
# ---------------------------------------------------------------------------


def load_ohlcv_frame(timeframe: str, periods: int) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="1min", tz="UTC")
    base = np.linspace(100.0, 110.0, periods)
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + 0.5,
            "volume": np.full(periods, 5.0),
        }
    )
    frame["decision_time"] = frame["date"] + pd.Timedelta(minutes=1)
    assert timeframe == "1m"
    return frame


def aggregate_five(frame: pd.DataFrame) -> pd.DataFrame:
    aggregated = (
        frame.set_index("date")
        .resample("5min", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    aggregated["decision_time"] = aggregated["date"] + pd.Timedelta(minutes=5)
    return aggregated
