"""Restart the forward collector against the CURRENT config, then verify it.

WHY THIS EXISTS
---------------
A running freqtrade reads its config ONCE at startup. The config file has been
corrected twice since the process was launched - once for the N=40 universe
(`PICK_THE_RUNG_2026-09-29.md`) and once for the explicitly-set `timeframe`
(`collector_fidelity.py` flagged it missing). **A process that is still running
with the old values in memory looks completely healthy**: heartbeats, RUNNING
state, no errors, a database file. Nothing in its own output says which config
it loaded.

So the restart has to be an explicit, verified step rather than something that
happens to coincide with a config edit - and it has to happen BEFORE the first
trade is recorded, because after that the data is a mix.

This is the third instance of one family in as many rounds: the collector's
config key (`database_url` vs `db_url`), its start state (`initial_state`), and
now its universe. **A long-lived process holds a snapshot of the configuration,
and nothing about it is observable from the outside.**

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\restart_collector.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"
DB = ROOT / "user_data" / "forward_perp.dryrun.sqlite"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
OUT = ROOT / "user_data" / "logs" / "fwd_out_restart.log"
ERR = ROOT / "user_data" / "logs" / "fwd_err_restart.log"


def main() -> int:
    import json
    import sqlite3

    cfg = json.load(open(CFG))
    n = len(cfg["pair_whitelist"])
    print(f"config on disk : {n} pairs, atr_stop={cfg.get('atr_stop')}, "
          f"risk={cfg.get('risk_per_trade')}, timeframe={cfg.get('timeframe')}, "
          f"db={cfg.get('db_url')}")

    trades = 0
    if DB.exists():
        try:
            trades = sqlite3.connect(str(DB)).execute(
                "select count(*) from trades").fetchone()[0]
        except Exception:
            trades = -1
    print(f"trades recorded so far: {trades}")
    if trades > 0:
        print("REFUSING to restart: trades already exist, so the database would "
              "mix configs.\n         Archive it and start a fresh series "
              "deliberately, or accept the mix knowingly.")
        return 1

    # find and stop any running collector
    me = os.getpid()
    killed = 0
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=60)
        for line in out.stdout.split():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid == me:
                continue
            try:
                cmd = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"(Get-CimInstance Win32_Process -Filter "
                     f"\"ProcessId={pid}\").CommandLine"],
                    capture_output=True, text=True, timeout=30).stdout
                if "config_perp_forward_dry" in cmd:
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
            except Exception:
                continue
    except Exception as e:  # noqa: BLE001
        print(f"process scan failed: {type(e).__name__}")
    print(f"stopped {killed} running collector process(es)")
    time.sleep(6)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([PY, "-m", "freqtrade", "trade", "--config", str(CFG)],
                         cwd=str(ROOT), stdout=open(OUT, "w"), stderr=open(ERR, "w"))
    print(f"started PID {p.pid}; waiting 150s for it to settle\n")
    time.sleep(150)

    r = subprocess.run([PY, str(ROOT / "tools" / "perp_short" / "verify_collector.py")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    print(r.stdout)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
