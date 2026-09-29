"""Sanity-check the funding attachment on the built panel.

Funding is charged only on settlement bars. Three silent failure modes were
found and fixed while building this panel; this script exists so a fourth
cannot pass unnoticed:
  1. the wrong column selected (funding_interval_hours = 8 read as a rate);
  2. a "within one bar" window marking the 04:00/12:00 bars as settlements
     (2x the real charge);
  3. merge_asof collapsing both keys to one column, so age == 0 everywhere and
     EVERY bar became a settlement.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

FEAT = "shark_data/wide/features"

rows = []
for f in sorted(glob.glob(f"{FEAT}/*.parquet")):
    sym = os.path.basename(f).replace(".parquet", "")
    d = pd.read_parquet(f)
    ev = d["funding_event"].to_numpy().astype(bool)
    n = len(d)
    ev_n = int(ev.sum())
    rate_sum = float(d.loc[ev, "funding_rate"].sum())
    # the exact invariant: every settlement in the source is attributed to
    # exactly one 4h bar, and the sum of the marked bar rates equals the sum of
    # the source rates. Symbols that moved to a 1h or off-grid funding interval
    # mid-sample (§3.18) have several settlements inside one bar — which is
    # precisely why the bar total is a SUM and not a single stamped rate.
    src = pd.read_csv(f"shark_data/wide/funding/{sym}.csv.gz")
    tcol = "calc_time" if "calc_time" in src.columns else src.columns[0]
    rcol = ("last_funding_rate" if "last_funding_rate" in src.columns
            else "funding_rate")
    t = pd.to_datetime(src[tcol], utc=True, format="ISO8601")
    r = pd.to_numeric(src[rcol], errors="coerce")
    src_sum = float(r.sum())
    src_bars = int(t.dt.floor("4h").nunique())
    rows.append({
        "symbol": sym,
        "bars": n,
        "event_bars": ev_n,
        "source_bars": src_bars,
        "bar_match": ev_n == src_bars,
        "sum_rate_panel": rate_sum,
        "sum_rate_source": src_sum,
        "rate_match": abs(rate_sum - src_sum) < 1e-9,
        "event_frac": ev_n / n,
        "max_abs_rate": float(d["funding_rate"].abs().max()),
    })

t = pd.DataFrame(rows)
t.to_csv("shark_data/wide/funding_check.csv", index=False)

print(t[t.symbol.isin(["BTCUSDT", "ETHUSDT", "SOLUSDT", "API3USDT"])]
      .to_string(index=False))
print()
print(f"symbols: {len(t)}")
print(f"marked bars == source settlement bars for "
      f"{int(t.bar_match.sum())}/{len(t)} symbols")
print(f"panel rate sum == source rate sum for "
      f"{int(t.rate_match.sum())}/{len(t)} symbols")
print(f"median event_frac = {t.event_frac.median():.4f} "
      f"(8h on a 4h grid = 0.5000; >0.5 = interval moved to 4h/1h mid-sample)")
print(f"max single-bar rate over panel = {t.max_abs_rate.max():.5f}")

print("\nmost negative cumulative funding (longs were PAID) — real, not an error:")
print(t.nsmallest(4, "sum_rate_panel")[["symbol", "sum_rate_panel", "event_frac"]]
      .to_string(index=False))

bad = t[~(t.bar_match & t.rate_match)]
assert bad.empty, (
    f"{len(bad)} symbols where the panel does not reproduce the source funding "
    f"exactly — over- or under-charged:\n{bad.to_string(index=False)}"
)
assert (t.event_frac >= 0.49).all(), "under-charged: settlement frac below 0.49"
print("\nOK: every settlement is attributed to exactly one bar and the rate "
      "totals reconcile with the source for all 104 symbols.")
