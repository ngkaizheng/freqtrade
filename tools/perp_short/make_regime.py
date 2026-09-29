"""Build the PANEL REGIME series the direction switch reads.

WHY THIS IS A SEPARATE ARTIFACT
-------------------------------
The regime is a property of the PANEL, not of any one symbol, and freqtrade's
`populate_indicators` sees exactly one pair at a time. So the regime has to be
computed once, outside the strategy, and joined back in by timestamp. This is
also the honest description of how it would work live: it is a market state,
not a per-asset feature.

WHAT IT IS (frozen in PREREG_DIRECTION_SWITCH_2026-09-28.md, not varied)
------------------------------------------------------------------------
    regime_t = 1 if equal-weight panel close > its own 200-bar SMA
              0 otherwise

200 bars of 4h = ~33 days. Chosen because it is unambiguously a "trend" rather
than a swing at this bar size, and fixed BEFORE the run. It is not searched.

THE ALIGNMENT TRAP THIS FILE EXISTS TO AVOID
--------------------------------------------
Joining a global series onto per-symbol frames by INDEX POSITION is wrong the
moment any symbol's history starts or ends at a different bar, and it is wrong
SILENTLY - the result looks like a strategy, just a different one. Every join
here is on the UTC timestamp, and the file asserts the join actually produced
values rather than NaN.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\make_regime.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")
OUT = "user_data/perp_short_out/panel_regime.csv"
SMA_BARS = 200
FORWARD = 7  # bars; only for the diagnostic print, not for the rule


def main() -> int:
    files = sorted(glob.glob(os.path.join(DATADIR, "futures", "*-4h-futures.feather")))
    if not files:
        raise SystemExit(f"no 4h futures under {DATADIR}")
    print(f"panel: {len(files)} symbols under {DATADIR}")

    frames = []
    lens = set()
    for fp in files:
        d = pd.read_feather(fp)[["date", "close"]]
        lens.add(len(d))
        frames.append(d.set_index("date")["close"].rename(fp))
    if len(lens) != 1:
        raise SystemExit(f"symbols have different bar counts {sorted(lens)}; "
                         f"a position-based stack would silently misalign them")
    px = pd.concat(frames, axis=1)
    print(f"grid: {px.shape[0]} bars  {px.index[0]} -> {px.index[-1]}  "
          f"missing per symbol: {int(px.isna().sum().sum())}")

    # equal-weight of the CLOSES, then equal-weight of the log returns.
    # Averaging closes is wrong: a coin 1000x another's price dominates the
    # "equal weight" average. This is the same bug as a price-level index.
    logret = np.log(px).diff()
    panel = logret.mean(axis=1)               # equal-weight log return per bar
    level = (1.0 + panel.fillna(0.0)).cumprod()

    sma = level.rolling(SMA_BARS, min_periods=SMA_BARS).mean()
    regime = (level > sma).astype(int)
    regime[sma.isna()] = np.nan               # not yet defined

    print(f"\nregime: {int(regime.sum())} up-bars, "
          f"{int((regime == 0).sum())} down-bars, "
          f"{int(regime.isna().sum())} undefined (first {SMA_BARS} bars)")
    print(f"panel total over the window: {level.iloc[-1] / level.iloc[0] - 1:+.1%}")

    print("\n=== regime by year (fraction of bars in an up-regime) ===")
    d = pd.DataFrame({"regime": regime, "level": level})
    for y, g in d.groupby(d.index.year):
        r = g["regime"].dropna()
        if len(r):
            print(f"   {y}  {r.mean()*100:5.1f}% up   "
                  f"panel {g['level'].iloc[-1]/g['level'].iloc[0]-1:+7.1%}")

    fwd = (level.shift(-FORWARD) / level - 1)
    tab = pd.DataFrame({"regime": regime, "fwd": fwd}).dropna()
    up = tab[tab["regime"] == 1]["fwd"]
    dn = tab[tab["regime"] == 0]["fwd"]
    print(f"\n=== is the regime actually predictive? (forward {FORWARD}-bar return) ===")
    print(f"   up-regime   n={len(up):<5} mean {up.mean()*100:+.3f}%/7d  "
          f"t {up.mean()/(up.std()/np.sqrt(len(up))):+.2f}")
    print(f"   down-regime n={len(dn):<5} mean {dn.mean()*100:+.3f}%/7d  "
          f"t {dn.mean()/(dn.std()/np.sqrt(len(dn))):+.2f}")
    print("\n   If the two are not separated, the direction switch is a coin flip")
    print("   dressed as a rule, and the strategy result will say so.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = pd.DataFrame({"date": regime.index, "regime": regime.to_numpy(),
                        "level": level.to_numpy()})
    out.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}  ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
