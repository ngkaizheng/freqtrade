"""B-1: THE BULL-MARKET BOOK. Long side, same frozen risk architecture.

WHY THIS FILE IS NOT "THE DELIVERED STRATEGY FLIPPED"
------------------------------------------------------
Two long variants of the delivered signal are ALREADY MEASURED and already closed, and
this file does not pretend otherwise:

* `PerpShort4h.py:239-242` states it in the source: *"SHORT ONLY. The long leg is
  net-negative in all 12 cells of the wide panel and all 3 cost regimes
  (WIDE_PANEL_RESULT.md §3)"*.
* `PerpShort4hSwitch` added a regime-switched long leg and produced **-44.5 % in 2023**,
  the year the panel rose **+198.6 %** - worse than the bleed it was built to fix.

So "flip the side" is not an open question, it is a closed one, and this strategy is
built to answer a DIFFERENT question: **is a long book on the deployed universe viable at
all once it carries the delivered book's risk architecture - the 4xATR stop, the 0.5 % risk
fraction and the drawdown breaker?**

The breaker matters more on the long side than on the short one, and the reason is in the
regime calendar this project just measured:

    panel buy-and-hold 2023-01 .. 2026-08 : +116.5 % total, -80.4 % peak-to-trough
    4h bars where the panel made money     : 51.7 %

A long book is levered to a market that ends up roughly flat after an 80 % round trip.
The short book does not pay that, because it is not long. **So the whole question for the
long side is whether risk control can be had without giving the upside back.**

WHAT IS INHERITED, AND WHY INHERITING IS THE POINT
-------------------------------------------------
`PerpShort4hDeploy` -> `PerpShort4hStop` -> `PerpShort4h` carry the 4xATR entry stop
(§16a: the one that is verified per trade at 0.40 % tolerance over 383 stop exits), the
2R target, the 42-bar time stop, the 0.5 % risk sizing, the 24-slot cap, the lazy one-shot
breaker init (trap 5) and the swallowed-exception guard (trap 6). Re-using all of it means
the ONLY variable under test is the side and the entry condition.

**The breaker is the untested part.** It ships enabled at `breaker_max_dd` and the project
has never measured what it does on EITHER side. It is read from config so a sweep changes
one number.

Run (see docs-myself/PREREG_BULL_2026-09-30.md):
    freqtrade backtesting --strategy PerpLong4h --config <cfg with side + breaker_max_dd>
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (os.path.join(os.path.dirname(_HERE), "strategies_frontier"), _HERE):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from freqtrade.persistence import Trade  # noqa: E402
from freqtrade.strategy import IStrategy, timeframe_to_prev_date  # noqa: E402
from PerpShort4hDeploy import PerpShort4hDeploy  # noqa: E402

import logging  # noqa: E402

logger = logging.getLogger(__name__)


class PerpLong4h(PerpShort4hDeploy):
    """The delivered book with the side inverted. Nothing else is changed."""

    # `side` is read from the config: "long" mirrors the frozen breakout, "panel" goes long
    # the market with the same risk architecture, and "off" is a control that must reproduce
    # the deployed book exactly.
    side: str = "long"
    # The panel trend length for `side="panel"`, in bars. 365 4h bars ~ 61 days, which is
    # the SAME lookback the frozen signal's low-volatility filter already uses, so the two
    # halves of this book are on one clock.
    panel_trend_bars: int = 365
    # B-2 (PREREG_BULL_2026-09-30.md round 2). "fixed" = the deployed mean-reversion
    # architecture (2R target + 42-bar time stop + 4xATR fixed stop). "run" = the long-run
    # architecture the B-1 mechanism calls for: no profit target, no time stop, and a
    # chandelier stop that trails the peak.
    exit_mode: str = "fixed"
    chandelier_atr: float = 3.0

    INTERFACE_VERSION = 3

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.side = str(config.get("side", "long")).lower()
        self.exit_mode = str(config.get("exit_mode", "fixed")).lower()
        self.chandelier_atr = float(config.get("chandelier_atr", 3.0))

        # `breaker_max_dd` is a READ-ONLY PROPERTY on PerpShort4hDeploy (line 90) that
        # reads it from the config and validates it. The first version of this file
        # assigned to it and every arm died with
        #   "property 'breaker_max_dd' has no setter"
        # - five backtests, zero results, one missing `getattr`. **A subclass that
        # overwrites a parent's property needs the parent's rule, not its own copy.**
        logger.info(
            "PerpLong4h: side=%s breaker_max_dd=%.3f (the breaker is the UNTESTED part)",
            self.side, getattr(self, "breaker_max_dd", float("nan")),
        )


    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = super().populate_indicators(dataframe, metadata)
        # The frozen signal already computes prev_high/prev_low/rvol/low_vol. The mirror
        # of `shark_short` is the upside breakout; nothing about the indicator set is new.
        df["shark_long"] = (
            (df["rvol"] >= self.rvol_threshold)
            & (df["close"] > df["prev_high"])
            & df["low_vol"]
        )
        return df

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        if self.side == "off":
            # CONTROL ARM. This must reproduce the deployed short book exactly; if it does
            # not, the harness is wrong and no other arm may be read.
            dataframe.loc[dataframe["shark_short"], "enter_short"] = 1
            dataframe["enter_tag"] = np.where(dataframe["shark_short"], "shark_short", "")
            return dataframe
        if self.side == "long":
            dataframe.loc[dataframe["shark_long"], "enter_long"] = 1
            dataframe["enter_tag"] = np.where(dataframe["shark_long"], "shark_long_mirror", "")
        elif self.side == "panel":
            # Long the market, not a breakout. The per-symbol close is compared with the
            # PER-SYMBOL trailing extreme so this needs no cross-symbol data at the entry
            # decision, and the Donchian level is shifted(1) so it cannot contain the bar
            # being tested - the same causality rule the frozen signal uses (§35).
            hi = (dataframe["high"].rolling(self.panel_trend_bars,
                                            min_periods=self.panel_trend_bars)
                  .max().shift(1))
            dataframe.loc[dataframe["close"] > hi, "enter_long"] = 1
            dataframe["enter_tag"] = np.where(dataframe["close"] > hi, "panel_trend", "")
        else:
            raise ValueError(f"unknown side {self.side!r}")
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # ------------------------------------------------------------------ exits
    # ⚠ THE PARENT'S ENTIRE EXIT PATH IS SHORT-ONLY BY CONSTRUCTION, and the first
    # run of this file proved it. Three places, all of them silent:
    #
    # 1. `_anchor_stop_price` returns `open + atr_stop * atr` - ABOVE the entry. For a
    #    long the stop must be BELOW it, or the trade has no stop at all and falls
    #    back to the class backstop of -30 %.
    # 2. `custom_stoploss` guards `if ratio <= 0: return None`. For a long the ratio
    #    is negative by construction, so the guard ALWAYS fires and the long runs
    #    with a 30 % stop instead of 4xATR - a ~6x wider risk unit, silently.
    # 3. `custom_exit` computes `risk = stop - open` and only acts `if risk > 0`.
    #    For a long risk is negative, so **the 2R target never fires on a long at all.**
    #
    # The control arm (`side="off"`) is what caught this: it returned **+2.89 % on 166
    # trades** against the deployed book's **+113.74 % on 1,111**, because the first
    # version of this file overrode `custom_exit` with `if trade.is_short: return None`
    # - which suppressed the parent's 2R target AND its 42-bar time stop. **A control arm
    # that reproduces the deployed number is the only reason this was found before any
    # long result was read.**
    #
    # EVERY short path here delegates to `super()`, so `side="off"` must reproduce the
    # deployed book exactly. That is the proof the mirror is a mirror and not a rewrite.

    def _anchor_stop_price(self, pair: str, trade: Trade) -> float | None:
        if trade.is_short:
            return super()._anchor_stop_price(pair, trade)
        atr = self.entry_atr(pair, trade)
        if atr is None:
            return None
        lev = trade.leverage or 1.0
        # ⚠ `self.stop_mult`, NOT `self.atr_stop`. B-6, 2026-09-30.
        # `PerpShort4hStop` reads the config's `atr_stop` into a property called
        # `stop_mult`; `atr_stop` itself stays frozen at its class constant of 1.5.
        # The short branch below delegates to `super()`, which uses `stop_mult`, so
        # the short book got 4.0. This line used `atr_stop` and therefore got 1.5 -
        # so the long book was SIZED for a 4.0xATR stop (custom_stake_amount is
        # inherited and uses stop_mult) and STOPPED at 1.5xATR. Measured: 797 of 835
        # floor-bound stop exits sat at exactly 1.5, ZERO at the configured 4.0, and
        # realised risk was 1.5/4.0 = 37.5% of the intended 0.5% per trade.
        # The asymmetry is invisible from the return column and from a code read:
        # the short line one above and this line look interchangeable.
        return trade.open_rate * lev - self.stop_mult * atr

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs) -> float | None:
        if trade.is_short:
            return super().custom_stoploss(pair, trade, current_time, current_rate,
                                          current_profit, after_fill=after_fill, **kwargs)
        if after_fill:
            return None
        sp = self._anchor_stop_price(pair, trade)
        if sp is None or not np.isfinite(sp) or sp <= 0:
            return None
        if not np.isfinite(current_rate) or current_rate <= 0:
            return None
        lev = trade.leverage or 1.0
        if self.exit_mode != "run":
            # A long's stop must sit BELOW the price. If it does not, return None and let
            # the wide class backstop stand - deliberately loud, not silently tight.
            if sp >= current_rate:
                return None
            return -float((1.0 - sp / current_rate) * lev)

        # ---- CHANDELIER: let the winner run, but keep a measured floor ----------
        # In "run" mode the fixed 4xATR anchor is replaced by a stop trailing the highest
        # high since entry, `chandelier_atr` ATRs below it. **This is the single change
        # the B-1 mechanism calls for**: the winner keeps going, the loser is still
        # stopped at a fixed, measured distance, and the breaker still bounds the equity.
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        try:
            entry_ts = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        except (AttributeError, TypeError, ValueError):
            return None
        if entry_ts is None:
            return None
        since = df.loc[df["date"] >= entry_ts]
        if since.empty or "atr" not in since:
            return None
        peak = float(since["high"].max())
        atr_now = float(since["atr"].iloc[-1])
        if not np.isfinite(atr_now) or atr_now <= 0:
            return None
        trail = peak - self.chandelier_atr * atr_now
        # Never LOOSEN: the chandelier may only raise the stop above the initial anchor.
        if trail < sp:
            trail = sp
        # ⚠ B-5, 2026-09-30. THE STOP CAN FAIL TO BE INSTALLED AT ALL.
        # `return None` here means "leave the existing stop alone", which is right only if a
        # stop already exists. On a trade whose entry-bar move already exceeds the floor, NO
        # bar ever has a placeable stop, so the custom stop is never installed and the trade
        # rides to the class -30% backstop on a position sized for 4xATR. Measured: 1 in 993
        # (UNI, -30.00% against a next-worst of -8.14% - a stop distribution has no hole in
        # it), and after the B-6 floor fix 1 in 734 (FARTCOIN, -29.98%). The same structure
        # is on the short side at PerpShort4h.py:341 and recorded 0 occurrences in 1,111.
        #
        # When the trailing stop is already violated there is nothing to trail: exit at the
        # market. Clamping to the measured floor instead would fill at a price the market has
        # already passed and make the backtest look BETTER than reality, which is the one
        # direction this project's cost work exists to avoid.
        if trail >= current_rate:
            trail = current_rate * (1.0 - 1e-4)
        ratio = -float((1.0 - trail / current_rate) * lev)
        # ⚠ A `custom_stoploss` EXCEPTION IS SWALLOWED BY FREQTRADE AND THE ENTRY IS
        # ALLOWED THROUGH (trap 6). The first version of this chandelier raised
        # `NameError: timeframe_to_prev_date` on EVERY call, so both long arms ran
        # their entire history on the -30 % class backstop and produced a number that
        # looked like a result. The tell is not the number - it is the ERROR line in
        # the log, which the run printed thousands of times and which is exactly the
        # signal this project has been trained to stop scrolling past. Now guarded
        # explicitly, and the guard is the thing that would have caught it.
        if not np.isfinite(ratio) or ratio >= 0:
            return None
        return ratio



    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> str | None:
        if trade.is_short:
            return super().custom_exit(pair, trade, current_time, current_rate,
                                       current_profit, **kwargs)
        if self.exit_mode == "run":
            # LONG-RUN MODE. The 2R target caps the winner and the 4xATR stop cuts the
            # average long at ~32 hours (B-1, section 45d: 1,437 of 1,284 trades left
            # through the stop at mean duration 1 day 8 hours, and the 2R target never
            # fired at all). **This mode removes BOTH and keeps only the breaker.**
            # It is the direct test of the mechanism B-1 handed over.
            return None
        sp = self._anchor_stop_price(pair, trade)

        if sp is not None and np.isfinite(sp) and 0 < sp < trade.open_rate * (trade.leverage or 1.0):
            lev = trade.leverage or 1.0
            open_price = trade.open_rate * lev
            risk = open_price - sp                      # positive for a long
            if risk > 0:
                target = open_price + self.target_r * risk
                if current_rate >= target:
                    return "target_2r"
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None

