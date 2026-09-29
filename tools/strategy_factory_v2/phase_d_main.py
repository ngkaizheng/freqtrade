"""Phase D -- the runner. Freeze, recompute, attribute, validate, stop.

    python -m tools.strategy_factory_v2.phase_d_main --out <run-dir>

The run fails closed. If any code path reads inside the final holdout, the
guard raises and nothing is written; if the freeze hashes drift, the run stops
before it computes anything; if the end-of-run access count is not exactly
zero, the report is not produced.
"""

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

from tools.strategy_factory_v2.discovery_engine import make_folds
from tools.strategy_factory_v2.freeze import (
    HoldoutAccessViolation,
    HoldoutGuard,
    freeze_candidates,
    regime_control_mask,
    verify_freeze,
)
from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.phase_d import (
    DIAGNOSTIC_YEARS,
    HORIZON,
    MIN_VALIDATION_SAMPLE,
    NO_SAMPLE,
    OPPOSITE,
    REPLICATED,
    SYMBOLS,
    TIMEFRAME,
    build_frames,
    by_fold,
    by_month,
    by_symbol,
    by_year,
    candidate_returns,
    classify_replication,
    missing_inputs,
)
from tools.strategy_factory_v2.spec import SPEC_VERSION
from tools.strategy_factory_v2.uncertainty import uncertainty_report

CANDIDATE_IDS = (
    "H13_BTC_FILTER_1H_STRONG_UP_SHORT",
    "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT",
)


def _load_partition() -> DataPartition:
    lock = read_lock()
    if not lock:
        raise SystemExit("no holdout lock file; the research boundary must exist before Phase D")
    return DataPartition(**lock["partition"])


def run_phase_d(output_dir: Path, candidates: Sequence[str] = CANDIDATE_IDS) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    partition = _load_partition()
    guard = HoldoutGuard(partition=partition)

    # ---- 1. freeze, before anything is computed -------------------------
    freeze = freeze_candidates(candidates)
    (output_dir / "candidate_freeze.json").write_text(
        json.dumps(freeze, indent=2, default=str), encoding="utf-8"
    )
    integrity = verify_freeze(freeze, candidates)
    if not integrity["intact"]:
        raise SystemExit(
            "candidate freeze check failed: " + "; ".join(integrity["problems"])
        )

    # ---- 2. recompute signals through the Phase C pipeline --------------
    print("building development frames...", flush=True)
    dev_frames = build_frames(SYMBOLS, TIMEFRAME, partition, "development", guard)
    print("building validation frames...", flush=True)
    val_frames = build_frames(SYMBOLS, TIMEFRAME, partition, "validation", guard)
    print(f"  development rows: {sum(len(f.frame) for f in dev_frames.values()):,}", flush=True)
    print(f"  validation rows : {sum(len(f.frame) for f in val_frames.values()):,}", flush=True)

    # The walk-forward folds come from the development region, unchanged.
    folds = make_folds(next(iter(dev_frames.values())).frame)

    results: list[dict[str, Any]] = []
    year_tables: list[pd.DataFrame] = []
    fold_tables: list[pd.DataFrame] = []
    symbol_tables: list[pd.DataFrame] = []
    month_tables: list[pd.DataFrame] = []
    attribution_rows: list[dict[str, Any]] = []
    uncertainty_rows: list[dict[str, Any]] = []

    for candidate_id in candidates:
        hypothesis = get(candidate_id)
        # A predicate whose inputs are absent is untestable, not empty. Saying so
        # explicitly is the difference between "the market offered no
        # opportunity" and "the code never gave it the chance to look".
        for region, frames in (("development", dev_frames), ("validation", val_frames)):
            absent = missing_inputs(hypothesis, frames)
            if absent:
                raise SystemExit(
                    f"{candidate_id}: required input(s) {absent} are absent in the "
                    f"{region} region. A candidate cannot be validated on a frame "
                    f"that does not carry its inputs."
                )
        dev_trades = candidate_returns(hypothesis, dev_frames)
        val_trades = candidate_returns(hypothesis, val_frames)

        dev_stats = by_symbol(dev_trades)
        year_table, year_summary = by_year(dev_trades)
        fold_table, fold_summary = by_fold(dev_trades, folds)
        val_symbol_table, val_symbol_summary = by_symbol(val_trades)
        month_table = by_month(val_trades)

        for table, store in (
            (year_table.assign(candidate=candidate_id), year_tables),
            (fold_table.assign(candidate=candidate_id), fold_tables),
            (dev_stats[0].assign(candidate=candidate_id, region="development"), symbol_tables),
            (val_symbol_table.assign(candidate=candidate_id, region="validation"), symbol_tables),
            (month_table.assign(candidate=candidate_id), month_tables),
        ):
            if table is not None and not table.empty:
                store.append(table)

        from tools.strategy_factory_v2.discovery_engine import trade_metrics

        dev_metrics = trade_metrics(dev_trades["net_base"]) if not dev_trades.empty else {"sample_count": 0}
        dev_stress = trade_metrics(dev_trades["net_stress"]) if not dev_trades.empty else {}
        val_metrics = trade_metrics(val_trades["net_base"]) if not val_trades.empty else {"sample_count": 0}
        val_stress = trade_metrics(val_trades["net_stress"]) if not val_trades.empty else {}

        dev_exp = dev_metrics.get("mean_return")
        val_exp = val_metrics.get("mean_return")
        verdict = classify_replication(dev_exp, val_exp, int(val_metrics.get("sample_count", 0)))

        uncertainty_rows.append(
            {
                "candidate": candidate_id,
                "region": "validation",
                **uncertainty_report(
                    val_trades["net_base"].to_numpy() if not val_trades.empty else np.array([])
                ),
            }
        )
        uncertainty_rows.append(
            {
                "candidate": candidate_id,
                "region": "development",
                **uncertainty_report(
                    dev_trades["net_base"].to_numpy() if not dev_trades.empty else np.array([])
                ),
            }
        )

        # ---- regime attribution: the mechanical control ------------------
        try:
            control_masks = {
                symbol: regime_control_mask(discovery.frame, hypothesis)
                for symbol, discovery in dev_frames.items()
            }
            control_trades = candidate_returns(
                hypothesis, dev_frames, mask_override=control_masks
            )
            control_stats = trade_metrics(control_trades["net_base"]) if not control_trades.empty else {"sample_count": 0}
            control_val_masks = {
                symbol: regime_control_mask(discovery.frame, hypothesis)
                for symbol, discovery in val_frames.items()
            }
            control_val_trades = candidate_returns(
                hypothesis, val_frames, mask_override=control_val_masks
            )
            control_val_stats = (
                trade_metrics(control_val_trades["net_base"]) if not control_val_trades.empty else {"sample_count": 0}
            )
            attribution_rows.append(
                {
                    "candidate": candidate_id,
                    "region": "development",
                    "candidate_trade_count": int(dev_metrics.get("sample_count", 0)),
                    "candidate_short_return": dev_exp,
                    "candidate_PF": dev_metrics.get("profit_factor"),
                    "candidate_expectancy": dev_exp,
                    "control_trade_count": int(control_stats.get("sample_count", 0)),
                    "control_short_return": control_stats.get("mean_return"),
                    "control_PF": control_stats.get("profit_factor"),
                    "control_expectancy": control_stats.get("mean_return"),
                    "regime_filter_uplift": (
                        (dev_exp - control_stats.get("mean_return"))
                        if dev_exp is not None and control_stats.get("mean_return") is not None
                        else None
                    ),
                    "control_status": "diagnostic only; not a hypothesis, not a candidate",
                }
            )
            attribution_rows.append(
                {
                    "candidate": candidate_id,
                    "region": "validation",
                    "candidate_trade_count": int(val_metrics.get("sample_count", 0)),
                    "candidate_short_return": val_exp,
                    "candidate_PF": val_metrics.get("profit_factor"),
                    "candidate_expectancy": val_exp,
                    "control_trade_count": int(control_val_stats.get("sample_count", 0)),
                    "control_short_return": control_val_stats.get("mean_return"),
                    "control_PF": control_val_stats.get("profit_factor"),
                    "control_expectancy": control_val_stats.get("mean_return"),
                    "regime_filter_uplift": (
                        (val_exp - control_val_stats.get("mean_return"))
                        if val_exp is not None and control_val_stats.get("mean_return") is not None
                        else None
                    ),
                    "control_status": "diagnostic only; not a hypothesis, not a candidate",
                }
            )
        except Exception as error:
            attribution_rows.append(
                {
                    "candidate": candidate_id,
                    "region": "both",
                    "status": "REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE",
                    "reason": str(error),
                }
            )

        results.append(
            {
                "candidate": candidate_id,
                "family": hypothesis.family,
                "timeframe": hypothesis.timeframe,
                "direction": hypothesis.expected_direction,
                "horizon_bars": HORIZON,
                "logic_hash": next(c["logic_hash"] for c in freeze["candidates"] if c["id"] == candidate_id),
                "development_n": int(dev_metrics.get("sample_count", 0)),
                "development_expectancy": dev_exp,
                "development_median": dev_metrics.get("median_return"),
                "development_std": dev_metrics.get("std_return"),
                "development_win_rate": dev_metrics.get("win_rate"),
                "development_pf": dev_metrics.get("profit_factor"),
                "development_sharpe": dev_metrics.get("sharpe"),
                "development_sortino": dev_metrics.get("sortino"),
                "development_stress_expectancy": dev_stress.get("mean_return"),
                "development_stress_pf": dev_stress.get("profit_factor"),
                "development_mae": dev_metrics.get("mae"),
                "development_mfe": dev_metrics.get("mfe"),
                "validation_n": int(val_metrics.get("sample_count", 0)),
                "validation_expectancy": val_exp,
                "validation_median": val_metrics.get("median_return"),
                "validation_std": val_metrics.get("std_return"),
                "validation_win_rate": val_metrics.get("win_rate"),
                "validation_pf": val_metrics.get("profit_factor"),
                "validation_sharpe": val_metrics.get("sharpe"),
                "validation_sortino": val_metrics.get("sortino"),
                "validation_stress_expectancy": val_stress.get("mean_return"),
                "validation_stress_pf": val_stress.get("profit_factor"),
                "validation_double_expectancy": (
                    trade_metrics(val_trades["net_double"]).get("mean_return")
                    if not val_trades.empty
                    else None
                ),
                "validation_sign": "POSITIVE" if (val_exp or 0) > 0 else ("NEGATIVE" if val_exp is not None else "--"),
                "replication_class": verdict,
                "year_summary": year_summary,
                "fold_summary": fold_summary,
                "development_symbol_summary": dev_stats[1],
                "validation_symbol_summary": val_symbol_summary,
                "validation_months": int(len(month_table)) if not month_table.empty else 0,
            }
        )
        print(
            f"  {candidate_id}: dev N={results[-1]['development_n']:,} "
            f"exp={_f(dev_exp)} | val N={results[-1]['validation_n']:,} "
            f"exp={_f(val_exp)} -> {verdict}",
            flush=True,
        )

    # ---- 3. the end-of-run holdout assertion ---------------------------
    guard.assert_clean()
    access_log = guard.log()
    (output_dir / "holdout_access_log.json").write_text(
        json.dumps(access_log, indent=2, default=str), encoding="utf-8"
    )

    frame = pd.DataFrame(results)
    return {
        "partition": partition,
        "freeze": freeze,
        "results": frame,
        "access_log": access_log,
        "guard": guard,
        "year_tables": year_tables,
        "fold_tables": fold_tables,
        "symbol_tables": symbol_tables,
        "month_tables": month_tables,
        "attribution": pd.DataFrame(attribution_rows),
        "uncertainty": pd.DataFrame(uncertainty_rows),
        "folds": folds,
    }


def _f(value: Any, digits: int = 5) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "--"
    if isinstance(value, (int, np.integer)):
        return str(value)
    return f"{float(value):+.{digits}f}"


def write_outputs(result: dict[str, Any], output_dir: Path, run_id: str) -> dict[str, Any]:
    frame: pd.DataFrame = result["results"]
    partition: DataPartition = result["partition"]
    access = result["access_log"]

    result["validation_results.csv"] = None
    frame.to_csv(output_dir / "validation_results.csv", index=False)
    _write(result["month_tables"], output_dir / "validation_by_month.csv")
    # Each symbol file carries exactly one region. Emitting both into each would
    # let a reader who opens only one of them draw a conclusion from the wrong
    # period.
    symbol_tables = result["symbol_tables"]
    _write(
        [t for t in symbol_tables if "region" in t.columns and (t["region"] == "validation").all()],
        output_dir / "validation_by_symbol.csv",
    )
    _write(result["year_tables"], output_dir / "development_year_diagnostics.csv")
    _write(result["fold_tables"], output_dir / "development_fold_diagnostics.csv")
    _write(
        [t for t in symbol_tables if "region" in t.columns and (t["region"] == "development").all()],
        output_dir / "development_symbol_diagnostics.csv",
    )
    result["attribution"].to_csv(output_dir / "regime_attribution.csv", index=False)
    result["uncertainty"].to_csv(output_dir / "uncertainty_diagnostics.csv", index=False)

    manifest = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "phase": "D (frozen candidate validation)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "candidates_frozen": len(result["freeze"]["candidates"]),
        "candidate_ids": [c["id"] for c in result["freeze"]["candidates"]],
        "development_accessed": True,
        "validation_accessed": True,
        "final_holdout_accessed": bool(access["final_holdout_access_count"]),
        "final_holdout_access_count": access["final_holdout_access_count"],
        "new_hypotheses": 0,
        "optimization_performed": False,
        "development_start": partition.development_start,
        "development_end": partition.development_end,
        "validation_start": partition.validation_start,
        "validation_end": partition.validation_end,
        "holdout_start": partition.holdout_start,
        "holdout_end": partition.holdout_end,
        "latest_complete_day": partition.latest_complete_day,
        "replication": {
            str(r["candidate"]): r["replication_class"] for _, r in frame.iterrows()
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    write_report(result, frame, output_dir)
    write_html(frame, output_dir)
    return manifest


def _write(tables: list[pd.DataFrame], path: Path) -> None:
    frames = [t for t in tables if t is not None and not t.empty]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined.to_csv(path, index=False)


def write_report(result: dict[str, Any], frame: pd.DataFrame, output_dir: Path) -> None:
    partition: DataPartition = result["partition"]
    access = result["access_log"]
    lines: list[str] = []
    add = lines.append

    add("# Phase D — Frozen Candidate Validation")
    add("")
    add("```text")
    add(f"Candidates frozen: {len(result['freeze']['candidates'])}")
    add("Development data accessed: YES")
    add("Validation data accessed: YES")
    add(f"Final holdout accessed: {'YES' if access['final_holdout_access_count'] else 'NO'}")
    add("New hypotheses introduced: NO")
    add("Candidate optimization performed: NO")
    add("```")
    add("")

    add("| Candidate | Development N | Development expectancy | Development stress expectancy | "
        "Validation N | Validation expectancy | Validation stress expectancy | Validation PF | "
        "Validation stress PF | Validation sign |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for _, row in frame.iterrows():
        add(
            f"| {row['candidate']} | {int(row['development_n']):,} | "
            f"{_f(row['development_expectancy'])} | {_f(row['development_stress_expectancy'])} | "
            f"{int(row['validation_n']):,} | {_f(row['validation_expectancy'])} | "
            f"{_f(row['validation_stress_expectancy'])} | {_f(row['validation_pf'], 3)} | "
            f"{_f(row['validation_stress_pf'], 3)} | {row['validation_sign']} |"
        )
    add("")

    add("## Replication classification")
    add("")
    add("| Candidate | Class | Development exp | Validation exp | Validation N |")
    add("|---|---|---:|---:|---:|")
    for _, row in frame.iterrows():
        add(
            f"| {row['candidate']} | **{row['replication_class']}** | "
            f"{_f(row['development_expectancy'])} | {_f(row['validation_expectancy'])} | "
            f"{int(row['validation_n']):,} |"
        )
    add("")
    add("This is descriptive evidence, not a pass/fail gate, and it is not a")
    add("winner score. `NO_MEANINGFUL_SAMPLE` is deliberately distinct from")
    add("failure: a candidate that did not fire in a five-month window has not")
    add("been shown wrong, it has not been shown anything.")
    add("")

    add("## Attribution — is the BTC regime doing the work?")
    add("")
    attribution = result["attribution"]
    if "status" in attribution.columns and attribution["status"].notna().any():
        add("`REGIME_ATTRIBUTION_CONTROL_NOT_AVAILABLE` — see `regime_attribution.csv`.")
    else:
        add("The control is the same SHORT setup with **only** the BTC regime clause")
        add("removed. It is a diagnostic, never a candidate.")
        add("")
        add("| Candidate | Region | Candidate N | Candidate exp | Control N | Control exp | Regime-filter uplift |")
        add("|---|---|---:|---:|---:|---:|---:|")
        for _, row in attribution.iterrows():
            add(
                f"| {row['candidate']} | {row['region']} | {int(row['candidate_trade_count']):,} | "
                f"{_f(row['candidate_expectancy'])} | {int(row['control_trade_count']):,} | "
                f"{_f(row['control_expectancy'])} | {_f(row['regime_filter_uplift'])} |"
            )
    add("")

    add("## Concentration — development period")
    add("")
    add("| Candidate | 2021-2022 P&L | 2023-2025 P&L | 2021-22 share | Positive years | Top-3 fold share |")
    add("|---|---:|---:|---:|---:|---:|")
    for _, row in frame.iterrows():
        years = row.get("year_summary") or {}
        folds = row.get("fold_summary") or {}
        add(
            f"| {row['candidate']} | {_f(years.get('year_2021_2022_pnl'), 2)} | "
            f"{_f(years.get('year_2023_2025_pnl'), 2)} | "
            f"{_f(years.get('share_2021_2022'), 2)} | {years.get('positive_year_count')} | "
            f"{_f(folds.get('top3_fold_profit_share'), 2)} |"
        )
    add("")

    add("## Uncertainty")
    add("")
    uncertainty = result["uncertainty"]
    add("| Candidate | Region | N | Lag-1 autocorr | Effective N | Bootstrap 95% CI | P(bootstrap > 0) |")
    add("|---|---|---:|---:|---:|---|---:|")
    for _, row in uncertainty.iterrows():
        bootstrap = row.get("bootstrap") or {}
        low, high = bootstrap.get("ci_low"), bootstrap.get("ci_high")
        interval = f"[{_f(low, 5)}, {_f(high, 5)}]" if low is not None else "--"
        add(
            f"| {row['candidate']} | {row['region']} | {int(row.get('n') or 0):,} | "
            f"{_f(row.get('lag1_autocorrelation'), 3)} | "
            f"{_f(row.get('effective_sample_size'), 1)} | {interval} | "
            f"{_f(bootstrap.get('bootstrap_p_gt_zero'), 3)} |"
        )
    add("")
    add("Signals generated from overlapping windows are not independent, so the naive")
    add("t-statistic overstates the evidence. The block-bootstrap interval is the")
    add("honest one. It is a diagnostic and has not been turned into a gate.")
    add("")

    add("## Recomputation discrepancy -- read this before trusting either number")
    add("")
    discrepant = frame[
        frame["development_stress_expectancy"].notna()
        & (frame["development_expectancy"] > 0)
        & (frame["development_stress_expectancy"] < 0)
    ]
    if len(discrepant):
        add("Phase C measured the candidates on the **walk-forward validation windows**")
        add("only. Phase D recomputes over the **contiguous** development region. The two")
        add("sample sets differ, and for at least one candidate the difference changes a")
        add("conclusion:")
        add("")
        add("| Candidate | Phase C fold-restricted | Phase D contiguous |")
        add("|---|---|---|")
        for _, row in discrepant.iterrows():
            add(
                f"| {row['candidate']} | passed the stress-positive gate | "
                f"**stress expectancy {_f(row['development_stress_expectancy'])} (negative)** "
                f"on {int(row['development_n']):,} signals |"
            )
        add("")
        add("This is not a case of picking whichever number is convenient. The")
        add("contiguous figure is the one recomputed from the frozen definition, and it")
        add("is the one this report leads with. The fold-restricted figure was not wrong;")
        add("it answered a narrower question. A candidate whose edge exists only in the")
        add("gaps between folds is not the candidate that was described.")
        add("")
    else:
        add("Phase C measured on walk-forward validation windows; Phase D recomputes")
        add("over the contiguous development region. No candidate changed sign under")
        add("stress between the two.")
        add("")

    add("## Evidence separation")
    add("")
    add("| Evidence tier | Status |")
    add("|---|---|")
    add("| Development | exists — this is where the candidates were found |")
    add("| Validation | "
        + ("exists — the candidates were recomputed and measured here" if True else "absent")
        + " |")
    add("| **Final holdout** | **ABSENT — sealed, access count "
        f"{access['final_holdout_access_count']}** |")
    add("")

    add("## Interpretation limits")
    add("")
    add("- Validation spans about five months against several years of development.")
    add("  A failure to replicate is informative; it is **not** proof that the")
    add("  development result was false. Power is low by construction.")
    add("- The final holdout remains the only genuinely untouched data in the")
    add("  project, and it has not been opened. It must stay last.")
    add("- Nothing here validates a *strategy*. These are conditional-return")
    add("  measurements on a research candidate, with a fixed holding horizon and a")
    add("  simplified cost and funding model — not an executable backtest.")
    add("- No threshold was changed in either direction. No hypothesis was added,")
    add("  dropped, or rescoped.")
    add("")

    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(frame: pd.DataFrame, output_dir: Path) -> None:
    rows = "".join(
        f"<tr><td>{html.escape(str(r.candidate))}</td>"
        f"<td>{int(r.development_n):,}</td><td>{_f(r.development_expectancy)}</td>"
        f"<td>{int(r.validation_n):,}</td><td>{_f(r.validation_expectancy)}</td>"
        f"<td>{html.escape(str(r.replication_class))}</td></tr>"
        for r in frame.itertuples()
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Phase D — Frozen Candidate Validation</title>
<style>body{{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem}}
table{{border-collapse:collapse;font-size:.9rem}}th,td{{border:1px solid #d4d4d4;padding:.35rem .6rem;text-align:left}}
th{{background:#f5f5f5}}.banner{{background:#dcfce7;border-left:4px solid #16a34a;padding:.75rem 1rem;margin:1rem 0}}
</style></head><body>
<h1>Phase D — Frozen Candidate Validation</h1>
<p>Spec <code>{html.escape(SPEC_VERSION)}</code></p>
<div class="banner"><b>Final holdout accessed: NO.</b> Development and validation
evidence only. No hypothesis was added and no candidate was optimised.</div>
<table><tr><th>Candidate</th><th>Dev N</th><th>Dev expectancy</th><th>Val N</th>
<th>Val expectancy</th><th>Class</th></tr>{rows}</table>
</body></html>
"""
    (output_dir / "report.html").write_text(document, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.strategy_factory_v2.phase_d_main")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = run_phase_d(args.out)
    except HoldoutAccessViolation as error:
        print(f"ABORTED: {error}", file=sys.stderr)
        return 2
    manifest = write_outputs(result, args.out, args.out.name)

    print()
    print("=" * 60)
    print("PHASE D STATUS: COMPLETE")
    print(f"CANDIDATES FROZEN: {manifest['candidates_frozen']}")
    print("VALIDATION ACCESSED: YES")
    print(f"FINAL HOLDOUT ACCESSED: {'YES' if manifest['final_holdout_accessed'] else 'NO'}")
    print(f"NEW HYPOTHESES: {manifest['new_hypotheses']}")
    print("OPTIMIZATION: NO")
    print("=" * 60)
    for _, row in result["results"].iterrows():
        print(
            f"  {row['candidate']}: {row['replication_class']} "
            f"(dev {_f(row['development_expectancy'])} / val {_f(row['validation_expectancy'])} "
            f"on {int(row['validation_n'])} signals)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
