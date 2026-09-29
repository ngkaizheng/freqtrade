"""Re-point the forward collector at the chosen rung, N=40, preserving order.

`PICK_THE_RUNG_2026-09-29.md`: the minimax rule picks N=40 (min t 1.84 across the
two windows, regret 0.23 - the lowest regret of any rung). The ladder's top four
rungs span only 0.38 of min t, so 25-100 is a genuinely flat region and the
choice inside it is not worth optimising further.

**The ORDER of the whitelist is part of the decision**, not a formatting detail:
with 24 slots and a clustered book, the same universe ordered alphabetically
returned +4.14% and ordered by liquidity -17.52%. So the pair list is written in
liquidity-rank order and that is asserted, not assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
N = 40

liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
top = liq.head(N)
pairs = [s[:-4] + "/USDT:USDT" for s in top["symbol"]]

# the universe must still be in DESCENDING liquidity order
q = top["med_quote"].to_numpy()
assert all(q[i] >= q[i + 1] for i in range(len(q) - 1)), \
    "universe is not in liquidity order - that is the 8th trap"

cfg_path = ROOT / "user_data" / "config_perp_forward_dry.json"
cfg = json.load(open(cfg_path))
cfg["pair_whitelist"] = pairs
cfg["exchange"] = dict(cfg["exchange"])
cfg["exchange"]["pair_whitelist"] = pairs
json.dump(cfg, open(cfg_path, "w"), indent=2)

print(f"collector universe -> top {N} of 515 by median quote volume")
print(f"   first 5 : {pairs[:5]}")
print(f"   last 3  : {pairs[-3:]}")
print(f"   cohort A share : {float((top['cohort'] == 'A').mean())*100:.1f}%")
print(f"   median quote   : ${top['med_quote'].median():,.0f}/bar")
print(f"   order asserted : descending liquidity (the 8th trap)")
print(f"   written to     : {cfg_path}")
print()
print("   restart the collector for it to take effect:")
print("     .venv\\Scripts\\python.exe -m freqtrade trade "
      "--config user_data\\config_perp_forward_dry.json")
