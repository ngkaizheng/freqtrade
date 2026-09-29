"""GATE: did the long book's stop actually apply, and at the CONFIGURED distance?

WHY THIS FILE EXISTS
--------------------
`verify_stop.py` is the short book's flagship gate: it reads the trade export, recomputes the
frozen rule from the raw candles, and asserts the two agree, with ZERO tolerance for a trade that
fell through to the class backstop. The long book was delivered on 2026-09-30 with a published
result and **no equivalent gate at all**.

The absence was not harmless. On its first run this gate found two things the 50 previous rounds
did not:

  1. **THE FLOOR WAS AT THE WRONG MULTIPLE.** `PerpLong4h` placed its floor with `self.atr_stop`
     - the frozen class constant, 1.5 - while `PerpShort4hStop` reads the config into a property
     called `stop_mult` and the short book used that. So the long book was SIZED for 4.0xATR and
     STOPPED at 1.5xATR. 797 of 835 floor-bound stops sat at exactly 1.5; **zero** at the
     configured 4.0. Check 3 below exists solely to make that class of defect impossible to ship.
  2. **ONE STOP OUT OF 993 NEVER GOT INSTALLED** and the trade rode to the -30 % class backstop.

THE RULE, AS THE ENGINE EXECUTES IT
------------------------------------
For a long in `exit_mode="run"`, on every bar b since entry:

    floor   = entry - stop_mult x ATR(entry bar)              # never loosen
    trail   = (running peak of `high` since entry) - chandelier_atr x ATR(b)
    stop_b  = max(trail, floor)
    if stop_b >= price(b): install nothing (the stop is already violated)
    else:                 stop := max(stop, stop_b)          # freqtrade only tightens

That is not a single formula, it is a ratchet with a "sometimes nothing happens" branch, so the
gate does not try to replay it. **It brackets the answer instead**, which is exact and cannot be
fooled by a wrong guess about which bar set the stop:

    floor  <=  realised_stop  <=  max(trail at the exit bar, floor)

and it separately pins the floor multiple to the CONFIGURED value. A stop tighter than the rule
allows is as much a bug as one that is too loose, and both bounds are checked.

CHECKS
------
  1. non-empty trade list, non-empty stop-exit list;
  2. every exit is a stop or the end-of-backtest `force_exit` - the BEHAVIOURAL proof that
     `exit_mode: "run"` was honoured (in `fixed` mode this book emits hundreds of `time_stop`s);
  3. **the floor is the configured multiple**: `m = (entry - stop)/ATR(entry) <= atr_stop` for
     every trade, AND a non-trivial share sits exactly at `atr_stop` so the check cannot pass
     vacuously. This is the check that would have caught the 1.5/4.0 split brain;
  4. no stop sits at the -30 % class backstop. **Mirrored for a long**: the backstop is 30 % BELOW
     entry, so the test is on `stop/entry` against 0.70, not against 0.30;
  5. the stop is never TIGHTER than the rule permits;
  6. on an entry-bar exit the stop is below entry (the mirror bug puts it above and exits at once).

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_verify_stop.py
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_verify_stop.py <archive.zip>
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATADIR = Path(os.environ.get("PERP_BULL_DATADIR", str(ROOT / "user_data" / "data" / "wide526")))
PINNED = ROOT / "user_data" / "bull_delivered_out"
DELIVERED_CFG = ROOT / "user_data" / "config_perp_bull_dry.json"
STRATEGY = "PerpLong4h"
TF = "4h"
ATR_PERIOD = 14
CLASS_BACKSTOP = 0.30
TOL_PCT = 0.004

STOP_REASONS = ("stop_loss", "trailing_stop_loss")
ALLOWED_REASONS = set(STOP_REASONS) | {"force_exit", "liquidation"}


def settings() -> dict:
    cfg = json.loads(DELIVERED_CFG.read_text(encoding="utf-8"))
    return {"atr_stop": float(cfg["atr_stop"]), "chandelier_atr": float(cfg["chandelier_atr"])}


def newest_archive() -> Path:
    """The PINNED delivery archive, located by matching the EMBEDDED config.

    "Newest zip in a directory several runs write into" is the decay trap that already bit
    `verify_stop.py`: it silently became a stale archive from a panel that has since been deleted,
    and the gate crashed instead of verifying anything. So the archive must carry the DELIVERED
    config - same strategy, same logfile, same exportfilename - or this refuses.
    """
    if not PINNED.is_dir():
        raise SystemExit(
            f"FAIL - {PINNED} does not exist. Create it, then run the backtest with\n"
            f"  --backtest-directory {PINNED}\n"
            f"(the directory must EXIST: freqtrade's _generate_filename tests is_dir() and, "
            f"finding it false, writes a FILE named after the path into its parent - silently.)"
        )
    want = json.loads(DELIVERED_CFG.read_text(encoding="utf-8"))
    hits = []
    for z in sorted(PINNED.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                cj = [n for n in zf.namelist() if n.endswith("_config.json")]
                if not cj:
                    continue
                c = json.loads(zf.read(cj[0]))
                if (c.get("strategy") == STRATEGY
                        and c.get("logfile") == want.get("logfile")
                        and c.get("exportfilename") == want.get("exportfilename")):
                    hits.append(z)
        except Exception:                                        # noqa: BLE001
            continue
    if not hits:
        raise SystemExit(f"FAIL - no archive in {PINNED} carries the delivered config")
    return hits[-1]


def atr_series(df: pd.DataFrame) -> pd.Series:
    """Exactly the strategy's ATR. Any divergence here invalidates the gate."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / ATR_PERIOD, adjust=False, min_periods=ATR_PERIOD).mean()


def main() -> int:
    st = settings()
    atr_stop, chand = st["atr_stop"], st["chandelier_atr"]
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest_archive()
    with zipfile.ZipFile(path) as zf:
        mj = [n for n in zf.namelist()
              if n.endswith(".json") and not n.endswith("_config.json")][0]
        payload = json.loads(zf.read(mj))
    strat = payload["strategy"][STRATEGY]
    trades = strat["trades"]
    comp = payload["strategy_comparison"][0]

    print(f"archive         : {path.name}")
    print(f"strategy        : {STRATEGY}   atr_stop(config) = {atr_stop}   "
          f"chandelier_atr = {chand}")
    print(f"trades          : {len(trades)}   total = {comp['profit_total'] * 100:.4f} %   "
          f"PF = {comp['profit_factor']:.4f}   maxDD = "
          f"{strat.get('max_relative_drawdown', float('nan')) * 100:.4f} %")

    fails: list[str] = []
    if not trades:
        print("\nFAIL - zero trades. That is a silent dead signal, not a result.")
        return 1

    reasons = Counter(t.get("exit_reason", "?") for t in trades)
    print(f"exit reasons    : {dict(reasons)}")
    bad_reasons = {k: v for k, v in reasons.items() if k not in ALLOWED_REASONS}
    if bad_reasons:
        fails.append(f"exit reasons outside exit_mode='run': {bad_reasons}")
        print(f"  [FAIL] unexpected exit reasons: {bad_reasons}")

    cache: dict[str, pd.DataFrame] = {}
    mults: list[float] = []
    at_floor = 0
    n_sl = 0
    fallthrough: list[str] = []
    warn: list[str] = []
    looser: list[str] = []
    tighter: list[str] = []
    above_entry: list[str] = []
    unmodelled: list[str] = []

    for t in trades:
        pair = t["pair"]
        fname = pair.replace("/", "_").replace(":", "_").replace("-", "_")
        fp = DATADIR / "futures" / f"{fname}-{TF}-futures.feather"
        if fp not in cache:
            d = pd.read_feather(fp)[["date", "open", "high", "low", "close"]].copy()
            d["atr"] = atr_series(d)
            cache[fp] = d.set_index("date")
        d = cache[fp]
        entry_ts = pd.Timestamp(t["open_date"]).tz_convert("UTC")
        exit_ts = pd.Timestamp(t["close_date"]).tz_convert("UTC")
        entry = float(t["open_rate"])
        lev = float(t.get("leverage") or 1.0)
        if t.get("exit_reason") not in STOP_REASONS or t.get("stop_loss_abs") is None:
            continue
        n_sl += 1
        stop = float(t["stop_loss_abs"])
        if entry <= 0:
            continue

        # ATR at the entry bar, or the bar before it: `entry_atr` falls back to the most
        # recent available bar on the entry candle, and both are causally legitimate.
        a_entry = None
        for bar in (entry_ts, entry_ts - pd.Timedelta(hours=4)):
            try:
                v = float(d.at[bar, "atr"])
            except KeyError:
                continue
            if np.isfinite(v) and v > 0:
                a_entry = v
                break
        if a_entry is None:
            unmodelled.append(f"{pair} {entry_ts}: no usable ATR at or before the entry bar")
            continue

        ratio = stop / entry
        m = (entry - stop) / a_entry
        mults.append(m)
        if abs(m - atr_stop) <= 0.02 * atr_stop:
            at_floor += 1

        # (4) the class backstop. Two DIFFERENT causes produce it and they are not the same
        # defect, so conflating them would hide one behind the other:
        #
        #   (a) THE ANCHOR IS UNREACHABLE. The configured floor sits WIDER than the class
        #       -30% backstop, and freqtrade only ever tightens, so the backstop silently
        #       becomes the operative stop. This is a property of the class `stoploss` and of
        #       the name, not a failure of the strategy - `verify_stop.py` already reports it
        #       as a warning for the short book, whose widest 4xATR stop is 28.35 % and so
        #       FITS. On FARTCOIN the 4xATR floor is 31.2 %, which does not. Note this class
        #       only exists BECAUSE of the B-6 fix: at the old 1.5xATR floor this name's stop
        #       was 11.7 % and comfortably inside.
        #   (b) THE STOP WAS NEVER INSTALLED. `custom_stoploss` returned None on every bar,
        #       so nothing was ever set. That is a genuine risk-control failure.
        if abs(ratio - (1.0 - CLASS_BACKSTOP)) < 0.005:
            floor_px = entry * lev - atr_stop * a_entry
            unreachable = floor_px < entry * (1.0 - CLASS_BACKSTOP) * (1 - TOL_PCT)
            msg = (f"{pair} {entry_ts} -> {exit_ts}: stop at {ratio:.4f} of entry "
                   f"({ratio - 1:+.2%})")
            if unreachable:
                warn.append(msg + f" - the {atr_stop:g}xATR floor is "
                                  f"{1 - floor_px / entry:.2%} of price, WIDER than the "
                                  f"-{CLASS_BACKSTOP:.0%} class backstop, which therefore "
                                  f"binds. The backstop is TIGHTER than intended, so the "
                                  f"realised risk is below target, not above it.")
            else:
                fallthrough.append(msg + " - the custom stop was NEVER INSTALLED on this "
                                         "trade (custom_stoploss returned None on every bar)")
            continue

        # (3) the floor may not be looser than the configured multiple
        if m > atr_stop * 1.01 + 0.01:
            looser.append(
                f"{pair} {entry_ts}: implied floor multiple {m:.3f} exceeds the configured "
                f"atr_stop {atr_stop:g} - the stop is further out than the strategy's own anchor")
        # (5) nor tighter than the rule allows. The chandelier is a RATCHET and the peak is
        # non-decreasing while the ATR is not, so the tightest legal stop is the running MAX
        # over the window - not the value at the exit bar. The first version used the exit bar
        # only and flagged 308 perfectly correct stops; a ceiling that is wrong in the strict
        # direction is worse than no ceiling, because it teaches the reader to ignore it.
        since = d.loc[entry_ts:exit_ts]
        if not since.empty and "atr" in since:
            floor = entry * lev - atr_stop * a_entry
            hi = since["high"].cummax().to_numpy()
            at = since["atr"].to_numpy()
            ok = np.isfinite(at) & (at > 0)
            if ok.any():
                legal = np.maximum(hi[ok] - chand * at[ok], floor)
                ceiling = float(legal.max())
                if stop > ceiling * (1 + TOL_PCT):
                    tighter.append(
                        f"{pair} {entry_ts}: stop {stop:.8f} is TIGHTER than the rule allows "
                        f"({ceiling:.8f})")
        # (6) the mirror bug
        if exit_ts == entry_ts and stop >= entry:
            above_entry.append(f"{pair} {entry_ts}: stop {stop:.8f} is not below entry "
                               f"{entry:.8f} on the entry bar")

    print(f"\nstop exits      : {n_sl}")
    if n_sl == 0:
        fails.append("no stop exits at all - the stop may never have applied")
    if mults:
        m = np.array(mults)
        print(f"implied floor multiple (entry - stop) / ATR(entry):")
        print(f"   min {m.min():.3f}  p5 {np.percentile(m, 5):.3f}  median "
              f"{np.median(m):.3f}  max {m.max():.3f}   (atr_stop = {atr_stop:g})")
        print(f"   sitting on the configured floor: {at_floor} of {len(m)} "
              f"({100 * at_floor / len(m):.1f} %)")
        if len(m) > 5:
            s = np.sort(m[m > 0])
            if len(s) > 1:
                print(f"   worst {s[-1]:.3f}  2nd-worst {s[-2]:.3f}   "
                      f"<- a stop-distance distribution has no hole in it")
        # a gate that cannot fail is not a gate: if almost nothing sits on the floor the
        # ceiling test is carrying the whole load, and that must be visible.
        share = at_floor / len(m)
        if share < 0.05:
            fails.append(f"only {share:.1%} of stops sit on the configured floor, so check 3 "
                         f"is nearly vacuous - the gate is not proving what it claims")
        if m.max() > atr_stop * 1.01 + 0.01:
            print(f"   MAX {m.max():.3f} EXCEEDS atr_stop {atr_stop:g} "
                  f"<- the floor is not the configured multiple")

    for label, items in (("stop never installed", fallthrough),
                         ("stop looser than the anchor", looser),
                         ("stop tighter than the rule", tighter),
                         ("stop not below entry", above_entry),
                         ("unmodelled", unmodelled)):
        if items:
            fails.append(f"{len(items)} {label}")
            print(f"\n[FAIL] {len(items)} {label}:")
            for x in items[:8]:
                print("   x", x)
            if len(items) > 8:
                print(f"   ... and {len(items) - 8} more")
    if warn:
        print(f"\n[warn] {len(warn)} trade(s) stopped by the class backstop because the "
              f"configured floor is wider than it. Not a failure -")
        print("       the backstop is tighter than the strategy intended, so realised risk "
              "is BELOW target.")
        for x in warn[:5]:
            print("   !", x)
        if len(warn) > 5:
            print(f"   ... and {len(warn) - 5} more")

    print()
    if fails:
        print(f"FAIL - the stop did NOT apply as configured. {len(fails)} problem(s).")
        return 1
    print(f"PASS - all {n_sl} stop exits respect the configured {atr_stop:g}xATR floor, none "
          f"fell through to the\n       -{CLASS_BACKSTOP:.0%} class backstop, none is tighter "
          f"than the chandelier rule permits, and every exit is a\n       stop or the "
          f"end-of-backtest force_exit - which is what exit_mode='run' means.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
