"""Command-line entry point for the isolated strategy factory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.strategy_factory.data import load_pair_bundle
from tools.strategy_factory.preregistration import PAIRS, preregistration_manifest
from tools.strategy_factory.runner import run_factory


DEFAULT_DATA_DIR = Path("user_data/data/binance/futures")


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--pair",
        dest="pairs",
        action="append",
        choices=list(PAIRS),
        help="Repeat to audit/run a subset; defaults to BTC and ETH.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory",
        description="Run the pre-registered BTC/ETH OHLCV strategy-factory MVP.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit local data and print the frozen manifest.")
    _common(audit)

    run = subparsers.add_parser("run", help="Run the full pre-registered search.")
    _common(run)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--start", default=None, help="Half-open UTC start, e.g. 2022-01-01.")
    run.add_argument("--end", default=None, help="Half-open UTC end, e.g. 2025-01-01.")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--max-specs", type=int, default=None)
    run.add_argument("--draws", type=int, default=None)

    smoke = subparsers.add_parser(
        "smoke", help="Run a deliberately truncated diagnostic profile; never call it a result."
    )
    _common(smoke)
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--start", default=None)
    smoke.add_argument("--end", default=None)
    smoke.add_argument("--overwrite", action="store_true")
    smoke.add_argument("--max-specs", type=int, default=8)
    smoke.add_argument("--draws", type=int, default=50)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pairs = tuple(args.pairs or PAIRS)
    if args.command == "audit":
        audits = [load_pair_bundle(args.data_dir, pair).audit for pair in pairs]
        print(
            json.dumps(
                {"preregistration": preregistration_manifest(), "data_audits": audits},
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    result = run_factory(
        data_dir=args.data_dir,
        output_dir=args.output,
        pairs=pairs,
        start=args.start,
        end=args.end,
        max_specs=args.max_specs,
        monte_carlo_draws=args.draws,
        overwrite=args.overwrite,
        quick=args.command == "smoke",
    )
    print(f"Run directory: {result.output_dir}")
    print(f"Trials: {result.manifest['executed_trial_count']} / {result.manifest['full_trial_count']}")
    print(f"Survivors: {len(result.survivors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
