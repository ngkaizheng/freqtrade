"""
Verify the fatal claim: is the E#4 gross edge 0.274%/day, or is that a
formula artefact?

`e4_feasibility.py` computed the edge as  DEC * |IC| * sigma  = 3.51 * 0.0195
* 4.02%. That is a Gaussian linear-map identity: the expected return of a
decile long-short portfolio when the signal has a given linear correlation with
the return. It assumes jointly normal, linear dependence.

The adversarial review claims the ACTUAL decile portfolio earns 0.0160%/day
with t = 0.22, i.e. 17x less, and that the signal is therefore not significant
at the portfolio level even though the IC is.

Both can be measured. The IC is a rank correlation; the portfolio is a
sort-and-hold. They are different objects and they are allowed to disagree --
that gap is the whole point of this check.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\verify_claim1.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"
REBASE = -0.90
DEC = 3.51


def load():
    frames = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if (d["close"].pct_change() < REBASE).any():
            continue
        frames[sym] = d["close"]
    return pd.concat(frames, axis=1).sort_index()


def spearman_ic(sig: pd.Series, fwd: pd.Series) -> float:
    j = pd.concat([sig.rename("s"), fwd.rename("f")], axis=1).dropna()
    if len(j) < 20:
        return float("nan")
    return float(j["s"].rank().corr(j["f"].rank()))


def pearson_ic(sig: pd.Series, fwd: pd.Series) -> float:
    j = pd.concat([sig.rename("s"), fwd.rename("f")], axis=1).dropna()
    if len(j) < 20:
        return float("nan")
    return float(j["s"].corr(j["f"]))


def main() -> None:
    px = load()
    rets = px.pct_change(fill_method=None)
    fwd = rets.shift(-1)
    sig = rets                      # yesterday's return, known at today's close

    print("=" * 82)
    print("1. THE IC, THREE WAYS")
    print("=" * 82)
    dates = [d for d in rets.index if d in fwd.index]
    sp, pe = [], []
    for d in dates:
        a, b = sig.loc[d], fwd.loc[d]
        j = pd.concat([a.rename("s"), b.rename("f")], axis=1).dropna()
        if len(j) < 20:
            continue
        sp.append(j["s"].rank().corr(j["f"].rank()))
        pe.append(j["s"].corr(j["f"]))
    sp, pe = np.array(sp), np.array(pe)
    for name, arr in [("Spearman", sp), ("Pearson", pe)]:
        t = arr.mean() / arr.std(ddof=1) * math.sqrt(len(arr))
        print(f"  {name:<9} mean {arr.mean():+.5f}   t {t:+.2f}   n {len(arr)}")

    print()
    print("=" * 82)
    print("2. THE ACTUAL DECILE LONG-SHORT PORTFOLIO -- reversal, equal weight")
    print("=" * 82)
    rows, prev = [], None
    for d in dates:
        a, b = sig.loc[d], fwd.loc[d]
        j = pd.concat([a.rename("s"), b.rename("f")], axis=1).dropna()
        if len(j) < 30:
            continue
        k = max(1, int(round(len(j) * 0.10)))
        longs = j["s"].nsmallest(k).index        # buy the losers
        shorts = j["s"].nlargest(k).index       # sell the winners
        w = pd.Series(0.0, index=longs.union(shorts))
        w.loc[longs] = 0.5 / k
        w.loc[shorts] = -0.5 / k
        gross = float(w.reindex(j.index).fillna(0.0).mul(j["f"]).sum())
        turnover = (float(w.abs().sum()) if prev is None
                    else float((w - prev.reindex(w.index).fillna(0.0)).abs().sum()))
        prev = w
        rows.append({"date": d, "gross": gross, "turnover": turnover})
    res = pd.DataFrame(rows).set_index("date")
    n = len(res)
    t = res["gross"].mean() / res["gross"].std(ddof=1) * math.sqrt(n)
    print(f"  rebalances          {n}")
    print(f"  mean gross per day  {res['gross'].mean()*100:+.5f}%")
    print(f"  t                   {t:+.2f}")
    print(f"  annualised gross    {res['gross'].mean()*365*100:+.2f}%")
    print(f"  mean turnover       {res['turnover'].mean():.2f}")
    eq = (1 + res["gross"]).cumprod()
    print(f"  cumulative gross    {(eq.iloc[-1]-1)*100:+.1f}%   max dd "
          f"{float((eq/eq.cummax()-1).min())*100:+.1f}%")

    sigma = float(rets.std(axis=1).mean())
    print()
    print("=" * 82)
    print("3. THE FORMULA THE REPORTS USED, AGAINST THE PORTFOLIO IT DESCRIBES")
    print("=" * 82)
    for name, ic in [("Spearman", float(np.nanmean(sp))), ("Pearson", float(np.nanmean(pe)))]:
        implied = DEC * abs(ic) * sigma
        print(f"  {name:<9} 3.51 x |IC| x sigma = 3.51 x {abs(ic):.5f} x "
              f"{sigma*100:.2f}% = {implied*100:.4f}%/day")
    print(f"  ACTUAL decile portfolio          = {res['gross'].mean()*100:+.4f}%/day")
    ratio = (DEC * abs(float(np.nanmean(sp))) * sigma) / abs(res["gross"].mean())
    print(f"\n  ratio: formula overstates by {ratio:.1f}x")
    print(f"  breakeven round trip implied by the FORMULA : "
          f"{res['gross'].mean()/res['turnover'].mean()*1e4:.1f} bps")
    print(f"  breakeven round trip implied by the PORTFOLIO: "
          f"{res['gross'].mean()/res['turnover'].mean()*1e4:.1f} bps")

    print()
    print("=" * 82)
    print("4. BY YEAR -- is the edge even still there?")
    print("=" * 82)
    res["year"] = res.index.year
    y = res.groupby("year")["gross"].agg(["mean", "count"])
    y["t"] = y["mean"] / res.groupby("year")["gross"].std(ddof=1) * np.sqrt(y["count"])
    print(y.round(6).to_string())
    print("""
  The IC and the portfolio are different objects. A significant rank
  correlation does NOT imply a significant long-short portfolio, and the size
  of the gap between them is the honest measure of how much of the IC is
  expressible as a tradeable spread.""")


if __name__ == "__main__":
    main()
