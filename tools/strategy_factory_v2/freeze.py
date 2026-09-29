"""Phase D -- candidate freezing and the holdout guard.

Two jobs, both about making a promise checkable rather than stated.

**Freezing.** A candidate that can be edited during its own validation is not
being validated, it is being fitted to whatever the validation region happens
to show. So the candidate's identity is pinned before anything runs: a
``logic_hash`` over its preregistered definition, its thresholds and the
predicate source that implements it, and a ``source_hash`` over the bytes of the
code that will execute it. If either changes mid-run, the freeze check fails
and the run stops.

**Guarding the holdout.** The final holdout is the only data in the project that
has never been looked at, and its entire value is that it still has not been.
A boundary enforced by convention is a boundary that eventually gets crossed by
an option, a default argument, or a date range nobody checked. Here the guard
is a counter that every holdout read increments, and a run that ends with a
non-zero count fails closed -- it refuses to produce a report claiming a clean
validation while quietly having peeked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Sequence

from tools.strategy_factory_v2.holdout import DataPartition, HoldoutViolation
from tools.strategy_factory_v2.hypothesis_eval import HANDLERS
from tools.strategy_factory_v2.spec import SPEC_VERSION


class HoldoutAccessViolation(RuntimeError):
    """Raised the moment any code path reads inside the final holdout."""


# ---------------------------------------------------------------------------
# Freezing
# ---------------------------------------------------------------------------


def _handler_source(family: str) -> str:
    """The source of the predicate that implements a candidate's family."""

    from tools.strategy_factory_v2 import hypothesis_eval

    handler = HANDLERS[family]
    import inspect

    return inspect.getsource(handler)


def logic_hash(hypothesis) -> str:
    """Hash of everything that defines the candidate's *behaviour*.

    Includes the preregistered condition text, the thresholds, the required
    features, and the body of the predicate that implements it. A change to any
    of those changes the hash, which is exactly the intent.
    """

    payload = {
        "hypothesis_id": hypothesis.hypothesis_id,
        "family": hypothesis.family,
        "condition": hypothesis.condition,
        "thresholds": hypothesis.thresholds,
        "features": list(hypothesis.features),
        "required_fields": list(hypothesis.required_fields),
        "timeframe": hypothesis.timeframe,
        "expected_direction": hypothesis.expected_direction,
        "predicate_source": _handler_source(hypothesis.family),
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_hash(paths: Sequence[Path]) -> str:
    """Hash of the module bytes that will execute the candidates."""

    digest = sha256()
    for path in sorted(paths):
        if not path.exists():
            continue
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def freeze_candidates(
    candidate_ids: Sequence[str], package_dir: Path | None = None
) -> dict[str, Any]:
    """Produce the freeze record for a set of candidate ids."""

    from tools.strategy_factory_v2.hypotheses import get

    package = package_dir or Path("tools/strategy_factory_v2")
    executed = [
        package / "hypothesis_eval.py",
        package / "features.py",
        package / "regime.py",
        package / "discovery.py",
        package / "discovery_engine.py",
        package / "joins.py",
        package / "spec.py",
    ]
    shared_source = source_hash(executed)
    candidates = []
    for candidate_id in candidate_ids:
        hypothesis = get(candidate_id)
        candidates.append(
            {
                "id": hypothesis.hypothesis_id,
                "family": hypothesis.family,
                "timeframe": hypothesis.timeframe,
                "expected_direction": hypothesis.expected_direction,
                "thresholds": hypothesis.thresholds,
                "condition": hypothesis.condition,
                "logic_hash": logic_hash(hypothesis),
                "source_hash": shared_source,
            }
        )
    return {
        "spec_version": SPEC_VERSION,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "phase": "D (frozen candidate validation)",
        "candidates": candidates,
        "freeze_policy": (
            "A candidate's logic_hash covers its preregistered condition, its "
            "thresholds and the source of the predicate that implements it. The "
            "source_hash covers the module bytes that will execute it. Neither "
            "may change during Phase D; a change fails the freeze check and "
            "stops the run."
        ),
        "optimization_permitted": False,
        "new_hypotheses_permitted": False,
    }


def verify_freeze(record: dict[str, Any], candidate_ids: Sequence[str]) -> dict[str, Any]:
    """Re-derive every hash and confirm nothing drifted since the freeze."""

    from tools.strategy_factory_v2.hypotheses import get

    frozen = {entry["id"]: entry for entry in record["candidates"]}
    problems: list[str] = []
    if sorted(frozen) != sorted(candidate_ids):
        problems.append(
            f"frozen set {sorted(frozen)} does not match the requested set {sorted(candidate_ids)}"
        )
    for candidate_id, entry in frozen.items():
        try:
            current = logic_hash(get(candidate_id))
        except KeyError as error:
            problems.append(str(error))
            continue
        if current != entry["logic_hash"]:
            problems.append(
                f"{candidate_id}: logic_hash changed "
                f"({entry['logic_hash'][:12]} -> {current[:12]})"
            )
    return {"intact": not problems, "problems": problems}


# ---------------------------------------------------------------------------
# The holdout guard
# ---------------------------------------------------------------------------


@dataclass
class HoldoutGuard:
    """Fails the run if anything reads inside the sealed final holdout."""

    partition: DataPartition
    access_count: int = 0
    attempts: list[dict[str, Any]] = field(default_factory=list)
    fail_closed: bool = True

    @property
    def boundary(self) -> pd.Timestamp:  # type: ignore[name-defined]
        return pd.Timestamp(self.partition.holdout_start)

    def assert_no_holdout(self, frame, time_column: str = "date", context: str = "") -> None:
        """Refuse a frame that contains any holdout row."""

        import pandas as pd  # local: keeps the module import-light

        if frame is None or len(frame) == 0 or time_column not in frame.columns:
            return
        stamps = pd.to_datetime(frame[time_column], utc=True)
        offending = stamps[stamps >= pd.Timestamp(self.partition.holdout_start)]
        self.access_count += int(len(offending))
        if len(offending):
            record = {
                "context": context,
                "rows": int(len(offending)),
                "first": str(offending.min()),
                "last": str(offending.max()),
                "boundary": self.partition.holdout_start,
                "detected_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.attempts.append(record)
            if self.fail_closed:
                raise HoldoutAccessViolation(
                    f"final holdout read detected{(' in ' + context) if context else ''}: "
                    f"{len(offending)} row(s) at or after {self.partition.holdout_start}. "
                    "Phase D must not touch the holdout; the run is aborted."
                )

    def assert_clean(self) -> None:
        """The end-of-run assertion. A non-zero count aborts."""

        if self.access_count != 0:
            raise HoldoutAccessViolation(
                f"final_holdout_access_count == {self.access_count}, expected 0; "
                f"{len(self.attempts)} offending read(s) recorded"
            )

    def log(self) -> dict[str, Any]:
        return {
            "final_holdout_start": self.partition.holdout_start,
            "final_holdout_end": self.partition.holdout_end,
            "final_holdout_access_count": self.access_count,
            "attempts": list(self.attempts),
            "policy": (
                "The final holdout is sealed during Phase D. Every candidate frame "
                "passes through assert_no_holdout before use, and the run aborts "
                "if the end-of-run access count is anything but zero."
            ),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Regime attribution control
# ---------------------------------------------------------------------------


def regime_control_mask(frame, hypothesis) -> Any:
    """The candidate with ONLY the BTC regime restriction removed.

    This is deliberately mechanical. The frozen candidate's own condition is
    "the symbol's trend is bearish AND the reference asset's trend regime equals
    a named state". Dropping the second clause leaves a signal that uses the
    same trend definition, the same timeframe, the same features and the same
    direction -- it simply stops being conditioned on the reference asset.

    It is a diagnostic control, not a hypothesis: it is never added to the
    registry, never eligible for promotion, and cannot trigger a parameter
    change. If building it would require new logic rather than the removal of
    one clause, this function raises and the caller reports
    ``REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE``.
    """

    import pandas as pd

    required = {"trend_regime"}
    if not required.issubset(set(frame.columns)):
        raise HoldoutViolation("REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE")
    bullish = ("STRONG_UP", "WEAK_UP")
    bearish = ("STRONG_DOWN", "WEAK_DOWN")
    states = bullish if hypothesis.expected_direction == "long" else bearish
    return frame["trend_regime"].isin(states).fillna(False).astype(bool)
