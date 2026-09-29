"""
BuyAndHold -- benchmark only, NOT a candidate strategy.

Enters once at full stake and never exits, with no volatility overlay. It exists
so that buy-and-hold is measured by freqtrade's own metric definitions
(Sharpe on daily wallet balance, drawdown on balance) rather than by a
hand-rolled formula that may annualise differently. Comparing a strategy's
freqtrade Sharpe against a hand-computed benchmark Sharpe would not be
apples to apples.
"""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class BuyAndHold(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False
    startup_candle_count = 5
    process_only_new_candles = True

    minimal_roi = {"0": 100000.0}
    stoploss = -0.99
    use_exit_signal = True
    use_custom_stoploss = False
    trailing_stop = False

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

    position_adjustment_enable = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, ["enter_long", "enter_tag"]] = (1, "buy_and_hold")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_stake_amount(
        self, pair, current_time, current_rate, proposed_stake, min_stake,
        max_stake, leverage, entry_tag, side, **kwargs
    ):
        return max_stake  # fully invested
