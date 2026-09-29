"""
S2 TrendVolTarget -- pre-registered in docs-myself/PREREG_MULTI_STRATEGY_2026-09-27.md

Long while close > SMA(200), flat otherwise, exposure scaled by inverse realised
volatility. SMA-200 is the conventional published parameter and is NOT tuned.
"""

import numpy as np
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class TrendVolTarget(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False
    startup_candle_count = 220
    process_only_new_candles = True

    minimal_roi = {"0": 1000.0}
    stoploss = -0.99
    use_exit_signal = True
    use_custom_stoploss = False
    trailing_stop = False

    sma_len = 200
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
        dataframe["sma"] = dataframe["close"].rolling(self.sma_len).mean()
        rets = dataframe["close"].pct_change()
        dataframe["realised_vol"] = rets.rolling(self.vol_lookback).std() * np.sqrt(365.0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["sma"]) & dataframe["sma"].notna(),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_up")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["sma"]) & dataframe["sma"].notna(),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_down")
        return dataframe

    def _vol_fraction(self, pair: str) -> float | None:
        if self.dp is None:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 2 or "realised_vol" not in df.columns:
            return None
        vol = df["realised_vol"].iloc[-2]  # previous completed bar only
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
            return None
        if min_stake and abs(diff) < min_stake:
            return None
        return diff
