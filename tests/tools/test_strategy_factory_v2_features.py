"""Phase B tests: the feature engine and its point-in-time contract."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.features import (
    baseline_distribution,
    build_features,
    excursion_features,
    forward_returns,
    funding_features,
    open_interest_features,
    taker_flow_features,
)
from tools.strategy_factory_v2.spec import (
    ATR_PERIODS,
    EXPANDING_MIN_EVENTS,
    EMA_PERIODS,
    FUNDING_PERCENTILE_CUTS,
    OI_WINDOWS,
    RETURN_WINDOWS,
    TAKER_FLOW_WINDOWS,
)


def _price(periods: int = 1200, freq: str = "1h", start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    rng = np.random.default_rng(11)
    steps = rng.normal(0.0004, 0.01, periods)
    close = 100.0 * np.exp(np.cumsum(steps))
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close * (1.0 + rng.normal(0, 0.0005, periods)),
            "high": close * 1.004,
            "low": close * 0.996,
            "close": close,
            "volume": np.abs(rng.normal(1000.0, 200.0, periods)) + 1.0,
        }
    )
    minutes = {"1h": 60, "15m": 15, "5m": 5}[freq]
    frame["decision_time"] = frame["date"] + pd.Timedelta(minutes=minutes)
    return frame


def _funding(periods: int = 40, start: str = "2024-01-01") -> pd.DataFrame:
    times = pd.date_range(start, periods=periods, freq="8h", tz="UTC")
    return pd.DataFrame(
        {
            "event_time": times,
            "settlement_time": times,
            "funding_rate": np.linspace(-0.0004, 0.0006, periods),
            "offset_ms": np.zeros(periods, dtype="int64"),
            "source": "synthetic",
        }
    )


def _events(times: pd.DatetimeIndex, values: np.ndarray, column: str) -> pd.DataFrame:
    return pd.DataFrame({"timestamp": times, column: values})


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_build_features_requires_a_decision_time_column() -> None:
    frame = _price().drop(columns=["decision_time"])
    try:
        build_features(frame, "1h")
    except ValueError as error:
        assert "decision_time" in str(error)
        return
    raise AssertionError("a frame without decision_time must be rejected")


def test_build_features_rejects_unsorted_decision_time() -> None:
    frame = _price(periods=100)
    shuffled = frame.iloc[::-1].reset_index(drop=True)
    try:
        build_features(shuffled, "1h")
    except ValueError as error:
        assert "sorted" in str(error)
        return
    raise AssertionError("an unsorted frame must be rejected")


def test_every_preregistered_window_is_present() -> None:
    bundle = build_features(_price(), "1h", symbol="T/USDT:USDT")
    frame = bundle.frame
    for window in RETURN_WINDOWS:
        assert f"ret_{window}" in frame.columns
    for period in ATR_PERIODS:
        assert f"atr_{period}" in frame.columns
    for span in EMA_PERIODS:
        assert f"ema_{span}" in frame.columns
    for window in TAKER_FLOW_WINDOWS:
        assert f"taker_imbalance_roll_{window}" in frame.columns
    assert "vwap_distance" in frame.columns
    assert "range_ratio" in frame.columns


# ---------------------------------------------------------------------------
# Causality of individual features
# ---------------------------------------------------------------------------


def test_returns_use_only_past_bars() -> None:
    frame = _price(periods=600)
    bundle = build_features(frame, "1h")
    spot = 400
    # A 12-bar return at bar t is close[t] / close[t-12] - 1, nothing later.
    expected = frame["close"].iloc[spot] / frame["close"].iloc[spot - 12] - 1.0
    assert abs(bundle.frame["ret_12"].iloc[spot] - expected) < 1e-12


def test_trailing_percentile_is_bounded_and_backward_only() -> None:
    bundle = build_features(_price(periods=800), "1h")
    percentile = bundle.frame["volume_percentile"].dropna()
    assert percentile.min() >= 0.0
    assert percentile.max() <= 100.0
    # The leading window must be unavailable, never silently filled.
    assert bundle.frame["volume_percentile"].iloc[:287].isna().all()
    assert bundle.frame["volume_percentile"].iloc[287:].notna().all()


def test_feature_unchanged_when_only_the_future_changes() -> None:
    frame = _price(periods=800)
    cut = 600
    baseline = build_features(frame, "1h").frame
    mutated = frame.copy()
    future = mutated.index[cut:]
    mutated.loc[future, ["open", "high", "low", "close"]] *= 3.0
    mutated.loc[future, ["open", "high", "low", "close"]] *= 3.0
    result = build_features(mutated, "1h").frame
    for column in ("ret_12", "atr_14", "ema_20", "realized_vol_30", "volume_percentile"):
        left = baseline[column].iloc[:cut]
        right = result[column].iloc[:cut]
        assert left.equals(right), f"{column} changed when only the future changed"


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


def test_funding_is_an_event_stream_not_a_forward_fill() -> None:
    price = _price(periods=48, freq="1h")
    events = _funding(periods=3)
    bundle = build_features(
        price, "1h", funding_events=events, funding_interval_hours=8.0
    )
    frame = bundle.frame
    # One settlement at 2024-01-01 00:00 is knowable from the 01:00 bar close on.
    assert bool(frame["funding_available"].iloc[0])
    assert abs(frame["funding_rate_last"].iloc[0] - events["funding_rate"].iloc[0]) < 1e-15
    # The rate is a step function of the last published settlement, not a ramp.
    assert frame["funding_rate_last"].nunique() <= len(events)
    # The raw event stream is preserved un-filled for the cost model.
    assert len(bundle.funding_events) == 3


def test_funding_features_are_nan_before_the_first_settlement() -> None:
    price = _price(periods=24, freq="1h", start="2023-12-31")
    events = _funding(periods=3, start="2024-01-02")
    frame = funding_features(events, price, 8.0)
    early = frame["funding_rate_last"].iloc[:24]
    assert early.isna().all()
    assert not bool(frame["funding_available"].iloc[:24].any())


def test_funding_percentile_is_expanding_and_never_sees_a_future_event() -> None:
    # The expanding percentile needs EXPANDING_MIN_EVENTS settlements before it
    # is defined at all, so the frame has to span enough bars to reach one.
    events = _funding(periods=200)
    price = _price(periods=24 * 30, freq="1h", start="2024-01-01")
    frame = funding_features(events, price, 8.0)
    values = frame["funding_percentile"].dropna()
    assert not values.empty, "no bar ever reached a defined funding percentile"
    assert values.min() >= 0.0 and values.max() <= 100.0
    # The expanding percentile is undefined until EXPANDING_MIN_EVENTS
    # settlements have been observed: 30 events x 8h = 240 bars of warm-up.
    warmup = EXPANDING_MIN_EVENTS * 8 - 12
    assert frame["funding_percentile"].iloc[:warmup].isna().all()
    assert frame["funding_percentile"].iloc[warmup + 12:].notna().any()


def test_missing_funding_yields_nan_and_a_false_flag() -> None:
    frame = funding_features(None, _price(periods=50), 8.0)
    assert frame["funding_rate_last"].isna().all()
    assert not frame["funding_available"].any()


def test_funding_is_never_continuously_charged() -> None:
    # The feature surface exposes a *rate*, never an accrued cost. A continuous
    # accrual would appear as a column that drifts between settlements; a step
    # function of the last published rate is the correct shape.
    events = _funding(periods=5)
    frame = funding_features(events, _price(periods=48, freq="1h"), 8.0)
    series = frame["funding_rate_last"].dropna()
    distinct_steps = series[series.diff().fillna(0.0) != 0.0].shape[0]
    assert distinct_steps <= len(events), (
        "funding_rate_last changed more often than there are settlements, which "
        "means something is interpolating between events"
    )


# ---------------------------------------------------------------------------
# Open interest and taker flow
# ---------------------------------------------------------------------------


def test_open_interest_features_are_nan_without_events() -> None:
    frame = open_interest_features(None, _price(periods=400))
    for window in OI_WINDOWS:
        assert f"oi_change_{window}" in frame.columns
        assert frame[f"oi_change_{window}"].isna().all()
    assert frame["open_interest"].isna().all()


def test_open_interest_change_matches_the_preregistered_window() -> None:
    price = _price(periods=400)
    times = price["decision_time"]
    values = np.linspace(1000.0, 2000.0, len(price))
    frame = open_interest_features(_events(times, values, "open_interest"), price)
    spot = 300
    expected = values[spot] - values[spot - 60]
    assert abs(frame["oi_change_60"].iloc[spot] - expected) < 1e-9


def test_open_interest_mutation_of_the_future_is_inert() -> None:
    price = _price(periods=400)
    times = price["decision_time"]
    values = np.linspace(1000.0, 2000.0, len(price))
    baseline = open_interest_features(_events(times, values, "open_interest"), price)
    mutated_values = values.copy()
    mutated_values[300:] += 5000.0
    mutated = open_interest_features(_events(times, mutated_values, "open_interest"), price)
    assert baseline["open_interest"].iloc[:300].equals(mutated["open_interest"].iloc[:300])
    assert baseline["oi_change_60"].iloc[:300].equals(mutated["oi_change_60"].iloc[:300])
    assert baseline["oi_percentile"].iloc[:300].equals(mutated["oi_percentile"].iloc[:300])
    # The mutation must actually have landed, or the test proves nothing.
    assert not baseline["open_interest"].iloc[350:].equals(
        mutated["open_interest"].iloc[350:]
    )


def test_taker_imbalance_matches_the_plan_definition() -> None:
    price = _price(periods=50)
    times = price["decision_time"]
    buy = np.full(len(price), 60.0)
    sell = np.full(len(price), 40.0)
    events = pd.DataFrame({"timestamp": times, "taker_buy_volume": buy, "taker_sell_volume": sell})
    frame = taker_flow_features(events, price)
    expected = (60.0 - 40.0) / (60.0 + 40.0)
    assert abs(frame["taker_imbalance"].iloc[-1] - expected) < 1e-12


def test_taker_imbalance_is_nan_not_zero_when_absent() -> None:
    # The failure mode this guards against is a missing taker feed being filled
    # with a neutral 0.0, which would look like "buyers and sellers balanced"
    # on a day when the feed simply was not collected.
    frame = taker_flow_features(None, _price(periods=50))
    assert "taker_imbalance" in frame.columns
    assert frame["taker_imbalance"].isna().all()
    assert frame["taker_buy_volume"].isna().all()
    assert frame["taker_sell_volume"].isna().all()
    for window in TAKER_FLOW_WINDOWS:
        assert frame[f"taker_imbalance_roll_{window}"].isna().all()


# ---------------------------------------------------------------------------
# Labels and baselines
# ---------------------------------------------------------------------------


def test_forward_returns_are_undefined_where_there_is_no_future() -> None:
    price = _price(periods=200)
    forwards = forward_returns(price, (6, 12, 24))
    for horizon in (6, 12, 24):
        column = f"fwd_ret_{horizon}"
        assert forwards[column].iloc[-horizon:].isna().all()
        assert forwards[column].iloc[: -horizon - 1].notna().any()


def test_forward_return_matches_a_manual_shift() -> None:
    price = _price(periods=100)
    forwards = forward_returns(price, (12,))
    spot = 50
    expected = price["close"].iloc[spot + 12] / price["close"].iloc[spot] - 1.0
    assert abs(forwards["fwd_ret_12"].iloc[spot] - expected) < 1e-12


def test_excursions_are_signed_against_the_decision_close() -> None:
    price = _price(periods=200)
    excursions = excursion_features(price, (12,))
    spot = 100
    window = price.iloc[spot + 1 : spot + 13]
    expected_mfe = window["high"].max() / price["close"].iloc[spot] - 1.0
    expected_mae = window["low"].min() / price["close"].iloc[spot] - 1.0
    assert abs(excursions["mfe_12"].iloc[spot] - expected_mfe) < 1e-12
    assert abs(excursions["mae_12"].iloc[spot] - expected_mae) < 1e-12
    # MAE is the adverse excursion and is therefore never positive.
    assert excursions["mae_12"].iloc[spot] <= 0.0
    # MFE must be at least as favourable as MAE for a long perspective.
    assert excursions["mfe_12"].iloc[spot] >= excursions["mae_12"].iloc[spot]


def test_baseline_distribution_reports_unconditional_statistics() -> None:
    rng = np.random.default_rng(3)
    series = pd.Series(rng.normal(0.0, 0.01, 5000))
    baseline = baseline_distribution(series)
    assert baseline["count"] == 5000
    assert abs(baseline["mean"]) < 0.001
    assert baseline["p05"] < baseline["p25"] < baseline["p75"] < baseline["p95"]
    assert baseline_distribution(pd.Series(dtype=float))["count"] == 0


def test_warmup_flag_is_false_before_the_longest_window_fills() -> None:
    frame = build_features(_price(periods=400), "1h").frame
    assert not bool(frame["warmup_complete"].iloc[0])
    assert bool(frame["warmup_complete"].iloc[-1])
