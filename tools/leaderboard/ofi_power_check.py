"""AGENTS.md 1a POWER CHECK for the tick-level order-flow line, BEFORE any download.

Question: if we upgrade from kline-aggregated taker-buy volume to TICK-LEVEL signed
volume, can the experiment produce a verdict?

This script does not test the signal. It tests whether the test is capable of
answering, and it does that with the cheapest possible evidence: the dispersion of
the thing being predicted, measured on data already on disk.

THE HURDLE IS FIXED AND MEASURED, NOT ASSUMED
---------------------------------------------
    cost = 12.0 bps  (calm, measured, RESEARCH_STATE.md 1b)
    cost = 34.9 bps  (COVID, measured)
A lift below 12 bps is not a weak result, it is a dead one. So the only question is
whether the design can resolve a lift of that size, and against what.

WHAT IS ACTUALLY AVAILABLE (checked, not assumed)
-------------------------------------------------
Binance Vision publishes for spot:  trades, aggTrades, bookDepth (percentage bands),
bookTicker.  It does NOT publish L2 quote updates, so the Cont-Kuo-Stoikov order-flow
imbalance in its textbook form is NOT obtainable for these venues. What IS obtainable
is tick-level SIGNED TRADE VOLUME, which is a different thing from what the repo
already measured (kline taker-buy aggregate) only in its within-bar path.
"""
import os

import numpy as np
import pandas as pd

DATADIR = "user_data/data_leaderboard"
COST_CALM, COST_COVID = 12.0, 34.9  # bps round trip, measured

rows = []
pairs = sorted(
    os.path.basename(f)[: -len("-5m.feather")]
    for f in os.listdir(DATADIR) if f.endswith("-5m.feather")
)
for p in pairs[:12]:
    path = os.path.join(DATADIR, f"{p}-5m.feather")
    if not os.path.exists(path):
        continue
    d = pd.read_feather(path, columns=["close"])
    c = d["close"].to_numpy(dtype="float64")
    for h, name in ((1, "1bar_5m"), (3, "3bar_15m"), (12, "12bar_1h")):
        fwd = np.full(len(c), np.nan)
        fwd[:-h] = c[h:] / c[:-h] - 1.0
        fwd = fwd[~np.isnan(fwd)]
        rows.append(dict(pair=p, horizon=name, sd_bps=fwd.std(ddof=1) * 1e4, n=len(fwd)))

df = pd.DataFrame(rows)
agg = df.groupby("horizon")["sd_bps"].agg(["mean", "min", "max"])
agg["bars_per_pair"] = df.groupby("horizon")["n"].mean()
print("Per-signal dispersion of forward returns, measured on 12 pairs x 2021-2026")
print(f"{'horizon':>10s} {'sd_bps(mean)':>13s} {'sd_bps(min)':>12s} {'sd_bps(max)':>12s} {'bars/pair':>11s}")
for h, r in agg.iterrows():
    print(f"{h:>10s} {r['mean']:13.2f} {r['min']:12.2f} {r['max']:12.2f} {r['bars_per_pair']:11.0f}")

print(f"""
MINIMUM DETECTABLE LIFT, on the GROSS series
--------------------------------------------
A conditional signal's lift has standard error  ~ sd / sqrt(n_eff).  This repo's rule
(AGENTS.md 3.1) is that n is the EFFECTIVE count after a dependence correction, and
that the block bootstrap over the time-sorted signal sequence is the only admissible
estimator. A 5m bar carries a 1-bar serial dependence; taking IAT = 3 as the working
value (the repo's own measured range is 5.9-12 for denser series, 1.0 for the
cross-sectional portfolio), the effective count is n/3.

Bars available: {int(agg.loc['1bar_5m','bars_per_pair']*len(pairs[:12])):,} across 12 pairs,
~{int(agg.loc['1bar_5m','bars_per_pair']*33):,} across 33. Assume only 5% of bars fire
a given signal, which is already generous for an OFI-style condition.
""")

sd1 = agg.loc["1bar_5m", "mean"]
n1_12 = agg.loc["1bar_5m", "bars_per_pair"] * 12
n1_33 = agg.loc["1bar_5m", "bars_per_pair"] * 33

print(f"{'signal rate':>12s} {'n_eff (33 pairs, IAT=3)':>25s} {'MDE @ t=2.0':>13s} {'MDE @ t=3.0':>13s}")
for rate in (0.02, 0.05, 0.10, 0.25):
    n_eff = n1_33 * rate / 3.0
    mde2 = sd1 / np.sqrt(n_eff) * 2.0
    mde3 = sd1 / np.sqrt(n_eff) * 3.0
    print(f"{rate*100:11.0f}% {n_eff:25,.0f} {mde2:12.1f}bps {mde3:12.1f}bps")

print(f"""
READ THIS BEFORE DOWNLOADING ANYTHING
--------------------------------------
The bar for a usable lift is {COST_CALM:.1f} bps (calm) to {COST_COVID:.1f} bps (COVID).
The only horizon at which the measured dispersion is small enough for a 12 bps effect
to be resolvable is 1bar_5m, and only with a very high signal rate.
""")
sd1h = agg.loc["1bar_5m", "mean"]
n_needed = (sd1h * 3.0 / COST_CALM) ** 2 * 3.0  # t=3 (the corrected bar), IAT=3
print(f"To resolve a {COST_CALM:.1f} bps lift at the CORRECTED bar t=3.0 with IAT=3 and a 5% signal rate,")
print(f"one needs n_eff = {n_needed:,.0f} effective signal observations, i.e.")
print(f"n_signal = {n_needed*3:,.0f}, i.e. {n_needed*3/0.05:,.0f} bars scanned, i.e.")
print(f"{n_needed*3/0.05/agg.loc['1bar_5m','bars_per_pair']:.0f} pair-years of 5m data.")

print(f"""
AND THE REPO ALREADY LOOKED AT THE PARENT OF THIS
--------------------------------------------------
The 5m factor scan (PREREG_FACTOR_SCAN_2026-09-27) measured bar-level signed volume
(CVD), RVOL and VWAP deviation on 9 symbols x 3.47M bars, both directions, 20 buckets
each. Best gross edge ANYWHERE: 2.47 bps, against a 12.0 bps calm round trip - short
by 5x. CVD specifically: t_adj 0.54 long / -0.88 short.

Tick-level signed volume is the SAME statistic with the within-bar path retained. The
repo has not established that the path matters; it has established that the aggregate
does not. The question this line poses is narrow: does within-bar sequencing carry
information the bar aggregate does not?

That is a real question, and it is testable - but only after the power check above is
passed, and the power check must be read against the cost hurdle, not against t=2.0.
""")
