"""Phase A2.5 -- provenance accounting for every ingested archive file.

The A2 report claimed "79 files, 0 verified, 0 unverified". All three numbers
cannot be true, and the cause was a ledger that accumulated per-file records in
memory and then wrote the dataset summary without them. A file that appears in
no accounting bucket has not been accounted for, and an audit that cannot say
where a number came from is not an audit.

This module rebuilds the accounting from the filesystem rather than trusting
the ledger, because the filesystem is the only source that cannot drift. Every
archive file on disk is walked, given exactly one provenance state, and
described completely.

The four states are exhaustive and mutually exclusive:

``CHECKSUM_VERIFIED``
    The file's SHA-256 matches the value in its published ``.CHECKSUM`` sidecar.
``NO_CHECKSUM_AVAILABLE``
    The archive publishes no sidecar for this file. The bytes are recorded and
    their own digest is stored, but it is *not* called verified -- a self
    digest proves the file is internally consistent, not that it is the file
    Binance published.
``NOT_CHECKED``
    No sidecar was fetched, most often because the file was already on disk
    from an earlier run. Its digest is still recorded so the state is
    reproducible, and it is never silently promoted to verified.
``FAILED``
    A sidecar exists and the digest does not match, or the file is unreadable.
    The file is not ingested.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

CHECKSUM_VERIFIED = "CHECKSUM_VERIFIED"
NO_CHECKSUM_AVAILABLE = "NO_CHECKSUM_AVAILABLE"
NOT_CHECKED = "NOT_CHECKED"
FAILED = "FAILED"

PROVENANCE_STATES = (CHECKSUM_VERIFIED, NO_CHECKSUM_AVAILABLE, NOT_CHECKED, FAILED)

ARCHIVE_ROOT = Path("user_data/data/binance_v2/archive")
PROVENANCE_PATH = Path("user_data/data/binance_v2/provenance.json")

KIND_LABELS = {
    "klines": "binance_public_data/futures/um/{cadence}/klines",
    "metrics": "binance_public_data/futures/um/daily/metrics",
    "indexPriceKlines": "binance_public_data/futures/um/monthly/indexPriceKlines",
    "markPriceKlines": "binance_public_data/futures/um/monthly/markPriceKlines",
}


@dataclass
class FileProvenance:
    """The complete account of one archive file."""

    path: str
    source: str
    source_type: str
    checksum_status: str
    checksum_algorithm: str
    checksum_expected: str
    checksum_actual: str
    file_size: int
    first_seen: str
    ingested_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dataset_of(path: Path, root: Path) -> tuple[str, str, str]:
    """Recover (kind, symbol, interval) from an archive path."""

    parts = path.relative_to(root).parts
    if len(parts) < 3:
        return ("unknown", "unknown", "unknown")
    kind, symbol = parts[0], parts[1]
    interval = parts[2] if len(parts) > 3 else ""
    return (kind, symbol, interval)


def scan_archive(root: Path = ARCHIVE_ROOT) -> list[tuple[Path, tuple[str, str, str]]]:
    if not root.exists():
        return []
    found: list[tuple[Path, tuple[str, str, str]]] = []
    for path in sorted(root.rglob("*.zip")):
        found.append((path, _dataset_of(path, root)))
    return found


def verify_one(
    path: Path,
    dataset: tuple[str, str, str],
    client,
    ledger: dict[str, Any],
    check: bool = True,
) -> FileProvenance:
    """Classify one file into exactly one provenance state."""

    kind, symbol, interval = dataset
    blob = path.read_bytes()
    actual = sha256(blob).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    key = f"{kind}/{symbol}/{interval}/{path.name}"
    prior = ledger.get("files", {}).get(key, {})

    record = FileProvenance(
        path=str(path),
        source=f"{KIND_LABELS.get(kind, 'binance_public_data')}/{symbol}/{interval}/{path.name}",
        source_type="binance_public_archive",
        checksum_status=NOT_CHECKED,
        checksum_algorithm="sha256",
        checksum_expected="",
        checksum_actual=actual,
        file_size=len(blob),
        first_seen=prior.get("retrieved_utc", now),
        ingested_at=prior.get("ingested_utc", now),
    )

    if not check:
        return record

    remote_key = (
        f"data/futures/um/daily/metrics/{symbol}/{path.name}"
        if kind == "metrics"
        else f"data/futures/um/monthly/{kind}/{symbol}/{interval}/{path.name}"
    )
    try:
        sidecar = client._get(f"{client.endpoint}/{remote_key}.CHECKSUM").decode().split()[0].strip()
    except Exception:
        # No sidecar published. The digest above still pins the bytes, but it
        # is a self-digest and must not be reported as verification.
        record.checksum_status = NO_CHECKSUM_AVAILABLE
        return record
    record.checksum_expected = sidecar
    if sidecar == actual:
        record.checksum_status = CHECKSUM_VERIFIED
    else:
        record.checksum_status = FAILED
    return record


def verify_archive(
    root: Path = ARCHIVE_ROOT,
    client=None,
    ledger: dict[str, Any] | None = None,
    workers: int = 16,
    check: bool = True,
    progress: Callable[[str], None] | None = None,
    files: Sequence[tuple[Path, tuple[str, str, str]]] | None = None,
) -> list[FileProvenance]:
    """Walk the archive and classify every file into exactly one state."""

    if client is None:
        from tools.strategy_factory_v2.recovery import BinanceArchive

        client = BinanceArchive(retries=2, backoff=1.6)
    ledger = ledger or {}
    items = list(files) if files is not None else scan_archive(root)
    results: list[FileProvenance] = []

    def task(item):
        path, dataset = item
        return verify_one(path, dataset, client, ledger, check=check)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(task, item) for item in items]
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                results.append(future.result())
            except Exception:
                # An unreadable file is FAILED, not missing.
                results.append(
                    FileProvenance(
                        path="<unreadable>",
                        source="<unreadable>",
                        source_type="binance_public_archive",
                        checksum_status=FAILED,
                        checksum_algorithm="sha256",
                        checksum_expected="",
                        checksum_actual="",
                        file_size=0,
                        first_seen=datetime.now(timezone.utc).isoformat(),
                        ingested_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            if progress and index % 500 == 0:
                progress(f"    verified {index}/{len(items)}")
    return sorted(results, key=lambda r: r.path)


def summarise(records: Sequence[FileProvenance]) -> dict[str, Any]:
    counts = {state: 0 for state in PROVENANCE_STATES}
    for record in records:
        counts[record.checksum_status] = counts.get(record.checksum_status, 0) + 1
    unclassified = [r.path for r in records if r.checksum_status not in PROVENANCE_STATES]
    return {
        "total_files": len(records),
        "by_state": counts,
        "unclassified": len(unclassified),
        "unclassified_paths": unclassified[:20],
        "total_bytes": sum(r.file_size for r in records),
        "distinct_sources": len({r.source for r in records}),
    }


def write_provenance(records: Sequence[FileProvenance], path: Path = PROVENANCE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summarise(records),
        "files": [record.as_dict() for record in records],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def load_provenance(path: Path = PROVENANCE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"summary": {"total_files": 0, "by_state": {}}, "files": []}
    return json.loads(path.read_text(encoding="utf-8"))
