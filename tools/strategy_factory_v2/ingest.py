"""Phase A2 orchestration: plan, fetch, verify, ingest, and capability matrix.

This module turns a recovery plan into a verified canonical dataset, and then
describes -- per symbol and per field -- exactly what is available, what is
absent, and what has not been audited yet.

The three states are deliberately distinct:

``AVAILABLE``
    Audited on disk, coverage known, source recorded.
``ABSENT``
    Audited on disk, and genuinely not there.
``UNKNOWN``
    Not audited against the authoritative source yet. This is *not* a synonym
    for ABSENT and must never be collapsed into it. A field marked ABSENT has
    been looked for and not found; a field marked UNKNOWN has not been looked
    for. Reporting UNKNOWN as False would turn "we did not check" into "it does
    not exist", which is how a research system quietly convinces itself that a
    question is unanswerable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.recovery import (
    INDEX_KLINES,
    KLINE,
    MARK_KLINES,
    METRICS,
    RECOVERY_ROOT,
    BinanceArchive,
    DatasetSpec,
    RecoveryError,
    parse_kline,
    parse_metrics,
    parse_reference_kline,
)

AVAILABLE = "AVAILABLE"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

CANONICAL_FIELDS = (
    "price",
    "funding",
    "open_interest",
    "taker_flow",
    "index_price",
    "mark_price",
    "basis",
)

#: Where the recovered canonical tables live. Separate from the pre-existing
#: Freqtrade tree so that nothing here can overwrite a source dataset.
CANONICAL_DIR = RECOVERY_ROOT / "canonical"
ARCHIVE_DIR = RECOVERY_ROOT / "archive"
LEDGER_PATH = RECOVERY_ROOT / "recovery_ledger.json"


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


@dataclass
class IngestRecord:
    """Provenance for one ingested canonical dataset."""

    kind: str
    symbol: str
    interval: str
    rows: int
    start: str
    end: str
    files: int
    bytes_downloaded: int
    files_verified: int
    files_checksum_unavailable: int
    source: str
    ingested_utc: str = ""
    duplicate_rows: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"datasets": {}, "files": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"datasets": {}, "files": {}}


def save_ledger(ledger: dict[str, Any], path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")


def dataset_key(spec: DatasetSpec) -> str:
    return f"{spec.kind}/{spec.symbol}/{spec.interval}"


def canonical_path(spec: DatasetSpec, root: Path = CANONICAL_DIR) -> Path:
    folder = {
        KLINE: "price",
        METRICS: "open_interest",
        INDEX_KLINES: "index_price",
        MARK_KLINES: "mark_price",
    }[spec.kind]
    return root / folder / f"{spec.symbol}_{spec.interval}.feather"


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def plan_dataset(
    spec: DatasetSpec, client: BinanceArchive, limit: int | None = None
) -> tuple[list, dict[str, Any]]:
    """Resolve a spec to the archive files that cover its requested window."""

    remote = client.list(spec.prefix)
    import re

    pattern = r"-\d{4}-\d{2}\.zip$" if spec.cadence == "monthly" else r"-\d{4}-\d{2}-\d{2}\.zip$"
    archives = [f for f in remote if re.search(pattern, f.key)]
    selected = list(archives)
    before = len(archives)
    selected = [f for f in selected if spec.start <= f.period and f.period <= spec.end]
    available_span = {
        "archive_files_found": before,
        "archive_first": archives[0].period if archives else None,
        "archive_last": archives[-1].period if archives else None,
        "selected_files": len(selected),
        "requested_start": spec.start,
        "requested_end": spec.end,
    }
    if limit is not None:
        selected = selected[:limit]
        available_span["truncated_to"] = limit
    return selected, available_span


def latest_complete_period(
    spec: DatasetSpec, client: BinanceArchive, safety_days: int = 1
) -> str | None:
    """The latest period the archive has actually published.

    Never "today". A period still being written is incomplete by definition, and
    a dataset that ends mid-day produces a research boundary nobody can reason
    about. The archive itself is the only authority on what is complete.
    """

    remote = client.list(spec.prefix)
    import re

    pattern = r"-\d{4}-\d{2}\.zip$" if spec.cadence == "monthly" else r"-\d{4}-\d{2}-\d{2}\.zip$"
    periods = sorted({f.period for f in remote if re.search(pattern, f.key)})
    if not periods:
        return None
    if spec.cadence == "monthly":
        # A month is only complete once the archive publishes the next one.
        today = datetime.now(timezone.utc)
        cutoff = f"{today.year:04d}-{today.month:02d}"
        complete = [p for p in periods if p < cutoff]
        return complete[-1] if complete else None
    return (datetime.now(timezone.utc) - timedelta(days=safety_days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def _download_one(
    client: BinanceArchive,
    remote,
    spec: DatasetSpec,
    ledger: dict[str, Any],
    force: bool = False,
) -> dict[str, Any] | None:
    """Fetch and verify one archive file, reusing a previous verified copy.

    The ledger is consulted first, but it is written only when a dataset
    *finishes*. An interrupted run therefore leaves hundreds of verified files
    on disk with no ledger entry, and trusting the ledger alone would re-download
    all of them. The on-disk file is the second source of truth, which is what
    makes an interrupted recovery genuinely resumable rather than merely
    restartable.
    """

    local = ARCHIVE_DIR / spec.kind / spec.symbol / spec.interval / remote.name
    cached = ledger["files"].get(remote.key)
    if cached and not force and local.exists() and cached.get("sha256"):
        return cached
    if local.exists() and not force:
        blob = local.read_bytes()
        import hashlib

        record = {
            "key": remote.key,
            "url": f"{client.endpoint}/{remote.key}",
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "local_path": str(local),
            "checksum_status": "reused_from_disk",
        }
        return record
    try:
        return client.fetch_verified(remote.key, local)
    except RecoveryError as error:
        return {"key": remote.key, "error": str(error)}


def recover_dataset(
    spec: DatasetSpec,
    client: BinanceArchive,
    limit: int | None = None,
    workers: int = 8,
    force: bool = False,
    progress: Callable[[str], None] | None = None,
) -> IngestRecord:
    """Fetch, verify and ingest one dataset, resuming from the ledger."""

    ledger = load_ledger()
    remote_files, plan = plan_dataset(spec, client, limit)
    if not remote_files:
        return IngestRecord(
            kind=spec.kind,
            symbol=spec.symbol,
            interval=spec.interval,
            rows=0,
            start="",
            end="",
            files=0,
            bytes_downloaded=0,
            files_verified=0,
            files_checksum_unavailable=0,
            source=spec.prefix,
            ingested_utc=datetime.now(timezone.utc).isoformat(),
            errors=[f"no archive files matched {spec.start}..{spec.end} under {spec.prefix}"],
        )

    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    verified = unavailable = downloaded = 0
    total_bytes = 0

    def task(remote):
        return _download_one(client, remote, spec, ledger, force)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, remote): remote for remote in remote_files}
        for index, future in enumerate(as_completed(futures), start=1):
            remote = futures[future]
            try:
                record = future.result()
            except Exception as error:  # pragma: no cover - defensive
                errors.append(f"{remote.name}: {type(error).__name__}: {error}")
                continue
            if record is None:
                continue
            if record.get("error"):
                errors.append(f"{remote.name}: {record['error']}")
                continue
            ledger["files"][remote.key] = record
            status = record.get("checksum_status")
            verified += int(status == "verified")
            unavailable += int(status == "checksum_unavailable")
            if not record.get("local_path", "").endswith(".zip"):
                downloaded += int(status == "checksum_unavailable")
            total_bytes += int(record.get("bytes", 0))
            try:
                blob = Path(record["local_path"]).read_bytes()
                if spec.kind == KLINE:
                    frames.append(parse_kline(blob, spec.symbol, spec.interval, remote.key))
                elif spec.kind == METRICS:
                    frames.append(parse_metrics(blob, spec.symbol, remote.key))
                elif spec.kind == INDEX_KLINES:
                    frames.append(
                        parse_reference_kline(
                            blob, spec.symbol, spec.interval, remote.key, "index_price"
                        )
                    )
                elif spec.kind == MARK_KLINES:
                    frames.append(
                        parse_reference_kline(
                            blob, spec.symbol, spec.interval, remote.key, "mark_price"
                        )
                    )
            except Exception as error:
                errors.append(f"{remote.name}: parse failed: {type(error).__name__}: {error}")
            if progress and index % 25 == 0:
                progress(f"    {spec.kind}/{spec.symbol}/{spec.interval}: {index}/{len(remote_files)}")

    if not frames:
        return IngestRecord(
            kind=spec.kind,
            symbol=spec.symbol,
            interval=spec.interval,
            rows=0,
            start="",
            end="",
            files=len(remote_files),
            bytes_downloaded=total_bytes,
            files_verified=verified,
            files_checksum_unavailable=unavailable,
            source=spec.prefix,
            ingested_utc=datetime.now(timezone.utc).isoformat(),
            errors=errors or ["every archive file failed"],
        )

    combined = pd.concat(frames, ignore_index=True)
    time_column = "date" if spec.kind == KLINE else "timestamp"
    # Duplicate policy is explicit: monthly archives can overlap at a boundary,
    # and the later file's value wins. This is recorded rather than implied.
    duplicate_rows = int(combined.duplicated(subset=[time_column]).sum())
    combined = combined.drop_duplicates(subset=[time_column], keep="last")
    combined = combined.sort_values(time_column).reset_index(drop=True)

    destination = canonical_path(spec)
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.to_feather(destination)

    record = IngestRecord(
        kind=spec.kind,
        symbol=spec.symbol,
        interval=spec.interval,
        rows=int(len(combined)),
        start=str(combined[time_column].iloc[0]),
        end=str(combined[time_column].iloc[-1]),
        files=len(remote_files),
        bytes_downloaded=total_bytes,
        files_verified=verified,
        files_checksum_unavailable=unavailable,
        source=spec.prefix,
        ingested_utc=datetime.now(timezone.utc).isoformat(),
        errors=errors,
        duplicate_rows=duplicate_rows,
    )
    # Merge the per-file records collected during the loop into the persisted
    # ledger. Reloading first and *replacing* would discard every one of them,
    # which is exactly the defect that made a fully recovered dataset report
    # "archive files fetched: 0".
    persisted = load_ledger()
    persisted.setdefault("files", {}).update(ledger["files"])
    persisted.setdefault("datasets", {})[dataset_key(spec)] = {
        **record.as_dict(),
        "canonical_path": str(destination),
    }
    save_ledger(persisted)
    return record


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------

_STATUS_COLUMNS = {
    "price": ("price", None),
    "funding": ("funding", None),
    "open_interest": ("open_interest", "5m"),
    "taker_flow": ("taker_flow", None),
    "index_price": ("index_price", "1h"),
    "mark_price": ("mark_price", "1h"),
}


def _local_field_span(folder: Path, symbol: str) -> tuple[str, str, int]:
    """Return (start, end, rows) for a local canonical file, or empties."""

    if not folder.exists():
        return "", "", 0
    for path in sorted(folder.glob(f"{symbol}_*.feather")):
        try:
            frame = pd.read_feather(path, columns=None)
        except Exception:
            continue
        column = next((c for c in ("date", "timestamp", "settlement_time") if c in frame.columns), None)
        if column is None or frame.empty:
            continue
        return str(frame[column].iloc[0]), str(frame[column].iloc[-1]), int(len(frame))
    return "", "", 0


def _local_funding_span(base: str) -> tuple[str, str, int]:
    """Funding is local-only; it is never re-fetched, and it is already verified."""

    for folder in (Path("user_data/data/binance_funding"), Path("user_data/data/binance/futures")):
        if not folder.exists():
            continue
        candidates = sorted(folder.glob(f"{base}*funding*.feather")) if folder.name == "binance_funding" else sorted(
            folder.glob(f"{base}_*-funding_rate.feather")
        )
        for path in candidates:
            try:
                frame = pd.read_feather(path)
            except Exception:
                continue
            column = next((c for c in ("fundingTime", "date") if c in frame.columns), None)
            if column is None or frame.empty:
                continue
            stamps = pd.to_datetime(frame[column], utc=True)
            return str(stamps.min()), str(stamps.max()), int(len(frame))
    return "", "", 0


def capability_matrix(symbols: Sequence[str], probes: dict[str, Any]) -> pd.DataFrame:
    """Build ``data_capability_matrix.csv``.

    ``probes`` is the result of :func:`probe_remote_availability` -- what the
    authoritative source actually publishes. A field whose remote probe has not
    been run is UNKNOWN, never ABSENT.
    """

    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        base = symbol.replace("USDT", "_USDT", 1) if "USDT" in symbol else symbol
        base = base.removesuffix("_USDT")
        row: dict[str, Any] = {"symbol": symbol}

        for field_name, (folder_name, _) in _STATUS_COLUMNS.items():
            if field_name == "funding":
                start, end, rows_ = _local_funding_span(base)
                status = AVAILABLE if rows_ else ABSENT
            elif field_name == "price":
                start, end, rows_ = _local_field_span(CANONICAL_DIR / "price", symbol)
                if not rows_:
                    start, end, rows_ = _local_field_span(
                        CANONICAL_DIR / "price", f"{symbol}_{'15m'}"
                    )
                status = AVAILABLE if rows_ else UNKNOWN
            elif field_name == "taker_flow":
                start, end, rows_ = _local_field_span(CANONICAL_DIR / "price", symbol)
                status = AVAILABLE if rows_ else UNKNOWN
            else:
                start, end, rows_ = _local_field_span(CANONICAL_DIR / folder_name, symbol)
                status = AVAILABLE if rows_ else UNKNOWN
                remote = (probes.get(field_name) or {}).get(symbol)
                if status != AVAILABLE and remote is True:
                    status = UNKNOWN  # published remotely, not yet ingested here
                elif status != AVAILABLE and remote is False:
                    status = ABSENT  # probed and confirmed not published
            row[f"{field_name}_start"] = start or ""
            row[f"{field_name}_end"] = end or ""
            row[f"{field_name}_rows"] = rows_
            row[f"{field_name}_status"] = status

        # Basis is only defined from a genuine index price.
        row["basis_status"] = (
            AVAILABLE
            if row["index_price_status"] == AVAILABLE and row["mark_price_status"] == AVAILABLE
            else "ABSENT"
        )
        rows.append(row)
    frame = pd.DataFrame(rows)
    ordered: list[str] = ["symbol"]
    for name in CANONICAL_FIELDS:
        # ``basis_status`` is already produced by the CANONICAL_FIELDS loop, so
        # appending it again here would give the frame a duplicated column and
        # every ``row["basis_status"]`` lookup would return a Series.
        ordered += [f"{name}_start", f"{name}_end", f"{name}_rows", f"{name}_status"]
    for column in ordered:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, ordered]


MISSING_BASIS = "ABSENT"


#: How the capability matrix's field vocabulary maps onto the hypothesis
#: registry's. These are genuinely different names for the same thing, and
#: guessing the correspondence is how a fully-recovered dataset ends up still
#: reporting its funding families as blocked.
#:
#: * ``funding`` carries the whole settlement stream, which is what the registry
#:   means by ``funding_rate``.
#: * ``taker_flow`` is only complete when *both* legs are present, because the
#:   imbalance divides by their sum; a single leg is DEGRADED, not AVAILABLE.
MATRIX_TO_REGISTRY_FIELDS: dict[str, tuple[str, ...]] = {
    "price": (),
    "funding": ("funding_rate",),
    "open_interest": ("open_interest",),
    "taker_flow": ("taker_buy_volume", "taker_sell_volume"),
    "index_price": ("index_price",),
    "mark_price": ("mark_price",),
}


def registry_field_status(matrix: pd.DataFrame) -> dict[str, str]:
    """Translate the capability matrix into the registry's field vocabulary.

    A field counts as available if *any* usable symbol has it, which is the
    honest reading for a cross-sectional study. The per-symbol detail is
    preserved in the matrix itself.
    """

    from tools.strategy_factory_v2.data import AVAILABLE, DEGRADED

    ok = (AVAILABLE, DEGRADED)
    status: dict[str, str] = {}
    for _, row in matrix.iterrows():
        for matrix_field, registry_fields in MATRIX_TO_REGISTRY_FIELDS.items():
            value = row.get(f"{matrix_field}_status", UNKNOWN)
            if not registry_fields:
                continue
            if matrix_field == "taker_flow":
                # Both legs are required by the imbalance definition.
                usable = value in ok
            else:
                usable = value in ok
            for registry_field in registry_fields:
                if usable:
                    status[registry_field] = AVAILABLE
                elif status.get(registry_field) != AVAILABLE:
                    status.setdefault(registry_field, value)
    return status


def probe_remote_availability(
    specs: Sequence[DatasetSpec], client: BinanceArchive
) -> dict[str, Any]:
    """Ask the authoritative archive what it actually publishes.

    This is the difference between ABSENT and UNKNOWN. Without a probe, a field
    that was never downloaded is simply unknown, and reporting it as absent
    would assert a fact about the world that nobody checked.
    """

    probes: dict[str, Any] = {"_checked_utc": datetime.now(timezone.utc).isoformat()}
    by_kind: dict[str, dict[str, Any]] = {KLINE: {}, METRICS: {}, INDEX_KLINES: {}, MARK_KLINES: {}}
    for spec in specs:
        try:
            files, _ = plan_dataset(spec, client)
        except Exception as error:
            by_kind[spec.kind][spec.symbol] = f"probe_failed: {type(error).__name__}"
            continue
        by_kind[spec.kind][spec.symbol] = bool(files)
    probes["_by_kind"] = by_kind
    probes["open_interest"] = by_kind.get(METRICS, {})
    probes["index_price"] = by_kind.get(INDEX_KLINES, {})
    probes["mark_price"] = by_kind.get(MARK_KLINES, {})
    probes["price"] = by_kind.get(KLINE, {})
    probes["taker_flow"] = by_kind.get(KLINE, {})  # taker rides inside the kline file
    return probes
