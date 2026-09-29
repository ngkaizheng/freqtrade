"""One-off: record the FINAL verdict on the 4h short leg, and the missing baseline.

This supersedes the CORRECTION row added earlier the same day. All three earlier
statements are left in place and marked, because the whole value of the state
file is that a later agent can see what was believed, when, and what overturned
it. The trajectory V1 -> V2 -> V3 -> V4 is the most transferable thing this
project produced about its own method.
"""
import io
import sys

P = "docs-myself/RESEARCH_STATE.md"

FINAL_ROW = (
    "| ⚠ **FINAL VERDICT 2026-09-28 (fourth revision) — IT IS NEITHER BETA NOR "
    "ALPHA. IT IS A MARKET-TIMING OVERLAY, AND THE PROJECT NEVER BUILT THE "
    "BASELINE THAT WOULD HAVE SAID SO.** | **CLOSED. Full: "
    "`VERDICT_4H_SHORT_2026-09-28.md`.** | **THE MISSING BASELINE: 'ALWAYS SHORT "
    "THE EQUAL-WEIGHT PANEL, COMPOUNDED, NO SIGNAL, NO COST' LOSES "
    "**-65.6%** over the same window (CAGR -25.4%, maxDD 88.6%, weekly Sharpe "
    "-0.33), while the 4.0-ATR strategy makes **+57.9%** - a difference of "
    "**+123.5%**. So the return is NOT harvested beta. And the panel drift is NOT "
    "a fact either: on non-overlapping 7-day windows (n=191) it is **+62.3% "
    "annualised in 2023, +12.7% in 2024, -125.6% in 2025, -73.8% in 2026**, all "
    "windows **t = -0.74**, i.e. **2 of 4 years have the opposite sign**. The "
    "earlier '-0.547% per 7 days' was a full-window average over a panel that "
    "rose in the first half. Year by year: always-short **+72.9%** in 2023 vs "
    "strategy **-40.1%**, so the strategy LOST 113pp in the year the panel "
    "rose. **What the +123.5% actually is: the strategy is short only at bars "
    "where the market then falls (forward panel return -2.123% at signal bars "
    "vs -0.523% unconditionally). And that component has NO cross-sectional "
    "part - the signalling symbol's excess over the contemporaneous panel is "
    "**-0.199% (n=5919, t=-2.21)** on all signals and **+0.449% (n=1132, "
    "t=+1.62)** on executed trades, i.e. OPPOSITE SIGNS depending on a defensible "
    "choice of population, against a market that moved -4.3% to -5.4%. The "
    "honest statement is 'indistinguishable from zero', not 'zero' and not "
    "'negative'.** **So: not alpha, not beta, a regime-dependent timing overlay "
    "- and §1d's canonical peer-reviewed test of prospective market timing "
    "(Hurst/Ooi/Pedersen 2017, JPM 44(1)) is null.** It fails S2 at every "
    "dependence treatment and S5 (2 of 4 years). **NOT a power problem: if the "
    "component were alpha, n=1,140 would be ample. Per AGENTS.md 1a this line is "
    "measured, not under-sampled.** |"
)

METHOD_ROW = (
    "| **A control group proves 'there is information', not 'what information'** "
    "(new, METHOD — the most transferable finding of 2026-09-28) | **TRAP — it "
    "produced a confident headline that had to be retracted 3 times in 12 "
    "hours** | A timing-destroyed control (same frequency, same universe, seeded "
    "in code) separates 'the entry timing carries information' from 'it carries "
    "nothing'. It CANNOT separate **(a) cross-sectional information** from "
    "**(b) market-direction information**, because a random-entry book loses "
    "under both, so the control passes either way. **Three claims in this file "
    "were made and retracted on 2026-09-28 in sequence**: (V2) 'the signal is "
    "real' - overturned because the control asked the wrong question; (V3) 'it "
    "is market beta' - overturned because **the project had never measured the "
    "baseline 'always short the panel', which LOSES 65.6%**, and the panel ROSE "
    "in 2023 (+62.3% annualised) while the strategy lost 40.1% that year; (V4) "
    "the settled one - not beta, not alpha, a regime-dependent timing overlay "
    "with a cross-sectional component indistinguishable from zero. **The missing "
    "instrument was a BENCHMARK, not a control.** **RULE: any long/short book "
    "must be reported against (i) the unconditional same-direction book and "
    "(ii) its own market-neutralised excess, before its return means anything. "
    "`tools/perp_short/beta_check.py` and `r_stats.market_excess()` now do both "
    "and print them by default.** |"
)

CHANGE = (
    "| 2026-09-28 | **FOURTH REVISION OF THE SAME CONCLUSION, AND THE ONE THAT "
    "SURVIVES: the 4h short leg is NEITHER BETA NOR ALPHA — IT IS A "
    "REGIME-DEPENDENT MARKET-TIMING OVERLAY. Closed.** "
    "`VERDICT_4H_SHORT_2026-09-28.md`, `tools/perp_short/beta_check.py`. "
    "**What finally settled it was a baseline this project had never built: "
    "'always short the equal-weight panel, compounded, no signal, no cost' "
    "LOSES -65.6%** (CAGR -25.4%, maxDD 88.6%, Sharpe -0.33) against the "
    "strategy's +57.9% — a **+123.5%** gap. So the return is not harvested beta. "
    "**And the drift is not a fact:** on non-overlapping 7-day windows (n=191) "
    "the panel is **+62.3% annualised in 2023, +12.7% in 2024, -125.6% in 2025, "
    "-73.8% in 2026, all-windows t = -0.74** — two of four years the opposite "
    "sign. The earlier '-0.547%/7 days' was a full-window average over a panel "
    "that ROSE in the first half; in 2023 always-short made **+72.9%** while the "
    "strategy lost **40.1%**. **What the +123.5% is: the strategy is short only "
    "at bars where the market then falls (panel forward -2.123% at signal bars "
    "vs -0.523% unconditional) — and that component has NO cross-sectional part: "
    "excess over the contemporaneous panel is **-0.199% (n=5919, t=-2.21)** on "
    "all signals and **+0.449% (n=1132, t=+1.62)** on executed trades, opposite "
    "signs under two defensible populations, against a -4.3%/-5.4% market move. "
    "**The defensible statement is 'indistinguishable from zero'.** It fails S2 "
    "at every dependence treatment and S5 (2/4 years), and §1d's canonical "
    "peer-reviewed test of prospective market timing (Hurst/Ooi/Pedersen 2017, "
    "JPM) is null. **Not a power problem.** **The transferable lesson, and it "
    "cost three retracted headlines in 12 hours: A CONTROL GROUP PROVES THERE IS "
    "INFORMATION, NOT WHAT INFORMATION. A timing-destroyed control cannot "
    "separate cross-sectional from directional information, because a random book "
    "loses under both. The missing instrument was a BENCHMARK.** Every long/short "
    "book in this repo must now be reported against the unconditional "
    "same-direction book AND its own market-neutralised excess, and "
    "`beta_check.py` + `r_stats.market_excess()` do both by default.** |"
)

A2 = "| ⚠ **CORRECTION 2026-09-28 (later the same day) — THE 'CONTROL-VALIDATED"
A3 = "| **~~SUPERSEDED 2026-09-28 — SEE THE CORRECTION ROW ABOVE~~**"
A4 = "| **Stop multiple (4h short) + TIMING-DESTROYED"


def main() -> int:
    with io.open(P, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if any(l.startswith("| ⚠ **FINAL VERDICT 2026-09-28") for l in lines):
        print("already present")
        return 0

    # 1. the final verdict goes at the TOP of the section-1 table
    hdr1 = next((i for i, l in enumerate(lines) if l.startswith("| line | state |")), -1)
    if hdr1 < 0:
        print("section 1 header not found")
        return 1
    lines[hdr1 + 2:hdr1 + 2] = [FINAL_ROW, METHOD_ROW]

    # 2. mark the two superseded rows
    for anchor in (A2, A3):
        for i, l in enumerate(lines):
            if l.startswith(anchor):
                lines[i] = "| **~~SUPERSEDED BY THE FINAL VERDICT ROW~~** " + l[2:]
                break

    # 3. change-log entry at the very top
    anchor = next((i for i, l in enumerate(lines)
                   if l.startswith("| 2026-09-28 | **⚠ CORRECTION TO THE")), -1)
    if anchor >= 0:
        lines[anchor:anchor] = [CHANGE]
    else:
        hdr = next((i for i, l in enumerate(lines) if l == "| date | change |"), -1)
        if hdr >= 0:
            lines[hdr + 2:hdr + 2] = [CHANGE]

    with io.open(P, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("inserted final verdict + method row + change-log entry; "
          "marked 2 superseded rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
