"""
PerpTrendSlow — low-turnover 1h long-only trend baseline for USDT perpetuals.

This is a separate research candidate from the 5m PerpTrendBreakout strategy.
The motivation is empirical: 5m/15m breakout and mean-reversion variants
were overwhelmed by fees, funding, and intrabar assumptions in local screens.
A slower 1h EMA50/EMA200 regime filter produced a much more stable result in
pre-specified train/test screens, but it is not a profitability guarantee.

Design:
- Long-only while the 1h EMA50 is above EMA200.
- Enter on the EMA50/EMA200 upward cross; exit on the downward cross.
- Initial stop is 3 ATR, capped at 4% underlying price distance.
- Maximum holding time is 180 hours to limit funding exposure.
- Leverage is read from ``perp_leverage`` and defaults to 1x.

The next validation gate is a real Freqtrade 2026.8 backtest with current
1h mark/funding data, lookahead analysis, and a dry-run forward test.
"""

from datetime import datetime, timedelta

import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute


class PerpTrendSlow(IStrategy):
    """1h long-only trend candidate; research baseline, not a live signal."""

    INTERFACE_VERSION = 3

    can_short = False
    timeframe = "1h"
    startup_candle_count = 500
    process_only_new_candles = True

    minimal_roi = {"0": 10.0}
    stoploss = -0.10
    use_custom_stoploss = True
    trailing_stop = False
    use_exit_signal = True
    position_adjustment_enable = False

    ema_fast_period = 50
    ema_slow_period = 200
    atr_period = 14
    atr_stop_multiplier = 3.0
    max_stop_distance = 0.04
    max_hold_hours = 180
    default_leverage = 1.0

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "force_exit": "market",
        "force_entry": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(
            span=self.ema_fast_period,
            adjust=False,
            min_periods=self.ema_fast_period,
        ).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(
            span=self.ema_slow_period,
            adjust=False,
            min_periods=self.ema_slow_period,
        ).mean()
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"]),
            ["enter_long", "enter_tag"],
        ] = (1, "ema50_200_up")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"]),
            ["exit_long", "exit_tag"],
        ] = (1, "ema50_200_down")
        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """Allow a controlled 1x/2x research comparison from configuration."""
        try:
            requested = float(self.config.get("perp_leverage", self.default_leverage))
        except (TypeError, ValueError):
            requested = self.default_leverage
        return max(1.0, min(requested, max_leverage))

    def _previous_atr(self, pair: str) -> float | None:
        if self.dp is None:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or "atr" not in dataframe.columns:
            return None
        # The current 1h candle is not complete at entry time.
        row = dataframe.iloc[-2] if len(dataframe) > 1 else dataframe.iloc[-1]
        atr = row["atr"]
        if pd.isna(atr) or float(atr) <= 0:
            return None
        return float(atr)

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool = False,
        **kwargs,
    ) -> float | None:
        """Set a capped ATR stop once, then leave it fixed until exit."""
        atr = self._previous_atr(pair)
        if atr is None:
            return None

        stop_price = trade.get_custom_data("initial_stop_price")
        if stop_price is None and after_fill:
            distance = min(
                atr * self.atr_stop_multiplier,
                current_rate * self.max_stop_distance,
            )
            stop_price = current_rate - distance
            trade.set_custom_data("initial_stop_price", stop_price)

        if stop_price is None or stop_price >= current_rate:
            return None
        return stoploss_from_absolute(
            float(stop_price),
            current_rate=current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage or 1.0,
        )

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        """Exit stale positions so a failed regime does not pay funding forever."""
        if current_time - trade.open_date_utc >= timedelta(hours=self.max_hold_hours):
            return "time_stop"
        return None

    plot_config = {
        "main_plot": {
            "ema_fast": {"color": "blue"},
            "ema_slow": {"color": "orange"},
        },
        "subplots": {
            "Risk": {
                "atr": {"color": "purple"},
            },
        },
    }
