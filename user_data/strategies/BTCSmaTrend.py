"""
BTCSmaTrend — the SMA-50 exposure rule validated on 15 years of BTC/USD.

Origin: this project's own research (docs-myself/findings-sma-15year.md).
NOT from quant-research-handoff; the handoff's MA200 rule was rejected here.

    Close > SMA(50)  ->  100% exposure
    Close < SMA(50)  ->   50% exposure

Evidence (BTC/USD, Bitstamp, 2012-03-05 -> 2026-09-19, 14.6y, 10bps):
    buy & hold : CAGR  94.53%  MaxDD -84.86%  Sharpe 1.26
    SMA-50     : CAGR 102.56%  MaxDD -74.37%  Sharpe 1.45
    flat 78.5% : CAGR  77.31%  MaxDD -75.12%  Sharpe 1.26

Gates passed:
  * beats the matched-exposure flat control: bootstrap CI [+0.01, +0.37]
  * beats the matched-DRAWDOWN constant (75% exposure, Sharpe 1.26) by +0.187
  * placebo p=0.002 (500 random-exposure draws at matched mean)
  * 2011-2019 holdout, never searched before: Sharpe 1.70 vs 1.54
  * walk-forward stitched OOS: 1.20 vs buy & hold 1.04
  * parameter plateau: windows 10-150 all give Sharpe 1.40-1.45
  * MinBTL: 4.4y needed for the 106-trial ledger, 14.6y available
  * robust to 100bps costs, 3 bars of delay, and exposure noise

HONEST LIMITATIONS (read before trading this):
  * ONE asset. Multi-asset replication was 4/5 but with much shorter histories.
  * MaxDD is still ~-74%. This is better than buy & hold but NOT "safe".
  * The edge over the matched constant is +0.19 Sharpe, not a transformation.
  * Daily n=5312 massively overstates independence; ~79 drawdown episodes.
  * No funding cost modelled (this is spot).

Implementation mirrors MA200Exposure: 1 unit = half the available stake, so
2 units == 100% exposure and the other half stays in reserve for the
50% -> 100% transition.
"""

from datetime import datetime

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class BTCSmaTrend(IStrategy):
    INTERFACE_VERSION = 3

    # --- validated parameters (from the 15-year study) ---
    ma_period: int = 50
    exposure_risk_on: float = 1.00
    exposure_risk_off: float = 0.50

    timeframe = "1d"
    can_short = False

    # Exposure management is a state mapping, not a path-dependent exit.
    stoploss = -0.99
    trailing_stop = False
    minimal_roi = {"0": 1000}
    use_exit_signal = False

    process_only_new_candles = True
    position_adjustment_enable = True

    # The MA needs 50 bars before the signal is valid.
    startup_candle_count: int = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma"] = dataframe["close"].rolling(
            self.ma_period, min_periods=self.ma_period
        ).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Always want exposure; this only fires when flat.
        dataframe.loc[dataframe["sma"].notna(), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """Allocate one unit at entry (1 unit == 50% exposure)."""
        unit = max_stake / 2
        if min_stake is not None and unit < min_stake:
            return min_stake
        return unit

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None:
        """Resize between 50% and 100% exposure on Close vs SMA.

        IMPORTANT — live/backtest cadence difference:
        In live and dry-run this callback fires on EVERY process throttle
        (~5s), whereas in backtesting it fires once per candle. Acting on each
        call produced 24% cancelled orders in a live dry-run test (order
        created, cancelled, replaced, repeatedly) — pure spread cost that the
        backtest cannot show.

        Two guards prevent that, and they are safe here because the signal is a
        daily-candle state, so at most one action per candle is ever correct:
          1. act only once per known candle
          2. never act while this trade already has an open order
        """
        # Guard 1: one action per candle.
        last_candle = trade.get_custom_data("last_adjust_candle")
        candle_key = str(current_time.date()) if self.timeframe.endswith("d") \
            else current_time.replace(second=0, microsecond=0).isoformat()
        if last_candle == candle_key:
            return None

        # Guard 2: an order is already in flight — let it resolve first.
        if any(o.ft_is_open for o in trade.orders):
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None

        last = dataframe.iloc[-1]
        sma = last["sma"]
        if sma != sma:  # NaN guard: MA not warmed up
            return None

        unit = trade.get_custom_data("unit")
        if unit is None:
            unit = trade.stake_amount
            trade.set_custom_data("unit", unit)
        if unit <= 0:
            return None

        target_exposure = (
            self.exposure_risk_on if last["close"] > sma else self.exposure_risk_off
        )
        want_units = target_exposure / self.exposure_risk_off
        have_units = trade.stake_amount / unit

        # Dead-band to avoid churn on float drift.
        if want_units > have_units + 0.25:
            add = (want_units - have_units) * unit
            if max_stake is not None and add > max_stake:
                add = max_stake
            if min_stake is not None and add < min_stake:
                return None
            trade.set_custom_data("last_adjust_candle", candle_key)
            return add

        if want_units < have_units - 0.25:
            trim = (have_units - want_units) * unit
            if trim >= trade.stake_amount:
                return None  # never fully close here
            trade.set_custom_data("last_adjust_candle", candle_key)
            return -trim

        # Already at target: record the candle so we do not re-evaluate on the
        # next throttle tick within the same candle.
        trade.set_custom_data("last_adjust_candle", candle_key)
        return None
