"""Write the fast half of the v4 evidence set immediately.

`v4_evidence.py` holds everything in memory until the very end, so a rate-limited
history loop blocks the two products that are already computed and cheap:
the fresh candidate metrics and the attention/velocity shortlist. This writes
those two files on their own so downstream scoring can proceed while the
per-coin market_chart pulls continue in the background.

When the slow job finishes it will overwrite v4_evidence.csv with the same rows
plus the history columns (vol_accel, supply_30d_pct, supply_ann_pct). The market
and screen columns are identical between the two, and `verify_v4.py` asserts that.
"""
from __future__ import annotations

import sys
import time

import pandas as pd

sys.path.insert(0, "tools/catalyst_scan")
from v4_evidence import (  # noqa: E402
    CANDIDATE_IDS, OUT, attention_screen, fresh_markets, trending,
)

print("fresh market pull ...", file=sys.stderr)
for attempt in range(6):
    mkt = fresh_markets(CANDIDATE_IDS)
    if not mkt.empty:
        break
    time.sleep(25)
if mkt.empty:
    raise SystemExit("FATAL: market pull still empty after retries")

mkt.to_csv(OUT / "v4_evidence.csv", index=False)
print(f"  wrote v4_evidence.csv rows={len(mkt)}", file=sys.stderr)

snap = pd.read_csv(OUT / "market_snapshot.csv")
att = attention_screen(snap)
att.to_csv(OUT / "attention_screen.csv", index=False)
print(f"  wrote attention_screen.csv rows={len(att)}", file=sys.stderr)

tr = trending()
(OUT / "trending.txt").write_text("\n".join(tr), encoding="utf-8")

cols = ["symbol", "rank", "mcap", "fdv", "vol_mcap", "fdv_mcap",
        "chg24", "chg7", "chg30", "ath_chg", "mom_accel", "screen_score"]
pd.set_option("display.width", 200)
print("\n=== ATTENTION / VELOCITY SHORTLIST (top 60) ===", file=sys.stderr)
print(att[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"),
      file=sys.stderr)
print(f"\n=== COINGECKO TRENDING ===\n{', '.join(tr)}", file=sys.stderr)
