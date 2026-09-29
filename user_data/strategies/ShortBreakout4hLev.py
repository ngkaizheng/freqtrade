# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import logging

import numpy as np
import pandas as pd
from datetime import datetime
from pandas import DataFrame
from typing import Optional

from freqtrade.strategy import IStrategy

# --------------------------------
import talib.abstract as ta  # noqa: F401

logger = logging.getLogger(__name__)


class ShortBreakout4hLev(IStrategy):
    """
    SHARK-01 frozen rule on 4h Binance USD-M perps, SHORT side only, with an
    EXPLICIT ``leverage()`` callback so a leverage matrix is actually measured.

    WHY A SEPARATE FILE (this is the point of the file)
    ---------------------------------------------------
    ``ShortBreakout4h.py`` has NO ``leverage()`` callback. A bare
    ``perp_leverage`` key in the config is read by the *live* bot, but in
    backtesting the per-pair leverage comes from the strategy callback /
    leverage tiers. Without a callback there is nothing that guarantees the
    run is at 2x rather than silently at 1x. The whole matrix is meaningless
    if the leverage knob is a no-op, so the knob is made explicit here and
    every run asserts what it actually used.

    THE RULE IS UNCHANGED from ``ShortBreakout4h.py`` — same code path, same
    numbers, so the two files are directly comparable:

        relative volume >= 2.0 over a 20-bar SMA
        20-bar Donchian breakout, SHORT side only (close < prev 20-bar low)
        low-vol regime: trailing 42-bar vol < its median over 365 bars
        stop  = fixed -3.6% (the panel's median 1.5x ATR%)
        target= 2R measured off the adaptive ATR
        time stop = 42 bars (~7 days)

    STATED APPROXIMATIONS (inherited, not new)
      * the stop is a FIXED -0.036 rather than per-bar adaptive ATR. Two
        attempts at adaptive ``custom_stoploss`` in this repo produced
        confident wrong answers (a ratchet, then a -50% default).
      * funding IS modelled here, but only if funding/mark data is on disk;
        ``fail_without_data=True`` means a missing feed aborts the run rather
        than silently scoring funding as zero. Do not "fix" that by adding
        data for only some symbols.
    """

    INTERFACE_VERSION = 3

    timeframe = "4h"
    timeframe_min = 240

    can_short: bool = True

    minimal_roi = {"0": 100}

    # panel median 1.5 x ATR% (measured on these 24 symbols:
    # min 1.47% / median 3.61% / max 5.04%)
    stoploss = -0.036

    trailing_stop = False

    process_only_new_candles = False

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # vol42 (42) + a 365-bar median needing 120 min_periods, plus 20 for the
    # breakout/rvol -> 420 is the true requirement.
    startup_candle_count: int = 420

    rvol_period = 20
    rvol_threshold = 2.0
    breakout_period = 20
    atr_stop = 1.5
    target_r = 2.0
    time_stop_bars = 42
    vol_lookback = 42
    vol_med_window = 365

    # every leverage the matrix is allowed to request
    ALLOWED_LEVERAGES = (1.0, 2.0, 5.0, 10.0, 20.0)
    default_leverage = 1.0

    # THE STOP IS DEFINED IN PRICE TERMS AND HELD THERE.
    #
    # Freqtrade's `stoploss` is a MARGIN stop: trade_model.adjust_stop_loss
    # converts it to a stop PRICE by dividing by leverage
    # (`current_price * (1 ± abs(stoploss / leverage))`). So a flat -0.036 is
    # a 3.6% price stop at 1x but only 0.18% at 20x -- verified against the
    # exported fills, which match the formula to six decimals.
    #
    # A first pass of this matrix left `stoploss = -0.036` flat and produced
    # -63% at 20x with 89% of trades stopped on their entry bar. That was not
    # a leverage result, it was a 0.18% stop on a 4h candle. Scaling the
    # margin stop by the leverage keeps the frozen 3.6% PRICE stop intact, so
    # every cell tests the same rule and leverage only changes how much
    # margin is at risk.
    price_stop = 0.036

    # bookkeeping so the caller can assert what the run actually used
    leverage_requests: list = []
    effective_stoploss: float | None = None

    def bot_start(self, *args, **kwargs):
        """Fail loudly if the configured leverage is not one the matrix allows,
        and pin the margin stop so the PRICE stop stays at `price_stop`.
        """
        requested = self.config.get("perp_leverage", self.default_leverage)
        try:
            requested = float(requested)
        except (TypeError, ValueError):
            raise ValueError(
                f"perp_leverage is not a number: {requested!r}. The matrix is "
                f"1/2/5/10/20x only."
            )
        if requested not in self.ALLOWED_LEVERAGES:
            raise ValueError(
                f"perp_leverage={requested} is not in the frozen matrix "
                f"{self.ALLOWED_LEVERAGES}. Refusing to run an unlabelled cell."
            )
        self.stoploss = -self.price_stop * requested
        self.effective_stoploss = self.stoploss
        self.leverage_requests = []
        logger.info(
            "ShortBreakout4hLev: cell=%sx, margin stop=%.4f, "
            "price stop=%.4f%% (held constant across the matrix)",
            requested, self.stoploss, 100 * self.price_stop,
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
        """Return the configured matrix leverage, clamped to what the exchange
        allows. Records every call so a no-op knob is visible in the logs.
        """
        try:
            requested = float(self.config.get("perp_leverage", self.default_leverage))
        except (TypeError, ValueError):
            requested = self.default_leverage
        used = max(1.0, min(requested, max_leverage))
        if used != requested:
            # Not fatal, but the cell is then NOT the requested leverage and
            # the result must not be filed under it.
            logger.warning(
                "%s: requested %sx but max_leverage is %sx -> actually using %sx. "
                "This cell is NOT %sx.",
                pair, requested, max_leverage, used, requested,
            )
        self.leverage_requests.append((pair, requested, max_leverage, used))
        return used

    # ------------------------------------------------------------------
    # Frozen rule (docs-myself/PREREG_WIDE_PANEL_2026-09-27.md)
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """ATR(14), relative volume(20), 20-bar Donchian, frozen low-vol filter.

        The breakout levels EXCLUDE the current bar (shift(1)) and the
        volatility median is shifted(1), so nothing reads the bar it decides.
        The relative-volume average INCLUDES the current bar, which is causal
        because that bar's volume is complete at its close; this matches the
        shark engine's convention exactly.
        """
        df = dataframe.copy()

        prev_close = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = tr.ewm(alpha=1.0 / 14.0, adjust=False,
                           min_periods=14).mean()

        vol = df["volume"].clip(lower=0.0)
        df["volume_sma"] = vol.rolling(self.rvol_period,
                                       min_periods=self.rvol_period).mean()
        df["rvol"] = vol / df["volume_sma"].replace(0.0, np.nan)

        df["prev_high"] = df["high"].rolling(self.breakout_period,
                                             min_periods=self.breakout_period
                                             ).max().shift(1)
        df["prev_low"] = df["low"].rolling(self.breakout_period,
                                           min_periods=self.breakout_period
                                           ).min().shift(1)

        lr = np.log(df["close"]).diff()
        df["vol42"] = lr.rolling(self.vol_lookback,
                                 min_periods=self.vol_lookback).std()
        df["vol42_med"] = df["vol42"].rolling(
            self.vol_med_window, min_periods=120).median().shift(1)
        df["low_vol"] = (df["vol42"] < df["vol42_med"]).fillna(False)

        df["shark_short"] = ((df["rvol"] >= self.rvol_threshold)
                             & (df["close"] < df["prev_low"])
                             & df["low_vol"])
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict
                             ) -> DataFrame:
        """SHORT only. The long leg is net-negative in every cell and every
        cost regime of the wide-panel run.

        Conditions are evaluated on the signal candle's close; freqtrade fills
        at the next candle's open, matching the shark engine's convention.
        """
        dataframe.loc[dataframe["shark_short"],
                       ["enter_long", "enter_short"]] = (0, 1)
        dataframe.loc[~dataframe["shark_short"],
                       ["enter_long", "enter_short"]] = (0, 0)
        dataframe["enter_tag"] = np.where(dataframe["shark_short"],
                                          "shark_short", "")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict
                            ) -> DataFrame:
        """No signal exit: the 2R target and the time stop are rule-based."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def custom_exit(self, pair: str, trade, current_time, current_rate: float,
                    current_profit: float, **kwargs) -> Optional[str]:
        """2R target, else a 42-bar (~7 day) time stop."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(df) < 2:
            return None
        atr = df["atr"].iloc[-1]
        if np.isfinite(atr) and atr > 0:
            target = trade.open_rate - self.target_r * self.atr_stop * atr
            if current_rate <= target:
                return "target_2r"
        # SECONDS PER BAR = timeframe_min * 60 (4h -> 14400). Dividing by 240
        # (seconds per HOUR) reads one 4h bar as 60 bars and force-exits ~85%
        # of trades on their entry bar. That bug cost -31.72% once already.
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None
