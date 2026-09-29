"""
E#11 -- the actual Moskowitz-Ooi-Pedersen construction: long-short,
volatility-scaled, diversified across timeframes.

E#7 tested "time-series momentum" as long/cash at 126 days and found no
protection in 2022. That is not MOP. MOP is long-SHORT, VOLATILITY-SCALED, and
DIVERSIFIED ACROSS LOOKBACKS, and it reports that it "performs best during
extreme markets" -- the opposite of what E#7 found. This tests the real thing.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e11_mop.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
OUT = Path(__file__).resolve().parent

TOP_N = 50
LOOKBACK_DAYS = (21, 42, 63, 84, 126, 189, 252)     # 1,2,3,4,6,9,12 months
VOL_WINDOW = 30
TARGET_VOLS = (0.10, 0.15, 0.20)
CLIP = 4.0
COST_RT = (3.6 + 10.0) / 1e4
REBASE = -0.90
DAYS = 365


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


def main() -> int:
    px, qv = load()
    uni = list(qv.median().nlargest(TOP_N).index)
    px = px[uni]
    dates = px.index
    n, k = len(px), px.shape[1]
    print(f"universe: top {TOP_N} liquid names, {n} daily bars, "
          f"{dates[0].date()} -> {dates[-1].date()}")

    r = px.pct_change(fill_method=None).fillna(0.0)
    rv = r.rolling(VOL_WINDOW).std() * math.sqrt(DAYS)            # per-name annualised vol
    rv = rv.clip(lower=0.05)

    print()
    print("=" * 104)
    print("STEP 1 -- per-name, per-lookback: signal x inverse own volatility")
    print("=" * 104)
    # BOTH the signal and the volatility weight are decided one bar back.
    # The signal was shifted but the weight was not: `w = tv / rv` used rv
    # computed through t and was applied to r[t], so the position size was a
    # function of the return it earned. Same one-bar look-ahead the adversarial
    # review found in E#8. Stage 2 was already shifted; stage 1 was not.
    legs = {}
    for L in LOOKBACK_DAYS:
        sig = np.sign(px / px.shift(L) - 1.0)                   # +1 long, -1 short
        for tv in TARGET_VOLS:
            w = (tv / rv).clip(0.0, CLIP).shift(1)
            leg = (sig.shift(1) * w * r).sum(axis=1) / w.notna().sum(axis=1).replace(0, np.nan)
            legs[(L, tv)] = leg.fillna(0.0)

    print(f"{'lookback':>9} {'tgt vol':>9} {'ann ret%':>10} {'ann vol%':>10} {'Sharpe':>8} {'turnover/yr':>13}")
    print("-" * 66)
    for (L, tv), leg in legs.items():
        ann_r = leg.mean() * DAYS
        ann_v = leg.std(ddof=1) * math.sqrt(DAYS)
        to = leg.diff().abs().mean() * DAYS
        print(f"{L:>9}d {tv:>9.0%} {ann_r*100:>10.1f} {ann_v*100:>10.1f} "
              f"{ann_r/ann_v:>8.2f} {to:>13.1f}")

    print()
    print("=" * 104)
    print("STEP 2 -- aggregate across lookbacks, then a portfolio vol target (MOP stage 2)")
    print("=" * 104)
    agg = {}
    for tv in TARGET_VOLS:
        combined = pd.DataFrame({L: legs[(L, tv)] for L in LOOKBACK_DAYS}).mean(axis=1)
        agg[tv] = combined

    bench = r.mean(axis=1)
    bh = (1 + bench).cumprod()
    print(f"  buy-and-hold: CAGR {((bh.iloc[-1])**(DAYS/n)-1)*100:+.1f}%  "
          f"maxDD {(bh/bh.cummax()-1).min()*100:+.1f}%  "
          f"Sharpe {bench.mean()/bench.std(ddof=1)*math.sqrt(DAYS):+.2f}")

    print()
    print(f"{'stage-1 tgt':>12} {'stage-2 tgt':>12} {'CAGR%':>9} {'maxDD%':>9} "
          f"{'Sharpe':>8} {'turnover/yr':>13}")
    print("-" * 70)
    results = []
    for tv1 in TARGET_VOLS:
        base = agg[tv1]
        pvol = base.rolling(VOL_WINDOW).std() * math.sqrt(DAYS)
        for tv2 in TARGET_VOLS:
            expo = (tv2 / pvol).clip(0.0, CLIP).shift(1).fillna(0.0)
            gross = base * expo
            to = expo.diff().abs().fillna(expo.abs())
            net = gross - to * COST_RT
            eqc = (1 + net).cumprod()
            years = len(net) / DAYS
            cagr = (eqc.iloc[-1] ** (1 / years) - 1) * 100
            dd = (eqc / eqc.cummax() - 1).min() * 100
            sh = net.mean() / net.std(ddof=1) * math.sqrt(DAYS)
            results.append({"t1": tv1, "t2": tv2, "cagr": cagr, "dd": dd,
                            "sharpe": sh, "turnover": to.mean() * DAYS,
                            "mean_expo": expo.mean(), "series": net})
            print(f"{tv1:>12.0%} {tv2:>12.0%} {cagr:>9.1f} {dd:>9.1f} "
                  f"{sh:>8.2f} {to.mean()*DAYS:>13.1f}")

    print()
    print("=" * 104)
    print("THE MOP PREDICTION: does it hold up in a DOWN market?  (2022)")
    print("=" * 104)
    bh22 = (1 + bench).loc["2022"].prod() - 1
    print(f"  buy-and-hold 2022: {bh22*100:+.1f}%")
    for res in results:
        s = res["series"].loc["2022"]
        strat22 = (1 + s).prod() - 1
        ratio = strat22 / bh22 if bh22 else float("nan")
        tag = ""
        if ratio > 1.0:
            tag = "   <-- PROTECTED (loses less than holding)"
        print(f"  t1={res['t1']:.0%} t2={res['t2']:.0%}: {strat22*100:>+7.1f}%   "
              f"ratio {ratio:>5.2f}x{tag}")

    print()
    print("  E#7's long/cash 126d result, for comparison: ratio 0.96x")
    print("  MOP's published claim: the diversified portfolio 'performs best during")
    print("  extreme markets'.")

    best = max(results, key=lambda x: x["sharpe"])
    # The volatility overlay makes the return series autocorrelated BY
    # CONSTRUCTION -- exposure is a smooth 30-day function of volatility -- so a
    # naive sqrt(T) Sharpe overstates it. This is the same correction R1 made to
    # Phase C, and not applying it here would be holding a rule I wrote.
    print()
    print("=" * 104)
    print("SHARPE, NAIVE VERSUS DEPENDENCE-ADJUSTED")
    print("=" * 104)
    print(f"{'t1':>5} {'t2':>5} {'Sharpe naive':>14} {'IAT':>7} {'eff N':>8} {'Sharpe adj':>12}")
    print("-" * 60)
    for res in results:
        s = res["series"].to_numpy(float)
        x = s - s.mean()
        den = float((x ** 2).sum())
        tau = 1.0
        if den > 0:
            for lag in range(1, 31):
                rho = float((x[lag:] * x[:-lag]).sum() / den)
                if rho <= 0:
                    break
                tau += 2 * rho
        adj = res["sharpe"] * math.sqrt(1.0 / max(tau, 1.0))
        res["sharpe_adjusted"] = adj
        res["iat"] = tau
        res["effective_n"] = len(s) / max(tau, 1.0)
        print(f"{res['t1']:>5.0%} {res['t2']:>5.0%} {res['sharpe']:>14.2f} "
              f"{tau:>7.2f} {res['effective_n']:>8.0f} {adj:>12.2f}")
    print("""
  The adjusted column is the one to believe. Vol-targeting returns are serially
  correlated by construction, and this project has been bitten by exactly this
  three times: Phase C's 17 "significant" hypotheses, the 4h reversal signal,
  and the monthly reversal IC.""")

    out = {
        "experiment": "E#11",
        "note": "MOP construction; not a formal pre-registration; 7th look at this panel",
        "universe": "top 50 by median daily quote volume",
        "buy_and_hold_2022_pct": round(float(bh22 * 100), 2),
        "grid": [{k: v for k, v in res.items() if k != "series"} for res in results],
        "best_by_sharpe": {k: v for k, v in best.items() if k != "series"},
    }
    (OUT / "e11_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwritten {OUT / 'e11_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
