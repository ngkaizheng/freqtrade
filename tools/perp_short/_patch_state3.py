"""One-off: record the liquidity-ladder result in RESEARCH_STATE.md.

The ladder is a SECOND pre-registered, pre-run negative on the same frozen
signal. It is appended-and-correct: nothing earlier is rewritten, because the
value of the state file is that a later reader can see what was believed, when,
and what overturned it.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Cost-admissible universe — liquidity ladder on the same frozen 4h short "
    "signal** | **2026-09-28 — L1 PASSES (the cost mechanism is real), L2 FAILS IN "
    "EVERY RUNG (there is no edge)** | Prereg `PREREG_LIQUIDITY_LADDER_2026-09-28.md` "
    "**frozen before any rung ran**, with the post-hoc trap stated up front: the "
    "24-symbol rung was **already positive in hand** when the design was written. "
    "Result `LIQUIDITY_LADDER_2026-09-28.md`; `tools/widepanel/build_ladder.py`, "
    "`tools/perp_short/ladder_report.py`; `user_data/perp_short_out/ladder.csv`. "
    "**Universe = top N by median per-bar quote volume** (a market property, not a "
    "P&L filter), N in {12, 24, 50, 104}, one shared datadir so only the whitelist "
    "changes, and **`max_open_trades` pinned to the rung size** so concurrency "
    "cannot float with `len(pairlist)`. Panel liquidity spread is **16x** "
    "(top-24 median $20.3M/bar vs bottom-54 $1.29M/bar, thinnest $700K). "
    "**MEAN NET R, AND IT IS MONOTONE IN ALL FOUR REGIMES:** engine-default "
    "**+0.167 / +0.154 / +0.103 / +0.086** -> calm **+0.123 / +0.113 / +0.065 / "
    "+0.051** -> volatile **+0.083 / +0.076 / +0.030 / +0.019** -> **covid "
    "+0.037 / +0.034 / −0.008 / −0.017**. **That is gate L1 passing, and it is a "
    "statement about COST, not about the signal: widening the universe does not "
    "make the edge worse, it makes the edge more expensive to collect.** "
    "**L2 FAILS EVERYWHERE** - dependence-adjusted t >= 2.0 is reached in no rung "
    "at no cost regime; the largest value is **+1.05** (N=104, engine-default, i.e. "
    "with slippage assumed away) and at measured_covid the **by-timestamp t is "
    "NEGATIVE in three of four rungs** (-0.77 / -0.59 / -0.43 / -0.12). "
    "**The one thing worth carrying forward: N=12 is the only configuration in the "
    "whole project that is positive at EVERY cost regime (+0.037 at covid) and "
    "positive in 3 of 4 calendar years (2023 +0.114, 2024 +0.146, 2025 +0.068, 2026 "
    "-0.241), with 50-67% of symbols individually positive. It is still NOT "
    "significant (t = -0.77 by-timestamp, +0.28 by-week) and the prereg calls it a "
    "lead, never a confirmation.** The only thing that would change this is "
    "**measuring the real round trip on those 12 contracts with bookDepth**, not "
    "another backtest - at 12 bps the +0.037R stands up, at 35 bps it is noise "
    "like every other rung. **LINE CLOSED.** |"
)

CHANGE = (
    "| 2026-09-28 | **SECOND PRE-REGISTERED NEGATIVE ON THE SAME FROZEN SIGNAL: A "
    "LIQUIDITY LADDER. The cost mechanism is real; the edge is not.** Prereg "
    "`PREREG_LIQUIDITY_LADDER_2026-09-28.md` (frozen before any rung, with the "
    "post-hoc trap stated in §0 of it: the 24-symbol rung was already positive in "
    "hand). Result `LIQUIDITY_LADDER_2026-09-28.md`. **THE LADDER IS MONOTONE IN "
    "EVERY COST REGIME**: mean net R at engine-default **+0.167 / +0.154 / +0.103 "
    "/ +0.086** for N = 12 / 24 / 50 / 104, and at **measured_covid +0.037 / "
    "+0.034 / −0.008 / −0.017**. Widening the universe does not degrade the signal, "
    "it raises the price of collecting it — which is exactly what §1b's depth data "
    "(the long tail is 1-3 orders of magnitude thinner) and §1c's `cost_R` law "
    "predict, now confirmed end-to-end in the engine. **But t >= 2.0 is reached in "
    "no rung at no cost regime** (best +1.05, and that is with slippage assumed "
    "away); at measured_covid the by-timestamp t is **negative in three of four** "
    "rungs. **The one carry-forward: N=12 is the only configuration in this project "
    "positive at every cost regime and in 3 of 4 calendar years, and it is still "
    "not significant (t = -0.77).** The next action on it is a **bookDepth "
    "measurement of those 12 contracts, not a backtest.** Also caught here: "
    "`r_stats.report()` returns a field named `n` meaning TRADE COUNT, and merging "
    "it under the same key as the rung size **silently turned the ladder's x-axis "
    "from rung size into trade count (12/24/50/104 rendered as 436/658/867/1106) "
    "while the table still looked perfectly normal** — the §3 family again, reached "
    "through two different things sharing one name. |"
)

TRAP_ROW = (
    "| **Two different quantities named `n`** (new, cross-cutting) | **TRAP — it "
    "silently swapped a table's x-axis and the table still looked fine** | "
    "`tools/perp_short/r_stats.report()` returns `\"n\": <trade count>`. The ladder "
    "report merged that dict under the same key as the **rung size**, so the pivot "
    "was indexed 436 / 658 / 867 / 1,106 instead of 12 / 24 / 50 / 104. The output "
    "was a well-formed, plausible, **completely wrong** table, and the gate loop "
    "below it then matched nothing and printed an empty section. Renamed to "
    "`n_trades` on merge. This is §3's family (a comparison that silently became a "
    "different one) reached through **two different quantities sharing one name** — "
    "the same shape as §3.32b's 'one signal, several values, several bases'. |"
)


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")

    if any("Cost-admissible universe" in l for l in lines):
        print("already present")
        return 0

    idx = next((i for i, l in enumerate(lines)
                if l.startswith("| **`PerpShort4h`**")), -1)
    if idx < 0:
        print("anchor row not found")
        return 1
    lines[idx:idx] = [ROW]

    trap_idx = next((i for i, l in enumerate(lines)
                     if l.startswith("| **A `custom_stoploss` stop exports")), -1)
    if trap_idx >= 0:
        lines[trap_idx + 1:trap_idx + 1] = [TRAP_ROW]

    hdr = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
    if hdr >= 0:
        lines[hdr + 2:hdr + 2] = [CHANGE]

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted ladder row, trap row, and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
