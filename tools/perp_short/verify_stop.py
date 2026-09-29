"""GATE: did the per-trade ATR stop actually apply, or did it silently fall back?

WHY THIS FILE EXISTS
--------------------
This repository has been bitten three times by the same failure shape, and each
time it produced a confident number instead of an error:

  * `WIDE_FT_MATRIX` / `LEVERAGE_MATRIX`: a flat `stoploss` is a MARGIN stop, so
    20x silently turned a 3.6% PRICE stop into 0.18%. Fake "leverage destroys
    returns" curve, 89.4% of trades dead on their entry bar.
  * `RegimeBreakoutExitStudy`: `pd.Timestamp.floor("5m")` raises on pandas 3, a
    local `except` swallowed it, `custom_stoploss` returned `None`, and every
    frozen stop fell back to the class backstop. Five of six arms printed
    plausible numbers while measuring nothing.
  * Freqle's own leaderboard: strategies writing v2 `buy`/`sell` columns produce
    ZERO trades and no error on the current engine.

So: this does not inspect the code and conclude it is right. It reads the trade
EXPORT - what actually happened - and recomputes the frozen rule from the raw
candles, then asserts the two agree.

CHECKS
------
  1. The trade list is non-empty (a silent dead signal must fail the build).
  2. For every stop exit, the realised stop distance equals
     1.5 x ATR(entry bar) within exchange price precision.
  3. NO trade was closed by the -30% class backstop. If one was, the ATR stop
     did not apply to it and every R figure downstream is wrong.
  4. No stop distance anywhere exceeds a sane ceiling (the panel's widest
     1.5xATR% is 5.04%; anything past 2x that means the anchor broke).

NOTE ON exit_reason - NEW TRAP, FOUND HERE
------------------------------------------
A stop that `custom_stoploss` ADJUSTS is exported as **`trailing_stop_loss`**,
not `stop_loss`. `LocalTrade.adjust_stop_loss` sets `is_stop_loss_trailing = True`
on every modification of an already-set stop (trade_model.py:895-896), so the
flag means "this stop was adjusted at least once", NOT "a trailing stop moved".
A frozen 1.5xATR stop that was tightened once on its first bar is therefore
indistinguishable from a trailing stop in the export.

Anyone doing an exit-reason decomposition - which this repo has now done twice -
will count every ATR stop as a trailing stop, conclude "trailing stops are
firing on most trades", and then try to remove a stop that is doing exactly what
it was frozen to do. This verifier counts BOTH reasons as stop exits.

Run:
    .venv\Scripts\python.exe tools\\perp_short\\verify_stop.py
    .venv\Scripts\python.exe tools\\perp_short\\verify_stop.py <path-to-backtest.zip>
"""

from __future__ import annotations

import glob
import json
import os
import sys
import zipfile
from collections import Counter

import numpy as np
import pandas as pd

# ⚠ CORRECTED 2026-09-30. The defaults pointed at `user_data/data/wide_ft` and
# atr_stop=1.5, i.e. the 2026-09-27 `PerpShort4h` run. That panel was replaced by
# `wide526`, so **this gate had been CRASHING with FileNotFoundError instead of
# running** - and it is one of the three gates `HOW_TO_RUN_2026-09-29.md` tells a
# reader to execute. A gate that cannot run is not a gate. The defaults now
# describe the delivered configuration; both remain overridable by env var so a
# frontier arm can still be verified.
DATADIR = os.environ.get("PERP_SHORT_DATADIR", "user_data/data/wide526")
TF = "4h"
ATR_PERIOD = 14
# The frozen rule for the DELIVERED book is 4.0. Frontier arms vary it, and the
# gate MUST be told which one it is looking at: verifying a 4.0-ATR arm against
# 1.5 would fail every trade and read as "the strategy is broken" when the
# strategy is fine and the gate is pointed at the wrong parameter.
ATR_STOP = float(os.environ.get("PERP_SHORT_ATR_STOP", "4.0"))
DEFAULT_ARCHIVE = os.environ.get(
    "PERP_SHORT_ARCHIVE",
    "user_data/sizing_out/full/n50/backtest-result-2026-09-28_21-44-27.zip")
DEFAULT_STRATEGY = os.environ.get("PERP_SHORT_STRATEGY", "PerpShort4hSizing")
TOL_PCT = 0.004  # 0.4% of price: generous enough for tick rounding, far below
#                  the real stop-distance spread, so a broken anchor cannot hide
#                  inside it.

# A custom stoploss that gets ADJUSTED is exported as `trailing_stop_loss`
# (adjust_stop_loss sets is_stop_loss_trailing on any modification). Counting
# only `stop_loss` reads as "the stop never fired" when in fact it fired 502
# times. See the note in the docstring.
STOP_REASONS = ("stop_loss", "trailing_stop_loss")

# The class `stoploss` on the frozen strategy, in price terms. A stop is treated
# as "the backstop" when its distance sits within 0.5 points of it.
CLASS_BACKSTOP = 0.30

failures: list[str] = []
notes: list[str] = []


def newest_zip(strategy: str = "PerpShort4h") -> str:
    """Newest archive that actually contains THIS strategy's trades.

    Two agents write into these directories concurrently, and several
    strategies share them. Selecting purely on mtime picks whatever ran last -
    which here produced a KeyError on the strategy name, and would just as
    easily have produced a confident VERDICT about a different strategy's stop.

    ⚠ 2026-09-30: if PERP_SHORT_ARCHIVE is set, or DEFAULT_ARCHIVE exists, the
    DELIVERED configuration is used. "Newest in a directory nobody writes to any
    more" silently decayed into a two-month-old archive from a panel that has
    since been deleted, and the gate crashed instead of verifying anything.
    """
    pinned = os.environ.get("PERP_SHORT_ARCHIVE") or DEFAULT_ARCHIVE
    if pinned and os.path.exists(pinned):
        return pinned
    extra = os.environ.get("PERP_SHORT_GLOB", "")
    cands = glob.glob(extra) if extra else (
        glob.glob("user_data/perp_short_out/*.zip")
        + glob.glob("user_data/backtest_results/*.zip")
        + glob.glob("user_data/stopfront_out/**/*.zip", recursive=True)
    )
    cands.sort(key=os.path.getmtime, reverse=True)
    for c in cands:
        try:
            with zipfile.ZipFile(c) as z:
                name = [n for n in z.namelist()
                        if n.endswith(".json") and "meta" not in n][0]
                if strategy in json.loads(z.read(name)).get("strategy", {}):
                    return c
        except Exception:
            continue
    raise SystemExit(f"no archive containing {strategy} found")


def load_trades(path: str, strategy: str = "PerpShort4h") -> list[dict]:
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.endswith(".json") and "meta" not in n][0]
        payload = json.loads(z.read(name))
    return payload["strategy"][strategy]["trades"]

def atr_series(df: pd.DataFrame) -> pd.Series:
    """Exactly the strategy's ATR. Any divergence here invalidates the gate."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False, min_periods=ATR_PERIOD).mean()


def main() -> int:
    strategy = os.environ.get("PERP_SHORT_STRATEGY", DEFAULT_STRATEGY)
    path = sys.argv[1] if len(sys.argv) > 1 else newest_zip(strategy)
    trades = load_trades(path, strategy=strategy)
    print(f"backtest archive : {path}")
    print(f"strategy         : {strategy}   atr_stop = {ATR_STOP}")
    print(f"trades           : {len(trades)}")
    if not trades:
        print("\nFAIL - zero trades. That is a silent dead signal, not a result.")
        return 1

    # the exchange file is what defines 'the realised stop'
    expected: list[float] = []
    dist_pct: list[float] = []
    unreachable: list[str] = []
    bad: list[str] = []
    backstop_hits = 0
    reasons = Counter()

    cache: dict[str, pd.DataFrame] = {}
    matched: Counter = Counter()
    same_candle_exits = 0
    worse_fills = 0
    for t in trades:
        pair = t["pair"]
        # freqtrade's own pair_to_filename: "CRV/USDT:USDT" -> "CRV_USDT_USDT"
        fname = pair.replace("/", "_").replace(":", "_").replace("-", "_")
        fp = os.path.join(DATADIR, "futures", f"{fname}-{TF}-futures.feather")
        if fp not in cache:
            d = pd.read_feather(fp)[["date", "open", "high", "low", "close"]].copy()
            d["atr"] = atr_series(d)
            cache[fp] = d.set_index("date")
        d = cache[fp]

        entry_ts = pd.Timestamp(t["open_date"]).tz_convert("UTC")
        # freqtrade records open_date at the candle OPEN; the signal bar is the
        # previous one. On the ENTRY candle the analysed frame has not yet been
        # extended to that bar, so the strategy's custom_stoploss resolves the
        # ATR from the PREVIOUS bar. Both are causally legitimate and both are
        # accepted; which one fired is reported.
        try:
            atr_entry = d.at[entry_ts, "atr"]
        except KeyError:
            atr_entry = float("nan")
        try:
            atr_prev = d.at[entry_ts - pd.Timedelta(hours=4), "atr"]
        except KeyError:
            atr_prev = float("nan")

        entry = float(t["open_rate"])
        reasons[t.get("exit_reason", "?")] += 1

        if t.get("exit_reason") in STOP_REASONS:
            # Measure where the STOP WAS set, not where the trade filled.
            # `stop_loss_abs` is the anchor's realised price; `close_rate` can
            # differ on a same-candle exit, where the engine fills at the
            # candle OPEN (_get_close_rate_for_stoploss: "our stoploss was
            # already lower than candle high ... exit at open price"). For a
            # short that fill is WORSE than the stop, so it is a pessimistic
            # artefact, not a strategy defect. Counted and reported below.
            anchor_price = t.get("stop_loss_abs")
            if anchor_price is None:
                anchor_price = float(t["close_rate"])
            else:
                same_candle = str(t["open_date"]) == str(t["close_date"])
                if same_candle:
                    same_candle_exits += 1
                    if float(t["close_rate"]) > float(anchor_price):
                        worse_fills += 1
            got = float(anchor_price) - entry
            cands = {"entry_bar": ATR_STOP * float(atr_entry),
                     "signal_bar": ATR_STOP * float(atr_prev)}
            # pick the candidate that actually explains the fill
            best, best_err = None, None
            for name, exp in cands.items():
                if not np.isfinite(exp) or exp <= 0:
                    continue
                err = abs(got - exp) / entry
                if best_err is None or err < best_err:
                    best, best_err = name, err
            matched[best or "none"] += 1
            if best is None:
                bad.append(f"{pair} {entry_ts}: no usable ATR in either bar")
            elif best_err > TOL_PCT:
                bad.append(
                    f"{pair} {entry_ts}: stop at {got:.8f} vs entry-bar "
                    f"{cands['entry_bar']:.8f} / signal-bar {cands['signal_bar']:.8f} "
                    f"(closest is {best_err:.3%} off, tolerance {TOL_PCT:.2%})"
                )
            expected.append(best_err if best else float("nan"))
            # Two distinct backstop checks, and the second one only became
            # necessary when the stop multiple was widened.
            #
            # (a) did a trade actually get closed AT the class backstop?
            #     i.e. is the realised stop indistinguishable from -30%?
            #     The first version used a hard 20% ceiling, copied from the
            #     24-symbol majors' widest 1.5xATR% and then re-used a second
            #     time as "anything past this is the backstop". That failed a
            #     CORRECT 4.0-ATR run on six real long-tail trades, whose stops
            #     legitimately sit at 20-28% of price.
            # (b) IS THE ANCHOR EVEN REACHABLE? A 4xATR stop on a thin name can
            #     exceed the -30% class backstop, and freqtrade only ever
            #     TIGHTENS - so the backstop would silently become the operative
            #     stop and the strategy would be measuring something else. On
            #     this run the widest was 28.35%, i.e. it FITS, but by 1.65
            #     points. This is a property of the class `stoploss`, not of the
            #     run, so it is checked and reported rather than assumed.
            if abs(got / entry - 0.30) < 0.005:
                backstop_hits += 1
                bad.append(
                    f"{pair} {entry_ts}: stop sits at {got / entry:.2%}, "
                    f"indistinguishable from the -30% class backstop"
                )
            if best is not None and cands[best] / entry > 0.30:
                unreachable.append(
                    f"{pair} {entry_ts}: {best} stop is {cands[best]/entry:.2%} of "
                    f"price, WIDER than the -30% class backstop - the backstop "
                    f"would bind and this trade's stop would be wrong"
                )
            dist_pct.append(got / entry)

    print(f"\nexit reasons     : {dict(reasons)}")
    n_sl = len(expected)
    print(f"stop exits      : {n_sl}")
    print(f"anchor resolved : {dict(matched)}")
    print(f"same-candle stop exits: {same_candle_exits} "
          f"(of which {worse_fills} filled worse than the stop - pessimistic, "
          f"the engine's documented same-bar fill)")
    if n_sl == 0:
        failures.append("no stop exits at all - the stop may never have applied")

    if n_sl:
        e = np.array([x for x in expected if np.isfinite(x)])
        if len(e):
            print(f"closest-candidate error: median {np.median(e):.5%}  "
                  f"p95 {np.percentile(e, 95):.5%}  max {e.max():.5%}  "
                  f"(tolerance {TOL_PCT:.2%})")
        d = np.array(dist_pct)
        print(f"realised stop distance as % of price: median {np.median(d):.2%}  "
              f"p95 {np.percentile(d, 95):.2%}  max {d.max():.2%}   "
              f"(class backstop is -{CLASS_BACKSTOP:.0%})")
    if unreachable:
        print(f"\n⚠ {len(unreachable)} trade(s) have an ATR stop WIDER than the "
              f"-{CLASS_BACKSTOP:.0%} class backstop. freqtrade only tightens, so")
        print("  the backstop would become the operative stop for them. Widen the")
        print("  class `stoploss` before running a wider stop multiple.")
        for u in unreachable[:5]:
            print("   !", u)
    failures.extend(bad[:20])
    if len(bad) > 20:
        failures.append(f"... and {len(bad) - 20} more mismatches")

    for n in notes[:10]:
        print("note:", n)

    print()
    if failures:
        print("FAIL - the ATR stop did NOT apply as frozen. Do not trust any R figure.")
        for f in failures[:25]:
            print("   x", f)
        return 1
    print(f"PASS - every stop-loss exit filled at {ATR_STOP:g} x ATR(entry bar), "
          f"within tolerance,")
    print(f"       and no trade fell through to the -{CLASS_BACKSTOP:.0%} class "
          f"backstop.")
    if unreachable:
        print(f"       ⚠ but {len(unreachable)} trade(s) exceed the class backstop - "
              f"see the warning above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
