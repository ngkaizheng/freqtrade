"""One-off: record the walk-forward result and the 10th bug.

The 10th bug is the most important of the ten, because it is a MISSING
measurement rather than a wrong one: t_by_ts - the strictest dependence
treatment, and the one this project has always used for its verdicts - returned
nan through both the shape test and the walk-forward, so the single statistic
most diagnostic of "is this just a market bet" was never computed.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

ROW = (
    "| **Walk-forward test of the SELECTION PROCESS — the last unexamined "
    "decision** | **2026-09-28 — THE CHOICE IS WINDOW-DEPENDENT, AND UNDER THE "
    "STRICTEST DEPENDENCE TREATMENT THE EFFECT DOES NOT CARRY FORWARD "
    "(OOS by-timestamp t = 0.03)** | Prereg "
    "`PREREG_WALKFORWARD_SELECTION_2026-09-28.md`; result "
    "`WALKFORWARD_RESULT_2026-09-28.md`; "
    "`tools/{perp_short/walkforward.py,widepanel/build_wf_configs.py}`; "
    "choice written to `user_data/perp_short_out/wf_choice.json`. **WHAT WAS "
    "TESTED:** every rung of the ladder had been chosen with the whole sample in "
    "view; the shape test showed the CURVE is real but cannot show that the POINT "
    "picked off it is the one a practitioner would have picked live. This project "
    "cannot manufacture an untouched holdout, so it tested the DECISION instead: "
    "**DEVELOPMENT 2023-01 to 2024-12 may be the only data any choice uses; OOS "
    "2025-01 to 2026-08 is evaluated once.** The choice rule was frozen in the "
    "prereg (highest naive t on net R at measured_covid) and **the script writes "
    "the development ranking to disk before any OOS trade is read**, because a "
    "selection test whose selector can see the test data is not one, and the "
    "failure is invisible - you just find the OOS 'disagrees' and re-examine the "
    "rule. **THREE DIFFERENT ANSWERS: DEVELOPMENT PICKS N=25 (t=2.76), OOS's BEST "
    "IS N=40 (t=2.08), THE FULL SAMPLE PICKED N=50.** Gate **W1 selection "
    "stability FAILS** - the setting is window-dependent, so N=50 is 'an' "
    "operating point, not 'the' one. **W2 OOS sign PASSES** (N=25: mean R "
    "+0.2586, naive t 1.65, calm t 2.10). **W3 as written PASSES - and that is "
    "the finding: the prereg gated on the NAIVE t, which this project has never "
    "actually used for a verdict; the BY-TIMESTAMP t, which it has, is 0.03 on "
    "OOS and negative (-0.39 to -0.90) at every rung from 50 up. The honest "
    "reading is that W3's pass came from writing the wrong criterion into the "
    "prereg, not from the effect holding.** This is the same fact the shape test "
    "found from the other side - **naive t good, by-timestamp t ~0, and a negative "
    "market-neutralised excess** are three descriptions of one thing: the book earns "
    "by being short the WHOLE MARKET on a few timestamps, not from any sequence of "
    "independent trades. |"
)

NAN_TRAP = (
    "| **`df.set_index(idx).groupby(idx)` returns an EMPTY series** (new, "
    "cross-cutting, **the 10th instance, and the first one that is a MISSING "
    "MEASUREMENT rather than a wrong one — the most dangerous kind**) | "
    "**TRAP — the strictest dependence treatment was never computed, in two "
    "rounds, and reported as `nan`** | `idx` is a Series aligned to the frame's "
    "ORIGINAL RangeIndex; `set_index(idx)` replaces the frame's index with the "
    "timestamps, so when the same Series is then used as the groupby key, pandas "
    "aligns a RangeIndex-keyed object to a timestamp-indexed one and produces "
    "**nothing**. `tstat([])` then returns nan, and nan flows silently into the "
    "output. It hit `t_by_ts` in `ladder_shape.py` and `walkforward.py` - and "
    "**t_by_ts is the statistic this project uses for every verdict** and the one "
    "most diagnostic of 'is this just a market bet'. It was absent from the entire "
    "11-rung shape test and the entire walk-forward, and nothing errored. "
    "**Why this class is worse than the other nine: a wrong number gets argued "
    "about, a missing one just disappears.** The first nine produced a confident "
    "wrong answer; this one produced no answer at all, and a nan in a results table "
    "reads as 'not applicable' rather than 'never computed'. **Rule: treat any nan "
    "in a reported statistic as a FAILED COMPUTATION, not as an absent measurement, "
    "and assert the group count is non-zero before computing a t on it. Correct "
    "form: `df.groupby(idx)[\"R\"]`.** |"
)

CHANGE = (
    "| 2026-09-28 | **THE LAST UNEXAMINED DECISION TESTED, AND IT SAYS THE SETTING "
    "IS WINDOW-DEPENDENT AND THE EFFECT DOES NOT CARRY FORWARD UNDER THIS "
    "PROJECT'S OWN STRICTEST TEST.** `WALKFORWARD_RESULT_2026-09-28.md`, "
    "`PREREG_WALKFORWARD_SELECTION_2026-09-28.md`. **What was tested:** every "
    "rung had been chosen with the whole sample in view, and the shape test could "
    "only show the curve is real, not that the point picked off it is the one a "
    "practitioner would have picked live. No untouched holdout exists and none can "
    "be made, so the DECISION was tested instead: **DEVELOPMENT 2023-01 to 2024-12 "
    "is the only data any choice may use; OOS 2025-01 to 2026-08 is evaluated "
    "once.** The choice rule was frozen in the prereg and the script writes the "
    "development ranking to disk before reading any OOS trade. **THREE DIFFERENT "
    "ANSWERS: development picks N=25 (t=2.76), OOS's best is N=40 (t=2.08), the "
    "full sample picked N=50. W1 selection stability FAILS.** OOS sign and naive t "
    "both hold for N=25 (mean R +0.2586, naive t 1.65, calm 2.10). **BUT THE GATE "
    "THAT FIRED WAS THE WRONG ONE, AND THAT IS THE FINDING: the prereg gated on the "
    "NAIVE t, which this project has never used for a verdict; the BY-TIMESTAMP t, "
    "which it has used throughout, is 0.03 on OOS and negative at every rung from "
    "50 up (-0.39 to -0.90).** The honest reading is that W3's pass came from "
    "writing the wrong criterion into the prereg, not from the effect holding. "
    "**This is the same fact the shape test found from the other side: naive t "
    "good, by-timestamp t ~0, market-neutralised excess negative - three "
    "descriptions of one thing, namely a book that earns by being short the whole "
    "market on a few timestamps rather than from independent trades.** "
    "**Operationally the reproducible statement is not a rung but a RANGE: N=25 to "
    "N=300 is positive out of sample, only N=515 is not, so the mid-range is a more "
    "honest operating point than any single cell three different windows disagreed "
    "on.** *(b) ⚠ 10th silent bug, and the first MISSING measurement, which is worse "
    "than the nine wrong ones: **`df.set_index(idx).groupby(idx)` returns an EMPTY "
    "series** - `idx` is aligned to the original RangeIndex, `set_index` replaces "
    "the frame's index with timestamps, and pandas aligns the two to nothing. "
    "**`t_by_ts` was `nan` through the entire 11-rung shape test AND the entire "
    "walk-forward, and nothing errored.** That is the statistic this project uses "
    "for every verdict. **A wrong number gets argued about; a missing one just "
    "disappears, and a nan in a results table reads as 'not applicable' rather than "
    "'never computed'. Any nan in a reported statistic is a FAILED COMPUTATION, not "
    "an absent measurement - and assert the group count is non-zero before taking a "
    "t of it.** |"
)

A = "| **Walk-forward test of the SELECTION PROCESS"
B = "| **Ladder SHAPE test on 11 rungs"
C = "| 2026-09-28 | **THE SELECTION OBJECTION TO THE FIRST t>=2.0"


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
    lines[idx:idx] = [ROW, NAN_TRAP]
    ch = next((i for i, l in enumerate(lines) if l.startswith(C)), -1)
    if ch >= 0:
        lines[ch:ch] = [CHANGE]
    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted walk-forward row, nan trap row, change-log entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
