from __future__ import annotations

import numpy as np
import pandas as pd

from tools.strategy_factory.engine import apply_cost_scenario, simulate_trades
from tools.strategy_factory.models import CostScenario, StrategySpec


def _frame(n=12):
    dates = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    close = np.arange(n, dtype=float) + 100
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "atr14_1m": 1.0,
        }
    )


def _spec():
    return StrategySpec("H2_EMA_RETEST", {"atr_stop": 1.0, "target_r": 2.0}, 5)


def test_signal_close_enters_next_open_and_stop_wins():
    frame = _frame()
    frame.attrs["pair"] = "BTC/USDT:USDT"
    long_signal = np.zeros(len(frame), dtype=bool)
    short_signal = np.zeros(len(frame), dtype=bool)
    long_signal[0] = True
    trades = simulate_trades(frame, long_signal, short_signal, _spec(), pd.DataFrame())
    assert len(trades) == 1
    assert trades[0].entry_index == 1
    assert trades[0].exit_reason == "target"


def test_adverse_funding_ignores_credits_and_counts_zero_event():
    frame = _frame()
    frame.attrs["pair"] = "BTC/USDT:USDT"
    long_signal = np.zeros(len(frame), dtype=bool)
    long_signal[0] = True
    funding = pd.DataFrame(
        {
            "date": [frame.loc[1, "date"], frame.loc[2, "date"]],
            "funding_rate": [-0.001, 0.0],
        }
    )
    trade = simulate_trades(frame, long_signal, np.zeros(len(frame), dtype=bool), _spec(), funding)[0]
    assert trade.funding_rate_sum == -0.001
    assert trade.funding_payer_cost == 0
    assert trade.funding_events == 2


def test_reset_forces_flat_state_at_boundary():
    frame = _frame(20)
    frame.attrs["pair"] = "BTC/USDT:USDT"
    long_signal = np.zeros(len(frame), dtype=bool)
    long_signal[[0, 10]] = True
    reset_spec = StrategySpec("H2_EMA_RETEST", {"atr_stop": 1.0, "target_r": 10.0}, 20)
    trades = simulate_trades(
        frame,
        long_signal,
        np.zeros(len(frame), dtype=bool),
        reset_spec,
        pd.DataFrame(),
        reset_indices={10},
    )
    assert [trade.exit_reason for trade in trades] == ["boundary_reset", "end_of_data"]
    assert trades[1].entry_index == 11


def test_cost_scenario_charges_both_sides():
    frame = _frame()
    frame.attrs["pair"] = "BTC/USDT:USDT"
    long_signal = np.zeros(len(frame), dtype=bool)
    long_signal[0] = True
    raw = pd.DataFrame(
        {
            "side": [1],
            "entry_open": [100.0],
            "exit_price_raw": [101.0],
            "funding_payer_cost": [0.0],
        }
    )
    result = apply_cost_scenario(raw, CostScenario("test", fee_bps=5, slippage_bps=2))
    assert result.loc[0, "fee_cost"] == 0.001
    assert result.loc[0, "net_return"] < 0.01
