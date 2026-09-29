"""Write the A2.5 integrity artifacts.

    python -m tools.strategy_factory_v2.integrity_gate --out <run-dir>

Emits ``data_integrity_v2.json``, ``data_integrity_report.md`` and a refreshed
``data_capability_matrix.csv``, and prints a PASS/FAIL verdict. The exit code
is non-zero on FAIL, so a pipeline cannot proceed past a failed gate by
ignoring its output.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from tools.strategy_factory_v2.coverage_report import write_capability_matrix_csv
from tools.strategy_factory_v2.integrity import (
    BASIS_DEFINITION,
    BASIS_SOURCE,
    DUPLICATE_POLICY,
    FUNDING_OBSERVABILITY,
    PRICE_INTERVALS,
    SYMBOLS,
    run_gate,
)
from tools.strategy_factory_v2.spec import SPEC_VERSION


def _md_table(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return lines


def write_report(gate: dict[str, Any], matrix: pd.DataFrame, output_dir: Path) -> Path:
    lines: list[str] = []
    add = lines.append
    add("# Phase A2.5 — data integrity report")
    add("")
    add(f"- Spec version: `{SPEC_VERSION}`")
    add(f"- Generated: {gate['generated_utc']}")
    add(f"- **A2.5 STATUS: {gate['a25_status']}** "
        f"({gate['criteria_total'] - len(gate['criteria_failed'])}/{gate['criteria_total']} criteria)")
    add("")
    if gate["a25_status"] != "PASS":
        add("> The gate FAILED. Phase C must not run. Failed criteria:")
        add("")
        for name in gate["criteria_failed"]:
            add(f"> - {name}")
        add("")

    add("## 1. Gate criteria")
    add("")
    add("| Criterion | Result | Detail |")
    add("|---|---|---|")
    for criterion in gate["criteria"]:
        add(f"| {criterion['criterion']} | **{'PASS' if criterion['passed'] else 'FAIL'}** | "
            f"{criterion['detail']} |")
    add("")

    add("## 2. Provenance")
    add("")
    provenance = gate.get("provenance", {})
    by_state = provenance.get("by_state", {})
    add("| State | Files |")
    add("|---|---:|")
    for state, count in sorted(by_state.items()):
        add(f"| `{state}` | {count:,} |")
    add(f"| **total** | **{provenance.get('total_files', 0):,}** |")
    add("")
    add(f"- Distinct published sources: {provenance.get('distinct_sources', 0):,}")
    add(f"- Total bytes: {provenance.get('total_bytes', 0):,}")
    add(f"- Files in no state: **{provenance.get('unclassified', 0)}**")
    add("")
    add("Every archive file is in exactly one state. `CHECKSUM_VERIFIED` means the file's")
    add("SHA-256 matches the value in the sidecar Binance publishes beside it. A file with")
    add("no sidecar would be `NO_CHECKSUM_AVAILABLE`, and a file that was only classified")
    add("from disk would be `NOT_CHECKED` — neither is ever called verified.")
    add("")

    add("## 3. Dataset integrity")
    add("")
    add("| Symbol | Dataset | TF | Rows | Start | End | Dup | Missing | Invalid | Order | Max gap (min) |")
    add("|---|---|---|---:|---|---|---:|---:|---:|---|---:|")
    for dataset in gate["datasets"]:
        add(
            f"| {dataset['symbol']} | {dataset['dataset']} | {dataset['interval']} | "
            f"{dataset['rows']:,} | {str(dataset['start'])[:10]} | {str(dataset['end'])[:10]} | "
            f"{dataset['duplicate_rows']} | {dataset['missing_intervals']} | "
            f"{dataset['invalid_rows']} | {dataset['timestamp_order']} | "
            f"{dataset['max_gap_minutes']:.0f} |"
        )
    add("")
    add(f"**Duplicate policy.** {DUPLICATE_POLICY}")
    add("")

    add("## 4. Basis")
    add("")
    add(f"- Definition as implemented: `{BASIS_DEFINITION}`")
    add(f"- Source classification: `{BASIS_SOURCE}`")
    add("- Join: backward as-of — an index observation is used only at or before its timestamp.")
    add("")
    add("| Symbol | Status | Rows | Start | End | Missing | Mean (bps) | Std (bps) |")
    add("|---|---|---:|---|---|---:|---:|---:|")
    for entry in gate["basis"]:
        add(
            f"| {entry['symbol']} | {entry['status']} | {entry['basis_rows']:,} | "
            f"{str(entry['basis_start'])[:10]} | {str(entry['basis_end'])[:10]} | "
            f"{entry['basis_missing_rows']:,} | {entry['basis_mean_bps']} | {entry['basis_std_bps']} |"
        )
    add("")
    add("Basis is a derived feature, so it carries coverage metadata exactly like a")
    add("fetched dataset. A field reported AVAILABLE with blank coverage is a claim")
    add("nobody checked.")
    add("")

    add("## 5. Causal joins")
    add("")
    add("### Open interest")
    add("")
    add("| Symbol | Attached | Median age (s) | p95 age (s) | Max age (s) | Leakage | Control fired |")
    add("|---|---:|---:|---:|---:|---:|---|")
    for entry in gate["oi_joins"]:
        if entry.get("status") != "OK":
            add(f"| {entry['symbol']} | — | — | — | — | MISSING | — |")
            continue
        joined = entry["as_joined"]["age_seconds"]
        add(
            f"| {entry['symbol']} | {entry['as_joined']['attached_rows']:,} | "
            f"{joined['median']:.0f} | {joined['p95']:.0f} | {joined['max']:.0f} | "
            f"{entry['leakage']['violations']} | "
            f"{'yes' if entry['negative_control']['detected'] else 'NO'} |"
        )
    add("")
    add("The negative control re-stamps every OI observation 60 minutes **earlier** while")
    add("retaining the true timestamp, which is what happens when someone decides a sample")
    add("\"belongs\" to the bar before it. The age stays positive, so only a check against")
    add("the un-rewritten truth catches it.")
    add("")
    add("### Funding")
    add("")
    add("| Symbol | Events | Attached | Leakage | Control fired |")
    add("|---|---:|---:|---:|---|")
    for entry in gate["funding_joins"]:
        if entry.get("status") != "OK":
            add(f"| {entry['symbol']} | — | — | MISSING | — |")
            continue
        add(
            f"| {entry['symbol']} | {entry['events']:,} | "
            f"{entry['as_joined']['attached_rows']:,} | {entry['leakage']['violations']} | "
            f"{'yes' if entry['negative_control']['detected'] else 'NO'} |"
        )
    add("")
    add("**Funding observability convention** (fixed by the preregistration):")
    add("")
    for key, value in FUNDING_OBSERVABILITY.items():
        add(f"- `{key}`: {value}")
    add("")

    add("## 6. Cross-source validation")
    add("")
    add("| Dataset | Symbol | Sources | Overlap | Max abs diff | Mean abs diff | Median abs diff | Exact match |")
    add("|---|---|---|---:|---:|---:|---:|---:|")
    for entry in gate["cross_source"]:
        add(
            f"| {entry['dataset']} | {entry['symbol']} | {', '.join(entry['sources'])} | "
            f"{entry['overlap_rows'] if entry['overlap_rows'] is not None else '—'} | "
            f"{entry['max_abs_diff'] if entry['max_abs_diff'] is not None else '—'} | "
            f"{entry['mean_abs_diff'] if entry['mean_abs_diff'] is not None else '—'} | "
            f"{entry['median_abs_diff'] if entry['median_abs_diff'] is not None else '—'} | "
            f"{entry['exact_match_rate'] if entry['exact_match_rate'] is not None else '—'} |"
        )
    add("")

    add("## 7. Data capability matrix")
    add("")
    status_columns = [c for c in matrix.columns if c.endswith("_status")]
    add("| Asset | " + " | ".join(s.replace("_status", "") for s in status_columns) + " |")
    add("|---" * (len(status_columns) + 1) + "|")
    for _, row in matrix.iterrows():
        add(f"| {row['symbol']} | " + " | ".join(str(row[c]) for c in status_columns) + " |")
    add("")

    path = output_dir / "data_integrity_report.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.strategy_factory_v2.integrity_gate")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    gate = run_gate()
    output = args.out
    output.mkdir(parents=True, exist_ok=True)

    (output / "data_integrity_v2.json").write_text(
        json.dumps(gate, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    # Rebuild the matrix from the audit rather than from the ingest-time view,
    # so an AVAILABLE field always carries the coverage the audit measured.
    from tools.strategy_factory_v2.a2_finalize import build_matrix

    matrix = build_matrix()
    basis_by_symbol = {entry["symbol"]: entry for entry in gate["basis"]}
    for field in ("basis_start", "basis_end", "basis_rows"):
        matrix[field] = [
            basis_by_symbol.get(symbol, {}).get(field, 0) or 0 for symbol in matrix["symbol"]
        ]
    matrix["basis_status"] = [
        basis_by_symbol.get(symbol, {}).get("status", "UNKNOWN") for symbol in matrix["symbol"]
    ]
    matrix["basis_source"] = BASIS_SOURCE
    matrix["basis_definition"] = BASIS_DEFINITION
    write_capability_matrix_csv(matrix, output)
    write_report(gate, matrix, output)

    print(f"A2.5 STATUS: {gate['a25_status']}")
    for criterion in gate["criteria"]:
        print(f"  [{'PASS' if criterion['passed'] else 'FAIL'}] {criterion['criterion']}")
    print(f"artifacts -> {output}")
    return 0 if gate["a25_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
