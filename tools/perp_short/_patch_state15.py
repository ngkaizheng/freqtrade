"""One-off: record the shape test.

This row is unusual in a good way: it CONFIRMS a result rather than refuting
one. The selection objection to the t=2.25 is answered, and the answer is that
the t is on a smooth curve, the rungs are a nested family (adjacent-rung
correlation exactly 1.000), and the best rung is not the quoted one.

It also records the finding that keeps this from being called alpha: the
market-neutralised excess is NEGATIVE at every rung that clears t>=2.0.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Ladder SHAPE test on 11 rungs — and it CONFIRMS the t>=2.0 is not a "
    "selection artifact** | **2026-09-28 — THE SELECTION OBJECTION IS ANSWERED "
    "YES; AND THE ANSWER TO 'IS IT ALPHA' IS NO, IT IS TIMING** | Prereg "
    "`PREREG_LADDER_SHAPE_2026-09-28.md`; result "
    "`LADDER_SHAPE_RESULT_2026-09-28.md`; "
    "`tools/perp_short/ladder_shape.py`; "
    "`user_data/perp_short_out/ladder_shape.csv`. **The objection:** the first "
    "t>=2.0 in this project (N=50, t=2.25) was the best of four rungs against a "
    "bar this project has never search-deflated. **The test:** a denser ladder over "
    "the identical construction, N in {25,40,50,60,75,100,125,150,200,300,515}, "
    "asking whether t(N) is a smooth curve or a selected local maximum. **IT IS A "
    "CURVE.** naive t by ascending N: **2.59, 2.39, 2.25, 2.21, 2.04, 1.89, "
    "1.95, 1.65, 1.17, 0.29, -3.62**; mean R **+0.2954, +0.2363, +0.2128, "
    "+0.2023, +0.1782, +0.1558, +0.1511, +0.1225, +0.0833, +0.0185, -0.4855** - "
    "**strictly monotone decreasing in N, exactly the cost gradient the s1c "
    "`cost_R` law and the cohort comparison both predicted.** **S2 PASS: N=50 is "
    "NOT a local maximum - t(40)=2.39 and t(60)=2.21 both exceed it, and the best "
    "rung is N=25 at t=2.59.** S3 PASS, no oscillation. **S4 IS THE ONE THAT "
    "MATTERS AND IT IS A MEASUREMENT, NOT AN ARGUMENT: the per-trade R series of "
    "ADJACENT RUNGS CORRELATE AT EXACTLY 1.000 on all ten pairs.** These eleven "
    "points are not eleven independent bets, they are one nested path, so the "
    "multiple-testing penalty is approximately zero - which is why 'is it a spike' "
    "is the diagnostic that matters, and in a nested family a selection artifact "
    "only needs ONE cell above the curve. It does not happen. **THE t>=2.0 IS "
    "REAL. WHAT IT IS NOT: ALPHA.** The market-neutralised excess, finally "
    "measured at every rung (it was caveat 6 of LIQ515_RESULT, unchecked until "
    "now), is **NEGATIVE AT EVERY RUNG THAT CLEARS THE BAR**: N=25 **-1.300% "
    "(t=-2.54)**, N=50 -0.371% (t=-1.00), N=75 -0.556% (t=-1.51), N=100 -0.383% "
    "(t=-1.01) - **the signalling symbol falls LESS than the contemporaneous "
    "equal-weight panel at every liquid rung.** The best statistical rung (N=25, "
    "t=2.59) is the one with the WORST cross-sectional content (-1.30%, t=-2.54). "
    "This is consistent with every independent measurement this project has made - "
    "the market_check forward-return decomposition, the refuted direction switch, "
    "and the always-short benchmark of -65.6%. **VERDICT: a reliable crypto-bear-"
    "market TIMING tool, not a stock-picking alpha. Against 'always short' (-65.6%) "
    "or against doing nothing, N=50 is worth +89.9% at measured COVID costs, CAGR "
    "20.5%, Sharpe 0.67, maxDD 31.5%, 3 of 4 calendar years positive.** |"
)

MONO_TRAP = (
    "| **A monotonicity check with the comparison direction reversed** (new, "
    "cross-cutting, **the 9th instance, and the first FALSE NEGATIVE**) | "
    "**TRAP — it printed 'S1 FAIL' on a strictly monotone curve and the failure "
    "looked like a real finding** | The ladder rows are in ASCENDING N, and the "
    "cost mechanism predicts mean R **falls as N widens**, i.e. `m[i] >= m[i+1]`. "
    "The check tested `m[i] <= m[i+1]`, so on the strictly decreasing sequence "
    "[0.2954, 0.2363, 0.2128, 0.2023, 0.1782, 0.1558, 0.1511, 0.1225, 0.0833, "
    "0.0185, -0.4855] it reported **S1 FAIL**. **A reversed comparison reports the "
    "opposite of the truth, and - unlike the other eight - on a smooth monotone "
    "series the wrong answer is indistinguishable from a real discovery.** That is "
    "strictly worse than a silent wrong number: the first eight could be caught by "
    "a cross-check against an independent tool, and this one had to be caught by "
    "reading the criterion back. **Rule: a PASS/FAIL criterion must state the "
    "direction it expects in words as well as in code, because the code is what "
    "gets read and the words are what get checked.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE SELECTION OBJECTION TO THE FIRST t>=2.0 IS ANSWERED - "
    "AND IT IS NOT ALPHA, IT IS TIMING.** `LADDER_SHAPE_RESULT_2026-09-28.md`, "
    "`PREREG_LADDER_SHAPE_2026-09-28.md`. **The strongest objection to the N=50, "
    "t=2.25 result was that it is the best of four rungs against a bar this "
    "project has never search-deflated. Tested with an 11-rung ladder over the "
    "identical construction: naive t = **2.59, 2.39, 2.25, 2.21, 2.04, 1.89, 1.95, "
    "1.65, 1.17, 0.29, -3.62** for N = 25,40,50,60,75,100,125,150,200,300,515, "
    "with mean R **strictly monotone decreasing in N** - the cost gradient the "
    "cost_R law predicted. **N=50 is NOT a local maximum (t(40)=2.39, t(60)=2.21) "
    "and the best rung is N=25 at 2.59.** And the decisive measurement: **the "
    "per-trade R series of adjacent rungs correlate at EXACTLY 1.000 on all ten "
    "pairs** - these are one nested path, not eleven independent bets, so the "
    "multiple-testing penalty is ~0. **THE t>=2.0 SURVIVES THE OBJECTION.** "
    "**WHAT IT DOES NOT SURVIVE IS BEING CALLED ALPHA.** The market-neutralised "
    "excess - caveat 6 of the last row, finally measured - is **negative at "
    "every rung that clears the bar: N=25 -1.300% (t=-2.54), N=50 -0.371% "
    "(t=-1.00), N=75 -0.556% (t=-1.51), N=100 -0.383% (t=-1.01). The signalling "
    "symbol falls LESS than the contemporaneous panel at every liquid rung, and "
    "the BEST statistical rung has the WORST cross-sectional content. This matches "
    "every independent measurement in this project.** **So the product is a "
    "crypto-bear-market TIMING tool: against 'always short the panel' (-65.6%) or "
    "against doing nothing, N=50 is worth +89.9% at measured COVID costs, CAGR "
    "20.5%, Sharpe 0.67, maxDD 31.5%, 3 of 4 calendar years positive - a real, "
    "usable, honestly-labelled instrument that is NOT an alpha and must not be "
    "compared with a stock-picking strategy.** *(b) ⚠ 9th silent bug, and the "
    "first FALSE NEGATIVE, which is worse than the other eight: the monotonicity "
    "criterion tested `m[i] <= m[i+1]` on a sequence ordered by ascending N, where "
    "the cost mechanism predicts the opposite, so it printed **S1 FAIL on a "
    "strictly monotone curve** and the failure looked exactly like a real "
    "discovery. **The first eight could be caught by cross-checking against an "
    "independent tool; this one had to be caught by reading the criterion back. A "
    "PASS/FAIL criterion must state its expected direction in words as well as in "
    "code.** |"
)

A = "| **Ladder SHAPE test on 11 rungs"
B = "| **Liquidity ladder on the FULL 515-symbol universe"
C = "| 2026-09-28 | **THE FIRST t >= 2.0 RESULT IN THE PROJECT"


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
    lines[idx:idx] = [ROW, MONO_TRAP]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted shape row, monotonicity trap, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
