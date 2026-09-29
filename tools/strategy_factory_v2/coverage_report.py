"""Phase A2 reporting: the capability matrix, coverage report and manifest.

The four artifacts this module produces exist to answer one question without
ambiguity: *what can this project actually measure, and what has it merely
assumed?*

The distinction that matters throughout is three-valued. ``AVAILABLE`` means it
was audited on disk and its coverage is known. ``ABSENT`` means it was looked
for and is not there. ``UNKNOWN`` means nobody has checked. The third state is
the one that usually gets lost, and losing it is how a research system ends up
believing a question is unanswerable when in fact nobody asked.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from tools.strategy_factory_v2.holdout import (
    DEVELOPMENT,
    FINAL_HOLDOUT,
    VALIDATION,
    DataPartition,
)
from tools.strategy_factory_v2.ingest import (
    ABSENT,
    AVAILABLE,
    CANONICAL_FIELDS,
    UNKNOWN,
    load_ledger,
)
from tools.strategy_factory_v2.spec import SPEC_VERSION

_STATUS_ICON = {AVAILABLE: "OK", ABSENT: "ABSENT", UNKNOWN: "**UNKNOWN**"}


def write_capability_matrix_csv(matrix: pd.DataFrame, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "data_capability_matrix.csv"
    matrix.to_csv(path, index=False)
    return path


def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "--"
    text = str(value)
    return text[:19].replace("+00:00", "Z")


def write_data_coverage_report(
    matrix: pd.DataFrame,
    local_audit: dict[str, Any],
    partition: DataPartition | None,
    ledger: dict[str, Any],
    blocked_hypotheses: dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    add = lines.append

    add("# Phase A2 -- data coverage report")
    add("")
    add(f"- Spec version: `{SPEC_VERSION}`")
    add(f"- Generated: {datetime.now(timezone.utc).isoformat()}")
    add("")
    add("> Status vocabulary is deliberately three-valued. `UNKNOWN` means the field")
    add("> has **not** been audited yet. It is never reported as `ABSENT`: a field")
    add("> nobody looked for is not the same as a field that does not exist, and")
    add("> collapsing the two is how a system convinces itself a question is")
    add("> unanswerable when nobody actually asked.")
    add("")

    # ---- headline --------------------------------------------------------
    add("## 1. Headline")
    add("")
    add("| Metric | Value |")
    add("|---|---:|")
    counts = {field: (matrix[f"{field}_status"] == AVAILABLE).sum() for field in CANONICAL_FIELDS}
    for field in CANONICAL_FIELDS:
        add(f"| Symbols with `{field}` available | {counts[field]} / {len(matrix)} |")
    add(f"| Preregistered hypotheses | {blocked_hypotheses.get('hypothesis_count')} |")
    add(f"| Testable | **{blocked_hypotheses.get('testable_hypotheses')}** |")
    add(f"| BLOCKED | **{blocked_hypotheses.get('blocked_hypotheses')}** |")
    add("")

    # ---- capability matrix ----------------------------------------------
    add("## 2. Data capability matrix")
    add("")
    header = "| Asset | " + " | ".join(f"{f} | {f}_rows" for f in CANONICAL_FIELDS) + " |"
    # Render a compact status + row-count table.
    add("| Asset | " + " | ".join(CANONICAL_FIELDS) + " |")
    add("|---" * (len(CANONICAL_FIELDS) + 1) + "|")
    for _, row in matrix.iterrows():
        cells = []
        for field in CANONICAL_FIELDS:
            status = row.get(f"{field}_status", UNKNOWN)
            rows_ = int(row.get(f"{field}_rows") or 0)
            mark = _STATUS_ICON.get(status, status)
            cells.append(f"{mark}<br>{rows_:,}" if rows_ else mark)
        add(f"| {row['symbol']} | " + " | ".join(cells) + " |")
    add("")
    add("Counts under each status are row counts. A field marked `UNKNOWN` has rows")
    add("only if it was audited but not ingested; a field with neither a status nor")
    add("rows is genuinely unaudited.")
    add("")

    # ---- coverage --------------------------------------------------------
    add("## 3. Exact coverage per dataset")
    add("")
    add("| Dataset | Rows | Start | End | Files | Checksum-verified | Unverified |")
    add("|---|---:|---|---|---:|---:|---:|")
    for key, record in sorted(ledger.get("datasets", {}).items()):
        add(
            f"| `{key}` | {int(record.get('rows') or 0):,} | {_fmt(record.get('start'))} | "
            f"{_fmt(record.get('end'))} | {int(record.get('files') or 0):,} | "
            f"{int(record.get('files_verified') or 0):,} | "
            f"{int(record.get('files_checksum_unavailable') or 0):,} |"
        )
    add("")

    # ---- local sources ---------------------------------------------------
    add("## 4. Pre-existing local sources (unchanged by this phase)")
    add("")
    add("| Symbol | Field | Rows | Start | End |")
    add("|---|---|---:|---|---|")
    for symbol, audit in sorted((local_audit.get("symbol_audits") or {}).items()):
        for timeframe, report in sorted(
            (audit.get("timeframes") or {}).items(),
            key=lambda kv: kv[0],
        ):
            add(
                f"| {symbol} | price {timeframe} | {int(report.get('rows') or 0):,} | "
                f"{_fmt(report.get('start'))} | {_fmt(report.get('end'))} |"
            )
        funding = (audit.get("funding") or {}).get("selected") or {}
        if funding.get("status") == AVAILABLE:
            add(
                f"| {symbol} | funding (8h) | {int(funding.get('rows') or 0):,} | "
                f"{_fmt(funding.get('start'))} | {_fmt(funding.get('end'))} |"
            )
    add("")

    # ---- research boundary ----------------------------------------------
    add("## 5. Research boundary")
    add("")
    if partition is None:
        add("**No partition could be declared.** Without a partition there is no")
        add("untested data, and a survivor would have nothing left to prove itself on.")
    else:
        add("| Region | Start | End | Policy |")
        add("|---|---|---|---|")
        add(
            f"| {DEVELOPMENT} | {_fmt(partition.development_start)} | "
            f"{_fmt(partition.development_end)} | feature research, hypothesis discovery |"
        )
        add(
            f"| {VALIDATION} | {_fmt(partition.validation_start)} | "
            f"{_fmt(partition.validation_end)} | selection may not see this |"
        )
        add(
            f"| **{FINAL_HOLDOUT}** | {_fmt(partition.holdout_start)} | "
            f"{_fmt(partition.holdout_end)} | **never read during development** |"
        )
        add("")
        add(f"- Latest complete day (derived from the data, never from the clock): "
            f"**{partition.latest_complete_day}**")
        add(f"- Boundary source: {partition.boundary_source}")
        add("")
        add("The holdout is enforced by `tools/strategy_factory_v2/holdout.py`, which")
        add("rejects any development frame containing a timestamp at or after")
        add(f"`{_fmt(partition.holdout_start)}`, and records every access with a written")
        add("justification and the spec version frozen beforehand.")
    add("")

    # ---- blocked ---------------------------------------------------------
    add("## 6. Hypotheses still BLOCKED")
    add("")
    blocked_ids = blocked_hypotheses.get("blocked_hypothesis_ids") or []
    if not blocked_ids:
        add("**None.** Every preregistered hypothesis has the data it requires.")
    else:
        families = blocked_hypotheses.get("families", {})
        add("| Family | Blocked | Requires |")
        add("|---|---:|---|")
        for name, entry in sorted(families.items()):
            if entry.get("blocked"):
                add(f"| {name} | {entry['blocked']} | {', '.join(entry['required_fields'])} |")
        add("")
        add(f"Total blocked hypothesis ids: **{len(blocked_ids)}**")
        add("")
        add("```text")
        for hypothesis_id in blocked_ids:
            add(hypothesis_id)
        add("```")
    add("")

    # ---- integrity -------------------------------------------------------
    add("## 7. Data integrity")
    add("")
    ledger_files = ledger.get("files", {})
    total = len(ledger_files)
    verified = sum(1 for f in ledger_files.values() if f.get("checksum_status") == "verified")
    unavailable = sum(
        1 for f in ledger_files.values() if f.get("checksum_status") == "checksum_unavailable"
    )
    failed = sum(1 for f in ledger_files.values() if f.get("error"))
    add(f"- Archive files fetched: **{total:,}**")
    add(f"- Checksum verified against the published `.CHECKSUM` sidecar: **{verified:,}**")
    add(f"- Published without a sidecar (recorded, not treated as verified): **{unavailable:,}**")
    add(f"- Failed: **{failed:,}**")
    add("")
    add("A file whose checksum does not match is deleted and reported. It is never")
    add("parsed, because a file that failed verification is worse than a missing one:")
    add("a missing file is obvious, a silently wrong one is not.")
    add("")

    # ---- known quirks ----------------------------------------------------
    add("## 8. Known characteristics of the recovered data")
    add("")
    add("These are properties of the source, not defects introduced by recovery.")
    add("They constrain how the data may be used.")
    add("")
    add("- **Open interest is not on a regular grid.** Binance publishes 288")
    add("  irregularly spaced samples per day, in unsorted order. It is ingested as")
    add("  the event stream it is. Resampling it onto a clean 5-minute grid would")
    add("  assert a sampling precision the source does not provide.")
    add("- **Early kline CSVs are headerless.** Binance switched to named headers")
    add("  partway through the archive; both layouts are parsed and the format used")
    add("  is recorded per file.")
    add("- **Taker sell volume is derived**, as `volume - taker_buy_volume`. Binance")
    add("  publishes no taker-sell column. This is exact arithmetic on two reported")
    add("  fields, not an estimate.")
    add("- **Funding is 8-hourly**, not 1-hourly, and is sourced locally. It is never")
    add("  re-fetched, because the two existing sources already agree bit-for-bit on")
    add("  every shared settlement.")
    add("")

    path = output_dir / "data_coverage_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_audit_v2(
    local_audit: dict[str, Any],
    matrix: pd.DataFrame,
    ledger: dict[str, Any],
    partition: DataPartition | None,
    blocked_hypotheses: dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec_version": SPEC_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "A2 (data recovery and capability matrix)",
        "hypothesis_experiment_run": False,
        "pre_existing_data": local_audit,
        "recovered_capability_matrix": matrix.to_dict("records"),
        "recovered_datasets": ledger.get("datasets", {}),
        "archive_file_count": len(ledger.get("files", {})),
        "partition": partition.as_dict() if partition else None,
        "hypothesis_registry": blocked_hypotheses,
    }
    path = output_dir / "data_audit_v2.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def write_manifest(
    local_audit: dict[str, Any],
    matrix: pd.DataFrame,
    ledger: dict[str, Any],
    partition: DataPartition | None,
    blocked_hypotheses: dict[str, Any],
    output_dir: Path,
    run_id: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    from tools.strategy_factory_v2.data import data_fingerprint
    from tools.strategy_factory_v2.spec import spec_manifest

    payload = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "phase": "A2 (data recovery and capability matrix)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "hypothesis_experiment_run": False,
        "hypotheses_added": 0,
        "note": (
            "No hypothesis was evaluated. The preregistered registry is unchanged "
            "at 92; acquiring data does not license new hypotheses."
        ),
        "data_fingerprint_local": data_fingerprint(local_audit),
        "preregistration": spec_manifest(),
        "partition": partition.as_dict() if partition else None,
        "development_cutoff": partition.development_end if partition else None,
        "holdout_start": partition.holdout_start if partition else None,
        "holdout_end": partition.holdout_end if partition else None,
        "latest_complete_day": partition.latest_complete_day if partition else None,
        "capability_matrix": matrix.to_dict("records"),
        "hypothesis_registry": blocked_hypotheses,
        "recovered_dataset_count": len(ledger.get("datasets", {})),
        "archive_file_count": len(ledger.get("files", {})),
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
