"""Analyze the dry-run database for execution-layer defects.

The dry-run surfaced two things the backtest could never show:

  1. STALE-DB POLLUTION: the existing tradesv3.dryrun.sqlite already held
     Trade(id=44, pair=BTC/USDT, exchange=Binance, opened 2026-05-03) from an
     earlier session. The new Bitstamp/BTCSmaTrend run picked it up and started
     managing it, producing foreign-exchange orders.

  2. ORDER CHURN: logs showed "Position adjust: about to create a new order"
     repeating every ~5s, with orders created then cancelled then replaced.
     adjust_trade_position is called on every process throttle in live/dry-run,
     but only once per candle in backtest. That asymmetry is exactly what the
     freqtrade docs warn about.
"""

import sqlite3
from collections import Counter

DB = "tradesv3.dryrun.sqlite"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 92)
print("# DRY-RUN DATABASE ANALYSIS")
print("=" * 92)

# ---- trades ----
trades = cur.execute(
    "SELECT id, pair, exchange, is_open, open_date, close_date, "
    "stake_amount, amount, strategy, enter_tag FROM trades ORDER BY id"
).fetchall()
print(f"\n  trades in DB: {len(trades)}")
print(f"\n  {'id':>4} {'pair':<10} {'exchange':<10} {'open?':<6} "
      f"{'strategy':<20} {'opened':<20} {'stake':>10}")
for t in trades:
    print(f"  {t['id']:>4} {t['pair']:<10} {str(t['exchange']):<10} "
          f"{str(t['is_open']):<6} {str(t['strategy']):<20} "
          f"{str(t['open_date'])[:19]:<20} {t['stake_amount']:>10.4f}")

# ---- orders ----
try:
    orders = cur.execute(
        "SELECT id, ft_trade_id, ft_order_side, status, order_date, "
        "order_filled_date, cost, price, ft_order_tag FROM orders "
        "ORDER BY id"
    ).fetchall()
except sqlite3.OperationalError:
    orders = []

print(f"\n  orders in DB: {len(orders)}")
if orders:
    print(f"\n  {'id':>5} {'trade':>6} {'side':<6} {'status':<10} "
          f"{'tag':<20} {'cost':>10}  created")
    for o in orders[-40:]:
        print(f"  {o['id']:>5} {str(o['ft_trade_id']):>6} {o['ft_order_side']:<6} "
              f"{str(o['status']):<10} {str(o['ft_order_tag'] or '-'):<20} "
              f"{float(o['cost'] or 0):>10.4f}  {str(o['order_date'])[:19]}")

    # ---- churn metrics ----
    print(f"\n{'=' * 92}")
    print("# ORDER CHURN ANALYSIS")
    print(f"{'=' * 92}")
    by_trade = Counter(o["ft_trade_id"] for o in orders)
    print(f"\n  orders per trade: {dict(by_trade)}")
    status_ct = Counter(str(o["status"]) for o in orders)
    print(f"  status breakdown: {dict(status_ct)}")
    side_ct = Counter(str(o["ft_order_side"]) for o in orders)
    print(f"  side breakdown  : {dict(side_ct)}")

    cancelled = sum(1 for o in orders if str(o["status"]).lower() == "canceled")
    filled = sum(1 for o in orders if "fill" in str(o["status"]).lower())
    filled_cost = sum(float(o["cost"] or 0) for o in orders
                      if "fill" in str(o["status"]).lower())
    if filled:
        print(f"\n  filled orders : {filled}   total filled cost: {filled_cost:.2f}")
    if cancelled:
        print(f"  CANCELLED orders: {cancelled}  "
              f"({cancelled / len(orders):.0%} of all orders)")
        print(f"\n  !! Each cancel+replace costs a spread. In live trading this is")
        print(f"     real money lost to churn, not visible in the backtest.")

con.close()

print(f"\n{'=' * 92}")
print("# DEFECT SUMMARY")
print(f"{'=' * 92}")
print("""
  DEFECT 1 - stale database carries foreign trades
    The DB held an open Binance BTC/USDT trade from a previous session. The
    Bitstamp run adopted it and emitted orders tagged exchange=Binance.
    Fix: use a dedicated db_url per strategy/exchange, and never share
    tradesv3.dryrun.sqlite across configs.

  DEFECT 2 - order churn from adjust_trade_position cadence
    In live/dry-run the callback fires on every process throttle (~5s); in
    backtest it fires once per candle. Orders were created, cancelled and
    replaced repeatedly. Fix: only act on a NEW candle, and skip when an
    order is already open.
""")
