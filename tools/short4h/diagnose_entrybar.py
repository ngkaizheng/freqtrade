"""Why does the 20x cell kill 97% of trades on their entry bar when the 1x
cell does not? Inspect raw trade records rather than aggregates.
"""

import glob
import json
import zipfile

import pandas as pd

pd.set_option("display.width", 200)


def load(cell):
    f = glob.glob(f"user_data/backtest_results/matrix/{cell}/backtest-result-*.zip")[0]
    z = zipfile.ZipFile(f)
    st = json.loads(z.read(z.namelist()[0]))["strategy"]["ShortBreakout4hLev"]
    t = pd.DataFrame(st["trades"])
    t["open_date"] = pd.to_datetime(t["open_date"], utc=True)
    return t


a = load("base_c500_l1")
b = load("base_c500_l20")

for name, t in (("1x", a), ("20x", b)):
    d = t["trade_duration"]
    print(f"--- {name} ---")
    print("  duration(min) describe:", {k: round(v, 2) for k, v in d.describe().items()})
    print("  share with duration == 0:", round(100 * (d == 0).mean(), 2), "%")
    print("  stop_loss rate:", round(100 * (t["exit_reason"] == "stop_loss").mean(), 2), "%")
    sl = t[t["exit_reason"] == "stop_loss"]
    print("  stop_loss profit_ratio describe:",
          {k: round(v, 5) for k, v in sl["profit_ratio"].describe().items()})
    print("  max loss profit_ratio:", round(sl["profit_ratio"].min(), 5))

print("\n--- 6 example 20x trades on their entry bar ---")
ex = b[b["trade_duration"] <= 4].head(6)
cols = ["pair", "open_date", "close_date", "open_rate", "close_rate",
        "stake_amount", "leverage", "profit_ratio", "profit_abs", "exit_reason"]
print(ex[cols].to_string(index=False))

print("\n--- matching 1x trades for the same pair+entry ---")
for _, r in ex.head(3).iterrows():
    m = a[(a["pair"] == r["pair"]) & (a["open_date"] == r["open_date"])]
    if len(m):
        m = m.iloc[0]
        print(f"  {r['pair']} {r['open_date']}: 1x profit_ratio={m['profit_ratio']:+.5f} "
              f"exit={m['exit_reason']} hold={m['trade_duration']}min | "
              f"20x profit_ratio={r['profit_ratio']:+.5f} exit={r['exit_reason']} "
              f"hold={r['trade_duration']}min")
