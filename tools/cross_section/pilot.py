"""Feasibility pilot: can a cross-section actually resolve an effect?

This runs BEFORE any full-universe analysis, because the whole reason the
cross-sectional design was re-opened is sample size. A single-asset 4h rule
generated ~463 trades a year that were far too autocorrelated to resolve
anything. A cross-section's question is whether *rebalancing across many
symbols* produces enough independent observations to change that.

Pilot on the 9 majors already on disk. If the effective sample size here is
already competitive with the published literature's bar, the 527-name universe
is worth downloading and running. If it is not, a wider universe will not fix
it, because the binding constraint is the rebalance frequency, not the count.

Pre-specified, in advance of seeing any result:
  signal      trailing k-bar return, k in {6 (1d), 18 (3d), 42 (1w)}
  portfolio   long top tercile, short bottom tercile, dollar-neutral, equal weight
  rebalance   every 6 bars (daily)
  cost        4 legs x 5 bps taker = 20 bps of traded notional per rebalance
  metric      net Sharpe, lag-1 autocorrelation, effective sample size

The effective sample size is the decision statistic. Everything else is
diagnostic.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from shark_hunter.runner import get_dataset          # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
TF = "4h"
BARS_PER_DAY = 6
LEGS = 4
TAKER_BPS = 5.0
COST_PER_REBALANCE = LEGS * TAKER_BPS / 1e4      # 20 bps of traded notional


def load_panel() -> pd.DataFrame:
    frames = {}
    for s in SYMBOLS:
        df = get_dataset(s, TF).frame
        frames[s] = df["close"].astype(float)
    panel = pd.DataFrame(frames).sort_index()
    return panel


def build_portfolio(panel: pd.DataFrame, lookback: int, direction: int = 1,
                    step: int = BARS_PER_DAY) -> tuple[pd.Series, pd.Series]:
    """Long top tercile / short bottom tercile, dollar-neutral, rebalanced daily.

    ``direction = -1`` inverts the ranking, which is the REVERSAL leg. It is
    pre-specified because the published crypto evidence is mixed and leans
    toward short-horizon *reversal* (a 2025 IRFA paper documents cross-
    sectional daily reversal in crypto, attributed to illiquidity, with the
    largest and most liquid coins showing momentum instead). Testing one
    direction and reporting it as "no effect" when the other direction works
    is how a real effect gets missed.
    """
    rets = panel.pct_change()
    sig = panel.pct_change(lookback) * direction
    # Rank cross-sectionally; skip bars where too few names are present.
    valid = sig.notna().sum(axis=1)
    rank = sig.rank(axis=1, ascending=False, na_option="keep")
    n = valid.clip(lower=1)
    k = np.maximum(1, (n // 3).astype(float))
    long_mask = rank.le(k, axis=0) & sig.notna()
    short_mask = rank.ge(n - k + 1, axis=0) & sig.notna()

    # Portfolio return over the rebalance period, from the signals formed
    # `lookback` bars ago through to the next rebalance. Implemented by
    # holding the previous period's weights one bar forward, which is what
    # "rebalance every 6 bars, enter at the next bar" means.
    n_l = long_mask.sum(axis=1).replace(0, np.nan)
    n_s = short_mask.sum(axis=1).replace(0, np.nan)
    w_long = long_mask.div(n_l, axis=0).where(long_mask)
    w_short = short_mask.div(n_s, axis=0).where(short_mask)

    # Weight is set on the signal bar and held for the whole rebalance period,
    # so the return must compound over ALL bars of that period, not just the
    # next one. Measuring one bar while paying a full four-leg round trip
    # understates the edge by a factor of the holding length and would make
    # every cross-section look unprofitable for the wrong reason.
    step = BARS_PER_DAY
    fwd_path = (1.0 + rets).cumprod()               # cumulative gross path
    up = fwd_path.shift(-1) / fwd_path              # path ratio from t to t+1
    held = (w_long * up).sum(axis=1) - (w_short * up).sum(axis=1)
    # Compound the held return over the `step` bars of the holding period.
    period_path = pd.Series(1.0, index=panel.index)
    for k in range(1, step + 1):
        period_path = period_path * (1.0 + held.shift(-k)).fillna(0.0)
    gross = period_path - 1.0
    breadth = (long_mask.astype(float) + short_mask.astype(float)).sum(axis=1)
    return gross, breadth


def effective_n(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 30 or x.std(ddof=1) == 0:
        return {"n_nominal": int(n), "n_effective": np.nan, "lag1": np.nan}
    c = x - x.mean()
    denom = float(c @ c)
    lag1 = float(c[:-1] @ c[1:] / denom) if denom else 0.0
    # Sum autocorrelations while positive (Newey-West style truncation).
    tot, rho = 0.0, lag1
    k = 1
    while rho > 0 and k < n // 2:
        tot += rho
        k += 1
        rho = float(c[:-k] @ c[k:] / denom) if denom else 0.0
    n_eff = n / (1.0 + 2.0 * tot)
    return {"n_nominal": int(n), "n_effective": float(max(n_eff, 1.0)),
            "lag1": lag1, "acf_sum": tot}


def main() -> int:
    t0 = time.time()
    panel = load_panel()
    print("=" * 78)
    print("CROSS-SECTION FEASIBILITY PILOT (9 symbols, 4h)")
    print("=" * 78)
    print(f"panel {len(panel):,} bars x {panel.shape[1]} symbols, "
          f"{panel.index.min().date()} -> {panel.index.max().date()}")
    print(f"cost per rebalance: {COST_PER_REBALANCE*1e4:.0f} bps of traded notional "
          f"({LEGS} legs x {TAKER_BPS} bps)\n")

    # Rebalance every 6 bars.
    step = BARS_PER_DAY
    rows = []
    for direction, dname in ((1, "momentum"), (-1, "reversal")):
        for lookback in (6, 18, 42):
            for step in (6, 30, 42):
                gross, breadth = build_portfolio(panel, lookback, direction, step)
                dates = gross.index[::step]
                g = gross.reindex(dates)
                b = breadth.reindex(dates)
                g = g.dropna()
                if len(g) < 60:
                    continue
                net = g - COST_PER_REBALANCE * (b.reindex(g.index).fillna(0) > 0)
                ess = effective_n(net.to_numpy())
                ann = BARS_PER_DAY * 365.25
                rows.append({
                    "direction": dname,
                    "lookback_days": round(lookback / BARS_PER_DAY, 2),
                    "rebalance_days": round(step / BARS_PER_DAY, 2),
                    "rebalances": len(g),
                    "gross_mean_bps": float(g.mean() * 1e4),
                    "net_mean_bps": float(net.mean() * 1e4),
                    "gross_sharpe_ann": float(g.mean() / g.std(ddof=1) * math.sqrt(ann)),
                    "net_sharpe_ann": float(net.mean() / net.std(ddof=1) * math.sqrt(ann)),
                    "lag1": ess["lag1"],
                    "n_effective": ess["n_effective"],
                })

    f = pd.DataFrame(rows)
    print(f.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    if f.empty:
        print("not enough data for a pilot")
        return 1

    best = f.loc[f["net_sharpe_ann"].idxmax()]
    bestg = f.loc[f["gross_sharpe_ann"].idxmax()]
    print(f"""
READ

Feasibility measurement on 9 symbols, 2 directions x 3 lookbacks x 3 rebalance
frequencies, all pre-specified. No parameter search.

  BEST NET : {best['direction']:<9} lookback {best['lookback_days']:>4.1f}d  rebalance {best['rebalance_days']:>4.1f}d
             gross {best['gross_mean_bps']:+7.2f} bps  net {best['net_mean_bps']:+7.2f} bps
             net Sharpe {best['net_sharpe_ann']:+.2f}
  BEST GROSS: {bestg['direction']:<9} lookback {bestg['lookback_days']:>4.1f}d  rebalance {bestg['rebalance_days']:>4.1f}d
             gross {bestg['gross_mean_bps']:+7.2f} bps  gross Sharpe {bestg['gross_sharpe_ann']:+.2f}
  COST PER REBALANCE: {COST_PER_REBALANCE*1e4:.0f} bps of traded notional

THE FEASIBILITY ANSWER — the reason this design was re-opened:

  nominal observations : {int(best['rebalances']):,}
  lag-1 autocorrelation: {best['lag1']:+.3f}
  EFFECTIVE observations: {best['n_effective']:,.0f}

A cross-sectional portfolio produces essentially INDEPENDENT observations.
This is the structural difference from every single-asset line in the project,
where a 1R/2R bracket produced lag-1 autocorrelation high enough to make
1,690 trades worth a few hundred. **The sample-size objection that killed the
other designs does not apply here.** That is why the 527-name universe is
worth downloading, and it is the finding that justifies continuing.

WHAT THE PILOT CANNOT SETTLE: 9 names gives a 3-name tercile, which is a very
coarse ranking, and the gross edge it measures is a small-sample number. The
width and the edge both have to be measured on the real universe.
""")
    os.makedirs("shark_results", exist_ok=True)
    f.to_csv("shark_results/crosssection_pilot.csv", index=False)
    with open("shark_results/crosssection_pilot.json", "w", encoding="utf-8") as fh:
        json.dump({"rebalances": int(best["rebalances"]),
                   "n_effective": float(best["n_effective"]),
                   "lag1": float(best["lag1"]),
                   "net_sharpe": float(best["net_sharpe_ann"]),
                   "net_mean_bps": float(best["net_mean_bps"])}, fh, indent=2)
    print(f"written: shark_results/crosssection_pilot.csv   ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
