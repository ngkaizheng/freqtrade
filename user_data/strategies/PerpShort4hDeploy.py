"""DEPLOYABLE version: the 4.0xATR short book plus a drawdown circuit breaker.

WHAT THIS IS, PLAINLY
---------------------
A runnable configuration of a signal that is NOT significance-validated. The
user was told the evidence and chose to trade it anyway; this file is the
consequence of that choice, and it exists so the choice is a clean one:

  * `PerpShort4hStop` (the frozen baseline) is UNCHANGED and untouched. This
    file inherits from it. Diff the two and the only difference is the breaker.
  * The ONLY addition: after `breaker_max_dd` of peak-to-trough equity loss,
    new entries are refused for `breaker_cooldown_bars` 4h bars.

WHY THE BREAKER IS THE RIGHT INSTRUMENT
---------------------------------------
The panel result measured what actually causes the damage: **72% of trades
share a timestamp with another, and the cross-sectional mean has beta = 1.000.**
This book fires on many names AT ONCE and they are not independent. Measured
peak concurrency on the 4h run: **18 positions open simultaneously**, median 7.

The engine fills every stop exactly at the stop price, so a backtest cannot
show what a cascade costs. The stress figure from `tools/perp_short/risk_sweep.py`:
at 1% risk per trade, all 18 stopping and each gapping 50% past the stop costs
about **27% of the account in one moment**. A breaker cannot prevent that moment,
but it prevents the second, the third and the fourth - which is the difference
between a bad quarter and a blown account.

WHY IT IS BUILT ON `confirm_trade_entry`
----------------------------------------
An earlier draft tried to do this inside `populate_indicators` /
`populate_entry_trend`, which is **wrong for backtesting**: those run ONCE per
pair over the whole frame, not once per bar, so a stateful breaker never advances
and the backtest silently measures the un-broken strategy while the file claims
otherwise. `confirm_trade_entry` is called on every entry attempt and is handed
`current_time`, which is what the cooldown needs. It is the only hook that both
runs per-event and carries a usable clock.

WHAT THE BREAKER IS NOT
-----------------------
**It is tuned in-sample.** `breaker_max_dd` was chosen by looking at 2023-2026
drawdowns on the same data it is then judged on. That is the compromise the user
authorised, and it is stated here so nobody mistakes it for a validated control.

Run:
    freqtrade backtesting --config user_data\\config_perp_short_deploy.json \\
        --datadir user_data\\data\\wide104 --strategy-path user_data\\strategies \\
        --strategy PerpShort4hDeploy
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

import numpy as np

# Resolve the lineage directories from THIS FILE's location, not from the process
# working directory. The previous form was two relative `sys.path.insert` calls,
# which meant the bot started only if `freqtrade` was launched from the repo root:
# launch it from anywhere else and `from PerpShort4hStop import ...` dies with a
# bare ImportError that looks like a missing strategy. The deployed config is
# otherwise directory-independent, so this is the one thing in the file that was.
# Behaviour when launched from the repo root is unchanged - the resolved paths are
# the same two directories.
_HERE = os.path.dirname(os.path.abspath(__file__))          # .../user_data/strategies
for _d in (os.path.join(os.path.dirname(_HERE), "strategies_frontier"), _HERE):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from freqtrade.persistence import Trade  # noqa: E402
from freqtrade.strategy import IStrategy  # noqa: E402

from PerpShort4hStop import PerpShort4hStop  # noqa: E402

import logging  # noqa: E402

logger = logging.getLogger(__name__)

BARS_4H = timedelta(hours=4)


class PerpShort4hDeploy(PerpShort4hStop):
    """Frozen 4.0xATR short rule + a drawdown circuit breaker."""

    # an int is False and a bool is an int, so these are read as floats and
    # range-checked rather than trusted for truthiness - a `0` here would read
    # as "breaker off" and a `1.0` as "breaker always on", and neither is what
    # anyone writing the key intends.
    @property
    def breaker_max_dd(self) -> float:
        v = float(self.config.get("breaker_max_dd", 0.25))
        if not (0.0 < v < 1.0):
            raise ValueError(
                f"breaker_max_dd must be a fraction strictly inside (0,1); got "
                f"{v}. 0 reads as 'off' and 1.0 as 'always on'.")
        return v

    @property
    def breaker_cooldown_bars(self) -> int:
        return int(self.config.get("breaker_cooldown_bars", 42))

    def bot_loop_start(self, *args, **kwargs):
        # deliberately does NOT touch the breaker state - see _init_state for
        # why resetting it here is the bug this file was written around.
        return None

    def _init_state(self):
        """Initialise the breaker's state ONCE, lazily.

        ⚠ THE FIRST VERSION USED `bot_loop_start` FOR THIS AND IT WAS THE BUG.
        `bot_loop_start` is called more than once during a backtest (it is
        reached per pair as the data is prepared), so every call reset
        `_peak_equity` to None. The peak therefore tracked the CURRENT equity,
        the drawdown was identically 0.0000 at every single entry, and the
        breaker **never fired once across a run with a 43.9% drawdown** - while
        the backtest printed an entirely normal equity curve and a +78.61%
        headline.

        That is the most dangerous version of this repo's most common failure:
        a risk control that fails OPEN, silently, inside a result that looks
        perfect. It is recorded in `RESEARCH_STATE.md` as a cross-cutting trap.
        Lazy init from the first `confirm_trade_entry` cannot be re-entered.
        """
        if not hasattr(self, "_breaker_ready"):
            self._peak_equity = None
            self._halt_until = None
            self.breaker_trips = 0
            self._calls = 0
            self._breaker_ready = True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time,
                           **kwargs) -> bool:
        """Refuse new entries while the breaker is halted.

        Runs on every entry attempt, which is the only reason this works in
        backtesting. Returning False drops the signal; it is NOT a silent
        no-op, and the trip count is exposed so a run can assert on it.

        ⚠ THE FIRST VERSION OF THIS FUNCTION WAS A SILENT NO-OP AND THE BACKTEST
        DID NOT NOTICE. The first deploy run produced **1,140 trades, byte for
        byte the same as the un-broken arm**, and a +36% change in return that
        had to be explained as tuning - when the truth was that the breaker had
        never fired once. The cause: backtesting wraps this call in
        `strategy_safe_wrapper(self.strategy.confirm_trade_entry,
        default_retval=True)` (backtesting.py:1191), **so ANY exception raised
        here is swallowed and the entry is allowed through.** A risk control that
        fails open and reports nothing is worse than no risk control, so the
        breaker below logs its own first trip, and the runbook requires checking
        `breaker_trips` rather than assuming the breaker did something.
        """
        try:
            self._init_state()
            eq = self.wallets.get_total(self.config["stake_currency"])
            if eq is None or eq <= 0 or not np.isfinite(eq):
                raise ValueError(f"wallet total is {eq!r}")
            eq = float(eq)
            self._peak_equity = eq if self._peak_equity is None else max(
                self._peak_equity, eq)
            peak = self._peak_equity
            dd = 1.0 - (eq / peak) if peak > 0 else 0.0
            self._calls += 1
            halt = self._halt_until
            if halt is not None and current_time < halt:
                return False
            if dd >= self.breaker_max_dd and halt is None:
                self._halt_until = current_time + self.breaker_cooldown_bars * BARS_4H
                self.breaker_trips = getattr(self, "breaker_trips", 0) + 1
                logger.warning(
                    f"PERP DEPLOY BREAKER TRIPPED #{self.breaker_trips} at "
                    f"{current_time}: equity {eq:.2f} vs peak {peak:.2f} "
                    f"(dd {dd:.2%} >= {self.breaker_max_dd:.2%}), halting entries "
                    f"for {self.breaker_cooldown_bars} bars. "
                    f"CHECK breaker_trips IS NON-ZERO - a silent no-op here "
                    f"would be invisible.")
                return False
            return True
        except Exception:
            # fail LOUD, then behave as freqtrade would. Raising is pointless -
            # the wrapper swallows it - so at least make it visible.
            logger.exception("PERP DEPLOY BREAKER RAISED; entry allowed through. "
                             "The breaker is NOT working.")
            return True
