"""
Did E#6 do its job in the year it lost money?

A long-momentum book shorts the weakest quintile as well as longing the
strongest, so in a falling market it has a theoretical reason to fall LESS
than the market. If it fell as much or more, the signal did not work in the
one regime where the construction should have been most comfortable -- and
that is a stronger negative than "it lost money in a bear market".

Run:  .venv\\Scripts\\python.exe tools\\cross_sectional\\regime_check.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RES = Path(__file__).resolve().parent

reb = pd.read_csv(RES / "e6_rebalances.csv", parse_dates=["week"])
reb["year"] = reb["week"].dt.year

print("=" * 88)
print("E#6 NET, COMPOUNDED, AGAINST THE BASKET IT WAS SORTED FROM")
print("=" * 88)
rows = []
for y, g in reb.groupby("year"):
    n = len(g)
    e6 = (1 + g["net"]).prod() - 1
    gross = (1 + g["gross"]).prod() - 1
    rows.append({
        "year": y,
        "weeks": n,
        "E#6_gross_pct": gross * 100,
        "E#6_net_pct": e6 * 100,
        "mean_turnover": g["turnover"].mean(),
    })
t = pd.DataFrame(rows).round(2)
print(t.to_string(index=False))
print("""
  For reference, from check_bull_premise.py on the same universe:
    BTC       2023 +154.8%   2024 +111.5%   2025  -7.4%   2026  -11.5%
    equal-wt  2023 +105.7%   2024 +111.7%   2025  -4.9%   2026  -12.2%

  A long-momentum cross-sectional book shorted a fifth of the universe, so in a
  down market it should have fallen LESS than the equal-weight basket. Read the
  2025 and 2026 rows against that expectation -- not against zero.""")

print("=" * 88)
print("THE SEPTEMBER 2026 BOUNCE THE FORWARD COLLECTOR CAUGHT")
print("=" * 88)
fwd = pd.read_csv(ROOT / "user_data/forward/klines_1d.csv.gz")
b = fwd[fwd.symbol == "BTCUSDT"].sort_values("date")
hist_last = 78549.60          # 2026-08-31, end of the archive
print(f"  2026-08-31 (archive end)  {hist_last:,.0f}")
print(f"  {b['date'].iloc[0]}                  {b['close'].iloc[0]:,.0f}")
print(f"  {b['date'].iloc[-1]}                 {b['close'].iloc[-1]:,.0f}")
print(f"  change over {len(b)} days            {(b['close'].iloc[-1]/hist_last-1)*100:+.1f}%")
print(f"""
  Against a year-to-date return of -11.5%, that is a bounce, not a bull
  market. And it cannot settle the question: E#6's formation window is 3 to 24
  WEEKS, so {len(b)} daily bars do not move the signal. Confirming whether the
  strategy works in a genuine uptrend needs months of forward data, which is
  exactly what the collector is now accumulating.""")
