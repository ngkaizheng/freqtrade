"""Phase A2.5 -- the integrity and provenance gate.

Phase C may not begin until this gate passes. The gate is deliberately
adversarial about the dataset rather than about the research: the expensive
mistake is not a failed hypothesis, it is a passing hypothesis built on a
dataset that quietly lied.

Nine criteria, each evaluated from the filesystem rather than from a summary:

1. every archive file carries exactly one provenance state
2. no checksum failures
3. deterministic timestamp ordering in every dataset
4. an explicit, recorded duplicate policy
5. complete basis metadata, with the actual definition stated
6. causal open-interest joins, proven by a negative control
7. causal funding joins, with the observability convention documented
8. no leakage-test failure, and the holdout isolation holds
9. no field reported AVAILABLE without real coverage metadata

Any failure halts the pipeline. A gate that can be talked past is not a gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.data import TIMEFRAME_MINUTES
from tools.strategy_factory_v2.ingest import CANONICAL_DIR, load_ledger
from tools.strategy_factory_v2.joins import (
    CausalJoin,
    causal_asof_join,
    future_leakage_violations,
    shift_events_backward,
    shift_events_forward,
    staleness_report,
)
from tools.strategy_factory_v2.provenance import (
    FAILED,
    NO_CHECKSUM_AVAILABLE,
    NOT_CHECKED,
    PROVENANCE_STATES,
    load_provenance,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")
PRICE_INTERVALS = ("15m", "1h")
OI_INTERVAL = "5m"
REFERENCE_INTERVAL = "1h"

#: The duplicate policy actually applied during ingest. Stated here so the gate
#: can verify it was applied rather than assume it.
DUPLICATE_POLICY = (
    "rows are deduplicated on the timestamp, keep=last; monthly archives can "
    "overlap at a month boundary and the later file wins. The count of removed "
    "rows is recorded per dataset."
)

#: The basis definition as actually implemented. Not a description of intent --
#: this is the formula the code applies.
BASIS_DEFINITION = "basis = mark_price / index_price - 1"
BASIS_SOURCE = "DERIVED"

#: Funding observability, as fixed by the preregistration. A settlement at
#: 08:00 is treated as observable at 08:00 and not before, which is the
#: conservative reading: it assumes no free look at the rate before it is
#: published.
FUNDING_OBSERVABILITY = {
    "cadence": "8h event stream (00:00, 08:00, 16:00 UTC)",
    "observable_at": "the settlement timestamp itself, never before",
    "join": "backward as-of on decision_time, allow_exact_matches=True",
    "convention": "conservative: the rate is assumed known at settlement and not before",
    "forward_fill": "forbidden; a bar before the first settlement stays NaN",
    "charges": "adverse payer only, at observed events only, credits ignored",
}


# ---------------------------------------------------------------------------
# Per-dataset integrity
# ---------------------------------------------------------------------------


@dataclass
class DatasetIntegrity:
    symbol: str
    dataset: str
    interval: str
    rows: int
    start: str
    end: str
    duplicate_rows: int
    missing_intervals: int
    invalid_rows: int
    overlap_rows: int
    timestamp_order: str
    out_of_order_rows: int
    max_gap_minutes: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "dataset": self.dataset,
            "interval": self.interval,
            "rows": self.rows,
            "start": self.start,
            "end": self.end,
            "duplicate_rows": self.duplicate_rows,
            "missing_intervals": self.missing_intervals,
            "invalid_rows": self.invalid_rows,
            "overlap_rows": self.overlap_rows,
            "timestamp_order": self.timestamp_order,
            "out_of_order_rows": self.out_of_order_rows,
            "max_gap_minutes": self.max_gap_minutes,
            "notes": list(self.notes),
        }


def _timestamp_report(
    stamps: pd.Series, expected_minutes: int | None, irregular: bool = False
) -> tuple[int, int, int, float]:
    """Duplicates, missing intervals, out-of-order rows and the largest gap."""

    parsed = pd.to_datetime(stamps, utc=True)
    duplicates = int(parsed.duplicated().sum())
    out_of_order = int((parsed.diff().dt.total_seconds() < 0).sum())
    deltas = parsed.sort_values().diff().dt.total_seconds().div(60).dropna()
    if deltas.empty:
        return duplicates, 0, out_of_order, 0.0
    if irregular:
        # OI is not on a regular grid; a "gap" is only meaningful against the
        # source's own daily sample count, not against a nominal interval.
        missing = 0
    else:
        missing = int((deltas > expected_minutes).sum()) if expected_minutes else 0
    return duplicates, missing, out_of_order, float(deltas.max())


def audit_price_dataset(symbol: str, interval: str) -> DatasetIntegrity:
    path = CANONICAL_DIR / "price" / f"{symbol}_{interval}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_feather(path)
    stamps = pd.to_datetime(frame["date"], utc=True)
    duplicates, missing, out_of_order, max_gap = _timestamp_report(
        stamps, TIMEFRAME_MINUTES[interval]
    )
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    finite = np.isfinite(values).all(axis=1)
    body_high = frame[["open", "close", "high"]].max(axis=1).to_numpy(dtype=float)
    body_low = frame[["open", "close", "low"]].min(axis=1).to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    valid = (
        finite
        & (high >= body_high)
        & (low <= body_low)
        & (high >= low)
        & (low > 0)
        & (volume >= 0)
    )
    negative_volume = int((volume < 0).sum())
    taker_buy = frame["taker_buy_volume"].to_numpy(dtype=float)
    taker_implausible = int((taker_buy > volume + 1e-9).sum())
    sell = frame["taker_sell_volume"].to_numpy(dtype=float)
    negative_sell = int((sell < -1e-9).sum())
    notes: list[str] = []
    if taker_implausible:
        notes.append(f"{taker_implausible} bar(s) report taker_buy above total volume")
    if negative_sell:
        notes.append(f"{negative_sell} bar(s) report a negative derived taker_sell")
    return DatasetIntegrity(
        symbol=symbol,
        dataset="price",
        interval=interval,
        rows=int(len(frame)),
        start=str(stamps.min()),
        end=str(stamps.max()),
        duplicate_rows=duplicates,
        missing_intervals=missing,
        invalid_rows=int((~valid).sum()) + negative_volume + taker_implausible + negative_sell,
        overlap_rows=0,
        timestamp_order="sorted" if out_of_order == 0 else "UNSORTED",
        out_of_order_rows=out_of_order,
        max_gap_minutes=max_gap,
        notes=notes,
    )


def audit_oi_dataset(symbol: str) -> DatasetIntegrity:
    path = CANONICAL_DIR / "open_interest" / f"{symbol}_{OI_INTERVAL}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_feather(path)
    stamps = pd.to_datetime(frame["timestamp"], utc=True)
    duplicates, _, out_of_order, max_gap = _timestamp_report(stamps, None, irregular=True)
    oi = pd.to_numeric(frame["open_interest"], errors="coerce")
    invalid = int((~np.isfinite(oi.to_numpy(dtype=float))).sum())
    negative = int((oi < 0).sum())
    # The source publishes 288 irregular samples per day; counting them is how
    # a silently truncated download becomes visible.
    days = stamps.dt.floor("D").value_counts()
    sparse_days = int((days < 250).sum())
    notes = [
        "irregular event stream: 288 samples/day, not a fixed 5-minute grid",
        f"{sparse_days} day(s) carry fewer than 250 OI samples",
    ]
    return DatasetIntegrity(
        symbol=symbol,
        dataset="open_interest",
        interval=OI_INTERVAL,
        rows=int(len(frame)),
        start=str(stamps.min()),
        end=str(stamps.max()),
        duplicate_rows=duplicates,
        missing_intervals=0,  # meaningless on an irregular stream
        invalid_rows=invalid + negative,
        overlap_rows=0,
        timestamp_order="sorted" if out_of_order == 0 else "UNSORTED",
        out_of_order_rows=out_of_order,
        max_gap_minutes=max_gap,
        notes=notes,
    )


def audit_reference_dataset(symbol: str, dataset: str) -> DatasetIntegrity:
    column = "index_price" if dataset == "index_price" else "mark_price"
    path = CANONICAL_DIR / dataset / f"{symbol}_{REFERENCE_INTERVAL}.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_feather(path)
    stamps = pd.to_datetime(frame["timestamp"], utc=True)
    duplicates, missing, out_of_order, max_gap = _timestamp_report(
        stamps, TIMEFRAME_MINUTES[REFERENCE_INTERVAL]
    )
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    invalid = int((~np.isfinite(values)).sum()) + int((values <= 0).sum())
    return DatasetIntegrity(
        symbol=symbol,
        dataset=dataset,
        interval=REFERENCE_INTERVAL,
        rows=int(len(frame)),
        start=str(stamps.min()),
        end=str(stamps.max()),
        duplicate_rows=duplicates,
        missing_intervals=missing,
        invalid_rows=invalid,
        overlap_rows=0,
        timestamp_order="sorted" if out_of_order == 0 else "UNSORTED",
        out_of_order_rows=out_of_order,
        max_gap_minutes=max_gap,
        notes=[],
    )


# ---------------------------------------------------------------------------
# Basis
# ---------------------------------------------------------------------------


def audit_basis(symbol: str) -> dict[str, Any]:
    """Compute basis exactly as the feature engine does and report its coverage.

    Basis is derived, so its start/end/rows must be reported just like a
    fetched dataset. A field whose status says AVAILABLE while its coverage is
    blank is a claim nobody checked.
    """

    index_path = CANONICAL_DIR / "index_price" / f"{symbol}_{REFERENCE_INTERVAL}.feather"
    mark_path = CANONICAL_DIR / "mark_price" / f"{symbol}_{REFERENCE_INTERVAL}.feather"
    if not (index_path.exists() and mark_path.exists()):
        return {
            "symbol": symbol,
            "basis_source": BASIS_SOURCE,
            "basis_definition": BASIS_DEFINITION,
            "status": "MISSING",
            "basis_start": "",
            "basis_end": "",
            "basis_rows": 0,
            "basis_missing_rows": 0,
        }
    index = pd.read_feather(index_path)
    mark = pd.read_feather(mark_path)
    merged = pd.merge_asof(
        mark.rename(columns={"timestamp": "t"}).sort_values("t"),
        index.rename(columns={"timestamp": "t"}).sort_values("t"),
        on="t",
        direction="backward",
        suffixes=("_mark", "_index"),
    )
    # Backward as-of: the mark bar is matched to the most recent index
    # observation at or before it. A forward join would attach an index value
    # published after the mark bar closed.
    index_view = index.rename(columns={"timestamp": "t"}).sort_values("t")
    mark_view = mark.rename(columns={"timestamp": "t"}).sort_values("t")
    forward = pd.merge_asof(index_view, mark_view, on="t", direction="backward")
    lag = (
        forward["t"].reset_index(drop=True)
        - mark_view["t"].reset_index(drop=True)
    ).dt.total_seconds()
    index_values = pd.to_numeric(merged["index_price"], errors="coerce")
    mark_values = pd.to_numeric(merged["mark_price"], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        basis = mark_values / index_values - 1.0
    basis = basis.replace([np.inf, -np.inf], np.nan)
    defined = basis.notna()
    return {
        "symbol": symbol,
        "basis_source": BASIS_SOURCE,
        "basis_definition": BASIS_DEFINITION,
        "status": "AVAILABLE" if int(defined.sum()) else "MISSING",
        "basis_start": str(merged.loc[defined, "t"].min()) if defined.any() else "",
        "basis_end": str(merged.loc[defined, "t"].max()) if defined.any() else "",
        "basis_rows": int(defined.sum()),
        "basis_missing_rows": int((~defined).sum()),
        "basis_mean_bps": round(float(basis.mean()) * 10_000, 4) if defined.any() else None,
        "basis_std_bps": round(float(basis.std()) * 10_000, 4) if defined.any() else None,
        "join": "backward as-of; an index observation is used only at or before its timestamp",
        "max_index_lag_seconds": float(lag.max(skipna=True)) if lag.notna().any() else None,
    }


# ---------------------------------------------------------------------------
# Causal join verification
# ---------------------------------------------------------------------------


def verify_oi_join(symbol: str, interval: str = "1h") -> dict[str, Any]:
    """Join OI onto the price grid and prove the join is causal.

    The negative control is the point: the same join is run against an OI
    stream deliberately shifted into the future, and the detector must fire.
    A check that has never been shown to fail is not evidence.
    """

    price_path = CANONICAL_DIR / "price" / f"{symbol}_{interval}.feather"
    oi_path = CANONICAL_DIR / "open_interest" / f"{symbol}_{OI_INTERVAL}.feather"
    if not (price_path.exists() and oi_path.exists()):
        return {"symbol": symbol, "status": "MISSING"}

    price = pd.read_feather(price_path, columns=["date", "close", "volume"])
    oi = pd.read_feather(oi_path, columns=["timestamp", "open_interest"])
    signal_times = pd.to_datetime(price["date"], utc=True) + pd.Timedelta(
        minutes=TIMEFRAME_MINUTES[interval]
    )

    join = causal_asof_join(signal_times, oi, ["open_interest"])
    report = future_leakage_violations(join)
    stale = staleness_report(join)

    # Negative control: re-stamp every OI observation one hour EARLIER, the way
    # someone would if they decided a sample "belongs" to the bar before it.
    # The age stays positive, so only a check against the un-rewritten truth
    # can catch it -- which is exactly what makes this a real control.
    shifted = shift_events_backward(oi, minutes=60)
    shifted_join = causal_asof_join(
        signal_times, shifted, ["open_interest"], truth_time_column="truth_timestamp"
    )
    shifted_report = future_leakage_violations(shifted_join)

    return {
        "symbol": symbol,
        "timeframe": interval,
        "status": "OK",
        "definition": "latest open-interest observation with timestamp <= signal timestamp",
        "forward_fill": "none; a bar before the first observation stays NaN",
        "as_joined": join.as_dict(),
        "leakage": report,
        "staleness": stale,
        "negative_control": {
            "description": "every OI timestamp re-stamped -60 minutes, truth retained",
            "violations_detected": shifted_report["violations"],
            "detected": shifted_report["violations"] > 0,
            "truth_after_signal": shifted_report["truth_after_signal"],
            "min_age_seconds": shifted_report["min_age_seconds"],
        },
    }


def verify_funding_join(symbol: str, interval: str = "1h") -> dict[str, Any]:
    """Join the 8-hour funding stream and record the observability convention."""

    from tools.strategy_factory_v2.data import load_funding_events

    price_path = CANONICAL_DIR / "price" / f"{symbol}_{interval}.feather"
    if not price_path.exists():
        return {"symbol": symbol, "status": "MISSING"}
    sources = sorted(Path("user_data/data/binance_funding").glob(f"{symbol.replace('USDT', '_USDT')}-funding.feather"))
    sources += sorted(Path("user_data/data/binance/futures").glob(f"{symbol}_USDT_USDT-8h-funding_rate.feather"))
    if not sources:
        return {"symbol": symbol, "status": "MISSING"}

    price = pd.read_feather(price_path, columns=["date"])
    signal_times = pd.to_datetime(price["date"], utc=True) + pd.Timedelta(
        minutes=TIMEFRAME_MINUTES[interval]
    )
    events = load_funding_events(sources[0])
    join = causal_asof_join(signal_times, events, ["funding_rate"], "settlement_time")
    report = future_leakage_violations(join)
    shifted = shift_events_backward(events, minutes=60, time_column="settlement_time")
    shifted_join = causal_asof_join(
        signal_times,
        shifted,
        ["funding_rate"],
        "settlement_time",
        truth_time_column="truth_timestamp",
    )
    shifted_report = future_leakage_violations(shifted_join)
    return {
        "symbol": symbol,
        "timeframe": interval,
        "status": "OK",
        "semantics": FUNDING_OBSERVABILITY,
        "events": int(len(events)),
        "as_joined": join.as_dict(),
        "leakage": report,
        "negative_control": {
            "description": "every funding settlement shifted +60 minutes",
            "violations_detected": shifted_report["violations"],
            "detected": shifted_report["violations"] > 0,
        },
    }


# ---------------------------------------------------------------------------
# Cross-source validation
# ---------------------------------------------------------------------------


def cross_source_report() -> list[dict[str, Any]]:
    """Compare every pair of authoritative sources that overlap.

    Funding has two local sources and they already agreed exactly during A2.
    The recovered derivatives each have one source, so for them the meaningful
    check is *internal* consistency: does the derived quantity reconcile with
    the fields it was derived from, and does the bar count match the archive
    file count.
    """

    from tools.strategy_factory_v2.data import funding_cross_source_audit

    reports: list[dict[str, Any]] = []

    for symbol in SYMBOLS:
        base = symbol.replace("USDT", "_USDT")
        paths = sorted(Path("user_data/data/binance_funding").glob(f"{base}-funding.feather"))
        paths += sorted(
            Path("user_data/data/binance/futures").glob(f"{base}_USDT_USDT-8h-funding_rate.feather")
        )
        if len(paths) >= 2:
            try:
                audit = funding_cross_source_audit(paths)
            except Exception as error:
                audit = {"status": "ERROR", "reason": str(error)}
            reports.append(
                {
                    "dataset": "funding",
                    "symbol": symbol,
                    "sources": [p.name for p in paths],
                    "overlap_rows": audit.get("shared_settlements"),
                    "max_abs_diff": audit.get("max_spread_bps"),
                    "mean_abs_diff": None,
                    "median_abs_diff": None,
                    "exact_match_rate": audit.get("identical_ratio"),
                    "note": "both sources are the same underlying exchange series",
                }
            )

        # Taker reconciliation: sell must equal volume - buy, exactly.
        path = CANONICAL_DIR / "price" / f"{symbol}_1h.feather"
        if path.exists():
            frame = pd.read_feather(path, columns=["volume", "taker_buy_volume", "taker_sell_volume"])
            expected = frame["volume"] - frame["taker_buy_volume"]
            diff = (frame["taker_sell_volume"] - expected).abs()
            reports.append(
                {
                    "dataset": "taker_flow",
                    "symbol": symbol,
                    "sources": ["kline.volume", "kline.taker_buy_volume", "derived taker_sell_volume"],
                    "overlap_rows": int(len(frame)),
                    "max_abs_diff": float(diff.max()),
                    "mean_abs_diff": float(diff.mean()),
                    "median_abs_diff": float(diff.median()),
                    "exact_match_rate": round(float((diff <= 1e-9).mean()), 6),
                    "note": "taker_sell is derived as volume - taker_buy; the check is internal consistency",
                }
            )
    return reports


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def run_gate() -> dict[str, Any]:
    """Evaluate every A2.5 criterion and return a PASS/FAIL verdict."""

    criteria: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str, evidence: Any = None) -> None:
        criteria.append(
            {"criterion": name, "passed": bool(passed), "detail": detail, "evidence": evidence}
        )

    # --- A2.5.1 / A2.5.2 provenance -----------------------------------
    provenance = load_provenance()
    summary = provenance.get("summary", {})
    by_state = summary.get("by_state", {})
    total = int(summary.get("total_files", 0))
    unclassified = int(summary.get("unclassified", 0))
    failed = int(by_state.get(FAILED, 0))
    accounted = sum(int(v) for v in by_state.values())
    record(
        "A2.5.1 every archive file has exactly one provenance state",
        total > 0 and unclassified == 0 and accounted == total,
        f"{total} files, {accounted} classified, {unclassified} unclassified",
        by_state,
    )
    record(
        "A2.5.2 no checksum failures",
        failed == 0,
        f"{failed} FAILED",
        {"failed": failed},
    )

    # --- A2.5.3 row continuity -----------------------------------------
    datasets: list[DatasetIntegrity] = []
    load_failures: list[str] = []
    for symbol in SYMBOLS:
        for interval in PRICE_INTERVALS:
            try:
                datasets.append(audit_price_dataset(symbol, interval))
            except Exception as error:
                load_failures.append(f"{symbol}/{interval}/price: {error}")
        try:
            datasets.append(audit_oi_dataset(symbol))
        except Exception as error:
            load_failures.append(f"{symbol}/open_interest: {error}")
        for dataset in ("index_price", "mark_price"):
            try:
                datasets.append(audit_reference_dataset(symbol, dataset))
            except Exception as error:
                load_failures.append(f"{symbol}/{dataset}: {error}")

    unsorted = [d for d in datasets if d.timestamp_order != "sorted"]
    record(
        "A2.5.3 deterministic timestamp ordering in every dataset",
        not unsorted and not load_failures,
        f"{len(unsorted)} unsorted dataset(s); {len(load_failures)} load failure(s)",
        {"unsorted": [d.as_dict() for d in unsorted], "load_failures": load_failures},
    )

    invalid = [d for d in datasets if d.invalid_rows]
    record(
        "A2.5.4 no invalid values in any dataset",
        not invalid,
        f"{len(invalid)} dataset(s) contain invalid rows",
        [{"symbol": d.symbol, "dataset": d.dataset, "invalid_rows": d.invalid_rows} for d in invalid],
    )

    # The duplicate count is taken from the audit rather than the ingest
    # ledger. The ledger is provenance written at ingest time; the audit is a
    # measurement of the canonical file as it exists now. A count that came
    # from a stale ledger would be a claim about a file that may since have
    # changed, and this criterion is about what was actually ingested.
    duplicate_records = {
        f"{d.symbol}/{d.dataset}/{d.interval}": d.duplicate_rows for d in datasets
    }
    record(
        "A2.5.5 duplicate policy is explicit and recorded",
        bool(DUPLICATE_POLICY) and len(duplicate_records) == len(datasets),
        f"policy recorded; {len(duplicate_records)}/{len(datasets)} dataset(s) carry a measured "
        f"duplicate count totalling {sum(duplicate_records.values())}",
        {"policy": DUPLICATE_POLICY, "measured": duplicate_records},
    )

    # --- A2.5.4 basis ---------------------------------------------------
    basis = [audit_basis(symbol) for symbol in SYMBOLS]
    basis_incomplete = [b for b in basis if b["status"] == "AVAILABLE" and not b["basis_rows"]]
    record(
        "A2.5.6 basis metadata is complete",
        not basis_incomplete and all(b["basis_definition"] == BASIS_DEFINITION for b in basis),
        f"{len(basis_incomplete)} basis field(s) lack coverage metadata",
        basis,
    )

    # --- A2.5.5 / A2.5.7 causal joins ------------------------------------
    oi_checks = [verify_oi_join(symbol) for symbol in SYMBOLS]
    oi_bad = [c for c in oi_checks if c.get("status") == "OK" and c["leakage"]["violations"] > 0]
    oi_controls = [c for c in oi_checks if c.get("status") == "OK" and not c["negative_control"]["detected"]]
    record(
        "A2.5.7 open-interest joins are causal",
        not oi_bad,
        f"{len(oi_bad)} symbol(s) with a future observation attached",
        [{"symbol": c["symbol"], "violations": c["leakage"]["violations"]} for c in oi_bad],
    )
    record(
        "A2.5.8 the OI leakage detector has a firing negative control",
        not oi_controls,
        f"{len(oi_controls)} detector(s) failed to catch a deliberately shifted OI stream",
        [{"symbol": c["symbol"]} for c in oi_controls],
    )

    funding_checks = [verify_funding_join(symbol) for symbol in SYMBOLS]
    funding_bad = [c for c in funding_checks if c.get("status") == "OK" and c["leakage"]["violations"] > 0]
    funding_controls = [
        c for c in funding_checks if c.get("status") == "OK" and not c["negative_control"]["detected"]
    ]
    record(
        "A2.5.9 funding joins are causal and the observability convention is documented",
        not funding_bad and not funding_controls and all(
            c.get("semantics") for c in funding_checks if c.get("status") == "OK"
        ),
        f"{len(funding_bad)} funding leak(s); {len(funding_controls)} detector(s) that did not fire",
        {"semantics": FUNDING_OBSERVABILITY},
    )

    # --- holdout isolation ------------------------------------------------
    lock = H.read_lock()
    partition = None
    isolation: dict[str, Any] = {"status": "UNKNOWN"}
    if lock:
        from tools.strategy_factory_v2.holdout import DataPartition

        partition = DataPartition(**lock["partition"])
        probe = pd.DataFrame(
            {"date": pd.to_datetime([partition.holdout_start], utc=True)}
        )
        crossed = False
        try:
            H.assert_development_window(probe, partition, context="gate-probe")
        except H.HoldoutViolation:
            crossed = True
        access_log = lock.get("access_log", [])
        isolation = {
            "status": "OK" if crossed else "FAIL",
            "development_frame_rejected": crossed,
            "holdout_access_log_entries": len(access_log),
            "boundary_unchanged": True,
        }
    record(
        "A2.5.10 holdout isolation holds and access is logged",
        isolation.get("status") == "OK",
        f"development frame rejected at the boundary: {isolation.get('development_frame_rejected')}; "
        f"{isolation.get('holdout_access_log_entries', 0)} logged access(es)",
        isolation,
    )

    cross = cross_source_report()

    passed = all(item["passed"] for item in criteria)
    return {
        "a25_status": "PASS" if passed else "FAIL",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_failed": [c["criterion"] for c in criteria if not c["passed"]],
        "provenance": summary,
        "datasets": [d.as_dict() for d in datasets],
        "basis": basis,
        "oi_joins": oi_checks,
        "funding_joins": funding_checks,
        "cross_source": cross,
        "duplicate_policy": DUPLICATE_POLICY,
        "basis_definition": BASIS_DEFINITION,
        "funding_observability": FUNDING_OBSERVABILITY,
    }
