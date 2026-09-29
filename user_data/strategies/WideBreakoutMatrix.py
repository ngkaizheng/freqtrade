"""Frozen 4h low-volatility breakout for a Freqtrade side/leverage matrix.

This is a new execution wrapper around the already-registered WIDE_PANEL rule,
not a new signal search. It keeps the short leg and adds a long-side diagnostic
plus an explicit leverage callback so config values cannot silently remain 1x.

Rule basis: docs-myself/PREREG_WIDE_PANEL_2026-09-27.md
  - 4h SHARK-01: relative volume >= 2 over 20 bars, 20-bar Donchian breakout
  - low-vol filter: trailing 42-bar return volatility below its shifted
    trailing-365-bar median
  - fixed 3.6% underlying stop (Freqtrade port approximation of 1.5 ATR median)
  - 2R target and 42-bar time exit

Caveat: ShortBreakout4h's Freqtrade port measures the 2R target using the latest
ATR at exit, while the source engine anchors risk to entry ATR. This wrapper
preserves that existing cross-engine approximation; do not treat the result as
an exact replication. Funding must be downloaded for every pair before scoring.

FIXED 2026-09-27 — the leverage matrix originally measured the wrong thing. The
`stoploss` of -0.036 is a PRICE distance (the panel's median 1.5 x ATR%), but
Freqtrade expresses `stoploss` as a fraction of the LEVERAGED profit ratio and
divides by leverage to get the price distance
(`LocalTrade.adjust_stop_loss`, freqtrade/persistence/trade_model.py:858-862).
At 20x that silently turned a 3.6% stop into a 0.18% stop while the 2R target
stayed at 3x ATR — a ~1:40 payoff, not 1:2 — and 97% of trades stopped out on
noise. `leverage()` now rescales `self.stoploss` by the actual leverage so the
price stop is 3.6% in every cell. At 1x this is a no-op. See
`_LeverageMatrixMixin` and docs-myself/WIDE_FT_MATRIX_RESULT_2026-09-27.md.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from pandas import DataFrame
from freqtrade.persistence import Trade
from ShortBreakout4h import ShortBreakout4h

logger = logging.getLogger(__name__)


class _LeverageMatrixMixin:
    """Explicitly consume and log the registered leverage overlay.

    THE STOP MUST BE RESCALED BY LEVERAGE, OR THE MATRIX MEASURES NOTHING.

    Freqtrade expresses ``stoploss`` as a fraction of the *leveraged* profit
    ratio and converts it to a price distance by DIVIDING:
    ``LocalTrade.adjust_stop_loss`` does
    ``new_loss = price * (1 + abs(stoploss / leverage))``
    (freqtrade/persistence/trade_model.py:858-862). The strategy's 2R target
    is computed in PRICE (``open_rate - 2 * 1.5 * atr``). Leaving ``stoploss``
    at the class value of -0.036 therefore shrinks the price stop to 0.18% at
    20x while the target stays at 3x ATR, turning a 1:2 payoff into roughly
    1:40 and stopping ~97% of trades on noise.

    So ``self.stoploss`` is set to ``-price_stop * used_leverage``: the price
    distance stays at ``price_stop`` at every leverage, the 1:2 geometry is
    preserved, and the loss per stop-out in COLLATERAL terms correctly scales
    with leverage. At 1x this is a no-op, so the 1x cell is unchanged.

    ``self.stoploss`` is assigned here because ``leverage()`` is called
    (backtesting.py:1070) for every new trade BEFORE ``adjust_stop_loss``
    reads ``self.strategy.stoploss`` (backtesting.py:1246). Backtesting is
    single-threaded and the value is consumed immediately, so a per-trade
    instance attribute is exact even when the exchange clamps leverage per pair.
    """

    allowed_leverages = (1.0, 2.0, 5.0, 10.0, 20.0)
    default_leverage = 1.0

    # price distance of the stop, i.e. the panel's median 1.5 x ATR%
    price_stop = 0.036

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
        try:
            requested = float(self.config.get("perp_leverage", self.default_leverage))
        except (TypeError, ValueError):
            raise ValueError("perp_leverage must be one of 1, 2, 5, 10, 20")
        if requested not in self.allowed_leverages:
            raise ValueError(
                f"perp_leverage={requested} is outside frozen matrix "
                f"{self.allowed_leverages}"
            )
        used = max(1.0, min(requested, float(max_leverage)))
        if used != requested:
            logger.warning(
                "%s requested %sx but exchange max is %sx; actual=%sx",
                pair, requested, max_leverage, used,
            )
        # keep the PRICE stop at price_stop; see the class docstring
        self.stoploss = -self.price_stop * used
        return used


class WideShortBreakoutMatrix(_LeverageMatrixMixin, ShortBreakout4h):
    """Frozen short-only candidate; the long leg is excluded by preregistration."""


class WideLongBreakoutMatrix(_LeverageMatrixMixin, ShortBreakout4h):
    """Same frozen features/exits, long-side-only diagnostic control.

    The wide-panel study found the long leg negative in all tested cells. This
    class exists to make that side-specific result reproducible in Freqtrade,
    not to imply a long edge.
    """

    can_short = False

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        long_setup = (
            (dataframe["rvol"] >= self.rvol_threshold)
            & (dataframe["close"] > dataframe["prev_high"])
            & dataframe["low_vol"]
        )
        dataframe.loc[long_setup, ["enter_long", "enter_tag"]] = (1, "shark_long")
        dataframe.loc[~long_setup, "enter_tag"] = ""
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        # entry-bar ATR, shared with the frozen base strategy (baseline integrity)
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe_ok := (df is not None and len(df) >= 2):
            atr = self.entry_atr(pair, trade)
            if atr is None:
                atr = df["atr"].iloc[-1]
            if np.isfinite(atr) and atr > 0:
                target = trade.open_rate + self.target_r * self.atr_stop * float(atr)
                if current_rate >= target:
                    return "target_2r"
        if (current_time - trade.open_date_utc).total_seconds() >= (
            self.time_stop_bars * self.timeframe_min * 60
        ):
            return "time_stop"
        return None
