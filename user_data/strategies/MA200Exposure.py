"""
MA200Exposure — exposure-management strategy.

Origin: quant-research-handoff/strategy/MA200Exposure-SPEC.md

    Close > MA200  ->  100% exposure
    Close < MA200  ->   50% exposure

This is a RISK-MANAGEMENT rule, not an alpha signal. The research spec is
explicit that drawdown reduction is partly MECHANICAL (proven by permutation
test) — see the placebo check in tools/ for why that matters.

Implementation notes
--------------------
Freqtrade models one trade at a time with a stake, not target weights. We map
the spec's exposure onto Freqtrade like this:

  * the initial entry always allocates HALF of the available stake -> "1 unit"
  * exposure 100% == 2 units, exposure 50% == 1 unit
  * `adjust_trade_position` adds one unit to reach 100%, or trims one unit
    to reach 50%

Holding half a unit in reserve is what makes the 50% <-> 100% transitions
possible at all; it is an implementation artefact, not part of the research
rule.

The research spec freezes these parameters and forbids tuning them:
MA200 SMA on daily close; 100%/50%; no 150/180/220/250 variants; no 75/25.
"""

from datetime import datetime

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class MA200Exposure(IStrategy):
    INTERFACE_VERSION = 3

    # --- frozen research parameters (do not tune) ---
    ma_period: int = 200
    exposure_risk_on: float = 1.00
    exposure_risk_off: float = 0.50

    timeframe = "1d"
    can_short = False

    # Exposure management has no per-trade stop by design: the research rule is
    # a state mapping, not a path-dependent exit. Kept wide so it stays inert.
    stoploss = -0.99
    trailing_stop = False

    # Never take profit: the position is only ever resized, not closed.
    minimal_roi = {"0": 1000}
    use_exit_signal = False

    process_only_new_candles = True
    position_adjustment_enable = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ma200"] = dataframe["close"].rolling(
            self.ma_period, min_periods=self.ma_period
        ).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Always want exposure. Entry only fires when flat, so this simply
        # re-establishes the position after any resize/miss.
        dataframe.loc[dataframe["ma200"].notna(), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No full exits under this rule; exposure is managed via resizing.
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
        """Allocate one unit at entry, where 1 unit == 50% exposure.

        100% exposure is therefore 2 units, so half the available stake is
        held in reserve for the 50% -> 100% transition.
        """
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
        """Resize between 50% and 100% exposure based on Close vs MA200."""
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None

        last = dataframe.iloc[-1]
        ma200 = last["ma200"]
        if ma200 != ma200:  # NaN guard: not enough history yet
            return None

        close = last["close"]

        unit = trade.get_custom_data("unit")
        if unit is None:
            # First adjustment call: stake is still exactly one unit.
            unit = trade.stake_amount
            trade.set_custom_data("unit", unit)

        if unit <= 0:
            return None

        # Express everything in "units", where 1 unit == exposure_risk_off (50%).
        target_exposure = (
            self.exposure_risk_on if close > ma200 else self.exposure_risk_off
        )
        want_units = target_exposure / self.exposure_risk_off
        have_units = trade.stake_amount / unit

        # Dead-band to avoid churning on tiny float drift.
        if want_units > have_units + 0.25:
            add = (want_units - have_units) * unit
            if max_stake is not None and add > max_stake:
                add = max_stake
            if min_stake is not None and add < min_stake:
                return None
            return add

        if want_units < have_units - 0.25:
            trim = (have_units - want_units) * unit
            if trim >= trade.stake_amount:
                return None  # never fully close here
            return -trim

        return None
