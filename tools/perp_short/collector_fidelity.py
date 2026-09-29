"""Does the collector's CONFIG match the strategy that was actually validated?

This exists because the collector reads `atr_stop` from the CONFIG
(`PerpShort4hStop._anchor_stop_price` -> `self.config.get("atr_stop",
self.atr_stop)`) while the class default is **1.5**. The research was done at
**4.0**. A collector launched without that key would be collecting data for a
DIFFERENT STRATEGY than the one every result in this repository describes -
and nothing would say so, because the config is a file nobody re-reads and a
1.5xATR book is not obviously wrong from the outside.

So the fidelity check is not "is the config valid". It is: **does every key that
changes the strategy's BEHAVIOUR carry the value the research used?**

Run:
    .venv\\Scripts\\python.exe tools\\perp_short\\collector_fidelity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "user_data" / "config_perp_forward_dry.json"

# (key, expected, why it changes the strategy's behaviour, not just its sizing)
EXPECTED = [
    ("strategy", "PerpShort4hDeploy", "which strategy class runs at all"),
    ("strategy_path", "user_data/strategies", "where that class is found"),
    ("initial_state", "running", "without it the bot heartbeats in STOPPED"),
    ("dry_run", True, "the collector must not place real orders"),
    ("timeframe", "4h", "a different bar changes every signal"),
    ("atr_stop", 4.0,
     "READ FROM THE CONFIG by PerpShort4hStop; the class default is 1.5, so a "
     "missing key silently collects a DIFFERENT STRATEGY from the one this "
     "repository measured"),
    ("risk_per_trade", 0.005,
     "0.5% - the 0.5% setting is what ROLLING_RISK measured, and 47% vs 17.3% "
     "max drawdown is the difference between this and 1%"),
    ("max_open_trades", 24, "slot count; the whitelist ORDER interacts with it"),
    ("breaker_max_dd", 0.20, "the circuit breaker is inert without it"),
    ("breaker_cooldown_bars", 42, "how long the breaker halts"),
    ("db_url", "sqlite:///user_data/forward_perp.dryrun.sqlite",
     "the key is db_url, not database_url; the wrong key opens a stale DB"),
]


def main() -> int:
    cfg = json.load(open(CFG))
    print("COLLECTOR FIDELITY: is the config the one the research measured?\n")
    print(f"  {CFG}\n")
    bad = 0
    for key, want, why in EXPECTED:
        got = cfg.get(key, "<MISSING>")
        ok = (got == want) or (isinstance(want, float)
                               and isinstance(got, (int, float))
                               and abs(got - want) < 1e-9)
        mark = "OK  " if ok else "FAIL"
        if not ok:
            bad += 1
        print(f"  [{mark}] {key:<22} = {str(got):<42} expected {want}")
        if not ok:
            print(f"         -> {why}")

    wl = cfg.get("exchange", {}).get("pair_whitelist", [])
    top = cfg.get("pair_whitelist", [])
    print(f"\n  whitelist length      : {len(wl)} (whitelist {len(top)}, "
          f"they {'match' if wl == top else 'DO NOT MATCH'})")
    if wl != top:
        bad += 1
        print("         -> exchange.pair_whitelist is the one freqtrade uses; a "
              "mismatch means the strategy ran on a different universe")
    if wl and wl[:3] != ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
        print("  [warn] the universe does not start with the majors in liquidity "
              "rank order - with 24 slots the ORDER decides who gets filled")

    print()
    if bad:
        print(f"VERDICT: {bad} MISMATCH(ES). The collector would be running "
              f"something other than\n         the strategy this repository "
              f"measured. Fix before trusting any data it produces.")
        return 1
    print("VERDICT: the config matches the validated strategy. Data this "
          "collector\n         produces describes the book in "
          "HOW_TO_RUN_2026-09-29.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
