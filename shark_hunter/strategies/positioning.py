"""Positioning and flow signals that the study downloaded but never tested.

The Binance `daily/metrics` archive carries four columns beyond open
interest.  The spec only ever asked for OI, so the other three were fetched,
normalised, carried through the pipeline -- and then never used by any
strategy:

    count_toptrader_long_short_ratio  -> top_trader_ls_ratio
    count_long_short_ratio            -> long_short_account_ratio
    sum_taker_long_short_vol_ratio    -> taker_ls_vol_ratio

They are free, at 5-minute resolution, covering the whole sample, and they
are the most direct measurement of *positioning* available in this data --
which is the thing the "whale / shark" thesis is actually about.  Ignoring
them because the spec did not name them would be letting the specification
override the evidence.

These are extensions beyond the spec's eight strategies, kept in a separate
module so SHARK-01..08 stay exactly as the plan defined them.

Deliberate framing: each is a *classification* of where positioning sits, not
a directional call.  Whether "crowded longs" is bullish or bearish is measured
here, not assumed.  The 4h OI-quadrant result already showed price-DOWN
states carrying positive forward drift, which is the opposite of the usual
reading, so the prior for any directional story here should be low.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.engine import (R_VOL_BO, StrategySpec, REASON_NAMES)
from .recipes import _col_num, StrategyRecipe

REASON_POS_TOPTRADER = 15
REASON_POS_ACCOUNTS = 16
REASON_POS_TAKER = 17
REASON_NAMES.update({
    REASON_POS_TOPTRADER: "RVOL_BREAKOUT_TOPTRADER_LS",
    REASON_POS_ACCOUNTS: "RVOL_BREAKOUT_ACCOUNT_LS",
    REASON_POS_TAKER: "RVOL_BREAKOUT_TAKER_LS",
})


@dataclass(frozen=True)
class PositioningRecipe(StrategyRecipe):
    """SHARK-01 plus one positioning condition."""
    positioning: str | None = None      # 'top_trader' | 'accounts' | 'taker'
    position_lookback: int = 3
    require_crowded: bool = True        # True = crowded with longs (ratio rising)


POSITIONING_STRATEGIES: dict[str, PositioningRecipe] = {
    "SHARK-09-TOPTRADER": PositioningRecipe(
        "SHARK-09-TOPTRADER",
        "SHARK-01 plus top-trader long/short ratio rising over 3 bars.",
        positioning="top_trader", position_lookback=3, require_crowded=True),
    "SHARK-10-ACCOUNTS": PositioningRecipe(
        "SHARK-10-ACCOUNTS",
        "SHARK-01 plus global long/short account ratio rising over 3 bars.",
        positioning="accounts", position_lookback=3, require_crowded=True),
    "SHARK-11-TAKER": PositioningRecipe(
        "SHARK-11-TAKER",
        "SHARK-01 plus taker buy/sell volume ratio rising over 3 bars.",
        positioning="taker", position_lookback=3, require_crowded=True),
    "SHARK-12-TOPTRADER-SHORT": PositioningRecipe(
        "SHARK-12-TOPTRADER-SHORT",
        "SHARK-01 plus top-trader long/short ratio FALLING (longs unwinding).",
        positioning="top_trader", position_lookback=3, require_crowded=False),
}

POSITIONING_COLUMNS = {
    "top_trader": "top_trader_ls_ratio",
    "accounts": "long_short_account_ratio",
    "taker": "taker_ls_vol_ratio",
}


def positioning_signal(df: pd.DataFrame, recipe: PositioningRecipe) -> pd.Series:
    """True where positioning is crowded, oriented by the recipe.

    "Crowded long" is a ratio above its own recent level.  Using the change
    rather than a fixed threshold keeps this scale-free across symbols, whose
    ratio levels differ by more than a factor of two.
    """
    col = POSITIONING_COLUMNS[recipe.positioning]
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    s = pd.to_numeric(df[col], errors="coerce")
    chg = s - s.shift(recipe.position_lookback)
    ok = chg.notna()
    return (chg > 0) if recipe.require_crowded else (chg < 0)


def build_positioning_spec(df: pd.DataFrame, recipe: PositioningRecipe, *,
                           atr_stop: float = 1.0, r_multiple: float = 2.0,
                           time_stop_bars: int = 48,
                           cooldown_bars: int = 3) -> StrategySpec:
    """SHARK-01 with one positioning condition ANDed onto the entry."""
    n = len(df)
    rvol = _col_num(df, "rvol")
    close = _col_num(df, "close")
    prev_high = _col_num(df, "prev_high")
    prev_low = _col_num(df, "prev_low")

    base = (~np.isnan(rvol)) & (rvol >= 2.0)
    bo_long = base & (close > prev_high)
    bo_short = base & (close < prev_low)

    pos = positioning_signal(df, recipe).to_numpy(dtype=bool)
    # Symmetric in a defensible way: crowded longs may argue either way, so
    # both sides require the same crowding state rather than encoding a
    # directional story the data has not supported.
    bo_long = bo_long & pos
    bo_short = bo_short & pos

    code = {"top_trader": REASON_POS_TOPTRADER,
            "accounts": REASON_POS_ACCOUNTS,
            "taker": REASON_POS_TAKER}[recipe.positioning]
    reasons = np.where(bo_long, code, R_VOL_BO).astype(int)
    zeros = np.zeros(n, dtype=bool)
    return StrategySpec(
        name=recipe.name, long_entry=bo_long, short_entry=bo_short,
        long_exit=zeros, short_exit=zeros,
        long_reason=reasons, short_reason=reasons,
        atr_stop=atr_stop, r_multiple=r_multiple,
        time_stop_bars=time_stop_bars, cooldown_bars=cooldown_bars,
        use_signal_exit=False)
