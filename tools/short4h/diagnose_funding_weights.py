"""Why does total funding flip sign between 2x and 5x when the trade set and
the holding periods are identical?

Hypothesis: funding is charged on NOTIONAL, and notional compounds with the
account. At higher leverage the account is larger later in the sample, so the
notional weighting shifts onto the late trades. If the late period pays
negative funding, the notional-weighted total flips sign even though every
individual trade is unchanged.

Test: compute, per year, the notional-weighted mean of each trade's own
implied funding rate (funding_i / notional_i). If the weighted mean is
positive early and negative late, the hypothesis holds.
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
    # this trade's own implied average funding rate over its holding period
    t["implied_rate"] = t["funding_fees"] / t["notional"]
    t["year"] = t["open_date"].dt.year
    return t


frames = {lev: load(lev) for lev in (1, 5, 10, 20)}

print("notional-weighted mean funding rate by year")
print("(unweighted mean shown beside it -- identical trades, so that column")
print(" is the same at every leverage; only the WEIGHT changes)\n")

rows = []
for year in sorted(frames[1]["year"].unique()):
    r = {"year": year, "unweighted": frames[1][frames[1].year == year]["implied_rate"].mean()}
    for lev in (1, 5, 10, 20):
        sub = frames[lev][frames[lev].year == year]
        r[f"w{lev}x"] = (sub["implied_rate"] * sub["notional"]).sum() / sub["notional"].sum()
    rows.append(r)

df = pd.DataFrame(rows).set_index("year")
print(df.to_string(float_format=lambda v: f"{v:+.6f}"))

print("\nfull-sample totals (funding USDT on 5000 USDT of capital):")
for lev in (1, 2, 5, 10, 20):
    t = frames.get(lev)
    if t is None:
        f = glob.glob(f"user_data/backtest_results/matrix/base_c5000_l{lev:g}/backtest-result-*.zip")[0]
        z = zipfile.ZipFile(f)
        t = pd.DataFrame(json.loads(z.read(z.namelist()[0]))["strategy"]["ShortBreakout4hLev"]["trades"])
    print(f"  {lev:>2}x  funding={t['funding_fees'].sum():+9.1f} USDT")
