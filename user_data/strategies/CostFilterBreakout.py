"""
CostFilterBreakout -- PerpTrendBreakout + ONE entry filter, nothing else changed.

Pre-registration: docs-myself/PREREG_COST_FILTER_2026-09-27.md

The filter is mechanical, not fitted:

    atr / close  >=  cost_k * round_trip_cost

Rationale: a trade can only pay for itself if the move it can capture is large
relative to what the round trip costs. `atr/close` proxies the capturable move;
`round_trip_cost` is the real cost. Both sides are prior quantities -- no
parameter here was chosen by looking at returns.

cost_k is read from the config so every pre-registered level is run without
editing code. cost_k = 0 disables the filter and reproduces the parent exactly.

Everything else -- timeframe, 1h regime filter, breakout window, volume filter,
ATR stop, exits, leverage -- is inherited untouched.
"""

from pandas import DataFrame

from PerpTrendBreakout import PerpTrendBreakout


class CostFilterBreakout(PerpTrendBreakout):
    """PerpTrendBreakout with a cost-aware entry filter bolted on."""

    # 2 x 0.05% taker, i.e. the round trip in units of notional.
    round_trip_cost = 0.0010

    def _cost_k(self) -> float:
        try:
            return float(self.config.get("cost_k", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)

        k = self._cost_k()
        if k <= 0:
            return dataframe  # baseline: identical to the parent

        atr_frac = dataframe["atr"] / dataframe["close"]
        # `atr` is already computed on completed candles only by talib; using the
        # same row is consistent with how the parent sizes its stop.
        passes = atr_frac >= (k * self.round_trip_cost)

        for col in ("enter_long", "enter_short"):
            if col in dataframe.columns:
                dataframe.loc[~passes, col] = 0
        if "enter_tag" in dataframe.columns:
            dataframe.loc[~passes, "enter_tag"] = ""

        return dataframe
