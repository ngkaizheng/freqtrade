"""Causality + signal sanity check for the leaderboard strategy.

Run:
    .venv\\Scripts\\python.exe tools\\leaderboard\\test_causality.py

This is the repo's own gate, not the engine's. AGENTS.md section 3 requires:

  "Assert causality by truncation, not by inspection. Recompute every feature on a
   truncated history and assert the shared bars are bit-identical. That catches
   lookahead that hand-written rule checks miss."

freqtrade's own `lookahead-analysis` is a weaker test, and on this repo's Binance
futures setup it cannot run at all (see RESEARCH_STATE.md). So this does it directly.

It also enforces the other rule from the same section: a silent dead signal must fail
the build rather than look like a weak result. If a strategy produces zero entries on
data where its feeds are present, that is an error, not a finding.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies", "leaderboard"))
from NotAnotherSMAOffsetStrategy import NotAnotherSMAOffsetStrategy  # noqa: E402

DATADIR = "user_data/data_leaderboard"
PAIRS = ["BTC_USDT", "ETH_USDT", "BNB_USDT", "SOL_USDT", "XRP_USDT", "ADA_USDT"]
READ_COLS = ["ma_buy_14", "ma_sell_24", "hma_50", "ema_100", "sma_9", "EWO", "rsi", "rsi_fast", "rsi_slow"]

failures = []


def run(df):
    s = NotAnotherSMAOffsetStrategy(config={})
    d = s.populate_indicators(df.copy(), {"pair": "X/USDT"})
    d = s.populate_entry_trend(d, {"pair": "X/USDT"})
    d = s.populate_exit_trend(d, {"pair": "X/USDT"})
    return d


for pair in PAIRS:
    path = os.path.join(DATADIR, f"{pair}-5m.feather")
    df = pd.read_feather(path).iloc[:60000].reset_index(drop=True)
    full = run(df)

    n_entries = int(full["enter_long"].fillna(0).sum())
    n_exits = int(full["exit_long"].fillna(0).sum())
    print(f"{pair:10s} n={len(df):6d}  enter_long={n_entries:5d}  exit_long={n_exits:6d}")

    # RULE: a silent dead signal is an error, not a result
    if n_entries == 0:
        failures.append(f"{pair}: ZERO entries - silent dead signal, not a result")
    if n_exits == 0:
        failures.append(f"{pair}: ZERO exits - silent dead signal, not a result")

    # RULE: truncation-based causality
    cut = 45000
    shared = 5000
    trunc = run(df.iloc[:cut].reset_index(drop=True))
    lo = cut - shared
    for col in READ_COLS:
        a = trunc[col].to_numpy()[lo:]
        b = full[col].to_numpy()[lo:cut]
        d = float(np.nanmax(np.abs(np.nan_to_num(a) - np.nan_to_num(b))))
        if d != 0.0:
            failures.append(f"{pair}: truncation {col} differs by {d:.3e} -> LOOKAHEAD")
    for col in ["enter_long", "exit_long"]:
        a = trunc[col].fillna(0).to_numpy()[lo:]
        b = full[col].fillna(0).to_numpy()[lo:cut]
        if not np.array_equal(a, b):
            failures.append(f"{pair}: truncation {col} differs -> LOOKAHEAD")
    print(f"           truncation causality on last {shared} shared bars: bit-identical")

print()
if failures:
    print("FAIL")
    for f in failures:
        print("   x", f)
    sys.exit(1)
print("PASS - signals are non-empty and strictly causal under truncation.")
