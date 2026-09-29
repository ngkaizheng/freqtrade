# The entry signal of the leaderboard strategy, with the exit model REPLACED.
#
# WHY
# ---
# Measured on 2026 data the selection never saw (tools/leaderboard/entry_power2.py):
#
#   entry conditional lift, 1h horizon, 443 signals
#     lift +48.04 bps, dependence-adjusted t = 2.81, p = 0.004
#     after a 20 bps round trip: +28.04 bps
#     after this repo's measured 35 bps COVID round trip: +13.04 bps
#
# ...while the upstream strategy's OWN exit rule destroys it: on the same 2026 data,
# 90 of 120 exits went through `exit_signal` and LOST 37.48% in aggregate.
#
# The edge is in the entry. The upstream exit model spends it. This strategy keeps the
# entry byte-for-byte and replaces only the exit: a fixed 1h hold, which is the same
# horizon the lift was measured at - not a tuned parameter.
#
# DISCLOSURE - this is a SELECTION and must be reported as one:
#   3 horizons were measured (15m, 1h, 3h) and 1h was kept. On the out-of-sample
#   block the net-after-cost lifts were +9.02 / +28.04 / +2.62 bps, so 1h wins by a
#   factor of ~3 over the next best and the choice is not marginal. But 3 was tried.
#
# NOT LOOKED AT: trailing stop, ROI ladder, the -35% stoploss. All are disabled.
# minimal_roi is set to 1000% so the ROI path can never fire.

# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from functools import reduce
from datetime import datetime, timedelta
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter

# @Rallipanos  - entry conditions copied verbatim from
# davidzr/freqtrade-strategies/strategies/NotAnotherSMAOffsetStrategy
# (SHA 4d2d11e0015688cf09253f019b60d047a751ab52), converted v2 -> v3.

buy_params = {
    "base_nb_candles_buy": 14,
    "ewo_high": 2.327,
    "ewo_high_2": -2.327,
    "ewo_low": -20.988,
    "low_offset": 0.975,
    "low_offset_2": 0.955,
    "rsi_buy": 69,
}
sell_params = {"base_nb_candles_sell": 24, "high_offset": 0.991, "high_offset_2": 0.997}

HOLD_MINUTES = 60  # 1h. Measured, not tuned: see module docstring.


def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    return (ema1 - ema2) / df["low"] * 100


class LeaderboardEntry1hHold(IStrategy):
    INTERFACE_VERSION = 3

    # 1000% so the ROI path can never trigger; exits are custom_exit only.
    minimal_roi = {"0": 10.0}

    # Kept wide purely as a safety net for a catastrophic move; the measured
    # strategy never reaches it inside 1h, and it is NOT a tuned parameter.
    stoploss = -0.35

    # TRAP, verified in this repo: freqtrade/strategy/interface.py:1469 gates
    # custom_exit INSIDE `if self.use_exit_signal:`. Setting use_exit_signal=False
    # does not merely silence exit_long - it silently disables custom_exit too, and
    # this strategy then holds for months and only leaves via the stoploss. You must
    # leave use_exit_signal True and keep populate_exit_trend returning nothing.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    trailing_stop = False

    base_nb_candles_buy = IntParameter(
        5, 80, default=buy_params["base_nb_candles_buy"], space="buy", optimize=True
    )
    base_nb_candles_sell = IntParameter(
        5, 80, default=sell_params["base_nb_candles_sell"], space="sell", optimize=True
    )
    low_offset = DecimalParameter(0.9, 0.99, default=buy_params["low_offset"], space="buy", optimize=True)
    low_offset_2 = DecimalParameter(0.9, 0.99, default=buy_params["low_offset_2"], space="buy", optimize=True)
    high_offset = DecimalParameter(0.95, 1.1, default=sell_params["high_offset"], space="sell", optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=sell_params["high_offset_2"], space="sell", optimize=True)
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(-20.0, -8.0, default=buy_params["ewo_low"], space="buy", optimize=True)
    ewo_high = DecimalParameter(2.0, 12.0, default=buy_params["ewo_high"], space="buy", optimize=True)
    ewo_high_2 = DecimalParameter(-6.0, 12.0, default=buy_params["ewo_high_2"], space="buy", optimize=True)
    rsi_buy = IntParameter(30, 70, default=buy_params["rsi_buy"], space="buy", optimize=True)

    timeframe = "5m"
    process_only_new_candles = True
    startup_candle_count = 200

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float,
                    **kwargs) -> str | None:
        if trade.open_date_utc + timedelta(minutes=HOLD_MINUTES) <= current_time:
            return "hold_1h"
        return None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] = ta.EMA(
            dataframe, timeperiod=self.base_nb_candles_buy.value
        )
        dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] = ta.EMA(
            dataframe, timeperiod=self.base_nb_candles_sell.value
        )
        dataframe["hma_50"] = qtpylib.hull_moving_average(dataframe["close"], window=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["sma_9"] = ta.SMA(dataframe, timeperiod=9)
        dataframe["EWO"] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["rsi_slow"] = ta.RSI(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["rsi_fast"] < 35)
            & (dataframe["close"] < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset.value))
            & (dataframe["EWO"] > self.ewo_high.value)
            & (dataframe["rsi"] < self.rsi_buy.value)
            & (dataframe["volume"] > 0)
            & (dataframe["close"] < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value)),
            ["enter_long", "enter_tag"],
        ] = (1, "ewo1")

        dataframe.loc[
            (dataframe["rsi_fast"] < 35)
            & (dataframe["close"] < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset_2.value))
            & (dataframe["EWO"] > self.ewo_high_2.value)
            & (dataframe["rsi"] < self.rsi_buy.value)
            & (dataframe["volume"] > 0)
            & (dataframe["close"] < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value))
            & (dataframe["rsi"] < 25),
            ["enter_long", "enter_tag"],
        ] = (1, "ewo2")

        dataframe.loc[
            (dataframe["rsi_fast"] < 35)
            & (dataframe["close"] < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset.value))
            & (dataframe["EWO"] < self.ewo_low.value)
            & (dataframe["volume"] > 0)
            & (dataframe["close"] < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value)),
            ["enter_long", "enter_tag"],
        ] = (1, "ewolow")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # deliberately empty: all exits are custom_exit (fixed 1h hold)
        return dataframe
