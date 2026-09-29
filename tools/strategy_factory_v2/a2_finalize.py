"""Phase A2 finalization: partition, capability matrix, and the four artifacts.

Run after :mod:`tools.strategy_factory_v2.recover`. It performs no network
access and evaluates no hypothesis; it only describes the dataset and declares
the research boundary.

    python -m tools.strategy_factory_v2.a2_finalize \
        --out user_data/strategy_factory_runs/v2/<run>
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from tools.strategy_factory_v2.coverage_report import (
    write_audit_v2,
    write_capability_matrix_csv,
    write_data_coverage_report,
    write_manifest,
)
from tools.strategy_factory_v2.data import run_audit
from tools.strategy_factory_v2.holdout import (
    DataPartition,
    declare_partition,
    latest_complete_day,
    write_lock,
)
from tools.strategy_factory_v2.ingest import (
    AVAILABLE,
    CANONICAL_DIR,
    capability_matrix,
    load_ledger,
    registry_field_status,
)
from tools.strategy_factory_v2.hypotheses import registry_manifest
from tools.strategy_factory_v2.spec import SPEC_VERSION

#: The pre-existing local price end. Everything after it is holdout, because
#: nothing before this phase ever looked past it.
LOCAL_PRICE_END = pd.Timestamp("2025-11-18 22:12:00+00:00")

SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")


def _load_canonical(symbol: str, folder: str, interval: str = "1h") -> pd.DataFrame | None:
    path = CANONICAL_DIR / folder / f"{symbol}_{interval}.feather"
    if not path.exists():
        return None
    try:
        return pd.read_feather(path)
    except Exception:
        return None


def build_matrix(probes: dict[str, Any] | None = None) -> pd.DataFrame:
    return capability_matrix(SYMBOLS, probes or {})


def compute_partition(matrix: pd.DataFrame) -> tuple[DataPartition | None, dict[str, Any]]:
    """Derive the development / holdout split from the recovered data.

    The split is placed at the boundary that already exists: the end of the
    pre-existing local price data. Nothing after that point has ever been
    loaded, inspected or used, so everything after it is genuinely untouched.
    Choosing the split by reference to what has already been seen is the only
    way to guarantee the holdout has no history of being peeked at.
    """

    detail: dict[str, Any] = {"per_symbol": {}}
    development_frames: list[pd.DataFrame] = []
    holdout_frames: list[pd.DataFrame] = []

    for symbol in SYMBOLS:
        frame = _load_canonical(symbol, "price", "1h")
        if frame is None or frame.empty:
            detail["per_symbol"][symbol] = "no recovered 1h price"
            continue
        stamps = pd.to_datetime(frame["date"], utc=True)
        development = frame[stamps <= LOCAL_PRICE_END]
        holdout = frame[stamps > LOCAL_PRICE_END]
        detail["per_symbol"][symbol] = {
            "total_rows": int(len(frame)),
            "start": str(stamps.min()),
            "end": str(stamps.max()),
            "development_rows": int(len(development)),
            "holdout_rows": int(len(holdout)),
            "holdout_start": str(stamps[stamps > LOCAL_PRICE_END].min())
            if len(holdout)
            else None,
        }
        if len(development) and len(holdout):
            development_frames.append(development)
            holdout_frames.append(holdout)

    if not development_frames or not holdout_frames:
        detail["error"] = (
            "no symbol has both a development region and a post-2025-11-18 holdout region"
        )
        return None, detail

    # Use the longest common development span and the union of holdout coverage.
    development_start = min(
        pd.to_datetime(f["date"], utc=True).min() for f in development_frames
    )
    holdout_end = max(pd.to_datetime(f["date"], utc=True).max() for f in holdout_frames)
    holdout_start = max(
        pd.to_datetime(f["date"], utc=True).min() for f in holdout_frames
    )
    validation_end = LOCAL_PRICE_END
    validation_start = max(development_start, validation_end - pd.Timedelta(days=165))

    partition = DataPartition(
        development_start=str(development_start),
        development_end=str(validation_start),
        validation_start=str(validation_start),
        validation_end=str(validation_end),
        holdout_start=str(holdout_start),
        holdout_end=str(holdout_end),
        latest_complete_day=latest_complete_day(
            pd.DataFrame({"date": [holdout_start, holdout_end]})
        ),
        boundary_source=(
            "end of the pre-existing local price data (2025-11-18); nothing after "
            "this point had ever been loaded before Phase A2"
        ),
    )
    return partition, detail


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory_v2.a2_finalize",
        description="Produce the Phase A2 capability matrix, coverage report and manifest.",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("user_data/data/binance/futures"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    output = args.out
    output.mkdir(parents=True, exist_ok=True)

    print("auditing pre-existing local data...", flush=True)
    local_audit = run_audit(args.data_dir, with_hash=False)

    print("building capability matrix...", flush=True)
    ledger = load_ledger()
    summary_path = Path("user_data/data/binance_v2/recovery_summary.json")
    probes = {}
    if summary_path.exists():
        probes = json.loads(summary_path.read_text(encoding="utf-8")).get("remote_probe", {})
    matrix = build_matrix(probes)

    # The registry is consulted with the *recovered* capability, not the old
    # one. The hypothesis list itself is untouched: recovering data unlocks
    # preregistered families, it does not license new ones. The two modules use
    # different names for the same fields, so the translation is explicit.
    merged_fields = registry_field_status(matrix)
    price_symbols = list(matrix[matrix["price_status"] == AVAILABLE]["symbol"])
    registry = registry_manifest(merged_fields, price_symbols, price_available=bool(price_symbols))

    print("declaring the research partition...", flush=True)
    partition, detail = compute_partition(matrix)
    if partition is not None:
        write_lock(partition)
        print(f"  development : {partition.development_start} -> {partition.development_end}")
        print(f"  validation  : {partition.validation_start} -> {partition.validation_end}")
        print(f"  HOLDOUT     : {partition.holdout_start} -> {partition.holdout_end}")
        print(f"  latest complete day: {partition.latest_complete_day}")

    write_capability_matrix_csv(matrix, output)
    write_data_coverage_report(matrix, local_audit, partition, ledger, registry, output)
    write_audit_v2(local_audit, matrix, ledger, partition, registry, output)
    write_manifest(local_audit, matrix, ledger, partition, registry, output, output.name)
    (output / "partition_detail.json").write_text(
        json.dumps(detail, indent=2, default=str), encoding="utf-8"
    )

    print(f"\nartifacts -> {output}")
    for name in (
        "data_capability_matrix.csv",
        "data_coverage_report.md",
        "data_audit_v2.json",
        "manifest.json",
    ):
        print(f"  {name}")
    print(
        f"\nhypotheses: {registry['hypothesis_count']} preregistered, "
        f"{registry['testable_hypotheses']} testable, "
        f"{registry['blocked_hypotheses']} BLOCKED"
    )
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
