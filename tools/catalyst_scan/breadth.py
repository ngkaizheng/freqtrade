"""Market breadth from the saved snapshot - characterises the regime a catalyst
trade has to fight (or ride)."""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
m = pd.read_csv(OUT / "market_snapshot.csv").dropna(subset=["chg30"])
print(f"=== MARKET BREADTH  (data {m['updated'].max()}) ===")
bands = [(0, 200, "rank 1-200"), (200, 600, "rank 201-600"), (600, 1300, "rank 601-1250")]
for lo, hi, lab in bands:
    s = m[(m["rank"] > lo) & (m["rank"] <= hi)]
    if s.empty:
        continue
    print(
        f"{lab:14s} n={len(s):4d} | median 30d {s['chg30'].median():+7.2f}% | median 7d {s['chg7'].median():+6.2f}%"
        f" | share up 30d {100 * (s['chg30'] > 0).mean():5.1f}% | share up 7d {100 * (s['chg7'] > 0).mean():5.1f}%"
        f" | median from ATH {s['ath_chg'].median():+7.1f}%"
    )
print()
print("snapshot total mcap: $%.2fT over %d coins" % (m["mcap"].sum() / 1e12, len(m)))
print("coins with mcap > $10M:", int((m["mcap"] > 1e7).sum()))
print()
t = m[m["rank"] <= 300]
print("=== 30D CHANGE DISTRIBUTION, top 300 ===")
print(t["chg30"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_string())
print()
print("=== share of top 300 within 25% of ATH ===")
print(f"{100 * (t['ath_chg'] > -25).mean():.1f}%  (n={int((t['ath_chg'] > -25).sum())})")
print("those names:", ", ".join(t[t["ath_chg"] > -25]["symbol"].tolist()))
