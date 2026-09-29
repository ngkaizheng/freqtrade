"""
S1 VolTargetHold -- pre-registered in docs-myself/PREREG_MULTI_STRATEGY_2026-09-27.md

Always in the market. Exposure scaled by inverse realised volatility.
No directional signal at all. This is E#8's mechanism expressed in freqtrade.

target_vol=0.20 and vol_lookback=30 are taken from E#8's pre-registration and are
deliberately NOT tuned here. Do not "improve" them -- see the prereg.
"""

from datetime import datetime

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class VolTargetHold(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False
    startup_candle_count = 220
    process_only_new_candles = True

    # Exposure strategy: no price stop, no take-profit. Exits are signal-driven.
    minimal_roi = {"0": 1000.0}
    stoploss = -0.99
    use_exit_signal = True
    use_custom_stoploss = False
    trailing_stop = False

    # vol overlay -- FROZEN from E#8
    target_vol = 0.20
    vol_lookback = 30
    rebalance_band = 0.10

    order_types = {
        "entry": "market",
        "exit": "market",
        "emergency_exit": "market",
        "force_exit": "market",
        "force_entry": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    position_adjustment_enable = True
    max_entry_position_adjustment = -1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rets = dataframe["close"].pct_change()
        dataframe["realised_vol"] = rets.rolling(self.vol_lookback).std() * np.sqrt(365.0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            dataframe["realised_vol"].notna(),
            ["enter_long", "enter_tag"],
        ] = (1, "voltgt_hold")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe  # never exit on a signal

    # ------------------------------------------------------------------ vol
    def _vol_fraction(self, pair: str) -> float | None:
        """Target exposure = min(1, target_vol / realised_vol).

        Reads the PREVIOUS COMPLETED bar only (iloc[-2]). Using vol[t] on r_t was
        found as a look-ahead defect in this repo twice (E#8, E#11).
        """
        if self.dp is None:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 2 or "realised_vol" not in df.columns:
            return None
        vol = df["realised_vol"].iloc[-2]
        if vol is None or not np.isfinite(vol) or vol <= 0:
            return None
        return float(min(1.0, self.target_vol / vol))

    def custom_stake_amount(
        self, pair, current_time, current_rate, proposed_stake, min_stake,
        max_stake, leverage, entry_tag, side, **kwargs
    ):
        frac = self._vol_fraction(pair)
        if frac is None:
            return proposed_stake
        stake = max_stake * frac
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def adjust_trade_position(
        self, trade: Trade, current_time, current_rate, current_profit,
        min_stake, max_stake, current_entry_rate, current_exit_rate,
        current_entry_profit, current_exit_profit, **kwargs
    ):
        frac = self._vol_fraction(trade.pair)
        if frac is None:
            return None
        equity = self.wallets.get_total_stake_amount()
        diff = equity * frac - trade.stake_amount
        if abs(diff) < self.rebalance_band * equity:
            return None  # inside the band: do not churn fees
        if min_stake and abs(diff) < min_stake:
            return None
        return diff
