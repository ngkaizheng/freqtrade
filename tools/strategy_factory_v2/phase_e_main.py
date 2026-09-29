"""Phase E -- the runner. Unseal, evaluate once, report, stop.

    python -m tools.strategy_factory_v2.phase_e_main --out <run-dir>

The order is the discipline: the protocol is written first, the holdout is
unsealed through the production lock second, and only then is a holdout row
read. The run cannot be repeated meaningfully, and the report says so.
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.discovery_engine import trade_metrics
from tools.strategy_factory_v2.freeze import freeze_candidates, verify_freeze
from tools.strategy_factory_v2.holdout import DataPartition, read_lock
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.phase_e import (
    CANDIDATE_IDS,
    HOLDOUT_MONTHS,
    HORIZON,
    MEANINGFUL_SAMPLE,
    REGIME_CLAIM,
    SYMBOLS,
    TIMEFRAME,
    _f,
    build_holdout_frames,
    build_protocol,
    classify_holdout,
    holdout_trades,
)
from tools.strategy_factory_v2.spec import SPEC_VERSION
from tools.strategy_factory_v2.uncertainty import uncertainty_report

UNSEAL_JUSTIFICATION = (
    "Phase E: the first and only final-holdout evaluation of two candidates frozen "
    "in Phase D. The protocol, including the interpretation categories, was written "
    "to disk before any holdout row was read."
)


def _load_partition() -> DataPartition:
    lock = read_lock()
    if not lock:
        raise SystemExit("no holdout lock file; the boundary must exist before Phase E")
    return DataPartition(**lock["partition"])


def _load_phase_d_evidence(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Validation-stage observation counts for each frozen candidate.

    Read from the Phase D artifact rather than recomputed, so the number that
    gates the holdout is the number Phase D actually reported. If the artifact
    is missing the run refuses to continue: an unverifiable candidate is not a
    verified one, and a holdout open is not repeatable.
    """

    candidates_dir = output_dir.parent
    if output_dir.name.startswith("phase-e"):
        candidates_dir = output_dir.parent
    artifact = candidates_dir / "phase-d-validation-20260926" / "validation_results.csv"
    if not artifact.exists():
        raise SystemExit(
            f"Phase D validation evidence not found at {artifact}; refusing to open "
            "the final holdout without knowing whether the candidates can answer it"
        )
    frame = pd.read_csv(artifact)
    if not {"candidate", "validation_n"}.issubset(frame.columns):
        raise SystemExit(
            f"{artifact} does not carry candidate/validation_n; cannot gate the holdout"
        )
    return {
        str(row["candidate"]): {
            "observations": int(row["validation_n"]),
            "replication_class": str(row.get("replication_class", "")),
        }
        for _, row in frame.iterrows()
    }


def run_phase_e(output_dir: Path, candidates: Sequence[str] = CANDIDATE_IDS) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    partition = _load_partition()

    # ---- 0. candidates must be able to answer before the holdout is spent ----
    evidence = _load_phase_d_evidence(output_dir)
    missing = [c for c in candidates if c not in evidence]
    if missing:
        raise SystemExit(
            f"no Phase D validation evidence for {missing}; refusing to open the "
            "final holdout"
        )
    try:
        H.assert_candidates_eligible(
            {c: evidence[c] for c in candidates}, MEANINGFUL_SAMPLE, stage="final holdout"
        )
    except H.HoldoutViolation as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"eligibility gate passed: {len(candidates)} candidate(s) at or above "
        f"{MEANINGFUL_SAMPLE} validation observations",
        flush=True,
    )

    # ---- 1. protocol, before any holdout row is read ---------------------
    protocol = build_protocol(candidates, partition, output_dir)
    print("protocol written (before any holdout row was read)", flush=True)

    # ---- 2. unseal through the production lock ---------------------------
    access_started = datetime.now(timezone.utc).isoformat()
    before = len((H.read_lock() or {}).get("access_log", []))
    partition = H.unseal(
        partition,
        justification=UNSEAL_JUSTIFICATION,
        spec_version=SPEC_VERSION,
        spec_path=output_dir / "final_holdout_protocol.json",
    )
    # Measured, not asserted. The count of holdout reads is whatever the
    # production lock has recorded, including reads made by runs that later
    # failed while writing their report -- the data was read either way, and a
    # count that excludes those would understate how many times the only
    # untested data in the project has been exposed.
    measured_access_count = len((H.read_lock() or {}).get("access_log", []))
    print(
        f"final holdout unsealed and recorded in the production lock "
        f"(lock entries {before} -> {measured_access_count})",
        flush=True,
    )

    # ---- 3. candidate logic must match the Phase D freeze -----------------
    frozen = {c["id"]: c for c in freeze_candidates(candidates)["candidates"]}
    drift = []
    for entry in protocol["candidates"]:
        current = frozen[entry["id"]]["logic_hash"]
        if current != entry["logic_hash"]:
            drift.append(entry["id"])
    if drift:
        raise SystemExit(f"candidate logic changed since the protocol was written: {drift}")

    # ---- 4. rebuild features over the holdout ----------------------------
    print("rebuilding features over the holdout (warm-up included)...", flush=True)
    frames, leakage = build_holdout_frames(partition, SYMBOLS)
    access_completed = datetime.now(timezone.utc).isoformat()
    rows_read = sum(int(len(f.frame)) for f in frames.values())
    warmup_rows = sum(int(f.frame["is_warmup"].sum()) for f in frames.values())
    print(
        f"  {rows_read:,} rows built ({warmup_rows:,} warm-up, excluded from counts); "
        f"leakage violations: {leakage['violations']}",
        flush=True,
    )

    results: list[dict[str, Any]] = []
    month_tables: list[pd.DataFrame] = []
    symbol_tables: list[pd.DataFrame] = []
    regime_tables: list[pd.DataFrame] = []
    uncertainty_rows: list[dict[str, Any]] = []

    for candidate_id in candidates:
        hypothesis = get(candidate_id)
        trades = holdout_trades(hypothesis, frames, partition.holdout_start)
        metrics = trade_metrics(trades["net_base"]) if not trades.empty else {"sample_count": 0}
        stress = trade_metrics(trades["net_stress"]) if not trades.empty else {}
        double = trade_metrics(trades["net_double"]) if not trades.empty else {}
        sample = int(metrics.get("sample_count", 0))
        expectancy = metrics.get("mean_return")
        stress_expectancy = stress.get("mean_return")

        # The established direction comes from the earlier, already-reported
        # evidence, not from anything computed here.
        established = ESTABLISHED_DIRECTION.get(candidate_id, "unknown")
        category, reason = classify_holdout(
            expectancy, stress_expectancy, established, sample
        )

        results.append(
            {
                "candidate": candidate_id,
                "logic_hash": next(
                    c["logic_hash"] for c in protocol["candidates"] if c["id"] == candidate_id
                ),
                "trade_count": sample,
                "mean_return": expectancy,
                "median_return": metrics.get("median_return"),
                "std_return": metrics.get("std_return"),
                "win_rate": metrics.get("win_rate"),
                "profit_factor": metrics.get("profit_factor"),
                "expectancy": expectancy,
                "stress_expectancy": stress_expectancy,
                "stress_profit_factor": stress.get("profit_factor"),
                "double_cost_expectancy": double.get("mean_return"),
                "max_drawdown": max_drawdown(trades["net_base"]) if not trades.empty else None,
                "sharpe": metrics.get("sharpe"),
                "sortino": metrics.get("sortino"),
                "mae": float(trades["mae"].mean()) if not trades.empty and trades["mae"].notna().any() else None,
                "mfe": float(trades["mfe"].mean()) if not trades.empty and trades["mfe"].notna().any() else None,
                "gross_pnl": float(trades["raw_return"].sum()) if not trades.empty else 0.0,
                "net_pnl": float(trades["net_base"].sum()) if not trades.empty else 0.0,
                "stress_net_pnl": float(trades["net_stress"].sum()) if not trades.empty else 0.0,
                "established_direction": established,
                "interpretation": category,
                "interpretation_reason": reason,
            }
        )

        uncertainty_rows.append(
            {
                "candidate": candidate_id,
                "region": "final_holdout",
                **uncertainty_report(
                    trades["net_base"].to_numpy() if not trades.empty else np.array([])
                ),
            }
        )

        month_tables.append(_month_table(trades, candidate_id))
        symbol_tables.append(_symbol_table(trades, candidate_id))
        regime_tables.append(_regime_table(trades, candidate_id))

        print(
            f"  {candidate_id}: N={sample:,} exp={_f(expectancy)} "
            f"stress={_f(stress_expectancy)} -> {category}",
            flush=True,
        )

    comparison = build_comparison(protocol, results)

    return {
        "partition": partition,
        "protocol": protocol,
        "results": pd.DataFrame(results),
        "months": pd.concat(month_tables, ignore_index=True),
        "symbols": pd.concat(symbol_tables, ignore_index=True),
        "regimes": pd.concat(regime_tables, ignore_index=True),
        "uncertainty": pd.DataFrame(uncertainty_rows),
        "comparison": comparison,
        "leakage": leakage,
        "access": {
            "holdout_access_started": access_started,
            "holdout_access_completed": access_completed,
            "rows_read": int(rows_read),
            "warmup_rows_excluded": int(warmup_rows),
            "symbols_read": list(SYMBOLS),
            "feature_sets_read": [
                "price_1h", "open_interest_5m", "funding_8h", "index_price_1h", "mark_price_1h"
            ],
            "final_holdout_access_count": int(measured_access_count),
            "previous_access_count": 0,
            "count_source": "production lock file access_log length after this run",
            "count_note": (
                "This counts every recorded read of the sealed region, including "
                "runs that later failed while assembling their report. The data was "
                "read in those runs too. A count that only tallied successful runs "
                "would understate how often the project's only untested data has "
                "been exposed."
            ),
            "unblinded": True,
            "statement": (
                "The final holdout has been read. It is no longer untouched data "
                "and no later analysis may describe it as such."
            ),
        },
    }


#: Directions established before the holdout was opened, carried forward.
ESTABLISHED_DIRECTION = {
    "H13_BTC_FILTER_1H_STRONG_UP_SHORT": "unknown",
    "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT": "positive",
}


def max_drawdown(returns: pd.Series) -> float | None:
    if returns is None or returns.empty:
        return None
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def _stats(group: pd.DataFrame) -> dict[str, Any]:
    if not len(group):
        return {
            "trade_count": 0, "pnl": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0,
            "mean_return": None, "expectancy": None, "profit_factor": None,
            "win_rate": None,
        }
    metrics = trade_metrics(group["net_base"])
    return {
        "trade_count": int(len(group)),
        "pnl": float(group["net_base"].sum()),
        "net_pnl": float(group["net_base"].sum()),
        "gross_pnl": float(group["raw_return"].sum()),
        "mean_return": metrics.get("mean_return"),
        "expectancy": metrics.get("mean_return"),
        "profit_factor": metrics.get("profit_factor"),
        "win_rate": metrics.get("win_rate"),
    }


def _month_table(trades: pd.DataFrame, candidate: str) -> pd.DataFrame:
    rows = []
    for month in HOLDOUT_MONTHS:
        group = trades[trades["month"] == month] if not trades.empty else trades
        rows.append({"candidate": candidate, "month": month, **_stats(group)})
    table = pd.DataFrame(rows)
    table["positive"] = table["pnl"] > 0
    table["negative"] = table["pnl"] < 0
    table["zero_signal"] = table["trade_count"] == 0
    return table


def _symbol_table(trades: pd.DataFrame, candidate: str) -> pd.DataFrame:
    rows = []
    for symbol in SYMBOLS:
        group = trades[trades["symbol"] == symbol] if not trades.empty else trades
        rows.append({"candidate": candidate, "symbol": symbol, **_stats(group)})
    table = pd.DataFrame(rows)
    total = float(table["pnl"].sum())
    table["pnl_share"] = (table["pnl"] / total) if total else np.nan
    return table


def _regime_table(trades: pd.DataFrame, candidate: str) -> pd.DataFrame:
    """The BTC reference state actually observed on each signal.

    Descriptive only: the buckets are whatever the reference regime produced,
    not buckets chosen after the fact.
    """

    if trades.empty:
        return pd.DataFrame(
            columns=["candidate", "btc_regime", "signal_count", "pnl", "expectancy", "profit_factor"]
        )
    rows = []
    for state, group in trades.groupby("btc_regime", sort=True):
        rows.append(
            {"candidate": candidate, "btc_regime": state, "signal_count": int(len(group)), **_stats(group)}
        )
    return pd.DataFrame(rows)


def build_comparison(protocol: dict[str, Any], results: list[dict[str, Any]]) -> pd.DataFrame:
    """The fixed four-region evidence progression, from the earlier runs."""

    earlier = _load_prior_evidence()
    rows = []
    for row in results:
        candidate = row["candidate"]
        history = earlier.get(candidate, {})
        for key in ("development_contiguous", "development_fold_restricted", "validation"):
            entry = history.get(key, {})
            rows.append({"candidate": candidate, "region": key, **entry})
        rows.append(
            {
                "candidate": candidate,
                "region": "final_holdout",
                "n": int(row["trade_count"]),
                "expectancy": row["expectancy"],
                "stress_expectancy": row["stress_expectancy"],
                "profit_factor": row["profit_factor"],
                "stress_profit_factor": row["stress_profit_factor"],
                "bootstrap_ci": "(see final_holdout_uncertainty.csv)",
            }
        )
    return pd.DataFrame(rows)


def _load_prior_evidence() -> dict[str, Any]:
    """Read the already-reported Phase C/D numbers. Nothing is recomputed here."""

    out: dict[str, Any] = {}
    phase_d = Path("user_data/strategy_factory_runs/v2/phase-d-validation-20260926/validation_results.csv")
    if phase_d.exists():
        frame = pd.read_csv(phase_d)
        for _, row in frame.iterrows():
            out.setdefault(row["candidate"], {})["validation"] = {
                "n": int(row["validation_n"]),
                "expectancy": row["validation_expectancy"],
                "stress_expectancy": row["validation_stress_expectancy"],
                "profit_factor": row["validation_pf"],
                "stress_profit_factor": row["validation_stress_pf"],
                "bootstrap_ci": "(see uncertainty_diagnostics.csv)",
            }
            # Phase D recomputed development contiguously; Phase C measured it
            # on walk-forward validation windows only. Both are reported,
            # neither is presented as the other.
            out[row["candidate"]]["development_contiguous"] = {
                "n": int(row["development_n"]),
                "expectancy": row["development_expectancy"],
                "stress_expectancy": row["development_stress_expectancy"],
                "profit_factor": row["development_pf"],
                "stress_profit_factor": row["development_stress_pf"],
                "bootstrap_ci": "(see uncertainty_diagnostics.csv)",
            }
    phase_c = Path("user_data/strategy_factory_runs/v2/20260926-phaseC/hypothesis_results.csv")
    if phase_c.exists():
        frame = pd.read_csv(phase_c)
        for _, row in frame.iterrows():
            entry = out.setdefault(row["hypothesis_id"], {}).setdefault("development_fold_restricted", {})
            if entry:
                continue
            entry.update(
                {
                    "n": int(row["sample_count"]),
                    "expectancy": row["mean_return"],
                    "stress_expectancy": row["stress_expectancy"],
                    "profit_factor": row["profit_factor"],
                    "stress_profit_factor": row["stress_profit_factor"],
                    "bootstrap_ci": "(not computed in Phase C)",
                }
            )
    return out



if __name__ == "__main__":
    raise SystemExit(main())
