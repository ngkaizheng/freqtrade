"""One-off: record the horizon power frontier and the deployment decision note.

The power frontier is a CLOSE, not a lead: it answers "should we try another
timeframe" once and for all, with arithmetic rather than a 30-minute backtest.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Horizon power frontier (the last untested dimension of the 4h signal)** "
    "| **2026-09-28 — CLOSED BY ARITHMETIC, NOT BY A BACKTEST. No timeframe makes "
    "this family measurable.** | `docs-myself/POWER_OPTIMUM_AND_DEPLOYMENT_2026-09-28.md`, "
    "`tools/perp_short/power_optimum.py`. **AGENTS.md 1a done before spending "
    "compute.** Two forces pull in opposite directions on the one dimension never "
    "varied: **cost favours longer bars** (`cost_R = bps/(stop_mult x atr_pct x 1e4)`, "
    "and measured atr_pct is 208.6 bps at 4h vs 495.2 at 1d, so cost_R falls "
    "**0.042R -> 0.018R**, a 57% cut); **power favours shorter bars** (trades scale "
    "as 1/horizon and t = (m/sigma) x sqrt(n), so n falling 6x costs t 2.4x). "
    "Per-trade signal-to-noise is BACK-SOLVED from the measured run, "
    "**m/sigma = 0.60/sqrt(1140) = 0.01777**, and is the only term the horizon "
    "argument can move. **Result, holding gross R constant (generous to long bars): "
    "4h t=0.89, 8h t=0.67, 16h t=0.49, 24h t=0.41 - MONOTONE DOWN.** Required mean "
    "net R for t=2.0 is **+0.404 at 4h against +0.179 available = short by 2.3x**, "
    "and the gap WIDENS to 4.9x at 1d. **4h is the best cell in the grid and it is "
    "the one already measured. There is no horizon at which this becomes "
    "measurable, and the reason is arithmetic rather than disappointment. This "
    "answers 'should we try another timeframe' permanently.** |"
)

TRAP = (
    "| **`m/sigma` back-solved as `m / (t/sqrt(n))` instead of `t/sqrt(n)`** (new, "
    "cross-cutting, and the FOURTH instance of this repo's own family in one "
    "session) | **TRAP — it printed `t = 340` and the table looked perfectly "
    "normal** | `power_optimum.py` derives the per-trade signal-to-noise from a "
    "measured (t, n). The identity is **t = (m/sigma) x sqrt(n), therefore "
    "m/sigma = t / sqrt(n)**. The first version computed `m / (t / sqrt(n))`, "
    "which is a nested division and returns ~6.8 instead of ~0.018 - a factor of "
    "380 that propagated into `t = 340` and `required effect 0.0x the measured "
    "one`, **both printed in the same well-formed, confident table as the correct "
    "rows.** It was not caught by reading; it should have been caught by noticing "
    "that 340 is not a t-statistic. **`power_optimum.py` now refuses to print a "
    "frontier unless `0 < m/sigma < 0.2` and `0 < t < 20`**, and re-derives the "
    "measured t from m/sigma and n as a printed sanity line. **This is AGENTS.md "
    "section 3's family - a comparison that silently became a different one - and "
    "it is now the fourth recorded instance in this one session, after the stale-ATR "
    "fallback, the hard-coded subset ceiling, and the `n` column collision.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE LAST UNTESTED DIMENSION OF THE 4H SIGNAL IS CLOSED BY "
    "ARITHMETIC, AND A DEPLOYMENT DECISION NOTE IS WRITTEN. "
    "`POWER_OPTIMUM_AND_DEPLOYMENT_2026-09-28.md`.** **Horizon (the one dimension "
    "never varied) fails the AGENTS.md 1a check BEFORE any backtest was run.** "
    "Cost favours longer bars and power favours shorter ones, and the trade is "
    "unfavourable: measured atr_pct 208.6 bps at 4h vs 495.2 at 1d cuts cost_R "
    "**0.042 -> 0.018**, but trades fall ~6x and t falls 2.4x. Back-solving "
    "m/sigma from the measured run gives **0.01777**; holding gross R constant "
    "(generous to long bars) the frontier is **4h t=0.89, 8h 0.67, 16h 0.49, 24h "
    "0.41 - monotone down**. Required mean net R for t=2.0 is +0.404 at 4h against "
    "+0.179 available, **short by 2.3x**, and the gap widens to 4.9x at 1d. **There "
    "is no horizon at which this family becomes measurable. 'Should we try another "
    "timeframe' is now answered permanently, for free, instead of costing 30 "
    "minutes of backtest per cell.** *(b) ⚠ AND THE SCRIPT I WROTE TO DO THIS "
    "CONTAINED THE REPO'S OWN FAMILIAR BUG: `m/sigma` was computed as "
    "`m/(t/sqrt(n))` rather than `t/sqrt(n)`, so it printed **`t = 340`** in an "
    "otherwise well-formed, confident table. 340 is not a t-statistic and it was "
    "not caught by reading. The tool now REFUSES to print unless 0 < m/sigma < 0.2 "
    "and 0 < t < 20, and re-derives the measured t as a printed sanity line. "
    "**That is the fourth instance of AGENTS.md section 3's family in one session** "
    "- after the stale-ATR fallback that capped the reference strategy's stop, the "
    "hard-coded 24-symbol ceiling that failed correct 104-symbol runs twice, and "
    "the `n` column collision that silently swapped a table's x-axis. **The lesson "
    "is not 'be careful with units'. It is that every one of these produced a "
    "table that looked completely normal, and none was caught by inspection - only "
    "by an assertion written after the fact.** *(c) The same document states the "
    "deployment position plainly for the user, who asked to make money: this is a "
    "leveraged short-timing overlay, +57.9% over 3.4y at measured COVID costs "
    "against -65.6% for always-short, 47% max drawdown, 2 of 4 calendar years "
    "negative, t = -0.15, and no cross-sectional component. It can be run, the "
    "code and three gates are green, but it must be labelled a directional timing "
    "tool and not a strategy.** |"
)

A = "| **Horizon power frontier (the last untested dimension of the 4h signal)**"


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
    lines[hdr + 2:hdr + 2] = [ROW, TRAP]

    hit = next((i for i, l in enumerate(lines)
                if l.startswith("| 2026-09-28 | **THE CARRY LINE RE-TESTED")), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    else:
        h2 = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
        if h2 >= 0:
            lines[h2 + 2:h2 + 2] = [CHANGE]

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted power-frontier row, unit-bug trap row, and change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
