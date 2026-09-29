"""Does the funding charge scale linearly with leverage?

The matrix shows funding flipping sign between 2x and 5x, which linear scaling
does not explain. Measure per-trade funding and notional on the SHARED trades
so the trade set is held fixed.
"""

import glob
import json
import zipfile

import pandas as pd


def load(lev):
    f = glob.glob(f"user_data/backtest_results/matrix/base_c5000_l{lev:g}/backtest-result-*.zip")[0]
    z = zipfile.ZipFile(f)
    st = json.loads(z.read(z.namelist()[0]))["strategy"]["ShortBreakout4hLev"]
    t = pd.DataFrame(st["trades"])
    t["open_date"] = pd.to_datetime(t["open_date"], utc=True)
    t["notional"] = t["amount"] * t["open_rate"]
    return t[["pair", "open_date", "funding_fees", "notional", "close_date"]]


a, b, c = load(1), load(10), load(20)
m = a.merge(b, on=["pair", "open_date"], suffixes=("_1", "_10"))
m = m.merge(c, on=["pair", "open_date"], suffixes=("", "_20"))
m["close_date_10"] = m["close_date_10"] if "close_date_10" in m else m["close_date_1"]

print("shared trades:", len(m))
for tag, col in (("1x", "funding_fees_1"), ("10x", "funding_fees_10"), ("20x", "funding_fees")):
    f = m[col]
    n = m["notional" + ("_1" if tag == "1x" else "_10" if tag == "10x" else "")]
    print(f"{tag:>3}  funding/trade={f.mean():+.5f}  total={f.sum():+9.1f}  "
          f"notional mean={n.mean():8.1f}  funding per unit notional={f.sum()/n.sum():+.6f}")

r1010 = m["funding_fees_10"].mean() / m["funding_fees_1"].mean()
r2010 = m["funding_fees"].mean() / m["funding_fees_10"].mean()
print(f"\nper-trade funding ratio 10x/1x  = {r1010:.2f}   (linear would be 10.00)")
print(f"per-trade funding ratio 20x/10x = {r2010:.2f}   (linear would be 2.00)")
print(f"notional ratio 10x/1x  = "
      f"{m['notional_10'].mean()/m['notional_1'].mean():.2f}")
print(f"notional ratio 20x/10x = "
      f"{m['notional'].mean()/m['notional_10'].mean():.2f}")
