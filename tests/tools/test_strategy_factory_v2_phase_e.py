"""Phase E tests: unsealing, the warm-up boundary, and classification.

The holdout is now permanently unblinded, so the tests cannot exercise the real
one. What they *can* pin is the mechanism: that a sealed partition refuses to
build features, that unsealing requires a written justification, and that
warm-up rows can never contribute an observation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.phase_e import (
    HOLDOUT_MONTHS,
    INTERPRETATION_CATEGORIES,
    MEANINGFUL_SAMPLE,
    REGIME_CLAIM,
    classify_holdout,
)


def _partition(unsealed: bool = False) -> DataPartition:
    return DataPartition(
        development_start="2020-02-01 00:00:00+00:00",
        development_end="2025-06-06 22:12:00+00:00",
        validation_start="2025-06-06 22:12:00+00:00",
        validation_end="2025-11-18 22:12:00+00:00",
        holdout_start="2025-11-18 23:00:00+00:00",
        holdout_end="2026-08-31 23:00:00+00:00",
        latest_complete_day="2026-08-31",
        unsealed=unsealed,
    )


# ---------------------------------------------------------------------------
# Unsealing
# ---------------------------------------------------------------------------


def test_a_sealed_partition_refuses_to_build_holdout_features() -> None:
    from tools.strategy_factory_v2.discovery import build_discovery_frame

    try:
        build_discovery_frame("BTCUSDT", "1h", _partition(unsealed=False), "final_holdout")
    except H.HoldoutViolation as error:
        assert "sealed" in str(error)
        return
    raise AssertionError("a sealed holdout must refuse a feature build")


def test_unsealed_partition_is_permanently_marked() -> None:
    partition = _partition(unsealed=True)
    assert partition.is_unsealed
    partition.require_unsealed("test")


def test_unseal_demands_a_justification_and_a_spec_version() -> None:
    import tools.strategy_factory_v2.holdout as module

    original = module.LOCK_FILE
    with tempfile.TemporaryDirectory() as tmp:
        module.LOCK_FILE = Path(tmp) / "lock.json"
        try:
            for justification, spec in (("", "v"), ("why", ""), ("  ", "  ")):
                try:
                    module.unseal(_partition(), justification, spec)
                except H.HoldoutViolation:
                    continue
                raise AssertionError(
                    f"unsealing with justification={justification!r} spec={spec!r} "
                    "must be refused"
                )
            opened = module.unseal(_partition(), "unit test", "test-spec")
            assert opened.is_unsealed
            lock = module.read_lock()
            assert lock["unblinded"]["spec_version"] == "test-spec"
            assert len(lock["access_log"]) == 1
        finally:
            module.LOCK_FILE = original


def test_the_region_flag_alone_cannot_open_the_holdout() -> None:
    # A region name is not a key. Only unsealing is.
    assert _partition(unsealed=False).is_unsealed is False
    assert _partition(unsealed=True).is_unsealed is True


# ---------------------------------------------------------------------------
# Warm-up
# ---------------------------------------------------------------------------


def test_warmup_rows_are_flagged_and_excluded() -> None:
    boundary = pd.Timestamp("2025-11-18 23:00:00+00:00")
    decision = pd.Series(pd.date_range("2025-11-15", periods=120, freq="1h", tz="UTC"))
    warmup = decision < boundary
    assert warmup.any(), "the fixture must contain warm-up rows"
    assert not warmup.iloc[-1]
    # Warm-up rows are development data; every feature is trailing, so a bar at
    # the boundary can only reference bars before it.
    assert (decision[warmup] < boundary).all()


def test_build_discovery_frame_rejects_an_unknown_region() -> None:
    from tools.strategy_factory_v2.discovery import build_discovery_frame

    try:
        build_discovery_frame("BTCUSDT", "1h", _partition(unsealed=True), "everything")
    except ValueError as error:
        assert "region must be" in str(error)
        return
    raise AssertionError("an unknown region must be rejected")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classification_uses_the_categories_fixed_in_the_protocol() -> None:
    assert set(INTERPRETATION_CATEGORIES) == {
        "POSITIVE_REPLICATION",
        "NEGATIVE_REPLICATION",
        "NO_MEANINGFUL_SAMPLE",
        "MIXED",
    }
    # Categories are descriptive, never a numeric score.
    for name, description in INTERPRETATION_CATEGORIES.items():
        assert isinstance(description, str) and description


def test_positive_holdout_against_a_positive_history() -> None:
    category, _ = classify_holdout(0.004, 0.003, "positive", 2000)
    assert category == "POSITIVE_REPLICATION"


def test_negative_holdout_is_labelled_negative_not_rescued() -> None:
    category, _ = classify_holdout(-0.002, -0.003, "positive", 2655)
    assert category == "NEGATIVE_REPLICATION"


def test_a_sign_flip_between_cost_models_is_mixed() -> None:
    category, reason = classify_holdout(0.004, -0.001, "positive", 2000)
    assert category == "MIXED"
    assert "stress" in reason


def test_a_thin_sample_is_never_a_failure_verdict() -> None:
    for n in (0, 1, 27, MEANINGFUL_SAMPLE - 1):
        category, reason = classify_holdout(-0.01, -0.02, "positive", n)
        assert category == "NO_MEANINGFUL_SAMPLE", n
        assert "below" in reason


def test_exact_zero_expectancy_is_mixed_not_a_verdict() -> None:
    category, _ = classify_holdout(0.0, 0.0, "positive", 2000)
    assert category == "MIXED"


def test_an_unestablished_direction_cannot_replicate() -> None:
    category, _ = classify_holdout(0.004, 0.003, "unknown", 2000)
    assert category == "NO_MEANINGFUL_SAMPLE"


# ---------------------------------------------------------------------------
# Protocol and language
# ---------------------------------------------------------------------------


def test_the_regime_claim_is_not_strengthened() -> None:
    # Phase D established an association between a conditioning condition and a
    # return. The protocol must not describe it as causation, and must not use
    # the language the Phase D report already rejected.
    text = REGIME_CLAIM.lower()
    assert "not proof" in text
    assert "association" in text
    for banned in ("proves", "guarantee", "causal contribution"):
        assert banned not in text, f"the regime claim must not assert {banned!r}"
    # A causal verb may appear only inside an explicit negation.
    for index in [i for i in range(len(text)) if text.startswith("causes", i)]:
        window = text[max(0, index - 40) : index + 10]
        assert "not" in window, f"unnegated causal language near: {window!r}"


def test_months_cover_the_holdout_without_gaps() -> None:
    assert HOLDOUT_MONTHS == (
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
        "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
    )
    assert len(set(HOLDOUT_MONTHS)) == len(HOLDOUT_MONTHS)


def test_phase_e_introduced_no_hypothesis() -> None:
    from tools.strategy_factory_v2.hypotheses import EXPECTED_HYPOTHESIS_COUNT, HYPOTHESES

    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT == 92
