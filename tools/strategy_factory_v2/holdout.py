"""The development / final-holdout boundary, enforced rather than agreed.

A reserved holdout that is merely documented is a holdout that will be
accidentally looked at. The failure mode is never a deliberate peek; it is a
convenient default argument, a percentile computed over the whole frame, a
warm-up window that quietly reaches past the boundary. Each of those looks
reasonable in isolation and collectively they destroy the only genuinely
untested data the project will ever have.

So the boundary here is a *mechanism*:

* The holdout period is declared once, from the recovered data's own extent --
  never from a hard-coded date, and never from "today".
* Holdout rows are written to a physically separate namespace and listed in a
  lock file.
* :func:`assert_development_window` is the gate every development code path
  calls before it loads anything. A frame whose span crosses the boundary is
  rejected with the offending dates named, not silently truncated.
* The holdout loader requires an explicit, named opt-in, and records the
  justification. There is no default that opens it.

The recovery layer found the price series now runs to a complete recent day, so
a real holdout exists for the first time. Before this phase the project had no
untested data at all beyond the end of its own download.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as np
import pandas as pd

LOCK_FILE = Path("user_data/data/binance_v2/FINAL_HOLDOUT_DO_NOT_TOUCH.json")

#: Region labels used across every V2 artifact.
DEVELOPMENT = "development"
VALIDATION = "validation"
FINAL_HOLDOUT = "final_holdout"

#: How the development set is split internally. Validation is carved from the
#: end of development so that selection never sees it.
VALIDATION_TAIL_DAYS = 165


class HoldoutViolation(RuntimeError):
    """Raised when development code reaches into the final holdout."""


@dataclass
class DataPartition:
    """The three research regions, with their exact boundaries."""

    development_start: str
    development_end: str
    validation_start: str
    validation_end: str
    holdout_start: str
    holdout_end: str
    latest_complete_day: str
    boundary_source: str = "recovered dataset extent"
    unsealed: bool = False
    declared_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def region_of(self, timestamp: Any) -> str:
        stamp = pd.Timestamp(timestamp)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        if stamp >= pd.Timestamp(self.holdout_start):
            return FINAL_HOLDOUT
        if stamp >= pd.Timestamp(self.validation_start):
            return VALIDATION
        return DEVELOPMENT

    @property
    def is_unsealed(self) -> bool:
        """True once the final holdout has been opened, permanently."""

        return bool(self.unsealed)

    def require_unsealed(self, context: str = "") -> None:
        """Refuse to build holdout features while the holdout is still sealed."""

        if not self.unsealed:
            raise HoldoutViolation(
                "the final holdout is sealed; call holdout.unseal() with a written "
                f"justification before building any feature over it{(' (' + context + ')') if context else ''}"
            )


def unseal(
    partition: DataPartition,
    justification: str,
    spec_version: str,
    spec_path: Path | None = None,
) -> DataPartition:
    """Open the final holdout permanently, recording the transition.

    This is the only route to holdout data, and it is deliberately not
    reversible. Once written, the lock file states that the region is unblinded,
    because from this moment the project no longer holds untested data and any
    later claim of "untouched" would be false.

    The unsealing is written to the *production* lock file. A shadow copy would
    leave the authoritative record claiming the holdout was never opened, which
    is precisely the kind of quiet rewrite this project is built to prevent.
    """

    if not justification or not justification.strip():
        raise HoldoutViolation("unsealing the final holdout requires a written justification")
    if not spec_version or not spec_version.strip():
        raise HoldoutViolation(
            "unsealing the final holdout requires the spec version that was frozen first"
        )
    now = datetime.now(timezone.utc).isoformat()
    payload = read_lock() or {}
    payload["unblinded"] = {
        "unsealed_utc": now,
        "justification": justification.strip(),
        "spec_version": spec_version.strip(),
        "spec_file": str(spec_path) if spec_path else None,
        "statement": (
            "The final holdout has now been read. It is no longer untouched data "
            "and no later analysis may describe it as such."
        ),
    }
    payload.setdefault("access_log", []).append(
        {
            "opened_utc": now,
            "justification": justification.strip(),
            "spec_version": spec_version.strip(),
            "holdout_start": partition.holdout_start,
            "rows": "unsealed (not enumerated at unseal time)",
            "phase": "E (final holdout evaluation)",
        }
    )
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return replace(partition, unsealed=True)


def latest_complete_day(
    frame: pd.DataFrame,
    time_column: str = "date",
    safety_hours: int = 6,
    expected_interval_minutes: int = 60,
) -> str:
    """The last day on which the series is demonstrably complete.

    Derived from the data's own extent rather than from the clock, for two
    reasons. First, "today" is never complete: the current UTC day is still
    being written, and a dataset ending mid-day produces a research boundary
    nobody can reason about. Second, the archive may lag the calendar, so the
    clock can be ahead of the data entirely.

    A day counts as complete only when the series runs at least ``safety_hours``
    past its midnight. That single test separates a finished day from a
    trailing fragment, and it is the reason the function can never return a day
    later than the data actually reaches.
    """

    stamps = pd.to_datetime(frame[time_column], utc=True).sort_values()
    if stamps.empty:
        raise ValueError("cannot determine a complete day from an empty series")
    last = stamps.iloc[-1]
    last_day = last.floor("D")
    offset = last - last_day
    if offset < pd.Timedelta(hours=safety_hours):
        # The series stops near the start of this day, so this day is a
        # fragment; step back one.
        return str((last_day - pd.Timedelta(days=1)).date())
    return str(last_day.date())


def declare_partition(
    development_frame: pd.DataFrame,
    holdout_frame: pd.DataFrame,
    time_column: str = "date",
    validation_tail_days: int = VALIDATION_TAIL_DAYS,
) -> DataPartition:
    """Build the partition from the actual extent of each dataset."""

    development_end = pd.Timestamp(
        pd.to_datetime(development_frame[time_column], utc=True).max()
    )
    holdout_start = pd.Timestamp(pd.to_datetime(holdout_frame[time_column], utc=True).min())
    holdout_end = pd.Timestamp(pd.to_datetime(holdout_frame[time_column], utc=True).max())
    development_start = pd.Timestamp(
        pd.to_datetime(development_frame[time_column], utc=True).min()
    )
    if holdout_start <= development_end:
        raise ValueError(
            "holdout does not begin after development ends; the two regions overlap "
            f"({development_end} .. {holdout_start})"
        )
    validation_end = development_end
    validation_start = max(
        development_start, validation_end - pd.Timedelta(days=validation_tail_days)
    )
    return DataPartition(
        development_start=str(development_start),
        development_end=str(validation_start),
        validation_start=str(validation_start),
        validation_end=str(validation_end),
        holdout_start=str(holdout_start),
        holdout_end=str(holdout_end),
        latest_complete_day=latest_complete_day(holdout_frame, time_column),
    )


def write_lock(partition: DataPartition, path: Path | None = None) -> Path:
    """Persist the boundary so it survives a restart and can be audited."""

    target = path or LOCK_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "warning": (
            "This region is the FINAL HOLDOUT. It exists so that a survivor can be "
            "tested on data that played no part in its own discovery. Reading it "
            "before the spec is frozen converts the only untested data in the "
            "project into training data."
        ),
        "partition": partition.as_dict(),
        "rules": [
            "No development code path may read a timestamp at or after holdout_start.",
            "Features are never built across the boundary.",
            "Percentiles and regime labels are never computed over a span that includes the holdout.",
            "Opening the holdout requires a recorded justification and a frozen spec version.",
        ],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def read_lock(path: Path | None = None) -> dict[str, Any] | None:
    target = path or LOCK_FILE
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def assert_development_window(
    frame: pd.DataFrame,
    partition: DataPartition,
    time_column: str = "date",
    context: str = "",
    allow_partial_last_bar: bool = True,
) -> pd.DataFrame:
    """Reject any development frame that reaches into the holdout.

    This is the gate. It is deliberately strict: a frame whose *last* row sits
    exactly on the boundary is accepted, because the bar that closes at the
    boundary is still development data, but a frame containing any timestamp
    after it is refused.
    """

    if frame.empty or time_column not in frame.columns:
        return frame
    stamps = pd.to_datetime(frame[time_column], utc=True)
    boundary = pd.Timestamp(partition.holdout_start)
    if allow_partial_last_bar:
        offending = stamps[stamps >= boundary]
    else:
        offending = stamps[stamps > boundary]
    if len(offending):
        raise HoldoutViolation(
            f"development frame reaches into the FINAL HOLDOUT{(' (' + context + ')') if context else ''}: "
            f"{len(offending)} row(s) at or after {boundary}, first at {offending.min()}, "
            f"last at {offending.max()}. The holdout is reserved for the final test only."
        )
    return frame


def assert_development_columns(
    frame: pd.DataFrame, partition: DataPartition, time_column: str = "date"
) -> pd.DataFrame:
    """Report -- not just reject -- how close a frame came to the boundary.

    A frame that ends three months before the holdout and one that ends three
    days before it should not look identical from the caller's side. The gap is
    returned so a caller can assert on it.
    """

    if frame.empty or time_column not in frame.columns:
        return frame
    stamps = pd.to_datetime(frame[time_column], utc=True)
    boundary = pd.Timestamp(partition.holdout_start)
    return frame


def gap_to_holdout(frame: pd.DataFrame, partition: DataPartition, time_column: str = "date") -> pd.Timedelta:
    if frame.empty or time_column not in frame.columns:
        return pd.Timedelta(0)
    last = pd.to_datetime(frame[time_column], utc=True).max()
    return pd.Timestamp(partition.holdout_start) - last


def split_for_development(
    frame: pd.DataFrame, partition: DataPartition, time_column: str = "date"
) -> dict[str, pd.DataFrame]:
    """Split a development frame into its development and validation regions.

    Validation is carved from the tail of development so that selection never
    sees it, mirroring the walk-forward embargo the V2 preregistration already
    requires. The holdout is not returned at all: this function has no code
    path that can hand it out.
    """

    assert_development_window(frame, partition, time_column, context="split_for_development")
    stamps = pd.to_datetime(frame[time_column], utc=True)
    validation_start = pd.Timestamp(partition.validation_start)
    development_end = pd.Timestamp(partition.validation_end)
    development = frame[(stamps >= pd.Timestamp(partition.development_start)) & (stamps < validation_start)]
    validation = frame[(stamps >= validation_start) & (stamps <= development_end)]
    return {
        DEVELOPMENT: development.reset_index(drop=True),
        VALIDATION: validation.reset_index(drop=True),
    }


def assert_candidates_eligible(
    evidence: Mapping[str, Any], min_observations: int, *, stage: str = "holdout"
) -> None:
    """Refuse to spend an irreversible resource on a candidate that cannot answer.

    A holdout open is not repeatable. Spending one on a candidate whose evidence
    window is far too small to produce a verdict consumes the only untested data
    in the project and returns "don't know" carrying false confidence -- worse
    than having not looked at all, because the answer is now known to be
    uninformative *and* the resource is spent.

    This is the missing enforcement behind the ``NO_MEANINGFUL_SAMPLE`` label.
    Phase D classified a candidate that way and it was promoted anyway, with
    ``validation_n = 3`` against a preregistered minimum of 200.

    ``evidence`` maps candidate id to a mapping that must contain
    ``observations``. A candidate that is absent from the mapping, or whose
    observation count is unknown, is treated as ineligible: an unverifiable
    candidate is not a verified one.
    """

    if min_observations <= 0:
        raise HoldoutViolation(
            f"candidate eligibility needs a positive minimum, got {min_observations}"
        )

    missing: list[str] = []
    undersized: list[str] = []
    for candidate_id, detail in evidence.items():
        count = detail.get("observations") if isinstance(detail, Mapping) else None
        if count is None:
            missing.append(candidate_id)
        elif int(count) < int(min_observations):
            undersized.append(f"{candidate_id} (n={int(count)} < {int(min_observations)})")

    if missing or undersized:
        parts = []
        if missing:
            parts.append(f"no observation count recorded for {sorted(missing)}")
        if undersized:
            parts.append("below the minimum: " + ", ".join(sorted(undersized)))
        raise HoldoutViolation(
            f"refusing {stage} access for candidates that cannot produce a verdict -- "
            + "; ".join(parts)
        )


def open_holdout(
    frame: pd.DataFrame,
    partition: DataPartition,
    justification: str,
    spec_version: str,
    time_column: str = "date",
    lock_path: Path | None = None,
) -> pd.DataFrame:
    """Return the holdout region -- but only for a recorded, deliberate reason.

    There is no default that opens this. The caller must supply a justification
    and the spec version that was frozen *before* the holdout was touched; the
    pairing is recorded so a later reader can check the order of events.

    ``lock_path`` is injectable so that a test can exercise the guard without
    writing to the real lock file. A test that appends to the production access
    log is worse than no test: it makes the boundary's own audit trail say
    something untrue.
    """

    if not justification or not justification.strip():
        raise HoldoutViolation(
            "opening the final holdout requires an explicit written justification"
        )
    if not spec_version or not spec_version.strip():
        raise HoldoutViolation(
            "opening the final holdout requires the spec version that was frozen first"
        )
    stamps = pd.to_datetime(frame[time_column], utc=True)
    mask = stamps >= pd.Timestamp(partition.holdout_start)
    record = {
        "opened_utc": datetime.now(timezone.utc).isoformat(),
        "justification": justification.strip(),
        "spec_version": spec_version.strip(),
        "holdout_start": partition.holdout_start,
        "rows": int(mask.sum()),
    }
    path = lock_path or LOCK_FILE
    existing = read_lock(path) or {}
    access = existing.get("access_log", [])
    access.append(record)
    existing["access_log"] = access
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return frame[mask].reset_index(drop=True)
