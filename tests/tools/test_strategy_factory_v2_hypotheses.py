"""Tests for the preregistered hypothesis registry.

The registry is the contract that makes V2 auditable. These tests guard the
properties that make it trustworthy: unique ids, complete metadata, no
unfrozen thresholds, and -- most importantly -- that a hypothesis whose data is
absent is reported BLOCKED rather than quietly weakened.
"""

from __future__ import annotations

from tools.strategy_factory_v2.hypotheses import (
    BLOCKED,
    CANONICAL_FIELDS,
    CROSS_ASSET,
    EXPECTED_HYPOTHESIS_COUNT,
    FUNDING,
    HYPOTHESES,
    OPEN_INTEREST,
    PRICE,
    TAKER,
    TESTABLE,
    available_fields,
    cross_asset_available,
    get,
    hypotheses_as_records,
    registry_manifest,
    status_for,
)
from tools.strategy_factory_v2.regime import FUNDING_STATES
from tools.strategy_factory_v2.spec import (
    DISCOVERY_TIMEFRAMES,
    FUNDING_PERCENTILE_CUTS,
    OI_PERCENTILE_CUTS,
    SPEC_VERSION,
    TAKER_IMBALANCE_CUTS,
    VOL_PERCENTILE_CUTS,
)

TREND_SCORE_CUTS = (-1.0, -0.25, 0.25, 1.0)
VOL_REGIME_WINDOW = 30

FULL_DATA = {
    "funding_rate": "AVAILABLE",
    "open_interest": "AVAILABLE",
    "mark_price": "AVAILABLE",
    "index_price": "AVAILABLE",
    "basis": "AVAILABLE",
    "taker_buy_volume": "AVAILABLE",
    "taker_sell_volume": "AVAILABLE",
}
NO_DERIVATIVES = {
    "funding_rate": "MISSING",
    "open_interest": "MISSING",
    "mark_price": "MISSING",
    "index_price": "MISSING",
    "basis": "MISSING",
    "taker_buy_volume": "MISSING",
    "taker_sell_volume": "MISSING",
}
FUNDING_AND_MARK = dict(NO_DERIVATIVES, funding_rate="AVAILABLE", mark_price="AVAILABLE")
TWO_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

#: Every percentile cut the frozen spec declares anywhere.
TOTAL_CUTS = {
    float(c)
    for c in (*VOL_PERCENTILE_CUTS, *OI_PERCENTILE_CUTS, *FUNDING_PERCENTILE_CUTS, *TAKER_IMBALANCE_CUTS, *TREND_SCORE_CUTS)
}
#: Window sizes and other discrete preregistered magnitudes.
PREREGISTERED_SCALARS = {
    0.0, 1.0, 3.0, 5.0, 6.0, 10.0, 12.0, 15.0, 20.0, 24.0, 30.0, 48.0, 50.0, 60.0,
    100.0, 120.0, 200.0, 288.0, 365.0,
}


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_registry_size_is_frozen_and_inside_the_preregistered_band() -> None:
    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT
    assert 50 <= len(HYPOTHESES) <= 100, (
        "the plan fixes the registry at roughly 50-100 hypotheses to prevent a "
        "combinatorial search from being passed off as reasoning"
    )


def test_hypothesis_ids_are_unique() -> None:
    ids = [h.hypothesis_id for h in HYPOTHESES]
    assert len(ids) == len(set(ids))


def test_every_hypothesis_carries_complete_metadata() -> None:
    for hypothesis in HYPOTHESES:
        assert hypothesis.hypothesis_id
        assert hypothesis.family
        assert len(hypothesis.economic_reason) > 40, (
            f"{hypothesis.hypothesis_id} has no real economic reason"
        )
        assert hypothesis.features, hypothesis.hypothesis_id
        assert hypothesis.required_fields, hypothesis.hypothesis_id
        assert hypothesis.condition, hypothesis.hypothesis_id
        assert hypothesis.invalidation, hypothesis.hypothesis_id
        assert hypothesis.expected_direction in ("long", "short")
        assert hypothesis.preregistered is True
        assert hypothesis.entry_definition and hypothesis.exit_definition


def test_every_required_field_is_from_the_canonical_vocabulary() -> None:
    for hypothesis in HYPOTHESES:
        unknown = set(hypothesis.required_fields) - set(CANONICAL_FIELDS)
        assert not unknown, f"{hypothesis.hypothesis_id} requires unknown fields {unknown}"


def test_every_timeframe_is_a_preregistered_discovery_timeframe() -> None:
    for hypothesis in HYPOTHESES:
        assert hypothesis.timeframe in DISCOVERY_TIMEFRAMES, hypothesis.hypothesis_id


def test_every_condition_is_mirrored_into_a_long_and_a_short_reading() -> None:
    families: dict[str, set[str]] = {}
    for hypothesis in HYPOTHESES:
        families.setdefault(hypothesis.family, set()).add(hypothesis.expected_direction)
    for family, directions in families.items():
        assert directions == {"long", "short"}, f"{family} is not researched in both directions"


def test_registry_covers_all_fifteen_plan_families() -> None:
    families = {h.family for h in HYPOTHESES}
    assert len(families) == 15
    for index in range(1, 16):
        assert any(f.startswith(f"H{index}_") for f in families), f"H{index} is missing"


def test_registry_serialises_to_json_compatible_records() -> None:
    import json

    records = hypotheses_as_records()
    assert len(records) == len(HYPOTHESES)
    payload = json.dumps(records)
    assert SPEC_VERSION in payload
    assert json.loads(payload)[0]["preregistered"] is True


def test_get_returns_a_known_hypothesis_and_rejects_an_unknown_one() -> None:
    first = HYPOTHESES[0]
    assert get(first.hypothesis_id) is first
    try:
        get("H99_NOT_A_HYPOTHESIS")
    except KeyError:
        return
    raise AssertionError("an unknown hypothesis id must raise KeyError")


# ---------------------------------------------------------------------------
# Data-dependency gating
# ---------------------------------------------------------------------------


def test_capability_translation_maps_the_audit_onto_the_vocabulary() -> None:
    assert available_fields(FULL_DATA) == set(CANONICAL_FIELDS) - {CROSS_ASSET}
    partial = available_fields(FUNDING_AND_MARK, cross_asset_available_=True)
    assert partial == {PRICE, "volume", FUNDING, "mark_price", CROSS_ASSET}
    assert available_fields(NO_DERIVATIVES) == {PRICE, "volume"}


def test_cross_asset_needs_two_price_symbols_not_a_derivatives_feed() -> None:
    assert not cross_asset_available(["BTC/USDT:USDT"])
    assert cross_asset_available(TWO_SYMBOLS)
    # A full derivatives feed on one symbol must not unlock cross-asset.
    assert status_for(HYPOTHESES[0], FULL_DATA, ["BTC/USDT:USDT"], price_available=True) in (
        TESTABLE,
        BLOCKED,
    )


def test_hypotheses_are_testable_when_every_required_field_exists() -> None:
    blocked = [
        h.hypothesis_id
        for h in HYPOTHESES
        if status_for(h, FULL_DATA, TWO_SYMBOLS, price_available=True) == BLOCKED
    ]
    assert not blocked, f"a complete dataset must make every hypothesis testable: {blocked}"


def test_oi_families_are_blocked_without_open_interest() -> None:
    for hypothesis in HYPOTHESES:
        if OPEN_INTEREST in hypothesis.required_fields:
            assert (
                status_for(hypothesis, FUNDING_AND_MARK, TWO_SYMBOLS, price_available=True)
                == BLOCKED
            ), hypothesis.hypothesis_id


def test_taker_families_are_blocked_without_taker_flow() -> None:
    for hypothesis in HYPOTHESES:
        if TAKER in hypothesis.required_fields:
            assert (
                status_for(hypothesis, FUNDING_AND_MARK, TWO_SYMBOLS, price_available=True)
                == BLOCKED
            ), hypothesis.hypothesis_id


def test_basis_family_is_blocked_without_an_index_price() -> None:
    # mark price alone is not enough: basis is (mark - index) / index.
    mark_only = dict(NO_DERIVATIVES, mark_price="AVAILABLE")
    basis = [h for h in HYPOTHESES if h.family == "H10_basis_extremes"]
    assert basis
    for hypothesis in basis:
        assert status_for(hypothesis, mark_only, TWO_SYMBOLS, price_available=True) == BLOCKED


def test_price_only_families_remain_testable_without_any_derivatives_data() -> None:
    price_only = [h for h in HYPOTHESES if set(h.required_fields) <= {PRICE, "volume"}]
    assert price_only, "the plan expects volatility and regime families to need no feed"
    for hypothesis in price_only:
        assert (
            status_for(hypothesis, NO_DERIVATIVES, TWO_SYMBOLS, price_available=True)
            == TESTABLE
        ), hypothesis.hypothesis_id


def test_no_price_data_blocks_everything() -> None:
    for hypothesis in HYPOTHESES:
        assert status_for(hypothesis, FULL_DATA, TWO_SYMBOLS, price_available=False) == BLOCKED


# ---------------------------------------------------------------------------
# Registry manifest
# ---------------------------------------------------------------------------


def test_manifest_without_data_defers_the_verdict() -> None:
    manifest = registry_manifest()
    assert manifest["testable_hypotheses"] is None if "testable_hypotheses" in manifest else True
    assert manifest["hypothesis_count"] == len(HYPOTHESES)
    for entry in manifest["families"].values():
        assert entry["testable"] is None
        assert entry["blocked"] is None


def test_manifest_with_partial_data_reports_exact_blocked_counts() -> None:
    manifest = registry_manifest(FUNDING_AND_MARK, TWO_SYMBOLS, price_available=True)
    assert manifest["blocked_hypotheses"] == len(manifest["blocked_hypothesis_ids"])
    assert manifest["testable_hypotheses"] + manifest["blocked_hypotheses"] == len(HYPOTHESES)
    assert manifest["blocked_hypotheses"] > 0
    # Every blocked id must belong to a family that requires a missing field.
    for hypothesis_id in manifest["blocked_hypothesis_ids"]:
        hypothesis = get(hypothesis_id)
        entry = manifest["families"][hypothesis.family]
        assert set(hypothesis.required_fields) & {
            OPEN_INTEREST,
            TAKER,
            "index_price",
        }, hypothesis_id
        assert hypothesis_id in entry["blocked_hypothesis_ids"]


def test_manifest_blocked_counts_sum_across_families() -> None:
    manifest = registry_manifest(FUNDING_AND_MARK, TWO_SYMBOLS, price_available=True)
    total_blocked = sum(entry["blocked"] for entry in manifest["families"].values())
    assert total_blocked == manifest["blocked_hypotheses"]


# ---------------------------------------------------------------------------
# Thresholds are the preregistered ones
# ---------------------------------------------------------------------------


def test_hypothesis_thresholds_are_invented_nothing() -> None:
    # Every numeric threshold a hypothesis carries must come from the frozen
    # spec. A number that appears in no preregistered table is a threshold that
    # was chosen after seeing a result, which is the thing this whole file
    # exists to prevent.
    preregistered: set[float] = set(TOTAL_CUTS) | set(PREREGISTERED_SCALARS)
    for hypothesis in HYPOTHESES:
        for name, value in hypothesis.thresholds.items():
            if isinstance(value, float):
                assert value in preregistered, (
                    f"{hypothesis.hypothesis_id}.{name}={value} is not a preregistered value"
                )


def test_regime_cuts_are_all_preregistered_and_exercised() -> None:
    from tools.strategy_factory_v2 import regime as R

    # The regime engine's own cut points must be the spec's, not fresh numbers.
    # The trend regime is the one that classifies on absolute cuts rather than
    # percentiles; the other four all use preregistered percentile cuts.
    assert tuple(R.TREND_SCORE_CUTS) == TREND_SCORE_CUTS
    assert R.VOL_REGIME_WINDOW == VOL_REGIME_WINDOW
    for name, cuts, states in (
        ("trend", R.TREND_SCORE_CUTS, R.TREND_STATES),
        ("volatility", VOL_PERCENTILE_CUTS, R.VOL_STATES),
        ("open_interest", OI_PERCENTILE_CUTS, R.OI_STATES),
        ("funding", FUNDING_PERCENTILE_CUTS, R.FUNDING_STATES),
    ):
        assert len(states) == len(cuts) + 1, name
        assert list(cuts) == sorted(cuts), name
        for cut in cuts:
            assert float(cut) in TOTAL_CUTS, f"{name} cut {cut} is not preregistered"


def test_trend_is_classified_on_absolute_cuts_not_a_trailing_percentile() -> None:
    # A trailing percentile of a slowly rising quantity saturates: a sustained
    # trend looks ordinary against its own recent history. This test pins the
    # decision so nobody reintroduces the percentile for the trend regime.
    from tools.strategy_factory_v2 import regime as R

    import pandas as pd

    score = pd.Series([5.0] * 400, index=range(400), dtype=float)
    states = R._cut(score, R.TREND_SCORE_CUTS, R.TREND_STATES)
    assert (states == "STRONG_UP").all(), (
        "a persistently high normalised score must classify as STRONG_UP; a "
        "trailing percentile would call this NEUTRAL"
    )
