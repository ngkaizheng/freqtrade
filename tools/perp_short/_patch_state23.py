"""One-off: record HOW_TO_RUN as the single current page, and the warmup
reachability check that would otherwise have been a 12th silent no-op.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **`HOW_TO_RUN_2026-09-29.md` — the single current, actionable page** | "
    "**2026-09-29 — written because after 17 rounds the repository contains 20+ "
    "documents that CONTRADICT EACH OTHER ON PURPOSE (they are a timeline, not a "
    "manual), and a reader picking one at random would deploy the RETRACTED "
    "104-symbol version** | `HOW_TO_RUN_2026-09-29.md`; supersedes the operational "
    "content of `DEPLOYABLE_4H_SHORT_2026-09-28.md`, whose header now points at "
    "it. **It states, in one place and without hedging: the three settings to copy "
    "(universe = top 40 of 515 by median quote volume; whitelist ordered by "
    "LIQUIDITY, which is a decision and not formatting; risk 0.5% per trade for a "
    "12% portfolio budget), the measured-cost performance, the three ways it "
    "kills you (a bull market, a cascade costing ~27% of the account at the worst "
    "moment, and the absence of out-of-sample confirmation), and the three gates "
    "that check implementation fidelity but say NOTHING about whether the signal "
    "is alpha. It also says plainly what the strategy IS - a market-timing tool "
    "with no cross-sectional edge, the triggering symbols falling LESS than the "
    "panel - so it cannot be misread as a stock-picker. |"
)

WARMUP_ROW = (
    "| **A 4h strategy with `startup_candle_count=420` needs 70 days of history "
    "that the live API may not serve — and would then run for YEARS without a "
    "single signal** (new, cross-cutting) | **TRAP — ruled out here by "
    "measurement, not by assumption** | A forward collector on a 4h timeframe "
    "needs **420 bars = 1,680 hours = 70 days** of warm-up before the first "
    "indicator is defined. **If the exchange will not serve that far back, the "
    "collector runs happily for the 6.8 years this project requires, emits a "
    "heartbeat every 60 seconds, and produces ZERO signals — with no error and no "
    "warning.** It is the STOPPED-heartbeat trap one level further out: the thing "
    "that would hide it is not a wrong number but the ABSENCE of any number. "
    "Measured: Binance returns **12,000** 4h bars going back for BTCUSDT, so 420 is "
    "comfortably reachable, and `verify_collector.py` now asserts it on every run "
    "rather than trusting it once. **A collector must be checked for whether it "
    "CAN produce its first record before it is credited with running.** |"
)

CHANGE = (
    "| 2026-09-29 | **AFTER 17 ROUNDS THE REPO HAD 20+ CONTRADICTING DOCUMENTS AND "
    "NO SINGLE PAGE YOU COULD ACT ON; AND THE COLLECTOR'S WARM-UP WAS FOUND TO BE "
    "A QUESTION, NOT AN ASSUMPTION.** `HOW_TO_RUN_2026-09-29.md`. **A research "
    "repository is a TIMELINE, not a manual** - the 104-symbol deployment, the "
    "retraction, the 515-symbol widening, the N=40 choice and the collector are all "
    "correct at the moment they were written and wrong now, and a reader opening "
    "a random one would deploy a RETRACTED configuration. **One page now states "
    "the three settings to copy (top 40 of 515 by median quote volume, whitelist "
    "ORDERED BY LIQUIDITY, 0.5% per trade), the measured-cost performance, the "
    "three ways it kills you, and the three gates that check implementation "
    "fidelity while saying nothing about alpha.** *(b) ⚠ And a 12th silent no-op "
    "was caught before it could become a 6.8-year one: **a 4h strategy with "
    "`startup_candle_count=420` needs 70 days of history before its first indicator "
    "exists.** If the live API will not serve that far back, the collector runs "
    "for the whole 6.8 years this project needs, heartbeats every minute, and "
    "emits ZERO signals - no error, no warning. **That is the STOPPED-heartbeat "
    "trap one level further out: what would hide it is the ABSENCE of a number, "
    "not a wrong one.** Measured Binance serves 12,000 4h bars back for BTCUSDT, "
    "so it is ruled out - by measurement, and `verify_collector.py` now asserts it "
    "on every run. **A collector must be shown to be able to produce its first "
    "record before it is credited with running.** |"
)

A = "| **`HOW_TO_RUN_2026-09-29.md`"
B = "| **Which rung to actually run"
C = "| 2026-09-29 | **THE OPERATING POINT IS NOW CHOSEN BY A RULE"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx < 0:
        print("anchor not found")
        return 1
    lines[idx:idx] = [ROW, WARMUP_ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted HOW_TO_RUN row, warmup trap row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
