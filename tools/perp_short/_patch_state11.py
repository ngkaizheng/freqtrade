"""One-off: record the direction-switch refutation and the short-only-replay bug.

Two entries:
  * the REFUTED direction switch (a closed line, with its gate table), and
  * the 6th instance of this session's bug family - a hard-coded direction
    assumption in the cost-replay tool that was wrong by 7x on a two-sided book.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

SWITCH_ROW = (
    "| **Direction switch (long/short by the panel's own 200-bar SMA)** | "
    "**2026-09-28 — PRE-REGISTERED AND REFUTED ON EVERY GATE, INCLUDING THE ONE "
    "THAT MOTIVATED IT. The short-only book stands unchanged.** | Prereg "
    "`PREREG_DIRECTION_SWITCH_2026-09-28.md` (frozen before the run, and it "
    "**declares itself post-hoc** - the 2023 loss was known before it was "
    "written); result `DIRECTION_SWITCH_RESULT_2026-09-28.md`; "
    "`user_data/strategies/PerpShort4hSwitch.py`, "
    "`tools/perp_short/make_regime.py`. **Why, and this is a genuine reopening "
    "under the charter's 2.A.4 test for structural change:** the delivered book "
    "is STRUCTURALLY SHORT-ONLY, and in 2023 - the year the panel rose +50.7% - "
    "it returned **-40.5%**. A user running it through a bull market bleeds for "
    "quarters, and that is a defect in the product, not a market risk to accept. "
    "**THE REGIME ITSELF WORKS, AND THE DIAGNOSTIC PREDICTED THE OUTCOME BEFORE "
    "THE STRATEGY RAN** (`make_regime.py`, forward 7-bar return: up-regime "
    "**+0.011%, t = +0.15**; down-regime **-0.232%, t = -4.08**). The "
    "separation is real but **asymmetric - the down-regime is strong and the "
    "up-regime is statistically zero**, which already forecasts that a long leg "
    "adds cost without edge. **IT DID.** Adding 1,223 long trades to 958 shorts "
    "moved the book from **+52.4% to -58.7%** at measured COVID costs, CAGR "
    "13.0% to -22.7%, maxDD 47.2% to **66.3%**, PF 1.10 to **0.85**. Year by "
    "year: 2023 **-44.5% (WORSE than the -40.5% it was built to fix, so T1 "
    "FAILS)**, 2024 **-26.0%** (T2 FAILS), 2025 +23.2% (T2 FAILS), 2026 -20.3%. "
    "**All six gates fail.** **The long leg is swept and comes back: 30.2% of "
    "stopped-out trades were ultimately winners** - a 4xATR stop in a choppy "
    "long market. This CORROBORATES `WIDE_PANEL_RESULT_2026-09-28` section 3 "
    "(the long leg negative in all 12 cells and 3 cost regimes) with a "
    "completely independent implementation. **The delivered book is unchanged and "
    "its numbers are unchanged; `PerpShort4hSwitch` is kept as a reproducible "
    "REFUTATION, not a candidate.** |"
)

REPLAY_TRAP = (
    "| **The cost-replay tool hard-coded SHORT and was wrong by 7x on a two-sided "
    "book** (new, cross-cutting, **the 6th instance of this session's family, and "
    "the first inside the ANALYSIS rather than the strategy**) | **TRAP — the "
    "engine said -31.23% and the replay said +208.8% on the SAME 2,181 trades** | "
    "`cost_frontier.replay` computed `gross = (entry - close) * qty` with no "
    "reference to direction. Correct for a short; **the exact negative of the "
    "truth for a long**, so a losing long was booked as a winning one. Every "
    "number this repo reported before 2026-09-28 was safe by ACCIDENT - the "
    "delivered strategy is short-only, so the assumption was never tested. "
    "`PerpShort4hSwitch` was the first two-sided book and the first failure. "
    "**Fixed to read `is_short` from the export, and the tool now prints the "
    "long/short split so a reader can see which book it scored. Verified by "
    "regression: the short-only book returns identical numbers (gross +161.1%, "
    "engine +131.6%, COVID +52.4%, maxDD 47.2%).** **The general rule: a "
    "hard-coded direction, sign, or convention in an analysis tool is untested "
    "until the first input violates it, and the violation shows up as a "
    "DISAGREEMENT BETWEEN TWO TOOLS, not as an error in either.** |"
)

CHANGE = (
    "| 2026-09-28 | **DIRECTION SWITCH PRE-REGISTERED AND REFUTED; AND THE 6TH "
    "SILENT BUG OF THE SESSION, THIS TIME INSIDE THE ANALYSIS.** "
    "`DIRECTION_SWITCH_RESULT_2026-09-28.md`. *(a) **WHY THIS WAS WORTH "
    "REOPENING A CLOSED LINE:** the delivered book is structurally SHORT-ONLY and "
    "returned **-40.5% in 2023, the year the panel rose +50.7%**. The prereg "
    "declares itself post-hoc and the charter's structural-change test is met - "
    "same signal, same stop, same target, same sizing; only the DIRECTION "
    "varies, by a regime rule frozen in advance (panel close vs its own 200-bar "
    "SMA, not searched). **The regime diagnostic predicted the answer BEFORE the "
    "strategy ran**: up-regime forward 7d **+0.011% (t = +0.15)**, down-regime "
    "**-0.232% (t = -4.08)** - real separation, but **asymmetric, with the long "
    "side statistically zero**. Adding 1,223 longs to 958 shorts moved the book "
    "from **+52.4% to -58.7%** at measured COVID costs, maxDD 47.2% -> **66.3%**, "
    "PF 1.10 -> **0.85**, and **2023 got WORSE (-44.5%) rather than better**. "
    "**All six gates fail, including T1 - the one that motivated the design.** "
    "30.2% of stopped-out longs ultimately won, i.e. a 4xATR stop was being "
    "swept repeatedly in a choppy long market; this independently corroborates "
    "`WIDE_PANEL_RESULT_2026-09-28` s3 that the long leg is negative in all 12 "
    "cells. **The delivered book is unchanged; `PerpShort4hSwitch` is retained "
    "as a reproducible REFUTATION.** *(b) ⚠ AND THE WAY IT WAS CAUGHT IS THE "
    "LESSON: **the engine said -31.23% and `cost_frontier.replay` said +208.8% "
    "on the SAME 2,181 trades - a 7x disagreement.** `replay` computed "
    "`gross = (entry - close) * qty` with no reference to direction, so every "
    "long was booked with the wrong sign. **Every number this repo reported "
    "before today was safe by ACCIDENT, because the delivered strategy is "
    "short-only; the first two-sided book was the first test of that "
    "assumption.** Fixed to read `is_short`, now prints the long/short split, "
    "and verified by regression against the short-only book (identical numbers). "
    "**A hard-coded sign in an analysis tool is untested until the first input "
    "violates it, and the violation appears as a disagreement between two tools "
    "rather than an error in either. That is now SIX silent bugs this session, "
    "every one caught by an assertion or a cross-check, never by reading.** "
    "*(c) Charter compliance, recorded so it is not quietly lost: **there is NO "
    "untouched holdout in this project** (`binance_v2/"
    "FINAL_HOLDOUT_DO_NOT_TOUCH.json` records `unblinded: 2026-09-26T01:42:43`, "
    "burned), so nothing produced today has out-of-sample confirmation; and the "
    "freqtrade dry-run that was started is an **EXECUTION SMOKE TEST "
    "(RESEARCH_GOAL 2.F.3), not the reward for a passing candidate** - no real "
    "credentials, no real orders, no real funds were used. |"
)

A = "| **Direction switch (long/short by the panel's own 200-bar SMA)**"
B = "| **A drawdown circuit breaker that fails OPEN, silently"
C = "| 2026-09-28 | **THE DELIVERABLE BUILT, AND THE MOST DANGEROUS BUG OF THE"


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
    lines[hdr + 2:hdr + 2] = [SWITCH_ROW, REPLAY_TRAP]
    hit = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if hit >= 0:
        lines[hit:hit] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted switch-refutation row, replay trap row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
