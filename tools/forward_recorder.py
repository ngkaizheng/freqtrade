"""Daily forward-validation recorder (shadow backtest + parity checks).

What this is for
----------------
The statistical edge question is unanswerable on any realistic sample (a +0.17
Sharpe edge needs ~271 years of daily data to detect at 80% power). But a
different, answerable question exists:

    Does the strategy's IMPLEMENTATION behave live exactly as the backtest
    predicts?

That question resolves in WEEKS, not decades, and it targets the class of bug
already found once in this project: "the code ran without error but the
semantics were wrong" (24% order churn; the tz-aware/tz-naive all-NaN reindex).

Each run appends one row capturing, for the same timestamp:
  * what the backtest engine (data up to T) says the signal should be
  * what the live/dry-run bot actually decided
  * the resulting exposure, price, and any order activity

Usage (idempotent; safe to run daily via cron/Task Scheduler):

    python tools/forward_recorder.py            # record today
    python tools/forward_recorder.py --report   # summarize parity so far
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

DATA = "user_data/data/bitstamp/BTC_USD-1d.feather"
DRYRUN_DB = "tradesv3.btcsma.dryrun.sqlite"
LOG = "user_data/forward_validation/parity_log.csv"
MA_PERIOD = 50
RISK_ON, RISK_OFF = 1.00, 0.50
ASSUMED_COST_BPS = 10.0

FIELDS = [
    "recorded_at", "candle_date", "close", "sma", "signal_target_exposure",
    "exposure_band", "live_trade_open", "live_stake", "live_amount",
    "live_rate", "live_exposure_frac", "live_open_orders", "live_order_count",
    "dry_run_wallet", "parity_signal", "parity_exposure", "notes",
]


def load_close():
    d = pd.read_feather(DATA)
    d = d.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return d


def compute_signal(close: pd.Series, ma_period: int = MA_PERIOD):
    """Backtest signal from data up to and including the last CLOSED candle.

    The last row of the feather file is today's still-forming candle while the
    market is open, so we drop it and use the previous complete candle. That
    mirrors what a daily strategy can legitimately know at decision time.
    """
    out = close.copy()
    sma = out.rolling(ma_period, min_periods=ma_period).mean()
    return sma


def read_dryrun():
    """Current dry-run state, if the DB exists."""
    if not os.path.exists(DRYRUN_DB):
        return None
    con = sqlite3.connect(DRYRUN_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        t = cur.execute(
            "SELECT id, pair, is_open, stake_amount, amount, open_rate "
            "FROM trades WHERE is_open=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        oc = cur.execute("SELECT COUNT(*) FROM orders WHERE status='open'").fetchone()[0]
        tot = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        con.close()
        if not t:
            return {"open": False, "orders_open": oc, "orders_total": tot}
        return {"open": True, "id": t["id"], "pair": t["pair"],
                "stake": float(t["stake_amount"] or 0),
                "amount": float(t["amount"] or 0),
                "rate": float(t["open_rate"] or 0),
                "orders_open": oc, "orders_total": tot}
    except sqlite3.OperationalError:
        con.close()
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--wallet", type=float, default=10000.0)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(LOG), exist_ok=True)

    if args.report:
        return report()

    d = load_close()
    closes = d.set_index("date")["close"].astype(float)
    sma = compute_signal(closes)

    # Use the last COMPLETE candle: drop the final row if it is today.
    now = datetime.now(timezone.utc)
    idx = closes.index
    last_complete = idx[-2] if (now - idx[-1].to_pydatetime()).total_seconds() < 86400 else idx[-1]
    pos = list(idx).index(last_complete)

    c = float(closes.iloc[pos])
    s = float(sma.iloc[pos])
    if s != s:
        print("SMA not warmed up; nothing to record.")
        return 0

    target = RISK_ON if c > s else RISK_OFF
    band = RISK_ON / RISK_OFF
    # The strategy holds 1 unit == RISK_OFF exposure; 2 units == RISK_ON.
    target_units = target / RISK_OFF

    live = read_dryrun()
    notes = []
    if live is None:
        notes.append("no dry-run DB")
        live_expo = None
        parity_sig = "NO_DATA"
        parity_expo = "NO_DATA"
    elif not live["open"]:
        notes.append("flat in dry-run")
        live_expo = 0.0
        parity_sig = "MISMATCH_FLAT" if target > 0 else "OK"
        parity_expo = "MISMATCH_FLAT"
    else:
        # Exposure fraction = position value / total wallet.
        pos_val = live["amount"] * live["rate"]
        live_expo = pos_val / args.wallet if args.wallet else None
        # Backtest expects: 1 unit (RISK_OFF) or 2 units (RISK_ON) of a 2-unit book.
        expected_units = target_units
        actual_units = live["stake"] / (args.wallet / 2) if args.wallet else None
        parity_sig = "OK"
        if actual_units is None:
            parity_expo = "NO_DATA"
        elif abs(actual_units - expected_units) < 0.25:
            parity_expo = "OK"
        else:
            parity_expo = f"MISMATCH(exp {expected_units:.2f}u got {actual_units:.2f}u)"
            notes.append("exposure drift")

    row = {
        "recorded_at": now.isoformat(),
        "candle_date": str(last_complete.date()),
        "close": round(c, 2),
        "sma": round(s, 2),
        "signal_target_exposure": target,
        "exposure_band": f"{RISK_ON:.2f}/{RISK_OFF:.2f}",
        "live_trade_open": live["open"] if live else "",
        "live_stake": round(live["stake"], 4) if live and live["open"] else "",
        "live_amount": round(live["amount"], 8) if live and live["open"] else "",
        "live_rate": round(live["rate"], 2) if live and live["open"] else "",
        "live_exposure_frac": round(live_expo, 4) if live_expo is not None else "",
        "live_open_orders": live["orders_open"] if live else "",
        "live_order_count": live["orders_total"] if live else "",
        "dry_run_wallet": args.wallet,
        "parity_signal": parity_sig,
        "parity_exposure": parity_expo,
        "notes": "; ".join(notes),
    }

    df = pd.DataFrame([row], columns=FIELDS)

    # Idempotency: replace any existing row for this candle date rather than
    # appending a duplicate. Without this, running twice in a day inflates the
    # observation count and corrupts the turnover estimate.
    if os.path.exists(LOG):
        prev = pd.read_csv(LOG)
        before = len(prev)
        prev = prev[prev["candle_date"].astype(str) != str(row["candle_date"])]
        df = pd.concat([prev, df], ignore_index=True)
        df = df[FIELDS]
        replaced = before != len(prev)
    else:
        replaced = False

    df.to_csv(LOG, index=False)

    print(f"{'replaced' if replaced else 'recorded'} {row['candle_date']}  "
          f"close={row['close']}  sma={row['sma']}  target={target:.0%}")
    print(f"  signal parity  : {parity_sig}")
    print(f"  exposure parity: {parity_expo}")
    if notes:
        print(f"  notes          : {'; '.join(notes)}")
    return 0


def report():
    if not os.path.exists(LOG):
        print("no log yet; run without --report first")
        return 0
    df = pd.read_csv(LOG)
    print("=" * 88)
    print("# FORWARD VALIDATION REPORT")
    print("=" * 88)
    print(f"\n  observations: {len(df)}")
    if len(df):
        print(f"  span        : {df['candle_date'].iloc[0]} -> {df['candle_date'].iloc[-1]}")
        print(f"\n  signal parity  : {df['parity_signal'].value_counts().to_dict()}")
        print(f"  exposure parity: {df['parity_exposure'].value_counts().to_dict()}")
        # Turnover: how many target changes so far?
        ch = int((df["signal_target_exposure"].diff().abs() > 0).sum())
        yrs = max(len(df) / 365.0, 1e-9)
        # NOTE: the backtest expectation is ~19 REBALANCES/year, not ~9.
        # 9.4x/year is TURNOVER (exposure units); each flip moves exposure by
        # 0.5, so flips = turnover / 0.5 = ~19. Conflating the two was an error
        # I made and corrected -- see tools/turnover_reconciliation.py.
        print(f"\n  target changes observed : {ch}  "
              f"(backtest expectation ~19/year; implied {ch/yrs:.1f}/year)")
        print(f"  distinct candle dates   : {df['candle_date'].nunique()}")
    print(f"\n  log: {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
