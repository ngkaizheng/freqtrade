"""Dataset assembly: raw sources -> one aligned, integrity-checked frame per
(symbol, timeframe), plus the feature block every strategy consumes.

The assembled frame is the single source of truth for the whole study.  A
strategy never sees a column that was not produced here, which is what makes
the ablation in step 20 meaningful.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import config as C
from .. import features
from . import sources as S
from .normalization import (IntegrityReport, check_integrity, repair_frozen_bars)


# --------------------------------------------------------------------------
# raw accessors
# --------------------------------------------------------------------------

def load_klines(symbol: str, timeframe: str = C.PRIMARY_TIMEFRAME,
                start: dt.datetime | None = None,
                end: dt.datetime | None = None) -> pd.DataFrame:
    src = S.KlineSource(symbol=symbol, timeframe=timeframe,
                        start=start or C.STUDY_START, end=end or C.STUDY_END)
    return src.fetch()


def load_metrics(symbol: str, start: dt.datetime | None = None,
                 end: dt.datetime | None = None) -> pd.DataFrame:
    src = S.MetricsSource(symbol=symbol, start=start or C.STUDY_START,
                          end=end or C.STUDY_END)
    return S.MetricsSource.normalize(src.fetch())


def load_funding(symbol: str, start: dt.datetime | None = None,
                 end: dt.datetime | None = None) -> pd.DataFrame:
    src = S.FundingSource(symbol=symbol, start=start or C.STUDY_START,
                          end=end or C.STUDY_END)
    return src.fetch()


def load_liquidations(symbol: str) -> pd.DataFrame:
    src = S.LiquidationSource(symbol=symbol, start=C.STUDY_START, end=C.STUDY_END)
    return src.fetch()


# --------------------------------------------------------------------------
# assembled dataset
# --------------------------------------------------------------------------

@dataclass
class Dataset:
    symbol: str
    timeframe: str
    frame: pd.DataFrame
    integrity: IntegrityReport
    unavailable: dict[str, str]

    def split(self, name: str) -> pd.DataFrame:
        spec = next(s for s in C.SPLITS if s.name == name)
        return self.frame.loc[(self.frame.index >= spec.start) & (self.frame.index < spec.end)]

    def __len__(self) -> int:
        return len(self.frame)


def build_dataset(symbol: str, timeframe: str = C.PRIMARY_TIMEFRAME,
                  start: dt.datetime | None = None,
                  end: dt.datetime | None = None,
                  strict: bool = True) -> Dataset:
    """Load every source for one symbol, align on the kline grid, add features."""
    start = start or C.STUDY_START
    end = end or C.STUDY_END

    base = load_klines(symbol, timeframe, start, end)
    if base.empty:
        raise ValueError(f"no kline data for {symbol} {timeframe} {start}..{end}")

    # Mask stale/frozen bars before anything consumes them.  They are data
    # artefacts, not market states, and they corrupt RVOL, the rolling
    # breakout level and ATR.  Masked to NaN rather than interpolated, so no
    # price or volume path is invented.
    base, n_frozen = repair_frozen_bars(base)
    if n_frozen:
        print(f"[data] {symbol} {timeframe}: masked {n_frozen} frozen bars")

    integrity = check_integrity(base, timeframe)
    integrity.notes.append(f"{n_frozen} frozen bars masked")
    if strict and not integrity.ok:
        raise ValueError(f"integrity failure for {symbol} {timeframe}: {integrity.to_dict()}")

    df = base.copy()
    df["split"] = [C.split_of(ts) for ts in df.index]

    # --- derivatives-only sources, reindexed onto the kline grid ------------
    unavailable: dict[str, str] = {}

    metrics = load_metrics(symbol, start, end)
    if metrics.empty:
        unavailable["open_interest"] = "no metrics archive returned data"
    else:
        df = df.join(_align_metrics(metrics, df.index, timeframe), how="left")

    funding = load_funding(symbol, start, end)
    if funding.empty:
        unavailable["funding"] = "no funding archive returned data"
    else:
        # Funding is an event series.  A bar is charged the most recent funding
        # rate that was *known* at or before that bar's open (spec 14/34).
        rate = funding["funding_rate"].reindex(funding.index.union(df.index)).ffill()
        df["funding_rate"] = rate.reindex(df.index)
        df["funding_event"] = _funding_event_flag(funding.index, df.index)

    liq = load_liquidations(symbol)
    if liq.empty:
        unavailable["liquidation"] = S.LIQUIDATION_COVERAGE["reason"]
    else:
        df = df.join(liq, how="left")

    # --- features ----------------------------------------------------------
    df = features.add_all(df, timeframe=timeframe)

    return Dataset(symbol=symbol, timeframe=timeframe, frame=df,
                   integrity=integrity, unavailable=unavailable)


def _align_metrics(metrics: pd.DataFrame, bar_index: pd.DatetimeIndex,
                   timeframe: str) -> pd.DataFrame:
    """Put 5-minute open interest onto a (possibly coarser) bar grid.

    Open interest is a point-in-time snapshot, not a flow, so the correct
    aggregation is ``last``: the value carried by a 1h bar is the reading at
    the close of its final 5m sub-bar, which is exactly what was known when
    the 1h bar closed.  Summing or averaging would invent a number the market
    never published, and averaging in particular would leak information
    backwards from the end of the hour into its start.
    """
    if timeframe == "5m":
        return metrics
    rule = {"1m": "1min", "1h": "1h", "4h": "4h"}.get(timeframe)
    if rule is None:
        raise ValueError(f"no open-interest alignment rule for timeframe {timeframe!r}")
    collapsed = metrics.resample(rule).last()
    return collapsed.reindex(bar_index)


def _funding_event_flag(event_index: pd.DatetimeIndex,
                        bar_index: pd.DatetimeIndex) -> pd.Series:
    """True on the bar that *contains* a funding timestamp.

    Marking is positional, not propagated: the previous implementation
    forward-filled the flag, which left it True on every bar from the first
    funding event onward -- charging funding 96x too often at 5m.  For each
    funding timestamp we take the last bar whose open is at or before it.

    Charging on the bar that contains the timestamp keeps the cost inside the
    bar loop without needing an intrabar sub-model.  A position opened at that
    bar's open is charged for it, which is marginally conservative.
    """
    if len(event_index) == 0 or len(bar_index) == 0:
        return pd.Series(False, index=bar_index)
    if getattr(event_index, "tz", None) is None:
        event_index = event_index.tz_localize("UTC")
    if bar_index.tz is None:
        bar_index = bar_index.tz_localize("UTC")
    pos = bar_index.searchsorted(event_index, side="right") - 1
    pos = pos[pos >= 0]
    flags = np.zeros(len(bar_index), dtype=bool)
    flags[np.unique(pos)] = True
    return pd.Series(flags, index=bar_index)
