"""Freqtrade port of the pre-registered FUNDING FILTER cell (short leg only).

This is a VALIDATION wrapper, not a new search. The cell it ports was frozen
before it was run in `PREREG_PAYOFF_FUNDING_LONG_2026-09-27.md` §2 and already
measured by the shark engine (t_adj 2.4059, the only cell in this project that
has ever crossed t = 2). Reproducing it in a second engine answers exactly one
question: does the effect survive an independent implementation?

WHAT IT CANNOT DO: clear the S7 deflated bar (snr 0.1446 vs 0.2522 required at
41,472 searched trials). That bar does not move because a number was recomputed
in Freqtrade. Whatever this run shows, the parent line stays a near-miss.

Rule ported verbatim from `tools/widepanel/build_panel.py:259-270`:

    funding7d        = sum of funding SETTLED in the trailing 42 4h bars (7 days)
    funding7d_med365 = median(funding7d) over 365 bars, min_periods=120, shift(1)
    funding_high     = funding7d >  funding7d_med365      <- the lead cell
    funding_low      = funding7d <  funding7d_med365      <- the control

Two details that are load-bearing and easy to get wrong (build_panel.py:225-256):

  * A settlement is attributed to the 4h bar whose window CONTAINS it, and all
    settlements inside one bar are SUMMED. 21 of the 104 symbols run on a 1h
    funding interval, so marking only the bar holding a single timestamp
    under-charges them by 1-15%.
  * It is a LEFT JOIN onto the 4h grid, never a merge_asof. A backward asof
    forward-fills the last rate onto every later bar, marks every bar as a
    settlement, and charges funding ~6x too often.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from freqtrade.misc import pair_to_filename
from freqtrade.persistence import Trade
from pandas import DataFrame

from ShortBreakout4h import ShortBreakout4h
from WideBreakoutMatrix import _LeverageMatrixMixin

logger = logging.getLogger(__name__)

# one funding file per pair per backtest process; keyed by the resolved path
_FUNDING_CACHE: dict[str, pd.Series] = {}


def _funding_per_4h_bar(pair: str, datadir: Path, grid: pd.Series) -> pd.Series:
    """Funding settled inside each 4h bar, summed, aligned to `grid` (4h open times).

    Raises rather than returning NaN: a missing funding feed is BLOCKED, and a
    silently all-zero column would read as "funding is always flat" and produce
    a confident wrong filter.
    """
    path = datadir / "futures" / f"{pair_to_filename(pair)}-1h-funding_rate.feather"
    if not path.is_file():
        raise FileNotFoundError(
            f"BLOCKED: no funding data for {pair} at {path}. The funding filter "
            f"cannot run without it; run "
            f"`freqtrade download-data --exchange binance --pairs {pair} "
            f"--timeframes 1h --trading-mode futures`."
        )
    if path not in _FUNDING_CACHE:
        fr = pd.read_feather(path)
        fr = fr.rename(columns={"date": "funding_time"})
        fr["funding_time"] = pd.to_datetime(fr["funding_time"], utc=True)
        # floor BEFORE grouping: Binance timestamps carry positive ms jitter
        # (e.g. 08:00:00.008) and would otherwise fall outside their own bar
        fr["bar"] = fr["funding_time"].dt.floor("4h")
        per_bar = fr.groupby("bar")["funding_rate"].sum()
        _FUNDING_CACHE[str(path)] = per_bar

    per_bar = _FUNDING_CACHE[str(path)]
    aligned = per_bar.reindex(pd.DatetimeIndex(grid))
    covered = aligned.notna().mean()
    if covered < 0.5:
        raise ValueError(
            f"BLOCKED: {path} covers only {covered:.1%} of the backtest grid for "
            f"{pair}; refusing to treat the gap as zero funding."
        )
    return aligned.fillna(0.0).to_numpy()


class _FundingFilterMixin:
    """Applies the frozen funding filter on top of the frozen low-vol rule."""

    funding_side = "high"  # "high" = the lead cell, "low" = the control
    target_r = 2.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_indicators(dataframe, metadata)
        grid = pd.DatetimeIndex(pd.to_datetime(df["date"], utc=True))
        rate = _funding_per_4h_bar(metadata["pair"], Path(self.config["datadir"]), grid)

        # 42 x 4h bars = 7 days. min_periods=10 is the pre-registered value.
        df["funding7d"] = pd.Series(rate).rolling(42, min_periods=10).sum().to_numpy()
        df["funding7d_med365"] = (
            df["funding7d"].rolling(365, min_periods=120).median().shift(1)
        )
        hi = (df["funding7d"] > df["funding7d_med365"]).fillna(False)
        lo = (df["funding7d"] < df["funding7d_med365"]).fillna(False)
        df["funding_high"] = hi
        df["funding_low"] = lo
        return df

    def _funding_ok(self, df: DataFrame) -> pd.Series:
        if self.funding_side == "high":
            return df["funding_high"]
        if self.funding_side == "low":
            return df["funding_low"]
        raise ValueError(f"funding_side must be 'high' or 'low', got {self.funding_side}")

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # base rule AND the funding filter - the prereg cell is the conjunction
        sig = dataframe["shark_short"] & self._funding_ok(dataframe)
        dataframe.loc[:, ["enter_long", "enter_short"]] = (0, 0)
        dataframe.loc[sig, ["enter_short", "enter_tag"]] = (1, f"shark_short_f{self.funding_side}")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def custom_exit(
        self, pair: str, trade: Trade, current_time, current_rate: float,
        current_profit: float, **kwargs
    ) -> Optional[str]:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(df) < 2:
            return None
        atr = self.entry_atr(pair, trade)   # frozen at entry, not the latest bar
        if atr is None:
            atr = df["atr"].iloc[-1]
        if np.isfinite(atr) and atr > 0:
            if current_rate <= trade.open_rate - self.target_r * self.atr_stop * atr:
                return f"target_{self.target_r:g}r"
        held = ((current_time - trade.open_date_utc).total_seconds()
                / (self.timeframe_min * 60))
        if held >= self.time_stop_bars:
            return "time_stop"
        return None


class WideFundingHigh2R(_FundingFilterMixin, _LeverageMatrixMixin, ShortBreakout4h):
    """THE PRE-REGISTERED LEAD CELL: low-vol AND funding_high, 2R target, short."""

    funding_side = "high"
    target_r = 2.0


class WideFundingLow2R(_FundingFilterMixin, _LeverageMatrixMixin, ShortBreakout4h):
    """THE CONTROL: the same rule with the funding sign flipped.

    Without this cell the 2.5x spread between signs cannot be distinguished from
    noise, and the whole lead is unreadable.
    """

    funding_side = "low"
    target_r = 2.0


class WideFundingHigh3R(_FundingFilterMixin, _LeverageMatrixMixin, ShortBreakout4h):
    """The combined cell: funding_high x 3.0R (highest net R/trade in the prereg)."""

    funding_side = "high"
    target_r = 3.0
