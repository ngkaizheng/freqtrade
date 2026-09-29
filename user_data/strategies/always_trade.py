"""AlwaysTradeStrategy - Simple version"""
from typing import Dict
from pandas import DataFrame
from freqtrade.strategy import IStrategy

class AlwaysTradeStrategy(IStrategy):
    """Always enter trades, exit on next candle with minimal ROI"""
    
    INTERFACE_VERSION = 3
    timeframe = "1m"
    startup_candle_count = 1
    can_short = False
    use_exit_signal = True

    # Make ROI very easy to hit quickly
    minimal_roi = {
        "0": 0.001,  # 0.1% profit - very easy to hit
        "1": 0.0001   # Almost immediate exit
    }
    
    # Very tight stoploss to avoid interference
    stoploss = -0.02  # -2%

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        dataframe.loc[dataframe['volume'] > 0, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        # Simple exit: use ROI instead of exit signals
        dataframe['exit_long'] = 0
        return dataframe