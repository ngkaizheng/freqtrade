"""Phase E -- report and entry point. Appended to ``phase_e_main``."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.phase_e_main import run_phase_e
from tools.strategy_factory_v2.phase_e import (
    HOLDOUT_MONTHS,
    MEANINGFUL_SAMPLE,
    REGIME_CLAIM,
    _f,
)
from tools.strategy_factory_v2.spec import SPEC_VERSION


def _unpack(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value) if value.startswith("{") else json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


import ast  # noqa: E402


def write_report(result: dict[str, Any], output_dir: Path) -> None:
    frame: pd.DataFrame = result["results"]
    access = result["access"]
    partition = result["partition"]
    leakage = result["leakage"]

    lines: list[str] = []
    add = lines.append

    add("# Phase E — Final Holdout Evaluation")
    add("")
    add("```text")
    add(f"Candidates frozen: {len(result['protocol']['candidates'])}")
    add("New hypotheses: 0")
    add("Optimization: NO")
    add("Final holdout accessed: YES")
    add("```")
    add("")

    add("| Candidate | Holdout N | Holdout expectancy | Holdout stress expectancy | "
        "Holdout PF | Holdout stress PF | Bootstrap 95% CI | Interpretation |")
    add("|---|---:|---:|---:|---:|---:|---|---|")
    uncertainty = result["uncertainty"]
    for _, row in frame.iterrows():
        report = uncertainty[uncertainty["candidate"] == row["candidate"]]
        ci = "--"
        if len(report):
            boot = _unpack(report.iloc[0].get("bootstrap"))
            if boot.get("status") == "OK":
                ci = f"[{_f(boot['ci_low'])}, {_f(boot['ci_high'])}]"
        add(
            f"| {row['candidate']} | {int(row['trade_count']):,} | {_f(row['expectancy'])} | "
            f"{_f(row['stress_expectancy'])} | {_f(row['profit_factor'], 3)} | "
            f"{_f(row['stress_profit_factor'], 3)} | {ci} | **{row['interpretation']}** |"
        )
    add("")

    add("## What this does and does not say")
    add("")
    add("The final holdout is the only data in this project that played no part in")
    add("choosing a hypothesis, a threshold, a timeframe or a cost. It has now been")
    add("read. **It is no longer untouched data**, and nothing in this report may be")
    add("read as though it were.")
    add("")
    for _, row in frame.iterrows():
        add(f"- **{row['candidate']}** — {row['interpretation']}: {row['interpretation_reason']}.")
    add("")
    add(f"The regime claim carried forward from Phase D, unstrengthened: {REGIME_CLAIM}")
    add("")

    add("## 1. Monthly decomposition")
    add("")
    months: pd.DataFrame = result["months"]
    add("| Month | " + " | ".join(frame["candidate"]) + " |")
    add("|---" * (len(frame) + 1) + "|")
    for month in HOLDOUT_MONTHS:
        cells = []
        for candidate in frame["candidate"]:
            row = months[(months["candidate"] == candidate) & (months["month"] == month)]
            if not len(row):
                cells.append("--")
                continue
            entry = row.iloc[0]
            if int(entry["trade_count"]) == 0:
                cells.append("0 signals")
            else:
                cells.append(f"{int(entry['trade_count'])} / {_f(entry['expectancy'])}")
        add(f"| {month} | " + " | ".join(cells) + " |")
    add("")
    add("Cells show `trade count / expectancy`. No month was merged, removed or")
    add("reordered, including months with zero signals.")
    add("")
    for candidate in frame["candidate"]:
        subset = months[months["candidate"] == candidate]
        add(
            f"- `{candidate}`: **{int(subset['positive'].sum())} positive, "
            f"{int(subset['negative'].sum())} negative, "
            f"{int(subset['zero_signal'].sum())} zero-signal month(s)**"
        )
    add("")

    add("## 2. Symbol decomposition")
    add("")
    symbols: pd.DataFrame = result["symbols"]
    add("| Candidate | Symbol | Trades | P&L | P&L share | Expectancy | PF |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for _, row in symbols.iterrows():
        add(
            f"| {row['candidate']} | {row['symbol']} | {int(row['trade_count']):,} | "
            f"{_f(row['pnl'], 3)} | {_f(row['pnl_share'], 2)} | {_f(row['expectancy'])} | "
            f"{_f(row['profit_factor'], 3)} |"
        )
    add("")
    add("No symbol was excluded after the fact. The reference asset BTC cannot")
    add("confirm itself, so it contributes no signals to these cross-asset")
    add("candidates; that is a property of the definition, not a selection.")
    add("")

    add("## 3. BTC reference-state decomposition")
    add("")
    regimes: pd.DataFrame = result["regimes"]
    if regimes.empty:
        add("No signals were produced, so there is nothing to decompose.")
    else:
        add("| Candidate | BTC reference state | Signals | P&L | Expectancy | PF |")
        add("|---|---|---:|---:|---:|---:|")
        for _, row in regimes.iterrows():
            add(
                f"| {row['candidate']} | {row['btc_regime']} | {int(row['signal_count']):,} | "
                f"{_f(row['pnl'], 3)} | {_f(row['expectancy'])} | {_f(row['profit_factor'], 3)} |"
            )
    add("")
    add("The buckets are whatever the reference regime actually produced on the")
    add("signals. No bucket was created, merged or renamed after the fact.")
    add("")
    add("One state per candidate is structural, not a truncation: each candidate is")
    add("defined as shorting *inside* one named BTC state, so no other state can")
    add("produce a signal for it.")
    add("")

    add("## 4. Dependence-aware uncertainty")
    add("")
    add("| Candidate | N | Lag-1 autocorr | Effective N | Bootstrap 95% CI | P(>0) |")
    add("|---|---:|---:|---:|---|---:|")
    for _, row in uncertainty.iterrows():
        boot = _unpack(row.get("bootstrap"))
        ci = (
            f"[{_f(boot['ci_low'])}, {_f(boot['ci_high'])}]"
            if boot.get("status") == "OK"
            else str(boot.get("status", "--"))
        )
        add(
            f"| {row['candidate']} | {int(row.get('n') or 0):,} | "
            f"{_f(row.get('lag1_autocorrelation'), 3)} | "
            f"{_f(row.get('effective_sample_size'), 1)} | {ci} | "
            f"{_f(boot.get('bootstrap_p_gt_zero'), 3) if boot.get('status') == 'OK' else '--'} |"
        )
    add("")
    add("Signals from overlapping windows are serially dependent, so the naive")
    add("pooled t-statistic overstates the evidence. The block-bootstrap interval is")
    add("the honest one. No new threshold was derived from it.")
    add("")

    add("## 5. Evidence progression")
    add("")
    comparison: pd.DataFrame = result["comparison"]
    add("| Candidate | Region | N | Expectancy | Stress expectancy | PF | Stress PF |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for _, row in comparison.iterrows():
        add(
            f"| {row['candidate']} | {row['region']} | "
            f"{int(row.get('n') or 0):,} | {_f(row.get('expectancy'))} | "
            f"{_f(row.get('stress_expectancy'))} | {_f(row.get('profit_factor'), 3)} | "
            f"{_f(row.get('stress_profit_factor'), 3)} |"
        )
    add("")
    add("Regions are shown side by side and never averaged. The most favourable")
    add("region is not selected.")
    add("")

    add("## 6. Leakage and access accounting")
    add("")
    add(f"- Rows built over the holdout window: **{access['rows_read']:,}**")
    add(f"- Warm-up rows (development data, excluded from all counts): "
        f"**{access['warmup_rows_excluded']:,}**")
    add(f"- Derivative rows checked for `truth_timestamp <= decision_timestamp`: "
        f"**{leakage['rows_checked']:,}**")
    add(f"- Leakage violations: **{leakage['violations']}**")
    add(f"- Holdout access count: **{access['final_holdout_access_count']}** "
        f"(was {access['previous_access_count']} before this phase)")
    add(f"- Access count source: {access.get('count_source', 'n/a')}")
    add(f"- Unsealed at: {access['holdout_access_started']}")
    add("")
    if access.get("count_note"):
        add(access["count_note"])
        add("")
    add("")
    add("The holdout transition was written to the production lock file, not to a")
    add("shadow copy, so the authoritative record states that the region was opened.")
    add("")

    add("## 7. Interpretation limits")
    add("")
    add("- A positive holdout is **evidence of replication**, not proof of future")
    add("  profitability.")
    add("- A negative holdout is **evidence against replication over this period**,")
    add("  not proof that the relationship can never occur again.")
    add(f"- A replication statement requires at least {MEANINGFUL_SAMPLE} holdout")
    add("  observations; below that the verdict is `NO_MEANINGFUL_SAMPLE`, which is")
    add("  not a failure verdict.")
    add("- These are conditional-return measurements on a research candidate with a")
    add("  fixed holding horizon and a simplified cost and funding model. They are")
    add("  **not** an executable backtest, and no Freqtrade strategy exists.")
    add("- Nothing here was tuned. No threshold, parameter, regime definition,")
    add("  timeframe, symbol or holding period was changed after the protocol was")
    add("  written.")
    add("")

    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(frame: pd.DataFrame, output_dir: Path) -> None:
    rows = "".join(
        f"<tr><td>{html.escape(str(r.candidate))}</td><td>{int(r.trade_count):,}</td>"
        f"<td>{_f(r.expectancy)}</td><td>{_f(r.stress_expectancy)}</td>"
        f"<td>{_f(r.profit_factor, 3)}</td>"
        f"<td>{html.escape(str(r.interpretation))}</td></tr>"
        for r in frame.itertuples()
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Phase E — Final Holdout Evaluation</title>
<style>body{{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem}}
table{{border-collapse:collapse;font-size:.9rem}}th,td{{border:1px solid #d4d4d4;padding:.35rem .6rem;text-align:left}}
th{{background:#f5f5f5}}.banner{{background:#fef3c7;border-left:4px solid #d97706;padding:.75rem 1rem;margin:1rem 0}}
</style></head><body>
<h1>Phase E — Final Holdout Evaluation</h1>
<p>Spec <code>{html.escape(SPEC_VERSION)}</code> &middot; 2 frozen candidates &middot;
0 new hypotheses &middot; no optimization</p>
<div class="banner"><b>The final holdout has been read.</b> It is no longer untouched
data. A positive result is evidence of replication, not proof of future profitability.</div>
<table><tr><th>Candidate</th><th>Holdout N</th><th>Expectancy</th><th>Stress</th>
<th>PF</th><th>Interpretation</th></tr>{rows}</table>
</body></html>
"""
    (output_dir / "report.html").write_text(document, encoding="utf-8")


def write_outputs(result: dict[str, Any], output_dir: Path, run_id: str) -> dict[str, Any]:
    frame: pd.DataFrame = result["results"]
    frame.to_csv(output_dir / "final_holdout_results.csv", index=False)
    result["months"].to_csv(output_dir / "final_holdout_by_month.csv", index=False)
    result["symbols"].to_csv(output_dir / "final_holdout_by_symbol.csv", index=False)
    result["regimes"].to_csv(output_dir / "final_holdout_by_regime.csv", index=False)
    result["uncertainty"].to_csv(output_dir / "final_holdout_uncertainty.csv", index=False)
    result["comparison"].to_csv(
        output_dir / "development_validation_holdout_comparison.csv", index=False
    )
    (output_dir / "holdout_access_log.json").write_text(
        json.dumps(result["access"], indent=2, default=str), encoding="utf-8"
    )

    manifest = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "phase": "E (final holdout evaluation)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "candidates_evaluated": int(len(frame)),
        "final_holdout_accessed": True,
        "final_holdout_access_count": result["access"]["final_holdout_access_count"],
        "new_hypotheses": 0,
        "optimization": False,
        "candidate_logic_changed": False,
        "holdout_start": result["partition"].holdout_start,
        "holdout_end": result["partition"].holdout_end,
        "rows_read": result["access"]["rows_read"],
        "warmup_rows_excluded": result["access"]["warmup_rows_excluded"],
        "leakage_violations": result["leakage"]["violations"],
        "leakage_rows_checked": result["leakage"]["rows_checked"],
        "interpretations": {
            str(r["candidate"]): r["interpretation"] for _, r in frame.iterrows()
        },
        "regime_claim": REGIME_CLAIM,
        "unblinded": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    write_report(result, output_dir)
    write_html(frame, output_dir)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.strategy_factory_v2.phase_e_main")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_phase_e(args.out)
    manifest = write_outputs(result, args.out, args.out.name)

    print()
    print("=" * 60)
    print("PHASE E STATUS: COMPLETE")
    print(f"CANDIDATES EVALUATED: {manifest['candidates_evaluated']}")
    print("FINAL HOLDOUT ACCESSED: YES")
    print("NEW HYPOTHESES: 0")
    print("OPTIMIZATION: NO")
    print("CANDIDATE LOGIC CHANGED: NO")
    print("=" * 60)
    for _, row in result["results"].iterrows():
        print(
            f"  {row['candidate']}: {row['interpretation']} "
            f"(N={int(row['trade_count']):,}, exp={_f(row['expectancy'])}, "
            f"stress={_f(row['stress_expectancy'])})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
