"""Self-test: can the forward criteria checker actually DETECT failures?

A checker that only ever returns INSUFFICIENT_DATA is untested. Lesson L7 says
verify by exit code and by behaviour, not by inspection. Lesson L2 says a passing
check must be confirmed independently.

This script builds SYNTHETIC forward logs with known defects and asserts the
checker flags each one. If a defect goes undetected, the checker is broken and
the protocol is worthless.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

LOG = "user_data/forward_validation/parity_log.csv"
BACKUP = LOG + ".selftest.bak"

FIELDS = ["recorded_at", "candle_date", "close", "sma",
          "signal_target_exposure", "exposure_band", "live_trade_open",
          "live_stake", "live_amount", "live_rate", "live_exposure_frac",
          "live_open_orders", "live_order_count", "dry_run_wallet",
          "parity_signal", "parity_exposure", "notes"]


def make_log(n_days, parity_signal="OK", parity_exposure="OK",
             rebalance_every=19, start="2026-01-01"):
    """Build a synthetic log with a controlled number of rebalances."""
    rows = []
    dates = pd.date_range(start, periods=n_days, freq="D")
    # Start at 1.0 (risk-on); flip exposure every `rebalance_every` days
    expo = 1.0
    for i, d in enumerate(dates):
        if rebalance_every and i > 0 and i % rebalance_every == 0:
            expo = 0.5 if expo == 1.0 else 1.0
        rows.append({
            "recorded_at": d.isoformat(),
            "candle_date": str(d.date()),
            "close": 80000.0 + i,
            "sma": 72000.0,
            "signal_target_exposure": expo,
            "exposure_band": "1.00/0.50",
            "live_trade_open": True,
            "live_stake": 9999.0,
            "live_amount": 0.12,
            "live_rate": 80000.0,
            "live_exposure_frac": expo,
            "live_open_orders": 0,
            "live_order_count": 2,
            "dry_run_wallet": 10000.0,
            "parity_signal": parity_signal,
            "parity_exposure": parity_exposure,
            "notes": "",
        })
    return pd.DataFrame(rows, columns=FIELDS)


def run_checker():
    r = subprocess.run(
        [sys.executable, "tools/forward_criteria_check.py"],
        capture_output=True, text=True,
    )
    return r.stdout


def parse_verdicts(out):
    """Extract (criterion1, criterion2) verdicts by SECTION, not by '->'.

    Reading the last '->' line picks up Criterion 2, not Criterion 1 -- which is
    exactly the bug this self-test exists to catch. Parse the labelled overall
    summary instead; it is unambiguous.
    """
    c1 = c2 = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Criterion 1 (implementation)"):
            c1 = s.split(":", 1)[1].strip()
        elif s.startswith("Criterion 2 (mechanism)"):
            c2 = s.split(":", 1)[1].strip()
    return c1, c2


def main():
    print("=" * 92)
    print("# SELF-TEST — does the forward criteria checker detect real defects?")
    print("=" * 92)

    # back up the real log
    had = os.path.exists(LOG)
    if had:
        shutil.copy(LOG, BACKUP)

    os.makedirs(os.path.dirname(LOG), exist_ok=True)

    cases = [
        ("healthy, 200 days, ~19 reb/yr", 200, "OK", "OK", 19, "PASS"),
        ("signal mismatch", 200, "MISMATCH", "OK", 19, "FAIL"),
        ("exposure mismatch", 200, "OK", "MISMATCH", 19, "FAIL"),
        ("too few rebalances (~3.6/yr)", 200, "OK", "OK", 55, "FAIL"),
        ("too many rebalances (~73/yr)", 200, "OK", "OK", 5, "FAIL"),
        ("short record (30 days)", 30, "OK", "OK", 19, "INSUFFICIENT_DATA"),
    ]

    passed = 0
    try:
        for label, n, ps, pe, rebal, expect in cases:
            df = make_log(n, ps, pe, rebal)
            df.to_csv(LOG, index=False)
            out = run_checker()
            c1, _c2 = parse_verdicts(out)
            verdict = c1
            ok = verdict == expect
            passed += ok
            status = "OK  " if ok else "BAD "
            print(f"  {status} {label:<32} expected {expect:<18} got {verdict}")
    finally:
        if had:
            shutil.move(BACKUP, LOG)
        else:
            os.remove(LOG)

    print(f"\n  {passed}/{len(cases)} defect cases detected correctly")
    print(f"\n  -> {'checker is functional' if passed == len(cases) else 'CHECKER IS BROKEN -- fix before trusting it'}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
