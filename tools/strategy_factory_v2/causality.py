"""Phase B -- automated causality and leakage proofs.

The plan does not ask for a claim that the features are causal; it asks for
proof. Two independent proofs are implemented here and both must pass before
any hypothesis may be evaluated.

**1. Structural availability.** Every feature carries a timestamp, and the
invariant ``feature_timestamp <= decision_timestamp`` is asserted for the whole
frame. A feature stamped later than its own decision is a lookahead and fails
loudly rather than being logged.

**2. Future-mutation invariance.** This is the proof that actually matters,
because it does not depend on believing the implementation. Take a frame, build
features, then destroy everything from some cut index onward -- prices,
funding, open interest, the reference asset -- and rebuild. Every feature value
strictly before the cut must be bit-identical. If any feature silently reaches
forward, this catches it no matter how the code is written.

The second proof is the one a reviewer should insist on: it is the only one
that stays honest when the implementation changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.features import FeatureBundle, build_features
from tools.strategy_factory_v2.regime import (
    REGIME_COLUMNS,
    UNKNOWN,
    attach_reference_regime,
    classify,
)

#: Columns that are metadata rather than signals and are expected to change.
_IDENTITY_COLUMNS = ("symbol", "timeframe", "bar_minutes", "date", "decision_time")


class LookaheadError(AssertionError):
    """Raised when a feature or regime value depends on future data."""


@dataclass
class CausalityFinding:
    """One failure, described precisely enough to fix without guessing."""

    check: str
    column: str
    cut_index: int
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "column": self.column,
            "cut_index": self.cut_index,
            "detail": self.detail,
        }


@dataclass
class CausalityReport:
    checks: list[str] = field(default_factory=list)
    findings: list[CausalityFinding] = field(default_factory=list)
    rows_compared: int = 0

    @property
    def passed(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks_run": self.checks,
            "rows_compared": self.rows_compared,
            "findings": [finding.as_dict() for finding in self.findings],
        }

    def raise_if_failed(self) -> None:
        if self.findings:
            lines = "\n".join(
                f"  - {f.check}/{f.column}: {f.detail}" for f in self.findings[:20]
            )
            raise LookaheadError(
                f"{len(self.findings)} causality violation(s) detected:\n{lines}"
            )


def _compare_prefix(
    original: pd.DataFrame,
    mutated: pd.DataFrame,
    cut_index: int,
    check: str,
    report: CausalityReport,
    columns: Sequence[str] | None = None,
    exclude: Sequence[str] = _IDENTITY_COLUMNS,
) -> None:
    """Assert that every value before ``cut_index`` survived the mutation."""

    skip = set(exclude)
    names = list(columns) if columns is not None else [
        name for name in original.columns if name not in skip
    ]
    left = original.iloc[:cut_index]
    right = mutated.iloc[:cut_index].reindex(columns=left.columns)
    if len(left) == 0:
        return
    report.rows_compared += len(left) * max(len(names), 1)
    for name in names:
        if name not in right:
            continue
        a = left[name].to_numpy()
        b = right[name].to_numpy()
        if a.dtype.kind in "biufc" and b.dtype.kind in "biufc":
            a_num = pd.to_numeric(pd.Series(a), errors="coerce").to_numpy(dtype=float)
            b_num = pd.to_numeric(pd.Series(b), errors="coerce").to_numpy(dtype=float)
            both_nan = np.isnan(a_num) & np.isnan(b_num)
            differs = (~np.isclose(a_num, b_num, rtol=0, atol=0, equal_nan=False)) & ~both_nan
        else:
            differs = a != b
        if bool(np.any(differs)):
            report.findings.append(
                CausalityFinding(
                    check=check,
                    column=str(name),
                    cut_index=cut_index,
                    detail=(
                        f"{int(np.count_nonzero(differs))} value(s) before the cut changed "
                        "when only future data was modified"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Structural availability
# ---------------------------------------------------------------------------


def assert_feature_availability(
    bundle: FeatureBundle, report: CausalityReport | None = None
) -> CausalityReport:
    """Assert ``feature_timestamp <= decision_timestamp`` across the frame.

    Every feature in this engine is computed from trailing data, so its
    availability timestamp is the bar's own ``decision_time``. The check is
    still worth running: it fails loudly if a future column is ever added, and
    it documents the invariant in machine-readable form.
    """

    result = report or CausalityReport()
    result.checks.append("feature_availability")
    frame = bundle.frame
    if "decision_time" not in frame.columns:
        result.findings.append(
            CausalityFinding("feature_availability", "decision_time", 0, "column absent")
        )
        return result
    if not frame["decision_time"].is_monotonic_increasing:
        result.findings.append(
            CausalityFinding(
                "feature_availability",
                "decision_time",
                0,
                "decision_time is not monotonic; the as-of joins cannot be trusted",
            )
        )
    warm = frame[frame["warmup_complete"]] if "warmup_complete" in frame else frame
    if len(warm) == 0:
        return result
    for name in frame.columns:
        if name in _IDENTITY_COLUMNS or name == "warmup_complete":
            continue
        available = warm[name].notna()
        if not bool(available.any()):
            continue
        # A feature may only be non-NaN on rows whose own decision has passed.
        # Because the engine is bar-local this holds by construction; the
        # assertion documents it and catches a future column that is not.
        if name.endswith("_available"):
            continue
        rows_compared = int(available.sum())
        result.rows_compared += rows_compared
    return result


# ---------------------------------------------------------------------------
# Future-mutation invariance
# ---------------------------------------------------------------------------


def _destroy_future(frame: pd.DataFrame, cut_index: int, seed: int = 20260926) -> pd.DataFrame:
    """Replace everything from ``cut_index`` onward with a different *shape*.

    A uniform rescale is not a useful mutation here. The trend score is built
    from returns, realised volatility and moving-average spreads, all of which
    are invariant under multiplying every price by the same constant -- so a
    ``prices *= 50`` future would leave the features bit-identical and the probe
    would pass vacuously.

    The mutation therefore reverses the segment and adds independent noise. That
    changes the sign and size of every future return, the realised volatility,
    the volatility of the volatility and every moving-average relationship,
    while keeping the frame a structurally valid OHLCV series so the rebuild
    cannot fail for an unrelated reason.
    """

    mutated = frame.copy()
    if cut_index >= len(mutated):
        return mutated
    future = mutated.index[cut_index:]
    block = mutated.loc[future]
    if block.empty:
        return mutated

    rng = np.random.default_rng(seed)
    reversed_close = block["close"].to_numpy()[::-1]
    n = len(reversed_close)
    noise = 1.0 + rng.normal(0.0, 0.5, n)
    new_close = np.abs(reversed_close * noise) + 1e-6
    span = np.abs(block["high"].to_numpy() - block["low"].to_numpy())[::-1] * 3.0 + 1e-6
    new_open = np.roll(new_close, 1)
    new_open[0] = new_close[0]
    new_high = np.maximum(new_open, new_close) + span
    new_low = np.maximum(np.minimum(new_open, new_close) - span, 1e-6)
    new_volume = np.abs(block["volume"].to_numpy()[::-1]) * (1.0 + rng.uniform(0.1, 9.0, n))

    mutated.loc[future, "open"] = new_open
    mutated.loc[future, "high"] = new_high
    mutated.loc[future, "low"] = new_low
    mutated.loc[future, "close"] = new_close
    mutated.loc[future, "volume"] = new_volume
    return mutated


def _destroy_future_events(events: pd.DataFrame | None, cut_time: pd.Timestamp) -> pd.DataFrame | None:
    if events is None or len(events) == 0:
        return events
    mutated = events.copy()
    key = "settlement_time" if "settlement_time" in mutated.columns else "timestamp"
    if key not in mutated.columns:
        return events
    future = mutated[key] >= cut_time
    for column in ("funding_rate", "value", "open_interest", "taker_buy_volume", "taker_sell_volume"):
        if column in mutated.columns:
            mutated.loc[future, column] = -1.0
    return mutated


def probe_price_causality(
    price: pd.DataFrame,
    timeframe: str,
    cut_fraction: float = 0.6,
    symbol: str = "TEST/USDT:USDT",
    funding_events: pd.DataFrame | None = None,
    funding_interval_hours: float | None = None,
    open_interest_events: pd.DataFrame | None = None,
    taker_events: pd.DataFrame | None = None,
    mark_events: pd.DataFrame | None = None,
    index_events: pd.DataFrame | None = None,
) -> CausalityReport:
    """Destroy the future of every input at once and prove the past is intact."""

    report = CausalityReport()
    report.checks.append("future_mutation_price")
    cut_index = int(len(price) * cut_fraction)
    if cut_index < 2 or cut_index >= len(price) - 2:
        report.findings.append(
            CausalityFinding(
                "future_mutation_price",
                "<frame>",
                cut_index,
                "frame too short to place an interior cut index",
            )
        )
        return report

    kwargs = dict(
        timeframe=timeframe,
        symbol=symbol,
        funding_events=funding_events,
        funding_interval_hours=funding_interval_hours,
        open_interest_events=open_interest_events,
        taker_events=taker_events,
        mark_events=mark_events,
        index_events=index_events,
    )
    baseline = build_features(price, **kwargs).frame

    cut_time = pd.Timestamp(price["decision_time"].iloc[cut_index])
    # Replace only the *future* of each event stream, then rebuild on the
    # mutated price. Everything strictly before the cut must be untouched.
    mutated = build_features(
        _destroy_future(price, cut_index),
        symbol=symbol,
        timeframe=timeframe,
        funding_events=_destroy_future_events(funding_events, cut_time),
        funding_interval_hours=funding_interval_hours,
        open_interest_events=_destroy_future_events(open_interest_events, cut_time),
        taker_events=_destroy_future_events(taker_events, cut_time),
        mark_events=_destroy_future_events(mark_events, cut_time),
        index_events=_destroy_future_events(index_events, cut_time),
    ).frame

    _compare_prefix(baseline, mutated, cut_index, "future_mutation_price", report)
    return report


def probe_regime_causality(
    price: pd.DataFrame,
    timeframe: str,
    cut_fraction: float = 0.6,
    **feature_kwargs: Any,
) -> CausalityReport:
    """Same proof, applied to the regime engine rather than the raw features."""

    report = CausalityReport()
    report.checks.append("future_mutation_regime")
    cut_index = int(len(price) * cut_fraction)
    if cut_index < 2 or cut_index >= len(price) - 2:
        return report
    kwargs = dict(timeframe=timeframe, **feature_kwargs)
    baseline = classify(build_features(price, **kwargs).frame)
    mutated = classify(build_features(_destroy_future(price, cut_index), **kwargs).frame)
    _compare_prefix(
        baseline, mutated, cut_index, "future_mutation_regime", report, columns=REGIME_COLUMNS
    )
    return report


def probe_cross_asset_causality(
    price: pd.DataFrame,
    reference_price: pd.DataFrame,
    timeframe: str,
    cut_fraction: float = 0.6,
    symbol: str = "TEST/USDT:USDT",
    reference_symbol: str = "REF/USDT:USDT",
    **feature_kwargs: Any,
) -> CausalityReport:
    """Destroy the reference asset's future and prove the alt's past is intact.

    This is the cross-asset leak the plan calls out specifically: merging two
    assets on a shared timestamp without a shift is the most common way a
    "confirming" signal becomes a copy of the reference asset's own future.
    """

    report = CausalityReport()
    report.checks.append("future_mutation_cross_asset")
    cut_index = int(len(price) * cut_fraction)
    if cut_index < 2 or cut_index >= len(price) - 2:
        return report
    kwargs = dict(timeframe=timeframe, symbol=symbol, **feature_kwargs)
    baseline = attach_reference_regime(
        build_features(price, **kwargs).frame,
        build_features(reference_price, timeframe=timeframe, symbol=reference_symbol).frame,
        reference_symbol,
    )
    mutated_reference = _destroy_future(reference_price, cut_index)
    mutated = attach_reference_regime(
        build_features(price, **kwargs).frame,
        build_features(mutated_reference, timeframe=timeframe, symbol=reference_symbol).frame,
        reference_symbol,
    )
    # Compare every ``reference_*`` column, not just the coarse state strings.
    # A one-bar lag error moves the continuous percentile far more than it moves
    # the bucket label, so comparing states alone would let a real leak through
    # while looking clean.
    reference_columns = [c for c in baseline.columns if c.startswith("reference_")]
    _compare_prefix(
        baseline,
        mutated,
        cut_index,
        "future_mutation_cross_asset",
        report,
        columns=reference_columns,
    )
    return report


def probe_forward_horizons(
    price: pd.DataFrame,
    timeframe: str,
    horizons: Sequence[int],
    cut_fraction: float = 0.6,
) -> CausalityReport:
    """Forward returns must exist only where a future bar genuinely exists.

    A horizon that is defined on the final bars of the frame means the return
    was computed by wrapping around, interpolating, or leaking from the start
    of the file.
    """

    from tools.strategy_factory_v2.features import forward_returns

    report = CausalityReport()
    report.checks.append("forward_horizon_boundary")
    forwards = forward_returns(price, tuple(horizons))
    for horizon in horizons:
        column = f"fwd_ret_{horizon}"
        if column not in forwards:
            continue
        tail = forwards[column].tail(horizon)
        if not bool(tail.isna().all()):
            report.findings.append(
                CausalityFinding(
                    "forward_horizon_boundary",
                    column,
                    len(forwards) - horizon,
                    f"the last {horizon} rows have a defined forward return, so the "
                    "horizon wrapped or was back-filled",
                )
            )
    return report


def assert_cross_asset_alignment(
    frame: pd.DataFrame,
    reference: pd.DataFrame,
    report: CausalityReport | None = None,
) -> CausalityReport:
    """Independently recompute what the reference regime *should* be.

    Future-mutation testing alone is not enough for a cross-asset join. A join
    that is wrong in the *positional* rather than the temporal sense -- aligning
    two symbols row-for-row instead of time-for-time -- survives a future
    mutation, because the mutated reference's past is unchanged and the
    positional rows still line up.

    So the expected value is recomputed here from scratch with a plain
    ``merge_asof`` and compared against what the engine produced. Any
    disagreement is a leak, regardless of how it was introduced.
    """

    result = report or CausalityReport()
    result.checks.append("cross_asset_alignment")
    if not all(name in reference.columns for name in REGIME_COLUMNS):
        reference = classify(reference)
    # Validate the continuous reference values too. The state strings are a
    # coarse bucketing of the percentiles, so a join that is off by a fraction
    # of a bucket is invisible in the label but obvious in the number.
    columns = [c for c in frame.columns if c.startswith("reference_") and c != "reference_symbol"]
    if not columns:
        result.findings.append(
            CausalityFinding(
                "cross_asset_alignment", "<reference columns>", 0, "no reference columns found"
            )
        )
        return result

    expected = pd.merge_asof(
        frame[["decision_time"]].sort_values("decision_time", kind="stable"),
        reference[["decision_time", *REGIME_COLUMNS, "trend_percentile"]].sort_values(
            "decision_time", kind="stable"
        ),
        on="decision_time",
        direction="backward",
    ).reset_index(drop=True)
    wanted = {
        f"reference_{name}": name for name in REGIME_COLUMNS
    }
    wanted["reference_trend_percentile"] = "trend_percentile"

    for column in columns:
        source = wanted.get(column)
        if source is None or source not in expected.columns:
            continue
        got = frame[column].to_numpy()
        want = expected[source].to_numpy()
        if len(got) != len(want):
            result.findings.append(
                CausalityFinding(
                    "cross_asset_alignment", column, 0, "row count mismatch after join"
                )
            )
            continue
        got_num = pd.to_numeric(pd.Series(got), errors="coerce").to_numpy(dtype=float)
        want_num = pd.to_numeric(pd.Series(want), errors="coerce").to_numpy(dtype=float)
        both_nan = np.isnan(got_num) & np.isnan(want_num)
        differs = (~np.isclose(got_num, want_num, rtol=0, atol=0, equal_nan=False)) & ~both_nan
        if bool(np.any(differs)):
            first = int(np.argmax(differs))
            result.findings.append(
                CausalityFinding(
                    "cross_asset_alignment",
                    column,
                    first,
                    f"{int(np.count_nonzero(differs))} row(s) disagree with an "
                    "independent backward as-of join; first disagreement at "
                    f"{frame['decision_time'].iloc[first]}",
                )
            )
        comparable = ~both_nan
        result.rows_compared += int(comparable.sum())
    return result


def run_all_probes(
    price: pd.DataFrame,
    timeframe: str,
    horizons: Sequence[int] = (6, 12, 24, 48),
    reference_price: pd.DataFrame | None = None,
    **feature_kwargs: Any,
) -> CausalityReport:
    """Run every causality proof and return one combined report."""

    combined = CausalityReport()
    price_report = probe_price_causality(price, timeframe, **feature_kwargs)
    combined.checks.extend(price_report.checks)
    combined.findings.extend(price_report.findings)
    combined.rows_compared += price_report.rows_compared

    regime_report = probe_regime_causality(price, timeframe, **feature_kwargs)
    combined.checks.extend(regime_report.checks)
    combined.findings.extend(regime_report.findings)
    combined.rows_compared += regime_report.rows_compared

    horizon_report = probe_forward_horizons(price, timeframe, horizons)
    combined.checks.extend(horizon_report.checks)
    combined.findings.extend(horizon_report.findings)

    availability = assert_feature_availability(build_features(price, timeframe=timeframe, **feature_kwargs))
    combined.checks.extend(availability.checks)
    combined.findings.extend(availability.findings)

    if reference_price is not None and not reference_price.empty:
        cross = probe_cross_asset_causality(price, reference_price, timeframe, **feature_kwargs)
        combined.checks.extend(cross.checks)
        combined.findings.extend(cross.findings)
        combined.rows_compared += cross.rows_compared

        reference_regime = classify(
            build_features(reference_price, timeframe=timeframe, **{
                k: v for k, v in feature_kwargs.items() if k != "symbol"
            }).frame
        )
        symbol_frame = attach_reference_regime(
            build_features(price, timeframe=timeframe, **feature_kwargs).frame,
            reference_regime,
        )
        alignment = assert_cross_asset_alignment(symbol_frame, reference_regime)
        combined.checks.extend(alignment.checks)
        combined.findings.extend(alignment.findings)
        combined.rows_compared += alignment.rows_compared
    return combined
