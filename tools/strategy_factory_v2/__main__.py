"""Command-line entry point for Strategy Factory V2.

The V1 MVP CLI (``python -m tools.strategy_factory``) is untouched. V2 lives
behind its own ``-v2`` subcommands so that a V1 script cannot accidentally
invoke a V2 code path, and so a V2 run cannot be mistaken for a V1 run.

    python -m tools.strategy_factory_v2 audit-v2
    python -m tools.strategy_factory_v2 discover-v2
    python -m tools.strategy_factory_v2 report-v2 --run <dir>
    python -m tools.strategy_factory_v2 test-v2
    python -m tools.strategy_factory_v2 selftest-v2

``discover-v2`` and ``report-v2`` perform the Phase A/B audit and write the data
reality report. ``paper-v2`` is registered but refuses to run until Phase C/D
have produced survivors, because a paper trader with nothing to trade is just
a way to generate the appearance of progress.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from tools.strategy_factory_v2.data import data_fingerprint, run_audit
from tools.strategy_factory_v2.hypotheses import registry_manifest
from tools.strategy_factory_v2.reports import (
    write_data_audit_json,
    write_data_reality_report,
    write_html_report,
    write_run_report,
)
from tools.strategy_factory_v2.spec import (
    DISCOVERY_TIMEFRAMES,
    PRIMARY_TIMEFRAMES,
    SPEC_VERSION,
    V2_RUN_ROOT,
    spec_manifest,
)

DEFAULT_DATA_DIR = Path("user_data/data/binance/futures")


def _price_symbols(manifest: dict[str, Any]) -> list[str]:
    """Symbols that actually have usable price data.

    A funding-only symbol cannot be researched: there are no returns to
    condition on, so it is excluded from the cross-asset symbol pool.
    """

    return [
        symbol
        for symbol, audit in sorted(manifest["symbol_audits"].items())
        if audit.get("timeframes")
    ]


def _capabilities(manifest: dict[str, Any]) -> tuple[dict[str, str], list[str], bool]:
    """Merge per-symbol field status into a single V2 capability verdict.

    A field counts as available if *any* usable symbol has it. That is the
    honest reading for a cross-sectional study, and the per-symbol table in the
    report preserves which symbols actually carry it.
    """

    merged: dict[str, str] = {}
    price_available = False
    for audit in manifest["symbol_audits"].values():
        if audit.get("timeframes"):
            price_available = True
        for name, status in (audit.get("field_status") or {}).items():
            if merged.get(name) == "AVAILABLE":
                continue
            merged[name] = status if status == "AVAILABLE" else merged.get(name, status)
    return merged, _price_symbols(manifest), price_available


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory_v2",
        description="Strategy Factory V2: regime + derivatives research system.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
        sub.add_argument("--extra-dir", type=Path, action="append", default=[])

    audit = subparsers.add_parser(
        "audit-v2", help="Audit local data and print the frozen V2 manifest as JSON."
    )
    common(audit)

    discover = subparsers.add_parser(
        "discover-v2",
        help="Run the Phase A/B audit and write the data reality report.",
    )
    common(discover)
    discover.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output directory; defaults to {V2_RUN_ROOT}/<utc-timestamp>",
    )
    discover.add_argument(
        "--timeframe",
        action="append",
        default=None,
        help="Timeframe to run causality probes on; repeatable. Defaults to the "
        "discovery timeframes that the data actually supports.",
    )
    discover.add_argument(
        "--max-rows",
        type=int,
        default=20000,
        help="Cap bars per symbol during causality probes to keep the audit quick. "
        "0 disables the cap.",
    )
    discover.add_argument(
        "--skip-probes",
        action="store_true",
        help="Skip the causality probes. The report then states that they did not run.",
    )
    discover.add_argument("--overwrite", action="store_true")

    report = subparsers.add_parser("report-v2", help="Re-render reports from a run directory.")
    report.add_argument("--run", type=Path, required=True)
    report.add_argument("--overwrite", action="store_true")

    tests = subparsers.add_parser(
        "test-v2", help="Run the V2 test suite with the built-in zero-dependency runner."
    )
    tests.add_argument("--pattern", default=None)
    tests.add_argument("--quiet", action="store_true")

    subparsers.add_parser(
        "selftest-v2",
        help="Run the causality probes on real data and report pass/fail.",
    ).add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)

    paper = subparsers.add_parser(
        "paper-v2", help="Reserved for Phase E. Refuses to run before survivors exist."
    )
    paper.add_argument("--run", type=Path, required=True)

    return parser


def _resolve_output(args: argparse.Namespace) -> Path:
    if getattr(args, "output", None):
        return args.output
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(V2_RUN_ROOT) / stamp


def _best_reference(
    inventory: dict[str, Any],
    symbol_key: str,
    timeframe: str,
    price: pd.DataFrame,
    max_rows: int,
) -> tuple[pd.DataFrame | None, str | None, float]:
    """Pick the reference asset whose bars actually cover the subject's span.

    This matters more than it looks. A cross-asset causality probe only means
    something when both assets share a time span: if the reference has a much
    longer history, "destroy its future" destroys the entire overlapping
    window, and every historical reference value changes. The probe would then
    report a leak that is really a mismatched-harness artifact.

    Rather than silently skipping the check, an asset that cannot be matched is
    reported as such -- an unrunnable check must never read as a passed one.
    """

    from tools.strategy_factory_v2.data import load_ohlcv

    start, end = price["decision_time"].iloc[0], price["decision_time"].iloc[-1]
    best: tuple[pd.DataFrame | None, str | None, float] = (None, None, 0.0)
    for other_key, item in sorted(inventory.items()):
        if other_key == symbol_key or timeframe not in item.price:
            continue
        try:
            frame = load_ohlcv(item.price[timeframe].path, timeframe)
        except Exception:  # pragma: no cover - defensive
            continue
        window = frame[
            (frame["decision_time"] >= start) & (frame["decision_time"] <= end)
        ].reset_index(drop=True)
        overlap = len(window) / max(len(price), 1)
        if overlap > best[2]:
            best = (window, item.symbol, overlap)
    if best[2] < 0.9:
        return None, best[1], best[2]
    return best[0], best[1], best[2]


def _probes(
    manifest: dict[str, Any],
    data_dir: Path,
    extra_dirs: Sequence[Path],
    timeframes: Sequence[str] | None,
    max_rows: int,
) -> dict[str, Any] | None:
    """Run the causality probes on the real discovered data."""

    from tools.strategy_factory_v2.causality import run_all_probes
    from tools.strategy_factory_v2.data import discover, load_funding_events, load_ohlcv

    inventory = discover(data_dir, extra_dirs)
    price_symbols = [key for key, item in sorted(inventory.items()) if item.price]
    if not price_symbols:
        return {
            "passed": False,
            "checks_run": [],
            "rows_compared": 0,
            "findings": [
                {
                    "check": "setup",
                    "column": "<none>",
                    "cut_index": 0,
                    "detail": "no symbol with price data was discovered",
                }
            ],
        }

    def _load_events(item: Any) -> tuple[pd.DataFrame | None, float | None]:
        if not item.funding:
            return None, None
        try:
            events = load_funding_events(item.funding[0].path)
        except Exception:  # pragma: no cover - defensive
            return None, None
        if not len(events):
            return None, None
        spacing = events["settlement_time"].diff().dt.total_seconds().median()
        try:
            interval = float(spacing) / 3600.0
        except (TypeError, ValueError):
            interval = None
        return events, interval

    requested = list(timeframes) if timeframes else list(DISCOVERY_TIMEFRAMES)
    attempts: list[str] = []
    for timeframe in requested:
        symbol_key = next(
            (
                key
                for key in price_symbols
                if timeframe in inventory[key].price
            ),
            None,
        )
        if symbol_key is None:
            attempts.append(f"{timeframe}: no symbol has stored {timeframe} data")
            continue
        item = inventory[symbol_key]
        price = load_ohlcv(item.price[timeframe].path, timeframe)
        if max_rows and len(price) > max_rows:
            price = price.iloc[-max_rows:].reset_index(drop=True)
        funding, interval = _load_events(item)
        reference, reference_symbol, overlap = _best_reference(
            inventory, symbol_key, timeframe, price, max_rows
        )

        report = run_all_probes(
            price,
            timeframe,
            horizons=(6, 12, 24, 48),
            reference_price=reference,
            symbol=item.symbol,
            funding_events=funding,
            funding_interval_hours=interval,
        )
        payload = report.as_dict()
        payload["timeframe"] = timeframe
        payload["symbol"] = item.symbol
        payload["reference_symbol"] = reference_symbol
        payload["reference_overlap"] = round(overlap, 4)
        payload["rows_in_scope"] = int(len(price))
        if reference is None:
            payload.setdefault("notes", []).append(
                "cross-asset checks were not runnable: no other symbol covers this "
                f"timeframe's span (best overlap {overlap:.1%}). An unrunnable check "
                "is reported as such rather than counted as a pass."
            )
        return payload
    return {
        "passed": False,
        "checks_run": [],
        "rows_compared": 0,
        "findings": [
            {
                "check": "setup",
                "column": "<none>",
                "cut_index": 0,
                "detail": "; ".join(attempts) or f"no usable timeframe in {requested}",
            }
        ],
    }


def _selftest(data_dir: Path, extra_dirs: Sequence[Path] = ()) -> int:
    manifest = run_audit(data_dir, extra_dirs, with_hash=False)
    merged, symbols, price_available = _capabilities(manifest)
    registry = registry_manifest(merged, symbols, price_available)
    result = _probes(manifest, data_dir, extra_dirs, None, 20000)
    print(json.dumps({"registry": {
        "total": registry["hypothesis_count"],
        "testable": registry["testable_hypotheses"],
        "blocked": registry["blocked_hypotheses"],
    }, "causality": result}, indent=2, default=str))
    return 0 if result and result.get("passed") else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "audit-v2":
        manifest = run_audit(args.data_dir, args.extra_dir, with_hash=True)
        merged, symbols, price_available = _capabilities(manifest)
        print(
            json.dumps(
                {
                    "spec_version": SPEC_VERSION,
                    "preregistration": spec_manifest(),
                    "data_fingerprint": data_fingerprint(manifest),
                    "capabilities": {
                        "fields": merged,
                        "price_symbols": symbols,
                        "price_available": price_available,
                    },
                    "hypothesis_registry": registry_manifest(merged, symbols, price_available),
                    "data_audits": manifest,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0

    if args.command == "selftest-v2":
        return _selftest(args.data_dir)

    if args.command == "test-v2":
        from tools.strategy_factory_v2._testrunner import main as runner_main

        forwarded: list[str] = []
        if args.pattern:
            forwarded += ["--pattern", args.pattern]
        if args.quiet:
            forwarded += ["--quiet"]
        return runner_main(forwarded)

    if args.command == "paper-v2":
        print(
            "paper-v2 is not available. Phase A/B has not produced survivors, and a "
            "paper trader with nothing to trade would only simulate the appearance "
            "of progress. See the data reality report for what must be acquired first.",
            file=sys.stderr,
        )
        return 2

    if args.command == "report-v2":
        audit_path = args.run / "data_audit.json"
        if not audit_path.exists():
            print(f"No data_audit.json in {args.run}", file=sys.stderr)
            return 2
        manifest = json.loads(audit_path.read_text(encoding="utf-8"))
        registry_path = args.run / "hypothesis_registry.json"
        registry = (
            json.loads(registry_path.read_text(encoding="utf-8"))
            if registry_path.exists()
            else registry_manifest()
        )
        causality_path = args.run / "causality.json"
        causality = (
            json.loads(causality_path.read_text(encoding="utf-8"))
            if causality_path.exists()
            else None
        )
        write_data_reality_report(manifest, registry, causality, args.run)
        write_html_report(manifest, registry, causality, args.run)
        print(f"Reports written to {args.run}")
        return 0

    # discover-v2
    output = _resolve_output(args)
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        print(
            f"Output directory is not empty: {output}. Use a new path or --overwrite.",
            file=sys.stderr,
        )
        return 2
    output.mkdir(parents=True, exist_ok=True)

    manifest = run_audit(args.data_dir, args.extra_dir, with_hash=True)
    merged, symbols, price_available = _capabilities(manifest)
    registry = registry_manifest(merged, symbols, price_available)
    causality = (
        None
        if args.skip_probes
        else _probes(manifest, args.data_dir, args.extra_dir, args.timeframe, args.max_rows)
    )

    write_data_audit_json(manifest, output)
    (output / "hypothesis_registry.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    if causality is not None:
        (output / "causality.json").write_text(
            json.dumps(causality, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
    write_data_reality_report(manifest, registry, causality, output)
    write_html_report(manifest, registry, causality, output)

    run_manifest = {
        "run_id": output.name,
        "spec_version": SPEC_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "A+B (canonical data, features, regime, causality)",
        "hypothesis_experiment_run": False,
        "note": (
            "No hypothesis has been evaluated. This run only establishes what the "
            "data can support and proves the features are causal."
        ),
        "data_dir": str(args.data_dir),
        "extra_dirs": [str(p) for p in args.extra_dir],
        "data_fingerprint": data_fingerprint(manifest),
        "preregistration": spec_manifest(),
        "capabilities": {
            "fields": merged,
            "price_symbols": symbols,
            "price_available": price_available,
        },
        "hypothesis_registry": registry,
        "causality": causality,
        "data_audits": manifest,
    }
    write_run_report(run_manifest, output)

    print(f"Run directory: {output}")
    print(f"Symbols discovered: {manifest['symbols_discovered']}")
    print(
        f"Primary timeframes ready: {', '.join(manifest['primary_timeframes_ready']) or 'none'}"
    )
    print(
        f"Hypotheses: {registry['hypothesis_count']} preregistered, "
        f"{registry['testable_hypotheses']} testable, "
        f"{registry['blocked_hypotheses']} BLOCKED"
    )
    if causality is None:
        print("Causality probes: SKIPPED (--skip-probes)")
    else:
        print(
            f"Causality probes: {'PASSED' if causality.get('passed') else 'FAILED'} "
            f"({causality.get('rows_compared', 0):,} values compared)"
        )
    print(f"Reports: DATA_REALITY.md, report.html, data_audit.json, manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
