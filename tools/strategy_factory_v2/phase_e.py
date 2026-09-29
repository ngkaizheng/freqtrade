"""Phase E -- the final holdout evaluation.

One reading, once, of the only data the project has that played no part in
choosing anything. The design is arranged so that the temptation to look twice
is not merely discouraged but structurally awkward: the protocol -- including
the interpretation categories -- is written to disk before a single holdout row
is read, and the holdout is unsealed through the production lock so the
authoritative record says it happened.

Warm-up is the one subtlety worth stating plainly. The regime engine needs
288 bars before its percentiles mean anything, so the holdout frame is built
from 90 days *before* the boundary. Those rows are development data, every
feature is trailing, and the warm-up rows are flagged and excluded from every
count. Without them the first twelve days of a nine-month holdout would be
scored on regimes that had not formed yet, which would manufacture a negative
result rather than measure one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.discovery import (
    HOLDOUT_WARMUP_DAYS,
    DiscoveryFrame,
    build_discovery_frame,
    higher_timeframe_regime,
    with_regime,
    with_reference,
)
from tools.strategy_factory_v2.discovery_engine import (
    REFERENCE_SYMBOL,
    net_return,
    trade_metrics,
)
from tools.strategy_factory_v2.freeze import logic_hash
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.hypotheses import get
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.joins import future_leakage_violations
from tools.strategy_factory_v2.spec import (
    BASE_COST,
    DOUBLE_COST,
    SPEC_VERSION,
    STRESS_COST,
)
from tools.strategy_factory_v2.uncertainty import uncertainty_report

CANDIDATE_IDS = (
    "H13_BTC_FILTER_1H_STRONG_UP_SHORT",
    "H13_BTC_FILTER_1H_STRONG_DOWN_SHORT",
)
HORIZON = 12
TIMEFRAME = "1h"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")

#: Fixed calendar months of the holdout. Chosen from the boundary, not from
#: the data: the holdout runs 2025-11-18 to 2026-08-31, so these are the ten
#: months it touches.
HOLDOUT_MONTHS = (
    "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
    "2026-04", "2026-05", "2026-06", "2026-07", "2026-08",
)

#: A replication statement needs a sample. Fixed here, in the protocol file,
#: before any holdout row is read.
MEANINGFUL_SAMPLE = 100

#: The interpretation categories, defined in the protocol before results exist.
INTERPRETATION_CATEGORIES = {
    "POSITIVE_REPLICATION": (
        "Holdout expectancy shares the sign of the established development and "
        "validation direction, at base and at stress cost, with a meaningful sample."
    ),
    "NEGATIVE_REPLICATION": (
        "Holdout expectancy has the opposite sign from the established "
        "development/validation direction, with a meaningful sample."
    ),
    "NO_MEANINGFUL_SAMPLE": (
        "Too few holdout observations to support a replication statement. This is "
        "not a failure verdict: a candidate that did not fire has not been shown "
        "anything, in either direction."
    ),
    "MIXED": (
        "The directional result is not consistent across cost models, calendar "
        "months, symbols or BTC reference states."
    ),
}

#: The language the Phase D report established about the regime filter. Carried
#: forward verbatim: a conditioned subset with higher returns is a correlation
#: between a condition and a return, not proof that the condition causes it.
REGIME_CLAIM = (
    "The regime-conditioned subset showed higher conditional returns than the "
    "unfiltered control. That is an association between a conditioning condition "
    "and a return. It is not proof that the filter causes the return, and no "
    "stronger claim is made here."
)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


def build_protocol(
    candidates: Sequence[str], partition: DataPartition, output_dir: Path
) -> dict[str, Any]:
    """Write the interpretation contract before any holdout row is read."""

    from tools.strategy_factory_v2.freeze import source_hash

    package = Path("tools/strategy_factory_v2")
    protocol = {
        "spec_version": SPEC_VERSION,
        "phase": "E (final holdout evaluation)",
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "written_before_any_holdout_row_was_read": True,
        "candidates": [
            {
                "id": candidate_id,
                "logic_hash": logic_hash(get(candidate_id)),
                "thresholds": get(candidate_id).thresholds,
                "condition": get(candidate_id).condition,
                "timeframe": get(candidate_id).timeframe,
                "expected_direction": get(candidate_id).expected_direction,
            }
            for candidate_id in candidates
        ],
        "candidate_logic_source_hash": source_hash(
            [
                package / "hypothesis_eval.py",
                package / "features.py",
                package / "regime.py",
                package / "discovery.py",
                package / "discovery_engine.py",
                package / "joins.py",
                package / "spec.py",
            ]
        ),
        "data_boundary": {
            "final_holdout_start": partition.holdout_start,
            "final_holdout_end": partition.holdout_end,
            "latest_complete_day": partition.latest_complete_day,
            "immutable": True,
            "note": (
                "The holdout ends at the latest complete price day established by "
                "A2. It is neither extended nor shortened after results are seen, "
                "and no data outside it is inspected."
            ),
        },
        "timeframe": TIMEFRAME,
        "holding_horizon_bars": HORIZON,
        "warmup_days": HOLDOUT_WARMUP_DAYS,
        "warmup_policy": (
            "Frames are built from warmup_days before the boundary so trailing "
            "windows and regime percentiles are defined. Those rows are "
            "development data, every feature is trailing, and the rows are flagged "
            "and excluded from all counts."
        ),
        "metrics": [
            "trade_count", "mean_return", "median_return", "win_rate",
            "profit_factor", "expectancy", "stress_expectancy",
            "stress_profit_factor", "max_drawdown", "sharpe", "sortino",
            "MAE", "MFE", "gross_pnl", "net_pnl",
        ],
        "cost_assumptions": {
            "base": BASE_COST.as_dict(),
            "stress": STRESS_COST.as_dict(),
            "double": DOUBLE_COST.as_dict(),
            "tuned_after_results": False,
        },
        "funding_assumptions": {
            "payer": "adverse only",
            "credits": "ignored",
            "source": "observed settlement events only",
            "rate": "no forward fill",
        },
        "leverage": 1.0,
        "interpretation_procedure": {
            "categories": INTERPRETATION_CATEGORIES,
            "meaningful_sample_minimum": MEANINGFUL_SAMPLE,
            "rule": (
                "Classification compares the holdout sign against the established "
                "development and validation direction at BOTH base and stress cost. "
                "A sign that flips between cost models, or that is carried by a "
                "single month or a single symbol while the rest are negative, is "
                "MIXED rather than replicated."
            ),
            "no_new_threshold": (
                "No PF, Sharpe, expectancy or win-rate threshold is introduced. The "
                "Phase C survivor gates were discovery gates and are not re-applied "
                "or re-weighted here. The holdout answers one question: does the "
                "frozen candidate reproduce its previously observed behaviour in "
                "completely untouched data?"
            ),
            "prohibited_claims": [
                "proves the strategy works",
                "guarantees profitability",
                "ready for live trading",
                "will make money",
                "is a winning strategy",
            ],
        },
        "regime_claim": REGIME_CLAIM,
        "forbidden": [
            "optimization", "retuning", "new hypotheses", "candidate modification",
            "new controls", "new regime definitions", "new thresholds",
            "new holding periods", "new timeframes", "new symbols",
            "Freqtrade strategy generation", "deployment", "order execution",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final_holdout_protocol.json").write_text(
        json.dumps(protocol, indent=2, default=str), encoding="utf-8"
    )
    return protocol


# ---------------------------------------------------------------------------
# Frame construction
# ---------------------------------------------------------------------------


def _attach_reference(frames: dict[str, DiscoveryFrame], partition: DataPartition) -> None:
    reference = frames.get(REFERENCE_SYMBOL)
    if reference is None:
        return
    for symbol, frame in frames.items():
        if symbol == REFERENCE_SYMBOL:
            frame.frame["reference_trend_regime"] = "UNKNOWN"
            frame.frame["htf_trend_regime"] = "UNKNOWN"
            frame.frame["relative_strength"] = np.nan
            frame.frame["pullback_depth"] = np.nan
            continue
        with_reference(frame, reference)
        try:
            frame.frame["htf_trend_regime"] = higher_timeframe_regime(
                symbol, TIMEFRAME, partition, frame.frame["decision_time"]
            )
        except Exception:
            frame.frame["htf_trend_regime"] = "UNKNOWN"
        frame.frame = frame.frame.copy()


def build_holdout_frames(
    partition: DataPartition,
    symbols: Sequence[str] = SYMBOLS,
) -> tuple[dict[str, DiscoveryFrame], dict[str, Any]]:
    """Rebuild the frozen pipeline over the final holdout, warm-up included."""

    frames: dict[str, DiscoveryFrame] = {}
    for symbol in symbols:
        frames[symbol] = with_regime(
            build_discovery_frame(symbol, TIMEFRAME, partition, "final_holdout")
        )
    _attach_reference(frames, partition)

    leakage: dict[str, Any] = {"checks": [], "violations": 0, "rows_checked": 0}
    for symbol, frame in frames.items():
        for column in ("oi_source_timestamp", "funding_source_timestamp", "index_source_timestamp"):
            if column not in frame.frame.columns:
                continue
            present = frame.frame[column].notna()
            age_column = column.replace("_source_timestamp", "_age_seconds")
            if age_column not in frame.frame.columns:
                continue
            ages = frame.frame.loc[present, age_column]
            violations = int((ages < 0).sum())
            leakage["rows_checked"] += int(present.sum())
            leakage["violations"] += violations
            leakage["checks"].append(
                {
                    "symbol": symbol,
                    "column": column,
                    "attached_rows": int(present.sum()),
                    "negative_age_rows": violations,
                    "max_age_seconds": float(ages.max()) if len(ages) else None,
                }
            )
    return frames, leakage


def holdout_trades(
    hypothesis, frames: dict[str, DiscoveryFrame], holdout_start: str
) -> pd.DataFrame:
    """Per-signal net returns, restricted strictly to the holdout window.

    Warm-up rows carry ``is_warmup = True`` and are dropped here, so no bar
    before the boundary can contribute an observation.
    """

    side = 1 if hypothesis.expected_direction == "long" else -1
    column = f"fwd_ret_{HORIZON}"
    boundary = pd.Timestamp(holdout_start)
    rows: list[pd.DataFrame] = []
    for symbol, discovery in frames.items():
        frame = discovery.frame
        if column not in frame.columns:
            continue
        eligible = frame["decision_time"] >= boundary
        if "is_warmup" in frame.columns:
            eligible = eligible & ~frame["is_warmup"].astype(bool)
        mask = evaluate(hypothesis, frame) & eligible
        selected = frame.loc[mask]
        if selected.empty:
            continue
        raw = pd.to_numeric(selected[column], errors="coerce")
        funding = pd.to_numeric(
            selected.get("funding_rate_last", pd.Series(0.0, index=selected.index)),
            errors="coerce",
        ).fillna(0.0)
        block = pd.DataFrame(
            {
                "symbol": symbol,
                "decision_time": pd.to_datetime(selected["decision_time"], utc=True),
                "raw_return": raw.to_numpy(),
                "funding_rate": funding.to_numpy(),
                "mae": pd.to_numeric(
                    selected.get("mae_12", pd.Series(np.nan, index=selected.index)),
                    errors="coerce",
                ).to_numpy(),
                "mfe": pd.to_numeric(
                    selected.get("mfe_12", pd.Series(np.nan, index=selected.index)),
                    errors="coerce",
                ).to_numpy(),
                "btc_regime": selected.get(
                    "reference_trend_regime", pd.Series("UNKNOWN", index=selected.index)
                ).astype(str).to_numpy(),
                "own_regime": selected["trend_regime"].astype(str).to_numpy(),
            }
        ).dropna(subset=["raw_return"])
        if block.empty:
            continue
        block["net_base"] = net_return(
            block["raw_return"], side, BASE_COST, HORIZON, block["funding_rate"]
        ).to_numpy()
        block["net_stress"] = net_return(
            block["raw_return"], side, STRESS_COST, HORIZON, block["funding_rate"]
        ).to_numpy()
        block["net_double"] = net_return(
            block["raw_return"], side, DOUBLE_COST, HORIZON, block["funding_rate"]
        ).to_numpy()
        block["month"] = block["decision_time"].dt.strftime("%Y-%m")
        rows.append(block)
    columns = [
        "symbol", "decision_time", "raw_return", "funding_rate", "mae", "mfe",
        "btc_regime", "own_regime", "net_base", "net_stress", "net_double", "month",
    ]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=columns)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_holdout(
    holdout_expectancy: float | None,
    holdout_stress_expectancy: float | None,
    established_direction: str,
    sample: int,
) -> tuple[str, str]:
    """Return ``(category, reason)`` using the categories frozen in the protocol."""

    if sample < MEANINGFUL_SAMPLE or holdout_expectancy is None:
        return (
            "NO_MEANINGFUL_SAMPLE",
            f"{sample} holdout observations is below the {MEANINGFUL_SAMPLE} "
            "required for a replication statement",
        )
    if established_direction not in ("positive", "negative"):
        return (
            "NO_MEANINGFUL_SAMPLE",
            "no established development/validation direction to replicate",
        )
    base_sign = np.sign(holdout_expectancy)
    stress_sign = np.sign(holdout_stress_expectancy) if holdout_stress_expectancy is not None else base_sign
    if base_sign != stress_sign:
        return (
            "MIXED",
            "the sign differs between the base and stress cost models",
        )
    if base_sign == 0:
        return ("MIXED", "holdout expectancy is exactly zero")
    # The label describes the holdout sign, as the protocol defines it. Whether
    # that agrees with the earlier evidence is carried in the reason text, so a
    # negative holdout is never dressed up as a replication.
    label = "POSITIVE_REPLICATION" if base_sign > 0 else "NEGATIVE_REPLICATION"
    agrees = (base_sign > 0) == (established_direction == "positive")
    return (
        label,
        f"holdout expectancy {_f(holdout_expectancy)} is "
        + (
            f"positive, matching the established {established_direction} direction"
            if agrees
            else f"negative, opposing the established {established_direction} direction"
        )
        + " at base and stress cost",
    )


def _f(value: Any, digits: int = 5) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "--"
    if isinstance(value, (int, np.integer)):
        return str(value)
    return f"{float(value):+.{digits}f}"
