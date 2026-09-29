"""Diagnostic: is the leverage collapse in run_matrix.py a property of the
signal, or an artefact of `stake_amount: unlimited` interacting with the
24-slot concurrency cap?

Compares the 1x and 20x cells directly, on shared and on all entries.
"""

import glob
import json
import zipfile

import pandas as pd


def load(cell):
    f = glob.glob(f"user_data/backtest_results/matrix/{cell}/backtest-result-*.zip")[0]
    z = zipfile.ZipFile(f)
    st = json.loads(z.read(z.namelist()[0]))["strategy"]["ShortBreakout4hLev"]
    t = pd.DataFrame(st["trades"])
    t["open_date"] = pd.to_datetime(t["open_date"], utc=True)
    return t


def show(name, t):
    stake = t["stake_amount"].mean()
    ratio = t["profit_ratio"].mean()
    pabs = t["profit_abs"].mean()
    dur = t["trade_duration"].median() / 60.0
    exits = t["exit_reason"].value_counts().to_dict()
    win = 100.0 * (t["profit_ratio"] > 0).mean()
    fund = t["funding_fees"].sum()
    print(f"{name:>4}  n={len(t):<5} mean_stake={stake:8.2f}  "
          f"mean_profit_ratio={ratio:+.5f}  mean_profit_abs={pabs:+.4f}  "
          f"sum_abs={t['profit_abs'].sum():+9.2f}")
    print(f"      median_hold={dur:5.1f}h  winrate={win:5.1f}%  funding={fund:+7.2f}")
    print(f"      exits={exits}")


a = load("base_c500_l1")
b = load("base_c500_l20")
ka = set(zip(a["pair"], a["open_date"]))
kb = set(zip(b["pair"], b["open_date"]))
print(f"1x entries={len(a)}  20x entries={len(b)}  shared={len(ka & kb)}\n")
show("1x", a)
show("20x", b)

common = ka & kb
ma = a[[(p, d) in common for p, d in zip(a["pair"], a["open_date"])]]
mb = b[[(p, d) in common for p, d in zip(b["pair"], b["open_date"])]]
print(f"\n--- shared entries only: {len(ma)} ---")
show("1x", ma)
show("20x", mb)
r = mb["profit_ratio"].mean() / ma["profit_ratio"].mean()
print(f"\nper-trade profit_ratio ratio 20x/1x = {r:.3f}   (pure re-levering would give 20.0)")
print(f"notional ratio 20x/1x = {mb['stake_amount'].mean() * 20 / (ma['stake_amount'].mean()):.3f}")
