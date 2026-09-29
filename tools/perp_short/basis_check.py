"""DIAGNOSIS: is the perp basis still dislocated from its no-arbitrage price?

WHY THIS EXISTS — A CORRECTION TO WHAT THIS PROJECT CLOSED
----------------------------------------------------------
`RESEARCH_STATE.md` closes the funding/basis carry line, and the reason given is
that the funding **excess** is negative: -0.88 %/yr on the full panel to
-1.56 %/yr on the common intersection, with BTC at +0.62 %/yr, and 43% of the
"carry" being an exchange parameter rather than a risk premium (the modal
settlement equals the administered parameter exactly).

**That closed the wrong object.** He, Manela, Ross & von Wachter, "Fundamentals of
Perpetual Futures" (arXiv:2212.06888, v7 2026-09-17) price the perp against a
no-arbitrage benchmark that absorbs the interest rate and the funding clamp:

    F_t = (1 - Phi^-1(r))^-1 * S_t

and trade the **deviation of the futures price from that benchmark**, not the
funding rate. **The funding payment is a transfer; the basis is the thing that
can be mispriced.** Their headline, for Binance BTC perps and RETAIL costs:

    Sharpe 3.35 under high trading costs, and **3.27 after additionally charging
    the effective bid-ask spread** (10.46 / 11.65 for fee-free market makers).

That is cost-adjusted, on this venue, and this repo has never tested it. Before
building anything, the question is only: **is the dislocation still there in
2023-2026?** The same paper says deviations shrink ~22 percentage points a year
and were compressed by Binance's April 2022 portfolio margining - which is a
strong prior that the answer may be no.

THE NO-ARBITRAGE PREMIUM, DERIVED NOT ASSUMED
----------------------------------------------
Binance's funding rate is  clamp(average premium index over 8h, -0.05%, +0.05%)
+ 0.01%.  Writing p = (F-S)/F for the premium index and Phi for the funding
function, the no-arbitrage condition Phi(p*) = r gives

    p* = Phi^-1(r) = clamp(r - 0.0001, -0.0005, +0.0005)

and the fair futures price is F = S / (1 - p*). At a 5%/yr USD rate, r =
0.0000137/day, so p* = -0.0000863 - i.e. **the perp should sit about 0.86 bps
BELOW spot on average.** The clamp binds only if r drifts more than 60 bps from
the 1 bp admin rate, which it does not, so the sensitivity to the rate assumption
is the rate assumption itself, and it is reported.

This script introduces no strategy, no threshold and no parameter search. It
measures one number per pair per day.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\basis_check.py
"""

from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

SPOT_DIR = "user_data/data/binance"
PERP_DIR = "user_data/data/wide104/futures"
OUT = "user_data/perp_short_out/basis_check.csv"

FUND_ADMIN = 0.0001        # Binance: +0.01% when the premium is unclamped
CLAMP = 0.0005             # +-0.05% clamp on the premium component
HOLD = 7                   # days; the paper's random-maturity unwind is a
#                            bounded stopping time, so a horizon must be stated


def no_arb_premium(r_annual: float) -> float:
    r_daily = r_annual / 365.25
    return float(np.clip(r_daily - FUND_ADMIN, -CLAMP, CLAMP))


def base(sym: str) -> str:
    """Normalise to the base asset. Spot files are 'AAVE_USDT-1d.feather' while
    perp files are 'AAVE_USDT_USDT-4h-futures.feather' (freqtrade's
    pair_to_filename), so a naive split('-')[0] comparison gives ZERO overlap
    on a file inventory that plainly contains 47 common names."""
    s = sym
    for suf in ("_USDT_USDT", "_USDT", "_USDC", "_BTC"):
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def main() -> int:
    spot = {base(os.path.basename(f).split("-")[0]): f
            for f in glob.glob(os.path.join(SPOT_DIR, "*-1d.feather"))}
    perps = {}
    for f in glob.glob(os.path.join(PERP_DIR, "*-1d-futures.feather")):
        b = os.path.basename(f)
        perps[base(b.split("-")[0])] = f
    if not spot:
        raise SystemExit(f"no 1d spot under {SPOT_DIR}")
    if not perps:
        # perp panel is 4h; derive 1d from it
        for f in glob.glob(os.path.join(PERP_DIR, "*-4h-futures.feather")):
            b = os.path.basename(f)
            perps[base(b.split("-")[0])] = f
        print(f"no 1d perp files; using the 4h panel ({len(perps)} symbols) "
              f"and resampling to 1d")
    both = sorted(set(spot) & set(perps))
    print(f"spot 1d: {len(spot)} pairs   perp: {len(perps)} symbols   "
          f"OVERLAP: {len(both)}")
    if len(both) < 5:
        raise SystemExit("not enough overlap to say anything")
    print(f"pairs: {', '.join(both[:20])}{'...' if len(both) > 20 else ''}\n")

    for rate in (0.03, 0.05, 0.08):
        p_star = no_arb_premium(rate)
        print(f"  risk-free {rate:.0%}/yr -> r = {rate/365.25:.7f}/day -> "
              f"no-arb premium p* = {p_star*1e4:+.2f} bps "
              f"-> fair F/S = {1/(1-p_star):.6f}")
    p_star = no_arb_premium(0.05)

    rows = []
    for sym in both:
        s = pd.read_feather(spot[sym])[["date", "close"]].set_index("date")["close"]
        p = pd.read_feather(perps[sym])[["date", "close"]].set_index("date")["close"]
        if p.index.freq is None and len(p) > 30:
            try:
                p = p.resample("1D").last()
            except Exception:
                pass
        j = pd.concat([s.rename("spot"), p.rename("perp")], axis=1, join="inner").dropna()
        if len(j) < 200:
            continue
        prem = (j["perp"] - j["spot"]) / j["perp"]
        dev = prem - p_star
        # forward premium change over the hold = the convergence payoff,
        # market-neutral because spot and perp legs cancel the price move
        fwd = (prem.shift(-HOLD) - prem).to_numpy()[:-HOLD]
        d = dev.to_numpy()[:-HOLD]
        rows.append({"symbol": sym, "n": len(d),
                     "mean_dev_bps": float(np.nanmean(d) * 1e4),
                     "sd_dev_bps": float(np.nanstd(d) * 1e4),
                     "mean_prem_bps": float(np.nanmean(prem.to_numpy()[:-HOLD]) * 1e4),
                     "abs_dev_bps": float(np.nanmean(np.abs(d)) * 1e4),
                     "fwd_bps": float(np.nanmean(fwd) * 1e4)})

    df = pd.DataFrame(rows)
    if df.empty:
        print("no usable pairs")
        return 1
    print(f"\n=== THE PREMIUM vs THE NO-ARBITRAGE PRICE (1d, p* = {p_star*1e4:+.2f} bps) ===")
    print(f"{'symbol':<16}{'n':>7}{'mean prem':>12}{'mean dev':>11}{'sd dev':>10}"
          f"{'mean|dev|':>12}{'fwd 7d':>10}")
    for r in df.sort_values("mean_dev_bps").itertuples(index=False):
        print(f"{r.symbol:<16}{r.n:>7}{r.mean_prem_bps:>+11.1f}b{r.mean_dev_bps:>+10.1f}b"
              f"{r.sd_dev_bps:>9.1f}b{r.abs_dev_bps:>11.1f}b{r.fwd_bps:>+9.1f}b")
    print(f"\n  cross-pair: mean deviation {df['mean_dev_bps'].mean():+.1f} bps, "
          f"median {df['mean_dev_bps'].median():+.1f} bps, "
          f"mean |deviation| {df['abs_dev_bps'].mean():.1f} bps, "
          f"mean sd {df['sd_dev_bps'].mean():.1f} bps")
    print(f"  pairs with a POSITIVE mean deviation: {(df['mean_dev_bps'] > 0).sum()}"
          f"/{len(df)}")
    print(f"  pairs with |deviation| > 35 bps (one COVID round trip): "
          f"{(df['abs_dev_bps'] > 35).sum()}/{len(df)}")

    print("\n=== IS THE DISLOCATION DECLINING? (the paper says ~22pp/yr) ===")
    for sym in both[:1]:
        pass
    series = {}
    for sym in both:
        s = pd.read_feather(spot[sym])[["date", "close"]].set_index("date")["close"]
        p = pd.read_feather(perps[sym])[["date", "close"]].set_index("date")["close"]
        if p.index.freq is None and len(p) > 30:
            try:
                p = p.resample("1D").last()
            except Exception:
                pass
        j = pd.concat([s.rename("spot"), p.rename("perp")], axis=1, join="inner").dropna()
        if len(j) < 200:
            continue
        prem = (j["perp"] - j["spot"]) / j["perp"] - p_star
        g = prem.groupby(prem.index.year).agg(["mean", lambda x: np.mean(np.abs(x))])
        series[sym] = g
    yrs = sorted({y for g in series.values() for y in g.index})
    print(f"{'year':>7}{'n pairs':>10}{'mean dev (bps)':>18}{'mean |dev| (bps)':>20}")
    for y in yrs:
        ms = [g.loc[y, "mean"] * 1e4 for g in series.values() if y in g.index]
        ab = [g.loc[y, "<lambda_0>"] * 1e4 for g in series.values() if y in g.index]
        if ms:
            print(f"{y:>7}{len(ms):>10}{np.mean(ms):>+18.1f}{np.mean(ab):>20.1f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}")
    print("\nWHAT WOULD MAKE THIS WORTH BUILDING: a mean |deviation| that stays")
    print("well above the cost of a round trip on BOTH legs (this repo measures")
    print("12.0 bps calm to 34.9 bps COVID for ONE side, so a spot+perp pair pays")
    print("roughly double), a decay that has not taken it below that line, and")
    print("reversion that is not faster than the cost. None of that is decided")
    print("by this script - it is decided by the numbers above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
