"""Is the short book a MARKET bet? Forward market return at the signal bars.

WHY THIS QUESTION, AND WHY IT IS THE DECISIVE ONE
-------------------------------------------------
`WIDE_PANEL_RESULT_2026-09-28.md` §2 already measured that the long+short book
regressed on the market at **beta = 1.000** and called it *"a pure directional
market bet wearing a volume filter as a disguise"*. That verdict was reached on
the shark engine. Nothing since has tested it on the freqtrade trades.

The coincidence decomposition made it sharper. Bucketing trades by how many
symbols signalled on the same bar:

    1 alone   -0.105R     3-4   +0.387R     8-12  +0.066R
    2         -0.180R     5-7   -0.520R     13+   +0.559R   <- t = 3.76

The 13+ bucket is large and its t is far past any bar used in this project. The
obvious reading is "market-wide breakouts carry information". There is a second
reading that costs nothing to test and would explain everything: **when 20+
symbols break down together, the MARKET falls** - and a short book is simply the
cheapest way to own that. If the second reading is right, every R in this
project is a market-timing overlay, and `PREREG_WIDE_PANEL` §1d already closed
market timing (Hurst/Ooi/Pedersen 2017, JPM, null).

So: at every bar where the panel produced ANY signal, what did the EQUAL-WEIGHT
PANEL do over the same 42-bar holding window the strategy uses?

  * if forward market return falls monotonically with n_coincident, the signal
    is a market-timing overlay and the per-symbol R is not a per-symbol edge;
  * if it does NOT, the short book's edge is idiosyncratic - which would be
    surprising, and would be the first genuinely new thing in this line.

Either answer is useful. Only one of them is what anyone would want to trade.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\market_check.py
"""

from __future__ import annotations

import glob
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies"))

from PerpShort4h import PerpShort4h  # noqa: E402

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")
HOLD = 42  # the strategy's 42-bar (~7 day) holding window, frozen


def main() -> int:
    files = sorted(glob.glob(os.path.join(DATADIR, "futures", "*-4h-futures.feather")))
    if not files:
        raise SystemExit(f"no 4h futures files under {DATADIR}")
    print(f"panel: {len(files)} symbols under {DATADIR}")

    s = PerpShort4h(config={})
    closes, counts = [], Counter()
    grid = None
    for fp in files:
        d = pd.read_feather(fp)
        if grid is None:
            grid = d["date"].to_numpy()
        out = s.populate_indicators(d[["date", "open", "high", "low", "close", "volume"]]
                                   .copy(), {"pair": "X/USDT:USDT"})
        # log returns, aligned by POSITION on the shared 4h grid
        c = out["close"].to_numpy(dtype=float)
        r = np.full(len(c), np.nan)
        # log return is the DIFFERENCE of logs. A ratio here
        # (np.log(c[1:]) / np.log(c[:-1])) returns ~1.0 per bar for any price
        # above 1, so summing 42 of them yields ~42 = 4200% - a table full of
        # plausible-looking t-statistics attached to an absurd number. Only
        # "% falling" gave it away.
        r[1:] = np.log(c[1:]) - np.log(c[:-1])
        closes.append(r)
        for i in np.flatnonzero(out["shark_short"].to_numpy()):
            counts[int(i)] += 1

    R = np.vstack(closes)                       # (symbols, bars)
    n_bars = R.shape[1]
    # equal-weight forward return over the frozen holding window
    fwd = np.full(n_bars, np.nan)
    for i in range(n_bars - HOLD):
        seg = R[:, i:i + HOLD]
        ok = ~np.isnan(seg)
        if ok.sum() < 20:
            continue
        fwd[i] = np.nanmean(seg.sum(axis=1))    # sum of log returns == log ret
    fwd[R.shape[1] - HOLD:] = np.nan

    print(f"bars with >=1 signal: {len(counts)}   horizon: {HOLD} bars")
    # A sanity floor, because the bug above produced a full table of confident
    # t-statistics before anything objected. A 7-day forward LOG return on a
    # crypto panel beyond +-100% is not a measurement.
    fin = fwd[np.isfinite(fwd)]
    if len(fin) and np.abs(fin).max() > 1.0:
        print(f"\n❌ REFUSING TO PRINT: max |forward log return| over {HOLD} bars is "
              f"{np.abs(fin).max():.2f} (>1.0 = +-100%). That is not a market move, "
              f"it is a units bug.")
        return 1
    print(f"sanity: max |forward log return| = {np.abs(fin).max():.3f} (7 days)\n")
    print("\n=== EQUAL-WEIGHT PANEL FORWARD RETURN, BY COINCIDENCE BUCKET ===")
    print(f"{'n_coincident':>13}{'bars':>7}{'mean fwd':>11}{'median':>9}"
          f"{'t':>7}{'% falling':>11}")
    rows = []
    for lo, hi, lbl in [(1, 1, "1"), (2, 2, "2"), (3, 4, "3-4"), (5, 7, "5-7"),
                        (8, 12, "8-12"), (13, 10**9, "13+")]:
        bars = [i for i, n in counts.items() if lo <= n <= hi and np.isfinite(fwd[i])]
        if len(bars) < 5:
            continue
        v = fwd[bars]
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
        rows.append((lbl, len(bars), v.mean(), np.median(v), t, (v < 0).mean()))
        print(f"{lbl:>13}{len(bars):>7}{v.mean()*100:>+10.3f}%{np.median(v)*100:>+8.3f}%"
              f"{t:>7.2f}{(v<0).mean()*100:>10.1f}%")

    print("\n  (mean fwd is a LOG return over 7 days; -2% is a ~2% market drop)")

    if len(rows) >= 3:
        m = np.array([r[2] for r in rows])
        rho = np.corrcoef(np.arange(len(m)), m)[0, 1]
        print(f"\n   corr(bucket index, mean forward market return) = {rho:+.3f}")
        print("   -> MONOTONE: the signal IS a market-timing overlay."
              if rho < -0.5 else
              "   -> NOT monotone: high-coincidence bars are NOT simply market drops.")

    # how big is the market move at the 13+ bars, versus the panel overall?
    bars13 = [i for i, n in counts.items() if n >= 13 and np.isfinite(fwd[i])]
    allb = [i for i in counts if np.isfinite(fwd[i])]
    if bars13 and allb:
        print(f"\n=== SCALE ===")
        print(f"   all signal bars      : mean fwd {np.nanmean(fwd[allb])*100:+.3f}%  "
              f"median {np.nanmedian(fwd[allb])*100:+.3f}%  n={len(allb)}")
        print(f"   n_coincident >= 13   : mean fwd {np.nanmean(fwd[bars13])*100:+.3f}%  "
              f"median {np.nanmedian(fwd[bars13])*100:+.3f}%  n={len(bars13)}")
        print(f"   every 4h bar (baseline): mean fwd "
              f"{np.nanmean(fwd[np.isfinite(fwd)])*100:+.3f}%")

    print("\n=== PER-SYMBOL CHECK: do the SIGNALLING symbols fall more than the panel? ===")
    # ALL bars first, then split by coincidence, because the two answers differ
    # and the difference is the whole point: a positive excess overall can still
    # be zero in the trades that actually carry the P&L.
    def excess_for(bars_wanted):
        sym, pan = [], []
        for fp, r in zip(files, R):
            d = pd.read_feather(fp)
            out = s.populate_indicators(d[["date", "open", "high", "low", "close", "volume"]]
                                       .copy(), {"pair": "X/USDT:USDT"})
            sig = out["shark_short"].to_numpy()
            for i in bars_wanted:
                if sig[i] and np.isfinite(fwd[i]) and i + HOLD <= len(r):
                    seg = r[i:i + HOLD]
                    if not np.isnan(seg).any():
                        sym.append(seg.sum())
                        pan.append(fwd[i])
        if not sym:
            return None
        so, pa = np.array(sym), np.array(pan)
        diff = so - pa
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
        return so, pa, diff, t

    allbars = [i for i in counts if np.isfinite(fwd[i])]
    r = excess_for(allbars)
    if r:
        so, pa, diff, t = r
        print(f"\n   -- ALL signalling bars --")
        print(f"   n = {len(diff)}")
        print(f"   signaller forward : mean {so.mean()*100:+.3f}%")
        print(f"   panel forward     : mean {pa.mean()*100:+.3f}%")
        print(f"   EXCESS            : mean {diff.mean()*100:+.3f}%   t = {t:+.2f}")
        print(f"   -> the book beats the market by {diff.mean()/so.mean()*100:.1f}% "
              f"of its own move" if so.mean() != 0 else "")

    print("\n   -- split by coincidence, because the overall number can hide it --")
    print(f"{'bucket':>10}{'n':>7}{'signaller':>12}{'panel':>10}{'EXCESS':>10}{'t':>8}")
    for lo, hi, lbl in [(1, 2, "1-2"), (3, 4, "3-4"), (5, 7, "5-7"),
                        (8, 12, "8-12"), (13, 10**9, "13+")]:
        bars_w = [i for i, n in counts.items() if lo <= n <= hi and np.isfinite(fwd[i])]
        r = excess_for(bars_w)
        if not r or len(r[0]) < 30:
            continue
        so, pa, diff, t = r
        print(f"{lbl:>10}{len(diff):>7}{so.mean()*100:>+11.3f}%{pa.mean()*100:>+9.3f}%"
              f"{diff.mean()*100:>+9.3f}%{t:>8.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
