"""Frozen MVP search space and validation rules.

Nothing in this module may be changed after inspecting MVP results. A changed
hypothesis or gate requires a new ``spec_version`` and a fresh run directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from tools.strategy_factory.models import CostScenario, StrategySpec


SPEC_VERSION = "2026-09-25-mvp-v1"
HYPOTHESIS_IDS = (
    "H1_VWAP_PULLBACK",
    "H2_EMA_RETEST",
    "H3_UTC_ORB",
    "H4_ATR_COMPRESSION",
)
PAIRS = ("BTC/USDT:USDT", "ETH/USDT:USDT")
PAIR_BASES = {
    "BTC/USDT:USDT": "BTC_USDT_USDT",
    "ETH/USDT:USDT": "ETH_USDT_USDT",
}

BASE_COST = CostScenario(name="base_taker", fee_bps=5.0, slippage_bps=1.0)
STRESS_COST = CostScenario(
    name="stress_taker", fee_bps=10.0, slippage_bps=3.0
)
COST_SCENARIOS = (BASE_COST, STRESS_COST)

# A signal completed at a bar close can only fill at the next bar open. The
# same-bar stop is checked before the target, and the adverse funding convention
# charges funding that a position pays while ignoring credits/rebates.
EXECUTION_RULES = {
    "entry": "next_1m_open",
    "same_bar_conflict": "stop_before_target",
    "funding": "adverse_only; charge each observed payer event, ignore credits",
    "leverage": 1.0,
    "boundary": "force_flat_and_purge_crossing_trades",
    "informative_source": "stored_5m_authoritative; audit_1m_resample_only",
    "intrabar_data_limit": "OHLCV; exact event order inside a candle is unknowable",
}

PARAMETER_SPACES: dict[str, dict[str, tuple[int | float, ...]]] = {
    "H1_VWAP_PULLBACK": {
        "trend_fast": (9, 20),
        "trend_slow": (50, 200),
        "pullback_bps": (0, 10),
        "contraction_max": (0.8, 1.0),
        "confirmation_min": (1.0, 1.2),
        "atr_stop": (1.0, 1.5),
        "target_r": (1.0, 1.5, 2.0),
    },
    "H2_EMA_RETEST": {
        "ema_fast": (5, 9, 12),
        "ema_slow": (21, 34),
        "atr_stop": (1.0, 1.5),
        "target_r": (1.0, 1.5, 2.0),
    },
    "H3_UTC_ORB": {
        "range_minutes": (5, 15, 30),
        "trade_window_hours": (1, 4, 24),
        "volume_min": (1.0, 1.5, 2.0),
        "atr_stop": (1.0, 1.5),
        "target_r": (1.0, 2.0),
    },
    "H4_ATR_COMPRESSION": {
        "lookback": (20, 60),
        "compression_max": (0.75, 0.9),
        "breakout_window": (20, 60),
        "volume_min": (1.0, 1.5),
        "atr_stop": (1.5, 2.0),
        "target_r": (2.0, 3.0),
    },
}

MAX_HOLD_MINUTES = {
    "H1_VWAP_PULLBACK": 120,
    "H2_EMA_RETEST": 90,
    "H3_UTC_ORB": 120,
    "H4_ATR_COMPRESSION": 180,
}


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 365
    validation_days: int = 90
    step_days: int = 90
    embargo_hours: int = 4
    first_validation: str = "2022-01-01"
    min_train_trades: int = 30
    selection_metric: str = "net_sharpe_then_expectancy"


@dataclass(frozen=True)
class StatisticalConfig:
    annualization: int = 365
    monte_carlo_draws: int = 2000
    monte_carlo_block_days: int = 7
    random_seed: int = 20260925
    dsr_threshold: float = 0.95
    reality_check_alpha: float = 0.05


@dataclass(frozen=True)
class AcceptanceGates:
    min_oos_trades: int = 100
    min_positive_fold_fraction: float = 0.60
    min_base_profit_factor: float = 1.05
    min_stress_profit_factor: float = 1.00
    min_dsr: float = 0.95
    max_reality_check_p: float = 0.05
    min_positive_parameter_fraction: float = 0.25
    require_btc_and_eth_positive_expectancy: bool = True


WALK_FORWARD = WalkForwardConfig()
STATISTICS = StatisticalConfig()
ACCEPTANCE = AcceptanceGates()


def generate_specs() -> list[StrategySpec]:
    """Enumerate the complete deterministic grid in a stable order."""

    specs: list[StrategySpec] = []
    for hypothesis_id in HYPOTHESIS_IDS:
        space = PARAMETER_SPACES[hypothesis_id]
        names = tuple(space)
        for values in product(*(space[name] for name in names)):
            params: dict[str, int | float] = dict(zip(names, values, strict=True))
            specs.append(
                StrategySpec(
                    hypothesis_id=hypothesis_id,
                    params=params,
                    max_hold_minutes=MAX_HOLD_MINUTES[hypothesis_id],
                    spec_version=SPEC_VERSION,
                )
            )
    return specs


def preregistration_manifest() -> dict[str, Any]:
    """Return the exact search and gate definition written into every run."""

    return {
        "spec_version": SPEC_VERSION,
        "pairs": list(PAIRS),
        "hypotheses": list(HYPOTHESIS_IDS),
        "parameter_spaces": PARAMETER_SPACES,
        "max_hold_minutes": MAX_HOLD_MINUTES,
        "cost_scenarios": [scenario.as_dict() for scenario in COST_SCENARIOS],
        "execution_rules": EXECUTION_RULES,
        "walk_forward": vars(WALK_FORWARD),
        "statistics": vars(STATISTICS),
        "acceptance_gates": vars(ACCEPTANCE),
        "trial_count": len(generate_specs()),
    }
