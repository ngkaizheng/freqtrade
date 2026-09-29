"""Phase F -- postmortem and mechanism audit.

Phase E opened the final holdout and it did not replicate. That is a complete
result, and the temptation it creates is the one this phase exists to refuse:
the holdout is now readable, so a post-hoc story about *why* it failed can be
manufactured on demand, and a story that explains a failure is one short step
from a rule that fixes it. The rule that fixes it would be fitted to the same
data that produced the failure.

So this module measures and never concludes. It asks one question -- *when did
the relationship stop, and did the inputs change?* -- and it is built so the
question cannot quietly become a different one:

* **No threshold of the candidate is touched.** The signal rule, the regime
  definition, the timeframe, the horizon, the symbols and the cost model are
  the frozen ones. :func:`assert_candidate_untouched` re-derives each
  candidate's ``logic_hash`` and refuses to run if any of them moved.
* **Every bucket is fixed from the boundary, not from the result.** Calendar
  months, calendar years and rolling windows are enumerated from the partition
  dates alone. There is no breakpoint search, because searching a timeline for
  the point where an effect died is a way of *finding* a breakpoint whether or
  not one exists.
* **Every output is stamped.** Each artifact carries
  ``analysis_status = POST_HOC_EXPLORATORY`` and
  ``candidate_selection_allowed = false``, so a number cannot travel out of
  this directory without its status travelling with it.
* **The timeline is stitched, not re-derived.** The development and holdout
  segments are built by the frozen Phase C pipeline and joined on the boundary
  the holdout already established, so a holdout number in this report is the
  same number Phase E produced rather than a re-measurement that happens to
  agree.

The audit is descriptive throughout. "Basis was lower in the holdout" is a
statement about two distributions; "basis drives the edge" is not a statement
this phase is entitled to make, and the report does not make it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.discovery import (
    FORWARD_HORIZON_BARS,
    HOLDOUT_WARMUP_DAYS,
    DiscoveryFrame,
    build_discovery_frame,
    with_regime,
)
from tools.strategy_factory_v2.discovery_engine import REFERENCE_SYMBOL, trade_metrics
from tools.strategy_factory_v2.freeze import logic_hash, regime_control_mask
from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.phase_d import HORIZON as PHASE_D_HORIZON
from tools.strategy_factory_v2.phase_d import candidate_returns
from tools.strategy_factory_v2.phase_e import HORIZON as PHASE_E_HORIZON
from tools.strategy_factory_v2.phase_e import _attach_reference as _phase_e_attach_reference
from tools.strategy_factory_v2.spec import (
    BASE_COST,
    DOUBLE_COST,
    MIN_OOS_TRADES,
    SPEC_VERSION,
    STRESS_COST,
)
from tools.strategy_factory_v2.uncertainty import effective_sample_size


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

#: The candidate the audit is about. The other frozen candidate is carried for
#: completeness but has too small a holdout sample to decompose.
PRIMARY_CANDIDATE = "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT"
CANDIDATE_IDS = (
    "H13_BTC_FILTER_1H_STRONG_UP_SHORT",
    "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT",
)

#: The audit's own metadata. These two strings appear in every artifact.
ANALYSIS_STATUS = "POST_HOC_EXPLORATORY"
CANDIDATE_SELECTION_ALLOWED = False
POST_HOC_LABELS = ("POST_HOC", "EXPLORATORY", "NOT_FOR_CANDIDATE_SELECTION")

#: Frozen candidate parameters, carried from Phase C unchanged. Declared here so
#: a reader can see that nothing in this phase chose them.
HORIZON = 12
TIMEFRAME = "1h"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")

#: The holding horizon is not a Phase F choice. It was fixed in Phase C and
#: carried unchanged through Phase D and Phase E, and this module refuses to run
#: if those three ever disagree with each other or with the constant above --
#: a timeline assembled at a different horizon than the one the candidate was
#: measured at would be a comparison against nothing.
assert PHASE_D_HORIZON == PHASE_E_HORIZON == HORIZON, (
    "the holding horizon has drifted between phases; Phase F cannot stitch a "
    f"timeline at {HORIZON} bars while the candidate was measured at "
    f"{PHASE_D_HORIZON}/{PHASE_E_HORIZON}"
)

#: Rolling diagnostics use one fixed window and one fixed step, declared here
#: rather than tuned. Six months at a monthly step is the coarsest scale that
#: still shows a decay curve across a six-and-a-half-year timeline; the value
#: is a reporting choice made from the *calendar*, not from the result.
ROLLING_WINDOW_DAYS = 180
ROLLING_STEP_DAYS = 30

#: Period labels, in chronological order. The three regions the pipeline
#: already defines, reported side by side and never merged.
REGION_ORDER = ("development", "validation", "final_holdout")

#: Numeric inputs H13 actually conditions on, plus the derivatives features the
#: plan names. Fixed list: a drift table that grows a new row because a column
#: happened to be present is how a post-hoc audit becomes a fishing expedition.
DRIFT_FEATURES: tuple[tuple[str, str], ...] = (
    ("price_return_24", "ret_24"),
    ("realized_vol_30", "realized_vol_30"),
    ("open_interest_level", "open_interest"),
    ("open_interest_change_288", "oi_change_288"),
    ("open_interest_pct_change_288", "oi_pct_change_288"),
    ("funding_rate_last", "funding_rate_last"),
    ("basis", "basis"),
    ("mark_index_spread", "mark_index_spread"),
    ("trend_score", "trend_score"),
    ("volatility_percentile", "volatility_percentile"),
)

#: The BTC trend states whose frequency the audit measures. The regime
#: definition itself is frozen and is not re-derived here.
TREND_STATES = ("STRONG_DOWN", "WEAK_DOWN", "NEUTRAL", "WEAK_UP", "STRONG_UP")

#: Descriptive drift labels. Labels, not scores: there is deliberately no
#: ordering among them and nothing consumes them programmatically.
DRIFT_LABELS = ("STABLE", "DRIFTED", "DISAPPEARED", "INSUFFICIENT_DATA", "AMBIGUOUS")

#: Rules behind the labels, fixed here and applied mechanically. The thresholds
#: are conventions for *describing* a comparison, not selection thresholds:
#: nothing below is allowed to promote, demote or re-rank anything.
DRIFT_MIN_SAMPLE = MIN_OOS_TRADES
#: A value that has shrunk to this fraction of its development magnitude is
#: labelled DISAPPEARED rather than merely smaller.
DRIFT_DISAPPEARED_RATIO = 0.25
#: A relative change larger than this is labelled DRIFTED.
DRIFT_RELATIVE_THRESHOLD = 0.50


class PhaseFViolation(RuntimeError):
    """Raised when a Phase F run would breach the post-hoc boundary."""


# ---------------------------------------------------------------------------
# Evidence status
# ---------------------------------------------------------------------------


FORBIDDEN_EVIDENCE_LABELS = (
    "untouched",
    "unseen",
    "unblinded holdout",
    "validation",
    "holdout",
)


def load_unblinded_partition() -> tuple[DataPartition, dict[str, Any]]:
    """Load the partition, requiring proof that the holdout was already opened.

    Phase F does **not** call :func:`holdout.unseal`. The region was unsealed in
    Phase E and the production lock records that fact; calling unseal again
    would append a second unseal event to an audit trail that is supposed to
    be a record of what actually happened, and would imply the opening was
    contemporaneous with this audit. It was not.

    Instead the existing record is read and the partition is marked unsealed
    from it. A lock with no ``unblinded`` block means the region was never
    opened, and this function refuses.
    """

    lock = read_lock()
    if not lock:
        raise PhaseFViolation(
            "no holdout lock file; the boundary must exist before Phase F"
        )
    record = lock.get("unblinded")
    if not record:
        raise PhaseFViolation(
            "the production lock records no unsealing event. Phase F is a "
            "postmortem of an opened holdout and cannot run against a sealed one."
        )
    # Set the flag by assignment rather than by keyword: a lock written by
    # ``write_lock`` already carries ``unsealed`` in its partition dict, and
    # passing it twice is a TypeError. The production lock happens not to,
    # which is exactly the kind of accident a boundary loader must not depend on.
    fields = dict(lock["partition"])
    fields["unsealed"] = True
    partition = DataPartition(**fields)
    return partition, {
        "already_unblinded": True,
        "unsealed_utc": record.get("unsealed_utc"),
        "unsealed_by_phase": record.get("phase", "E (final holdout evaluation)"),
        "unsealed_justification": record.get("justification"),
        "new_unseal_event_written": False,
        "note": (
            "Phase F read data the holdout guard already released in Phase E. No "
            "new unseal event was written to the production lock, because no new "
            "unsealing occurred; writing one would make the audit trail claim "
            "something that did not happen."
        ),
        "rows_in_production_access_log": len(lock.get("access_log", [])),
    }


def assert_candidate_untouched(candidate_ids: Sequence[str] = CANDIDATE_IDS) -> dict[str, str]:
    """Re-derive every candidate's logic hash and refuse if one moved.

    The hash covers the preregistered condition, the thresholds and the source
    of the predicate that implements them. If it changes, the object under audit
    is a different object and the audit is void, so this check fails closed
    rather than warning.
    """

    hashes: dict[str, str] = {}
    moved: list[str] = []
    for candidate_id in candidate_ids:
        current = logic_hash(get(candidate_id))
        hashes[candidate_id] = current
        recorded = _phase_d_frozen_hashes().get(candidate_id)
        if recorded and recorded != current:
            moved.append(candidate_id)
    if moved:
        raise PhaseFViolation(
            f"candidate logic changed since Phase D: {moved}. A postmortem of a "
            "modified candidate describes a different object than the one that "
            "failed; the audit is refused rather than relabelled."
        )
    return hashes


def _phase_d_frozen_hashes() -> dict[str, str]:
    """The hashes Phase D froze, read from the run that wrote them."""

    path = Path("user_data/strategy_factory_runs/v2/phase-d-validation-20260926/candidate_freeze.json")
    if not path.exists():
        return {}
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry["id"]): str(entry["logic_hash"])
        for entry in payload.get("candidates", [])
    }


def status_columns() -> dict[str, Any]:
    """The two columns every Phase F table carries."""

    return {
        "analysis_status": ANALYSIS_STATUS,
        "candidate_selection_allowed": CANDIDATE_SELECTION_ALLOWED,
    }


def stamp(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the status columns to a table."""

    if frame.empty and len(frame.columns) == 0:
        return frame
    out = frame.copy()
    out["analysis_status"] = ANALYSIS_STATUS
    out["candidate_selection_allowed"] = CANDIDATE_SELECTION_ALLOWED
    return out


# ---------------------------------------------------------------------------
# The timeline
# ---------------------------------------------------------------------------


@dataclass
class Timeline:
    """One continuous frame per symbol, stitched at the holdout boundary."""

    frames: dict[str, DiscoveryFrame]
    partition: DataPartition
    periods: dict[str, tuple[pd.Timestamp, pd.Timestamp]]
    development_rows: int = 0
    holdout_rows: int = 0
    warmup_rows_excluded: int = 0
    boundary_gap_rows: int = 0
    incomplete_outcome_rows: int = 0

    def period_mask(self, frame: pd.DataFrame, period: str) -> pd.Series:
        start, end = self.periods[period]
        times = pd.to_datetime(frame["decision_time"], utc=True)
        if period == "validation":
            # The partition's validation_end is mid-hour (22:12) and the bar
            # grid is 1h, so a closed interval there would drop the final bar
            # of the region. The holdout boundary is the next exact hour, so
            # validation runs up to it: no bar is lost and none is counted
            # twice.
            return (times >= start) & (times < end)
        return (times >= start) & (times < end)

    @property
    def start(self) -> pd.Timestamp:
        return self.periods[REGION_ORDER[0]][0]

    @property
    def end(self) -> pd.Timestamp:
        return self.periods[REGION_ORDER[-1]][1]


def region_periods(partition: DataPartition) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """The three fixed regions, on the decision clock."""

    return {
        "development": (
            pd.Timestamp(partition.development_start),
            pd.Timestamp(partition.validation_start),
        ),
        "validation": (
            pd.Timestamp(partition.validation_start),
            pd.Timestamp(partition.holdout_start),
        ),
        "final_holdout": (
            pd.Timestamp(partition.holdout_start),
            pd.Timestamp(partition.holdout_end),
        ),
    }


def _attach_reference(frames: dict[str, DiscoveryFrame], partition: DataPartition) -> None:
    """Attach the reference regime exactly as Phase E did.

    Delegated rather than reimplemented on purpose: a Phase F reference column
    that differed from Phase E's would make the holdout segment of this audit a
    second, subtly different measurement of the same region.
    """

    _phase_e_attach_reference(frames, partition)


def build_timeline(
    partition: DataPartition,
    symbols: Sequence[str] = SYMBOLS,
    timeframe: str = TIMEFRAME,
    progress: Callable[[str], None] | None = None,
) -> Timeline:
    """Build the continuous 2020..2026 frame for every symbol.

    The two segments come from the frozen pipeline and are joined at the
    boundary the holdout already established. Both sides were built by
    ``build_discovery_frame``, so every feature on both sides is trailing and
    both sides are warm where it matters. The only rows that lose an outcome
    are the last twelve bars of the development segment, whose forward window
    crosses into a region that segment is not allowed to read; they are
    counted and reported rather than quietly filled in.
    """

    boundary = pd.Timestamp(partition.holdout_start)
    say = progress or (lambda _message: None)

    say("building the development segment...")
    development = {
        symbol: with_regime(
            build_discovery_frame(symbol, timeframe, partition, "development")
        )
        for symbol in symbols
    }
    _attach_reference(development, partition)

    say("building the final-holdout segment (already unblinded in Phase E)...")
    holdout = {
        symbol: with_regime(
            build_discovery_frame(symbol, timeframe, partition, "final_holdout")
        )
        for symbol in symbols
    }
    _attach_reference(holdout, partition)

    frames: dict[str, DiscoveryFrame] = {}
    development_rows = 0
    holdout_rows = 0
    warmup_rows = 0
    gap_rows = 0
    incomplete = 0

    for symbol in symbols:
        head = development[symbol]
        tail = holdout[symbol]

        head_times = pd.to_datetime(head.frame["decision_time"], utc=True)
        tail_times = pd.to_datetime(tail.frame["decision_time"], utc=True)
        left = head.frame.loc[head_times < boundary].reset_index(drop=True)
        right = tail.frame.loc[tail_times >= boundary].reset_index(drop=True)

        # Counted *before* the boundary filter, or it is always zero. The
        # holdout frame carries 90 days of development warm-up precisely so the
        # trailing windows and regime percentiles are already defined when the
        # holdout opens; those rows exist, they are excluded here, and a report
        # that said "0 warm-up rows" because it looked in the wrong place would
        # be describing a warm-up that never happened.
        if "is_warmup" in tail.frame.columns:
            warmup_rows += int(tail.frame["is_warmup"].astype(bool).sum())

        merged = pd.concat([left, right], ignore_index=True)
        merged["is_warmup"] = False
        merged["timeframe"] = timeframe
        merged["symbol"] = symbol

        return_column = f"fwd_ret_{HORIZON}"
        if return_column in merged.columns:
            incomplete += int(pd.to_numeric(merged[return_column], errors="coerce").isna().sum())

        development_rows += int(len(left))
        holdout_rows += int(len(right))
        gap_rows += len(head_times[head_times >= boundary])

        frames[symbol] = DiscoveryFrame(
            symbol=symbol,
            timeframe=timeframe,
            frame=merged,
            funding_events=head.funding_events,
            partition=partition,
            attach_report={"phase_f": "development+final_holdout stitched at the boundary"},
        )

    # A stitch that silently produced two bars for one timestamp, or a gap,
    # would corrupt every chronological statement in the report. Asserted.
    for symbol, discovery in frames.items():
        times = pd.to_datetime(discovery.frame["decision_time"], utc=True)
        if times.duplicated().any():
            raise PhaseFViolation(
                f"{symbol}: the stitched timeline contains duplicate decision times"
            )
        if not times.is_monotonic_increasing:
            raise PhaseFViolation(f"{symbol}: the stitched timeline is not ordered")

    return Timeline(
        frames=frames,
        partition=partition,
        periods=region_periods(partition),
        development_rows=development_rows,
        holdout_rows=holdout_rows,
        warmup_rows_excluded=warmup_rows,
        boundary_gap_rows=gap_rows,
        incomplete_outcome_rows=incomplete,
    )


# ---------------------------------------------------------------------------
# Small numerical helpers
# ---------------------------------------------------------------------------


def calendar_months(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    """Every calendar month the timeline touches, enumerated from the dates."""

    months: list[str] = []
    year, month = pd.Timestamp(start).year, pd.Timestamp(start).month
    final = (pd.Timestamp(end).year, pd.Timestamp(end).month)
    while (year, month) <= final:
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def calendar_years(start: pd.Timestamp, end: pd.Timestamp) -> list[int]:
    """Every calendar year the timeline touches."""

    return list(range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1))


def run_lengths(flags: Sequence[bool] | np.ndarray) -> np.ndarray:
    """Lengths of the consecutive ``True`` runs in a boolean series."""

    values = np.asarray(flags, dtype=bool)
    if values.size == 0:
        return np.array([], dtype=int)
    padded = np.concatenate(([False], values, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return (edges[1::2] - edges[::2]).astype(int)


def wasserstein_1d(left: np.ndarray, right: np.ndarray, levels: int = 99) -> float:
    """First Wasserstein distance, estimated on a shared quantile grid.

    Estimated rather than imported: the sample sizes here are in the tens of
    thousands, and at that size the quantile average is indistinguishable from
    the exact integral, while an exact solver would add a dependency the rest
    of this package deliberately does not have.
    """

    if left.size == 0 or right.size == 0:
        return float("nan")
    grid = np.linspace(0.005, 0.995, levels)
    return float(np.mean(np.abs(np.quantile(left, grid) - np.quantile(right, grid))))


def standardized_wasserstein(left: np.ndarray, right: np.ndarray) -> float:
    """Wasserstein distance divided by the pooled standard deviation.

    A raw distance is uninterpretable across features measured in different
    units -- contracts, basis points and returns do not share a scale. Dividing
    by the pooled standard deviation expresses the shift in units of the
    feature's own spread, which is comparable.
    """

    if left.size == 0 or right.size == 0:
        return float("nan")
    pooled = np.sqrt(
        (float(np.var(left, ddof=1)) + float(np.var(right, ddof=1))) / 2.0
    ) if left.size > 1 and right.size > 1 else 0.0
    if not np.isfinite(pooled) or pooled <= 0:
        return float("nan")
    return wasserstein_1d(left, right) / pooled


def ks_distance(left: np.ndarray, right: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov statistic, computed directly."""

    if left.size == 0 or right.size == 0:
        return float("nan")
    a = np.sort(left)
    b = np.sort(right)
    grid = np.concatenate((a, b))
    cdf_a = np.searchsorted(a, grid, side="right") / a.size
    cdf_b = np.searchsorted(b, grid, side="right") / b.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def _finite(series: Any) -> np.ndarray:
    values = pd.to_numeric(pd.Series(series), errors="coerce").to_numpy(dtype=float)
    return values[np.isfinite(values)]


def distribution_row(values: np.ndarray) -> dict[str, float | int]:
    """mean/median/std and the five deciles the plan names."""

    if values.size == 0:
        return {
            "count": 0, "mean": None, "median": None, "std": None,
            "p10": None, "p25": None, "p50": None, "p75": None, "p90": None,
        }
    return {
        "count": int(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values, ddof=1)) if values.size > 1 else float("nan"),
        "p10": float(np.percentile(values, 10)),
        "p25": float(np.percentile(values, 25)),
        "p50": float(np.percentile(values, 50)),
        "p75": float(np.percentile(values, 75)),
        "p90": float(np.percentile(values, 90)),
    }


def _stats(group: pd.DataFrame) -> dict[str, Any]:
    """The metrics every Phase F table reports, on one group of signals."""

    if group is None or len(group) == 0:
        return {
            "trade_count": 0,
            "expectancy": None,
            "stress_expectancy": None,
            "profit_factor": None,
            "stress_profit_factor": None,
            "net_pnl": 0.0,
            "gross_pnl": 0.0,
            "win_rate": None,
        }
    base = trade_metrics(group["net_base"])
    stress = trade_metrics(group["net_stress"])
    return {
        "trade_count": int(len(group)),
        "expectancy": base.get("mean_return"),
        "stress_expectancy": stress.get("mean_return"),
        "profit_factor": base.get("profit_factor"),
        "stress_profit_factor": stress.get("profit_factor"),
        "net_pnl": float(group["net_base"].sum()),
        "gross_pnl": float(group["raw_return"].sum()),
        "win_rate": base.get("win_rate"),
    }


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------


def signal_trades(
    candidate_id: str,
    frames: dict[str, DiscoveryFrame],
    mask_override: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """One row per signal over the whole stitched timeline.

    The candidate's own predicate decides membership; an override exists only
    for the diagnostic unfiltered control, which is the same signal with the
    reference-asset clause removed.
    """

    return candidate_returns(get(candidate_id), frames, mask_override=mask_override)


def control_trades(candidate_id: str, frames: dict[str, DiscoveryFrame]) -> pd.DataFrame:
    """The already-defined unfiltered control, on the same timeline.

    Reused from Phase D rather than rebuilt: a control whose membership rule
    differed from the one the 26x comparison was measured against would make
    this audit's attribution table incomparable with the result it explains.
    """

    hypothesis = get(candidate_id)
    override = {
        symbol: regime_control_mask(discovery.frame, hypothesis)
        for symbol, discovery in frames.items()
    }
    return candidate_returns(hypothesis, frames, mask_override=override)


def _in_period(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if trades.empty:
        return trades
    times = pd.to_datetime(trades["decision_time"], utc=True)
    return trades.loc[(times >= start) & (times < end)]


# ---------------------------------------------------------------------------
# Section 3 -- the fixed chronological timeline
# ---------------------------------------------------------------------------


def period_metrics(
    trades_by_candidate: dict[str, pd.DataFrame],
    timeline: Timeline,
) -> pd.DataFrame:
    """Month, year and region buckets over the whole timeline.

    Every bucket the calendar contains is emitted, including buckets with no
    signals. A month that produced nothing is evidence about the candidate, and
    a table that quietly omits it invites the reader to assume it never existed.
    """

    months = calendar_months(timeline.start, timeline.end)
    years = calendar_years(timeline.start, timeline.end)
    rows: list[dict[str, Any]] = []
    for candidate_id, trades in trades_by_candidate.items():
        frame = trades.copy()
        if not frame.empty:
            frame["month"] = pd.to_datetime(frame["decision_time"], utc=True).dt.strftime("%Y-%m")
            frame["year"] = pd.to_datetime(frame["decision_time"], utc=True).dt.year
        for bucket_type, keys in (("calendar_month", months), ("calendar_year", years)):
            column = "month" if bucket_type == "calendar_month" else "year"
            for key in keys:
                group = frame[frame[column] == key] if not frame.empty else frame
                rows.append(
                    {
                        "candidate": candidate_id,
                        "bucket_type": bucket_type,
                        "bucket": key,
                        **_stats(group),
                    }
                )
        for region in REGION_ORDER:
            start, end = timeline.periods[region]
            group = _in_period(frame, start, end)
            rows.append(
                {
                    "candidate": candidate_id,
                    "bucket_type": "region",
                    "bucket": region,
                    **_stats(group),
                }
            )
    table = pd.DataFrame(rows)
    table["bucket_start"] = [
        _bucket_start(row["bucket_type"], row["bucket"]) for _, row in table.iterrows()
    ]
    table["bucket_end"] = [
        _bucket_end(row["bucket_type"], row["bucket"]) for _, row in table.iterrows()
    ]
    return table


def _bucket_start(bucket_type: str, bucket: Any) -> str:
    if bucket_type == "calendar_month":
        return f"{bucket}-01"
    if bucket_type == "calendar_year":
        return f"{int(bucket):04d}-01-01"
    return ""


def _bucket_end(bucket_type: str, bucket: Any) -> str:
    if bucket_type == "calendar_month":
        year, month = int(str(bucket)[:4]), int(str(bucket)[5:7])
        following = pd.Timestamp(year=year, month=month, day=1) + pd.DateOffset(months=1)
        return str((following - pd.Timedelta(days=1)).date())
    if bucket_type == "calendar_year":
        return f"{int(bucket):04d}-12-31"
    return ""


def rolling_metrics(
    trades: pd.DataFrame,
    timeline: Timeline,
    window_days: int = ROLLING_WINDOW_DAYS,
    step_days: int = ROLLING_STEP_DAYS,
) -> pd.DataFrame:
    """Fixed-window rolling expectancy across the timeline.

    The window and step are module constants chosen from the calendar, not
    from a plot. A researcher who could pick the window after seeing the curve
    would find a width at which the decay looks sharp, and that width would
    carry no information.
    """

    rows: list[dict[str, Any]] = []
    window = pd.Timedelta(days=window_days)
    step = pd.Timedelta(days=step_days)
    cursor = timeline.start
    frame = trades
    while cursor + window <= timeline.end:
        group = _in_period(frame, cursor, cursor + window)
        rows.append(
            {
                "window_start": str(cursor),
                "window_end": str(cursor + window),
                "window_days": window_days,
                "step_days": step_days,
                "primary_region": _window_region(cursor, cursor + window, timeline),
                **_stats(group),
            }
        )
        cursor += step
    return pd.DataFrame(rows)


def _window_region(start: pd.Timestamp, end: pd.Timestamp, timeline: Timeline) -> str:
    """Name the region a rolling window sits in, or say that it spans two.

    A window straddling the validation boundary is labelled ``spanning`` rather
    than being assigned to whichever region happens to contain more of it. The
    label is bookkeeping, but a window silently attributed to the wrong region
    would be read as a finding.
    """

    touched = [
        name
        for name in REGION_ORDER
        if start < timeline.periods[name][1] and end > timeline.periods[name][0]
    ]
    if len(touched) == 1:
        return touched[0]
    return "spanning" if touched else "outside_timeline"


# ---------------------------------------------------------------------------
# Section 4 -- input distribution drift
# ---------------------------------------------------------------------------


def feature_distribution_drift(timeline: Timeline) -> pd.DataFrame:
    """Per-feature distribution by period and symbol, plus a distance measure.

    A shift in a feature's distribution is a description of two samples. It is
    not evidence that the feature drove the result, and the report says so
    wherever the table appears.
    """

    rows: list[dict[str, Any]] = []
    for symbol, discovery in timeline.frames.items():
        frame = discovery.frame
        times = pd.to_datetime(frame["decision_time"], utc=True)
        for feature_name, column in DRIFT_FEATURES:
            if column not in frame.columns:
                continue
            series = pd.to_numeric(frame[column], errors="coerce")
            pools: dict[str, np.ndarray] = {}
            for region in REGION_ORDER:
                start, end = timeline.periods[region]
                pools[region] = _finite(series.loc[(times >= start) & (times < end)])
            for region in REGION_ORDER:
                rows.append(
                    {
                        "symbol": symbol,
                        "feature": feature_name,
                        "source_column": column,
                        "period": region,
                        **distribution_row(pools[region]),
                    }
                )
            development, holdout = pools["development"], pools["final_holdout"]
            rows.append(
                {
                    "symbol": symbol,
                    "feature": feature_name,
                    "source_column": column,
                    "period": "development_vs_final_holdout",
                    **distribution_row(np.array([])),
                    "standardized_wasserstein": standardized_wasserstein(development, holdout),
                    "ks_distance": ks_distance(development, holdout),
                }
            )

        # Pooled rows across the four tradeable alts, one per region plus the
        # comparison. BTC is excluded because it can never signal for a
        # cross-asset candidate; that exclusion is structural, not a selection,
        # and the reference asset's own regime is reported separately in
        # section 5. The pooled rows exist because the per-symbol tables alone
        # leave a reader to average four numbers by hand -- and a hand-averaged
        # drift statistic is the one most likely to be done wrong.
        for feature_name, column in DRIFT_FEATURES:
            pools = {
                region: _pooled_values(timeline, column, region, exclude={REFERENCE_SYMBOL})
                for region in REGION_ORDER
            }
            for region in REGION_ORDER:
                rows.append(
                    {
                        "symbol": "POOLED_ALTS",
                        "feature": feature_name,
                        "source_column": column,
                        "period": region,
                        **distribution_row(pools[region]),
                    }
                )
            rows.append(
                {
                    "symbol": "POOLED_ALTS",
                    "feature": feature_name,
                    "source_column": column,
                    "period": "development_vs_final_holdout",
                    **distribution_row(np.array([])),
                    "standardized_wasserstein": standardized_wasserstein(
                        pools["development"], pools["final_holdout"]
                    ),
                    "ks_distance": ks_distance(
                        pools["development"], pools["final_holdout"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def _pooled_values(
    timeline: Timeline, column: str, region: str, exclude: set[str]
) -> np.ndarray:
    """One feature's values across symbols, for one region."""

    start, end = timeline.periods[region]
    parts: list[np.ndarray] = []
    for symbol, discovery in timeline.frames.items():
        if symbol in exclude:
            continue
        frame = discovery.frame
        if column not in frame.columns:
            continue
        times = pd.to_datetime(frame["decision_time"], utc=True)
        series = pd.to_numeric(frame[column], errors="coerce")
        parts.append(_finite(series.loc[(times >= start) & (times < end)]))
    return np.concatenate(parts) if parts else np.array([])


# ---------------------------------------------------------------------------
# Section 5 -- BTC regime frequency drift
# ---------------------------------------------------------------------------


def regime_frequency(timeline: Timeline) -> pd.DataFrame:
    """How often, and for how long, each BTC trend state occurred per period.

    Measured on the reference asset's own regime column -- the classifier that
    the candidate actually conditions on -- and never re-thresholded.
    """

    reference = timeline.frames.get(REFERENCE_SYMBOL)
    rows: list[dict[str, Any]] = []
    if reference is None:
        return pd.DataFrame(
            columns=[
                "period", "regime", "bars", "bar_share", "first_occurrence",
                "last_occurrence", "mean_run_bars", "median_run_bars",
                "max_run_bars", "run_count",
            ]
        )
    frame = reference.frame
    times = pd.to_datetime(frame["decision_time"], utc=True)
    states = frame["trend_regime"].astype(str)
    for region in REGION_ORDER:
        start, end = timeline.periods[region]
        window = (times >= start) & (times < end)
        region_states = states.loc[window]
        region_times = times.loc[window]
        bars = max(len(region_states), 1)
        for state in TREND_STATES:
            flags = (region_states == state).to_numpy()
            lengths = run_lengths(flags)
            stamps = region_times[flags]
            rows.append(
                {
                    "period": region,
                    "regime": state,
                    "bars": int(flags.sum()),
                    "bar_share": float(flags.sum() / bars),
                    "first_occurrence": str(stamps.min()) if len(stamps) else "",
                    "last_occurrence": str(stamps.max()) if len(stamps) else "",
                    "mean_run_bars": float(lengths.mean()) if lengths.size else None,
                    "median_run_bars": float(np.median(lengths)) if lengths.size else None,
                    "max_run_bars": int(lengths.max()) if lengths.size else None,
                    "run_count": int(lengths.size),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 6 -- signal-frequency drift
# ---------------------------------------------------------------------------


def signal_frequency(
    candidate_id: str,
    timeline: Timeline,
) -> pd.DataFrame:
    """Signal rate and clustering by period.

    A fall in expectancy can come from the market paying less, from the
    candidate firing more often on worse opportunities, or from its signals
    bunching into blocks. These are different failures with different
    implications, and only the first is a statement about the market.
    """

    hypothesis = get(candidate_id)
    rows: list[dict[str, Any]] = []
    for region in REGION_ORDER:
        start, end = timeline.periods[region]
        per_symbol: list[dict[str, Any]] = []
        all_lengths: list[np.ndarray] = []
        total = 0
        for symbol, discovery in timeline.frames.items():
            frame = discovery.frame
            times = pd.to_datetime(frame["decision_time"], utc=True)
            in_window = (times >= start) & (times < end)
            flags = evaluate_in_window(hypothesis, frame).loc[in_window].to_numpy()
            lengths = run_lengths(flags)
            all_lengths.append(lengths)
            total += int(flags.sum())
            per_symbol.append({"symbol": symbol, "signals": int(flags.sum()), "bars": int(in_window.sum())})
        pooled_lengths = np.concatenate(all_lengths) if all_lengths else np.array([], dtype=int)
        months = max((end - start).days / 30.4375, 1e-9)
        weeks = max((end - start).days / 7.0, 1e-9)
        total_bars = sum(entry["bars"] for entry in per_symbol)
        for entry in per_symbol:
            rows.append(
                {
                    "candidate": candidate_id,
                    "period": region,
                    "symbol": entry["symbol"],
                    "bars": entry["bars"],
                    "signals": entry["signals"],
                    "signals_per_month": entry["signals"] / months,
                    "signals_per_week": entry["signals"] / weeks,
                    "signal_share_of_bars": (entry["signals"] / entry["bars"]) if entry["bars"] else None,
                    "mean_consecutive_length": (
                        float(pooled_lengths.mean()) if pooled_lengths.size else None
                    ),
                    "median_consecutive_length": (
                        float(np.median(pooled_lengths)) if pooled_lengths.size else None
                    ),
                    "max_consecutive_length": (
                        int(pooled_lengths.max()) if pooled_lengths.size else None
                    ),
                    "consecutive_block_count": int(pooled_lengths.size),
                    "period_signals": total,
                }
            )
        # One pooled row per region, on the cross-asset total. The per-symbol
        # rows alone invite a reader to divide a per-symbol signal count by a
        # cross-asset month length, which understates the rate by the number of
        # trading symbols and looks like a collapse in frequency that never
        # happened.
        rows.append(
            {
                "candidate": candidate_id,
                "period": region,
                "symbol": "POOLED",
                "bars": total_bars,
                "signals": total,
                "signals_per_month": total / months,
                "signals_per_week": total / weeks,
                "signal_share_of_bars": (total / total_bars) if total_bars else None,
                "mean_consecutive_length": (
                    float(pooled_lengths.mean()) if pooled_lengths.size else None
                ),
                "median_consecutive_length": (
                    float(np.median(pooled_lengths)) if pooled_lengths.size else None
                ),
                "max_consecutive_length": (
                    int(pooled_lengths.max()) if pooled_lengths.size else None
                ),
                "consecutive_block_count": int(pooled_lengths.size),
                "period_signals": total,
            }
            )
    return pd.DataFrame(rows)


def evaluate_in_window(hypothesis, frame: pd.DataFrame) -> pd.Series:
    from tools.strategy_factory_v2.hypothesis_eval import evaluate

    return evaluate(hypothesis, frame)


# ---------------------------------------------------------------------------
# Section 7 -- symbol x period
# ---------------------------------------------------------------------------


def symbol_period_matrix(trades: pd.DataFrame, timeline: Timeline) -> pd.DataFrame:
    """The fixed 5 x 3 matrix. No symbol is dropped, reordered or reweighted."""

    rows: list[dict[str, Any]] = []
    frame = trades.copy()
    if not frame.empty:
        frame["period"] = _period_labels(frame["decision_time"], timeline)
    for symbol in SYMBOLS:
        for period in REGION_ORDER:
            group = (
                frame[(frame["symbol"] == symbol) & (frame["period"] == period)]
                if not frame.empty
                else frame
            )
            rows.append({"symbol": symbol, "period": period, **_stats(group)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 8 -- gross versus cost
# ---------------------------------------------------------------------------


def cost_decomposition(
    trades: pd.DataFrame, side: int, partition: DataPartition, cost=BASE_COST
) -> pd.DataFrame:
    """Split the net return into gross, fee, slippage and funding components.

    The decomposition is additive by construction and is checked against the
    frozen engine's own net return in :func:`assert_decomposition_reconciles`.
    Only the base cost model is decomposed. Stress and double exist in the
    frozen protocol and are reported elsewhere; running the decomposition on
    several cost scenarios and reporting whichever separates the components
    best would be a parameter scan wearing a diagnostic's clothes.
    """

    rows: list[dict[str, Any]] = []
    for period, group in _group_by_period(trades, partition).items():
        if len(group) == 0:
            rows.append({"period": period, "cost_scenario": cost.name, **_EMPTY_COST})
            continue
        raw = pd.to_numeric(group["raw_return"], errors="coerce").to_numpy(dtype=float)
        funding = pd.to_numeric(group["funding_rate"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        fee = float(cost.fee_bps) / 10_000.0
        slippage = float(cost.slippage_bps) / 10_000.0
        entry = 1.0 + side * slippage
        exit_ = 1.0 - side * slippage
        after_slippage = ((1.0 + raw) / entry - 1.0)
        after_slippage = (1.0 + after_slippage) * exit_ - 1.0
        funding_charge = np.maximum(0.0, side * np.nan_to_num(funding))
        net = after_slippage - 2.0 * fee - funding_charge
        rows.append(
            {
                "period": period,
                "cost_scenario": cost.name,
                "trade_count": int(len(group)),
                "raw_expectancy": float(np.mean(raw)),
                "gross_expectancy": float(np.mean(after_slippage)),
                "fee_impact": float(-2.0 * fee),
                "slippage_impact": float(np.mean(after_slippage - raw)),
                "funding_impact": float(-np.mean(funding_charge)),
                "net_expectancy": float(np.mean(net)),
                "fee_share_of_raw": float((-2.0 * fee) / np.mean(raw)) if np.mean(raw) else np.nan,
                "funding_share_of_gross": (
                    float(-np.mean(funding_charge) / np.mean(after_slippage))
                    if np.mean(after_slippage)
                    else np.nan
                ),
                "recomputed_net_max_abs_error": float(
                    np.max(np.abs(net - group["net_base"].to_numpy(dtype=float)))
                ),
            }
        )
    return pd.DataFrame(rows)


_EMPTY_COST: dict[str, Any] = {
    "trade_count": 0,
    "raw_expectancy": None,
    "gross_expectancy": None,
    "fee_impact": None,
    "slippage_impact": None,
    "funding_impact": None,
    "net_expectancy": None,
    "fee_share_of_raw": np.nan,
    "funding_share_of_gross": np.nan,
    "recomputed_net_max_abs_error": np.nan,
}


def _group_by_period(trades: pd.DataFrame, partition: DataPartition | None = None) -> dict[str, pd.DataFrame]:
    """Split a signal frame into the three fixed regions."""

    if partition is None or trades.empty:
        return {}
    periods = region_periods(partition)
    return {region: _in_period(trades, *periods[region]) for region in REGION_ORDER}


def assert_decomposition_reconciles(table: pd.DataFrame, tolerance: float = 1e-12) -> None:
    """Fail if the component split does not add back up to the frozen net."""

    if table.empty:
        return
    error = pd.to_numeric(table["recomputed_net_max_abs_error"], errors="coerce").max()
    if np.isfinite(error) and float(error) > tolerance:
        raise PhaseFViolation(
            f"the cost decomposition does not reconcile with the frozen engine "
            f"(max error {error:.3e}); the split is not the same arithmetic the "
            "candidate was measured with"
        )


# ---------------------------------------------------------------------------
# Section 9 -- holding horizons
# ---------------------------------------------------------------------------


def holding_horizon_diagnostics(
    candidate_id: str, timeline: Timeline, horizons: Sequence[int] = FORWARD_HORIZON_BARS
) -> pd.DataFrame:
    """Expectancy at the horizons the research code already defines.

    ``FORWARD_HORIZON_BARS`` is the set Phase C registered. Introducing a
    horizon that is not on that list would be a parameter scan, and picking the
    best-looking row out of the result would be a candidate.
    """

    hypothesis = get(candidate_id)
    side = 1 if hypothesis.expected_direction == "long" else -1
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        column = f"fwd_ret_{horizon}"
        for region in REGION_ORDER:
            start, end = timeline.periods[region]
            values: list[np.ndarray] = []
            funding: list[np.ndarray] = []
            for symbol, discovery in timeline.frames.items():
                frame = discovery.frame
                if column not in frame.columns:
                    continue
                times = pd.to_datetime(frame["decision_time"], utc=True)
                mask = (
                    evaluate_in_window(hypothesis, frame)
                    & (times >= start)
                    & (times < end)
                )
                selected = frame.loc[mask.fillna(False)]
                if selected.empty:
                    continue
                returns = pd.to_numeric(selected[column], errors="coerce")
                # The return and its funding rate have to be dropped *together*.
                # A longer horizon leaves the last few bars without an outcome;
                # keeping their funding rates would silently pair a return with
                # the wrong signal's cost, and the array lengths would not match.
                usable = returns.notna().to_numpy()
                if not usable.any():
                    continue
                values.append(returns.to_numpy(dtype=float)[usable])
                rates = pd.to_numeric(
                    selected.get("funding_rate_last", pd.Series(0.0, index=selected.index)),
                    errors="coerce",
                ).fillna(0.0)
                funding.append(rates.to_numpy(dtype=float)[usable])
            if not values:
                rows.append(
                    {"candidate": candidate_id, "horizon_bars": horizon, "period": region,
                     "trade_count": 0, "expectancy": None, "raw_expectancy": None}
                )
                continue
            raw = np.concatenate(values)
            rates = np.concatenate(funding) if funding else np.zeros_like(raw)
            fee = float(BASE_COST.fee_bps) / 10_000.0
            slippage = float(BASE_COST.slippage_bps) / 10_000.0
            # Same two steps, in the same order, as discovery_engine.net_return:
            # scale the *equity* up by the entry slippage, then scale the
            # resulting equity down by the exit slippage. Multiplying the
            # return by the exit factor instead returns roughly -1 for every
            # signal, which looks like a finding and is arithmetic.
            after_slippage = (1.0 + raw) / (1.0 + side * slippage) - 1.0
            after_slippage = (1.0 + after_slippage) * (1.0 - side * slippage) - 1.0
            net = after_slippage - 2.0 * fee - np.maximum(0.0, side * rates)
            rows.append(
                {
                    "candidate": candidate_id,
                    "horizon_bars": horizon,
                    "period": region,
                    "trade_count": int(raw.size),
                    "raw_expectancy": float(np.mean(raw)) if raw.size else None,
                    "expectancy": float(np.mean(net)) if net.size else None,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 10 -- dependence structure
# ---------------------------------------------------------------------------


def dependence_diagnostics(
    trades_by_candidate: dict[str, pd.DataFrame], timeline: Timeline
) -> pd.DataFrame:
    """Autocorrelation, effective sample size and block length by period."""

    rows: list[dict[str, Any]] = []
    for candidate_id, trades in trades_by_candidate.items():
        frame = trades.copy()
        if not frame.empty:
            frame["period"] = _period_labels(frame["decision_time"], timeline)
        for region in REGION_ORDER:
            group = frame[frame["period"] == region] if not frame.empty else frame
            values = (
                pd.to_numeric(group["net_base"], errors="coerce").to_numpy(dtype=float)
                if len(group)
                else np.array([], dtype=float)
            )
            dependence = effective_sample_size(values) if values.size else {}
            blocks = _block_lengths(group, timeline) if len(group) else np.array([], dtype=int)
            rows.append(
                {
                    "candidate": candidate_id,
                    "period": region,
                    "observations": int(values.size),
                    "lag1_autocorrelation": dependence.get("lag1_autocorrelation"),
                    "integrated_autocorrelation_time": dependence.get(
                        "integrated_autocorrelation_time"
                    ),
                    "effective_sample_size": dependence.get("effective_sample_size"),
                    "mean_block_length": float(blocks.mean()) if blocks.size else None,
                    "median_block_length": float(np.median(blocks)) if blocks.size else None,
                    "max_block_length": int(blocks.max()) if blocks.size else None,
                    "block_count": int(blocks.size),
                }
            )
    return pd.DataFrame(rows)


def _period_labels(decision_time: pd.Series, timeline: Timeline) -> pd.Series:
    times = pd.to_datetime(decision_time, utc=True)
    labels = pd.Series("", index=times.index, dtype="object")
    for region in REGION_ORDER:
        start, end = timeline.periods[region]
        labels.loc[(times >= start) & (times < end)] = region
    return labels


def _block_lengths(group: pd.DataFrame, timeline: Timeline, gap_hours: int = 13) -> np.ndarray:
    """Consecutive signals in clock time, not in row order.

    Two signals four hours apart sit in the same holding window and share most
    of their feature history; a block defined by bar adjacency would call them
    independent events. The gap is the holding horizon plus one bar, which is
    the point beyond which two signals can no longer share an outcome window.
    """

    if group.empty:
        return np.array([], dtype=int)
    times = pd.to_datetime(group["decision_time"], utc=True).sort_values()
    gaps = times.diff()
    breaks = gaps > pd.Timedelta(hours=gap_hours)
    boundaries = np.flatnonzero(breaks.to_numpy())
    starts = np.concatenate(([0], boundaries + 1))
    ends = np.concatenate((boundaries, [len(times) - 1]))
    return (ends - starts + 1).astype(int)


# ---------------------------------------------------------------------------
# Section 11 -- regime-conditioned attribution
# ---------------------------------------------------------------------------


def regime_attribution(
    candidate_id: str,
    candidate: pd.DataFrame,
    control: pd.DataFrame,
    timeline: Timeline,
) -> pd.DataFrame:
    """Candidate versus the already-defined unfiltered control, per period.

    The difference is an association between a conditioning condition and a
    return. It is not a causal effect, the control is not optimised, and a
    period in which the lift is negative is reported with the same prominence
    as one where it is positive.
    """

    rows: list[dict[str, Any]] = []
    for region in REGION_ORDER:
        start, end = timeline.periods[region]
        candidate_group = _in_period(candidate, start, end)
        control_group = _in_period(control, start, end)
        candidate_stats = _stats(candidate_group)
        control_stats = _stats(control_group)
        difference = None
        if candidate_stats["expectancy"] is not None and control_stats["expectancy"] is not None:
            difference = candidate_stats["expectancy"] - control_stats["expectancy"]
        rows.append(
            {
                "candidate": candidate_id,
                "period": region,
                "candidate_signals": candidate_stats["trade_count"],
                "candidate_expectancy": candidate_stats["expectancy"],
                "candidate_stress_expectancy": candidate_stats["stress_expectancy"],
                "control_signals": control_stats["trade_count"],
                "control_expectancy": control_stats["expectancy"],
                "control_stress_expectancy": control_stats["stress_expectancy"],
                "difference": difference,
                "control_definition": (
                    "the same bearish-trend signal with the reference-asset regime "
                    "clause removed; defined in Phase D and not modified here"
                ),
                "claim_limit": (
                    "association only; a conditioned subset with higher returns is "
                    "not proof that the condition causes them"
                ),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 12 -- descriptive drift labels
# ---------------------------------------------------------------------------


def label_drift(
    development: float | None,
    validation: float | None,
    holdout: float | None,
    development_n: int,
    holdout_n: int,
    neutral: float = 0.0,
) -> str:
    """Apply the fixed labelling rules. Descriptive, and consumed by nothing.

    The rules, in order: too few observations to say anything; a value that
    changed sign or collapsed to a fraction of its development magnitude;
    a value that moved by more than the declared relative threshold; otherwise
    unchanged. A development value equal to the neutral level is ambiguous by
    construction -- there is no magnitude to compare against.

    ``neutral`` is the level at which a quantity carries no information, and it
    defaults to zero because that is right for a return and wrong for a ratio.
    A profit factor of 0.8 is a loss and a profit factor of 1.2 is a gain, so
    both are "positive" and a sign test would call 1.2 -> 0.8 stable when it
    crossed the only line that matters. Passing ``neutral=1.0`` makes the rules
    compare 0.2 against -0.2 and the crossing shows up.
    """

    if development is None or holdout is None:
        return "INSUFFICIENT_DATA"
    if development_n < DRIFT_MIN_SAMPLE or holdout_n < DRIFT_MIN_SAMPLE:
        return "INSUFFICIENT_DATA"
    if not np.isfinite(development) or not np.isfinite(holdout):
        return "AMBIGUOUS"
    development = float(development) - neutral
    holdout = float(holdout) - neutral
    if abs(development) < 1e-12:
        return "AMBIGUOUS"
    if np.sign(development) != np.sign(holdout):
        return "DISAPPEARED"
    if abs(holdout) < DRIFT_DISAPPEARED_RATIO * abs(development):
        return "DISAPPEARED"
    if abs(holdout - development) / abs(development) > DRIFT_RELATIVE_THRESHOLD:
        return "DRIFTED"
    return "STABLE"


def hypothesis_drift_table(
    diagnostics: Sequence[
        tuple[str, str, float | None, float | None, float | None, int, int, float]
    ],
) -> pd.DataFrame:
    """Assemble the section 12 table.

    Each entry is ``(diagnostic, interpretation, development, validation,
    final_holdout, development_n, final_holdout_n, neutral)``. The interpretation
    column is a sentence a reader can check against the numbers; the label is
    produced by :func:`label_drift` from the same fixed rules and is not a score.
    """

    rows = [
        {
            "diagnostic": name,
            "development": development,
            "validation": validation,
            "final_holdout": holdout,
            "interpretation": interpretation,
            "label": label_drift(
                development, validation, holdout, dev_n, hold_n, neutral=neutral
            ),
            "development_n": dev_n,
            "final_holdout_n": hold_n,
            "neutral_level": neutral,
        }
        for name, interpretation, development, validation, holdout, dev_n, hold_n, neutral
        in diagnostics
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 13 -- the conclusion that must survive
# ---------------------------------------------------------------------------


def conclusion_rows(
    trades_by_candidate: dict[str, pd.DataFrame], timeline: Timeline
) -> pd.DataFrame:
    """The three-period record, side by side and never averaged.

    Averaging the periods would be the single most misleading thing this
    project could do here: it would convert one negative region and two
    positive ones into a number that describes no region that ever existed.
    """

    rows: list[dict[str, Any]] = []
    for candidate_id, trades in trades_by_candidate.items():
        for region in REGION_ORDER:
            start, end = timeline.periods[region]
            group = _in_period(trades, start, end)
            stats = _stats(group)
            rows.append(
                {
                    "candidate": candidate_id,
                    "period": region,
                    "period_start": str(start),
                    "period_end": str(end),
                    **stats,
                    "averaged_with_other_periods": False,
                }
            )
    return pd.DataFrame(rows)


def direction_convention_audit(
    trades_by_candidate: dict[str, pd.DataFrame], timeline: Timeline
) -> pd.DataFrame:
    """Report, per period, the expectancy under both return conventions.

    **This is a defect audit, not a candidate.**

    Every evaluator in this package reads ``fwd_ret_<h>``, which is a plain
    forward price return, and charges costs through ``net_return``. ``net_return``
    uses its ``side`` argument for exactly two things -- which way the slippage
    bites, and which way the funding cashflow is charged -- and never multiplies
    the return by it. A hypothesis whose ``expected_direction`` is ``short`` is
    therefore measured on the *long* profit and loss of the asset it would have
    shorted.

    The mirrored column below is what the same signals look like under the other
    convention. It exists to size the defect, not to propose anything:

    * it is **not** a candidate, is **not** in the registry, and may never be
      promoted;
    * no threshold, horizon, symbol or filter was chosen to produce it;
    * the registry still holds 92 hypotheses and this phase added none.

    The mirrored number is reported because a defect whose size is unknown
    cannot be triaged. It is emphatically not a finding.
    """

    rows: list[dict[str, Any]] = []
    for candidate_id, trades in trades_by_candidate.items():
        for region in REGION_ORDER:
            start, end = timeline.periods[region]
            group = _in_period(trades, start, end)
            stats = _stats(group)
            expectancy = stats["expectancy"]
            rows.append(
                {
                    "candidate": candidate_id,
                    "period": region,
                    "trade_count": stats["trade_count"],
                    "registered_direction": get(candidate_id).expected_direction,
                    "expectancy_under_the_engine_as_written": expectancy,
                    "expectancy_under_the_mirrored_convention": (
                        None if expectancy is None else -float(expectancy)
                    ),
                    "engine_observed_direction": "long (the engine never negates fwd_ret)",
                    "defect": "the registered direction is not applied to the return series",
                    "is_candidate": False,
                    "promotion_allowed": False,
                    "note": (
                        "Diagnostic only. The mirrored column sizes an engine "
                        "defect; it is not a hypothesis and may not be selected, "
                        "frozen or promoted."
                    ),
                }
            )
    return pd.DataFrame(rows)


def _f(value: Any, digits: int = 5) -> str:
    if value is None:
        return "--"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    if not np.isfinite(number):
        return "--"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{number:+.{digits}f}"
