from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_absolute,
)


class RegimeVolBreakout5m(IStrategy):
    """
    RegimeVolBreakout5m

    Hypothesis:
        Crypto short-term returns are more persistent during
        higher-timeframe directional regimes when accompanied by
        lower-timeframe volatility and volume expansion.

    Main timeframe:
        5m

    Informative timeframe:
        1h

    Entry:
        LONG
            1h bullish regime
            +
            5m trend aligned
            +
            breakout above prior 24-candle high
            +
            volume expansion
            +
            volatility expansion
            +
            positive momentum

        SHORT
            inverse conditions

    Exit:
        - Dynamic ATR trailing stoploss
        - Fixed unleveraged price target
        - Momentum failure
        - Time stop

    IMPORTANT:
        This is a research hypothesis.
        It is NOT assumed to be profitable.
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    startup_candle_count = 400

    can_short = True

    # We want explicit exit signals.
    use_exit_signal = True

    # We use the custom ATR stoploss.
    use_custom_stoploss = True

    # Keep the static stoploss as a hard backstop.
    # This is deliberately small because this is a short-term strategy.
    stoploss = -0.009

    # Disable ROI so that ROI does not fight the explicit exit model.
    minimal_roi = {
        "0": 100.0
    }

    # ---------------------------------------------------------
    # Research constants
    # ---------------------------------------------------------

    BREAKOUT_LOOKBACK = 24          # 24 x 5m = 2 hours
    VOLUME_LOOKBACK = 30            # 150 minutes
    ATR_PERIOD = 14
    ATR_BASELINE = 96               # 8 hours
    EMA_FAST = 21
    EMA_SLOW = 55

    VOLUME_MULTIPLIER = 1.30
    ATR_EXPANSION_MULTIPLIER = 1.05

    ADX_MIN = 18.0

    LONG_RSI_MIN = 55.0
    LONG_RSI_MAX = 78.0

    SHORT_RSI_MIN = 22.0
    SHORT_RSI_MAX = 45.0

    MIN_BODY_ATR = 0.30

    # Actual price movement, NOT leveraged PnL.
    TAKE_PROFIT = 0.018

    # After approximately 90 minutes, momentum should have
    # produced something. Otherwise abandon the trade.
    TIME_STOP_MINUTES = 90

    # ATR trailing distance.
    ATR_STOP_MULTIPLIER = 3.0

    @informative("1h")
    def populate_indicators_1h(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:
        """
        Higher timeframe regime.

        Freqtrade's informative decorator handles the higher
        timeframe merge without requiring us to manually perform
        a potentially lookahead-biased merge.
        """

        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    def populate_indicators(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:

        # -----------------------------------------------------
        # 5m trend
        # -----------------------------------------------------

        dataframe["ema_21"] = ta.EMA(
            dataframe,
            timeperiod=self.EMA_FAST,
        )

        dataframe["ema_55"] = ta.EMA(
            dataframe,
            timeperiod=self.EMA_SLOW,
        )

        dataframe["rsi"] = ta.RSI(
            dataframe,
            timeperiod=14,
        )

        dataframe["adx"] = ta.ADX(
            dataframe,
            timeperiod=14,
        )

        # -----------------------------------------------------
        # ATR / volatility
        # -----------------------------------------------------

        dataframe["atr"] = ta.ATR(
            dataframe,
            timeperiod=self.ATR_PERIOD,
        )

        dataframe["atr_pct"] = (
            dataframe["atr"] / dataframe["close"]
        )

        # Previous volatility baseline.
        dataframe["atr_pct_baseline"] = (
            dataframe["atr_pct"]
            .rolling(self.ATR_BASELINE)
            .median()
            .shift(1)
        )

        dataframe["vol_expansion"] = (
            dataframe["atr_pct"]
            >
            dataframe["atr_pct_baseline"]
            * self.ATR_EXPANSION_MULTIPLIER
        )

        # -----------------------------------------------------
        # Volume expansion
        # -----------------------------------------------------

        dataframe["volume_mean"] = (
            dataframe["volume"]
            .rolling(self.VOLUME_LOOKBACK)
            .mean()
            .shift(1)
        )

        dataframe["volume_ratio"] = (
            dataframe["volume"]
            / dataframe["volume_mean"]
        )

        dataframe["volume_expansion"] = (
            dataframe["volume_ratio"]
            > self.VOLUME_MULTIPLIER
        )

        # -----------------------------------------------------
        # Donchian breakout
        # IMPORTANT:
        # shift(1) prevents today's candle from defining its own
        # breakout level.
        # -----------------------------------------------------

        dataframe["breakout_high"] = (
            dataframe["high"]
            .shift(1)
            .rolling(self.BREAKOUT_LOOKBACK)
            .max()
        )

        dataframe["breakout_low"] = (
            dataframe["low"]
            .shift(1)
            .rolling(self.BREAKOUT_LOOKBACK)
            .min()
        )

        dataframe["breakout_long"] = (
            dataframe["close"]
            > dataframe["breakout_high"]
        )

        dataframe["breakout_short"] = (
            dataframe["close"]
            < dataframe["breakout_low"]
        )

        # -----------------------------------------------------
        # Candle body strength
        # -----------------------------------------------------

        dataframe["body"] = (
            dataframe["close"]
            - dataframe["open"]
        ).abs()

        dataframe["body_atr"] = (
            dataframe["body"]
            / dataframe["atr"]
        )

        # -----------------------------------------------------
        # Higher timeframe regime
        # -----------------------------------------------------

        dataframe["regime_long"] = (
            (dataframe["close_1h"] > dataframe["ema_50_1h"])
            &
            (dataframe["ema_50_1h"] > dataframe["ema_200_1h"])
            &
            (dataframe["adx_1h"] > 15)
        )

        dataframe["regime_short"] = (
            (dataframe["close_1h"] < dataframe["ema_50_1h"])
            &
            (dataframe["ema_50_1h"] < dataframe["ema_200_1h"])
            &
            (dataframe["adx_1h"] > 15)
        )

        # -----------------------------------------------------
        # 5m local trend
        # -----------------------------------------------------

        dataframe["trend_long"] = (
            dataframe["ema_21"]
            > dataframe["ema_55"]
        )

        dataframe["trend_short"] = (
            dataframe["ema_21"]
            < dataframe["ema_55"]
        )

        # -----------------------------------------------------
        # Valid data guard
        # -----------------------------------------------------

        dataframe["data_valid"] = (
            dataframe["volume"].notna()
            &
            dataframe["atr"].notna()
            &
            dataframe["atr_pct_baseline"].notna()
            &
            dataframe["volume_mean"].notna()
            &
            dataframe["breakout_high"].notna()
            &
            dataframe["breakout_low"].notna()
            &
            dataframe["ema_200_1h"].notna()
        )

        return dataframe

    def populate_entry_trend(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        # =====================================================
        # LONG
        # =====================================================

        long_condition = (
            dataframe["data_valid"]

            # Higher timeframe regime
            &
            dataframe["regime_long"]

            # Local trend
            &
            dataframe["trend_long"]

            # Breakout
            &
            dataframe["breakout_long"]

            # Participation
            &
            dataframe["volume_expansion"]

            # Volatility expansion
            &
            dataframe["vol_expansion"]

            # Trend strength
            &
            (dataframe["adx"] > self.ADX_MIN)

            # Momentum
            &
            (dataframe["rsi"] >= self.LONG_RSI_MIN)
            &
            (dataframe["rsi"] <= self.LONG_RSI_MAX)

            # Candle must have meaningful body
            &
            (dataframe["body_atr"] >= self.MIN_BODY_ATR)

            # Never trade zero volume
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[
            long_condition,
            "enter_long"
        ] = 1

        dataframe.loc[
            long_condition,
            "enter_tag"
        ] = "regime_breakout_long"

        # =====================================================
        # SHORT
        # =====================================================

        short_condition = (
            dataframe["data_valid"]

            # Higher timeframe regime
            &
            dataframe["regime_short"]

            # Local trend
            &
            dataframe["trend_short"]

            # Breakdown
            &
            dataframe["breakout_short"]

            # Participation
            &
            dataframe["volume_expansion"]

            # Volatility expansion
            &
            dataframe["vol_expansion"]

            # Trend strength
            &
            (dataframe["adx"] > self.ADX_MIN)

            # Momentum
            &
            (dataframe["rsi"] >= self.SHORT_RSI_MIN)
            &
            (dataframe["rsi"] <= self.SHORT_RSI_MAX)

            # Meaningful candle
            &
            (dataframe["body_atr"] >= self.MIN_BODY_ATR)

            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[
            short_condition,
            "enter_short"
        ] = 1

        dataframe.loc[
            short_condition,
            "enter_tag"
        ] = "regime_breakout_short"

        return dataframe

    def populate_exit_trend(
        self,
        dataframe: DataFrame,
        metadata: dict,
    ) -> DataFrame:

        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # =====================================================
        # Momentum failure
        # =====================================================

        long_exit = (
            (dataframe["close"] < dataframe["ema_21"])
            |
            (dataframe["close"] < dataframe["ema_50_1h"])
        )

        short_exit = (
            (dataframe["close"] > dataframe["ema_21"])
            |
            (dataframe["close"] > dataframe["ema_50_1h"])
        )

        dataframe.loc[
            long_exit,
            "exit_long"
        ] = 1

        dataframe.loc[
            short_exit,
            "exit_short"
        ] = 1

        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:

        # -----------------------------------------------------
        # Calculate actual unleveraged price movement.
        #
        # This deliberately does NOT use current_profit because
        # current_profit in futures can reflect leverage.
        # -----------------------------------------------------

        if trade.is_short:
            price_move = (
                trade.open_rate / current_rate
            ) - 1.0
        else:
            price_move = (
                current_rate / trade.open_rate
            ) - 1.0

        # -----------------------------------------------------
        # Take profit
        # -----------------------------------------------------

        if price_move >= self.TAKE_PROFIT:
            return "tp_1_8pct"

        # -----------------------------------------------------
        # Momentum has produced a small profit but then failed.
        #
        # Let winning trades exit instead of turning them back
        # into full losses.
        # -----------------------------------------------------

        if price_move >= 0.008:

            dataframe, _ = self.dp.get_analyzed_dataframe(
                pair,
                self.timeframe,
            )

            if dataframe is not None and not dataframe.empty:
                last = dataframe.iloc[-1]

                if trade.is_short:
                    momentum_failed = (
                        last["close"]
                        > last["ema_21"]
                    )
                else:
                    momentum_failed = (
                        last["close"]
                        < last["ema_21"]
                    )

                if momentum_failed:
                    return "profit_momentum_failure"

        # -----------------------------------------------------
        # Time stop
        # -----------------------------------------------------

        held_minutes = (
            current_time - trade.open_date_utc
        ).total_seconds() / 60.0

        if held_minutes >= self.TIME_STOP_MINUTES:
            return "time_stop"

        return None

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(
            pair,
            self.timeframe,
        )

        if dataframe is None or dataframe.empty:
            return None

        last = dataframe.iloc[-1]

        atr = last["atr"]

        if not np.isfinite(atr) or atr <= 0:
            return None

        # Trail at 3 ATR from current price.
        if trade.is_short:

            stop_price = (
                current_rate
                + self.ATR_STOP_MULTIPLIER * atr
            )

            return stoploss_from_absolute(
                stop_price,
                current_rate=current_rate,
                is_short=True,
                leverage=trade.leverage,
            )

        stop_price = (
            current_rate
            - self.ATR_STOP_MULTIPLIER * atr
        )

        return stoploss_from_absolute(
            stop_price,
            current_rate=current_rate,
            is_short=False,
            leverage=trade.leverage,
        )

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Deliberately conservative.

        Start research at 1x.
        If the strategy survives OOS / stress testing,
        change ONLY this number to 2.0 and rerun.
        """

        return min(1.0, max_leverage)