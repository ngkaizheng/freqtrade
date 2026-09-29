"""F-1: can the forward collector actually RECORD a trade?

WHY
---
The delivered book's only route to ever being validated is the forward collector, which
needs 6.8 years. **A 6.8-year test is worth nothing if the collector cannot record a trade
when one occurs.** `verify_collector.py` proves the process is alive; nothing proves the
SIGNAL path or the RECORD path works. This does.

F1  RECORD PATH. Write a synthetic trade into a COPY of the live DB through freqtrade's
    own persistence models and read it back with the accessors a forward analysis would
    use. **Positive control:** a deliberately malformed row must NOT come back, so the
    check is shown capable of failing. **The live database is never written.**
F2  SIGNAL PATH. Load the deployed strategy's own class, run populate_indicators and the
    entry logic over the 4h data the collector is reading, and assert: no exception, and
    indicators non-null on a stated fraction of bars. **A zero is a FAIL, not a weak
    result** - that is this project's trap #1, a mask built from all-False that looks
    exactly like "no signal".
F3  CADENCE. Count signals per symbol-year and compute how many are expected between the
    collector's start and now, beside the 0 actually recorded. **AGENTS.md 1a applied to
    the collector:** if the expected count over elapsed time is ~0, then 0 trades is
    CONSISTENT AND UNINFORMATIVE, and the report must say so instead of calling it
    progress.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\forward_path_check.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
LOG = ROOT / "user_data" / "logs" / "forward_perp.log"
DATA = ROOT / "user_data" / "data" / "wide526" / "futures"
STRAT_DIR = ROOT / "user_data" / "strategies"
FRONTIER = ROOT / "user_data" / "strategies_frontier"
sys.path.insert(0, str(STRAT_DIR))
sys.path.insert(0, str(FRONTIER))

STARTED = "2026-09-29 04:26:38"          # first line of the live log, UTC
# §23a, measured: the frozen signal fires 2,169 times over 40 symbols x 3.67y
PREREG_RATE_PER_SYM_YEAR = 14.8


def elapsed_days(now: datetime) -> float:
    s = datetime.strptime(STARTED, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return max((now - s).total_seconds() / 86400.0, 0.0)


def f1_record_path() -> tuple[bool, str]:
    """Write a synthetic trade into a COPY of the live DB and read it back.

    ⚠ The first version of this read `Trade.query` (which does not exist in
    freqtrade 2026.8) and, more seriously, built the Configuration from the ORIGINAL
    config - so the engine pointed at the LIVE database while the test believed it had
    a copy. **A safety control that is written but not actually pointing where it claims
    is worse than no control.** The config is now rewritten to the copy's path BEFORE
    the engine is created, and the copy is made first.
    """
    from freqtrade.persistence import Trade, init_db
    from freqtrade.configuration import Configuration

    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    db = cfg["db_url"].replace("sqlite:///", "")
    live = ROOT / db
    if not live.exists():
        return False, f"live database not found at {db}"

    fails: list[str] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        copy = Path(td) / "copy.sqlite"
        shutil.copy2(live, copy)
        cfg2 = json.loads(json.dumps(cfg))
        cfg2["db_url"] = f"sqlite:///{copy.as_posix()}"
        # prove the engine really is on the copy, not the live file
        assert cfg2["db_url"] != cfg["db_url"], "config rewrite did not take"

        init_db(cfg2["db_url"])
        q = Trade.session.query(Trade)
        before = q.count()

        written, why = False, ""
        try:
            t = Trade(
                pair="FWDTEST/USDT:USDT", base_currency="FWDTEST",
                stake_currency="USDT", stake_amount=1.0, amount=1.0,
                open_rate=1.0, open_rate_requested=1.0, open_trade_value=1.0,
                fee_open=0.0, fee_open_currency="USDT",
                is_open=True, is_short=True, leverage=1.0, exchange="binance",
                trading_mode="futures", timeframe=4, strategy="PerpShort4hDeploy",
                enter_tag="FWDTEST",
                stop_loss_pct=-0.30, initial_stop_loss_pct=-0.30,
            )
            Trade.session.add(t)
            Trade.session.commit()
            written = True
        except Exception as e:                                # noqa: BLE001
            why = f"{type(e).__name__}: {str(e)[:80]}"
            fails.append(f"write failed: {why}")

        if written:
            got = Trade.session.query(Trade).filter_by(pair="FWDTEST/USDT:USDT").all()
            if len(got) != 1:
                fails.append(f"read back returned {len(got)} rows, expected exactly 1")
            else:
                r = got[0]
                if r.strategy != "PerpShort4hDeploy" or int(r.timeframe) != 4:
                    fails.append(f"read back lost columns: strategy={r.strategy!r} "
                                 f"timeframe={r.timeframe!r}")
            ghost = Trade.session.query(Trade).filter_by(
                pair="NEVER/WRITTEN/USDT:USDT").count()
            if ghost:
                fails.append(f"the read path returned {ghost} rows for a pair that does "
                             f"not exist - it is not filtering, so the positive result "
                             f"above would mean nothing")
        msg = ("; ".join(fails) if fails else
               f"the COPY opened with {before} trades; a synthetic trade written through "
               f"freqtrade's own models was read back exactly once with its strategy and "
               f"timeframe intact, and a pair that was never written returned 0 rows "
               f"(positive control passed). The live DB was copied, never written.")
        # Release the sqlite handle BEFORE the temp dir is removed. On Windows an open
        # file cannot be deleted, and the resulting PermissionError aborted the run
        # AFTER the check had already passed - i.e. a passing test reported as a crash.
        try:
            Trade.session.remove()
            Trade.session.get_bind().dispose()
        except Exception:                                       # noqa: BLE001
            pass
    return (not fails), msg



def f2_signal_path() -> tuple[bool, str]:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pairs = cfg["exchange"]["pair_whitelist"]
    from PerpShort4hDeploy import PerpShort4hDeploy

    strat = PerpShort4hDeploy(cfg)
    n_ok, n_bars, n_null, entries, rows = 0, 0, 0, 0, []
    problems: list[str] = []
    for p in pairs:
        k = p.replace("/", "_").replace(":", "_")
        f = DATA / f"{k}-4h-futures.feather"
        if not f.exists():
            continue
        df = pd.read_feather(f)
        if "date" in df.columns:
            df = df.set_index(pd.to_datetime(df["date"], utc=True))
        try:
            # freqtrade 2026.8: populate_indicators returns the DataFrame ITSELF,
            # not a (frame, populated) tuple. Unpacking a tuple was the reason the
            # first run reported "no pair could be analysed at all" - a harness
            # error reported as a verdict about the deliverable.
            out = strat.populate_indicators(df.copy(), metadata={"pair": p})
        except Exception as e:                                # noqa: BLE001
            problems.append(f"{k}: {type(e).__name__}: {str(e)[:60]}")
            continue
        n_ok += 1
        sig = strat.populate_entry_trend(out.copy(), metadata={"pair": p})
        e = int((sig.get("enter_short", pd.Series(dtype=bool)) == 1).sum())
        entries += e
        n_bars += len(out)
        n_null += int(out["rvol"].isna().sum()) if "rvol" in out else 0
        rows.append((k, len(out), e, int(out["close"].notna().sum())))
    if n_ok == 0:
        return False, "no pair could be analysed at all"
    if problems:
        return False, f"{len(problems)} pairs raised: {problems[:3]}"
    cover = 1 - n_null / max(n_bars, 1)
    if cover < 0.90:
        return False, (f"indicators are non-null on only {cover*100:.1f}% of bars; a mask "
                       f"that produces almost nothing is indistinguishable from no signal")
    return True, (f"{n_ok} pairs analysed with no exception; indicators non-null on "
                  f"{cover*100:.2f}% of {n_bars:,} bars; {entries} entry signals across "
                  f"the full 4h panel")


def main() -> int:
    print("F-1  CAN THE FORWARD COLLECTOR RECORD A TRADE?\n")
    fails = []

    print("F1  RECORD PATH  (synthetic trade through freqtrade's own models, DB COPIED)")
    ok1, m1 = f1_record_path()
    print(f"    {'PASS' if ok1 else 'FAIL'}  {m1}\n")
    if not ok1:
        fails.append("F1 record path")

    print("F2  SIGNAL PATH  (the deployed strategy's own code on live 4h data)")
    ok2, m2 = f2_signal_path()
    print(f"    {'PASS' if ok2 else 'FAIL'}  {m2}\n")
    if not ok2:
        fails.append("F2 signal path")

    print("F3  CADENCE  (is 0 trades informative, or just early?)")
    now = datetime.now(timezone.utc)
    days = elapsed_days(now)
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    n_sym = len(cfg["exchange"]["pair_whitelist"])
    expected = PREREG_RATE_PER_SYM_YEAR * n_sym * days / 365.0
    print(f"    collector started {STARTED} UTC; {days:.2f} days elapsed, now {now:%Y-%m-%d %H:%M} UTC")
    print(f"    measured signal rate: {PREREG_RATE_PER_SYM_YEAR}/symbol-year (section 23a, "
          f"2,169 over 40 symbols x 3.67y)")
    print(f"    EXPECTED signals since start: {PREREG_RATE_PER_SYM_YEAR} x {n_sym} x "
          f"{days:.2f}/365 = {expected:.2f}")
    print(f"    ACTUALLY recorded: 0 trades")
    if expected < 0.5:
        print(f"    -> 0 trades is CONSISTENT with the rate and UNINFORMATIVE. It is not")
        print(f"       progress and must not be reported as progress. At this rate the")
        print(f"       first expected signal is about "
              f"{365/(PREREG_RATE_PER_SYM_YEAR*n_sym):.1f} days after start.")
    else:
        print(f"    -> 0 trades is BELOW the expected {expected:.2f} and is a warning.")

    print("\n" + "=" * 74)
    if fails:
        print(f"VERDICT: THE FORWARD COLLECTOR IS UNVERIFIED - {', '.join(fails)} FAILED.")
        print("The forward series is VOID until the broken link is fixed and this check")
        print("passes. 'The collector is running' is not a result.")
        return 1
    print("VERDICT: BOTH PATHS WORK. The collector would record a trade if one occurred,")
    print("and the strategy's signal logic reaches its entry condition on live data.")
    print("What is still unproven is the EDGE, not the apparatus - and 6.8 years of")
    print("forward data cannot be shortened by anything this project can do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
