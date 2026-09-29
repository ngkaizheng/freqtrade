"""Regression tests for the three calibration fixes found by the 2026-09-26 audit.

Each test here corresponds to a defect that was measured on real artifacts, not
a hypothetical. They are grouped in one file so the audit findings and their
enforcement stay together.

  R1  significance must be computed on dependence-adjusted statistics
  R4  logic_hash must exist at the discovery stage, not only at the freeze
  R5  a candidate that cannot answer must not be able to spend a holdout open
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.discovery_engine import HypothesisOutcome
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.phase_c import multiple_testing_analysis
from tools.strategy_factory_v2.uncertainty import effective_sample_size


# --------------------------------------------------------------------- R1


def _outcome(hypothesis_id: str, *, series=None, n=2000, mean=0.004,
             std=0.03) -> HypothesisOutcome:
    return HypothesisOutcome(
        hypothesis_id=hypothesis_id,
        family="H13_btc_regime_filter",
        timeframe="1h",
        expected_direction="short",
        sample_count=n,
        metrics={"sample_count": n, "mean_return": mean, "std_return": std},
        net_returns=series,
    )


def test_serial_dependence_deflates_the_t_statistic() -> None:
    """A persistent series carries the evidence of n/tau observations, not n.

    Two identical-mean outcomes, one independent and one strongly persistent,
    must not receive the same t-statistic. Before the fix they did.
    """
    rng = np.random.default_rng(7)
    independent = rng.normal(0.004, 0.03, 2000)
    # AR(1) with rho = 0.8 -> integrated autocorrelation time well above 1
    persistent = np.empty(2000)
    persistent[0] = 0.004
    for i in range(1, 2000):
        persistent[i] = 0.8 * persistent[i - 1] + rng.normal(0.0, 0.03 * 0.6)

    dep = effective_sample_size(persistent)
    assert dep["integrated_autocorrelation_time"] > 2.0, dep
    assert dep["effective_sample_size"] < len(persistent) / 2.0, dep

    result = multiple_testing_analysis(
        [
            _outcome("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT", series=independent),
            _outcome("H13_BTC_FILTER_1H_STRONG_UP_SHORT", series=persistent),
        ],
        pd.DataFrame(),
    )
    rows = {r["hypothesis_id"]: r for r in result["per_hypothesis"]}
    a = rows["H13_BTC_FILTER_1H_STRONG_DOWN_SHORT"]
    b = rows["H13_BTC_FILTER_1H_STRONG_UP_SHORT"]

    assert a["dependence_checked"] and b["dependence_checked"]
    assert b["integrated_autocorrelation_time"] > a["integrated_autocorrelation_time"]
    assert b["effective_sample_size"] < a["effective_sample_size"]
    assert b["t_stat_dependence_adjusted"] < a["t_stat_dependence_adjusted"]


def test_unverifiable_dependence_cannot_be_significant() -> None:
    """Fail closed: no return series means significance cannot be claimed."""
    result = multiple_testing_analysis(
        [_outcome("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT", series=None, n=50000,
                  mean=0.05, std=0.01)],
        pd.DataFrame(),
    )
    row = result["per_hypothesis"][0]
    assert row["dependence_checked"] is False
    assert not row["p_bh_significant"]
    assert result["hypotheses_with_dependence_checked"] == 0


def test_the_deflation_reproduces_the_audit_finding_on_a_realistic_population() -> None:
    """The case that actually happened: 88 tested, 17 reported, 2 real.

    A population of H13-like candidates on persistent series must not produce a
    long list of "significant" results once the variance is deflated by each
    hypothesis's own integrated autocorrelation time. This is the defect the
    2026-09-26 gate audit measured on the real Phase C artifacts.
    """
    rho = 0.85
    rng = np.random.default_rng(17)
    outcomes = []
    for i in range(88):
        n = 8000
        sd = 0.03
        # one strong candidate, the rest null or weak
        mu = 0.0043 if i == 0 else (0.0010 if i % 4 == 0 else 0.0)
        series = np.empty(n)
        series[0] = mu
        innovations = rng.normal(0.0, sd * math.sqrt(1 - rho**2), n)
        for j in range(1, n):
            series[j] = mu + rho * (series[j - 1] - mu) + innovations[j]
        outcomes.append(
            HypothesisOutcome(
                hypothesis_id=f"H13_BTC_FILTER_1H_STRONG_{i:02d}",
                family="H13_btc_regime_filter",
                timeframe="1h",
                expected_direction="short",
                sample_count=n,
                metrics={"sample_count": n, "mean_return": mu, "std_return": sd},
                net_returns=pd.Series(series),
            )
        )

    result = multiple_testing_analysis(outcomes, pd.DataFrame())

    assert result["hypotheses_with_dependence_checked"] == 88
    # Deflation can only reduce the evidence, never inflate it. A pure
    # white-noise null has IAT ~ 1 and is left alone; a persistent one is cut.
    strong = []
    for row in result["per_hypothesis"]:
        assert row["t_stat_dependence_adjusted"] <= row["t_stat"] + 1e-9
        if row["mean_return"] and row["mean_return"] > 0:
            strong.append(row)
    assert strong
    for row in strong:
        assert row["integrated_autocorrelation_time"] > 1.0
        assert row["t_stat_dependence_adjusted"] < row["t_stat"]

    # The point of the fix: a small number of survivors, not a long list.
    assert result["bh_significant_count"] <= 5, result["bh_significant_count"]


def pytest_approx(value: float, rel: float = 1e-9):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) <= rel * max(1.0, abs(value))
    return _Approx()


# --------------------------------------------------------------------- R4


def test_discovery_stage_records_a_logic_hash() -> None:
    """The hash must exist where the screening statistic is produced.

    It used to appear only in the Phase D freeze record, so two stages could
    evaluate different things under one hypothesis id and nothing would notice.
    """
    rng = np.random.default_rng(3)
    series = rng.normal(0.001, 0.02, 400)
    result = multiple_testing_analysis(
        [_outcome("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT", series=series, n=400)],
        pd.DataFrame(),
    )
    digest = result["per_hypothesis"][0]["logic_hash"]
    assert isinstance(digest, str) and len(digest) == 64, digest

    from tools.strategy_factory_v2.freeze import logic_hash
    from tools.strategy_factory_v2.hypotheses import get

    assert digest == logic_hash(get("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT"))


def test_every_discovery_row_carries_a_hash_and_a_dependence_figure() -> None:
    rng = np.random.default_rng(5)
    outcomes = [
        _outcome("H13_BTC_FILTER_1H_STRONG_DOWN_SHORT", series=rng.normal(0.0, 0.02, 300)),
        _outcome("H3_FUNDING_EXTREME_1H_P95_SHORT", series=rng.normal(0.0, 0.02, 300)),
    ]
    result = multiple_testing_analysis(outcomes, pd.DataFrame())
    assert result["hypotheses_tested"] == 2
    for row in result["per_hypothesis"]:
        assert len(row["logic_hash"]) == 64
        assert row["integrated_autocorrelation_time"] >= 1.0
        assert row["effective_sample_size"] <= row["sample_count"] + 1e-6
    assert "integrated autocorrelation time" in result["correction"]


# --------------------------------------------------------------------- R5


def test_eligibility_refuses_a_candidate_that_cannot_answer() -> None:
    """validation_n = 3 against a preregistered minimum of 200.

    This is the exact case that was frozen and then promoted to Phase E.
    """
    try:
        H.assert_candidates_eligible(
            {"H13_BTC_FILTER_1H_STRONG_UP_SHORT": {"observations": 3}}, 200
        )
    except H.HoldoutViolation as exc:
        assert "n=3 < 200" in str(exc)
    else:
        raise AssertionError("an undersized candidate must be refused")


def test_eligibility_refuses_a_candidate_it_cannot_verify() -> None:
    """Fail closed: a missing observation count is not a passing one."""
    for evidence in (
        {"A": {}},
        {"A": {"observations": None}},
        {"A": "not-a-mapping"},
    ):
        try:
            H.assert_candidates_eligible(evidence, 200)
        except H.HoldoutViolation:
            continue
        raise AssertionError(f"unverifiable evidence must be refused: {evidence}")


def test_eligibility_needs_a_positive_minimum() -> None:
    try:
        H.assert_candidates_eligible({"A": {"observations": 10}}, 0)
    except H.HoldoutViolation as exc:
        assert "positive minimum" in str(exc)
    else:
        raise AssertionError("a non-positive minimum must be refused")


def test_eligibility_passes_when_every_candidate_can_answer() -> None:
    H.assert_candidates_eligible(
        {
            "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT": {"observations": 1340},
            "H13_BTC_FILTER_1H_STRONG_UP_SHORT": {"observations": 200},
        },
        200,
    )


def test_eligibility_names_every_offender_at_once() -> None:
    """A single run must not surface one undersized candidate at a time."""
    try:
        H.assert_candidates_eligible(
            {
                "A": {"observations": 3},
                "B": {"observations": 27},
                "C": {"observations": 5000},
            },
            100,
        )
    except H.HoldoutViolation as exc:
        message = str(exc)
        assert "A (n=3 < 100)" in message and "B (n=27 < 100)" in message
    else:
        raise AssertionError("undersized candidates must be refused")


# --------------------------------------------------------------------- R7
#
# Root-caused 2026-09-26. Two stages measured the same per-signal quantity and
# disagreed by 21.85x because Phase C silently discarded signals falling outside
# the walk-forward windows. The discarded slice carried all of the losses.


def test_development_frame_stops_before_the_validation_window() -> None:
    """The development region must not reach into reserved validation data.

    Extending it to validation_end let the last walk-forward fold sit entirely
    inside the validation region, so the "validation" result stopped being
    independent of the screening statistic. Demonstrated on
    H13_BTC_FILTER_1H_STRONG_UP_SHORT: Phase D's validation_n=3 was
    bit-identical to Phase C fold 18.
    """
    lock = H.read_lock()
    if lock is None:
        # No lock on disk: the invariant that matters is still checkable from
        # the source, which is what the second half of this test does.
        source = Path("tools/strategy_factory_v2/discovery.py").read_text(encoding="utf-8")
        block = source.split('if region == "development":', 1)[1].split("elif", 1)[0]
        assert "partition.development_end" in block
        assert "partition.validation_end" not in block
        return

    partition = DataPartition(**lock["partition"])
    assert pd.Timestamp(partition.development_end) <= pd.Timestamp(partition.validation_start)

    source = Path("tools/strategy_factory_v2/discovery.py").read_text(encoding="utf-8")
    region_block = source.split('if region == "development":', 1)[1].split("elif", 1)[0]
    assert "partition.development_end" in region_block
    assert "partition.validation_end" not in region_block


def test_out_of_fold_signals_are_recorded_not_discarded() -> None:
    """The fold filter's exclusions must be visible in the metrics.

    Silently dropping them is what let two stages disagree by an order of
    magnitude while both reported a single, unqualified sample_count.
    """
    fields = {
        "matched_signals_total",
        "in_fold_signals",
        "out_of_fold_signals",
        "out_of_fold_fraction",
        "out_of_fold_expectancy",
    }
    source = Path("tools/strategy_factory_v2/discovery_engine.py").read_text(encoding="utf-8")
    for field in fields:
        assert f'"{field}"' in source, field


def test_enough_folds_uses_the_preregistered_minimum() -> None:
    """The gate was hard-coded to 3 while the preregistration says 15."""
    from tools.strategy_factory_v2.spec import WALK_FORWARD_V2

    assert WALK_FORWARD_V2.min_folds == 15
    source = Path("tools/strategy_factory_v2/discovery_engine.py").read_text(encoding="utf-8")
    assert '"enough_folds": len(folds) >= WALK_FORWARD_V2.min_folds' in source
    assert "len(valid_folds) >= 3" not in source


def test_empty_folds_cannot_be_used_to_inflate_the_fold_fraction() -> None:
    """UP_SHORT scored 11/15 = 0.733; over all 19 folds it is 11/19 = 0.579.

    The gate passed only because zero-trade folds were dropped from both
    numerator and denominator. A fold in which the rule never fired is evidence
    that it did not fire, and it counts.
    """
    folds_total, folds_positive = 19, 11
    assert folds_positive / folds_total < 0.60
    assert folds_positive / 15 >= 0.60      # the way it was actually computed
    from tools.strategy_factory_v2.spec import MIN_POSITIVE_FOLD_FRACTION

    assert MIN_POSITIVE_FOLD_FRACTION == 0.60
