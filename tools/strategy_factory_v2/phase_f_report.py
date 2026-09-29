"""Phase F -- report and entry point.

Every table this module writes is stamped ``POST_HOC_EXPLORATORY`` before it
leaves memory, and the report says the same thing in prose at the top. A number
that can travel out of this directory without its status attached to it is a
number that will eventually be quoted as evidence for a strategy.
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

from tools.strategy_factory_v2 import phase_f as F
from tools.strategy_factory_v2 import phase_f_main as M
from tools.strategy_factory_v2.phase_f_main import run_phase_f
from tools.strategy_factory_v2.spec import BASE_COST, DOUBLE_COST, SPEC_VERSION, STRESS_COST


#: The artifacts the plan requires, by name. Written in this order so the
#: directory listing a reader sees matches the plan.
REQUIRED_OUTPUTS = (
    "postmortem_report.md",
    "postmortem_report.html",
    "period_metrics.csv",
    "rolling_metrics.csv",
    "feature_distribution_drift.csv",
    "regime_frequency.csv",
    "signal_frequency.csv",
    "symbol_period_matrix.csv",
    "cost_decomposition.csv",
    "holding_horizon_diagnostics.csv",
    "dependence_diagnostics.csv",
    "regime_attribution_posthoc.csv",
    "manifest.json",
)

#: Additional artifacts, beyond the required list. A diagnostic a reader has to
#: reconstruct by hand is a diagnostic that will not be checked.
EXTRA_OUTPUTS = (
    "hypothesis_drift_assessment.csv",
    "candidate_conclusion.csv",
    "direction_convention_audit.csv",
    "holdout_access_log.json",
)

STATUS_BLOCK = (
    "POST_HOC\n"
    "EXPLORATORY\n"
    "NOT_FOR_CANDIDATE_SELECTION"
)


def _f(value: Any, digits: int = 5) -> str:
    return F._f(value, digits)


def _pct(value: Any, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "--"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "--"


def _n(value: Any) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "--"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "--"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_report(result: dict[str, Any], output_dir: Path) -> None:
    partition = result["partition"]
    summary = result["timeline_summary"]
    conclusion = result["conclusion"]
    primary = F.PRIMARY_CANDIDATE

    lines: list[str] = []
    add = lines.append

    add("# Phase F — Postmortem and Mechanism Audit")
    add("")
    add("```text")
    add(f"analysis_status          = {F.ANALYSIS_STATUS}")
    add(f"candidate_selection_allowed = {str(F.CANDIDATE_SELECTION_ALLOWED).lower()}")
    add(f"spec_version             = {SPEC_VERSION}")
    add("new_hypotheses           = 0")
    add("candidates_modified      = 0")
    add("optimization             = NO")
    add("```")
    add("")

    add("## What this phase is, and what it is not")
    add("")
    add("Phase E opened the final holdout and the candidate did not replicate. This")
    add("phase asks one question about that failure: **when did the relationship stop,")
    add("and did the inputs change?** It does not ask how to make the candidate work,")
    add("because a rule fitted to the failure would be fitted to the same data that")
    add("produced it.")
    add("")
    add("Everything below is therefore descriptive. Two statements that this report")
    add("deliberately never makes: that any input *caused* the result, and that any")
    add("observation here should become a new hypothesis. The audit stops where the")
    add("evidence stops.")
    add("")

    # ---- 1. evidence status ------------------------------------------------
    add("## 1. Evidence status")
    add("")
    add("The following region is permanently unblinded. It was opened in Phase E and")
    add("it can never again be described as untouched, unseen, unblinded, validation,")
    add("or holdout for any future candidate-selection purpose.")
    add("")
    add("```text")
    add(f"2025-11-18 23:00:00+00:00  ->  {partition.holdout_end}")
    add(f"unsealed at                :  {result['access']['unsealed_utc']}")
    add(f"unsealed by                :  {result['access']['unsealed_by_phase']}")
    add(f"new unseal event by Phase F:  {str(result['access']['new_unseal_event_written']).lower()}")
    add("```")
    add("")
    add(result["access"]["note"])
    add("")
    add("Every artifact in this directory carries the two status fields, and this")
    add("report is no exception:")
    add("")
    add("```text")
    add(f"analysis_status = {F.ANALYSIS_STATUS}")
    add(f"candidate_selection_allowed = {str(F.CANDIDATE_SELECTION_ALLOWED).lower()}")
    add("```")
    add("")

    # ---- 2. no rescue ------------------------------------------------------
    add("## 2. No strategy rescue")
    add("")
    add("Phase F modified **no** threshold, timeframe, holding period, symbol list, cost")
    add("model, filter or parameter, and created no H16, H17 or any other hypothesis.")
    add("This is checked mechanically, not promised: the run re-derives each")
    add("candidate's `logic_hash` — which covers its preregistered condition, its")
    add("thresholds and the source of the predicate that implements them — and")
    add("refuses to start if any hash differs from the one Phase D froze.")
    add("")
    add("| Candidate | logic_hash |")
    add("|---|---|")
    for candidate_id, digest in sorted(result["logic_hashes"].items()):
        add(f"| {candidate_id} | `{digest[:16]}…` |")
    add("")

    # ---- 2b. the defect this audit found -----------------------------------
    audit = result["direction_convention_audit"]
    add("## 2b. A defect in the measurement engine, found by this audit")
    add("")
    add("> **This is a defect report. It is not a result, and the mirrored numbers")
    add("> below are not a candidate.**")
    add("")
    add("Every evaluator in this package reads `fwd_ret_<h>`, which is a plain")
    add("forward price return, and charges costs through `net_return`. `net_return`")
    add("uses its `side` argument for exactly two things — which way the slippage")
    add("bites, and which way the funding cashflow is charged — and **never")
    add("multiplies the return by it**.")
    add("")
    add("So a hypothesis registered with `expected_direction = short` has been")
    add("measured on the **long** profit and loss of the asset it would have")
    add("shorted. The same is true in reverse for the long-labelled hypotheses: the")
    add("direction label in the registry is carried into the funding and slippage")
    add("convention, and then stops there.")
    add("")
    add("| Candidate | Registered direction | Period | N | As the engine wrote it | Mirrored |")
    add("|---|---|---|---:|---:|---:|")
    for _, row in audit.iterrows():
        add(
            f"| {row['candidate']} | {row['registered_direction']} | {row['period']} | "
            f"{_n(row['trade_count'])} | {_f(row['expectancy_under_the_engine_as_written'])} | "
            f"{_f(row['expectancy_under_the_mirrored_convention'])} |"
        )
    add("")
    add("Read for `H13_BTC_FILTER_1H_STRONG_DOWN_SHORT`: the short that \"worked\" in")
    add("development and validation lost money in both, and the short that \"failed\"")
    add("in the final holdout was roughly flat. The candidate did not fail to")
    add("replicate. **It was never measured in the direction it was registered in.**")
    add("")
    add("What this does and does not authorise:")
    add("")
    add("- It does **not** create a candidate. The mirrored column is a diagnostic")
    add("  with `is_candidate = false` and `promotion_allowed = false`.")
    add("- It does **not** license a fix here. Correcting `net_return` would change")
    add("  the measurement of every hypothesis in the registry, which invalidates")
    add("  the Phase C, D and E results retroactively. That is a new experiment with a")
    add("  new id, a new preregistration and a new frozen holdout — not a patch to")
    add("  this phase.")
    add("- It does **not** soften the Phase E conclusion. The project still has")
    add("  **0 research survivors**, and the reason is now worse than a failed")
    add("  replication.")
    add("")
    add("Every hypothesis in the 92-entry registry shares this defect, because every")
    add("evaluator shares this code path. The registry's direction labels are")
    add("meaningful for funding and slippage and are **not** reflected in the")
    add("measured returns.")
    add("")

    # ---- 3. failure timeline ----------------------------------------------
    add("## 3. Failure timeline")
    add("")
    add(f"A single continuous frame per symbol, stitched at the boundary the holdout")
    add(f"already established: {summary['development_rows']:,} development rows plus")
    add(f"{summary['holdout_rows']:,} holdout rows, {summary['warmup_rows_excluded']:,}")
    add(f"warm-up rows excluded, {summary['rows_without_complete_outcome']:,} rows")
    add("without a complete forward outcome. Both segments were built by the frozen")
    add("Phase C pipeline, so the holdout segment reproduces the Phase E numbers")
    add("rather than re-measuring them.")
    add("")
    add("### The three regions, side by side, never averaged")
    add("")
    add("| Candidate | Period | Start | End | N | Expectancy | Stress expectancy | PF | Stress PF |")
    add("|---|---|---|---|---:|---:|---:|---:|---:|")
    for _, row in conclusion.iterrows():
        add(
            f"| {row['candidate']} | {row['period']} | {row['period_start'][:10]} | "
            f"{row['period_end'][:10]} | {_n(row['trade_count'])} | "
            f"{_f(row['expectancy'])} | {_f(row['stress_expectancy'])} | "
            f"{_f(row['profit_factor'], 3)} | {_f(row['stress_profit_factor'], 3)} |"
        )
    add("")
    add("The three regions are shown as three results. They are not combined into a")
    add("single number, because no such number describes any period that existed.")
    add("")

    years = result["period_metrics"][
        (result["period_metrics"]["candidate"] == primary)
        & (result["period_metrics"]["bucket_type"] == "calendar_year")
    ]
    add(f"### Calendar years — {primary}")
    add("")
    add("| Year | N | Expectancy | Stress expectancy | PF | Stress PF | Net P&L |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for _, row in years.iterrows():
        add(
            f"| {int(row['bucket'])} | {_n(row['trade_count'])} | {_f(row['expectancy'])} | "
            f"{_f(row['stress_expectancy'])} | {_f(row['profit_factor'], 3)} | "
            f"{_f(row['stress_profit_factor'], 3)} | {_f(row['net_pnl'], 3)} |"
        )
    add("")
    add("Fixed calendar years, taken from the boundary dates. No breakpoint was")
    add("searched for: a researcher able to choose where the timeline splits will")
    add("always find a split at which the decay looks sharp, and that split will")
    add("carry no information.")
    add("")

    rolling = result["rolling_metrics"]
    add("### Rolling expectancy")
    add("")
    add(
        f"Fixed {rolling['window_days'].iloc[0]}-day windows on a "
        f"{rolling['step_days'].iloc[0]}-day step, declared in the module before any "
        "number was computed. The window is a reporting choice made from the"
    )
    add("calendar, not a fitted parameter.")
    add("")
    add("| Window start | Region | N | Expectancy | Stress expectancy | PF |")
    add("|---|---|---:|---:|---:|---:|")
    for _, row in rolling.iterrows():
        if int(row["trade_count"]) == 0:
            continue
        add(
            f"| {str(row['window_start'])[:10]} | {row['primary_region']} | "
            f"{_n(row['trade_count'])} | {_f(row['expectancy'])} | "
            f"{_f(row['stress_expectancy'])} | {_f(row['profit_factor'], 3)} |"
        )
    add("")
    add("Full table, including zero-signal windows, in `rolling_metrics.csv`.")
    add("")

    # ---- 4. distribution drift --------------------------------------------
    drift = result["feature_distribution_drift"]
    pooled = drift[
        (drift["symbol"] == "POOLED_ALTS")
        & (~drift["period"].astype(str).str.startswith("development_vs"))
    ]
    add("## 4. Input distribution drift")
    add("")
    add("The inputs H13 actually conditions on, and the derivatives features around")
    add("them, measured per period. A shift in a feature's distribution is a statement")
    add("about two samples. It is not evidence that the feature drove the result, and")
    add("this section does not infer causality from it.")
    add("")
    add("| Feature | Period | N | mean | median | std | p10 | p25 | p50 | p75 | p90 |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for feature, group in pooled.groupby("feature", sort=False):
        for _, row in group.iterrows():
            add(
                f"| {feature} | {row['period']} | {_n(row['count'])} | {_f(row['mean'])} | "
                f"{_f(row['median'])} | {_f(row['std'])} | {_f(row['p10'])} | {_f(row['p25'])} | "
                f"{_f(row['p50'])} | {_f(row['p75'])} | {_f(row['p90'])} |"
            )
    add("")
    add("### Distribution distance, development versus final holdout")
    add("")
    add("| Feature | Std. Wasserstein | KS distance |")
    add("|---|---:|---:|")
    distances = drift[
        (drift["period"] == "development_vs_final_holdout")
        & drift["standardized_wasserstein"].notna()
    ]
    for feature, group in distances.groupby("feature", sort=False):
        worst = group.loc[group["standardized_wasserstein"].idxmax()]
        ks = group["ks_distance"].max()
        add(
            f"| {feature} | {_f(worst['standardized_wasserstein'], 3)} ({worst['symbol']}) | "
            f"{_f(ks, 3)} |"
        )
    add("")
    add("The distance is expressed in units of the feature's own pooled standard")
    add("deviation, so a basis measured in fractions and an open interest measured in")
    add("contracts are comparable. Per-symbol rows are in `feature_distribution_drift.csv`.")
    add("")

    # ---- 5. regime frequency ----------------------------------------------
    regimes = result["regime_frequency"]
    add("## 5. BTC regime frequency drift")
    add("")
    add("Measured on the reference asset's own regime column, with the frozen")
    add("thresholds. No cut point was moved.")
    add("")
    add("| BTC state | " + " | ".join(F.REGION_ORDER) + " |")
    add("|---|" + "---:|" * len(F.REGION_ORDER))
    for state in F.TREND_STATES:
        cells = []
        for region in F.REGION_ORDER:
            row = regimes[(regimes["period"] == region) & (regimes["regime"] == state)]
            cells.append(_pct(row["bar_share"].iloc[0]) if len(row) else "--")
        add(f"| {state} | " + " | ".join(cells) + " |")
    add("")
    add("Share of reference-asset bars in each state, by region.")
    add("")
    add("| BTC state | Region | Bars | Mean run (bars) | Median run | Max run | Runs |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for _, row in regimes.iterrows():
        add(
            f"| {row['regime']} | {row['period']} | {_n(row['bars'])} | "
            f"{_f(row['mean_run_bars'], 1)} | {_f(row['median_run_bars'], 1)} | "
            f"{_n(row['max_run_bars'])} | {_n(row['run_count'])} |"
        )
    add("")
    strong_down = regimes[regimes["regime"] == "STRONG_DOWN"]
    shares = ", ".join(
        f"{row['period']} {_pct(row['bar_share'])}" for _, row in strong_down.iterrows()
    )
    add(f"STRONG_DOWN share by region: {shares}. Whether that share moved, and whether")
    add("it moved enough to matter for a candidate that only fires inside it, is the")
    add("question this section exists to answer.")
    add("")

    # ---- 6. signal frequency ----------------------------------------------
    signal_rate = result["signal_frequency"]
    pooled_signal = signal_rate[signal_rate["symbol"] == "POOLED"]
    add("## 6. Signal-frequency drift")
    add("")
    add(f"For `{primary}`. A fall in expectancy can come from the market paying less,")
    add("from the candidate firing more often on worse opportunities, or from its")
    add("signals bunching into blocks. These are different failures.")
    add("")
    add("| Period | Signals | Signals/month | Signals/week | Mean block | Median block | Max block | Blocks |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in pooled_signal.iterrows():
        add(
            f"| {row['period']} | {_n(row['period_signals'])} | "
            f"{_f(row['signals_per_month'], 2)} | {_f(row['signals_per_week'], 2)} | "
            f"{_f(row['mean_consecutive_length'], 2)} | "
            f"{_f(row['median_consecutive_length'], 2)} | "
            f"{_n(row['max_consecutive_length'])} | {_n(row['consecutive_block_count'])} |"
        )
    add("")
    add("Per-symbol rows are in `signal_frequency.csv`. Blocks are consecutive")
    add("`True` signal bars per symbol, on that symbol's own clock.")
    add("")

    # ---- 7. symbol x period ------------------------------------------------
    symbols = result["symbol_period_matrix"]
    add("## 7. Symbol-period decomposition")
    add("")
    add("The fixed 5 × 3 matrix. No symbol was excluded after the fact, reweighted, or")
    add("reordered.")
    add("")
    add("| Symbol | " + " | ".join(F.REGION_ORDER) + " |")
    add("|---|" + "---|" * len(F.REGION_ORDER))
    for symbol in F.SYMBOLS:
        cells = []
        for period in F.REGION_ORDER:
            row = symbols[(symbols["symbol"] == symbol) & (symbols["period"] == period)]
            if not len(row):
                cells.append("--")
                continue
            entry = row.iloc[0]
            if int(entry["trade_count"]) == 0:
                cells.append("0 signals")
            else:
                cells.append(
                    f"{_n(entry['trade_count'])} / {_f(entry['expectancy'])} / "
                    f"PF {_f(entry['profit_factor'], 2)}"
                )
        add(f"| {symbol} | " + " | ".join(cells) + " |")
    add("")
    add("Cells show `N / expectancy / PF`. The reference asset BTC cannot confirm")
    add("itself, so it contributes no signals to a cross-asset candidate; that is a")
    add("property of the definition, not a selection.")
    add("")

    # ---- 8. gross vs cost --------------------------------------------------
    costs = result["cost_decomposition"]
    add("## 8. Gross versus cost decomposition")
    add("")
    add(
        f"Frozen cost model only: `{BASE_COST.name}` "
        f"(fee {BASE_COST.fee_bps:.0f} bps, slippage {BASE_COST.slippage_bps:.0f} bps). "
        "No alternative cost was tested, and no cost was reduced to make a number "
        "look better."
    )
    add("")
    add("| Period | N | Raw | Gross | Fee | Slippage | Funding | Net |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in costs.iterrows():
        add(
            f"| {row['period']} | {_n(row['trade_count'])} | {_f(row['raw_expectancy'])} | "
            f"{_f(row['gross_expectancy'])} | {_f(row['fee_impact'])} | "
            f"{_f(row['slippage_impact'])} | {_f(row['funding_impact'])} | "
            f"{_f(row['net_expectancy'])} |"
        )
    add("")
    add("`raw` is the price move alone; `gross` is after slippage and before fees and")
    add("funding; `net` is the frozen net the candidate was measured with. The four")
    add("components are additive and the split is checked against the frozen engine's")
    add("own net return on every period, so this table is the same arithmetic, split.")
    add("")
    add("The question the table answers is narrow: did the holdout deteriorate because")
    add("the gross return fell, or because a cost component grew? Those have very")
    add("different implications, and only one of them is about the market paying less.")
    add("")

    # ---- 9. holding horizon -----------------------------------------------
    horizons = result["holding_horizon_diagnostics"]
    add("## 9. Holding-horizon diagnostic")
    add("")
    add("Only the horizons the research code already registers")
    add(f"(`{'`, `'.join(str(h) for h in horizons['horizon_bars'].unique())}` bars).")
    add("No new horizon was introduced, and the best-looking row here is not a")
    add("candidate and is not a recommendation.")
    add("")
    pivot = horizons.pivot_table(
        index="horizon_bars", columns="period", values="expectancy", aggfunc="first"
    )
    add("| Horizon (bars) | " + " | ".join(F.REGION_ORDER) + " |")
    add("|---|" + "---:|" * len(F.REGION_ORDER))
    for horizon in horizons["horizon_bars"].unique():
        cells = []
        for period in F.REGION_ORDER:
            value = pivot.loc[horizon, period] if period in pivot.columns else None
            cells.append(_f(value))
        add(f"| {int(horizon)} | " + " | ".join(cells) + " |")
    add("")
    add("Descriptive only. A horizon that looks better in one period than another is")
    add("not evidence that it is the right horizon; it is evidence that the sample")
    add("varies with the horizon, which is what a relationship that is not")
    add("horizon-specific looks like.")
    add("")
    agreement = M.HORIZON_SIGN_AGREEMENT["value"]
    if agreement is not None:
        add(
            f"Across those horizons, {_pct(agreement, 0)} of them kept the development "
            "sign in the final holdout. That number is a description of two columns "
            "in this table and nothing more: it is not a vote, not a p-value, and "
            "not a basis for choosing a horizon."
        )
        add("")

    # ---- 10. dependence ----------------------------------------------------
    dependence = result["dependence_diagnostics"]
    add("## 10. Dependence structure")
    add("")
    add("| Candidate | Period | N | Lag-1 autocorr | Integrated autocorr time | Effective N | Mean block | Max block |")
    add("|---|---|---:|---:|---:|---:|---:|---:|")
    for _, row in dependence.iterrows():
        add(
            f"| {row['candidate']} | {row['period']} | {_n(row['observations'])} | "
            f"{_f(row['lag1_autocorrelation'], 3)} | "
            f"{_f(row['integrated_autocorrelation_time'], 2)} | "
            f"{_f(row['effective_sample_size'], 1)} | "
            f"{_f(row['mean_block_length'], 1)} | {_n(row['max_block_length'])} |"
        )
    add("")
    add("The same dependence-aware method Phase D and Phase E used. Blocks are")
    add("signals within a holding horizon of one another, so they share their outcome")
    add("window and are not independent observations.")
    add("")

    # ---- 11. attribution ---------------------------------------------------
    attribution = result["regime_attribution_posthoc"]
    add("## 11. Regime-conditioned attribution")
    add("")
    add("| Period | Candidate N | Candidate exp. | Control N | Control exp. | Difference |")
    add("|---|---:|---:|---:|---:|---:|")
    for _, row in attribution.iterrows():
        add(
            f"| {row['period']} | {_n(row['candidate_signals'])} | "
            f"{_f(row['candidate_expectancy'])} | {_n(row['control_signals'])} | "
            f"{_f(row['control_expectancy'])} | {_f(row['difference'])} |"
        )
    add("")
    add("The control is the already-defined diagnostic one: the same bearish-trend")
    add("signal with the reference-asset regime clause removed, as defined in Phase D")
    add("and not modified here. The difference is an **association** between a")
    add("conditioning condition and a return. It is not a causal effect, the control")
    add("was not optimised, and a period in which the difference is negative is")
    add("reported with the same prominence as one where it is positive.")
    add("")

    # ---- 12. drift assessment ---------------------------------------------
    drift_table = result["hypothesis_drift_assessment"]
    add("## 12. Hypothesis drift assessment")
    add("")
    add("| Diagnostic | Development | Validation | Final holdout | Label | Interpretation |")
    add("|---|---:|---:|---:|---|---|")
    for _, row in drift_table.iterrows():
        add(
            f"| {row['diagnostic']} | {_f(row['development'])} | {_f(row['validation'])} | "
            f"{_f(row['final_holdout'])} | **{row['label']}** | {row['interpretation']} |"
        )
    add("")
    add("Labels come from fixed rules declared in `phase_f.py`:")
    add("")
    add(f"- `INSUFFICIENT_DATA` — fewer than {F.DRIFT_MIN_SAMPLE} observations in a region")
    add(f"- `DISAPPEARED` — the sign changed, or the value fell below "
        f"{F.DRIFT_DISAPPEARED_RATIO:.0%} of its development magnitude")
    add(f"- `DRIFTED` — a relative change above {F.DRIFT_RELATIVE_THRESHOLD:.0%}")
    add("- `AMBIGUOUS` — the development value is zero, so there is no magnitude to compare")
    add("- `STABLE` — none of the above")
    add("")
    add("These labels are **descriptive**. They are not scores, they are not ordered,")
    add("and nothing consumes them programmatically. In particular they do not")
    add("generate hypotheses: a `DISAPPEARED` row is a description of a difference,")
    add("not a specification for the next experiment.")
    add("")

    # ---- 13. conclusion ----------------------------------------------------
    add("## 13. Candidate conclusion")
    add("")
    add(f"`{primary}` preserves the result exactly as Phase E reported it:")
    add("")
    add("```text")
    add("development      : positive")
    add("validation       : positive")
    add("final holdout    : negative")
    add("```")
    add("")
    add("These three statements are not averaged, not reconciled, and not softened.")
    add("The holdout block-bootstrap interval crossed zero, so the accurate reading")
    add("of the holdout is *the previous positive effect failed to replicate, and the")
    add("holdout is compatible with no edge* — not that the holdout has statistically")
    add("proven a reverse edge.")
    add("")
    add("**Read section 2b first.** Those three statements are the engine's output,")
    add("and the engine measured every short-labelled hypothesis on the long side.")
    add("The record above is preserved exactly as Phase E wrote it; the defect is")
    add("reported alongside it, not folded into it.")
    add("")
    add("`H13_BTC_FILTER_1H_STRONG_UP_SHORT` remains `NO_MEANINGFUL_SAMPLE`: too few")
    add("holdout observations to support a replication statement in either direction.")
    add("That is not a failure verdict and is not re-stated as one here.")
    add("")
    add("**The project currently has 0 research survivors.**")
    add("")

    # ---- 14. artifacts -----------------------------------------------------
    add("## 14. Outputs")
    add("")
    add("```text")
    for name in REQUIRED_OUTPUTS + EXTRA_OUTPUTS:
        add(name)
    add("```")
    add("")
    add("Every CSV carries `analysis_status = POST_HOC_EXPLORATORY` and")
    add("`candidate_selection_allowed = false` as columns, so the status travels with")
    add("the numbers into whatever reads them next.")
    add("")

    # ---- 15. stop ----------------------------------------------------------
    add("## 15. Stop condition")
    add("")
    add("This phase ends here. No new hypothesis, no modified candidate, no")
    add("optimization, no Freqtrade strategy, no deployment, no order.")
    add("")
    add("The next experiment, if there is one, must carry a **new experiment id, a new")
    add("preregistration, and a newly frozen untouched holdout**. The project currently")
    add("holds no untouched data: the only region that ever had that status was opened")
    add("in Phase E. Any new holdout has to be built from data that arrives after")
    add("today, and frozen before anything is measured on it.")
    add("")

    (output_dir / "postmortem_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(result: dict[str, Any], output_dir: Path) -> None:
    conclusion = result["conclusion"]
    drift_table = result["hypothesis_drift_assessment"]

    conclusion_rows = "".join(
        f"<tr><td>{html.escape(str(r.candidate))}</td><td>{html.escape(str(r.period))}</td>"
        f"<td>{_n(r.trade_count)}</td><td>{_f(r.expectancy)}</td>"
        f"<td>{_f(r.stress_expectancy)}</td><td>{_f(r.profit_factor, 3)}</td></tr>"
        for r in conclusion.itertuples()
    )
    drift_rows = "".join(
        f"<tr><td>{html.escape(str(r.diagnostic))}</td><td>{_f(r.development)}</td>"
        f"<td>{_f(r.validation)}</td><td>{_f(r.final_holdout)}</td>"
        f"<td class=\"label\">{html.escape(str(r.label))}</td></tr>"
        for r in drift_table.itertuples()
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Phase F — Postmortem and Mechanism Audit</title>
<style>body{{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem;max-width:60rem}}
table{{border-collapse:collapse;font-size:.9rem;margin:1rem 0;width:100%}}
th,td{{border:1px solid #d4d4d4;padding:.35rem .6rem;text-align:left}}
th{{background:#f5f5f5}}.banner{{background:#fee2e2;border-left:4px solid #dc2626;
padding:.9rem 1rem;margin:1rem 0}}.status{{background:#fef3c7;border-left:4px solid #d97706;
padding:.9rem 1rem;margin:1rem 0}}.label{{font-weight:600}}
code{{background:#f3f4f6;padding:.1rem .3rem;border-radius:3px}}
</style></head><body>
<h1>Phase F — Postmortem and Mechanism Audit</h1>
<p>Spec <code>{html.escape(SPEC_VERSION)}</code> &middot; 0 new hypotheses &middot;
0 candidate modifications &middot; no optimization</p>

<div class="status"><b>POST_HOC / EXPLORATORY / NOT_FOR_CANDIDATE_SELECTION.</b>
<code>analysis_status = {html.escape(F.ANALYSIS_STATUS)}</code> &middot;
<code>candidate_selection_allowed = false</code>.
Every table in this report is descriptive. Nothing here establishes causation and
nothing here is a proposal for a new hypothesis.</div>

<div class="banner"><b>0 research survivors.</b> The final holdout was opened in Phase E
and did not replicate. The region is permanently unblinded and is not untouched data.</div>

<div class="banner"><b>Engine defect found by this audit.</b> <code>net_return</code> applies
<code>side</code> to slippage and to the funding clip but never multiplies the forward
return by it. A hypothesis registered <code>short</code> is therefore measured on the
<em>long</em> P&amp;L of the asset. This affects every hypothesis in the registry, is not
fixed here, and the mirrored figures it produces are <b>not a candidate</b>.</div>

<h2>Regions, side by side, never averaged</h2>
<table><tr><th>Candidate</th><th>Period</th><th>N</th><th>Expectancy</th>
<th>Stress</th><th>PF</th></tr>{conclusion_rows}</table>

<h2>Drift assessment</h2>
<table><tr><th>Diagnostic</th><th>Development</th><th>Validation</th>
<th>Final holdout</th><th>Label</th></tr>{drift_rows}</table>

<p>Labels are descriptive, not scores, and are not ordered. They do not generate
hypotheses.</p>
</body></html>
"""
    (output_dir / "postmortem_report.html").write_text(document, encoding="utf-8")


# ---------------------------------------------------------------------------
# Artifact writing
# ---------------------------------------------------------------------------


def _stamp(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None:
        return pd.DataFrame()
    return F.stamp(frame)


def write_outputs(result: dict[str, Any], output_dir: Path, run_id: str) -> dict[str, Any]:
    tables = {
        "period_metrics.csv": result["period_metrics"],
        "rolling_metrics.csv": result["rolling_metrics"],
        "feature_distribution_drift.csv": result["feature_distribution_drift"],
        "regime_frequency.csv": result["regime_frequency"],
        "signal_frequency.csv": result["signal_frequency"],
        "symbol_period_matrix.csv": result["symbol_period_matrix"],
        "cost_decomposition.csv": result["cost_decomposition"],
        "holding_horizon_diagnostics.csv": result["holding_horizon_diagnostics"],
        "dependence_diagnostics.csv": result["dependence_diagnostics"],
        "regime_attribution_posthoc.csv": result["regime_attribution_posthoc"],
        "hypothesis_drift_assessment.csv": result["hypothesis_drift_assessment"],
        "candidate_conclusion.csv": result["conclusion"],
        "direction_convention_audit.csv": result["direction_convention_audit"],
    }
    for name, frame in tables.items():
        _stamp(frame).to_csv(output_dir / name, index=False)

    (output_dir / "holdout_access_log.json").write_text(
        json.dumps(result["access"], indent=2, default=str), encoding="utf-8"
    )

    manifest = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "phase": "F (postmortem and mechanism audit)",
        "created_utc": result["created_utc"],
        "analysis_status": F.ANALYSIS_STATUS,
        "candidate_selection_allowed": F.CANDIDATE_SELECTION_ALLOWED,
        "post_hoc_labels": list(F.POST_HOC_LABELS),
        "purpose": (
            "Explain why a candidate that was positive in development and validation "
            "was negative in the final holdout. Diagnosis only."
        ),
        "prohibited_and_not_performed": {
            "candidate_modification": 0,
            "new_hypotheses": 0,
            "threshold_changes": 0,
            "timeframe_changes": 0,
            "holding_period_changes": 0,
            "symbol_selection": 0,
            "cost_reduction": 0,
            "optimization": False,
            "breakpoint_search": False,
            "freqtrade_strategy_generation": False,
            "deployment": False,
            "order_execution": False,
        },
        "candidates_audited": sorted(result["logic_hashes"]),
        "candidate_logic_hashes": result["logic_hashes"],
        "executed_source_hash": result["executed_source_hash"],
        "cost_model": {
            "decomposed": BASE_COST.as_dict(),
            "stress_reported": STRESS_COST.as_dict(),
            "double_reported": DOUBLE_COST.as_dict(),
            "alternative_costs_tested": 0,
        },
        "timeline": result["timeline_summary"],
        "evidence_status": {
            "final_holdout_start": result["partition"].holdout_start,
            "final_holdout_end": result["partition"].holdout_end,
            "already_unblinded": True,
            "unsealed_utc": result["access"]["unsealed_utc"],
            "new_unseal_event_written": result["access"]["new_unseal_event_written"],
            "may_be_described_as": "post-hoc diagnostic data only",
            "may_not_be_described_as": [
                "untouched", "unseen", "unblinded", "validation", "holdout",
            ],
            "for_candidate_selection": False,
        },
        "stop_condition": {
            "new_hypotheses": 0,
            "candidate_modifications": 0,
            "optimization": False,
            "next_experiment_requires": [
                "a new experiment id",
                "a new preregistration",
                "a newly frozen untouched holdout",
                "a corrected return-convention in net_return, since the fix "
                "invalidates every Phase C/D/E number retroactively",
            ],
        },
        "engine_defect_found": {
            "defect": (
                "net_return applies `side` to slippage and to the funding clip but "
                "never multiplies the forward return by it, so a hypothesis "
                "registered with expected_direction='short' is measured on the long "
                "profit and loss of the asset."
            ),
            "affects": "every hypothesis in the 92-entry registry",
            "detected_by": "Phase F (this run)",
            "fixed_here": False,
            "why_not_fixed_here": (
                "Correcting it would retroactively invalidate the Phase C, D and E "
                "results. That is a new experiment with a new id and a new "
                "preregistration, not a patch to a post-hoc audit."
            ),
            "mirrored_column_is_a_candidate": False,
        },
        "outputs": list(REQUIRED_OUTPUTS) + list(EXTRA_OUTPUTS),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    write_report(result, output_dir)
    write_html(result, output_dir)
    return manifest


def assert_outputs_complete(output_dir: Path) -> None:
    """Fail if a required artifact is missing.

    A phase that silently produces eleven of thirteen files reads as complete
    to anyone who skims the console output, and the two missing ones are
    usually the two nobody checked.
    """

    missing = [name for name in REQUIRED_OUTPUTS if not (output_dir / name).exists()]
    if missing:
        raise F.PhaseFViolation(
            f"Phase F did not write every required artifact; missing: {missing}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    default = Path(
        "user_data/strategy_factory_runs/v2/phase-f-postmortem-"
        + datetime.now(timezone.utc).strftime("%Y%m%d")
    )
    parser = argparse.ArgumentParser(prog="python -m tools.strategy_factory_v2.phase_f_main")
    parser.add_argument("--out", type=Path, default=default)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = run_phase_f(args.out)
    manifest = write_outputs(result, args.out, args.out.name)
    assert_outputs_complete(args.out)

    print()
    print("=" * 60)
    print("PHASE F STATUS: COMPLETE")
    print(f"POST_HOC ONLY: {'YES' if F.ANALYSIS_STATUS == 'POST_HOC_EXPLORATORY' else 'NO'}")
    print("NEW HYPOTHESES: 0")
    print("CANDIDATE MODIFICATIONS: 0")
    print("OPTIMIZATION: NO")
    print("=" * 60)
    print()
    print("The candidate conclusion is unchanged:")
    for _, row in result["conclusion"].iterrows():
        print(
            f"  {row['candidate']} / {row['period']}: N={int(row['trade_count']):,} "
            f"expectancy={_f(row['expectancy'])}"
        )
    print()
    print(f"Artifacts: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
