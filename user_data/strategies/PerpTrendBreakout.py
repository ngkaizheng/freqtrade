"""
PerpTrendBreakout — conservative research baseline for USDT perpetual futures.

This strategy is intentionally separate from the validated daily spot strategy.
It is a first-pass research candidate, not a claim of profitable edge.

Design:
- 5m Donchian breakout with a 1h EMA regime filter.
- Relative-volume confirmation to avoid low-liquidity breakouts.
- ATR-based initial stop and volatility-aware trailing stop.
- 12h time stop to limit funding exposure.
- Long and short support for isolated futures.

The ``perp_leverage`` key in the backtest/dry-run config is read by the
``leverage`` callback. Keep it at 1.0 until the unlevered result survives
out-of-sample, fee, funding, and slippage stress tests.
"""

from datetime import datetime, timedelta

import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_absolute


class PerpTrendBreakout(IStrategy):
    """5m trend-following breakout baseline for Binance USDT perpetuals."""

    INTERFACE_VERSION = 3

    can_short = True
    timeframe = "5m"
    startup_candle_count = 250
    process_only_new_candles = True

    # The strategy uses signal/time exits and an ATR stop rather than a fixed ROI.
    minimal_roi = {"0": 10.0}
    stoploss = -0.10
    use_custom_stoploss = True
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    position_adjustment_enable = False

    # 1h regime filter.
    trend_fast_period = 50
    trend_slow_period = 200

    # 5m breakout and participation filters.
    breakout_window = 20
    volume_window = 50
    min_volume_ratio = 1.5
    ema_fast_period = 20

    # ATR risk controls. Distance caps below are fractions of underlying price;
    # stoploss_from_absolute() converts the absolute stop to leveraged trade risk.
    atr_period = 14
    atr_stop_multiplier = 1.5
    max_stop_distance = 0.03
    trailing_activation_distance = 0.01
    trailing_atr_multiplier = 1.5
    max_trailing_distance = 0.03
    max_hold_hours = 12

    # Set through the config key ``perp_leverage`` for comparable runs.
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

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(
            span=self.trend_fast_period,
            adjust=False,
            min_periods=self.trend_fast_period,
        ).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(
            span=self.trend_slow_period,
            adjust=False,
            min_periods=self.trend_slow_period,
        ).mean()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(
            span=self.ema_fast_period,
            adjust=False,
            min_periods=self.ema_fast_period,
        ).mean()
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Shift the channel and volume baseline so the current candle cannot
        # define the level it is trying to break.
        dataframe["breakout_high"] = (
            dataframe["high"]
            .rolling(self.breakout_window, min_periods=self.breakout_window)
            .max()
            .shift(1)
        )
        dataframe["breakout_low"] = (
            dataframe["low"]
            .rolling(self.breakout_window, min_periods=self.breakout_window)
            .min()
            .shift(1)
        )
        dataframe["volume_median"] = (
            dataframe["volume"]
            .rolling(self.volume_window, min_periods=self.volume_window)
            .median()
            .shift(1)
        )
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_median"].replace(
            0, float("nan")
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        liquid_breakout = dataframe["volume_ratio"] >= self.min_volume_ratio
        uptrend = (
            (dataframe["ema_fast_1h"] > dataframe["ema_slow_1h"])
            & (dataframe["close_1h"] > dataframe["ema_fast_1h"])
        )
        downtrend = (
            (dataframe["ema_fast_1h"] < dataframe["ema_slow_1h"])
            & (dataframe["close_1h"] < dataframe["ema_fast_1h"])
        )

        long_setup = (
            (dataframe["close"] > dataframe["breakout_high"])
            & (dataframe["close"] > dataframe["ema_fast"])
            & uptrend
            & liquid_breakout
        )
        short_setup = (
            (dataframe["close"] < dataframe["breakout_low"])
            & (dataframe["close"] < dataframe["ema_fast"])
            & downtrend
            & liquid_breakout
        )

        dataframe.loc[long_setup, ["enter_long", "enter_tag"]] = (1, "long_breakout")
        dataframe.loc[short_setup, ["enter_short", "enter_tag"]] = (1, "short_breakout")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_exit = qtpylib.crossed_below(dataframe["close"], dataframe["ema_fast"])
        long_exit |= qtpylib.crossed_below(dataframe["ema_fast_1h"], dataframe["ema_slow_1h"])
        short_exit = qtpylib.crossed_above(dataframe["close"], dataframe["ema_fast"])
        short_exit |= qtpylib.crossed_above(dataframe["ema_fast_1h"], dataframe["ema_slow_1h"])

        dataframe.loc[long_exit, ["exit_long", "exit_tag"]] = (1, "ema_reversal")
        dataframe.loc[short_exit, ["exit_short", "exit_tag"]] = (1, "ema_reversal")
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
        """Read a controlled research leverage override from the config."""
        try:
            requested = float(self.config.get("perp_leverage", self.default_leverage))
        except (TypeError, ValueError):
            requested = self.default_leverage
        return max(1.0, min(requested, max_leverage))

    def _latest_atr(self, pair: str) -> float | None:
        if self.dp is None:
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty or "atr" not in dataframe.columns:
            return None
        # Use the previous completed 5m candle. The current candle's
        # high/low/close are not known when an entry is filled at its open.
        atr_row = dataframe.iloc[-2] if len(dataframe) > 1 else dataframe.iloc[-1]
        atr = atr_row["atr"]
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
        """Set an ATR initial stop, then trail it after an underlying move."""
        atr = self._latest_atr(pair)
        if atr is None:
            return None

        initial_stop = trade.get_custom_data("initial_stop_price")
        best_price = trade.get_custom_data("best_price")

        # Backtesting calls this once after the entry order is filled. Using
        # the fill price here avoids deriving the stop from the candle high.
        if after_fill and initial_stop is None:
            stop_fraction = min(
                (atr * self.atr_stop_multiplier) / current_rate,
                self.max_stop_distance,
            )
            distance = current_rate * stop_fraction
            initial_stop = (
                current_rate - distance if not trade.is_short else current_rate + distance
            )
            trade.set_custom_data("initial_stop_price", initial_stop)
            trade.set_custom_data("best_price", current_rate)

        if best_price is None:
            best_price = current_rate
        elif trade.is_short:
            best_price = min(float(best_price), current_rate)
        else:
            best_price = max(float(best_price), current_rate)
        trade.set_custom_data("best_price", best_price)

        if initial_stop is not None:
            candidate_stop = float(initial_stop)
        else:
            candidate_stop = None

        # Activate trailing only after a fixed underlying-price move, so the
        # activation threshold is comparable between 1x and 2x runs.
        if current_profit >= self.trailing_activation_distance * (trade.leverage or 1.0):
            trail_fraction = min(
                (atr * self.trailing_atr_multiplier) / float(best_price),
                self.max_trailing_distance,
            )
            trail_distance = float(best_price) * trail_fraction
            if trade.is_short:
                trailing_stop = float(best_price) + trail_distance
                if trailing_stop >= current_rate:
                    return None
                candidate_stop = (
                    trailing_stop
                    if candidate_stop is None
                    else min(candidate_stop, trailing_stop)
                )
            else:
                trailing_stop = float(best_price) - trail_distance
                if trailing_stop <= current_rate:
                    return None
                candidate_stop = (
                    trailing_stop
                    if candidate_stop is None
                    else max(candidate_stop, trailing_stop)
                )

        if candidate_stop is None:
            return None
        if not trade.is_short and candidate_stop >= current_rate:
            return None
        if trade.is_short and candidate_stop <= current_rate:
            return None

        return stoploss_from_absolute(
            candidate_stop,
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
        """Cap time held so a failed breakout does not pay funding forever."""
        if current_time - trade.open_date_utc >= timedelta(hours=self.max_hold_hours):
            return "time_stop"
        return None

    plot_config = {
        "main_plot": {
            "ema_fast": {"color": "blue"},
            "breakout_high": {"color": "green"},
            "breakout_low": {"color": "red"},
        },
        "subplots": {
            "Trend": {
                "ema_fast_1h": {"color": "blue"},
                "ema_slow_1h": {"color": "orange"},
            },
            "Risk": {
                "atr": {"color": "purple"},
            },
        },
    }
