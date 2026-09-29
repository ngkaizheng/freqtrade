"""Phase C -- regime and derivatives discovery on development data only.

The pipeline is deliberately linear and each stage writes something the next
one cannot rewrite:

1. build the causal discovery frame, per symbol and discovery timeframe
2. evaluate all 92 preregistered hypotheses on that frame
3. measure conditional forward returns against the unconditional baseline
4. charge costs and funding to produce a net per-signal return series
5. run the preregistered walk-forward folds
6. deflate for the number of trials tested, and apply the survivor gates

Nothing here selects a winner. A hypothesis becomes a survivor only by passing
every gate in ``spec.SURVIVOR_CRITERIA``, and zero survivors is a complete,
valid result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np
import pandas as pd

from tools.strategy_factory_v2.discovery import (
    FORWARD_HORIZON_BARS,
    DiscoveryFrame,
    build_discovery_frame,
    higher_timeframe_regime,
    with_regime,
    with_reference,
)
from tools.strategy_factory_v2.features import baseline_distribution
from tools.strategy_factory_v2.hypotheses import HYPOTHESES, Hypothesis
from tools.strategy_factory_v2.hypothesis_eval import evaluate
from tools.strategy_factory_v2.spec import (
    BASE_COST,
    DOUBLE_COST,
    MIN_OOS_TRADES,
    MIN_POSITIVE_FOLD_FRACTION,
    MIN_TOTAL_OBSERVATIONS,
    SPEC_VERSION,
    STATISTICS_V2,
    STRESS_COST,
    SURVIVOR_CRITERIA,
    WALK_FORWARD_V2,
    WALK_FORWARD_V2,
)

REFERENCE_SYMBOL = "BTCUSDT"
HORIZON_LABELS = {1: "5m-ish", 3: "15m-ish", 6: "30m-ish", 12: "1h-ish", 24: "4h-ish"}


# ---------------------------------------------------------------------------
# Cost and funding
# ---------------------------------------------------------------------------


def net_return(
    raw_return: pd.Series,
    side: int,
    cost,
    holding_bars: int,
    funding_cashflow: pd.Series,
) -> pd.Series:
    """Per-signal net return after adverse costs and adverse-payer funding.

    Slippage and fee are charged on both sides, multiplicatively adverse.

    ``funding_cashflow`` is the funding *rate* for the signal, and the
    adverse-payer convention is enforced here rather than at the call site. A
    long pays when the rate is positive and a short pays when it is negative,
    so the charge is ``max(0, side * rate)``; the negative half is discarded
    rather than paid out. An earlier version trusted the caller to do this
    clip, which meant a caller that passed a credit could quietly turn the
    conservative convention into an optimistic one. A convention that depends
    on every caller remembering it is not a convention.
    """

    fee = float(cost.fee_bps) / 10_000.0
    slippage = float(cost.slippage_bps) / 10_000.0
    entry = 1.0 + side * slippage
    exit_ = 1.0 - side * slippage
    with np.errstate(divide="ignore", invalid="ignore"):
        gross = (1.0 + raw_return) / entry - 1.0
        gross = (1.0 + gross) * exit_ - 1.0
    rate = funding_cashflow.to_numpy(dtype=float)
    charge = np.maximum(0.0, side * np.nan_to_num(rate))
    net = gross - 2.0 * fee - charge
    return pd.Series(net, index=raw_return.index)


def funding_cashflow_for_window(
    events: pd.DataFrame, side: int, start: pd.Timestamp, end: pd.Timestamp
) -> float:
    """Adverse-payer funding charged over a holding window.

    Conservative by construction: a position only pays when it is the payer, so
    ``side * rate`` is clipped at zero. A negative rate can therefore never
    become a credit.
    """

    if events is None or len(events) == 0:
        return 0.0
    window = events[
        (events["settlement_time"] >= start) & (events["settlement_time"] < end)
    ]
    if window.empty:
        return 0.0
    return float(np.maximum(0.0, side * window["funding_rate"].to_numpy(dtype=float)).sum())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def trade_metrics(returns: pd.Series) -> dict[str, Any]:
    """Per-signal metrics. Every figure is reported, not just the good ones."""

    values = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    count = int(len(values))
    if count == 0:
        return {"sample_count": 0, "status": "INSUFFICIENT_SAMPLE"}
    gains = values[values > 0]
    losses = values[values < 0]
    total = float(losses.abs().sum())
    daily = values  # per-signal; annualised statistics use the fold aggregation
    mean = float(values.mean())
    std = float(values.std(ddof=1)) if count > 1 else np.nan
    return {
        "sample_count": count,
        "status": "OK" if count >= MIN_TOTAL_OBSERVATIONS else "INSUFFICIENT_SAMPLE",
        "mean_return": mean,
        "median_return": float(values.median()),
        "std_return": std,
        "win_rate": float((values > 0).mean()),
        "profit_factor": float(gains.sum() / total) if total > 0 else np.inf,
        "expectancy": mean,
        "volatility": std,
        # Per-trade Sharpe / Sortino. These are NOT annualised: a per-signal
        # return series has no natural annual horizon, and the constant that
        # used to be applied here was hard-coded to sqrt(365*24*60/15) = 187.19
        # for every timeframe, which inflated a 1h hypothesis's Sharpe by ~2x
        # and made the reported numbers uninterpretable. Multiplying by a
        # 15m-period annualisation factor is not meaningful for 1h or 4h
        # signals, and the two stages used it identically, so it did not cause
        # the 22x disagreement -- but it made every reported Sharpe wrong.
        "sharpe": (mean / std) if std and np.isfinite(std) and std > 0 else np.nan,
        "sortino": (
            mean / float(np.sqrt(np.mean(np.square(np.minimum(values.to_numpy(), 0.0)))))
            if count > 1 and np.any(values < 0)
            else np.nan
        ),
        "sharpe_annualisation": "none applied; per-signal returns have no annual horizon",
        "skew": float(values.skew()) if count > 2 else np.nan,
        "kurtosis": float(values.kurtosis()) + 3.0 if count > 3 else np.nan,
    }


def conditional_report(
    frame: pd.DataFrame, hypothesis: Hypothesis, mask: pd.Series
) -> list[dict[str, Any]]:
    """Conditional forward returns per horizon, against the unconditional baseline.

    A positive conditional mean is not a finding on its own; it has to be an
    improvement on what the same symbol and horizon delivers with no condition
    at all. Both are reported, and the lift is what the reader judges.
    """

    rows: list[dict[str, Any]] = []
    for horizon in FORWARD_HORIZON_BARS:
        column = f"fwd_ret_{horizon}"
        if column not in frame.columns:
            continue
        returns = pd.to_numeric(frame[column], errors="coerce")
        conditional = returns[mask.fillna(False)]
        unconditional = returns
        base = baseline_distribution(unconditional)
        stats = trade_metrics(conditional)
        mean = stats.get("mean_return")
        rows.append(
            {
                "hypothesis_id": hypothesis.hypothesis_id,
                "family": hypothesis.family,
                "timeframe": hypothesis.timeframe,
                "expected_direction": hypothesis.expected_direction,
                "horizon_bars": horizon,
                "horizon_label": HORIZON_LABELS.get(horizon, f"{horizon} bars"),
                "signal_bars": int(mask.fillna(False).sum()),
                "sample_count": stats.get("sample_count", 0),
                "conditional_mean": mean,
                "conditional_median": stats.get("median_return"),
                "conditional_std": stats.get("std_return"),
                "conditional_win_rate": stats.get("win_rate"),
                "baseline_mean": base.get("mean"),
                "baseline_median": base.get("median"),
                "baseline_std": base.get("std"),
                "baseline_count": base.get("count"),
                "lift_vs_baseline": (
                    None
                    if mean is None or base.get("mean") is None
                    else float(mean) - float(base["mean"])
                ),
                "status": stats.get("status"),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Walk-forward folds
# ---------------------------------------------------------------------------


def make_folds(frame: pd.DataFrame, config=WALK_FORWARD_V2) -> list[dict[str, Any]]:
    """Rolling folds inside the development region.

    Folds are cut on the *decision* clock and each carries an embargo before
    its validation window, so a feature computed at the end of training cannot
    be the same observation that validates it.
    """

    start = pd.Timestamp(frame["decision_time"].min())
    end = pd.Timestamp(frame["decision_time"].max())
    folds: list[dict[str, Any]] = []
    validation_start = start + pd.Timedelta(days=config.train_days)
    fold_id = 0
    while validation_start < end:
        train_start = validation_start - pd.Timedelta(days=config.train_days)
        validation_end = validation_start + pd.Timedelta(days=config.validation_days)
        if train_start >= start and validation_end <= end:
            folds.append(
                {
                    "fold_id": fold_id,
                    "train_start": train_start,
                    "train_end": validation_start - pd.Timedelta(hours=config.embargo_hours),
                    "validation_start": validation_start,
                    "validation_end": validation_end,
                }
            )
            fold_id += 1
        validation_start += pd.Timedelta(days=config.step_days)
    return folds


def in_window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    times = pd.to_datetime(frame["decision_time"], utc=True)
    return (times >= start) & (times < end)


# ---------------------------------------------------------------------------
# Per-hypothesis evaluation
# ---------------------------------------------------------------------------


@dataclass
class HypothesisOutcome:
    hypothesis_id: str
    family: str
    timeframe: str
    expected_direction: str
    sample_count: int
    fold_rows: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    gates: dict[str, bool] = field(default_factory=dict)
    survivor: bool = False
    verdict: str = "FAIL"
    #: The pooled per-signal net return series, at BASE_COST. Kept because
    #: significance cannot be computed honestly without it: the observations
    #: overlap in time, so a naive t-statistic treats correlated duplicates as
    #: independent evidence. ``phase_c.multiple_testing_analysis`` needs this
    #: series to compute the integrated autocorrelation time.
    net_returns: pd.Series | None = None



def evaluate_hypothesis(
    hypothesis: Hypothesis,
    frames: dict[str, pd.DataFrame],
    horizon: int = 12,
) -> HypothesisOutcome:
    """Evaluate one hypothesis across the walk-forward folds, pooling assets.

    Assets are pooled rather than averaged so the trade count stays honest:
    five assets contributing twenty signals each is not the same evidence as one
    asset contributing twenty, and the survivor gate is written on counts. Folds
    are cut on a common decision clock so every asset is measured over the same
    windows, and each fold records which symbols contributed to it -- a signal
    that only fires on one asset must be visible as such rather than blended
    into an aggregate.
    """

    side = 1 if hypothesis.expected_direction == "long" else -1
    return_column = f"fwd_ret_{horizon}"

    if not frames:
        return HypothesisOutcome(
            hypothesis_id=hypothesis.hypothesis_id,
            family=hypothesis.family,
            timeframe=hypothesis.timeframe,
            expected_direction=hypothesis.expected_direction,
            sample_count=0,
            verdict="INSUFFICIENT_SAMPLE",
        )

    reference_frame = next(iter(frames.values()))
    folds = make_folds(reference_frame)

    # Signals the predicate matches but that fall outside every walk-forward
    # validation window are excluded from the headline statistics. That is
    # correct -- the first ``train_days`` are burned as training -- but it was
    # silent, and silence here is what produced a 22x disagreement between two
    # stages measuring the same thing. The discarded count and its own P&L are
    # now recorded so the exclusion can be seen rather than inferred.
    full_parts: list[pd.Series] = []
    for symbol, frame in frames.items():
        if return_column not in frame.columns:
            continue
        mask = evaluate(hypothesis, frame)
        matched = mask.fillna(False)
        if not bool(matched.any()):
            continue
        returns = pd.to_numeric(frame.loc[matched, return_column], errors="coerce").dropna()
        if returns.empty:
            continue
        funding = frame.get("funding_rate_last")
        cashflow = pd.Series(0.0, index=returns.index)
        if funding is not None:
            cashflow = pd.to_numeric(funding.loc[returns.index], errors="coerce").fillna(0.0)
        full_parts.append(net_return(returns, side, BASE_COST, horizon, cashflow))
    full_series = pd.concat(full_parts) if full_parts else pd.Series(dtype=float)

    fold_rows: list[dict[str, Any]] = []
    pooled: list[pd.Series] = []
    stress_pooled: list[pd.Series] = []
    double_pooled: list[pd.Series] = []

    for fold in folds:
        base_parts: list[pd.Series] = []
        stress_parts: list[pd.Series] = []
        double_parts: list[pd.Series] = []
        contributors: list[str] = []
        for symbol, frame in frames.items():
            if return_column not in frame.columns:
                continue
            mask = evaluate(hypothesis, frame)
            selected = in_window(frame, fold["validation_start"], fold["validation_end"]) & mask.fillna(False)
            if not bool(selected.any()):
                continue
            returns = pd.to_numeric(frame.loc[selected, return_column], errors="coerce").dropna()
            if returns.empty:
                continue
            funding = frame.get("funding_rate_last")
            cashflow = pd.Series(0.0, index=returns.index)
            if funding is not None:
                rates = pd.to_numeric(funding.loc[returns.index], errors="coerce").fillna(0.0)
                # Signed rate; net_return applies the adverse-payer clip.
                cashflow = rates
            base_parts.append(net_return(returns, side, BASE_COST, horizon, cashflow))
            stress_parts.append(net_return(returns, side, STRESS_COST, horizon, cashflow))
            double_parts.append(net_return(returns, side, DOUBLE_COST, horizon, cashflow))
            contributors.append(symbol)

        if not base_parts:
            fold_rows.append(
                {**{k: str(v) for k, v in fold.items()}, "trades": 0,
                 "expectancy": None, "symbols": []}
            )
            continue

        base = pd.concat(base_parts)
        stress = pd.concat(stress_parts)
        double = pd.concat(double_parts)
        pooled.append(base)
        stress_pooled.append(stress)
        double_pooled.append(double)
        stats = trade_metrics(base)
        stress_stats = trade_metrics(stress)
        fold_rows.append(
            {
                **{k: str(v) for k, v in fold.items()},
                "symbols": ",".join(contributors),
                "trades": stats["sample_count"],
                "expectancy": stats.get("mean_return"),
                "profit_factor": stats.get("profit_factor"),
                "stress_expectancy": stress_stats.get("mean_return"),
                "stress_profit_factor": stress_stats.get("profit_factor"),
                "double_cost_expectancy": trade_metrics(double).get("mean_return"),
                "win_rate": stats.get("win_rate"),
            }
        )

    metrics = trade_metrics(pd.concat(pooled) if pooled else pd.Series(dtype=float))
    stress_metrics = trade_metrics(
        pd.concat(stress_pooled) if stress_pooled else pd.Series(dtype=float)
    )
    double_metrics = trade_metrics(
        pd.concat(double_pooled) if double_pooled else pd.Series(dtype=float)
    )
    sample = int(metrics.get("sample_count", 0))

    valid_folds = [r for r in fold_rows if r.get("trades", 0) > 0]
    # The preregistered gate is "positive expectancy in >=60% of OOS folds".
    # The denominator is every fold, not the folds that happened to trade: a
    # fold in which the rule never fired is evidence that it did not fire, and
    # dropping empty folds from both numerator and denominator is the choice
    # that makes the gate pass. Measured: H13_BTC_FILTER_1H_STRONG_UP_SHORT
    # scored 11/15 = 0.733 this way and 11/19 = 0.579 over all folds, which is
    # below the 0.60 minimum.
    positive_folds = [r for r in fold_rows if (r.get("expectancy") or 0) > 0]
    positive_fraction = len(positive_folds) / len(fold_rows) if fold_rows else 0.0
    empty_folds = len(fold_rows) - len(valid_folds)

    # No single fold may dominate: a result that lives on one lucky window is
    # not a result.
    profits = np.array(
        [r.get("expectancy", 0.0) * r.get("trades", 0) for r in valid_folds], dtype=float
    )
    if profits.sum() > 0:
        share = float(profits.max() / profits.sum())
    else:
        share = 1.0 if len(profits) else 0.0

    # DIAGNOSTIC, NOT A GATE. The preregistered rule caps a *single* fold's
    # contribution, and an edge can satisfy that neatly by spreading itself
    # thinly across several correlated early folds -- 2021 and 2022 in
    # particular, when crypto was in a violent uptrend. Reporting the top-three
    # share and the per-year split makes that visible without changing a
    # threshold after the fact. Loosening *or* tightening a gate once results
    # are in view is exactly what the preregistration forbids, in both
    # directions; a diagnostic is the honest alternative.
    ordered_profits = np.sort(profits)[::-1]
    top3_share = (
        float(ordered_profits[:3].sum() / profits.sum()) if profits.sum() > 0 else 1.0
    )
    yearly: dict[str, float] = {}
    for row in valid_folds:
        year = str(row.get("validation_start", ""))[:4]
        yearly[year] = yearly.get(year, 0.0) + (row.get("expectancy") or 0.0) * row.get("trades", 0)
    year_series = pd.Series(yearly).sort_index() if yearly else pd.Series(dtype=float)
    year_positive_fraction = (
        float((year_series > 0).mean()) if len(year_series) else 0.0
    )

    gates = {
        "oos_expectancy_positive": bool((metrics.get("mean_return") or 0) > 0),
        "stress_expectancy_positive": bool((stress_metrics.get("mean_return") or 0) > 0),
        "double_cost_expectancy_positive": bool((double_metrics.get("mean_return") or 0) > 0),
        "min_base_profit_factor": bool(
            (metrics.get("profit_factor") or 0) > SURVIVOR_CRITERIA["min_base_profit_factor"]
        ),
        "min_stress_profit_factor": bool(
            (stress_metrics.get("profit_factor") or 0)
            > SURVIVOR_CRITERIA["min_stress_profit_factor"]
        ),
        "min_oos_observations": sample >= MIN_OOS_TRADES,
        "min_positive_fold_fraction": positive_fraction >= MIN_POSITIVE_FOLD_FRACTION,
        "max_single_fold_profit_share": share <= SURVIVOR_CRITERIA["max_single_fold_profit_share"],
        "enough_folds": len(folds) >= WALK_FORWARD_V2.min_folds,
    }
    survivor = all(gates.values())

    if sample < MIN_OOS_TRADES:
        verdict = "INSUFFICIENT_SAMPLE"
    elif survivor:
        verdict = "PROMISING_BUT_UNVERIFIED"
    else:
        verdict = "FAIL"

    return HypothesisOutcome(
        hypothesis_id=hypothesis.hypothesis_id,
        family=hypothesis.family,
        timeframe=hypothesis.timeframe,
        expected_direction=hypothesis.expected_direction,
        sample_count=sample,
        net_returns=pd.concat(pooled) if pooled else None,
        fold_rows=fold_rows,
        metrics={
            **metrics,
            "stress": stress_metrics,
            "double_cost": double_metrics,
            "double_cost_expectancy": double_metrics.get("mean_return"),
            # What the fold filter removed, recorded rather than discarded.
            # For H13_BTC_FILTER_1H_STRONG_UP_SHORT this was 540 of 994 signals
            # carrying -0.0048 each, which is the whole of the 22x gap between
            # the screening stage and the validation stage.
            "matched_signals_total": int(len(full_series)),
            "in_fold_signals": int(sample),
            "out_of_fold_signals": int(max(0, len(full_series) - sample)),
            "out_of_fold_fraction": (
                round(max(0, len(full_series) - sample) / len(full_series), 4)
                if len(full_series) else None
            ),
            "out_of_fold_expectancy": (
                round(float(full_series.mean()), 8) if len(full_series) else None
            ),
            "in_fold_expectancy": metrics.get("mean_return"),
            "positive_fold_fraction": positive_fraction,
            "max_single_fold_profit_share": share,
            "top3_fold_profit_share": top3_share,
            "yearly_pnl": {str(k): round(float(v), 6) for k, v in year_series.items()},
            "positive_year_fraction": year_positive_fraction,
            "folds_evaluated": len(valid_folds),
            "folds_total": len(fold_rows),
            "folds_without_signals": empty_folds,
        },
        gates=gates,
        survivor=survivor,
        verdict=verdict,
    )