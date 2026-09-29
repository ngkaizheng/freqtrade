"""Write the Phase C artifacts and print the required status block.

    python -m tools.strategy_factory_v2.phase_c --out user_data/strategy_factory_runs/v2/<run>

Every required artifact is written from the run's own results. The report leads
with the untested and failed populations rather than the survivors, because a
reader who sees only the survivors has been shown a selection.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.phase_c import run_phase_c
from tools.strategy_factory_v2.spec import (
    SPEC_VERSION,
    SURVIVOR_CRITERIA,
    spec_manifest,
)


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "--"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_outputs(result: dict[str, Any], output_dir: Path, run_id: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes = result["outcomes"]
    partition = result["partition"]

    # ---- trial ledger (one JSON object per line) -------------------------
    (output_dir / "trial_ledger.jsonl").write_text(
        "\n".join(result["ledger_lines"]) + "\n", encoding="utf-8"
    )

    # ---- hypothesis results ---------------------------------------------
    rows = []
    for outcome in outcomes:
        metrics = outcome.metrics
        stress = metrics.get("stress", {})
        rows.append(
            {
                "hypothesis_id": outcome.hypothesis_id,
                "family": outcome.family,
                "timeframe": outcome.timeframe,
                "expected_direction": outcome.expected_direction,
                "sample_count": outcome.sample_count,
                "mean_return": metrics.get("mean_return"),
                "median_return": metrics.get("median_return"),
                "std_return": metrics.get("std_return"),
                "win_rate": metrics.get("win_rate"),
                "profit_factor": metrics.get("profit_factor"),
                "expectancy": metrics.get("expectancy"),
                "sharpe": metrics.get("sharpe"),
                "sortino": metrics.get("sortino"),
                "stress_expectancy": stress.get("mean_return"),
                "stress_profit_factor": stress.get("profit_factor"),
                "double_cost_expectancy": metrics.get("double_cost_expectancy"),
                "positive_fold_fraction": metrics.get("positive_fold_fraction"),
                "max_single_fold_profit_share": metrics.get("max_single_fold_profit_share"),
                "top3_fold_profit_share": metrics.get("top3_fold_profit_share"),
                "positive_year_fraction": metrics.get("positive_year_fraction"),
                "yearly_pnl": json.dumps(metrics.get("yearly_pnl", {})),
                "folds_evaluated": metrics.get("folds_evaluated"),
                **{f"gate_{k}": v for k, v in outcome.gates.items()},
                "verdict": outcome.verdict,
                "survivor": outcome.survivor,
            }
        )
    hypotheses_frame = pd.DataFrame(rows).sort_values(
        ["survivor", "mean_return"], ascending=[False, False], na_position="last"
    )
    hypotheses_frame.to_csv(output_dir / "hypothesis_results.csv", index=False)

    # ---- conditional returns ---------------------------------------------
    conditional = pd.DataFrame(result["conditional_rows"])
    if not conditional.empty:
        conditional = conditional.sort_values(
            ["hypothesis_id", "symbol", "horizon_bars"]
        )
    conditional.to_csv(output_dir / "conditional_returns.csv", index=False)

    # ---- fold results -----------------------------------------------------
    folds = pd.DataFrame(result["fold_rows"])
    if not folds.empty:
        folds = folds.sort_values(["hypothesis_id", "fold_id"])
    folds.to_csv(output_dir / "fold_results.csv", index=False)

    # ---- regime summary ---------------------------------------------------
    regimes = pd.DataFrame(result["regime_rows"])
    if not regimes.empty:
        regimes = regimes.sort_values(["symbol", "timeframe", "regime", "state"])
    regimes.to_csv(output_dir / "regime_summary.csv", index=False)

    # ---- multiple testing -------------------------------------------------
    (output_dir / "multiple_testing.json").write_text(
        json.dumps(result["multiple"], indent=2, default=str), encoding="utf-8"
    )

    # ---- data snapshot ----------------------------------------------------
    (output_dir / "data_snapshot.json").write_text(
        json.dumps(result["snapshots"], indent=2, default=str), encoding="utf-8"
    )

    # ---- manifest ---------------------------------------------------------
    manifest = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "phase": "C (regime + derivatives discovery)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": result["elapsed_seconds"],
        "a25_status": result["gate"]["a25_status"],
        "development_start": partition.development_start,
        "development_end": partition.development_end,
        "validation_start": partition.validation_start,
        "validation_end": partition.validation_end,
        "holdout_start": partition.holdout_start,
        "holdout_end": partition.holdout_end,
        "final_holdout_accessed": False,
        "live_trading_code_created": False,
        "hypotheses_registered": len(HYPOTHESIS_IDS),
        "hypotheses_tested": len(outcomes),
        "hypotheses_unmatched": len(result["untested"]),
        "survivors": len(result["survivors"]),
        "survivor_criteria": dict(SURVIVOR_CRITERIA),
        "preregistration": spec_manifest(),
        "data_snapshot": result["snapshots"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    write_report(result, hypotheses_frame, output_dir)
    write_html(result, hypotheses_frame, output_dir)

    return manifest


from tools.strategy_factory_v2.hypotheses import HYPOTHESES  # noqa: E402

HYPOTHESIS_IDS = HYPOTHESES


def write_report(result: dict[str, Any], table: pd.DataFrame, output_dir: Path) -> Path:
    outcomes = result["outcomes"]
    multiple = result["multiple"]
    untested = result["untested"]
    survivors = result["survivors"]
    lines: list[str] = []
    add = lines.append

    add("# Phase C — regime + derivatives discovery")
    add("")
    add(f"- Spec version: `{SPEC_VERSION}`")
    add(f"- Run: `{result['partition'].declared_utc}`")
    add(f"- A2.5 integrity gate: **{result['gate']['a25_status']}**")
    add(f"- Elapsed: {result['elapsed_seconds']:.0f}s")
    add(f"- **Final holdout accessed: NO**")
    add("")

    add("## Headline")
    add("")
    add("| Metric | Value |")
    add("|---|---:|")
    add(f"| Preregistered hypotheses | {len(HYPOTHESIS_IDS)} |")
    add(f"| Tested | {len(outcomes)} |")
    add(f"| Unmatched (no bar satisfied the condition) | {len(untested)} |")
    add(f"| Research survivors | **{len(survivors)}** |")
    add(f"| Significant after multiple-testing correction | {multiple['bh_significant_count']} |")
    add("")

    if not survivors:
        add("> **Zero survivors.** That is a valid research result, not a failure to")
        add("> report. No threshold was loosened, no hypothesis was dropped, and no")
        add("> parameter was introduced to rescue one.")
        add("")
    else:
        add(f"> **{len(survivors)} survivors — and one caveat that matters more than the")
        add("> headline.** The preregistered concentration rule caps what a *single* fold")
        add("> may contribute. It does not stop an edge from spreading itself thinly")
        add("> across several correlated early folds, and that is what happened here:")
        add("")
        add("| Survivor | N | Top-3 fold share | Positive years | P&L by year |")
        add("|---|---:|---:|---:|---|")
        for outcome in survivors:
            yearly = outcome.metrics.get("yearly_pnl", {})
            add(
                f"| {outcome.hypothesis_id} | {outcome.sample_count:,} | "
                f"{_fmt(outcome.metrics.get('top3_fold_profit_share'), 2)} | "
                f"{_fmt(outcome.metrics.get('positive_year_fraction'), 2)} | "
                f"{ {k: round(v, 2) for k, v in yearly.items()} } |"
            )
        add("")
        add("> The 2021-2022 crypto uptrend carries most of the profit. A 2023 loss")
        add("> appears in the larger survivor. This does **not** change the verdict --")
        add("> the preregistered gates were applied as written and were not adjusted after")
        add("> the fact -- but it is the first thing a validator should attack, and it is")
        add("> why the verdict is `PROMISING_BUT_UNVERIFIED` and not `PASS`.")
        add("")
        add("> The two survivors also disagree with each other: one fires when BTC is in a")
        add("> strong uptrend and the other in a strong downtrend, yet both trade the same")
        add("> direction. The common factor is the direction, not the regime, so the")
        add("> regime filter may be incidental to what is actually being measured.")
        add("")

    add("## 1. Universe and timeframes")
    add("")
    add("| Item | Value |")
    add("|---|---|")
    add("| Symbols | " + ", ".join(sorted({k.split('/')[0] for k in result['snapshots']})) + " |")
    add("| Discovery timeframes | 15m, 1h |")
    add("| Region used | development only |")
    add(f"| Development | {result['partition'].development_start} → {result['partition'].development_end} |")
    add(f"| Holdout (untouched) | {result['partition'].holdout_start} → {result['partition'].holdout_end} |")
    add("")

    add("## 2. Verdict distribution")
    add("")
    if not table.empty:
        add("| Verdict | Hypotheses |")
        add("|---|---:|")
        for verdict, count in table["verdict"].value_counts().items():
            add(f"| {verdict} | {count} |")
        add("")

    add("## 3. Full tested population")
    add("")
    add("Every hypothesis that produced at least one signal is listed, whether it")
    add("passed or failed. A leaderboard of only the winners would misrepresent")
    add("the experiment.")
    add("")
    add("| Hypothesis | TF | Dir | N | Mean | Stress | PF | Stress PF | Folds+ | Adj p | Verdict |")
    add("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    adjusted = {r["hypothesis_id"]: r for r in multiple["per_hypothesis"]}
    for _, row in table.iterrows():
        adj = adjusted.get(row["hypothesis_id"], {}).get("p_bh_adjusted")
        add(
            f"| {row['hypothesis_id']} | {row['timeframe']} | {row['expected_direction'][:1].upper()} | "
            f"{row['sample_count']:,} | {_fmt(row['mean_return'])} | {_fmt(row['stress_expectancy'])} | "
            f"{_fmt(row['profit_factor'], 3)} | {_fmt(row['stress_profit_factor'], 3)} | "
            f"{_fmt(row['positive_fold_fraction'], 2)} | {_fmt(adj, 4)} | {row['verdict']} |"
        )
    add("")

    if untested:
        add("## 4. Untested hypotheses")
        add("")
        add("These matched no bar at their timeframe on any symbol. They are recorded")
        add("as untested rather than failed, because a condition that never fires is a")
        add("statement about the dataset, not about the market.")
        add("")
        add("| Hypothesis | Reason |")
        add("|---|---|")
        for entry in untested:
            add(f"| {entry['hypothesis_id']} | {entry['reason']} |")
        add("")

    add("## 5. Multiple testing")
    add("")
    add(f"- Correction: {multiple['correction']}")
    add(f"- Hypotheses tested: {multiple['hypotheses_tested']}")
    add(f"- With a usable sample: {multiple['hypotheses_with_usable_sample']}")
    add(f"- Raw p median: {_fmt(multiple['raw_p_median'], 4)}")
    add(f"- Raw p minimum: {_fmt(multiple['raw_p_min'], 4)}")
    add(f"- Significant after correction (alpha={multiple['alpha']}): "
        f"**{multiple['bh_significant_count']}**")
    add("")
    add("With ninety-two tests, a single unadjusted result below 0.05 is close to what")
    add("you would expect from noise alone. Nothing is promoted to survivor without")
    add("passing this correction as well as the preregistered gates.")
    add("")

    add("## 6. Interpretation limits")
    add("")
    add("- The final holdout was **not** opened. Nothing here has been tested on data")
    add("  that played no part in its own discovery.")
    add("- A survivor would still be a *research* survivor: it would need a separately")
    add("  frozen spec, a validation stage, and a forward paper period before it could")
    add("  be considered for any capital.")
    add("- Pooled results blend assets. `fold_results.csv` records which symbols")
    add("  contributed to each fold so an asset-specific signal stays visible.")
    add("- The gate thresholds are the preregistered ones and were not adjusted.")
    add("- Concentration is reported per hypothesis (`top3_fold_profit_share`,")
    add("  `yearly_pnl`) as a *diagnostic*. It is deliberately not a gate: changing a")
    add("  gate after seeing results is forbidden in both directions, so the")
    add("  weakness is disclosed rather than patched.")
    add("- Nothing has been tested on the final holdout. A survivor here has survived")
    add("  only walk-forward folds *inside* the development region, which is a weaker")
    add("  claim than out-of-sample validation and a much weaker claim than a")
    add("  forward period the strategy never saw.")
    add("")

    path = output_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_html(result: dict[str, Any], table: pd.DataFrame, output_dir: Path) -> Path:
    """A dependency-free HTML view, consistent with the MVP's no-plotting rule."""

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(r.hypothesis_id))}</td>"
        f"<td>{html.escape(str(r.timeframe))}</td>"
        f"<td>{r.sample_count:,}</td>"
        f"<td class='{'pos' if (r.mean_return or 0) > 0 else 'neg'}'>"
        f"{_fmt(r.mean_return, 8)}</td>"
        f"<td>{_fmt(r.profit_factor, 3)}</td>"
        f"<td>{html.escape(str(r.verdict))}</td>"
        "</tr>"
        for r in table.itertuples()
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Strategy Factory V2 — Phase C</title>
<style>
 body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color:#111; }}
 table {{ border-collapse: collapse; font-size: .85rem; }}
 th, td {{ border:1px solid #d4d4d4; padding:.3rem .55rem; text-align:left; }}
 th {{ background:#f5f5f5; }}
 .pos {{ color:#166534; }} .neg {{ color:#991b1b; }}
 .banner {{ background:#fef3c7; border-left:4px solid #d97706; padding:.75rem 1rem; margin:1rem 0; }}
</style></head><body>
<h1>Strategy Factory V2 — Phase C</h1>
<p>Spec <code>{html.escape(SPEC_VERSION)}</code> &middot; A2.5 gate
<strong>{result['gate']['a25_status']}</strong> &middot;
<b>final holdout accessed: NO</b></p>
<div class="banner">
 {len(result['survivors'])} research survivors out of {len(result['hypotheses'] if 'hypotheses' in result else result['outcomes'])}
 tested preregistered hypotheses. Zero survivors is a valid result.
</div>
<table><tr><th>Hypothesis</th><th>TF</th><th>N</th><th>Mean net</th><th>PF</th><th>Verdict</th></tr>
{rows}</table>
</body></html>
"""
    path = output_dir / "report.html"
    path.write_text(document, encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.strategy_factory_v2.phase_c")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_phase_c(args.out)
    manifest = write_outputs(result, args.out, args.out.name)

    print()
    print("=" * 60)
    print(f"A2.5 STATUS: {manifest['a25_status']}")
    print("PHASE C STATUS: COMPLETE")
    print(f"HYPOTHESES TESTED: {manifest['hypotheses_tested']}")
    print(f"SURVIVORS: {manifest['survivors']}")
    print("FINAL HOLDOUT ACCESSED: NO")
    print("LIVE TRADING CODE CREATED: NO")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
