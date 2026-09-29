"""Forward-validation criterion checker — enforces docs-myself/FORWARD-PROTOCOL.md.

The protocol is only worth anything if the checks actually run. This script
evaluates Criterion 1 (implementation) and Criterion 2 (mechanism) against the
accumulated forward record and prints a PASS / FAIL / INSUFFICIENT-DATA verdict.

It deliberately returns INSUFFICIENT_DATA rather than PASS when there is not yet
enough forward record. Reporting "PASS" off one observation would be the same
over-reading the lessons ledger documents (L6, L9).

Usage:
    python tools/forward_criteria_check.py
"""

import os
import sqlite3
import sys

import numpy as np
import pandas as pd

LOG = "user_data/forward_validation/parity_log.csv"
DB = "tradesv3.btcsma.dryrun.sqlite"
DATA = "user_data/data/bitstamp/BTC_USD-1d.feather"

# Frozen expectations from the protocol
EXPECTED_REBAL_PER_YEAR = 19.0
REBAL_TOLERANCE = (10.0, 35.0)
MAX_CANCEL_RATE = 0.05
MAX_COST_BPS = 20.0          # 2x the 10bps assumption
EXPOSURE_TOL_UNITS = 0.25
MIN_DAYS_FOR_IMPL = 90
MIN_REBALANCES_FOR_IMPL = 4
MIN_DAYS_FOR_MECH = 180
VR_THRESHOLD = 1.0


def load_log():
    if not os.path.exists(LOG):
        return pd.DataFrame()
    return pd.read_csv(LOG)


def check_implementation(df):
    """Criterion 1. Returns (status, lines, counters)."""
    out = []
    counters = {}

    if df.empty:
        return "INSUFFICIENT_DATA", ["  no forward records yet"], counters

    n_days = df["candle_date"].nunique()
    counters["days"] = n_days

    # 1a signal parity
    bad_sig = int((df["parity_signal"].astype(str) != "OK").sum())
    counters["signal_mismatch"] = bad_sig
    out.append(f"  1a signal parity        : {bad_sig} mismatch(es) "
               f"{'OK' if bad_sig == 0 else 'FAIL'}")

    # 1b exposure parity
    bad_exp = int((df["parity_exposure"].astype(str) != "OK").sum())
    counters["exposure_mismatch"] = bad_exp
    out.append(f"  1b exposure parity      : {bad_exp} mismatch(es) "
               f"{'OK' if bad_exp == 0 else 'FAIL'}")

    # 1e rebalance cadence
    changes = int((df["signal_target_exposure"].diff().abs() > 0).sum())
    counters["rebalances"] = changes
    yrs = max(n_days / 365.0, 1e-9)
    implied = changes / yrs
    counters["rebal_per_year"] = implied
    if n_days < MIN_DAYS_FOR_IMPL:
        cadence_note = f"INSUFFICIENT ({n_days}d < {MIN_DAYS_FOR_IMPL}d)"
        cadence_ok = None
    else:
        cadence_ok = REBAL_TOLERANCE[0] <= implied <= REBAL_TOLERANCE[1]
        cadence_note = "OK" if cadence_ok else "FAIL"
    out.append(f"  1e rebalance cadence    : {changes} over {n_days}d "
               f"= {implied:.1f}/yr (expect ~{EXPECTED_REBAL_PER_YEAR:.0f}, "
               f"range {REBAL_TOLERANCE[0]:.0f}-{REBAL_TOLERANCE[1]:.0f}) "
               f"{cadence_note}")

    # 1c/1d/1g from the DB
    cancel_rate = None
    if os.path.exists(DB):
        con = sqlite3.connect(DB)
        cur = con.cursor()
        o = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        c = cur.execute("SELECT COUNT(*) FROM orders WHERE status='canceled'").fetchone()[0]
        dup = cur.execute(
            "SELECT COUNT(*) FROM (SELECT ft_trade_id, order_date, ft_order_side, "
            "COUNT(*) n FROM orders GROUP BY 1,2,3 HAVING n > 1)"
        ).fetchone()[0]
        con.close()
        cancel_rate = (c / o) if o else 0.0
        counters["cancel_rate"] = cancel_rate
        counters["orders"] = o
        out.append(f"  1c cancelled-order rate : {c}/{o} = {cancel_rate:.1%} "
                   f"(max {MAX_CANCEL_RATE:.0%}) "
                   f"{'OK' if cancel_rate <= MAX_CANCEL_RATE else 'FAIL'}")
        out.append(f"  1g duplicate orders     : {dup} "
                   f"{'OK' if dup == 0 else 'FAIL'}")
    else:
        out.append("  1c cancelled-order rate : no DB")
        out.append("  1g duplicate orders     : no DB")

    # 1d realised cost — cannot be measured without real fills; state that
    out.append("  1d realised cost        : NOT MEASURABLE in dry-run "
               "(no real fills) — requires live or recorded spread")

    failed = []
    if bad_sig: failed.append("1a")
    if bad_exp: failed.append("1b")
    if cancel_rate is not None and cancel_rate > MAX_CANCEL_RATE: failed.append("1c")
    if cadence_ok is False: failed.append("1e")

    if failed:
        status = "FAIL"
    elif n_days < MIN_DAYS_FOR_IMPL or changes < MIN_REBALANCES_FOR_IMPL:
        status = "INSUFFICIENT_DATA"
    else:
        status = "PASS"
    return status, out, counters


def check_mechanism(df):
    """Criterion 2 — variance ratio on forward returns, vs the historical basis."""
    out = []
    if df.empty or df["candle_date"].nunique() < MIN_DAYS_FOR_MECH:
        out.append(f"  forward VR(20)          : INSUFFICIENT "
                   f"({df['candle_date'].nunique() if not df.empty else 0}d < "
                   f"{MIN_DAYS_FOR_MECH}d)")
        return "INSUFFICIENT_DATA", out

    d = pd.read_feather(DATA).sort_values("date").drop_duplicates("date")
    d = d.set_index("date")["close"].astype(float)
    r = d.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()

    start = pd.Timestamp(df["candle_date"].min(), tz=r.index.tz)
    fwd = r[r.index >= start]
    if len(fwd) < MIN_DAYS_FOR_MECH:
        out.append(f"  forward VR(20)          : INSUFFICIENT ({len(fwd)} returns)")
        return "INSUFFICIENT_DATA", out

    q = 20
    v = fwd.to_numpy()
    v1 = np.var(v, ddof=1)
    qr = np.convolve(v, np.ones(q), "valid")
    vr = float(np.var(qr, ddof=1) / (q * v1)) if v1 > 0 else np.nan
    out.append(f"  forward VR(20)          : {vr:.3f} "
               f"(historical basis ~1.19; threshold > {VR_THRESHOLD})")
    status = "PASS" if vr > VR_THRESHOLD else "FAIL"
    return status, out


def main():
    df = load_log()

    print("=" * 92)
    print("# FORWARD VALIDATION — CRITERION CHECK")
    print("=" * 92)
    print(f"\n  protocol : docs-myself/FORWARD-PROTOCOL.md")
    print(f"  frozen   : BTC/USD, SMA-50, 100/50, 10bps, pre-committed window")

    if df.empty:
        print("\n  no forward records found")
        return 0

    span = f"{df['candle_date'].min()} -> {df['candle_date'].max()}"
    print(f"  record   : {len(df)} observations, {df['candle_date'].nunique()} "
          f"distinct candles")
    print(f"  span     : {span}")

    s1, lines1, counters = check_implementation(df)
    print(f"\n{'=' * 92}")
    print("# CRITERION 1 — IMPLEMENTATION")
    print(f"{'=' * 92}")
    for ln in lines1:
        print(ln)
    print(f"\n  -> {s1}")

    s2, lines2 = check_mechanism(df)
    print(f"\n{'=' * 92}")
    print("# CRITERION 2 — MECHANISM (variance ratio)")
    print(f"{'=' * 92}")
    for ln in lines2:
        print(ln)
    print(f"\n  -> {s2}")

    # ---- Overall ----
    print(f"\n{'=' * 92}")
    print("# OVERALL")
    print(f"{'=' * 92}")
    print(f"\n  Criterion 1 (implementation) : {s1}")
    print(f"  Criterion 2 (mechanism)      : {s2}")

    if "FAIL" in (s1, s2):
        verdict = "IMPLEMENTATION INVALID — investigate per protocol"
    elif "INSUFFICIENT_DATA" in (s1, s2):
        verdict = ("IN PROGRESS — not enough forward record to judge. "
                   "Reporting PASS here would be over-reading (L6/L9).")
    else:
        verdict = ("IMPLEMENTATION FAITHFUL, mechanism not contradicted. "
                   "NOTE: this does NOT establish a durable edge — "
                   "SE(Sharpe) over this span is far too large.")
    print(f"\n  {verdict}")

    # Explicitly restate the power limit so no reader over-reads
    days = df["candle_date"].nunique()
    yrs = max(days / 365.0, 1e-9)
    print(f"\n  Power check: {days} forward days = {yrs:.2f}y "
          f"-> SE(Sharpe) ~ {1/np.sqrt(yrs):.2f}.")
    print(f"  The paired rule-vs-flat edge needs ~10-20 years to detect "
          f"(autocorrelation-adjusted; see findings-power-analysis.md).")
    print(f"  A profitable period here would NOT confirm the edge (protocol Question B).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
