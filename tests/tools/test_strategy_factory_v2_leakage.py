"""Phase B tests: causality and leakage proofs.

These are the tests that matter most. A feature engine that quietly reads the
future produces beautiful backtests and a worthless strategy, and the only
defence is an automated proof that runs before every experiment.

Two of these tests are *negative controls*: they inject a real lookahead bug
and assert that the probes catch it. Without them, a probe that passes
vacuously would look identical to a probe that passes honestly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import causality as C
from tools.strategy_factory_v2 import features as F
from tools.strategy_factory_v2 import regime as R
from tools.strategy_factory_v2.data import asof_join
from tools.strategy_factory_v2.features import build_features
from tools.strategy_factory_v2.regime import REGIME_COLUMNS, attach_reference_regime, classify


def _price(periods: int = 1200, seed: int = 3, trend: float = 0.0002) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="1h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(trend, 0.01, periods)))
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": np.abs(rng.normal(1000.0, 250.0, periods)) + 1.0,
        }
    )
    frame["decision_time"] = frame["date"] + pd.Timedelta(hours=1)
    return frame


def _funding(periods: int = 60) -> pd.DataFrame:
    times = pd.date_range("2024-01-01", periods=periods, freq="8h", tz="UTC")
    return pd.DataFrame(
        {
            "event_time": times,
            "settlement_time": times,
            "funding_rate": np.linspace(-0.0004, 0.0006, periods),
            "offset_ms": np.zeros(periods, dtype="int64"),
            "source": "synthetic",
        }
    )


def _oi(price: pd.DataFrame, seed: int = 9) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    values = 50_000.0 + np.cumsum(rng.normal(0.0, 200.0, len(price)))
    return pd.DataFrame({"timestamp": price["decision_time"].to_numpy(), "open_interest": values})


def _taker(price: pd.DataFrame, seed: int = 13) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(price)
    return pd.DataFrame(
        {
            "timestamp": price["decision_time"].to_numpy(),
            "taker_buy_volume": np.abs(rng.normal(100.0, 20.0, n)),
            "taker_sell_volume": np.abs(rng.normal(100.0, 20.0, n)),
        }
    )


def _kwargs() -> dict:
    price = _price()
    return dict(
        symbol="T/USDT:USDT",
        funding_events=_funding(),
        funding_interval_hours=8.0,
        open_interest_events=_oi(price),
        taker_events=_taker(price),
    )


# ---------------------------------------------------------------------------
# The honest path
# ---------------------------------------------------------------------------


def test_all_probes_pass_on_clean_data() -> None:
    price = _price()
    report = C.run_all_probes(price, "1h", reference_price=_price(seed=4), **_kwargs())
    assert report.passed, report.as_dict()["findings"][:3]
    assert report.rows_compared > 0
    assert "future_mutation_price" in report.checks
    assert "future_mutation_regime" in report.checks
    assert "future_mutation_cross_asset" in report.checks
    assert "cross_asset_alignment" in report.checks
    assert "forward_horizon_boundary" in report.checks


def test_probes_cover_both_price_and_derivatives_inputs() -> None:
    price = _price()
    report = C.probe_price_causality(price, "1h", **_kwargs())
    assert report.passed, report.as_dict()["findings"][:3]
    # The run must have swept the whole feature surface, not one column. A probe
    # that silently compared three numbers would pass just as happily.
    assert report.rows_compared > 30_000, report.rows_compared
    # And the inputs under test must include the derivatives streams, which is
    # the case only if they were actually attached.
    bundle = build_features(price, "1h", **_kwargs())
    assert bundle.frame["open_interest"].notna().any()
    assert bundle.frame["taker_imbalance"].notna().any()
    assert bundle.frame["funding_rate_last"].notna().any()


def test_forward_horizon_boundary_rejects_a_backfilled_horizon() -> None:
    price = _price(periods=200)
    honest = C.probe_forward_horizons(price, "1h", (12, 24))
    assert honest.passed


def test_forward_horizon_probe_catches_a_wrapped_horizon() -> None:
    price = _price(periods=200)
    # Simulate a wrapped horizon: the final rows get a value from the start.
    original = F.forward_returns

    def wrapped(frame, horizons):
        out = original(frame, horizons)
        for horizon in horizons:
            column = f"fwd_ret_{horizon}"
            out[column] = out[column].fillna(out[column].iloc[0])
        return out

    F.forward_returns = wrapped
    try:
        report = C.probe_forward_horizons(price, "1h", (12, 24))
    finally:
        F.forward_returns = original
    assert not report.passed, "a wrapped forward horizon must be detected"


# ---------------------------------------------------------------------------
# Negative control 1: a centred rolling window
# ---------------------------------------------------------------------------


def test_probe_catches_a_centred_rolling_window() -> None:
    original = F._trailing_rank
    R._trailing_rank = F._trailing_rank = (
        lambda series, window: series.rolling(window, min_periods=window, center=True).rank(pct=True)
        * 100.0
    )
    try:
        report = C.probe_price_causality(_price(), "1h", **_kwargs())
    finally:
        F._trailing_rank = original
        R._trailing_rank = original
    assert not report.passed, "a centred window peeks forward and must be caught"
    assert any(f.column == "volume_percentile" for f in report.findings)


# ---------------------------------------------------------------------------
# Negative control 2: a cross-asset join that reads one bar into the future
# ---------------------------------------------------------------------------


def test_probe_catches_a_cross_asset_lag_error() -> None:
    original = C.attach_reference_regime

    def leaky(frame, reference, reference_symbol="REF/USDT:USDT"):
        reference = classify(reference)
        shifted = reference.copy()
        shifted["decision_time"] = shifted["decision_time"] - pd.Timedelta(hours=1)
        right = shifted[["decision_time", *REGIME_COLUMNS, "trend_percentile"]].sort_values(
            "decision_time"
        )
        joined = asof_join(
            frame[["decision_time"]].reset_index(drop=True),
            right,
            "decision_time",
            "decision_time",
            "reference_",
        ).reset_index(drop=True)
        out = frame.copy().reset_index(drop=True)
        for name in REGIME_COLUMNS:
            out[f"reference_{name}"] = joined[f"reference_{name}"].to_numpy()
        out["reference_trend_percentile"] = np.asarray(
            pd.to_numeric(pd.Series(joined["reference_trend_percentile"]), errors="coerce"),
            dtype=float,
        )
        return out

    C.attach_reference_regime = leaky
    try:
        report = C.probe_cross_asset_causality(
            _price(), _price(seed=6), "1h", cut_fraction=0.6, **_kwargs()
        )
    finally:
        C.attach_reference_regime = original
    assert not report.passed, "a one-bar cross-asset lag must be caught"
    assert any(f.column.startswith("reference_") for f in report.findings)


# ---------------------------------------------------------------------------
# Negative control 3: a lookahead hidden in the reference's own features
# ---------------------------------------------------------------------------


def test_probe_catches_leakage_inside_the_reference_asset() -> None:
    original = R.classify

    def leaky_classify(frame):
        out = original(frame)
        # Peek one bar forward when labelling the reference.
        for name in REGIME_COLUMNS:
            out[name] = out[name].shift(-1).fillna(R.UNKNOWN)
        return out

    R.classify = leaky_classify
    try:
        report = C.probe_cross_asset_causality(
            _price(), _price(seed=6), "1h", cut_fraction=0.6, **_kwargs()
        )
    finally:
        R.classify = original
    assert not report.passed, "a reference labelled from the future must be caught"


# ---------------------------------------------------------------------------
# The mutation must actually be destructive
# ---------------------------------------------------------------------------


def test_mutation_changes_shape_not_just_scale() -> None:
    # A uniform rescale leaves returns, realised volatility and MA spreads
    # unchanged, so it would make the probe pass vacuously. The mutation has to
    # change the *shape* of the future.
    price = _price(periods=600)
    mutated = C._destroy_future(price, 400)
    before = price["close"].pct_change(24).iloc[:400]
    after = mutated["close"].pct_change(24).iloc[:400]
    assert np.allclose(before.to_numpy(), after.to_numpy(), equal_nan=True)
    assert not np.allclose(
        price["close"].iloc[400:].to_numpy(), mutated["close"].iloc[400:].to_numpy()
    )


def test_mutation_keeps_the_frame_a_valid_ohlcv_series() -> None:
    price = _price(periods=300)
    mutated = C._destroy_future(price, 200)
    assert (mutated["high"] >= mutated[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (mutated["low"] <= mutated[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (mutated["low"] > 0).all()
    assert (mutated["volume"] >= 0).all()


# ---------------------------------------------------------------------------
# The report contract
# ---------------------------------------------------------------------------


def test_failed_report_raises_loudly() -> None:
    report = C.CausalityReport()
    report.findings.append(C.CausalityFinding("check", "column", 0, "detail"))
    try:
        report.raise_if_failed()
    except C.LookaheadError as error:
        assert "causality violation" in str(error)
        return
    raise AssertionError("a failed causality report must raise")


def test_passing_report_does_not_raise() -> None:
    C.CausalityReport().raise_if_failed()


def test_short_frame_is_reported_not_silently_skipped() -> None:
    report = C.probe_price_causality(_price(periods=3), "1h")
    assert not report.passed
    assert report.findings and "too short" in report.findings[0].detail
