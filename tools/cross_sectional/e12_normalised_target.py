"""
E#12 -- the CANONICAL Moreira-Muir rule versus the fixed 20% target E#8 used.

WHY
---
E#8 used exposure = 0.20 / realised_vol. That is an ABSOLUTE annualised
target. The canonical rule in Moreira & Muir (JF 72(4) 2017) is NORMALISED:
exposure is the inverse of forecast variance scaled by a constant that
preserves the strategy's own unconditional volatility, so AVERAGE LEVERAGE IS
ABOUT 1 and the "target" is an endogous property of the asset, not a number
you pick.

Guo & Liu (SSRN 3385377) object to precisely the arbitrary constant in the
weight factor -- which is the fixed-target rule. No canonical paper uses an
absolute target and none validates 20%.

And Moreira & Muir's own Figure 3 says the failure mode is the opposite of the
intuition the fixed target embodies: "Our strategy takes relatively more risk
when volatility is low (e.g., the 1960's) hence its losses are not
surprisingly concentrated in these times." A fixed 20% target is LONG when
realised vol is below 20% -- it levers UP in exactly the calm periods their
paper identifies as the danger.

So the fixed 20% may be working for the wrong reason, and it may be levering
into the documented failure mode. The normalised rule has average leverage ~1
by construction and cannot.

ALSO: Cheng, Deng, Wang & Yu (Applied Economics 53(47), 2021,
doi 10.1080/00036846.2021.1922597, peer-reviewed; free preprint arXiv:2102.04591)
report that force-liquidated BitMEX investors used average leverage ~60x, and
that "the normal distribution assumption on return significantly
underestimates margin levels by at least 50%" (measured daily excess kurtosis
65.36). Any vol target is Gaussian-calibrated. This script therefore also
reports the overlay's realised effective leverage and its tail, so the
Gaussian assumption can be checked rather than assumed.

PRE-REGISTERED
--------------
Rules compared, all reported, none selected:
  A. fixed target,        exposure = T / realised_vol,  T in {10%, 20%, 35%, 50%}
  B. NORMALISED (Moreira-Muir), exposure = (uncond_vol / realised_vol) x
     leverage_scale, rescaled so mean exposure over the sample = 1
Reported per rule: CAGR, max drawdown, Sharpe (naive AND IAT-adjusted), mean
and max effective leverage, and the p99 of the exposure.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 250)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
VOL_WINDOW = 30
DAYS = 365
COST_RT = (3.6 + 10.0) / 1e4
REBASE = -0.90
FIXED_TARGETS = (0.10, 0.20, 0.35, 0.50)
LEVERAGE_SCALES = (1.0, 1.5, 2.0)


def load():
    closes, vols = {}, {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close", "quote_volume"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        d = d[d["quote_volume"] > 0]
        if (d["close"].pct_change() < REBASE).any():
            continue
        closes[sym] = d["close"]
        vols[sym] = d["quote_volume"]
    return (pd.concat(closes, axis=1).sort_index(),
            pd.concat(vols, axis=1).sort_index())


def iat(x):
    v = np.asarray(x, float)
    x_ = v - v.mean()
    den = float((x_ ** 2).sum())
    if den <= 0:
        return 1.0
    tau = 1.0
    for lag in range(1, 31):
        rho = float((x_[lag:] * x_[:-lag]).sum() / den)
        if rho <= 0:
            break
        tau += 2 * rho
    return tau


def evaluate(r, expo, label, rule, params):
    strat = r * expo
    to = expo.diff().abs().fillna(expo.abs())
    net = strat - to * COST_RT
    eq = (1 + net).cumprod()
    years = len(net) / DAYS
    tau = iat(net.to_numpy())
    return {
        "rule": rule,
        "params": params,
        "label": label,
        "cagr_pct": float((eq.iloc[-1] ** (1 / years) - 1) * 100),
        "max_dd_pct": float((eq / eq.cummax() - 1).min() * 100),
        "sharpe_naive": float(net.mean() / net.std(ddof=1) * math.sqrt(DAYS)),
        "sharpe_adj": float(net.mean() / net.std(ddof=1) * math.sqrt(DAYS) / math.sqrt(tau)),
        "iat": tau,
        "mean_exposure": float(expo.mean()),
        "max_exposure": float(expo.max()),
        "p99_exposure": float(expo.quantile(0.99)),
        "turnover_per_year": float(to.mean() * DAYS),
    }


def main() -> int:
    px, qv = load()
    uni = list(qv.median().nlargest(TOP_N).index)
    basket = px[uni].mean(axis=1).ffill()
    r = basket.pct_change(fill_method=None).fillna(0.0)
    rv = r.rolling(VOL_WINDOW).std().shift(1) * math.sqrt(DAYS)
    uncond = float(rv.mean())

    print(f"basket: top {TOP_N} liquid names, {len(r)} bars")
    print(f"mean realised vol: {uncond*100:.1f}%/yr  (p10 {rv.quantile(0.1)*100:.0f}%, "
          f"p90 {rv.quantile(0.9)*100:.0f}%)")
    bh = (1 + r).cumprod()
    print(f"buy-and-hold: CAGR {((bh.iloc[-1])**(DAYS/len(r))-1)*100:+.1f}%  "
          f"maxDD {(bh/bh.cummax()-1).min()*100:+.1f}%  "
          f"Sharpe {r.mean()/r.std(ddof=1)*math.sqrt(DAYS):+.2f}\n")

    results = []
    for t in FIXED_TARGETS:
        e = (t / rv).clip(0.0, 4.0).fillna(0.0)
        results.append(evaluate(r, e, f"fixed {t:.0%}", "A_fixed", {"target": t}))

    for k in LEVERAGE_SCALES:
        raw = uncond / rv
        e = (raw * k).clip(0.0, 4.0).fillna(0.0)
        e = e * (1.0 / e[e > 0].mean())        # normalise mean exposure to 1
        results.append(evaluate(r, e, f"normalised, scale {k}", "B_normalised",
                                {"leverage_scale": k}))

    out = pd.DataFrame(results)
    print("=" * 118)
    print("FIXED TARGET (what E#8 used) versus NORMALISED (the canonical Moreira-Muir rule)")
    print("=" * 118)
    print(f"{'rule':<26}{'CAGR%':>9}{'maxDD%':>9}{'Sharpe':>8}{'SharpeAdj':>11}"
          f"{'mean exp':>10}{'p99 exp':>9}{'max exp':>9}{'turn/yr':>9}")
    print("-" * 110)
    for _, x in out.iterrows():
        print(f"{x['label']:<26}{x['cagr_pct']:>9.1f}{x['max_dd_pct']:>9.1f}"
              f"{x['sharpe_naive']:>8.2f}{x['sharpe_adj']:>11.2f}"
              f"{x['mean_exposure']:>10.2f}{x['p99_exposure']:>9.2f}"
              f"{x['max_exposure']:>9.2f}{x['turnover_per_year']:>9.1f}")

    print("""
  The normalised rows hold MEAN exposure at 1 by construction, so their max and
  p99 exposure is the real story: that is the leverage the strategy actually
  runs when the market is calm, and Moreira & Muir identify exactly that
  condition as where their losses concentrated.

  Cheng et al. (Applied Economics 2021) measured force-liquidated BitMEX
  investors at average leverage ~60x and report that a normal distribution
  understates required margin by at least 50% (daily excess kurtosis 65.36).
  Every vol target is Gaussian-calibrated. If p99 exposure here is large, the
  Gaussian assumption is doing work nobody has validated.""")

    (OUT / "e12_result.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwritten {OUT / 'e12_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
