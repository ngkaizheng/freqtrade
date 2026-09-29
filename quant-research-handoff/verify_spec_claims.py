"""Corrected SPEC table: 50% rule vs 100/0 rule vs hold, on SPEC's own windows."""
import sys, os
sys.path.insert(0, "code")
import pandas as pd
from quant.engine import run_backtest
from quant.metrics import cagr, max_drawdown, sharpe_ci_monthly

d = pd.read_csv("data/cache_long/SPY.csv", index_col=0, parse_dates=True)
if d.index.tz is not None:
    d.index = d.index.tz_localize(None)
cl, op = d["Close"].astype(float), d["Open"].astype(float)
ma200 = cl.rolling(200, min_periods=200).mean()
below = (cl < ma200).fillna(False)
O = d[["Open"]].rename(columns={"Open": "SPY"})


def eq_for(red):
    w = pd.Series(1.0, index=cl.index)
    if red is not None:
        w[below] = red
    return run_backtest(pd.DataFrame({"SPY": w}), O, cost_bps=10.0, rebalance="D")["equity"].dropna()


arms = {"hold": eq_for(None), "MA200->50%": eq_for(0.5), "MA200->0%": eq_for(0.0)}

print("SPEC section 3 headline (SPY 1993-2026, 10bps):")
print(f"{'arm':13s}{'CAGR%':>8}{'Sharpe':>9}{'MaxDD%':>9}{'recovery?':>11}")
for k, e in arms.items():
    dd = max_drawdown(e)
    print(f"{k:13s}{cagr(e):8.2f}{sharpe_ci_monthly(e)[0]:9.3f}{dd[0]:9.2f}")

print("\nSPEC section 3 crash table, using SPEC's OWN windows (crash_periods.csv):")
PERIODS = [("2000-2002 互联网泡沫", "2000-01-01", "2002-12-31"),
           ("2008-2009 金融危机", "2008-01-01", "2009-12-31"),
           ("2020 新冠崩盘", "2020-02-01", "2020-12-31"),
           ("2022 加息熊市", "2022-01-01", "2022-12-31"),
           ("2010-2026 整体牛市", "2010-01-01", "2026-12-31")]
print(f"{'period':26s}{'hold':>10}{'MA200->50%':>13}{'MA200->0%':>12}")
for label, a, b in PERIODS:
    row = [f"{label:26s}"]
    for k in ("hold", "MA200->50%", "MA200->0%"):
        s = arms[k].loc[a:b]
        row.append(f"{(s.iloc[-1]/s.iloc[0]-1)*100:+9.2f}%")
    print("".join(f"{c:>{w}}" for c, w in zip(row, [26, 10, 13, 12])))
