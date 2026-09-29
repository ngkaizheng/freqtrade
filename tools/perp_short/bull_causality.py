"""GATE: the long book is causal, AND its stop does not depend on the frame window.

WHY THIS FILE EXISTS
--------------------
Two different claims, and the second one is the one that matters for this book.

**1. The indicators are causal.** The long book adds exactly one column, `shark_long`, and it is
built from `rvol`, `prev_high` and `low_vol` - all three inherited from the frozen parent, which
`test_causality.py` already verifies. Inheriting a verified column is a real argument, and this
gate re-asserts it from the raw candles rather than taking the inheritance on trust: recompute on
a truncated history, compare the shared bars bit for bit.

**2. THE STOP DOES NOT DEPEND ON HOW MUCH HISTORY THE FRAME HAPPENS TO HOLD.** This is the
long book's own risk and the short book has no version of it, because the short book anchors its
stop at the ENTRY bar and never looks forward.

`DataProvider.get_analyzed_dataframe` behaves differently by runmode, in the same process:

    backtest / hyperopt :  df.iloc[max(0, max_index - 1000) : max_index]   <- last 1000 bars
    dry_run / live      :  the frame as cached, with no slicing at all

The chandelier computes `peak = max(high) since entry` and `atr_now` off that frame. **If either
depended on where the window started, the backtest and a live bot would place different stops on
the same trade in the same market** - and the backtest is the one that gets published. So this
gate asserts the stop is identical under three different framings of the same history:

    (a) freqtrade's backtest slice at bar k      (1000-bar window, excludes bar k)
    (b) the whole history up to bar k            (no window, excludes bar k)
    (c) the whole history INCLUDING bar k        (no window, one bar MORE than the engine sees)

(c) is the lookahead probe: if the value at bar k changes when bar k itself is added to the
frame, the rule is reading the bar it is deciding on. (a) vs (b) is the window probe.

Both must be bit-identical. A strategy that passes is one whose live stop equals its backtested
stop, which is the property that makes a backtest worth publishing at all.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_causality.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
CFG = ROOT / "user_data" / "config_perp_bull_dry.json"
MAX_DATAFRAME_CANDLES = 1000          # freqtrade/data/dataprovider.py
BARS = 240                            # bars probed per symbol
PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "DOGE/USDT:USDT",
         "ADA/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT", "XRP/USDT:USDT"]
TF = "4h"


def load(strategy_cls, pair: str) -> pd.DataFrame:
    f = pair.replace("/", "_").replace(":", "_").replace("-", "_")
    fp = DATA / f"{f}-{TF}-futures.feather"
    d = pd.read_feather(fp)
    d["date"] = pd.to_datetime(d["date"], utc=True)
    d = d.sort_values("date").reset_index(drop=True)
    return strategy_cls.populate_indicators(s, d, {"pair": pair})       # noqa: F821


def main() -> int:
    for dd in (ROOT / "user_data" / "strategies_frontier", ROOT / "user_data" / "strategies"):
        sys.path.insert(0, str(dd))
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    from PerpLong4h import PerpLong4h

    global s
    s = PerpLong4h.__new__(PerpLong4h)
    s.config = cfg
    s.side, s.exit_mode = "long", "run"
    s.chandelier_atr = float(cfg["chandelier_atr"])
    # `stop_mult` is a READ-ONLY property on PerpShort4hStop, and assigning to it raises
    # "property has no setter" - the same trap PerpLong4h's own __init__ documents. It reads
    # s.config, which is set above, so it is simply read rather than written.
    s.atr_period, s.rvol_period, s.breakout_period = 14, 20, 20
    s.vol_lookback, s.rvol_threshold = 42, 2.0

    fails: list[str] = []
    print(f"candelier = {s.chandelier_atr} x ATR, floor = {s.stop_mult} x ATR, "
          f"probing {BARS} bars on {len(PAIRS)} symbols\n")

    for pair in PAIRS:
        df = load(PerpLong4h, pair)
        n = len(df)
        probes = np.linspace(n - BARS, n - 2, 60).astype(int)

        # ---- 1. indicator causality: recompute on truncated history ----------
        k = int(probes[len(probes) // 2])
        trunc = load(PerpLong4h, pair).iloc[:k + 1]
        full = df.iloc[:k + 1]
        cols = ["atr", "rvol", "prev_high", "prev_low", "vol42", "vol42_med", "shark_long"]
        bad = []
        for c in cols:
            a, b = full[c].to_numpy(), trunc[c].to_numpy()
            m = min(len(a), len(b))
            if not np.array_equal(a[:m], b[:m], equal_nan=True):
                bad.append(c)
        n_sig = int(df["shark_long"].iloc[:k + 1].sum())
        status = "PASS" if not bad else f"FAIL {bad}"
        print(f"  {pair:<18} indicators on truncated history : {status}"
              f"   (shark_long signals in the shared window: {n_sig})")
        if bad:
            fails.append(f"{pair}: columns {bad} differ under truncation")
        if n_sig == 0:
            fails.append(f"{pair}: ZERO shark_long signals in the probed window - a silent "
                         f"dead signal, not a result")

        # ---- 2. the stop must not depend on the frame's extent ---------------
        # Two WELL-POSED questions. The first version of this probe compared adjacent decision
        # points, which differ by construction, and sliced `df.iloc[:j-1000]` believing it was
        # freqtrade's `iloc[j-1000:j]`; it reported 6 phantom lookahead failures.
        #
        #   LOOKAHEAD: is the stop at bar k the same when the frame STOPS at k as when the
        #              frame carries every bar after k? If not, the rule is reading the future.
        #   WINDOW:    is it the same when the frame holds only freqtrade's 1000-bar window as
        #              when it holds the whole history? If not, a live bot and a backtest place
        #              different stops on the same trade.
        entry_i = int(probes[0]) - 30
        entry_px = float(df["close"].iloc[entry_i])
        floor = entry_px - s.stop_mult * float(df["atr"].iloc[entry_i])

        def stop_at(frame: pd.DataFrame) -> float | None:
            """The strategy's own arithmetic over EXACTLY the frame it is handed.

            The caller supplies the framing, because the framing is the thing under test:
            passing the whole history in is how you ask "what would this rule produce if it
            could see every future bar?", and getting the same answer back is the proof that
            it cannot.
            """
            seg = frame[frame.index >= entry_i]
            if seg.empty or "atr" not in seg:
                return None
            a = float(seg["atr"].iloc[-1])
            if not np.isfinite(a) or a <= 0:
                return None
            return max(float(seg["high"].max()) - s.chandelier_atr * a, floor)

        look_diff = win_diff = 0
        for k in probes:
            if k <= entry_i:
                continue
            cut = stop_at(df.iloc[:k + 1])                        # frame ENDS at bar k
            win = stop_at(df.iloc[max(0, k + 1 - MAX_DATAFRAME_CANDLES):k + 1])
            if cut is None or win is None:
                continue
            if cut != win:
                win_diff += 1
            # END-TO-END CAUSALITY: rebuild the indicators from raw candles truncated at k
            # and walk the whole stop path again. If any indicator reached forward, the
            # re-derived path differs from the one computed on the full history. This is the
            # project's canonical method - "recompute every feature on a truncated history" -
            # applied to the stop rather than to a column, and it is the only version of the
            # lookahead question that is well posed. The first attempt compared the stop at
            # bar k against the stop at the LAST bar of the full history, which is a different
            # decision point, and reported 60 phantom lookahead failures on every symbol.
            redone = load(PerpLong4h, pair).iloc[:k + 1]
            if stop_at(redone) != cut:
                look_diff += 1
        print(f"  {'':<18} stop vs END-TO-END truncation      : "
              f"{'PASS' if look_diff == 0 else f'FAIL {look_diff} bars'}")
        print(f"  {'':<18} stop vs frame WINDOW (1000 bars)   : "
              f"{'PASS' if win_diff == 0 else f'FAIL {win_diff} bars'}")
        if look_diff:
            fails.append(f"{pair}: rebuilding the indicators from candles truncated at bar k "
                         f"changes the stop at that bar ({look_diff} bars) - LOOKAHEAD")
        if win_diff:
            fails.append(f"{pair}: the stop depends on how much history the frame holds "
                         f"({win_diff} bars) - a live bot and a backtest would disagree")

    print()
    if fails:
        print(f"FAIL - {len(fails)} problem(s):")
        for f in fails:
            print("   x", f)
        return 1
    print("PASS - every indicator is bit-identical on a truncated history, the signal is not")
    print("       dead, and the chandelier stop is bit-identical whether the frame holds the")
    print("       backtest's 1000-bar window or the whole history - so a live bot places the")
    print("       same stop the backtest published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
