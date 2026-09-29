"""Is the NEGATIVE train->test rank correlation robust?

reconciliation_jackknife_vs_oos.py found Spearman rho = -0.810 on the 20-major
pool between in-sample window edge and out-of-sample window edge. A NEGATIVE
correlation means the in-sample-best window is systematically among the worst
out-of-sample -- the strongest possible statement of "do not select on
in-sample performance".

But 8 windows is a small sample; rho = -0.810 on n=8 is p ~ 0.015 by rank test,
which is suggestive, not decisive. And the BTC panel gave rho = -0.143.

This script checks whether the negative relationship is stable across several
independent train/test splits rather than one. It is DIAGNOSTIC: no rule is
being selected, and nothing is re-tuned.
"""

import os
import numpy as np
import pandas as pd

PPY_C, COST_C = 365, 10.0
WINDOWS = [10, 20, 30, 50, 75, 100, 150, 200]
MAJORS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK",
          "LTC", "BCH", "ATOM", "UNI", "AAVE", "XLM", "ETC", "ALGO", "FIL",
          "NEO", "TRX"]


def sharpe(r, ppy=PPY_C):
    sd = r.std()
    return float(r.mean() / sd * np.sqrt(ppy)) if sd and sd > 0 else np.nan


def sma_expo(close, w):
    ma = close.rolling(w, min_periods=w).mean()
    v = ma.notna()
    out = pd.Series(0.5, index=close.index)
    out[v] = np.where(close[v] > ma[v], 1.0, 0.5)
    return out


def edge(close, rets, w, cost=COST_C):
    e = sma_expo(close, w)
    pos = e.shift(1).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    r = sharpe(pos * rets - turn * cost / 10_000.0)
    f = sharpe(pd.Series(float(e.mean()), index=rets.index) * rets)
    return r - f


def main():
    print("=" * 94)
    print("# STABILITY OF THE NEGATIVE TRAIN->TEST RANK CORRELATION")
    print("=" * 94)
    print("\n  Diagnostic: no selection, no tuning. 8 windows, several splits.")

    # Build panels
    d = pd.read_feather("user_data/data/bitstamp/BTC_USD-1d.feather")
    d = d.sort_values("date").drop_duplicates("date")
    btc = d.set_index("date")["close"].astype(float).iloc[200:]
    r_btc = btc.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    closes = {}
    for m in MAJORS:
        p = f"user_data/data/binance/{m}_USDT-1d.feather"
        if not os.path.exists(p):
            continue
        dd = pd.read_feather(p).sort_values("date").drop_duplicates("date")
        closes[f"{m}/USDT"] = dd.set_index("date")["close"].astype(float)
    panel = pd.DataFrame(closes).sort_index().loc["2019-01-01":]
    prets = panel.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    ew = prets.mean(axis=1, skipna=True).fillna(0.0)
    idx = panel.ffill().mean(axis=1)

    def rho_for(close, rets, split_date, test_len_days):
        c = pd.Timestamp(split_date, tz=close.index.tz)
        tr = close.index < c
        te_end = c + pd.Timedelta(days=test_len_days)
        te = (close.index >= c) & (close.index < te_end)
        if tr.sum() < 400 or te.sum() < 100:
            return None
        a = [edge(close[tr], rets[tr], w) for w in WINDOWS]
        b = [edge(close[te], rets[te], w) for w in WINDOWS]
        if any(np.isnan(x) for x in a + b):
            return None
        return float(pd.Series(a).corr(pd.Series(b), method="spearman")), a, b

    print(f"\n  {'dataset':<26} {'split':<12} {'test窗':>7} {'rho':>8} "
          f"{'train-best w':>13} {'its test edge':>14}")
    results = []
    for label, close, rets, splits, tlen in (
        ("BTC/USD (Bitstamp)", btc, r_btc,
         ["2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01",
          "2025-01-01"], 550),
        ("20-major pool", idx, ew,
         ["2021-06-01", "2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01",
          "2024-01-01"], 400),
    ):
        for s in splits:
            out = rho_for(close, rets, s, tlen)
            if out is None:
                continue
            rho, a, b = out
            bi = int(np.argmax(a))
            results.append({"dataset": label, "split": s, "rho": rho,
                            "best_w": WINDOWS[bi], "best_test": b[bi],
                            "max_test": max(b)})
            print(f"  {label:<26} {s:<12} {tlen:>7} {rho:>+8.3f} "
                  f"{'SMA-' + str(WINDOWS[bi]):>13} {b[bi]:>+14.3f}")

    df = pd.DataFrame(results)
    print(f"\n{'=' * 94}")
    print("# SUMMARY")
    print(f"{'=' * 94}")
    for label in df["dataset"].unique():
        sub = df[df["dataset"] == label]
        print(f"\n  {label}  ({len(sub)} splits)")
        print(f"    mean rho             : {sub['rho'].mean():+.3f}")
        print(f"    rho range            : {sub['rho'].min():+.3f} .. "
              f"{sub['rho'].max():+.3f}")
        print(f"    splits with rho < 0  : {int((sub['rho'] < 0).sum())}/{len(sub)}")
        print(f"    train-best window test edge > 0 : "
              f"{int((sub['best_test'] > 0).sum())}/{len(sub)}")
        print(f"    mean train-best test edge       : {sub['best_test'].mean():+.3f}")
        print(f"    mean test-best (oracle) edge    : {sub['max_test'].mean():+.3f}")

    print(f"""
  INTERPRETATION

  If rho is negative across most splits, then selecting the window on in-sample
  performance is ACTIVELY HARMFUL: you systematically land on a window that
  underperforms out-of-sample. The 'oracle' test-best column shows what would
  have been available only with hindsight -- the gap between it and the
  train-best column is the cost of having to choose in advance.

  This sharpens the status of the candidate: it is not merely that the edge is
  unproven, it is that the standard method of choosing its one free parameter
  does not transfer. A forward test must therefore use a PRE-COMMITTED window,
  or better, avoid the free parameter entirely.""")


if __name__ == "__main__":
    main()
