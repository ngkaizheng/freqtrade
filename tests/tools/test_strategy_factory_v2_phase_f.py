"""Phase F tests: the post-hoc boundary, enforced rather than promised.

The failure mode this file exists to prevent is not a crash. It is a Phase F
run that succeeds, writes thirteen tidy artifacts, and quietly becomes the
reason a modified candidate gets a second look. Every test here is therefore
about a boundary: that the candidate cannot move, that the holdout cannot be
called untouched again, that a table cannot leave without its status, and that
the description of the failure is not quietly turned into a prescription.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import phase_f as F
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.spec import BASE_COST, SPEC_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _partition(unsealed: bool = True) -> DataPartition:
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


def _timeline() -> F.Timeline:
    return F.Timeline(frames={}, partition=_partition(), periods=F.region_periods(_partition()))


def _signals(n: int = 10, start: str = "2020-01-01", freq: str = "1h") -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "symbol": ["ETHUSDT"] * n,
            "decision_time": times,
            "raw_return": np.linspace(-0.01, 0.02, n),
            "funding_rate": np.full(n, 0.0001),
            "net_base": np.linspace(-0.011, 0.019, n),
            "net_stress": np.linspace(-0.016, 0.014, n),
        }
    )


# ---------------------------------------------------------------------------
# The post-hoc boundary
# ---------------------------------------------------------------------------


def test_the_status_is_post_hoc_and_selection_is_closed() -> None:
    assert F.ANALYSIS_STATUS == "POST_HOC_EXPLORATORY"
    assert F.CANDIDATE_SELECTION_ALLOWED is False
    assert F.POST_HOC_LABELS == ("POST_HOC", "EXPLORATORY", "NOT_FOR_CANDIDATE_SELECTION")


def test_every_table_carries_both_status_fields() -> None:
    table = F.stamp(pd.DataFrame({"expectancy": [1.0, -1.0]}))
    assert "analysis_status" in table.columns
    assert "candidate_selection_allowed" in table.columns
    assert set(table["analysis_status"]) == {"POST_HOC_EXPLORATORY"}
    assert set(table["candidate_selection_allowed"]) == {False}


def test_the_candidates_are_still_the_frozen_ones() -> None:
    hashes = F.assert_candidate_untouched()
    assert sorted(hashes) == sorted(F.CANDIDATE_IDS)
    for digest in hashes.values():
        assert isinstance(digest, str) and len(digest) == 64


def test_a_moved_candidate_stops_the_run() -> None:
    # The guard has to fail closed, not warn. A Phase F run that continued
    # after detecting a changed predicate would be auditing a different object
    # than the one that failed.
    original = F._phase_d_frozen_hashes
    F._phase_d_frozen_hashes = lambda: {F.PRIMARY_CANDIDATE: "0" * 64}
    try:
        F.assert_candidate_untouched()
    except F.PhaseFViolation as error:
        assert F.PRIMARY_CANDIDATE in str(error)
        return
    finally:
        F._phase_d_frozen_hashes = original
    raise AssertionError("a changed candidate logic hash must stop the run")


def test_the_horizon_has_not_drifted_between_phases() -> None:
    from tools.strategy_factory_v2 import phase_d, phase_e

    assert F.HORIZON == phase_d.HORIZON == phase_e.HORIZON == 12


def test_the_spec_version_is_unchanged() -> None:
    # Phase F is a diagnosis, not a new protocol. Bumping the spec version
    # would invalidate every run directory written before it.
    assert SPEC_VERSION == "2026-09-26-v2-regime-derivatives"


def test_phase_f_introduced_no_hypothesis() -> None:
    from tools.strategy_factory_v2.hypotheses import EXPECTED_HYPOTHESIS_COUNT, HYPOTHESES

    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT == 92
    assert "H16" not in "".join(h.hypothesis_id for h in HYPOTHESES)


# ---------------------------------------------------------------------------
# The holdout, already opened
# ---------------------------------------------------------------------------


def test_a_sealed_lock_refuses_the_postmortem() -> None:
    from tools.strategy_factory_v2 import holdout as H

    original = H.LOCK_FILE
    with tempfile.TemporaryDirectory() as tmp:
        H.LOCK_FILE = Path(tmp) / "lock.json"
        try:
            H.LOCK_FILE.write_text(
                json.dumps({"partition": _partition(unsealed=False).as_dict()}),
                encoding="utf-8",
            )
            try:
                F.load_unblinded_partition()
            except F.PhaseFViolation as error:
                assert "unsealing" in str(error)
                return
        finally:
            H.LOCK_FILE = original
    raise AssertionError("a sealed holdout must refuse a postmortem")


def test_an_unblinded_lock_opens_without_writing_a_new_event() -> None:
    from tools.strategy_factory_v2 import holdout as H

    original = H.LOCK_FILE
    with tempfile.TemporaryDirectory() as tmp:
        H.LOCK_FILE = Path(tmp) / "lock.json"
        try:
            H.LOCK_FILE.write_text(
                json.dumps(
                    {
                        "partition": _partition(unsealed=False).as_dict(),
                        "access_log": [{"opened_utc": "when"}],
                        "unblinded": {
                            "unsealed_utc": "2026-09-26T01:42:43+00:00",
                            "phase": "E (final holdout evaluation)",
                        },
                    }
                ),
                encoding="utf-8",
            )
            before = H.LOCK_FILE.read_text(encoding="utf-8")
            partition, access = F.load_unblinded_partition()
            after = H.LOCK_FILE.read_text(encoding="utf-8")
            assert partition.is_unsealed
            assert access["already_unblinded"] is True
            assert access["new_unseal_event_written"] is False
            # Writing a second unseal event would make the audit trail claim a
            # second opening that never happened.
            assert before == after
        finally:
            H.LOCK_FILE = original


def test_the_periods_do_not_overlap_and_do_not_gap() -> None:
    periods = F.region_periods(_partition())
    assert list(periods) == list(F.REGION_ORDER)
    for earlier, later in zip(F.REGION_ORDER, F.REGION_ORDER[1:]):
        assert periods[earlier][1] == periods[later][0], (earlier, later)
    assert periods["development"][0] == pd.Timestamp("2020-02-01 00:00:00+00:00")
    assert periods["final_holdout"][1] == pd.Timestamp("2026-08-31 23:00:00+00:00")


# ---------------------------------------------------------------------------
# Fixed buckets
# ---------------------------------------------------------------------------


def test_calendar_buckets_come_from_the_dates_not_the_results() -> None:
    months = F.calendar_months(pd.Timestamp("2020-02-01", tz="UTC"), pd.Timestamp("2026-08-31 23:00", tz="UTC"))
    assert months[0] == "2020-02"
    assert months[-1] == "2026-08"
    assert len(months) == 79 == len(set(months))
    assert F.calendar_years(pd.Timestamp("2020-02-01", tz="UTC"), pd.Timestamp("2026-08-31 23:00", tz="UTC")) == [
        2020, 2021, 2022, 2023, 2024, 2025, 2026
    ]


def test_the_rolling_window_is_fixed_before_it_is_used() -> None:
    assert F.ROLLING_WINDOW_DAYS == 180
    assert F.ROLLING_STEP_DAYS == 30
    # The function takes them as defaults, not as something it derived.
    import inspect

    signature = inspect.signature(F.rolling_metrics)
    assert signature.parameters["window_days"].default == F.ROLLING_WINDOW_DAYS
    assert signature.parameters["step_days"].default == F.ROLLING_STEP_DAYS


def test_a_window_straddling_a_boundary_is_labelled_spanning() -> None:
    timeline = _timeline()
    development = timeline.periods["development"]
    holdout = timeline.periods["final_holdout"]
    assert F._window_region(development[0], development[1], timeline) == "development"
    straddling_start = holdout[0] - pd.Timedelta(days=30)
    assert F._window_region(straddling_start, holdout[0] + pd.Timedelta(days=30), timeline) == "spanning"


def test_run_lengths_count_consecutive_signals() -> None:
    assert list(F.run_lengths([True, True, False, True])) == [2, 1]
    assert list(F.run_lengths([False, False])) == []
    assert list(F.run_lengths([])) == []


# ---------------------------------------------------------------------------
# The cost decomposition reconciles
# ---------------------------------------------------------------------------


def test_the_cost_split_adds_back_up_to_the_frozen_net_return() -> None:
    from tools.strategy_factory_v2.discovery_engine import net_return

    # Inside the development region, so the period split actually has rows.
    trades = _signals(50, start="2020-03-01")
    expected = net_return(
        trades["raw_return"], -1, BASE_COST, F.HORIZON, trades["funding_rate"]
    ).to_numpy()
    trades["net_base"] = expected
    table = F.cost_decomposition(trades, -1, _partition(), BASE_COST)
    F.assert_decomposition_reconciles(table)
    development = table[table["period"] == "development"]
    assert len(development) == 1
    row = development.iloc[0]
    total = (
        row["raw_expectancy"]
        + row["slippage_impact"]
        + row["fee_impact"]
        + row["funding_impact"]
    )
    assert abs(total - row["net_expectancy"]) < 1e-12


def test_a_decomposition_that_does_not_reconcile_is_refused() -> None:
    trades = _signals(20, start="2020-03-01")
    table = F.cost_decomposition(trades, -1, _partition(), BASE_COST)
    table["recomputed_net_max_abs_error"] = 0.5
    try:
        F.assert_decomposition_reconciles(table)
    except F.PhaseFViolation as error:
        assert "reconcile" in str(error)
        return
    raise AssertionError("a decomposition that does not add up must stop the run")


def test_the_fee_component_is_never_reduced_to_help_a_result() -> None:
    trades = _signals(20, start="2020-03-01")
    table = F.cost_decomposition(trades, -1, _partition(), BASE_COST)
    populated = table[table["trade_count"] > 0]
    assert len(populated) == 1
    # 2 x 5 bps, adverse, every signal. A different number here would mean the
    # frozen cost model had been quietly edited.
    for _, row in populated.iterrows():
        assert abs(row["fee_impact"] + 0.001) < 1e-12


# ---------------------------------------------------------------------------
# Drift labels
# ---------------------------------------------------------------------------


def test_the_drift_labels_are_the_five_the_plan_names() -> None:
    assert F.DRIFT_LABELS == ("STABLE", "DRIFTED", "DISAPPEARED", "INSUFFICIENT_DATA", "AMBIGUOUS")


def test_a_sign_flip_is_disappeared_not_drifted() -> None:
    assert F.label_drift(0.004, 0.005, -0.002, 10000, 2655) == "DISAPPEARED"


def test_a_collapse_to_a_fraction_of_the_development_value_is_disappeared() -> None:
    assert F.label_drift(0.004, 0.004, 0.0005, 10000, 2655) == "DISAPPEARED"


def test_a_moderate_move_is_drifted_and_a_small_one_is_stable() -> None:
    # 0.003 -> 0.004 is a 33% move, under the declared 50% threshold.
    assert F.label_drift(0.004, 0.004, 0.003, 10000, 2655) == "STABLE"
    # 0.004 -> 0.008 is a 100% move, over it.
    assert F.label_drift(0.004, 0.004, 0.008, 10000, 2655) == "DRIFTED"


def test_a_thin_sample_is_never_a_verdict() -> None:
    assert F.label_drift(0.004, 0.004, -0.01, 10, 2655) == "INSUFFICIENT_DATA"
    assert F.label_drift(0.004, 0.004, -0.01, 10000, 27) == "INSUFFICIENT_DATA"
    assert F.label_drift(None, None, None, 0, 0) == "INSUFFICIENT_DATA"


def test_a_zero_development_value_is_ambiguous_not_stable() -> None:
    assert F.label_drift(0.0, 0.0, 0.0001, 10000, 2655) == "AMBIGUOUS"


# ---------------------------------------------------------------------------
# Distribution distance
# ---------------------------------------------------------------------------


def test_identical_distributions_have_no_distance() -> None:
    rng = np.random.default_rng(7)
    sample = rng.normal(size=5000)
    assert F.standardized_wasserstein(sample, sample) == 0.0
    assert F.ks_distance(sample, sample) == 0.0


def test_a_shift_shows_up_in_both_distances() -> None:
    rng = np.random.default_rng(7)
    left = rng.normal(size=5000)
    right = rng.normal(loc=2.0, size=5000)
    assert F.standardized_wasserstein(left, right) > 1.0
    assert F.ks_distance(left, right) > 0.5


def test_a_constant_feature_has_no_standardized_distance() -> None:
    # Dividing by a zero spread would produce an infinite distance that means
    # nothing, so it is reported as missing rather than as an enormous shift.
    assert not np.isfinite(F.standardized_wasserstein(np.ones(100), np.ones(100)))


def test_a_distribution_row_reports_every_percentile_the_plan_names() -> None:
    row = F.distribution_row(np.arange(1.0, 101.0))
    for key in ("mean", "median", "std", "p10", "p25", "p50", "p75", "p90"):
        assert key in row and row[key] is not None
    assert F.distribution_row(np.array([]))["count"] == 0


# ---------------------------------------------------------------------------
# Structure of the outputs
# ---------------------------------------------------------------------------


def test_the_drift_feature_list_is_fixed_and_non_empty() -> None:
    names = [name for name, _column in F.DRIFT_FEATURES]
    assert len(names) == len(set(names))
    assert {"basis", "funding_rate_last", "open_interest_level", "price_return_24",
            "realized_vol_30", "mark_index_spread"} <= set(names)


def test_the_required_artifacts_are_the_thirteen_the_plan_names() -> None:
    from tools.strategy_factory_v2 import phase_f_report as R

    assert R.REQUIRED_OUTPUTS == (
        "postmortem_report.md",
        "postmortem_report.html",
        "period_metrics.csv",
        "rolling_metrics.csv",
        "feature_distribution_drift.csv",
        "regime_frequency.csv",
        "signal_frequency.csv",
        "symbol_period_matrix.csv",
        "cost_decomposition.csv",
        "holding_horizon_diagnostics.csv",
        "dependence_diagnostics.csv",
        "regime_attribution_posthoc.csv",
        "manifest.json",
    )


def test_a_missing_artifact_fails_the_phase() -> None:
    from tools.strategy_factory_v2 import phase_f_report as R

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for name in R.REQUIRED_OUTPUTS:
            (directory / name).write_text("", encoding="utf-8")
        R.assert_outputs_complete(directory)
        (directory / "cost_decomposition.csv").unlink()
        try:
            R.assert_outputs_complete(directory)
        except F.PhaseFViolation as error:
            assert "cost_decomposition.csv" in str(error)
            return
    raise AssertionError("a missing required artifact must fail the phase")


def test_the_symbol_matrix_is_fixed_and_keeps_every_symbol() -> None:
    trades = _signals(20, start="2020-01-01")
    matrix = F.symbol_period_matrix(trades, _timeline())
    assert len(matrix) == len(F.SYMBOLS) * len(F.REGION_ORDER) == 15
    assert set(matrix["symbol"]) == set(F.SYMBOLS)
    # BTC cannot confirm itself, so it is structurally empty rather than absent.
    btc = matrix[(matrix["symbol"] == "BTCUSDT") & (matrix["period"] == "development")]
    assert int(btc["trade_count"].iloc[0]) == 0


def test_the_attribution_table_refuses_to_call_the_filter_causal() -> None:
    source = _flatten("tools/strategy_factory_v2/phase_f.py")
    # A causal verb is allowed only inside an explicit negation. The docstring
    # saying that "basis drives the edge" is not a statement this phase may
    # make must not itself be mistaken for a causal claim.
    for index in [i for i in range(len(source)) if source.startswith("drives the edge", i)]:
        window = source[max(0, index - 90) : index + 60]
        assert "not" in window, f"unnegated causal language near: {window!r}"
    for banned in ("the filter causes", "regime causes", "regime filter drove"):
        assert banned not in source.lower(), banned


def test_the_cost_model_was_not_altered_for_this_phase() -> None:
    assert BASE_COST.fee_bps == 5.0
    assert BASE_COST.slippage_bps == 1.0
    assert BASE_COST.name == "base_taker"


# ---------------------------------------------------------------------------
# The direction-convention defect
# ---------------------------------------------------------------------------


def test_net_return_does_not_apply_the_registered_direction_to_the_return() -> None:
    """Pin the defect Phase F found, so it cannot be forgotten.

    ``net_return`` takes a ``side`` and uses it for slippage and for the funding
    clip -- but never multiplies the forward return by it. A hypothesis
    registered ``short`` is therefore measured on the *long* profit and loss.

    This test asserts the **defective** behaviour on purpose. It is the thing
    that makes the defect visible: if someone later fixes ``net_return``, this
    test fails and the retroactive invalidation of the Phase C/D/E numbers has
    to be dealt with deliberately rather than discovered later.
    """

    from tools.strategy_factory_v2.discovery_engine import net_return

    rising = pd.Series([0.10])
    long_side = net_return(rising, 1, BASE_COST, F.HORIZON, pd.Series([0.0]))
    short_side = net_return(rising, -1, BASE_COST, F.HORIZON, pd.Series([0.0]))
    # Both sides keep the sign of the raw price move, which is the defect.
    assert long_side.iloc[0] > 0
    assert short_side.iloc[0] > 0, (
        "if this now fails, net_return has started negating the return for a "
        "short. That is the fix -- and it retroactively invalidates every "
        "Phase C, D and E number, so it needs a new experiment id and a new "
        "preregistration, not a quiet patch."
    )


def test_the_forward_return_is_a_plain_price_return() -> None:
    from tools.strategy_factory_v2.features import forward_returns

    close = pd.Series([100.0, 110.0, 121.0])
    out = forward_returns(pd.DataFrame({"close": close}), (1,))
    assert abs(out["fwd_ret_1"].iloc[0] - 0.10) < 1e-12


def test_the_audit_marks_the_mirrored_column_as_not_a_candidate() -> None:
    trades = {
        F.PRIMARY_CANDIDATE: _signals(20, start="2020-01-01"),
        "H13_BTC_FILTER_1H_STRONG_UP_SHORT": _signals(5, start="2020-01-01"),
    }
    audit = F.direction_convention_audit(trades, _timeline())
    assert not audit.empty
    assert set(audit["registered_direction"]) <= {"long", "short"}
    assert (audit["is_candidate"] == False).all()  # noqa: E712
    assert (audit["promotion_allowed"] == False).all()  # noqa: E712
    # The mirrored column is exactly the sign flip, which is the whole point.
    for _, row in audit.iterrows():
        original = row["expectancy_under_the_engine_as_written"]
        mirrored = row["expectancy_under_the_mirrored_convention"]
        if original is not None and not pd.isna(original):
            assert abs(original + mirrored) < 1e-12


def _flatten(path: str) -> str:
    """Source text with runs of whitespace collapsed, for phrase checks.

    A banned-phrase test that trips over a line break is a test that gets
    deleted the first time someone reformats the file, which is the opposite of
    what it is for.
    """

    return " ".join(Path(path).read_text(encoding="utf-8").split())


def test_the_audit_names_the_defect_rather_than_softening_it() -> None:
    source = _flatten("tools/strategy_factory_v2/phase_f.py")
    assert "never multiplies the return by it" in source
    assert "not a candidate" in source
    assert "promoted" in source


def test_the_manifest_records_the_defect_and_its_non_fix() -> None:
    from tools.strategy_factory_v2 import phase_f_report as R

    source = _flatten("tools/strategy_factory_v2/phase_f_report.py")
    assert "engine_defect_found" in source
    assert "fixed_here" in source
    assert "mirrored_column_is_a_candidate" in source
    assert R.EXTRA_OUTPUTS[-2] == "direction_convention_audit.csv"
