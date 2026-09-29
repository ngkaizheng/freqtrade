"""Verify the Freqtrade funding filter reproduces the shark panel EXACTLY.

A cross-engine check is worthless if the two engines disagree about which bars
the filter fires on. This recomputes funding7d / funding7d_med365 / funding_high
from the same funding feather files, for every one of the 24 symbols, and diffs
it bar-for-bar against `shark_data/wide/features/<sym>.parquet`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "user_data" / "strategies"))

from WideFundingFilter import _funding_per_4h_bar  # noqa: E402

DATADIR = REPO / "user_data" / "data" / "wide_ft"
PANEL = REPO / "shark_data" / "wide" / "features"


def main() -> None:
    # panel stem is BTCUSDT / 1000SHIBUSDT; funding feather is BTC_USDT_USDT
    have_data = {p.name.split("-1h-funding_rate")[0].split("_")[0]
                 for p in (DATADIR / "futures").glob("*-1h-funding_rate.feather")}
    syms = sorted(p.stem for p in PANEL.glob("*.parquet")
                  if p.stem.removesuffix("USDT") in have_data)
    print(f"wide_ft funding symbols: {len(have_data)}   "
          f"panel symbols with both: {len(syms)}")
    if not syms:
        # a 0/0 comparison prints as a pass; it must not
        raise SystemExit("BLOCKED: no symbol has both datasets; nothing was verified")
    print()
    print(f"{'symbol':<14s} {'rows':>6s} {'match':>7s} {'diff':>6s} "
          f"{'f7d maxabs':>11s} {'f7d_med':>9s} {'hi%':>7s} {'pan hi%':>8s}")
    tot_rows = tot_diff = 0
    hi_mismatch_total = 0
    for s in syms:
        pan = pd.read_parquet(PANEL / f"{s}.parquet")
        tcol = "open_time" if "open_time" in pan.columns else "date"
        t = pd.to_datetime(pan[tcol], utc=True)
        grid = pd.Series(t.to_numpy())

        rate = _funding_per_4h_bar(f"{s[:-4]}/USDT:USDT", DATADIR, grid)
        f7d = pd.Series(rate).rolling(42, min_periods=10).sum().to_numpy()
        fmed = pd.Series(f7d).rolling(365, min_periods=120).median().shift(1).to_numpy()
        hi = (pd.Series(f7d) > pd.Series(fmed)).fillna(False).to_numpy()
        lo = (pd.Series(f7d) < pd.Series(fmed)).fillna(False).to_numpy()

        p_f7d = pan["funding7d"].to_numpy()
        p_med = pan["funding7d_med365"].to_numpy()
        p_hi = pan["funding_high"].to_numpy().astype(bool)
        p_lo = pan["funding_low"].to_numpy().astype(bool)

        finite = np.isfinite(p_f7d) & np.isfinite(f7d)
        maxabs = float(np.max(np.abs(p_f7d[finite] - f7d[finite]))) if finite.any() else 0.0
        both = np.isfinite(p_f7d) & np.isfinite(fmed)
        medmax = float(np.max(np.abs(p_med[both] - fmed[both]))) if both.any() else 0.0
        exact = int((hi == p_hi).all() and (lo == p_lo).all())
        ndiff = int((hi != p_hi).sum()) + int((lo != p_lo).sum())
        tot_rows += len(pan)
        tot_diff += ndiff
        hi_mismatch_total += ndiff
        print(f"{s:<14s} {len(pan):6d} {str(exact == 1):>7s} {ndiff:6d} "
              f"{maxabs:11.2e} {medmax:9.2e} {100*hi.mean():6.1f}% {100*p_hi.mean():7.1f}%")

    print(f"\ntotal rows {tot_rows:,}   total bar-level disagreements {tot_diff}")
    if tot_rows == 0 or tot_diff:
        raise SystemExit("MISMATCH — do not report the backtest")
    print("EXACT MATCH: every funding_high / funding_low bar agrees with the shark panel")


if __name__ == "__main__":
    main()
