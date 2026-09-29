"""Phase D -- the engine: recompute, attribute, validate, classify.

The shape of this phase is deliberately narrow. Two candidates were found in
Phase C. They are frozen, recomputed through the same pipeline, measured on the
reserved validation region, and then dissected for stability. Nothing is
optimised, nothing is added, and the final holdout is never read.

Every number in the output is a *diagnostic* unless it is one of the frozen
Phase C metrics. That distinction is enforced by construction: this module
contains no threshold, and cannot promote, demote or re-rank a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.discovery import (
    DiscoveryFrame,
    build_discovery_frame,
    higher_timeframe_regime,
    with_regime,
    with_reference,
)
from tools.strategy_factory_v2.discovery_engine import (
    HORIZON_LABELS,
    REFERENCE_SYMBOL,
    in_window,
    make_folds,
    net_return,
    trade_metrics,
)
from tools.strategy_factory_v2.freeze import (
    HoldoutGuard,
    freeze_candidates,
    regime_control_mask,
    verify_freeze,
)
from tools.strategy_factory_v2.holdout import DataPartition
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.spec import (
    BASE_COST,
    DOUBLE_COST,
    SPEC_VERSION,
    STRESS_COST,
)

#: The holding horizon, in bars of the 1h candidate timeframe, fixed by the
#: Phase C protocol. Changing it would be a parameter scan.
HORIZON = 12
TIMEFRAME = "1h"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT")
#: Fixed calendar years, chosen before any Phase D number was computed.
DIAGNOSTIC_YEARS = (2021, 2022, 2023, 2024, 2025)

REPLICATED = "REPLICATED_SIGN"
OPPOSITE = "OPPOSITE_SIGN"
NO_SAMPLE = "NO_MEANINGFUL_SAMPLE"
#: A candidate whose validation sample is too small to say anything is not
#: thereby disproven; the two are reported as different verdicts on purpose.
MIN_VALIDATION_SAMPLE = 100


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------


def _side(hypothesis) -> int:
    return 1 if hypothesis.expected_direction == "long" else -1


def _attach_reference(frames: dict[str, DiscoveryFrame], region: str) -> None:
    """Attach the reference asset's regime to every other symbol.

    The cross-asset families are defined entirely in terms of the reference
    asset, so a frame without the reference column makes them vacuously false
    rather than wrong. That is a silent zero, which is the most dangerous kind
    of wrong answer a research pipeline can produce -- so the reference is
    attached in *every* region, and the absence of the column is separately
    asserted before any mask is evaluated.
    """

    reference = frames.get(REFERENCE_SYMBOL)
    if reference is None:
        return
    for symbol, frame in frames.items():
        if symbol == REFERENCE_SYMBOL:
            # A self-join is degenerate: the reference cannot confirm itself.
            for column in (
                "reference_trend_regime", "htf_trend_regime",
            ):
                frame.frame[column] = "UNKNOWN"
            frame.frame["relative_strength"] = np.nan
            frame.frame["pullback_depth"] = np.nan
            continue
        with_reference(frame, reference)
        try:
            frame.frame["htf_trend_regime"] = higher_timeframe_regime(
                symbol, TIMEFRAME, frame.partition, frame.frame["decision_time"]
            )
        except Exception:
            frame.frame["htf_trend_regime"] = "UNKNOWN"
        frame.frame = frame.frame.copy()


def build_frames(
    symbols: Sequence[str], timeframe: str, partition: DataPartition, region: str, guard: HoldoutGuard
) -> dict[str, DiscoveryFrame]:
    """Rebuild the frames through the Phase C pipeline, for one region."""

    frames: dict[str, DiscoveryFrame] = {}
    for symbol in symbols:
        frame = with_regime(build_discovery_frame(symbol, timeframe, partition, region))
        # The guard runs on every frame before any mask is evaluated. If the
        # frame has grown into the holdout, the run aborts here rather than
        # producing a clean-looking report.
        guard.assert_no_holdout(
            frame.frame, "date", context=f"{symbol}/{timeframe}/{region}"
        )
        frames[symbol] = frame
    _attach_reference(frames, region)
    return frames


def missing_inputs(hypothesis, frames: dict[str, DiscoveryFrame]) -> list[str]:
    """Feature columns a candidate needs that no frame provides.

    Reported rather than absorbed. A predicate that matches nothing because its
    inputs are absent looks exactly like a predicate that matched nothing
    because the market offered no opportunity, and the two must not be
    confused.
    """

    if not frames:
        return ["<no frames>"]
    reference = next(iter(frames.values())).frame
    needed = {
        "H1_trend_oi_confirmation": ("trend_regime", "oi_change_288"),
        "H2_trend_oi_divergence": ("trend_regime", "oi_change_288"),
        "H3_funding_extremes": ("funding_percentile", "funding_available"),
        "H4_funding_price_divergence": ("trend_regime", "funding_change"),
        "H5_funding_oi": ("funding_rate_last", "oi_change_288"),
        "H6_price_oi_taker": ("trend_regime", "taker_imbalance_percentile"),
        "H7_deleveraging_proxy": ("oi_change_288",),
        "H8_vol_compression_expansion": ("volatility_percentile", "range_ratio"),
        "H9_volatility_shock": ("volatility_percentile",),
        "H10_basis_extremes": ("basis_percentile", "basis_available"),
        "H11_cross_asset_confirmation": ("trend_regime", "reference_trend_regime"),
        "H12_cross_asset_divergence": ("trend_regime", "reference_trend_regime"),
        "H13_btc_regime_filter": ("trend_regime", "reference_trend_regime"),
        "H14_multi_timeframe_confirmation": ("trend_regime", "htf_trend_regime"),
        "H15_regime_specific_activation": ("trend_regime", "volatility_regime"),
    }.get(hypothesis.family, ())
    return sorted(name for name in needed if name not in reference.columns)


def candidate_returns(
    hypothesis,
    frames: dict[str, DiscoveryFrame],
    mask_override: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Per-signal base, stress and double-cost net returns, tagged by bar time.

    Returns a tidy frame with one row per signal so every downstream diagnostic
    -- year, month, symbol, fold -- is a groupby rather than a separate
    reimplementation that could drift from the numbers it is describing.
    """

    side = _side(hypothesis)
    column = f"fwd_ret_{HORIZON}"
    rows: list[pd.DataFrame] = []
    for symbol, discovery in frames.items():
        frame = discovery.frame
        mask = (
            mask_override[symbol]
            if mask_override is not None
            else evaluate(hypothesis, frame)
        )
        selected = frame.loc[mask.fillna(False)]
        if selected.empty:
            continue
        raw = pd.to_numeric(selected[column], errors="coerce")
        funding = pd.to_numeric(
            selected.get("funding_rate_last", pd.Series(0.0, index=selected.index)),
            errors="coerce",
        ).fillna(0.0)
        mae = pd.to_numeric(
            selected.get("mae_12", pd.Series(np.nan, index=selected.index)), errors="coerce"
        )
        mfe = pd.to_numeric(
            selected.get("mfe_12", pd.Series(np.nan, index=selected.index)), errors="coerce"
        )
        zero = pd.Series(0.0, index=selected.index)
        block = pd.DataFrame(
            {
                "symbol": symbol,
                "decision_time": pd.to_datetime(selected["decision_time"], utc=True),
                "raw_return": raw.to_numpy(),
                "funding_rate": funding.to_numpy(),
                "mae": mae.to_numpy(),
                "mfe": mfe.to_numpy(),
                "btc_regime": selected.get(
                    "reference_trend_regime", pd.Series("UNKNOWN", index=selected.index)
                ).astype(str).to_numpy(),
                "own_regime": selected["trend_regime"].astype(str).to_numpy(),
            }
        ).dropna(subset=["raw_return"])
        block["net_base"] = net_return(block["raw_return"], side, BASE_COST, HORIZON, block["funding_rate"]).to_numpy()
        block["net_stress"] = net_return(block["raw_return"], side, STRESS_COST, HORIZON, block["funding_rate"]).to_numpy()
        block["net_double"] = net_return(block["raw_return"], side, DOUBLE_COST, HORIZON, block["funding_rate"]).to_numpy()
        rows.append(block)
    if not rows:
        return pd.DataFrame(
            columns=[
                "symbol", "decision_time", "raw_return", "funding_rate", "mae", "mfe",
                "btc_regime", "own_regime", "net_base", "net_stress", "net_double",
            ]
        )
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Group diagnostics
# ---------------------------------------------------------------------------


def _stats(group: pd.DataFrame) -> dict[str, Any]:
    base = trade_metrics(group["net_base"])
    stress = trade_metrics(group["net_stress"])
    return {
        "trade_count": int(len(group)),
        "pnl": float(group["net_base"].sum()),
        "gross_pnl": float(group["raw_return"].sum()),
        "stress_pnl": float(group["net_stress"].sum()),
        "mean_return": base.get("mean_return"),
        "median_return": base.get("median_return"),
        "std_return": base.get("std_return"),
        "win_rate": base.get("win_rate"),
        "profit_factor": base.get("profit_factor"),
        "expectancy": base.get("mean_return"),
        "stress_expectancy": stress.get("mean_return"),
        "stress_profit_factor": stress.get("profit_factor"),
        "mae": float(group["mae"].mean()) if "mae" in group and group["mae"].notna().any() else None,
        "mfe": float(group["mfe"].mean()) if "mfe" in group and group["mfe"].notna().any() else None,
    }


_EMPTY_STATS: dict[str, Any] = {
    "trade_count": 0,
    "pnl": 0.0,
    "gross_pnl": 0.0,
    "stress_pnl": 0.0,
    "mean_return": None,
    "median_return": None,
    "std_return": None,
    "win_rate": None,
    "profit_factor": None,
    "expectancy": None,
    "stress_expectancy": None,
    "stress_profit_factor": None,
    "mae": None,
    "mfe": None,
}


def _stats_or_empty(group: pd.DataFrame) -> dict[str, Any]:
    """Statistics for a group, or a fully-shaped empty row.

    A group with no observations still has to occupy its column, so the empty
    case is spelled out rather than left to a ragged concat.
    """

    return _stats(group) if len(group) else dict(_EMPTY_STATS)


def by_year(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if trades.empty:
        return pd.DataFrame(), {}
    frame = trades.copy()
    frame["year"] = frame["decision_time"].dt.year
    frame = frame[frame["year"].isin(DIAGNOSTIC_YEARS)]
    rows = []
    for year in DIAGNOSTIC_YEARS:
        group = frame[frame["year"] == year]
        rows.append({"year": year, **_stats_or_empty(group)})
    table = pd.DataFrame(rows)
    total = float(table["pnl"].sum())
    table["pnl_share"] = (table["pnl"] / total) if total else np.nan
    early = float(table[table["year"].isin((2021, 2022))]["pnl"].sum())
    late = float(table[table["year"].isin((2023, 2024, 2025))]["pnl"].sum())
    positive = table[table["pnl"] > 0]
    negative = table[table["pnl"] < 0]
    summary = {
        "total_pnl": total,
        "year_2021_2022_pnl": early,
        "year_2023_2025_pnl": late,
        "share_2021_2022": (early / total) if total else None,
        "positive_year_count": int(len(positive)),
        "negative_year_count": int(len(negative)),
        "largest_positive_year": str(positive.loc[positive["pnl"].idxmax(), "year"]) if len(positive) else None,
        "largest_positive_year_share": (
            float(positive["pnl"].max() / total) if total and len(positive) else None
        ),
        "largest_negative_year": str(negative.loc[negative["pnl"].idxmin(), "year"]) if len(negative) else None,
        "largest_negative_year_pnl": float(negative["pnl"].min()) if len(negative) else None,
    }
    return table, summary


def by_symbol(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if trades.empty:
        return pd.DataFrame(), {}
    rows = []
    for symbol in sorted(trades["symbol"].unique()):
        group = trades[trades["symbol"] == symbol]
        rows.append({"symbol": symbol, **_stats(group)})
    table = pd.DataFrame(rows).sort_values("pnl", ascending=False)
    total = float(table["pnl"].sum())
    table["pnl_share"] = (table["pnl"] / total) if total else np.nan
    top = table.iloc[0] if len(table) else None
    return table, {
        "total_pnl": total,
        "largest_symbol_profit_share": float(top["pnl_share"]) if top is not None and total else None,
        "largest_symbol": str(top["symbol"]) if top is not None else None,
        "symbol_count": int(len(table)),
    }


def by_month(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["month"] = frame["decision_time"].dt.strftime("%Y-%m")
    rows = [{"month": month, **_stats(group)} for month, group in frame.groupby("month", sort=True)]
    return pd.DataFrame(rows)


def by_fold(trades: pd.DataFrame, folds: Sequence[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    if trades.empty:
        return pd.DataFrame(), {}
    rows = []
    for fold in folds:
        window = (trades["decision_time"] >= fold["validation_start"]) & (
            trades["decision_time"] < fold["validation_end"]
        )
        group = trades[window]
        rows.append(
            {
                "fold_id": fold["fold_id"],
                "validation_start": str(fold["validation_start"]),
                "validation_end": str(fold["validation_end"]),
                **_stats_or_empty(group),
            }
        )
    table = pd.DataFrame(rows)
    valid = table[table["trade_count"] > 0]
    profits = valid["pnl"].to_numpy(dtype=float)
    total = float(profits.sum()) if len(profits) else 0.0
    ordered = np.sort(profits)[::-1] if len(profits) else np.array([])
    summary = {
        "folds_evaluated": int(len(valid)),
        "top1_fold_profit_share": float(ordered[0] / total) if total and len(ordered) else None,
        "top3_fold_profit_share": float(ordered[:3].sum() / total) if total and len(ordered) else None,
        "bottom_fold_pnl": float(profits.min()) if len(profits) else None,
        "median_fold_pnl": float(np.median(profits)) if len(profits) else None,
        "positive_fold_count": int((profits > 0).sum()) if len(profits) else 0,
    }
    return table, summary


# ---------------------------------------------------------------------------
# Replication classification
# ---------------------------------------------------------------------------


def classify_replication(
    development_expectancy: float | None,
    validation_expectancy: float | None,
    validation_n: int,
) -> str:
    """Descriptive classification. Not a gate, and not a winner score."""

    if validation_n < MIN_VALIDATION_SAMPLE or validation_expectancy is None:
        return NO_SAMPLE
    if not np.isfinite(validation_expectancy) or validation_expectancy == 0:
        return NO_SAMPLE
    if development_expectancy is None or not np.isfinite(development_expectancy):
        return NO_SAMPLE
    if np.sign(validation_expectancy) == np.sign(development_expectancy):
        return REPLICATED
    return OPPOSITE
