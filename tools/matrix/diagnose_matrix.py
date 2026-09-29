"""Diagnose the leverage matrix: units, Sharpe variants, cost split, and why the
trade COUNT changes with leverage (which would break the clean-scaling reading)."""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "user_data" / "matrix"


def load(side: str, lev: int) -> dict:
    z = OUT / f"{side}_lev{lev}.zip"
    with zipfile.ZipFile(z) as zf:
        n = next(x for x in zf.namelist() if x.endswith(".json") and "meta" not in x)
        return json.loads(zf.read(n))["strategy"]


def r(side, lev):
    d = load(side, lev)
    return d[next(iter(d))]


print("=" * 100)
print("A. UNIT CHECK on one cell (short 1x) — CLI table vs exported JSON")
print("=" * 100)
x = r("short", 1)
for k in ("winrate", "cagr", "max_relative_drawdown", "expectancy", "sharpe",
          "profit_factor", "sqn", "p_value", "market_change", "profit_total",
          "avg_stake_amount", "starting_balance", "final_balance", "backtest_days",
          "trades_per_day", "total_volume", "rejected_signals", "left_open_trades",
          "max_drawdown_low", "expectancy_ratio"):
    print(f"  {k:24s} {x.get(k)}")
print("  cagr recomputed:",
      (x["final_balance"] / x["starting_balance"]) ** (365.25 / x["backtest_days"]) - 1)
print("  market_change check: mean(entry_rate) ->", x["market_change"])

print()
print("=" * 100)
print("B. CLI table rows for short 1x (ground truth for which Sharpe is which)")
print("=" * 100)
log = (OUT / "short_lev1.log").read_text(encoding="utf-8", errors="replace")
for line in log.splitlines():
    if any(k in line for k in ("Sharpe", "Sortino", "Calmar", "Total profit %",
                               "Absolute Drawdown", "Max Drawdown", "Profit factor",
                               "Expectancy", "Trades per day", "Total/Daily Avg")):
        print("   ", line.strip())

print()
print("=" * 100)
print("C. WHY DOES TRADE COUNT MOVE WITH LEVERAGE?")
print("=" * 100)


def concurrency(trades):
    ev = []
    for t in trades:
        ev.append((t["open_date"], 1))
        ev.append((t["close_date"], -1))
    ev.sort()
    cur = peak = 0
    over = 0
    for _, d in ev:
        cur += d
        peak = max(peak, cur)
        if cur > 24:
            over += 1
    return peak, over


for side in ("short", "long"):
    print(f"\n  --- {side} ---")
    base = None
    for lev in (1, 2, 5, 10, 20):
        x = r(side, lev)
        t = x["trades"]
        levs = Counter(tr.get("leverage") for tr in t)
        ex = Counter(tr.get("exit_reason") for tr in t)
        peak, over = concurrency(t)
        stake = x["starting_balance"] / 24
        keys = {tr["open_date"][:10] + tr["pair"] for tr in t}
        if base is None:
            base = keys
        print(f"   {lev:2d}x  trades={len(t):5d}  peak_concurrent={peak:3d}  "
              f"over24_evts={over:4d}  lev_used={dict(levs)}  "
              f"avg_stake={x['avg_stake_amount']:10,.0f}  stake_at_start={stake:9,.0f}")
        print(f"        exits={dict(ex)}")
        print(f"        entry-dates not in 1x set: {len(keys - base)}   "
              f"missing vs 1x: {len(base - keys)}")

print()
print("=" * 100)
print("D. COST SPLIT (short side): fees vs funding vs net")
print("=" * 100)
print(f"{'lev':>5} {'trades':>7} {'fees':>12} {'funding':>11} {'profit_abs':>12} "
      f"{'net_of_costs':>13} {'pf':>6} {'exit%':>7}")
for side in ("short", "long"):
    print(f"  --- {side} ---")
    for lev in (1, 2, 5, 10, 20):
        x = r(side, lev)
        t = x["trades"]
        fees = -sum((tr.get("fee_open") or 0) * (tr.get("stake_amount") or 0) +
                    (tr.get("fee_close") or 0) * (tr.get("stake_amount") or 0) *
                    (tr.get("close_rate") or 1) / (tr.get("open_rate") or 1)
                    for tr in t)
        fund = sum(tr.get("funding_fees") or 0 for tr in t)
        pa = x["profit_total"]
        ex = Counter(tr.get("exit_reason") for tr in t)
        slpct = 100 * ex.get("stop_loss", 0) / max(len(t), 1)
        print(f"{lev:5d} {len(t):7d} {fees:12,.0f} {fund:11,.0f} {pa:12,.0f} "
              f"{pa - fees + fund:13,.0f} {x['profit_factor']:6.2f} {slpct:6.1f}%")
