"""Run the A2.5.1 provenance pass over the whole recovered archive.

    python -m tools.strategy_factory_v2.verify_provenance [--no-check]

Verifying every file means fetching every ``.CHECKSUM`` sidecar. That is
thousands of small requests and takes a while, which is the point: a provenance
claim that was not checked must be reported as NOT_CHECKED, and the only way to
earn CHECKSUM_VERIFIED is to actually compare.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Sequence

from tools.strategy_factory_v2.provenance import (
    PROVENANCE_PATH,
    summarise,
    verify_archive,
    write_provenance,
)
from tools.strategy_factory_v2.recovery import BinanceArchive


def _load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {entry["path"]: entry for entry in payload.get("files", [])}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.strategy_factory_v2.verify_provenance"
    )
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Classify from disk only. Files become NOT_CHECKED; nothing is called verified.",
    )
    parser.add_argument("--out", type=Path, default=PROVENANCE_PATH)
    parser.add_argument("--shard", type=int, default=0, help="Verify only this 0-based shard.")
    parser.add_argument("--shards", type=int, default=1)
    args = parser.parse_args(list(argv) if argv is not None else None)

    client = BinanceArchive(retries=2, backoff=1.6)
    started = time.time()

    from tools.strategy_factory_v2.provenance import (
        FileProvenance,
        scan_archive,
        write_provenance,
    )

    everything = scan_archive()
    if args.shards > 1:
        everything = [
            item for index, item in enumerate(everything) if index % args.shards == args.shard
        ]
    print(f"verifying {len(everything)} files (shard {args.shard + 1}/{args.shards})", flush=True)

    records = verify_archive(
        client=client,
        workers=args.workers,
        check=not args.no_check,
        files=everything,
        progress=lambda message: print(message, flush=True),
    )

    # Merge with any previous shard so a chunked run accumulates rather than
    # overwrites. A partial pass that silently replaced the whole would be
    # worse than no pass at all.
    merged = _load_existing(args.out)
    for record in records:
        merged[record.path] = record.as_dict()
    combined = [FileProvenance(**entry) for entry in merged.values()]

    summary = summarise(combined)
    summary["elapsed_seconds"] = round(time.time() - started, 1)
    write_provenance(combined, args.out)
    print(json.dumps(summary, indent=2, default=str))
    print(f"-> {args.out}")
    return 0 if summary["unclassified"] == 0 and summary["by_state"].get("FAILED", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
