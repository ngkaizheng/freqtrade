"""Bulk data download entry point.

    python -m shark_hunter.download klines
    python -m shark_hunter.download metrics
    python -m shark_hunter.download funding
    python -m shark_hunter.download all

Everything lands in ``shark_data/`` as gzipped CSV and is reused on re-run.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config as C
from .data import loader
from .data.sources import FundingSource, KlineSource, MetricsSource


def _one_kline(args) -> tuple[str, int, int]:
    symbol, tf = args
    t0 = time.time()
    df = loader.load_klines(symbol, tf)
    return f"{symbol} {tf}", len(df), time.time() - t0


def _one_metrics(symbol: str) -> tuple[str, int, int]:
    t0 = time.time()
    df = loader.load_metrics(symbol)
    return f"{symbol} oi", len(df), time.time() - t0


def _one_funding(symbol: str) -> tuple[str, int, int]:
    t0 = time.time()
    df = loader.load_funding(symbol)
    return f"{symbol} funding", len(df), time.time() - t0


def _run(label: str, jobs: list, fn, workers: int) -> None:
    print(f"=== {label}: {len(jobs)} jobs, {workers} workers ===", flush=True)
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, j): j for j in jobs}
        for fut in as_completed(futures):
            name, rows, secs = fut.result()
            done += 1
            print(f"[{done}/{len(jobs)}] {name:>18}  rows={rows:>8}  {secs:6.1f}s", flush=True)
    print(f"=== {label} complete in {time.time() - t0:.1f}s ===", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Shark Hunter data download")
    ap.add_argument("what", choices=["klines", "metrics", "funding", "all", "liquidation"])
    ap.add_argument("--timeframes", nargs="*", default=["5m"])
    ap.add_argument("--symbols", nargs="*", default=list(C.UNIVERSE))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--inner", type=int, default=0,
                    help="override the per-source request fan-out (default "
                         f"{C.DOWNLOAD_WORKERS}; metrics uses outer*inner concurrent requests)")
    args = ap.parse_args(argv)

    if args.inner:
        C.DOWNLOAD_WORKERS = args.inner

    if args.what in ("klines", "all"):
        jobs = [(s, tf) for s in args.symbols for tf in args.timeframes]
        _run("klines", jobs, _one_kline, args.workers)

    if args.what in ("metrics", "all"):
        # metrics is one small file per symbol per day; heavier fan-out helps.
        _run("metrics", list(args.symbols), _one_metrics, 9)

    if args.what in ("funding", "all"):
        _run("funding", list(args.symbols), _one_funding, 9)

    if args.what == "liquidation":
        src = __import__("shark_hunter.data.sources", fromlist=["LiquidationSource"])
        print("LIQUIDATION DATA UNAVAILABLE (no free public historical source).")
        print(src.LIQUIDATION_COVERAGE["reason"])
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
