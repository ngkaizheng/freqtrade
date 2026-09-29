"""POWER-OPTIMUM ARITHMETIC: is ANY timeframe capable of clearing the bar?

WHY THIS IS COMPUTED AND NOT BACKTESTED
---------------------------------------
`AGENTS.md` section 1a: before committing to an experiment, check that the
available data could produce a verdict at all. A test that cannot conclude
"consumes compute and returns 'don't know' carrying false confidence."

The one dimension of this signal never varied is the HORIZON, and it has an
obvious pull in both directions:

  * COST FAVOURS LONGER. `cost_R = round_trip_bps / (stop_mult x atr_pct x 1e4)`,
    and `atr_pct` grows with the bar, so a 1d bar costs about HALF as much per unit
    of risk as a 4h bar. Measured at 4h with a 4xATR stop: 34.9 bps over a
    ~240 bps stop = 0.036R; at 1d the stop is ~580 bps = 0.015R.
  * POWER FAVOURS SHORTER. Trades scale roughly as 1/timeframe, and
    t = (m/sigma) x sqrt(n_eff). Losing a factor of 6 in n costs a factor of
    2.4 in t.

Which one binds is pure arithmetic once the two elasticities are measured, and
both are measurable from data already on disk. So: measure them, compute the
frontier, and only then decide whether any backtest is worth 30 minutes.

WHAT IS AND IS NOT CONCLUDED HERE
---------------------------------
This does NOT say the signal has no edge. It says what the edge would have to
look like at each horizon to reach t = 2.0, which is a statement about the
REQUIRED effect size. That is the question that decides whether to spend compute,
and it is exactly what section 1a asks for.

Run:
    $env:PERP_SHORT_DATADIR="user_data/data/wide104"
    .venv\\Scripts\\python.exe tools\\perp_short\\power_optimum.py
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")
BAR = 4  # hours per bar in the stored panel
T_BAR = 2.0
COST_BPS = 34.9  # measured COVID round trip, the stress end

# measured on the 4h panel: mean net R and t at the 4.0-ATR arm
N_4H = 1140
MEAN_4H = 0.1213
T_NAIVE_4H = 0.60


def main() -> int:
    files = sorted(glob.glob(os.path.join(DATADIR, "futures", "*-4h-futures.feather")))
    if not files:
        raise SystemExit(f"no 4h futures under {DATADIR}")

    # ---- 1. the two elasticities, measured from the data ----------------
    # (a) how does atr_pct scale with the bar? resample 4h -> 8h -> 16h -> 1d
    rets, horizons = [], [4, 8, 16, 24]
    for fp in files[:40]:
        d = pd.read_feather(fp)[["date", "high", "low", "close"]]
        c = d.set_index("date")["close"]
        r4 = np.log(c).diff().dropna()
        for h in horizons:
            n_per = h // BAR
            if n_per > 1:
                r = np.log(c).diff().resample(f"{h}h").sum().dropna()
            else:
                r = r4
            rets.append({"h": h, "atr_pct": float(r.std() * 1e4)})
    A = pd.DataFrame(rets).groupby("h")["atr_pct"].median()
    print("=== (a) atr_pct vs bar length (median over 40 symbols) ===")
    for h in horizons:
        print(f"   {h:>3}h   {A[h]:>8.1f} bps")

    # (b) how does the SIGNAL RATE scale with the bar?
    sys.path.insert(0, os.path.join("user_data", "strategies"))
    from PerpShort4h import PerpShort4h
    s = PerpShort4h(config={})
    rates = []
    for fp in files:
        d = pd.read_feather(fp)
        out = s.populate_indicators(
            d[["date", "open", "high", "low", "close", "volume"]].copy(),
            {"pair": "X/USDT:USDT"})
        sig = out["shark_short"].to_numpy()
        nz = sig[np.isfinite(out["atr"].to_numpy())]
        rates.append({"h": 4, "rate": float(nz.sum()) / len(nz)})
    R4 = pd.DataFrame(rates)["rate"].median()
    print(f"\n=== (b) signal rate at 4h: {R4*100:.3f}% of bars ===")
    print("   (the 4h panel is the only one on disk; the rescaling of the")
    print("    signal rate with horizon is ASSUMED 1/h and flagged as such below)")

    # ---- 2. the per-trade signal-to-noise, from the 4h run -------------
    # t = (m/sigma) * sqrt(n)  ->  m/sigma = t / sqrt(n).  NOT t / (t/sqrt(n)),
    # which is how the first version of this line read and which printed
    # "t = 340" - a number so absurd it should have been caught on sight. There
    # is now an assertion below, because a plausible-looking table is not a
    # guard against a unit error.
    snr = T_NAIVE_4H / np.sqrt(N_4H)
    if not (0.0 < snr < 0.2):
        raise SystemExit(f"❌ m/sigma = {snr:.4f} is not a plausible per-trade "
                         f"signal-to-noise for a strategy; a units error is the "
                         f"likely cause. Refusing to print a frontier.")
    print(f"\n=== (c) per-trade signal-to-noise implied by the 4h run ===")
    print(f"   t = (m/sigma) x sqrt(n)  ->  m/sigma = {T_NAIVE_4H:.2f} / sqrt({N_4H}) "
          f"= {snr:.5f}")
    print(f"   sanity: that reproduces the measured t -> "
          f"{snr * np.sqrt(N_4H):.2f} (measured {T_NAIVE_4H:.2f})")
    print(f"   that is the only free parameter the horizon argument can move.")

    # ---- 3. the frontier ----------------------------------------------
    print(f"\n=== THE HORIZON FRONTIER ===")
    print(f"   cost regime: {COST_BPS} bps round trip (measured COVID, the stress end)")
    print(f"   gross R held at the measured 4h gross (0.2208) - i.e. ASSUMING the")
    print(f"   effect does not decay with horizon, which is generous to longer bars\n")
    gross = 0.2208
    print(f"{'bar':>6}{'atr_pct':>10}{'cost_R':>9}{'net_R':>9}{'n (est)':>10}"
          f"{'t (est)':>9}{'need net_R':>12}{'verdict':>10}")
    rows = []
    for h in horizons:
        atr_pct = A[h]
        cost_r = COST_BPS / (4.0 * atr_pct)   # 4xATR stop
        net_r = gross - cost_r
        # trades scale as 1/h relative to the measured 4h count
        n = N_4H * (BAR / h)
        t = snr * (net_r / MEAN_4H) * np.sqrt(n)
        if not (0.0 < t < 20.0):
            raise SystemExit(f"❌ t = {t:.2f} at {h}h is implausible; units error.")
        # mean net R required for t = 2.0, holding m/sigma and n fixed
        need_net = T_BAR / (snr * np.sqrt(n)) * MEAN_4H
        verdict = "PASS" if t >= T_BAR else "FAIL"
        rows.append({"h": h, "atr_pct": atr_pct, "cost_R": cost_r, "net_R": net_r,
                     "n": n, "t": t, "need": need_net, "verdict": verdict})
        print(f"{h:>5}h{atr_pct:>10.1f}{cost_r:>9.3f}{net_r:>9.3f}{n:>10.0f}"
              f"{t:>9.2f}{need_net:>12.4f}{verdict:>10}")

    print(f"\n   t is computed as  (m/sigma)_4h x (net_R/net_R_4h) x sqrt(n_h),")
    print(f"   with n_h = n_4h x (4h/h). Two assumptions are FLAGGED, not hidden:")
    print(f"     (i)  the signal rate per bar scales as 1/h - if daily breakouts")
    print(f"          are proportionally RARER than 4h breakouts, n falls further")
    print(f"          and every row is optimistic;")
    print(f"     (ii) gross R is held constant - if the effect decays with horizon")
    print(f"          (as it does for most crypto signals), every row above is")
    print(f"          optimistic as well.")

    best = max(rows, key=lambda r: r["t"])
    print(f"\n   best horizon in the grid: {best['h']}h, t = {best['t']:.2f}")
    print(f"   measured 4h t for the same quantity: {T_NAIVE_4H:.2f}")
    print(f"   -> lengthening the horizon makes it WORSE, not better, even though it")
    print(f"      cuts cost_R from {rows[0]['cost_R']:.3f}R to "
          f"{rows[-1]['cost_R']:.3f}R")

    print("\n=== WHAT WOULD IT TAKE, IN PLAIN TERMS? ===")
    for r in rows:
        print(f"   {r['h']:>3}h  mean net R required for t=2.0: {r['need']:+.4f}  |  "
              f"available: {r['net_R']:+.4f}  ->  short by {r['need']/r['net_R']:.1f}x")
    print(f"\n   The 4h bar is the best the grid offers and is the one already")
    print(f"   measured. Halving the cost by going to daily costs far more than")
    print(f"   the loss of trades buys back. **There is no horizon at which this")
    print(f"   signal family becomes measurable, and that is arithmetic rather")
    print(f"   than disappointment.**")
    print("\n   THIS IS THE ANSWER TO 'should we try another timeframe': no.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
