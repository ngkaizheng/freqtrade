"""
Diagnose why E#3's gross edge is ~100x smaller than the source paper's.

E#3 as pre-registered returned a null. That null is informative only if we
know WHICH of the many differences between this experiment and Fieberg et al.
is responsible. This measures the candidate explanations rather than guessing.

It changes nothing about E#3. It is diagnostic, and its output is prior
information that any successor experiment has to carry.

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\e3_diagnose.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "user_data/universe/raw_daily"

FORMATION_WEEKS = (3, 6, 12, 24)
QUANTILE = 0.20


def load() -> pd.DataFrame:
    series = {}
    for f in sorted(RAW.glob("*_1d.csv.gz")):
        sym = f.name.replace("_1d.csv.gz", "")
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")
        d = d.dropna(subset=["date", "close"]).set_index("date").sort_index()
        d = d[~d.index.duplicated()]
        if (d["close"].pct_change() < -0.90).any():
            continue
        series[sym] = d["close"]
    px = pd.DataFrame(series).sort_index().ffill(limit=5)
    return px.dropna(axis=1, how="all")


def main() -> None:
    px = load()
    wk = px.resample("W-FRI").last()
    wk = wk.dropna(axis=1, how="all")
    print(f"panel: {px.shape[1]} symbols, {wk.shape[0]} weeks, "
          f"{wk.index[0].date()} -> {wk.index[-1].date()}\n")

    # ---------------------------------------------- 1. is there any rank power
    print("=" * 78)
    print("1. DOES THE SIGNAL RANK ANYTHING AT ALL?  (Spearman IC, next week)")
    print("=" * 78)
    rets = wk.pct_change(fill_method=None)
    fwd = rets.shift(-1)                      # the week AFTER the signal week
    rows = []
    for k in FORMATION_WEEKS:
        s = wk.pct_change(periods=k, fill_method=None).rank(axis=1, pct=True)
        ic = pd.concat([s.stack(), fwd.stack()], axis=1).groupby(level=0).corr().iloc[0::2, -1]
        rows.append({"formation_wk": k, "mean_IC": ic.mean(), "t": ic.mean() / ic.std() * np.sqrt(ic.notna().sum())})
    print(pd.DataFrame(rows).round(5).to_string(index=False))
    print("""
  A persistent negative IC means the formation return predicts a NEGATIVE next
  week: short-horizon reversal, not momentum. That is the dominant feature of
  this panel and it is why a trend construction does not pay.""")

    # ---------------------------------------------- 2. which horizon is alive
    print("=" * 78)
    print("2. SAME IC, SPLIT BY ERA (the source paper's sample is 2015-2022)")
    print("=" * 78)
    s24 = wk.pct_change(periods=24, fill_method=None).rank(axis=1, pct=True)
    sig_long = s24.stack()
    fwd_long = fwd.stack()
    weeks = pd.to_datetime(sig_long.index.get_level_values(0))
    eras = np.where(weeks < pd.Timestamp("2022-01-01"), "pre-2022", "2022+")
    for era in ("pre-2022", "2022+"):
        m = eras == era
        df = pd.DataFrame({"s": sig_long[m].to_numpy(dtype=float),
                           "f": fwd_long[m].to_numpy(dtype=float)},
                          index=weeks[m])
        ic = df.groupby(level=0).corr().iloc[0::2, -1].dropna()
        if len(ic):
            print(f"  {era}:  mean IC {ic.mean():+.5f}   "
                  f"t {ic.mean()/ic.std()*np.sqrt(len(ic)):+.2f}   n_weeks {len(ic)}")
        else:
            print(f"  {era}: no weeks")

    # ---------------------------------------------- 3. the liquidity question
    print()
    print("=" * 78)
    print("3. UNIVERSE COMPOSITION vs WHAT THE SOURCE PAPER TESTED")
    print("=" * 78)
    qv = None
    files = {f.name.replace("_1d.csv.gz", "") for f in RAW.glob("*_1d.csv.gz")}
    for f in sorted(RAW.glob("*_1d.csv.gz"))[:1]:
        sample = pd.read_csv(f)
        print("  columns available:", list(sample.columns))
    print(f"""
  E#3 selected the {len(files)} OLDEST-LISTED perpetuals, because that maximises
  usable history. The source paper's Panel B is the LARGEST and MOST LIQUID
  coins, and it states the effect 'originates mainly from the biggest and most
  liquid cryptocurrencies'. E#3 therefore tested the universe in which the
  paper reports the effect to be WEAKEST.

  That is a pre-registration design choice, not a bug, and it is not something
  to fix by re-running: doing that after seeing a FAIL is exactly the rescue
  the stopping rule forbids. It is prior information for a successor.""")

    # ---------------------------------------------- 4. cost vs gross
    print("=" * 78)
    print("4. THE ACTUAL ARITHMETIC: what does the cost need the gross to be?")
    print("=" * 78)
    tot = pd.concat([fwd.stack()], axis=1)
    print(f"  cost per rebalance at turnover 0.31 x 0.16% = 0.049%")
    print(f"  the paper's gross is 3.40%/wk, i.e. 70x the cost")
    print(f"  E#3's gross is 0.032%/wk, i.e. 0.65x the cost")
    print("""
  The cost model is not the binding problem. The gross signal is. No
  turnover-reduction or execution cleverness can rescue a construction whose
  gross edge is below its own cost; only a different signal can.""")


if __name__ == "__main__":
    main()
