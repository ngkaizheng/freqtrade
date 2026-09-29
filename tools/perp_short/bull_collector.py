"""Start (if needed) and VERIFY the long book's forward collector.

WHY A SEPARATE FILE
-------------------
`restart_collector.py` exists for the short book and does the right thing. Editing it to take a
config argument would put the PRIMARY artefact's tooling at risk for the convenience of the new
one, and this repository has already been burned by exactly that twice - `run_capped.ps1` carries
the comment "SEPARATE FILE, AGAIN. Two agents rewriting one script is how a run gets
half-applied". So: a second file, with a deliberately disjoint process match.

⚠ THE PROCESS MATCH IS `config_perp_bull_dry`. It is NOT a substring of `config_perp_forward_dry`,
so this can never kill the short book's collector. A match of "perp" or "dry" would have.

THE THREE CHECKS, AND WHY EACH ONE EXISTS
-----------------------------------------
1. **the process is running** - the weakest check, and the one people stop at.
2. **the last state change is RUNNING and the last heartbeat CARRIES state RUNNING.** This is the
   one that matters. A missing `initial_state` produces a process that heartbeats every 60
   seconds, writes a log, holds an open database connection, and sits in state **STOPPED** - it
   produces no error and no number and looks perfectly healthy. That failure was reported as
   "running" twice in this project's history, and it was missing from the long config until
   `bull_config_gate.py` found it on 2026-09-30.
3. **the running process is using the config on disk.** A long-lived process reads its config
   ONCE. After any edit the file and the process disagree silently.

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\bull_collector.py
"""

from __future__ import annotations

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_bull_dry.json"
DB = ROOT / "user_data" / "bull_perp.dryrun.sqlite"
OUT = ROOT / "user_data" / "logs" / "bull_out_restart.log"
ERR = ROOT / "user_data" / "logs" / "bull_err_restart.log"
LOG = ROOT / "user_data" / "logs" / "bull_perp.log"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
MATCH = "config_perp_bull_dry"
# 40 names, measured by `event_rate.py` for the SHORT book on the same universe. The long book
# mirrors the same signal, so the order of magnitude is the right one to sanity-check "0 trades"
# against; it is an expectation, not a guarantee.
EXPECTED_PER_DAY = 1.62

fails: list[str] = []
warns: list[str] = []


def running_pids() -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Select-Object -ExpandProperty ProcessId"],
        capture_output=True, text=True, timeout=90)
    pids = []
    for line in out.stdout.split():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def cmdline(pid: int) -> str:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
        capture_output=True, text=True, timeout=60).stdout


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    n = len(cfg["exchange"]["pair_whitelist"])
    print("=" * 78)
    print(f"config on disk : {n} pairs, atr_stop={cfg.get('atr_stop')}, "
          f"chandelier={cfg.get('chandelier_atr')}, exit_mode={cfg.get('exit_mode')}, "
          f"risk={cfg.get('risk_per_trade')}")
    print(f"initial_state  : {cfg.get('initial_state')!r}   "
          f"(absent = the process heartbeats in STOPPED and produces nothing)")
    print(f"db_url         : {cfg.get('db_url')}")
    print("=" * 78)

    if cfg.get("initial_state") != "running":
        fails.append("the config has no initial_state=running - do not start this")
        print("  [FAIL] refusing to start a collector that would heartbeat in STOPPED")
        return 1

    trades = 0
    if DB.exists():
        try:
            trades = sqlite3.connect(str(DB)).execute(
                "select count(*) from trades").fetchone()[0]
        except Exception:                                       # noqa: BLE001
            trades = -1
    print(f"trades already in {DB.name}: {trades}")

    # ---- is it already running? -------------------------------------------
    mine, found = os.getpid(), []
    for pid in running_pids():
        if pid == mine:
            continue
        try:
            if MATCH in cmdline(pid):
                found.append(pid)
        except Exception:                                       # noqa: BLE001
            continue
    print(f"running {MATCH} process(es): {found or 'none'}")

    if not found:
        for pid in running_pids():
            try:
                if MATCH in cmdline(pid):
                    os.kill(pid, signal.SIGTERM)
            except Exception:                                   # noqa: BLE001
                continue
        time.sleep(4)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        p = subprocess.Popen([PY, "-m", "freqtrade", "trade", "--config", str(CFG)],
                             cwd=str(ROOT), stdout=open(OUT, "w"), stderr=open(ERR, "w"))
        print(f"started PID {p.pid}; waiting 150s for it to settle\n")
        time.sleep(150)
    else:
        print("already running - not restarting (a restart would mix configs if trades exist)\n")

    # ---- the three checks --------------------------------------------------
    print("-" * 78)
    print("1. PROCESS")
    pids = [pid for pid in running_pids() if MATCH in cmdline(pid)]
    if pids:
        print(f"  [PASS] running: {pids}")
    else:
        fails.append("no collector process")
        print("  [FAIL] not running")

    print("2. THE DATABASE AND THE STATE  (the check that actually matters)")
    if not DB.exists():
        fails.append(f"{DB.name} does not exist - the process never opened its database")
        print(f"  [FAIL] {DB.name} missing")
    else:
        print(f"  [PASS] {DB.name} exists")

    txt = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
    if not txt:
        fails.append("no log - the process produced nothing at all")
        print("  [FAIL] no log")
    else:
        # freqtrade logs `Changing state to: RUNNING` and then heartbeats as
        #   Bot heartbeat. PID=..., version='...', state='RUNNING'
        # The check that matters is the LAST HEARTBEAT'S OWN state, not whether the string
        # RUNNING appears anywhere: a bot can transition to RUNNING and then sit in STOPPED.
        # The first version of this script matched `State\.(\w+)` and matched nothing at all,
        # reporting a perfectly healthy collector as FAILING - the mirror image of the bug it
        # exists to catch, and a reminder that a gate which cannot parse reality is worse
        # than no gate, because it is believed.
        transitions = re.findall(r"Changing state to:\s*(\w+)", txt)
        beats = re.findall(r"Bot heartbeat\.[^\n]*?state='(\w+)'", txt)
        last = transitions[-1] if transitions else None
        last_beat = beats[-1] if beats else None
        print(f"  transitions : {transitions[-5:] or 'none'}   last = {last}")
        print(f"  heartbeats  : {len(beats)}   last heartbeat's own state = {last_beat}")
        if last_beat is None:
            fails.append("no heartbeat in the log - the process has not proven it is still alive")
            print("  [FAIL] no heartbeat")
        elif last_beat != "RUNNING":
            fails.append(f"the last heartbeat carries state={last_beat!r}, not RUNNING - the "
                         f"initial_state failure: alive, healthy-looking, producing nothing")
            print(f"  [FAIL] last heartbeat state is {last_beat}, not RUNNING")
        else:
            print("  [PASS] the last heartbeat CARRIES state=RUNNING")
        if last is not None and last != "RUNNING" and last_beat == "RUNNING":
            warns.append(f"the last state TRANSITION was {last} though the last heartbeat is "
                         f"RUNNING - odd, worth a look")

    print("3. THE RUNNING PROCESS USES THE CONFIG ON DISK")
    if pids:
        cl = cmdline(pids[0])
        if CFG.name in cl:
            print(f"  [PASS] command line references {CFG.name}")
        else:
            fails.append("the running process was NOT started with this config")
            print(f"  [FAIL] command line does not reference {CFG.name}: {cl[:120]}")
    wl = re.findall(r"Whitelist with (\d+) pairs", txt)
    if wl:
        ok = int(wl[-1]) == n
        print(f"  [{'PASS' if ok else 'FAIL'}] the process loaded {wl[-1]} pairs, "
              f"the config has {n}")
        if not ok:
            fails.append(f"the process loaded {wl[-1]} pairs, the config has {n} - the "
                         f"process is running a STALE config")
    else:
        warns.append("could not confirm the loaded pair count from the log")

    print("-" * 78)
    if fails:
        print("NOTES, NOT FAILURES:" if not warns else "")
        for w in warns:
            print(f"    - {w}")
        print(f"\n{len(fails)} FAILURE(S):")
        for f in fails:
            print("    x", f)
        return 1
    print(f"trades: {trades}.")
    if trades == 0:
        print(f"  That is NORMAL, not evidence of failure: at the measured event rate of")
        print(f"  {EXPECTED_PER_DAY}/day for 40 names, fewer than 0.14 trades is the expected")
        print(f"  count in the first hours. A collector is judged by whether it heartbeats in")
        print(f"  RUNNING, not by whether it has traded yet.")
    print("\n  NOTE WHAT THIS COLLECTOR CANNOT DO. The forward test that would confirm the")
    print("  LONG book needs the same 6.8 years as the short one, and the short book's final")
    print("  holdout was burned on 2026-09-26 - so a long-run confirmation inside this sample")
    print("  is not available at any horizon. This collector starts the series; it does not")
    print("  shorten it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
