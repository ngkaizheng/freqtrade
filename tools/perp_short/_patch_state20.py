"""One-off: record the coincidence-sizing REJECTION and the risk-matching failure.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Coincidence-based POSITION SIZING (the last measured mechanism not yet "
    "used)** | **2026-09-29 — REJECTED. The mechanism is real; the fix makes the "
    "drawdown 33.6% WORSE, and the risk-matching premise behind the comparison "
    "was itself wrong.** | Prereg `PREREG_SIZING_COINCIDENCE_2026-09-29.md`; "
    "result `SIZING_COINCIDENCE_RESULT_2026-09-29.md`; "
    "`user_data/strategies_frontier/PerpShort4hSizing.py`; "
    "`tools/perp_short/{build_sizing_configs,sizing_compare}.py`. **THE MECHANISM "
    "IS MEASURED AND LIVE-OBSERVABLE:** at a bar where 13+ perps break down "
    "together the equal-weight panel's forward 42-bar return is **-4.678% "
    "(t=-4.61)**, roughly three times every other coincidence bucket "
    "(-1.465% at n=1 through -2.645% at n=5-7), and how many symbols signalled "
    "is countable at the signal bar. **Everything else frozen** - signal, 4.0xATR "
    "entry-bar stop, 2R target, 42-bar time stop, universe, liquidity band, costs, "
    "breaker - **and Q was the 85th percentile of the coincidence distribution "
    "(13), fixed before the run, not searched.** **RESULT AT MATCHED NOMINAL "
    "RISK, measured COVID costs:** unsized N=50 862 trades / mean R +0.2128 / "
    "t_naive 2.25 / t_by_ts 0.47 / account +89.9% / **maxDD 31.5%** / peak "
    "concurrency 17; sized N=50 **1,253 trades** / +0.1988 / 2.57 / **0.08** / "
    "+140.4% / **maxDD 42.1%** / **concurrency 24**. N=100: 1,081 / +0.1558 / 1.89 "
    "/ 0.03 / +80.3% / 33.0% / 18  ->  sized 1,706 / +0.1678 / 2.54 / **-0.06** / "
    "+168.9% / **47.1%** / **24**. **GATES: C-2 PASS, C-5 PASS, and both C-3 "
    "(peak exposure) and C-4 (the key one, max drawdown at least 20% lower) "
    "FAIL - the drawdown went the wrong way.** **⚠ AND THE RISK-MATCHING PREMISE "
    "WAS ITSELF WRONG:** the prereg required total risk to be held constant, "
    "implemented by dividing the base risk by the mean size multiplier 0.5695. "
    "**But `max_stake_frac=0.25` stopped binding at the higher base risk, so "
    "real exposure ROSE** - trades 862 -> 1,253, concurrency 17 -> 24 - and the "
    "account numbers look better for exactly that reason. **A risk-matching "
    "implementation that does not check the constraint it is matching against has "
    "not matched risk, it has added it.** |"
)

PATTERN_ROW = (
    "| **A mechanism that measures correctly can still fail as a fix — and here it "
    "has now happened THREE times** (new, METHOD, and probably this project's most "
    "transferable finding) | **PATTERN, not a trap: mechanism-correct, "
    "fix-rejected, THREE for THREE** | (1) `RegimeBreakoutExitStudy` (5m): the exit "
    "diagnosis was RIGHT - gross moved -0.0780R -> -0.0128R from changing the exit "
    "alone - and all 6 arms were still null. (2) `PerpShort4hSwitch`: the bull-market "
    "bleed was REAL and the fix made the book worse, +52.4% -> -58.7%, because the "
    "long leg the bleed needed was itself unprofitable. (3) Coincidence sizing: the "
    "13+ bucket's market move IS 3x every other bucket's, and sizing by it made "
    "maxDD 31.5% -> 42.1% because a `max_stake_frac` cap stopped binding. **In all "
    "three, an independently measured mechanism was consumed by a DIFFERENT "
    "constraint in the implementation - an exit model, a long leg, a position cap - "
    "and the resulting P&L change would have been read as a result about the "
    "mechanism if the mechanism had not been measured first.** **The discipline "
    "that pays for itself: measure the mechanism in its OWN right before embedding "
    "it, and pre-register the gate that the fix must improve the thing it was "
    "designed to fix** - C-4 here rejected a rule that improved mean R, which is "
    "the only reason this is a clean rejection rather than a second headline. |"
)

CHANGE = (
    "| 2026-09-29 | **THE LAST MEASURED MECHANISM TRIED AS A FIX, AND REJECTED BY "
    "THE GATE THAT EXISTED TO REJECT IT.** "
    "`SIZING_COINCIDENCE_RESULT_2026-09-29.md`, "
    "`PREREG_SIZING_COINCIDENCE_2026-09-29.md`. **The mechanism:** at a bar where "
    "13+ perps break down together the equal-weight panel's forward 42-bar return "
    "is **-4.678% (t=-4.61)**, ~3x every other coincidence bucket, and the count "
    "is live-observable. **The rule:** full size at 13+, half size otherwise, with "
    "Q = the 85th percentile fixed before the run and everything else frozen. "
    "**The result at measured COVID costs:** unsized N=50 862 trades / mean R "
    "+0.2128 / t_naive 2.25 / t_by_ts 0.47 / +89.9% / **maxDD 31.5%**; sized N=50 "
    "**1,253 trades** / +0.1988 / 2.57 / **0.08** / +140.4% / **maxDD 42.1%**. "
    "**C-2 and C-5 pass; C-3 (peak exposure) and C-4 (the key gate, max drawdown "
    "at least 20% lower) FAIL - the drawdown went the wrong way.** "
    "**⚠ AND THE RISK-MATCHING PREMISE WAS ITSELF WRONG:** the prereg required "
    "constant total risk, done by dividing the base risk by 0.5695 - but "
    "`max_stake_frac=0.25` stopped binding at the higher base risk, so real "
    "exposure ROSE (trades 862 -> 1,253, concurrency 17 -> 24) and the account "
    "numbers look better for exactly that reason. **A risk-matching implementation "
    "that does not check the constraint it is matching against has not matched "
    "risk, it has added it.** *(b) ⚠ And this is the third time, with the same "
    "shape: **a mechanism that measures correctly fails as a fix.** (1) the 5m exit "
    "study - the diagnosis was right and all six arms were null; (2) the direction "
    "switch - the bull-market bleed was real and the fix took the book from +52.4% "
    "to -58.7%; (3) here - the 13+ bucket's market move is 3x and sizing by it "
    "took maxDD from 31.5% to 42.1%. **In all three, an independently measured "
    "mechanism was consumed by a DIFFERENT constraint in the implementation - an "
    "exit model, a long leg, a position cap.** The two things that made these clean "
    "rejections rather than second headlines: the mechanism was measured in its own "
    "right first, and the prereg carried a gate on the thing the fix was designed "
    "to fix (C-4), which rejected a rule that IMPROVED mean R. |"
)

A = "| **Coincidence-based POSITION SIZING"
B = "| **Horizon power frontier (the last untested dimension"
C = "| 2026-09-29 | **THE VENUE VERDICT IS CORRECTED FROM BLOCKED"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith(A) for l in lines):
        print("already present")
        return 0
    idx = next((i for i, l in enumerate(lines) if l.startswith(B)), -1)
    if idx < 0:
        print("anchor row not found")
        return 1
    lines[idx:idx] = [ROW, PATTERN_ROW]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted sizing-rejection row, pattern row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
