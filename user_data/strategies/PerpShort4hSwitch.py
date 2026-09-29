"""Direction switch: the same signal, long or short by the PANEL's own trend.

WHY
---
`PerpShort4hDeploy` is structurally short-only, and 2023 cost it **-40.5%** in a
year when the panel rose **+50.7% annualised**. A user running it through a
crypto bull market watches it bleed for quarters. That is a defect in the
product rather than a market risk to accept, because the same signal machinery
exists on the long side.

The regime is READ, not predicted: `panel close > its own 200-bar SMA`
(~33 days). This is NOT the closed `btc_regime_filter` line - that FILTERED a
fixed-direction book and was tested by Hurst/Ooi/Pedersen (2017, JPM), which
found prospective regime TIMING null. This CHOOSES the direction, which is a
different object and is not decided by that result.

    `tools/perp_short/make_regime.py` writes the series and prints whether it
    separates at all. On this panel it does, and asymmetrically:

        up-regime    forward 7d  +0.011%   t = +0.15
        down-regime  forward 7d  -0.232%   t = -4.08

    **The up-regime is weak and the down-regime is strong.** So the honest
    prediction from the regime alone is that this ADDS a mediocre long leg to a
    good short leg. If the long leg turns out to add nothing, the right answer
    is to keep the short-only book and say so - not to tune the window.

WHAT IS FROZEN
---------------
Entry signal, 4.0xATR stop at the entry bar, 2R target, 42-bar time stop, 1x,
1% risk, 24 slots, the circuit breaker, and the measured costs are all inherited
UNCHANGED from `PerpShort4hDeploy`. Only the direction varies, by the one rule
in `docs-myself/PREREG_DIRECTION_SWITCH_2026-09-28.md`. The regime window is
not searched, here or later.

THE JOIN IS ON TIMESTAMP, NEVER ON ROW POSITION
-----------------------------------------------
A global series joined onto per-symbol frames by position is wrong the moment
one symbol's history starts or ends at a different bar - and wrong SILENTLY,
producing a plausible-looking strategy that is a different one. Every lookup
here is by UTC timestamp, and the strategy asserts the join produced values.

Run:
    freqtrade backtesting --config user_data\\config_perp_switch.json \\
        --datadir user_data\\data\\wide104 --timerange 20230101-20260928
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies"))

from freqtrade.persistence import Trade  # noqa: E402

from PerpShort4hDeploy import PerpShort4hDeploy  # noqa: E402

REGIME_CSV = "user_data/perp_short_out/panel_regime.csv"


class PerpShort4hSwitch(PerpShort4hDeploy):
    """Frozen signal + exit + sizing; direction chosen by the panel regime."""

    _regime: dict | None = None

    @classmethod
    def regime_map(cls) -> dict:
        """timestamp (ns) -> 0/1. Loaded once per process, never per pair."""
        if cls._regime is None:
            if not os.path.exists(REGIME_CSV):
                raise FileNotFoundError(
                    f"{REGIME_CSV} is missing. Run tools/perp_short/make_regime.py "
                    f"first. Substituting a per-pair proxy here would silently "
                    f"turn a PANEL rule into a per-asset rule, which is a "
                    f"different strategy.")
            d = pd.read_csv(REGIME_CSV)
            ts = pd.to_datetime(d["date"], utc=True)
            cls._regime = {int(t.value): int(r) if r == r else None
                           for t, r in zip(ts, d["regime"])}
        return cls._regime

    def populate_indicators(self, dataframe, metadata: dict):
        df = super().populate_indicators(dataframe, metadata)
        reg = self.regime_map()
        dates = pd.to_datetime(df["date"], utc=True)
        r = np.array([reg.get(int(t.value)) for t in dates], dtype=float)
        df["panel_regime"] = r
        # `shark_long` is the SAME rule as `shark_short`, reflected: it needs the
        # breakdown replaced by a breakout, so it is written out explicitly
        # rather than inverted, because inverting a mask of NaN-unfriendly
        # columns silently produces True where the data is missing.
        df["shark_long"] = ((df["rvol"] >= self.rvol_threshold)
                            & (df["close"] > df["prev_high"])
                            & df["low_vol"])
        return df

    def populate_entry_trend(self, dataframe, metadata: dict):
        r = dataframe["panel_regime"]
        if r.notna().sum() == 0:
            raise ValueError(
                "the panel regime joined to zero bars. That is a join failure, "
                "not a strategy that declines to trade - refuse rather than "
                "produce a book with no regime at all.")
        long_on = (dataframe["shark_long"] & (r == 1)).fillna(False)
        short_on = (dataframe["shark_short"] & (r == 0)).fillna(False)
        dataframe["enter_long"] = long_on.astype(int)
        dataframe["enter_short"] = short_on.astype(int)
        dataframe["enter_tag"] = np.where(long_on, "panel_up_breakout",
                                          np.where(short_on,
                                                   "panel_down_breakout", ""))
        return dataframe
