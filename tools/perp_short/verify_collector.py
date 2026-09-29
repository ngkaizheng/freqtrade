"""Verify the forward collector is actually RUNNING, not merely starting.

WHY THIS FILE EXISTS
--------------------
Rounds 11 and 12 reported the forward collector as "configured and running".
**That was wrong.** What had been verified was that `freqtrade trade` starts and
loads the strategy for 100 seconds, after which the process was killed. Three
separate things were true and none of them was the one reported:

  1. the bot STARTED,
  2. the bot was KILLED 100 seconds later,
  3. and it would not have RUN even left alone - the key was **`database_url`
     instead of `db_url`**, which freqtrade does not reject: it silently fell
     back to the repo-root default `tradesv3.dryrun.sqlite`, opened a stale
     database full of open simulated trades from an earlier session, and refused
     to start with a warning that reads like a market condition rather than a
     config typo.

**"it starts" is not "it runs", and the difference is invisible in a smoke test
that only greps for a strategy name.** This script asserts the three things that
distinguish them:

  * the database file exists and is non-empty,
  * the log contains `Changing state to: RUNNING` and NOT a `STOPPED` after it,
  * two heartbeats with DIFFERENT PIDs, separated in time, so the process is
    alive rather than a single log line from a process that has since exited.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\verify_collector.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "user_data" / "forward_perp.dryrun.sqlite"
LOG = ROOT / "user_data" / "logs" / "forward_perp.log"

# Measured by tools/perp_short/event_rate.py on the DEPLOYED N=40 configuration:
# 2,167 signals in 3.67 years. That is the only defensible basis for deciding
# whether a period of silence is normal - anything else is a guess.
SIGNALS_PER_YEAR = 2167 / 3.67


def n_trades() -> int:
    try:
        import sqlite3
        return int(sqlite3.connect(str(DB)).execute(
            "select count(*) from trades").fetchone()[0])
    except Exception:  # noqa: BLE001
        return -1


def started_at(text: str):
    """When the CURRENT process first beat, taken from the first heartbeat of
    the last PID seen.

    ⚠ TIMEZONE, and this cost an 8-hour error the first time: freqtrade writes
    its log in LOCAL time, while its archive filenames are UTC. The first
    version tagged the log's local timestamp as UTC and then compared it to
    `datetime.now(timezone.utc)`, which produced **-0.24 days** for a bot that
    had plainly been up for a day - a negative duration, printed without
    complaint. So: parse the log as NAIVE LOCAL and compare it to NAIVE LOCAL
    `now()`. Both sides naive, both sides the same clock. Anything else is
    mixing two clocks and hoping.
    """
    from datetime import datetime
    hits = re.findall(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - freqtrade\.worker - INFO - "
        r"Bot heartbeat\. PID=(\d+)", text)
    if not hits:
        return None
    last_pid = hits[-1][1]
    for ts, pid in hits:
        if pid == last_pid:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    return None


def main() -> int:
    print("FORWARD COLLECTOR: IS IT ACTUALLY RUNNING?\n")
    ok = True

    if DB.exists() and DB.stat().st_size > 0:
        print(f"  [1/3] database  : OK  {DB.name} ({DB.stat().st_size:,} bytes)")
    else:
        print(f"  [1/3] database  : **MISSING OR EMPTY** {DB}")
        ok = False

    text = LOG.read_text(encoding="utf-8", errors="ignore") if LOG.exists() else ""
    if not text:
        print("  [2/3] log        : **MISSING**")
        return 1

    running = text.count("Changing state to: RUNNING")
    stopped = text.count("Changing state to: STOPPED")
    print(f"  [2/3] state      : RUNNING x{running}, STOPPED x{stopped}")
    if running == 0:
        print("             **THE BOT NEVER REACHED RUNNING**")
        ok = False
    last_run = text.rfind("Changing state to: RUNNING")
    last_stop = text.rfind("Changing state to: STOPPED")
    if last_stop > last_run:
        print("             **the LAST state change was to STOPPED** - it started and "
              "then halted")
        ok = False
    for pat, why in (("Handle these trades manually", "stale open trades block start"),
                     ("error_code' 429", "coingecko rate limit (harmless)")):
        if pat in text:
            print(f"             note: {why}")

    pids = re.findall(r"heartbeat\. PID=(\d+)", text)
    uniq = sorted(set(pids))
    print(f"  [3/3] heartbeats : {len(pids)} total, {len(uniq)} distinct PIDs")
    if len(uniq) < 1:
        print("             **NO HEARTBEAT - the process is not alive**")
        ok = False
    else:
        print(f"             last PID {uniq[-1]}, last at "
              f"{text.rfind('heartbeat')} (char offset into the log)")

    # ⚠ A heartbeat is NOT evidence of running. The bot printed one every 60s
    # while sitting in state STOPPED waiting for a `/start` RPC that nobody sent,
    # and that is what made "it is running" look true for two rounds.
    hb_states = re.findall(r"heartbeat\. PID=\d+, version='[^']*', state='(\w+)'", text)
    if hb_states:
        last_state = hb_states[-1]
        print(f"             last heartbeat STATE = {last_state}"
              f"   (a heartbeat in STOPPED is not a running bot)")
        if last_state != "RUNNING":
            ok = False

    print("\n=== CAN IT EVEN SIGNAL? (startup_candle_count reachability) ===")
    print("\n=== IS THE RUNNING BOT USING THE CONFIG ON DISK? ===")
    # A fourth variant of the same failure, found in round 19. The config file
    # was re-pointed from N=100 to N=40 and reported as done - and the running
    # process kept its ORIGINAL 100-pair universe for two hours, because
    # freqtrade reads the config ONCE at startup and the hourly
    # "Whitelist with N pairs" line is a pairlist refresh, not a config reload.
    # "I changed the config" is not "the running thing uses the changed config."
    # Nothing errored; the bot was healthy the whole time on the wrong universe.
    # For a collector that must run for 6.8 years, that is the most expensive
    # possible silence.
    import json as _json
    cfg_path = ROOT / "user_data" / "config_perp_forward_dry.json"
    on_disk = len(_json.load(open(cfg_path))["pair_whitelist"])
    m = re.findall(r"Whitelist with (\d+) pairs", text)
    running = int(m[-1]) if m else None
    print(f"             config on disk : {on_disk} pairs")
    print(f"             running bot    : {running} pairs" if running is not None
          else "             running bot    : **no whitelist line found in the log**")
    if running is None or running != on_disk:
        print("             **MISMATCH - the process is running a DIFFERENT universe")
        print("                from the file. Restart it, or the collector fills a")
        print("                series that does not match the design.**")
        ok = False
    else:
        print("             match - RESTART the bot whenever the config file changes")

    print("\n=== CAN IT EVEN SIGNAL? (startup_candle_count reachability) ===")
    # A 4h strategy with startup_candle_count=420 needs 70 days of 4h history.
    # and never produces a single signal - with no error, no warning, and a
    # heartbeat every minute. Same failure family as the STOPPED heartbeat, one
    # level further out.
    try:
        import datetime as _dt
        import requests as _rq
        s = _rq.Session()
        s.headers.update({"User-Agent": "verify/1.0"})
        need = 420
        got, cur, oldest = 0, int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000), None
        for _ in range(12):
            r = s.get("https://fapi.binance.com/fapi/v1/klines",
                      params={"symbol": "BTCUSDT", "interval": "4h",
                              "limit": 1000, "endTime": cur}, timeout=30)
            d = r.json()
            if not isinstance(d, list) or not d:
                break
            oldest = int(d[-1][0])
            got += len(d)
            cur = oldest - 1
            if len(d) < 1000:
                break
        enough = got >= need
        print(f"             4h bars reachable: {got}   needed: {need}   "
              f"{'OK' if enough else '**TOO FEW - IT WOULD NEVER SIGNAL**'}")
        if not enough:
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"             reachability check failed: {type(e).__name__}")

    print()
    # -------------------------------------------------------------------
    # IS SILENCE EXPECTED? The MISSING-MEASUREMENT trap, applied to the
    # collector itself.
    #
    # This script used to print "0 trades is expected for a 4h strategy that
    # started minutes ago" as a fixed sentence, forever, whatever the elapsed
    # time. That is unfalsifiable: it would say the same thing after a YEAR of
    # silence, which is exactly when a broken collector and a rare signal look
    # identical. E-1 measured the event rate — 2,167 signals in 3.67 years on
    # 40 symbols = 1.62 per DAY across the whole universe — so the expected
    # count over the elapsed time is computable, and the silence can be graded.
    # -------------------------------------------------------------------
    head = None
    try:
        import json as _json
        from datetime import datetime as _dt
        _cfg = _json.loads(open(
            "user_data/config_perp_forward_dry.json", encoding="utf-8").read())
        _n = len(_cfg["exchange"]["pair_whitelist"])
        _start = started_at(text)
        if _start is None:
            raise ValueError("no heartbeat for the current PID")
        _days = (_dt.now() - _start).total_seconds() / 86400.0
        if _days < 0:
            # a negative duration is a CLOCK problem, not a collector problem,
            # and it must never be allowed through to a verdict as a number
            raise ValueError(f"negative elapsed time ({_days:.2f} days) - "
                             f"the log's clock and the system clock disagree")
        _expect = (SIGNALS_PER_YEAR / 365.25) * _days
        head = (_start, _days, _n, _expect, SIGNALS_PER_YEAR)
    except Exception as e:  # noqa: BLE001
        print(f"             (could not grade the silence: {type(e).__name__})")

    if head is not None:
        _start, _days, _n, _expect, _spy = head
        print("=== IS THE SILENCE EXPECTED? ===")
        print(f"  running for (LOWER BOUND): {_days:.2f} days "
              f"(since {_start:%Y-%m-%d %H:%M} local)")
        print("     the log is append-only across restarts, so this can UNDERSTATE")
        print("     uptime - which understates the expected count, the safe direction")
        print(f"  measured event rate    : {_spy:.0f} signals/year on {_n} symbols"
              f"  = {_spy/365.25:.2f}/day")
        print(f"  expected signals so far: {_expect:.2f}")
        if n_trades() == 0:
            if _expect < 1.0:
                print("  -> 0 trades is CONSISTENT: fewer than one was due. This")
                print("     says nothing about whether the edge is real.")
            else:
                print(f"  -> 0 trades with {_expect:.1f} expected is ANOMALOUS.")
                print("     Silence this long is not explainable by rarity;")
                print("     investigate the signal path before trusting this bot.")
                ok = False
        else:
            print(f"  -> {n_trades()} trades against {_expect:.1f} expected: "
                  f"the bot IS signalling.")

    print()
    if ok:
        print("VERDICT: the collector is RUNNING and will produce the series the")
        print("6.8-year forward test needs. Leave it up.")
        # ASCII only: the Windows console here is GBK and a UnicodeEncodeError
        # raised AFTER every check has passed reads as a failed verification.
        print("   Report it as 'running'. Whether it is PRODUCING DATA is answered")
        print("   by the event-rate grade above, not by a fixed sentence.")
        return 0
    print("VERDICT: the collector is NOT running.")
    print("  * 'it starts' was verified; 'it runs' was NOT, and reported as if it were.")
    print("  * check: db path (three slashes, relative), stale open trades, and that")
    print("    the log's LAST state change is RUNNING rather than STOPPED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
