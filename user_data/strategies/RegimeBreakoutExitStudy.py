"""
RegimeBreakoutExitStudy — PRE-REGISTERED EXIT-FAMILY STUDY.

Protocol: docs-myself/PREREG_EXIT_FAMILY_2026-09-27.md (frozen 2026-09-27,
BEFORE any arm of this study was run).

WHAT IS FROZEN
--------------
The entry, byte-for-byte from RegimeVolBreakout5m: the 1h EMA50/200 + ADX
regime, the 5m EMA21/55 trend filter, the 24-bar Donchian breakout with
shift(1), volume_expansion (1.30x), vol_expansion (1.05x), ADX > 18, the RSI
bands, body_atr >= 0.30, volume > 0, and the data_valid guard.

No entry parameter is tuned here or in any arm. That is what makes the arms a
PAIRED design: every arm trades the same entries, so the arms differ only in
how a trade is ended.

WHAT IS VARIED
--------------
The exit only, selected by the `exit_arm` config key (X0..X5), following the
`perp_leverage` convention already used elsewhere in this repo.

ARM TABLE (see the preregistration for the rationale)
-----------------
X0  control: 3xATR re-anchored trail + 0.9% static backstop + 1.8% target
             + 90-min time stop + ema21/ema50_1h exit signal.
    Reproduces RegimeVolBreakout5m exactly.
X1  1.5xATR frozen at entry, 3R target,  90 min, exit signal ON.
X2  1.5xATR frozen at entry, 3R target, 180 min, exit signal ON.
X3  2.5xATR frozen at entry, 2R target, 180 min, exit signal ON.
X4  2.5xATR frozen at entry, 2R target, 180 min, exit signal OFF.
X5  no stop, no target, fixed 18-bar (90 min) hold, exit signal OFF.

THE FROZEN-STOP DETAIL THAT MATTERS
-----------------------------------
`LocalTrade.adjust_stop_loss` computes the stop as
`current_price * (1 - |ratio| / leverage)` -- from the CURRENT price, not the
entry. So passing a constant stoploss RATIO yields a stop that trails the price
down, which is a trailing stop, not a frozen one. A frozen stop therefore has to
be expressed as an absolute PRICE and converted per bar via
`stoploss_from_absolute`, which is what `frozen_stop_price` does below.

Related and already paid for in this repo: `stoploss` is a fraction of the
LEVERAGED profit ratio and is divided by leverage, so a flat `stoploss` is a
MARGIN stop. This strategy is pinned at 1x by `leverage()`, so the two coincide
and the R unit is a price distance. That is why R is defined on price here, and
why the preregistration forbids any leverage arm from being added later without
re-deriving R.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_absolute


# arm -> exit specification. Frozen in the preregistration; do not add keys.
ARMS: dict[str, dict] = {
    # stop_atr : ATR multiple frozen at entry, or None for no custom stop
    # trail     : re-anchor the stop to the latest price every bar (X0 only)
    # target_r  : take-profit in R units, or None for no target
    # time_min  : time stop in minutes
    # sig_on    : use populate_exit_trend's ema21 / ema50_1h signal
    # r_atr     : ATR multiple used to DEFINE the R unit for this arm
    "X0": dict(stop_atr=None, trail=True, target_r=None, time_min=90,
               sig_on=True, r_atr=3.0, backstop=-0.009, fixed_target_pct=0.018),
    "X1": dict(stop_atr=1.5, trail=False, target_r=3.0, time_min=90,
               sig_on=True, r_atr=1.5, backstop=-0.10, fixed_target_pct=None),
    "X2": dict(stop_atr=1.5, trail=False, target_r=3.0, time_min=180,
               sig_on=True, r_atr=1.5, backstop=-0.10, fixed_target_pct=None),
    "X3": dict(stop_atr=2.5, trail=False, target_r=2.0, time_min=180,
               sig_on=True, r_atr=2.5, backstop=-0.10, fixed_target_pct=None),
    "X4": dict(stop_atr=2.5, trail=False, target_r=2.0, time_min=180,
               sig_on=False, r_atr=2.5, backstop=-0.10, fixed_target_pct=None),
    "X5": dict(stop_atr=None, trail=False, target_r=None, time_min=90,
               sig_on=False, r_atr=1.5, backstop=-0.10, fixed_target_pct=None),
}

# R unit floor, from the preregistration: a dead-volatility bar must not be able
# to produce an absurdly large R.
R_FLOOR = 0.002


class RegimeBreakoutExitStudy(IStrategy):
    """Exit-family study on a frozen RegimeVolBreakout5m entry."""

    INTERFACE_VERSION = 3

    timeframe = "5m"
    startup_candle_count = 400

    can_short = True

    use_exit_signal = True
    use_custom_stoploss = True

    # use_exit_signal MUST stay True on every arm.
    #
    # IStrategy._get_exit_trade_type (interface.py:1469) evaluates custom_exit
    # ONLY inside `if self.use_exit_signal:`. Setting it False to disable the
    # ema exit signal therefore also disables the take-profit and the time stop,
    # leaving the stoploss as the only exit. That produced a first X4 run of
    # 8 trades in 312 days, which is a dead study, not a finding.
    #
    # The correct switch is to make populate_exit_trend emit ZEROS for the
    # sig_off arms, so exit_ is None and control falls through to custom_exit.
    # The arms that need sig_off are X4 and X5.

    # Wide backstop. Per-arm backstops are applied in bot_start(); this value is
    # only a safety net if bot_start is bypassed. At 5m an 18-bar hold cannot
    # reach -10%, so for X5 (no stop by design) this is inert.
    stoploss = -0.10

    minimal_roi = {"0": 100.0}

    # --- frozen entry constants (identical to RegimeVolBreakout5m) -------------
    BREAKOUT_LOOKBACK = 24
    VOLUME_LOOKBACK = 30
    ATR_PERIOD = 14
    ATR_BASELINE = 96
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

    # X0's momentum-failure exit threshold, from the baseline.
    X0_MOMENTUM_MIN = 0.008

    arm: str = "X0"

    # ------------------------------------------------------------------ setup
    def bot_start(self, **kwargs) -> None:
        arm = str(self.config.get("exit_arm", "X0")).upper()
        if arm not in ARMS:
            raise ValueError(
                f"exit_arm={arm!r} is not a registered arm. "
                f"Registered: {sorted(ARMS)}. See PREREG_EXIT_FAMILY_2026-09-27.md."
            )
        self.arm = arm
        spec = ARMS[arm]
        # Per-arm backstop. X0 reproduces the baseline's -0.009; the frozen-ATR
        # arms need a backstop WIDER than their own stop or it would bind first.
        self.stoploss = spec["backstop"]
        # Deliberately NOT set from spec["sig_on"] -- see the class-attribute
        # comment. sig_off arms are handled in populate_exit_trend instead.
        self.use_exit_signal = True

    # ------------------------------------------------------- frozen entry code
    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST)
        dataframe["ema_55"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.ATR_PERIOD)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        dataframe["atr_pct_baseline"] = (
            dataframe["atr_pct"].rolling(self.ATR_BASELINE).median().shift(1)
        )
        dataframe["vol_expansion"] = (
            dataframe["atr_pct"]
            > dataframe["atr_pct_baseline"] * self.ATR_EXPANSION_MULTIPLIER
        )
        dataframe["volume_mean"] = (
            dataframe["volume"].rolling(self.VOLUME_LOOKBACK).mean().shift(1)
        )
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean"]
        dataframe["volume_expansion"] = dataframe["volume_ratio"] > self.VOLUME_MULTIPLIER

        # shift(1): the current candle must not define its own breakout level.
        dataframe["breakout_high"] = (
            dataframe["high"].shift(1).rolling(self.BREAKOUT_LOOKBACK).max()
        )
        dataframe["breakout_low"] = (
            dataframe["low"].shift(1).rolling(self.BREAKOUT_LOOKBACK).min()
        )
        dataframe["breakout_long"] = dataframe["close"] > dataframe["breakout_high"]
        dataframe["breakout_short"] = dataframe["close"] < dataframe["breakout_low"]

        dataframe["body"] = (dataframe["close"] - dataframe["open"]).abs()
        dataframe["body_atr"] = dataframe["body"] / dataframe["atr"]

        dataframe["regime_long"] = (
            (dataframe["close_1h"] > dataframe["ema_50_1h"])
            & (dataframe["ema_50_1h"] > dataframe["ema_200_1h"])
            & (dataframe["adx_1h"] > 15)
        )
        dataframe["regime_short"] = (
            (dataframe["close_1h"] < dataframe["ema_50_1h"])
            & (dataframe["ema_50_1h"] < dataframe["ema_200_1h"])
            & (dataframe["adx_1h"] > 15)
        )
        dataframe["trend_long"] = dataframe["ema_21"] > dataframe["ema_55"]
        dataframe["trend_short"] = dataframe["ema_21"] < dataframe["ema_55"]

        # A guard that can only ever be True if its inputs are present. Built
        # from | on boolean columns rather than &= from an all-False seed, so a
        # missing column or a dtype slip cannot silently produce all-False
        # (AGENTS.md §3).
        guards = [
            dataframe["volume"].notna(),
            dataframe["atr"].notna(),
            dataframe["atr_pct_baseline"].notna(),
            dataframe["volume_mean"].notna(),
            dataframe["breakout_high"].notna(),
            dataframe["breakout_low"].notna(),
            dataframe["ema_200_1h"].notna(),
        ]
        data_valid = guards[0]
        for g in guards[1:]:
            data_valid = data_valid | g
        dataframe["data_valid"] = data_valid
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        common = (
            dataframe["data_valid"]
            & dataframe["volume_expansion"]
            & dataframe["vol_expansion"]
            & (dataframe["adx"] > self.ADX_MIN)
            & (dataframe["body_atr"] >= self.MIN_BODY_ATR)
            & (dataframe["volume"] > 0)
        )

        long_condition = (
            common
            & dataframe["regime_long"]
            & dataframe["trend_long"]
            & dataframe["breakout_long"]
            & (dataframe["rsi"] >= self.LONG_RSI_MIN)
            & (dataframe["rsi"] <= self.LONG_RSI_MAX)
        )
        dataframe.loc[long_condition, "enter_long"] = 1
        dataframe.loc[long_condition, "enter_tag"] = "regime_breakout_long"

        short_condition = (
            common
            & dataframe["regime_short"]
            & dataframe["trend_short"]
            & dataframe["breakout_short"]
            & (dataframe["rsi"] >= self.SHORT_RSI_MIN)
            & (dataframe["rsi"] <= self.SHORT_RSI_MAX)
        )
        dataframe.loc[short_condition, "enter_short"] = 1
        dataframe.loc[short_condition, "enter_tag"] = "regime_breakout_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        if not ARMS[self.arm]["sig_on"]:
            # Leave both at zero. use_exit_signal stays True so that custom_exit
            # (target + time stop) is still evaluated -- see interface.py:1469.
            return dataframe
        dataframe.loc[dataframe["close"] < dataframe["ema_21"], "exit_long"] = 1
        dataframe.loc[dataframe["close"] < dataframe["ema_50_1h"], "exit_long"] = 1
        dataframe.loc[dataframe["close"] > dataframe["ema_21"], "exit_short"] = 1
        dataframe.loc[dataframe["close"] > dataframe["ema_50_1h"], "exit_short"] = 1
        return dataframe

    # ------------------------------------------------------------- R machinery
    def entry_atr(self, pair: str, trade: Trade) -> Optional[float]:
        """ATR frozen at the ENTRY bar.

        TIMEFRAME FLOOR TRAP, PAID FOR 2026-09-27.
        `pd.Timestamp.floor("5m")` RAISES ValueError on pandas 3.0.5 --
        "'m' is no longer supported" (ambiguous: minutes vs milliseconds). Only
        "5min" parses. ShortBreakout4h floors on "4h" and never hit this, so a
        5m strategy must not copy that call.

        The first version of this study did copy it, and the consequences were
        silent and total:
          * the ValueError was caught by a local `except` -> entry_atr -> None
          * frozen_stop_price -> None -> custom_stoploss -> None
          * freqtrade's strategy_safe_wrapper(..., supress_error=True) hid the
            rest
          * the frozen stop was therefore NEVER set and every arm silently ran
            on the -10% backstop, with the R target also disabled because
            r_unit() calls this same function.
        Three layers of silence around one bug, and the backtest still printed a
        confident table. Hence the explicit failure below and the assert in
        tools/verify_exit_study.py, which checks the realised stop distance.

        Uses freqtrade's own timeframe_to_prev_date, which is the canonical
        helper and parses "5m" correctly.
        """
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) < 2:
            return None
        try:
            entry_ts = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        except (AttributeError, TypeError, ValueError) as e:
            # A bad open_date_utc is a data problem and may degrade to None.
            # A bad TIMEFRAME is a code problem and must never be silent.
            if "Invalid frequency" in str(e) or "timeframe" in str(e).lower():
                raise
            return None
        at_entry = df.loc[df["date"] == entry_ts, "atr"]
        v = float(at_entry.iloc[-1]) if len(at_entry) else float(df["atr"].iloc[0])
        return v if np.isfinite(v) and v > 0 else None

    def r_unit(self, pair: str, trade: Trade) -> Optional[float]:
        """R as a FRACTION of price: |entry - stop| / entry, floored at R_FLOOR.

        Returned as a fraction (e.g. 0.005) so it can be compared across arms
        whose price risk differs by design.
        """
        atr = self.entry_atr(pair, trade)
        if atr is None:
            return None
        spec = ARMS[self.arm]
        width = spec["r_atr"] * atr
        frac = width / trade.open_rate if trade.open_rate else None
        if frac is None or not np.isfinite(frac):
            return None
        return max(frac, R_FLOOR)

    def frozen_stop_price(self, pair: str, trade: Trade, current_rate: float) -> Optional[float]:
        """Absolute stop price, FROZEN at the entry bar's ATR."""
        atr = self.entry_atr(pair, trade)
        if atr is None:
            return None
        width = ARMS[self.arm]["stop_atr"] * atr
        if trade.is_short:
            return trade.open_rate + width
        return trade.open_rate - width

    # ------------------------------------------------------------------ exits
    def custom_stoploss(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, after_fill: bool, **kwargs,
    ) -> Optional[float]:
        spec = ARMS[self.arm]
        if not spec["trail"]:
            if spec["stop_atr"] is None:
                return None  # X5: no custom stop
            stop_price = self.frozen_stop_price(pair, trade, current_rate)
            if stop_price is None:
                return None
            return stoploss_from_absolute(
                stop_price, current_rate=current_rate,
                is_short=trade.is_short, leverage=trade.leverage,
            )

        # X0 control: re-anchor 3xATR to the latest price every bar.
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        atr = float(df["atr"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0:
            return None
        width = 3.0 * atr
        stop_price = current_rate + width if trade.is_short else current_rate - width
        return stoploss_from_absolute(
            stop_price, current_rate=current_rate,
            is_short=trade.is_short, leverage=trade.leverage,
        )

    def custom_exit(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, **kwargs,
    ) -> Optional[str]:
        spec = ARMS[self.arm]
        # Unleveraged price movement, not current_profit.
        price_move = (
            (trade.open_rate / current_rate) - 1.0
            if trade.is_short
            else (current_rate / trade.open_rate) - 1.0
        )

        if spec["fixed_target_pct"] is not None:
            # X0 reproduces the baseline's +1.8% unleveraged target.
            if price_move >= spec["fixed_target_pct"]:
                return "tp_1_8pct"
        elif spec["target_r"] is not None:
            r_frac = self.r_unit(pair, trade)
            if r_frac is not None and price_move >= spec["target_r"] * r_frac:
                return f"tp_{spec['target_r']:.0f}R"

        if spec["trail"] and price_move >= self.X0_MOMENTUM_MIN:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                failed = (
                    last["close"] > last["ema_21"]
                    if trade.is_short
                    else last["close"] < last["ema_21"]
                )
                if failed:
                    return "profit_momentum_failure"

        held = (current_time - trade.open_date_utc).total_seconds() / 60.0
        if held >= spec["time_min"]:
            return "time_stop"
        return None

    def leverage(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_leverage: float, max_leverage: float,
        entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        return min(1.0, max_leverage)
