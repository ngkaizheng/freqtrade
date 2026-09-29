"""Re-verification of the v3 round's numbers on fresh data (v3 s46 requires it).

The v3 report was written against a CoinGecko snapshot at 19:05Z. This compares it
to the 20:02Z pull used by the v4 round, token by token, so a claim in the v3
report can be checked rather than trusted. Anything beyond a few percent of drift
is a data problem, not market movement.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
SYMS = ["KNTQ", "AVA", "AERO", "LDO", "SYRUP", "ENA", "ZRO", "STONK",
        "PONS", "HYPE", "UNI", "ORE", "BTT", "WIN", "SUSHI", "VSN"]

old = pd.read_csv(OUT / "market_snapshot.csv")
new = pd.read_csv(OUT / "v4_evidence.csv")
# Tickers are NOT unique in a 2,000-coin snapshot (duplicate-symbol scams exist),
# so index by symbol AND market-cap rank rather than by symbol alone.
old = old.sort_values("rank").drop_duplicates("symbol").set_index("symbol")
new = new.sort_values("rank").drop_duplicates("symbol").set_index("symbol")

print(f"{'sym':<8s}{'mcap v3':>12s}{'mcap v4':>12s}{'drift%':>9s}"
      f"{'30d v3':>10s}{'30d v4':>10s}{'7d v3':>9s}{'7d v4':>9s}")
worst = 0.0
for s in SYMS:
    if s not in old.index or s not in new.index:
        print(f"{s:<8s}  MISSING")
        continue
    a, b = old.loc[s, "mcap"], new.loc[s, "mcap"]
    d = (b / a - 1) * 100
    worst = max(worst, abs(d))
    print(f"{s:<8s}{a/1e6:>11.1f}M{b/1e6:>11.1f}M{d:>9.2f}"
          f"{old.loc[s, 'chg30']:>10.2f}{new.loc[s, 'chg30']:>10.2f}"
          f"{old.loc[s, 'chg7']:>9.2f}{new.loc[s, 'chg7']:>9.2f}")
print(f"\nlargest market-cap drift: {worst:.2f}% over ~1 hour")
print("verdict: v3 data re-verified" if worst < 10 else
      "verdict: DRIFT EXCEEDS 10% - investigate before trusting v3")
