"""Phase B tests: the deterministic regime engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.features import build_features
from tools.strategy_factory_v2.regime import (
    FUNDING_STATES,
    LIQUIDITY_STATES,
    OI_STATES,
    REGIME_COLUMNS,
    TREND_SCORE_CUTS,
    TREND_STATES,
    UNKNOWN,
    VOL_STATES,
    _cut,
    attach_reference_regime,
    classify,
    market_state,
    regime_distribution,
    trend_score,
)
from tools.strategy_factory_v2.spec import (
    FUNDING_PERCENTILE_CUTS,
    LIQUIDITY_PERCENTILE_CUTS,
    OI_PERCENTILE_CUTS,
    VOL_PERCENTILE_CUTS,
)


def _price(periods: int = 2000, seed: int = 5, trend: float = 0.0002) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="1h", tz="UTC")
    rng = np.random.default_rng(seed)
    steps = rng.normal(trend, 0.01, periods)
    close = 100.0 * np.exp(np.cumsum(steps))
    volume = np.abs(rng.normal(1000.0, 300.0, periods)) + 1.0
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": volume,
        }
    )
    frame["decision_time"] = frame["date"] + pd.Timedelta(hours=1)
    return frame


def _percentile_series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=range(len(values)), dtype=float)


# ---------------------------------------------------------------------------
# The bucketing primitive
# ---------------------------------------------------------------------------


def test_cut_requires_one_more_label_than_cut_point() -> None:
    try:
        _cut(_percentile_series([50.0]), (20.0, 80.0), ("A", "B"))
    except ValueError as error:
        assert "inconsistent" in str(error)
        return
    raise AssertionError("mismatched cuts and labels must raise")


def test_cut_assigns_states_in_preregistered_bands() -> None:
    # Four states, three cuts, so four probe values -- one inside each band.
    series = _percentile_series([10.0, 50.0, 85.0, 99.0])
    result = _cut(series, VOL_PERCENTILE_CUTS, VOL_STATES)
    assert result.tolist() == list(VOL_STATES)
    # Band edges are inclusive on the lower side.
    assert _cut(_percentile_series([20.0]), VOL_PERCENTILE_CUTS, VOL_STATES).iloc[0] == "NORMAL_VOL"
    assert _cut(_percentile_series([19.9]), VOL_PERCENTILE_CUTS, VOL_STATES).iloc[0] == "LOW_VOL"


def test_cut_maps_nan_to_unknown_not_to_a_middle_bucket() -> None:
    series = _percentile_series([float("nan"), 50.0])
    result = _cut(series, VOL_PERCENTILE_CUTS, VOL_STATES)
    assert result.iloc[0] == UNKNOWN
    assert result.iloc[1] == "NORMAL_VOL"


def test_every_regime_has_exactly_one_more_state_than_cut() -> None:
    pairs = (
        (TREND_SCORE_CUTS, TREND_STATES),
        (VOL_PERCENTILE_CUTS, VOL_STATES),
        (LIQUIDITY_PERCENTILE_CUTS, LIQUIDITY_STATES),
        (OI_PERCENTILE_CUTS, OI_STATES),
        (FUNDING_PERCENTILE_CUTS, FUNDING_STATES),
    )
    for cuts, states in pairs:
        assert len(states) == len(cuts) + 1, (cuts, states)
        assert list(cuts) == sorted(cuts), "cuts must be ascending"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classify_produces_all_five_regime_columns() -> None:
    bundle = build_features(_price(), "1h", symbol="T/USDT:USDT")
    regimes = classify(bundle.frame)
    for column in REGIME_COLUMNS:
        assert column in regimes.columns
    # regex=False: "+" is a quantifier, not a literal separator.
    assert regimes["market_state"].str.contains("+", regex=False).all()


def test_classify_only_emits_declared_states_or_unknown() -> None:
    regimes = classify(build_features(_price(), "1h").frame)
    allowed = {
        "trend_regime": set(TREND_STATES) | {UNKNOWN},
        "volatility_regime": set(VOL_STATES) | {UNKNOWN},
        "liquidity_regime": set(LIQUIDITY_STATES) | {UNKNOWN},
        "oi_regime": set(OI_STATES) | {UNKNOWN},
        "funding_regime": set(FUNDING_STATES) | {UNKNOWN},
    }
    for column, states in allowed.items():
        assert set(regimes[column].unique()) <= states, column


def test_open_interest_regime_is_unknown_when_the_data_is_absent() -> None:
    regimes = classify(build_features(_price(), "1h").frame)
    # The whole point: an absent feed must not masquerade as OI_NORMAL.
    assert (regimes["oi_regime"] == UNKNOWN).all()
    assert (regimes["oi_percentile_trail"].isna()).all()


def test_trend_regime_distinguishes_an_uptrend_from_a_downtrend() -> None:
    up = classify(build_features(_price(seed=1, trend=0.004), "1h").frame)
    down = classify(build_features(_price(seed=2, trend=-0.004), "1h").frame)
    up_bullish = (up["trend_regime"].isin(["STRONG_UP", "WEAK_UP"])).mean()
    down_bullish = (down["trend_regime"].isin(["STRONG_UP", "WEAK_UP"])).mean()
    up_bearish = (up["trend_regime"].isin(["STRONG_DOWN", "WEAK_DOWN"])).mean()
    down_bearish = (down["trend_regime"].isin(["STRONG_DOWN", "WEAK_DOWN"])).mean()
    # The classifier must separate direction, not merely react to volatility.
    assert up_bullish > up_bearish, f"uptrend read as {up_bullish:.1%} bullish vs {up_bearish:.1%}"
    assert down_bearish > down_bullish, f"downtrend read as {down_bearish:.1%} bearish vs {down_bullish:.1%}"
    # A strong drift must dominate, not merely tilt. The bar is a wide margin
    # over the opposite reading, not a majority of bars: the score is noisy
    # bar-to-bar and the trailing percentile is meant to stay calibrated.
    assert up_bullish > 3.0 * max(up_bearish, 0.01), f"only {up_bullish:.1%} bullish"
    assert down_bearish > 3.0 * max(down_bullish, 0.01), f"only {down_bearish:.1%} bearish"


def test_trend_score_is_scale_invariant() -> None:
    # Multiplying every price by a constant must not change the regime: the
    # score is built from ratios, which is what makes symbols comparable.
    frame = _price(seed=7)
    scaled = frame.copy()
    for column in ("open", "high", "low", "close"):
        scaled[column] = scaled[column] * 17.0
    a = trend_score(build_features(frame, "1h").frame).dropna()
    b = trend_score(build_features(scaled, "1h").frame).dropna()
    assert np.allclose(a.to_numpy(), b.to_numpy(), rtol=1e-9, atol=1e-12)


def test_regime_is_stable_under_mutation_of_the_future() -> None:
    frame = _price(periods=2000)
    cut = 1500
    baseline = classify(build_features(frame, "1h").frame)
    mutated = frame.copy()
    block = mutated.iloc[cut:].copy()
    block[["open", "high", "low", "close"]] = block[["open", "high", "low", "close"]].iloc[::-1] * 2.0
    mutated.iloc[cut:] = block
    result = classify(build_features(mutated, "1h").frame)
    for column in ("trend_regime", "volatility_regime", "liquidity_regime", "trend_percentile"):
        assert baseline[column].iloc[:cut].equals(
            result[column].iloc[:cut]
        ), f"{column} changed when only the future changed"


def test_market_state_is_the_ordered_concatenation() -> None:
    regimes = classify(build_features(_price(), "1h").frame)
    row = regimes.iloc[500]
    expected = "+".join(str(row[name]) for name in REGIME_COLUMNS)
    assert row["market_state"] == expected
    assert market_state(regimes).iloc[500] == expected


def test_regime_distribution_sums_to_one() -> None:
    regimes = classify(build_features(_price(), "1h").frame)
    distribution = regime_distribution(regimes)
    for column in REGIME_COLUMNS:
        assert abs(distribution[distribution["regime"] == column]["share"].sum() - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Cross-asset
# ---------------------------------------------------------------------------


def test_reference_regime_uses_only_the_past_of_the_reference() -> None:
    subject = build_features(_price(periods=1200, seed=1), "1h").frame
    reference = build_features(_price(periods=1200, seed=2, trend=-0.003), "1h").frame
    attached = attach_reference_regime(subject, reference, "REF/USDT:USDT")
    expected = pd.merge_asof(
        attached[["decision_time"]].sort_values("decision_time"),
        reference.assign(**{name: classify(reference)[name] for name in REGIME_COLUMNS})[
            ["decision_time", *REGIME_COLUMNS]
        ].sort_values("decision_time"),
        on="decision_time",
        direction="backward",
    )
    for name in REGIME_COLUMNS:
        attached_values = attached[f"reference_{name}"].to_numpy()
        expected_values = expected[name].to_numpy()
        comparable = expected_values.astype(str) != UNKNOWN
        assert (attached_values[comparable].astype(str) == expected_values[comparable].astype(str)).all(), name


def test_reference_regime_requires_a_join_key() -> None:
    subject = build_features(_price(periods=400), "1h").frame.drop(columns=["decision_time"])
    reference = classify(build_features(_price(periods=400), "1h").frame)
    try:
        attach_reference_regime(subject, reference)
    except ValueError as error:
        assert "decision_time" in str(error)
        return
    raise AssertionError("a missing join key must raise, not silently return UNKNOWN")
