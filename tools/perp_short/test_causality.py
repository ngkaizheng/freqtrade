"""Causality gate for PerpShort4h, by truncation - not by inspection.

WHY TRUNCATION AND NOT lookahead-analysis
-----------------------------------------
`freqtrade lookahead-analysis` is worth running, and the repo runs it. But its
own docs caveat it: *"A negative result of each does not guarantee that there
are none of the above errors included"*, and Freqle (which builds a 5,330-row
leaderboard on the engine) concedes it *"identifies most common problems"*.

A truncation test is strictly stronger for a causal indicator set: recompute
every feature on a history that ENDS EARLIER, and assert the overlapping bars
are bit-identical. A single look-ahead - a `.max()` that forgot `.shift(1)`, a
rolling median computed over the current bar, an `.expanding()` that peeks -
changes a value on a bar near the cut. Inspection does not catch that;
recomputation does.

It also catches the class this repository has actually paid for: a silent
fallback or an all-False mask that produces a plausible, empty, wrong answer.

CHECKS
------
  1. Every indicator column is bit-identical on the shared bars under truncation.
  2. `shark_short`, `enter_short` and `enter_tag` are bit-identical likewise.
  3. The signal is NOT empty. A zero-trade strategy is a silent dead signal, and
     it must fail the build, not look like a weak result (AGENTS.md §3).
  4. The Donchian level really excludes the bar it is tested against: feeding a
     bar with a brand-new high must not change that bar's own `prev_high`.
  5. The vol-median comparison really excludes the signal bar's own volatility.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\test_causality.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join("user_data", "strategies"))

from PerpShort4h import PerpShort4h  # noqa: E402

DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide104")
PAIRS = ["BTC_USDT_USDT", "ETH_USDT_USDT", "SOL_USDT_USDT", "DOGE_USDT_USDT",
         "AAVE_USDT_USDT", "XRP_USDT_USDT"]
COLS = ["atr", "volume_sma", "rvol", "prev_high", "prev_low", "vol42",
        "vol42_med", "low_vol", "shark_short", "enter_short"]
OVERLAP = 1500

failures: list[str] = []


def run(df: pd.DataFrame) -> pd.DataFrame:
    s = PerpShort4h(config={})
    out = s.populate_indicators(df.copy(), {"pair": "X/USDT:USDT"})
    return s.populate_entry_trend(out, {"pair": "X/USDT:USDT"})


def same(a, b, name) -> bool:
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        failures.append(f"{name}: shape {a.shape} vs {b.shape}")
        return False
    if a.dtype == bool or b.dtype == bool or a.dtype.kind in "OSU":
        ok = np.array_equal(a.astype(object), b.astype(object))
    else:
        an, bn = np.isnan(a.astype(float)), np.isnan(b.astype(float))
        if not np.array_equal(an, bn):
            failures.append(f"{name}: NaN pattern differs")
            return False
        ok = np.array_equal(np.nan_to_num(a.astype(float)),
                            np.nan_to_num(b.astype(float)))
    if not ok:
        failures.append(f"{name}: NOT bit-identical under truncation")
    return ok


def main() -> int:
    print("TRUNCATION CAUSALITY GATE - PerpShort4h")
    print(f"datadir: {DATADIR}\n")
    for p in PAIRS:
        fp = os.path.join(DATADIR, "futures", f"{p}-4h-futures.feather")
        if not os.path.exists(fp):
            failures.append(f"missing {fp}")
            continue
        df = pd.read_feather(fp)
        if len(df) < OVERLAP * 3:
            failures.append(f"{p}: only {len(df)} bars, need > {OVERLAP*3}")
            continue

        full = run(df)
        n_sig = int(full["shark_short"].sum())
        if n_sig == 0:
            failures.append(f"{p}: ZERO signals - silent dead signal, not a result")
        print(f"{p:<18} bars={len(df):<6} signals={n_sig:<5} "
              f"({n_sig/len(df)*100:.2f}%)  first={df['date'].iloc[0].date()}")

        for cut in (len(df) - 800, len(df) - 2500):
            tr = run(df.iloc[:cut].reset_index(drop=True))
            lo = cut - OVERLAP
            for c in COLS:
                same(tr[c].to_numpy()[lo:], full[c].to_numpy()[lo:cut],
                     f"{p} cut={cut} {c}")
            same(tr["enter_tag"].to_numpy()[lo:],
                 full["enter_tag"].to_numpy()[lo:cut], f"{p} cut={cut} enter_tag")
        print(f"{'':<18} truncation at 2 cut points, last {OVERLAP} shared bars: OK")

    # ---- check 4: the Donchian level excludes its own bar ----
    d = pd.read_feather(os.path.join(DATADIR, "futures",
                                     f"{PAIRS[0]}-4h-futures.feather")).iloc[:3000].copy()
    base = run(d)
    spiked = d.copy()
    # give the LAST bar a high above every previous high
    spiked.loc[spiked.index[-1], "high"] = base["high"].max() * 2.0
    out = run(spiked)
    lo = len(d) - 1 - 5
    if not np.array_equal(base["prev_high"].to_numpy()[lo:],
                          out["prev_high"].to_numpy()[lo:]):
        failures.append("CHECK 4: prev_high on a prior bar changed when the LAST "
                        "bar's high was spiked -> the level contains its own bar")
    else:
        print("\nCHECK 4  Donchian excludes the tested bar: OK "
              "(spiking the last bar's high left earlier prev_high bit-identical)")

    # ---- check 5: the vol median excludes the signal bar ----
    spiked2 = d.copy()
    spiked2.loc[spiked2.index[-1], "close"] = base["close"].iloc[-1] * 3.0
    out2 = run(spiked2)
    if not np.array_equal(base["vol42_med"].to_numpy()[lo:],
                          out2["vol42_med"].to_numpy()[lo:]):
        failures.append("CHECK 5: vol42_med on a prior bar changed when the LAST "
                        "bar's price was spiked -> the threshold sees its own bar")
    else:
        print("CHECK 5  vol-median excludes the signal bar: OK")

    print()
    if failures:
        print("FAIL")
        for f in failures[:25]:
            print("   x", f)
        return 1
    print("PASS - every indicator, mask and tag is bit-identical under truncation,")
    print("       the signal is non-empty, and both look-ahead probes are negative.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
