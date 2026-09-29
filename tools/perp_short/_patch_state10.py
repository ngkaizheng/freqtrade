"""One-off: record the DEPLOYABLE package and the silent-no-op breaker trap.

The breaker trap is the most important entry of the session: a risk control that
failed OPEN, silently, inside a backtest that printed a completely normal equity
curve, and that I nearly shipped. It is the fifth instance of the same family and
the first one that was a RISK CONTROL.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

DEPLOY_ROW = (
    "| **`PerpShort4hDeploy` — THE DELIVERABLE (built after the user accepted a "
    "methodology compromise)** | **2026-09-28 — RUNNABLE, GATED, HONESTLY "
    "LABELLED AS NOT-SIGNIFICANT** | `docs-myself/DEPLOYABLE_4H_SHORT_2026-09-28.md`; "
    "`user_data/strategies/PerpShort4hDeploy.py` (inherits the frozen "
    "`PerpShort4hStop`, which is UNCHANGED, so a diff shows the breaker is the "
    "only addition); `user_data/config_perp_short_deploy.json`; "
    "`tools/perp_short/risk_sweep.py`. **The user was shown the evidence (t = "
    "-0.15, no cross-sectional component, timing only) and chose to trade it "
    "anyway. This is the consequence of that choice, and the compromise is "
    "labelled rather than hidden.** **Numbers on CORRECTED data (the 1h mark "
    "files were shipping without a `date` column - see the trap row below - and "
    "the first runs were on partial data): 1,132 trades, 104 Binance USD-M perps, "
    "2023-03-22 to 2026-08-31, 1x, 1% risk per trade, 24 slots, 4xATR stop, "
    "breaker ON. Engine output **+89.26%, maxDD 23.12%**; measured-cost frontier "
    "**calm +100.6% / cascade +92.1% / volatile +76.2% / COVID (34.9bps) +52.4%**, "
    "CAGR 13.0%, Sharpe 0.50, PF 1.10. Years at COVID: **2023 -40.5%, 2024 "
    "+54.4%, 2025 +70.2%, 2026 -9.5%** - still 2 of 4 negative. Buy&hold on the "
    "same 104 pairs: median **-80.9%**, 16% positive. ⚠ **THE ENGINE'S REPORTED "
    "DRAWDOWN IS OPTIMISTIC**: freqtrade measures it on `free + used` with `used` "
    "at ENTRY value, not marked to market, so it prints 23.12% where the true "
    "equity path gives **47.2%**. Both are shown in the document; believe the "
    "larger one. Gates: stop verification **PASS (355/355 at 4xATR, max error "
    "0.00168%)**, truncation causality **PASS**. Still, in one line: **this is a "
    "leveraged short-TIMING tool with no stock-picking ability, not an alpha "
    "strategy.** |"
)

BREAKER_ROW = (
    "| **A drawdown circuit breaker that fails OPEN, silently, and the backtest "
    "prints a normal curve** (new, cross-cutting, **the 5th instance of this "
    "family and the first one that was a RISK CONTROL**) | **TRAP — shipped in "
    "`PerpShort4hDeploy`, never fired once across a 43.9% drawdown, and looked "
    "perfect** | `confirm_trade_entry` in backtesting is wrapped as "
    "`strategy_safe_wrapper(self.strategy.confirm_trade_entry, "
    "default_retval=True)` (`backtesting.py:1191`) - **any exception inside it is "
    "swallowed and the entry is allowed through**, so a broken risk control does "
    "not even error. Three layers each hid it: (1) **`bot_loop_start` is called "
    "MORE THAN ONCE in a backtest** (it is reached per pair as data is prepared), "
    "so `self._peak_equity = None` ran repeatedly and the peak tracked the "
    "CURRENT equity - the log shows `equity=111250 peak=111250` then "
    "`equity=102072 peak=102072`, so **dd was identically 0.0000 at every entry**; "
    "(2) `if eq is None or eq <= 0: eq = dry_run_wallet` turned 'wallet unreadable' "
    "into 'equity never moves'; (3) the wrapper above swallowed anything raised. "
    "**All three fixes are in the file**: lazy one-shot state init, RAISE instead of "
    "falling back when the wallet is unreadable, and a WARNING on every trip that "
    "says to check `breaker_trips` is non-zero. **The general rule: a control that "
    "silently does nothing is worse than no control, because it buys comfort - and "
    "the only way this was found was that the run produced exactly 1,140 trades, "
    "byte-identical to the un-broken arm, which is not a number a breaker's first "
    "version should ever produce.** |"
)

MARK_ROW = (
    "| **`to_feather()` on a DatetimeIndex drops the `date` COLUMN on read** (new, "
    "cross-cutting) | **TRAP — 104/104 futures mark files were unreadable and the "
    "backtest ran anyway on partial data** | `df.set_index('date').resample('1h')"
    ".to_feather(path)` writes the timestamp as the frame INDEX, and "
    "`read_feather` does not restore the index name. freqtrade's loader then "
    "logged `Unexpected column count 5 - expected 6` for most symbols **and the "
    "backtest continued**, producing a full-length equity curve with an ERROR "
    "line nobody reads. `tools/widepanel/export_full104.py` shipped this way and "
    "every 104-symbol result before the fix was computed on partial data. "
    "**Fix: `.reset_index()` before writing.** **Related and worse: with "
    "`trading_mode: futures`, funding and mark load with `fail_without_data=True` "
    "(`backtesting.py:428,441`) - so a MISSING file crashes loudly, but a "
    "MALFORMED one only logs.** Assert the schema after writing, and count the "
    "files you expect back. |"
)

CHANGE = (
    "| 2026-09-28 | **THE DELIVERABLE BUILT, AND THE MOST DANGEROUS BUG OF THE "
    "SESSION FOUND WHILE BUILDING IT.** `PerpShort4hDeploy` + "
    "`config_perp_short_deploy.json` + `DEPLOYABLE_4H_SHORT_2026-09-28.md`. The "
    "user was shown the evidence and elected to trade a non-significant result; "
    "the compromise is labelled, not hidden. **On corrected data: 1,132 trades, "
    "engine +89.26% / measured-COVID +52.4%, CAGR 13.0%, Sharpe 0.50, PF 1.10, "
    "years 2023 -40.5% / 2024 +54.4% / 2025 +70.2% / 2026 -9.5% (2 of 4 still "
    "negative), against buy&hold median -80.9%. Gates green: 355/355 stops at "
    "4xATR, truncation causality PASS. ⚠ THE ENGINE'S OWN DRAWDOWN IS OPTIMISTIC "
    "because it measures `free + used` with `used` at ENTRY value, not marked to "
    "market: it printed 23.12% where the true equity path is 47.2%.** "
    "*(b) ⚠⚠ **THE BREAKER WAS A SILENT NO-OP AND I ALMOST SHIPPED IT.** The "
    "first version never fired once across a 43.9% drawdown, and the run produced "
    "**exactly 1,140 trades - byte-identical to the un-broken arm - with a normal "
    "+78.61% curve.** Three layers hid it: `bot_loop_start` runs MORE THAN ONCE in "
    "a backtest, so `self._peak_equity = None` reset the peak per pair and **dd "
    "was identically 0.0000 at every single entry** (`equity=111250 peak=111250` "
    "then `equity=102072 peak=102072` in the log); a `dry_run_wallet` fallback "
    "turned 'wallet unreadable' into 'equity never moves'; and "
    "`strategy_safe_wrapper(confirm_trade_entry, default_retval=True)` "
    "(`backtesting.py:1191`) **swallows any exception and allows the entry**. A "
    "risk control that fails open silently is worse than no control because it "
    "buys comfort. Fixed three ways, and the trip counter is now asserted rather "
    "than assumed. **This is the FIFTH instance of AGENTS.md section 3's family in "
    "one session and the first that was a risk control; the first four all "
    "produced a table that looked completely normal, and every one was caught by "
    "an assertion rather than by reading.** *(c) **AND THE DATA WAS BROKEN UNDER "
    "ALL OF IT: 104/104 futures mark files were being written with `to_feather()` "
    "on a DatetimeIndex, which drops the `date` COLUMN on read.** freqtrade logged "
    "`Unexpected column count 5 - expected 6` for most symbols **and the backtest "
    "continued on partial data**. Every 104-symbol number before the fix was "
    "computed on it. The asymmetry is the lesson: with `trading_mode: futures` a "
    "MISSING funding/mark file CRASHES (`fail_without_data=True`), but a "
    "MALFORMED one only logs. **Assert the schema after writing and count the "
    "files back.*** |"
)

A = "| **`PerpShort4hDeploy` — THE DELIVERABLE"
B = "| **`entry_atr` fallback picks the OLDEST bar**"
C = "| 2026-09-28 | **THE CARRY LINE RE-TESTED AGAINST THE RIGHT OBJECT"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    hdr = next((i for i, l in enumerate(lines) if l.startswith("| line | state |")), -1)
    if hdr < 0:
        print("section 1 header not found")
        return 1
    lines[hdr + 2:hdr + 2] = [DEPLOY_ROW, BREAKER_ROW]
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx >= 0:
        lines[idx:idx] = [MARK_ROW]
    hit = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted deploy row, breaker trap row, mark trap row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
