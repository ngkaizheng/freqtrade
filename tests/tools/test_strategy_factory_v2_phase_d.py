"""Phase D tests: freezing, the holdout guard, attribution, and uncertainty.

The guard tests are the important ones. A holdout that is only *believed* to be
untouched is worth nothing, so these assert that the guard actually fires.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.discovery_engine import trade_metrics
from tools.strategy_factory_v2.freeze import (
    HoldoutAccessViolation,
    HoldoutGuard,
    freeze_candidates,
    logic_hash,
    regime_control_mask,
    verify_freeze,
)
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.phase_d import (
    MIN_VALIDATION_SAMPLE,
    NO_SAMPLE,
    OPPOSITE,
    REPLICATED,
    classify_replication,
    missing_inputs,
)
from tools.strategy_factory_v2.uncertainty import (
    block_bootstrap_ci,
    effective_sample_size,
    uncertainty_report,
)

CANDIDATES = (
    "H13_BTC_FILTER_1H_STRONG_UP_SHORT",
    "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT",
)


def _partition() -> DataPartition:
    return DataPartition(
        development_start="2020-02-01 00:00:00+00:00",
        development_end="2025-06-06 22:12:00+00:00",
        validation_start="2025-06-06 22:12:00+00:00",
        validation_end="2025-11-18 22:12:00+00:00",
        holdout_start="2025-11-18 23:00:00+00:00",
        holdout_end="2026-08-31 23:00:00+00:00",
        latest_complete_day="2026-08-31",
    )


# ---------------------------------------------------------------------------
# Freeze
# ---------------------------------------------------------------------------


def test_freeze_records_a_hash_per_candidate() -> None:
    record = freeze_candidates(CANDIDATES)
    assert record["spec_version"]
    assert record["frozen_at"]
    assert record["optimization_permitted"] is False
    assert record["new_hypotheses_permitted"] is False
    assert len(record["candidates"]) == 2
    for entry in record["candidates"]:
        assert len(entry["logic_hash"]) == 64
        assert len(entry["source_hash"]) == 64
        assert entry["id"] in CANDIDATES


def test_freeze_survives_its_own_verification() -> None:
    record = freeze_candidates(CANDIDATES)
    result = verify_freeze(record, CANDIDATES)
    assert result["intact"], result["problems"]


def test_logic_hash_changes_when_a_threshold_changes() -> None:
    # The hash is only meaningful if it moves when the definition moves.
    import dataclasses

    from tools.strategy_factory_v2.hypotheses import get

    original = get(CANDIDATES[0])
    before = logic_hash(original)
    mutated = dataclasses.replace(
        original, thresholds={**original.thresholds, "btc_state": "NEUTRAL"}
    )
    assert logic_hash(mutated) != before


def test_freeze_check_detects_a_drifted_set() -> None:
    record = freeze_candidates(CANDIDATES)
    result = verify_freeze(record, (CANDIDATES[0],))
    assert not result["intact"]
    assert result["problems"]


def test_phase_d_evaluates_only_the_frozen_candidates() -> None:
    from tools.strategy_factory_v2.hypotheses import EXPECTED_HYPOTHESIS_COUNT, HYPOTHESES

    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT == 92
    assert all(candidate in {h.hypothesis_id for h in HYPOTHESES} for candidate in CANDIDATES)


# ---------------------------------------------------------------------------
# The holdout guard
# ---------------------------------------------------------------------------


def test_guard_allows_a_development_frame() -> None:
    guard = HoldoutGuard(partition=_partition())
    frame = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")}
    )
    guard.assert_no_holdout(frame)
    guard.assert_clean()
    assert guard.access_count == 0


def test_guard_allows_the_bar_closing_exactly_on_the_boundary() -> None:
    guard = HoldoutGuard(partition=_partition())
    frame = pd.DataFrame(
        {"date": pd.to_datetime(["2025-11-18 22:00:00+00:00"], utc=True)}
    )
    guard.assert_no_holdout(frame)
    assert guard.access_count == 0


def test_guard_fails_closed_on_a_holdout_read() -> None:
    guard = HoldoutGuard(partition=_partition())
    frame = pd.DataFrame(
        {"date": pd.date_range("2026-01-01", periods=10, freq="1h", tz="UTC")}
    )
    try:
        guard.assert_no_holdout(frame, context="unit-test")
    except HoldoutAccessViolation as error:
        assert "unit-test" in str(error)
        assert guard.access_count == 10, "the attempt must still be counted"
        assert guard.attempts and guard.attempts[0]["rows"] == 10
        return
    raise AssertionError("reading the holdout must abort the run")


def test_guard_assert_clean_fails_after_any_access() -> None:
    guard = HoldoutGuard(partition=_partition())
    guard.fail_closed = False  # let the read through so the end check can be tested
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-01-01"], utc=True)})
    guard.assert_no_holdout(frame)
    try:
        guard.assert_clean()
    except HoldoutAccessViolation as error:
        assert "expected 0" in str(error)
        return
    raise AssertionError("a non-zero access count must fail the end-of-run check")


def test_guard_log_reports_a_zero_count() -> None:
    guard = HoldoutGuard(partition=_partition())
    log = guard.log()
    assert log["final_holdout_access_count"] == 0
    assert log["attempts"] == []
    assert "sealed" in log["policy"]


# ---------------------------------------------------------------------------
# Missing inputs
# ---------------------------------------------------------------------------


def test_missing_inputs_detects_an_absent_reference_column() -> None:
    # A cross-asset candidate on a frame with no reference column is untestable,
    # not empty. Reporting it as zero is how a bug becomes a finding.
    frame = pd.DataFrame(
        {
            "trend_regime": ["NEUTRAL"] * 10,
            "reference_trend_regime": ["NEUTRAL"] * 10,
        }
    )
    discovery = type("D", (), {"frame": frame})()
    hypothesis = get(CANDIDATES[0])
    assert missing_inputs(hypothesis, {"BTCUSDT": discovery}) == []

    stripped = frame.drop(columns=["reference_trend_regime"])
    discovery.frame = stripped
    assert missing_inputs(hypothesis, {"BTCUSDT": discovery}) == ["reference_trend_regime"]


# ---------------------------------------------------------------------------
# Regime attribution control
# ---------------------------------------------------------------------------


def test_regime_control_removes_only_the_reference_clause() -> None:
    hypothesis = get(CANDIDATES[0])
    frame = pd.DataFrame(
        {
            "trend_regime": [
                "STRONG_DOWN", "WEAK_DOWN", "NEUTRAL", "STRONG_UP", "WEAK_UP", "NEUTRAL",
            ],
            "reference_trend_regime": ["STRONG_UP", "NEUTRAL", "NEUTRAL"] * 2,
        }
    )
    control = regime_control_mask(frame, hypothesis)
    # A short candidate's control is "the symbol's own trend is bearish",
    # regardless of what the reference is doing.
    assert control.tolist() == [True, True, False, False, False, False]


def test_regime_control_does_not_invent_a_different_direction() -> None:
    long_hypothesis = get("H13_BTC_FILTER_1H_STRONG_UP_LONG")
    frame = pd.DataFrame(
        {"trend_regime": ["STRONG_UP", "WEAK_UP", "STRONG_DOWN", "NEUTRAL"]}
    )
    control = regime_control_mask(frame, long_hypothesis)
    assert control.tolist() == [True, True, False, False]


def test_regime_control_reports_unavailable_rather_than_guessing() -> None:
    hypothesis = get(CANDIDATES[0])
    frame = pd.DataFrame({"something_else": [1, 2, 3]})
    try:
        regime_control_mask(frame, hypothesis)
    except H.HoldoutViolation as error:
        assert "REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE" in str(error)
        return
    raise AssertionError("a control that cannot be built must say so, not improvise")


# ---------------------------------------------------------------------------
# Replication classification
# ---------------------------------------------------------------------------


def test_replication_classification_separates_small_samples_from_failure() -> None:
    assert classify_replication(0.004, 0.005, 1340) == REPLICATED
    assert classify_replication(0.004, -0.002, 1340) == OPPOSITE
    # Three signals is not evidence of anything, in either direction.
    assert classify_replication(0.004, 0.02, 3) == NO_SAMPLE
    assert classify_replication(0.004, 0.005, MIN_VALIDATION_SAMPLE - 1) == NO_SAMPLE
    assert classify_replication(0.004, None, 1340) == NO_SAMPLE


def test_replication_is_descriptive_not_a_gate() -> None:
    # A negative validation expectancy on a thin sample is NO_SAMPLE, never FAIL.
    # There is no FAIL verdict anywhere in Phase D by design.
    for n in (1, 10, 50, 99):
        assert classify_replication(0.01, -0.05, n) == NO_SAMPLE
    assert classify_replication(0.01, -0.05, 100) == OPPOSITE


# ---------------------------------------------------------------------------
# Uncertainty
# ---------------------------------------------------------------------------


def test_effective_sample_size_shrinks_under_persistence() -> None:
    rng = np.random.default_rng(3)
    independent = rng.normal(0.0, 0.01, 4000)
    persistent = np.zeros(4000)
    for i in range(1, 4000):
        persistent[i] = 0.9 * persistent[i - 1] + rng.normal(0.0, 0.003)
    a = effective_sample_size(independent)
    b = effective_sample_size(persistent)
    assert a["effective_sample_size"] > 0.85 * a["n"], "independent data keeps its N"
    assert b["effective_sample_size"] < 0.35 * b["n"], (
        "persistent data must lose effective observations, or the standard "
        "error is understated and the evidence looks stronger than it is"
    )
    assert b["lag1_autocorrelation"] > 0.7


def test_uncertainty_report_shows_the_dependence_penalty() -> None:
    rng = np.random.default_rng(11)
    persistent = np.zeros(2000)
    for i in range(1, 2000):
        persistent[i] = 0.95 * persistent[i - 1] + rng.normal(0.002, 0.004)
    report = uncertainty_report(persistent)
    assert report["status"] == "OK"
    assert report["effective_sample_size"] < 0.2 * report["n"]
    assert abs(report["dependence_adjusted_t_stat"]) < abs(report["naive_t_stat"]), (
        "adjusting for dependence must reduce confidence, never raise it"
    )


def test_block_bootstrap_reports_an_interval_and_is_deterministic() -> None:
    rng = np.random.default_rng(5)
    values = rng.normal(0.001, 0.01, 1500)
    a = block_bootstrap_ci(values, draws=500, seed=7)
    b = block_bootstrap_ci(values, draws=500, seed=7)
    assert a["ci_low"] == b["ci_low"] and a["ci_high"] == b["ci_high"]
    assert a["ci_low"] < a["observed"] < a["ci_high"]
    assert a["block_length"] == 24 and a["draws"] == 500
    assert "block length" in a["note"].lower()


def test_block_bootstrap_refuses_a_tiny_sample() -> None:
    result = block_bootstrap_ci([0.1, -0.2, 0.3], draws=100)
    assert result["status"] == "INSUFFICIENT_SAMPLE"
    assert "ci_low" not in result
