"""Phase A2 driver: recover the missing datasets from the Binance archive.

Run as a module. It is deliberately separate from the V2 CLI's research
commands, because a download that decides a research boundary must be an
obvious, isolated act rather than a side effect of an audit.

    python -m tools.strategy_factory_v2.recover \
        --symbols BTCUSDT ETHUSDT XRPUSDT SOLUSDT BNBUSDT \
        --start 2020-01-01 \
        --out user_data/strategy_factory_runs/v2/<run>

The run is resumable: the ledger under ``user_data/data/binance_v2`` records
every verified file, and re-running skips what is already on disk.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from tools.strategy_factory_v2.ingest import (
    LEDGER_PATH,
    capability_matrix,
    load_ledger,
    probe_remote_availability,
    recover_dataset,
)
from tools.strategy_factory_v2.recovery import (
    INDEX_KLINES,
    KLINE,
    MARK_KLINES,
    METRICS,
    BinanceArchive,
    DatasetSpec,
    default_specs,
)

DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory_v2.recover",
        description="Recover open interest, taker flow, index and mark from the Binance archive.",
    )
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-12-31")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int, default=None, help="Max archive files per dataset (smoke).")
    parser.add_argument("--kinds", nargs="+", default=["klines", "metrics", "indexPriceKlines", "markPriceKlines"])
    parser.add_argument("--intervals", nargs="+", default=["15m", "1h"])
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already verified.")
    parser.add_argument("--probe-only", action="store_true", help="Only probe the archive; fetch nothing.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    client = BinanceArchive(pause=0.02)
    specs = [s for s in default_specs(args.symbols, args.start, args.end) if s.kind in args.kinds]
    specs = [s for s in specs if s.kind == METRICS or s.interval in args.intervals]

    print(f"recovery plan: {len(specs)} datasets, {len(args.symbols)} symbols", flush=True)
    probes = probe_remote_availability(specs, client)
    print(f"remote probe complete at {probes['_checked_utc']}", flush=True)

    if args.probe_only:
        print(json.dumps(probes, indent=2, default=str))
        return 0

    started = time.time()
    results: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        label = f"{spec.kind}/{spec.symbol}/{spec.interval}"
        print(f"[{index}/{len(specs)}] {label}", flush=True)
        record = recover_dataset(
            spec, client, limit=args.limit, workers=args.workers, force=args.force
        )
        payload = record.as_dict()
        payload["errors_count"] = len(record.errors)
        results.append(payload)
        status = "ok " if not record.errors else f"ERR({len(record.errors)})"
        print(
            f"    {status} rows={record.rows:,} {record.start[:19]} -> {record.end[:19]} "
            f"files={record.files} verified={record.files_verified} "
            f"unverified={record.files_checksum_unavailable} "
            f"bytes={record.bytes_downloaded/1e6:.1f}MB",
            flush=True,
        )
        for error in record.errors[:3]:
            print(f"      ! {error}", flush=True)

    matrix = capability_matrix(args.symbols, probes)
    ledger = load_ledger()
    elapsed = time.time() - started
    summary = {
        "recovered_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "symbols": list(args.symbols),
        "start": args.start,
        "end": args.end,
        "datasets": results,
        "capability_matrix": matrix.to_dict("records"),
        "remote_probe": probes,
        "ledger_path": str(LEDGER_PATH),
    }
    print(json.dumps({"elapsed_seconds": round(elapsed, 1),
                      "datasets_ok": sum(1 for r in results if not r["errors"]),
                      "datasets_with_errors": sum(1 for r in results if r["errors"])},
                     indent=2))
    Path("user_data/data/binance_v2/recovery_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print(f"summary -> user_data/data/binance_v2/recovery_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
