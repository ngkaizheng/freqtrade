"""Schema normalisation and data integrity checks.

Every dataset that enters the study passes through :func:`check_integrity`.
A dataset that fails a hard check must not be backtested -- silently feeding a
gappy series into a rolling indicator produces numbers that look plausible and
are meaningless.  This is the same discipline the previous handoff project's
`methodology/test_regressions.py` enforced, applied to input data instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .sources import TIMEFRAME_MS

OHLC_COLUMNS = ["open", "high", "low", "close"]


@dataclass
class IntegrityReport:
    rows: int = 0
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    duplicates: int = 0
    missing_bars: int = 0
    longest_gap: int = 0
    non_monotonic: int = 0
    ohlc_violations: int = 0
    negative_volume: int = 0
    frozen_bars: int = 0
    null_cells: int = 0
    tz_aware: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (self.duplicates == 0 and self.missing_bars == 0
                and self.ohlc_violations == 0 and self.non_monotonic == 0
                and self.negative_volume == 0)

    def to_dict(self) -> dict:
        return {
            "rows": self.rows, "start": str(self.start), "end": str(self.end),
            "duplicates": self.duplicates, "missing_bars": self.missing_bars,
            "longest_gap_bars": self.longest_gap, "non_monotonic": self.non_monotonic,
            "ohlc_violations": self.ohlc_violations,
            "negative_volume": self.negative_volume,
            "frozen_bars": self.frozen_bars,
            "null_cells": self.null_cells,
            "tz_aware": self.tz_aware, "ok": self.ok, "notes": self.notes,
        }


def frozen_runs(df: pd.DataFrame, min_run: int = 3) -> list[tuple[int, int]]:
    """Contiguous runs of bars with no trading range and no volume.

    A missing-row check does not catch these: the rows are present, on the
    grid, and structurally valid, but the price is frozen and the volume is
    zero.  A cross-check of native 1h klines against the aggregation of 5m
    klines exposed a 19-bar instance on BTCUSDT (2023-11-10) where the 5m
    series froze while the exchange's own 1h bar showed an active market.

    These are data artefacts, not market states, and they corrupt the
    features: RVOL collapses, the rolling breakout level absorbs the frozen
    value and suppresses the breakout that follows, and ATR shrinks.
    """
    bad = ((df["high"] <= df["low"]) & (df["volume"] <= 0)).to_numpy()
    runs, start = [], None
    for i, v in enumerate(bad):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_run:
                runs.append((start, i))
            start = None
    if start is not None and len(bad) - start >= min_run:
        runs.append((start, len(bad)))
    return runs


def repair_frozen_bars(df: pd.DataFrame, min_run: int = 3) -> tuple[pd.DataFrame, int]:
    """Mask artefact bars with NaN rather than interpolating them.

    Interpolating would invent a price and a volume path that never happened,
    which is exactly the kind of quiet fabrication this project is trying to
    avoid.  Masking keeps the time grid regular -- so rolling windows stay
    aligned -- while the strategy's NaN guards stop those bars generating
    signals.  Rolling means ignore NaN rather than poisoning downstream bars.

    Returns ``(frame, n_masked)``.
    """
    runs = frozen_runs(df, min_run)
    if not runs:
        return df, 0
    out = df.copy()
    for a, b in runs:
        out.iloc[a:b, out.columns.get_indexer(
            ["open", "high", "low", "close", "volume", "quote_volume",
             "taker_buy_volume", "taker_sell_volume"])] = np.nan
    return out, int(sum(b - a for a, b in runs))


def check_integrity(df: pd.DataFrame, timeframe: str) -> IntegrityReport:
    rep = IntegrityReport()
    if df is None or df.empty:
        rep.notes.append("empty dataset")
        return rep

    rep.rows = len(df)
    rep.tz_aware = isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None
    rep.start, rep.end = df.index.min(), df.index.max()
    rep.null_cells = int(df.isna().sum().sum())

    step = pd.Timedelta(milliseconds=TIMEFRAME_MS[timeframe])

    if not rep.tz_aware:
        rep.notes.append("index is not tz-aware UTC")
    if df.index.has_duplicates:
        rep.duplicates = int(df.index.duplicated().sum())
    if not df.index.is_monotonic_increasing:
        rep.non_monotonic = int((np.diff(df.index.values).astype("timedelta64[ns]")
                                 .astype("int64") <= 0).sum())

    # Gap detection on the union of expected grid points.
    full = pd.date_range(df.index.min(), df.index.max(), freq=step, tz="UTC")
    missing = full.difference(df.index)
    rep.missing_bars = len(missing)
    if len(missing):
        # Longest run of consecutive missing bars.
        arr = missing.view("int64")
        breaks = np.flatnonzero(np.diff(arr) != step.value)
        runs = np.diff(np.concatenate(([-1], breaks, [len(arr) - 1])))
        rep.longest_gap = int(runs.max()) if len(runs) else 0
        rep.notes.append(f"longest missing run: {rep.longest_gap} bars")

    if all(c in df.columns for c in OHLC_COLUMNS):
        o, h, l, c = (df[x] for x in OHLC_COLUMNS)
        # `h < l` (strictly): high == low is a legitimate zero-range bar, and
        # flagging it as corrupt would reject good data on illiquid prints.
        bad = (h < l) | (h < o) | (h < c) | (l > o) | (l > c)
        rep.ohlc_violations = int(bad.sum())

    if "volume" in df.columns:
        rep.negative_volume = int((df["volume"] < 0).sum())
        rep.frozen_bars = int(sum(b - a for a, b in frozen_runs(df)))

    return rep


def assert_clean(df: pd.DataFrame, timeframe: str, label: str) -> IntegrityReport:
    rep = check_integrity(df, timeframe)
    if not rep.ok:
        raise ValueError(
            f"integrity failure for {label} ({timeframe}): {rep.to_dict()}")
    return rep
