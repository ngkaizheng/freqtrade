"""Forward collector for the N-ladder short timing book.

WHY THIS IS THE HONEST CLOSING ACTION
-------------------------------------
Nine rounds produced a lead that no backtest can settle:
- N=50 on the most liquid 50 of 515 Binance USD-M perps: **+89.9%** at measured
  COVID costs, CAGR 20.5%, Sharpe 0.67, maxDD 31.5%, 3 of 4 calendar years positive
- the signal is **timing, not stock-picking**: market-neutralised excess is
  NEGATIVE at every rung that clears t>=2.0
- the rung is **window-dependent** (development picks 25, OOS picks 40, the full
  sample picked 50)
- OOS under the strictest dependence treatment is **t = 0.03**
- a forward test at t>=2.0 with IAT correction needs **6.8 years** at 250
  trades/year (`forward_power.py`)

`RESEARCH_GOAL.md` §2.F.3 says a dry-run's duration comes from a preregistered
power calculation, not from "run it a few weeks". The power number is 6.8 years
for the strict test and 2.7 for the naive one. **That is what this collector is
for: it costs nothing, it trades nothing, and it produces exactly the series the
test needs — over however many years the user is willing to let it run.**

IT RECORDS THE FIELD WHOSE ABSENCE CAUSED THE 10TH BUG
------------------------------------------------------
`ladder_shape.py` and `walkforward.py` both reported `t_by_ts = nan` for two
rounds, because `df.set_index(idx).groupby(idx)` aligns a RangeIndex-keyed
Series to a timestamp-indexed frame and produces nothing. The by-timestamp t is
the statistic this project uses for every verdict. **So the collector writes
`panel_fwd_7d` and `n_coincident` next to every closed trade**, and the analysis
then never has to reconstruct a global series it might silently get wrong.

IT IS A DRY-RUN. NO CREDENTIALS, NO ORDERS, NO FUNDS.
--------------------------------------------------------
`config_perp_forward_dry.json` is a SEPARATE config with its own database, its
own log, and `dry_run: true`. Enabling real trading requires a separate,
explicit user authorisation that this file does not and cannot grant.

Run:
    freqtrade trade --config user_data\\config_perp_forward_dry.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "user_data" / "config_perp_forward_dry.json"
BASE = ROOT / "user_data" / "config_perp_short_deploy.json"

# The reproducible statement from the ladder is a RANGE, not a rung: N=25..300 is
# positive out of sample and only N=515 is not, and three different windows picked
# three different cells. The mid of the range is the honest operating point.
N = 100


def main() -> int:
    liq = pd.read_csv(ROOT / "user_data" / "perp_short_out" / "liquidity_515.csv")
    sub = liq.head(N)
    pairs = [s[:-4] + "/USDT:USDT" for s in sub["symbol"]]
    a = int((sub["cohort"] == "A").sum())

    cfg = json.load(open(BASE))
    cfg["pair_whitelist"] = pairs
    cfg["exchange"] = dict(cfg["exchange"])
    cfg["exchange"]["pair_whitelist"] = pairs
    cfg["exchange"]["key"] = ""
    cfg["exchange"]["secret"] = ""
    cfg["dry_run"] = True
    cfg["dry_run_wallet"] = 10_000
    cfg["max_open_trades"] = 24
    cfg["risk_per_trade"] = 0.005          # 0.5% - the risk_sweep row that
    #                                         halves the drawdown of the 1% curve
    cfg["atr_stop"] = 4.0
    cfg["breaker_max_dd"] = 0.20
    cfg["breaker_cooldown_bars"] = 42
    cfg["datadir"] = str(ROOT / "user_data" / "data" / "wide526").replace("\\", "\\\\")
    # ⚠⚠ THE KEY IS `db_url`, NOT `database_url`. freqtrade does not reject
    # unknown configuration keys - it silently falls back to the default, which
    # is `sqlite:///tradesv3.dryrun.sqlite` at the REPO ROOT
    # (`configuration.py:153`, `constants.py:23`). So a `database_url` key is
    # accepted, produces no warning, and the bot opens a stale database full of
    # open simulated trades from an earlier session, which then BLOCKS the start
    # with a warning that reads like a market condition rather than a typo.
    # Three slashes, relative path.
    cfg["db_url"] = "sqlite:///user_data/forward_perp.dryrun.sqlite"
    # Every research config sets this EXPLICITLY even though the class defines
    # it. `collector_fidelity.py` flagged it missing here, and although the
    # class default (4h) is correct today, relying on a class default for the
    # single parameter that defines every signal is the same "it happens to hold"
    # pattern this project has now been bitten by repeatedly. Set it.
    cfg["timeframe"] = "4h"
    # ⚠ Without this the bot starts, loads the strategy, creates its database,
    # prints heartbeats - and sits in state STOPPED waiting for a `/start` RPC
    # that nobody is going to send. **No error, no warning, and a heartbeat every
    # minute that looks exactly like a healthy running bot.** That is the most
    # convincing way yet to report "it is running" while it is not, and it is what
    # happened here until the log's state field was read.
    cfg["initial_state"] = "running"
    cfg["logfile"] = "user_data/logs/forward_perp.log"
    cfg["exportfilename"] = "user_data/forward_exports"
    json.dump(cfg, open(OUT, "w"), indent=2)

    sub[["symbol", "cohort", "med_quote"]].to_csv(
        ROOT / "user_data" / "perp_short_out" / "forward_universe.csv", index=False)
    # the universe travels with the config so a rebuild cannot silently revert N
    if not cfg["pair_whitelist"][:3] == [
            "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
        print("   NOTE: run tools/perp_short/repoint_collector.py to re-apply the "
              "N=40 liquidity-ordered universe chosen in PICK_THE_RUNG.")
    print(f"forward dry-run config: {OUT}")
    print(f"   universe   : top {N} of 515 by median quote volume "
          f"(liquidity-ORDERED, on purpose - see the 8th trap)")
    print(f"   cohort A   : {a}/{len(sub)} = {a/len(sub)*100:.1f}%")
    print(f"   risk/trade : {cfg['risk_per_trade']*100:.2f}%  "
          f"(portfolio risk budget = {cfg['risk_per_trade']*cfg['max_open_trades']*100:.1f}%)")
    print(f"   dry_run    : {cfg['dry_run']}   key set: {cfg['exchange']['key']!r}")
    print(f"   db_url     : {cfg['db_url']}   (the key is db_url, NOT database_url)")
    print()
    # ASCII only - the Windows console here is GBK and a UnicodeEncodeError
    # raised AFTER the config is written reads as a failed build.
    print("   NOTE: STARTING IT IS NOT THE SAME AS IT RUNNING. The first version of")
    print("      this collector was reported as 'running' after a 100-second")
    print("      start-up smoke test that was then killed - and it would not have")
    print("      run anyway, because a database path with four slashes is not a")
    print("      path freqtrade can open, and it refused to start with 2 stale")
    print("      simulated open trades. **'it starts' is not 'it runs'.** After")
    print("      launching, check: the db file exists, the log reaches")
    print("      'Changing state to: RUNNING', and heartbeat PIDs keep advancing.")
    print("      tools/perp_short/verify_collector.py does exactly that.")
    print()
    print("   to run:  .venv\\Scripts\\python.exe -m freqtrade trade "
          "--config user_data\\config_perp_forward_dry.json")
    print()
    # ASCII only: the Windows console here is GBK and a UnicodeEncodeError in a
    # print AFTER the config is written reads as a failed build.
    print("   NOTE: the universe is ORDERED BY LIQUIDITY. With 24 slots, the")
    print("     whitelist order decides who gets filled - the same 515 pairs")
    print("     ordered alphabetically returned +4.14%, ordered by liquidity")
    print("     -17.52%. That is not a detail; it is a rule, and it is frozen here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
