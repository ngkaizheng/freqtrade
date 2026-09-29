"""Phase C tests: the causal join, the hypothesis predicates, and the engine.

The predicates are tested against frames that deliberately violate the
conditions, because a predicate that returns True for everything is
indistinguishable from one that is correct until you look at how many bars it
claims.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.discovery_engine import (
    make_folds,
    net_return,
    trade_metrics,
)
from tools.strategy_factory_v2.hypotheses import EXPECTED_HYPOTHESIS_COUNT, HYPOTHESES
from tools.strategy_factory_v2.hypothesis_eval import HANDLERS, evaluate
from tools.strategy_factory_v2.joins import (
    causal_asof_join,
    future_leakage_violations,
    shift_events_backward,
    staleness_report,
)
from tools.strategy_factory_v2.phase_c import benjamini_hochberg, one_sided_p_value
from tools.strategy_factory_v2.spec import BASE_COST, STRESS_COST


# ---------------------------------------------------------------------------
# Causal join
# ---------------------------------------------------------------------------


def _events(n: int = 50, step_minutes: int = 5) -> pd.DataFrame:
    stamps = pd.date_range("2024-01-01", periods=n, freq=f"{step_minutes}min", tz="UTC")
    return pd.DataFrame({"timestamp": stamps, "value": np.arange(n, dtype=float)})


def test_causal_join_attaches_only_the_past() -> None:
    events = _events()
    signals = pd.Series(
        pd.date_range("2024-01-01 00:00", periods=30, freq="5min", tz="UTC")
    )
    join = causal_asof_join(signals, events, ["value"])
    assert future_leakage_violations(join)["violations"] == 0
    # A signal at 00:20 sees the observation at 00:20, not 00:25.
    row = join.frame.iloc[4]
    assert pd.Timestamp(row["source_timestamp"]) <= pd.Timestamp(row["signal_timestamp"])
    assert row["age_seconds"] >= 0


def test_causal_join_detects_a_backward_timestamp_rewrite() -> None:
    # The realistic leak: a sample re-stamped into the bar before it, which
    # leaves a positive age and defeats an age-only check.
    events = _events()
    leaked = shift_events_backward(events, minutes=60)
    signals = pd.Series(
        pd.date_range("2024-01-01 00:00", periods=30, freq="5min", tz="UTC")
    )
    join = causal_asof_join(
        signals, leaked, ["value"], truth_time_column="truth_timestamp"
    )
    report = future_leakage_violations(join)
    assert report["violations"] > 0
    assert report["truth_after_signal"] > 0
    assert report["min_age_seconds"] >= 0, (
        "the age is positive; only the truth check can see this leak"
    )


def test_causal_join_leaves_early_signals_unattached() -> None:
    events = _events(n=10, step_minutes=5)
    signals = pd.Series(
        pd.date_range("2023-12-31 23:00", periods=6, freq="5min", tz="UTC")
    )
    join = causal_asof_join(signals, events, ["value"])
    assert join.frame["value"].iloc[:10].isna().all(), (
        "a bar before the first observation must stay NaN, not borrow one"
    )


def test_causal_join_reports_staleness() -> None:
    events = _events(n=5, step_minutes=5)
    signals = pd.Series(
        pd.date_range("2024-01-01 00:00", periods=100, freq="5min", tz="UTC")
    )
    join = causal_asof_join(signals, events, ["value"])
    report = staleness_report(join, threshold_hours=0.1)
    assert report["exceeds_threshold"] > 0
    assert report["age_seconds_max"] > 0


def test_join_tolerates_mixed_timestamp_resolutions() -> None:
    # pandas 3 keeps whatever resolution the source carried, and merge_asof
    # refuses to join us against ns.
    events = _events(n=10)
    events["timestamp"] = events["timestamp"].astype("datetime64[us, UTC]")
    signals = pd.Series(
        pd.date_range("2024-01-01", periods=10, freq="5min", tz="UTC")
    )
    join = causal_asof_join(signals, events, ["value"])
    assert len(join.frame) == 10


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def _frame(n: int = 2000) -> pd.DataFrame:
    index = pd.RangeIndex(n)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
            "decision_time": pd.date_range("2024-01-01 01:00", periods=n, freq="1h", tz="UTC"),
            "trend_regime": ["NEUTRAL"] * n,
            "volatility_regime": ["NORMAL_VOL"] * n,
            "reference_trend_regime": ["NEUTRAL"] * n,
            "htf_trend_regime": ["NEUTRAL"] * n,
            "oi_change_288": np.zeros(n),
            "oi_percentile_288": np.full(n, 50.0),
            "oi_percentile": np.full(n, 50.0),
            "funding_rate_last": np.zeros(n),
            "funding_change": np.zeros(n),
            "funding_available": True,
            "funding_percentile": np.full(n, 50.0),
            "taker_imbalance": np.zeros(n),
            "taker_imbalance_percentile": np.full(n, 50.0),
            "taker_flow_available": True,
            "basis": np.zeros(n),
            "basis_percentile": np.full(n, 50.0),
            "basis_available": True,
            "volatility_percentile": np.full(n, 50.0),
            "range_ratio": np.ones(n),
            "volume_percentile": np.full(n, 50.0),
            "abs_ret_288": np.zeros(n),
            "relative_strength": np.zeros(n),
            "pullback_depth": np.ones(n),
        },
        index=index,
    )
    return frame


def test_every_family_has_a_predicate() -> None:
    families = {h.family for h in HYPOTHESES}
    assert families == set(HANDLERS), (
        f"families without a predicate: {sorted(families - set(HANDLERS))}; "
        f"predicates without a family: {sorted(set(HANDLERS) - families)}"
    )


def test_predicates_fire_on_a_flat_frame_only_where_that_is_correct() -> None:
    # A frame where nothing moves must not satisfy any condition that requires
    # a move. The one exception is a mean-reversion style gated to the NEUTRAL
    # regime: in a flat market "the regime is neutral" is genuinely true, and
    # the condition is about the state, not about there being a move to revert.
    frame = _frame()
    fired = [h.hypothesis_id for h in HYPOTHESES if bool(evaluate(h, frame).any())]
    allowed = {
        h.hypothesis_id
        for h in HYPOTHESES
        if h.family == "H15_regime_specific_activation"
        and h.thresholds.get("style") == "MEAN_REVERSION"
    }
    unexpected = sorted(set(fired) - allowed)
    assert not unexpected, f"these fired on a flat frame: {unexpected[:5]}"


def test_a_neutral_frame_does_not_satisfy_a_directional_condition() -> None:
    # Sanity check on the exception above: with an explicitly bullish regime,
    # the mean-reversion style must stop matching.
    frame = _frame()
    frame.loc[:, "trend_regime"] = "STRONG_UP"
    hypothesis = next(
        h for h in HYPOTHESES
        if h.family == "H15_regime_specific_activation"
        and h.thresholds.get("style") == "MEAN_REVERSION"
        and h.expected_direction == "short"
    )
    assert not evaluate(hypothesis, frame).any()


def test_trend_oi_predicate_requires_both_conditions() -> None:
    hypothesis = next(
        h for h in HYPOTHESES if h.family == "H1_trend_oi_confirmation"
        and h.expected_direction == "long" and h.timeframe == "1h"
    )
    frame = _frame()
    # Trend up, OI flat -> no.
    frame.loc[100:, "trend_regime"] = "STRONG_UP"
    assert not evaluate(hypothesis, frame).iloc[100:].any()
    # Add rising OI -> yes.
    frame["oi_change_288"] = 0.0
    frame.loc[100:, "oi_change_288"] = 5.0
    assert evaluate(hypothesis, frame).iloc[100:].all()


def test_btc_filter_predicate_requires_the_named_state() -> None:
    hypothesis = next(
        h for h in HYPOTHESES if h.family == "H13_btc_regime_filter"
        and h.expected_direction == "short" and h.timeframe == "1h"
        and h.thresholds.get("btc_state") == "STRONG_UP"
    )
    frame = _frame()
    frame.loc[:, "trend_regime"] = "STRONG_DOWN"
    frame.loc[:, "reference_trend_regime"] = "STRONG_UP"
    assert evaluate(hypothesis, frame).all()
    # The BTC state must be the named one, not merely bullish.
    frame.loc[:, "reference_trend_regime"] = "NEUTRAL"
    assert not evaluate(hypothesis, frame).any()


def test_volatility_shock_needs_actual_transition() -> None:
    hypothesis = next(
        h for h in HYPOTHESES if h.family == "H9_volatility_shock" and h.timeframe == "1h"
    )
    frame = _frame()
    frame["volatility_percentile"] = 95.0  # already high, never transitions
    assert not evaluate(hypothesis, frame).any()
    frame["volatility_percentile"] = np.concatenate(
        [np.full(500, 5.0), np.full(1500, 95.0)]
    )
    mask = evaluate(hypothesis, frame)
    assert mask.iloc[500]  # the bar where it crossed
    assert mask.sum() == 1, "a shock is a transition, not a state"


def test_missing_feature_yields_false_not_a_default() -> None:
    hypothesis = next(
        h for h in HYPOTHESES if h.family == "H1_trend_oi_confirmation"
    )
    frame = _frame().drop(columns=["oi_change_288"])
    mask = evaluate(hypothesis, frame)
    assert not mask.any()
    assert mask.dtype == bool


def test_evaluate_never_returns_nan() -> None:
    frame = _frame()
    frame.loc[100:200, "oi_change_288"] = np.nan
    for hypothesis in HYPOTHESES:
        mask = evaluate(hypothesis, frame)
        assert mask.dtype == bool, hypothesis.hypothesis_id
        assert not mask.isna().any(), hypothesis.hypothesis_id


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def test_net_return_is_worse_with_higher_costs() -> None:
    returns = pd.Series([0.01, -0.005, 0.002])
    funding = pd.Series(0.0, index=returns.index)
    base = net_return(returns, 1, BASE_COST, 12, funding)
    stress = net_return(returns, 1, STRESS_COST, 12, funding)
    assert (stress <= base).all()


def test_net_return_charges_funding_only_on_the_payer_side() -> None:
    returns = pd.Series([0.0])
    # A long with a positive (paying) rate is charged; a negative rate is a
    # credit and must be ignored under the conservative convention.
    charged = net_return(returns, 1, BASE_COST, 12, pd.Series([0.001]))
    credit = net_return(returns, 1, BASE_COST, 12, pd.Series([-0.001]))
    flat = net_return(returns, 1, BASE_COST, 12, pd.Series([0.0]))
    assert charged.iloc[0] < flat.iloc[0]
    assert abs(credit.iloc[0] - flat.iloc[0]) < 1e-15, (
        "a funding credit must not be allowed to create a rebate"
    )


def test_trade_metrics_report_an_empty_sample_honestly() -> None:
    stats = trade_metrics(pd.Series(dtype=float))
    assert stats["sample_count"] == 0
    assert stats["status"] == "INSUFFICIENT_SAMPLE"
    assert "mean_return" not in stats


def test_folds_never_overlap_the_holdout() -> None:
    # One fold needs train_days + validation_days; the frame must be long
    # enough or no fold exists and there is nothing to check.
    rows = 24 * 600
    frame = _frame(rows)
    frame["decision_time"] = pd.date_range("2020-01-01", periods=rows, freq="1h", tz="UTC")
    partition = H.DataPartition(
        development_start="2020-01-01 00:00:00+00:00",
        development_end="2025-01-01 00:00:00+00:00",
        validation_start="2025-01-01 00:00:00+00:00",
        validation_end="2025-06-01 00:00:00+00:00",
        holdout_start="2025-06-01 00:00:00+00:00",
        holdout_end="2026-01-01 00:00:00+00:00",
        latest_complete_day="2026-01-01",
    )
    frame = frame[frame["decision_time"] < pd.Timestamp(partition.validation_end)]
    folds = make_folds(frame)
    assert folds, "a five-year development region must contain folds"
    for fold in folds:
        assert fold["validation_end"] <= pd.Timestamp(partition.validation_end), (
            "a fold may not extend past the region it was built from"
        )
        assert fold["train_end"] < fold["validation_start"], "the embargo must be positive"
        assert fold["train_start"] < fold["train_end"]


# ---------------------------------------------------------------------------
# Multiple testing
# ---------------------------------------------------------------------------


def test_benjamini_hochberg_is_monotone_and_bounded() -> None:
    p_values = [0.001, 0.01, 0.02, 0.04, 0.5, 0.9]
    adjusted = benjamini_hochberg(p_values)
    assert len(adjusted) == len(p_values)
    assert all(0.0 <= v <= 1.0 for v in adjusted)
    assert all(adjusted[i] <= adjusted[i + 1] + 1e-12 for i in range(len(adjusted) - 1))
    assert all(a >= p for a, p in zip(adjusted, p_values, strict=True)), (
        "an adjusted p-value may never be smaller than its raw value"
    )


def test_benjamini_hochberg_handles_the_empty_case() -> None:
    assert benjamini_hochberg([]) == []


def test_benjamini_hochberg_rejects_a_flattering_correction() -> None:
    # With many tests, a p of 0.04 must not survive at alpha 0.05.
    p_values = [0.04] + [0.5] * 99
    adjusted = benjamini_hochberg(p_values)
    assert adjusted[0] > 0.05, (
        "a single 0.04 among a hundred tests is exactly what multiple testing "
        "is supposed to suppress"
    )


def test_one_sided_p_value_is_nan_for_tiny_samples() -> None:
    assert np.isnan(one_sided_p_value(3, 1.0))
    assert one_sided_p_value(500, 5.0) < 0.01
    assert one_sided_p_value(500, -5.0) > 0.99


# ---------------------------------------------------------------------------
# The registry did not move
# ---------------------------------------------------------------------------


def test_phase_c_did_not_add_or_remove_hypotheses() -> None:
    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT == 92


def test_no_survivor_gate_was_loosened() -> None:
    from tools.strategy_factory_v2.spec import SURVIVOR_CRITERIA

    assert SURVIVOR_CRITERIA["min_base_profit_factor"] == 1.05
    assert SURVIVOR_CRITERIA["min_stress_profit_factor"] == 1.00
    assert SURVIVOR_CRITERIA["max_single_fold_profit_share"] == 0.35
    assert SURVIVOR_CRITERIA["min_positive_fold_fraction"] == 0.60
    assert SURVIVOR_CRITERIA["min_oos_trades"] == 200
    assert SURVIVOR_CRITERIA["max_reality_check_p"] == 0.05
