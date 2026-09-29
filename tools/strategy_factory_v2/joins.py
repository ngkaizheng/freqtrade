"""Causal as-of joining of event streams onto a decision grid.

The single most dangerous operation in a derivatives study is attaching an
event series to a bar grid. Done correctly it is a backward as-of join. Done
slightly wrong -- a forward fill, a centred window, a join on a rounded
timestamp, a merge without a lag -- it produces a beautiful backtest of a
signal that is really a copy of the future.

Three things make that failure hard to see, and all three are addressed here:

**The join is explicit about its clock.** A candle labelled 08:00 on a 5-minute
grid is actionable at 08:05. Features are stamped at the close, never at the
label, because the label is the one convention that reliably hides an
off-by-one.

**The join reports its own provenance.** For every attached value it returns
the ``source_timestamp`` it came from, the ``signal_timestamp`` it was attached
to, and the ``age_seconds`` between them. A join that quietly reaches forward
is visible as a negative age, and a join that reaches *too far back* -- which
looks perfectly causal but attaches a stale reading to a live bar -- is visible
as an age exceeding a declared staleness bound. Both are checked, because
"causal" and "sensible" are different properties.

**The check has a negative control.** :func:`future_leakage_violations` is
tested against a deliberately shifted event stream. A detector that has never
been shown to fire is not evidence that nothing is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import pandas as pd

#: The Binance OI stream publishes 288 irregular samples per day, so a bar may
#: legitimately be several hours from its most recent observation. This bound
#: is a *reporting* threshold, not a validity test: exceeding it is flagged so
#: a human can decide whether the OI series has stopped updating, not because the
#: join is wrong.
DEFAULT_STALENESS_HOURS = 24.0


@dataclass
class CausalJoin:
    """A joined frame plus the evidence that the join was causal."""

    frame: pd.DataFrame
    value_columns: list[str] = field(default_factory=list)
    source_time_column: str = "source_timestamp"
    signal_time_column: str = "signal_timestamp"
    age_column: str = "age_seconds"
    truth_time_column: str = "truth_timestamp"

    @property
    def values(self) -> pd.DataFrame:
        return self.frame.loc[:, self.value_columns]

    def as_dict(self) -> dict[str, Any]:
        ages = self.frame[self.age_column]
        return {
            "rows": int(len(self.frame)),
            "value_columns": list(self.value_columns),
            "attached_rows": int(self.frame[self.value_columns].notna().any(axis=1).sum()),
            "unattached_rows": int(self.frame[self.value_columns].isna().all(axis=1).sum()),
            "age_seconds": {
                "min": float(ages.min(skipna=True)) if ages.notna().any() else None,
                "median": float(ages.median(skipna=True)) if ages.notna().any() else None,
                "p95": float(ages.quantile(0.95)) if ages.notna().any() else None,
                "max": float(ages.max(skipna=True)) if ages.notna().any() else None,
            },
        }


def _as_utc_ns(values: pd.Series) -> pd.Series:
    """Normalize to UTC at nanosecond resolution.

    ``merge_asof`` refuses to join keys whose dtypes differ, and pandas 3 keeps
    whatever resolution the source happened to carry: a funding file floored to
    minutes comes back as ``datetime64[us]`` while a price timestamp is
    ``datetime64[ns]``. Normalising both sides here is the difference between a
    join that works and one that fails for a reason that has nothing to do with
    the data.
    """

    series = pd.Series(values)
    if not pd.api.types.is_datetime64_any_dtype(series):
        series = pd.to_datetime(series, utc=True)
    elif series.dt.tz is None:
        series = series.dt.tz_localize("UTC")
    else:
        series = series.dt.tz_convert("UTC")
    return series.astype("datetime64[ns, UTC]")


def causal_asof_join(
    signal_times: pd.Series | pd.DatetimeIndex,
    events: pd.DataFrame,
    value_columns: Sequence[str],
    event_time_column: str = "timestamp",
    signal_time_column: str = "signal_timestamp",
    truth_time_column: str | None = None,
) -> CausalJoin:
    """Attach the latest event at or before each signal time.

    ``truth_time_column`` exists so the join can prove it used only
    observations that genuinely existed at decision time. In production it is
    the same column as ``event_time_column`` and the check is a tautology. In
    the negative-control test it carries the *unshifted* time while the join
    key carries a rewritten one, which is the only way a detector can catch a
    leak that has disguised itself as a positive age -- which is precisely what
    happens when someone re-stamps a sample into the bar it "belongs" to.

    Never forward-fills in the sense that matters: a bar with no prior event is
    left NaN, and the join never reaches forward even by one nanosecond.
    ``allow_exact_matches=True`` is intentional and conservative in the right
    direction: an event stamped exactly at a signal time is treated as known at
    that time, which is the assumption the preregistration already fixes for
    funding settlements.
    """

    left = pd.DataFrame({signal_time_column: _as_utc_ns(pd.Series(signal_times)).to_numpy()})
    left = left.sort_values(signal_time_column, kind="stable").reset_index(drop=True)

    right = events.copy()
    right[event_time_column] = _as_utc_ns(right[event_time_column])
    if truth_time_column and truth_time_column in right.columns:
        right["__truth_time__"] = _as_utc_ns(right[truth_time_column])
    keep = [event_time_column, *value_columns]
    if truth_time_column and "__truth_time__" in right.columns:
        keep.append("__truth_time__")
    right = right.loc[:, keep].sort_values(event_time_column, kind="stable")
    right = right.rename(columns={event_time_column: "__event_time__"})

    merged = pd.merge_asof(
        left,
        right,
        left_on=signal_time_column,
        right_on="__event_time__",
        direction="backward",
        allow_exact_matches=True,
    )

    age = (merged[signal_time_column] - merged["__event_time__"]).dt.total_seconds()
    out = pd.DataFrame(
        {
            signal_time_column: merged[signal_time_column],
            **{c: merged[c] for c in value_columns},
            "source_timestamp": merged["__event_time__"],
            "age_seconds": age,
        }
    )
    if "__truth_time__" in merged.columns:
        out["truth_timestamp"] = merged["__truth_time__"]
    else:
        out["truth_timestamp"] = merged["__event_time__"]
    return CausalJoin(
        frame=out.reset_index(drop=True),
        value_columns=list(value_columns),
        signal_time_column=signal_time_column,
    )


def future_leakage_violations(join: CausalJoin) -> dict[str, Any]:
    """Detect any attached value that was not yet observable at decision time.

    Two independent signatures, because one is not enough:

    * a **negative age** -- the join reached forward past the decision;
    * a **truth timestamp after the signal** -- the join reached back to an
      observation that, in real time, had not happened yet.

    The second is the one that matters in practice. Re-stamping a sample into
    the bar it "belongs" to leaves a perfectly positive age, so an age-only
    check reports a clean bill of health on a dataset that has been shifted
    into the future.
    """

    frame = join.frame
    ages = frame[join.age_column]
    attached = frame[join.value_columns].notna().any(axis=1)
    signal = pd.to_datetime(frame[join.signal_time_column], utc=True)
    truth = pd.to_datetime(frame[join.truth_time_column], utc=True)

    forward_reach = attached & (ages < 0)
    truth_after_signal = attached & (truth > signal)
    violations = int((forward_reach | truth_after_signal).sum())

    detail: list[dict[str, Any]] = []
    if violations:
        offending = frame[forward_reach | truth_after_signal].head(5)
        for _, row in offending.iterrows():
            detail.append(
                {
                    "signal_timestamp": str(row[join.signal_time_column]),
                    "source_timestamp": str(row[join.source_time_column]),
                    "truth_timestamp": str(row[join.truth_time_column]),
                    "age_seconds": float(row[join.age_column]),
                    "signature": (
                        "future_observation"
                        if pd.to_datetime(row[join.truth_time_column], utc=True)
                        > pd.to_datetime(row[join.signal_time_column], utc=True)
                        else "forward_reach"
                    ),
                }
            )
    return {
        "attached_rows": int(attached.sum()),
        "violations": violations,
        "forward_reach": int(forward_reach.sum()),
        "truth_after_signal": int(truth_after_signal.sum()),
        "min_age_seconds": float(ages.min(skipna=True)) if ages.notna().any() else None,
        "examples": detail,
    }


def staleness_report(
    join: CausalJoin, threshold_hours: float = DEFAULT_STALENESS_HOURS
) -> dict[str, Any]:
    """Report how stale the attached observations are.

    Distinct from leakage: a stale join is still causal, but a bar carrying a
    twelve-hour-old open interest is not describing the current market, and
    that is worth knowing before the number is interpreted.
    """

    frame = join.frame
    attached = frame[join.value_columns].notna().any(axis=1)
    ages = frame.loc[attached, join.age_column].dropna()
    if ages.empty:
        return {"rows": 0, "attached_rows": 0, "exceeds_threshold": 0, "threshold_hours": threshold_hours}
    threshold = threshold_hours * 3600.0
    exceeds = int((ages > threshold).sum())
    return {
        "rows": int(len(frame)),
        "attached_rows": int(attached.sum()),
        "threshold_hours": threshold_hours,
        "exceeds_threshold": exceeds,
        "exceeds_ratio": round(exceeds / len(ages), 6),
        "age_seconds_max": float(ages.max()),
        "age_seconds_p99": float(ages.quantile(0.99)),
    }


def shift_events_forward(events: pd.DataFrame, minutes: int, time_column: str = "timestamp") -> pd.DataFrame:
    """Return a copy with every event timestamp moved later.

    Only ever used by the negative-control test. A detector that cannot catch a
    deliberately leaked stream is not a detector.
    """

    shifted = events.copy()
    shifted[time_column] = shifted[time_column] + pd.Timedelta(minutes=minutes)
    return shifted


def shift_events_backward(
    events: pd.DataFrame, minutes: int, time_column: str = "timestamp"
) -> pd.DataFrame:
    """Re-stamp every event earlier, keeping the true time in ``truth_timestamp``.

    This is the realistic leak. Someone decides the 08:05 open-interest sample
    "belongs" to the 08:00 bar and re-stamps it accordingly. The resulting join
    has a perfectly positive age -- the join did reach backwards, it just
    reached to a value that had not happened yet -- so an age-only check calls
    it clean. Only a check against the un-rewritten truth catches it.
    """

    shifted = events.copy()
    shifted["truth_timestamp"] = events[time_column]
    shifted[time_column] = events[time_column] - pd.Timedelta(minutes=minutes)
    return shifted


def verify_join_is_causal(
    signal_times: pd.Series,
    events: pd.DataFrame,
    value_columns: Sequence[str],
    event_time_column: str = "timestamp",
    tolerance_rows: int = 0,
) -> tuple[CausalJoin, dict[str, Any]]:
    """Join, then assert the result contains no future observation."""

    join = causal_asof_join(signal_times, events, value_columns, event_time_column)
    report = future_leakage_violations(join)
    if report["violations"] > tolerance_rows:
        raise AssertionError(
            f"causal join leaked {report['violations']} future observation(s); "
            f"first: {report['examples'][:1]}"
        )
    return join, report
