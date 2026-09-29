"""Frozen V2 research constants.

Nothing in this module may be edited after V2 results are inspected. Every
value here is *preregistered*: it is chosen from economic reasoning or from a
standard statistical convention, never from a result.

The values are transcribed from ``PREREGISTRATION_V2.md``. That document is the
human-readable contract; this module is its single machine-readable mirror. If
the two ever disagree, that is a bug -- fix the module to match the document and
bump ``SPEC_VERSION``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.strategy_factory.models import CostScenario


# Bumping this invalidates every previously written V2 run directory.
SPEC_VERSION = "2026-09-26-v2-regime-derivatives"

#: The MVP must remain reproducible; V2 never writes outside its own namespace.
V2_RUN_ROOT = "user_data/strategy_factory_runs/v2"
V1_RUN_ROOT = "user_data/strategy_factory_runs/full-mvp-20260925"

#: V1 components are imported read-only for reuse (never modified).
V1_REUSED_COMPONENTS = (
    "tools.strategy_factory.data.as_utc",
    "tools.strategy_factory.models.CostScenario",
)


# --------------------------------------------------------------------------
# Timeframes (plan section 38)
# --------------------------------------------------------------------------

#: Primary alpha-discovery timeframes.
PRIMARY_TIMEFRAMES = ("5m", "15m", "1h")
#: Optional timeframes; only used when the underlying data exists.
OPTIONAL_TIMEFRAMES = ("30m", "4h")
#: 1m is reserved for execution simulation, never for alpha discovery.
EXECUTION_TIMEFRAME = "1m"

#: The preregistered cross-product is screened on these two timeframes only.
#:
#: Why not 5m: a 5m bar closes exactly on the 00:00/08:00/16:00 funding
#: settlements, so a 5m grid aliases the funding event stream. Screening on an
#: aliased grid produces regime statistics that are an artifact of the clock.
#: 5m is kept as a *confirmation* timeframe: the full cross-product is screened
#: on DISCOVERY_TIMEFRAMES, and 5m is evaluated afterwards for survivors only.
#: Fixing this before results exist is the whole point -- a timeframe axis that
#: is trimmed after seeing results would be exactly the overfitting the plan
#: forbids.
DISCOVERY_TIMEFRAMES = ("15m", "1h")

#: Evaluated for survivors, not for the full cross-product.
CONFIRMATION_TIMEFRAMES = ("5m",)

TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "8h": 480,
    "1d": 1440,
    "1w": 10080,
}

#: Forward-return horizons measured in bars, per plan section 19.
FORWARD_HORIZONS_BARS = (1, 3, 6, 12, 24, 48, 96, 288)


# --------------------------------------------------------------------------
# Feature windows (plan sections 8, 9, 12) -- preregistered, never optimised
# --------------------------------------------------------------------------

#: Trailing windows, expressed in BARS of the feature's own timeframe.
RETURN_WINDOWS = (1, 3, 6, 12, 24, 48)
ATR_PERIODS = (14, 30, 60)
REALIZED_VOL_WINDOWS = (30, 60, 120)
EMA_PERIODS = (20, 50, 100, 200)
OI_WINDOWS = (30, 60, 120, 288)
TAKER_FLOW_WINDOWS = (5, 15, 30, 60)
VWAP_WINDOW = 48
ROLLING_HIGH_LOW_WINDOW = 48
RANGE_WINDOW = 48
#: Minimum bars before a rolling feature is considered valid at all.
MIN_WARMUP_BARS = 288


# --------------------------------------------------------------------------
# Percentile thresholds (plan sections 14, 16, 17, 27)
# --------------------------------------------------------------------------

#: Volatility regime cut-points on the trailing volatility percentile.
VOL_PERCENTILE_CUTS = (20.0, 80.0, 95.0)
#: Positioning (open interest) regime cut-points.
OI_PERCENTILE_CUTS = (20.0, 80.0, 95.0)
#: Funding regime cut-points.
FUNDING_PERCENTILE_CUTS = (5.0, 25.0, 75.0, 95.0)
#: Liquidity regime cut-points on trailing volume percentile.
LIQUIDITY_PERCENTILE_CUTS = (20.0, 80.0)
#: The only preregistered magnitude thresholds for taker imbalance (section 27).
TAKER_IMBALANCE_CUTS = (10.0, 20.0)
#: Trailing window used to build every percentile/z-score feature. Long enough to
#: be stable, short enough to track regime drift.
PERCENTILE_WINDOW = 288
#: Window used for expanding-style "history to date" funding statistics.
EXPANDING_MIN_EVENTS = 30

#: Trend regime cut-points, in units of the normalised trend score.
#:
#: The trend is classified on the *absolute* normalised score rather than on a
#: trailing percentile of it, and that is a deliberate departure from the other
#: four regimes. The score is already dimensionless -- it is a volatility-
#: normalised blend of the 24-bar move and the 50/200 moving-average spread --
#: so absolute cuts are meaningful and comparable across symbols without any
#: per-symbol calibration.
#:
#: A trailing percentile would actively misclassify a sustained trend. A trend
#: that is slowly but persistently rising makes its own recent history look
#: ordinary, so it spends most of its life near the 50th percentile of its own
#: tail and the classifier calls a raging bull market NEUTRAL. Measured on
#: real BTC data, a market whose score averaged +3.3 standard deviations was
#: labelled bullish on only 29% of bars. Percentiles are the right tool for
#: raw-unit quantities (open interest, funding, volume) where cross-symbol
#: comparability is the goal; they are the wrong tool for a quantity that is
#: already normalised.
TREND_SCORE_CUTS = (-1.0, -0.25, 0.25, 1.0)


# --------------------------------------------------------------------------
# Cost model (plan section 41) -- costs are never tuned to make a pass
# --------------------------------------------------------------------------


BASE_COST = CostScenario(name="base_taker", fee_bps=5.0, slippage_bps=1.0)
STRESS_COST = CostScenario(name="stress_taker", fee_bps=10.0, slippage_bps=3.0)
#: Robustness check required by plan section 53: 2x the base scenario.
DOUBLE_COST = CostScenario(
    name="double_base",
    fee_bps=BASE_COST.fee_bps * 2,
    slippage_bps=BASE_COST.slippage_bps * 2,
)
COST_SCENARIOS = (BASE_COST, STRESS_COST, DOUBLE_COST)

#: Research defaults to 1x. Leverage must never manufacture a return.
RESEARCH_LEVERAGE = 1.0

#: Funding is charged only at observed events, adverse payer only (section 42).
FUNDING_POLICY = {
    "apply": "at_observed_events_only",
    "payer_convention": "adverse_only",
    "count_credits": False,
    "forward_fill": "forbidden",
    "missing": "funding_available=false",
}


# --------------------------------------------------------------------------
# Execution model (plan sections 39, 40, 43)
# --------------------------------------------------------------------------

EXECUTION_RULES = {
    "signal": "at_candle_close",
    "entry": "next_bar_open",
    "same_bar_stop_vs_target": "stop_first",
    "gap_through_stop": "fill_at_realistic_gap_price",
    "intrabar_data_limit": "OHLCV; event order inside a candle is unknowable",
    "leverage": RESEARCH_LEVERAGE,
    "boundary": "force_flat_and_purge_crossing_trades",
}


# --------------------------------------------------------------------------
# Walk-forward and statistics (plan sections 44, 45, 49, 50)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WalkForwardConfigV2:
    """Rolling train/validation/OOS folds. OOS is never used for selection."""

    train_days: int = 365
    validation_days: int = 90
    step_days: int = 90
    embargo_hours: int = 4
    min_folds: int = 15
    #: The final holdout is reserved up front and never inspected for tuning.
    final_holdout_days: int = 90


@dataclass(frozen=True)
class StatisticalConfigV2:
    annualization: int = 365
    resamples: int = 2000
    block_days: int = 7
    random_seed: int = 20260926
    reality_check_alpha: float = 0.05


WALK_FORWARD_V2 = WalkForwardConfigV2()
STATISTICS_V2 = StatisticalConfigV2()


# --------------------------------------------------------------------------
# Sample and survival gates (plan sections 47, 51, 52, 53)
# --------------------------------------------------------------------------

MIN_TOTAL_OBSERVATIONS = 200
MIN_OOS_TRADES = 200
MIN_POSITIVE_FOLD_FRACTION = 0.60
MAX_SINGLE_FOLD_PROFIT_SHARE = 0.35
MIN_BASE_PROFIT_FACTOR = 1.05
MIN_STRESS_PROFIT_FACTOR = 1.00
MIN_DOUBLE_COST_EXPECTANCY = 0.0

#: Every one of these must pass. They may not be loosened after seeing results.
SURVIVOR_CRITERIA: dict[str, Any] = {
    "oos_expectancy_positive": True,
    "stress_expectancy_positive": True,
    "double_cost_expectancy_positive": True,
    "min_base_profit_factor": MIN_BASE_PROFIT_FACTOR,
    "min_stress_profit_factor": MIN_STRESS_PROFIT_FACTOR,
    "min_oos_trades": MIN_OOS_TRADES,
    "min_total_observations": MIN_TOTAL_OBSERVATIONS,
    "min_positive_fold_fraction": MIN_POSITIVE_FOLD_FRACTION,
    "min_dsr": 0.0,
    "max_reality_check_p": STATISTICS_V2.reality_check_alpha,
    "max_single_fold_profit_share": MAX_SINGLE_FOLD_PROFIT_SHARE,
}

#: Terminal verdicts. There is deliberately no "best" verdict.
VERDICTS = ("PASS", "FAIL", "INSUFFICIENT_SAMPLE", "PROMISING_BUT_UNVERIFIED")

#: A survivor is still only a RESEARCH SURVIVOR, never a live strategy.
SURVIVOR_LABEL = "RESEARCH_SURVIVOR"

FORWARD_VALIDATION = {
    "minimum_days": 30,
    "preferred_days": (60, 90),
    "live_capital": False,
    "kill_switch": "documented thresholds only; never improvised",
}


# --------------------------------------------------------------------------
# Anti-overfitting rules (plan sections 46, 73) -- encoded, not just documented
# --------------------------------------------------------------------------

ANTI_OVERFITTING_RULES = {
    "generic_parameter_optimizer": "forbidden",
    "post_hoc_threshold_edit": "forbidden; requires a NEW hypothesis id and a new spec version",
    "manual_winner_selection": "forbidden",
    "cherry_picking": "forbidden",
    "oos_for_parameter_selection": "forbidden",
    "final_holdout_for_tuning": "forbidden",
    "cost_tuning_to_pass": "forbidden",
    "force_survivors": "forbidden",
    "resample_count_changes": "must be recorded in the manifest with a reason",
}


def spec_manifest() -> dict[str, Any]:
    """Return the exact V2 protocol written into every run manifest."""

    return {
        "spec_version": SPEC_VERSION,
        "primary_timeframes": list(PRIMARY_TIMEFRAMES),
        "discovery_timeframes": list(DISCOVERY_TIMEFRAMES),
        "confirmation_timeframes": list(CONFIRMATION_TIMEFRAMES),
        "optional_timeframes": list(OPTIONAL_TIMEFRAMES),
        "execution_timeframe": EXECUTION_TIMEFRAME,
        "return_windows": list(RETURN_WINDOWS),
        "atr_periods": list(ATR_PERIODS),
        "realized_vol_windows": list(REALIZED_VOL_WINDOWS),
        "ema_periods": list(EMA_PERIODS),
        "oi_windows": list(OI_WINDOWS),
        "taker_flow_windows": list(TAKER_FLOW_WINDOWS),
        "percentile_window": PERCENTILE_WINDOW,
        "vol_percentile_cuts": list(VOL_PERCENTILE_CUTS),
        "oi_percentile_cuts": list(OI_PERCENTILE_CUTS),
        "funding_percentile_cuts": list(FUNDING_PERCENTILE_CUTS),
        "liquidity_percentile_cuts": list(LIQUIDITY_PERCENTILE_CUTS),
        "taker_imbalance_cuts": list(TAKER_IMBALANCE_CUTS),
        "trend_score_cuts": list(TREND_SCORE_CUTS),
        "cost_scenarios": [scenario.as_dict() for scenario in COST_SCENARIOS],
        "funding_policy": FUNDING_POLICY,
        "execution_rules": EXECUTION_RULES,
        "leverage": RESEARCH_LEVERAGE,
        "walk_forward": vars(WALK_FORWARD_V2),
        "statistics": vars(STATISTICS_V2),
        "survivor_criteria": dict(SURVIVOR_CRITERIA),
        "verdicts": list(VERDICTS),
        "anti_overfitting": dict(ANTI_OVERFITTING_RULES),
        "forward_validation": dict(FORWARD_VALIDATION),
        "v1_reused_components": list(V1_REUSED_COMPONENTS),
        "v2_run_root": V2_RUN_ROOT,
        "v1_run_root_readonly": V1_RUN_ROOT,
    }
